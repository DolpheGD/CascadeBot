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

# WIDTH IS THE TIGHT ONE. HEIGHT BARELY MATTERS.
#
# Measured on a phone rather than guessed. 16 across fits; past that the
# rows wrap and the map becomes a staircase. Height has no such limit --
# a Discord embed scrolls, so a tall area costs the player a thumb
# movement and nothing else.
#
# That asymmetry is worth designing around: an area that wants to be big
# should get TALLER, not wider. A 9x24 stairwell reads perfectly on a
# phone and a 20x9 hall does not exist.
MAX_WIDTH = 16
MAX_HEIGHT = 30

# Discord's per-field ceiling. The grid occupies one field on its own.
#
# This is what actually caps the size, and 16x30 is deliberately just
# inside it: 509 UTF-16 units of ⬛, or 989 in the pathological case
# where every single tile is a surrogate-pair emoji like 🧊. Both fit,
# the second with little to spare -- which is why the limit stays
# asserted in tools/check_story.py against the REAL rendered grid rather
# than against a guess at its size.
MAX_FIELD_CHARS = 1024

# HOW MUCH ROOM ONE AREA MAY TAKE UP.
#
# Was 40, on the reasoning that a journey through many small named places
# beats pacing one big hall -- which is still true of CORRIDORS, and is
# why the prologue's lab is three tight rooms.
#
# It is not true of a hub. Cascade Central is somewhere you return to
# thirty times, and a place you keep coming back to should feel like a
# place: room to put people in, corners that aren't on the critical
# path, somewhere to hang a crooked banner. 90 gives a tall area real
# space while the density rules still insist it earns it -- a bigger
# room needs proportionally more in it, so this can't be used to ship
# an empty one.
MAX_ROOM_TILES = 90

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

