"""
The one-time reset pays everybody, in order, without runaway spread.

    python -m tools.check_compensation

WHY A ONE-TIME TOOL IS WORTH CHECKING. It runs once, against every real
account, and it cannot be undone. There is no second attempt in which
somebody notices a player got nothing -- by then the old database is a
backup file and the new one is live. The whole cost of getting this wrong
lands in the ten minutes after it is run.

WHAT THE CURVE HAS TO DO, all four at once:

  1. PAY EVERYONE. Every account here is being wiped without being
     asked. The straight refund paid three of sixteen players exactly
     nothing, which is not compensation, it is a deletion with extra
     steps.

  2. PRESERVE ORDER. Somebody who accumulated more must still receive
     more. Compression is not levelling -- if a curve ever inverts two
     players, it has stopped being a refund and become a lottery.

  3. COMPRESS. The linear formula ran 160x on shards and 7,428x on gold
     across the real player table, and those numbers record who was
     around while things were being handed out rather than anything
     anybody played for. Carrying them into a fresh start hands the new
     game a settled hierarchy on day one.

  4. STAY BOUNDED. floor + cap is a hard ceiling. A player with ten
     times the progress of the next one must not receive ten times the
     payout, and the asymptote is what guarantees it no matter what the
     raw figure turns out to be.

The real player table is used as the fixture, because a curve that
behaves on invented numbers and not on the actual distribution is a curve
that has been tested against the wrong thing.
"""

from __future__ import annotations

import sys

# The live player table at the time of the reset: the linear payout each
# account would have received. Kept as the fixture because it is the
# distribution this actually has to handle.
LIVE_PAYOUTS = [
    # name, shards, gold, fragments
    ("Sader", 25_920, 0, 0),
    ("Reynamations", 11_664, 125_145, 0),
    ("Polo", 9_720, 0, 0),
    ("Sine", 8_586, 557_128, 3_321),
    ("Refender", 2_916, 94_393, 221),
    ("Nutvanw", 1_782, 52_149, 137),
    ("AIZER", 1_782, 0, 0),
    ("500 billian", 1_620, 309_789, 1_582),
    ("Splash", 1_296, 6_070, 5),
    ("Dolphe", 648, 14_655, 0),
    ("veronika", 648, 75, 0),
    ("Nyrvite", 324, 2_313, 8),
    ("Filtered", 162, 2_994, 8),
    ("Nepos", 0, 0, 0),
    ("Romain", 0, 0, 0),
    ("Zodor", 0, 3, 0),
]

# The most the top account may receive relative to the emptiest one.
# Above this the reset is handing out a head start somebody else cannot
# close by playing.
MAX_SPREAD = 20.0


