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
kit, not just their gear, has a distinct identity. A few characters also
got a damage_stat swapped onto a less-common stat (Refender's skill now
scales off his own DEFENSE instead of ATK; Caandy stacks SPD on herself
and buffs the team's SPD instead of ATK) to reward gearing around a stat
other than pure ATK/ELE. A couple of intentional cross-character combos
came out of this: Arkiver's skill (damage_bonus_if_debuffed) pays off
noticeably harder alongside any of the many Support DPS units that apply
a debuff first, and Nebula's team DEF ultimate (Summit Advantage) directly
amplifies both halves of Refender's new DEF-scaling kit at once. A couple
of characters per class (FAX, Caliper, Dolphe, Arkiver) were deliberately
left on the simple/generic shape as an easy, low-complexity baseline pick
within their class, rather than making every single option equally exotic.

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
            "resource_type": "energy", "resource_cost": 50, "cooldown": 0, "is_ultimate": True,
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
            "resource_type": "energy", "resource_cost": 50, "cooldown": 0, "is_ultimate": True,
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
            "description": "Boost the whole team's ATK by 20% for 2 turns.",
            "effect": {"kind": "team_buff", "buff_stat": "attack", "buff_percent": 20, "duration": 2},
        },
        "ultimate": {
            "id": "avatar_amplifier_ultimate", "name": "Overdrive",
            "resource_type": "energy", "resource_cost": 50, "cooldown": 0, "is_ultimate": True,
            "description": "Boost the whole team's ATK by 45% for 3 turns.",
            "effect": {"kind": "team_buff", "buff_stat": "attack", "buff_percent": 45, "duration": 3},
        },
        "passive": {
            "id": "avatar_amplifier_passive", "name": "Unshakeable Resolve", "trigger": "on_turn_start",
            "description": "At the start of every turn, restores 4 energy and 6 SP to the whole team.",
            "effect": {"kind": "aura_team_resource_regen", "energy_amount": 4, "mana_amount": 6},
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
            "resource_type": "energy", "resource_cost": 50, "cooldown": 0, "is_ultimate": True,
            "description": "Heal the whole team for 40% of each member's max HP.",
            "effect": {"kind": "team_heal_percent_max_hp", "percent": 40},
        },
        "passive": {
            "id": "avatar_sustain_passive", "name": "Second Wind", "trigger": "on_turn_start",
            "description": "At the start of every turn, the whole team regenerates 3% of their own max HP.",
            "effect": {"kind": "aura_team_regen", "percent": 3},
        },
    },
}


def _skill(cid, name, cost, cd, desc, effect):
    return {"id": cid, "name": name, "resource_type": "mana", "resource_cost": cost,
            "cooldown": cd, "description": desc, "effect": effect}


def _ultimate(cid, name, desc, effect):
    return {"id": cid, "name": name, "resource_type": "energy", "resource_cost": 50,
            "cooldown": 0, "is_ultimate": True, "description": desc, "effect": effect}


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


def _amplifier_passive(cid, name, desc, energy_amount=4, mana_amount=6):
    return _passive(cid, name, "on_turn_start", desc,
                     {"kind": "aura_team_resource_regen", "energy_amount": energy_amount, "mana_amount": mana_amount})