# Suffixed onto a LEGEND entry (never drawn on the grid itself) for a
# tile that will move the story forward -- see map_service.legend_lines.
# It is not subject to the fixed-width rule below, because it never
# appears in the grid where mismatched glyph widths would stagger the
# rows; it only ever sits at the end of a line of ordinary text.
EMOJI_QUEST = "❗"


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
    # ==================================================================
    # ACT ONE -- the only corridor left in the game.
    #
    # Three small rooms, walked once, that exist to teach combat and get
    # you picked up. Everything after this is the hub, which you return
    # to. The old story was NINETEEN of these in a line; what survived
    # the rewrite is the opening, because waking up in a collapsing lab
    # is a good way to start a game and the rest was corridor.
    # ==================================================================
    "lab_cell": {
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
                "mission": "pr1_wake_up",
            },
            "E": {
                "kind": "exit",
                "emoji": "🚪",
                "name": "Buckled door",
                "to_area": "lab_corridor",
                "to": [1, 1],
                "one_way": True,   # the room stops existing behind you
                "requires_mission": "pr1_wake_up",
                "locked_text": (
                    "The frame is bent, and there is a D-class unit between you and it "
                    "that is not running its greeting routine."
                ),
            },
            "R": {
                "kind": "note",
                "emoji": "🛏",
                "name": "Restraint frame",
                "text": (
                    "Padded, adjustable, open. The cuffs were released from *inside* the "
                    "console.\n\nEleven months of weight readings on the rail. Three "
                    "different hands wrote them."
                ),
            },
            "f": {
                "kind": "note",
                "emoji": "🔥",
                "name": "Burning debris",
                "text": (
                    "A ceiling panel, still alight, lying exactly where you were lying.\n\n"
                    "You moved before you were awake. Something in you did, anyway."
                ),
            },
        },
    },

    "lab_corridor": {
        "name": "Sector 9 — East Corridor",
        "region": "Ocellios Lab",
        "blurb": "On fire at both ends. Only one end is passable.",
        "grid": [
            "#########",
            "#@.....a#",
            "#.#d#d#.#",
            "#c..L..E#",
            "#########",
        ],
        "legend": {
            "d": {"kind": "decor", "emoji": "🧯"},
            "L": {
                "kind": "mission",
                "emoji": "⚡",
                "name": "The blocked stretch",
                "mission": "pr2_long_way_out",
            },
            "E": {
                "kind": "exit",
                "emoji": "🚪",
                "name": "Out, into the cold",
                "to_area": "lab_yard",
                "to": [1, 3],
                "one_way": True,   # so does the corridor
                "requires_mission": "pr2_long_way_out",
                "locked_text": "Not while those two are still up and arguing about you.",
            },
            "a": {
                "kind": "note",
                "emoji": "📋",
                "name": "Assignment board",
                "text": (
                    "A duty roster for Sector 9, curling in the heat.\n\n"
                    "Your name is not on it. There is a line at the bottom with no name "
                    "on it at all, and a signature next to the blank."
                ),
            },
            "c": {
                "kind": "cache",
                "emoji": "🧰",
                "name": "Wall locker",
                "grant": {"gold": 120, "wood": 15},
            },
        },
    },

    "lab_yard": {
        "name": "Ocellios Lab — The Yard",
        "region": "Ocellios Lab",
        "blurb": "Snow, sirens, and one vehicle that is not running away.",
        "grid": [
            "#########",
            "#ss#P#ss#",
            "#..H....#",
            "#w..@..M#",
            "#ss###ss#",
            "#########",
        ],
        "legend": {
            "s": {"kind": "decor", "emoji": "🌲"},
            "M": {
                "kind": "mission",
                "emoji": "🚐",
                "name": "The waiting transport",
                "mission": "pr3_pickup",
            },
            "H": {
                "kind": "exit",
                "emoji": "🛣",
                "name": "South, with Dolphe",
                "to_area": "hub_atrium",
                "to": [5, 3],
                "one_way": True,   # nobody drives back to Sector 9
                "requires_mission": "pr3_pickup",
                "locked_text": "There's a transport idling by the fence and a man in the doorway waiting on an answer.",
            },
            "P": {
                "kind": "note",
                "emoji": "🏢",
                "name": "The lab, behind you",
                "text": (
                    "Sector 9 is coming apart one storey at a time, unhurriedly, like "
                    "something deciding to sit down.\n\n"
                    "Nobody else has come out of it."
                ),
            },
            "w": {
                "kind": "cache",
                "emoji": "🎒",
                "name": "Dropped kit",
                "grant": {"gold": 150, "stone": 20},
            },
        },
    },

    # ==================================================================
    # CASCADE CENTRAL -- the hub.
    #
    # Five connected rooms you come back to between every mission, rather
    # than a corridor you walk once. This is the structural change the
    # rewrite is actually about: the old story was eight rooms in a line,
    # so nowhere was ever revisited and nobody was ever there when you
    # got back.
    #
    # Each room owns ONE system and the person who explains it, so
    # "where do I go to do X" has a physical answer:
    #
    #     Atrium     Dolphe      the mission board
    #     Ops Deck   Jofrog      squad, class
    #     Armory     Refender    gear, the forge
    #     Mess       Blueflame   pulls, the exchange
    #     Gatehouse  --          travel, and eventually /adventure
    #
    # Laid out as a plus: the Atrium is the middle and everything is one
    # room away from it, so no part of the hub is ever more than two
    # moves from any other. A hub you have to remember the shape of is a
    # hub people stop walking around in.
    # ==================================================================
    "hub_atrium": {
        "name": "Cascade Central — The Atrium",
        "region": "Team Cascade",
        "blurb": "Somebody has hung a banner. It is slightly crooked and nobody has fixed it.",
        # TALL, now that height is nearly free (see MAX_HEIGHT). The
        # Atrium is the room the player walks through most often in the
        # whole game, so it gets the space: a mezzanine at the top with
        # the board on it, the floor in the middle, and the three doors
        # at the bottom where you'd expect doors to be.
        "grid": [
            "############",
            "#pp######pp#",
            "#z.p.D.p..w#",
            "#.pA.HR.Cp.#",
            "#..pp..pp..#",
            "#...q..u...#",
            "#..pp..pp..#",
            "#.p.b..n.p.#",
            "#..pp..pp..#",
            "#W...@....M#",
            "#..pp..pp..#",
            "#.y.EL...x.#",
            "#....S.....#",
            "#pp######pp#",
            "############",
        ],
        "legend": {
            "p": {"kind": "decor", "emoji": "🪴"},
            "H": {
                "kind": "station",
                "emoji": "🏛",
                "name": "Cascade HQ",
                "panel": "hq",
                "feature": "base",
            },
            "R": {
                "kind": "station",
                "emoji": "⛩",
                "name": "The shrine gallery",
                "panel": "shrines",
                "feature": "base",
            },
            "E": {
                "kind": "station",
                "emoji": "🌾",
                "name": "The yield board",
                "panel": "harvesters",
                "feature": "base",
            },
            "L": {
                "kind": "station",
                "emoji": "🔬",
                "name": "The Research Lab (a shed)",
                "panel": "lab",
                "feature": "lab",
            },
            "A": {
                "kind": "mission",
                "emoji": "📋",
                "name": "The mission board",
                "mission": "pr4_the_atrium",
            },
            "C": {
                "kind": "mission",
                "emoji": "📎",
                "name": "The clipboard nobody wants",
                "mission": "pr8_the_base",
                "requires_mission": "pr7_the_mess",
                "locked_text": "Dolphe is holding it, and has decided you're not settled in enough for it yet.",
            },
            "u": {
                "kind": "npc",
                "emoji": "☕",
                "name": "The coffee machine",
                "lines": [
                    {"text": ("Industrial, ancient, and covered in handwritten notes.\n\n"
                              "**DO NOT USE SETTING 3**\n"
                              "*(setting 3 is fine — R)*\n"
                              "**IT IS NOT FINE**\n"
                              "*(it is fine if you hold the lever — R)*\n"
                              "**THAT IS NOT THE SAME AS FINE**")},
                    {"text": ("You try setting 3.\n\nIt is, broadly, fine. You do have to "
                              "hold the lever.")},
                ],
                "repeat": "Setting 3. Hold the lever. You've made your peace with it.",
            },
            "b": {
                "kind": "npc",
                "emoji": "🐈",
                "name": "The depot cat",
                "lines": [
                    {"text": ("There is a cat asleep on a crate of flares.\n\n"
                              "Nobody has explained the cat. You get the impression that "
                              "asking would mark you out as new.")},
                    {"text": ("The cat has moved to a different crate and is asleep on "
                              "that one now.\n\nIt opens one eye, establishes that you "
                              "are not food, and closes it again.")},
                    {"text": ("Jofrog is standing near the cat, not touching it, at a "
                              "distance he has clearly calculated.\n\n"
                              "\"I am told they come to you,\" he says quietly, without "
                              "moving. \"I am being extremely available.\"")},
                ],
                "repeat": "Asleep. Somewhere new. Unbothered.",
            },
            "w": {
                "kind": "cache",
                "emoji": "📦",
                "name": "Unsorted intake",
                "grant": {"gold": 200, "lootbox": "common", "wood": 20},
            },
            "x": {
                "kind": "cache",
                "emoji": "🧃",
                "name": "The good vending machine",
                "grant": {"gold": 150, "lootbox": "uncommon"},
            },
            "y": {
                "kind": "note",
                "emoji": "🖼",
                "name": "The wall of photographs",
                "text": (
                    "Four years of squad photos, pinned in rough order.\n\n"
                    "The oldest ones have more people in them. Nobody has arranged "
                    "them to make that point; it's just what happened when they were "
                    "pinned up in order."
                ),
            },
            "z": {
                "kind": "note",
                "emoji": "🧯",
                "name": "The evacuation plan",
                "text": (
                    "A laminated floor plan of a building that is not this building.\n\n"
                    "Somebody has crossed out the address and written *close enough* "
                    "underneath, and somebody else has added *it really isn't*."
                ),
            },
            "n": {
                "kind": "cache",
                "emoji": "📥",
                "name": "The in-tray",
                "grant": {"gold": 250, "lootbox": "uncommon"},
            },
            "q": {
                "kind": "npc",
                "emoji": "📌",
                "name": "The crooked banner",
                "lines": [
                    {"text": ("**TEAM CASCADE — WE PUT IT BACK**\n\n"
                              "Hand-painted, and hung about four degrees off true.\n\n"
                              "Someone has pencilled underneath, in much smaller letters: "
                              "*mostly*.")},
                ],
                "repeat": "Still crooked. Still mostly.",
            },
            "D": {
                "kind": "npc",
                "emoji": "🎩",
                "name": "Dolphe",
                "lines": [
                    {"text": ("He's reading something and doesn't look up.\n\n"
                              "\"You're the one from the lab.\" A pause. \"Sit down, don't "
                              "sit down, I'm not going to make it weird.\"\n\n"
                              "He puts the paper down. He does look up.\n\n"
                              "\"Welcome to Team Cascade. We clean up what the Cascade left "
                              "behind. It's dangerous, it doesn't pay, and I'm not going to "
                              "pretend otherwise at you.\"")},
                    {"text": ("\"The banner was Blueflame's idea. He hung it at four in the "
                              "morning and it's been crooked ever since.\"\n\n"
                              "\"I've decided that's character.\"")},
                ],
                "repeat": "\"Board's over there when you want it.\"",
            },
            "M": {
                "kind": "exit",
                "emoji": "🚪",
                "name": "East — the Ops Deck",
                "to_area": "hub_ops",
                "to": [1, 3],
            },
            "W": {
                "kind": "exit",
                "emoji": "🚪",
                "name": "West — the Armory",
                "to_area": "hub_armory",
                "to": [7, 3],
            },
            "S": {
                "kind": "exit",
                "emoji": "🚪",
                "name": "South — the Mess",
                "to_area": "hub_mess",
                "to": [4, 1],
            },
        },
    },

    "hub_ops": {
        "name": "Cascade Central — The Ops Deck",
        "region": "Team Cascade",
        "blurb": "Six screens, four of them showing the same thing, one showing a card game.",
        "grid": [
            "#########",
            "#ss#J#ss#",
            "#..QO...#",
            "#W..@..T#",
            "#.......#",
            "#ss###ss#",
            "#########",
        ],
        "legend": {
            "s": {"kind": "decor", "emoji": "🖥"},
            "Q": {
                "kind": "station",
                "emoji": "📇",
                "name": "The duty roster",
                "panel": "squad",
                "feature": "squad",
            },
            "O": {
                "kind": "mission",
                "emoji": "🎯",
                "name": "The training floor",
                "mission": "pr5_ops_deck",
            },
            "J": {
                "kind": "npc",
                "emoji": "🤖",
                "name": "Jofrog",
                "lines": [
                    {"text": ("He is standing at parade rest facing a wall.\n\n"
                              "\"I am told I do not have to stand behind you. I am standing "
                              "behind you anyway.\"\n\nA pause.\n\n"
                              "\"It is a preference now. That is the difference.\"")},
                    {"text": ("\"Four of you go out. That is the rule. I have run the "
                              "numbers on three and the numbers are rude.\"\n\n"
                              "He brightens considerably.\n\n"
                              "\"Would you like to see them?\"")},
                    {"text": ("\"I have been given a locker. There is nothing to put in "
                              "it.\"\n\nHe considers this.\n\n"
                              "\"I am told that is a normal problem. I am enjoying it.\"")},
                ],
                "repeat": "\"Still here. Still a preference.\"",
            },
            "T": {
                "kind": "npc",
                "emoji": "🃏",
                "name": "The card game",
                "lines": [
                    {"text": ("Two off-duty operators and a screen that is supposed to be "
                              "showing the northern relay.\n\n"
                              "\"It's fine,\" one says, not looking up. \"The relay's been "
                              "fine for six years.\"\n\n"
                              "The other one wins. Neither of them mentions the relay again.")},
                ],
                "repeat": "The game is still going. The relay is still not on screen.",
            },
            "W": {
                "kind": "exit",
                "emoji": "🚪",
                "name": "West — the Atrium",
                "to_area": "hub_atrium",
                "to": [9, 4],
            },
        },
    },

    "hub_armory": {
        "name": "Cascade Central — The Armory",
        "region": "Team Cascade",
        "blurb": "Everything is labelled. The labels are in a handwriting that takes itself seriously.",
        "grid": [
            "#########",
            "#rr#R#rr#",
            "#..GV...#",
            "#F..@..E#",
            "#.......#",
            "#rr###rr#",
            "#########",
        ],
        "legend": {
            "r": {"kind": "decor", "emoji": "🗃"},
            "V": {
                "kind": "mission",
                "emoji": "🧰",
                "name": "The kit-out bench",
                "mission": "pr6_armory",
            },
            "R": {
                "kind": "npc",
                "emoji": "🛡",
                "name": "Refender",
                "lines": [
                    {"text": ("\"Offense and defense are the same decision made twice.\"\n\n"
                              "He says this as a greeting. He appears to think it is one.\n\n"
                              "\"Most people gear for damage and then die. Most people are "
                              "also very fast about it, so at least it's efficient.\"")},
                    {"text": ("\"You'll want to level what you have before you chase what "
                              "you don't.\"\n\nHe taps a shelf.\n\n"
                              "\"This is not advice about gear. But it works on gear.\"")},
                    {"text": ("He is rearranging a shelf that was already arranged.\n\n"
                              "\"Balance,\" he says, moving a box four inches left, \"is "
                              "not a thing you achieve. It is a thing you maintain.\"\n\n"
                              "He moves it back.")},
                ],
                "repeat": "\"Come back when something's broken. Something usually is.\"",
            },
            "F": {
                "kind": "station",
                "emoji": "⚒",
                "name": "The forge bench",
                "panel": "forge",
                "feature": "forge",
            },
            "G": {
                "kind": "station",
                "emoji": "🏷",
                "name": "The requisitions counter",
                "panel": "shop",
                "feature": "base",
            },
            "E": {
                "kind": "exit",
                "emoji": "🚪",
                "name": "East — the Atrium",
                "to_area": "hub_atrium",
                "to": [1, 4],
            },
        },
    },

    "hub_mess": {
        "name": "Cascade Central — The Mess",
        "region": "Team Cascade",
        "blurb": "Warm, loud, and the only room in the building anyone decorated on purpose.",
        "grid": [
            "#########",
            "#tt.N.tt#",
            "#t.VX..t#",
            "#..B.C..#",
            "#t..@..t#",
            "#tt.G.tt#",
            "#########",
        ],
        "legend": {
            "t": {"kind": "decor", "emoji": "🪑"},
            "V": {
                "kind": "station",
                "emoji": "🎴",
                "name": "Chary's booth",
                "panel": "exchange",
                "feature": "exchange",
            },
            "X": {
                "kind": "mission",
                "emoji": "🍜",
                "name": "The long table",
                "mission": "pr7_the_mess",
            },
            "C": {
                "kind": "npc",
                "emoji": "🍲",
                "name": "The counter",
                "lines": [
                    {"text": ("A pot, a ladle, and a sign reading TAKE WHAT YOU NEED in "
                              "the Armory handwriting.\n\n"
                              "Underneath, in Blueflame's: *and then take a bit more, "
                              "you look terrible*.")},
                ],
                "repeat": "The pot is never empty. Nobody has ever seen it filled.",
            },
            "N": {
                "kind": "exit",
                "emoji": "🚪",
                "name": "North — the Atrium",
                "to_area": "hub_atrium",
                "to": [5, 5],
            },
            "B": {
                "kind": "npc",
                "emoji": "🔥",
                "name": "Blueflame",
                "lines": [
                    {"text": ("He is eating alone at a table built for eight, and looks "
                              "completely content about it.\n\n"
                              "\"You're the lab one.\" He gestures at the bench opposite "
                              "with a fork. \"Everything burns eventually. I just prefer "
                              "to be early.\"\n\nHe goes back to eating.\n\n"
                              "\"That's a joke. Mostly.\"")},
                    {"text": ("\"I'm not Cascade, before someone tells you badly. World "
                              "Aligners. I'm here because the food's better and Dolphe "
                              "doesn't ask me things.\"\n\nA beat.\n\n"
                              "\"He asks me things constantly. But politely, so it "
                              "doesn't count.\"")},
                    {"text": ("\"Josh'll turn up eventually. He always does, usually "
                              "somewhere he shouldn't be.\"\n\n"
                              "The cheerfulness doesn't move, but something under it "
                              "does.\n\n\"Don't take it personally when he doesn't like "
                              "you. It's not about you.\"")},
                ],
                "repeat": "\"Sit down or don't. The soup's the same either way.\"",
            },
            "G": {
                "kind": "exit",
                "emoji": "🚪",
                "name": "South — the Gatehouse",
                "to_area": "hub_gate",
                "to": [4, 2],
            },
        },
    },

    "hub_gate": {
        "name": "Cascade Central — The Gatehouse",
        "region": "Team Cascade",
        "blurb": "The last warm room before the cold one. Somebody has written GOOD LUCK on the door in marker.",
        "grid": [
            "#########",
            "#cc.N.cc#",
            "#c.Y.Z.c#",
            "#..K.L..#",
            "#c..@..c#",
            "#cc.D.cc#",
            "#########",
        ],
        "legend": {
            "c": {"kind": "decor", "emoji": "📦"},
            "Y": {
                "kind": "mission",
                "emoji": "📡",
                "name": "The northern relay job",
                "mission": "pr9_first_contract",
                "requires_mission": "pr8_the_base",
                "locked_text": "Dolphe hasn't handed you a real one yet. Finish settling in first.",
            },
            "Z": {
                "kind": "mission",
                "emoji": "🛻",
                "name": "The road south",
                "mission": "pr10_the_convoy",
                "requires_mission": "pr9_first_contract",
                "locked_text": "You'd have to be coming back from something first.",
            },
            "D": {
                "kind": "mission",
                "emoji": "🚪",
                "name": "The door, with GOOD LUCK on it",
                "mission": "pr11_the_gate",
                "requires_mission": "pr10_the_convoy",
                "locked_text": "Not yet. Dolphe wants a word before you go out properly.",
            },
            "L": {
                "kind": "npc",
                "emoji": "🧤",
                "name": "The lockers",
                "lines": [
                    {"text": ("Thirty lockers, most of them open and empty. Six are shut.\n\n"
                              "One has a photograph taped inside the door, face-in, so you "
                              "would have to be the person it belongs to to see it.")},
                ],
                "repeat": "Six still shut.",
            },
            "N": {
                "kind": "exit",
                "emoji": "🚪",
                "name": "North — the Mess",
                "to_area": "hub_mess",
                "to": [4, 5],
            },
            "K": {
                "kind": "npc",
                "emoji": "🚏",
                "name": "The board by the door",
                "lines": [
                    {"text": ("A roster of everyone currently outside the walls, written "
                              "up in the same serious handwriting as the Armory labels.\n\n"
                              "Most names have a time next to them. Two don't.\n\n"
                              "Nobody has erased them.")},
                ],
                "repeat": "The two names without times are still there.",
            },
        },
    },
}


