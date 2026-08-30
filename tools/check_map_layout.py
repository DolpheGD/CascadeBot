"""Check that optional map content does not change the field layout."""

from __future__ import annotations

import sys


def main() -> int:
    from bot.utils.embedder.story import map_embed

    common = {
        "area": {"name": "Test Area", "blurb": ""},
        "grid": ".",
        "legend": [],
    }
    floor = map_embed(**common, standing_on=None)
    occupied = map_embed(**common, standing_on="Object")

    floor_fields = floor.to_dict().get("fields", [])
    occupied_fields = occupied.to_dict().get("fields", [])
    stable = (
        len(floor_fields) == len(occupied_fields)
        and floor_fields[-1]["name"] == "\u200b"
        and floor_fields[-1]["value"] == "\u200b"
        and occupied_fields[-1]["name"] == "You're standing on"
    )
    if not stable:
        print("FAIL -- optional map content changes the field layout.")
        return 1
    print("OK -- optional map content keeps a stable field layout.")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, ".")
    raise SystemExit(main())
