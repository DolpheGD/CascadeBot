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

# ---------------------------------------------------------------------
# LEVEL-UP COSTS.
#
# The old curve had three problems:
#
#   1. Material cost was FLAT -- 3 per level, forever. Levelling an item
#      from 30 to 31 cost exactly what 1 to 2 did, so the material half
#      of the cost stopped meaning anything almost immediately.
#   2. Gold rose strictly linearly (15 x level), which over a 35-level
#      climb never really bit.
#   3. Material TYPE was chosen by RARITY alone, and only ever two types.
#      A Divine item consumed Void/Entropy at level 1, and every upgrade
#      a player did at a given rarity drew on the same two resources --
#      so progress bottlenecked hard on whichever one they were short of,
#      while the other six piled up unused.
#
# Now:
#   * Material quantity grows with level (LEVEL_UP_MATERIAL_BASE plus one
#     more every LEVELS_PER_MATERIAL_STEP).
#   * Gold grows slightly faster than linear (see _gold_for_level) so the
#     last few levels of a high-rarity item are a real investment.
#   * Material TYPE is driven by the item's LEVEL, through overlapping
#     BANDS of THREE materials each. Overlap matters: consecutive bands
#     share a material, so crossing a band boundary is a gradual shift
#     rather than a wall, and drawing on three at once means no single
#     resource gates progress. Rarity still matters -- it sets the level
#     cap, so only high-rarity items ever reach the bands that consume
#     Void and Entropy.
# ---------------------------------------------------------------------
LEVEL_UP_GOLD_PER_LEVEL = 15          # kept as the linear base
LEVEL_UP_MATERIAL_BASE = 2            # materials at level 1
LEVELS_PER_MATERIAL_STEP = 4          # +1 material every N levels
GOLD_SUPERLINEAR_DIVISOR = 38         # smaller = steeper high-level gold

# (max_level_inclusive, materials). Checked in order; the last entry
# catches everything above it.
_MATERIAL_BANDS: list[tuple[int, tuple[MaterialType, ...]]] = [
    (5,  (MaterialType.WOOD, MaterialType.STONE)),
    (10, (MaterialType.WOOD, MaterialType.STONE, MaterialType.METAL)),
    (15, (MaterialType.STONE, MaterialType.METAL, MaterialType.CRYSTAL)),
    (20, (MaterialType.METAL, MaterialType.CRYSTAL, MaterialType.XENDIUM)),
    (25, (MaterialType.CRYSTAL, MaterialType.XENDIUM, MaterialType.PERMAFROST_ORE)),
    (30, (MaterialType.XENDIUM, MaterialType.PERMAFROST_ORE, MaterialType.VOID)),
    (99, (MaterialType.PERMAFROST_ORE, MaterialType.VOID, MaterialType.ENTROPY)),
]


def materials_for_level(level: int) -> tuple[MaterialType, ...]:
    """The materials an upgrade AT `level` consumes -- see the bands
    above. Level-driven rather than rarity-driven so a freshly-dropped
    Divine item still starts on wood and stone."""
    for ceiling, materials in _MATERIAL_BANDS:
        if level <= ceiling:
            return materials
    return _MATERIAL_BANDS[-1][1]


def material_qty_for_level(level: int) -> int:
    """Total material units one level-up at `level` costs, before it's
    split across that band's types."""
    return LEVEL_UP_MATERIAL_BASE + max(0, (level - 1)) // LEVELS_PER_MATERIAL_STEP


def _gold_for_level(level: int) -> int:
    """Gold for one level-up at `level`. Linear base with a gentle
    super-linear term, so early upgrades stay cheap and the last stretch
    of a Divine item actually costs something."""
    return int(round(LEVEL_UP_GOLD_PER_LEVEL * level * (1 + level / GOLD_SUPERLINEAR_DIVISOR)))


def materials_for_rarity(rarity: Rarity) -> tuple[MaterialType, ...]:
    """Kept for callers that only know an item's rarity (display code).
    Reports the band the item's LEVEL CAP falls in -- i.e. the materials
    that rarity will eventually demand."""
    from bot.game.loot.rarity_config import upgrade_level_cap
    return materials_for_level(upgrade_level_cap(rarity))


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
def get_level_up_cost(item, levels: int = 1, db=None, player=None) -> dict:
    """`db`/`player` are optional so display code that only has an item
    still works; when given, the Research Lab's upgrade_cost_percent perk
    is applied."""
    cap = upgrade_level_cap(item.rarity)
    max_levels = max(0, min(levels, cap - item.item_level))
    if max_levels <= 0:
        return {"levels": 0, "gold": 0, "materials": {}, "at_cap": True}

    # Costs are computed PER LEVEL and summed, so a multi-level upgrade
    # charges exactly what doing them one at a time would -- and so a
    # batch that crosses a material band boundary correctly draws on both
    # bands rather than picking one for the whole run.
    gold = 0
    materials: dict[str, int] = {}
    for i in range(max_levels):
        level = item.item_level + i
        gold += _gold_for_level(level)

        band = materials_for_level(level)
        qty = material_qty_for_level(level)
        # Spread across the band's materials as evenly as possible,
        # rotating which one absorbs the remainder by level so the same
        # material isn't always the one asked for most.
        base, extra = divmod(qty, len(band))
        for j, material in enumerate(band):
            amount = base + (1 if j < extra else 0)
            if amount:
                materials[material.value] = materials.get(material.value, 0) + amount

    if db is not None and player is not None:
        from bot.services import research_service
        discount = research_service.perk_value(db, player.id, "upgrade_cost_percent")
        if discount:
            factor = 1 - discount / 100
            gold = max(1, int(round(gold * factor)))
            materials = {k: max(1, int(round(v * factor))) for k, v in materials.items()}

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
