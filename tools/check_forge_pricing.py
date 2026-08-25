"""
The Forge has to be worth opening.

    python -m tools.check_forge_pricing

A crafting station competes with doing nothing. Gear already drops for
free, so the Forge only earns its place by letting a player TARGET a slot
and rarity -- and the moment that targeting costs more than it is worth,
the correct play is to ignore the building entirely. That failure is
completely silent: nothing errors, the UI works, the buttons all
function, and the feature is simply dead.

It had happened. The measurement that shows it is craft cost against the
gold needed to take that same item to MAX LEVEL:

    rarity      craft gold   gold to max   ratio      (before)
    rare             2,500         3,745   0.67x
    epic             7,000         7,410   0.94x
    legendary       18,000        12,700   1.42x
    mythic          45,000        19,865   2.27x
    divine         110,000        29,155   3.77x

Crafting a Divine cost nearly four times what it costs to fully upgrade
one. Acquisition should be the cheap half of owning an item; that ladder
inverted the relationship, and inverted hardest at the top, where
targeting is the only reason to craft at all.

The cause was two curves with different shapes: craft gold multiplied by
~2.5x per tier while everything it competes with rose by about 1.5x.
Curves like that are fine near the bottom and absurd at the top, which is
exactly how this survived -- the early game felt fine.

WHAT IS ASSERTED

  * craft cost stays within a bounded multiple of the item's own
    lifetime upgrade gold, at EVERY rarity -- this is the "is it worth
    it" test, and the bound is what stops the curves diverging again
  * reforge < transfer < craft, at every rarity. Transfer also destroys
    the donor item, a cost in no table, so it must sit below craft.
    A previous pass fixed this at Divine only and left it inverted at
    four rarities out of five while claiming it held everywhere; the
    prices are now derived from the craft ladder so the ordering cannot
    come apart.
  * salvaging never returns more than it costs to make -- no material
    laundry
  * unlocking a forge level costs less than a few crafts at the rarity
    it unlocks. A gate priced above the thing it gates is a gate nobody
    opens.
"""

from __future__ import annotations

import sys

# Craft gold as a multiple of the gold to take that item to max level.
# Below the floor and crafting is free money; above the ceiling and it is
# cheaper to ignore the Forge. 1.5 leaves room for rarity to cost more
# without the top tier becoming ornamental.
MIN_CRAFT_RATIO = 0.4
MAX_CRAFT_RATIO = 1.5

# A forge upgrade may cost at most this many crafts at the rarity it
# unlocks.
MAX_UPGRADE_AS_CRAFTS = 3.0


def main() -> int:
    sys.path.insert(0, ".")
    from bot.database.models.enums import Rarity
    from bot.game.economy.forge_config import (
        CRAFT_COST,
        FORGE_MAX_RARITY,
        FORGE_UPGRADE_COST,
        SALVAGE_RETURN_PERCENT,
        reforge_cost,
        salvage_material_base,
        transfer_cost,
    )
    from bot.game.loot.rarity_config import upgrade_level_cap
    from bot.services import item_upgrade_service

    gold_for_level = getattr(item_upgrade_service, "_gold_for_level")
    failures: list[str] = []

    def gold_to_max(rarity: Rarity) -> int:
        return sum(gold_for_level(level)
                   for level in range(1, upgrade_level_cap(rarity)))

    # ---- 1. is a craft worth it -------------------------------------
    for rarity, cost in CRAFT_COST.items():
        target = gold_to_max(rarity)
        if not target:
            continue
        ratio = cost["gold"] / target
        if ratio > MAX_CRAFT_RATIO:
            failures.append(
                f"{rarity.value}: crafting costs {cost['gold']:,} gold but taking "
                f"that item to max costs {target:,} ({ratio:.2f}x) -- above "
                f"{MAX_CRAFT_RATIO}x nobody crafts, they wait for a drop")
        if ratio < MIN_CRAFT_RATIO:
            failures.append(
                f"{rarity.value}: crafting costs {cost['gold']:,} gold against "
                f"{target:,} to max ({ratio:.2f}x) -- that is cheap enough that "
                f"crafting replaces the loot table")

    # ---- 2. reforge < transfer < craft ------------------------------
    for rarity in Rarity:
        reforge = reforge_cost(rarity)
        transfer = transfer_cost(rarity)
        for key in ("gold", "materials"):
            if reforge[key] >= transfer[key]:
                failures.append(
                    f"{rarity.value}: reforge {key} ({reforge[key]:,}) is not below "
                    f"transfer ({transfer[key]:,}) -- re-rolling one ability should "
                    f"cost less than moving one AND destroying the donor")
            craft = CRAFT_COST.get(rarity)
            if craft and transfer[key] >= craft[key]:
                failures.append(
                    f"{rarity.value}: transfer {key} ({transfer[key]:,}) is not below "
                    f"a whole craft ({craft[key]:,}) -- transfer also consumes the "
                    f"donor item, so it must be the cheaper of the two")

    # ---- 3. salvage cannot launder ----------------------------------
    for rarity in Rarity:
        base = salvage_material_base(rarity)
        returned = max(1, round(base * SALVAGE_RETURN_PERCENT / 100))
        craft = CRAFT_COST.get(rarity)
        if craft and returned >= craft["materials"]:
            failures.append(
                f"{rarity.value}: salvage returns {returned} materials and a craft "
                f"costs {craft['materials']} -- craft, salvage, repeat is free "
                f"materials")

    # ---- 4. the gate costs less than what it gates -------------------
    for level, cost in FORGE_UPGRADE_COST.items():
        unlocked = FORGE_MAX_RARITY.get(level + 1)
        craft = CRAFT_COST.get(unlocked) if unlocked else None
        if not craft:
            continue
        crafts = cost.get("gold", 0) / craft["gold"]
        if crafts > MAX_UPGRADE_AS_CRAFTS:
            failures.append(
                f"forge {level}->{level + 1} costs {cost.get('gold', 0):,} gold, "
                f"{crafts:.1f}x the {craft['gold']:,} it costs to craft the "
                f"{unlocked.value} it unlocks -- the gate costs more than the prize")

    print(f"{'rarity':<11}{'reforge':>15}{'transfer':>15}{'craft':>15}"
          f"{'to max':>10}{'ratio':>8}")
    for rarity in Rarity:
        reforge, transfer = reforge_cost(rarity), transfer_cost(rarity)
        craft = CRAFT_COST.get(rarity)
        target = gold_to_max(rarity)
        ratio = (craft["gold"] / target) if (craft and target) else 0.0
        print(f"{rarity.value:<11}"
              f"{reforge['gold']:>9,}/{reforge['materials']:<5}"
              f"{transfer['gold']:>9,}/{transfer['materials']:<5}"
              f"{(format(craft['gold'], ',') if craft else '--'):>9}/"
              f"{(craft['materials'] if craft else '--'):<5}"
              f"{target:>10,}{ratio:>7.2f}x")

    if failures:
        print()
        for failure in failures:
            print(f"  FAIL  {failure}")
        return 1
    print("\nOK -- crafting is worth it, and reforge < transfer < craft "
          "everywhere.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
