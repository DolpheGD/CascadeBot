"""
Domains: a regenerating energy resource (Player.domain_energy /
domain_energy_updated_at) spent on single-battle "domain challenge"
fights against a fixed enemy squad (bot/game/economy/domain_config.py)
for direct, on-demand rewards without running a full expedition.

Energy regen math: point-based (whole energy, not a continuous rate the
way harvesters accrue), so the anchor (domain_energy_updated_at) must
advance by EXACT WHOLE INTERVALS consumed, not jump to "now" on every
read/sync -- otherwise partial progress toward the next point would be
silently lost every time energy is checked. See _sync_energy for the one
place this is actually mutated; get_current_energy is a pure read-only
projection safe to call anywhere for display, with no side effects.

A subtler bug this guards against: if energy sits at the cap for a long
stretch (the anchor goes untouched, since get_current_energy
short-circuits without even looking at it while capped) and is then
spent down below the cap, the anchor MUST be reset to "now" as part of
that spend -- otherwise the very next read would see a huge elapsed time
against a stale, days-old anchor and instantly grant a bogus refill back
up to full. _sync_energy always normalizes the anchor to "now" whenever
the result comes out at/above the cap, precisely to prevent that.

Battle persistence: unlike expedition combat (Expedition.combat_state,
which survives a bot restart or a player vanishing for a week -- see
combat_service.py's module docstring), an in-progress domain battle is
held ONLY in memory (_ACTIVE_BATTLES below), not the database. This is a
deliberate simplification appropriate to what a domain challenge actually
is -- one short, self-contained fight, not a persistent multi-day run --
and avoids overloading the Expedition table (modeled around dungeon
floors/node graphs that don't apply here) with a second, unrelated flow
just to get JSON persistence. The trade-off: a bot restart mid-domain-
fight loses that specific attempt, and the energy already spent on it is
not refunded. Given the affected surface is one quick battle rather than
hours of dungeon progress, this was judged an acceptable trade against
adding a new table for it.
"""

from __future__ import annotations

import datetime as dt

from bot.game.combat.battle import Battle
from bot.game.combat.enemies import get_template_by_name
from bot.game.combat.factory import build_enemy_combatant, build_party_combatants
from bot.game.economy.domain_config import (
    DOMAIN_DIFFICULTY_TIERS,
    ENERGY_REGEN_MINUTES_PER_POINT,
    max_domain_energy,
    enemy_level_for,
    get_domain_type,
    get_tier,
)
from bot.services import base_service, character_service, combat_service, lootbox_service
from bot.services.currency_service import add_currency
from bot.utils.time_utils import as_utc

# player_id -> Battle. See module docstring for why this is in-memory only.
_ACTIVE_BATTLES: dict[int, Battle] = {}
# player_id -> (domain_id, tier_id) -- so a win/loss can grant the right
# reward without needing to smuggle extra state through Battle itself.
_ACTIVE_CHALLENGE: dict[int, tuple[str, str]] = {}


class DomainChallengeError(Exception):
    """Raised for any reason a challenge can't start or resolve -- not
    enough energy, level too low, unknown domain/tier, no squad, or
    already mid-challenge. Message is written to be shown to the player
    as-is."""


def energy_cap(db, player) -> int:
    """This player's current energy ceiling, from their Cascade HQ level
    (see domain_config.DOMAIN_ENERGY_BY_HQ_LEVEL). Looked up rather than
    stored so an HQ upgrade takes effect immediately with nothing to
    migrate."""
    from bot.services import base_service, research_service
    base = max_domain_energy(base_service.get_hq_level(db, player))
    # Research Lab's Expansion branch raises the ceiling further.
    return base + int(research_service.perk_value(db, player.id, "domain_energy"))


