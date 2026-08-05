"""
Character skill/ultimate/passive kits -- the Combat Overhaul's replacement
for the old scroll-granted ultimate. Every combatant now gets these
straight from their kit rather than gear:

  * `character_skill`    -- one active ability, costs MANA, always available.
  * `character_ultimate` -- one active ability, costs 50 ENERGY.
  * `character_passive`  -- one always-on passive, no resource cost, that
    reinforces the character's class role (DPS hits harder as the fight
    goes on, Amplifier/Sustain trickle resources/healing to the WHOLE team
    every turn, etc.) -- reuses the same passive effect kinds gear passives
    already use (bot/game/combat/effects.py's trigger_on_turn_start), so no
    new combat-resolution code is needed for these.

Same `effect` dict shape as bot/game/loot/abilities.py so
bot/game/combat/effects.py resolves them identically -- including the
team-oriented kinds added for this system: `heal_lowest_ally_percent_max_hp`,
`team_heal_percent_max_hp`, `team_buff`, and (for the always-on team-aura
passives specifically) `aura_team_resource_regen` / `aura_team_regen` (see
effects.py::trigger_on_turn_start).

Kit-diversity pass: every one of the 24 pulled characters used to lean on
exactly one of 4 generic passive shapes purely by class (DPS/Support DPS
stacked ATK/Crit Rate, Amplifier/Sustain ran a team-aura), differing only
in flavor text -- e.g. FAX, Slikrz, Andy, and Caliper were all functionally
identical Support DPS units. Reworked roughly two-thirds of the roster's
passives (and a handful of actives) onto effect kinds that were previously
gear-only (bot/game/loot/abilities.py's ARMOR_PASSIVES) -- lifesteal,
crit_damage_bonus, damage_reflect, damage_reduction,
damage_reduction_scales_with_missing_hp, chance_stun_attacker,
prevent_death, on_kill_restore, shield_regen -- so each character's own
kit, not just their gear, has a distinct identity. A couple of intentional
cross-character combos came out of this: Arkiver's skill
(damage_bonus_if_debuffed) pays off noticeably harder alongside any of the
many Support DPS units that apply a debuff first. A couple of characters
per class (FAX, Caliper, Dolphe, Arkiver) were deliberately left on the
simple/generic shape as an easy, low-complexity baseline pick within their
class, rather than making every single option equally exotic.

CLASS-IDENTITY PASS (see the ROLE CONTRACT block further down this file
for the full reasoning and the exact rule). Amplifier and Sustain kits had
drifted off their own class names -- Jofrog was an "Amplifier" with no
buff anywhere in his kit, Refender was a "Sustain" whose primary button
was single-target damage, Nebula was an Amplifier who only ever buffed
DEFENSE (a Sustain stat), and Evz's Sustain ultimate handed out ATK.
Every Amplifier now buffs an OFFENSIVE stat with both buttons; every
Sustain now heals, shields, or buffs a DEFENSIVE stat with both. Three
new effect kinds carry this without flattening anyone's flavor:
team_buff_and_resource (a buff with the old resource-restore riding on
it, for the logistics-flavored Amplifiers), team_double_buff, and
team_shield_and_buff / team_heal_and_buff for Sustains.

ELEMENTAL-SCALING PASS. Only 2 of 27 character abilities scaled off the
ELE stat, so half the game's damage stat, every ELE substat roll, every
ELE shrine and the ELE-vulnerability mechanic had almost nothing to
attach to -- gearing for ELE was close to a trap. Arkiver, Axel,
Blueflame and Nyrvite are now fully ELE-scaled (all four had explicitly
elemental bios already: elemental gauntlets, void augments, fire, and a
kit rebuilt around break damage), and Sader Vorae is deliberately SPLIT
-- ATK on the skill that applies her ELE-vulnerability mark, ELE on the
ultimate that cashes it in. Their signature-stat bumps in
character_seed_data.py moved from growth_attack to growth_elemental to
match, so the stat their abilities read is the stat they actually grow.
That takes the split to 8 ELE / 15 ATK and gives an elemental squad a
real damage core plus its own support line (Virtual and Jofrog both buff
ELE; Sader Vorae marks for it; Nyrvite destabilises for DoT).

Josh rework: previously the weakest 5-star DPS in practice (see
character_seed_data.py's docstring for the growth_attack scaling bug this
uncovered) despite nominally being the flagship. Reworked into the
roster's hardest-scaling DPS: his skill (Aligner's Resolve) now ramps up
via damage_scales_with_missing_hp instead of a flat multiplier, his
passive (Unfinished Business) snowballs off on_kill_restore instead of a
generic ATK stack, and his ultimate is a full rename/rework into
Catastrophe Ball -- an aoe_damage ultimate, unique among DPS-class kits
(every other DPS ultimate here is single-target), reflecting a World
Aligner leader who brings the whole fight down on everyone at once.

Kit-diversity pass, round 2 (new engine mechanics -- see effects.py's
"New-mechanics pass" docstring section for the implementations): five
characters were given a kit piece built on a mechanic that plain didn't
exist before this pass, rather than a new combination of old ones.
FAX (extra_turn_on_kill) doesn't stop moving once he's landed a kill --
an immediate bonus turn instead of the usual resource/sustain payoff.
IH (on_hit_team_buff) rallies the WHOLE squad's ATK the instant he
personally takes a hit -- "sacrificial support" where tanking a hit is
itself the trigger. Sader Vorae's skill (apply_vulnerability_stack) marks
a single target with a stacking Vulnerability instead of her old flat
AOE debuff, rewarding focused fire from her AND from any elemental
teammate finishing the marked target off (her ultimate stays the old
AOE SPD-debuff shape, so she still has AOE utility -- just not on her
spammable skill anymore). Blueflame (dot_amplifier) turns his own
aoe_damage_chance_dot casts into the hardest-hitting burns in the game.
Evz's ultimate (sacrifice_hp_team_buff) is the Blood-Sustain family's
buff sibling to Kotori's sacrifice_hp_heal_* kinds -- pays with her own
HP to empower the WHOLE side, herself included (unlike Kotori's heals,
which pointedly never heal the caster).

AMPLIFIER POWER PASS. Measured over 400 simulated fights, adding an
Amplifier to a 3-DPS squad moved the win rate from 11.2% to 11.4% -- i.e.
the class was very nearly a wasted slot, because a buff turn cost a full
turn of damage and returned roughly the same amount spread thinly. Every
Amplifier's buff magnitudes went up ~60-80% and their durations from 2-3
turns to 3-4, and the class's resource aura went from 4 energy/turn to
9-12. That last one matters far more than it used to: it was written when
ultimates were effectively uncastable, and now that every action charges
(see effects.py's PLAYER ENERGY ECONOMY block) feeding the squad energy
is close to an extra ultimate per fight. Post-pass the same comparison is
11.2% -> 81.2%, and a squad running one Amplifier AND one Sustain wins
100% where four DPS win 11% -- which is the intended shape: support isn't
a tax on your damage slots, it's the thing that makes them work.

SHIELDER PASS. Bee Jee and Jofrog are now dedicated SHIELDERS rather than
another two healers. Jofrog moved class outright (Amplifier -> Sustain --
see character_seed_data.py): "a former robotic bodyguard" is a bodyguard,
and he's now the game's taunt carrier, standing in front of the squad
behind a shield (taunt_and_shield / taunt_and_team_shield). Bee Jee keeps
her medic flavour but specialises -- a single-target shield she can drop
on whoever the enemy intent has telegraphed, a team shield + cleanse
ultimate, and a passive (shield_amplifier) that makes every shield she
grants 30% larger rather than being the third character in the roster
with a self-only shield_regen. Refender stays the heal/DEF hybrid, so
"Sustain" now spans three distinct answers to incoming damage: heal it
(Lily/Aura/Kotori), absorb it (Bee Jee/Jofrog), or reduce it (Refender).

Two registries:
  * CLASS_KIT_MAP -- keyed by CharacterClass, used ONLY for the player's own
    avatar (CharacterTemplate.is_player_avatar), since it can switch class
    freely (PlayerCharacter.current_class) and its whole kit -- skill,
    ultimate, AND passive -- needs to follow.
  * CHARACTER_KIT_MAP / CHARACTER_PASSIVE_MAP -- keyed by
    CharacterTemplate.skill_id/.ultimate_id/.passive_id, one fixed set per
    pulled character.

bot/game/combat/factory.py resolves all three into a built Combatant.
"""

