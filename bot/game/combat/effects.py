"""
Everything that actually happens during a hit or an ability cast. Every
function appends plain-English strings to `log` so the battle can be
rendered later (Discord embed, CLI, tests) without this module knowing
anything about presentation.

Damage pipeline for a single hit (_resolve_hit):
  1. Defender's dodge chance -> miss entirely, fire on_dodge passives.
  2. Attacker's crit chance -> crit_damage multiplier, then any
     crit_damage_bonus passives (e.g. Executioner) stack on top.
  3. Percentage mitigation from defender's defense (bot.game.combat.formulas).
  4. Defender's always-on damage_reduction passives (e.g. Iron Skin).
  5. Defender's is_defending flag (from the Defend action) halves it.
  6. Subtract HP, then resolve always-on reactive passives: attacker's
     lifesteal, defender's damage_reflect.
  7. Check on_low_hp (heal-at-threshold / prevent-death) and on_kill hooks.
"""

from __future__ import annotations

import random

from bot.game.combat import formulas
from bot.game.combat.combatant import Combatant
from bot.game.combat.status import DamageOverTime, StatModifier


def resolve_basic_attack(attacker: Combatant, defender: Combatant, rng: random.Random, log: list) -> None:
    _resolve_hit(attacker, defender, damage_percent=100, damage_stat="attack", rng=rng, log=log)


def resolve_active_ability(
    attacker: Combatant, defender: Combatant, ability: dict, rng: random.Random, log: list
) -> None:
    attacker.spend_resource(ability)
    log.append(f"{attacker.name} uses {ability['name']}!")

    effect = ability["effect"]
    kind = effect["kind"]

    if kind == "damage_multiplier":
        _resolve_hit(attacker, defender, effect["damage_percent"],
                     effect.get("damage_stat", "attack"), rng, log)

    elif kind == "damage_and_dot":
        hit = _resolve_hit(attacker, defender, effect["damage_percent"],
                            effect.get("damage_stat", "attack"), rng, log)
        if hit and defender.is_alive():
            flat_amount = attacker.effective_stat(effect["dot_stat"]) * effect["dot_percent"] / 100
            defender.dots.append(DamageOverTime(
                flat_amount=flat_amount, duration=effect["duration"],
                source=ability["name"], stat_source=effect["dot_stat"],
            ))
            log.append(f"{defender.name} is burning!")

    elif kind == "damage_and_debuff":
        hit = _resolve_hit(attacker, defender, effect["damage_percent"],
                            effect.get("damage_stat", "attack"), rng, log)
        if hit and defender.is_alive():
            defender.modifiers.append(StatModifier(
                stat=effect["debuff_stat"], percent=effect["debuff_percent"],
                duration=effect["duration"], source=ability["name"],
            ))
            log.append(f"{defender.name}'s {effect['debuff_stat']} is reduced!")

    elif kind == "heal_percent_max_hp":
        healed = attacker.heal(attacker.max_hp * effect["percent"] / 100)
        log.append(f"{attacker.name} heals {healed} HP.")

    elif kind == "damage_and_stun":
        hit = _resolve_hit(attacker, defender, effect["damage_percent"],
                            effect.get("damage_stat", "attack"), rng, log)
        if hit and defender.is_alive():
            defender.stunned_turns += effect["duration"]
            log.append(f"{defender.name} is stunned!")

    elif kind == "self_buff_debuff":
        attacker.modifiers.append(StatModifier(
            effect["buff_stat"], effect["buff_percent"], effect["duration"], ability["name"]
        ))
        attacker.modifiers.append(StatModifier(
            effect["debuff_stat"], effect["debuff_percent"], effect["duration"], ability["name"]
        ))
        log.append(f"{attacker.name} is empowered!")

    elif kind == "damage_execute_heal":
        hit = _resolve_hit(attacker, defender, effect["damage_percent"],
                            effect.get("damage_stat", "attack"), rng, log)
        if hit and not defender.is_alive():
            healed = attacker.heal(attacker.max_hp * effect["heal_percent_on_kill"] / 100)
            log.append(f"{attacker.name} is reinvigorated, healing {healed} HP!")

    else:
        log.append(f"({ability['name']} has no combat effect implemented yet)")


