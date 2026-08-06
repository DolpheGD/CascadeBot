"""
Validate the whole story script without running it.

    python -m tools.check_story

Story content has the same property that made `tools/check_encounters.py`
necessary: it's pure data resolved by a generic interpreter, so a typo
doesn't fail at import or startup. It fails when a player reaches that
one beat -- which for a story mission might be the fourth mission of a
chapter, twenty minutes in, and the failure is a dead button in the
middle of a scripted scene.

Checked:

  * ids unique across every chapter, and every mission reachable
  * every beat has the keys its `kind` needs
  * every enemy name in a battle beat exists in the roster
  * every reward key is a real currency or a valid item rarity
  * every `unlock` names a real feature, and every feature that IS
    gated has exactly one unlock beat somewhere
  * every flag read by `requires`/`unless` is written by some choice --
    a beat gated on a flag nobody sets can never appear
  * a mission cannot be empty, and cannot end on a `choice` (the player
    would pick an option and see nothing happen)

Map density checks land here too once areas exist -- see
docs/STORY_MODE.md.
"""

from __future__ import annotations

import sys

BEAT_KINDS = {"dialogue", "choice", "battle", "encounter", "reward", "unlock"}


def _check_maps() -> list[str]:
    """Validate every overworld area.

    The density rules here are the load-bearing ones. A grid map in a
    button UI does not fail by being too big, it fails by being SPARSE:
    every step costs a Discord round-trip, so a step that usually returns
    nothing is pure friction, and that gets worse the more room you have
    to wander. Density can't be eyeballed once areas vary in size, so it
    is asserted -- an area that fails is a design bug, not a preference.

    Also checked, in rough order of how badly each one ruins a session:

      * reachability -- content walled off from the spawn is content
        nobody will ever see, and it looks completely fine in the source
      * exits that land in a wall or a nonexistent area
      * lock ordering -- a tile requiring a mission that can only be
        started BEYOND that tile is a softlock, and the prologue is
        exactly where a softlock is unrecoverable
      * every mission in story_config placed on exactly one tile
      * glyph width, including variation selectors, which shear a column
        on mobile without looking wrong in an editor
    """
    from collections import deque

    from bot.game.story import map_config as mc
    from bot.game.story import story_config as sc

    from bot.database.models.enums import Rarity
    from bot.game.combat.enemies import ENEMY_TEMPLATES
    from bot.services.currency_service import VALID_CURRENCIES

    enemy_names = {t["name"] for t in ENEMY_TEMPLATES}
    rarities = {r.value for r in Rarity}
    failures: list[str] = []
    placed: dict[str, list[str]] = {}

    def check_grant(where: str, grant: dict) -> None:
        """Map rewards use the same block shape as story rewards, so they
        get the same validation -- a typo'd currency on a cache is exactly
        as invisible as one on a mission."""
        for key, value in (grant or {}).items():
            if key == "item":
                if value not in rarities:
                    failures.append(f"{where}: item rarity {value!r} does not exist")
            elif key == "character":
                continue
            elif key not in VALID_CURRENCIES:
                failures.append(f"{where}: '{key}' is not a currency")

    for area_id, area in mc.AREAS.items():
        grid = area.get("grid") or []
        if not grid:
            failures.append(f"area '{area_id}': no grid")
            continue

        width, height = mc.area_size(area)
        if width > mc.MAX_WIDTH or height > mc.MAX_HEIGHT:
            failures.append(
                f"area '{area_id}': {width}x{height} exceeds "
                f"{mc.MAX_WIDTH}x{mc.MAX_HEIGHT} (wraps on mobile)"
            )
        if len({len(row) for row in grid}) != 1:
            failures.append(f"area '{area_id}': rows are not all the same length")

        # The rendered grid goes into ONE embed field, and Discord
        # truncates a field over 1024 characters without complaining --
        # which on a map means invisible walls rather than a visible
        # error. Measured against the widest glyph any tile can draw.
        widest = max(
            [len(mc.EMOJI_WALL), len(mc.EMOJI_FLOOR), len(mc.EMOJI_PLAYER),
             len(mc.EMOJI_DONE), len(mc.EMOJI_LOCKED)]
            + [len(e.get("emoji", "")) for e in (area.get("legend") or {}).values()]
        )
        rendered = height * (width * widest + 1)
        if rendered > mc.MAX_FIELD_CHARS:
            failures.append(
                f"area '{area_id}': renders to ~{rendered} chars, over Discord's "
                f"{mc.MAX_FIELD_CHARS}-char field limit -- it would be silently truncated"
            )

        # ROOM SIZE. Small connected rooms beat a few big halls: easier to
        # read on a phone, and a journey through named places is what the
        # story actually is.
        walkable_count = len(mc.walkable_tiles(area))
        if walkable_count > mc.MAX_ROOM_TILES:
            failures.append(
                f"area '{area_id}': {walkable_count} walkable tiles (max "
                f"{mc.MAX_ROOM_TILES}) -- split it into connected rooms"
            )
        if not area.get("region"):
            failures.append(
                f"area '{area_id}': no `region` -- every room states where it is, so the "
                f"player always knows both the place and the part of the world it's in"
            )

        # Spawn
        spawns = sum(row.count(mc.SPAWN_CHAR) for row in grid)
        if spawns != 1:
            failures.append(f"area '{area_id}': {spawns} spawn tiles (needs exactly 1)")

        # Legend <-> grid agreement, both directions.
        used = {
            char for row in grid for char in row
            if char not in (mc.WALL_CHAR, mc.FLOOR_CHAR, mc.SPAWN_CHAR)
        }
        legend = area.get("legend") or {}
        for char in sorted(used - set(legend)):
            failures.append(f"area '{area_id}': '{char}' is on the grid with no legend entry")
        for char in sorted(set(legend) - used):
            failures.append(f"area '{area_id}': legend has '{char}', which is on no tile")
        for char in sorted(used):
            count = sum(row.count(char) for row in grid)
            if count > 1:
                failures.append(
                    f"area '{area_id}': '{char}' appears {count} times -- one legend "
                    f"entry cannot describe two different tiles"
                )

        # Contents
        bonus = area.get("completion_bonus")
        if bonus:
            check_grant(f"area '{area_id}' completion_bonus", bonus)

        for char, content in legend.items():
            where = f"area '{area_id}' tile '{char}'"
            kind = content.get("kind")
            emoji = content.get("emoji", "")
            if "️" in emoji:
                failures.append(
                    f"{where}: emoji {emoji!r} contains a variation selector, which "
                    f"renders narrow and shears the column on mobile"
                )
            if not content.get("name"):
                failures.append(f"{where}: no name")

            if kind == "mission":
                mission_id = content.get("mission")
                if sc.get_mission(mission_id) is None:
                    failures.append(f"{where}: no mission named {mission_id!r}")
                else:
                    placed.setdefault(mission_id, []).append(f"{area_id}/{char}")
            elif kind == "note":
                if not content.get("text"):
                    failures.append(f"{where}: note with no text")
            elif kind == "cache":
                if not content.get("grant"):
                    failures.append(f"{where}: cache with nothing in it")
                check_grant(where, content.get("grant") or {})
            elif kind == "hunt":
                enemies = content.get("enemies") or []
                if not enemies:
                    failures.append(f"{where}: hunt with no enemies")
                if len(enemies) > 5:
                    failures.append(f"{where}: {len(enemies)} enemies (engine allows 5)")
                for enemy in enemies:
                    if enemy not in enemy_names:
                        failures.append(f"{where}: no enemy template named {enemy!r}")
                if not isinstance(content.get("level"), int):
                    failures.append(f"{where}: hunt needs an integer level")
                if not content.get("grant"):
                    failures.append(
                        f"{where}: hunt with no reward -- an optional fight that pays "
                        f"nothing is a trap, not a choice"
                    )
                check_grant(where, content.get("grant") or {})
                if "Optional" not in (content.get("text") or ""):
                    failures.append(
                        f"{where}: hunt text must tell the player it's OPTIONAL and that "
                        f"losing is free, or it reads as required content they can fail"
                    )
            elif kind == "exit":
                target = content.get("to_area")
                destination = mc.AREAS.get(target)
                if destination is None:
                    failures.append(f"{where}: exits to unknown area {target!r}")
                else:
                    tx, ty = content.get("to", [None, None])
                    if not isinstance(tx, int) or not isinstance(ty, int):
                        failures.append(f"{where}: exit has no integer [x, y]")
                    elif mc.is_wall(destination, tx, ty):
                        failures.append(f"{where}: exit lands inside a wall at ({tx}, {ty})")
            else:
                failures.append(f"{where}: unknown tile kind {kind!r}")

            needed = content.get("requires_mission")
            if needed and sc.get_mission(needed) is None:
                failures.append(f"{where}: requires unknown mission {needed!r}")

            roster = content.get("requires_characters")
            if roster is not None and (not isinstance(roster, int) or roster < 1):
                failures.append(f"{where}: requires_characters must be a positive int")

            if (needed or roster) and not content.get("locked_text"):
                failures.append(
                    f"{where}: locked with no locked_text -- a door that won't say what "
                    f"opens it is a bug report waiting to happen"
                )

        # Reachability from the spawn, by orthogonal walking.
        walkable = set(mc.walkable_tiles(area))
        spawn = mc.spawn_of(area)
        seen = {spawn}
        queue = deque([spawn])
        while queue:
            x, y = queue.popleft()
            for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
                nxt = (x + dx, y + dy)
                if nxt in walkable and nxt not in seen:
                    seen.add(nxt)
                    queue.append(nxt)
        for x, y in sorted(walkable - seen):
            char = mc.tile_char(area, x, y)
            failures.append(
                f"area '{area_id}': ({x}, {y}) [{char}] is walled off from the spawn"
            )

        # DENSITY. Both halves of the rule.
        content_tiles = [
            (x, y) for (x, y) in walkable if mc.tile_content(area, x, y) is not None
        ]
        if walkable:
            density = len(content_tiles) / len(walkable)
            if density < mc.MIN_DENSITY:
                failures.append(
                    f"area '{area_id}': density {density:.0%} is below "
                    f"{mc.MIN_DENSITY:.0%} ({len(content_tiles)}/{len(walkable)} tiles do "
                    f"something) -- the map is mostly walking"
                )

        if content_tiles:
            # Multi-source BFS out from every interactive tile at once:
            # the distance that matters is to the NEAREST one.
            distance = {tile: 0 for tile in content_tiles}
            queue = deque(content_tiles)
            while queue:
                x, y = queue.popleft()
                for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
                    nxt = (x + dx, y + dy)
                    if nxt in walkable and nxt not in distance:
                        distance[nxt] = distance[(x, y)] + 1
                        queue.append(nxt)
            for tile in sorted(walkable):
                steps = distance.get(tile)
                if steps is None or steps > mc.MAX_DISTANCE_TO_CONTENT:
                    failures.append(
                        f"area '{area_id}': {tile} is {steps if steps is not None else 'infinitely'}"
                        f" steps from anything interactive (max {mc.MAX_DISTANCE_TO_CONTENT})"
                    )

    # Every mission placed exactly once.
    for mission in sc.all_missions():
        where = placed.get(mission["id"], [])
        if not where:
            failures.append(
                f"mission '{mission['id']}' is on no tile -- unreachable now that the "
                f"overworld is the way in"
            )
        elif len(where) > 1:
            failures.append(f"mission '{mission['id']}' is on {len(where)} tiles: {where}")

    # LOCK ORDERING. A tile gated behind a mission that lives further
    # along the same one-way path is a softlock; in the prologue it's an
    # unrecoverable one, since there's nothing else to go and do.
    reachable_missions: set[str] = set()
    frontier = [mc.STARTING_AREA]
    open_areas: set[str] = set()
    progressed = True
    while progressed:
        progressed = False
        for area_id in list(frontier):
            if area_id in open_areas:
                continue
            area = mc.AREAS.get(area_id)
            if area is None:
                continue
            open_areas.add(area_id)
            progressed = True
        for area_id in list(open_areas):
            for content in (mc.AREAS[area_id].get("legend") or {}).values():
                needed = content.get("requires_mission")
                if needed and needed not in reachable_missions:
                    continue
                if content.get("kind") == "mission":
                    if content["mission"] not in reachable_missions:
                        reachable_missions.add(content["mission"])
                        progressed = True
                elif content.get("kind") == "exit":
                    target = content.get("to_area")
                    if target in mc.AREAS and target not in open_areas:
                        frontier.append(target)
                        progressed = True

    for mission in sc.all_missions():
        if placed.get(mission["id"]) and mission["id"] not in reachable_missions:
            failures.append(
                f"mission '{mission['id']}' can never be started -- its tile, or the area "
                f"holding it, is locked behind a mission that isn't reachable first"
            )

    total_tiles = sum(len(mc.walkable_tiles(a)) for a in mc.AREAS.values())
    interactive = sum(
        1 for a in mc.AREAS.values() for (x, y) in mc.walkable_tiles(a)
        if mc.tile_content(a, x, y) is not None
    )
    print(f"areas    : {len(mc.AREAS)}")
    print(f"tiles    : {total_tiles} walkable, {interactive} interactive "
          f"({interactive / total_tiles:.0%} density)" if total_tiles else "tiles    : 0")
    return failures


