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

    kind      "mission" | "note" | "cache" | "hunt" | "exit"
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

OPTIONAL CONTENT -- `cache` and `hunt`
--------------------------------------
Notes are worth reading for the story, and nothing else. That is fine for
some tiles and a wasted opportunity for others: a player who explores
every room should end up materially better off than one who walks the
critical path, or exploring is a tax on people who like exploring.

    cache   one-time optional loot. `grant` is the same reward block the
            story uses. Claimed once, then it renders as empty.
    hunt    an optional FIGHT, off the critical path and deliberately
            harder than the mission fights around it. `enemies`, `level`
            and `grant`. Losing costs nothing and touches no mission
            progress -- an optional fight that could set you back would
            just teach players to avoid optional fights.

Both are tracked in PlayerStory.read_tiles alongside notes, so "have I
already had this" is one question with one answer.

AREA COMPLETION
---------------
`completion_bonus` on an area pays out once, when every interactive tile
in it has been used. It is the payoff for thoroughness specifically --
the reward for the LAST tile, which is otherwise the least interesting
one to walk to.

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
# RELAXED, because the old values CAUSED the clutter.
#
# MIN_DENSITY 0.28 with MAX_DISTANCE 2 forced every walkable tile to sit
# within two steps of something interactive. The rule was written to stop
# sparse maps being a boring walk, and it overcorrected into "every tile
# is interactive and every tile has a paragraph" -- 77 notes across 7
# areas, all of which the checker demanded.
#
# The real fix is smaller rooms rather than denser ones: a 5x5 room with
# three things in it is dense by construction and needs no rule at all.
# So the floor drops and the reach widens, and the size CEILING gains a
# matching floor -- see MAX_ROOM_TILES.
MIN_DENSITY = 0.12
MAX_DISTANCE_TO_CONTENT = 4

# Measured on a phone, not guessed: 12 across is comfortable, 14 is
# pushing it. 13 leaves a margin for narrower devices.
MAX_WIDTH = 13
MAX_HEIGHT = 12

# Discord's per-field ceiling. The grid occupies one field on its own.
MAX_FIELD_CHARS = 1024

# ROOMS ARE SMALL AND THERE ARE MANY OF THEM.
#
# The overworld read as a few big cluttered halls because the format
# allowed 13x12 and nothing pushed back. A journey through a dozen small
# named places is both easier to read on a phone and truer to what the
# story is -- you are travelling, not pacing one room.
#
# Enforced by tools/check_story.py: an area over this many walkable tiles
# should be split into connected rooms instead.
MAX_ROOM_TILES = 40

# How many legend lines the map screen shows before it stops listing
# scenery. The list is there to make the grid legible, not to inventory
# it -- see map_service.legend_lines.
MAX_LEGEND_LINES = 6

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


# ----------------------------------------------------------------------
# AREA SHAPES -- MAKE THEM DIFFERENT FROM EACH OTHER
# ----------------------------------------------------------------------
# Every area in this file used to be the same map. Not similar: the SAME
# -- 9x5 or 7x5, one solid block of wall in the middle, four content
# tiles around the outside. Nineteen areas, two footprints between them.
# The story travels from a lab cell to a glacier to a freight yard to a
# counting house and they all played identically, because the shape of a
# room is most of what a room is when the only verb is "walk".
#
# The limits allow far more than that (MAX_WIDTH 13, MAX_HEIGHT 12,
# MAX_ROOM_TILES 40 walkable), and they were never the constraint -- the
# constraint was that the first map got copied eighteen times.
#
# So the shape is now part of the writing, and should stay that way:
#
#     ocellios_cell           5x5    a box, deliberately claustrophobic
#     divide_shed             5x7    one cold room, taller than it is wide
#     glacier_countinghouse   7x9    a stairwell of record rooms
#     cascade_ops             9x7    a squarer room broken up by desks
#     glacier_drift           9x8    irregular, picked through
#     entrospire_yard         9x9    a perimeter with an office inside it
#     glacier_ridge          11x5    a long walk with one drop off the side
#     deadlands_crossing     11x7    a crossroads, drawn as one
#     wastelands_picket      13x5    a long line, because it is a picket line
#     glacier_shelf          13x6    wide and shallow
#     divide_fence           13x5    the longest thin walk in the chapter
#
# The density rules below still bind -- a bigger map is only allowed if
# it has the content to justify the walking. tools/check_story.py fails
# the build otherwise, which is what stops "make it bigger" from
# quietly becoming "make it emptier".
# ----------------------------------------------------------------------

