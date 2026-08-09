"""
Equip/unequip logic and inventory listing.

Combat Overhaul: WEAPON and ARTIFACT hold exactly one item per character;
ARMOR and ACCESSORY each hold up to two (see enums.SLOT_CAPACITY) -- so a
full loadout is 1 weapon + 1 artifact + 2 armor + 2 accessories. Equipment
attaches to a specific PlayerCharacter (InventoryItem.character_id) rather
than the player directly, since each of your up-to-4 squad members has
their own loadout. Unequipped items still live in one shared, player-wide
inventory pool -- only equipping assigns an item to a character.
"""

from __future__ import annotations

from dataclasses import dataclass

from bot.database.models.enums import SLOT_CAPACITY, EquipmentSlot, Rarity
from bot.database.models.equipment_model import InventoryItem
from bot.services.currency_service import add_currency, format_currency

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
    """A single row in the item inventory browser -- always a rolled
    InventoryItem now (lootboxes moved to the separate general inventory
    -- see list_combined_entries' docstring). `entry_id` is a stable
    string key ("item:<id>") used for Prev/Next/Jump navigation."""
    entry_id: str
    kind: str  # always "item" now
    obj: object  # InventoryItem
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


def get_equipped_by_slot(db, character_id: int) -> dict[EquipmentSlot, list[InventoryItem]]:
    """Every equipped item for the given character, grouped by slot --
    handy for a profile/loadout view that needs to show every slot, empty
    or not. WEAPON/ARTIFACT lists will have at most 1 entry; ARMOR/
    ACCESSORY lists will have at most SLOT_CAPACITY[slot] entries (2)."""
    equipped = list_equipped(db, character_id)
    by_slot: dict[EquipmentSlot, list[InventoryItem]] = {slot: [] for slot in EquipmentSlot}
    for item in equipped:
        by_slot[item.slot].append(item)
    for items in by_slot.values():
        items.sort(key=lambda it: it.id)
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
    """Equips `item` onto `character` (a PlayerCharacter). WEAPON/ARTIFACT
    hold 1 item; ARMOR/ACCESSORY hold up to SLOT_CAPACITY[slot] (2) --
    see bot.database.models.enums.SLOT_CAPACITY. If the slot is already
    full, the oldest-equipped item in that slot is auto-swapped back to
    the shared, unequipped pool to make room."""
    if item.player_id != character.player_id:
        return False, "You don't own that item."
    if item.is_equipped and item.character_id == character.id:
        return False, f"{item.display_name} is already equipped on {character.display_name}."

    current_in_slot = (
        db.query(InventoryItem)
        .filter_by(character_id=character.id, slot=item.slot, is_equipped=True)
        .order_by(InventoryItem.id)
        .all()
    )

    swapped_out = None
    capacity = SLOT_CAPACITY[item.slot]
    if len(current_in_slot) >= capacity:
        swapped_out = current_in_slot[0]
        swapped_out.is_equipped = False
        swapped_out.character_id = None

    item.character_id = character.id
    item.is_equipped = True
    db.commit()

    swap_note = f" (swapped out {swapped_out.display_name})" if swapped_out is not None else ""
    return True, f"Equipped {item.display_name} on {character.display_name}{swap_note}."


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
    return True, f"Sold {name} for {format_currency('gold', value)}."


def list_sellable_by_rarity(db, player_id: int, rarity: Rarity) -> list[InventoryItem]:
    """Every UNEQUIPPED item a player owns at exactly `rarity` -- the
    candidate set for mass-selling. Equipped items are never swept up in
    a mass sell, same as single-item sell_item -- unequip first if one of
    those needs to go too."""
    return (
        db.query(InventoryItem)
        .filter_by(player_id=player_id, rarity=rarity, is_equipped=False)
        .all()
    )


def preview_sell_by_rarity(db, player_id: int, rarity: Rarity) -> tuple[int, int]:
    """(item count, total gold) if every unequipped `rarity` item were
    sold right now -- used to show a confirmation before mass-selling
    actually happens, since it's not undoable."""
    items = list_sellable_by_rarity(db, player_id, rarity)
    return len(items), sum(get_sell_value(i) for i in items)


def sell_by_rarity(db, player, rarity: Rarity) -> tuple[bool, str, int, int]:
    """Sells every unequipped item of exactly `rarity` in one shot (the
    mass Sell by Rarity flow). Returns (ok, message, count_sold,
    gold_earned); ok is False (with a count/earned of 0) if there was
    nothing to sell."""
    items = list_sellable_by_rarity(db, player.id, rarity)
    if not items:
        return False, f"You don't have any unequipped {rarity.value.title()} items to sell.", 0, 0

    count = len(items)
    total_value = sum(get_sell_value(i) for i in items)
    for item in items:
        db.delete(item)
    add_currency(db, player, "gold", total_value)
    db.commit()

    plural = "s" if count != 1 else ""
    message = f"Sold {count} {rarity.value.title()} item{plural} for {format_currency('gold', total_value)}."
    return True, message, count, total_value


