"""
Assert that a dropped item and an upgraded item are priced identically.

    python -m tools.check_gear_curve

THE BUG THIS EXISTS FOR
-----------------------
An item's main stat was computed in two places:

  * LootGenerator.roll_main_stat, when the item drops
  * upgrades.level_up, when the player pays to improve it

They were different formulas. The generator applied the level curve; the
upgrade path used a hardcoded +1.0 per level and no curve at all. On a
base-10 Rare attack item that meant 5.31 on drop and 11.80 after one
upgrade -- a 2.44x jump for one level, followed by a crawl.

Nothing failed. The item worked, the number went up, and the shape of
progression was wrong in a way only a player grinding levels would ever
notice. It also survived one whole attempt at fixing "the gear curve",
because that pass only touched the generator -- which is not the code
path an upgraded item goes through.

So this check walks both paths over every rarity and every level and
asserts they agree exactly, then asserts the resulting curve is actually
what the config claims: linear, low at the start, high at the end, with
no step anywhere.
"""

from __future__ import annotations

import sys

# The largest per-level jump we'll accept as "linear", as a multiple of
# the average per-level gain. A true straight line is 1.0; anything at or
# under this is indistinguishable in play.
MAX_STEP_RATIO = 1.05


def main() -> int:
    from bot.database.models.enums import Rarity
    from bot.game.loot.rarity_config import RARITY_STAT_MULTIPLIER, upgrade_level_cap
    from bot.game.loot.stat_pools import (
        MAIN_STAT_CURVE_EXPONENT, MAIN_STAT_GROWTH_PER_LEVEL, main_stat_for,
    )

    failures: list[str] = []
    checked = 0

    # ---- 1. the two code paths agree ---------------------------------
    #
    # level_up() is exercised through its real signature via a stand-in
    # item, so this compares what the GENERATOR would produce against
    # what an UPGRADE actually writes -- not two calls to the same
    # helper, which would prove nothing.
    from bot.game.loot import upgrades

    class _Template:
        def __init__(self, base, stat):
            self.base_main_stat_value = base
            self.main_stat = stat

    class _Item:
        def __init__(self, template, rarity, level):
            self.template = template
            self.rarity = rarity
            self.item_level = level
            self.main_stat_value = 0.0
            self.substats = []

    for stat in MAIN_STAT_GROWTH_PER_LEVEL:
        template = _Template(10.0, stat)
        for rarity in Rarity:
            multiplier = RARITY_STAT_MULTIPLIER[rarity]
            for level in range(1, upgrade_level_cap(rarity)):
                checked += 1
                item = _Item(template, rarity, level)
                upgrades.level_up(item, 1)
                expected = main_stat_for(10.0, stat, level + 1, multiplier)
                if abs(item.main_stat_value - expected) > 0.01:
                    failures.append(
                        f"{rarity.value} {stat} level {level}->{level + 1}: "
                        f"upgrading gives {item.main_stat_value}, but a freshly "
                        f"dropped item at that level would be {expected} -- the "
                        f"drop and upgrade paths have drifted apart again"
                    )
                    break

    # ---- 2. the curve is linear, as the config claims ----------------
    if abs(MAIN_STAT_CURVE_EXPONENT - 1.0) > 1e-9:
        failures.append(
            f"MAIN_STAT_CURVE_EXPONENT is {MAIN_STAT_CURVE_EXPONENT}, not 1.0 -- "
            f"the curve is documented as linear"
        )

    # ---- 3. no step anywhere, and it genuinely climbs ----------------
    for rarity in (Rarity.RARE, Rarity.LEGENDARY, Rarity.DIVINE):
        cap = upgrade_level_cap(rarity)
        multiplier = RARITY_STAT_MULTIPLIER[rarity]
        values = [main_stat_for(10.0, "attack", level, multiplier)
                  for level in range(1, cap + 1)]
        gains = [values[i + 1] - values[i] for i in range(len(values) - 1)]
        average = sum(gains) / len(gains)
        worst = max(gains)
        if worst > average * MAX_STEP_RATIO:
            failures.append(
                f"{rarity.value}: biggest single-level gain is {worst:.2f} against "
                f"an average of {average:.2f} -- that is a step, not a line"
            )
        if values[-1] <= values[0]:
            failures.append(f"{rarity.value}: levelling does not increase the stat")

    from bot.game.loot.rarity_config import RARITY_STAT_MULTIPLIER as RM
    sample = [(r, main_stat_for(10.0, "attack", 1, RM[r]),
               main_stat_for(10.0, "attack", upgrade_level_cap(r), RM[r]))
              for r in (Rarity.COMMON, Rarity.RARE, Rarity.LEGENDARY, Rarity.DIVINE)]

    print(f"paths    : {checked} (rarity, stat, level) upgrades compared "
          f"against a fresh drop")
    print(f"curve    : exponent {MAIN_STAT_CURVE_EXPONENT:g} (linear), "
          f"no step over {MAX_STEP_RATIO:g}x the average gain")
    print("shape    : base-10 attack item, level 1 -> cap")
    for rarity, low, high in sample:
        print(f"           {rarity.value:<10} {low:>6.2f} -> {high:>7.2f}  "
              f"({high / low:.1f}x)")
    print()
    if failures:
        for line in dict.fromkeys(failures):
            print(f"  FAIL  {line}")
        return 1
    print("OK -- dropping and upgrading agree, and the curve is a straight line.")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, ".")
    sys.exit(main())
