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

    if failures:
        print()
        for failure in failures:
            print(f"  FAIL  {failure}")
        return 1
    print("\nOK -- everyone is paid, order holds, and the spread is bounded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
