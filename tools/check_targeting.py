"""
Verify targeted 5-star selection on both banners.

    python -m tools.check_targeting

The promise made to the player is specific and testable:

    "Pick a 5-star. It gets a better rate. And if a 5-star turns up that
     ISN'T your pick, the next one is guaranteed to be."

That promise has exactly one failure mode that matters and it is
invisible: it mostly works. A guarantee that fires 95% of the time looks
identical to a working one for as long as anybody is paying attention,
and the 5% who lose a guarantee they earned have no way to prove it and
will be told they misremembered.

So this does not inspect the code. It PULLS -- tens of thousands of
simulated 5-stars per banner, through the real resolve_five_star -- and
asserts:

  1. NO MISS IS EVER FOLLOWED BY A MISS. This is the whole promise, and
     it is checked as a hard invariant on the sequence rather than as a
     rate. One violation anywhere fails the run.

  2. THE ADVERTISED RATE IS THE MEASURED RATE. The share of 5-stars that
     are the target, over the long run, has to match what the config
     claims once the guarantee is accounted for. A "miss" branch that can
     return the target anyway would push the real rate above the stated
     one -- flattering, still wrong, and it would make the guarantee arm
     after pulls the player counts as wins.

  3. A GUARANTEE IS NEVER SPENT ON NOTHING. With no target set, or a
     target that is not in the pool, an armed guarantee must survive.
     Consuming it silently is the single most expensive bug this system
     can have.

  4. BOTH BANNERS BEHAVE IDENTICALLY, because they share the rule. The
     characters and cards paths are exercised separately and compared.
"""

from __future__ import annotations

import random
import sys

TRIALS = 40_000


def main() -> int:
    sys.path.insert(0, ".")

    from bot.services.pull_service import (
        TARGET_FIVE_STAR_RATE_PERCENT,
        resolve_five_star,
    )

    failures: list[str] = []

    def run(pool, target, key_of, label):
        rng = random.Random(20260819)
        guaranteed = False
        hits = 0
        previous_was_miss = False
        double_miss_at = None
        for index in range(TRIALS):
            chosen, hit, guaranteed = resolve_five_star(
                rng, pool, target, key_of, guaranteed)
            if hit:
                hits += 1
                previous_was_miss = False
            else:
                if previous_was_miss and double_miss_at is None:
                    double_miss_at = index
                previous_was_miss = True
        return hits / TRIALS, double_miss_at

    # ---- banner 1: characters, keyed by template name ----
    class T:
        def __init__(self, name):
            self.name = name

    char_pool = [T(f"Char{i}") for i in range(12)]
    char_rate, char_double = run(char_pool, "Char3", lambda t: t.name, "characters")

    # ---- banner 2: cards, keyed by dict id ----
    card_pool = [{"id": f"card_{i}", "name": f"Card {i}"} for i in range(9)]
    card_rate, card_double = run(card_pool, "card_4", lambda c: c["id"], "cards")

    for label, double_at in (("characters", char_double), ("cards", card_double)):
        if double_at is not None:
            failures.append(
                f"{label}: two misses in a row at 5-star #{double_at} -- the "
                f"guarantee did not fire, which is the one thing it promises"
            )

    # Expected long-run share of 5-stars that are the target.
    #
    # Not the raw rate. Let p be the configured target rate. From a
    # cleared state a pull hits with probability p; on a miss the next is
    # certain. That two-state chain settles at 1/(2 - p) -- so 55% per
    # roll shows up as ~69% of all 5-stars, and checking against the raw
    # 55% would fail a correct implementation.
    p = TARGET_FIVE_STAR_RATE_PERCENT / 100
    expected = 1 / (2 - p)
    tolerance = 0.015
    for label, rate in (("characters", char_rate), ("cards", card_rate)):
        if abs(rate - expected) > tolerance:
            failures.append(
                f"{label}: {rate:.1%} of 5-stars were the target, expected "
                f"{expected:.1%} +/- {tolerance:.1%} for a {p:.0%} pick-up rate "
                f"with a guarantee"
            )

    # ---- 3: an armed guarantee survives a banner the target isn't on --
    rng = random.Random(7)
    for label, pool, key_of in (("characters", char_pool, lambda t: t.name),
                                ("cards", card_pool, lambda c: c["id"])):
        _chosen, hit, after = resolve_five_star(rng, pool, None, key_of, True)
        if not after or hit:
            failures.append(
                f"{label}: an armed guarantee was consumed by a pull with NO "
                f"target set -- the player loses a guarantee they earned")
        _chosen, hit, after = resolve_five_star(
            rng, pool, "not-in-this-pool", key_of, True)
        if not after or hit:
            failures.append(
                f"{label}: an armed guarantee was consumed by a pull whose target "
                f"is not in the pool")

    # ---- 4: the two banners agree ----
    if abs(char_rate - card_rate) > 0.02:
        failures.append(
            f"the two banners disagree: characters {char_rate:.1%} vs cards "
            f"{card_rate:.1%} -- they are meant to share one rule")

    print(f"trials     : {TRIALS:,} five-stars per banner")
    print(f"pick-up    : {TARGET_FIVE_STAR_RATE_PERCENT:.0f}% per 5-star, "
          "guarantee on the next after a miss")
    print(f"characters : {char_rate:.1%} of 5-stars were the target")
    print(f"cards      : {card_rate:.1%} of 5-stars were the target")
    print(f"expected   : {expected:.1%}")
    print("worst case : 2 five-stars to land a specific pick, always")

    if failures:
        print()
        for failure in failures:
            print(f"  FAIL  {failure}")
        return 1
    print("\nOK -- the guarantee always fires and the advertised rate is the real one.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
