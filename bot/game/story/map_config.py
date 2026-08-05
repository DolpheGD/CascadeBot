"""
The story overworld: areas, laid out as grids.

Pure data, same as story_config. The interpreter is
bot/services/map_service.py and knows nothing about any specific area,
which is what lets tools/check_story.py walk every map without a
database.

----------------------------------------------------------------------
THE MAP IS A CONTAINER, MISSIONS ARE THE CONTENTS
----------------------------------------------------------------------
Adding the overworld deliberately did NOT add a second content system.
A tile whose kind is "mission" simply starts a mission from
story_config, which then runs through the beat engine exactly as it did
before the map existed, and hands control back to the map when it ends.

So the prologue's 21 beats were not rewritten to live on the map -- they
were placed on it. That's the whole point of the container/contents
split, and it's why stages 1-2 remain independently playable: rip the
map out and the missions still run.

----------------------------------------------------------------------
AUTHORING FORMAT
----------------------------------------------------------------------
An area is drawn as ASCII, one character per tile, because a map you can
SEE in the source is a map whose density and dead ends are obvious while
you're writing it:

    "grid": [
        "#######",
        "#D.b.J#",
        "#..#..#",
        "#@.c.E#",
        "#######",
    ],

Three characters are built in:

    #   wall (not walkable)
    .   plain floor
    @   the spawn tile (floor; exactly one per area)

Every OTHER character must appear in the area's `legend`, and each one
describes a single tile's contents. Distinct characters for distinct
tiles is enforced by the checker: reusing 'D' for two different NPCs
would silently give them the same dialogue.

A legend entry is:

    kind      "mission" | "note" | "exit"
    emoji     what's drawn on the grid (see EMOJI WIDTH below)
    name      shown when you're standing on it

    mission   (kind="mission") the story_config mission id to start
    text      (kind="note")    flavour text, shown on interact
    to_area   (kind="exit")    area id to travel to
    to        (kind="exit")    [x, y] to arrive at

    requires_mission  optional: the tile is LOCKED until that mission is
                      complete. Used for doors -- this is what makes a
                      map a small puzzle rather than a walk.
    requires_characters
                      optional: locked until the player owns at least N
                      characters. This exists for exactly one reason --
                      the prologue's last fight is unwinnable solo, and
                      the prologue teaches pulling rather than gifting a
                      squadmate. A mission lock can't express "has the
                      player actually done the thing yet", and a tutorial
                      that hands you the reward for a mechanic is a
                      tutorial you can finish without learning it.
    locked_text       what the player is told when it's locked. Always
                      say what would open it; a door that just says "no"
                      is a bug report waiting to happen.

----------------------------------------------------------------------
DENSITY IS THE THING THAT MATTERS
----------------------------------------------------------------------
Every step is a Discord round-trip. If a step usually returns nothing,
movement is pure friction, and that failure mode gets WORSE the larger
the map. So `tools/check_story.py` asserts two things about every area:

  * a minimum fraction of walkable tiles have contents (MIN_DENSITY)
  * no walkable tile is further than MAX_DISTANCE_TO_CONTENT steps from
    something interactive

An area that fails those is a design bug, not a matter of taste. Both
constants live here so the rule and the maps it governs stay together.

----------------------------------------------------------------------
EMOJI WIDTH
----------------------------------------------------------------------
The grid is rendered as emoji in an embed, and mis-matched glyph widths
turn a map into a staircase on mobile. Two rules, both checked:

  * every glyph must come from a fixed-width block (the big coloured
    squares) or be a plain single-codepoint emoji
  * NO variation selectors (U+FE0F). '🗒️' is 🗒 + VS16 and renders
    narrower than 📄 on Android, which is enough to shear a column.

Width past 7 wraps on mobile regardless of what an area "wants", so
that's the hard ceiling.
"""

from __future__ import annotations

