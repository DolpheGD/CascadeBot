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
        "mana": c.mana,
        "max_mana": c.max_mana,
        "energy": c.energy,
        "max_energy": c.max_energy,
        "active_abilities": [_ability_to_json(a) for a in c.active_abilities],
        "passive_abilities": [_ability_to_json(a) for a in c.passive_abilities],
        "cooldowns": dict(c.cooldowns),
        "charges_used": dict(c.charges_used),
        "stacks": dict(c.stacks),
        "modifiers": [dataclasses.asdict(m) for m in c.modifiers],
        "dots": [dataclasses.asdict(d) for d in c.dots],
        "stunned_turns": c.stunned_turns,
        "is_defending": c.is_defending,
    }


def combatant_from_dict(data: dict) -> Combatant:
    return Combatant(
        name=data["name"],
        is_player=data["is_player"],
        base_stats=dict(data["base_stats"]),
        current_hp=data["current_hp"],
        max_hp=data["max_hp"],
        mana=data["mana"],
        max_mana=data["max_mana"],
        energy=data["energy"],
        max_energy=data["max_energy"],
        active_abilities=list(data["active_abilities"]),
        passive_abilities=list(data["passive_abilities"]),
        cooldowns=dict(data["cooldowns"]),
        charges_used=dict(data["charges_used"]),
        stacks=dict(data["stacks"]),
        modifiers=[StatModifier(**m) for m in data["modifiers"]],
        dots=[DamageOverTime(**d) for d in data["dots"]],
        stunned_turns=data["stunned_turns"],
        is_defending=data["is_defending"],
    )


def battle_to_dict(battle: Battle) -> dict:
    all_combatants = [battle.player] + battle.enemies
    return {
        "player": combatant_to_dict(battle.player),
        "enemies": [combatant_to_dict(e) for e in battle.enemies],
        "round_number": battle.round_number,
        "log": list(battle.log),
        "result": battle.result,
        # Index into [player] + enemies, not names -- unambiguous even when
        # two enemies share a name (e.g. two Goblins).
        "turn_order_indices": [all_combatants.index(c) for c in battle._turn_order],
        "turn_index": battle._turn_index,
    }


def battle_from_dict(data: dict, rng: random.Random | None = None) -> Battle:
    """Rebuilds a Battle exactly as it was, including whose turn it is.
    Bypasses Battle.__init__ (which would kick off a fresh round 1) since
    we're restoring an already-in-progress fight."""
    player = combatant_from_dict(data["player"])
    enemies = [combatant_from_dict(e) for e in data["enemies"]]
    all_combatants = [player] + enemies

    battle = Battle.__new__(Battle)
    battle.player = player
    battle.enemies = enemies
    battle.rng = rng or random.Random()
    battle.round_number = data["round_number"]
    battle.log = list(data["log"])
    battle.result = data["result"]
    battle._turn_order = [all_combatants[i] for i in data["turn_order_indices"]]
    battle._turn_index = data["turn_index"]
    return battle