# Which area a new player starts in, and where.
STARTING_AREA = "lab_cell"


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


def is_decor(area: dict, x: int, y: int) -> bool:
    """A DECORATION tile: drawn, never walked on, never interacted with.

    Decoration is how a room stops being a corridor with content in it --
    trees, crates, terminals, a coffee machine. It exists purely so the
    map reads as a place.

    IT IS SOLID, and that is the design decision worth recording. The
    density rules (MIN_DENSITY / MAX_DISTANCE_TO_CONTENT) exist because
    every step is a Discord round-trip, so a walkable tile with nothing
    on it is pure friction -- and decoration is, by definition, tiles
    with nothing on them. Making it non-walkable means a room can be
    decorated as heavily as it likes without a single one of those rules
    being relaxed: a tree you can't walk through is still a tree, and the
    walkable area stays exactly as dense as the checker demands.
    """
    char = tile_char(area, x, y)
    if char is None or char in (WALL_CHAR, FLOOR_CHAR, SPAWN_CHAR):
        return False
    entry = (area.get("legend") or {}).get(char) or {}
    return entry.get("kind") == "decor"


def is_wall(area: dict, x: int, y: int) -> bool:
    """Whether (x, y) blocks movement. Decoration counts -- see is_decor."""
    char = tile_char(area, x, y)
    return char is None or char == WALL_CHAR or is_decor(area, x, y)


def tile_content_raw(area: dict, x: int, y: int) -> dict | None:
    """The legend entry for (x, y), INCLUDING decoration.

    Only the renderer wants this -- it needs a decor tile's emoji to draw
    it. Everything else should use tile_content, which hides decoration
    so that no interaction path has to remember it exists."""
    char = tile_char(area, x, y)
    if char is None or char in (WALL_CHAR, FLOOR_CHAR, SPAWN_CHAR):
        return None
    return area.get("legend", {}).get(char)


def tile_content(area: dict, x: int, y: int) -> dict | None:
    """The INTERACTIVE legend entry for (x, y), if the tile has one.

    Decoration returns None: it is scenery, it cannot be stood on (see
    is_decor), and treating it as content would put trees in the legend
    and in the "you're standing on" line."""
    entry = tile_content_raw(area, x, y)
    if entry and entry.get("kind") == "decor":
        return None
    return entry


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