# Density rules. See the block comment above -- these are the numbers
# tools/check_story.py enforces.
MIN_DENSITY = 0.28          # fraction of walkable tiles that must do something
MAX_DISTANCE_TO_CONTENT = 2  # in steps, from any walkable tile

# Hard ceiling from Discord's mobile embed width.
MAX_WIDTH = 7
MAX_HEIGHT = 9

# Terrain glyphs. WALL is drawn; FLOOR is deliberately the dimmer of the
# two so contents read as the foreground.
WALL_CHAR = "#"
FLOOR_CHAR = "."
SPAWN_CHAR = "@"

EMOJI_WALL = "⬛"
EMOJI_FLOOR = "⬜"
EMOJI_PLAYER = "🧍"
EMOJI_DONE = "✅"
EMOJI_LOCKED = "🔒"


AREAS: dict[str, dict] = {
    # ==================================================================
    # THE DAILY DOLPHE -- the prologue's hub.
    #
    # Small and dense on purpose: this is the first thing a new player
    # ever walks around in, and it has to teach "move, then interact"
    # in about six steps. Every interior tile touches something.
    #
    # The east door is locked until p3, which is what stops a new player
    # walking straight into the prologue's last fight with a solo
    # level-1 avatar -- a fight measured at 0% win rate that way.
    # ==================================================================
    "daily_dolphe": {
        "name": "The Daily Dolphe",
        "blurb": "What used to be a newspaper. Six desks, four of them empty.",
        "grid": [
            "#######",
            "#D.b.J#",
            "#..#..#",
            "#@cP.E#",
            "#######",
        ],
        "legend": {
            "D": {
                "kind": "mission",
                "emoji": "📰",
                "name": "Dolphe's desk",
                "mission": "p1_answer_the_call",
            },
            "b": {
                "kind": "mission",
                "emoji": "📦",
                "name": "Supply bench",
                "mission": "p2_field_kit",
                "requires_mission": "p1_answer_the_call",
                "locked_text": (
                    "Bee Jee isn't handing out kit to someone who hasn't spoken to Dolphe "
                    "yet. Talk to him at the desk to the west first."
                ),
            },
            "J": {
                "kind": "mission",
                "emoji": "👥",
                "name": "The roster board",
                "mission": "p3_who_else",
                "requires_mission": "p2_field_kit",
                "locked_text": (
                    "Names, photos, and a lot of red string. Bee Jee said to get kitted "
                    "out before you start reading it."
                ),
            },
            "c": {
                "kind": "note",
                "emoji": "📄",
                "name": "Pinned clipping",
                "text": (
                    "**CASCADE INCIDENT — NO CASUALTIES CONFIRMED**\n\n"
                    "A front page from nine days after. Someone has gone over the headline "
                    "in pen, twice, hard enough to tear it.\n\n"
                    "In the margin, in different handwriting: *four hundred and six.*"
                ),
            },
            "P": {
                "kind": "note",
                "emoji": "☕",
                "name": "The good chair",
                "text": (
                    "A chair, a cold coffee, and a sticky note on the armrest.\n\n"
                    "*\"If you're reading this I'm either at the printer or I'm not. "
                    "— B.J.\"*"
                ),
            },
            "E": {
                "kind": "exit",
                "emoji": "🚪",
                "name": "Side entrance",
                "to_area": "the_approach",
                "to": [1, 3],
                "requires_mission": "p3_who_else",
                "requires_characters": 2,
                "locked_text": (
                    "The door out to the loading lane. You could go through it right now "
                    "and get exactly as far as the first person who's waiting.\n\n"
                    "Read the roster board first, then use **`/pull`** and put whoever "
                    "answers into your **`/squad`**. Josh isn't opening this until there's "
                    "more than one of you."
                ),
            },
        },
    },

    # ==================================================================
    # THE APPROACH -- a corridor, not a hub.
    #
    # Deliberately shaped as one path with a single branch. After the
    # newsroom taught free movement, this teaches that the map can
    # CHANNEL you, which is the shape every later chapter's set-pieces
    # will use.
    # ==================================================================
    "the_approach": {
        "name": "The Loading Lane",
        "blurb": "Behind the building. Somebody has been waiting a while.",
        "grid": [
            "#######",
            "#f.t..#",
            "#.###.#",
            "#@.w.X#",
            "#######",
        ],
        "legend": {
            "f": {
                "kind": "note",
                "emoji": "🪜",
                "name": "Fire escape",
                "text": (
                    "The ladder to the roof, padlocked at the bottom rung. The lock is "
                    "new. The rest of it is not.\n\n"
                    "Somebody decided which way out of this building still works."
                ),
            },
            "t": {
                "kind": "note",
                "emoji": "🚚",
                "name": "Delivery truck",
                "text": (
                    "The Daily Dolphe's last delivery truck, up on blocks with the tyres "
                    "gone.\n\n"
                    "The side panel still reads THE TRUTH, DAILY. Under it, scratched in "
                    "with a key: *not lately.*"
                ),
            },
            "w": {
                "kind": "note",
                "emoji": "🚨",
                "name": "Xendium marker",
                "text": (
                    "A survey stake driven into the concrete, tagged with a company "
                    "sigil you don't recognise and a date three weeks out.\n\n"
                    "Somebody has already scheduled what happens to this building."
                ),
            },
            "X": {
                "kind": "mission",
                "emoji": "🥊",
                "name": "The lane's end",
                "mission": "p4_the_approach",
            },
        },
    },
}


