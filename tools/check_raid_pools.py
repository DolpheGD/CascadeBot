"""
Assert every raid tier is actually clearable.

    python -m tools.check_raid_pools

WHY THIS IS A SCRIPT AND NOT A COMMENT.

A raid attack contributes `boss max HP - boss current HP`, which is
ceilinged by the boss's own health bar. So a tier whose `hp_per_attack`
exceeds that bar can never be finished -- not "is hard", cannot be
finished, by any number of players at any power level. Every raid above
the starter tier was in exactly that state before the boss HP multiplier
was added (see the BOSS HP MULTIPLIER block in raid_config).

That failure is invisible from the config file: `hp_per_attack: 26_000`
looks like a big number, not an impossible one, because whether it's
impossible depends on an enemy template in a different module scaled by
a level in a third. This script does that arithmetic and fails loudly,
so a future retune of either side can't silently recreate the bug.

What's checked, per tier, against the DEFAULT difficulty (the one the
raid is summoned at, and the one everyone fights unless they opt out):

  1. an on-target attack strips less than MAX_HEALTHY_ATTACK_FRACTION of
     the boss's real bar, so the target is reachable at all, and
  2. the whole pool falls inside the tier's total attack budget.

Both are evaluated against the WEAKEST boss in the tier's pool, since a
raid rolls one at random and it only takes one bad roll to hand a server
an unclearable week.

Non-default difficulties are reported but not failed. A Skirmish boss is
20 levels down and has a correspondingly small bar, so a full kill there
credits less than one on-target attack -- that IS the trade the
difficulty picker offers, not a broken tier.
"""

from __future__ import annotations

import sys


# Biggest allowed jump in total HP pool between consecutive tiers.
MAX_TIER_STEP = 4.0
# Fewest bosses a tier may draw from, so repeat raids aren't identical.
MIN_POOL_SIZE = 8


def main() -> int:
    from bot.game.combat.enemies import get_template_by_name
    from bot.game.combat.factory import build_enemy_combatant
    from bot.game.economy.raid_config import (
        DEFAULT_RAID_DIFFICULTY,
        MAX_HEALTHY_ATTACK_FRACTION,
        RAID_DIFFICULTIES,
        RAID_TIERS,
        attacks_per_player,
        boss_hp_multiplier,
        pool_hp_for,
        RAID_TIERS,
        expected_participants,
        get_difficulty,
        pool_hp_for,
        raid_boss_level,
    )

    def weakest_boss(tier: dict, difficulty: dict):
        level = raid_boss_level(tier["boss_level"], difficulty)
        built = [
            (build_enemy_combatant(get_template_by_name(name), level=level,
                                   hp_multiplier=boss_hp_multiplier(tier)), name)
            for name in tier["boss_pool"]
        ]
        return min(built, key=lambda pair: pair[0].max_hp)

    failures: list[str] = []
    default = get_difficulty(DEFAULT_RAID_DIFFICULTY)

    print(f"{'tier':<12}{'weakest boss':<24}{'bossHP':>10}{'perAttack':>11}"
          f"{'frac':>7}{'attacks':>9}{'budget':>8}")
    for tier in RAID_TIERS:
        pool = pool_hp_for(tier)
        budget = expected_participants(tier) * attacks_per_player(tier)
        per_attack = tier["hp_per_attack"]
        boss, boss_name = weakest_boss(tier, default)
        fraction = per_attack / boss.max_hp
        needed = pool / per_attack

        print(f"{tier['id']:<12}{boss_name[:23]:<24}{boss.max_hp:>10,}{per_attack:>11,}"
              f"{fraction:>7.0%}{needed:>9.0f}{budget:>8}")

        if fraction > MAX_HEALTHY_ATTACK_FRACTION:
            failures.append(
                f"{tier['id']}: an on-target attack must strip {fraction:.0%} of "
                f"{boss_name}'s {boss.max_hp:,} HP (limit {MAX_HEALTHY_ATTACK_FRACTION:.0%})"
            )
        if needed > budget:
            failures.append(
                f"{tier['id']}: pool of {pool:,} needs {needed:.0f} on-target attacks "
                f"but only {budget} exist"
            )

    # Informational: what one perfect attack is worth at each difficulty,
    # i.e. a full kill times that difficulty's contribution multiplier.
    # Anything under 100% means even killing the boss doesn't hit the
    # per-attack target -- expected at Skirmish, worth seeing elsewhere.
    print(f"\n{'tier':<12}" + "".join(f"{d['name']:>12}" for d in RAID_DIFFICULTIES))
    for tier in RAID_TIERS:
        cells = []
        for difficulty in RAID_DIFFICULTIES:
            boss, _ = weakest_boss(tier, difficulty)
            credited = boss.max_hp * difficulty["contribution_multiplier"]
            cells.append(f"{credited / tier['hp_per_attack']:>11.0%}")
        print(f"{tier['id']:<12}" + "".join(cells))
    print("(a full kill, as a % of one attack's target)")

    print()
    # ------------------------------------------------------------------
    # LADDER SHAPE. A tier being individually clearable says nothing about
    # whether the JUMP to it is reasonable, and the jump is what players
    # actually feel. The pools ran 4,160 -> 160,000 -> 440,000 -> 880,000:
    # a 38x step, then 2.8x, then 2.0x. Every sizing axis moved at once
    # between the first two tiers (hp_per_attack 520 -> 4,000, expected
    # participants 2 -> 4, attacks 4 -> 10), so clearing the starter raid
    # taught a server nothing about the next one -- it just met a wall.
    # ------------------------------------------------------------------
    previous, previous_name = None, None
    for tier in RAID_TIERS:
        pool = pool_hp_for(tier)
        if previous is not None:
            step = pool / previous
            if step > MAX_TIER_STEP:
                failures.append(
                    f"{tier['id']}: {step:.1f}x bigger than {previous_name} "
                    f"({previous:,} -> {pool:,}), max {MAX_TIER_STEP:.1f}x"
                )
            if step < 1.0:
                failures.append(
                    f"{tier['id']}: SMALLER than {previous_name} "
                    f"({previous:,} -> {pool:,})"
                )
        previous, previous_name = pool, tier["id"]

    gates = [t["min_roster_levels"] for t in RAID_TIERS]
    if gates != sorted(gates):
        failures.append(f"min_roster_levels is not monotonic: {gates}")

    for tier in RAID_TIERS:
        if len(tier["boss_pool"]) < MIN_POOL_SIZE:
            failures.append(
                f"{tier['id']}: only {len(tier['boss_pool'])} bosses in the pool "
                f"(min {MIN_POOL_SIZE}) -- consecutive raids will repeat"
            )

    print()
    print("ladder    : " + " -> ".join(f"{pool_hp_for(t):,}" for t in RAID_TIERS))
    print("pool sizes: " + ", ".join(f"{t['id']}={len(t['boss_pool'])}" for t in RAID_TIERS))
    print(f"distinct bosses across all tiers: "
          f"{len({n for t in RAID_TIERS for n in t['boss_pool']})}")

    if failures:
        for line in dict.fromkeys(failures):
            print(f"  FAIL  {line}")
        return 1
    print(f"OK -- all {len(RAID_TIERS)} raid tiers are clearable within their attack budget.")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, ".")
    sys.exit(main())
