"""
Forge: craft, salvage, reforge and transfer.

Every operation routes its material costs through
forge_config.split_materials so no single resource ever gates the Forge,
and through research_service's `forge_cost_percent` perk so the Research
Lab's Salvage branch actually makes forging cheaper -- the two buildings
are meant to feed each other rather than sit in separate menus.

Crafting reuses LootGenerator rather than building items by hand, so a
forged item is indistinguishable from a dropped one in every respect
except that the player chose its slot and rarity. That's deliberate: the
Forge removes the two most frustrating rolls, not the item system.
"""

from __future__ import annotations

import random

from bot.database.models.enums import EquipmentSlot, ItemType, Rarity
from bot.database.models.base_building_model import PlayerForge
from bot.database.models.equipment_model import InventoryItem, ItemTemplate
from bot.game.economy.forge_config import (
    salvage_material_base,
    CRAFT_COST,
    REFORGE_COST,
    SALVAGE_RETURN_PERCENT,
    TRANSFER_COST,
    forge_upgrade_cost,
    is_max_forge_level,
    max_craft_rarity,
    operation_unlocked,
    split_materials,
)
from bot.services import research_service
from bot.services.currency_service import add_currency, format_currency, spend_currency


class ForgeError(Exception):
    """Any reason a forge action can't proceed, phrased for the player."""


def get_or_create_forge(db, player) -> PlayerForge:
    forge = db.get(PlayerForge, player.id)
    if forge is None:
        forge = PlayerForge(player_id=player.id, level=1)
        db.add(forge)
        db.commit()
        db.refresh(forge)
    return forge


def _discounted(db, player, amount: int) -> int:
    """Apply the Research Lab's forge_cost_percent perk."""
    percent = research_service.perk_value(db, player.id, "forge_cost_percent")
    return max(1, int(round(amount * (1 - percent / 100))))


def craft_cost(db, player, rarity: Rarity) -> dict:
    # A rarity the Forge doesn't craft raises a player-facing error
    # rather than a KeyError. This is reachable in practice: craft
    # buttons carry their rarity in the custom_id, so a message left
    # open from before the ladder was rebased at Rare still has a
    # `...:common` button on it, and pressing it used to crash the
    # interaction instead of explaining anything.
    base = CRAFT_COST.get(rarity)
    if base is None:
        floor = min(CRAFT_COST, key=lambda r: r.sort_order)
        raise ForgeError(
            f"The Forge doesn't make {rarity.value.title()} gear -- it starts at "
            f"**{floor.value.title()}**. Anything below that drops freely in the field."
        )
    gold = _discounted(db, player, base["gold"])
    materials = split_materials(_discounted(db, player, base["materials"]), rarity)
    return {"gold": gold, "materials": materials}


def _charge(db, player, gold: int, materials: dict[str, int], label: str) -> None:
    """Spend gold + materials atomically, refunding anything already
    taken if a later charge fails. A partial charge would quietly eat
    resources, which is the worst possible failure for a crafting UI."""
    spent: list[tuple[str, int]] = []
    for currency, amount in [("gold", gold), *materials.items()]:
        if amount <= 0:
            continue
        if not spend_currency(db, player, currency, amount):
            for c, a in spent:
                add_currency(db, player, c, a)
            db.commit()
            raise ForgeError(f"Not enough {format_currency(currency, amount)} to {label}.")
        spent.append((currency, amount))


# ----------------------------------------------------------------------
# Craft
# ----------------------------------------------------------------------

