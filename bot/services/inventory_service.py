"""
Equip/unequip logic and inventory listing.

Combat Overhaul: every slot (WEAPON, ARTIFACT, ARMOR, ACCESSORY) holds
exactly one item now -- the old two-per-slot primary/secondary pairing
(InventoryItem.equip_slot_index) is gone. Equipment also now attaches to a
specific PlayerCharacter (InventoryItem.character_id) rather than the
player directly, since each of your up-to-4 squad members has their own
loadout. Unequipped items still live in one shared, player-wide inventory
pool -- only equipping assigns an item to a character.
"""

from __future__ import annotations

from dataclasses import dataclass

from bot.database.models.enums import EquipmentSlot, Rarity
from bot.database.models.equipment_model import InventoryItem
from bot.services.currency_service import add_currency

# Flat sell value per rarity at item_level 1, scaling up modestly with
# level -- selling is meant to clear out clutter for a bit of gold, not
# compete with actually using/upgrading gear.
SELL_VALUE_BY_RARITY: dict[Rarity, int] = {
    Rarity.COMMON: 15,
    Rarity.UNCOMMON: 30,
    Rarity.RARE: 60,
    Rarity.EPIC: 120,
    Rarity.LEGENDARY: 250,
    Rarity.MYTHIC: 500,
    Rarity.DIVINE: 1000,
}
SELL_VALUE_PER_LEVEL = 0.08  # +8% of base value per item_level above 1


@dataclass
class InventoryEntry:
    """A single row in the unified inventory browser -- either a rolled
    InventoryItem or a stack of lootboxes of one tier. `entry_id` is a
    stable string key ("item:<id>" / "box:<tier>") used for Prev/Next/Jump
    navigation so both kinds can be paged through as one list."""
    entry_id: str
    kind: str  # "item" | "lootbox"
    obj: object  # InventoryItem | PlayerLootbox
    sort_key: tuple


def list_inventory(db, player_id: int) -> list[InventoryItem]:
    return (
        db.query(InventoryItem)
        .filter_by(player_id=player_id)
        .order_by(InventoryItem.slot, InventoryItem.rarity.desc(), InventoryItem.id)
        .all()
    )


def list_equipped(db, character_id: int) -> list[InventoryItem]:
    return (
        db.query(InventoryItem)
        .filter_by(character_id=character_id, is_equipped=True)
        .order_by(InventoryItem.slot)
        .all()
    )


def get_equipped_by_slot(db, character_id: int) -> dict[EquipmentSlot, InventoryItem | None]:
    """One item (or None) per slot for the given character -- handy for a
    profile/loadout view that needs to show every slot, empty or not."""
    equipped = list_equipped(db, character_id)
    by_slot: dict[EquipmentSlot, InventoryItem | None] = {slot: None for slot in EquipmentSlot}
    for item in equipped:
        by_slot[item.slot] = item
    return by_slot


def get_item(db, item_id: int, player_id: int) -> InventoryItem | None:
    """Fetches an item only if it belongs to `player_id` -- callers should
    never trust an item_id without this ownership check."""
    item = db.get(InventoryItem, item_id)
    if item is None or item.player_id != player_id:
        return None
    return item


def get_neighbor_item_id(db, player_id: int, current_item_id: int, direction: str) -> int | None:
    """Returns the previous/next item id in the player's sorted inventory
    relative to `current_item_id`, or None at either end. Used to build
    persistent Prev/Next buttons whose target is baked into the custom_id
    rather than any per-message stored position."""
    ids = [item.id for item in list_inventory(db, player_id)]
    if current_item_id not in ids:
        return None

    idx = ids.index(current_item_id)
    if direction == "prev":
        return ids[idx - 1] if idx > 0 else None
    return ids[idx + 1] if idx < len(ids) - 1 else None


