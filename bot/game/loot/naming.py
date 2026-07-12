"""
Turns a generated item into a display name: exactly ONE prefix, then the
item's base name -- e.g. "Iron Sword", "Voidwalker Blade", "Legendary
Dagger". No suffixes, no stacked modifiers. Purely cosmetic -- naming
never affects stats.

The prefix comes from the item's SET if it belongs to one (set_prefix on
the ItemTemplate -- see bot/database/models/equipment_model.py and the set
catalog in bot/game/loot/item_seed_data.py), since a set's identity is
exactly the kind of thing a simple, consistent prefix should communicate.
Non-set items fall back to a plain rarity-flavored generic prefix.
"""

from __future__ import annotations

import random

from bot.database.models.enums import Rarity

# Fallback prefix for items that don't belong to a set, by rarity.
GENERIC_PREFIX_BY_RARITY: dict[Rarity, list[str]] = {
    Rarity.COMMON: ["Worn", "Plain"],
    Rarity.UNCOMMON: ["Sturdy", "Reliable"],
    Rarity.RARE: ["Fine", "Notable"],
    Rarity.EPIC: ["Heroic", "Exalted"],
    Rarity.LEGENDARY: ["Legendary", "Storied"],
    Rarity.MYTHIC: ["Mythic", "Transcendent"],
    Rarity.DIVINE: ["Divine", "Celestial"],
}


def generate_display_name(
    base_name: str,
    rarity: Rarity,
    substats: list[dict],
    active_ability: dict | None,
    passive_ability: dict | None,
    rng: random.Random,
    set_prefix: str = "",
) -> str:
    """`substats`/`active_ability`/`passive_ability` are no longer used to
    pick the prefix (kept as parameters so callers don't all need updating)
    -- the prefix is purely set_prefix-or-rarity now, not mechanics-driven,
    per the naming simplification."""
    if set_prefix:
        return f"{set_prefix} {base_name}"

    # Common items with no set stay completely plain -- not every drop
    # should sound special.
    if rarity == Rarity.COMMON:
        return base_name

    prefix = rng.choice(GENERIC_PREFIX_BY_RARITY[rarity])
    return f"{prefix} {base_name}"
