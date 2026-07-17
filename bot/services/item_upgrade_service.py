"""
Bridges the pure item math in bot/game/loot/upgrades.py to the player's
wallet. The upgrade math itself stays currency-agnostic (it's just stats);
this is where "does the player have enough gold/tokens/materials" lives.

Every "how much will this cost" function here has a matching preview
(get_*_cost) that callers (cogs/UI) can show BEFORE the player commits, per
the display requirement that costs should always be visible up front.
"""

from __future__ import annotations

from bot.database.models.enums import MaterialType, Rarity
from bot.game.loot.rarity_config import (
    ADD_SUBSTAT_COST,
    MAX_SUBSTATS,
    REROLL_COST,
    upgrade_level_cap,
)
from bot.game.loot.upgrades import add_substat as _add_substat_math
from bot.game.loot.upgrades import level_up, reroll_substats
from bot.services import quest_service
from bot.services.currency_service import add_currency, format_currency, spend_currency

LEVEL_UP_GOLD_PER_LEVEL = 15
LEVEL_UP_MATERIAL_PER_LEVEL = 3

# Which two materials a given rarity's upgrades consume (see
# MaterialType.tier in enums.py -- common/uncommon items use tier-0
# materials, all the way up to Divine using tier-3 Void/Entropy).
_MATERIALS_BY_TIER: dict[int, tuple[MaterialType, MaterialType]] = {
    0: (MaterialType.WOOD, MaterialType.STONE),
    1: (MaterialType.METAL, MaterialType.CRYSTAL),
    2: (MaterialType.XENDIUM, MaterialType.PERMAFROST_ORE),
    3: (MaterialType.VOID, MaterialType.ENTROPY),
}

_RARITY_TO_MATERIAL_TIER: dict[Rarity, int] = {
    Rarity.COMMON: 0, Rarity.UNCOMMON: 0,
    Rarity.RARE: 1, Rarity.EPIC: 1,
    Rarity.LEGENDARY: 2, Rarity.MYTHIC: 2,
    Rarity.DIVINE: 3,
}


def materials_for_rarity(rarity: Rarity) -> tuple[MaterialType, MaterialType]:
    return _MATERIALS_BY_TIER[_RARITY_TO_MATERIAL_TIER[rarity]]


# ---------------------------------------------------------------------
# Reroll -- re-rolls existing substats only. Flat gold cost per rarity
# (does NOT scale with reroll_count); token cost also flat per rarity.
# ---------------------------------------------------------------------
def get_reroll_cost(item) -> dict[str, int]:
    return dict(REROLL_COST[item.rarity])


def reroll_item(db, player, item) -> tuple[bool, str]:
    if not item.substats:
        return False, f"{item.display_name} has no substats to reroll yet -- add one first."

    cost = get_reroll_cost(item)
    if getattr(player, "reroll_tokens", 0) < cost["tokens"]:
        return False, f"Not enough {format_currency('reroll_tokens', cost['tokens'])}."
    if not spend_currency(db, player, "reroll_tokens", cost["tokens"]):
        return False, f"Not enough {format_currency('reroll_tokens', cost['tokens'])}."
    if not spend_currency(db, player, "gold", cost["gold"]):
        # refund tokens since gold failed -- add_currency, never spend_currency
        # with a negative amount (spend_currency rejects negatives outright).
        add_currency(db, player, "reroll_tokens", cost["tokens"])
        return False, f"Not enough {format_currency('gold', cost['gold'])}."

    reroll_substats(item)
    db.commit()
    return True, f"Rerolled {item.display_name} for {format_currency('reroll_tokens', cost['tokens'])} + {format_currency('gold', cost['gold'])}."


# ---------------------------------------------------------------------
# Add substat -- grows substat count up to MAX_SUBSTATS. Much steeper
# than a plain reroll.
# ---------------------------------------------------------------------
def get_add_substat_cost(item) -> dict[str, int] | None:
    if len(item.substats) >= MAX_SUBSTATS:
        return None
    return dict(ADD_SUBSTAT_COST[item.rarity])


def add_substat_to_item(db, player, item) -> tuple[bool, str]:
    cost = get_add_substat_cost(item)
    if cost is None:
        return False, f"{item.display_name} already has the maximum of {MAX_SUBSTATS} substats."

    if not spend_currency(db, player, "reroll_tokens", cost["tokens"]):
        return False, f"Not enough {format_currency('reroll_tokens', cost['tokens'])}."
    if not spend_currency(db, player, "gold", cost["gold"]):
        add_currency(db, player, "reroll_tokens", cost["tokens"])
        return False, f"Not enough {format_currency('gold', cost['gold'])}."

    _add_substat_math(item)
    db.commit()
    return True, f"Added a new substat to {item.display_name} for {format_currency('reroll_tokens', cost['tokens'])} + {format_currency('gold', cost['gold'])}."


# ---------------------------------------------------------------------
# Level up -- gold + tiered materials, capped by rarity.
# ---------------------------------------------------------------------
def get_level_up_cost(item, levels: int = 1) -> dict:
    cap = upgrade_level_cap(item.rarity)
    max_levels = max(0, min(levels, cap - item.item_level))
    if max_levels <= 0:
        return {"levels": 0, "gold": 0, "materials": {}, "at_cap": True}

    gold = sum(LEVEL_UP_GOLD_PER_LEVEL * (item.item_level + i) for i in range(max_levels))
    mat_qty = sum(LEVEL_UP_MATERIAL_PER_LEVEL for _ in range(max_levels))
    mat_a, mat_b = materials_for_rarity(item.rarity)
    # split the material cost across the tier's two materials
    materials = {mat_a.value: (mat_qty + 1) // 2, mat_b.value: mat_qty // 2}
    return {"levels": max_levels, "gold": gold, "materials": materials, "at_cap": max_levels < levels}


def level_up_item(db, player, item, levels: int = 1) -> tuple[bool, str]:
    cost = get_level_up_cost(item, levels)
    if cost["levels"] <= 0:
        cap = upgrade_level_cap(item.rarity)
        return False, f"{item.display_name} is already at its upgrade cap for {item.rarity.value} rarity ({cap})."

    if not spend_currency(db, player, "gold", cost["gold"]):
        return False, f"Not enough {format_currency('gold', cost['gold'])}."

    spent_materials = []
    for mat_name, qty in cost["materials"].items():
        if qty <= 0:
            continue
        if not spend_currency(db, player, mat_name, qty):
            # refund gold + any materials already spent this call
            add_currency(db, player, "gold", cost["gold"])
            for spent_name, spent_qty in spent_materials:
                add_currency(db, player, spent_name, spent_qty)
            return False, f"Not enough {format_currency(mat_name, qty)}."
        spent_materials.append((mat_name, qty))

    level_up(item, cost["levels"])
    db.commit()
    quest_service.record_progress(db, player, "upgrade_gear")
    note = " (capped)" if cost["at_cap"] else ""
    return True, f"{item.display_name} leveled up to {item.item_level} for {format_currency('gold', cost['gold'])}{note}."
