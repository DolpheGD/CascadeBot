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
from bot.game.combat.status import DamageOverTime, HealOverTime, StatModifier, Vulnerability


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
        # Bug fix: vulnerabilities were never serialized, so every
        # Vulnerability stack silently vanished the moment a battle was
        # saved and reloaded -- which for expedition combat is after
        # EVERY single action (see the load -> mutate -> save note in this
        # module's docstring). Sader Vorae's whole kit is built on
        # stacking these, so in practice her mark never once survived to
        # do anything. Now that DoT amplification also rides on
        # Vulnerability (see effects.DOT_VULNERABILITY_STAT), this would
        # have quietly broken that too.
        "vulnerabilities": [dataclasses.asdict(v) for v in c.vulnerabilities],
        "stunned_turns": c.stunned_turns,
        "taunt_turns": c.taunt_turns,
        "base_actions_per_cycle": c.base_actions_per_cycle,
        "shield": c.shield,
        "ramp_percent_per_turn": c.ramp_percent_per_turn,
        "ramp_stacks": c.ramp_stacks,
        "enemy_heal_stacks": c.enemy_heal_stacks,
        "enemy_shield_stacks": c.enemy_shield_stacks,
        "max_poise": c.max_poise,
        "poise": c.poise,
        "break_turns": c.break_turns,
        "break_tick_armed": c.break_tick_armed,
        # Break resistance escalation (see combatant.py) -- without this
        # persisted, a target's accumulated resistance would reset on
        # every save/load, which for expedition combat is after every
        # single action, i.e. the escalation would never happen at all.
        "break_count": c.break_count,
        "bonus_poise_damage": c.bonus_poise_damage,
        "guarding": c.guarding,
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
        # .get with a default: saves written before vulnerabilities were
        # serialized simply resume with none, which is exactly the
        # behaviour they already had.
        vulnerabilities=[Vulnerability(**v) for v in data.get("vulnerabilities", [])],
        stunned_turns=data["stunned_turns"],
        # Absent on pre-taunt saves -- 0 means "not taunting", which is
        # the behaviour those battles already had.
        taunt_turns=data.get("taunt_turns", 0),
        base_actions_per_cycle=data.get("base_actions_per_cycle", 1),
        shield=data.get("shield", 0.0),
        ramp_percent_per_turn=data.get("ramp_percent_per_turn", 0.0),
        ramp_stacks=data.get("ramp_stacks", 0),
        enemy_heal_stacks=data.get("enemy_heal_stacks", 0),
        enemy_shield_stacks=data.get("enemy_shield_stacks", 0),
        # Saves from before the poise system have no poise keys. Defaulting
        # max_poise to 0 leaves those enemies unbreakable rather than
        # crashing or silently full-poise; the next battle built from a
        # template gets real values. break_turns/guarding default to
        # "no effect", which is always safe to resume into.
        max_poise=data.get("max_poise", 0),
        poise=data.get("poise", 0),
        break_turns=data.get("break_turns", 0),
        break_count=data.get("break_count", 0),
        break_tick_armed=data.get("break_tick_armed", False),
        bonus_poise_damage=data.get("bonus_poise_damage", 0),
        guarding=data.get("guarding", False),
    )


def battle_to_dict(battle: Battle) -> dict:
    all_combatants = battle.party + battle.enemies
    return {
        "party": [combatant_to_dict(c) for c in battle.party],
        "enemies": [combatant_to_dict(e) for e in battle.enemies],
        # Cleared at the end of every party turn, so this is only ever
        # non-None mid-turn -- but expedition combat saves after EVERY
        # interaction, including the free target-select action, so it has
        # to round-trip or picking an ally then casting would lose the
        # pick in between.
        "ally_target_index": battle.ally_target_index,
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
        # Telegraphed enemy intents, as {enemy index: {ability, target
        # index}}. These live on Combatant.pending_intent but CAN'T be
        # written by combatant_to_dict, because the target is a live
        # Combatant reference -- it only becomes an index once you can see
        # the whole roster, which is here.
        #
        # This has to persist or the mechanic is a lie: every player action
        # is load -> mutate -> save -> render, so an intent decided during
        # rendering and then dropped would be re-rolled on the next
        # interaction, and the enemy would do something other than what the
        # player was shown. That's tolerable when the telegraph is
        # decoration; it is not tolerable now that Guard and poise-breaking
        # are decisions made against it.
        "pending_intents": _intents_to_dict(all_combatants),
    }


def _intents_to_dict(all_combatants: list[Combatant]) -> dict:
    """{combatant index: [queued intent, ...]} -- the WHOLE queue, not
    just the next one, since the battle screen telegraphs every move in
    it and each one is binding (see Combatant.pending_intents)."""
    intents: dict[str, list] = {}
    for i, c in enumerate(all_combatants):
        queue = []
        for pending in c.pending_intents:
            target = pending.get("target")
            target_index = next(
                (j for j, other in enumerate(all_combatants) if other is target), None
            )
            if target_index is None:
                break  # target left the battle; drop this and everything after it
            queue.append({
                "ability": _ability_to_json(pending.get("ability")),
                "target_index": target_index,
            })
        if queue:
            intents[str(i)] = queue
    return intents


def _intents_from_dict(data: dict, all_combatants: list[Combatant]) -> None:
    for index_str, queue in (data.get("pending_intents") or {}).items():
        index = int(index_str)
        if index >= len(all_combatants):
            continue
        # Saves from before the queue was introduced stored a single
        # intent dict rather than a list; accept both so an in-flight
        # battle survives the upgrade.
        if isinstance(queue, dict):
            queue = [queue]
        restored = []
        for intent in queue:
            target_index = intent.get("target_index")
            if target_index is None or target_index >= len(all_combatants):
                break
            restored.append({
                "ability": intent.get("ability"),
                "target": all_combatants[target_index],
            })
        all_combatants[index].pending_intents = restored


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
    # Absent on saves from before ally targeting existed -- None is
    # exactly the "no explicit choice, fall back to automatic" value, so
    # those resume with the original behaviour.
    battle.ally_target_index = data.get("ally_target_index")
    battle.cycle_number = data.get("cycle_number", 0)
    # Old saves (pre-cycle-system) won't have this -- an empty queue just
    # means the next turn will build a fresh cycle from whoever's alive,
    # which self-heals cleanly.
    battle.cycle_order = [all_combatants[i] for i in data.get("cycle_order_indices", [])]
    battle._current_actor = all_combatants[data["current_actor_index"]]
    # Restore telegraphed intents last -- they point at Combatant objects,
    # so every combatant has to exist first. Absent on pre-poise saves, in
    # which case intents are simply re-decided on the next peek, exactly
    # as they were before this was persisted.
    _intents_from_dict(data, all_combatants)
    return battle
