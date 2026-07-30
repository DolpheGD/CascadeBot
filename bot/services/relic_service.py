"""
Run-scoped relic state: what the player is holding this expedition, and
how it gets applied when a battle is built.

Storage note: relics live on Expedition.relics, a JSON column that has
existed (unused, alongside temp_buffs/temp_curses/gold_collected) since
the expedition model was first written. Reusing it means no migration --
and because the column defaults to an empty list, an expedition already in
flight when this shipped simply has no relics rather than breaking.

Like every other JSON column in this project, `relics` is REASSIGNED
wholesale rather than mutated in place -- SQLAlchemy doesn't detect
in-place mutation of a plain JSON column, so `expedition.relics.append(x)`
would silently fail to persist. See _mark_completed in dungeon_service for
the same hazard on `graph`.

Effects are applied in apply_relic_effects, called from
combat_service.start_battle immediately after apply_shrine_bonuses --
relics are conceptually the run-scoped sibling of shrines (party-wide,
applied at build time, never persisted onto the Combatant), so they live
in the same seam.
"""

from __future__ import annotations

import random

from bot.game.combat.combatant import STAT_KEYS
from bot.game.dungeon.relic_config import (
    OFFER_SIZE,
    get_relic,
    roll_offer,
)
from bot.utils.logger import get_logger

logger = get_logger("relics")


# ----------------------------------------------------------------------
# Held relics
# ----------------------------------------------------------------------

def held_ids(expedition) -> list[str]:
    return list(expedition.relics or [])


def held_relics(expedition) -> list[dict]:
    """The full catalog entry for every relic held this run. Silently
    skips ids that no longer exist in the catalog, so removing or renaming
    a relic can never break an expedition that's already carrying it."""
    relics = []
    for relic_id in held_ids(expedition):
        relic = get_relic(relic_id)
        if relic is None:
            logger.warning("Expedition %s holds unknown relic %r -- ignoring", expedition.id, relic_id)
            continue
        relics.append(relic)
    return relics


def grant_relic(db, expedition, relic_id: str) -> dict | None:
    """Adds a relic to the run. Returns the catalog entry, or None if the
    id is unknown or already held (relics never stack -- the offer already
    excludes duplicates, this is the belt-and-braces check)."""
    relic = get_relic(relic_id)
    if relic is None:
        return None
    current = held_ids(expedition)
    if relic_id in current:
        return None

    expedition.relics = current + [relic_id]  # reassign, never append -- see module docstring
    db.commit()
    return relic


def offer_relics(expedition, rng: random.Random | None = None, size: int = OFFER_SIZE) -> list[dict]:
    """`size` distinct relics to choose between, excluding anything
    already held this run."""
    rng = rng or random.Random()
    return roll_offer(rng, exclude_ids=set(held_ids(expedition)), size=size)


def grant_random_relic(db, expedition, rng: random.Random | None = None) -> dict | None:
    """Grants ONE weighted-random relic outright, no choice offered -- the
    boss-clear and elite-victory drop path. Returns the relic, or None if
    the player somehow already holds the entire catalog."""
    offer = offer_relics(expedition, rng=rng, size=1)
    if not offer:
        return None
    return grant_relic(db, expedition, offer[0]["id"])


# ----------------------------------------------------------------------
# Effects
# ----------------------------------------------------------------------

def gold_multiplier(expedition) -> float:
    """Combined multiplier from every gold_multiplier relic held, as a
    plain factor (1.0 = unchanged). Additive between relics rather than
    multiplicative, so two +30% relics are +60% and not +69% -- same
    convention gear percent substats use."""
    bonus = 0.0
    for relic in held_relics(expedition):
        for effect in _flatten(relic["effect"]):
            if effect["kind"] == "gold_multiplier":
                bonus += effect["percent"]
    return 1.0 + bonus / 100


def bonus_poise_damage(expedition) -> int:
    """Extra poise chipped per landed hit from poise_damage relics."""
    total = 0
    for relic in held_relics(expedition):
        for effect in _flatten(relic["effect"]):
            if effect["kind"] == "poise_damage":
                total += int(effect["bonus"])
    return total