# Which area a new player starts in, and where.
STARTING_AREA = "daily_dolphe"


# ----------------------------------------------------------------------
# Lookups.
# ----------------------------------------------------------------------

def get_area(area_id: str) -> dict | None:
    return AREAS.get(area_id)


def area_size(area: dict) -> tuple[int, int]:
    """(width, height). Width is taken from the widest row so a ragged
    grid is a checker failure rather than a silent index error."""
    grid = area["grid"]
    return (max(len(row) for row in grid), len(grid))


def tile_char(area: dict, x: int, y: int) -> str | None:
    """The raw character at (x, y), or None if off-grid."""
    grid = area["grid"]
    if not (0 <= y < len(grid)):
        return None
    row = grid[y]
    if not (0 <= x < len(row)):
        return None
    return row[x]


def is_wall(area: dict, x: int, y: int) -> bool:
    char = tile_char(area, x, y)
    return char is None or char == WALL_CHAR


def tile_content(area: dict, x: int, y: int) -> dict | None:
    """The legend entry for (x, y), if the tile has one."""
    char = tile_char(area, x, y)
    if char is None or char in (WALL_CHAR, FLOOR_CHAR, SPAWN_CHAR):
        return None
    return area.get("legend", {}).get(char)


def spawn_of(area: dict) -> tuple[int, int]:
    for y, row in enumerate(area["grid"]):
        x = row.find(SPAWN_CHAR)
        if x != -1:
            return (x, y)
    # Checked by tools/check_story.py, so reaching this means the checker
    # was skipped -- fall back to the first walkable tile rather than
    # stranding the player off-grid.
    for y, row in enumerate(area["grid"]):
        for x, char in enumerate(row):
            if char != WALL_CHAR:
                return (x, y)
    return (0, 0)


def walkable_tiles(area: dict) -> list[tuple[int, int]]:
    width, height = area_size(area)
    return [
        (x, y)
        for y in range(height)
        for x in range(width)
        if not is_wall(area, x, y)
    ]


def missions_in(area_id: str) -> list[str]:
    area = AREAS.get(area_id) or {}
    return [
        entry["mission"]
        for entry in (area.get("legend") or {}).values()
        if entry.get("kind") == "mission"
    ]


def area_of_mission(mission_id: str) -> str | None:
    for area_id in AREAS:
        if mission_id in missions_in(area_id):
            return area_id
    return None
