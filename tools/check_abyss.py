"""
Validate the Void Abyss ladder without running it.

    python -m tools.check_abyss

The Abyss has a failure mode no other mode has: a floor can be perfectly
tuned and still be **impossible**, because it demands more distinct
characters than exist. Twelve chambers of four is forty-eight characters;
the roster has thirty. That is not a difficulty problem, it is a floor
nobody can ever enter, and it looks completely fine in the config.

Checked:

  * every enemy name exists
  * every reward key is a real currency or item rarity
  * a floor never demands more distinct characters than the roster HAS
  * rotating floors keep the SAME chamber count across every rotation --
    otherwise the roster requirement moves under a player mid-cycle
  * level, roster gate and chamber count all rise monotonically
  * static floors have no rotations and rotating floors have no fixed
    chambers, so `chambers_for` can never silently pick the wrong branch
"""

from __future__ import annotations

import sys


def main() -> int:
    from bot.database.models.enums import Rarity
    from bot.game.abyss import abyss_config as ac
    from bot.game.characters.character_seed_data import CHARACTER_TEMPLATES
    from bot.game.combat.enemies import ENEMY_TEMPLATES
    from bot.services.currency_service import VALID_CURRENCIES

    enemy_names = {t["name"] for t in ENEMY_TEMPLATES}
    rarities = {r.value for r in Rarity}
    roster_size = len(CHARACTER_TEMPLATES)
    failures: list[str] = []

    numbers = [f["floor"] for f in ac.FLOORS]
    if numbers != sorted(numbers) or len(set(numbers)) != len(numbers):
        failures.append(f"floor numbers are not unique and ascending: {numbers}")

    previous = None
    for floor in ac.FLOORS:
        where = f"floor {floor['floor']}"

        has_fixed = "chambers" in floor
        has_rot = "rotations" in floor
        if has_fixed == has_rot:
            failures.append(f"{where}: needs exactly one of 'chambers' / 'rotations'")
            continue
        if ac.is_rotating(floor) and not has_rot:
            failures.append(f"{where}: is a rotating floor but has fixed chambers")
        if not ac.is_rotating(floor) and has_rot:
            failures.append(f"{where}: is a static floor but has rotations")

        variants = floor["rotations"] if has_rot else [floor["chambers"]]
        counts = {len(v) for v in variants}
        if len(counts) != 1:
            failures.append(
                f"{where}: rotations disagree on chamber count {sorted(counts)} -- the "
                f"roster requirement would move under a player mid-cycle"
            )

        needed = ac.characters_required(floor)
        if needed > roster_size:
            failures.append(
                f"{where}: demands {needed} distinct characters but only {roster_size} "
                f"exist -- nobody can ever enter it"
            )

        for vi, variant in enumerate(variants):
            for ci, chamber in enumerate(variant, start=1):
                if not chamber:
                    failures.append(f"{where} rotation {vi} chamber {ci}: no enemies")
                if len(chamber) > 5:
                    failures.append(
                        f"{where} rotation {vi} chamber {ci}: {len(chamber)} enemies "
                        f"(engine allows 5)"
                    )
                for name in chamber:
                    if name not in enemy_names:
                        failures.append(f"{where}: no enemy template named {name!r}")

        for key, value in (floor.get("rewards") or {}).items():
            if key == "item":
                if value not in rarities:
                    failures.append(f"{where}: item rarity {value!r} does not exist")
            elif key not in VALID_CURRENCIES:
                failures.append(f"{where}: '{key}' is not a currency")

        if previous is not None:
            for field in ("level", "min_roster_levels"):
                if floor[field] < previous[field]:
                    failures.append(
                        f"{where}: {field} {floor[field]} is below floor "
                        f"{previous['floor']}'s {previous[field]}"
                    )
            if ac.chamber_count(floor) < ac.chamber_count(previous):
                failures.append(f"{where}: fewer chambers than the floor before it")
        previous = floor

    static = [f for f in ac.FLOORS if not ac.is_rotating(f)]
    rotating = [f for f in ac.FLOORS if ac.is_rotating(f)]
    print(f"floors    : {len(ac.FLOORS)} ({len(static)} static, {len(rotating)} rotating)")
    print(f"stars     : {ac.max_stars()} available")
    print(f"roster    : {roster_size} characters exist; deepest floor wants "
          f"{max(ac.characters_required(f) for f in ac.FLOORS)}")
    print("levels    : " + " -> ".join(str(f["level"]) for f in ac.FLOORS))
    print("gates     : " + " -> ".join(f"{f['min_roster_levels']:,}" for f in ac.FLOORS))
    print(f"rotation  : every {ac.ROTATION_DAYS} days")

    print()
    if failures:
        for line in dict.fromkeys(failures):
            print(f"  FAIL  {line}")
        return 1
    print("OK -- every floor is enterable, escalating, and made of real enemies.")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, ".")
    sys.exit(main())
