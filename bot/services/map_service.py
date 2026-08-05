"""
The overworld interpreter: where you are, where you can go, what's here.

Knows nothing about any specific area. Everything it moves through comes
from bot/game/story/map_config.py, so tools/check_story.py can walk every
map exhaustively without a database.

----------------------------------------------------------------------
WHAT THIS DELIBERATELY DOESN'T DO
----------------------------------------------------------------------
It does not run content. Stepping onto a mission tile returns a
descriptor saying "this tile would start p1_answer_the_call"; STARTING it
is story_service's job, through the same `start_mission` a linear player
used before the map existed.

That split is the reason the map was cheap to add. The map answers
"where", the beat engine answers "what happens", and neither imports the
other. It's also what keeps stages 1-2 independently playable: delete
this module and every mission still runs.

----------------------------------------------------------------------
MOVEMENT IS ONE TILE, ORTHOGONAL, AND ALWAYS CHEAP
----------------------------------------------------------------------
No diagonals, no pathfinding, no multi-tile moves. Every move is a
bounds check and a wall check, which means a move can never fail in a way
that needs explaining -- the direction button simply isn't offered when
the tile is a wall. A greyed-out button is a better answer than an error
message the player has to read.
"""

from __future__ import annotations

from bot.game.story import map_config as mc
from bot.game.story import story_config as sc


class MapError(Exception):
    """Any reason a map action can't proceed, phrased for the player."""


# (dx, dy) in grid coordinates: y grows DOWNWARD, because that's the
# order the grid rows are written in and matching the source beats
# matching a maths convention nobody is looking at.
DIRECTIONS: dict[str, tuple[int, int]] = {
    "north": (0, -1),
    "south": (0, 1),
    "west": (-1, 0),
    "east": (1, 0),
}

DIRECTION_LABELS = {
    "north": "⬆️", "south": "⬇️", "west": "⬅️", "east": "➡️",
}


# ----------------------------------------------------------------------
# Position
# ----------------------------------------------------------------------

def ensure_placed(db, story) -> tuple[str, int, int]:
    """Where the player is, spawning them if they've never been placed.

    A story row created before the overworld shipped has `area` NULL, and
    so does a brand-new one. Both mean the same thing and get the same
    treatment, which is why this is a single code path rather than a
    migration.
    """
    if story.area and mc.get_area(story.area) is not None:
        return (story.area, story.pos_x, story.pos_y)

    area_id = mc.STARTING_AREA
    spawn_x, spawn_y = mc.spawn_of(mc.get_area(area_id))
    story.area, story.pos_x, story.pos_y = area_id, spawn_x, spawn_y
    _mark_visited(story, area_id, spawn_x, spawn_y)
    db.commit()
    return (area_id, spawn_x, spawn_y)


def current_area(db, story) -> dict:
    area_id, _, _ = ensure_placed(db, story)
    return mc.get_area(area_id)


def _mark_visited(story, area_id: str, x: int, y: int) -> None:
    # JSON columns are reassigned wholesale, never mutated in place --
    # SQLAlchemy does not detect a mutation inside a JSON value and the
    # write is silently lost on commit.
    visited = dict(story.visited or {})
    seen = [tuple(pair) for pair in visited.get(area_id, [])]
    if (x, y) not in seen:
        seen.append((x, y))
        visited[area_id] = [list(pair) for pair in seen]
        story.visited = visited


def has_read(story, area_id: str, char: str) -> bool:
    return char in (story.read_tiles or {}).get(area_id, [])


def mark_read(db, story, area_id: str, char: str) -> None:
    read = dict(story.read_tiles or {})
    chars = list(read.get(area_id, []))
    if char not in chars:
        chars.append(char)
        read[area_id] = chars
        story.read_tiles = read
        db.commit()


# ----------------------------------------------------------------------
# Locks
# ----------------------------------------------------------------------

