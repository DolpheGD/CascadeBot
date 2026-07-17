"""
Combatants are built once at battle start and thrown away when it ends --
nothing here is persisted (except the HP snapshot combat_service takes
back out afterward). This is the only place that needs to know how
PlayerCharacter + InventoryItem + kit registries map onto Combatant.

Combat Overhaul: every squad member (including the player's own avatar) is
built the same way via build_character_combatant() -- one Combatant per
PlayerCharacter. There is no more single "the player" Combatant; a full
battle now runs build_party_combatants() for up to 4 squad members against
1-3 (or more, for tougher encounters) enemy Combatants.

Stat resolution order (important for the "flat vs percent substats"
design): percent-based substats are always computed against the
CHARACTER'S pure base stat at their current level (before any gear), never
against another item's bonus -- so equipping several items that each roll
"+10% attack" all add the same absolute amount; they never compound with
each other.

Ability resolution per character:
  * character_skill (mana) + character_ultimate (energy, 100) -- always
    present, resolved from the kit registries (bot/game/combat/skills.py)
    by class (for the switchable avatar) or by the character's fixed
    skill_id/ultimate_id (for pulled characters).
  * weapon_skill -- from the equipped WEAPON's active_ability, if any.
  * artifact_skill -- from the equipped ARTIFACT's active_ability, if any.
  * passives -- from the equipped ARMOR/ACCESSORY's passive_ability, if any.
"""

from __future__ import annotations

from bot.database.models.enums import ItemType
from bot.game.combat.combatant import STAT_KEYS, Combatant
from bot.game.combat.skills import (
    get_character_passive,
    get_character_skill,
    get_character_ultimate,
    get_class_kit,
)


def base_character_stats(player_character) -> dict:
    """Template base stats + linear growth to the character's current
    level. Only HP/ATK/DEF/ELE/MP/SPD grow with level (per the leveling
    spec: 'marginally' -- crit rate/damage/recharge stay put and are gear's
    job to move)."""
    template = player_character.template
    levels = max(0, player_character.level - 1)
    return {
        "attack": template.base_attack + template.growth_attack * levels,
        "defense": template.base_defense + template.growth_defense * levels,
        "elemental": template.base_elemental + template.growth_elemental * levels,
        "speed": template.base_speed + template.growth_speed * levels,
        "max_hp": template.base_hp + template.growth_hp * levels,
        "max_mana": template.base_mana + template.growth_mana * levels,
        "crit_rate": template.base_crit_rate,
        "crit_damage": template.base_crit_damage,
        "recharge": template.base_recharge,
    }


# Back-compat alias -- keep the old private name working for any in-repo
# callers that predate the public export above.
_base_character_stats = base_character_stats


def _resolve_gear_stats(base_stats: dict, equipped_items: list) -> dict:
    """Combines pure character base stats with every equipped item's flat
    and percent contributions. Percent substats are computed once against
    `base_stats` (the pre-gear values), then added as a flat amount -- they
    never compound with other items' bonuses."""
    final_stats = dict(base_stats)

    for item in equipped_items:
        for stat in STAT_KEYS:
            final_stats[stat] += item.total_stat_bonus_flat(stat)

    for item in equipped_items:
        for stat in STAT_KEYS:
            percent = item.percent_substats_for(stat)
            if percent:
                final_stats[stat] += base_stats.get(stat, 0) * percent / 100

    return final_stats


def _gear_abilities(equipped_items: list) -> tuple[dict | None, dict | None, list]:
    """Returns (weapon_skill, artifact_skill, passive_abilities) from
    whatever's equipped -- each slot holds at most one item now."""
    weapon_skill = None
    artifact_skill = None
    passive_abilities: list = []

    for item in equipped_items:
        if item.item_type == ItemType.WEAPON and item.active_ability:
            weapon_skill = dict(item.active_ability)
            weapon_skill["source"] = "weapon"
            weapon_skill["source_item"] = item.display_name
        elif item.item_type == ItemType.ARTIFACT and item.active_ability:
            artifact_skill = dict(item.active_ability)
            artifact_skill["source"] = "artifact"
            artifact_skill["source_item"] = item.display_name
        elif item.item_type == ItemType.ARMOR and item.passive_ability:
            passive = dict(item.passive_ability)
            passive["source_item"] = item.display_name
            passive_abilities.append(passive)

    return weapon_skill, artifact_skill, passive_abilities


