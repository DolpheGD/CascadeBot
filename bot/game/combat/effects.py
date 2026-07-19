"""
Everything that actually happens during a hit, a skill cast, or an ultimate.
Every function appends plain-English strings to `log` so the battle can be
rendered later (Discord embed, CLI, tests) without this module knowing
anything about presentation.

Damage pipeline for a single hit (_resolve_hit):
  1. Attacker's crit rate -> crit_damage multiplier, then any
     crit_damage_bonus passives (e.g. Executioner) stack on top.
     (There is no dodge/miss chance anywhere in combat.)
  2. Percentage mitigation from defender's defense (bot.game.combat.formulas).
     Applies the same way whether the hit is physical (attack-based) or
     elemental (elemental-based) -- there's no separate resist stat.
  3. Defender's always-on damage_reduction passives (e.g. Iron Skin).
  4. Subtract HP, then resolve always-on reactive passives: attacker's
     lifesteal, defender's damage_reflect, defender's chance to stun the
     attacker (chance_stun_attacker).
  5. Check on_low_hp (heal-at-threshold / prevent-death) and on_kill hooks.

Resource economy: the basic Attack action is the only thing that generates
energy and mana (by the attacker's Recharge stat) -- see
Combatant.gain_energy_and_mana(). Skills (weapon/artifact) spend mana.
The ultimate (from an equipped scroll) spends energy instead, and is only
usable once energy hits 50.

Team-oriented effect kinds (own-side buffs/heals/resource restores, and
opposing-side debuffs) apply identically whether the caster is a player or
an enemy -- "allies" is whoever else is alive on the caster's own side,
"opponents" is everyone alive on the other side. Both are optional and
default to empty/[defender], so single-target effect kinds can ignore them
entirely.

Blood-Sustain effect kinds (sacrifice_hp_heal_lowest_ally_percent_max_hp,
sacrifice_hp_heal_team_percent_max_hp, and the always-on passive kind
aura_team_regen_self_sacrifice) pay for their heal with the caster's OWN
HP via take_raw_hp_loss instead of mana/energy, and never heal the caster
themself -- introduced for Kotori (bot/game/combat/skills.py), a Sustain
who gives her own vitality to the team rather than trickling free HP.

Single-ally-targeted support kinds (ally_buff, restore_resource_to_lowest_ally,
cleanse_ally_and_heal) mirror their team-wide counterparts (team_buff,
team_resource_restore, cleanse_self_and_heal) but pick exactly one living
ally to help -- whichever needs it most by the relevant metric -- instead
of hitting the whole side or the caster. Each falls back to targeting the
caster if no ally is alive, so the effect is never wasted. damage_and_double_debuff
and team_resource_drain round out the debuff side: the former stacks two
stat debuffs from one hit, the latter drains energy/mana from the WHOLE
opposing side at once (opponents' counterpart to team_resource_restore).

Shield kit (content pass, new abilities): Combatant.shield is a flat
HP-equivalent pool that absorbs incoming damage before current_hp does
(see _resolve_hit). self_shield_percent_max_hp / team_shield_percent_max_hp
grant it as a burst from an active ability; the passive kind shield_regen
trickles a small amount every turn instead (trigger_on_turn_start), capped
so it can't be stacked indefinitely. Shields never expire on a timer --
they just get worn down by damage. damage_bonus_if_debuffed and
chance_double_hit are two more active kinds: the former rewards
follow-up damage after a debuff lands (synergizes with anything that
applies a StatModifier first), the latter is a flat percent chance to
swing a second time. damage_reduction_scales_with_missing_hp is the
passive counterpart of "gets sturdier while hurt" -- unlike the flat
damage_reduction passive (Iron Skin), its mitigation grows the lower the
wearer's own HP% is, evaluated fresh on every hit in _resolve_hit.

Support DPS role shift: the class moved from single-target burst+debuff
toward AOE damage that only SOMETIMES also debuffs. aoe_damage hits every
living opponent for the same damage_percent with no side effect.
aoe_damage_chance_debuff hits every living opponent, and each hit target
independently rolls debuff_chance_percent odds of picking up a stat
debuff -- unlike damage_and_debuff (guaranteed), the debuff here is a
per-target coin flip, which is the "sometimes applies debuffs" part of
the shift. aoe_damage_chance_resource_drain is the same shape with an
energy/mana drain instead of a stat debuff (Nyrvite's signal-jamming
flavor on the same AOE-plus-sometimes-more kit piece).
aoe_damage_chance_dot is the same shape again, but with a burn
(DamageOverTime) instead of a stat debuff -- Blueflame's kit piece.
"""

