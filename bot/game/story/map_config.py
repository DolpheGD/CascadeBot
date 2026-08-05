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
    # ==============================================================
    # OCELLIOS LAB -- the canon opening.
    #
    # The Player wakes here mid-collapse with Stubby's mechs hacked hostile.
    # This replaced a newsroom-recruitment prologue written before the lore
    # documents were read: the timeline is explicit that Dolphe News rebranded
    # to Team Cascade in 107 IC, two years BEFORE this, so there was no
    # newspaper left to be recruited into.
    #
    # The notes carry the amnesia plot, because the Player is silent by design
    # and cannot ask about it.
    # ==============================================================
    "ocellios_ruin": {
        "name": "Ocellios Lab — Sector 9",
        "blurb": "Coming apart. You do not remember arriving.",
        "grid": [
            "#############",
            "#T.s.c#R.m.o#",
            "#..w..#..b..#",
            "#..v.y...L.g#",
            "#####.#.....#",
            "#@.f.d#.k.rE#",
            "#############",
        ],
        "legend": {
            "T": {
                "kind": "mission",
                "emoji": "🧪",
                "name": "Sector 9 floor",
                "mission": "pr1_destruction_eruption",
            },
            "L": {
                "kind": "mission",
                "emoji": "🗄",
                "name": "Staging locker",
                "mission": "pr2_field_salvage",
                "requires_mission": "pr1_destruction_eruption",
                "locked_text": "Sealed on an electronic lock, and the corridor to it is full of a mech that has not decided you are a person.\n\nDeal with that first.",
            },
            "E": {
                "kind": "exit",
                "emoji": "🚪",
                "name": "East fire door",
                "to_area": "glacier_crossing",
                "to": [1, 5],
                "requires_mission": "pr2_field_salvage",
                "locked_text": "Weather on the other side, and nothing on this side but a burning lab.\n\nDon't walk into that in what you woke up wearing. There's a staging locker on this floor.",
            },
            "R": {
                "kind": "note",
                "emoji": "🛏",
                "name": "The restraint frame",
                "text": "Padded, adjustable, and open. The cuffs were released from the *inside* of the console, not by force.\n\nA chart on the rail logs a weight in kilos, twice daily, for eleven months. The handwriting changes three times. The weight barely does.",
            },
            "s": {
                "kind": "note",
                "emoji": "🩸",
                "name": "Spill station",
                "text": "An emergency spill kit, used recently, wrappers still on the floor.\n\nWhatever they cleaned up here, they cleaned it in a hurry and then left the building.",
            },
            "c": {
                "kind": "note",
                "emoji": "📋",
                "name": "Clipboard",
                "text": "**SUBJECT VIABILITY — WK 44**, and a column of readings that mean nothing to you.\n\nAt the bottom, in different pen: *ask Stubby re: transfer. Not my call anymore.*",
            },
            "w": {
                "kind": "note",
                "emoji": "🪟",
                "name": "Observation glass",
                "text": "A window between this room and the next, mirrored on the far side.\n\nYou can see yourself in it. Grey, small, and not entirely steady at the edges — like a signal that isn't quite tuned.",
            },
            "v": {
                "kind": "note",
                "emoji": "🔌",
                "name": "Blown junction",
                "text": "A power junction comprehensively destroyed from *this* side of the wall.\n\nThe scorch pattern is a starburst, centred about a metre off the floor. About where your hands would be.",
            },
            "y": {
                "kind": "note",
                "emoji": "🚨",
                "name": "Alarm panel",
                "text": "**CONTAINMENT FAULT — SECTOR 9.** It has been repeating since before you woke up.\n\nSector 9 is this room. The containment is you.",
            },
            "f": {
                "kind": "note",
                "emoji": "🧯",
                "name": "Fire door log",
                "text": "A maintenance tag signed every quarter for nine years.\n\nThe last four signatures are all the same and none are legible. Somebody stopped caring who was checking.",
            },
            "d": {
                "kind": "note",
                "emoji": "💻",
                "name": "Dead terminal",
                "text": "Fried with everything else on this circuit. One line is still burnt into the phosphor:\n\n**HHYPER — PHASE 1 — GO.**",
            },
            "m": {
                "kind": "note",
                "emoji": "🤖",
                "name": "Mech cradles",
                "text": "Six D-class cradles. Five empty, the sixth holding a unit with its control cover prised off.\n\nSomebody reached in and changed what these things want. It wasn't the lab.",
            },
            "b": {
                "kind": "note",
                "emoji": "📦",
                "name": "Shipping pallet",
                "text": "Crates stencilled for a freight route running north off the edge of the site map.\n\nEvery crate is within four kilos of every other crate.",
            },
            "o": {
                "kind": "note",
                "emoji": "🕳",
                "name": "Floor breach",
                "text": "The floor has opened onto the level below, which is on fire, which is somehow reassuring — it means there is a below.\n\nYou are, at least, still in a building.",
            },
            "k": {
                "kind": "note",
                "emoji": "🧥",
                "name": "Coat hook",
                "text": "One coat, three sizes too big, on a hook by the fire door.\n\nYou take it. Nobody at Cascade ever asks where you got it, which tells you something about how you looked when you arrived.",
            },
            "g": {
                "kind": "note",
                "emoji": "🧊",
                "name": "Cold draught",
                "text": "Air coming *in* under the east door, colder than anything you have a word for yet.\n\nOut there is a city called Glacier 15. You will learn its name from a man who used to live in it.",
            },
            "r": {
                "kind": "note",
                "emoji": "🔥",
                "name": "Sector 8",
                "text": "Through the glass, the next sector is already gone.\n\nWhatever went wrong started east of you and worked inward. You were the last room it reached, and it reached you last because somebody built this room to hold.",
            },
        },
    },

    # ==============================================================
    # THE CROSSING -- canon: the Player survives Glacier 15 by powering heat
    # beacons, is intercepted by Nebula and Gostley, and narrowly escapes a
    # mechanical worm.
    #
    # The drift-line fight keeps the `requires_characters: 2` guard the old
    # prologue used on its final fight, because it is still the first fight
    # that cannot be won solo. Here the guard is diegetic: Nebula says it out
    # loud, so the lock reads as a person refusing rather than a system.
    # ==============================================================
    "glacier_crossing": {
        "name": "Glacier 15 — The Crossing",
        "blurb": "White, then white, then white. A line of dead lamps going east.",
        "grid": [
            "#############",
            "#B.t.p#N.i.h#",
            "#..l..#..e..#",
            "#..u.z...W.a#",
            "#####.#.....#",
            "#@.c.k#.q.jE#",
            "#############",
        ],
        "legend": {
            "B": {
                "kind": "mission",
                "emoji": "🔥",
                "name": "First heat beacon",
                "mission": "pr3_heat_beacons",
            },
            "N": {
                "kind": "mission",
                "emoji": "🔦",
                "name": "The ridge",
                "mission": "pr4_the_anomaly",
                "requires_mission": "pr3_heat_beacons",
                "locked_text": "A light up on the ridge, tracking you.\n\nYou are not going to make it that far at this body temperature. Get the beacon line running first.",
            },
            "W": {
                "kind": "mission",
                "emoji": "🥊",
                "name": "The drift line",
                "mission": "pr5_through_the_drift",
                "requires_mission": "pr4_the_anomaly",
                "requires_characters": 2,
                "locked_text": "Thin ice over something with a shape to it.\n\n“Not as three,” Nebula says flatly. “Use the tag. Call somebody, put them in your squad, and then we walk it.”",
            },
            "E": {
                "kind": "exit",
                "emoji": "🚪",
                "name": "The base beacon",
                "to_area": "cascade_forward_base",
                "to": [1, 5],
                "requires_mission": "pr5_through_the_drift",
                "locked_text": "The big light, east, past the drift line.\n\nGostley has his hand flat on the ice and is not moving. “Not yet.”",
            },
            "t": {
                "kind": "note",
                "emoji": "🌡",
                "name": "Temperature stake",
                "text": "A survey stake with a dial on it, reading a number you decide not to look at twice.\n\nBelow the dial, scratched into the paint with a thumbnail: *keep moving keep moving keep moving.*",
            },
            "p": {
                "kind": "note",
                "emoji": "🚏",
                "name": "Beacon post 2",
                "text": "Dead lamp, live socket. It warms under your hand before you've decided to touch it.\n\nYou are beginning to suspect that whatever was done to you was done *for* something, and that you are currently doing it.",
            },
            "l": {
                "kind": "note",
                "emoji": "🏚",
                "name": "A roofline",
                "text": "Something rectangular under the drift, forty metres off the path. A roof.\n\nYou are not crossing a wilderness. You are walking along the top of somebody's street.",
            },
            "u": {
                "kind": "note",
                "emoji": "🚗",
                "name": "Buried vehicle",
                "text": "A family hauler, iced solid. Doors shut, seats empty, boot open and packed.\n\nThey packed. They got as far as loading it. Then they didn't drive.",
            },
            "z": {
                "kind": "note",
                "emoji": "📻",
                "name": "Dead relay",
                "text": "A public emergency relay, casing intact, battery flat for two years.\n\nYou put a hand on it out of a habit you didn't know you had. It coughs, plays four seconds of a children's weather jingle, and dies again.",
            },
            "c": {
                "kind": "note",
                "emoji": "🐾",
                "name": "Your own tracks",
                "text": "You've walked in a circle. Not a large one.\n\nThe beacons are not decoration. Without the line you would already be part of the landscape.",
            },
            "k": {
                "kind": "note",
                "emoji": "🧭",
                "name": "Snapped compass",
                "text": "Somebody's compass, dropped, needle spinning steadily and never settling.\n\nThere is too much void matter in this ice for magnets to mean anything. That is why they built a road out of lamps.",
            },
            "i": {
                "kind": "note",
                "emoji": "🧊",
                "name": "Ice core",
                "text": "A drill core left standing in its own hole, banded like tree rings.\n\nTwo years of clean ice. Then a black seam. Then, underneath, nine decades of nothing unusual at all.",
            },
            "e": {
                "kind": "note",
                "emoji": "🛰",
                "name": "Cascade's radar",
                "text": "A tripod dish pointed at the sky, freshly serviced, running off a battery somebody carried here on their back.\n\nThis is what saw you. Somewhere east an anomaly appeared on a screen, and Dolphe sent two people to find out what it was.",
            },
            "h": {
                "kind": "note",
                "emoji": "🪦",
                "name": "Marker cairn",
                "text": "Stones stacked waist-high, a name plate wired to the top, no grave underneath.\n\nThere are more of these than there are loose stones to build them from. Somebody has been rationing the memorials.",
            },
            "a": {
                "kind": "note",
                "emoji": "🕳",
                "name": "Entry hole",
                "text": "A shaft punched clean through the ice from below, wide enough to drive into.\n\nThe edges are machined. Whatever came up here was built, and it did not come up hungry. It came up *looking*.",
            },
            "q": {
                "kind": "note",
                "emoji": "🍫",
                "name": "Ration wrapper",
                "text": "Eight months past date and the best thing that has ever happened to you.\n\nYou will remember this wrapper for a long time, which is a strange thing to know about yourself while it is happening.",
            },
            "j": {
                "kind": "note",
                "emoji": "💡",
                "name": "Beacon post 9",
                "text": "The last post before the base light. This one is already lit.\n\nSomebody comes out this far to keep one lamp burning at the edge of a dead city, every night, for two years, in case.",
            },
        },
    },

    # ==============================================================
    # THE FORWARD BASE -- where the Player joins Team Cascade, and where the
    # prologue plants R.
    #
    # Dolphe is HE. File C-000 is unambiguous, and an earlier draft of this
    # prologue had it wrong in every single scene -- the kind of error that
    # gets copied forward into every chapter if it isn't fixed at the root.
    # ==============================================================
    "cascade_forward_base": {
        "name": "Cascade — Forward Base",
        "blurb": "One heated shell, one relay, and a great deal of extension cable.",
        "grid": [
            "#############",
            "#V.b...M.d.n#",
            "#.....#.....#",
            "#.c.z.#.m.u.#",
            "###.###.###.#",
            "#@.e...T..jE#",
            "#############",
        ],
        "legend": {
            "V": {
                "kind": "mission",
                "emoji": "🛠",
                "name": "Virtual's bench",
                "mission": "pr6_forward_base",
            },
            "M": {
                "kind": "mission",
                "emoji": "🗺",
                "name": "The map table",
                "mission": "pr7_the_map_table",
                "requires_mission": "pr6_forward_base",
                "locked_text": "Dolphe has three separate reports about you and is reading all of them at once.\n\n“Let Virtual finish. She's been holding a speech about that relay for a week and I would like somebody else to receive it.”",
            },
            "T": {
                "kind": "mission",
                "emoji": "🕯",
                "name": "The long table",
                "mission": "pr8_someone_got_here_first",
                "requires_mission": "pr7_the_map_table",
                "locked_text": "Chairs pulled round, nobody in them yet.\n\nGostley is still out at the drift hole, and whatever he has found, he is taking his time coming back with it.",
            },
            "E": {
                "kind": "exit",
                "emoji": "🪜",
                "name": "Up, and out",
                "to_area": "cryosphere_divide",
                "to": [1, 5],
                "requires_mission": "pr8_someone_got_here_first",
                "locked_text": "The stair up to the shelf road.\n\nDawn, Dolphe said. There's a man walking in and you're meeting him rested.",
            },
            "b": {
                "kind": "note",
                "emoji": "🔋",
                "name": "The battery bank",
                "text": "Car batteries wired into something they were never designed to power, taped over with **DO NOT BELIEVE THE GAUGE**.\n\nThe gauge reads full. It has read full for nine months.",
            },
            "d": {
                "kind": "note",
                "emoji": "🥫",
                "name": "Ration shelf",
                "text": "Tins sorted by expiry, then re-sorted by somebody with a different opinion about expiry.\n\nA note on the shelf: **THE WATER IS FINE. I TEST IT DAILY. STOP ASKING. — D.** Somebody has replied: *nobody asked.*",
            },
            "n": {
                "kind": "note",
                "emoji": "📻",
                "name": "The listening post",
                "text": "A receiver tuned to a Xender logistics band, scrolling freight manifests nobody is supposed to be reading.\n\nMost of it is concrete and fuel. Every eleventh entry is a crate routed north with no contents listed at all.",
            },
            "c": {
                "kind": "note",
                "emoji": "🛏",
                "name": "Camp beds",
                "text": "Four beds. Three made with a neatness that suggests military habit; the fourth is a nest of blankets and charging cables.\n\nYou can tell whose is whose, and you have been here under an hour.",
            },
            "z": {
                "kind": "note",
                "emoji": "🧰",
                "name": "Parts crate",
                "text": "Salvage sorted into bins by a system that is either brilliant or nonexistent.\n\nOne bin says **GOOD**. One says **BAD**. One says **ASK ME FIRST** and is padlocked.",
            },
            "m": {
                "kind": "note",
                "emoji": "🖼",
                "name": "The wall",
                "text": "Photographs pinned edge to edge. Team Cascade before any of this — a hangar, an airship, far too many people grinning at the camera.\n\nSomebody has gone along the row and turned eleven of them face-in. Nobody has turned them back.",
            },
            "u": {
                "kind": "note",
                "emoji": "📋",
                "name": "The rota",
                "text": "Watches, six hours each, in Nebula's handwriting.\n\nGostley's name is on four of them. Two are crossed out and rewritten in somebody else's hand, then crossed out again and rewritten back.",
            },
            "e": {
                "kind": "note",
                "emoji": "🩹",
                "name": "The medical corner",
                "text": "A folding table laid out with more care than the rest of the room combined. Everything labelled, everything within reach of the chair.\n\nThere are two cots. Cascade has been this far north for two years and has planned, consistently, for casualties.",
            },
            "j": {
                "kind": "note",
                "emoji": "🐬",
                "name": "The press plate",
                "text": "A single printing plate mounted on the wall like a trophy, from an edition that was never run.\n\nOne column. Four hundred and six names in eight-point type. It is the only decoration in the building.",
            },
        },
    },

    # ==============================================================
    # CRYOSPHERE DIVIDE -- Chapter 1's outdoor half, and where Josh arrives.
    #
    # Rex's cairn sits here as an optional NOTE rather than a beat. Josh will
    # not take you to it and will not talk about it; the player finding it
    # alone, unprompted, off the critical path, is a better version of that
    # scene than any dialogue could be.
    # ==============================================================
    "cryosphere_divide": {
        "name": "Cryosphere Divide",
        "blurb": "Where the shelf gives way. Xender says there is nothing here.",
        "grid": [
            "#############",
            "#J.f.s#C.g.p#",
            "#..t..#..v..#",
            "#..r.y...F.w#",
            "#####.#.....#",
            "#@.m.b#.k.dE#",
            "#############",
        ],
        "legend": {
            "J": {
                "kind": "mission",
                "emoji": "🧍",
                "name": "Josh, standing",
                "mission": "c1m1_the_man_off_the_shelf",
            },
            "C": {
                "kind": "mission",
                "emoji": "🥊",
                "name": "The survey camp",
                "mission": "c1m2_the_cut_line",
                "requires_mission": "c1m1_the_man_off_the_shelf",
                "locked_text": "Tents, four hours old, out past the divide.\n\nThere is a man at the base door who walked here from the shelf and has not been offered a chair yet. Do that first.",
            },
            "F": {
                "kind": "mission",
                "emoji": "🛠",
                "name": "The shed",
                "mission": "c1m3_no_supply_line",
                "requires_mission": "c1m2_the_cut_line",
                "locked_text": "A shed with the lights on, forty metres past a camp with a Xender rear guard standing in it.\n\nVirtual is *vibrating*. Nebula has a hand on her shoulder. “The camp first.”",
            },
            "E": {
                "kind": "exit",
                "emoji": "🚪",
                "name": "Down into the site",
                "to_area": "the_outpost",
                "to": [1, 5],
                "requires_mission": "c1m3_no_supply_line",
                "locked_text": "The service way down into Glacier 15 proper.\n\n“Kit first,” Virtual says. “I found a bench. Give me the hour.”",
            },
            "f": {
                "kind": "note",
                "emoji": "🚧",
                "name": "The new fence",
                "text": "Four metres, razor-topped, anchored into permafrost with a rig that cost more than a newspaper.\n\nThe angle is wrong for keeping people out. Every barb leans *inward*.",
            },
            "s": {
                "kind": "note",
                "emoji": "🪧",
                "name": "Site notice",
                "text": "**SITE DECOMMISSIONED — NO PERSONNEL ON SITE — XENDER INDUSTRIES**\n\nAn inspection slip is screwed underneath, signed every ninety days in the same hand for two years. The most recent one is eleven days old.",
            },
            "g": {
                "kind": "note",
                "emoji": "🚙",
                "name": "Vehicle park",
                "text": "Nine snowcats under covers, plugged into block heaters that are running.\n\nSomebody keeps nine vehicles warm at a site with no personnel on it.",
            },
            "p": {
                "kind": "note",
                "emoji": "📡",
                "name": "Relay mast",
                "text": "A mast, live, pointed south — not at the nearest town but past it, at the capital.\n\nWhatever this site says, it says directly to somebody who matters.",
            },
            "t": {
                "kind": "note",
                "emoji": "🥾",
                "name": "Boot tracks",
                "text": "A patrol route worn into the snow, doubled and redoubled, going nowhere in a loop.\n\nCurrent-issue tread. The loop has been walked several thousand times, and it never once goes near the divide.",
            },
            "r": {
                "kind": "note",
                "emoji": "🧤",
                "name": "A dropped glove",
                "text": "Half-buried, pointing away from the site. Civilian, and child-sized.\n\nThere were no civilians here. There was nobody here at all.",
            },
            "y": {
                "kind": "note",
                "emoji": "🐾",
                "name": "Four-point tracks",
                "text": "Something crossed here on four points, heavy enough to punch the crust, and it was not a snowcat.\n\nThe stride is even and the line is dead straight. Animals wander. This was walking a route.",
            },
            "v": {
                "kind": "note",
                "emoji": "✂",
                "name": "A cut strut",
                "text": "A fence strut sectioned in one pass, the cut face mirror-smooth and faintly blued.\n\nJosh looks at it for a while and then walks away without saying anything, which is itself an answer.",
            },
            "w": {
                "kind": "note",
                "emoji": "🕯",
                "name": "A cairn with a name",
                "text": "A memorial stack, older than the others, tucked where the wind cannot reach it.\n\nThe plate says **REX**. There is no date on it, because whoever built it did not know one.",
            },
            "m": {
                "kind": "note",
                "emoji": "🩺",
                "name": "Cached triage kit",
                "text": "A spare medical kit, cached at the divide, restocked and dated last week.\n\nCascade keeps supplies at the edge of this site permanently. They have never once stopped expecting to need them.",
            },
            "b": {
                "kind": "note",
                "emoji": "🛢",
                "name": "Fuel bunker",
                "text": "Diesel in quantity, with a delivery log bolted to the door.\n\nDeliveries every six weeks without a gap. The generator that eats it has never been switched off.",
            },
            "k": {
                "kind": "note",
                "emoji": "💡",
                "name": "Floodlights",
                "text": "Every floodlight lit, at noon, on a decommissioned site.\n\nJosh stands under one for a while. He was told for two years that this place was dark.",
            },
            "d": {
                "kind": "note",
                "emoji": "🧾",
                "name": "Nineteen slips",
                "text": "A clipboard in the guard shack, listing survey teams in and out.\n\nNineteen entries have an *in* time and no *out* time. Nineteen. Nobody has drawn a line under any of them.",
            },
        },
    },

    # ==============================================================
    # THE OUTPOST -- Chapter 1's interior, and the reveal.
    #
    # The notes carry what the dialogue refuses to. Nobody in the party will
    # say "there are no bodies" out loud, so the coat rack, the canteen and
    # the sign-in board say it for them.
    # ==============================================================
    "the_outpost": {
        "name": "The Outpost",
        "blurb": "Under Glacier 15. Every light on, nobody home for two years.",
        "grid": [
            "#############",
            "#c.a.L#G.x.o#",
            "#.....#.....#",
            "#.h.n.#.i.qX#",
            "###.###.###.#",
            "#@.z...S..w.#",
            "#############",
        ],
        "legend": {
            "L": {
                "kind": "mission",
                "emoji": "💻",
                "name": "The decrypt bench",
                "mission": "c1m4_the_letter",
            },
            "X": {
                "kind": "exit",
                "emoji": "🚂",
                "name": "The freight line",
                "to_area": "wastelands_line",
                "to": [1, 5],
                "requires_mission": "c1m5_what_he_left_on",
                "locked_text": "The service rail out of Glacier 15, still warm.\n\nThere is something standing on one knee at the bottom of the stairs, and nobody is leaving this building until that stops being a question."
            },
            "S": {
                "kind": "mission",
                "emoji": "🥊",
                "name": "The stairhead",
                "mission": "c1m5_what_he_left_on",
                "requires_mission": "c1m4_the_letter",
                "locked_text": "Stairs down to the vault level, and something enormous standing very still at the bottom of them.\n\n“Not yet,” Nebula says. “Walk the floor first. I want to know what we're standing on.”",
            },
            "c": {
                "kind": "note",
                "emoji": "🧥",
                "name": "The coat rack",
                "text": "Forty coats. Winter coats, the serious kind, still hanging.\n\nNobody walked out of Glacier 15 into that weather without a coat. Nobody walked out at all.",
            },
            "a": {
                "kind": "note",
                "emoji": "☕",
                "name": "The canteen",
                "text": "Trays on tables. Cups set down mid-conversation, in pairs and fours.\n\nFrozen solid and perfectly arranged. This room was not evacuated. It was *left*, between one sentence and the next.",
            },
            "G": {
                "kind": "note",
                "emoji": "🖥",
                "name": "Reception terminal",
                "text": "The sign-in board is live. **ON SITE TODAY: 0.**\n\nVirtual scrolls back through it. It has read zero every day for two years. The day before that it read 406, and the day before that, and the day before that.",
            },
            "x": {
                "kind": "note",
                "emoji": "🚸",
                "name": "The crèche",
                "text": "A site this remote ran on families. There is a room here with small chairs in it.\n\nA medical kit is cached by the door, restocked. Whoever restocks it goes in, comes out, and does not comment.",
            },
            "o": {
                "kind": "note",
                "emoji": "📦",
                "name": "Outbound crates",
                "text": "Two hundred crates, sealed, labelled for a freight route running further north than the map goes.\n\nManifests list contents by weight only. Every crate is within four kilos of every other crate — the same stencil you saw on a pallet in a burning lab.",
            },
            "h": {
                "kind": "note",
                "emoji": "🪪",
                "name": "A dropped badge",
                "text": "**J. — SITE ENGINEERING — GLACIER 15.**\n\nJosh picks it up, looks at it for a long moment, and puts it in his pocket. He does not say whose it is, and the initial is not his.",
            },
            "n": {
                "kind": "note",
                "emoji": "🕰",
                "name": "The wall clock",
                "text": "Still running. Still right, to the second, after two years on backup power.\n\nSomebody is maintaining this building to a standard. They are simply not living in it.",
            },
            "i": {
                "kind": "note",
                "emoji": "🩻",
                "name": "Medical bay",
                "text": "Stocked, sterile, untouched. The intake log runs for eleven years and stops on a Tuesday.\n\nThe last four entries are the same complaint in four different handwritings: *headaches, whole shift, all of us.*",
            },
            "q": {
                "kind": "note",
                "emoji": "🧹",
                "name": "The swept line",
                "text": "A clean strip across the floor, two metres wide, running from the outbound crates to the stairhead.\n\nEverything either side is under two years of dust. Something goes up and down this line often enough to keep it polished.",
            },
            "z": {
                "kind": "note",
                "emoji": "🔌",
                "name": "Distribution board",
                "text": "Site power, itemised. Lighting, heating, comms — all trivial.\n\nNinety-one percent of everything this site has drawn for two years goes to one unlabelled circuit, and that circuit goes *down*.",
            },
            "w": {
                "kind": "note",
                "emoji": "🧯",
                "name": "The sealed corridor",
                "text": "A corridor welded shut from the inside, with a handwritten sign wired to it:\n\n**DO NOT OPEN. NOT FOR YOUR SAKE.**\n\nNobody suggests opening it. Everybody looks at it for a long time.",
            },
        },
    },

    # ==============================================================
    # THE WASTELANDS LINE -- Chapter 2's outdoor half.
    #
    # The picket is canon (Cascade protects strikers and rioters in the
    # Wastelands) but reframed: the party is not assigned here, they are
    # chasing freight and walk into four hundred people sitting on the rails.
    # Josh counts them. Nobody makes him say the other number.
    # ==============================================================
    "wastelands_line": {
        "name": "The Wastelands — The Line",
        "blurb": "Rail, dust, and four hundred people refusing to move.",
        "grid": [
            "#############",
            "#F.s.b#P.r.w#",
            "#..t..#..k..#",
            "#..m.y...B.g#",
            "#####.#.....#",
            "#@.c.d#.n.qE#",
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
                "locked_text": "Banners, braziers, and a lot of people who have not moved in nine days.\n\nWork out where the freight is going before you walk into somebody else's strike.",
            },
            "E": {
                "kind": "exit",
                "emoji": "🚪",
                "name": "Down to Entrospire",
                "to_area": "entrospire_underside",
                "to": [1, 5],
                "requires_mission": "c2m2_the_picket",
                "locked_text": "The service stair down into the city, past a line of company security who are still deciding.\n\nSettle the embankment first.",
            },
            "B": {
                "kind": "note",
                "emoji": "📯",
                "name": "The strike fund tin",
                "text": "A biscuit tin with a slot cut in the lid and nine days of coins in it.\n\nWhen they empty it into your hands later, you will try to refuse, and the organiser will close your fingers on it the way Nebula did with the relay tag.",
            },
            "s": {
                "kind": "note",
                "emoji": "🪧",
                "name": "Banners",
                "text": "**PAY US** on most of them. On three, in different handwriting: **WHAT IS ON THE NIGHT TRAIN.**\n\nThose three are at the back, where the company photographers can't get an angle on them.",
            },
            "b": {
                "kind": "note",
                "emoji": "🔥",
                "name": "Brazier",
                "text": "An oil drum burning sleepers. Somebody has been feeding it for nine days.\n\nThere is a rota chalked on the drum. It is more organised than Cascade's.",
            },
            "r": {
                "kind": "note",
                "emoji": "📸",
                "name": "Company photographers",
                "text": "Two of them, on the embankment, photographing faces rather than banners.\n\nDolphe watches them work with an expression you cannot read. \"That used to be a job I hired for,\" he says.",
            },
            "w": {
                "kind": "note",
                "emoji": "🛤",
                "name": "The points",
                "text": "A set of points, padlocked in the straight-through position, with the lock painted over.\n\nSomething comes through here that is not allowed to be diverted.",
            },
            "t": {
                "kind": "note",
                "emoji": "🥾",
                "name": "Nine days of boots",
                "text": "The ballast is worn to powder in a strip forty metres long.\n\nFour hundred people have been walking the same short distance back and forth for over a week, because sitting still is harder than it sounds.",
            },
            "k": {
                "kind": "note",
                "emoji": "🍲",
                "name": "The soup line",
                "text": "Two trestle tables and an operation feeding four hundred people on nothing.\n\nA sign: **IF YOU ARE HUNGRY YOU ARE ONE OF US. THIS INCLUDES SCABS. WE ARE NOT ANIMALS.**",
            },
            "m": {
                "kind": "note",
                "emoji": "🚙",
                "name": "Security staging",
                "text": "Nine company vehicles parked in a line, engines warm, nobody in them.\n\nThey have been warm for nine days. This is a threat being made slowly.",
            },
            "y": {
                "kind": "note",
                "emoji": "🧾",
                "name": "The yard bosses' notice",
                "text": "**ALL SCHEDULED FREIGHT SUSPENDED PENDING RESOLUTION.**\n\nUnderneath, a second notice in a different font: **EXCEPT SERVICE 0210.** No explanation. No signature that isn't a letter.",
            },
            "g": {
                "kind": "note",
                "emoji": "📻",
                "name": "A borrowed radio",
                "text": "Somebody has rigged a receiver to the overhead line and is listening to company traffic.\n\nThey offer you the earpiece without being asked. Cascade has been doing this alone for two years and did not have to be.",
            },
            "c": {
                "kind": "note",
                "emoji": "🪦",
                "name": "Trackside marker",
                "text": "A memorial spike driven between the sleepers, with a hard hat wired to it.\n\n'06. A derailment the company called operator error. The operator's family are somewhere in this crowd.",
            },
            "d": {
                "kind": "note",
                "emoji": "🧊",
                "name": "Ice in the ballast",
                "text": "Frost, this far south, in the wrong season.\n\nWhatever runs on the night service is coming down off the shelf cold enough to bring the shelf with it.",
            },
            "n": {
                "kind": "note",
                "emoji": "🐾",
                "name": "Four-point tracks",
                "text": "The same even stride, the same dead-straight line, four hundred kilometres from the last set.\n\nIt crosses the rails once and does not come back.",
            },
            "q": {
                "kind": "note",
                "emoji": "🎺",
                "name": "The organiser's whistle",
                "text": "A referee's whistle on a bootlace, hung on a signal post where anyone can reach it.\n\nFour hundred people have agreed that whoever gets to it first is in charge. It has not been needed yet.",
            },
        },
    },

    # ==============================================================
    # ENTROSPIRE UNDERSIDE -- Chapter 2's interior, Chary, and Rohan.
    #
    # He is on screen here for the first time, and the area is built so that
    # he is standing at the END of it: the yard tile is the last thing you can
    # reach, and the notes on the way there are all evidence that he has been
    # running this for two years while nobody looked.
    # ==============================================================
    "entrospire_underside": {
        "name": "Entrospire — The Underside",
        "blurb": "Beneath the rail deck. Everything down here signs for itself.",
        "grid": [
            "#############",
            "#C.l.p#Y.h.v#",
            "#..a..#..e..#",
            "#..u.z...M.j#",
            "#####.#.....#",
            "#@.f.o#.R.dK#",
            "#############",
        ],
        "legend": {
            "C": {
                "kind": "mission",
                "emoji": "🃏",
                "name": "Chary's table",
                "mission": "c2m3_the_underside",
            },
            "Y": {
                "kind": "mission",
                "emoji": "🥊",
                "name": "The night yard",
                "mission": "c2m4_what_is_in_them",
                "requires_mission": "c2m3_the_underside",
                "locked_text": "A yard that closed in '06 and has lights on.\n\nYou need the key, and the woman with the key is dealing cards two streets west and has already seen you coming.",
            },
            "M": {
                "kind": "mission",
                "emoji": "🔻",
                "name": "The end of the yard",
                "mission": "c2m5_the_man_himself",
                "requires_mission": "c2m4_what_is_in_them",
                "locked_text": "There is a man sitting on a crate down there and he has not moved since you arrived.\n\nOpen the crates first. He seems content to wait, which is its own kind of answer.",
            },
            "K": {
                "kind": "note",
                "emoji": "🚧",
                "name": "The north gate",
                "text": "Chained, and the chain is threaded from the inside.\n\nWhen this opens it will be because somebody chose to open it for you, and that should worry you more than it does.",
            },
            "l": {
                "kind": "note",
                "emoji": "🪑",
                "name": "The long game",
                "text": "Chary's table has four chairs and three of them are stacked.\n\nShe plays alone most nights now. The regulars stopped coming down here about two years ago and nobody will say why.",
            },
            "p": {
                "kind": "note",
                "emoji": "💡",
                "name": "Deck lighting",
                "text": "The underside runs on light leaking through the rail deck above.\n\nWhen a train passes, the whole street strobes. Twice a month, at night, it strobes for a service nobody has a timetable for.",
            },
            "a": {
                "kind": "note",
                "emoji": "📇",
                "name": "The fence's index",
                "text": "A card index of everything sellable in Entrospire, cross-referenced by who wants it dead.\n\nUnder R there is one card. It is blank. It has been handled so often the corners are soft.",
            },
            "u": {
                "kind": "note",
                "emoji": "🩸",
                "name": "A cleaned patch",
                "text": "A section of pavement scrubbed to a different colour than the rest.\n\nSomebody did a thorough job, some time ago, and then kept doing it. It is the cleanest thing in the Underside.",
            },
            "z": {
                "kind": "note",
                "emoji": "📦",
                "name": "Empty crates",
                "text": "Crate frames stacked eight high, all the same dimensions as the ones at Glacier 15.\n\nThey are stencilled for the same route. They have never been filled.",
            },
            "h": {
                "kind": "note",
                "emoji": "🕯",
                "name": "A shrine of names",
                "text": "Candles, photographs, and a hand-lettered list under a sheet of plastic.\n\nIt is not the Glacier 15 list. It is longer, and more recent, and nobody official has ever counted it.",
            },
            "e": {
                "kind": "note",
                "emoji": "🧮",
                "name": "The yard ledger",
                "text": "Service 0210, twice a month, two years without a gap.\n\nSigned out every time by a single letter. Countersigned, every time, by a yard boss who resigned in '06 and has not been seen since.",
            },
            "v": {
                "kind": "note",
                "emoji": "🚿",
                "name": "Standpipe",
                "text": "The Underside's only clean water, and a laminated sign beside it:\n\n**TESTED DAILY. IT IS FINE. — D.**\n\nSomeone has added: *he really does come all this way to test it.*",
            },
            "j": {
                "kind": "note",
                "emoji": "🎞",
                "name": "Deck camera",
                "text": "A company camera bolted under the deck, pointed at the yard gate.\n\nThe cable has been spliced. Somebody has been watching the watchers, patiently, for a very long time.",
            },
            "f": {
                "kind": "note",
                "emoji": "🪟",
                "name": "Pawnbroker's window",
                "text": "Field kit, mostly. Ocellios badges, Xender issue, a Cascade relay tag with the strap cut.\n\nThe tag is not yours. Somebody else lit beacons once, and got this far, and stopped.",
            },
            "o": {
                "kind": "note",
                "emoji": "🚬",
                "name": "Somebody waiting",
                "text": "A doorway across from the yard gate with two years of cigarette ends in it, all the same brand.\n\nWhoever stands here does not smoke in a hurry, and has never once been moved on.",
            },
            "R": {
                "kind": "note",
                "emoji": "🪑",
                "name": "The crate at the end",
                "text": "A packing crate, set square to the yard's centre line, with a coat folded on it.\n\nIt is the only thing down here arranged for comfort. Somebody sits here to watch, regularly, and expects to be sitting a while.",
            },
            "d": {
                "kind": "note",
                "emoji": "🗝",
                "name": "A spare key, hung openly",
                "text": "On a nail beside the north gate, in plain sight, where anyone could take it.\n\nNobody has. In two years, in a district that steals everything, nobody has touched this key.",
            },
        },
    },

}


# Which area a new player starts in, and where.
STARTING_AREA = "ocellios_ruin"


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
