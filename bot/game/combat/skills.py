"""
Character skill/ultimate/passive kits -- the Combat Overhaul's replacement
for the old scroll-granted ultimate. Every combatant now gets these
straight from their kit rather than gear:

  * `character_skill`    -- one active ability, costs MANA, always available.
  * `character_ultimate` -- one active ability, costs 100 ENERGY.
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
            "resource_type": "energy", "resource_cost": 100, "cooldown": 0, "is_ultimate": True,
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
        "skill": {
            "id": "avatar_support_dps_skill", "name": "Marked Shot",
            "resource_type": "mana", "resource_cost": 18, "cooldown": 1,
            "description": "Deal 130% ATK damage and reduce the target's DEF by 20% for 2 turns.",
            "effect": {"kind": "damage_and_debuff", "damage_percent": 130, "damage_stat": "attack",
                       "debuff_stat": "defense", "debuff_percent": -20, "duration": 2},
        },
        "ultimate": {
            "id": "avatar_support_dps_ultimate", "name": "Coordinated Barrage",
            "resource_type": "energy", "resource_cost": 100, "cooldown": 0, "is_ultimate": True,
            "description": "Strike the target 3 times for 95% ATK damage each.",
            "effect": {"kind": "multi_hit", "hits": 3, "damage_percent_per_hit": 95, "damage_stat": "attack"},
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
            "resource_type": "energy", "resource_cost": 100, "cooldown": 0, "is_ultimate": True,
            "description": "Boost the whole team's ATK by 45% for 3 turns.",
            "effect": {"kind": "team_buff", "buff_stat": "attack", "buff_percent": 45, "duration": 3},
        },
        "passive": {
            "id": "avatar_amplifier_passive", "name": "Unshakeable Resolve", "trigger": "on_turn_start",
            "description": "At the start of every turn, restores 4 energy and 6 mana to the whole team.",
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
            "resource_type": "energy", "resource_cost": 100, "cooldown": 0, "is_ultimate": True,
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
    return {"id": cid, "name": name, "resource_type": "energy", "resource_cost": 100,
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
        "fax_skill", "Strafing Run", 18, 1,
        "Deal 130% ATK damage and reduce the target's DEF by 15% for 2 turns.",
        {"kind": "damage_and_debuff", "damage_percent": 130, "damage_stat": "attack",
         "debuff_stat": "defense", "debuff_percent": -15, "duration": 2},
    ),
    "fax_ultimate": _ultimate(
        "fax_ultimate", "Cargo Bomb Run",
        "Strike the target 3 times for 100% ATK damage each.",
        {"kind": "multi_hit", "hits": 3, "damage_percent_per_hit": 100, "damage_stat": "attack"},
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
        "sader_vorae_skill", "Strafing Pass", 20, 1,
        "Deal 135% ATK damage and reduce the target's SPD by 18% for 2 turns.",
        {"kind": "damage_and_debuff", "damage_percent": 135, "damage_stat": "attack",
         "debuff_stat": "speed", "debuff_percent": -18, "duration": 2},
    ),
    "sader_vorae_ultimate": _ultimate(
        "sader_vorae_ultimate", "Glacier 15 Reckoning",
        "Strike the target 3 times for 110% ATK damage each.",
        {"kind": "multi_hit", "hits": 3, "damage_percent_per_hit": 110, "damage_stat": "attack"},
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
        "At the start of every turn, hypes up the whole team, restoring 4 energy and 6 mana to each of them.",
    ),
    "fax_passive": _support_dps_passive(
        "fax_passive", "Frequent Flyer",
        "Gains 3% Crit Rate per turn (max 5 stacks) -- more accurate strafing runs the longer he flies.",
    ),
    "arkiver_passive": _dps_passive(
        "arkiver_passive", "Elemental Momentum",
        "Gains 4% ATK per turn (max 5 stacks) -- his gauntlets build charge the longer he fights.",
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
        "At the start of every turn, reads the terrain to keep the whole team's supply lines flowing: 5 energy and 7 mana each.",
        energy_amount=5, mana_amount=7,
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
}


def get_class_kit(character_class: CharacterClass) -> dict[str, dict]:
    return CLASS_KIT_MAP[character_class]


def get_character_skill(skill_id: str) -> dict | None:
    return CHARACTER_KIT_MAP.get(skill_id)


def get_character_ultimate(ultimate_id: str) -> dict | None:
    return CHARACTER_KIT_MAP.get(ultimate_id)


def get_character_passive(passive_id: str) -> dict | None:
    return CHARACTER_PASSIVE_MAP.get(passive_id)
