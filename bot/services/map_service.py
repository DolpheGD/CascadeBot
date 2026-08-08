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


# ----------------------------------------------------------------------
# NPCs -- people you can talk to more than once.
# ----------------------------------------------------------------------
# A tile that says one fixed line forever is scenery with a face. What
# makes a hub feel inhabited is that the same person has something new to
# say after you've done something, and something ordinary to say when
# they don't.
#
# An `npc` legend entry looks like:
#
#     "J": {
#         "kind": "npc", "emoji": "🤖", "name": "Jofrog",
#         "lines": [
#             {"text": "First thing he says."},
#             {"text": "Only once you've met Josh.",
#              "requires_flag": "c1_met_josh"},
#             {"text": "Only BEFORE you've met Josh.",
#              "unless_flag": "c1_met_josh"},
#         ],
#         "repeat": "What he says when there's nothing new.",
#         "quest": True,          # optional -- puts ❗ on the legend
#     }
#
# Lines are delivered in order, one per interaction, skipping any whose
# flag conditions aren't met. When they run out, `repeat` is used
# forever. A line that becomes available LATER (its flag gets set) is
# picked up then -- which is the whole point, and why this is ordered
# rather than random.
# ----------------------------------------------------------------------

def _line_available(story, line: dict) -> bool:
    flags = story.flags or {}
    required = line.get("requires_flag")
    if required and not flags.get(required):
        return False
    blocked = line.get("unless_flag")
    if blocked and flags.get(blocked):
        return False
    return True


def npc_line(db, story, area_id: str, char: str, content: dict) -> tuple[str, int | None, bool]:
    """(text, line index or None, exhausted).

    A None index means nothing new was said -- the repeat line -- and so
    nothing needs marking as read.
    """
    for index, line in enumerate(content.get("lines") or []):
        if has_read(story, area_id, f"{char}#{index}"):
            continue
        if not _line_available(story, line):
            continue
        return line.get("text", ""), index, False
    fallback = content.get("repeat") or "They don't have anything else to say right now."
    return fallback, None, True