def _resolve_hit(attacker: Combatant, defender: Combatant, damage_percent: float,
                  damage_stat: str, rng: random.Random, log: list) -> bool:
    """Returns True if the hit landed (wasn't dodged)."""
    if formulas.roll_percent(defender.effective_stat("dodge"), rng):
        log.append(f"{defender.name} dodges {attacker.name}'s attack!")
        _trigger_on_dodge(defender, log)
        return False

    raw = attacker.effective_stat(damage_stat) * damage_percent / 100

    is_crit = formulas.roll_percent(attacker.effective_stat("crit_chance"), rng)
    if is_crit:
        raw *= formulas.crit_multiplier(attacker.effective_stat("crit_damage"))
        for passive in attacker.find_passive("crit_damage_bonus"):
            raw *= 1 + passive["effect"]["percent"] / 100

    damage = formulas.mitigate(raw, defender.effective_stat("defense"))

    for passive in defender.find_passive("damage_reduction"):
        damage *= 1 - passive["effect"]["percent"] / 100

    if defender.is_defending:
        damage *= 0.5

    dealt = defender.take_raw_hp_loss(damage)
    crit_tag = " (CRIT!)" if is_crit else ""
    log.append(f"{attacker.name} hits {defender.name} for {dealt} damage{crit_tag}.")

    for passive in attacker.find_passive("lifesteal"):
        healed = attacker.heal(dealt * passive["effect"]["percent"] / 100)
        if healed:
            log.append(f"{attacker.name} drains {healed} HP.")

    for passive in defender.find_passive("damage_reflect"):
        reflected = attacker.take_raw_hp_loss(dealt * passive["effect"]["percent"] / 100)
        if reflected:
            log.append(f"{attacker.name} takes {reflected} reflected damage!")

    _trigger_on_low_hp(defender, log)

    if not defender.is_alive():
        _trigger_on_kill(attacker, log)

    return True


def _trigger_on_dodge(dodger: Combatant, log: list) -> None:
    for passive in dodger.passive_abilities:
        if passive.get("trigger") == "on_dodge" and passive["effect"]["kind"] == "self_buff":
            effect = passive["effect"]
            dodger.modifiers.append(StatModifier(
                effect["buff_stat"], effect["percent"], effect["duration"], passive["name"]
            ))
            log.append(f"{dodger.name}'s {passive['name']} activates!")


def _trigger_on_kill(killer: Combatant, log: list) -> None:
    for passive in killer.passive_abilities:
        if passive.get("trigger") == "on_kill" and passive["effect"]["kind"] == "on_kill_restore":
            effect = passive["effect"]
            healed = killer.heal(killer.max_hp * effect["hp_percent"] / 100)
            killer.mana = min(killer.max_mana, killer.mana + effect["mana"])
            log.append(f"{killer.name}'s {passive['name']} restores {healed} HP and {effect['mana']} mana.")


def _trigger_on_low_hp(combatant: Combatant, log: list) -> None:
    """Covers both 'prevented a fatal hit' and 'healed after crossing 25% HP'."""
    if combatant.current_hp <= 0:
        for passive in combatant.passive_abilities:
            if passive.get("trigger") == "on_low_hp" and passive["effect"]["kind"] == "prevent_death":
                used = combatant.charges_used.get(passive["id"], 0)
                if used < passive["effect"]["charges_per_combat"]:
                    combatant.current_hp = 1
                    combatant.charges_used[passive["id"]] = used + 1
                    log.append(f"{combatant.name}'s {passive['name']} prevents death!")
                    return
        return

    if combatant.current_hp <= combatant.max_hp * 0.25:
        for passive in combatant.passive_abilities:
            if passive.get("trigger") == "on_low_hp" and passive["effect"]["kind"] == "heal_percent_max_hp":
                used = combatant.charges_used.get(passive["id"], 0)
                if used < passive["effect"].get("charges_per_combat", 1):
                    healed = combatant.heal(combatant.max_hp * passive["effect"]["percent"] / 100)
                    combatant.charges_used[passive["id"]] = used + 1
                    log.append(f"{combatant.name}'s {passive['name']} triggers, healing {healed} HP!")


def trigger_on_turn_start(combatant: Combatant, log: list) -> None:
    for passive in combatant.passive_abilities:
        if passive.get("trigger") != "on_turn_start":
            continue
        effect = passive["effect"]

        if effect["kind"] == "stacking_buff":
            current = combatant.stacks.get(passive["id"], 0)
            if current < effect["max_stacks"]:
                combatant.stacks[passive["id"]] = current + 1
                log.append(f"{combatant.name}'s {passive['name']} grows stronger! ({current + 1} stacks)")

        elif effect["kind"] == "resource_regen":
            if effect["resource_type"] == "mana":
                combatant.mana = min(combatant.max_mana, combatant.mana + effect["amount"])
            else:
                combatant.energy = min(combatant.max_energy, combatant.energy + effect["amount"])
            log.append(f"{combatant.name} restores {effect['amount']} {effect['resource_type']} from {passive['name']}.")