def apply_relic_effects(expedition, combatants: list) -> None:
    """Mutates each PLAYER combatant in place with every held relic's
    effect. Called from combat_service.start_battle right after
    apply_shrine_bonuses.

    Percent stat bonuses are computed against each combatant's own value
    at the moment this runs -- which is post-gear and post-shrine -- and
    added as a flat amount, so relics never compound with each other. Same
    rule gear substats and shrines already follow.

    max_hp/max_mana changes are mirrored onto the Combatant's separate
    max_hp/max_mana/current_hp/mana attributes, exactly as
    apply_shrine_bonuses has to, or an HP relic would show in the UI
    without doing anything in the fight. A combatant already at full HP is
    topped up to the new maximum rather than starting the fight at a
    fraction of it -- taking a +max HP relic should feel like a heal, not
    like being handed a bigger empty bar.
    """
    if expedition is None:
        return
    relics = held_relics(expedition)
    if not relics:
        return

    players = [c for c in combatants if c.is_player]
    if not players:
        return

    from bot.game.loot.abilities import ARMOR_PASSIVES, get_ability_by_id

    for relic in relics:
        for effect in _flatten(relic["effect"]):
            kind = effect["kind"]

            if kind == "stat" and effect["stat"] in STAT_KEYS:
                for c in players:
                    was_full_hp = c.current_hp >= c.max_hp
                    c.base_stats[effect["stat"]] = (
                        c.base_stats.get(effect["stat"], 0)
                        * (1 + effect["percent"] / 100)
                    )
                    _sync_pools(c, was_full_hp)

            elif kind == "stat_flat" and effect["stat"] in STAT_KEYS:
                for c in players:
                    was_full_hp = c.current_hp >= c.max_hp
                    c.base_stats[effect["stat"]] = (
                        c.base_stats.get(effect["stat"], 0) + effect["amount"]
                    )
                    _sync_pools(c, was_full_hp)

            elif kind == "passive":
                try:
                    ability = get_ability_by_id(ARMOR_PASSIVES, effect["passive_id"])
                except KeyError:
                    # A relic pointing at a passive that's since been
                    # renamed shouldn't take a live battle down with it --
                    # log it and hand out nothing.
                    logger.warning(
                        "Relic %r references unknown passive %r", relic["id"], effect["passive_id"]
                    )
                    continue
                for c in players:
                    # Don't double up if the character already has this
                    # passive from gear -- most passive kinds stack
                    # additively and a duplicate would quietly double a
                    # relic's value for one character and not another.
                    if any(p["id"] == ability["id"] for p in c.passive_abilities):
                        continue
                    granted = dict(ability)
                    granted["source"] = "relic"
                    c.passive_abilities.append(granted)

            elif kind == "poise_damage":
                # Baked onto the Combatant so effects.py never has to know
                # what an expedition is, and so it survives serialization
                # with the rest of the battle.
                for c in players:
                    c.bonus_poise_damage += int(effect["bonus"])

            # gold_multiplier is read by dungeon_service when awarding run
            # gold rather than baked onto a Combatant -- it never applies
            # during a fight.


def _flatten(effect: dict) -> list[dict]:
    """Unwraps a "multi" effect into its parts; everything else is a
    single-element list, so callers can treat every relic uniformly."""
    if effect.get("kind") == "multi":
        return list(effect["effects"])
    return [effect]


def _sync_pools(combatant, was_full_hp: bool) -> None:
    """Keeps the Combatant's separate max_hp/max_mana (and the current
    values clamped to them) in step with base_stats after a relic changed
    the underlying stat."""
    if "max_hp" in combatant.base_stats:
        combatant.max_hp = max(1, round(combatant.base_stats["max_hp"]))
        if was_full_hp:
            combatant.current_hp = combatant.max_hp
        else:
            combatant.current_hp = min(combatant.current_hp, combatant.max_hp)
    if "max_mana" in combatant.base_stats:
        combatant.max_mana = max(0, round(combatant.base_stats["max_mana"]))
        combatant.mana = min(combatant.mana, combatant.max_mana)