def npc_has_new_line(db, story, area_id: str, char: str, content: dict) -> bool:
    """Whether this NPC has something unheard to say -- drives the ❗."""
    _, index, _ = npc_line(db, story, area_id, char, content)
    return index is not None


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

    if kind == "station":
        # A STATION is a tile that opens a real game panel -- the forge
        # bench opens the Forge, the map table opens Cascade HQ.
        #
        # The map already knows where everything is; before this, walking
        # up to the forge and then typing `/forge` was the player doing
        # the map's job for it. The panel opens ephemerally so the map
        # stays exactly where it was underneath.
        #
        # The tile carries the FEATURE it needs, so a station the story
        # hasn't unlocked yet refuses the same way the command would
        # rather than opening a panel for a system nobody has explained.
        return {
            "kind": "station",
            "name": content.get("name", "Terminal"),
            "emoji": content.get("emoji", ""),
            "panel": content.get("panel"),
            "feature": content.get("feature"),
        }

    if kind == "npc":
        line, index, exhausted = npc_line(db, story, state["area_id"], state["char"], content)
        if index is not None:
            # Per-LINE read state, keyed "char#index", so an NPC can be
            # talked to repeatedly and say something different each time.
            # read_tiles is already a per-area list of strings, so this
            # needs no schema change and no migration.
            mark_read(db, story, state["area_id"], f"{state['char']}#{index}")
        return {
            "kind": "note",  # rendered identically -- it's a readout on the map
            "name": content.get("name", "Someone"),
            "emoji": content.get("emoji", ""),
            "text": line,
            "exhausted": exhausted,
            "bonus": _completion_bonus_if_due(db, story, state["area_id"]),
        }

    if kind == "note":
        mark_read(db, story, state["area_id"], state["char"])
        return {
            "kind": "note",
            "name": content.get("name", "Something here"),
            "emoji": content.get("emoji", ""),
            "text": content.get("text", ""),
            "bonus": _completion_bonus_if_due(db, story, state["area_id"]),
        }

    if kind == "cache":
        if has_read(story, state["area_id"], state["char"]):
            return {"kind": "spent", "text": "You've already taken everything here."}
        mark_read(db, story, state["area_id"], state["char"])
        return {
            "kind": "cache",
            "name": content.get("name", "A cache"),
            "emoji": content.get("emoji", ""),
            "text": content.get("text", ""),
            "rewards": _grant(db, story, content.get("grant") or {}),
            "bonus": _completion_bonus_if_due(db, story, state["area_id"]),
        }

    if kind == "hunt":
        if has_read(story, state["area_id"], state["char"]):
            return {"kind": "spent", "text": "Whatever was here, you already dealt with it."}
        return {
            "kind": "hunt",
            "name": content.get("name", "Something waiting"),
            "emoji": content.get("emoji", ""),
            "text": content.get("text", ""),
            "enemies": content["enemies"],
            "level": content["level"],
            "char": state["char"],
            "area_id": state["area_id"],
        }

    if kind == "exit":
        return {
            "kind": "exit",
            "name": content.get("name", "A way out"),
            "to_area": content["to_area"],
            "to": content["to"],
        }

    if kind == "mission":
        mission = sc.get_mission(content["mission"]) or {}
        if state["done"] and not mission.get("repeatable"):
            # Refused HERE as well as in start_mission. The service call
            # is the real guard; this one exists so the UI can say
            # something specific instead of surfacing an exception, and
            # so the button can be disabled before it's ever pressed.
            return {
                "kind": "done",
                "name": content.get("name", "Something here"),
                "text": (
                    f"**{mission.get('name', 'That')}** is already behind you.\n\n"
                    "Story missions run once. If you want to fight something again, "
                    "that's what `/adventure`, `/domains` and `/raid` are for."
                ),
            }
        return {
            "kind": "mission",
            "name": content.get("name", "Something here"),
            "mission": content["mission"],
            "replay": state["done"],
        }

    return {"kind": "nothing"}


# ----------------------------------------------------------------------
# Optional content
# ----------------------------------------------------------------------

def _grant(db, story, grant: dict) -> list[str]:
    """Pay out through the STORY's grant block, not a second copy of it.

    One place in the codebase knows how to turn a reward dict into things
    a player owns; a parallel implementation here would drift the moment
    either side gained a currency."""
    if not grant:
        return []
    from bot.services import player_service, story_service

    player = player_service.get_player(db, story.player_id)
    if player is None:
        return []
    return story_service._grant(db, player, grant)


def interactive_chars(area: dict) -> set[str]:
    """Every tile in the area a player can DO something with.

    Exits are excluded: walking through a door is not engagement with the
    area, it's leaving it.

    NPCs are excluded too, and for a subtler reason: they are never
    finished. A flag set three missions later can give someone a new line,
    which would take a COMPLETED area back to incomplete and either
    re-award its bonus or leave a permanent unfinished mark. Completion
    is about the tiles you can exhaust; people aren't tiles you exhaust."""
    return {
        char for char, content in (area.get("legend") or {}).items()
        if content.get("kind") in ("note", "cache", "hunt")
    }


def area_complete(story, area_id: str) -> bool:
    area = mc.get_area(area_id)
    if area is None:
        return False
    wanted = interactive_chars(area)
    if not wanted:
        return False
    done = set((story.read_tiles or {}).get(area_id, []))
    return wanted.issubset(done)


def _completion_bonus_if_due(db, story, area_id: str) -> list[str]:
    """Pay the area's completion bonus the moment its last tile is used.

    Tracked with a sentinel char in read_tiles rather than a new column --
    '*' can never collide with a grid character, since the grid only ever
    holds legend keys."""
    area = mc.get_area(area_id)
    bonus = (area or {}).get("completion_bonus")
    if not bonus or not area_complete(story, area_id):
        return []
    if has_read(story, area_id, "*"):
        return []
    mark_read(db, story, area_id, "*")
    return _grant(db, story, bonus)