from __future__ import annotations

import random

from bot.game.combat import formulas
from bot.game.combat.combatant import Combatant
from bot.game.combat.status import DamageOverTime, HealOverTime, StatModifier


def resolve_basic_attack(attacker: Combatant, defender: Combatant, rng: random.Random, log: list) -> None:
    _resolve_hit(attacker, defender, damage_percent=100, damage_stat="attack", rng=rng, log=log)
    energy_gained, mana_gained = attacker.gain_energy_and_mana()
    if energy_gained or mana_gained:
        log.append(f"{attacker.name} gains {energy_gained} energy and {mana_gained} SP.")


def resolve_active_ability(
    attacker: Combatant, defender: Combatant, ability: dict, rng: random.Random, log: list,
    allies: list[Combatant] | None = None, opponents: list[Combatant] | None = None,
) -> None:
    """`allies` is every OTHER living combatant on attacker's side (not
    including attacker) -- only used by team-oriented effect kinds
    (team_heal_percent_max_hp, heal_lowest_ally_percent_max_hp, team_buff,
    team_resource_restore, team_regen_over_time), introduced for the Combat
    Overhaul's Sustain/Amplifier/Support DPS character kits
    (bot/game/combat/skills.py). `opponents` is every living combatant on
    the OTHER side (including defender) -- only used by team_debuff. Every
    other effect kind ignores both, so they're safe to omit for simple
    1v1-style abilities."""
    allies = allies or []
    opponents = opponents if opponents is not None else [defender]
    attacker.spend_resource(ability)
    icon = "💥" if ability.get("is_ultimate") else "✨"
    log.append(f"{icon} {attacker.name} uses {ability['name']}!")

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
        log.append(f"💚 {attacker.name} heals {healed} HP.")

    elif kind == "damage_and_stun":
        hit = _resolve_hit(attacker, defender, effect["damage_percent"],
                            effect.get("damage_stat", "attack"), rng, log)
        if hit and defender.is_alive():
            defender.stunned_turns += effect["duration"]
            log.append(f"😵 {defender.name} is stunned!")

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
            log.append(f"🔥 {attacker.name} is reinvigorated, healing {healed} HP!")

    elif kind == "multi_hit":
        total_dealt = 0
        for _ in range(effect["hits"]):
            if not defender.is_alive():
                break
            _resolve_hit(attacker, defender, effect["damage_percent_per_hit"],
                         effect.get("damage_stat", "attack"), rng, log, suppress_kill_log=True)
        _trigger_on_kill_if_dead(attacker, defender, log)

    elif kind == "damage_and_heal_self":
        hit = _resolve_hit(attacker, defender, effect["damage_percent"],
                            effect.get("damage_stat", "attack"), rng, log)
        if hit:
            healed = attacker.heal(attacker.effective_stat(effect.get("heal_stat", "attack")) * effect["heal_percent"] / 100)
            if healed:
                log.append(f"🩸 {attacker.name} siphons {healed} HP.")

    elif kind == "heal_and_self_buff":
        healed = attacker.heal(attacker.max_hp * effect["heal_percent"] / 100)
        attacker.modifiers.append(StatModifier(
            effect["buff_stat"], effect["buff_percent"], effect["duration"], ability["name"]
        ))
        log.append(f"💚 {attacker.name} heals {healed} HP and surges with power!")

    elif kind == "damage_all_and_debuff_self":
        # Used sparingly (big ultimates): hits current target hard and
        # trades a temporary defense drop for the burst.
        hit = _resolve_hit(attacker, defender, effect["damage_percent"],
                            effect.get("damage_stat", "attack"), rng, log)
        attacker.modifiers.append(StatModifier(
            effect["debuff_stat"], effect["debuff_percent"], effect["duration"], ability["name"]
        ))

    elif kind == "heal_lowest_ally_percent_max_hp":
        # Sustain/Support "single-target heal" kit piece -- picks whoever
        # (including the caster) is lowest on HP% among attacker + allies.
        candidates = [attacker] + [a for a in allies if a.is_alive()]
        target = min(candidates, key=lambda c: c.current_hp / max(1, c.max_hp))
        healed = target.heal(target.max_hp * effect["percent"] / 100)
        log.append(f"💚 {attacker.name}'s {ability['name']} heals {target.name} for {healed} HP.")

    elif kind == "team_heal_percent_max_hp":
        # Sustain ultimate piece -- heals the whole team at once.
        for member in [attacker] + [a for a in allies if a.is_alive()]:
            healed = member.heal(member.max_hp * effect["percent"] / 100)
            if healed:
                log.append(f"💚 {member.name} is healed for {healed} HP by {ability['name']}.")

    elif kind == "team_buff":
        # Amplifier kit piece -- buffs one stat across the whole team.
        for member in [attacker] + [a for a in allies if a.is_alive()]:
            member.modifiers.append(StatModifier(
                effect["buff_stat"], effect["buff_percent"], effect["duration"], ability["name"]
            ))
        log.append(f"📡 {attacker.name}'s {ability['name']} empowers the whole team!")

    elif kind == "execute_below_threshold":
        # Deals normal damage, but a much harder hit if the target is
        # already below the given HP% -- a finisher move.
        is_execute = defender.current_hp <= defender.max_hp * effect["hp_threshold_percent"] / 100
        percent = effect["execute_damage_percent"] if is_execute else effect["damage_percent"]
        _resolve_hit(attacker, defender, percent, effect.get("damage_stat", "attack"), rng, log)
        if is_execute:
            log.append(f"⚔️ {attacker.name} finishes with a decisive blow!")

    elif kind == "true_damage_percent_max_hp":
        # Ignores defense and damage_reduction entirely -- a flat
        # percentage of the target's max HP, for punching through
        # heavily armored targets.
        damage = defender.max_hp * effect["percent"] / 100
        dealt = defender.take_raw_hp_loss(damage)
        log.append(f"🔺 {attacker.name}'s {ability['name']} deals {dealt} true damage to {defender.name}, ignoring defense!")
        _trigger_on_low_hp(defender, log)
        if not defender.is_alive():
            _trigger_on_kill(attacker, log)

    elif kind == "damage_and_resource_drain":
        # Deals damage and strips energy/mana from the target -- an EMP-
        # style effect that can delay an ultimate or starve out a skill.
        hit = _resolve_hit(attacker, defender, effect["damage_percent"],
                            effect.get("damage_stat", "attack"), rng, log)
        if hit and defender.is_alive():
            energy_drained = min(defender.energy, effect.get("energy_drain", 0))
            mana_drained = min(defender.mana, effect.get("mana_drain", 0))
            defender.energy -= energy_drained
            defender.mana -= mana_drained
            if energy_drained or mana_drained:
                log.append(f"🔌 {defender.name} loses {energy_drained} energy and {mana_drained} SP!")

    elif kind == "cleanse_self_and_heal":
        # Self-repair: strips the caster's own debuffs/DOTs and heals a
        # percentage of max HP.
        removed = len([m for m in attacker.modifiers if m.percent < 0]) + len(attacker.dots)
        attacker.modifiers = [m for m in attacker.modifiers if m.percent >= 0]
        attacker.dots = []
        healed = attacker.heal(attacker.max_hp * effect["percent"] / 100)
        log.append(f"🛠️ {attacker.name} purges {removed} negative effect(s) and repairs {healed} HP.")

    elif kind == "damage_scales_with_missing_hp":
        # Ramping finisher -- the lower the target's current HP%, the
        # bigger the hit, up to bonus_damage_percent_at_zero_hp extra at
        # (theoretical) 0 HP.
        missing_fraction = 1 - (defender.current_hp / max(1, defender.max_hp))
        total_percent = effect["base_damage_percent"] + effect["bonus_damage_percent_at_zero_hp"] * missing_fraction
        _resolve_hit(attacker, defender, total_percent, effect.get("damage_stat", "elemental"), rng, log)

    elif kind == "team_debuff":
        # Applies a stat debuff to every living combatant on the OTHER
        # side at once -- the opposing-side counterpart to team_buff.
        for target in opponents:
            target.modifiers.append(StatModifier(
                effect["debuff_stat"], effect["debuff_percent"], effect["duration"], ability["name"]
            ))
        log.append(f"🌀 {attacker.name}'s {ability['name']} weakens the entire opposing side!")

    elif kind == "sacrifice_hp_heal_lowest_ally_percent_max_hp":
        # Blood-Sustain kit piece (Kotori) -- pays for the heal with the
        # caster's OWN HP instead of a resource, then mends whichever ally
        # (never the caster) is lowest on HP%. With no living ally to give
        # to, the caster heals themself instead so the cost isn't wasted.
        self_cost = attacker.max_hp * effect["self_cost_percent"] / 100
        paid = attacker.take_raw_hp_loss(self_cost)
        if paid:
            log.append(f"🩸 {attacker.name} sacrifices {paid} HP to fuel {ability['name']}.")
        living_allies = [a for a in allies if a.is_alive()]
        target = min(living_allies, key=lambda c: c.current_hp / max(1, c.max_hp)) if living_allies else attacker
        healed = target.heal(target.max_hp * effect["heal_percent"] / 100)
        if healed:
            log.append(f"💚 {attacker.name}'s {ability['name']} heals {target.name} for {healed} HP.")
        _trigger_on_low_hp(attacker, log)

    elif kind == "sacrifice_hp_heal_team_percent_max_hp":
        # Blood-Sustain ultimate piece (Kotori) -- pays for a full-team heal
        # with the caster's own HP. Only living allies are healed, not the
        # caster; the whole point is giving her own vitality away.
        self_cost = attacker.max_hp * effect["self_cost_percent"] / 100
        paid = attacker.take_raw_hp_loss(self_cost)
        if paid:
            log.append(f"🩸 {attacker.name} sacrifices {paid} HP to fuel {ability['name']}.")
        for member in [a for a in allies if a.is_alive()]:
            healed = member.heal(member.max_hp * effect["heal_percent"] / 100)
            if healed:
                log.append(f"💚 {member.name} is healed for {healed} HP by {ability['name']}.")
        _trigger_on_low_hp(attacker, log)

    elif kind == "damage_and_double_debuff":
        # Debuff-specialist kit piece (Axel) -- like damage_and_debuff but
        # strips down TWO stats on the target at once (e.g. ATK and DEF),
        # for characters built around dismantling a target rather than
        # just chipping DEF for a follow-up hit.
        hit = _resolve_hit(attacker, defender, effect["damage_percent"],
                            effect.get("damage_stat", "attack"), rng, log)
        if hit and defender.is_alive():
            defender.modifiers.append(StatModifier(
                stat=effect["debuff_stat_1"], percent=effect["debuff_percent_1"],
                duration=effect["duration"], source=ability["name"],
            ))
            defender.modifiers.append(StatModifier(
                stat=effect["debuff_stat_2"], percent=effect["debuff_percent_2"],
                duration=effect["duration"], source=ability["name"],
            ))
            log.append(f"🔻 {defender.name}'s {effect['debuff_stat_1']} and {effect['debuff_stat_2']} are reduced!")

    elif kind == "ally_buff":
        # Single-target buff support piece (IH) -- unlike team_buff,
        # this empowers just ONE ally (whichever living ally has the
        # lowest effective value of the buffed stat, i.e. who needs it
        # most) rather than the whole side. Falls back to buffing the
        # caster if no ally is alive to receive it.
        living_allies = [a for a in allies if a.is_alive()]
        target = min(living_allies, key=lambda c: c.effective_stat(effect["buff_stat"])) if living_allies else attacker
        target.modifiers.append(StatModifier(
            stat=effect["buff_stat"], percent=effect["buff_percent"],
            duration=effect["duration"], source=ability["name"],
        ))
        log.append(f"📈 {attacker.name}'s {ability['name']} empowers {target.name}!")

    elif kind == "restore_resource_to_lowest_ally":
        # Single-target resource-restore support piece (Jofrog) -- unlike
        # team_resource_restore, this tops off just whichever living ally
        # (never the caster) has the lowest combined energy+mana ratio.
        # Falls back to restoring the caster if no ally is alive.
        living_allies = [a for a in allies if a.is_alive()]

        def _resource_ratio(c):
            pool = c.max_energy + c.max_mana
            return (c.energy + c.mana) / pool if pool else 0

        target = min(living_allies, key=_resource_ratio) if living_allies else attacker
        energy_gained = min(target.max_energy - target.energy, effect.get("energy_amount", 0))
        mana_gained = min(target.max_mana - target.mana, effect.get("mana_amount", 0))
        target.energy += energy_gained
        target.mana += mana_gained
        if energy_gained or mana_gained:
            log.append(f"🔋 {target.name} gains {energy_gained} energy and {mana_gained} SP from {attacker.name}'s {ability['name']}.")

    elif kind == "cleanse_ally_and_heal":
        # Single-target cleanse support piece (Aura) -- the ally-facing
        # counterpart to cleanse_self_and_heal. Picks whichever living ally
        # is lowest on HP% (never the caster), strips their debuffs/DOTs,
        # and heals them. Falls back to cleansing/healing the caster if no
        # ally is alive.
        living_allies = [a for a in allies if a.is_alive()]
        target = min(living_allies, key=lambda c: c.current_hp / max(1, c.max_hp)) if living_allies else attacker
        removed = len([m for m in target.modifiers if m.percent < 0]) + len(target.dots)
        target.modifiers = [m for m in target.modifiers if m.percent >= 0]
        target.dots = []
        healed = target.heal(target.max_hp * effect["heal_percent"] / 100)
        log.append(f"🛠️ {attacker.name}'s {ability['name']} purges {removed} negative effect(s) from {target.name} and heals {healed} HP.")

    elif kind == "team_resource_drain":
        # Utility debuff piece (Nyrvite) -- the opposing-side counterpart to
        # team_resource_restore. Strips flat energy/mana from every living
        # combatant on the OTHER side at once, delaying their ultimates
        # and starving their skills.
        for target in [o for o in opponents if o.is_alive()]:
            energy_lost = min(target.energy, effect.get("energy_amount", 0))
            mana_lost = min(target.mana, effect.get("mana_amount", 0))
            target.energy -= energy_lost
            target.mana -= mana_lost
            if energy_lost or mana_lost:
                log.append(f"🔌 {target.name} loses {energy_lost} energy and {mana_lost} SP to {attacker.name}'s {ability['name']}!")

    elif kind == "team_resource_restore":
        # Instant support burst -- restores flat energy and/or mana to the
        # caster's whole side at once (as opposed to Arcane Battery-style
        # passives, which trickle a smaller amount every turn).
        for member in [attacker] + [a for a in allies if a.is_alive()]:
            energy_gained = min(member.max_energy - member.energy, effect.get("energy_amount", 0))
            mana_gained = min(member.max_mana - member.mana, effect.get("mana_amount", 0))
            member.energy += energy_gained
            member.mana += mana_gained
            if energy_gained or mana_gained:
                log.append(f"🔋 {member.name} gains {energy_gained} energy and {mana_gained} SP from {ability['name']}.")

    elif kind == "team_regen_over_time":
        # True regen -- unlike team_heal_percent_max_hp (an instant burst),
        # this heals the caster's whole side a percentage of their own max
        # HP at the start of each of their turns for several turns.
        for member in [attacker] + [a for a in allies if a.is_alive()]:
            member.heals.append(HealOverTime(
                percent_max_hp=effect["percent_max_hp_per_turn"], duration=effect["duration"],
                source=ability["name"],
            ))
        log.append(f"🌿 {attacker.name}'s {ability['name']} sets in, regenerating the whole team over time.")

    elif kind == "self_shield_percent_max_hp":
        # Ionic Ward-style burst shield -- grants the caster a flat
        # HP-equivalent pool (Combatant.shield) that absorbs incoming
        # damage before current_hp does (see _resolve_hit). Adds onto any
        # shield already up rather than overwriting it.
        requested = attacker.max_hp * effect["percent"] / 100
        gained = attacker.gain_shield(requested)
        log.append(f"🔷 {attacker.name} raises a shield worth {round(gained)} HP.")

    elif kind == "team_shield_percent_max_hp":
        # Aegis Broadcast-style team shield -- same idea as
        # self_shield_percent_max_hp but for the caster's whole side at
        # once, each member shielded off their OWN max HP.
        for member in [attacker] + [a for a in allies if a.is_alive()]:
            requested = member.max_hp * effect["percent"] / 100
            member.gain_shield(requested)
        log.append(f"🔷 {attacker.name}'s {ability['name']} shields the whole team!")

    elif kind == "damage_bonus_if_debuffed":
        # Weakpoint Scanner-style finisher -- deals extra damage if the
        # target already has ANY active negative StatModifier (from
        # anything -- a debuff kind on gear, a character skill, doesn't
        # matter which), rewarding follow-up damage after a debuff lands.
        has_debuff = any(m.percent < 0 for m in defender.modifiers)
        percent = effect["damage_percent"] + (effect["bonus_damage_percent"] if has_debuff else 0)
        _resolve_hit(attacker, defender, percent, effect.get("damage_stat", "attack"), rng, log)
        if has_debuff:
            log.append(f"🎯 {attacker.name} exploits {defender.name}'s weakened state!")

    elif kind == "chance_double_hit":
        # Riftcutter-style flat percent chance to swing again immediately
        # for the same damage. The first hit always lands; the second is
        # gated behind chance_percent and skipped if the first hit already
        # finished the target.
        _resolve_hit(attacker, defender, effect["damage_percent"],
                     effect.get("damage_stat", "attack"), rng, log, suppress_kill_log=True)
        if defender.is_alive() and formulas.roll_percent(effect["chance_percent"], rng):
            log.append(f"⚡ {attacker.name}'s {ability['name']} strikes again!")
            _resolve_hit(attacker, defender, effect["damage_percent"],
                         effect.get("damage_stat", "attack"), rng, log, suppress_kill_log=True)
        _trigger_on_kill_if_dead(attacker, defender, log)

    elif kind == "aoe_damage":
        # Support DPS AOE kind (Combat Overhaul role shift) -- hits every
        # living enemy at once for the same damage_percent, instead of
        # dumping it all into one target the way the class used to.
        for target in [o for o in opponents if o.is_alive()]:
            _resolve_hit(attacker, target, effect["damage_percent"],
                         effect.get("damage_stat", "attack"), rng, log)
        log.append(f"💥 {attacker.name}'s {ability['name']} sweeps the whole enemy side!")

    elif kind == "aoe_damage_chance_debuff":
        # Support DPS AOE-plus-debuff kind -- hits every living enemy at
        # once, and each hit target independently has debuff_chance_percent
        # odds of also picking up a stat debuff. "Sometimes applies
        # debuffs" is the point: unlike damage_and_debuff, it's not
        # guaranteed on every cast.
        for target in [o for o in opponents if o.is_alive()]:
            hit = _resolve_hit(attacker, target, effect["damage_percent"],
                                effect.get("damage_stat", "attack"), rng, log)
            if hit and target.is_alive() and formulas.roll_percent(effect["debuff_chance_percent"], rng):
                target.modifiers.append(StatModifier(
                    stat=effect["debuff_stat"], percent=effect["debuff_percent"],
                    duration=effect["duration"], source=ability["name"],
                ))
                log.append(f"{target.name}'s {effect['debuff_stat']} is reduced!")

    elif kind == "aoe_damage_chance_resource_drain":
        # Nyrvite's take on the AOE-plus-debuff shape -- same "hits
        # everyone, sometimes does more" idea as aoe_damage_chance_debuff,
        # but the "more" is a resource drain (energy/mana) instead of a
        # stat debuff, rolled independently per target.
        for target in [o for o in opponents if o.is_alive()]:
            hit = _resolve_hit(attacker, target, effect["damage_percent"],
                                effect.get("damage_stat", "attack"), rng, log)
            if hit and target.is_alive() and formulas.roll_percent(effect["drain_chance_percent"], rng):
                energy_drained = min(target.energy, effect.get("energy_drain", 0))
                mana_drained = min(target.mana, effect.get("mana_drain", 0))
                target.energy -= energy_drained
                target.mana -= mana_drained
                if energy_drained or mana_drained:
                    log.append(f"🔌 {target.name} loses {energy_drained} energy and {mana_drained} SP!")

    elif kind == "aoe_damage_chance_dot":
        # DoT sibling of aoe_damage_chance_debuff -- hits every living
        # enemy at once, and each hit target independently rolls
        # dot_chance_percent odds of catching a burn instead of a stat
        # debuff. Introduced for Blueflame, whose Support DPS kit leans
        # on damage-over-time rather than shredding a stat.
        for target in [o for o in opponents if o.is_alive()]:
            hit = _resolve_hit(attacker, target, effect["damage_percent"],
                                effect.get("damage_stat", "attack"), rng, log)
            if hit and target.is_alive() and formulas.roll_percent(effect["dot_chance_percent"], rng):
                flat_amount = attacker.effective_stat(effect["dot_stat"]) * effect["dot_percent"] / 100
                target.dots.append(DamageOverTime(
                    flat_amount=flat_amount, duration=effect["duration"],
                    source=ability["name"], stat_source=effect["dot_stat"],
                ))
                log.append(f"{target.name} is burning!")

    else:
        log.append(f"({ability['name']} has no combat effect implemented yet)")