def get_current_energy(db, player) -> int:
    """Read-only projection of current energy including any regen since
    domain_energy_updated_at -- does NOT write to the DB, safe to call
    anywhere just for display."""
    cap = energy_cap(db, player)
    if player.domain_energy >= cap:
        return cap
    now = dt.datetime.now(dt.timezone.utc)
    last = as_utc(player.domain_energy_updated_at)
    elapsed_minutes = (now - last).total_seconds() / 60
    points_gained = int(elapsed_minutes // ENERGY_REGEN_MINUTES_PER_POINT)
    return min(cap, player.domain_energy + points_gained)


def time_until_next_energy_point(db, player) -> dt.timedelta | None:
    """None if already at the cap. Otherwise how long until the next
    single point of energy regenerates."""
    if get_current_energy(db, player) >= energy_cap(db, player):
        return None
    now = dt.datetime.now(dt.timezone.utc)
    last = as_utc(player.domain_energy_updated_at)
    interval = dt.timedelta(minutes=ENERGY_REGEN_MINUTES_PER_POINT)
    elapsed = now - last
    remainder = elapsed - (elapsed // interval) * interval
    return interval - remainder


def _sync_energy(db, player) -> None:
    """Mutates player.domain_energy/domain_energy_updated_at in place to
    reflect regen since the last sync. ALWAYS normalizes the anchor to
    "now" whenever the result is at/above the cap (even if the stored
    value didn't need to change), so a later partial spend never inherits
    a stale anchor -- see module docstring. Caller is responsible for
    committing."""
    now = dt.datetime.now(dt.timezone.utc)
    last = as_utc(player.domain_energy_updated_at)
    cap = energy_cap(db, player)

    # Also clamps DOWN: nothing stops a player from banking energy at a
    # high cap, and the cap only ever rises, but clamping here keeps the
    # invariant true regardless.
    if player.domain_energy >= cap:
        player.domain_energy = cap
        player.domain_energy_updated_at = now
        return

    elapsed_minutes = (now - last).total_seconds() / 60
    points_gained = int(elapsed_minutes // ENERGY_REGEN_MINUTES_PER_POINT)
    if points_gained <= 0:
        return

    player.domain_energy = min(cap, player.domain_energy + points_gained)
    if player.domain_energy >= cap:
        player.domain_energy_updated_at = now
    else:
        player.domain_energy_updated_at = last + dt.timedelta(
            minutes=points_gained * ENERGY_REGEN_MINUTES_PER_POINT
        )


# ----------------------------------------------------------------------
# Unlocks (reworked -- see domain_config's UNLOCK block)
#
# A tier opens on TWO axes at once: a region that must have been fully
# cleared ("stage beaten") and a minimum sum of every owned character's
# level ("total character levels"). Player.level -- the old gate -- is no
# longer consulted anywhere in this module.
# ----------------------------------------------------------------------

def roster_total_levels(db, player) -> int:
    """Sum of every owned PlayerCharacter's level. This is the "total
    character levels" unlock axis: it only ever goes up, it can't be
    gamed by swapping the squad around right before a challenge, and it
    reflects real investment across the account rather than the single
    number Player.level was."""
    from bot.database.models.character_model import PlayerCharacter

    levels = db.query(PlayerCharacter.level).filter_by(player_id=player.id).all()
    return sum(level for (level,) in levels)


def average_squad_level(db, player) -> float:
    """Mean character level of the squad that would actually enter a
    fight right now -- the input to domain_config.enemy_level_for, so
    domain enemies scale to the party instead of a hardcoded level."""
    squad = character_service.get_squad(db, player)
    if not squad:
        return 1.0
    return sum(pc.level for pc in squad) / len(squad)


def tier_lock_reason(db, player, tier: dict) -> str | None:
    """None if `tier` is unlocked, else a short player-facing reason it
    isn't. Region requirement is reported first when both fail -- it's
    the one the player can act on most directly."""
    from bot.services import dungeon_service

    required_region = tier.get("required_region")
    if required_region and not dungeon_service.has_completed_region(db, player.id, required_region):
        return f"Clear {required_region}"

    required_levels = tier.get("min_roster_levels", 0)
    if required_levels:
        total = roster_total_levels(db, player)
        if total < required_levels:
            return f"{total}/{required_levels} total character levels"

    return None


def is_tier_unlocked(db, player, tier: dict) -> bool:
    return tier_lock_reason(db, player, tier) is None


def get_available_tiers(db, player) -> list[dict]:
    """Every difficulty tier the player has actually unlocked -- see
    domain_config.DOMAIN_DIFFICULTY_TIERS. The first tier has no
    requirements at all, so this is never empty."""
    return [t for t in DOMAIN_DIFFICULTY_TIERS if is_tier_unlocked(db, player, t)]


def has_active_challenge(player_id: int) -> bool:
    return player_id in _ACTIVE_BATTLES


def get_active_battle(player_id: int) -> Battle | None:
    return _ACTIVE_BATTLES.get(player_id)


def start_challenge(db, player, domain_id: str, tier_id: str) -> Battle:
    """Spends energy and starts a new domain battle, held in memory (see
    module docstring). Raises DomainChallengeError for any reason it
    can't proceed."""
    if player.id in _ACTIVE_BATTLES:
        raise DomainChallengeError("You're already in the middle of a domain challenge.")

    domain = get_domain_type(domain_id)
    if domain is None:
        raise DomainChallengeError("No such domain.")
    tier = get_tier(tier_id)
    if tier is None:
        raise DomainChallengeError("No such difficulty tier.")
    lock_reason = tier_lock_reason(db, player, tier)
    if lock_reason is not None:
        raise DomainChallengeError(f"{tier['name']} is still locked -- {lock_reason}.")

    _sync_energy(db, player)
    if player.domain_energy < tier["energy_cost"]:
        db.commit()  # still save whatever regen was just synced, even though the attempt failed
        raise DomainChallengeError(
            f"Not enough energy -- {tier['name']} costs {tier['energy_cost']}, "
            f"you have {player.domain_energy}."
        )

    squad = character_service.get_squad(db, player)
    if not squad:
        db.commit()
        raise DomainChallengeError("You need at least one character in your squad first.")

    # A domain challenge is a self-contained fight you pay energy for, not
    # a step in a longer run -- so it starts on full HP rather than
    # inheriting whatever an expedition left the squad on. See
    # combat_service.restore_squad_to_full_hp for the full reasoning.
    # Done BEFORE building combatants, since factory reads current_hp.
    combat_service.restore_squad_to_full_hp(db, squad)

    party_combatants = combat_service.build_player_party(db, player, squad=squad)

    # Enemy level is derived from the squad actually walking in, not
    # hardcoded per tier -- see domain_config's SCALING block. This is
    # what stops "cleared Glacier 15 at character level 7" from also
    # meaning "and the domain fight is trivial".
    level = enemy_level_for(tier, sum(pc.level for pc in squad) / len(squad))
    enemy_combatants = [
        build_enemy_combatant(get_template_by_name(name), level=level)
        for name in tier["squad"]
    ]

    player.domain_energy -= tier["energy_cost"]
    db.commit()

    battle = Battle(party_combatants, enemy_combatants)
    _ACTIVE_BATTLES[player.id] = battle
    _ACTIVE_CHALLENGE[player.id] = (domain_id, tier_id)
    return battle


def abandon_challenge(db, player) -> None:
    """Drops the in-memory battle without granting anything and syncs
    whatever HP the squad ended up at back to their PlayerCharacter rows
    -- e.g. if the player wants to bail on a losing fight rather than
    play it out. Energy already spent is NOT refunded (matches an
    expedition loss also not refunding anything already invested)."""
    battle = _ACTIVE_BATTLES.pop(player.id, None)
    _ACTIVE_CHALLENGE.pop(player.id, None)
    if battle is not None:
        # Deliberately does NOT sync HP back -- see resolve_challenge.
        db.commit()


def resolve_challenge(db, player) -> dict:
    """Call once battle.is_over(). Grants the reward on a win (nothing on
    a loss, matching expedition conventions), syncs squad HP back to
    PlayerCharacter rows, clears the in-memory battle, and returns a
    summary dict for the cog to render: {"won": bool, "domain": dict,
    "tier": dict, "reward_lines": list[str]}."""
    battle = _ACTIVE_BATTLES.get(player.id)
    if battle is None:
        raise DomainChallengeError("No active domain challenge.")
    domain_id, tier_id = _ACTIVE_CHALLENGE[player.id]
    domain = get_domain_type(domain_id)
    tier = get_tier(tier_id)

    won = battle.result == "won"
    reward_lines: list[str] = []

    if won:
        reward = domain["rewards"][tier_id]
        if domain["reward_kind"] == "currency":
            for currency, amount in reward.items():
                add_currency(db, player, currency, amount)
                reward_lines.append(f"+{amount} {currency}")
        elif domain["reward_kind"] == "lootbox":
            lootbox_tier, quantity = reward
            lootbox_service.grant_lootbox(db, player, lootbox_tier, quantity)
            reward_lines.append(f"+{quantity} {lootbox_tier} lootbox")
        elif domain["reward_kind"] == "xp":
            squad = character_service.get_squad(db, player)
            combat_service.apply_character_xp(db, squad, reward)
            reward_lines.append(f"+{reward} XP (split across squad)")

    # HP is deliberately NOT written back from a domain fight. The squad
    # entered on full HP (see start_challenge) and a domain is a
    # self-contained challenge paid for in ENERGY, so letting it also
    # spend HP would be a second, invisible cost -- and one with no way
    # to pay it back, since healing only exists at expedition campfires.
    # Leaving the persisted value untouched (still the None "full"
    # sentinel the entry reset wrote) also stops the profile from showing
    # a damaged squad that will be silently restored the next time the
    # player does anything.
    _ACTIVE_BATTLES.pop(player.id, None)
    _ACTIVE_CHALLENGE.pop(player.id, None)
    db.commit()

    return {"won": won, "domain": domain, "tier": tier, "reward_lines": reward_lines}
