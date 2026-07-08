"""
Combatants are built once at battle start and thrown away when it ends --
nothing here is persisted. This is the only place that needs to know how
Player + InventoryItem map onto Combatant.

Stat resolution order (important for the "flat vs percent substats"
design): percent-based substats are always computed against the player's
PURE base stat (before any gear), never against another item's bonus --
so equipping five items that each roll "+10% attack" all add the same
absolute amount, they never compound with each other.

Ability resolution:
  * WEAPON items contribute their active_ability into active_abilities,
    tagged source="weapon" -- up to 2 (one per equipped weapon).
  * ARTIFACT items contribute their active_ability into active_abilities,
    tagged source="artifact" -- up to 2 (one per equipped artifact).
  * ARMOR items (helmet/necklace, chest, leggings, boots) contribute only
    passive_ability into passive_abilities.
  * The SCROLL item's active_ability becomes ultimate_ability.
"""

from __future__ import annotations

from bot.database.models.enums import ItemType
from bot.game.combat.combatant import STAT_KEYS, Combatant


def _resolve_gear_stats(base_player_stats: dict, equipped_items: list) -> dict:
    """Combines pure player base stats with every equipped item's flat and
    percent contributions. Percent substats are computed once against
    `base_player_stats` (the pre-gear values), then added as a flat amount
    -- they never compound with other items' bonuses."""
    final_stats = dict(base_player_stats)

    for item in equipped_items:
        for stat in STAT_KEYS:
            final_stats[stat] += item.total_stat_bonus_flat(stat)

    for item in equipped_items:
        for stat in STAT_KEYS:
            percent = item.percent_substats_for(stat)
            if percent:
                final_stats[stat] += base_player_stats.get(stat, 0) * percent / 100

    return final_stats


def build_player_combatant(player, equipped_items: list) -> Combatant:
    """`equipped_items` should be the player's InventoryItems where
    is_equipped is True (fetch and filter before calling this)."""
    base_player_stats = {stat: getattr(player, stat) for stat in STAT_KEYS}
    final_stats = _resolve_gear_stats(base_player_stats, equipped_items)

    active_abilities = []
    passive_abilities = []
    ultimate_ability = None

    # Equip order is stable (ascending id / acquired_at via inventory
    # listing) so "primary" weapon/artifact consistently maps to skill
    # slot 1 and "secondary" to skill slot 2.
    for item in sorted(equipped_items, key=lambda i: (i.slot.value, i.equip_slot_index, i.id)):
        if item.item_type == ItemType.WEAPON:
            if item.active_ability:
                ability = dict(item.active_ability)
                ability["source"] = "weapon"
                ability["source_item"] = item.display_name
                active_abilities.append(ability)
        elif item.item_type == ItemType.ARTIFACT:
            if item.active_ability:
                ability = dict(item.active_ability)
                ability["source"] = "artifact"
                ability["source_item"] = item.display_name
                active_abilities.append(ability)
        elif item.item_type == ItemType.ARMOR:
            if item.passive_ability:
                passive = dict(item.passive_ability)
                passive["source_item"] = item.display_name
                passive_abilities.append(passive)
        elif item.item_type == ItemType.SCROLL:
            if item.active_ability:
                ultimate_ability = dict(item.active_ability)
                ultimate_ability["is_ultimate"] = True
                ultimate_ability["resource_type"] = "energy"
                ultimate_ability["resource_cost"] = 100
                ultimate_ability["cooldown"] = 0
                ultimate_ability["source_item"] = item.display_name

    return Combatant(
        name=player.username,
        is_player=True,
        base_stats=final_stats,
        current_hp=final_stats["max_hp"],
        max_hp=final_stats["max_hp"],
        mana=final_stats["max_mana"],
        max_mana=final_stats["max_mana"],
        energy=0,
        max_energy=player.max_energy,
        active_abilities=active_abilities,
        ultimate_ability=ultimate_ability,
        passive_abilities=passive_abilities,
    )


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
        ultimate.setdefault("resource_cost", 100)
        ultimate.setdefault("cooldown", 0)

    return Combatant(
        name=template["name"],
        is_player=False,
        base_stats=base_stats,
        current_hp=base_stats["max_hp"],
        max_hp=base_stats["max_hp"],
        # Enemies aren't resource-constrained the way players are for mana
        # -- their "budget" is which abilities they're given, not a scarce
        # pool. Energy is still capped at 100 so an enemy ultimate feels
        # earned rather than spammed turn one.
        mana=9999,
        max_mana=9999,
        energy=0,
        max_energy=100,
        active_abilities=[dict(a, source="enemy") for a in template.get("active_abilities", [])],
        ultimate_ability=ultimate,
        passive_abilities=list(template.get("passive_abilities", [])),
    )