def _resolve_hit(attacker: Combatant, defender: Combatant, damage_percent: float,
                  damage_stat: str, rng: random.Random, log: list,
                  suppress_kill_log: bool = False) -> bool:
    """Resolves one hit. Always lands -- there is no dodge/miss chance in
    this game. Returns True (kept as a return value so callers that guard
    follow-up effects on "did it hit" still read naturally)."""
    raw = attacker.effective_stat(damage_stat) * damage_percent / 100

    is_crit = formulas.roll_percent(attacker.effective_stat("crit_rate"), rng)
    if is_crit:
        raw *= formulas.crit_multiplier(attacker.effective_stat("crit_damage"))
        for passive in attacker.find_passive("crit_damage_bonus"):
            raw *= 1 + passive["effect"]["percent"] / 100

    damage = formulas.mitigate(raw, defender.effective_stat("defense"))

    for passive in defender.find_passive("damage_reduction"):
        damage *= 1 - passive["effect"]["percent"] / 100

    missing_fraction = 1 - (defender.current_hp / max(1, defender.max_hp))
    for passive in defender.find_passive("damage_reduction_scales_with_missing_hp"):
        eff = passive["effect"]
        reduction = eff["base_percent"] + eff["bonus_percent_at_zero_hp"] * missing_fraction
        damage *= 1 - reduction / 100

    if defender.shield > 0:
        absorbed = min(damage, defender.shield)
        defender.shield -= absorbed
        damage -= absorbed
        if absorbed:
            log.append(f"🔷 {defender.name}'s shield absorbs {round(absorbed)} damage.")

    dealt = defender.take_raw_hp_loss(damage)
    crit_tag = " (💥 CRIT!)" if is_crit else ""
    log.append(f"{attacker.name} hits {defender.name} for {dealt} damage{crit_tag}.")

    for passive in attacker.find_passive("lifesteal"):
        healed = attacker.heal(dealt * passive["effect"]["percent"] / 100)
        if healed:
            log.append(f"🩸 {attacker.name} drains {healed} HP.")

    for passive in defender.find_passive("damage_reflect"):
        reflected = attacker.take_raw_hp_loss(dealt * passive["effect"]["percent"] / 100)
        if reflected:
            log.append(f"🪞 {attacker.name} takes {reflected} reflected damage!")

    for passive in defender.find_passive("chance_stun_attacker"):
        if formulas.roll_percent(passive["effect"]["percent"], rng):
            attacker.stunned_turns += passive["effect"]["duration"]
            log.append(f"⚡ {defender.name}'s {passive['name']} stuns {attacker.name}!")

    _trigger_on_low_hp(defender, log)

    if not defender.is_alive() and not suppress_kill_log:
        _trigger_on_kill(attacker, log)

    return True


