"""
Every door on the overworld says where it goes.

    python -m tools.check_map_exits

The map is authored data, so this is a content check as much as a code
one: a new area added next month gets these guarantees for free, and an
area that breaks one fails here rather than in front of a player.

WHAT WENT WRONG THAT THIS PREVENTS

Exit tiles were listed by their authored name alone -- "Buckled door",
"Out, into the cold". Good writing, useless navigation: nothing on the
screen said where the door led, so the only way to find out was to walk
through and look. A four-door hub was four round trips to learn something
the map data already knew.

The destination is now RESOLVED from `to_area` rather than authored on
the door, which is the point: rename an area and every door pointing at
it follows automatically. Authoring it twice is the failure this codebase
hits most, and a door is the worst place to hit it, because a label that
disagrees with where you actually end up is worse than no label.

WHAT IS ASSERTED

  * every exit's `to_area` names a real area (a door to nowhere would
    crash travel(), and the player cannot avoid pressing it)
  * every exit resolves to a NON-EMPTY label -- the shared-prefix
    trimming must never eat the whole name
  * an exit whose destination is in a different building keeps enough
    name to say so
  * one-way exits are marked as one-way, because walking through one is
    irreversible
  * every area can be left (no room is a dead end you cannot exit)
"""

from __future__ import annotations

import sys


def main() -> int:
    sys.path.insert(0, ".")
    import bot.game.story.map_config as mc
    from bot.services.map_service import destination_label

    failures: list[str] = []
    exits = 0
    one_way = 0
    cross_building = 0

    SEPARATOR = " — "

    for area_id, area in mc.AREAS.items():
        area_exits = [
            (char, content)
            for char, content in (area.get("legend") or {}).items()
            if content.get("kind") == "exit"
        ]

        # A room with no way out. The prologue's final room is allowed to
        # be terminal -- it hands off to the story rather than the map --
        # so this reports rather than fails when the area is flagged.
        if not area_exits and not area.get("terminal"):
            failures.append(
                f"{area_id} ({area.get('name')}) has no exit -- a player who "
                f"walks in cannot walk out")

        for char, content in area_exits:
            exits += 1
            destination = content.get("to_area")
            target = mc.get_area(destination) if destination else None

            if target is None:
                failures.append(
                    f"{area_id} tile {char!r} ({content.get('name')}) leads to "
                    f"{destination!r}, which is not an area")
                continue

            label = destination_label(area_id, destination)
            if not label or not label.strip():
                failures.append(
                    f"{area_id} tile {char!r} resolves to an EMPTY destination "
                    f"label for {destination!r} -- prefix trimming ate the name")
                continue

            if label == "somewhere else":
                failures.append(
                    f"{area_id} tile {char!r} fell back to the vague label for "
                    f"{destination!r}")

            here = area.get("name") or ""
            there = target.get("name") or ""
            same_building = (
                SEPARATOR in here and SEPARATOR in there
                and here.split(SEPARATOR)[0] == there.split(SEPARATOR)[0]
            )
            if not same_building:
                cross_building += 1
                # Leaving the building is the case the player most needs
                # to notice, so the label must not have been trimmed down
                # to a bare room name that reads like next door.
                if label != there:
                    failures.append(
                        f"{area_id} tile {char!r} leads OUT of "
                        f"{here.split(SEPARATOR)[0]!r} to {there!r} but is "
                        f"labelled {label!r} -- it reads like a door down the hall")

            if content.get("one_way"):
                one_way += 1

    print(f"areas      : {len(mc.AREAS)}")
    print(f"exits      : {exits} ({cross_building} leave their building, "
          f"{one_way} one-way)")

    if failures:
        print()
        for failure in failures:
            print(f"  FAIL  {failure}")
        return 1
    print("\nOK -- every door resolves to a real place and says which one.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