def main() -> int:
    sys.path.insert(0, ".")
    from tools.reset_and_compensate import COMPENSATION_CURVE, compensate

    failures: list[str] = []
    columns = {"shards": 1, "gold": 2, "evolution_fragments": 3}

    print(f"{'currency':<20}{'floor':>8}{'cap':>9}{'top paid':>10}"
          f"{'spread':>8}{'zeroes':>8}")

    for currency, index in columns.items():
        floor, cap, _scale = COMPENSATION_CURVE[currency]
        paid = [compensate(currency, row[index]) for row in LIVE_PAYOUTS]

        # 1. everybody gets something
        zeroes = sum(1 for value in paid if value <= 0)
        if zeroes:
            failures.append(
                f"{currency}: {zeroes} account(s) receive nothing -- every one of "
                f"these players is being wiped without being asked")

        # 2. order is preserved
        pairs = sorted(zip((row[index] for row in LIVE_PAYOUTS), paid))
        for (raw_a, paid_a), (raw_b, paid_b) in zip(pairs, pairs[1:]):
            if raw_b > raw_a and paid_b < paid_a:
                failures.append(
                    f"{currency}: {raw_b:,} raw pays {paid_b:,} but {raw_a:,} raw "
                    f"pays {paid_a:,} -- the curve inverts two players")
                break

        # 3. compression actually happened
        spread = max(paid) / max(1, min(paid))
        if spread > MAX_SPREAD:
            failures.append(
                f"{currency}: top account receives {spread:.0f}x the emptiest "
                f"(limit {MAX_SPREAD:.0f}x) -- the curve is not compressing")

        # 4. bounded by floor + cap, whatever the input
        ceiling = floor + cap
        for absurd in (10**6, 10**9, 10**12):
            if compensate(currency, absurd) > ceiling:
                failures.append(
                    f"{currency}: a raw figure of {absurd:,} pays more than the "
                    f"floor+cap ceiling of {ceiling:,} -- the asymptote leaks")
                break

        # 5. the floor really is the floor
        if compensate(currency, 0) != floor:
            failures.append(
                f"{currency}: an empty account receives "
                f"{compensate(currency, 0):,}, not the floor of {floor:,}")

        print(f"{currency:<20}{floor:>8,}{cap:>9,}{max(paid):>10,}"
              f"{spread:>7.1f}x{zeroes:>8}")

    # Strictly increasing across the whole domain, not just at the
    # fixture's sample points -- a curve that is monotone on sixteen
    # values and not in between would pass the check above and still
    # invert two players who are not in this table.
    for currency in columns:
        previous = -1.0
        for raw in range(0, 200_000, 977):     # a prime-ish step, so the
            value = compensate(currency, raw)  # sampling is not aligned
            if value < previous:               # to any round number
                failures.append(
                    f"{currency}: not monotonic -- {raw:,} pays less than the "
                    f"value before it")
                break
            previous = value

    # ==================================================================
    # AUTHENTICITY: the ownership discount
    # ==================================================================
    #
    # Three real accounts owned more than anybody else and had played
    # none of it -- Sader with 26 characters at level 1, Polo with 18,
    # AIZER with 9. Under an ownership refund they collected the largest
    # shard payouts in the game for a roster that arrived by grant.
    #
    # The discount that fixes that is aimed at a handful of accounts and
    # runs against all sixteen, so what needs checking is mostly who it
    # must NOT hit: the small genuine players who also show a low average
    # level, for the ordinary reason that they only just started.
    from tools.reset_and_compensate import (
        MIN_AUTHENTICITY, OWNERSHIP_PAID, authenticity, discount)

    class _Char:
        """Minimal stand-in -- authenticity() reads level and avatar flag."""
        def __init__(self, level):
            self.level = level
            self.template = type("T", (), {"is_player_avatar": False})()

    def roster(count, level):
        return [_Char(level) for _ in range(count)]

    # 6. THE FLOOR SURVIVES ANY DISCOUNT.
    #
    # The single most important property here, and the reason discount()
    # subtracts the floor before scaling rather than multiplying the
    # whole payout. Nepos, Romain and Zodor own one character at level 1
    # -- indistinguishable from a granted roster by average level alone,
    # and they must still be paid in full at the floor.
    for currency in columns:
        floor = COMPENSATION_CURVE[currency][0]
        for factor in (MIN_AUTHENTICITY, 0.5, 1.0):
            if round(discount(currency, floor, factor)) != floor:
                failures.append(
                    f"{currency}: a factor of {factor} cuts into the floor "
                    f"({round(discount(currency, floor, factor)):,} vs {floor:,}) "
                    f"-- new players would be punished for being new")

    # 7. A GIFTED ROSTER IS PAID LESS THAN A PLAYED ONE OF EQUAL SIZE.
    # The whole point. Same holdings, same raw payout, different history.
    raw = 25_920 * 1.35
    gifted = discount("shards", compensate("shards", raw), authenticity(roster(26, 1)))
    played = discount("shards", compensate("shards", raw), authenticity(roster(26, 60)))
    if gifted >= played:
        failures.append(
            f"an unplayed roster is paid {gifted:,.0f} and a played roster of the "
            f"same size {played:,.0f} -- the discount is not discriminating")

    # 8. THE MOST-PLAYED ACCOUNT ENDS UP AHEAD OF THE MOST-GIFTED.
    # Stated against the real numbers, because a discount that is
    # directionally right and too small to reorder anybody has not
    # actually fixed the thing it was written for -- which is exactly
    # what happened when it was applied before the curve instead of
    # after, and cost the top offender all of 5%.
    top_gifted = discount("shards", compensate("shards", 25_920 * 1.35),
                          authenticity(roster(26, 1)))
    top_played = discount("shards", compensate("shards", 8_586 * 1.35),
                          authenticity(roster(22, 60)))
    if top_gifted >= top_played:
        failures.append(
            f"the most-gifted account still receives {top_gifted:,.0f} against the "
            f"most-played account's {top_played:,.0f} -- the discount is too weak "
            f"to reorder them, which was the reason for writing it")

    # 9. BOUNDED, AND NEVER ZERO.
    for count, level in ((0, 1), (1, 1), (26, 1), (26, 60), (26, 100)):
        factor = authenticity(roster(count, level))
        if not MIN_AUTHENTICITY <= factor <= 1.0:
            failures.append(
                f"{count} characters at level {level} gives a factor of {factor:.2f}, "
                f"outside [{MIN_AUTHENTICITY}, 1.0]")
    if authenticity([]) != 1.0:
        failures.append(
            "a player with no characters is discounted -- there is no ownership "
            "payout to scale, and nothing for them to have gamed")

    # 10. EFFORT-PAID CURRENCIES ARE LEFT ALONE.
    #
    # Gold and fragments are computed from levels and breakthroughs,
    # which are XP and spend and cannot be handed over. A granted account
    # already scores near zero on them with no rule required, so applying
    # the discount there would charge it twice for the same absence.
    if set(OWNERSHIP_PAID) & {"gold", "evolution_fragments"}:
        failures.append(
            "gold or fragments are being discounted -- both are already "
            "computed from levels, so this penalises the same gap twice")

    # 11. THE DISCOUNT PRESERVES ORDER among accounts with equal history.
    # Compression is allowed to narrow gaps, never to invert them.
    for currency in columns:
        index = columns[currency]
        for factor in (MIN_AUTHENTICITY, 0.6, 1.0):
            values = sorted((row[index],
                             discount(currency, compensate(currency, row[index]), factor))
                            for row in LIVE_PAYOUTS)
            for (raw_a, out_a), (raw_b, out_b) in zip(values, values[1:]):
                if raw_b > raw_a and out_b < out_a:
                    failures.append(
                        f"{currency}: at factor {factor} the discount inverts "
                        f"{raw_a:,} and {raw_b:,}")
                    break

    # 12. THE GOLD PAYOUT IS PRICED AGAINST THE GOLD ECONOMY.
    #
    # These constants were originally justified against the cost of
    # levelling one item to 50 (72,275), which made a 25,000 floor look
    # like a third of one item and therefore modest. Measured against
    # what gold is actually SPENT on -- the forge upgrade path and
    # crafting -- the same floor was a free Mythic craft handed to an
    # account with no progress, and the ceiling was 148% of the entire
    # upgrade economy.
    #
    # Tying the assertion to forge_config means it re-derives if the
    # forge is ever repriced, instead of drifting into another number
    # that is only defensible against a benchmark nobody rechecked.
    from bot.game.economy import forge_config as fc
    from bot.database.models.enums import Rarity

    forge_path = sum(step["gold"] for step in fc.FORGE_UPGRADE_COST.values())
    mythic_craft = fc.CRAFT_COST[Rarity.MYTHIC]["gold"]
    gold_floor, gold_cap, _ = COMPENSATION_CURVE["gold"]
    gold_ceiling = gold_floor + gold_cap

    if gold_floor >= mythic_craft:
        failures.append(
            f"the gold floor of {gold_floor:,} is at least a free Mythic craft "
            f"({mythic_craft:,}) for an account with no progress -- that is a head "
            f"start, not a restart kit")
    if gold_ceiling >= forge_path:
        failures.append(
            f"the gold ceiling of {gold_ceiling:,} covers the whole forge upgrade "
            f"path ({forge_path:,}) -- the top account is handed the upgrade "
            f"economy instead of playing for it")

    # 13. THE TOP OF THE GOLD CURVE IS ACTUALLY CONVERGED.
    #
    # Above roughly 100,000 raw the gaps record who was around while gold
    # was being handed out rather than anything anyone played for, so the
    # four biggest accounts should land close together. At the old scale
    # of 120,000 they spread over 51,585 gold, which is more than the
    # entire payout of everyone below them.
    top_four = sorted((compensate("gold", row[2]) for row in LIVE_PAYOUTS),
                      reverse=True)[:4]
    top_gap = top_four[0] - top_four[-1]
    if top_gap > gold_cap * 0.25:
        failures.append(
            f"the four largest gold accounts spread over {top_gap:,}, more than a "
            f"quarter of the {gold_cap:,} cap -- the curve is still paying for "
            f"differences at the top that nobody earned")

    print()
    print(f"{'gold landmark':<26}{'cost':>10}   vs compensation")
    print(f"{'one Rare craft':<26}{fc.CRAFT_COST[Rarity.RARE]['gold']:>10,}"
          f"   floor {gold_floor:,} = "
          f"{gold_floor / fc.CRAFT_COST[Rarity.RARE]['gold']:.1f}x")
    print(f"{'one Mythic craft':<26}{mythic_craft:>10,}"
          f"   ceiling {gold_ceiling:,} = {gold_ceiling / mythic_craft:.1f}x")
    print(f"{'full forge upgrade path':<26}{forge_path:>10,}"
          f"   ceiling is {gold_ceiling / forge_path * 100:.0f}% of it")
    print(f"{'top-4 spread':<26}{top_gap:>10,}   "
          f"(limit {int(gold_cap * 0.25):,})")

    print()
    print(f"{'roster':<26}{'factor':>8}{'shards on 25,920 raw':>24}")
    for label, count, level in (("26 chars, never played", 26, 1),
                                ("26 chars, avg level 14", 26, 14),
                                ("26 chars, avg level 60", 26, 60),
                                ("1 char, brand new", 1, 1)):
        factor = authenticity(roster(count, level))
        print(f"{label:<26}{factor:>8.2f}"
              f"{discount('shards', compensate('shards', raw), factor):>24,.0f}")

    if failures:
        print()
        for failure in failures:
            print(f"  FAIL  {failure}")
        return 1
    print("\nOK -- everyone is paid, order holds, the spread is bounded, and "
          "granted rosters do not outearn played ones.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