def _trigger_on_kill_if_dead(attacker: Combatant, defender: Combatant, log: list) -> None:
    if not defender.is_alive():
        _trigger_on_kill(attacker, log)


def _trigger_on_kill(killer: Combatant, log: list) -> None:
    for passive in killer.passive_abilities:
        if passive.get("trigger") == "on_kill" and passive["effect"]["kind"] == "on_kill_restore":
            effect = passive["effect"]
            healed = killer.heal(killer.max_hp * effect["hp_percent"] / 100)
            killer.mana = min(killer.max_mana, killer.mana + effect["mana"])
            log.append(f"☠️ {killer.name}'s {passive['name']} restores {healed} HP and {effect['mana']} SP.")


def _trigger_on_low_hp(combatant: Combatant, log: list) -> None:
    """Covers both 'prevented a fatal hit' and 'healed after crossing 25% HP'."""
    if combatant.current_hp <= 0:
        for passive in combatant.passive_abilities:
            if passive.get("trigger") == "on_low_hp" and passive["effect"]["kind"] == "prevent_death":
                used = combatant.charges_used.get(passive["id"], 0)
                if used < passive["effect"]["charges_per_combat"]:
                    combatant.current_hp = 1
                    combatant.charges_used[passive["id"]] = used + 1
                    log.append(f"✨ {combatant.name}'s {passive['name']} prevents death!")
                    return
        return

    if combatant.current_hp <= combatant.max_hp * 0.25:
        for passive in combatant.passive_abilities:
            if passive.get("trigger") == "on_low_hp" and passive["effect"]["kind"] == "heal_percent_max_hp":
                used = combatant.charges_used.get(passive["id"], 0)
                if used < passive["effect"].get("charges_per_combat", 1):
                    healed = combatant.heal(combatant.max_hp * passive["effect"]["percent"] / 100)
                    combatant.charges_used[passive["id"]] = used + 1
                    log.append(f"💚 {combatant.name}'s {passive['name']} triggers, healing {healed} HP!")