def finish_hunt(db, story, area_id: str, char: str, won: bool) -> list[str]:
    """Resolve an optional fight. Losing costs nothing at all."""
    story.pending_hunt = None
    db.commit()
    if not won:
        return []
    area = mc.get_area(area_id) or {}
    content = (area.get("legend") or {}).get(char) or {}
    mark_read(db, story, area_id, char)
    rewards = _grant(db, story, content.get("grant") or {})
    return rewards + _completion_bonus_if_due(db, story, area_id)


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
            # Decoration is checked BEFORE is_wall, because is_wall now
            # counts it as solid -- otherwise every tree would render as
            # a plain black block and the whole point of decorating
            # would be lost.
            if mc.is_decor(area, x, y):
                row += (mc.tile_content_raw(area, x, y) or {}).get("emoji", mc.EMOJI_WALL)
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
            elif (content.get("kind") in ("cache", "hunt")
                  and has_read(story, area_id, mc.tile_char(area, x, y))):
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

    # ESSENTIALS ONLY.
    #
    # The legend answers "what is there to DO here", not "what objects
    # exist here". A restraint frame, a burning panel, a tree -- these
    # are things you find by walking onto them, and listing them turns a
    # four-line orientation aid back into the wall of text this was
    # trimmed from once already. Worse, it buries the two entries that
    # actually matter among scenery that doesn't.
    #
    # So: missions and exits, which are how you make progress, plus
    # hunts, which are an optional FIGHT and therefore a decision worth
    # knowing about before you step on it. Notes, caches and decoration
    # are discoverable, which is what the map is for.
    LISTED_KINDS = {"mission", "exit", "hunt", "npc"}

    priority = {"mission": 0, "npc": 1, "exit": 2, "hunt": 3}
    entries = sorted(
        ((char, content) for char, content in (area.get("legend") or {}).items()
         if content.get("kind") in LISTED_KINDS),
        key=lambda kv: priority.get(kv[1].get("kind"), 9),
    )

    lines: list[str] = []
    for char, content in entries:
        if content.get("kind") == "hunt" and has_read(story, area_id, char):
            continue  # already fought; stop advertising it
        if len(lines) >= mc.MAX_LEGEND_LINES and content.get("kind") not in ("mission", "exit"):
            continue
        emoji = content.get("emoji", "")
        name = content.get("name", char)
        if tile_locked(db, story, content):
            lines.append(f"{mc.EMOJI_LOCKED} {name} — locked")
        elif content.get("kind") == "mission" and content["mission"] in completed:
            lines.append(f"{mc.EMOJI_DONE} {name} — done")
        else:
            # THE QUEST MARKER. A tile that will actually move the story
            # forward is suffixed with ❗ so the player can tell it apart
            # from scenery at a glance -- the thing every RPG hub does,
            # and the thing a grid of emoji most needs, since the map
            # itself can't distinguish "person with a job for you" from
            # "person". Suffixed rather than replacing the tile's own
            # emoji, so the legend entry still matches what's drawn.
            marker = (f" {mc.EMOJI_QUEST}"
                      if _is_quest(db, story, area_id, char, content) else "")
            lines.append(f"{emoji} {name}{marker}")
    return lines


def _is_quest(db, story, area_id: str, char: str, content: dict) -> bool:
    """Whether this tile has something for the player RIGHT NOW.

    Missions are the obvious case. An NPC qualifies while they still
    have an unheard line -- which is the marker doing its real job: it
    goes away once you've talked to them, and comes BACK when a flag
    unlocks something new to say, so the hub tells you where to go
    without you having to re-canvass every room.

    Exits deliberately never qualify: they're how you leave, not
    something to do, and marking every doorway defeats the point.
    """
    kind = content.get("kind")
    if kind == "mission":
        return True
    if kind == "npc":
        return npc_has_new_line(db, story, area_id, char, content)
    return False