from __future__ import annotations

from bot.database.models.enums import CharacterClass
from bot.game.combat.combatant import ULTIMATE_COOLDOWN

# ---------------------------------------------------------------------
# Avatar class kits -- what "You" gets while playing each of the 4 roles.
# Each class's passive reinforces that role: DPS/Support DPS snowball
# their own ATK/Crit Rate turn over turn (self-only, since a solo-fighter
# identity fits them), while Amplifier/Sustain use the newer team-aura
# passive kinds (aura_team_resource_regen / aura_team_regen) to trickle
# resources/healing to the WHOLE team every turn -- a much more direct fit
# for "support the team" than the earlier one-time save-yourself passives
# these used before those aura kinds existed.
# ---------------------------------------------------------------------
CLASS_KIT_MAP: dict[CharacterClass, dict[str, dict]] = {
    CharacterClass.DPS: {
        "skill": {
            "id": "avatar_dps_skill", "name": "Focused Strike",
            "resource_type": "mana", "resource_cost": 20, "cooldown": 1,
            "description": "Deal 190% ATK damage to the target.",
            "effect": {"kind": "damage_multiplier", "damage_percent": 190, "damage_stat": "attack"},
        },
        "ultimate": {
            "id": "avatar_dps_ultimate", "name": "Devastation",
            "resource_type": "energy", "resource_cost": 50, "cooldown": ULTIMATE_COOLDOWN, "is_ultimate": True,
            "description": "Strike the target 4 times for 75% ATK damage each.",
            "effect": {"kind": "multi_hit", "hits": 4, "damage_percent_per_hit": 75, "damage_stat": "attack"},
        },
        "passive": {
            "id": "avatar_dps_passive", "name": "Bloodlust", "trigger": "on_turn_start",
            "description": "Gains 4% ATK per turn (max 5 stacks) -- hits harder the longer the fight runs.",
            "effect": {"kind": "stacking_buff", "buff_stat": "attack", "percent_per_stack": 4, "max_stacks": 5},
        },
    },
    CharacterClass.SUPPORT_DPS: {
        # Combat Overhaul role shift: Support DPS moved from single-target
        # burst+guaranteed-debuff toward AOE damage that only SOMETIMES
        # also debuffs (see aoe_damage_chance_debuff in
        # bot/game/combat/effects.py) -- suppressing an entire enemy line
        # rather than picking one target apart.
        "skill": {
            "id": "avatar_support_dps_skill", "name": "Suppressing Fire",
            "resource_type": "mana", "resource_cost": 20, "cooldown": 1,
            "description": "Deal 90% ATK damage to all enemies, with a 50% chance to reduce each hit target's DEF by 15% for 2 turns.",
            "effect": {"kind": "aoe_damage_chance_debuff", "damage_percent": 90, "damage_stat": "attack",
                       "debuff_chance_percent": 50, "debuff_stat": "defense", "debuff_percent": -15, "duration": 2},
        },
        "ultimate": {
            "id": "avatar_support_dps_ultimate", "name": "Coordinated Barrage",
            "resource_type": "energy", "resource_cost": 50, "cooldown": ULTIMATE_COOLDOWN, "is_ultimate": True,
            "description": "Deal 140% ATK damage to all enemies and reduce each of their DEF by 20% for 2 turns.",
            "effect": {"kind": "aoe_damage_chance_debuff", "damage_percent": 140, "damage_stat": "attack",
                       "debuff_chance_percent": 100, "debuff_stat": "defense", "debuff_percent": -20, "duration": 2},
        },
        "passive": {
            "id": "avatar_support_dps_passive", "name": "Steady Aim", "trigger": "on_turn_start",
            "description": "Gains 3% Crit Rate per turn (max 5 stacks) -- gets more precise the longer they fight.",
            "effect": {"kind": "stacking_buff", "buff_stat": "crit_rate", "percent_per_stack": 3, "max_stacks": 5},
        },
    },
    CharacterClass.AMPLIFIER: {
        "skill": {
            "id": "avatar_amplifier_skill", "name": "Rally Cry",
            "resource_type": "mana", "resource_cost": 22, "cooldown": 2,
            "description": "Boost the whole team's ATK by 38% for 3 turns.",
            "effect": {"kind": "team_buff", "buff_stat": "attack", "buff_percent": 38, "duration": 3},
        },
        "ultimate": {
            "id": "avatar_amplifier_ultimate", "name": "Overdrive",
            "resource_type": "energy", "resource_cost": 50, "cooldown": ULTIMATE_COOLDOWN, "is_ultimate": True,
            # Buffs BOTH offensive stats so the avatar Amplifier is a
            # universal fit for either an ATK squad or an ELE squad -- it's
            # the one Amplifier a player can't choose not to have.
            "description": "Boost the whole team's ATK and ELE by 45% for 3 turns.",
            "effect": {"kind": "team_double_buff", "buff_stat_1": "attack", "buff_percent_1": 75,
                       "buff_stat_2": "elemental", "buff_percent_2": 75, "duration": 4},
        },
        "passive": {
            "id": "avatar_amplifier_passive", "name": "Unshakeable Resolve", "trigger": "on_turn_start",
            "description": "At the start of every turn, restores 3 energy and 4 SP to the whole team.",
            "effect": {"kind": "aura_team_resource_regen", "energy_amount": 3, "mana_amount": 4},
        },
    },
    CharacterClass.SUSTAIN: {
        "skill": {
            "id": "avatar_sustain_skill", "name": "Mending Light",
            "resource_type": "mana", "resource_cost": 20, "cooldown": 1,
            "description": "Heal whichever ally (including yourself) is lowest on HP for 25% of their max HP.",
            "effect": {"kind": "heal_lowest_ally_percent_max_hp", "percent": 25},
        },
        "ultimate": {
            "id": "avatar_sustain_ultimate", "name": "Sanctuary",
            "resource_type": "energy", "resource_cost": 50, "cooldown": ULTIMATE_COOLDOWN, "is_ultimate": True,
            "description": "Heal the whole team for 24% of each member's max HP.",
            "effect": {"kind": "team_heal_percent_max_hp", "percent": 24},
        },
        "passive": {
            "id": "avatar_sustain_passive", "name": "Second Wind", "trigger": "on_turn_start",
            "description": "At the start of every turn, the whole team regenerates 1% of their own max HP.",
            "effect": {"kind": "aura_team_regen", "percent": 1},
        },
    },
}


def _skill(cid, name, cost, cd, desc, effect):
    return {"id": cid, "name": name, "resource_type": "mana", "resource_cost": cost,
            "cooldown": cd, "description": desc, "effect": effect}