def trigger_on_turn_start(combatant: Combatant, log: list, allies: list[Combatant] | None = None) -> None:
    """`allies` is every OTHER living combatant on combatant's own side --
    only used by team-aura passive kinds (aura_team_resource_regen,
    aura_team_regen). Every other passive kind ignores it."""
    allies = allies or []
    for passive in combatant.passive_abilities:
        if passive.get("trigger") != "on_turn_start":
            continue
        effect = passive["effect"]

        if effect["kind"] == "stacking_buff":
            current = combatant.stacks.get(passive["id"], 0)
            if current < effect["max_stacks"]:
                combatant.stacks[passive["id"]] = current + 1
                log.append(f"📈 {combatant.name}'s {passive['name']} grows stronger! ({current + 1} stacks)")

        elif effect["kind"] == "resource_regen":
            if effect["resource_type"] == "mana":
                combatant.mana = min(combatant.max_mana, combatant.mana + effect["amount"])
            else:
                combatant.energy = min(combatant.max_energy, combatant.energy + effect["amount"])
            log.append(f"🔋 {combatant.name} restores {effect['amount']} {effect['resource_type']} from {passive['name']}.")

        elif effect["kind"] == "shield_regen":
            # Capacitor Shell-style trickle shield -- unlike the burst
            # self_shield_percent_max_hp active, this adds a small amount
            # of shield every turn for free, capped (default 50% of max
            # HP) so it can't be stacked into an unbreakable wall turn
            # after turn.
            cap = combatant.max_hp * effect.get("cap_percent", 50) / 100
            requested = min(cap - combatant.shield, combatant.max_hp * effect["percent"] / 100)
            requested = max(0.0, requested)
            gained = combatant.gain_shield(requested)
            if gained:
                log.append(f"🔷 {combatant.name}'s {passive['name']} reinforces their shield (+{round(gained)}).")

        elif effect["kind"] == "aura_team_resource_regen":
            # Support aura -- restores energy/mana to combatant AND its
            # living allies every turn, not just the owner.
            for member in [combatant] + [a for a in allies if a.is_alive()]:
                energy_gained = min(member.max_energy - member.energy, effect.get("energy_amount", 0))
                mana_gained = min(member.max_mana - member.mana, effect.get("mana_amount", 0))
                member.energy += energy_gained
                member.mana += mana_gained
                if energy_gained or mana_gained:
                    log.append(f"🔋 {member.name} gains {energy_gained} energy and {mana_gained} SP from {combatant.name}'s {passive['name']}.")

        elif effect["kind"] == "aura_team_regen":
            # Support aura -- heals combatant AND its living allies a
            # percentage of their own max HP every turn, for free (no
            # resource cost, unlike the active team_regen_over_time).
            for member in [combatant] + [a for a in allies if a.is_alive()]:
                healed = member.heal(member.max_hp * effect["percent"] / 100)
                if healed:
                    log.append(f"💚 {member.name} is healed for {healed} HP by {combatant.name}'s {passive['name']}.")

        elif effect["kind"] == "aura_team_regen_self_sacrifice":
            # Blood-Sustain aura (Kotori) -- unlike aura_team_regen, this
            # does NOT heal the owner. Every turn it costs the owner a
            # slice of their own max HP and gives that vitality to living
            # allies as a percentage heal, no resource cost either way.
            self_cost = combatant.max_hp * effect["self_cost_percent"] / 100
            paid = combatant.take_raw_hp_loss(self_cost)
            if paid:
                log.append(f"🩸 {combatant.name}'s {passive['name']} costs them {paid} HP.")
            for member in [a for a in allies if a.is_alive()]:
                healed = member.heal(member.max_hp * effect["percent"] / 100)
                if healed:
                    log.append(f"💚 {member.name} is healed for {healed} HP by {combatant.name}'s {passive['name']}.")
            _trigger_on_low_hp(combatant, log)