def roster_size(db, story) -> int:
    """How many characters the player owns."""
    from bot.database.models.character_model import PlayerCharacter

    return (
        db.query(PlayerCharacter)
        .filter_by(player_id=story.player_id)
        .count()
    )


def tile_locked(db, story, content: dict | None) -> bool:
    """Whether a tile's requirements are unmet.

    Two kinds of lock, and the split matters:

      * `requires_mission` reads from COMPLETED MISSIONS, never from
        flags. A flag can be set by a choice the player didn't
        understand; a completed mission is unambiguous, so a locked door
        can always be explained in one sentence without the writer
        tracking which flag implied what.

      * `requires_characters` reads the actual roster. This is the guard
        that lets the prologue TEACH pulling instead of gifting a
        squadmate -- the last fight is unwinnable solo, and "has the
        player pulled yet" is a question no mission lock can answer.
    """
    if not content:
        return False

    needed = content.get("requires_mission")
    if needed and needed not in (story.completed_missions or []):
        return True

    minimum = content.get("requires_characters")
    if minimum and roster_size(db, story) < int(minimum):
        return True

    return False


def lock_message(content: dict) -> str:
    explicit = content.get("locked_text")
    if explicit:
        return explicit
    needed = content.get("requires_mission")
    mission = sc.get_mission(needed) if needed else None
    if mission:
        return f"Locked. You need to finish **{mission['name']}** first."
    minimum = content.get("requires_characters")
    if minimum:
        return (
            f"Locked. You need at least **{minimum} characters** before you go through "
            f"here — use `/pull`, then `/squad`."
        )
    return "Locked."


# ----------------------------------------------------------------------
# Movement
# ----------------------------------------------------------------------

def available_directions(db, story) -> list[str]:
    """Which of the four moves land on a non-wall tile.

    Locked tiles are still WALKABLE -- you can stand on a locked door and
    be told why it won't open. Being unable to approach a door at all
    reads as a missing map, not a locked one.
    """
    area_id, x, y = ensure_placed(db, story)
    area = mc.get_area(area_id)
    return [
        name for name, (dx, dy) in DIRECTIONS.items()
        if not mc.is_wall(area, x + dx, y + dy)
    ]


def move(db, story, direction: str) -> dict:
    """Take one step. Returns the same descriptor shape as `look`."""
    if direction not in DIRECTIONS:
        raise MapError("That isn't a direction.")
    area_id, x, y = ensure_placed(db, story)
    area = mc.get_area(area_id)
    dx, dy = DIRECTIONS[direction]
    nx, ny = x + dx, y + dy

    if mc.is_wall(area, nx, ny):
        raise MapError("There's a wall that way.")

    story.pos_x, story.pos_y = nx, ny
    _mark_visited(story, area_id, nx, ny)
    db.commit()
    return look(db, story)


def travel(db, story, to_area: str, to: list[int] | tuple[int, int]) -> dict:
    """Move through an exit into another area."""
    area = mc.get_area(to_area)
    if area is None:
        raise MapError("That way leads nowhere yet.")
    x, y = int(to[0]), int(to[1])
    if mc.is_wall(area, x, y):
        # An exit pointing into a wall is an authoring error that
        # check_story catches, but arriving inside one would strand the
        # player with no legal move, so fall back to the spawn.
        x, y = mc.spawn_of(area)
    story.area, story.pos_x, story.pos_y = to_area, x, y
    _mark_visited(story, to_area, x, y)
    db.commit()
    return look(db, story)


# ----------------------------------------------------------------------
# Looking
# ----------------------------------------------------------------------

def look(db, story) -> dict:
    """Everything the UI needs about where the player is standing.

        {
          "area_id", "area", "x", "y",
          "content":  legend entry or None,
          "char":     the tile's grid character,
          "locked":   bool,
          "done":     mission on this tile is already complete,
          "directions": [...],
        }
    """
    area_id, x, y = ensure_placed(db, story)
    area = mc.get_area(area_id)
    content = mc.tile_content(area, x, y)
    completed = story.completed_missions or []
    return {
        "area_id": area_id,
        "area": area,
        "x": x,
        "y": y,
        "char": mc.tile_char(area, x, y),
        "content": content,
        "locked": tile_locked(db, story, content),
        "done": bool(
            content
            and content.get("kind") == "mission"
            and content.get("mission") in completed
        ),
        "directions": available_directions(db, story),
    }