def _ultimate(cid, name, desc, effect):
    # cooldown is ULTIMATE_COOLDOWN, not 0 -- see the block in
    # combatant.py. Every character ultimate goes through this helper, so
    # the floor on ultimate frequency is set in exactly one place.
    return {"id": cid, "name": name, "resource_type": "energy", "resource_cost": 50,
            "cooldown": ULTIMATE_COOLDOWN, "is_ultimate": True, "description": desc, "effect": effect}


def _passive(cid, name, trigger, desc, effect):
    return {"id": cid, "name": name, "trigger": trigger, "description": desc, "effect": effect}


# Reusable passive effects per class role -- every character's passive is
# one of these four (matching their class), just with a unique id/name/
# flavor description. Keeps every character mechanically reinforcing its
# role without needing a bespoke passive effect kind per character.
def _dps_passive(cid, name, desc, percent_per_stack=4, max_stacks=5):
    return _passive(cid, name, "on_turn_start", desc,
                     {"kind": "stacking_buff", "buff_stat": "attack",
                      "percent_per_stack": percent_per_stack, "max_stacks": max_stacks})


def _support_dps_passive(cid, name, desc, percent_per_stack=3, max_stacks=5):
    return _passive(cid, name, "on_turn_start", desc,
                     {"kind": "stacking_buff", "buff_stat": "crit_rate",
                      "percent_per_stack": percent_per_stack, "max_stacks": max_stacks})


def _amplifier_passive(cid, name, desc, energy_amount=4, mana_amount=5):
    # Bumped from 4 energy / 6 SP. That aura was near-worthless when it
    # was written, because energy did almost nothing -- ultimates were
    # effectively uncastable (see the PLAYER ENERGY ECONOMY block in
    # effects.py). Now that every action charges and ultimates actually
    # fire, feeding the whole squad energy every turn is a real
    # contribution: at 9/turn across 4 members it's most of an extra
    # ultimate per fight, team-wide.
    return _passive(cid, name, "on_turn_start", desc,
                     {"kind": "aura_team_resource_regen", "energy_amount": energy_amount, "mana_amount": mana_amount})


def _sustain_passive(cid, name, desc, percent=1):
    return _passive(cid, name, "on_turn_start", desc,
                     {"kind": "aura_team_regen", "percent": percent})


# ---------------------------------------------------------------------
# ROLE CONTRACT (class-identity pass).
#
# The two support classes had drifted off their own names. An AMPLIFIER
# is supposed to make the rest of the squad hit harder; a SUSTAIN is
# supposed to keep it alive. In practice several characters in each class
# did neither:
#
#   * Jofrog (Amplifier) had NO buff anywhere in his kit -- both his
#     skill and his ultimate just handed out energy/SP.
#   * Caandy and Virtual (Amplifiers) each had a resource-restore skill,
#     so half their kit was resource logistics rather than amplification.
#   * Refender (Sustain) opened with a pure single-target DAMAGE skill.
#   * Evz (Sustain) had an ATK-buff ultimate -- an Amplifier's job.
#
# Resource restoration isn't a bad effect, but it isn't amplification:
# it changes WHEN a teammate acts, not how hard they hit, and it reads to
# the player as nothing happening. It's kept as a secondary rider on
# several kits and as the Amplifier PASSIVE aura, but it no longer
# occupies a character's primary buttons.
#
# The contract these two helpers below now enforce for every member of
# their class:
#
#   AMPLIFIER -- both the skill AND the ultimate apply a team_buff (or
#     ally_buff) to a combat stat. Always. That is the class.
#   SUSTAIN   -- both the skill AND the ultimate either heal, shield, or
#     buff a DEFENSIVE stat (defense / max HP). Never raw damage.
#
# Where a character's flavor really wanted a non-buff effect (Caandy's
# visor sync, Jofrog's battery swap), the effect survives as the rider on
# a buff rather than as the whole ability -- see team_buff_and_resource
# in bot/game/combat/effects.py.
# ---------------------------------------------------------------------

AMPLIFIER_BUFF_STATS = {"attack", "elemental", "crit_rate", "crit_damage", "speed", "recharge"}
SUSTAIN_DEFENSIVE_STATS = {"defense", "max_hp"}


