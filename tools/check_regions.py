"""
Every configured region must be reachable, selectable and complete.

    python -m tools.check_regions

THE BUG THIS EXISTS FOR
-----------------------
Entrospire Deepworks shipped invisible. It had a full entry in
region_config, 8 combat enemies, 6 elites, a checkpoint boss, a final
boss, two commissions pointing at it, an unlock chained off Abyssnia, and
a completely green check suite.

There was no way to select it. `/adventure` carried its own hardcoded
list of five `app_commands.Choice` lines, and nobody had added a sixth.
The region config said six regions; the command said five; no tool
compared them.

That is the same shape as every other bug this repo keeps finding: two
places holding one fact. The command now builds its list from the config,
and this file asserts they agree -- plus everything else a region needs
before it counts as finished.

CHECKED
-------
  * the /adventure choices match ordered_regions() exactly
  * every region has enough enemies to fill its rooms (combat, elite, and
    BOTH a regular and a final boss -- a region with no "final" entry
    silently borrows another region's, which is how a boss ends up
    fighting outside its own tier)
  * the unlock chain is a single line with no orphans or cycles
  * difficulty rises monotonically on the fields that order the ladder
  * every region can actually generate a map
"""

from __future__ import annotations

import random
import sys


def main() -> int:
    sys.path.insert(0, ".")

    from bot.game.combat import enemies as catalog
    from bot.game.dungeon.generator import DungeonGenerator
    from bot.game.dungeon.region_config import (
        REGION_DIFFICULTY,
        ordered_regions,
        region_unlock_requirement,
    )

    failures: list[str] = []
    regions = ordered_regions()

    # ---- 1. the command offers exactly what the config defines --------
    try:
        from bot.cogs.dungeon import _REGION_CHOICES
        offered = [c.value for c in _REGION_CHOICES]
        missing = [r for r in regions if r not in offered]
        extra = [r for r in offered if r not in regions]
        if missing:
            failures.append(
                f"/adventure does not offer {missing} -- configured regions the "
                f"player cannot select")
        if extra:
            failures.append(
                f"/adventure offers {extra}, which are not in ordered_regions()")
        if len(offered) > 25:
            failures.append(
                f"/adventure offers {len(offered)} choices, over Discord's cap of 25")
    except Exception as exc:  # pragma: no cover
        failures.append(f"could not read /adventure's region choices: {exc!r}")
        offered = []

    # ---- 2. every region has the content its rooms need ---------------
    for region in regions:
        combat = catalog.get_templates_by_role("combat", region=region) or []
        elite = catalog.get_templates_by_role("elite", region=region) or []
        # get_templates_by_role falls back to the unfiltered pool when a
        # region has nothing, so identity is checked rather than count:
        # a fallback means this region has no roster of its own.
        all_combat = catalog.get_templates_by_role("combat") or []
        if combat is all_combat or len(combat) < 4:
            failures.append(
                f"'{region}' has {len(combat)} combat enemies of its own "
                f"(needs 4+; fewer means it borrows another region's roster)")
        if len(elite) < 3:
            failures.append(f"'{region}' has only {len(elite)} elite enemies")

        for role in ("regular", "final"):
            named = [t for t in catalog.get_templates_by_role("boss")
                     if t.get("region_roles", {}).get(region) == role]
            groups = [g for g, roles in getattr(catalog, "BOSS_GROUP_REGION_ROLES",
                                                {}).items()
                      if roles.get(region) == role]
            if not named and not groups:
                failures.append(
                    f"'{region}' has no '{role}' boss of its own -- "
                    f"get_boss_encounter will silently borrow one from another "
                    f"region, at a tier it was never balanced for")

    # ---- 3. the unlock chain is one line ------------------------------
    for index, region in enumerate(regions):
        required = region_unlock_requirement(region)
        if index == 0:
            if required is not None:
                failures.append(f"'{region}' is first but requires '{required}'")
        elif required != regions[index - 1]:
            failures.append(
                f"'{region}' unlocks after '{required}', not after "
                f"'{regions[index - 1]}' -- the chain forks or skips")

    # ---- 4. difficulty rises ------------------------------------------
    for field in ("tier", "level_offset", "combat_level_offset",
                  "reward_multiplier", "gold_multiplier"):
        previous = None
        for region in regions:
            value = REGION_DIFFICULTY[region].get(field)
            if previous is not None and value is not None and value < previous:
                failures.append(
                    f"'{region}' has {field}={value}, below the region before it "
                    f"({previous}) -- the ladder goes backwards")
            previous = value if value is not None else previous

    # ---- 5. every region can generate a map ---------------------------
    for region in regions:
        try:
            graph = DungeonGenerator(rng=random.Random(1)).generate(region)
            if not graph["nodes"]:
                failures.append(f"'{region}' generated an empty map")
        except Exception as exc:
            failures.append(f"'{region}' cannot generate a map: {exc!r}")

    print(f"regions    : {len(regions)} configured, {len(offered)} selectable")
    for region in regions:
        d = REGION_DIFFICULTY[region]
        combat = len(catalog.get_templates_by_role("combat", region=region) or [])
        elite = len(catalog.get_templates_by_role("elite", region=region) or [])
        print(f"  {region:<22} tier {d.get('tier')}  "
              f"{combat:>2} combat, {elite:>2} elite  ·  "
              f"unlocks after {region_unlock_requirement(region) or '(start)'}")

    if failures:
        print()
        for failure in sorted(set(failures)):
            print(f"  FAIL  {failure}")
        return 1
    print("\nOK -- every region is selectable, staffed, ordered and generable.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
