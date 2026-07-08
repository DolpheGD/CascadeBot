"""
Equip/unequip logic and inventory listing. Slot capacity rules (see
bot.database.models.enums.SLOT_CAPACITY): WEAPON and ARTIFACT each allow
two equipped items (primary/secondary, tracked via
InventoryItem.equip_slot_index); every other slot allows exactly one.
"""

from __future__ import annotations

from dataclasses import dataclass

from bot.database.models.enums import SLOT_CAPACITY, SLOT_DISPLAY_NAME, EquipmentSlot, slot_index_label
from bot.database.models.equipment_model import InventoryItem


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


def list_equipped(db, player_id: int) -> list[InventoryItem]:
    return (
        db.query(InventoryItem)
        .filter_by(player_id=player_id, is_equipped=True)
        .order_by(InventoryItem.slot, InventoryItem.equip_slot_index)
        .all()
    )


def get_equipped_by_slot(db, player_id: int) -> dict[EquipmentSlot, list[InventoryItem]]:
    """Every equipped item grouped by slot (list sorted by equip_slot_index
    so index 0 is always first) -- handy for a profile view that needs to
    show every slot, empty or not."""
    equipped = list_equipped(db, player_id)
    by_slot: dict[EquipmentSlot, list[InventoryItem]] = {slot: [] for slot in EquipmentSlot}
    for item in equipped:
        by_slot[item.slot].append(item)
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


def equip_item(db, player, item: InventoryItem) -> tuple[bool, str]:
    if item.is_equipped:
        return False, f"{item.display_name} is already equipped."

    capacity = SLOT_CAPACITY[item.slot]
    equipped_in_slot = (
        db.query(InventoryItem)
        .filter_by(player_id=player.id, slot=item.slot, is_equipped=True)
        .order_by(InventoryItem.equip_slot_index)
        .all()
    )

    if len(equipped_in_slot) >= capacity:
        if capacity == 1:
            # Single-capacity slots auto-swap: unequip the current occupant.
            equipped_in_slot[0].is_equipped = False
            item.equip_slot_index = 0
        else:
            names = ", ".join(
                f"{slot_index_label(item.slot, e.equip_slot_index)}: {e.display_name}"
                for e in equipped_in_slot
            )
            return False, (
                f"Both {SLOT_DISPLAY_NAME[item.slot]} slots are full ({names}). "
                "Unequip one first."
            )
    elif capacity > 1:
        used_indices = {e.equip_slot_index for e in equipped_in_slot}
        item.equip_slot_index = 0 if 0 not in used_indices else 1
    else:
        item.equip_slot_index = 0

    item.is_equipped = True
    db.commit()

    label = (
        f" ({slot_index_label(item.slot, item.equip_slot_index)})"
        if capacity > 1 else ""
    )
    return True, f"Equipped {item.display_name}{label}."


def unequip_item(db, player, item: InventoryItem) -> tuple[bool, str]:
    if not item.is_equipped:
        return False, f"{item.display_name} isn't equipped."

    item.is_equipped = False
    item.equip_slot_index = 0
    db.commit()
    return True, f"Unequipped {item.display_name}."


# ----------------------------------------------------------------------
# Unified browsing: items + lootboxes as one navigable, paginatable list.
# Lootboxes sort after items so gear (which you equip/upgrade more often)
# always comes first; within each group, items keep their normal slot/
# rarity ordering and lootboxes sort by tier.
# ----------------------------------------------------------------------

_LOOTBOX_TIER_ORDER = {"common": 0, "rare": 1, "epic": 2, "legendary": 3}


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