# ---------------------------------------------------------------------
# Fixed kits for the 9 pullable characters, keyed by the skill_id /
# ultimate_id set on their CharacterTemplate (character_seed_data.py).
# ---------------------------------------------------------------------
CHARACTER_KIT_MAP: dict[str, dict] = {
    # --- 3-star ---
    "lily_lovelace_skill": _skill(
        "lily_lovelace_skill", "Hearty Meal", 18, 1,
        "Heal the lowest-HP ally for 20% of their max HP.",
        {"kind": "heal_lowest_ally_percent_max_hp", "percent": 20},
    ),
    "lily_lovelace_ultimate": _ultimate(
        "lily_lovelace_ultimate", "Feast for the Brave",
        "Heal the whole team for 22% of each member's max HP.",
        {"kind": "team_heal_percent_max_hp", "percent": 22},
    ),
    "nexus_skill": _skill(
        "nexus_skill", "Trending Now", 20, 2,
        "Boost the whole team's Crit Rate by 30% for 3 turns.",
        {"kind": "team_buff", "buff_stat": "crit_rate", "buff_percent": 30, "duration": 3},
    ),
    "nexus_ultimate": _ultimate(
        "nexus_ultimate", "Gone Viral",
        "Boost the whole team's Crit Rate by 30% and Crit DMG by 35% for 3 turns.",
        {"kind": "team_double_buff", "buff_stat_1": "crit_rate", "buff_percent_1": 55,
         "buff_stat_2": "crit_damage", "buff_percent_2": 60, "duration": 4},
    ),
    "fax_skill": _skill(
        "fax_skill", "Wide Strafing Run", 18, 1,
        "Deal 70% ATK damage to all enemies, with a 40% chance to reduce each hit target's DEF by 15% for 2 turns.",
        {"kind": "aoe_damage_chance_debuff", "damage_percent": 70, "damage_stat": "attack",
         "debuff_chance_percent": 40, "debuff_stat": "defense", "debuff_percent": -15, "duration": 2},
    ),
    "fax_ultimate": _ultimate(
        "fax_ultimate", "Cargo Bomb Run",
        "Deal 100% ATK damage to all enemies and reduce each of their DEF by 15% for 2 turns.",
        {"kind": "aoe_damage_chance_debuff", "damage_percent": 100, "damage_stat": "attack",
         "debuff_chance_percent": 100, "debuff_stat": "defense", "debuff_percent": -15, "duration": 2},
    ),
    # ELEMENTAL scaling (see the elemental-scaling pass in this module's
    # docstring). His bio is literally "channeling elemental energy
    # through a pair of dual-wielded gauntlets" -- his ultimate already
    # scaled off ELE while his skill scaled off ATK, which meant gearing
    # him well was impossible: every point of ATK gear made half his kit
    # better and the other half not, and vice versa. Both halves are ELE
    # now, and character_seed_data.py gives him the ELE base/growth to
    # match.
    "arkiver_skill": _skill(
        "arkiver_skill", "Twin Fang Strike", 18, 1,
        "Deal 130% ELE damage, or 220% ELE damage if the target is already weakened by a debuff.",
        {"kind": "damage_bonus_if_debuffed", "damage_percent": 130,
         "bonus_damage_percent": 90, "damage_stat": "elemental"},
    ),
    "arkiver_ultimate": _ultimate(
        "arkiver_ultimate", "Elemental Fury",
        "Deal 380% ELE damage to the target.",
        {"kind": "damage_multiplier", "damage_percent": 380, "damage_stat": "elemental"},
    ),
    "slikrz_skill": _skill(
        "slikrz_skill", "Blank Stare", 18, 1,
        "Deal 70% ATK damage to all enemies, with a 40% chance to inflict a bleed on each hit target for 12% ATK per turn over 3 turns.",
        {"kind": "aoe_damage_chance_dot", "damage_percent": 70, "damage_stat": "attack",
         "dot_chance_percent": 40, "dot_stat": "attack", "dot_percent": 12, "duration": 3},
    ),
    "slikrz_ultimate": _ultimate(
        "slikrz_ultimate", "Flatline Frenzy",
        "Deal 100% ATK damage to all enemies and inflict a bleed on each of them for 15% ATK per turn over 3 turns.",
        {"kind": "aoe_damage_chance_dot", "damage_percent": 100, "damage_stat": "attack",
         "dot_chance_percent": 100, "dot_stat": "attack", "dot_percent": 15, "duration": 3},
    ),
    "evz_skill": _skill(
        "evz_skill", "Bedside Manner", 18, 1,
        "Cleanse all negative effects from the lowest-HP ally and heal them for 20% of their max HP.",
        {"kind": "cleanse_ally_and_heal", "heal_percent": 20},
    ),
    # SUSTAIN contract: this was an ATK buff -- an Amplifier's job on a
    # Sustain's ultimate. Kept the Blood-Sustain sacrifice identity
    # (she pays her own HP, same as before) but pointed at survival: a
    # hard DEF wall for the whole squad, which is what "brace for an
    # emergency landing" should actually mean.
    "evz_ultimate": _ultimate(
        "evz_ultimate", "Emergency Landing",
        "Sacrifice 20% of her own max HP to brace the whole team: +45% DEF for 3 turns.",
        {"kind": "sacrifice_hp_team_buff", "self_cost_percent": 20,
         "buff_stat": "defense", "buff_percent": 45, "duration": 3},
    ),
    # AMPLIFIER contract: her skill was a pure resource restore with no
    # buff at all. The visor-sync flavor survives as the rider on a real
    # Crit Rate buff (team_buff_and_resource).
    "caandy_skill": _skill(
        "caandy_skill", "Visor Sync", 20, 2,
        "Feed the squad live targeting data: +32% Crit Rate for 3 turns, and restore 8 energy and 10 SP to each of them.",
        {"kind": "team_buff_and_resource", "buff_stat": "crit_rate", "buff_percent": 32,
         "duration": 3, "energy_amount": 8, "mana_amount": 10},
    ),
    "caandy_ultimate": _ultimate(
        "caandy_ultimate", "AI Overclock",
        "Boost the whole team's SPD by 35% and Crit Rate by 20% for 3 turns.",
        {"kind": "team_double_buff", "buff_stat_1": "speed", "buff_percent_1": 55,
         "buff_stat_2": "crit_rate", "buff_percent_2": 40, "duration": 4},
    ),
    # ELEMENTAL scaling -- "forced to replace organs with void-powered
    # augments" is about as elemental as a bio gets, and this gives the
    # DPS class a second ELE option alongside Arkiver so an elemental
    # squad has a real damage core rather than one character.
    "axel_skill": _skill(
        "axel_skill", "Weakpoint Strike", 18, 1,
        "Deal 125% ELE damage and reduce the target's ATK and DEF by 15% each for 2 turns.",
        {"kind": "damage_and_double_debuff", "damage_percent": 125, "damage_stat": "elemental",
         "debuff_stat_1": "attack", "debuff_percent_1": -15,
         "debuff_stat_2": "defense", "debuff_percent_2": -15, "duration": 2},
    ),
    "axel_ultimate": _ultimate(
        "axel_ultimate", "Exposed Wound",
        "Deal 170% ELE damage, plus up to 170% more the lower the target's HP is.",
        {"kind": "damage_scales_with_missing_hp", "base_damage_percent": 170,
         "bonus_damage_percent_at_zero_hp": 170, "damage_stat": "elemental"},
    ),
    "ih_skill": _skill(
        "ih_skill", "Loadout Sweep", 18, 1,
        "Deal 70% ATK damage to all enemies, with a 40% chance to reduce each hit target's ATK by 15% for 2 turns.",
        {"kind": "aoe_damage_chance_debuff", "damage_percent": 70, "damage_stat": "attack",
         "debuff_chance_percent": 40, "debuff_stat": "attack", "debuff_percent": -15, "duration": 2},
    ),
    "ih_ultimate": _ultimate(
        "ih_ultimate", "Full Auto",
        "Deal 100% ATK damage to all enemies and reduce each of their ATK by 15% for 2 turns.",
        {"kind": "aoe_damage_chance_debuff", "damage_percent": 100, "damage_stat": "attack",
         "debuff_chance_percent": 100, "debuff_stat": "attack", "debuff_percent": -15, "duration": 2},
    ),

    # --- 4-star ---
    # DEDICATED SHIELDER (see the SHIELDER block in this module's
    # docstring). Bee Jee was already the closest thing the roster had to
    # one; her skill becomes a single-target shield so she can answer a
    # telegraphed hit on ONE character, which a team shield can't do
    # efficiently, and her ultimate becomes the team shield + cleanse.
    "bee_jee_skill": _skill(
        "bee_jee_skill", "Field Triage", 20, 1,
        "Shield one ally for 30% of their max HP -- pick who's about to be hit.",
        {"kind": "shield_ally_percent_max_hp", "percent": 30},
    ),
    "bee_jee_ultimate": _ultimate(
        "bee_jee_ultimate", "Antidote Protocol",
        "Shield the whole team for 28% of each member's max HP and purge every negative effect from them.",
        {"kind": "team_shield_and_cleanse", "shield_percent": 28},
    ),
    "sader_vorae_skill": _skill(
        "sader_vorae_skill", "Wide Strafing Pass", 20, 1,
        "Deal 90% ATK damage to the target and mark it, increasing the ELE damage it takes by 8% per stack (max 4 stacks).",
        {"kind": "apply_vulnerability_stack", "damage_percent": 90, "damage_stat": "attack",
         "vulnerable_damage_stat": "elemental", "percent_per_stack": 8, "max_stacks": 4},
    ),
    # Her SKILL stays ATK-scaled on purpose -- it's the enabler half of
    # her kit (it applies the ELE vulnerability mark), and keeping it on
    # a different stat than the mark it sets up is what makes her a
    # partner for elemental carries rather than a self-contained one.
    # Her ULTIMATE goes ELE so she can cash in her own stacks when
    # there's no elemental teammate to hand them to.
    "sader_vorae_ultimate": _ultimate(
        "sader_vorae_ultimate", "Glacier 15 Reckoning",
        "Deal 110% ELE damage to all enemies and reduce each of their SPD by 18% for 2 turns.",
        {"kind": "aoe_damage_chance_debuff", "damage_percent": 110, "damage_stat": "elemental",
         "debuff_chance_percent": 100, "debuff_stat": "speed", "debuff_percent": -18, "duration": 2},
    ),
    # AMPLIFIER contract: Nebula buffed DEFENSE with both buttons, which
    # is the SUSTAIN class's stat, not an Amplifier's -- she was
    # effectively a Sustain wearing an Amplifier label, and she competed
    # with Refender/Bee Jee rather than with Dolphe/Virtual. Reworked into
    # the roster's TEMPO Amplifier: Speed is an offensive buff (it moves
    # the whole squad earlier in the cycle -- see battle.py's
    # _build_cycle_order) and fits "reads the terrain, always a step
    # ahead" better than a flat damage number would. Her ultimate keeps a
    # DEF rider so the mountaineer-survivalist flavor survives.
    "nebula_skill": _skill(
        "nebula_skill", "Tactical Ground", 20, 2,
        "Boost the whole team's SPD by 40% for 3 turns -- everyone acts sooner.",
        {"kind": "team_buff", "buff_stat": "speed", "buff_percent": 40, "duration": 3},
    ),
    "nebula_ultimate": _ultimate(
        "nebula_ultimate", "Summit Advantage",
        "Boost the whole team's SPD by 40% and DEF by 30% for 3 turns.",
        {"kind": "team_double_buff", "buff_stat_1": "speed", "buff_percent_1": 65,
         "buff_stat_2": "defense", "buff_percent_2": 50, "duration": 4},
    ),
    "andy_skill": _skill(
        "andy_skill", "Wide Command Strafe", 20, 1,
        "Deal 75% ATK damage to all enemies, with a 45% chance to reduce each hit target's DEF by 18% for 2 turns.",
        {"kind": "aoe_damage_chance_debuff", "damage_percent": 75, "damage_stat": "attack",
         "debuff_chance_percent": 45, "debuff_stat": "defense", "debuff_percent": -18, "duration": 2},
    ),
    "andy_ultimate": _ultimate(
        "andy_ultimate", "Squadron Bombardment",
        "Deal 110% ATK damage to all enemies and reduce each of their DEF by 18% for 2 turns.",
        {"kind": "aoe_damage_chance_debuff", "damage_percent": 110, "damage_stat": "attack",
         "debuff_chance_percent": 100, "debuff_stat": "defense", "debuff_percent": -18, "duration": 2},
    ),
    "star_skill": _skill(
        "star_skill", "Lazy Haymaker", 20, 1,
        "Deal 220% ATK damage to the target.",
        {"kind": "damage_multiplier", "damage_percent": 220, "damage_stat": "attack"},
    ),
    "star_ultimate": _ultimate(
        "star_ultimate", "One and Done",
        "Deal 280% ATK damage to the target, or 450% if they're below 30% HP.",
        {"kind": "execute_below_threshold", "damage_percent": 280, "execute_damage_percent": 450,
         "hp_threshold_percent": 30, "damage_stat": "attack"},
    ),
    "kotori_skill": _skill(
        "kotori_skill", "Vein Offering", 18, 1,
        "Sacrifice 12% of your own max HP to heal the lowest-HP ally for 30% of their max HP.",
        {"kind": "sacrifice_hp_heal_lowest_ally_percent_max_hp", "self_cost_percent": 12, "heal_percent": 30},
    ),
    "kotori_ultimate": _ultimate(
        "kotori_ultimate", "Crimson Devotion",
        "Sacrifice 20% of your own max HP to heal the whole team for 35% of each member's max HP.",
        {"kind": "sacrifice_hp_heal_team_percent_max_hp", "self_cost_percent": 20, "heal_percent": 35},
    ),
    # DEDICATED SHIELDER + TANK. Jofrog moved from AMPLIFIER to SUSTAIN
    # (see character_seed_data.py) -- "a former robotic bodyguard who
    # escaped his programming" is a bodyguard, and the roster had no
    # character whose job was to physically stand in front of someone.
    # He's the game's taunt carrier: his skill pulls every enemy attack
    # onto himself behind a shield, his ultimate does it for the whole
    # squad. That combination is what makes taunt worth building around
    # rather than a curiosity -- see the TAUNT block in combatant.py.
    "jofrog_skill": _skill(
        "jofrog_skill", "Bodyguard Protocol", 18, 1,
        "Shield yourself for 35% of max HP, raise DEF by 40%, and force every enemy to attack you for 2 turns.",
        {"kind": "taunt_and_shield", "shield_percent": 35, "duration": 2,
         "buff_stat": "defense", "buff_percent": 40},
    ),
    "jofrog_ultimate": _ultimate(
        "jofrog_ultimate", "Full Grid Sync",
        "Shield the WHOLE team for 35% of their max HP and force every enemy to attack you for 3 turns.",
        {"kind": "taunt_and_team_shield", "shield_percent": 35, "duration": 3},
    ),
    "aura_skill": _skill(
        "aura_skill", "Field Dressing", 18, 1,
        "Cleanse all negative effects from the lowest-HP ally and heal them for 25% of their max HP.",
        {"kind": "cleanse_ally_and_heal", "heal_percent": 25},
    ),
    "aura_ultimate": _ultimate(
        "aura_ultimate", "Triage Surge",
        "Heal the whole team for 28% of each member's max HP.",
        {"kind": "team_heal_percent_max_hp", "percent": 28},
    ),

    # --- 5-star ---
    "josh_skill": _skill(
        "josh_skill", "Aligner's Resolve", 22, 1,
        "Deal 160% ATK damage, increased by up to 140% more the lower the target's HP is.",
        {"kind": "damage_scales_with_missing_hp", "base_damage_percent": 160,
         "bonus_damage_percent_at_zero_hp": 140, "damage_stat": "attack"},
    ),
    "josh_ultimate": _ultimate(
        "josh_ultimate", "Catastrophe Ball",
        "Hurl a catastrophic payload that devastates every enemy at once for 260% ATK damage.",
        {"kind": "aoe_damage", "damage_percent": 260, "damage_stat": "attack"},
    ),
    # SUSTAIN contract: his skill was a pure single-target DAMAGE ability
    # -- the one thing a Sustain isn't supposed to be doing with its
    # primary button. "Refense" is a philosophy of balance, so the rework
    # keeps that reading but resolves it defensively: he hardens the
    # squad rather than swinging at one enemy. His ultimate now pairs
    # the heal with that same hardening, so he's the roster's mitigation
    # Sustain as opposed to Aura/Lily's throughput healing.
    "refender_skill": _skill(
        "refender_skill", "Refense Stance", 18, 2,
        "Settle the whole squad into the Refense guard: +25% DEF for 2 turns.",
        {"kind": "team_buff", "buff_stat": "defense", "buff_percent": 25, "duration": 2},
    ),
    "refender_ultimate": _ultimate(
        "refender_ultimate", "Perfect Balance",
        "Heal the whole team for 24% of each member's max HP and raise their DEF by 35% for 3 turns.",
        {"kind": "team_heal_and_buff", "heal_percent": 24,
         "buff_stat": "defense", "buff_percent": 35, "duration": 3},
    ),
    "dolphe_skill": _skill(
        "dolphe_skill", "Cascade Directive", 22, 2,
        "Boost the whole team's ATK by 45% for 3 turns.",
        {"kind": "team_buff", "buff_stat": "attack", "buff_percent": 45, "duration": 3},
    ),
    "dolphe_ultimate": _ultimate(
        "dolphe_ultimate", "Full Cascade",
        "Boost the whole team's ATK by 80% and ELE by 80% for 4 turns.",
        {"kind": "team_double_buff", "buff_stat_1": "attack", "buff_percent_1": 80,
         "buff_stat_2": "elemental", "buff_percent_2": 80, "duration": 4},
    ),
    "caliper_skill": _skill(
        "caliper_skill", "Twin Trigger Sweep", 22, 1,
        "Deal 80% ATK damage to all enemies, with a 50% chance to reduce each hit target's DEF by 20% for 2 turns.",
        {"kind": "aoe_damage_chance_debuff", "damage_percent": 80, "damage_stat": "attack",
         "debuff_chance_percent": 50, "debuff_stat": "defense", "debuff_percent": -20, "duration": 2},
    ),
    "caliper_ultimate": _ultimate(
        "caliper_ultimate", "Full Auto Barrage",
        "Deal 130% ATK damage to all enemies and reduce each of their DEF by 20% for 2 turns.",
        {"kind": "aoe_damage_chance_debuff", "damage_percent": 130, "damage_stat": "attack",
         "debuff_chance_percent": 100, "debuff_stat": "defense", "debuff_percent": -20, "duration": 2},
    ),
    # Nyrvite was the game's one energy-drain character. Drain is gone
    # (see bot/game/combat/effects.py for why), so her kit was rebuilt
    # around the mechanic that replaced it -- she's now THE poise-break
    # specialist, which fits "strikes from the shadows at the weak point"
    # at least as well as signal-jamming did, and gives the break system
    # a dedicated character to build a squad around. Scales off ELE (see
    # the elemental-scaling pass in this module's docstring).
    "nyrvite_skill": _skill(
        "nyrvite_skill", "Shadowpierce", 20, 1,
        "Deal 80% ELE damage to all enemies, with a 50% chance to chip 3 extra Poise from each hit target.",
        {"kind": "aoe_damage_chance_poise_strike", "damage_percent": 80, "damage_stat": "elemental",
         "poise_chance_percent": 50, "bonus_poise": 3},
    ),
    "nyrvite_ultimate": _ultimate(
        "nyrvite_ultimate", "Blackout Protocol",
        "Shatter the enemy line's composure -- chip 5 Poise from every enemy at once, breaking any that can't take it.",
        {"kind": "team_poise_strike", "poise_damage": 5},
    ),
    # AMPLIFIER contract: his skill was a pure resource restore. Now an
    # ELE buff with the drone-resupply flavor riding on it -- and as a
    # 5-star Amplifier he's the roster's premier ELEMENTAL enabler (see
    # the elemental-scaling pass in this module's docstring), the natural
    # partner for the elemental DPS characters.
    "virtual_skill": _skill(
        "virtual_skill", "Drone Resupply", 24, 2,
        "Support drones prime the squad's tech: +42% ELE for 3 turns, and restore 9 energy and 11 SP to each of them.",
        {"kind": "team_buff_and_resource", "buff_stat": "elemental", "buff_percent": 42,
         "duration": 3, "energy_amount": 9, "mana_amount": 11},
    ),
    "virtual_ultimate": _ultimate(
        "virtual_ultimate", "Full Swarm Protocol",
        "Boost the whole team's ELE by 50% and ATK by 30% for 3 turns.",
        {"kind": "team_double_buff", "buff_stat_1": "elemental", "buff_percent_1": 80,
         "buff_stat_2": "attack", "buff_percent_2": 55, "duration": 4},
    ),
    # ELEMENTAL scaling, including the DoT's own stat_source -- he is the
    # game's fire character and every number in his kit was ATK-based,
    # which is both off-flavor and a wasted synergy: with the DoT
    # amplification mark that replaced energy drain, an ELE burn kit now
    # has a whole support axis (Virtual/Jofrog ELE buffs, Sader Vorae's
    # ELE vulnerability mark, Nyrvite's destabilise) to build around.
    "blueflame_skill": _skill(
        "blueflame_skill", "Kindling Spray", 20, 1,
        "Deal 75% ELE damage to all enemies, with a 45% chance to set each hit target ablaze for 12% ELE per turn over 3 turns.",
        {"kind": "aoe_damage_chance_dot", "damage_percent": 75, "damage_stat": "elemental",
         "dot_chance_percent": 45, "dot_stat": "elemental", "dot_percent": 12, "duration": 3},
    ),
    "blueflame_ultimate": _ultimate(
        "blueflame_ultimate", "Wildfire Purge",
        "Deal 105% ELE damage to all enemies and set each of them ablaze for 15% ELE per turn over 3 turns.",
        {"kind": "aoe_damage_chance_dot", "damage_percent": 105, "damage_stat": "elemental",
         "dot_chance_percent": 100, "dot_stat": "elemental", "dot_percent": 15, "duration": 3},
    ),
    # ==================================================================
    # ROSTER EXPANSION -- five characters, each built on a mechanic no
    # existing character owns, so they add options rather than variants.
    #
    #   Blastix   -- the only kit that pays for AOE with SELF-damage.
    #   Gostley   -- the only DPS that heals off executions.
    #   Daffysam. -- the only 3-star with a team cleanse.
    #   Chary     -- the only Amplifier that buffs by DEBUFFING the enemy.
    #   Aizer     -- the only character who scales off the enemy's missing
    #                health rather than their own.
    # ==================================================================
    "blastix_skill": _skill(
        "blastix_skill", "Overpressure Round", 22, 1,
        "Deal 105% ATK damage to all enemies, at the cost of 8% of your own max HP.",
        {"kind": "damage_all_and_debuff_self", "damage_percent": 105, "damage_stat": "attack",
         "self_cost_percent": 8, "debuff_stat": "defense", "debuff_percent": -10, "duration": 2},
    ),
    "blastix_ultimate": _ultimate(
        "blastix_ultimate", "Total Detonation",
        "Deal 210% ATK damage to every enemy and chip 4 Poise from each of them.",
        {"kind": "aoe_damage_chance_poise_strike", "damage_percent": 210, "damage_stat": "attack",
         "poise_chance_percent": 100, "bonus_poise": 4},
    ),
    "gostley_skill": _skill(
        "gostley_skill", "Grave Tithe", 20, 1,
        "Deal 165% ATK damage. If it kills, heal yourself for 25% of your max HP.",
        # The key is heal_percent_ON_KILL. Spelled "heal_percent" here
        # originally, which made Gostley's skill raise KeyError the
        # instant it actually killed something -- a crash that only fires
        # on success, so it survived every test that didn't land a
        # finishing blow.
        {"kind": "damage_execute_heal", "damage_percent": 165, "damage_stat": "attack",
         "heal_percent_on_kill": 25},
    ),
    "gostley_ultimate": _ultimate(
        "gostley_ultimate", "Last Rites",
        # The description used to promise an outright execute, which the
        # engine has no way to do -- `execute_below_threshold` deals
        # BIGGER damage under the threshold, it doesn't instant-kill. The
        # effect also omitted `execute_damage_percent` entirely, so the
        # ability raised KeyError the moment the target was low enough
        # for the execute branch to run. Both halves are fixed here, and
        # the text now states the real numbers: this game's rule is that
        # what an ability says is what it does.
        "Deal 250% ATK damage — or 600% if the target is below 22% HP.",
        {"kind": "execute_below_threshold", "damage_percent": 250,
         "execute_damage_percent": 600, "damage_stat": "attack",
         "hp_threshold_percent": 22},
    ),
    "daffysamlake_skill": _skill(
        "daffysamlake_skill", "Lakeside Rinse", 20, 2,
        "Purge every negative effect from one ally and heal them for 22% of their max HP.",
        {"kind": "cleanse_ally_and_heal", "heal_percent": 22},
    ),
    "daffysamlake_ultimate": _ultimate(
        "daffysamlake_ultimate", "High Water",
        "Shield the whole team for 26% of each member's max HP and purge every negative effect from them.",
        {"kind": "team_shield_and_cleanse", "shield_percent": 26},
    ),
    "chary_skill": _skill(
        "chary_skill", "Confidence Trick", 22, 2,
        "Strip 24% DEF from every enemy for 3 turns.",
        {"kind": "team_debuff", "debuff_stat": "defense", "debuff_percent": -24, "duration": 3},
    ),
    "chary_ultimate": _ultimate(
        "chary_ultimate", "House Always Wins",
        "Boost the whole team's ATK and Crit DMG by 55% for 4 turns.",
        {"kind": "team_double_buff", "buff_stat_1": "attack", "buff_percent_1": 55,
         "buff_stat_2": "crit_damage", "buff_percent_2": 55, "duration": 4},
    ),
    "aizer_skill": _skill(
        "aizer_skill", "Closing Argument", 20, 1,
        "Deal 120% ATK damage, rising to 240% against a target that has already lost most of its health.",
        {"kind": "damage_scales_with_missing_hp", "base_damage_percent": 120,
         "bonus_damage_percent_at_zero_hp": 120, "damage_stat": "attack"},
    ),
    "aizer_ultimate": _ultimate(
        "aizer_ultimate", "Verdict",
        "Strike four times for 80% ATK damage each.",
        {"kind": "multi_hit", "hits": 4, "damage_percent_per_hit": 80, "damage_stat": "attack"},
    ),
}


