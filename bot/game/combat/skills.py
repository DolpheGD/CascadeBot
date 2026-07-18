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
        "Boost the whole team's ATK by 35% for 3 turns.",
        {"kind": "team_buff", "buff_stat": "attack", "buff_percent": 35, "duration": 3},
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
        "Strike the target twice for 100% ATK damage each.",
        {"kind": "multi_hit", "hits": 2, "damage_percent_per_hit": 100, "damage_stat": "attack"},
    ),
    "arkiver_ultimate": _ultimate(
        "arkiver_ultimate", "Elemental Fury",
        "Deal 380% ELE damage to the target.",
        {"kind": "damage_multiplier", "damage_percent": 380, "damage_stat": "elemental"},
    ),
    "slikrz_skill": _skill(
        "slikrz_skill", "Blank Stare", 18, 1,
        "Deal 70% ATK damage to all enemies, with a 40% chance to reduce each hit target's DEF by 15% for 2 turns.",
        {"kind": "aoe_damage_chance_debuff", "damage_percent": 70, "damage_stat": "attack",
         "debuff_chance_percent": 40, "debuff_stat": "defense", "debuff_percent": -15, "duration": 2},
    ),
    "slikrz_ultimate": _ultimate(
        "slikrz_ultimate", "Flatline Frenzy",
        "Deal 100% ATK damage to all enemies and reduce each of their DEF by 15% for 2 turns.",
        {"kind": "aoe_damage_chance_debuff", "damage_percent": 100, "damage_stat": "attack",
         "debuff_chance_percent": 100, "debuff_stat": "defense", "debuff_percent": -15, "duration": 2},
    ),
    "evz_skill": _skill(
        "evz_skill", "Bedside Manner", 18, 1,
        "Heal the lowest-HP ally for 20% of their max HP.",
        {"kind": "heal_lowest_ally_percent_max_hp", "percent": 20},
    ),
    "evz_ultimate": _ultimate(
        "evz_ultimate", "Emergency Landing",
        "Heal the whole team for 35% of each member's max HP.",
        {"kind": "team_heal_percent_max_hp", "percent": 35},
    ),
    "caandy_skill": _skill(
        "caandy_skill", "Visor Sync", 20, 2,
        "Instantly restore 15 energy and 20 SP to the whole team.",
        {"kind": "team_resource_restore", "energy_amount": 15, "mana_amount": 20},
    ),
    "caandy_ultimate": _ultimate(
        "caandy_ultimate", "AI Overclock",
        "Boost the whole team's ATK by 40% for 3 turns.",
        {"kind": "team_buff", "buff_stat": "attack", "buff_percent": 40, "duration": 3},
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
        "Heal the lowest-HP ally for 25% of their max HP.",
        {"kind": "heal_lowest_ally_percent_max_hp", "percent": 25},
    ),
    "bee_jee_ultimate": _ultimate(
        "bee_jee_ultimate", "Antidote Protocol",
        "Heal the whole team for 45% of each member's max HP.",
        {"kind": "team_heal_percent_max_hp", "percent": 45},
    ),
    "sader_vorae_skill": _skill(
        "sader_vorae_skill", "Wide Strafing Pass", 20, 1,
        "Deal 75% ATK damage to all enemies, with a 45% chance to reduce each hit target's SPD by 18% for 2 turns.",
        {"kind": "aoe_damage_chance_debuff", "damage_percent": 75, "damage_stat": "attack",
         "debuff_chance_percent": 45, "debuff_stat": "speed", "debuff_percent": -18, "duration": 2},
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
        "Boost the whole team's ATK by 40% for 3 turns.",
        {"kind": "team_buff", "buff_stat": "attack", "buff_percent": 40, "duration": 3},
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
        "Deal 210% ATK damage to the target.",
        {"kind": "damage_multiplier", "damage_percent": 210, "damage_stat": "attack"},
    ),
    "josh_ultimate": _ultimate(
        "josh_ultimate", "Rex's Memory",
        "Deal 320% ATK damage; if this kills the target, heal for 30% max HP.",
        {"kind": "damage_execute_heal", "damage_percent": 320, "damage_stat": "attack",
         "heal_percent_on_kill": 30},
    ),
    "refender_skill": _skill(
        "refender_skill", "Refense Stance", 18, 2,
        "Gain 25% DEF for 2 turns, trading 10% ATK.",
        {"kind": "self_buff_debuff", "buff_stat": "defense", "buff_percent": 25,
         "debuff_stat": "attack", "debuff_percent": -10, "duration": 2},
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
    "nexus_passive": _amplifier_passive(
        "nexus_passive", "Clout Chaser",
        "At the start of every turn, hypes up the whole team, restoring 4 energy and 6 SP to each of them.",
    ),
    "fax_passive": _support_dps_passive(
        "fax_passive", "Frequent Flyer",
        "Gains 3% Crit Rate per turn (max 5 stacks) -- more accurate strafing runs the longer he flies.",
    ),
    "arkiver_passive": _dps_passive(
        "arkiver_passive", "Elemental Momentum",
        "Gains 4% ATK per turn (max 5 stacks) -- his gauntlets build charge the longer he fights.",
    ),
    "slikrz_passive": _support_dps_passive(
        "slikrz_passive", "Empty Static",
        "Gains 3% Crit Rate per turn (max 5 stacks) -- whatever's left of his focus sharpens the longer the fight runs.",
    ),
    "evz_passive": _sustain_passive(
        "evz_passive", "Old Habits",
        "At the start of every turn, the whole team is kept stable and healed for 3% of their own max HP.",
    ),
    "caandy_passive": _amplifier_passive(
        "caandy_passive", "HUD Uplink",
        "At the start of every turn, her visor feeds the whole team 4 energy and 6 SP.",
    ),
    "axel_passive": _dps_passive(
        "axel_passive", "Predator's Focus",
        "Gains 4% ATK per turn (max 5 stacks) -- she reads an opponent's weaknesses faster the longer she studies them.",
    ),
    "ih_passive": _support_dps_passive(
        "ih_passive", "Loadout Sync",
        "Gains 3% Crit Rate per turn (max 5 stacks) -- his own aim sharpens the longer he keeps the squad running.",
    ),

    # --- 4-star ---
    "bee_jee_passive": _sustain_passive(
        "bee_jee_passive", "Emergency Protocol",
        "At the start of every turn, the whole team is stabilized and healed for 4% of their own max HP.", percent=4,
    ),
    "sader_vorae_passive": _support_dps_passive(
        "sader_vorae_passive", "Glacier-Trained Reflexes",
        "Gains 3% Crit Rate per turn (max 5 stacks) -- years of Glacier 15 flight drills.",
    ),
    "nebula_passive": _amplifier_passive(
        "nebula_passive", "Terrain Advantage",
        "At the start of every turn, reads the terrain to keep the whole team's supply lines flowing: 5 energy and 7 SP each.",
        energy_amount=5, mana_amount=7,
    ),
    "andy_passive": _support_dps_passive(
        "andy_passive", "Squadron Discipline",
        "Gains 3% Crit Rate per turn (max 5 stacks) -- years of commanding a squadron sharpen every follow-up shot.",
    ),
    "star_passive": _dps_passive(
        "star_passive", "Cruise Control",
        "Gains 4% ATK per turn (max 5 stacks) -- he never rushes, but he never stops building up steam either.",
    ),
    "kotori_passive": _passive(
        "kotori_passive", "Bloodgift", "on_turn_start",
        "At the start of every turn, sacrifices 2% of her own max HP to heal the rest of the team for 4% of their own max HP each.",
        {"kind": "aura_team_regen_self_sacrifice", "self_cost_percent": 2, "percent": 4},
    ),
    "jofrog_passive": _amplifier_passive(
        "jofrog_passive", "Steady Supply",
        "At the start of every turn, keeps the whole team's systems topped up: 5 energy and 7 SP each.",
        energy_amount=5, mana_amount=7,
    ),
    "aura_passive": _sustain_passive(
        "aura_passive", "Steady Hands",
        "At the start of every turn, the whole team is stabilized and healed for 4% of their own max HP.", percent=4,
    ),

    # --- 5-star ---
    "josh_passive": _dps_passive(
        "josh_passive", "Unfinished Business",
        "Gains 5% ATK per turn (max 5 stacks) -- driven harder the longer the fight drags on.", percent_per_stack=5,
    ),
    "refender_passive": _sustain_passive(
        "refender_passive", "Refense Doctrine",
        "At the start of every turn, the whole team regenerates 4% of their own max HP -- balance, extended to everyone around him.", percent=4,
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
    "nyrvite_passive": _support_dps_passive(
        "nyrvite_passive", "Ghost Protocol",
        "Gains 4% Crit Rate per turn (max 5 stacks) -- unseen and unheard, she lines up the perfect shot.",
        percent_per_stack=4,
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
