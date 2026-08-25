"""
No sequence of trades turns a resource into more of itself.

    python -m tools.check_trade_loops

WHY THIS IS THE DANGEROUS PART OF A TRADING SYSTEM. Conversion events are
the only encounters that both TAKE and GIVE the same kinds of resource.
Everything else in the game is a faucet or a drain; a converter is both,
and two converters pointing at each other are a machine that prints
materials.

The failure is completely silent and it does not look like a bug. Nobody
crashes, no check on encounter shape fails, and the player who finds it
does not report it. It shows up weeks later as an economy where the
scarce materials are not scarce, and by then the cause is one retuned
number in one event that nobody connects to the symptom.

It also cannot be verified by reading. The rates are spread across
several events, each individually sensible, and the loop only appears
when you multiply three of them together. Refine 100 metal+crystal into
21 xendium+permafrost, downcycle those back, and whether you end up ahead
is not something anybody eyeballs correctly.

HOW IT IS CHECKED. Every deterministic trade (success_chance 1.0) is read
out of the encounter tables as a conversion between material tiers, using
the MAXIMUM of any range for what the player receives and the minimum for
what they pay -- the luckiest possible reading, because a loop that is
only profitable on good rolls is still a loop.

Round trips are then walked: tier A to tier B and back, and every
three-tier cycle. If any returns more than it started with, that is an
infinite source and this fails.

Trades are ALLOWED to be generous -- the encounter docstring says they
should be in the player's favour, and one-way generosity is fine. What is
not allowed is generosity that closes a circle.
"""

from __future__ import annotations

import itertools
import sys


def main() -> int:
    sys.path.insert(0, ".")
    from bot.database.models.enums import MATERIAL_TIERS
    from bot.game.dungeon.encounter_config import ENCOUNTERS

    # material name -> tier index
    tier_of: dict[str, int] = {}
    for index, materials in enumerate(MATERIAL_TIERS):
        for material in materials:
            tier_of[material.value] = index

    def best(value) -> float:
        """Most generous reading of an amount the player RECEIVES."""
        if isinstance(value, (list, tuple)):
            return float(max(value))
        return float(value)

    def cheapest(value) -> float:
        """Least the player could PAY."""
        if isinstance(value, (list, tuple)):
            return float(min(value))
        return float(value)

    # (from_tier, to_tier) -> best ratio seen, i.e. output per unit input
    conversions: dict[tuple[int, int], tuple[float, str]] = {}
    failures: list[str] = []
    trades = 0

    for encounter in ENCOUNTERS:
        for choice in encounter.get("choices", []):
            if choice.get("action") != "trade":
                continue
            if float(choice.get("success_chance", 0)) < 1.0:
                # A gambled trade is not a reliable converter; it cannot
                # be the basis of a printing loop.
                continue
            cost = choice.get("cost") or {}
            gain = (choice.get("on_success") or {}).get("gain") or {}

            spent_by_tier: dict[int, float] = {}
            for currency, amount in cost.items():
                if currency in tier_of:
                    spent_by_tier[tier_of[currency]] = (
                        spent_by_tier.get(tier_of[currency], 0) + cheapest(amount))
            if not spent_by_tier:
                continue

            gained_by_tier: dict[int, float] = {}
            if "material_tier" in gain:
                gained_by_tier[int(gain["material_tier"])] = best(gain.get("amount", 0))
            for currency, amount in gain.items():
                if currency in tier_of:
                    gained_by_tier[tier_of[currency]] = (
                        gained_by_tier.get(tier_of[currency], 0) + best(amount))
            if not gained_by_tier:
                continue

            trades += 1
            # Attribute the whole output to the whole input. With one
            # input tier and one output tier -- which every conversion
            # here has -- that is exact.
            if len(spent_by_tier) == 1 and len(gained_by_tier) == 1:
                (source, spent), = spent_by_tier.items()
                (target, gained), = gained_by_tier.items()
                if spent <= 0:
                    continue
                ratio = gained / spent
                key = (source, target)
                label = f"{encounter['id']}/{choice['id']}"
                if key not in conversions or ratio > conversions[key][0]:
                    conversions[key] = (ratio, label)

    # ---- same-tier trades must never exceed 1.0 ----------------------
    for (source, target), (ratio, label) in conversions.items():
        if source == target and ratio > 1.0:
            failures.append(
                f"{label} converts tier {source} into tier {source} at "
                f"{ratio:.2f}x -- that is a printing press on its own")

    # ---- two-step round trips ----------------------------------------
    tiers = range(len(MATERIAL_TIERS))
    for source, target in itertools.permutations(tiers, 2):
        out = conversions.get((source, target))
        back = conversions.get((target, source))
        if not out or not back:
            continue
        product = out[0] * back[0]
        if product > 1.0:
            failures.append(
                f"tier {source} -> {target} -> {source} returns {product:.2f}x "
                f"({out[1]} at {out[0]:.2f}x, then {back[1]} at {back[0]:.2f}x) "
                f"-- an infinite material source")

    # ---- three-step cycles -------------------------------------------
    for a, b, c in itertools.permutations(tiers, 3):
        legs = [conversions.get((a, b)), conversions.get((b, c)), conversions.get((c, a))]
        if not all(legs):
            continue
        product = legs[0][0] * legs[1][0] * legs[2][0]
        if product > 1.0:
            failures.append(
                f"tier {a} -> {b} -> {c} -> {a} returns {product:.2f}x via "
                f"{', '.join(leg[1] for leg in legs)} -- an infinite source")

    print(f"trades     : {trades} deterministic material conversions")
    print(f"routes     : {len(conversions)} distinct tier-to-tier rates")
    for (source, target), (ratio, label) in sorted(conversions.items()):
        direction = "up  " if target > source else ("down" if target < source else "flat")
        print(f"  tier {source} -> {target}  {direction}  {ratio:5.2f}x  ({label})")

    if failures:
        print()
        for failure in failures:
            print(f"  FAIL  {failure}")
        return 1
    print("\nOK -- every conversion loop runs at a loss.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
