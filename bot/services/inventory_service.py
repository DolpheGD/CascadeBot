"""
Equip/unequip logic and inventory listing. Slot capacity rule: exactly one
equipped item per slot, except RING which allows two -- matching the two
ring slots from the original design (Weapon/Helmet/Chest/Leggings/Boots/
Ring/Ring/Necklace/Artifact/Artifact).
"""

from __future__ import annotations

from bot.database.models.enums import EquipmentSlot
from bot.database.models.equipment_model import InventoryItem

RING_SLOT_CAPACITY = 2


def list_inventory(db, player_id: int) -> list[InventoryItem]:
    return (
        db.query(InventoryItem)
        .filter_by(player_id=player_id)
        .order_by(InventoryItem.slot, InventoryItem.rarity.desc())
        .all()
    )


def list_equipped(db, player_id: int) -> list[InventoryItem]:
    return db.query(InventoryItem).filter_by(player_id=player_id, is_equipped=True).all()


def get_item(db, item_id: int, player_id: int) -> InventoryItem | None:
    """Fetches an item only if it belongs to `player_id` -- callers should
    never trust an item_id without this ownership check."""
    item = db.get(InventoryItem, item_id)
    if item is None or item.player_id != player_id:
        return None
    return item


def equip_item(db, player, item: InventoryItem) -> tuple[bool, str]:
    if item.is_equipped:
        return False, f"{item.display_name} is already equipped."

    equipped_in_slot = (
        db.query(InventoryItem)
        .filter_by(player_id=player.id, slot=item.slot, is_equipped=True)
        .all()
    )
    capacity = RING_SLOT_CAPACITY if item.slot == EquipmentSlot.RING else 1

    if len(equipped_in_slot) >= capacity:
        if capacity == 1:
            # Single-capacity slots auto-swap: unequip the current occupant.
            equipped_in_slot[0].is_equipped = False
        else:
            names = ", ".join(e.display_name for e in equipped_in_slot)
            return False, f"Both ring slots are full ({names}). Unequip one first."

    item.is_equipped = True
    db.commit()
    return True, f"Equipped {item.display_name}."


def unequip_item(db, player, item: InventoryItem) -> tuple[bool, str]:
    if not item.is_equipped:
        return False, f"{item.display_name} isn't equipped."

    item.is_equipped = False
    db.commit()
    return True, f"Unequipped {item.display_name}."
