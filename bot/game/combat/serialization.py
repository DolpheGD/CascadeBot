"""
JSON (de)serialization for battle-scoped combat objects, so an in-progress
fight can be stored on Expedition.combat_state and rebuilt exactly -- across
a bot restart, a dropped connection, or the player just walking away for a
week. Nothing about combat state is ever held only in memory between
Discord interactions; every action is load -> mutate -> save.
"""

from __future__ import annotations

import dataclasses
import random

from bot.game.combat.battle import Battle
from bot.game.combat.combatant import Combatant
from bot.game.combat.status import DamageOverTime, HealOverTime, StatModifier


def _ability_to_json(ability: dict | None) -> dict | None:
    if ability is None:
        return None
    data = dict(ability)
    data.pop("min_rarity", None)  # only relevant at loot-roll time, not mid-battle
    return data


def combatant_to_dict(c: Combatant) -> dict:
    return {
        "name": c.name,
        "is_player": c.is_player,
        "base_stats": dict(c.base_stats),
        "current_hp": c.current_hp,
        "max_hp": c.max_hp,
        "character_id": c.character_id,
        "character_class": c.character_class,
        "mana": c.mana,
        "max_mana": c.max_mana,
        "energy": c.energy,
        "max_energy": c.max_energy,
        "active_abilities": [_ability_to_json(a) for a in c.active_abilities],
        "ultimate_ability": _ability_to_json(c.ultimate_ability),
        "passive_abilities": [_ability_to_json(a) for a in c.passive_abilities],
        "cooldowns": dict(c.cooldowns),
        "charges_used": dict(c.charges_used),
        "stacks": dict(c.stacks),
        "modifiers": [dataclasses.asdict(m) for m in c.modifiers],
        "dots": [dataclasses.asdict(d) for d in c.dots],
        "heals": [dataclasses.asdict(h) for h in c.heals],
        "stunned_turns": c.stunned_turns,
        "base_actions_per_cycle": c.base_actions_per_cycle,
        "shield": c.shield,
    }


def combatant_from_dict(data: dict) -> Combatant:
    return Combatant(
        name=data["name"],
        is_player=data["is_player"],
        base_stats=dict(data["base_stats"]),
        current_hp=data["current_hp"],
        max_hp=data["max_hp"],
        character_id=data.get("character_id"),
        character_class=data.get("character_class"),
        mana=data["mana"],
        max_mana=data["max_mana"],
        energy=data["energy"],
        max_energy=data["max_energy"],
        active_abilities=list(data["active_abilities"]),
        ultimate_ability=data.get("ultimate_ability"),
        passive_abilities=list(data["passive_abilities"]),
        cooldowns=dict(data["cooldowns"]),
        charges_used=dict(data["charges_used"]),
        stacks=dict(data["stacks"]),
        modifiers=[StatModifier(**m) for m in data["modifiers"]],
        dots=[DamageOverTime(**d) for d in data["dots"]],
        heals=[HealOverTime(**h) for h in data.get("heals", [])],
        stunned_turns=data["stunned_turns"],
        base_actions_per_cycle=data.get("base_actions_per_cycle", 1),
        shield=data.get("shield", 0.0),
    )


def battle_to_dict(battle: Battle) -> dict:
    all_combatants = battle.party + battle.enemies
    return {
        "party": [combatant_to_dict(c) for c in battle.party],
        "enemies": [combatant_to_dict(e) for e in battle.enemies],
        "turn_count": battle.turn_count,
        "log": list(battle.log),
        "result": battle.result,
        "target_index": battle.target_index,
        "cycle_number": battle.cycle_number,
        # Remaining queue for the in-progress cycle, stored as indices
        # into party + enemies (found by identity, same reasoning as
        # current_actor_index below -- two combatants can be
        # value-equal without being the same queued slot).
        "cycle_order_indices": [
            next(i for i, c in enumerate(all_combatants) if c is queued)
            for queued in battle.cycle_order
        ],
        # Index into party + enemies -- found by identity (`is`), not
        # list.index()'s value-equality, since Combatant is a dataclass
        # with default (value-based) __eq__: two combatants in an
        # identical state (e.g. two fresh copies of the same enemy type,
        # before either has taken damage or a cooldown) would otherwise
        # compare equal, and list.index() would silently return whichever
        # one happens to come first instead of the actual current actor.
        "current_actor_index": next(
            i for i, c in enumerate(all_combatants) if c is battle._current_actor
        ),
    }


def battle_from_dict(data: dict, rng: random.Random | None = None) -> Battle:
    """Rebuilds a Battle exactly as it was, including whose turn it is and
    the rest of the current cycle's queued turn order. Bypasses
    Battle.__init__ (which would kick off a fresh cycle from scratch)
    since we're restoring an already-in-progress fight."""
    party = [combatant_from_dict(p) for p in data["party"]]
    enemies = [combatant_from_dict(e) for e in data["enemies"]]
    all_combatants = party + enemies

    battle = Battle.__new__(Battle)
    battle.party = party
    battle.enemies = enemies
    battle.rng = rng or random.Random()
    battle.turn_count = data["turn_count"]
    battle.log = list(data["log"])
    battle.result = data["result"]
    battle.target_index = data.get("target_index", data.get("player_target_index", 0))
    battle.cycle_number = data.get("cycle_number", 0)
    # Old saves (pre-cycle-system) won't have this -- an empty queue just
    # means the next turn will build a fresh cycle from whoever's alive,
    # which self-heals cleanly.
    battle.cycle_order = [all_combatants[i] for i in data.get("cycle_order_indices", [])]
    battle._current_actor = all_combatants[data["current_actor_index"]]
    return battle