def equip_item(db, character, item: InventoryItem) -> tuple[bool, str]:
    """Equips `item` onto `character` (a PlayerCharacter). Every slot holds
    one item, so equipping into an already-occupied slot auto-swaps the
    previous occupant back to the shared, unequipped pool."""
    if item.player_id != character.player_id:
        return False, "You don't own that item."
    if item.is_equipped and item.character_id == character.id:
        return False, f"{item.display_name} is already equipped on {character.template.name}."

    current = (
        db.query(InventoryItem)
        .filter_by(character_id=character.id, slot=item.slot, is_equipped=True)
        .first()
    )
    if current is not None:
        current.is_equipped = False
        current.character_id = None

    item.character_id = character.id
    item.is_equipped = True
    db.commit()

    swap_note = f" (swapped out {current.display_name})" if current is not None else ""
    return True, f"Equipped {item.display_name} on {character.template.name}{swap_note}."


def unequip_item(db, item: InventoryItem) -> tuple[bool, str]:
    if not item.is_equipped:
        return False, f"{item.display_name} isn't equipped."

    item.is_equipped = False
    item.character_id = None
    db.commit()
    return True, f"Unequipped {item.display_name}."


def get_sell_value(item: InventoryItem) -> int:
    base = SELL_VALUE_BY_RARITY[item.rarity]
    return round(base * (1 + SELL_VALUE_PER_LEVEL * (item.item_level - 1)))


def sell_item(db, player, item: InventoryItem) -> tuple[bool, str]:
    if item.player_id != player.id:
        return False, "You don't own that item."
    if item.is_equipped:
        return False, f"{item.display_name} is equipped -- unequip it before selling."

    value = get_sell_value(item)
    add_currency(db, player, "gold", value)
    name = item.display_name
    db.delete(item)
    db.commit()
    return True, f"Sold {name} for {value} gold."


# ----------------------------------------------------------------------
# Unified browsing: items + lootboxes as one navigable, paginatable list.
# Lootboxes sort after items so gear (which you equip/upgrade more often)
# always comes first; within each group, items keep their normal slot/
# rarity ordering and lootboxes sort by tier.
# ----------------------------------------------------------------------

_LOOTBOX_TIER_ORDER = {"common": 0, "uncommon": 1, "rare": 2, "epic": 3, "legendary": 4, "mythic": 5}


def list_combined_entries(db, player_id: int) -> list["InventoryEntry"]:
    from bot.services import lootbox_service  # local import: avoids a service-to-service cycle

    entries: list[InventoryEntry] = []
    for item in list_inventory(db, player_id):
        entries.append(InventoryEntry(
            entry_id=f"item:{item.id}",
            kind="item",
            obj=item,
            sort_key=(0, item.slot.value, -item.rarity.sort_order, item.id),
        ))
    for owned in lootbox_service.list_player_lootboxes(db, player_id):
        tier = owned.template.tier
        entries.append(InventoryEntry(
            entry_id=f"box:{tier}",
            kind="lootbox",
            obj=owned,
            sort_key=(1, _LOOTBOX_TIER_ORDER.get(tier, 99)),
        ))

    entries.sort(key=lambda e: e.sort_key)
    return entries


def get_combined_entry(db, player_id: int, entry_id: str) -> "InventoryEntry | None":
    for entry in list_combined_entries(db, player_id):
        if entry.entry_id == entry_id:
            return entry
    return None


def get_neighbor_entry_id(db, player_id: int, current_entry_id: str, direction: str) -> str | None:
    ids = [e.entry_id for e in list_combined_entries(db, player_id)]
    if current_entry_id not in ids:
        return None

    idx = ids.index(current_entry_id)
    if direction == "prev":
        return ids[idx - 1] if idx > 0 else None
    return ids[idx + 1] if idx < len(ids) - 1 else None


def entry_index_and_total(db, player_id: int, entry_id: str) -> tuple[int, int]:
    ids = [e.entry_id for e in list_combined_entries(db, player_id)]
    if entry_id not in ids:
        return 0, len(ids)
    return ids.index(entry_id), len(ids)