# ----------------------------------------------------------------------
# SORT MODES
#
# The inventory had exactly one order -- slot, then rarity -- which is a
# reasonable default and useless for every actual question a player has.
# "What's my worst item" and "what's my highest-attack weapon" and
# "what did I just pick up" are the three reasons anyone opens this
# screen, and none of them were answerable without scrolling the whole
# list.
#
# Each mode is a key function over an InventoryItem. Every one of them
# ends in `item.id` so the order is TOTAL -- ties broken consistently.
# That matters more than it looks: the detail view walks prev/next
# through this same list, so an unstable sort would let "next" loop or
# skip when two items compare equal.
# ----------------------------------------------------------------------

def _main_stat_value(item) -> float:
    return float(getattr(item, "main_stat_value", 0) or 0)


SORT_MODES: dict[str, dict] = {
    "slot": {
        "label": "Slot, then rarity",
        "description": "The default — everything of a kind together.",
        "emoji": "🎒",
        "key": lambda i: (i.slot.value, -i.rarity.sort_order, -i.item_level, i.id),
    },
    "rarity": {
        "label": "Rarity (best first)",
        "description": "Divine down to Common.",
        "emoji": "💠",
        "key": lambda i: (-i.rarity.sort_order, -i.item_level, i.slot.value, i.id),
    },
    "level": {
        "label": "Item level (highest first)",
        "description": "What you've actually invested in.",
        "emoji": "⬆️",
        "key": lambda i: (-i.item_level, -i.rarity.sort_order, i.id),
    },
    "main_stat": {
        "label": "Main stat (biggest first)",
        "description": "Raw numbers, regardless of slot.",
        "emoji": "📈",
        "key": lambda i: (-_main_stat_value(i), -i.rarity.sort_order, i.id),
    },
    "newest": {
        "label": "Newest first",
        "description": "What you just picked up.",
        "emoji": "🆕",
        "key": lambda i: (-i.id,),
    },
    "worst": {
        "label": "Worst first",
        "description": "For clearing out the junk.",
        "emoji": "🗑️",
        "key": lambda i: (i.rarity.sort_order, i.item_level, _main_stat_value(i), i.id),
    },
}

DEFAULT_SORT = "slot"


def sort_mode(name: str | None) -> str:
    """Falls back to the default rather than raising -- a stale custom_id
    from a message left open across a deploy should reorder the list, not
    kill the interaction."""
    return name if name in SORT_MODES else DEFAULT_SORT


def list_combined_entries(db, player_id: int, sort: str | None = None) -> list["InventoryEntry"]:
    """Despite the name (kept to avoid touching every call site), this is
    now ITEMS ONLY -- lootboxes moved to their own general-inventory view
    (/stash, see cogs/inventory.py's general_inventory command) since they
    can't be equipped/sold/leveled/rerolled the way items can, and mixing
    them into the same sellable-items browser was confusing. `kind` is
    always "item" now; kept on InventoryEntry rather than collapsing the
    type entirely in case a different non-item entry needs to slot in here
    again later."""
    key = SORT_MODES[sort_mode(sort)]["key"]
    entries: list[InventoryEntry] = []
    for item in list_inventory(db, player_id):
        entries.append(InventoryEntry(
            entry_id=f"item:{item.id}",
            kind="item",
            obj=item,
            sort_key=key(item),
        ))
    entries.sort(key=lambda e: e.sort_key)
    return entries


def get_combined_entry(db, player_id: int, entry_id: str,
                       sort: str | None = None) -> "InventoryEntry | None":
    for entry in list_combined_entries(db, player_id, sort):
        if entry.entry_id == entry_id:
            return entry
    return None


def get_neighbor_entry_id(db, player_id: int, current_entry_id: str, direction: str,
                          sort: str | None = None) -> str | None:
    # Same sort as the page it was opened from -- otherwise "next" walks
    # a different list than the one the player is looking at.
    ids = [e.entry_id for e in list_combined_entries(db, player_id, sort)]
    if current_entry_id not in ids:
        return None

    idx = ids.index(current_entry_id)
    if direction == "prev":
        return ids[idx - 1] if idx > 0 else None
    return ids[idx + 1] if idx < len(ids) - 1 else None


def entry_index_and_total(db, player_id: int, entry_id: str,
                          sort: str | None = None) -> tuple[int, int]:
    ids = [e.entry_id for e in list_combined_entries(db, player_id, sort)]
    if entry_id not in ids:
        return 0, len(ids)
    return ids.index(entry_id), len(ids)