def interact(db, story) -> dict:
    """Resolve the tile the player is standing on.

    Returns one of:
        {"kind": "nothing"}
        {"kind": "locked",  "text": ...}
        {"kind": "note",    "name":, "text": ...}
        {"kind": "exit",    "to_area":, "to": ...}
        {"kind": "mission", "mission":, "replay": bool}

    Note it does NOT start the mission. The cog does, via story_service,
    so that map-started and menu-started missions go through identical
    code -- a second start path is a second place for the beat index to
    get out of step.
    """
    state = look(db, story)
    content = state["content"]
    if not content:
        return {"kind": "nothing"}

    if state["locked"]:
        return {"kind": "locked", "text": lock_message(content)}

    kind = content.get("kind")

    if kind == "note":
        mark_read(db, story, state["area_id"], state["char"])
        return {
            "kind": "note",
            "name": content.get("name", "Something here"),
            "emoji": content.get("emoji", ""),
            "text": content.get("text", ""),
        }

    if kind == "exit":
        return {
            "kind": "exit",
            "name": content.get("name", "A way out"),
            "to_area": content["to_area"],
            "to": content["to"],
        }

    if kind == "mission":
        return {
            "kind": "mission",
            "name": content.get("name", "Something here"),
            "mission": content["mission"],
            "replay": state["done"],
        }

    return {"kind": "nothing"}


# ----------------------------------------------------------------------
# Rendering
# ----------------------------------------------------------------------

def render(db, story) -> str:
    """The grid, as one emoji per tile.

    The player marker REPLACES whatever is under it rather than being
    drawn beside it -- the embed says what you're standing on in words
    directly underneath, and two sources of truth for the same tile is
    how you get a map that disagrees with itself.
    """
    area_id, px, py = ensure_placed(db, story)
    area = mc.get_area(area_id)
    completed = story.completed_missions or []
    width, height = mc.area_size(area)

    rows: list[str] = []
    for y in range(height):
        row = ""
        for x in range(width):
            if (x, y) == (px, py):
                row += mc.EMOJI_PLAYER
                continue
            if mc.is_wall(area, x, y):
                row += mc.EMOJI_WALL
                continue
            content = mc.tile_content(area, x, y)
            if not content:
                row += mc.EMOJI_FLOOR
            elif tile_locked(db, story, content):
                row += mc.EMOJI_LOCKED
            elif content.get("kind") == "mission" and content["mission"] in completed:
                row += mc.EMOJI_DONE
            else:
                row += content.get("emoji", mc.EMOJI_FLOOR)
        rows.append(row)
    return "\n".join(rows)


def legend_lines(db, story) -> list[str]:
    """A short "what's on this map" list to sit under the grid.

    This is the part that makes the grid legible. An emoji map alone is a
    puzzle about emoji; the same map with four labelled entries is a
    place. Completed and locked tiles stay listed rather than vanishing,
    so the player can see the shape of what they've done.
    """
    area_id, _, _ = ensure_placed(db, story)
    area = mc.get_area(area_id)
    completed = story.completed_missions or []

    lines: list[str] = []
    for char, content in (area.get("legend") or {}).items():
        if content.get("kind") == "note" and has_read(story, area_id, char):
            continue  # already read; stop advertising it
        emoji = content.get("emoji", "")
        name = content.get("name", char)
        if tile_locked(db, story, content):
            lines.append(f"{mc.EMOJI_LOCKED} {name} — locked")
        elif content.get("kind") == "mission" and content["mission"] in completed:
            lines.append(f"{mc.EMOJI_DONE} {name} — done")
        else:
            lines.append(f"{emoji} {name}")
    return lines
