"""
Assert that region difficulty actually goes UP.

    python -m tools.check_progression

A region only unlocks by clearing the one before it, so the ladder is a
chain: if any rung is harder than the rung after it, everything past that
point is unreachable no matter how well tuned it is on its own.

That is not hypothetical. Glacier 15 -- the FIRST region, and the one the
prologue now delivers a level-1 squad into -- had a 700 HP capstone while
The Wastelands after it had 420. A full-run simulation cleared 3% at
squad level 1 and 16% at level 5, and 69% of those runs died on the boss.
Every number in the region's own config looked reasonable; the bug was
only visible by comparing regions to each other, which nothing did.

Checked here:

  * FINAL boss HP is non-decreasing across the region order
  * no REGULAR boss in a region is wildly out of band with its peers --
    a first-region pool holding both a 270 HP boss and a 520 HP one means
    the draw, not the player, decides the run
  * combat and elite level offsets rise monotonically

These are cheap structural checks, not a balance simulation. They cannot
tell you a region is fun; they can only tell you the ladder is a ladder.
Run the full-run simulator for the rest.
"""

from __future__ import annotations

import sys

# How much bigger the biggest regular boss in a pool may be than the
# smallest, before the draw is deciding the run rather than the player.
MAX_REGULAR_BOSS_SPREAD = 2.0


def main() -> int:
    from bot.game.combat.enemies import ENEMY_TEMPLATES
    from bot.game.dungeon.region_config import REGION_DIFFICULTY, ordered_regions

    failures: list[str] = []
    regions = ordered_regions()

    def role_in(region: str, role: str) -> list[dict]:
        return [t for t in ENEMY_TEMPLATES
                if (t.get("region_roles") or {}).get(region) == role]

    # --- final boss ladder
    #
    # MEASURED AS THE WHOLE ENCOUNTER, AT THE LEVEL IT IS ACTUALLY FOUGHT.
    #
    # This used to compare raw base_stats["max_hp"], which is not a
    # difficulty at all -- it ignores both the region's level_offset and
    # every escort the boss brings. It was wrong in both directions at
    # once: it failed Glacier -> Wastelands (510 vs 420 base), where the
    # real numbers climb 816 -> 2669 and are fine, while passing
    # Wastelands -> Hotlands (420 vs 1050 base), where the real numbers
    # FALL 2669 -> 2352 because NF arrives with three escorts and X-RR
    # arrives alone. The one genuine inversion on the ladder was the one
    # the check couldn't see, and it had been reported as healthy for as
    # long as the check has existed.
    #
    # So: build the encounter, escorts included, at level_offset + 15
    # (mid-region depth), and compare that. It's the number the player
    # walks into.
    from bot.game.combat.factory import build_enemy_combatant
    from bot.game.combat.enemies import get_template_by_name

    MID_REGION_FLOOR = 15

    def encounter_hp(template: dict, level: int) -> int:
        group = [template] + [get_template_by_name(name)
                              for name in (template.get("escorts") or [])]
        return sum(build_enemy_combatant(t, level).max_hp for t in group)

    best: dict[str, int] = {}
    best_name: dict[str, str] = {}
    for region in regions:
        level = REGION_DIFFICULTY[region]["level_offset"] + MID_REGION_FLOOR
        for t in role_in(region, "final"):
            hp = encounter_hp(t, level)
            if hp > best.get(region, 0):
                best[region], best_name[region] = hp, t["name"]

    previous_hp, previous_region = 0, None
    for region in regions:
        hp = best.get(region)
        if hp is None:
            continue
        if hp < previous_hp:
            failures.append(
                f"'{region}' capstone ({best_name[region]}) is {hp:,} effective HP but "
                f"'{previous_region}' ({best_name[previous_region]}) before it is "
                f"{previous_hp:,} -- the ladder goes DOWN, and every region past "
                f"'{previous_region}' is gated behind the harder earlier one"
            )
        previous_hp, previous_region = hp, region

    # --- regular boss spread within a region
    for region in regions:
        pool = [(t["name"], t["base_stats"]["max_hp"]) for t in role_in(region, "regular")]
        if len(pool) < 2:
            continue
        low = min(hp for _, hp in pool)
        high = max(hp for _, hp in pool)
        if low and high / low > MAX_REGULAR_BOSS_SPREAD:
            worst = max(pool, key=lambda x: x[1])[0]
            # NOT `best_name` -- that name holds the capstone-per-region
            # dict this function reports with at the end, and rebinding it
            # to a string here silently corrupted the summary line for
            # every run where a spread failure fired.
            mildest = min(pool, key=lambda x: x[1])[0]
            failures.append(
                f"'{region}' regular bosses span {low}-{high} HP "
                f"({high / low:.1f}x, max {MAX_REGULAR_BOSS_SPREAD:.1f}x): drawing "
                f"{worst} instead of {mildest} decides the run before it starts"
            )

    # --- offsets rise
    for key in ("level_offset", "combat_level_offset"):
        previous, previous_region = None, None
        for region in regions:
            value = REGION_DIFFICULTY[region][key]
            if previous is not None and value < previous:
                failures.append(
                    f"{key}: '{region}' is {value} but '{previous_region}' before it is "
                    f"{previous}"
                )
            previous, previous_region = value, region

    print(f"regions   : {len(regions)}")
    print("capstones : " + " -> ".join(
        f"{best[r]:,}" for r in regions if r in best) + "  (effective HP, escorts included)")
    print("            " + " -> ".join(best_name[r] for r in regions if r in best))
    steps = [best[r] for r in regions if r in best]
    if len(steps) > 1:
        print("steps     : " + " -> ".join(
            f"{b / a:.2f}x" for a, b in zip(steps, steps[1:])))
    # Abyssnia fields TWO finals and `best` reports only the larger, so
    # the last step reads as a cliff when it is really two rungs: the
    # region's own capstone, and then Rohan, who is the end of the game
    # and is supposed to be a wall rather than a rung.
    for region in regions:
        others = sorted((encounter_hp(t, REGION_DIFFICULTY[region]["level_offset"]
                                      + MID_REGION_FLOOR), t["name"])
                        for t in role_in(region, "final"))
        if len(others) > 1:
            print(f"note      : '{region}' fields "
                  + ", ".join(f"{n} ({h:,})" for h, n in others)
                  + " -- the last is the end of the game, not a rung")
    print()
    if failures:
        for line in dict.fromkeys(failures):
            print(f"  FAIL  {line}")
        return 1
    print("OK -- the difficulty ladder rises, and no boss pool is a coin flip.")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, ".")
    sys.exit(main())