def craft_item(db, player, slot: EquipmentSlot, rarity: Rarity,
               rng: random.Random | None = None) -> InventoryItem:
    """Forge a new item in `slot` at exactly `rarity`. The TEMPLATE and
    substats are still rolled -- see the module docstring for why the
    Forge stops short of naming the exact item."""
    rng = rng or random.Random()
    forge = get_or_create_forge(db, player)

    if not operation_unlocked("craft", forge.level):
        raise ForgeError("Your Forge can't craft yet.")
    if rarity not in CRAFT_COST:
        floor = min(CRAFT_COST, key=lambda r: r.sort_order)
        raise ForgeError(
            f"The Forge doesn't make {rarity.value.title()} gear -- it starts at "
            f"**{floor.value.title()}**. Anything below that drops freely in the field."
        )
    ceiling = max_craft_rarity(forge.level)
    if rarity.sort_order > ceiling.sort_order:
        raise ForgeError(
            f"Your Forge can only craft up to **{ceiling.value.title()}**. "
            "Upgrade it to work with rarer materials."
        )

    # Templates that can legitimately roll at this rarity and slot --
    # respecting each template's own min/max so the Forge can't produce
    # an item the loot table never would.
    candidates = [
        t for t in db.query(ItemTemplate).filter_by(slot=slot).all()
        if t.min_rarity.sort_order <= rarity.sort_order <= t.max_rarity.sort_order
    ]
    if not candidates:
        raise ForgeError(f"Nothing in that slot can be forged at {rarity.value.title()} yet.")

    cost = craft_cost(db, player, rarity)
    _charge(db, player, cost["gold"], cost["materials"], "forge that")

    from bot.game.loot.generator import LootGenerator

    template = rng.choice(candidates)
    item = LootGenerator(rng).generate_item(
        template, player_id=player.id, item_level=1, rarity_override=rarity,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


# ----------------------------------------------------------------------
# Salvage
# ----------------------------------------------------------------------

def salvage_item(db, player, item: InventoryItem) -> dict[str, int]:
    """Break an item down for materials of its own rarity tier."""
    forge = get_or_create_forge(db, player)
    if not operation_unlocked("salvage", forge.level):
        raise ForgeError("Your Forge can't salvage yet.")
    if item.is_equipped:
        raise ForgeError(f"{item.display_name} is equipped -- unequip it first.")

    base = salvage_material_base(item.rarity)
    returned = split_materials(
        max(1, int(round(base * SALVAGE_RETURN_PERCENT / 100))), item.rarity
    )
    for currency, amount in returned.items():
        add_currency(db, player, currency, amount)
    db.delete(item)
    db.commit()
    return returned


# ----------------------------------------------------------------------
# Reforge -- re-roll the ability, keep the stats
# ----------------------------------------------------------------------

def reforge_item(db, player, item: InventoryItem, rng: random.Random | None = None) -> InventoryItem:
    """Re-roll which ability an item carries without touching its main
    stat or substats. The counterpart to /inventory's reroll, which does
    the opposite -- between them a player can fix either half of an item
    they like."""
    rng = rng or random.Random()
    forge = get_or_create_forge(db, player)
    if not operation_unlocked("reforge", forge.level):
        raise ForgeError("Reforging unlocks at Forge level 2.")
    if not (item.active_ability or item.passive_ability):
        raise ForgeError(f"{item.display_name} has no ability to reforge.")

    gold = _discounted(db, player, REFORGE_COST["gold"] * (item.rarity.sort_order + 1))
    materials = split_materials(
        _discounted(db, player, REFORGE_COST["materials"] * (item.rarity.sort_order + 1)),
        item.rarity,
    )
    _charge(db, player, gold, materials, "reforge that")

    from bot.game.loot.generator import LootGenerator

    active, passive = LootGenerator(rng).roll_ability(item.item_type, item.rarity, force=True)
    item.active_ability = active
    item.passive_ability = passive
    db.commit()
    db.refresh(item)
    return item


# ----------------------------------------------------------------------
# Transfer -- move an ability between items
# ----------------------------------------------------------------------

def transfer_ability(db, player, source: InventoryItem, target: InventoryItem) -> InventoryItem:
    """Move `source`'s ability onto `target`, destroying `source`.

    The Forge's endgame operation: it's how a player finally puts the
    ability they want onto the stat-line they want. Restricted to items
    of the same TYPE, because a weapon's active skill and an armour
    passive are not interchangeable -- the combat engine reads them from
    different slots entirely (see factory._gear_abilities)."""
    forge = get_or_create_forge(db, player)
    if not operation_unlocked("transfer", forge.level):
        raise ForgeError("Ability transfer unlocks at Forge level 4.")
    if source.id == target.id:
        raise ForgeError("Pick two different items.")
    if source.item_type != target.item_type:
        raise ForgeError(
            "Abilities can only move between items of the same type -- "
            "a weapon skill can't be fitted to armour."
        )
    if not (source.active_ability or source.passive_ability):
        raise ForgeError(f"{source.display_name} has no ability to transfer.")
    if source.is_equipped or target.is_equipped:
        raise ForgeError("Unequip both items first.")

    rarity = max(source.rarity, target.rarity, key=lambda r: r.sort_order)
    gold = _discounted(db, player, TRANSFER_COST["gold"] * (rarity.sort_order + 1))
    materials = split_materials(
        _discounted(db, player, TRANSFER_COST["materials"] * (rarity.sort_order + 1)), rarity
    )
    _charge(db, player, gold, materials, "transfer that ability")

    target.active_ability = source.active_ability
    target.passive_ability = source.passive_ability
    db.delete(source)
    db.commit()
    db.refresh(target)
    return target


# ----------------------------------------------------------------------
# Upgrade
# ----------------------------------------------------------------------

def upgrade_forge(db, player) -> tuple[bool, str]:
    forge = get_or_create_forge(db, player)
    if is_max_forge_level(forge.level):
        return False, "Your Forge is already at its maximum level."

    cost = forge_upgrade_cost(forge.level)
    try:
        _charge(db, player, cost.get("gold", 0),
                {k: v for k, v in cost.items() if k != "gold"}, "upgrade the Forge")
    except ForgeError as exc:
        return False, str(exc)

    forge.level += 1
    db.commit()
    return True, f"Forge upgraded to level {forge.level}!"
