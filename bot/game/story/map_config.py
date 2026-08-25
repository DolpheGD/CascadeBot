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
            "#....S..Y..#",
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
            "Y": {
                "kind": "exit",
                "emoji": "🧱",
                "name": "The back door — the yard",
                "to_area": "hub_yard",
                "to": [3, 4],
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
            "#..L....#",
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
            "L": {
                # CHAPTER THREE OPENS HERE, on Cascade's own Ops Deck --
                # deliberately not at the depot. The whole argument of
                # Chapter One was that the Aligners had to leave in order
                # to move quickly; the chapter that follows their being
                # RIGHT should start with them walking back in with the
                # evidence and a room full of people who now have to
                # listen.
                "kind": "mission",
                "emoji": "🗃",
                "name": "Nineteen crates, on the long table",
                "mission": "c3m1_the_long_room",
                "requires_mission": "c2m6_mr_r",
                "locked_text": "The Ops Deck is doing an ordinary day. Long may it last.",
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
        # Grown by two rows for Act Three. The Gatehouse is where every
        # job now launches from, so the three new missions live here
        # rather than in a new room -- a fourth area between "the hub"
        # and "the door out" would be a corridor with tiles in it.
        "grid": [
            "#########",
            "#cc.N.cc#",
            "#c.Y.Z.c#",
            "#..K.L..#",
            "#c.P.Q.c#",
            "#c..R..c#",
            "#cA.@..c#",
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
            "P": {
                "kind": "mission",
                "emoji": "🧹",
                "name": "The yard sweep, with Josh",
                "mission": "pr12_quiet_yard",
                "requires_mission": "pr10_the_convoy",
                "locked_text": "Josh isn't taking you anywhere yet.",
            },
            "Q": {
                "kind": "mission",
                "emoji": "🕴",
                "name": "The man in the south yard",
                "mission": "pr13_the_figure",
                "requires_mission": "pr12_quiet_yard",
                "locked_text": "There's nobody out there. Yet.",
            },
            "R": {
                "kind": "mission",
                "emoji": "📡",
                "name": "Something came over the ridge",
                "mission": "pr14_what_he_sent",
                "requires_mission": "pr13_the_figure",
                "locked_text": "Nothing's coming. Enjoy it.",
            },
            "D": {
                "kind": "mission",
                "emoji": "🚪",
                "name": "The door, with GOOD LUCK on it",
                "mission": "pr11_the_gate",
                # Now gated behind the WHOLE of Act Three rather than the
                # convoy, so the gate is the last thing you reach and the
                # call to action lands after the reason for it exists.
                "requires_mission": "pr14_what_he_sent",
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
            # CHAPTER ONE'S DOOR. An EXIT rather than a mission tile, so
            # the Aligner base is a place you can walk to and back from
            # for the rest of the game, not a cutscene you get sent to.
            # The prologue's own last mission still sits on D above; this
            # only appears once that's done.
            "A": {
                "kind": "exit",
                "emoji": "🛻",
                "name": "The car park — somebody's waiting",
                "to_area": "aligner_dock",
                "to": [3, 2],
                "requires_mission": "pr11_the_gate",
                "locked_text": "Just a car park. Two vans and a puddle.",
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

    # ==================================================================
    # CHAPTER ONE — THE WORLD ALIGNERS
    #
    # A second hub, deliberately built as the ANTI-Cascade-Central.
    # Cascade Central is warm, decorated, over-staffed and institutional;
    # the Aligners work out of a half-converted freight depot with four
    # people in it. Every room should read as "we left somewhere else to
    # be here, and we are not entirely sure it was worth it".
    #
    # Three areas, mirroring the prologue's shape so a player who learned
    # Cascade's building can read this one at a glance:
    #
    #     aligner_dock     you arrive here; the way back to Cascade
    #     aligner_floor    the main room, the people, the missions
    #     aligner_records  Josh's wall of two years' work on Mr. R
    #
    # ==================================================================
    # ==================================================================
    # THE YARD, THE ARCHIVE AND THE BUNKS
    #
    # Three rooms added to Team Cascade after the story was finished, for
    # the same reason the hub had five rooms and not two: a base you only
    # ever pass through is a corridor with a name. These are places to
    # stand still in. Almost nothing here is required -- one commission
    # board, a lot of notes, and the crew talking about what just
    # happened to them.
    # ==================================================================
    "hub_yard": {
        "name": "Cascade Central — The Back Yard",
        "region": "Team Cascade",
        "blurb": "Gravel, a pallet stack, and the board everybody actually reads.",
        "grid": [
            "###########",
            "#y..B..y..#",
            "#..P...T..#",
            "#y..@..C.y#",
            "#..S...N..#",
            "###########",
        ],
        "legend": {
            "y": {
                "kind": "decor",
                "emoji": "🪨",
                "name": "Gravel and weeds",
            },
            "B": {
                "kind": "board",
                "emoji": "📋",
                "name": "The commission board",
                "text": ("Corkboard under a plastic hood, because the last one "
                         "dissolved in the rain and Josh took it personally.\n\n"
                         "People pin work here that needs doing and cannot be "
                         "made into an order. Some of it is Cascade business. "
                         "Some of it is somebody asking a favour in the only "
                         "way they know how to ask."),
            },
            "P": {
                "kind": "npc",
                "emoji": "📦",
                "name": "The pallet stack",
                "repeat": True,
                "lines": [
                    {"text": ("Crates from six different suppliers, stacked by "
                              "somebody with strong opinions about weight "
                              "distribution.")},
                    {"text": ("One crate is stencilled ENTROSPIRE and has been "
                              "turned so the stencil faces the wall.")},
                    {"text": ("Somebody has written DO NOT SIT ON THIS on the top "
                              "crate. Somebody else has worn a smooth patch into "
                              "it anyway.")},
                ],
            },
            "T": {
                "kind": "note",
                "emoji": "🚚",
                "name": "The truck that never leaves",
                "text": ("Flatbed, tyres good, tank full, keys in a magnetic box "
                         "under the wheel arch that everybody knows about.\n\n"
                         "It is kept ready. Nobody has said out loud what it is "
                         "kept ready *for*, and nobody has suggested using it for "
                         "anything else either."),
            },
            "C": {
                "kind": "cache",
                "emoji": "🧯",
                "name": "The emergency locker",
                "text": ("Wall locker, red, with a checklist taped inside the "
                         "door. Every line is initialled.\n\n"
                         "Whoever has been checking it monthly for four years has "
                         "never once had to open it in anger, and has kept "
                         "checking it anyway."),
                "grant": {"gold": 1800, "evolution_fragments": 90, "cores": 140},
            },
            "S": {
                "kind": "exit",
                "emoji": "🚪",
                "name": "In — the Atrium",
                "to_area": "hub_atrium",
                "to": [6, 12],
            },
            "N": {
                "kind": "exit",
                "emoji": "🛏",
                "name": "The side door — the bunks",
                "to_area": "hub_bunks",
                "to": [1, 3],
                # GATED, and it was not.
                #
                # The bunks hold s4_the_photograph, which is Chapter Four
                # material and pays like it: 34,000 gold, 1,700 cores,
                # 1,200 fragments, a mythic and two mythic lootboxes. The
                # room sat two ungated doors from the Atrium, so a player
                # who had just finished the PROLOGUE could walk in and
                # take all of it. Measured, that one room was 34,000 of
                # the 45,170 gold reachable at that point.
                #
                # Gating the DOOR rather than the tile keeps the room
                # coherent -- the photograph, the go-bag and Jofrog's
                # conversation are one scene and should arrive together.
                "requires_mission": "c4m1_the_audit_begins",
                "locked_text": ("Somebody is asleep in there. Whatever this is "
                                "about, it can wait."),
            },
        },
    },

    "hub_bunks": {
        "name": "Cascade Central — The Bunks",
        "region": "Team Cascade",
        "blurb": "Eight beds, four of them made, and a window somebody keeps opening.",
        "grid": [
            "##########",
            "#Y.b.b.b.#",
            "#..K...W.#",
            "#..@.b.M.#",
            "#h.b.b.R.#",
            "##########",
        ],
        "legend": {
            "b": {
                "kind": "decor",
                "emoji": "🛏",
                "name": "A bunk",
            },
            "Y": {
                "kind": "exit",
                "emoji": "🚪",
                "name": "Out — the back yard",
                "to_area": "hub_yard",
                "to": [7, 4],
            },
            "K": {
                "kind": "npc",
                "emoji": "🧦",
                "name": "The drying rack",
                "repeat": True,
                "lines": [
                    {"text": "Four pairs of socks. Three people live here."},
                    {"text": ("Somebody has labelled theirs. Somebody else has "
                              "labelled the same pair, underneath, differently.")},
                ],
            },
            "W": {
                "kind": "note",
                "emoji": "🪟",
                "name": "The window that keeps getting opened",
                "text": ("Painted shut twice. Opened twice.\n\n"
                         "Refender opens it because the room gets stuffy. Jofrog "
                         "closes it because the room gets cold. Neither of them "
                         "has ever mentioned it to the other, and both of them "
                         "know exactly who is doing it."),
            },
            "M": {
                "kind": "mission",
                "emoji": "📷",
                "name": "The photograph on the bulkhead",
                "mission": "s4_the_photograph",
            },
            "R": {
                "kind": "cache",
                "emoji": "🎒",
                "name": "Somebody's go-bag",
                "text": ("Packed, zipped, and sitting at the foot of a made bed.\n\n"
                         "Two days of food, a spare coat, and a photograph face "
                         "down at the bottom. It has been packed for a long time. "
                         "The food has been rotated."),
                "grant": {"gold": 2400, "evolution_fragments": 110, "shards": 90},
            },
            "h": {
                "kind": "decor",
                "emoji": "🔥",
                "name": "The heater, ticking",
            },
        },
    },

    "aligner_dock": {
        "name": "Sixteen Freight — The Dock",
        "region": "World Aligners",
        "blurb": "A loading bay somebody has been living in. The shutters only open halfway now.",
        # Tightened from 11x8 after check_story measured 10% interactive
        # density and two corners five steps from anything. A loading bay
        # is meant to feel empty, but "empty" in a walking sim means the
        # player crosses six tiles of nothing to reach the next line of
        # dialogue -- so the room shrank and gained two things to look at.
        "grid": [
            "#########",
            "#k.C.V.k#",
            "#.J...D.#",
            "#k.N.S.k#",
            "#...@...#",
            "#########",
        ],
        "legend": {
            "k": {"kind": "decor", "emoji": "🧰"},
            "V": {
                "kind": "note",
                "emoji": "🚚",
                "name": "The van",
                "text": ("A depot van with the Cascade wordmark sanded off the door, "
                         "badly, by somebody who then lost interest.\n\n"
                         "The tax disc is nine days old. The lease on this building is "
                         "eleven."),
            },
            "S": {
                "kind": "note",
                "emoji": "🔩",
                "name": "The shutter",
                "text": ("It opens to about waist height and stops. There is a toolbox "
                         "open underneath it and a job written on the lid in marker.\n\n"
                         "**FIX SHUTTER** — and under that, in a different hand, "
                         "*it's fine, we duck*."),
            },
            "C": {
                "kind": "exit",
                "emoji": "🚪",
                "name": "The road back — Cascade Central",
                "to_area": "hub_gate",
                "to": [3, 6],
            },
            "N": {
                "kind": "exit",
                "emoji": "🚧",
                "name": "Inward — the floor",
                "to_area": "aligner_floor",
                "to": [5, 2],
            },
            "J": {
                "kind": "mission",
                "emoji": "🪧",
                "name": "Josh, waiting by the shutter",
                "mission": "c1m1_sixteen_freight",
            },
            "D": {
                "kind": "npc",
                "emoji": "🐬",
                "name": "Dolphin",
                # DOLPHIN IS THE CHAPTER'S COMIC REGISTER and its longest
                # optional thread. Every serious thing about him -- the
                # amnesia, HHyper, his brother -- is placed in optional
                # NPC lines rather than in a mission beat, per the brief:
                # the main line stays clear to follow, and the mystery is
                # something you go and find.
                "lines": [
                    {"text": ("He is wearing a coat that is very nearly Dolphe's coat, in "
                              "a blue that is very nearly Dolphe's blue.\n\n"
                              "\"Oh — hello. Hi. You're the lab one.\" He straightens up "
                              "and does a voice that is almost exactly Dolphe's voice, "
                              "and then stops doing it, because you are clearly not "
                              "fooled.\n\n"
                              "\"Sorry. Force of habit. I'm Dolphin.\"")},
                    {"text": ("\"So the coat thing is — right, so. Josh needs someone to "
                              "walk into Cascade rooms and be *nodded at*. That's the "
                              "whole job. I get nodded at.\"\n\n"
                              "He seems genuinely proud of this.\n\n"
                              "\"I've never actually signed anything. Once. I signed one "
                              "thing. It was a lunch order and it caused a *lot* of "
                              "trouble.\"")},
                    {"text": ("\"People think I want to *be* him. I don't.\" He considers "
                              "it properly, which is worse. \"I want people to look at me "
                              "like that. That's different. Dolphe has to decide things. "
                              "Have you seen the things he has to decide? No thank you.\"")},
                    {"text": ("\"Can I ask you something and you not make it weird.\"\n\n"
                              "He does not wait.\n\n"
                              "\"Do you think Refender would — no. No, forget it. She "
                              "corrected my *posture* last week. Out loud. In front of "
                              "Jofrog.\"\n\n"
                              "He goes quiet for slightly too long.\n\n\"It was still the "
                              "nicest thing anyone said to me that week.\"")},
                    {"text": ("\"I've got a brother. Dolpo. He flies with the H-Nation "
                              "now, HHyper's lot, which sounds worse than it is.\"\n\n"
                              "A pause.\n\n\"It might be exactly as bad as it is. We don't "
                              "talk. He'd tell you we don't talk because I'm a "
                              "disappointment, and he'd be about forty percent right, "
                              "which is the annoying amount.\"")},
                    {"text": ("\"Here's the bit I don't tell people.\" He says it lightly, "
                              "the way you'd mention weather.\n\n"
                              "\"I don't remember anything before about two years ago. Not "
                              "hazy. *Nothing.* I know my own name because Dolpo told me "
                              "it, and I know I'm his brother because he says so, and I "
                              "have decided to believe him, because the alternative is a "
                              "very long afternoon.\"")},
                    {"text": ("\"Two years,\" he says. \"Josh has been chasing his man for "
                              "two years. I've *existed* for two years.\"\n\n"
                              "He laughs at it. It doesn't take.\n\n"
                              "\"I mentioned that to him once. He didn't laugh either. He "
                              "wrote it on the wall in there, and he's never brought it "
                              "up since, and I would quite like it if he did.\"")},
                ],
                "repeat": "\"Still here. Still nearly him. It's a living.\"",
            },
        },
    },

    "aligner_floor": {
        "name": "Sixteen Freight — The Floor",
        "region": "World Aligners",
        "blurb": "Four people, a table meant for forty, and every light that still works pointed at one wall.",
        "grid": [
            "#############",
            "#ss..D..S..s#",
            "#s....Q....s#",
            "#..R..T..F..#",
            "#sU...Y....s#",
            "#ss..B..M..s#",
            "#s..E.@.C..s#",
            "#############",
        ],
        "legend": {
            "s": {"kind": "decor", "emoji": "📦"},
            "E": {
                # Opens only after Ashfield. The south building has been
                # there the whole chapter -- the key is taped under the
                # bench in Records from the moment you can reach it --
                # but there is no reason to go until the routing table
                # tells you Rohan has been reading everything Rex ever
                # filed.
                "kind": "exit",
                "emoji": "🔑",
                "name": "The south building",
                "to_area": "rex_workshop",
                "to": [4, 5],
                "requires_mission": "c1m3_ashfield",
                "locked_text": "Locked, and nobody has offered you the key.",
            },
            "C": {
                "kind": "mission",
                "emoji": "☕",
                "name": "Josh, with his coat still on",
                "mission": "c1m6_stay_out_of_it",
                "requires_mission": "c1m5_the_herald",
                "locked_text": "He's not back yet.",
            },
            "Y": {
                # Out into the yard, which only becomes a place once
                # there is something to defend it from.
                "kind": "exit",
                "emoji": "🚧",
                "name": "Out — the yard",
                "to_area": "depot_yard",
                "to": [5, 4],
                "requires_mission": "c3m6_the_bottom",
                "locked_text": "It's a car park. There's a puddle.",
            },
            "Q": {
                # CHAPTER TWO STARTS HERE, on the floor of the depot, at
                # six in the morning. Placed on a tile rather than
                # auto-playing after Chapter One: the overworld is the
                # way into every mission in the game, and one chapter
                # handing off to the next through a cutscene would be the
                # single place that isn't.
                "kind": "mission",
                "emoji": "📻",
                "name": "The good radio, on the table",
                "mission": "c2m1_the_fourteenth",
                "requires_mission": "c1m6_stay_out_of_it",
                "locked_text": "It's the middle of the night and everyone is asleep.",
            },
            "D": {
                "kind": "exit",
                "emoji": "🚧",
                "name": "Out — the Dock",
                "to_area": "aligner_dock",
                "to": [3, 4],
            },
            "U": {
                "kind": "exit",
                "emoji": "🪜",
                "name": "Up — the roof",
                "to_area": "aligner_roof",
                "to": [7, 2],
                "requires_mission": "c1m4_still_switched_on",
                "locked_text": ("Roof access. Blueflame has the key and has not "
                                "yet decided you are somebody who gets it."),
            },
            "S": {
                "kind": "exit",
                "emoji": "🗄",
                "name": "Through — the Records room",
                "to_area": "aligner_records",
                "to": [4, 4],
            },
            "T": {
                "kind": "mission",
                "emoji": "🗺",
                "name": "The table, and what's on it",
                "mission": "c1m2_the_pitch",
                "requires_mission": "c1m1_sixteen_freight",
                "locked_text": "They're still arguing. Give them the room.",
            },
            "M": {
                "kind": "mission",
                "emoji": "📻",
                "name": "The relay at Ashfield",
                "mission": "c1m3_ashfield",
                "requires_mission": "c1m2_the_pitch",
                "locked_text": "Nothing to go and look at yet.",
            },
            "R": {
                "kind": "npc",
                "emoji": "📐",
                "name": "Refender",
                "lines": [
                    {"text": ("She has laid out four sets of gear in four identical rows "
                              "and is adjusting the fourth by an amount you cannot see.\n\n"
                              "\"You're the one from Ocellios.\" Not a question. \"I've "
                              "read the intake note Cascade filed on you. It's three lines "
                              "and two of them are wrong.\"")},
                    {"text": ("\"I want to be clear that leaving Cascade was not a "
                              "*tantrum*.\" She does not look up. \"Cascade is a good "
                              "organisation that has become a large one. Large "
                              "organisations lose things. We lost a convoy in the spring "
                              "and the report took eleven weeks and concluded that it was "
                              "nobody's fault.\"\n\n"
                              "\"It was somebody's fault. I would simply like to know "
                              "whose.\"")},
                    {"text": ("\"Josh is not well. I'm aware that's blunt.\" She squares "
                              "the fourth row again. \"He is also correct, which is the "
                              "difficulty. If he were merely grieving I could look after "
                              "him. He is grieving *and* right, and those need opposite "
                              "handling.\"")},
                    {"text": ("On Dolphin, if you ask: \"He is not a spy. I checked — "
                              "thoroughly, and he never noticed, which rather settles "
                              "it.\"\n\nA pause.\n\n\"He is lonely and he is useful and "
                              "those are allowed to be two separate facts about a person. "
                              "Do not tell him I said the second one.\"")},
                ],
                "repeat": "\"Straighten that when you're done with it.\"",
            },
            "F": {
                "kind": "npc",
                "emoji": "🐸",
                "name": "Jofrog",
                "lines": [
                    {"text": ("\"You made it!\" He says this as though you had crossed an "
                              "ocean, rather than a car park.\n\n"
                              "\"Josh said you'd come and Refender said you wouldn't, and "
                              "I said I'd hold the bet, so now I owe myself money, which "
                              "I'm told isn't how betting works.\"")},
                    {"text": ("\"Everyone keeps asking whether we're *against* Cascade. "
                              "We're not! I like Cascade. Chary gives me the broken "
                              "biscuits.\"\n\nHe frowns at the difficulty of it.\n\n"
                              "\"We just want to be able to go and check a thing without "
                              "eleven people deciding first whether the thing is worth "
                              "checking. That's all it is. It's a very boring reason to "
                              "start a faction and I wish it were better.\"")},
                    {"text": ("\"Josh's wall used to be one piece of paper.\" He looks "
                              "toward the Records room the way you'd look at weather "
                              "coming in.\n\n\"I helped him put the second one up. I "
                              "haven't helped since. Not because he asked me not to.\"")},
                ],
                "repeat": "\"Still glad you came. That's not a bit, by the way.\"",
            },
            "B": {
                "kind": "npc",
                "emoji": "🔥",
                "name": "Blueflame",
                "lines": [
                    {"text": ("\"Told you Josh turns up somewhere he shouldn't be.\" He is "
                              "sitting on the table rather than at it. \"This is a "
                              "freight depot with a lease nobody's read. He's *thrilled*.\"")},
                    {"text": ("\"You want the honest version of why I'm here? The food's "
                              "worse.\" He shrugs. \"But nobody at Cascade ever told me "
                              "what we were actually doing. Here it's four people and a "
                              "wall and I can read the wall.\"")},
                    {"text": ("\"Ask him about Rex and he'll tell you the truth, which is "
                              "the problem. Most people lie about the bad one and you get "
                              "to move on politely.\"\n\nHe considers.\n\n\"He'll just "
                              "tell you. And then you're holding it too.\"")},
                ],
                "repeat": "\"Everything burns eventually. This place a bit faster, the wiring's awful.\"",
            },
        },
    },

    "aligner_records": {
        "name": "Sixteen Freight — Records",
        "region": "World Aligners",
        "blurb": "Two years of one man's work, on one wall, in one handwriting.",
        # One legend entry per CHARACTER, not per idea: check_story
        # rejects a letter used twice, because a legend maps a character
        # to a single tile and four 'W's would have made four identical
        # walls that all claim to be the whole wall. Split into the four
        # things actually pinned up, which is better writing anyway --
        # the wall becomes a case you read in pieces.
        "grid": [
            "#########",
            "#..W.M..#",
            "#...Z...#",
            "#T..L..P#",
            "#.......#",
            "#..C.O..#",
            "#...@...#",
            "#########",
        ],
        "legend": {
            "Z": {
                "kind": "puzzle",
                "puzzle_kind": "code",
                "emoji": "🔐",
                "name": "The cabinet nobody has a key for",
                # Chapter One material in a room the prologue opens. The
                # clue that solves it is something Refender says during
                # the pitch, so this gate is also what makes the puzzle
                # solvable rather than guessable.
                "requires_mission": "c1m2_the_pitch",
                "locked_text": ("A locked cabinet. You do not yet know how this "
                                "place files things, let alone the combination."),
                "text": ("Four-drawer steel cabinet, locked, with a four-letter "
                         "combination dial on the top drawer instead of a "
                         "keyhole.\n\n"
                         "Somebody has written on the dial housing in pencil, "
                         "very small: *ask the room*."),
                "clues": [
                    ("The drawers are labelled, top to bottom: ROUTES, OUTAGES, "
                     "HAULAGE, ASSETS."),
                    ("Refender, when you ask: \"Josh set that. He sets every "
                     "combination the same way — first letters, in the order "
                     "he'd file them.\""),
                    ("Filed the way Josh files things, those four subjects read "
                     "Assets, Haulage, Outages, Routes."),
                ],
                "answers": ["AHOR", "A H O R", "ahor"],
                "derivation": ("First letters of the four drawer subjects in "
                               "alphabetical order: Assets, Haulage, Outages, "
                               "Routes."),
                "on_solve": ("Four clicks and the drawer slides. Inside: a "
                             "bundle of freight manifests with the Cascade "
                             "letterhead cut off, and a smaller envelope with "
                             "nothing written on it at all."),
                "on_fail": "The dial spins back to where it started.",
                "grant": {"gold": 5200, "evolution_fragments": 260, "cores": 340,
                          "item": "epic"},
            },
            "W": {
                "kind": "note",
                "emoji": "📄",
                "name": "The wall itself",
                "text": ("Paper, edge to edge, four sheets high.\n\n"
                         "Every sheet is annotated in the same hand, and the annotations "
                         "get shorter as they get more recent. The early ones argue with "
                         "themselves. The late ones just say **where** and **when**."),
            },
            "M": {
                "kind": "note",
                "emoji": "🗺",
                "name": "The route maps",
                "text": ("Nineteen routes traced in nineteen colours, all of them "
                         "entering the same forty miles of country north of Ashfield.\n\n"
                         "Only four have a line coming back out, and all four of those "
                         "are drawn in pencil with a question mark on them."),
            },
            "T": {
                "kind": "note",
                "emoji": "📅",
                "name": "The dates, in Refender's hand",
                "text": ("A different handwriting from everything else on this wall: "
                         "smaller, straighter, and pinned up slightly crooked as though "
                         "by someone in a hurry to be done with it.\n\n"
                         "Fourteen dates over two years. Next to each one, a Cascade "
                         "reference number and a single word: *received*.\n\n"
                         "At the bottom: *he will not keep these. so I do.*"),
            },
            "C": {
                "kind": "note",
                "emoji": "📷",
                "name": "The photograph of the driller",
                "text": ("A Xender deep-driller the size of a house, lying in two "
                         "pieces in a field, photographed from a long way off.\n\n"
                         "The cut is perfectly straight and goes all the way through.\n\n"
                         "Somebody has drawn an arrow to a patch of plating near the "
                         "cut, where one character has been scratched into the metal "
                         "by hand: **R**."),
            },
            "L": {
                "kind": "exit",
                "emoji": "🚧",
                "name": "Back — the Floor",
                "to_area": "aligner_floor",
                "to": [8, 2],
            },
            "P": {
                "kind": "note",
                "emoji": "🖊",
                "name": "The one sheet that isn't a map",
                "text": ("A list of nineteen Xender survey teams, by number, with dates.\n\n"
                         "All nineteen went into the same stretch of country. None of "
                         "them filed anything on the way out.\n\n"
                         "At the bottom, in the same hand: *they are not hiding it. "
                         "nobody is looking.*"),
            },
            "O": {
                "kind": "npc",
                "emoji": "🕯",
                "name": "The corner Josh doesn't stand in",
                "lines": [
                    {"text": ("A workbench, pushed against the wall and kept clear.\n\n"
                              "There is nothing on it. There is a chair at it. The chair "
                              "is at the angle a chair ends up at when somebody stood up "
                              "and meant to come back.")},
                    {"text": ("Taped under the lip of the bench, where you would only find "
                              "it by not looking:\n\n"
                              "A workshop key, and a note that says *R — south building, "
                              "I've moved your good screwdriver, it's behind the thing you "
                              "said wasn't a shelf. — J*")},
                ],
                "repeat": "The chair is still at that angle.",
            },
        },
    },

    # ------------------------------------------------------------------
    # REX'S WORKSHOP — the chapter's quiet room, and its loudest one.
    #
    # The whole point of this area is that NOBODY EXPLAINS IT. Josh
    # cannot go in and does not pretend otherwise; Refender has been in
    # once and files it under things she does not discuss. So the story
    # here is told by objects in the positions their owner left them in,
    # and the player is the one who walks around and works it out.
    #
    # It is also where the chapter's last fight arrives, which is
    # deliberate: the one room in the game nobody wanted to disturb is
    # the room Rohan sends something into.
    # ------------------------------------------------------------------
    "rex_workshop": {
        "name": "The South Building — Rex's Workshop",
        "region": "World Aligners",
        "blurb": "Still powered. Still warm. Two years is not long enough for the dust to settle properly.",
        "grid": [
            "###########",
            "#b.T.M.L.b#",
            "#.........#",
            "#W...K...J#",
            "#....N....#",
            "#b..H.@..b#",
            "###########",
        ],
        "legend": {
            "b": {"kind": "decor", "emoji": "🪛"},
            "H": {
                "kind": "exit",
                "emoji": "🚪",
                "name": "Out — back to the Floor",
                "to_area": "aligner_floor",
                "to": [4, 5],
            },
            "K": {
                "kind": "mission",
                "emoji": "💡",
                "name": "The bench, and the light above it",
                "mission": "c1m4_still_switched_on",
            },
            "J": {
                "kind": "mission",
                "emoji": "📡",
                "name": "Something is coming up the access road",
                "mission": "c1m5_the_herald",
                "requires_mission": "c1m4_still_switched_on",
                "locked_text": "The road is empty. Enjoy that.",
            },
            "T": {
                "kind": "note",
                "emoji": "🔧",
                "name": "The tools",
                "text": ("Laid out in the order you would use them, not the order you "
                         "would store them.\n\n"
                         "A job was in progress here. It is still in progress here. "
                         "Nobody has had the authority, or the stomach, to declare it "
                         "finished."),
            },
            "M": {
                "kind": "note",
                "emoji": "☕",
                "name": "The mug",
                "text": ("Two thirds full, and long past the point of being anything "
                         "but a ring and a stain.\n\n"
                         "Somebody has washed the *outside* of it, carefully, and put it "
                         "back exactly where it was. More than once, by the look of the "
                         "ring."),
            },
            "L": {
                "kind": "note",
                "emoji": "📻",
                "name": "The receiver, still on",
                "text": ("A hand-built set, running off the mains, tuned to the northern "
                         "line and left recording.\n\n"
                         "The tape reel is full and has been full for a long time. The "
                         "counter reads a number in the tens of thousands.\n\n"
                         "Rex was listening to the Ashfield relay two years before "
                         "anybody else thought to."),
            },
            "N": {
                # CHAPTER TWO'S DOOR. Same pattern as the Gatehouse door
                # into the depot: an exit, not a cutscene, so the north
                # stays somewhere you can walk back from.
                "kind": "exit",
                "emoji": "🧭",
                "name": "North — the access road",
                "to_area": "north_checkpoint",
                "to": [5, 5],
                "requires_mission": "c2m1_the_fourteenth",
                "locked_text": "There's nothing north of here but forty miles of nothing.",
            },
            "W": {
                "kind": "note",
                "emoji": "📓",
                "name": "The notebook",
                "text": ("Open, face-down, at the page he was on.\n\n"
                         "Most of it is measurements. The last written page is not.\n\n"
                         "*second and a half. every time. it is not the equipment.*\n\n"
                         "*somebody is copying the line. told J. J thinks I need a "
                         "holiday. going to go and look at the mast myself on the 14th.*\n\n"
                         "There is no entry for the 14th, or for any day after it."),
            },
        },
    },

    # ==================================================================
    # CHAPTER TWO — THE FORTY MILES
    #
    # The country north of Ashfield, where nineteen survey teams went in
    # and none came out. Three areas, and they are deliberately the
    # emptiest maps in the game:
    #
    #     north_checkpoint  an H-Nation border post that should not be
    #                       there, which is how you learn somebody else
    #                       is also looking
    #     survey_site       the answer to the nineteen teams. Almost
    #                       entirely notes -- this is the chapter's
    #                       environmental payload, the way Rex's
    #                       workshop was Chapter One's
    #     the_cut           where Rohan is. One room, four things in it,
    #                       and no way to make it feel bigger
    #
    # Emptiness has to be EARNED against the density rule, so these use
    # small grids rather than sparse big ones -- the same lesson the
    # Dock taught when it failed at 10% interactive.
    # ==================================================================
    # ==================================================================
    # OPTIONAL BRANCHES
    #
    # Rooms hanging off the main route that the story never sends anybody
    # to. Everything in them is skippable, which is the point: the main
    # line stays tight, and the player who wants to go looking has
    # somewhere to look. Each is gated behind the mission that makes it
    # make sense, so nobody wanders into Chapter Four's material during
    # Chapter One.
    #
    # These carry the map's only `hunt` tiles. `hunt` has been implemented
    # in map_service since the map existed and was used by exactly zero
    # areas -- an optional fight that costs nothing to lose is the right
    # shape for side content, and it was sitting there unused.
    # ==================================================================
    "the_drifts": {
        "name": "The North — The Drifts",
        "region": "The North",
        "blurb": "West off the survey road. Nobody surveyed this part.",
        "grid": [
            "#########",
            "#.M.d.C.#",
            "#dd...dd#",
            "#.@.H..F#",
            "#dd...dd#",
            "#..S.W..#",
            "#########",
        ],
        "legend": {
            "d": {"kind": "decor", "emoji": "🌨", "name": "Drifted snow"},
            "S": {
                "kind": "exit",
                "emoji": "🛤",
                "name": "Back — the survey site",
                "to_area": "survey_site",
                "to": [3, 5],
            },
            "M": {
                "kind": "note",
                "emoji": "🪧",
                "name": "A marker post, leaning",
                "text": ("Survey marker, driven properly, guyed properly, and "
                         "eleven degrees off vertical.\n\n"
                         "The ground under it has moved. The post has not been "
                         "reset, which means whoever placed it never came back to "
                         "check it, which is not how any of these teams worked."),
            },
            "W": {
                "kind": "mission",
                "emoji": "🥾",
                "name": "Bootprints, going the wrong way",
                "mission": "s2_the_long_walk",
            },
            "H": {
                "kind": "hunt",
                "emoji": "❄",
                "name": "Something under the drift",
                "text": ("The drift moves. Not with the wind — against it, once, "
                         "and then it is still, and then it is not.\n\n"
                         "Optional. It is not on the way to anything, nobody "
                         "would ever know, and if it goes badly you simply walk "
                         "away — losing here costs you nothing at all."),
                # Solved, not authored: 49% health cost / 70% win against
                # the squad that can first open this door (level 22, via
                # c2m4). Chapter Two's hardest required fight costs 38%.
                "enemies": ["Permafrost Guardian", "Glacial Exterminator"],
                "level": 27,
                "grant": {"gold": 9000, "evolution_fragments": 400, "cores": 520,
                          "item": "mythic", "permafrost_ore": 60},
            },
            "C": {
                "kind": "cache",
                "emoji": "🎿",
                "name": "A sledge, abandoned",
                "text": ("Loaded, roped, and left. The rope has been cut, not "
                         "untied.\n\n"
                         "Whoever was pulling it decided very suddenly that they "
                         "would rather not be attached to it."),
                "grant": {"gold": 5200, "evolution_fragments": 240,
                          "lootbox": ("mythic", 2)},
            },
            "F": {
                "kind": "note",
                "emoji": "📻",
                "name": "A field radio, still warm",
                "text": ("Not warm from use. Warm from being kept somewhere warm "
                         "and then put down here recently.\n\n"
                         "It is tuned to the Cascade band. Somebody out here has "
                         "been listening to you the entire time, and has never "
                         "once keyed the mic."),
            },
        },
    },

    "lab_subbasement": {
        "name": "Ocellios Lab — Sub-Basement",
        "region": "Ocellios Lab",
        "blurb": "Under the floor you woke up on. It did not collapse with the rest.",
        "grid": [
            "##########",
            "#p..T.pR.#",
            "#..N...V.#",
            "#p.@.H..p#",
            "#..U...C.#",
            "#p..L.p..#",
            "##########",
        ],
        "legend": {
            "p": {"kind": "decor", "emoji": "🕳", "name": "Broken floor pan"},
            "R": {
                "kind": "puzzle",
                "puzzle_kind": "wiring",
                "emoji": "🔌",
                "name": "The patch panel",
                "text": ("Somebody has been keeping one fridge running in a "
                         "building with no mains power, and this is how: a patch "
                         "panel with eight terminals and four leads, four of the "
                         "leads pulled out and left hanging.\n\n"
                         "Whoever pulled them did it neatly, and labelled both "
                         "ends before they did.\n\n"
                         "Optional. Get it wrong and the board shorts, resets, "
                         "and sits there exactly as you found it."),
                "terminals": ["SUPPLY", "FRIDGE", "PUMP", "VENT",
                              "A-RAIL", "B-RAIL", "C-RAIL", "D-RAIL"],
                "clues": [
                    "SUPPLY goes to A-RAIL. That one is still connected; the others are not.",
                    "The fridge is on the B rail — it is written on the fridge.",
                    "The maintenance card says PUMP and VENT share the last two rails, pump first.",
                    "So: pump to C, vent to D.",
                ],
                "pairs": [["SUPPLY", "A-RAIL"], ["FRIDGE", "B-RAIL"],
                          ["PUMP", "C-RAIL"], ["VENT", "D-RAIL"]],
                "on_solve": ("Four leads seat with four small sounds, and the "
                             "board lights green all the way across.\n\n"
                             "The vent starts. Air moves down here for the first "
                             "time in a long while, and it carries the smell of a "
                             "place that has been sealed since before any of this "
                             "started."),
                "on_fail": "Something shorts. The board resets itself, patiently.",
                "grant": {"gold": 21000, "evolution_fragments": 880, "cores": 1200,
                          "item": "mythic", "echoes": 50},
            },
            "L": {
                "kind": "exit",
                "emoji": "🪜",
                "name": "Up — Level C",
                "to_area": "level_c",
                "to": [5, 5],
            },
            "T": {
                "kind": "note",
                "emoji": "🛏",
                "name": "Nine more of them",
                "text": ("Nine tables. Nine sets of restraints, all of them "
                         "undone from the inside at some point, all of them "
                         "re-fastened afterwards by somebody standing up.\n\n"
                         "One table is shorter than the others. It has been "
                         "shortened deliberately, at the foot, with a saw."),
            },
            "N": {
                "kind": "mission",
                "emoji": "📓",
                "name": "The intake ledger",
                "mission": "s3_the_fourth_name",
            },
            "U": {
                "kind": "note",
                "emoji": "🧬",
                "name": "A sample fridge, running",
                "text": ("On mains power, in a building with no mains power, "
                         "which means somebody has been feeding it from "
                         "somewhere.\n\n"
                         "Inside: forty vials, labelled by date. The most recent "
                         "is from last month."),
            },
            "H": {
                "kind": "hunt",
                "emoji": "🩸",
                "name": "It has been down here the whole time",
                "text": ("It does not come at you. It stands up, slowly, the way "
                         "somebody stands up who has been sitting for a very long "
                         "time, and it looks at you with an expression you "
                         "recognise and cannot place.\n\n"
                         "Optional. You do not have to do this, and losing costs "
                         "you nothing but the walk back down."),
                # Solved: 52% cost / 72% win against the level-32 squad
                # that can first open this door.
                #
                # Re-solved once. It was level 42 when Chapter Three was
                # reached at level 29; adding side missions raised the
                # story's own XP and fragment income, the squad arrived at
                # 32 with better gear, and the same level 42 fight fell to
                # 31% -- below the chapter around it again. Optional
                # content is not exempt from re-tuning when the economy
                # moves, and check_story is what noticed.
                "enemies": ["Ocellios Test Subject", "Illusion of Rex"],
                "level": 48,
                "grant": {"gold": 26000, "evolution_fragments": 950, "cores": 1300,
                          "item": "mythic", "echoes": 60},
            },
            "V": {
                "kind": "cache",
                "emoji": "🧳",
                "name": "A packed bag, never collected",
                "text": ("Somebody was leaving. Somebody packed carefully, "
                         "labelled everything, and set the bag by the stairs.\n\n"
                         "The label says a name and an address. The address is in "
                         "Kettleford."),
                "grant": {"gold": 14000, "evolution_fragments": 620,
                          "lootbox": ("mythic", 3)},
            },
            "C": {
                "kind": "cache",
                "emoji": "🔧",
                "name": "The maintenance stash",
                "text": ("Tools, spares, and a folding chair, all of it kept "
                         "properly. Somebody worked down here for years after "
                         "everybody else stopped."),
                "grant": {"gold": 11000, "evolution_fragments": 500, "metal": 90,
                          "crystal": 60},
            },
        },
    },

    "aligner_roof": {
        "name": "World Aligners — The Roof",
        "region": "World Aligners",
        "blurb": "Flat, gritty, and the only place in the building nobody argues.",
        "grid": [
            "#########",
            "#a.P..S.#",
            "#..D..G.#",
            "#a.@..H.#",
            "#..V..a.#",
            "#########",
        ],
        "legend": {
            "a": {"kind": "decor", "emoji": "📡", "name": "Aerial clutter"},
            "S": {
                "kind": "exit",
                "emoji": "🪜",
                "name": "Down — the floor",
                "to_area": "aligner_floor",
                "to": [6, 3],
            },
            "G": {
                "kind": "mission",
                "emoji": "🌇",
                "name": "Sit with him a while",
                "mission": "s1_higher_than_the_argument",
            },
            "D": {
                "kind": "npc",
                "emoji": "🐬",
                "name": "Dolphin, sitting on the parapet",
                "repeat": True,
                "lines": [
                    {"text": ("\"I come up here when I can't remember something "
                              "and I don't want anyone watching me try.\"")},
                    {"text": ("\"Dolpo says I was always like this. He says it "
                              "like it's a comfort. I don't think he knows it "
                              "isn't.\"")},
                    {"text": ("\"I know I'm not him. I do know that. I'd just "
                              "like to know what I *am*, and every time I get "
                              "close the thought slides off.\"")},
                    {"text": ("\"If it turns out Rohan did this to me — I don't "
                              "know what I'd want to happen. That's the part that "
                              "scares me. Not the not-knowing. The not-caring "
                              "what the answer costs.\"")},
                ],
            },
            "P": {
                "kind": "note",
                "emoji": "🪑",
                "name": "Two chairs",
                "text": ("Both facing out over the car park. Both with the grit "
                         "worn off the seat.\n\n"
                         "Somebody sits up here regularly with somebody else, and "
                         "neither of them has mentioned it downstairs."),
            },
            "V": {
                "kind": "cache",
                "emoji": "🧃",
                "name": "A cooler, restocked",
                "text": ("Somebody carries this up four flights and restocks it "
                         "for a person who has never asked them to."),
                "grant": {"gold": 4200, "evolution_fragments": 200, "cores": 260},
            },
            "H": {
                "kind": "hunt",
                "emoji": "🛰",
                "name": "The thing on the mast",
                "text": ("It has been sitting on the relay mast for a while, and "
                         "it has been listening. When it notices you noticing, it "
                         "stops pretending to be part of the mast.\n\n"
                         "Optional — Blueflame has walked past it every day for a "
                         "week. Losing costs nothing; it just goes back to "
                         "pretending."),
                # Solved: 41% cost / 82% win at level 14, against a
                # Chapter One whose hardest required fight costs 31%.
                # Was level 20, which measured 12% -- barely a fight.
                "enemies": ["Xender Spy Camera", "Corrupted Eris Sentry"],
                "level": 30,
                # EPIC, not legendary. This is gated behind c1m4 and
                # Chapter One's own missions top out at epic -- an
                # optional room handing out the next rarity band up is
                # how a player skips a tier of gear progression by
                # finding one room. Found by tools/check_reward_curve.
                "grant": {"gold": 4800, "evolution_fragments": 230, "cores": 300,
                          "item": "epic"},
            },
        },
    },

    "north_checkpoint": {
        "name": "The Forty Miles — Border Post",
        "region": "The North",
        "blurb": "Somebody has put a fence across a road that goes nowhere, and staffed it.",
        "grid": [
            "#########",
            "#f.B.P.f#",
            "#.......#",
            "#V..G..D#",
            "#.......#",
            "#f.S.@.f#",
            "#########",
        ],
        "legend": {
            "f": {"kind": "decor", "emoji": "🚧"},
            "S": {
                "kind": "exit",
                "emoji": "🧭",
                "name": "South — back to the workshop",
                "to_area": "rex_workshop",
                "to": [5, 4],
            },
            "G": {
                "kind": "mission",
                "emoji": "🪖",
                "name": "The gate, and the people on it",
                "mission": "c2m2_the_border",
            },
            "D": {
                "kind": "mission",
                "emoji": "🐬",
                "name": "The officer who won't come out of the hut",
                "mission": "c2m3_dolpo",
                "requires_mission": "c2m2_the_border",
                "locked_text": "Nobody's coming out while the gate's still an argument.",
            },
            "V": {
                "kind": "exit",
                "emoji": "🛤",
                "name": "Onward — the survey road",
                "to_area": "survey_site",
                "to": [4, 5],
                "requires_mission": "c2m3_dolpo",
                "locked_text": "The road past the post is closed, and currently that is not your call.",
            },
            "B": {
                "kind": "note",
                "emoji": "📋",
                "name": "The board on the gate",
                "text": ("An H-Nation notice, weather-bleached, in three languages.\n\n"
                         "**ROAD CLOSED. NOT A BORDER. DO NOT REPORT THIS POST.**\n\n"
                         "The last line has been added by hand, later, by somebody "
                         "with a different pen and a steadier grip."),
            },
            "P": {
                "kind": "note",
                "emoji": "⛽",
                "name": "The fuel log",
                "text": ("Kept in a plastic sleeve nailed to the hut wall, in the way "
                         "of people who intend to be somewhere a long time.\n\n"
                         "Fourteen months of entries. Every one of them is fuel going "
                         "**out** to a patrol, and back again with most of it "
                         "unburned.\n\n"
                         "Nobody stationed here has driven north. Not once, in "
                         "fourteen months."),
            },
        },
    },

    "survey_site": {
        "name": "The Forty Miles — Survey Point 9",
        "region": "The North",
        "blurb": "Nineteen teams came here. The equipment is all still running.",
        "grid": [
            "###########",
            "#..T.C.R..#",
            "#W......G.#",
            "#S...A...N#",
            "#.........#",
            "#..M.@.L..#",
            "###########",
        ],
        "legend": {
            "W": {
                "kind": "exit",
                "emoji": "🌨",
                "name": "West — off the road, into the drifts",
                "to_area": "the_drifts",
                "to": [3, 5],
                "requires_mission": "c2m4_survey_point_nine",
                "locked_text": ("There is nothing out that way and no reason to "
                                "go. Walk the site first."),
            },
            "G": {
                "kind": "puzzle",
                "puzzle_kind": "logic",
                "emoji": "🗂",
                "name": "The camp register",
                "text": ("A clipboard on a stake, with the camp assignments "
                         "half filled in and the rest rained off.\n\n"
                         "Four of the nineteen teams pitched in the inner ring. "
                         "The register says which ring, not which pitch, but the "
                         "duty log on the mess tent says enough to work it out.\n\n"
                         "Optional — it is a clipboard, and nothing is stopping "
                         "you walking past it."),
                "subjects": ["Team 4", "Team 9", "Team 11", "Team 19"],
                "values": ["North pitch", "East pitch", "South pitch", "West pitch"],
                "clues": [
                    "Team 19 pitched downwind of the bore head, which is the south pitch.",
                    "Team 4's mast is the one still transmitting, and it stands on the north pitch.",
                    "Team 11's supply pallet was found on the pitch next to Team 4's, on the east side.",
                    "That leaves one pitch, and one team.",
                ],
                "solution": {
                    "Team 4": "North pitch",
                    "Team 9": "West pitch",
                    "Team 11": "East pitch",
                    "Team 19": "South pitch",
                },
                "on_solve": ("Four names, four pitches, and the shape of it lands "
                             "all at once: they did not arrive together. They "
                             "arrived in order, each one pitching beside the last, "
                             "over eleven months.\n\n"
                             "Nobody was searching for anybody. Each team was sent "
                             "to the exact spot the last team stopped reporting "
                             "from."),
                "on_fail": "Two of those contradict the duty log. Try again.",
                "grant": {"gold": 8800, "evolution_fragments": 420, "cores": 560,
                          "item": "legendary"},
            },
            "S": {
                "kind": "exit",
                "emoji": "🛤",
                "name": "Back — the border post",
                "to_area": "north_checkpoint",
                "to": [1, 4],
            },
            "A": {
                "kind": "mission",
                "emoji": "📊",
                "name": "The middle of the site",
                "mission": "c2m4_survey_point_nine",
            },
            "N": {
                "kind": "mission",
                "emoji": "⛏",
                "name": "The bore head, and what's around it",
                "mission": "c2m5_nineteen",
                "requires_mission": "c2m4_survey_point_nine",
                "locked_text": "Walk the site first. Josh's rule, and it's a good one.",
            },
            "L": {
                "kind": "exit",
                "emoji": "🕳",
                "name": "Down — the cut",
                "to_area": "the_cut",
                "to": [3, 4],
                "requires_mission": "c2m5_nineteen",
                "locked_text": "There's a way down. You are not ready to take it.",
            },
            "T": {
                "kind": "note",
                "emoji": "⛺",
                "name": "The tents",
                "text": ("Nineteen camps, pitched in nineteen slightly different "
                         "styles, in a rough ring around the bore head.\n\n"
                         "Every one of them is still standing. Every one is empty, and "
                         "tidy, and zipped shut from the outside."),
            },
            "C": {
                "kind": "note",
                "emoji": "🍽",
                "name": "The mess tent",
                "text": ("Long tables, benches pushed in, and a serving pot that "
                         "somebody scoured out and turned upside down to dry.\n\n"
                         "Whatever happened here did not happen at a mealtime, and it "
                         "did not happen in a hurry."),
            },
            "R": {
                "kind": "note",
                "emoji": "📻",
                "name": "The comms mast",
                "text": ("Field mast, guyed properly, powered by a solar bank that "
                         "somebody has been keeping clear of snow.\n\n"
                         "It is transmitting. It has been transmitting for fourteen "
                         "months, on a loop, and the loop is a routine all-clear from "
                         "Survey Team 4.\n\n"
                         "Team 4 arrived eleven months ago."),
            },
            "M": {
                "kind": "cache",
                "emoji": "🧰",
                "name": "Team 11's supply pallet",
                "text": ("Broken open at some point and repacked by somebody who was "
                         "not the person who packed it originally.\n\n"
                         "Whoever repacked it took the food and left the tools."),
                "grant": {"gold": 2600, "item": "epic", "evolution_fragments": 120,
                          "lootbox": ("epic", 2)},
            },
        },
    },

    "the_cut": {
        "name": "The Forty Miles — The Cut",
        "region": "The North",
        "blurb": "A trench in the rock, machined, going down further than the light does.",
        "grid": [
            "#######",
            "#.E.W.#",
            "#..D..#",
            "#U.R.F#",
            "#..@..#",
            "#######",
        ],
        "legend": {
            "U": {
                "kind": "exit",
                "emoji": "🕳",
                "name": "Up — the survey site",
                "to_area": "survey_site",
                "to": [6, 5],
            },
            "R": {
                "kind": "mission",
                "emoji": "🕴",
                "name": "There is a man at the bottom of it",
                "mission": "c2m6_mr_r",
            },
            "E": {
                "kind": "note",
                "emoji": "🪨",
                "name": "The wall of the cut",
                "text": ("Rock, cut smooth, with the tool marks running in one "
                         "continuous direction from the top to as far down as you can "
                         "see.\n\n"
                         "One pass. Whatever made this did not stop, and did not need "
                         "to come back and tidy."),
            },
            "W": {
                "kind": "note",
                "emoji": "🧊",
                "name": "The nineteen crates",
                "text": ("Stacked against the cut wall, in numbered order, out of the "
                         "weather.\n\n"
                         "Each one holds one survey team's equipment: instruments, "
                         "logs, personal effects, all of it labelled and none of it "
                         "damaged.\n\n"
                         "Somebody collected these. Somebody carried them down here and "
                         "stacked them in the right order."),
            },
            "D": {
                # The lift. Locked until the summit, because Chapter
                # Three's first act is the argument about whether to come
                # back here at all -- and going down before having it
                # would make that argument decorative.
                "kind": "exit",
                "emoji": "🛗",
                "name": "The lift, and the letters above it",
                "to_area": "level_a",
                "to": [4, 5],
                "requires_mission": "c3m1_the_long_room",
                "locked_text": "The lift is down there and it is not going anywhere. Neither, yet, are you.",
            },
            "F": {
                "kind": "note",
                "emoji": "🗒",
                "name": "The clipboard on the last crate",
                "text": ("A tally, in a hand you have now seen on a driller, on a "
                         "Warden's housing plate, and on nothing else.\n\n"
                         "Nineteen entries. Each is a team number, a date, and one "
                         "word.\n\n"
                         "Eighteen of them say **RETURNED**.\n\n"
                         "The nineteenth says **KEPT**, and it is dated the 14th."),
            },
        },
    },

    # ==================================================================
    # CHAPTER THREE — BELOW THE CUT
    #
    # Two areas, and the design brief for both is: THIS IS A WORKPLACE.
    #
    # Every instinct says to make the villain's base sinister. The whole
    # horror of Rohan is that he is not running a lair, he is running an
    # operation -- swept floors, labelled shelving, a rota on the wall,
    # a kettle. The unsettling thing about Level A is that a reasonable
    # person could work there and many have.
    #
    # So the notes are deliberately mundane and the mundanity is the
    # payload. Nothing down here is written to be creepy; it is written
    # to be ORGANISED, and the player supplies the rest.
    # ==================================================================
    "level_a": {
        "name": "Below The Cut — Level A",
        "region": "The North",
        "blurb": "Swept concrete, good lighting, and a rota on the wall with names on it.",
        "grid": [
            "###########",
            "#p.R.S.C.p#",
            "#.........#",
            "#U...M...V#",
            "#.........#",
            "#p..B.@..p#",
            "###########",
        ],
        "legend": {
            "p": {"kind": "decor", "emoji": "🗄"},
            "U": {
                "kind": "exit",
                "emoji": "🛗",
                "name": "Up — the cut",
                "to_area": "the_cut",
                "to": [3, 3],
            },
            "M": {
                "kind": "mission",
                "emoji": "🚪",
                "name": "The doors at the end",
                "mission": "c3m2_level_a",
            },
            "V": {
                "kind": "mission",
                "emoji": "🎙",
                "name": "The room the loop comes from",
                "mission": "c3m3_the_voice",
                "requires_mission": "c3m2_level_a",
                "locked_text": "You can hear it from here. You are not ready to walk into it.",
            },
            "B": {
                "kind": "exit",
                "emoji": "🛗",
                "name": "Down — Level R",
                "to_area": "the_works",
                "to": [5, 5],
                "requires_mission": "c3m3_the_voice",
                "locked_text": "The lift will go down. It will not go down yet.",
            },
            "R": {
                "kind": "note",
                "emoji": "📋",
                "name": "The rota",
                "text": ("A duty rota, printed and laminated, covering a fortnight.\n\n"
                         "Six names. Shifts, breaks, a note about who is covering the "
                         "kettle run.\n\n"
                         "Four of the six names are on crates upstairs."),
            },
            "S": {
                "kind": "note",
                "emoji": "🧰",
                "name": "The shelving",
                "text": ("Industrial racking, floor to ceiling, every shelf labelled in "
                         "the same neat hand.\n\n"
                         "*SPARES — TRACK*. *SPARES — OPTICAL*. *RETURNS, PROCESSED*. "
                         "*RETURNS, PENDING*.\n\n"
                         "The pending shelf has three boxes on it. They are not "
                         "equipment boxes. They are the size of a person's effects."),
            },
            "C": {
                "kind": "cache",
                "emoji": "📦",
                "name": "Spares — optical",
                "text": ("A shelf of parts, catalogued, most of which came off "
                         "machines you have fought.\n\n"
                         "Whoever keeps this store is better at it than anyone at "
                         "Cascade, which Refender says out loud and then looks unhappy "
                         "about having said."),
                "grant": {"gold": 5000, "item": "mythic", "evolution_fragments": 200,
                          "cores": 300, "lootbox": ("legendary", 2)},
            },
        },
    },

    "the_works": {
        "name": "Below The Cut — Level R",
        "region": "The North",
        "blurb": "The bottom of the letters. Whatever he is doing, this is where it is done.",
        "grid": [
            "###########",
            "#..W.G.T..#",
            "#..Q.C....#",
            "#L...F...N#",
            "#.........#",
            "#..K.@.I..#",
            "###########",
        ],
        "legend": {
            "L": {
                "kind": "exit",
                "emoji": "🛗",
                "name": "Up — Level A",
                "to_area": "level_a",
                "to": [4, 5],
            },
            "F": {
                "kind": "mission",
                "emoji": "⚙",
                "name": "The floor, and what is on it",
                "mission": "c3m4_what_he_was_building",
            },
            "N": {
                "kind": "mission",
                "emoji": "📓",
                "name": "The desk with the ledger on it",
                "mission": "c3m5_inventory",
                "requires_mission": "c3m4_what_he_was_building",
                "locked_text": "One thing at a time. Josh's rule, still holding.",
            },
            "I": {
                "kind": "mission",
                "emoji": "🕴",
                "name": "He is waiting by the last door",
                "mission": "c3m6_the_bottom",
                "requires_mission": "c3m5_inventory",
                "locked_text": "He is not going anywhere. That is rather the difficulty.",
            },
            "Q": {
                "kind": "puzzle",
                "puzzle_kind": "sequence",
                "emoji": "🎛",
                "name": "The start-up panel",
                "text": ("Six breakers in a row, all off, and a laminated card "
                         "screwed to the panel above them.\n\n"
                         "The card is a start-up order. Somebody has been "
                         "following it for years, because the laminate is worn "
                         "through in six places and the wear is not even — the "
                         "same fingers, the same order, every time.\n\n"
                         "Optional. Throw them out of order and the interlock "
                         "trips and resets itself, and you can simply walk away."),
                "clues": [
                    "The card reads, in order: GROUND. FEED. PUMPS. LIGHTS. AIR. DOORS.",
                    ("Underneath, in pen: \"NOT the order on the breakers. The "
                     "breakers were relabelled in '19 and nobody redid the card.\"",),
                ],
                "steps": [
                    {"id": "ground", "label": "Ground"},
                    {"id": "feed", "label": "Feed"},
                    {"id": "pumps", "label": "Pumps"},
                    {"id": "lights", "label": "Lights"},
                    {"id": "air", "label": "Air"},
                    {"id": "doors", "label": "Doors"},
                ],
                "order": ["ground", "feed", "pumps", "lights", "air", "doors"],
                "on_solve": ("The interlock holds. Somewhere below you a pump "
                             "picks up, coughs, and settles into a rhythm it "
                             "clearly remembers.\n\n"
                             "Lights come on down the whole length of Level R, "
                             "one bank at a time, all the way to a far wall "
                             "nobody has been able to see until now."),
                "on_fail": ("The interlock trips on the third breaker and puts "
                            "everything back to off."),
                "grant": {"gold": 16000, "evolution_fragments": 700, "cores": 900,
                          "item": "mythic", "lootbox": ("mythic", 2)},
            },
            "W": {
                "kind": "note",
                "emoji": "🛠",
                "name": "The line",
                "text": ("An assembly line, running, unattended.\n\n"
                         "At the near end: raw plate. At the far end, finished and "
                         "racked in threes, Wardens.\n\n"
                         "There is a counter above it. It reads a number in the low "
                         "hundreds and it is not going down."),
            },
            "G": {
                "kind": "note",
                "emoji": "🗂",
                "name": "The wall of files",
                "text": ("Filing, floor to ceiling, alphabetical.\n\n"
                         "Not machines. **People.** One folder per person, and the "
                         "tabs run from before the survey teams to well after them.\n\n"
                         "Refender finds Cascade's convoy from the spring in under a "
                         "minute, because it is exactly where it should be."),
            },
            "T": {
                "kind": "note",
                "emoji": "☕",
                "name": "The kettle",
                "text": ("A kettle, two mugs on a tray, and a tin of the cheap tea "
                         "everybody in the world buys.\n\n"
                         "One of the mugs has been used recently. The other has been "
                         "put out ready, which is somehow the worst detail on this "
                         "entire level."),
            },
            "C": {
                # CHAPTER FOUR goes back DOWN, but only after a chapter
                # spent on the surface. Locked until the audit has been
                # fought on the ground, because the point of Chapter Four
                # is that Rohan stopped waiting for people to come to him.
                "kind": "exit",
                "emoji": "🛗",
                "name": "Down — Level C",
                "to_area": "level_c",
                "to": [5, 5],
                "requires_mission": "c4m4_the_other_end",
                "locked_text": "The shaft goes down. You have nothing to look for down it yet.",
            },
            "K": {
                "kind": "cache",
                "emoji": "🧊",
                "name": "The returns bench",
                "text": ("Personal effects, sorted, bagged and labelled, waiting to go "
                         "back up.\n\n"
                         "Jofrog checks every bag against the crate numbers he memorised "
                         "upstairs, and does not find the one he is looking for, and "
                         "does not say who it was for."),
                "grant": {"gold": 6000, "item": "mythic", "evolution_fragments": 240,
                          "shards": 400, "lootbox": ("legendary", 3)},
            },
        },
    },

    # ==================================================================
    # CHAPTER FOUR — THE AUDIT
    #
    # Two areas, and the pairing is the chapter's argument.
    #
    # depot_yard is the SURFACE: the freight depot from Chapter One,
    # sandbagged, with three factions' vehicles in the car park and
    # somebody's washing still on the line. Everything Chapter One
    # established as small and shabby is now the thing being defended,
    # which is the only way to make a base feel worth anything.
    #
    # level_c is what the surface is being defended FROM, and it is the
    # first room in the story that is not tidy -- because it is the first
    # one Rohan has not finished.
    # ==================================================================
    "depot_yard": {
        "name": "Sixteen Freight — The Yard",
        "region": "World Aligners",
        "blurb": "Sandbags, three factions' vehicles, and somebody's washing still on the line.",
        "grid": [
            "###########",
            "#g.A.W.H.g#",
            "#..N.V.P..#",
            "#F...S...J#",
            "#....O....#",
            "#g..R.@..g#",
            "###########",
        ],
        "legend": {
            "g": {"kind": "decor", "emoji": "🛢"},
            "R": {
                "kind": "exit",
                "emoji": "🚧",
                "name": "Inside — the Floor",
                "to_area": "aligner_floor",
                "to": [6, 6],
            },
            "S": {
                "kind": "mission",
                "emoji": "📡",
                "name": "Every radio in the building at once",
                "mission": "c4m1_the_audit_begins",
            },
            "J": {
                "kind": "mission",
                "emoji": "🧱",
                "name": "The line at the fence",
                "mission": "c4m2_the_yard",
                "requires_mission": "c4m1_the_audit_begins",
                "locked_text": "Nothing at the fence. Long may it last.",
            },
            "H": {
                "kind": "mission",
                "emoji": "🔧",
                "name": "Rex, with his hands in something",
                "mission": "c4m3_what_his_hands_remember",
                "requires_mission": "c4m2_the_yard",
                "locked_text": "He's asleep. Let him.",
            },
            "N": {
                "kind": "mission",
                "emoji": "📡",
                "name": "The signal that came back changed",
                "mission": "c5m1_revised",
                "requires_mission": "c4m6_audit_paused",
                "locked_text": "Eleven quiet days. Enjoy them.",
            },
            "V": {
                "kind": "mission",
                "emoji": "🏚",
                "name": "Kettleford, on the radio",
                "mission": "c5m2_kettleford",
                "requires_mission": "c5m1_revised",
                "locked_text": "Kettleford is fine. Kettleford was fine an hour ago.",
            },
            "P": {
                "kind": "mission",
                "emoji": "📐",
                "name": "Refender and Rex, arguing about a form",
                "mission": "c5m3_the_shape_of_the_form",
                "requires_mission": "c5m2_kettleford",
                "locked_text": "They haven't got anything to argue about yet.",
            },
            "O": {
                "kind": "mission",
                "emoji": "📻",
                "name": "Rex, with the new receiver",
                "mission": "c4m4_the_other_end",
                "requires_mission": "c4m3_what_his_hands_remember",
                "locked_text": "There's nothing to listen with yet.",
            },
            "A": {
                "kind": "note",
                "emoji": "🚗",
                "name": "The car park",
                "text": ("Three Cascade vans, an H-Nation flatbed with the plates taken "
                         "off, and the depot's own van with the wordmark still badly "
                         "sanded.\n\n"
                         "Somebody has chalked a rota on the flatbed's side panel. It "
                         "is in three handwritings and two languages and it is, as far "
                         "as anybody can tell, being followed."),
            },
            "W": {
                "kind": "note",
                "emoji": "🧺",
                "name": "The washing line",
                "text": ("Strung between the shutter and a sandbag emplacement, and "
                         "carrying four shirts, two towels and a coat that is very "
                         "nearly Dolphe's coat.\n\n"
                         "Nobody has taken it in. It has been there through two alerts. "
                         "At this point taking it in would mean something."),
            },
            "F": {
                "kind": "cache",
                "emoji": "📦",
                "name": "Cascade's third van, still half-loaded",
                "text": ("Supplies nobody has had time to unpack, with a manifest taped "
                         "to the inside of the door in Refender's handwriting.\n\n"
                         "Somebody has ticked off about a third of it and then written, "
                         "at the bottom: *stopped ticking, sorry, we needed it.*"),
                "grant": {"gold": 8000, "item": "mythic", "evolution_fragments": 300,
                          "shards": 500, "lootbox": ("legendary", 3)},
            },
        },
    },

    "level_c": {
        "name": "Below The Cut — Level C",
        "region": "The North",
        "blurb": "The first room down here that isn't finished, because he ran out of time.",
        "grid": [
            "###########",
            "#..M.B.P..#",
            "#....J....#",
            "#U...D...T#",
            "#S........#",
            "#..E.@.O..#",
            "###########",
        ],
        "legend": {
            "U": {
                "kind": "exit",
                "emoji": "🛗",
                "name": "Up — Level R",
                "to_area": "the_works",
                "to": [5, 2],
            },
            "S": {
                "kind": "exit",
                "emoji": "🪜",
                "name": "Down — a stairwell that isn't on the plan",
                "to_area": "lab_subbasement",
                "to": [4, 5],
                "requires_mission": "c3m5_inventory",
                "locked_text": ("A door behind the racking, with a handle worn "
                                "bright. You do not yet know enough to want to "
                                "know what is behind it."),
            },
            "D": {
                "kind": "mission",
                "emoji": "🗺",
                "name": "The wall he was working on",
                "mission": "c4m5_the_open_entry",
            },
            "T": {
                "kind": "mission",
                "emoji": "🕴",
                "name": "The last door on Level C",
                "mission": "c4m6_audit_paused",
                "requires_mission": "c4m5_the_open_entry",
                "locked_text": "One thing at a time. Still Josh's rule.",
            },
            "M": {
                "kind": "note",
                "emoji": "🗺",
                "name": "The regional map",
                "text": ("Wall-sized, hand-drawn, and more accurate than anything "
                         "Cascade owns.\n\n"
                         "Every settlement in the region is on it. Most have a number "
                         "beside them and a word: *counted*.\n\n"
                         "Four do not. One of the four is a freight depot on the wrong "
                         "side of a ring road, and beside it, in the same hand: "
                         "*anomalous. recount.*"),
            },
            "B": {
                "kind": "note",
                "emoji": "🧾",
                "name": "The unfinished column",
                "text": ("A tally sheet, half filled in, abandoned mid-line — the first "
                         "unfinished thing anybody has seen down here.\n\n"
                         "The pen is on the floor beside it, where it was dropped rather "
                         "than put down.\n\n"
                         "Whatever interrupted him, he did not have time to square it to "
                         "the edge."),
            },
            "P": {
                "kind": "note",
                "emoji": "📁",
                "name": "The folder left open",
                "text": ("One folder, open, face-up on a stool, and it is thin.\n\n"
                         "Four photographs of a man in a coat that is very nearly "
                         "somebody else's. A column of dates running to last month.\n\n"
                         "And, at the bottom, three lines added at three different "
                         "times, in the same hand, getting shorter:\n\n"
                         "*inventory does not resolve.*\n"
                         "*second attempt: does not resolve.*\n"
                         "*why.*"),
            },
            "E": {
                "kind": "cache",
                "emoji": "🧰",
                "name": "The bench he was working at",
                "text": ("Tools in the order you would use them, not the order you "
                         "would store them.\n\n"
                         "Rex looks at this bench for a long time when he comes down, "
                         "and does not say anything about it, and nobody asks."),
                "grant": {"gold": 10000, "item": "mythic", "evolution_fragments": 360,
                          "cores": 600, "lootbox": ("mythic", 2)},
            },
            "J": {
                "kind": "mission",
                "emoji": "📻",
                "name": "The signal room, and what Rex has done to it",
                "mission": "c5m4_unresolvable",
                "requires_mission": "c5m3_the_shape_of_the_form",
                "locked_text": "Nothing to broadcast yet.",
            },
            "O": {
                "kind": "exit",
                "emoji": "🛗",
                "name": "Down — the last shaft",
                "to_area": "the_last_letter",
                "to": [4, 4],
                "requires_mission": "c5m4_unresolvable",
                "locked_text": ("Another lift, and another counter. It starts at C and "
                                "runs down through nine more, and the bottom letter is "
                                "not one anybody here recognises.\n\n"
                                "You have nothing to take down it yet."),
            },
        },
    },

    # ==================================================================
    # THE LAST LETTER — the bottom of the shaft.
    #
    # Deliberately the SMALLEST area in the game. Four chapters spent
    # descending through rooms that got larger and better organised, and
    # the bottom is a box with a desk in it.
    #
    # Nothing here is grand, and that is the point: the answer to what
    # Rohan is turns out to be small, administrative and rather sad. A
    # cathedral would have promised something this story does not intend
    # to deliver.
    # ==================================================================
    "the_last_letter": {
        "name": "Below The Cut — The Last Letter",
        "region": "The North",
        "blurb": "A small room at the bottom of eleven, with a desk in it and nothing else running.",
        "grid": [
            "#########",
            "#.D.T.R.#",
            "#.......#",
            "#U..M..F#",
            "#...@...#",
            "#########",
        ],
        "legend": {
            "U": {
                "kind": "exit",
                "emoji": "🛗",
                "name": "Up — Level C",
                "to_area": "level_c",
                "to": [7, 5],
            },
            "M": {
                "kind": "mission",
                "emoji": "🕯",
                "name": "The desk at the bottom",
                "mission": "c5m5_the_last_letter",
            },
            "F": {
                "kind": "mission",
                "emoji": "🕴",
                "name": "He has stopped writing",
                "mission": "c5m6_nothing_to_file",
                "requires_mission": "c5m5_the_last_letter",
                "locked_text": "He is still writing. Let him finish the line.",
            },
            "D": {
                "kind": "note",
                "emoji": "📮",
                "name": "The outgoing tray",
                "text": ("A tray, and it is full.\n\n"
                         "Reports, in order, sealed and addressed and stacked. The "
                         "oldest at the bottom is dated four years ago. The newest is "
                         "from this morning.\n\n"
                         "None of them have been sent. There is nothing down here to "
                         "send them with."),
            },
            "T": {
                "kind": "note",
                "emoji": "📥",
                "name": "The incoming tray",
                "text": ("The same tray, on the other side of the desk.\n\n"
                         "It is empty, and it has been dusted."),
            },
            "R": {
                "kind": "note",
                "emoji": "🗓",
                "name": "The last thing that arrived",
                "text": ("One sheet, kept flat under glass — the only object down here "
                         "anybody has bothered to protect.\n\n"
                         "It is an instruction. It is four years old. It is in a hand "
                         "that is not his:\n\n"
                         "*Establish what is there. Report. Await further.*\n\n"
                         "There is no further. There has never been any further."),
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
