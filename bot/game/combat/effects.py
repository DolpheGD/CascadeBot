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
caster if no ally is alive, so the effect is never wasted.
damage_and_double_debuff stacks two stat debuffs from one hit.

ENERGY/MANA DRAIN WAS REMOVED FROM THE GAME. The three kinds that did it
(damage_and_resource_drain, team_resource_drain,
aoe_damage_chance_resource_drain) are gone, not deprecated -- draining a
resource is a purely subtractive effect with no counterplay: the target
can't respond to it, can't play around it, and the only thing it changes
is that something good happens later than it would have. Everything that
used them now uses one of five replacements, all of which feed mechanics
the player can actually engage with:

  * damage_and_poise_strike / aoe_damage_chance_poise_strike /
    team_poise_strike -- pay into the POISE economy instead (see the
    Poise/Break tuning block below). Same "disrupt their turn" fantasy,
    but the payoff is a break the player can see coming and build toward.
  * damage_and_dot_amplify / aoe_damage_chance_dot_amplify /
    team_dot_amplify -- mark the target so damage-over-time on it hits
    harder (see DOT_VULNERABILITY_STAT). This is a genuine team-synergy
    piece: a marker character and a separate burn character now multiply
    each other, where drain combo'd with nothing.

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
the shift. aoe_damage_chance_poise_strike is the same shape with a burst
of extra poise damage instead of a stat debuff (Nyrvite's kit piece,
post-drain-removal). aoe_damage_chance_dot is the same shape again, but
with a burn (DamageOverTime) instead of a stat debuff -- Blueflame's kit
piece -- and aoe_damage_chance_dot_amplify completes the set with the
DoT-amplification mark.

New-mechanics pass (roster diversity, round 2): four genuinely new pieces
of combat plumbing, not just new data on existing kinds.

1. Reactive team buff (`on_hit_team_buff`, always-on passive): the
   defender's WHOLE side (not just the defender) gets buffed the instant
   the defender takes a hit -- "sacrificial support," where tanking a hit
   for the team is itself the team-buff trigger. Needed `defender_allies`
   threaded into _resolve_hit (every OTHER living combatant on the
   DEFENDER's side, computed from `opponents` in resolve_active_ability,
   or passed straight into resolve_basic_attack by battle.py) alongside
   the existing `allies`/`opponents`.

2. Vulnerability stacking (`apply_vulnerability_stack` active kind +
   status.Vulnerability): a debuff that increases damage the TARGET takes
   from one specific damage_stat (e.g. elemental), stacking further with
   repeat hits from the same source instead of just refreshing a flat
   percent -- "the more you hit it, the more everyone's follow-up hits of
   that type hurt." Persists for the rest of the battle once applied
   (same convention as Combatant.stacks/ramp_stacks), so repeated casts
   from the same source build toward max_stacks instead of resetting.

