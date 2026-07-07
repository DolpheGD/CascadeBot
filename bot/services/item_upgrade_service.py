"""
Bridges the pure item math in bot/game/loot/upgrades.py to the player's
wallet. The upgrade math itself stays currency-agnostic (it's just stats);
this is where "does the player have enough gold" lives.
"""

from __future__ import annotations

from bot.game.loot.upgrades import level_up, reroll_substats
from bot.services.currency_service import spend_currency

REROLL_BASE_COST = 50
REROLL_COST_PER_PRIOR_REROLL = 25

LEVEL_UP_COST_PER_LEVEL = 20


def get_reroll_cost(item) -> int:
    return REROLL_BASE_COST + REROLL_COST_PER_PRIOR_REROLL * item.reroll_count


def get_level_up_cost(item, levels: int = 1) -> int:
    return sum(
        LEVEL_UP_COST_PER_LEVEL * (item.item_level + i) for i in range(levels)
    )


def reroll_item(db, player, item) -> tuple[bool, str]:
    cost = get_reroll_cost(item)
    if not spend_currency(db, player, "gold", cost):
        return False, f"Not enough gold (need {cost})."

    reroll_substats(item)
    db.commit()
    return True, f"Rerolled {item.display_name} for {cost} gold."


def level_up_item(db, player, item, levels: int = 1) -> tuple[bool, str]:
    cost = get_level_up_cost(item, levels)
    if not spend_currency(db, player, "gold", cost):
        return False, f"Not enough gold (need {cost})."

    level_up(item, levels)
    db.commit()
    return True, f"{item.display_name} leveled up to {item.item_level} for {cost} gold."