def _sustain_passive(cid, name, desc, percent=3):
    return _passive(cid, name, "on_turn_start", desc,
                     {"kind": "aura_team_regen", "percent": percent})


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
        "Heal the whole team for 35% of each member's max HP.",
        {"kind": "team_heal_percent_max_hp", "percent": 35},
    ),
    "nexus_skill": _skill(
        "nexus_skill", "Trending Now", 20, 2,
        "Boost the whole team's Crit Rate by 15% for 2 turns.",
        {"kind": "team_buff", "buff_stat": "crit_rate", "buff_percent": 15, "duration": 2},
    ),
    "nexus_ultimate": _ultimate(
        "nexus_ultimate", "Gone Viral",
        "Boost the whole team's Crit Rate by 30% for 3 turns.",
        {"kind": "team_buff", "buff_stat": "crit_rate", "buff_percent": 30, "duration": 3},
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
    "arkiver_skill": _skill(
        "arkiver_skill", "Twin Fang Strike", 18, 1,
        "Deal 130% ATK damage, or 220% ATK damage if the target is already weakened by a debuff.",
        {"kind": "damage_bonus_if_debuffed", "damage_percent": 130,
         "bonus_damage_percent": 90, "damage_stat": "attack"},
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
    "evz_ultimate": _ultimate(
        "evz_ultimate", "Emergency Landing",
        "Sacrifice 20% of her own max HP to boost the whole team's ATK by 35% for 3 turns.",
        {"kind": "sacrifice_hp_team_buff", "self_cost_percent": 20,
         "buff_stat": "attack", "buff_percent": 35, "duration": 3},
    ),
    "caandy_skill": _skill(
        "caandy_skill", "Visor Sync", 20, 2,
        "Instantly restore 15 energy and 20 SP to the whole team.",
        {"kind": "team_resource_restore", "energy_amount": 15, "mana_amount": 20},
    ),
    "caandy_ultimate": _ultimate(
        "caandy_ultimate", "AI Overclock",
        "Boost the whole team's SPD by 35% for 3 turns.",
        {"kind": "team_buff", "buff_stat": "speed", "buff_percent": 35, "duration": 3},
    ),
    "axel_skill": _skill(
        "axel_skill", "Weakpoint Strike", 18, 1,
        "Deal 125% ATK damage and reduce the target's ATK and DEF by 15% each for 2 turns.",
        {"kind": "damage_and_double_debuff", "damage_percent": 125, "damage_stat": "attack",
         "debuff_stat_1": "attack", "debuff_percent_1": -15,
         "debuff_stat_2": "defense", "debuff_percent_2": -15, "duration": 2},
    ),
    "axel_ultimate": _ultimate(
        "axel_ultimate", "Exposed Wound",
        "Deal 170% ATK damage, plus up to 170% more the lower the target's HP is.",
        {"kind": "damage_scales_with_missing_hp", "base_damage_percent": 170,
         "bonus_damage_percent_at_zero_hp": 170, "damage_stat": "attack"},
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
    "bee_jee_skill": _skill(
        "bee_jee_skill", "Field Triage", 20, 1,
        "Shield the whole team, each member absorbing damage equal to 18% of their own max HP.",
        {"kind": "team_shield_percent_max_hp", "percent": 18},
    ),
    "bee_jee_ultimate": _ultimate(
        "bee_jee_ultimate", "Antidote Protocol",
        "Shield the whole team, each member absorbing damage equal to 40% of their own max HP.",
        {"kind": "team_shield_percent_max_hp", "percent": 40},
    ),
    "sader_vorae_skill": _skill(
        "sader_vorae_skill", "Wide Strafing Pass", 20, 1,
        "Deal 90% ATK damage to the target and mark it, increasing the ELE damage it takes by 8% per stack (max 4 stacks).",
        {"kind": "apply_vulnerability_stack", "damage_percent": 90, "damage_stat": "attack",
         "vulnerable_damage_stat": "elemental", "percent_per_stack": 8, "max_stacks": 4},
    ),
    "sader_vorae_ultimate": _ultimate(
        "sader_vorae_ultimate", "Glacier 15 Reckoning",
        "Deal 110% ATK damage to all enemies and reduce each of their SPD by 18% for 2 turns.",
        {"kind": "aoe_damage_chance_debuff", "damage_percent": 110, "damage_stat": "attack",
         "debuff_chance_percent": 100, "debuff_stat": "speed", "debuff_percent": -18, "duration": 2},
    ),
    "nebula_skill": _skill(
        "nebula_skill", "Tactical Ground", 20, 2,
        "Boost the whole team's DEF by 20% for 2 turns.",
        {"kind": "team_buff", "buff_stat": "defense", "buff_percent": 20, "duration": 2},
    ),
    "nebula_ultimate": _ultimate(
        "nebula_ultimate", "Summit Advantage",
        "Boost the whole team's DEF by 45% for 3 turns.",
        {"kind": "team_buff", "buff_stat": "defense", "buff_percent": 45, "duration": 3},
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
    "jofrog_skill": _skill(
        "jofrog_skill", "Battery Swap", 18, 1,
        "Instantly restore 20 energy and 25 SP to the ally who needs it most.",
        {"kind": "restore_resource_to_lowest_ally", "energy_amount": 20, "mana_amount": 25},
    ),
    "jofrog_ultimate": _ultimate(
        "jofrog_ultimate", "Full Grid Sync",
        "Instantly restore 25 energy and 30 SP to the whole team.",
        {"kind": "team_resource_restore", "energy_amount": 25, "mana_amount": 30},
    ),
    "aura_skill": _skill(
        "aura_skill", "Field Dressing", 18, 1,
        "Cleanse all negative effects from the lowest-HP ally and heal them for 25% of their max HP.",
        {"kind": "cleanse_ally_and_heal", "heal_percent": 25},
    ),
    "aura_ultimate": _ultimate(
        "aura_ultimate", "Triage Surge",
        "Heal the whole team for 45% of each member's max HP.",
        {"kind": "team_heal_percent_max_hp", "percent": 45},
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
    "refender_skill": _skill(
        "refender_skill", "Refense Stance", 18, 2,
        "Channel pure defense into a decisive blow: deal 140% DEF damage to the target.",
        {"kind": "damage_multiplier", "damage_percent": 140, "damage_stat": "defense"},
    ),
    "refender_ultimate": _ultimate(
        "refender_ultimate", "Perfect Balance",
        "Heal the whole team for 40% of each member's max HP.",
        {"kind": "team_heal_percent_max_hp", "percent": 40},
    ),
    "dolphe_skill": _skill(
        "dolphe_skill", "Cascade Directive", 22, 2,
        "Boost the whole team's ATK by 28% for 2 turns.",
        {"kind": "team_buff", "buff_stat": "attack", "buff_percent": 28, "duration": 2},
    ),
    "dolphe_ultimate": _ultimate(
        "dolphe_ultimate", "Full Cascade",
        "Boost the whole team's ATK by 50% for 3 turns.",
        {"kind": "team_buff", "buff_stat": "attack", "buff_percent": 50, "duration": 3},
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
    "nyrvite_skill": _skill(
        "nyrvite_skill", "Signal Jam", 20, 1,
        "Deal 80% ATK damage to all enemies, with a 50% chance to drain 12 energy and 12 SP from each hit target.",
        {"kind": "aoe_damage_chance_resource_drain", "damage_percent": 80, "damage_stat": "attack",
         "drain_chance_percent": 50, "energy_drain": 12, "mana_drain": 12},
    ),
    "nyrvite_ultimate": _ultimate(
        "nyrvite_ultimate", "Blackout Protocol",
        "Drain 30 energy and 35 SP from every enemy at once.",
        {"kind": "team_resource_drain", "energy_amount": 30, "mana_amount": 35},
    ),
    "virtual_skill": _skill(
        "virtual_skill", "Drone Resupply", 24, 2,
        "Instantly restore 16 energy and 20 SP to the whole team.",
        {"kind": "team_resource_restore", "energy_amount": 16, "mana_amount": 20},
    ),
    "virtual_ultimate": _ultimate(
        "virtual_ultimate", "Full Swarm Protocol",
        "Boost the whole team's ATK by 48% for 3 turns.",
        {"kind": "team_buff", "buff_stat": "attack", "buff_percent": 48, "duration": 3},
    ),
    "blueflame_skill": _skill(
        "blueflame_skill", "Kindling Spray", 20, 1,
        "Deal 75% ATK damage to all enemies, with a 45% chance to set each hit target ablaze for 12% ATK per turn over 3 turns.",
        {"kind": "aoe_damage_chance_dot", "damage_percent": 75, "damage_stat": "attack",
         "dot_chance_percent": 45, "dot_stat": "attack", "dot_percent": 12, "duration": 3},
    ),
    "blueflame_ultimate": _ultimate(
        "blueflame_ultimate", "Wildfire Purge",
        "Deal 105% ATK damage to all enemies and set each of them ablaze for 15% ATK per turn over 3 turns.",
        {"kind": "aoe_damage_chance_dot", "damage_percent": 105, "damage_stat": "attack",
         "dot_chance_percent": 100, "dot_stat": "attack", "dot_percent": 15, "duration": 3},
    ),
}


# ---------------------------------------------------------------------
# Character passives -- reinforce each character's class role using the
# same 4 reusable passive shapes as the avatar's class passives above.
# Keyed separately from CHARACTER_KIT_MAP (by CharacterTemplate.passive_id)
# since a couple of characters share a passive shape but not a name/flavor.
# ---------------------------------------------------------------------
CHARACTER_PASSIVE_MAP: dict[str, dict] = {
    # --- 3-star ---
    "lily_lovelace_passive": _sustain_passive(
        "lily_lovelace_passive", "Comfort Food",
        "At the start of every turn, keeps the whole team fed and healed for 3% of their own max HP.",
    ),
    "nexus_passive": _passive(
        "nexus_passive", "Clout Chaser", "always",
        "Going viral hits different: her own critical hits deal an additional 15% damage.",
        {"kind": "crit_damage_bonus", "percent": 15},
    ),
    "fax_passive": _passive(
        "fax_passive", "Frequent Flyer", "always",
        "Once he's drawn blood, he doesn't let up: landing a killing blow earns him another turn immediately.",
        {"kind": "extra_turn_on_kill"},
    ),
    "arkiver_passive": _dps_passive(
        "arkiver_passive", "Elemental Momentum",
        "Gains 4% ATK per turn (max 5 stacks) -- his gauntlets build charge the longer he fights.",
    ),
    "slikrz_passive": _passive(
        "slikrz_passive", "Empty Static", "always",
        "Whatever's left of his focus makes every connecting hit count: critical hits deal an additional 12% damage.",
        {"kind": "crit_damage_bonus", "percent": 12},
    ),
    "evz_passive": _passive(
        "evz_passive", "Old Habits", "on_turn_start",
        "Steady hands, calm voice -- she never runs dry mid-operation: restores 10 mana at the start of every turn.",
        {"kind": "resource_regen", "resource_type": "mana", "amount": 10},
    ),
    "caandy_passive": _passive(
        "caandy_passive", "HUD Uplink", "on_turn_start",
        "Her own reflexes sharpen further each turn her visor runs: gains 4% SPD per turn (max 5 stacks).",
        {"kind": "stacking_buff", "buff_stat": "speed", "percent_per_stack": 4, "max_stacks": 5},
    ),
    "axel_passive": _passive(
        "axel_passive", "Predator's Focus", "always",
        "Her void-powered augments feed on the fight itself: heals for 12% of damage dealt on every hit.",
        {"kind": "lifesteal", "percent": 12},
    ),
    "ih_passive": _passive(
        "ih_passive", "Loadout Sync", "always",
        "A frontline motivator to the last: whenever he takes a hit, the whole squad feels the surge -- gain 6% ATK for 2 turns.",
        {"kind": "on_hit_team_buff", "buff_stat": "attack", "buff_percent": 6, "duration": 2},
    ),

    # --- 4-star ---
    "bee_jee_passive": _passive(
        "bee_jee_passive", "Emergency Protocol", "on_turn_start",
        "His own shielding tech recharges every turn: gains a shield equal to 6% of max HP (capped at 30%).",
        {"kind": "shield_regen", "percent": 6, "cap_percent": 30},
    ),
    "sader_vorae_passive": _passive(
        "sader_vorae_passive", "Glacier-Trained Reflexes", "always",
        "Years of surviving Glacier 15 taught her to turn a hit right back around: reflects 15% of damage taken back at the attacker.",
        {"kind": "damage_reflect", "percent": 15},
    ),
    "nebula_passive": _passive(
        "nebula_passive", "Terrain Advantage", "always",
        "Knows how to use the terrain to her advantage: reduces all incoming damage by 6%.",
        {"kind": "damage_reduction", "percent": 6},
    ),
    "andy_passive": _passive(
        "andy_passive", "Squadron Discipline", "always",
        "Years of commanding a squadron under fire taught him to hold the line: reduces all incoming damage by 8%.",
        {"kind": "damage_reduction", "percent": 8},
    ),
    "star_passive": _passive(
        "star_passive", "Cruise Control", "always",
        "He never rushes a swing -- when it finally lands, it lands harder. Critical hits deal an additional 18% damage.",
        {"kind": "crit_damage_bonus", "percent": 18},
    ),
    "kotori_passive": _passive(
        "kotori_passive", "Bloodgift", "on_turn_start",
        "At the start of every turn, sacrifices 2% of her own max HP to heal the rest of the team for 4% of their own max HP each.",
        {"kind": "aura_team_regen_self_sacrifice", "self_cost_percent": 2, "percent": 4},
    ),
    "jofrog_passive": _passive(
        "jofrog_passive", "Steady Supply", "on_turn_start",
        "An old bodyguard instinct dies hard: keeps his own plating charged, gaining a shield equal to 5% of max HP (capped at 25%).",
        {"kind": "shield_regen", "percent": 5, "cap_percent": 25},
    ),
    "aura_passive": _passive(
        "aura_passive", "Steady Hands", "on_low_hp",
        "She refuses to go down while someone still needs her: the first fatal hit in a fight instead leaves her at 1 HP.",
        {"kind": "prevent_death", "charges_per_combat": 1},
    ),

    # --- 5-star ---
    "josh_passive": _passive(
        "josh_passive", "Unfinished Business", "on_kill",
        "Every kill fuels him further: restores 20% max HP and 25 mana the instant he finishes an enemy.",
        {"kind": "on_kill_restore", "hp_percent": 20, "mana": 25},
    ),
    "refender_passive": _passive(
        "refender_passive", "Refense Doctrine", "always",
        "The harder he's hit, the sturdier he becomes: reduces incoming damage by 6%, plus up to 18% more the lower his own HP is.",
        {"kind": "damage_reduction_scales_with_missing_hp", "base_percent": 6, "bonus_percent_at_zero_hp": 18},
    ),
    "dolphe_passive": _amplifier_passive(
        "dolphe_passive", "Leader's Wavelength",
        "At the start of every turn, keeps the whole team synced and supplied: 6 energy and 8 SP each.",
        energy_amount=6, mana_amount=8,
    ),
    "caliper_passive": _support_dps_passive(
        "caliper_passive", "Dead Aim",
        "Gains 4% Crit Rate per turn (max 5 stacks) -- there isn't a shot she can't eventually thread.",
        percent_per_stack=4,
    ),
    "nyrvite_passive": _passive(
        "nyrvite_passive", "Ghost Protocol", "always",
        "Unseen and unheard, she's already gone before an attacker can follow through: 25% chance to stun an attacker for 1 turn whenever she's hit.",
        {"kind": "chance_stun_attacker", "percent": 25, "duration": 1},
    ),
    "virtual_passive": _passive(
        "virtual_passive", "Engineering Corps", "on_turn_start",
        "A personal drone escort reinforces him every turn: gains a shield equal to 5% of max HP (capped at 25%).",
        {"kind": "shield_regen", "percent": 5, "cap_percent": 25},
    ),
    "blueflame_passive": _passive(
        "blueflame_passive", "Slow Burn", "always",
        "Every fire he starts burns hotter than the last: DoTs he applies deal 25% increased damage.",
        {"kind": "dot_amplifier", "percent": 25},
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