3. Extra turn on kill (`extra_turn_on_kill`, always-on passive): landing
   a killing blow immediately re-queues the killer for another turn this
   same cycle (battle.py's take_party_action/take_enemy_turn diff the
   opposing side's living count around the action) instead of just
   restoring a resource like on_kill_restore does -- an unstoppable
   "clears one target, doesn't slow down" identity.

4. DoT amplification (`dot_amplifier`, always-on passive): every
   DamageOverTime the wearer applies (damage_and_dot, aoe_damage_chance_dot)
   is scaled up by a flat percent at the moment it's created, same
   frozen-at-application convention as the DOT's own flat_amount.

5. Sacrificial team buffing (`sacrifice_hp_team_buff` active kind): the
   Blood-Sustain family's sacrifice_hp_heal_* kinds, but for a team BUFF
   instead of a team heal -- pays with the caster's own HP via
   take_raw_hp_loss, then buffs the whole side (caster included).
"""

from __future__ import annotations

import random

from bot.game.combat import formulas
from bot.game.combat.combatant import Combatant
from bot.game.combat.status import DamageOverTime, HealOverTime, StatModifier, Vulnerability

# ----------------------------------------------------------------------
# Poise / Break / Guard tuning. See the Poise/Break block in combatant.py
# for what the mechanic is and why it's enemy-only.
#
# Poise damage is per LANDED HIT, deliberately decoupled from damage
# numbers: it counts actions, not power. That means breaking is a tactical
# problem ("what do I press, and when") rather than another thing raw gear
# score solves for you, and it stays balanced for free as damage scales
# over 100 levels of gear.
#
# An individual ability can override its value with "poise_damage" in its
# effect dict; without one it's inferred from what kind of action it was.
# Multi-hit and AOE abilities get no special casing -- they chip once per
# hit and per target respectively simply because every hit routes through
# _resolve_hit, which is what makes them the natural break tools.
# ----------------------------------------------------------------------
POISE_DAMAGE_BASIC = 1      # a plain Attack
POISE_DAMAGE_ABILITY = 2    # any weapon/artifact/character skill
POISE_DAMAGE_ULTIMATE = 3   # an ultimate

BREAK_DURATION_TURNS = 2

# Rebalance pass: was 50. A break already does three separate things at
# once -- it CANCELS the telegraphed move, it SKIPS the target's turns for
# the duration, and it amplifies incoming damage -- so the damage rider
# doesn't also need to be the largest multiplier in the game. Trimmed
# alongside the break-resistance escalation in combatant.py; see that
# block for the full picture of why the mechanic needed reining in.
BREAK_DAMAGE_BONUS_PERCENT = 35

# ----------------------------------------------------------------------
# BREAK POTENTIAL -- the intended ways to make breaking EASIER.
#
# The rebalance above deliberately doesn't just nerf poise: it moves the
# power from "always on, stacks without limit" to "earn it, on purpose".
# Three levers exist, all of which the player opts into:
#
#   1. `poise_damage_bonus` (always-on passive, gear or character) --
#      flat extra poise per landed hit, same shape the relics use.
#   2. `poise_shred` (rider on an active effect) -- permanently lowers
#      the target's max_poise for the rest of the battle. This is the
#      direct answer to break resistance: shred counteracts escalation,
#      so a squad built for breaking keeps breaking while an incidental
#      one doesn't.
#   3. `break_damage_bonus` (always-on passive) -- doesn't help you break
#      faster, but makes each break hit harder, for kits that want to
#      cash a rare break in rather than chain cheap ones.
#
# Poise shred is capped at MIN_SHREDDED_POISE so nothing can be reduced
# to an unbreakable-by-arithmetic 0 (which can_be_broken() reads as "has
# no poise system at all" -- a 0 here would make the target IMMUNE, the
# exact opposite of what shredding it should do).
# ----------------------------------------------------------------------
MIN_SHREDDED_POISE = 3


def apply_poise_shred(target: Combatant, amount: int, log: list, source: str = "") -> None:
    """Permanently lowers `target`'s max_poise for the rest of the
    battle, clamped so it can never reach the 0 that would read as
    "unbreakable". Current poise is clamped down with it, so shredding a
    nearly-broken target can finish the break immediately rather than
    leaving it stranded above its own new maximum."""
    if not target.can_be_broken() or amount <= 0:
        return
    before = target.max_poise
    target.max_poise = max(MIN_SHREDDED_POISE, target.max_poise - amount)
    target.poise = min(target.poise, target.max_poise)
    if target.max_poise < before:
        log.append(
            f"🪓 {target.name}'s guard is sundered -- max Poise {before} → {target.max_poise}"
            + (f" ({source})" if source else "")
        )


def _break_damage_percent(attacker: Combatant) -> float:
    """The damage amplification a break grants, for THIS attacker: the
    global BREAK_DAMAGE_BONUS_PERCENT plus any `break_damage_bonus`
    passives they carry. Per-attacker rather than global so a
    break-focused build can invest in cashing breaks in harder without
    raising the number for everyone (which is what made the mechanic
    oppressive in the first place)."""
    return BREAK_DAMAGE_BONUS_PERCENT + sum(
        p["effect"].get("percent", 0) for p in attacker.find_passive("break_damage_bonus")
    )


def total_poise_damage_bonus(attacker: Combatant) -> int:
    """Every source of bonus poise damage on a landed hit: run-scoped
    relics (Combatant.bonus_poise_damage, baked on at battle-build time)
    plus any `poise_damage_bonus` passives from gear or a character kit.
    Centralised here so relics and passives can never drift apart in how
    they're counted."""
    return attacker.bonus_poise_damage + sum(
        p["effect"].get("amount", 1) for p in attacker.find_passive("poise_damage_bonus")
    )

# ----------------------------------------------------------------------
# DoT amplification as a TARGET-side debuff.
#
# `dot_amplifier` (an always-on ATTACKER passive) already scaled up DoTs
# at the moment they were created. This is the other side of that: a
# stacking mark on the DEFENDER that scales up every DoT ticking on it,
# whoever applied them -- which is what makes it a team-synergy piece
# rather than a solo one, since a marker character and a separate burn
# character now multiply each other.
#
# Implemented as a status.Vulnerability with this sentinel damage_stat
# rather than a bespoke status type. Vulnerability already stacks per
# source, caps at max_stacks, persists battle-long and (as of this pass)
# serializes -- reusing it means no new plumbing anywhere, and the ℹ️
# Info view picks it up for free. It is deliberately NOT a real stat
# name, so it can never collide with a hit's damage_stat lookup in
# _resolve_hit.
# ----------------------------------------------------------------------
DOT_VULNERABILITY_STAT = "dot"


# ----------------------------------------------------------------------
# KIT REACTIONS -- passives that fire off what a character DOES.
#
# Character passives used to be drawn from a small pool of generic gear
# passives: 10 of 24 characters shared an effect kind with someone else
# (three separate crit_damage_bonus carriers, three stacking_buff, two
# damage_reduction, two shield_regen), and even the unique ones were
# borrowed wholesale -- lifesteal, damage_reflect, prevent_death -- so a
# passive told you nothing about the character it was attached to and
# never interacted with their own skill or ultimate.
#
# A kit reaction instead triggers on the ACTION the character's kit is
# built around. A healer's passive fires when she heals; a shielder's
# when he shields; a break specialist's when she breaks something. That
# makes the passive a reason to build INTO the kit rather than a flat
# stat rider, and it's why every one of them can now be unique.
#
# One dispatcher rather than a branch per character: the passive names
# an `event` and a flat `reward`, so adding a new reaction is data, not
# code. Rewards are deliberately a small closed set -- every one of them
# helps the TEAM as well as the caster, which is the other half of the
# design brief.
# ----------------------------------------------------------------------
KIT_EVENTS = frozenset({
    "heal", "shield", "buff", "debuff", "dot", "break", "cleanse", "ultimate", "sacrifice",
    # Fires when the actor damages an enemy that is ALREADY debuffed.
    # Raised from _resolve_hit rather than from the ability dispatcher,
    # because it's a property of the TARGET at the moment of the hit, not
    # of the ability being used. Exists for kits built to EXPLOIT debuffs
    # rather than apply them -- Arkiver's whole identity is
    # damage_bonus_if_debuffed, so keying his passive to "debuff" (as it
    # first was) meant it could never fire: he consumes debuffs, he
    # doesn't create them.
    "hit_debuffed",
    # Fires when the actor lands a killing blow. Distinct from the older
    # on_kill_restore passive KIND, which is self-only; this is the
    # team-facing version.
    "kill",
})

# Which events an ability raises, keyed off its effect kind. Derived from
# the kind rather than hand-tagged on each ability so a new ability can't
# ship silently failing to trigger the passives it should -- the author
# only has to get the effect kind right, which they already must.
_EVENT_KINDS: dict[str, set[str]] = {
    "heal": {
        "heal_lowest_ally_percent_max_hp", "team_heal_percent_max_hp", "heal_percent_max_hp",
        "cleanse_ally_and_heal", "cleanse_self_and_heal", "damage_and_heal_self",
        "heal_and_self_buff", "team_heal_and_buff", "team_regen_over_time",
        "sacrifice_hp_heal_lowest_ally_percent_max_hp", "sacrifice_hp_heal_team_percent_max_hp",
        "damage_execute_heal",
    },
    "shield": {
        "self_shield_percent_max_hp", "team_shield_percent_max_hp", "shield_ally_percent_max_hp",
        "team_shield_and_buff", "team_shield_and_cleanse", "taunt_and_shield",
        "taunt_and_team_shield",
    },
    "buff": {
        "team_buff", "team_double_buff", "team_buff_and_resource", "ally_buff",
        "self_buff_debuff", "heal_and_self_buff", "sacrifice_hp_team_buff",
        "team_shield_and_buff", "team_heal_and_buff",
    },
    "debuff": {
        "damage_and_debuff", "damage_and_double_debuff", "team_debuff",
        "aoe_damage_chance_debuff", "apply_vulnerability_stack",
    },
    "dot": {"damage_and_dot", "aoe_damage_chance_dot"},
    "cleanse": {"cleanse_ally_and_heal", "cleanse_self_and_heal", "team_shield_and_cleanse"},
    "sacrifice": {
        "sacrifice_hp_heal_lowest_ally_percent_max_hp",
        "sacrifice_hp_heal_team_percent_max_hp", "sacrifice_hp_team_buff",
    },
}


def kit_events_for(ability: dict) -> list[str]:
    """Every kit event this ability raises. An ability can raise several
    -- Evz's cleanse-and-heal is both a "cleanse" and a "heal", and a
    Sustain ultimate is additionally an "ultimate"."""
    kind = ability.get("effect", {}).get("kind")
    events = [event for event, kinds in _EVENT_KINDS.items() if kind in kinds]
    if ability.get("is_ultimate"):
        events.append("ultimate")
    return events


def buff_multiplier(caster: Combatant) -> float:
    """How much stronger this combatant's outgoing BUFFS are, from any
    `buff_amplifier` passive. The Amplifier class's answer to Bee Jee's
    shield_amplifier: it makes a support character better at the thing
    their kit already does, rather than handing them a flat stat, and it
    scales with the buffs they were going to cast anyway."""
    mult = 1.0
    for passive in caster.find_passive("buff_amplifier"):
        mult *= 1 + passive["effect"]["percent"] / 100
    return mult


def _buffed(caster: Combatant, percent: float) -> float:
    """A buff percentage after the caster's buff_amplifier. Rounded so
    the number the player reads in the Info panel isn't 27.000000000004."""
    return round(percent * buff_multiplier(caster), 1)


def trigger_kit_event(
    actor: Combatant,
    event: str,
    log: list,
    allies: list[Combatant] | None = None,
    target: Combatant | None = None,
) -> None:
    """Fire any `kit_reaction` passive on `actor` listening for `event`.

    `target` is whoever the triggering action affected (the healed ally,
    the broken enemy...), used by target-scoped rewards. `allies` is the
    caster's living side, used by team-scoped ones.

    Silent when nothing listens, which is the overwhelmingly common case
    -- this is called from several points in the ability dispatcher and
    must stay cheap."""
    allies = [a for a in (allies or []) if a.is_alive()]
    for passive in actor.find_passive("kit_reaction"):
        effect = passive["effect"]
        if effect.get("event") != event:
            continue
        _apply_kit_reward(actor, passive, effect, log, allies, target)


def _apply_kit_reward(actor, passive, effect, log, allies, target) -> None:
    """The reward half of a kit reaction. Flat shapes only -- nesting a
    full effect dict here would mean re-entering the whole ability
    dispatcher from inside a passive, which is a recursion hazard for no
    expressive gain."""
    reward = effect.get("reward")
    team = [actor] + allies
    name = passive["name"]

    if reward == "team_buff":
        for member in team:
            member.modifiers.append(StatModifier(
                stat=effect["buff_stat"], percent=effect["buff_percent"],
                duration=effect.get("duration", 2), source=name,
            ))
        log.append(f"🧬 {name}: the squad gains +{effect['buff_percent']:g}% {effect['buff_stat']}.")

    elif reward == "self_buff":
        actor.modifiers.append(StatModifier(
            stat=effect["buff_stat"], percent=effect["buff_percent"],
            duration=effect.get("duration", 2), source=name,
        ))
        log.append(f"🧬 {name}: {actor.name} gains +{effect['buff_percent']:g}% {effect['buff_stat']}.")

    elif reward == "target_buff" and target is not None and target.is_alive():
        target.modifiers.append(StatModifier(
            stat=effect["buff_stat"], percent=effect["buff_percent"],
            duration=effect.get("duration", 2), source=name,
        ))
        log.append(f"🧬 {name}: {target.name} gains +{effect['buff_percent']:g}% {effect['buff_stat']}.")

    elif reward == "target_shield" and target is not None and target.is_alive():
        gained = grant_shield(actor, target, effect["percent"])
        if gained:
            log.append(f"🧬 {name}: {target.name} gains a {round(gained)} HP shield.")

    elif reward == "team_shield":
        for member in team:
            grant_shield(actor, member, effect["percent"])
        log.append(f"🧬 {name}: the squad is shielded.")

    elif reward == "team_energy":
        for member in team:
            member.gain_energy(effect["amount"])
        log.append(f"🧬 {name}: the squad gains {effect['amount']} energy.")

    elif reward == "team_heal":
        for member in team:
            member.heal(member.max_hp * effect["percent"] / 100)
        log.append(f"🧬 {name}: the squad recovers {effect['percent']:g}% HP.")

    elif reward == "self_heal":
        healed = actor.heal(actor.max_hp * effect["percent"] / 100)
        if healed:
            log.append(f"🧬 {name}: {actor.name} recovers {healed} HP.")

    elif reward == "team_cleanse":
        # Strips the squad's debuffs and DoTs. Distinct from a healer's
        # single-target cleanse by being team-wide and free -- it rides
        # on an action the character was taking anyway.
        removed = 0
        for member in team:
            removed += len([m for m in member.modifiers if m.percent < 0]) + len(member.dots)
            member.modifiers = [m for m in member.modifiers if m.percent >= 0]
            member.dots = []
        if removed:
            log.append(f"🧬 {name}: the squad shakes off {removed} negative effect(s).")

    elif reward == "mark_vulnerable" and target is not None and target.is_alive():
        # Reuses status.Vulnerability rather than inventing a second
        # "takes more damage" mechanism -- it already stacks per source,
        # caps, serializes and shows up in the Info panel. This is the
        # team-facing shape: the debuffer marks, and EVERY squad member's
        # hits of that damage type cash it in.
        stat = effect.get("damage_stat", "attack")
        existing = next(
            (v for v in target.vulnerabilities
             if v.damage_stat == stat and v.source == name), None
        )
        if existing is not None:
            existing.stacks = min(existing.max_stacks, existing.stacks + 1)
        else:
            target.vulnerabilities.append(Vulnerability(
                damage_stat=stat, percent_per_stack=effect["percent_per_stack"],
                stacks=1, max_stacks=effect.get("max_stacks", 3), source=name,
            ))
        log.append(
            f"🧬 {name}: {target.name} takes +"
            f"{target.total_vulnerability_percent(stat):g}% {stat} damage."
        )



def grant_shield(caster: Combatant, target: Combatant, percent_max_hp: float) -> float:
    """Shields `target` for `percent_max_hp`% of the TARGET's max HP,
    scaled up by any `shield_amplifier` passives the CASTER carries.

    Exists as a single choke point for the same reason dot_amplifier's
    scaling is applied where DoTs are created: the amplifier belongs to
    the caster, but Combatant.gain_shield only knows about the recipient,
    so the multiplier can't live down there. Every shield-granting effect
    kind routes through here, which is what lets a dedicated shielder
    (Bee Jee) be better at shielding than a character who merely has a
    shield ability, without special-casing any individual ability.

    Returns the actual amount added -- gain_shield still applies the
    enemy diminishing-returns curve on top, so the requested and granted
    amounts can differ."""
    amount = target.max_hp * percent_max_hp / 100
    for passive in caster.find_passive("shield_amplifier"):
        amount *= 1 + passive["effect"]["percent"] / 100
    return target.gain_shield(amount)


def _apply_dot_vulnerability(target: Combatant, ability: dict, effect: dict, log: list) -> None:
    """Applies (or adds a stack to) the DoT-amplification mark on
    `target`. Shared by damage_and_dot_amplify, team_dot_amplify and
    aoe_damage_chance_dot_amplify so all three stack identically -- repeat
    applications from the SAME ability build one instance toward
    max_stacks; different abilities track their own."""
    source = ability["name"]
    existing = next(
        (v for v in target.vulnerabilities
         if v.damage_stat == DOT_VULNERABILITY_STAT and v.source == source),
        None,
    )
    if existing is not None:
        existing.stacks = min(existing.max_stacks, existing.stacks + 1)
        stacks_now = existing.stacks
    else:
        stacks_now = 1
        target.vulnerabilities.append(Vulnerability(
            damage_stat=DOT_VULNERABILITY_STAT,
            percent_per_stack=effect.get("percent_per_stack", 15),
            stacks=1,
            max_stacks=effect.get("max_stacks", 3),
            source=source,
        ))
    total = target.total_vulnerability_percent(DOT_VULNERABILITY_STAT)
    log.append(
        f"☣️ {target.name} is destabilised ({stacks_now}x) -- "
        f"damage-over-time on it deals +{total:g}% damage."
    )

GUARD_DAMAGE_REDUCTION_PERCENT = 50
# Energy banked when a guarded combatant is actually hit. Roughly a third
# of an ultimate, so two well-read guards meaningfully accelerate one.
GUARD_ENERGY_ON_HIT = 15
# Guard also builds resources like a basic attack does, at a reduced rate
# -- guarding is a tempo choice, not a free turn.
GUARD_RECHARGE_MULTIPLIER = 0.5

# ----------------------------------------------------------------------
# PLAYER ENERGY ECONOMY (bug fix: character ultimates were never cast).
#
# Energy used to come from exactly two places: a basic Attack, and Guard.
# Using a SKILL granted none. That is not a tuning problem, it's a dead
# mechanic: a character's skill is strictly better than their basic
# attack in almost every situation and is usually off cooldown every
# turn, so playing well meant never attacking, and never attacking meant
# never charging. Measured over 300 simulated fights, a squad using its
# skills whenever available cast ZERO ultimates in ~13,000 player turns
# -- and quadrupling Recharge changed nothing, because Recharge scales a
# gain that was never triggered.
#
# Every action a combatant takes now builds energy:
#
#   * Attack -- energy AND mana (unchanged). Attack keeps its exclusive
#     role as the ONLY source of SP, which is what stops it from becoming
#     a strictly-worse button now that it isn't the only way to charge.
#   * Skill / Ultimate -- energy only, at ABILITY_ENERGY_MULTIPLIER of
#     the attack rate. Slightly under attacking, so there's still a
#     reason to weave basics in beyond mana.
#   * Guard -- half rate, plus GUARD_ENERGY_ON_HIT if a hit lands
#     (unchanged).
#   * Taking a hit -- ENERGY_ON_TAKING_HIT, flat. This exists so the
#     characters who charge SLOWEST under an action-based rule are the
#     ones being attacked, which is exactly backwards otherwise: a
#     Sustain spending turns healing while soaking damage should reach
#     their ultimate sooner than a DPS standing untouched, not later.
#
# Deliberately mirrors the enemy rule (see ENEMY_ENERGY_PER_ACTION in
# battle.py) so "how does anything charge its ultimate" has one answer.
# ----------------------------------------------------------------------
ABILITY_ENERGY_MULTIPLIER = 0.8
ENERGY_ON_TAKING_HIT = 4


def grant_action_energy(actor: Combatant, log: list, multiplier: float = 1.0) -> None:
    """Energy (no mana) for taking a non-Attack action. Attack routes
    through gain_energy_and_mana instead, since it uniquely grants both.
    Silent by default -- these fire on literally every action, and a log
    line per action was the single noisiest thing in the battle log."""
    pct = max(0.0, actor.effective_stat("recharge")) * multiplier
    gained = int(round(actor.max_energy * pct / 100))
    if gained <= 0:
        return
    actor.gain_energy(gained)


def apply_stun(target: Combatant, duration: int, log: list) -> None:
    """Stun `target` for `duration` turns.

    Takes the MAXIMUM of the existing and new duration rather than adding
    them. Every stun in the game used to be `stunned_turns += duration`,
    which meant two enemies landing a 1-turn stun on the same character
    produced a 2-turn lockout, three produced 3, and a party facing
    several stun-carriers could lose a member for the rest of the fight
    with no counterplay and nothing on screen explaining why.

    Overlapping stuns now refresh rather than accumulate, which is the
    behaviour players already expect from every other duration effect
    here."""
    if duration <= 0:
        return
    already = target.stunned_turns > 0
    target.stunned_turns = max(target.stunned_turns, duration)
    log.append(f"😵 {target.name} is {'still ' if already else ''}stunned!")


def poise_damage_for(ability: dict | None) -> int:
    """How much poise one hit from `ability` chips. None means a basic
    attack. An explicit "poise_damage" in the ability's effect wins, so a
    designed guard-breaker can be tuned without touching this module."""
    if ability is None:
        return POISE_DAMAGE_BASIC
    override = ability.get("effect", {}).get("poise_damage")
    if override is not None:
        return int(override)
    return POISE_DAMAGE_ULTIMATE if ability.get("is_ultimate") else POISE_DAMAGE_ABILITY


def resolve_basic_attack(
    attacker: Combatant, defender: Combatant, rng: random.Random, log: list,
    defender_allies: list[Combatant] | None = None,
    attacker_allies: list[Combatant] | None = None,
) -> None:
    """`defender_allies` is every OTHER living combatant on defender's own
    side -- only used by defender-reactive team-oriented passives (e.g.
    on_hit_team_buff, see _resolve_hit). Safe to omit; those passives
    simply won't have anyone else to buff if it's left out."""
    defender_allies = defender_allies or []
    _resolve_hit(attacker, defender, damage_percent=100, damage_stat="attack", rng=rng, log=log,
                 defender_allies=defender_allies, attacker_allies=attacker_allies or [])
    energy_gained, mana_gained = attacker.gain_energy_and_mana()
    if energy_gained or mana_gained:
        log.append(f"{attacker.name} gains {energy_gained} energy and {mana_gained} SP.")


def resolve_guard(actor: Combatant, log: list) -> None:
    """The Guard action. Raises the actor's guard until their next turn
    begins (battle.py's _begin_turn clears it), halving incoming damage
    for that window and paying out bonus energy on any hit that lands
    while it's up -- see _resolve_hit.

    Guard still builds resources, at a reduced rate versus attacking, so
    it's a tempo trade rather than a strictly-worse or strictly-free turn:
    you give up this turn's damage to blunt an incoming one and come out
    slightly closer to your ultimate."""
    actor.guarding = True
    energy_gained, mana_gained = actor.gain_energy_and_mana(
        actor.effective_stat("recharge") * GUARD_RECHARGE_MULTIPLIER
    )
    log.append(f"🛡️ {actor.name} raises their guard.")
    if energy_gained or mana_gained:
        log.append(f"{actor.name} gains {energy_gained} energy and {mana_gained} SP.")


# Effect kinds that land on exactly ONE ally and therefore accept a
# player-chosen recipient (see _pick_ally). Exported so the combat UIs can
# decide whether to offer an ally selector for the acting character
# without duplicating this list in three cogs -- and, more importantly, so
# adding a sixth single-ally kind later can't silently ship without its
# selector.
ALLY_TARGET_KINDS = frozenset({
    "heal_lowest_ally_percent_max_hp",
    "sacrifice_hp_heal_lowest_ally_percent_max_hp",
    "ally_buff",
    "restore_resource_to_lowest_ally",
    "cleanse_ally_and_heal",
    "shield_ally_percent_max_hp",
})


# Effect kinds that hit or affect EVERY combatant on the opposing side
# rather than one target. The enemy intent telegraph has to know these:
# it was naming a single victim for an ability that hits the whole squad,
# which is worse than showing nothing -- a player would Guard the named
# character believing the rest were safe.
AOE_OPPONENT_KINDS = frozenset({
    "aoe_damage",
    "aoe_damage_chance_debuff",
    "aoe_damage_chance_dot",
    "aoe_damage_chance_poise_strike",
    "aoe_damage_chance_dot_amplify",
    "damage_all_and_debuff_self",
    "team_debuff",
    "team_dot_amplify",
    "team_poise_strike",
})

# Effect kinds that affect the CASTER'S OWN whole side (buffs, team heals,
# team shields). Shown as "whole squad"/"all allies" rather than a target
# name, for the same reason.
TEAM_SELF_KINDS = frozenset({
    "team_heal_percent_max_hp",
    "team_buff",
    "team_double_buff",
    "team_buff_and_resource",
    "team_resource_restore",
    "team_regen_over_time",
    "team_shield_percent_max_hp",
    "team_shield_and_buff",
    "team_heal_and_buff",
    "team_shield_and_cleanse",
    "sacrifice_hp_heal_team_percent_max_hp",
    "sacrifice_hp_team_buff",
    "taunt_and_team_shield",
})

# Kinds that only ever affect the caster.
SELF_ONLY_KINDS = frozenset({
    "heal_percent_max_hp",
    "self_buff_debuff",
    "heal_and_self_buff",
    "cleanse_self_and_heal",
    "self_shield_percent_max_hp",
    "taunt_and_shield",
})


def ability_scope(ability: dict | None) -> str:
    """How wide an ability's effect is: "aoe" (every opponent), "team"
    (the caster's whole side), "self", or "single".

    Used by the enemy intent telegraph so an AOE reads as "everyone"
    instead of naming one arbitrary victim. Keyed off the effect kind
    rather than a hand-set flag on each ability, so a new AOE ability
    can't ship without its telegraph being right -- the only thing an
    author has to get correct is the kind, which they already must."""
    if not ability:
        return "single"
    kind = ability.get("effect", {}).get("kind")
    if kind in AOE_OPPONENT_KINDS:
        return "aoe"
    if kind in TEAM_SELF_KINDS:
        return "team"
    if kind in SELF_ONLY_KINDS:
        return "self"
    return "single"


def ability_targets_ally(ability: dict | None) -> bool:
    """Whether `ability` lets the player choose which ally it affects."""
    if not ability:
        return False
    return ability.get("effect", {}).get("kind") in ALLY_TARGET_KINDS


def combatant_has_ally_targeting(combatant) -> bool:
    """True if any ability this combatant could use on their turn takes an
    ally target -- the condition for showing an ally selector."""
    if ability_targets_ally(combatant.ultimate_ability):
        return True
    return any(ability_targets_ally(a) for a in combatant.active_abilities)


def _pick_ally(
    attacker: Combatant,
    allies: list[Combatant],
    chosen_ally: Combatant | None,
    auto: "callable",
    include_self: bool,
) -> Combatant:
    """Resolves WHO a single-ally support effect lands on.

    Player-controlled combatants get to choose (`chosen_ally`, threaded
    down from Battle.ally_target_index -- see battle.py). Enemies, and any
    case where the chosen ally is missing or has since died, fall back to
    `auto`, the effect's own "who needs it most" heuristic.

    WHY THE CHOICE EXISTS. Auto-targeting made every support ability
    deterministic: there was no decision to make, so a Sustain player's
    turn was "press the heal and see who gets it". It was also frequently
    just wrong -- lowest HP% is a poor proxy for who's about to be
    attacked, and the enemy intent telegraph (which now shows the target
    a turn or more ahead) means the player often knows perfectly well who
    needs the shield and had no way to say so.

    `include_self` mirrors each effect's existing rule about whether the
    caster is a legal recipient: a plain heal may land on the caster, but
    the Blood-Sustain sacrifice kinds pointedly may not (paying your own
    HP to heal yourself is a no-op). A player who explicitly picks
    themself on a caster-excluded ability is honoured anyway -- if
    they've read the ability and still chose it, that's their call, and
    silently retargeting a deliberate choice is worse than letting it be
    a bad one."""
    living = [a for a in allies if a.is_alive()]
    if chosen_ally is not None and chosen_ally.is_alive():
        if chosen_ally is attacker:
            if include_self:
                return attacker
            # Caster-excluded effect, but the player asked for themself.
            return attacker
        if chosen_ally in living:
            return chosen_ally
    candidates = ([attacker] + living) if include_self else living
    if not candidates:
        return attacker
    return auto(candidates)


def resolve_active_ability(
    attacker: Combatant, defender: Combatant, ability: dict, rng: random.Random, log: list,
    allies: list[Combatant] | None = None, opponents: list[Combatant] | None = None,
    chosen_ally: Combatant | None = None,
) -> None:
    """`allies` is every OTHER living combatant on attacker's side (not
    including attacker) -- only used by team-oriented effect kinds
    (team_heal_percent_max_hp, heal_lowest_ally_percent_max_hp, team_buff,
    team_resource_restore, team_regen_over_time), introduced for the Combat
    Overhaul's Sustain/Amplifier/Support DPS character kits
    (bot/game/combat/skills.py). `opponents` is every living combatant on
    the OTHER side (including defender) -- used by team_debuff, AND as the
    source for `defender_allies`/`target_allies` below (every OTHER living
    member of whichever side is on the receiving end of a given hit) --
    used by defender-reactive team passives like on_hit_team_buff. Every
    other effect kind ignores all of this, so they're safe to omit for
    simple 1v1-style abilities.

    `chosen_ally` is the PLAYER'S explicitly picked recipient for the
    single-ally support kinds (heal_lowest_ally_percent_max_hp,
    cleanse_ally_and_heal, restore_resource_to_lowest_ally, ally_buff,
    sacrifice_hp_heal_lowest_ally_percent_max_hp). None -- always, for
    enemies -- keeps the original automatic "whoever needs it most"
    behaviour. See _pick_ally."""
    allies = allies or []
    opponents = opponents if opponents is not None else [defender]
    defender_allies = [o for o in opponents if o is not defender and o.is_alive()]
    attacker.spend_resource(ability)
    # Using an ability builds energy toward the NEXT ultimate -- see the
    # PLAYER ENERGY ECONOMY block above for why this has to exist.
    # Granted after spend_resource so an ultimate can't partially refund
    # itself on the same cast.
    grant_action_energy(attacker, log, multiplier=ABILITY_ENERGY_MULTIPLIER)
    icon = "💥" if ability.get("is_ultimate") else "✨"
    log.append(f"{icon} {attacker.name} uses {ability['name']}!")

    effect = ability["effect"]
    kind = effect["kind"]

    # Every hit this ability lands chips the same amount of poise (see
    # poise_damage_for). Bound once here and applied through the _hit
    # wrapper below rather than repeated as an argument on all ~20
    # _resolve_hit calls in this dispatcher -- and, because the wrapper is
    # per-hit rather than per-ability, a multi_hit ability chips once per
    # swing and an AOE once per target, for free.
    _ability_poise = poise_damage_for(ability)

    def _hit(*args, **kwargs):
        kwargs.setdefault("poise_damage", _ability_poise)
        # Also injects the caster's own side, which _resolve_hit needs
        # for team-scoped kit reactions (a break passive that rewards the
        # squad). Done here rather than on ~20 individual _hit calls.
        kwargs.setdefault("attacker_allies", allies)
        return _resolve_hit(*args, **kwargs)

    if kind == "damage_multiplier":
        _hit(attacker, defender, effect["damage_percent"],
                     effect.get("damage_stat", "attack"), rng, log, defender_allies=defender_allies)

    elif kind == "damage_and_dot":
        hit = _hit(attacker, defender, effect["damage_percent"],
                            effect.get("damage_stat", "attack"), rng, log, defender_allies=defender_allies)
        if hit and defender.is_alive():
            flat_amount = attacker.effective_stat(effect["dot_stat"]) * effect["dot_percent"] / 100
            for passive in attacker.find_passive("dot_amplifier"):
                flat_amount *= 1 + passive["effect"]["percent"] / 100
            defender.dots.append(DamageOverTime(
                flat_amount=flat_amount, duration=effect["duration"],
                source=ability["name"], stat_source=effect["dot_stat"],
            ))
            log.append(f"{defender.name} is burning!")

    elif kind == "damage_and_debuff":
        hit = _hit(attacker, defender, effect["damage_percent"],
                            effect.get("damage_stat", "attack"), rng, log, defender_allies=defender_allies)
        if hit and defender.is_alive():
            defender.modifiers.append(StatModifier(
                stat=effect["debuff_stat"], percent=effect["debuff_percent"],
                duration=effect["duration"], source=ability["name"],
            ))
            log.append(f"{defender.name}'s {effect['debuff_stat']} is reduced!")

    elif kind == "apply_vulnerability_stack":
        # Marks a single target with a stacking Vulnerability instead of a
        # StatModifier debuff -- see status.Vulnerability. Repeat casts
        # (matched by this ability's name as the `source`) add another
        # stack onto the SAME instance rather than creating a new one.
        hit = _hit(attacker, defender, effect["damage_percent"],
                            effect.get("damage_stat", "attack"), rng, log, defender_allies=defender_allies)
        if hit and defender.is_alive():
            existing = next(
                (v for v in defender.vulnerabilities
                 if v.damage_stat == effect["vulnerable_damage_stat"] and v.source == ability["name"]),
                None,
            )
            if existing is not None:
                existing.stacks = min(existing.max_stacks, existing.stacks + 1)
            else:
                defender.vulnerabilities.append(Vulnerability(
                    damage_stat=effect["vulnerable_damage_stat"],
                    percent_per_stack=effect["percent_per_stack"],
                    stacks=1, max_stacks=effect["max_stacks"], source=ability["name"],
                ))
            stacks_now = next(
                v.stacks for v in defender.vulnerabilities
                if v.damage_stat == effect["vulnerable_damage_stat"] and v.source == ability["name"]
            )
            log.append(
                f"🎯 {defender.name} is marked ({stacks_now}x) -- "
                f"takes increased {effect['vulnerable_damage_stat']} damage!"
            )

    elif kind == "heal_percent_max_hp":
        healed = attacker.heal(attacker.max_hp * effect["percent"] / 100)
        log.append(f"💚 {attacker.name} heals {healed} HP.")

    elif kind == "damage_and_stun":
        hit = _hit(attacker, defender, effect["damage_percent"],
                            effect.get("damage_stat", "attack"), rng, log, defender_allies=defender_allies)
        # Stun is a CHANCE, not a guarantee.
        #
        # This used to stun on every landed hit, with no roll at all. On
        # the player's side that's merely strong; on the enemy side it
        # was the single most oppressive thing in the game, because
        # sixteen enemy templates carry a stun source and losing a turn
        # outright is the one effect you cannot play around. Shield Bash
        # in particular sat at a 1-turn cooldown and 10 SP, so a single
        # enemy could deny a party member every other turn indefinitely.
        #
        # Abilities that don't specify a chance keep working (defaulting
        # to certain) so nothing silently changes shape -- the ones that
        # needed reining in state their odds explicitly.
        chance = effect.get("chance_percent", 100)
        if hit and defender.is_alive() and rng.uniform(0, 100) < chance:
            apply_stun(defender, effect["duration"], log)

    elif kind == "self_buff_debuff":
        attacker.modifiers.append(StatModifier(
            effect["buff_stat"], effect["buff_percent"], effect["duration"], ability["name"]
        ))
        attacker.modifiers.append(StatModifier(
            effect["debuff_stat"], effect["debuff_percent"], effect["duration"], ability["name"]
        ))
        log.append(f"{attacker.name} is empowered!")

    elif kind == "damage_execute_heal":
        hit = _hit(attacker, defender, effect["damage_percent"],
                            effect.get("damage_stat", "attack"), rng, log, defender_allies=defender_allies)
        if hit and not defender.is_alive():
            # Read with a fallback rather than a bare subscript: this
            # branch only runs on a KILL, so a missing key here is a
            # crash that hides until the ability succeeds. Accepting the
            # obvious misspelling costs nothing and turns a hard failure
            # into a working heal.
            percent = effect.get("heal_percent_on_kill", effect.get("heal_percent", 0))
            healed = attacker.heal(attacker.max_hp * percent / 100)
            log.append(f"🔥 {attacker.name} is reinvigorated, healing {healed} HP!")

    elif kind == "multi_hit":
        for _ in range(effect["hits"]):
            if not defender.is_alive():
                break
            _hit(attacker, defender, effect["damage_percent_per_hit"],
                         effect.get("damage_stat", "attack"), rng, log, suppress_kill_log=True, defender_allies=defender_allies)
        _trigger_on_kill_if_dead(attacker, defender, log, allies)

    elif kind == "damage_and_heal_self":
        hit = _hit(attacker, defender, effect["damage_percent"],
                            effect.get("damage_stat", "attack"), rng, log, defender_allies=defender_allies)
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
        hit = _hit(attacker, defender, effect["damage_percent"],
                            effect.get("damage_stat", "attack"), rng, log, defender_allies=defender_allies)
        attacker.modifiers.append(StatModifier(
            effect["debuff_stat"], effect["debuff_percent"], effect["duration"], ability["name"]
        ))

    elif kind == "heal_lowest_ally_percent_max_hp":
        # Sustain/Support "single-target heal" kit piece. The player picks
        # the recipient when they've chosen one; otherwise it falls back
        # to whoever (including the caster) is lowest on HP%. See _pick_ally.
        target = _pick_ally(
            attacker, allies, chosen_ally,
            auto=lambda cs: min(cs, key=lambda c: c.current_hp / max(1, c.max_hp)),
            include_self=True,
        )
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
        # Fall back to the normal damage number rather than subscripting.
        # The execute branch only runs against a LOW-HP target, so a
        # missing key here is a crash that hides until the ability is
        # doing its job -- exactly how Gostley's Last Rites shipped.
        percent = (effect.get("execute_damage_percent", effect["damage_percent"])
                   if is_execute else effect["damage_percent"])
        _hit(attacker, defender, percent, effect.get("damage_stat", "attack"), rng, log, defender_allies=defender_allies)
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

    elif kind == "damage_and_poise_strike":
        # Replaces the removed damage_and_resource_drain. Energy/mana
        # drain is gone from the game entirely (it made a fight worse
        # without making it more interesting -- there is no counterplay to
        # "your ultimate is further away now", it just subtracts). The
        # replacement pays into the poise economy instead: a heavy,
        # break-focused hit that chips far more poise than its damage
        # alone would. Same "disrupt the enemy's turn" fantasy, but the
        # payoff is a break the player can see coming and build toward.
        if effect.get("poise_shred"):
            apply_poise_shred(defender, effect["poise_shred"], log, source=ability["name"])
        _hit(attacker, defender, effect["damage_percent"],
             effect.get("damage_stat", "attack"), rng, log,
             defender_allies=defender_allies,
             poise_damage=poise_damage_for(ability) + effect.get("bonus_poise", 0))

    elif kind == "damage_and_dot_amplify":
        # The other half of the drain replacement: a mark that makes every
        # damage-over-time effect ticking on the target hurt more. Routed
        # through status.Vulnerability with damage_stat "dot" (see
        # DOT_VULNERABILITY_STAT) rather than a bespoke status, so it
        # stacks, serializes, and displays through plumbing that already
        # exists.
        hit = _hit(attacker, defender, effect["damage_percent"],
                   effect.get("damage_stat", "attack"), rng, log, defender_allies=defender_allies)
        if hit and defender.is_alive():
            _apply_dot_vulnerability(defender, ability, effect, log)

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
        _hit(attacker, defender, total_percent, effect.get("damage_stat", "elemental"), rng, log, defender_allies=defender_allies)

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
        target = _pick_ally(
            attacker, allies, chosen_ally,
            auto=lambda cs: min(cs, key=lambda c: c.current_hp / max(1, c.max_hp)),
            include_self=False,
        )
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

    elif kind == "sacrifice_hp_team_buff":
        # Blood-Sustain's buff sibling -- same self-cost-via-take_raw_hp_loss
        # payment as the sacrifice_hp_heal_* kinds above, but empowers the
        # whole side (caster INCLUDED, unlike the heal versions -- this one
        # is "give everyone, including yourself, an edge," not "give away
        # your own vitality") with a StatModifier instead of healing them.
        self_cost = attacker.max_hp * effect["self_cost_percent"] / 100
        paid = attacker.take_raw_hp_loss(self_cost)
        if paid:
            log.append(f"🩸 {attacker.name} sacrifices {paid} HP to fuel {ability['name']}.")
        for member in [attacker] + [a for a in allies if a.is_alive()]:
            member.modifiers.append(StatModifier(
                effect["buff_stat"], effect["buff_percent"], effect["duration"], ability["name"]
            ))
        log.append(f"📡 {attacker.name}'s {ability['name']} empowers the whole team!")
        _trigger_on_low_hp(attacker, log)

    elif kind == "damage_and_double_debuff":
        # Debuff-specialist kit piece (Axel) -- like damage_and_debuff but
        # strips down TWO stats on the target at once (e.g. ATK and DEF),
        # for characters built around dismantling a target rather than
        # just chipping DEF for a follow-up hit.
        hit = _hit(attacker, defender, effect["damage_percent"],
                            effect.get("damage_stat", "attack"), rng, log, defender_allies=defender_allies)
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
        target = _pick_ally(
            attacker, allies, chosen_ally,
            auto=lambda cs: min(cs, key=lambda c: c.effective_stat(effect["buff_stat"])),
            include_self=False,
        )
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
        def _resource_ratio(c):
            pool = c.max_energy + c.max_mana
            return (c.energy + c.mana) / pool if pool else 0

        target = _pick_ally(
            attacker, allies, chosen_ally,
            auto=lambda cs: min(cs, key=_resource_ratio),
            include_self=False,
        )
        energy_gained = min(target.max_energy - target.energy, effect.get("energy_amount", 0))
        mana_gained = min(target.max_mana - target.mana, effect.get("mana_amount", 0))
        energy_gained = target.gain_energy(energy_gained)
        target.mana += mana_gained
        if energy_gained or mana_gained:
            log.append(f"🔋 {target.name} gains {energy_gained} energy and {mana_gained} SP from {attacker.name}'s {ability['name']}.")

    elif kind == "cleanse_ally_and_heal":
        # Single-target cleanse support piece (Aura) -- the ally-facing
        # counterpart to cleanse_self_and_heal. Picks whichever living ally
        # is lowest on HP% (never the caster), strips their debuffs/DOTs,
        # and heals them. Falls back to cleansing/healing the caster if no
        # ally is alive.
        target = _pick_ally(
            attacker, allies, chosen_ally,
            auto=lambda cs: min(cs, key=lambda c: c.current_hp / max(1, c.max_hp)),
            include_self=False,
        )
        removed = len([m for m in target.modifiers if m.percent < 0]) + len(target.dots)
        target.modifiers = [m for m in target.modifiers if m.percent >= 0]
        target.dots = []
        healed = target.heal(target.max_hp * effect["heal_percent"] / 100)
        log.append(f"🛠️ {attacker.name}'s {ability['name']} purges {removed} negative effect(s) from {target.name} and heals {healed} HP.")

    elif kind == "team_dot_amplify":
        # Replaces the removed team_resource_drain. Marks EVERY living
        # enemy so that damage-over-time on them hits harder -- the
        # team-wide setup counterpart to damage_and_dot_amplify, and a
        # natural partner for the AOE-DoT kits (Blueflame, Slikrz) that
        # had nothing to combo with before.
        for target in [o for o in opponents if o.is_alive()]:
            _apply_dot_vulnerability(target, ability, effect, log)

    elif kind == "team_poise_strike":
        # Team-wide poise pressure: chips poise off every living enemy at
        # once with no damage attached. The other replacement shape for
        # the removed drain kinds -- "shut the whole enemy line down" as a
        # break-setup tool rather than a resource tax.
        amount = effect.get("poise_damage", 2) + total_poise_damage_bonus(attacker)
        for target in [o for o in opponents if o.is_alive()]:
            if effect.get("poise_shred"):
                apply_poise_shred(target, effect["poise_shred"], log, source=ability["name"])
            if target.damage_poise(amount):
                target.enter_break(BREAK_DURATION_TURNS)
                log.append(
                    f"💥 {target.name}'s poise SHATTERS! Its move is cancelled and it "
                    f"takes +{_break_damage_percent(attacker)}% damage for {BREAK_DURATION_TURNS} turns."
                )
            elif target.can_be_broken():
                log.append(f"🔨 {target.name}'s guard buckles ({target.poise}/{target.max_poise} poise).")

    elif kind == "team_buff_and_resource":
        # Amplifier class-identity pass (see the ROLE CONTRACT block in
        # bot/game/combat/skills.py). A team stat buff with a resource
        # restore riding along on it. Exists so that characters whose
        # FLAVOR is resource logistics (Caandy's visor sync, Jofrog's
        # battery swap, Virtual's drone resupply) still amplify -- which
        # is what their class promises -- without losing the flavor that
        # made them distinct. The buff is the point; the resource is the
        # garnish.
        for member in [attacker] + [a for a in allies if a.is_alive()]:
            member.modifiers.append(StatModifier(
                stat=effect["buff_stat"], percent=_buffed(attacker, effect["buff_percent"]),
                duration=effect["duration"], source=ability["name"],
            ))
            energy_gained = min(member.max_energy - member.energy, effect.get("energy_amount", 0))
            mana_gained = min(member.max_mana - member.mana, effect.get("mana_amount", 0))
            energy_gained = member.gain_energy(energy_gained)
            member.mana += mana_gained
        log.append(
            f"📡 {attacker.name}'s {ability['name']} boosts the team's {effect['buff_stat']} "
            f"by {effect['buff_percent']}% for {effect['duration']} turns"
            + (f", and restores {effect.get('energy_amount', 0)} energy / {effect.get('mana_amount', 0)} SP each."
               if effect.get("energy_amount") or effect.get("mana_amount") else ".")
        )

    elif kind == "team_double_buff":
        # Two stat buffs on the whole team from one cast -- the team-wide
        # sibling of self_buff_debuff's two-stat shape. Added for the
        # Amplifier pass so an Amplifier ultimate can feel like a bigger
        # deal than its own skill without simply printing a larger number
        # on the same single stat.
        for member in [attacker] + [a for a in allies if a.is_alive()]:
            for stat_key, pct_key in (("buff_stat_1", "buff_percent_1"), ("buff_stat_2", "buff_percent_2")):
                member.modifiers.append(StatModifier(
                    stat=effect[stat_key], percent=_buffed(attacker, effect[pct_key]),
                    duration=effect["duration"], source=ability["name"],
                ))
        log.append(
            f"📡 {attacker.name}'s {ability['name']} boosts the team's "
            f"{effect['buff_stat_1']} by {effect['buff_percent_1']}% and "
            f"{effect['buff_stat_2']} by {effect['buff_percent_2']}% for {effect['duration']} turns."
        )

    elif kind == "team_shield_and_buff":
        # Sustain class-identity pass (see the ROLE CONTRACT block in
        # skills.py): shields the whole team AND hardens it, so a Sustain
        # ultimate can be defensively decisive without just being a bigger
        # heal number than the last one.
        for member in [attacker] + [a for a in allies if a.is_alive()]:
            gained = grant_shield(attacker, member, effect["shield_percent"])
            member.modifiers.append(StatModifier(
                stat=effect["buff_stat"], percent=_buffed(attacker, effect["buff_percent"]),
                duration=effect["duration"], source=ability["name"],
            ))
            if gained:
                log.append(f"🔷 {member.name} gains a {round(gained)} HP shield.")
        log.append(
            f"🛡️ {attacker.name}'s {ability['name']} raises the team's "
            f"{effect['buff_stat']} by {effect['buff_percent']}% for {effect['duration']} turns."
        )

    elif kind == "team_heal_and_buff":
        # Sustain shape: an instant team heal plus a defensive stat buff.
        # Same reasoning as team_shield_and_buff -- gives Sustain kits a
        # second axis (mitigation) so they aren't all competing on
        # healing throughput alone.
        for member in [attacker] + [a for a in allies if a.is_alive()]:
            healed = member.heal(member.max_hp * effect["heal_percent"] / 100)
            member.modifiers.append(StatModifier(
                stat=effect["buff_stat"], percent=_buffed(attacker, effect["buff_percent"]),
                duration=effect["duration"], source=ability["name"],
            ))
            if healed:
                log.append(f"💚 {member.name} heals {healed} HP.")
        log.append(
            f"🛡️ {attacker.name}'s {ability['name']} raises the team's "
            f"{effect['buff_stat']} by {effect['buff_percent']}% for {effect['duration']} turns."
        )

    elif kind == "team_resource_restore":
        # Instant support burst -- restores flat energy and/or mana to the
        # caster's whole side at once (as opposed to Arcane Battery-style
        # passives, which trickle a smaller amount every turn).
        for member in [attacker] + [a for a in allies if a.is_alive()]:
            energy_gained = min(member.max_energy - member.energy, effect.get("energy_amount", 0))
            mana_gained = min(member.max_mana - member.mana, effect.get("mana_amount", 0))
            energy_gained = member.gain_energy(energy_gained)
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

    elif kind == "taunt_and_shield":
        # The tank button (see the TAUNT block in combatant.py). Pulls the
        # opposing side's single-target attacks onto the caster AND gives
        # them something to survive it with -- the two halves are one
        # ability on purpose, because a taunt without mitigation is just a
        # slower way to die, and a shield without a taunt doesn't protect
        # the squishy character the enemy was actually aiming at.
        gained = grant_shield(attacker, attacker, effect.get("shield_percent", 0))
        attacker.taunt_turns = max(attacker.taunt_turns, effect.get("duration", 2))
        if effect.get("buff_stat"):
            attacker.modifiers.append(StatModifier(
                stat=effect["buff_stat"], percent=effect["buff_percent"],
                duration=effect.get("duration", 2), source=ability["name"],
            ))
        log.append(
            f"🎯 {attacker.name} draws every attack for {attacker.taunt_turns} turn(s)"
            + (f" behind a {round(gained)} HP shield!" if gained else "!")
        )

    elif kind == "taunt_and_team_shield":
        # Ultimate-scale version: taunt onto the caster, but the shield
        # goes to the WHOLE squad. Taunting means the caster eats the
        # single-target damage while the team's shields absorb whatever
        # AOE still gets through -- which is the one combination that
        # makes a dedicated shielder better than a healer for a turn.
        attacker.taunt_turns = max(attacker.taunt_turns, effect.get("duration", 2))
        for member in [attacker] + [a for a in allies if a.is_alive()]:
            gained = grant_shield(attacker, member, effect["shield_percent"])
            if gained:
                log.append(f"🔷 {member.name} gains a {round(gained)} HP shield.")
        log.append(f"🎯 {attacker.name} draws every attack for {attacker.taunt_turns} turn(s)!")

    elif kind == "damage_and_self_taunt":
        # Enemy-facing shape (and usable by a player bruiser): hit
        # something, then force the other side to deal with you. This is
        # what stops the player from simply ignoring a defensive enemy
        # and bursting the healer standing behind it.
        _hit(attacker, defender, effect["damage_percent"],
             effect.get("damage_stat", "attack"), rng, log, defender_allies=defender_allies)
        attacker.taunt_turns = max(attacker.taunt_turns, effect.get("duration", 2))
        log.append(f"🎯 {attacker.name} demands attention -- attacks are forced onto it for {attacker.taunt_turns} turn(s)!")

    elif kind == "shield_ally_percent_max_hp":
        # Single-ALLY shield -- the shielder's counterpart to
        # heal_lowest_ally_percent_max_hp, and player-targetable through
        # the same ally selector (see ALLY_TARGET_KINDS). Shielding the
        # character an enemy has TELEGRAPHED an attack on is the most
        # direct use of the intent preview in the game, and it needed a
        # single-target shield to exist at all.
        target = _pick_ally(
            attacker, allies, chosen_ally,
            auto=lambda cs: min(cs, key=lambda c: c.current_hp / max(1, c.max_hp)),
            include_self=True,
        )
        gained = grant_shield(attacker, target, effect["percent"])
        log.append(f"🔷 {attacker.name}'s {ability['name']} shields {target.name} for {round(gained)} HP.")

    elif kind == "team_shield_and_cleanse":
        # Shielder ultimate shape: absorb AND purge. Distinct from the
        # healers' cleanse (cleanse_ally_and_heal, single target) by
        # covering the whole squad, which is what a dedicated shielder
        # should be better at than a healer.
        for member in [attacker] + [a for a in allies if a.is_alive()]:
            removed = len([m for m in member.modifiers if m.percent < 0]) + len(member.dots)
            member.modifiers = [m for m in member.modifiers if m.percent >= 0]
            member.dots = []
            gained = grant_shield(attacker, member, effect["shield_percent"])
            if gained or removed:
                log.append(
                    f"🔷 {member.name} gains a {round(gained)} HP shield"
                    + (f" and sheds {removed} negative effect(s)." if removed else ".")
                )

    elif kind == "self_shield_percent_max_hp":
        # Ionic Ward-style burst shield -- grants the caster a flat
        # HP-equivalent pool (Combatant.shield) that absorbs incoming
        # damage before current_hp does (see _resolve_hit). Adds onto any
        # shield already up rather than overwriting it.
        gained = grant_shield(attacker, attacker, effect["percent"])
        log.append(f"🔷 {attacker.name} raises a shield worth {round(gained)} HP.")

    elif kind == "team_shield_percent_max_hp":
        # Aegis Broadcast-style team shield -- same idea as
        # self_shield_percent_max_hp but for the caster's whole side at
        # once, each member shielded off their OWN max HP.
        for member in [attacker] + [a for a in allies if a.is_alive()]:
            grant_shield(attacker, member, effect["percent"])
        log.append(f"🔷 {attacker.name}'s {ability['name']} shields the whole team!")

    elif kind == "damage_bonus_if_debuffed":
        # Weakpoint Scanner-style finisher -- deals extra damage if the
        # target already has ANY active negative StatModifier (from
        # anything -- a debuff kind on gear, a character skill, doesn't
        # matter which), rewarding follow-up damage after a debuff lands.
        has_debuff = any(m.percent < 0 for m in defender.modifiers)
        percent = effect["damage_percent"] + (effect["bonus_damage_percent"] if has_debuff else 0)
        _hit(attacker, defender, percent, effect.get("damage_stat", "attack"), rng, log, defender_allies=defender_allies)
        if has_debuff:
            log.append(f"🎯 {attacker.name} exploits {defender.name}'s weakened state!")

    elif kind == "chance_double_hit":
        # Riftcutter-style flat percent chance to swing again immediately
        # for the same damage. The first hit always lands; the second is
        # gated behind chance_percent and skipped if the first hit already
        # finished the target.
        _hit(attacker, defender, effect["damage_percent"],
                     effect.get("damage_stat", "attack"), rng, log, suppress_kill_log=True, defender_allies=defender_allies)
        if defender.is_alive() and formulas.roll_percent(effect["chance_percent"], rng):
            log.append(f"⚡ {attacker.name}'s {ability['name']} strikes again!")
            _hit(attacker, defender, effect["damage_percent"],
                         effect.get("damage_stat", "attack"), rng, log, suppress_kill_log=True, defender_allies=defender_allies)
        _trigger_on_kill_if_dead(attacker, defender, log, allies)

    elif kind == "aoe_damage":
        # Support DPS AOE kind (Combat Overhaul role shift) -- hits every
        # living enemy at once for the same damage_percent, instead of
        # dumping it all into one target the way the class used to.
        for target in [o for o in opponents if o.is_alive()]:
            target_allies = [o for o in opponents if o is not target and o.is_alive()]
            _hit(attacker, target, effect["damage_percent"],
                         effect.get("damage_stat", "attack"), rng, log, defender_allies=target_allies)
        log.append(f"💥 {attacker.name}'s {ability['name']} sweeps the whole enemy side!")

    elif kind == "aoe_damage_chance_debuff":
        # Support DPS AOE-plus-debuff kind -- hits every living enemy at
        # once, and each hit target independently has debuff_chance_percent
        # odds of also picking up a stat debuff. "Sometimes applies
        # debuffs" is the point: unlike damage_and_debuff, it's not
        # guaranteed on every cast.
        for target in [o for o in opponents if o.is_alive()]:
            target_allies = [o for o in opponents if o is not target and o.is_alive()]
            hit = _hit(attacker, target, effect["damage_percent"],
                                effect.get("damage_stat", "attack"), rng, log, defender_allies=target_allies)
            if hit and target.is_alive() and formulas.roll_percent(effect["debuff_chance_percent"], rng):
                target.modifiers.append(StatModifier(
                    stat=effect["debuff_stat"], percent=effect["debuff_percent"],
                    duration=effect["duration"], source=ability["name"],
                ))
                log.append(f"{target.name}'s {effect['debuff_stat']} is reduced!")

    elif kind == "aoe_damage_chance_poise_strike":
        # Replaces the removed aoe_damage_chance_resource_drain. Same
        # "hits everyone, sometimes does more" shape as
        # aoe_damage_chance_debuff, but the "more" is a burst of extra
        # poise damage rolled independently per target -- an AOE that
        # sets up breaks across the whole enemy line instead of taxing
        # their resources.
        for target in [o for o in opponents if o.is_alive()]:
            target_allies = [o for o in opponents if o is not target and o.is_alive()]
            bonus = (
                effect.get("bonus_poise", 2)
                if formulas.roll_percent(effect.get("poise_chance_percent", 50), rng)
                else 0
            )
            _hit(attacker, target, effect["damage_percent"],
                 effect.get("damage_stat", "attack"), rng, log,
                 defender_allies=target_allies,
                 poise_damage=poise_damage_for(ability) + bonus)

    elif kind == "aoe_damage_chance_dot_amplify":
        # AOE sibling of damage_and_dot_amplify: hits every living enemy,
        # and each hit target independently rolls for the DoT-amplify
        # mark. The "sometimes more" version of team_dot_amplify.
        for target in [o for o in opponents if o.is_alive()]:
            target_allies = [o for o in opponents if o is not target and o.is_alive()]
            hit = _hit(attacker, target, effect["damage_percent"],
                       effect.get("damage_stat", "attack"), rng, log, defender_allies=target_allies)
            if hit and target.is_alive() and formulas.roll_percent(effect.get("amplify_chance_percent", 50), rng):
                _apply_dot_vulnerability(target, ability, effect, log)

    elif kind == "aoe_damage_chance_dot":
        # DoT sibling of aoe_damage_chance_debuff -- hits every living
        # enemy at once, and each hit target independently rolls
        # dot_chance_percent odds of catching a burn instead of a stat
        # debuff. Introduced for Blueflame, whose Support DPS kit leans
        # on damage-over-time rather than shredding a stat.
        for target in [o for o in opponents if o.is_alive()]:
            target_allies = [o for o in opponents if o is not target and o.is_alive()]
            hit = _hit(attacker, target, effect["damage_percent"],
                                effect.get("damage_stat", "attack"), rng, log, defender_allies=target_allies)
            if hit and target.is_alive() and formulas.roll_percent(effect["dot_chance_percent"], rng):
                flat_amount = attacker.effective_stat(effect["dot_stat"]) * effect["dot_percent"] / 100
                for passive in attacker.find_passive("dot_amplifier"):
                    flat_amount *= 1 + passive["effect"]["percent"] / 100
                target.dots.append(DamageOverTime(
                    flat_amount=flat_amount, duration=effect["duration"],
                    source=ability["name"], stat_source=effect["dot_stat"],
                ))
                log.append(f"{target.name} is burning!")

    else:
        log.append(f"({ability['name']} has no combat effect implemented yet)")

    # Kit reactions fire AFTER the ability has fully resolved, so a
    # passive that grants a shield off a heal can't be undone by the heal
    # it's reacting to, and so the log reads in causal order. One dispatch
    # point driven by the effect kind (see kit_events_for) rather than a
    # call inside each of ~20 branches.
    #
    # `chosen_ally` doubles as the reaction target: for every single-ally
    # kind it IS the recipient, and for team/self kinds a target-scoped
    # reward is meaningless anyway, so None is correct there.
    for event in kit_events_for(ability):
        trigger_kit_event(attacker, event, log, allies=allies, target=chosen_ally or attacker)


def _resolve_hit(attacker: Combatant, defender: Combatant, damage_percent: float,
                  damage_stat: str, rng: random.Random, log: list,
                  suppress_kill_log: bool = False,
                  defender_allies: list[Combatant] | None = None,
                  attacker_allies: list[Combatant] | None = None,
                  poise_damage: int = POISE_DAMAGE_BASIC) -> bool:
    """Resolves one hit. Always lands -- there is no dodge/miss chance in
    this game. Returns True (kept as a return value so callers that guard
    follow-up effects on "did it hit" still read naturally).

    `defender_allies` (every OTHER living combatant on defender's own
    side) is only used by defender-reactive team passives (on_hit_team_buff
    below); every other caller path is unaffected by leaving it out.

    `poise_damage` is how much this particular hit chips off the
    defender's poise (see the Poise/Break block in combatant.py). Because
    every hit funnels through here, multi-hit and AOE abilities chip once
    PER hit and PER target respectively without needing any special
    casing -- which is exactly the identity those effect kinds should
    have: multi_hit is the single-target break tool, aoe_* is the
    break-the-whole-group tool."""
    defender_allies = defender_allies or []
    raw = attacker.effective_stat(damage_stat) * damage_percent / 100

    is_crit = formulas.roll_percent(attacker.effective_stat("crit_rate"), rng)
    if is_crit:
        raw *= formulas.crit_multiplier(attacker.effective_stat("crit_damage"))
        for passive in attacker.find_passive("crit_damage_bonus"):
            raw *= 1 + passive["effect"]["percent"] / 100

    damage = formulas.mitigate(raw, defender.effective_stat("defense"))

    vulnerability_percent = defender.total_vulnerability_percent(damage_stat)
    if vulnerability_percent:
        damage *= 1 + vulnerability_percent / 100

    for passive in defender.find_passive("damage_reduction"):
        damage *= 1 - passive["effect"]["percent"] / 100

    missing_fraction = 1 - (defender.current_hp / max(1, defender.max_hp))
    for passive in defender.find_passive("damage_reduction_scales_with_missing_hp"):
        eff = passive["effect"]
        reduction = eff["base_percent"] + eff["bonus_percent_at_zero_hp"] * missing_fraction
        damage *= 1 - reduction / 100

    # A broken defender takes amplified damage for the whole break window.
    # This is the payoff half of the mechanic: breaking doesn't just deny
    # the enemy its telegraphed move, it opens a burst window worth having
    # saved an ultimate for.
    if defender.is_broken():
        damage *= 1 + _break_damage_percent(attacker) / 100

    # Guard: set by the player's Guard action on their previous turn and
    # cleared when their next turn begins, so it only ever covers the gap
    # between their turns -- precisely the window a telegraphed enemy move
    # lands in.
    if defender.guarding:
        damage *= 1 - GUARD_DAMAGE_REDUCTION_PERCENT / 100

    if defender.shield > 0:
        absorbed = min(damage, defender.shield)
        defender.shield -= absorbed
        damage -= absorbed
        if absorbed:
            log.append(f"🔷 {defender.name}'s shield absorbs {round(absorbed)} damage.")

    was_debuffed = any(m.percent < 0 for m in defender.modifiers)

    dealt = defender.take_raw_hp_loss(damage)
    crit_tag = " (💥 CRIT!)" if is_crit else ""
    guard_tag = " (🛡️ guarded)" if defender.guarding else ""
    log.append(f"{attacker.name} hits {defender.name} for {dealt} damage{crit_tag}{guard_tag}.")

    # Checked BEFORE the hit resolved (above) so a debuff this same hit
    # applies doesn't count -- the event means "you struck something that
    # was already weakened", which is the setup-then-exploit pattern it
    # exists to reward.
    if was_debuffed:
        trigger_kit_event(attacker, "hit_debuffed", log,
                          allies=attacker_allies or [], target=defender)

    # Being hit builds a little energy -- see the PLAYER ENERGY ECONOMY
    # block. Without this, an action-based rule alone would leave the
    # characters who take the most punishment charging the slowest, which
    # is precisely backwards for Sustain/tank kits. Applied to enemies
    # too, for the same symmetry reason ENEMY_ENERGY_PER_ACTION exists.
    if dealt > 0 and defender.is_alive():
        defender.gain_energy(ENERGY_ON_TAKING_HIT)

    # Guarding paid off -- a hit actually landed while it was up, so the
    # defender banks energy toward their ultimate. Reading a telegraph
    # correctly should accelerate you, not merely cost you less.
    if defender.guarding:
        before = defender.energy
        defender.gain_energy(GUARD_ENERGY_ON_HIT)
        if defender.energy > before:
            log.append(f"🛡️ {defender.name} holds firm and builds {defender.energy - before} energy.")

    if defender.damage_poise(poise_damage + total_poise_damage_bonus(attacker)):
        defender.enter_break(BREAK_DURATION_TURNS)
        log.append(
            f"💫 **{defender.name}'s guard is BROKEN!** Its move is cancelled and it "
            f"takes +{_break_damage_percent(attacker)}% damage for {BREAK_DURATION_TURNS} turns."
        )
        # "break" fires on an actual break rather than on casting a
        # break-ish ability, so a break-reaction passive pays out exactly
        # when the thing it's named for happens.
        trigger_kit_event(attacker, "break", log, allies=attacker_allies or [], target=defender)

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
            # Through apply_stun so a retaliation stun refreshes rather
            # than stacking on top of an ability stun -- see apply_stun.
            log.append(f"⚡ {defender.name}'s {passive['name']} stuns {attacker.name}!")
            apply_stun(attacker, passive["effect"]["duration"], log)

    for passive in defender.find_passive("on_hit_team_buff"):
        eff = passive["effect"]
        for member in [defender] + list(defender_allies):
            member.modifiers.append(StatModifier(eff["buff_stat"], eff["buff_percent"], eff["duration"], passive["name"]))
        log.append(f"📯 {defender.name}'s {passive['name']} rallies the whole team!")

    _trigger_on_low_hp(defender, log)

    if not defender.is_alive() and not suppress_kill_log:
        _trigger_on_kill(attacker, log)
        # The main kill path -- basic attacks and every damaging ability
        # route through here, so "kill" kit reactions have to fire here
        # too, not only from the ability dispatcher's own check.
        _trigger_kill_reactions(attacker, log, attacker_allies)

    return True


def _trigger_on_kill_if_dead(attacker: Combatant, defender: Combatant, log: list,
                             attacker_allies: list[Combatant] | None = None) -> None:
    if not defender.is_alive():
        _trigger_on_kill(attacker, log)
        _trigger_kill_reactions(attacker, log, attacker_allies)


def _trigger_kill_reactions(killer: Combatant, log: list, allies: list[Combatant] | None = None) -> None:
    """Kit reactions listening for "kill". Separate from _trigger_on_kill
    (which handles the older on_kill_restore passive kind) so the two
    don't have to share a payload shape."""
    trigger_kit_event(killer, "kill", log, allies=allies or [])


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
                combatant.gain_energy(effect["amount"])
            log.append(f"🔋 {combatant.name} restores {effect['amount']} {effect['resource_type']} from {passive['name']}.")

        elif effect["kind"] == "shield_regen":
            # Capacitor Shell-style trickle shield -- unlike the burst
            # self_shield_percent_max_hp active, this adds a small amount
            # of shield every turn for free, capped (default 50% of max
            # HP) so it can't be stacked into an unbreakable wall turn
            # after turn.
            cap = combatant.max_hp * effect.get("cap_percent", 50) / 100
            headroom_percent = max(0.0, (cap - combatant.shield) / max(1, combatant.max_hp) * 100)
            gained = grant_shield(combatant, combatant, min(headroom_percent, effect["percent"]))
            if gained:
                log.append(f"🔷 {combatant.name}'s {passive['name']} reinforces their shield (+{round(gained)}).")

        elif effect["kind"] == "taunt_regen":
            # Passive auto-taunt (Provoking Aura). Refreshes rather than
            # stacks -- max() not += -- so an active longer taunt from an
            # ability is never shortened by the passive ticking under it.
            combatant.taunt_turns = max(combatant.taunt_turns, effect.get("duration", 1))
            gained = grant_shield(combatant, combatant, effect.get("shield_percent", 0))
            log.append(
                f"🎯 {combatant.name}'s {passive['name']} draws every attack"
                + (f", shielding for {round(gained)}." if gained else ".")
            )

        elif effect["kind"] == "aura_team_resource_regen":
            # Support aura -- restores energy/mana to combatant AND its
            # living allies every turn, not just the owner.
            for member in [combatant] + [a for a in allies if a.is_alive()]:
                energy_gained = min(member.max_energy - member.energy, effect.get("energy_amount", 0))
                mana_gained = min(member.max_mana - member.mana, effect.get("mana_amount", 0))
                energy_gained = member.gain_energy(energy_gained)
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
