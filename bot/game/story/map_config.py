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

----------------------------------------------------------------------
SIZE
----------------------------------------------------------------------
The width ceiling was 7, guessed from "past roughly 7 it wraps badly on
mobile". Measured on an actual phone it comfortably fits 12 and will
take 14 if you push it -- so the real constraint was never the guess, it
was that nobody had looked. MAX_WIDTH is 13: one under the generous
number, so an area that renders fine on a roomy phone doesn't shear on a
narrow one.

The ceiling that actually bites now is Discord's **1024-character embed
field limit**, since the whole grid goes in one field. An emoji like ⬛
is a single codepoint, so a 13x12 grid is ~168 characters -- nowhere
near it -- but the limit is asserted in tools/check_story.py anyway,
because a silently truncated map is a map with invisible walls.

One caveat that shapes layouts: the embed's top-right is where a
thumbnail would go, so a wide area's first rows should not carry
anything the player must see. Top-LEFT is safe.
"""

from __future__ import annotations

# Density rules. See the block comment above -- these are the numbers
# tools/check_story.py enforces.
MIN_DENSITY = 0.28          # fraction of walkable tiles that must do something
MAX_DISTANCE_TO_CONTENT = 2  # in steps, from any walkable tile

# Measured on a phone, not guessed: 12 across is comfortable, 14 is
# pushing it. 13 leaves a margin for narrower devices.
MAX_WIDTH = 13
MAX_HEIGHT = 12

# Discord's per-field ceiling. The grid occupies one field on its own.
MAX_FIELD_CHARS = 1024

# Terrain glyphs. WALL is drawn; FLOOR is deliberately the dimmer of the
# two so contents read as the foreground.
WALL_CHAR = "#"
FLOOR_CHAR = "."
SPAWN_CHAR = "@"

EMOJI_WALL = "⬛"
EMOJI_FLOOR = "⬜"
# The player marker is a CAT. This is a lore thing.
EMOJI_PLAYER = "🐱"
EMOJI_DONE = "✅"
EMOJI_LOCKED = "🔒"


AREAS: dict[str, dict] = {
    # ==================================================================
    # THE DAILY DOLPHE -- the prologue's hub.
    #
    # 13x7, two rooms joined by a single gap in the middle wall. It was
    # 7x5 when the width ceiling was a guess; measured on a phone, 13
    # fits, so the newsroom is now a place with a layout rather than a
    # corridor with furniture.
    #
    # The extra room is spent almost entirely on NOTES, not on floor.
    # Sparseness is what kills a grid map in a button UI, so a bigger
    # area has to buy its size with things to find -- here that's the
    # empty desks, which do more worldbuilding than another line of
    # dialogue would.
    #
    # The east door is locked until p3 AND until the player owns two
    # characters -- the prologue's last fight is unwinnable solo.
    # ==================================================================
    "daily_dolphe": {
        "name": "The Daily Dolphe",
        "blurb": "What used to be a newspaper. Six desks, four of them empty.",
        "grid": [
            "#############",
            "#D.c.t#.b.k.#",
            "#..P..#..q..#",
            "#..w.y...n.g#",
            "#####.#.....#",
            "#@.v.f#.J.rE#",
            "#############",
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
                    "yet. Talk to her at the desk in the west room first."
                ),
            },
            "n": {
                "kind": "mission",
                "emoji": "📌",
                "name": "The corkboard",
                "mission": "p2b_the_corkboard",
                "requires_mission": "p2_field_kit",
                "locked_text": (
                    "Nexus is standing in front of it with his arms out. \"It's not "
                    "*ready*. Come back when you've got your kit on, you'll photograph "
                    "better.\""
                ),
            },
            "J": {
                "kind": "mission",
                "emoji": "👥",
                "name": "The roster board",
                "mission": "p3_who_else",
                "requires_mission": "p2b_the_corkboard",
                "locked_text": (
                    "Names, photos, and a lot of load-bearing string. Nexus would like a "
                    "word before you start reading it."
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
            "t": {
                "kind": "note",
                "emoji": "☎",
                "name": "The phone bank",
                "text": (
                    "Six handsets. One of them has a tally scratched into the plastic "
                    "beside it, six marks deep.\n\n"
                    "Six calls. Six messages. You didn't answer any of them, and she kept "
                    "the count anyway."
                ),
            },
            "w": {
                "kind": "note",
                "emoji": "🪟",
                "name": "The window",
                "text": (
                    "Ground floor, facing the street. Somebody has taped cardboard over "
                    "the lower half from the inside.\n\n"
                    "The tape is fresh. Whatever they're blocking the view of, it's a "
                    "recent problem."
                ),
            },
            "v": {
                "kind": "note",
                "emoji": "🖨",
                "name": "The press",
                "text": (
                    "The Daily Dolphe's printer, still warm, still loaded.\n\n"
                    "The last plate in the tray was never run. It's a single page, one "
                    "column, four hundred and six names in eight-point type."
                ),
            },
            "f": {
                "kind": "note",
                "emoji": "🗄",
                "name": "Filing cabinet",
                "text": (
                    "Drawer three is labelled GLACIER 15 and opens six inches before it "
                    "hits something.\n\n"
                    "It's empty. The obstruction is a second lock, fitted to the *inside* "
                    "of the drawer, by somebody who wanted it to look like it just stuck."
                ),
            },
            "k": {
                "kind": "note",
                "emoji": "🍜",
                "name": "The kettle corner",
                "text": (
                    "A hotplate, a stack of chipped bowls, and a laminated sign reading "
                    "**IF YOU EAT THE LAST ONE YOU REPLACE THE LAST ONE.**\n\n"
                    "Underneath, in marker: *this means you, Nexus.* And under that, in "
                    "different marker: *I have never once done this.*"
                ),
            },
            "q": {
                "kind": "note",
                "emoji": "🪑",
                "name": "Empty desks",
                "text": (
                    "Four desks nobody has cleared. A cardigan on one chair. A half-done "
                    "crossword under a mug ring.\n\n"
                    "Nothing has been packed up, because packing up would mean deciding "
                    "something. Nobody in this building is ready to decide it."
                ),
            },
            "r": {
                "kind": "note",
                "emoji": "🧯",
                "name": "Fire door",
                "text": (
                    "Chained. Not by the landlord — the chain is threaded from the inside "
                    "and there's a bolt-cutter propped against the frame, ready.\n\n"
                    "Somebody in here has already thought carefully about the difference "
                    "between keeping people out and getting people out."
                ),
            },
            "y": {
                # Sits IN the gap between the two rooms. Every player
                # crosses this tile, and before it had contents it was
                # the one square on the map more than two steps from
                # anything -- the checker found it, which is exactly the
                # kind of dead spot that's invisible when you're looking
                # at the ASCII and thinking about rooms.
                "kind": "note",
                "emoji": "🚪",
                "name": "The partition gap",
                "text": (
                    "There was a door here once. You can see the hinge screws, and the "
                    "lighter rectangle on the floor where it used to swing.\n\n"
                    "Somebody took it off and never put it back. In a building this "
                    "nervous, that's almost aggressive optimism."
                ),
            },
            "g": {
                "kind": "note",
                "emoji": "🗃",
                "name": "The archive",
                "text": (
                    "Ninety years of a newspaper, boxed and labelled by decade.\n\n"
                    "The last box is labelled with this year and a question mark."
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
    # THE LOADING LANE -- a corridor, not a hub.
    #
    # After the newsroom taught free movement, this teaches that the map
    # can CHANNEL you. One path, one branch, and the branch is scenery.
    # ==================================================================
    "the_approach": {
        "name": "The Loading Lane",
        "blurb": "Behind the building. Somebody has been waiting a while.",
        "grid": [
            "###########",
            "#l.t...s..#",
            "#.###.###.#",
            "#@.w.p..XE#",
            "###########",
        ],
        "legend": {
            "l": {
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
            "s": {
                "kind": "note",
                "emoji": "🛰",
                "name": "Rooftop antenna",
                "text": (
                    "Visible over the parapet: an antenna array far too good for this "
                    "building, guyed down with climbing rope.\n\n"
                    "Somebody competent built that in a hurry, out of whatever was to "
                    "hand. You'll meet her later."
                ),
            },
            "w": {
                "kind": "note",
                "emoji": "🚨",
                "name": "Xendium marker",
                "text": (
                    "A survey stake driven into the concrete, tagged with a company sigil "
                    "you don't recognise and a date three weeks out.\n\n"
                    "Somebody has already scheduled what happens to this building."
                ),
            },
            "p": {
                "kind": "note",
                "emoji": "🚬",
                "name": "Scuffed ground",
                "text": (
                    "Two sets of boot prints in the grit, facing the door. They've been "
                    "here long enough to have shifted their weight a few times.\n\n"
                    "Whoever they are, they're not passing through. They're waiting for "
                    "somebody to come out."
                ),
            },
            "X": {
                "kind": "mission",
                "emoji": "🥊",
                "name": "The lane's end",
                "mission": "p4_the_approach",
            },
            "E": {
                "kind": "exit",
                "emoji": "🚪",
                "name": "The basement stair",
                "to_area": "the_signal_room",
                "to": [1, 5],
                "requires_mission": "p4_the_approach",
                "locked_text": (
                    "A stairwell down, propped open with a brick. Josh is standing between "
                    "you and it, watching the two at the end of the lane.\n\n"
                    "\"Not past them. Through them.\""
                ),
            },
        },
    },

    # ==================================================================
    # THE SIGNAL ROOM -- the prologue's third act, and the first place
    # the player is somewhere that belongs to them.
    #
    # Deliberately the widest area: it's the one the player will come
    # back to. The three missions sit far apart on purpose so the room
    # has to be crossed rather than glanced at.
    # ==================================================================
    "the_signal_room": {
        "name": "The Signal Room",
        "blurb": "A basement, an antenna, and a car battery telling lies.",
        "grid": [
            "#############",
            "#V.b...M.d.a#",
            "#.....#.....#",
            "#.c.z.#.m.u.#",
            "###.###.###.#",
            "#@.eh...T..j#",
            "#############",
        ],
        "legend": {
            "V": {
                "kind": "mission",
                "emoji": "🛠",
                "name": "Virtual's bench",
                "mission": "p5_the_signal_room",
            },
            "M": {
                "kind": "mission",
                "emoji": "🗺",
                "name": "The map table",
                "mission": "p6_the_map_table",
                "requires_mission": "p5_the_signal_room",
                "locked_text": (
                    "Sader Vorae has both hands flat on the map and does not look up.\n\n"
                    "\"Talk to Virtual. She's been holding a speech about that antenna for "
                    "a week and I'd like somebody else to receive it.\""
                ),
            },
            "T": {
                "kind": "mission",
                "emoji": "🕯",
                "name": "The long table",
                "mission": "p7_what_we_do_now",
                "requires_mission": "p6_the_map_table",
                "locked_text": (
                    "Chairs pulled round, nobody in them yet.\n\n"
                    "Dolphe catches your eye from across the room. \"When Sader's done "
                    "with you. Not before — she'll only make me say it twice.\""
                ),
            },
            "b": {
                "kind": "note",
                "emoji": "🔋",
                "name": "The car battery",
                "text": (
                    "A car battery wired into something it was never designed to power, "
                    "with a strip of tape on it reading **DO NOT BELIEVE THE GAUGE**.\n\n"
                    "The gauge reads full. It has read full for nine months."
                ),
            },
            "d": {
                "kind": "note",
                "emoji": "🥫",
                "name": "Ration shelf",
                "text": (
                    "Tins, sorted by expiry, then re-sorted by somebody with a different "
                    "opinion about expiry.\n\n"
                    "A note taped to the shelf: **THE WATER IS FINE. I TEST IT DAILY. "
                    "STOP ASKING. — Daffysamlake.** Somebody has replied: *nobody asked.*"
                ),
            },
            "a": {
                "kind": "note",
                "emoji": "📻",
                "name": "The listening post",
                "text": (
                    "A receiver tuned to a Xender logistics band, scrolling freight "
                    "manifests nobody is supposed to be reading.\n\n"
                    "Most of it is concrete and fuel. Every eleventh entry is a crate "
                    "routed north with no contents listed at all."
                ),
            },
            "c": {
                "kind": "note",
                "emoji": "🛏",
                "name": "Camp beds",
                "text": (
                    "Four camp beds. Three are made with a neatness that suggests "
                    "military habit; the fourth is a nest of blankets and charging "
                    "cables.\n\n"
                    "You can tell exactly whose is whose, and you have met them for a "
                    "combined total of one afternoon."
                ),
            },
            "z": {
                "kind": "note",
                "emoji": "🧰",
                "name": "Parts crate",
                "text": (
                    "Salvage, sorted into bins by a system that is either brilliant or "
                    "nonexistent.\n\n"
                    "One bin is labelled **GOOD**. One is labelled **BAD**. One is "
                    "labelled **ASK ME FIRST** and is padlocked."
                ),
            },
            "m": {
                "kind": "note",
                "emoji": "🖼",
                "name": "The wall",
                "text": (
                    "Photographs, pinned edge to edge. Team Cascade before any of this — "
                    "a hangar, an airship, far too many people grinning at the camera.\n\n"
                    "Somebody has gone along the row and turned eleven of them face-in to "
                    "the wall. Nobody has turned them back."
                ),
            },
            "e": {
                "kind": "note",
                "emoji": "🪫",
                "name": "Bottom of the stairs",
                "text": (
                    "A torch clipped to the handrail, pointing up the stairwell rather "
                    "than down it.\n\n"
                    "It's positioned to light the face of anyone coming down. Not to help "
                    "them see."
                ),
            },
            "u": {
                "kind": "note",
                "emoji": "📋",
                "name": "The rota",
                "text": (
                    "A whiteboard split into watches, six hours each, names in Sader's "
                    "handwriting.\n\n"
                    "Josh's name is on four of them. Two are crossed out and rewritten in "
                    "somebody else's hand, then crossed out again and rewritten back."
                ),
            },
            "h": {
                "kind": "note",
                "emoji": "🩹",
                "name": "Bee Jee's corner",
                "text": (
                    "A folding table laid out with more care than the rest of the room "
                    "combined. Everything labelled. Everything within reach of the chair.\n\n"
                    "She has already restocked the kit she gave you upstairs, and she did "
                    "it before you got hurt rather than after."
                ),
            },
            "j": {
                "kind": "note",
                "emoji": "🧊",
                "name": "Josh, not sitting down",
                "text": (
                    "He's been in the corner since you came down, facing the stairwell, "
                    "arms folded.\n\n"
                    "\"I'm fine here.\" A pause. \"I don't like rooms with one way out. "
                    "Ask Sader why.\""
                ),
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
