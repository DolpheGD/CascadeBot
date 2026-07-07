"""
Combatants are built once at battle start and thrown away when it ends --
nothing here is persisted. This is the only place that needs to know how
Player + InventoryItem map onto Combatant.
"""

from __future__ import annotations

from bot.game.combat.combatant import STAT_KEYS, Combatant


def build_player_combatant(player, equipped_items: list) -> Combatant:
    """`equipped_items` should be the player's InventoryItems where
    is_equipped is True (fetch and filter before calling this)."""
    base_stats = {stat: getattr(player, stat) for stat in STAT_KEYS}

    active_abilities = []
    passive_abilities = []

    for item in equipped_items:
        for stat in STAT_KEYS:
            base_stats[stat] += item.total_stat_bonus(stat)
        if item.active_ability:
            active_abilities.append(item.active_ability)
        if item.passive_ability:
            passive_abilities.append(item.passive_ability)

    return Combatant(
        name=player.username,
        is_player=True,
        base_stats=base_stats,
        current_hp=base_stats["max_hp"],
        max_hp=base_stats["max_hp"],
        mana=player.max_mana,
        max_mana=player.max_mana,
        energy=player.max_energy,
        max_energy=player.max_energy,
        active_abilities=active_abilities,
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

    return Combatant(
        name=template["name"],
        is_player=False,
        base_stats=base_stats,
        current_hp=base_stats["max_hp"],
        max_hp=base_stats["max_hp"],
        # Enemies aren't resource-constrained the way players are -- their
        # "budget" is which abilities they're given, not a scarce pool.
        mana=9999,
        max_mana=9999,
        energy=9999,
        max_energy=9999,
        active_abilities=list(template.get("active_abilities", [])),
        passive_abilities=list(template.get("passive_abilities", [])),
    )