AREAS: dict[str, dict] = {

    # ==================================================================
    # THE PROLOGUE IS A JOURNEY THROUGH SMALL NAMED ROOMS.
    #
    # It used to be three 13x7 halls with every important thing in each
    # one, which is neither readable on a phone nor sensible in the
    # world: a lab, a glacier and a basement do not each contain one of
    # everything. Eight rooms now, 9-24 tiles apiece, each named and
    # placed in a region, connected in a line you travel along.
    #
    # The opening room is 3x3 on purpose. You wake in a box that is
    # coming down, and the first thing the game asks is "which way out".
    # ==================================================================
    "ocellios_cell": {
        "name": "Sector 9 — Containment",
        "region": "Ocellios Lab",
        "blurb": "Three metres square. The ceiling is coming down.",
        "grid": [
            "#####",
            "#R.f#",
            "#.@.#",
            "#T.E#",
            "#####",
        ],
        "legend": {
            "T": {
                "kind": "mission",
                "emoji": "🧪",
                "name": "The floor",
                "mission": "pr1_destruction_eruption",
            },
            "E": {
                "kind": "exit",
                "emoji": "🚪",
                "name": "Buckled door",
                "to_area": "ocellios_corridor",
                "to": [1, 2],
                "requires_mission": "pr1_destruction_eruption",
                "locked_text": "The frame is bent and there is a D-class unit between you and it, and it is not running its greeting routine.",
            },
            "R": {
                "kind": "note",
                "emoji": "🛏",
                "name": "Restraint frame",
                "text": "Padded, adjustable, open. The cuffs were released from *inside* the console.\n\nEleven months of weight readings on the rail. Three different hands wrote them.",
            },
            "f": {
                "kind": "note",
                "emoji": "🔥",
                "name": "Burning debris",
                "text": "A ceiling panel, still alight, lying where you were lying.\n\nYou moved before you were awake. Something in you did, anyway.",
            },
        },
    },

    "ocellios_corridor": {
        "name": "Sector 9 — East Corridor",
        "region": "Ocellios Lab",
        "blurb": "On fire at both ends. Only one end is passable.",
        "grid": [
            "#########",
            "#@<.d..a#",
            "#.#####.#",
            "#c..m..E#",
            "#########",
        ],
        "legend": {
            "E": {
                "kind": "exit",
                "emoji": "🚪",
                "name": "Staging door",
                "to_area": "ocellios_staging",
                "to": [1, 3],
            },
            "d": {
                "kind": "note",
                "emoji": "💻",
                "name": "Dead terminal",
                "text": "One line burnt into the phosphor:\n\n**HHYPER — PHASE 1 — GO.**",
            },
            "a": {
                "kind": "note",
                "emoji": "🚨",
                "name": "Alarm panel",
                "text": "**CONTAINMENT FAULT — SECTOR 9.** Repeating since before you woke.\n\nSector 9 was the room you woke in.",
            },
            "c": {
                "kind": "note",
                "emoji": "📋",
                "name": "Dropped clipboard",
                "text": "**SUBJECT VIABILITY — WK 44.**\n\nAt the bottom, different pen: *ask Stubby re: transfer. Not my call anymore.*",
            },
            "m": {
                "kind": "note",
                "emoji": "🤖",
                "name": "Mech cradles",
                "text": "Six cradles, five empty. The sixth holds a unit with its control cover prised off.\n\nSomebody changed what these things want. It wasn't the lab.",
            },
            "<": {
                "kind": "exit",
                "emoji": "🔙",
                "name": "Back to Sector 9 — Containment",
                "to_area": "ocellios_cell",
                "to": [1, 1],
            },
        },
    },

    "ocellios_staging": {
        "name": "Sector 9 — Staging",
        "region": "Ocellios Lab",
        "blurb": "Where the field teams kitted up. Nobody kitted up today.",
        "grid": [
            "#######",
            "#L...k#",
            "#<.#..#",
            "#@...E#",
            "#######",
        ],
        "legend": {
            "L": {
                "kind": "mission",
                "emoji": "🗄",
                "name": "Staging locker",
                "mission": "pr2_field_salvage",
            },
            "E": {
                "kind": "exit",
                "emoji": "🚪",
                "name": "Fire door — east",
                "to_area": "glacier_shelf",
                "to": [1, 3],
                "requires_mission": "pr2_field_salvage",
                "locked_text": "Weather on the other side and a burning lab on this one.\n\nDon't walk into that in what you woke up wearing. The locker is right there.",
            },
            "k": {
                "kind": "note",
                "emoji": "🧥",
                "name": "Coat hook",
                "text": "One coat, three sizes too big.\n\nYou take it. Nobody at Cascade ever asks where you got it.",
            },
            "<": {
                "kind": "exit",
                "emoji": "🔙",
                "name": "Back to Sector 9 — East Corridor",
                "to_area": "ocellios_corridor",
                "to": [1, 2],
            },
        },
    },

    "glacier_shelf": {
        "name": "The Shelf",
        "region": "Glacier 15",
        "blurb": "White to the horizon. A line of dead lamps going east.",
        # A WIDE, SHALLOW SHELF -- 13x6. See the AREA SHAPES note at the
        # top of AREAS for why the maps stopped all being the same ring.
        "grid": [
            "#############",
            "#@...t.....B#",
            "#.#########.#",
            "#<....c....E#",
            "#.#########.#",
            "#u...########",
        ],
        "legend": {
            "B": {
                "kind": "mission",
                "emoji": "🔥",
                "name": "First heat beacon",
                "mission": "pr3_heat_beacons",
            },
            "E": {
                "kind": "exit",
                "emoji": "🚪",
                "name": "East, along the line",
                "to_area": "glacier_ridge",
                "to": [1, 1],
                "requires_mission": "pr3_heat_beacons",
                "locked_text": "You will not survive the walk at this body temperature. Get the beacon lit.",
            },
            "t": {
                "kind": "note",
                "emoji": "🌡",
                "name": "Temperature stake",
                "text": "A dial you decide not to read twice.\n\nScratched into the paint: *keep moving keep moving keep moving.*",
            },
            "u": {
                "kind": "cache",
                "emoji": "🚗",
                "name": "Buried hauler",
                "text": "Doors shut, seats empty, boot open and packed. They loaded it. They never drove.",
                "grant": {
                    "gold": 320,
                    "permafrost_ore": 40,
                    "item": "uncommon",
                },
            },
            "c": {
                "kind": "note",
                "emoji": "🏚",
                "name": "A roofline",
                "text": "Something rectangular under the drift. A roof.\n\nYou are walking along the top of somebody's street.",
            },
            "<": {
                "kind": "exit",
                "emoji": "🔙",
                "name": "Back to Sector 9 — Staging",
                "to_area": "ocellios_staging",
                "to": [1, 3],
            },
        },
    },

    "glacier_ridge": {
        "name": "The Ridge",
        "region": "Glacier 15",
        "blurb": "Somebody up here has been watching you for a while.",
        # A RIDGE -- 11x5, a single long walk along the top with one
        # short drop off the side. Narrow because a ridge is narrow.
        "grid": [
            "###########",
            "#@<..N...e#",
            "#####.#####",
            "#h.......E#",
            "###########",
        ],
        "legend": {
            "N": {
                "kind": "mission",
                "emoji": "🔦",
                "name": "The light on the ridge",
                "mission": "pr4_the_anomaly",
            },
            "E": {
                "kind": "exit",
                "emoji": "🚪",
                "name": "Down to the drift line",
                "to_area": "glacier_drift",
                "to": [1, 3],
                "requires_mission": "pr4_the_anomaly",
                "locked_text": "There is a light tracking you from the ridge and it has not decided about you yet.\n\nGo and be decided about.",
            },
            "e": {
                "kind": "note",
                "emoji": "🛰",
                "name": "Cascade's radar",
                "text": "A tripod dish, freshly serviced, running off a battery somebody carried here.\n\nThis is what saw you.",
            },
            "h": {
                "kind": "note",
                "emoji": "🪦",
                "name": "Marker cairn",
                "text": "Stones waist-high, a name plate wired to the top, no grave underneath.\n\nThere are more of these than there are loose stones.",
            },
            "<": {
                "kind": "exit",
                "emoji": "🔙",
                "name": "Back to The Shelf",
                "to_area": "glacier_shelf",
                "to": [1, 3],
            },
        },
    },

    "glacier_drift": {
        "name": "The Drift Line",
        "region": "Glacier 15",
        "blurb": "Thin ice over something with a shape to it.",
        # DRIFTED SNOW -- 9x8, an irregular shape rather than a corridor,
        # so the drift reads as something you pick your way through.
        "grid": [
            "#########",
            "#@..a...#",
            "#<..###.#",
            "#....##j#",
            "###.....#",
            "#q..###.#",
            "#..W...E#",
            "#########",
        ],
        "legend": {
            "W": {
                "kind": "mission",
                "emoji": "🥊",
                "name": "The drift line",
                "mission": "pr5_through_the_drift",
                "requires_characters": 2,
                "locked_text": "“Not as three,” Nebula says flatly. “Use the tag. Call somebody, put them in your squad, and then we walk it.”",
            },
            "E": {
                "kind": "exit",
                "emoji": "🚪",
                "name": "The base light",
                "to_area": "cascade_workshop",
                "to": [1, 3],
                "requires_mission": "pr5_through_the_drift",
                "locked_text": "Gostley has his hand flat on the ice and is not moving. “Not yet.”",
            },
            "a": {
                "kind": "hunt",
                "emoji": "🕳",
                "name": "Entry hole",
                "text": "The shaft goes deeper than the worm needed, and something small came back up it.\n\n*Optional. Losing this costs you nothing at all.*",
                "enemies": [
                    "Concussion Drone",
                    "Concussion Drone",
                ],
                "level": 4,
                "grant": {
                    "gold": 400,
                    "permafrost_ore": 45,
                    "item": "uncommon",
                },
            },
            "j": {
                "kind": "note",
                "emoji": "💡",
                "name": "Beacon post 9",
                "text": "The last post before the base light, and this one is already lit.\n\nSomebody comes this far every night, for two years, in case.",
            },
            "q": {
                "kind": "note",
                "emoji": "🍫",
                "name": "Ration wrapper",
                "text": "Eight months past date and the best thing that has ever happened to you.",
            },
            "<": {
                "kind": "exit",
                "emoji": "🔙",
                "name": "Back to The Ridge",
                "to_area": "glacier_ridge",
                "to": [1, 1],
            },
        },
    },

    "cascade_workshop": {
        "name": "The Workshop",
        "region": "Cascade — Forward Base",
        "blurb": "One heated shell, one relay, and a great deal of cable.",
        "grid": [
            "#######",
            "#V...b#",
            "#<.#..#",
            "#@z..E#",
            "#######",
        ],
        "legend": {
            "V": {
                "kind": "mission",
                "emoji": "🛠",
                "name": "Virtual's bench",
                "mission": "pr6_forward_base",
            },
            "E": {
                "kind": "exit",
                "emoji": "🚪",
                "name": "Through to Ops",
                "to_area": "cascade_ops",
                "to": [1, 3],
                "requires_mission": "pr6_forward_base",
                "locked_text": "“Let Virtual finish. She's been holding a speech about that relay for a week and I'd like somebody else to receive it.”",
            },
            "b": {
                "kind": "note",
                "emoji": "🔋",
                "name": "The battery bank",
                "text": "Taped over with **DO NOT BELIEVE THE GAUGE**.\n\nThe gauge reads full. It has read full for nine months.",
            },
            "z": {
                "kind": "cache",
                "emoji": "🧰",
                "name": "Parts crate",
                "text": "Bins labelled **GOOD**, **BAD**, and **ASK ME FIRST**. The third is padlocked.",
                "grant": {
                    "metal": 70,
                    "crystal": 35,
                    "reroll_tokens": 4,
                },
            },
            "<": {
                "kind": "exit",
                "emoji": "🔙",
                "name": "Back to The Drift Line",
                "to_area": "glacier_drift",
                "to": [1, 3],
            },
        },
    },

    "cascade_ops": {
        "name": "Operations",
        "region": "Cascade — Forward Base",
        "blurb": "A map table, a long table, and eleven photographs turned to the wall.",
        # AN OPERATIONS ROOM -- 9x7, a squarer space broken by desks
        # rather than one loop around a solid block.
        "grid": [
            "#########",
            "#@..M..m#",
            "#<.#.#..#",
            "#..#.#..#",
            "#p.....T#",
            "#..###.E#",
            "#########",
        ],
        "legend": {
            "M": {
                "kind": "mission",
                "emoji": "🗺",
                "name": "The map table",
                "mission": "pr7_the_map_table",
            },
            "T": {
                "kind": "mission",
                "emoji": "🕯",
                "name": "The long table",
                "mission": "pr8_someone_got_here_first",
                "requires_mission": "pr7_the_map_table",
                "locked_text": "Chairs pulled round, nobody in them yet. Gostley is still out at the drift hole.",
            },
            "E": {
                "kind": "exit",
                "emoji": "🪜",
                "name": "Up, and north",
                "to_area": "divide_camp",
                "to": [1, 3],
                "requires_mission": "pr8_someone_got_here_first",
                "locked_text": "Dawn, Dolphe said. There's a man walking in and you're meeting him rested.",
            },
            "m": {
                "kind": "note",
                "emoji": "🖼",
                "name": "The wall",
                "text": "Team Cascade before any of this, pinned edge to edge.\n\nEleven photographs have been turned face-in. Nobody has turned them back.",
            },
            "p": {
                "kind": "note",
                "emoji": "🐬",
                "name": "The press plate",
                "text": "One column. Four hundred and six names in eight-point type.\n\nIt is the only decoration in the building.",
            },
            "<": {
                "kind": "exit",
                "emoji": "🔙",
                "name": "Back to The Workshop",
                "to_area": "cascade_workshop",
                "to": [1, 3],
            },
        },
    },

    # ---- Chapters 1-2, split the same way: small named rooms in a line.
    "divide_camp": {
        "name": "The Divide — Cascade Camp",
        "region": "Cryosphere Divide",
        "blurb": "Where the shelf gives way. A man walked in from the wrong direction.",
        "grid": [
            "#######",
            "#J...m#",
            "#<.#..#",
            "#@..kE#",
            "#######",
        ],
        "legend": {
            "J": {
                "kind": "mission",
                "emoji": "🧍",
                "name": "Josh, standing",
                "mission": "c1m1_the_man_off_the_shelf",
            },
            "E": {
                "kind": "exit",
                "emoji": "🚪",
                "name": "Out to the fence line",
                "to_area": "divide_fence",
                "to": [1, 3],
                "requires_mission": "c1m1_the_man_off_the_shelf",
                "locked_text": "There is a man at the door who walked here from the shelf and hasn't been offered a chair yet.",
            },
            "m": {
                "kind": "cache",
                "emoji": "🩺",
                "name": "Cached triage kit",
                "text": "Restocked and dated last week. Cascade has never stopped expecting to need it.",
                "grant": {
                    "gold": 400,
                    "crystal": 30,
                    "item": "uncommon",
                },
            },
            "k": {
                "kind": "note",
                "emoji": "💡",
                "name": "Floodlights",
                "text": "Every light lit, at noon, on a decommissioned site.\n\nJosh stands under one for a while. He was told for two years this place was dark.",
            },
            "<": {
                "kind": "exit",
                "emoji": "🔙",
                "name": "Back to Operations",
                "to_area": "cascade_ops",
                "to": [1, 3],
            },
        },
    },

    "divide_fence": {
        "name": "The Divide — Fence Line",
        "region": "Cryosphere Divide",
        "blurb": "Four metres of razor wire, and every barb leans inward.",
        # A FENCE LINE -- 13x5, the longest thin walk in the chapter: you
        # follow it, you don't wander around it.
        "grid": [
            "#############",
            "#@..s......d#",
            "#<#########.#",
            "#y....C...ME#",
            "#############",
        ],
        "legend": {
            "C": {
                "kind": "mission",
                "emoji": "🥊",
                "name": "The survey camp",
                "mission": "c1m2_the_cut_line",
            },
            "E": {
                "kind": "exit",
                "emoji": "🚪",
                "name": "On to the shed",
                "to_area": "divide_shed",
                "to": [1, 3],
                "requires_mission": "c1m2_the_cut_line",
                "locked_text": "There's a Xender rear guard standing in the camp between you and it.",
            },
            "s": {
                "kind": "note",
                "emoji": "🪧",
                "name": "Site notice",
                "text": "**SITE DECOMMISSIONED — NO PERSONNEL ON SITE.**\n\nThe inspection slip under it has been signed every ninety days for two years. The latest is eleven days old.",
            },
            "d": {
                "kind": "note",
                "emoji": "🧾",
                "name": "Nineteen slips",
                "text": "A clipboard in the guard shack. Nineteen entries have an *in* time and no *out* time.\n\nNobody has drawn a line under any of them.",
            },
            "y": {
                "kind": "hunt",
                "emoji": "🐾",
                "name": "Four-point tracks",
                "text": "An even stride, dead straight, running behind the vehicle park and stopping there.\n\n*Optional. Losing this costs you nothing at all.*",
                "enemies": [
                    "Glacial Exterminator",
                ],
                "level": 6,
                "grant": {
                    "gold": 900,
                    "crystal": 50,
                    "item": "rare",
                },
            },
            "<": {
                "kind": "exit",
                "emoji": "🔙",
                "name": "Back to The Divide — Cascade Camp",
                "to_area": "divide_camp",
                "to": [1, 3],
            },
            "M": {
                "kind": "mission",
                "emoji": "🗣",
                "name": "The long table",
                "mission": "c1m2b_the_argument",
            },
        },
    },

    "divide_shed": {
        "name": "The Cold Workshop",
        "region": "Cryosphere Divide",
        "blurb": "Bench, vice, power, roof. Virtual could cry.",
        # DELIBERATELY SMALL and taller than it is wide -- 5x7. A cold
        # one-room workshop should feel like one, and the size range only
        # reads as a range if some areas stay cramped.
        "grid": [
            "#####",
            "#F.w#",
            "#...#",
            "#<.b#",
            "#...#",
            "#@.E#",
            "#####",
        ],
        "legend": {
            "F": {
                "kind": "mission",
                "emoji": "🛠",
                "name": "The bench",
                "mission": "c1m3_no_supply_line",
            },
            "E": {
                "kind": "exit",
                "emoji": "🚪",
                "name": "Down into the site",
                "to_area": "outpost_atrium",
                "to": [1, 3],
                "requires_mission": "c1m3_no_supply_line",
                "locked_text": "“Kit first,” Virtual says. “I found a bench. Give me the hour.”",
            },
            "w": {
                "kind": "note",
                "emoji": "🕯",
                "name": "A cairn with a name",
                "text": "Older than the others, tucked where the wind can't reach it.\n\nThe plate says **REX**. There is no date, because whoever built it did not know one.",
            },
            "b": {
                "kind": "cache",
                "emoji": "🛢",
                "name": "Fuel bunker",
                "text": "Deliveries every six weeks without a gap, for a site with nobody on it.",
                "grant": {
                    "gold": 700,
                    "xendium": 25,
                    "item": "rare",
                },
            },
            "<": {
                "kind": "exit",
                "emoji": "🔙",
                "name": "Back to The Divide — Fence Line",
                "to_area": "divide_fence",
                "to": [1, 3],
            },
        },
    },

    "outpost_atrium": {
        "name": "Glacier 15 — Atrium",
        "region": "The Outpost",
        "blurb": "Every light on. Nobody home for two years.",
        "grid": [
            "#########",
            "#@..c..G#",
            "#<#####.#",
            "#a..L..E#",
            "#########",
        ],
        "legend": {
            "L": {
                "kind": "mission",
                "emoji": "💻",
                "name": "The decrypt bench",
                "mission": "c1m4_the_letter",
            },
            "E": {
                "kind": "exit",
                "emoji": "🚪",
                "name": "To the stairhead",
                "to_area": "outpost_stairhead",
                "to": [1, 3],
                "requires_mission": "c1m4_the_letter",
                "locked_text": "Stairs down to the vault level, and something enormous standing very still at the bottom of them.\n\n“Not yet,” Nebula says. “Walk the floor first. I want to know what we're standing on.”"
            },
            "c": {
                "kind": "note",
                "emoji": "🧥",
                "name": "The coat rack",
                "text": "Forty winter coats, still hanging.\n\nNobody walked out into that weather without a coat. Nobody walked out at all.",
            },
            "G": {
                "kind": "note",
                "emoji": "🖥",
                "name": "Reception terminal",
                "text": "**ON SITE TODAY: 0.**\n\nIt has read zero every day for two years. The day before that it read 406.",
            },
            "a": {
                "kind": "note",
                "emoji": "☕",
                "name": "The canteen",
                "text": "Cups set down mid-conversation, in pairs and fours, frozen solid.\n\nThis room was not evacuated. It was *left*.",
            },
            "<": {
                "kind": "exit",
                "emoji": "🔙",
                "name": "Back to The Cold Workshop",
                "to_area": "divide_shed",
                "to": [1, 3],
            },
        },
    },

    "outpost_stairhead": {
        "name": "Glacier 15 — Stairhead",
        "region": "The Outpost",
        "blurb": "Ninety-one percent of this site's power goes down these stairs.",
        "grid": [
            "#######",
            "#@..z.#",
            "#<###.#",
            "#w.MSX#",
            "#######",
        ],
        "legend": {
            "S": {
                "kind": "mission",
                "emoji": "🥊",
                "name": "The stairhead",
                "mission": "c1m5_what_he_left_on",
            },
            "X": {
                "kind": "exit",
                "emoji": "🚂",
                "name": "The freight line",
                "to_area": "wastelands_picket",
                "to": [1, 3],
                "requires_mission": "c1m5_what_he_left_on",
                "locked_text": "There is something standing on one knee at the bottom of the stairs, and nobody is leaving until that stops being a question.",
            },
            "z": {
                "kind": "note",
                "emoji": "🔌",
                "name": "Distribution board",
                "text": "Lighting, heating, comms — all trivial.\n\nNinety-one percent goes to one unlabelled circuit, and that circuit goes *down*.",
            },
            "w": {
                "kind": "hunt",
                "emoji": "🧯",
                "name": "The sealed corridor",
                "text": "**DO NOT OPEN. NOT FOR YOUR SAKE.**\n\nJosh reads it twice. “Him wrote that to keep something in, or keep someone out. Only one of them our problem.”\n\n*Optional. Losing this costs you nothing at all.*",
                "enemies": [
                    "Ocellios Test Subject",
                    "Voidwarp Construct",
                ],
                "level": 8,
                "grant": {
                    "gold": 1400,
                    "crystal": 80,
                    "shards": 60,
                    "item": "epic",
                },
            },
            "<": {
                "kind": "exit",
                "emoji": "🔙",
                "name": "Back to Glacier 15 — Atrium",
                "to_area": "outpost_atrium",
                "to": [1, 3],
            },
            "M": {
                "kind": "mission",
                "emoji": "🪜",
                "name": "The step outside",
                "mission": "c1m6_what_josh_owes",
            },
        },
    },

    "wastelands_picket": {
        "name": "The Line — The Picket",
        "region": "The Wastelands",
        "blurb": "Four hundred people sitting on the rails, nine days in.",
        # A PICKET LINE IS LONG -- 13x5, two long parallel runs, because
        # the fiction is people standing in a row across a freight bend.
        "grid": [
            "#############",
            "#@.s.....k..#",
            "#.#.#####.#.#",
            "#<..F...P..E#",
            "#############",
        ],
        "legend": {
            "F": {
                "kind": "mission",
                "emoji": "🚂",
                "name": "The freight bend",
                "mission": "c2m1_the_freight_line",
            },
            "P": {
                "kind": "mission",
                "emoji": "🥊",
                "name": "The picket line",
                "mission": "c2m2_the_picket",
                "requires_mission": "c2m1_the_freight_line",
                "locked_text": "Work out where the freight is going before you walk into somebody else's strike.",
            },
            "E": {
                "kind": "exit",
                "emoji": "🚪",
                "name": "Down to Entrospire",
                "to_area": "entrospire_tables",
                "to": [1, 3],
                "requires_mission": "c2m2_the_picket",
                "locked_text": "Company security are still deciding. Settle the embankment first.",
            },
            "s": {
                "kind": "note",
                "emoji": "🪧",
                "name": "Banners",
                "text": "**PAY US** on most of them. On three, in different handwriting: **WHAT IS ON THE NIGHT TRAIN.**\n\nThose three are at the back, where the photographers can't get an angle.",
            },
            "k": {
                "kind": "cache",
                "emoji": "🍲",
                "name": "The soup line",
                "text": "**IF YOU ARE HUNGRY YOU ARE ONE OF US. THIS INCLUDES SCABS. WE ARE NOT ANIMALS.**",
                "grant": {
                    "gold": 900,
                    "metal": 90,
                    "reroll_tokens": 6,
                },
            },
            "<": {
                "kind": "exit",
                "emoji": "🔙",
                "name": "Back to Glacier 15 — Stairhead",
                "to_area": "outpost_stairhead",
                "to": [1, 3],
            },
        },
    },

    "entrospire_tables": {
        "name": "The Underside — Chary's Table",
        "region": "Entrospire City",
        "blurb": "Beneath the rail deck. Everything down here signs for itself.",
        "grid": [
            "#######",
            "#C...a#",
            "#<.#..#",
            "#@..fE#",
            "#######",
        ],
        "legend": {
            "C": {
                "kind": "mission",
                "emoji": "🃏",
                "name": "Chary's table",
                "mission": "c2m3_the_underside",
            },
            "E": {
                "kind": "exit",
                "emoji": "🚪",
                "name": "To the night yard",
                "to_area": "entrospire_yard",
                "to": [1, 3],
                "requires_mission": "c2m3_the_underside",
                "locked_text": "You need the key, and the woman with the key is dealing cards two streets west.",
            },
            "a": {
                "kind": "note",
                "emoji": "📇",
                "name": "The fence's index",
                "text": "Everything sellable in Entrospire, cross-referenced by who wants it dead.\n\nUnder R there is one card. It is blank, and handled soft at the corners.",
            },
            "f": {
                "kind": "cache",
                "emoji": "🪟",
                "name": "Pawnbroker's window",
                "text": "A Cascade relay tag with the strap cut. It isn't yours.\n\nSomebody else lit beacons once, got this far, and stopped.",
                "grant": {
                    "gold": 1400,
                    "shards": 90,
                    "item": "epic",
                },
            },
            "<": {
                "kind": "exit",
                "emoji": "🔙",
                "name": "Back to The Line — The Picket",
                "to_area": "wastelands_picket",
                "to": [1, 3],
            },
        },
    },

    "entrospire_yard": {
        "name": "The Night Yard",
        "region": "Entrospire City",
        "blurb": "A yard that closed in '06 and has its lights on.",
        # A YARD WITH AN INNER OFFICE -- 9x9. The biggest single space in
        # the story so far, and the first that is taller than it is wide:
        # you walk the perimeter, then go INTO the middle for the ledger.
        "grid": [
            "#########",
            "#@..e..j#",
            "#.#####.#",
            "#.#Y.N#.#",
            "#.#...#.#",
            "#.#K.G#.#",
            "#.##.##.#",
            "#<..M...#",
            "#########",
        ],
        "legend": {
            "Y": {
                "kind": "mission",
                "emoji": "🥊",
                "name": "The yard gate",
                "mission": "c2m4_what_is_in_them",
            },
            "M": {
                "kind": "mission",
                "emoji": "🔻",
                "name": "The end of the yard",
                "mission": "c2m5_the_man_himself",
                "requires_mission": "c2m4_what_is_in_them",
                "locked_text": "There is a man sitting on a crate down there who has not moved since you arrived.\n\nOpen the crates first. He seems content to wait.",
            },
            "K": {
                "kind": "note",
                "emoji": "🚧",
                "name": "The north gate",
                "text": "Chained, and the chain is threaded from the inside.\n\nWhen this opens it will be because somebody chose to open it for you.",
            },
            "e": {
                "kind": "note",
                "emoji": "🧮",
                "name": "The yard ledger",
                "text": "Service 0210, twice a month, two years without a gap.\n\nSigned out every time by a single letter.",
            },
            "j": {
                "kind": "hunt",
                "emoji": "🎞",
                "name": "Deck camera",
                "text": "The splice is fresh and the cable runs into a maintenance void.\n\nSomebody has been watching the watchers, and they are still in there.\n\n*Optional. Losing this costs you nothing at all.*",
                "enemies": [
                    "Xender Convoy",
                    "Xender Loyalist",
                ],
                "level": 13,
                "grant": {
                    "gold": 1800,
                    "shards": 120,
                    "xendium": 50,
                    "item": "epic",
                },
            },
            "<": {
                "kind": "exit",
                "emoji": "🔙",
                "name": "Back to The Underside — Chary's Table",
                "to_area": "entrospire_tables",
                "to": [1, 3],
            },
            "N": {
                "kind": "mission",
                "emoji": "📒",
                "name": "The yard ledger",
                "mission": "c2m6_the_count",
            },
            "G": {
                "kind": "exit",
                "emoji": "\U0001f6aa",
                "name": "The north gate",
                "to_area": "deadlands_crossing",
                # The south arm of the crossroads. Was [1, 1], which is a
                # wall now that The Crossing is drawn as a cross rather
                # than a ring -- arriving from the north gate onto the
                # southern approach also reads better than the old
                # top-left corner.
                "to": [5, 5],
                "requires_mission": "c2m6_the_count",
                "locked_text": (
                    "The key fits. Finish here first -- the ledger is still open "
                    "on the crate and nobody has said the number out loud yet."
                ),
            },
        },
    },


    # ==================================================================
    # CHAPTER 3 -- north of the gate.
    #
    # Both earlier chapters ended pointing at a gate that opened onto
    # nothing, which is the worst possible place for a story to stop:
    # the player has the key in their pocket and the door goes nowhere.
    #
    # Three rooms, deliberately: the crossing, the camp, and the room
    # where the count happens. Small and linear on purpose -- this is
    # the chapter where the story arrives somewhere, and a maze would be
    # the wrong shape for an arrival.
    # ==================================================================

    "deadlands_crossing": {
        "name": "The Crossing",
        "region": "The Deadlands",
        "blurb": "North of the gate the ground stops agreeing to be ground.",
        # A CROSSROADS, drawn as one -- 11x7, four short arms meeting in
        # the middle, where the rope line is.
        "grid": [
            "###########",
            "####@.b####",
            "####.#.####",
            "#<..A.c..E#",
            "####.#.####",
            "####...####",
            "###########",
        ],
        "legend": {
            "A": {
                "kind": "mission",
                "emoji": "\U0001f9ed",
                "name": "The rope line",
                "mission": "c3m1_north_of_the_gate",
            },
            "b": {
                "kind": "note",
                "emoji": "\U0001f573",
                "name": "A hole that is not a hole",
                "text": (
                    "It is perfectly circular and it does not have a bottom, and when "
                    "Virtual drops a bolt into it there is no sound at all — not a "
                    "delayed sound. No sound.\n\n"
                    "*She writes down the time anyway. She writes down the time for "
                    "everything out here.*"
                ),
            },
            "c": {
                "kind": "cache",
                "emoji": "\U0001f6f7",
                "name": "A surveyor's kit",
                "text": (
                    "Xender-issue, two years old, dropped mid-measurement. The tripod is "
                    "still standing. Whoever set it up walked away from a job they were "
                    "halfway through and did not come back for the kit."
                ),
                "grant": {"gold": 2200, "permafrost_ore": 120, "item": "epic"},
            },
            "E": {
                "kind": "exit",
                "emoji": "\U0001f6aa",
                "name": "The rise",
                "to_area": "glacier_camp",
                "to": [1, 1],
                "requires_mission": "c3m1_north_of_the_gate",
                "locked_text": (
                    "Not until the rope line is anchored. Nobody crosses that on a guess."
                ),
            },
            "<": {
                "kind": "exit",
                "emoji": "\U0001f519",
                "name": "Back to the Freight Yard",
                "to_area": "entrospire_yard",
                "to": [5, 3],
            },
        },
    },

    "glacier_camp": {
        "name": "The Camp",
        "region": "Glacier 15",
        "blurb": "Eleven shelters. Somebody has been maintaining all eleven.",
        "grid": [
            "#########",
            "#@..d..B#",
            "#.#####.#",
            "#<..e..E#",
            "#########",
        ],
        "legend": {
            "B": {
                "kind": "mission",
                "emoji": "\U0001f3d5",
                "name": "The shelters",
                "mission": "c3m2_eleven_shelters",
            },
            "d": {
                "kind": "note",
                "emoji": "\U0001f4cf",
                "name": "The doorframe",
                "text": (
                    "Scratches at four heights, the topmost recent.\n\n"
                    "One line is labelled, in a careful adult hand: **the boy — 9**.\n\n"
                    "Above it, unlabelled, two more."
                ),
            },
            "e": {
                "kind": "cache",
                "emoji": "\U0001f9f0",
                "name": "A boot, repaired",
                "text": (
                    "Left outside a shelter, sole stitched back on with wire, done badly "
                    "and then done again properly on top of the bad job.\n\n"
                    "It is not Josh's size. Somebody else needed it more, and somebody "
                    "kept practising."
                ),
                "grant": {"gold": 2600, "shards": 220, "crystal": 90, "item": "epic"},
            },
            "E": {
                "kind": "exit",
                "emoji": "\U0001f6aa",
                "name": "The counting house",
                "to_area": "glacier_countinghouse",
                "to": [1, 1],
                "requires_mission": "c3m2_eleven_shelters",
                "locked_text": "Look at the shelters first. All eleven of them.",
            },
            "<": {
                "kind": "exit",
                "emoji": "\U0001f519",
                "name": "Back to The Crossing",
                "to_area": "deadlands_crossing",
                # Just inside the west arm, beside the way back out.
                "to": [2, 3],
            },
        },
    },

    "glacier_countinghouse": {
        "name": "The Counting House",
        "region": "Glacier 15",
        "blurb": "The only building with the lights on, and they have been on for two years.",
        # A COUNTING HOUSE HAS FLOORS -- 7x9, tall and narrow, switching
        # back on itself like a stairwell between record rooms.
        "grid": [
            "#######",
            "#@...f#",
            "#.###.#",
            "#C...g#",
            "#.###.#",
            "#....D#",
            "#.###.#",
            "#<....#",
            "#######",
        ],
        "legend": {
            "C": {
                "kind": "mission",
                "emoji": "\U0001f4d2",
                "name": "The ledger room",
                "mission": "c3m3_the_auditor",
            },
            "D": {
                "kind": "mission",
                "emoji": "\U0001f56f",
                "name": "The morning count",
                "mission": "c3m4_the_number",
            },
            "f": {
                "kind": "note",
                "emoji": "\U0001f4a1",
                "name": "The lights",
                "text": (
                    "Mains power. Out here. Running for two years to light one room "
                    "nobody was supposed to find.\n\n"
                    "*Virtual, flatly: \"That's not hiding. That's an office.\"*"
                ),
            },
            "g": {
                "kind": "note",
                "emoji": "\U0001f5c3",
                "name": "Filed correspondence",
                "text": (
                    "Two years of letters, all outbound, none sent. Every one is a "
                    "polite refusal addressed to a different newsroom, a different "
                    "relief office, a different survey board.\n\n"
                    "They are drafts of the replies Josh got."
                ),
            },
            "<": {
                "kind": "exit",
                "emoji": "\U0001f519",
                "name": "Back to The Camp",
                "to_area": "glacier_camp",
                "to": [1, 1],
            },
        },
    },

}


# Which area a new player starts in, and where.
STARTING_AREA = "ocellios_cell"


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