# ---------------------------------------------------------------------
# Character passives -- reinforce each character's class role using the
# same 4 reusable passive shapes as the avatar's class passives above.
# Keyed separately from CHARACTER_KIT_MAP (by CharacterTemplate.passive_id)
# since a couple of characters share a passive shape but not a name/flavor.
# ---------------------------------------------------------------------
CHARACTER_PASSIVE_MAP: dict[str, dict] = {
    # ------------------------------------------------------------------
    # UNIQUE KIT PASSIVES.
    #
    # Every passive here is unique to its character AND keyed to that
    # character's own skill/ultimate, so it tells you how to build them.
    # Before this pass, 10 of the 24 shared an effect kind with someone
    # else (three crit_damage_bonus carriers, three stacking_buff, two
    # damage_reduction, two shield_regen) and the rest were generic gear
    # passives borrowed wholesale -- a passive said nothing about the
    # character wearing it and never touched their own kit.
    #
    # Most are `kit_reaction`s (see effects.trigger_kit_event): they fire
    # on the ACTION the character's kit is built around -- a healer's on
    # healing, a shielder's on shielding, a break specialist's on
    # breaking -- and every reward reaches the TEAM as well as the
    # carrier, so a passive is a reason to run that character alongside
    # others rather than a private stat bonus.
    # ------------------------------------------------------------------

    # --- 3-star ---
    "lily_lovelace_passive": _passive(
        "lily_lovelace_passive", "Comfort Food", "on_heal",
        "A good meal does more than mend: every ally she heals also hits 14% harder for 2 turns.",
        # Turns her spammable single-target heal into a soft damage buff,
        # so healing the right person is an offensive decision too.
        {"kind": "kit_reaction", "event": "heal", "reward": "target_buff",
         "buff_stat": "attack", "buff_percent": 14, "duration": 2},
    ),
    "nexus_passive": _passive(
        "nexus_passive", "Clout Chaser", "on_buff",
        "Every buff he lands trends harder -- the squad also gains 12% Crit DMG for 2 turns.",
        # His kit is pure crit-rate buffing; this closes the loop by
        # supplying the crit DAMAGE those crits need to matter.
        {"kind": "kit_reaction", "event": "buff", "reward": "team_buff",
         "buff_stat": "crit_damage", "buff_percent": 12, "duration": 2},
    ),
    "fax_passive": _passive(
        "fax_passive", "Frequent Flyer", "always",
        "Once he's drawn blood he doesn't let up: a killing blow earns him another turn immediately.",
        {"kind": "extra_turn_on_kill"},
    ),
    "arkiver_passive": _passive(
        "arkiver_passive", "Elemental Momentum", "on_hit_debuffed",
        "His gauntlets feed on weakness: every hit he lands on an already-weakened enemy gives the squad 10% ELE for 2 turns.",
        # Keyed to "hit_debuffed", NOT "debuff" -- his kit CONSUMES
        # debuffs (damage_bonus_if_debuffed), it never applies one, so a
        # debuff-triggered passive on him could never fire at all. This
        # version makes the squad's setup pay the squad back: whoever
        # debuffs, Arkiver converts it into team-wide elemental power.
        {"kind": "kit_reaction", "event": "hit_debuffed", "reward": "team_buff",
         "buff_stat": "elemental", "buff_percent": 10, "duration": 2},
    ),
    "slikrz_passive": _passive(
        "slikrz_passive", "Empty Static", "on_dot",
        "Whatever's left of his focus goes into the burn: applying a bleed shields him for 7% of max HP.",
        # His kit is AOE bleed; each application sustains him, which is
        # what lets a fragile Support DPS keep casting into a crowd.
        {"kind": "kit_reaction", "event": "dot", "reward": "target_shield", "percent": 7},
    ),
    "evz_passive": _passive(
        "evz_passive", "Old Habits", "on_cleanse",
        "Field triage never really stops: an ally she cleanses also leaves with a shield worth 12% of their max HP.",
        {"kind": "kit_reaction", "event": "cleanse", "reward": "target_shield", "percent": 12},
    ),
    "caandy_passive": _passive(
        "caandy_passive", "HUD Uplink", "on_buff",
        "Her visor shares the firing solution: every buff she casts also feeds the squad 8 energy.",
        # Buff + resource is exactly her kit's shape, and energy is worth
        # far more now that ultimates actually fire.
        {"kind": "kit_reaction", "event": "buff", "reward": "team_energy", "amount": 8},
    ),
    "axel_passive": _passive(
        "axel_passive", "Predator's Focus", "on_debuff",
        "His augments feed on the wound: every debuff he inflicts heals him for 8% of max HP.",
        # His skill applies TWO debuffs at once, so this is deliberately
        # his highest-uptime sustain source and rewards leading with it.
        {"kind": "kit_reaction", "event": "debuff", "reward": "self_heal", "percent": 8},
    ),
    "ih_passive": _passive(
        "ih_passive", "Loadout Sync", "always",
        "A frontline motivator to the last: whenever he takes a hit, the whole squad gains 6% ATK for 2 turns.",
        {"kind": "on_hit_team_buff", "buff_stat": "attack", "buff_percent": 6, "duration": 2},
    ),

    # --- 4-star ---
    "bee_jee_passive": _passive(
        "bee_jee_passive", "Emergency Protocol", "always",
        "Her shielding tech is simply better calibrated: every shield she grants absorbs 30% more damage.",
        {"kind": "shield_amplifier", "percent": 30},
    ),
    "sader_vorae_passive": _passive(
        "sader_vorae_passive", "Glacier-Trained Reflexes", "on_debuff",
        "She reads a target once and the whole flight knows: marked enemies take +8% ATK damage per mark (max 3).",
        # Her skill already marks for ELE; this adds the ATK half, so her
        # mark now sets up the ENTIRE squad rather than only elemental
        # carries -- the clearest "build around me" passive in the roster.
        {"kind": "kit_reaction", "event": "debuff", "reward": "mark_vulnerable",
         "damage_stat": "attack", "percent_per_stack": 8, "max_stacks": 3},
    ),
    "nebula_passive": _passive(
        "nebula_passive", "Terrain Advantage", "always",
        "She picks the ground before the fight starts: every buff she casts is 25% stronger.",
        # Amplifier-defining. Multiplies her own SPD/DEF ultimate and
        # makes her the pick when the squad already has buffs to scale.
        {"kind": "buff_amplifier", "percent": 25},
    ),
    "andy_passive": _passive(
        "andy_passive", "Squadron Discipline", "on_debuff",
        "A squadron under fire holds formation: every debuff he lands shakes ALL negative effects off the squad.",
        # Originally a second mark_vulnerable, which made him a reskin of
        # Sader Vorae -- and marking is HER kit, not his. A commander
        # restoring order fits his bio better and gives the roster its
        # only repeatable team-wide cleanse, which is real utility
        # against the DoT and debuff enemies added to the roster.
        {"kind": "kit_reaction", "event": "debuff", "reward": "team_cleanse"},
    ),
    "star_passive": _passive(
        "star_passive", "Cruise Control", "on_kill",
        "When it lands, there's nothing left to argue with: every enemy he finishes gives the squad 16 energy.",
        # Keyed to KILLS, not to his ultimate. Measured over 40 fights, a
        # single-target DPS this heavy only gets ~3.8 turns before the
        # fight is already over, and reached his ultimate in 3 of 40 --
        # so an ultimate-triggered passive on him was near-dead content.
        # Kills are the thing he does constantly, and his execute
        # ultimate makes him better at them than anyone.
        {"kind": "kit_reaction", "event": "kill", "reward": "team_energy", "amount": 16},
    ),
    "kotori_passive": _passive(
        "kotori_passive", "Bloodgift", "on_sacrifice",
        "Every drop she spends is worth more than her own: sacrificing HP gives the squad 18% ATK for 2 turns.",
        # Both her buttons pay HP, so this fires constantly and converts
        # her self-harm identity into the squad's damage window.
        {"kind": "kit_reaction", "event": "sacrifice", "reward": "team_buff",
         "buff_stat": "attack", "buff_percent": 18, "duration": 2},
    ),
    "jofrog_passive": _passive(
        "jofrog_passive", "Bodyguard Protocol", "on_shield",
        "Standing in front is the whole job: every shield he grants also hardens its holder by 20% DEF.",
        # His kit is taunt + shields; the DEF rider makes those shields
        # last through the hits he's deliberately pulling onto himself.
        {"kind": "kit_reaction", "event": "shield", "reward": "team_buff",
         "buff_stat": "defense", "buff_percent": 20, "duration": 2},
    ),
    "aura_passive": _passive(
        "aura_passive", "Steady Hands", "on_low_hp",
        "She refuses to go down while someone still needs her: the first fatal hit in a fight leaves her at 1 HP.",
        {"kind": "prevent_death", "charges_per_combat": 1},
    ),
    "blueflame_passive": _passive(
        "blueflame_passive", "Slow Burn", "always",
        "Every fire he starts burns hotter than the last: DoTs he applies deal 25% increased damage.",
        {"kind": "dot_amplifier", "percent": 25},
    ),

    # --- 5-star ---
    "josh_passive": _passive(
        "josh_passive", "Unfinished Business", "on_kill",
        "Every kill fuels him further: restores 20% max HP and 25 SP the instant he finishes an enemy.",
        {"kind": "on_kill_restore", "hp_percent": 20, "mana": 25},
    ),
    "refender_passive": _passive(
        "refender_passive", "Refense Doctrine", "always",
        "Offense and defense are the same thing: he gains ATK equal to 60% of his DEF.",
        # Makes DEF his damage stat, so his own team DEF buff (and
        # Nebula's, and Bee Jee's) scales his damage -- a build direction
        # no other character has.
        {"kind": "stat_conversion", "from_stat": "defense", "to_stat": "attack", "percent": 60},
    ),
    "dolphe_passive": _passive(
        "dolphe_passive", "Leader's Wavelength", "on_turn_start",
        "He keeps the whole team synced and supplied: 5 energy and 6 SP to everyone, every turn.",
        {"kind": "aura_team_resource_regen", "energy_amount": 5, "mana_amount": 6},
    ),
    "caliper_passive": _passive(
        "caliper_passive", "Dead Aim", "on_ultimate",
        "She only needs the line once: her ultimate leaves the squad with 25% Crit Rate for 3 turns.",
        {"kind": "kit_reaction", "event": "ultimate", "reward": "team_buff",
         "buff_stat": "crit_rate", "buff_percent": 25, "duration": 3},
    ),
    "nyrvite_passive": _passive(
        "nyrvite_passive", "Ghost Protocol", "on_break",
        "She works the seams: every enemy she breaks feeds the squad 15 energy.",
        # Her entire kit is poise damage, so this is the payoff for the
        # thing she is already doing -- and it makes a break specialist
        # worth bringing for the TEAM, not just for the break.
        {"kind": "kit_reaction", "event": "break", "reward": "team_energy", "amount": 15},
    ),
    "virtual_passive": _passive(
        "virtual_passive", "Engineering Corps", "on_buff",
        "His drones follow every order he gives: each buff he casts also shields the squad for 10% of max HP.",
        # Buff-plus-shield is his drone-support flavour, and pairs his
        # Amplifier kit with a defensive layer no other Amplifier has.
        {"kind": "kit_reaction", "event": "buff", "reward": "team_shield", "percent": 10},
    ),

    # --- roster expansion ---
    "blastix_passive": _passive(
        "blastix_passive", "Blast Tolerance", "always",
        "He runs on his own blood: 14% of all damage he deals comes back as health.",
        # Closes the loop his SKILL opens. Overpressure Round costs 8% of
        # his max HP per cast, which with no sustain would make his own
        # best button unusable twice in a row; lifesteal turns that cost
        # into a rhythm -- spend health to hit everything, take it back off
        # the things you hit. An engine kind that already exists, rather
        # than a new hook invented for one character.
        {"kind": "lifesteal", "percent": 14},
    ),
    "gostley_passive": _passive(
        "gostley_passive", "Collector's Due", "on_kill",
        "Each life he takes feeds the squad: every kill restores 8% max HP to the whole team.",
        {"kind": "kit_reaction", "event": "kill", "reward": "team_heal", "percent": 8},
    ),
    "daffysamlake_passive": _passive(
        "daffysamlake_passive", "Still Waters", "on_cleanse",
        "Every effect he washes away leaves the team steadier -- +16% DEF for 2 turns.",
        {"kind": "kit_reaction", "event": "cleanse", "reward": "team_buff",
         "buff_stat": "defense", "buff_percent": 16, "duration": 2},
    ),
    "chary_passive": _passive(
        "chary_passive", "Reading the Room", "on_debuff",
        "She turns every weakness she finds into an opening: each debuff she lands gives the squad 13% Crit Rate for 2 turns.",
        # The pivot that makes her an Amplifier rather than a Support DPS:
        # her buttons debuff the ENEMY, and this is what converts that into
        # offence for her own side.
        {"kind": "kit_reaction", "event": "debuff", "reward": "team_buff",
         "buff_stat": "crit_rate", "buff_percent": 13, "duration": 2},
    ),
    "aizer_passive": _passive(
        "aizer_passive", "No Further Questions", "always",
        "He never stops closing: +6% ATK every turn, stacking up to 6 times.",
        {"kind": "stacking_buff", "buff_stat": "attack", "percent_per_stack": 6, "max_stacks": 6},
    ),
}


def get_class_kit(character_class: CharacterClass) -> dict[str, dict]:
    return CLASS_KIT_MAP[character_class]


def get_character_skill(skill_id: str) -> dict | None:
    return CHARACTER_KIT_MAP.get(skill_id)


def get_character_ultimate(ultimate_id: str) -> dict | None:
    return CHARACTER_KIT_MAP.get(ultimate_id)


def get_character_passive(passive_id: str) -> dict | None:
    return CHARACTER_PASSIVE_MAP.get(passive_id)