def main() -> int:
    from bot.database.models.enums import Rarity
    from bot.game.characters.character_seed_data import CHARACTER_TEMPLATES
    from bot.game.combat.enemies import ENEMY_TEMPLATES
    from bot.game.dungeon.encounter_config import get_encounter_by_id
    from bot.game.story import story_config as sc
    from bot.services.currency_service import VALID_CURRENCIES

    enemy_names = {t["name"] for t in ENEMY_TEMPLATES}
    rarities = {r.value for r in Rarity}
    failures: list[str] = []

    missions = sc.all_missions()
    ids = [m["id"] for m in missions]
    for duplicate in {i for i in ids if ids.count(i) > 1}:
        failures.append(f"duplicate mission id: {duplicate}")

    # Every flag anyone READS must be WRITTEN by some choice, or the beat
    # gated on it is unreachable content that looks fine in the file.
    written_flags: set[str] = set()
    for mission in missions:
        for beat in mission["beats"]:
            for option in beat.get("options", []) or []:
                written_flags.update((option.get("sets") or {}).keys())

    character_names = {t["name"] for t in CHARACTER_TEMPLATES}

    def check_grant(where: str, grant: dict) -> None:
        for key, value in (grant or {}).items():
            if key == "item":
                if isinstance(value, str) and value not in rarities:
                    failures.append(f"{where}: item rarity {value!r} does not exist")
            elif key == "character":
                # Validated against the seed data by NAME, because that's
                # what the grant uses -- a renamed or removed character
                # would otherwise fail silently at the moment a player
                # reaches the beat.
                if value not in character_names:
                    failures.append(f"{where}: no character template named {value!r}")
            elif key not in VALID_CURRENCIES:
                failures.append(f"{where}: '{key}' is not a currency")

    for mission in missions:
        name = mission["id"]
        beats = mission.get("beats") or []
        if not beats:
            failures.append(f"{name}: no beats")
        check_grant(f"{name}/rewards", mission.get("rewards") or {})

        if beats and beats[-1].get("kind") == "choice":
            failures.append(
                f"{name}: ends on a choice -- the player picks and sees nothing happen"
            )

        for index, beat in enumerate(beats):
            where = f"{name}[{index}]"
            kind = beat.get("kind")
            if kind not in BEAT_KINDS:
                failures.append(f"{where}: beat kind {kind!r} is not one of {sorted(BEAT_KINDS)}")
                continue

            for flag_name in list(beat.get("requires", [])) + list(beat.get("unless", [])):
                if flag_name not in written_flags:
                    failures.append(
                        f"{where}: gated on flag '{flag_name}', which no choice ever sets"
                    )

            if kind == "dialogue":
                if not beat.get("text"):
                    failures.append(f"{where}: dialogue with no text")
            elif kind == "choice":
                options = beat.get("options") or []
                if not 2 <= len(options) <= 4:
                    failures.append(f"{where}: {len(options)} options (needs 2-4)")
                option_ids = [o.get("id") for o in options]
                if len(set(option_ids)) != len(option_ids):
                    failures.append(f"{where}: duplicate option ids")
                for option in options:
                    if not option.get("label"):
                        failures.append(f"{where}: an option has no label")
            elif kind == "battle":
                enemies = beat.get("enemies") or []
                if not enemies:
                    failures.append(f"{where}: battle with no enemies")
                if len(enemies) > 5:
                    failures.append(f"{where}: {len(enemies)} enemies (engine allows 5)")
                for enemy in enemies:
                    if enemy not in enemy_names:
                        failures.append(f"{where}: no enemy template named {enemy!r}")
                if not isinstance(beat.get("level"), int):
                    failures.append(f"{where}: battle needs an integer level")
            elif kind == "encounter":
                if get_encounter_by_id(beat.get("encounter_id", "")) is None:
                    failures.append(
                        f"{where}: encounter {beat.get('encounter_id')!r} does not exist"
                    )
            elif kind == "reward":
                check_grant(where, beat.get("grant") or {})
            elif kind == "unlock":
                feature = beat.get("feature")
                if feature not in sc.FEATURES:
                    failures.append(f"{where}: unlocks unknown feature {feature!r}")

    # A gated feature with two unlock beats is ambiguous; with zero it's
    # simply ungated (which story_service allows on purpose), so only the
    # duplicate case is an error.
    for feature in sc.FEATURES:
        unlocks = [
            m["id"] for m in missions
            for b in m["beats"]
            if b.get("kind") == "unlock" and b.get("feature") == feature
        ]
        if len(unlocks) > 1:
            failures.append(f"feature '{feature}' is unlocked by more than one mission: {unlocks}")

    failures += _check_maps()

    gated = [f for f in sc.FEATURES if sc.feature_unlocked_by(f)]
    print(f"chapters : {len(sc.CHAPTERS)}")
    print(f"missions : {len(missions)}")
    print(f"beats    : {sum(len(m['beats']) for m in missions)}")
    print(f"flags    : {len(written_flags)} written ({', '.join(sorted(written_flags)) or 'none'})")
    print(f"gated    : {len(gated)}/{len(sc.FEATURES)} features "
          f"({', '.join(sorted(gated)) or 'none'})")

    print()
    if failures:
        for line in dict.fromkeys(failures):
            print(f"  FAIL  {line}")
        return 1
    print("OK -- every beat is runnable and every flag is reachable.")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, ".")
    sys.exit(main())