def build_character_combatant(player_character, equipped_items: list) -> Combatant:
    """`equipped_items` should be that character's InventoryItems where
    is_equipped is True (fetch and filter by character_id before calling)."""
    template = player_character.template
    base_stats = _base_character_stats(player_character)
    final_stats = _resolve_gear_stats(base_stats, equipped_items)

    effective_class = player_character.effective_class()
    if template.is_player_avatar:
        kit = get_class_kit(effective_class)
        character_skill, character_ultimate = kit["skill"], kit["ultimate"]
        character_passive = kit.get("passive")
    else:
        character_skill = get_character_skill(template.skill_id)
        character_ultimate = get_character_ultimate(template.ultimate_id)
        character_passive = get_character_passive(template.passive_id)

    weapon_skill, artifact_skill, passive_abilities = _gear_abilities(equipped_items)
    if character_passive:
        passive = dict(character_passive)
        passive["source"] = "character"
        passive_abilities.append(passive)

    active_abilities = []
    if character_skill:
        ability = dict(character_skill)
        ability["source"] = "character"
        active_abilities.append(ability)
    if weapon_skill:
        active_abilities.append(weapon_skill)
    if artifact_skill:
        active_abilities.append(artifact_skill)

    ultimate_ability = None
    if character_ultimate:
        ultimate_ability = dict(character_ultimate)
        ultimate_ability["source"] = "character"
        ultimate_ability["is_ultimate"] = True

    max_hp = round(final_stats["max_hp"])
    max_mana = round(final_stats["max_mana"])

    # If the character has HP persisted from a previous battle (see
    # PlayerCharacter.current_hp / the HP-persistence display change),
    # start there instead of full -- clamped in case max_hp changed
    # (leveling, regear) since it was last saved.
    starting_hp = getattr(player_character, "current_hp", None)
    starting_hp = max_hp if starting_hp is None else max(1, min(starting_hp, max_hp))

    return Combatant(
        name=template.name,
        is_player=True,
        base_stats=final_stats,
        current_hp=starting_hp,
        max_hp=max_hp,
        character_id=player_character.id,
        character_class=effective_class.value,
        mana=max_mana,
        max_mana=max_mana,
        energy=0,
        max_energy=50,
        active_abilities=active_abilities,
        ultimate_ability=ultimate_ability,
        passive_abilities=passive_abilities,
    )


def build_party_combatants(squad: list, equipped_items_by_character: dict) -> list[Combatant]:
    """`squad` is an ordered list of PlayerCharacter (slot 0 = avatar).
    `equipped_items_by_character` maps PlayerCharacter.id -> list of that
    character's equipped InventoryItems."""
    return [
        build_character_combatant(pc, equipped_items_by_character.get(pc.id, []))
        for pc in squad
    ]


def build_enemy_combatant(template: dict, level: int = 1) -> Combatant:
    """`level` is typically the dungeon floor/expedition depth the enemy
    was encountered at -- higher floors produce tougher enemies from the
    same template via level_scale_percent."""
    scale = 1 + (level - 1) * template.get("level_scale_percent", 8) / 100
    base_stats = {
        stat: round(template["base_stats"].get(stat, 0) * scale) for stat in STAT_KEYS
    }
    base_stats["max_hp"] = max(1, base_stats["max_hp"])

    ultimate = template.get("ultimate_ability")
    if ultimate:
        ultimate = dict(ultimate)
        ultimate["is_ultimate"] = True
        ultimate.setdefault("resource_type", "energy")
        ultimate.setdefault("resource_cost", 50)
        ultimate.setdefault("cooldown", 0)

    return Combatant(
        name=template["name"],
        is_player=False,
        base_stats=base_stats,
        current_hp=base_stats["max_hp"],
        max_hp=base_stats["max_hp"],
        # Enemies aren't resource-constrained the way players are for mana
        # -- their "budget" is which abilities they're given, not a scarce
        # pool. Energy is still capped at 50 so an enemy ultimate feels
        # earned rather than spammed turn one.
        mana=9999,
        max_mana=9999,
        energy=0,
        max_energy=50,
        active_abilities=[dict(a, source="enemy") for a in template.get("active_abilities", [])],
        ultimate_ability=ultimate,
        passive_abilities=list(template.get("passive_abilities", [])),
        # Cycle turn order (see battle.py): defaults to 1 action/cycle like
        # everyone else. Set "actions_per_cycle": 2 (or higher) on an enemy
        # template to make it act that many times every cycle -- e.g. for
        # an elite or boss meant to feel meaningfully faster/more dangerous
        # than a normal enemy without breaking the "everyone still gets a
        # turn" guarantee the cycle system is built around.
        base_actions_per_cycle=template.get("actions_per_cycle", 1),
    )
