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
from bot.game.combat.status import DamageOverTime, StatModifier


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
        "stunned_turns": c.stunned_turns,
        "turn_gauge": c.turn_gauge,
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
        stunned_turns=data["stunned_turns"],
        turn_gauge=data.get("turn_gauge", 0.0),
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
        # Index into party + enemies -- unambiguous even when two
        # combatants share a name (e.g. two Goblins).
        "current_actor_index": all_combatants.index(battle._current_actor),
    }


def battle_from_dict(data: dict, rng: random.Random | None = None) -> Battle:
    """Rebuilds a Battle exactly as it was, including whose turn it is and
    everyone's turn gauge. Bypasses Battle.__init__ (which would kick off a
    fresh turn-gauge race from zero) since we're restoring an
    already-in-progress fight."""
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
    battle._current_actor = all_combatants[data["current_actor_index"]]
    return battle
