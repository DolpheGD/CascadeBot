"""
The Void Abyss: the endgame mode.

Pure data, like every other *_config module. The interpreter lives in
bot/services/abyss_service.py and knows nothing about any specific floor,
which is what lets tools/check_abyss.py validate the whole ladder without
a database.

----------------------------------------------------------------------
THE ONE RULE THAT MAKES THIS DIFFERENT
----------------------------------------------------------------------
A floor is several CHAMBERS, and **no character may appear in more than
one chamber of the same floor**.

Everything else in the game rewards finding your four best characters and
never thinking about it again. This is the only mode that asks the
opposite question: how deep does your roster actually go? A player with
one immaculate squad and eleven benchwarmers will clear the early floors
and stop dead, and that is the intended experience -- the wall is roster
DEPTH, not gear.

That single constraint is why the Abyss can't be tuned like a raid. Fight
difficulty matters, but the real difficulty is that your second and third
teams are, by definition, the characters you didn't pick.

----------------------------------------------------------------------
STATIC FLOORS vs ROTATING FLOORS
----------------------------------------------------------------------
Floors 1-8 are STATIC. Their rewards are one-time, they never reset, and
they exist so that a mid-game player has something to chip at. Several are
clearable long before the endgame.

Floors 9-12 are ROTATING. They reset every ROTATION_DAYS, their enemies
change with the rotation, and their rewards are claimable once PER
ROTATION. This is the actual endgame: the hardest content in the game,
repeatable, and it never becomes a solved problem you farm forever with
one answer.

Rotation is derived from the calendar, not stored per player -- see
abyss_service.current_rotation(). Nothing schedules anything; the floor
you see is a function of what day it is, so there is no job to miss and
no state to drift.

----------------------------------------------------------------------
STARS
----------------------------------------------------------------------
Three per floor, and the extra two are deliberately about HOW you won:

    1  clear every chamber
    2  ...within STAR_CYCLE_LIMIT cycles in every chamber
    3  ...without losing a single character in any chamber

Speed and survival pull in opposite directions -- a defensive squad
survives but runs long, a glass squad is fast and fragile -- so three
stars means both halves of your roster are genuinely good, not just one.
"""

from __future__ import annotations

import datetime as dt

# ----------------------------------------------------------------------
# Rules
# ----------------------------------------------------------------------

# Rotating floors reset on this cadence. Two weeks is long enough that a
# player who misses a few days hasn't lost a cycle, and short enough that
# a bad rotation for your roster isn't a month-long wall.
ROTATION_DAYS = 14

# The epoch every rotation is counted from. Fixed, so the rotation index
# is a pure function of the date and never needs storing.
ROTATION_EPOCH = dt.date(2026, 1, 5)

# Cycles allowed per chamber for the second star.
STAR_CYCLE_LIMIT = 12

MAX_STARS_PER_FLOOR = 3

# Floors at or above this index rotate. Below it they are permanent.
FIRST_ROTATING_FLOOR = 9

# A chamber's team is a full squad. Chambers-per-floor times this is the
# number of DISTINCT characters a floor demands.
TEAM_SIZE = 4


# ----------------------------------------------------------------------
# FLOORS
#
# `chambers` is a list of enemy lists. Two chambers means 8 distinct
# characters; three means 12. The jump to three chambers at floor 9 is
# the real gate on the endgame, and it lines up with the rotation
# boundary on purpose: the rotating floors are exactly the ones that ask
# for a third team.
#
# `level` is per floor, applied to every enemy in it.
# `rewards` are ONE-TIME for static floors, once-per-rotation for
# rotating ones.
# ----------------------------------------------------------------------

FLOORS: list[dict] = [
    {
        "floor": 1,
        "name": "The Threshold",
        "blurb": "The first step down. It is not far.",
        "level": 12,
        "min_roster_levels": 40,
        "chambers": [
            ["Xender Henchmen", "Xender Recon Scout", "Concussion Drone"],
            ["Rogue Security Drone", "Ad-Drone Swarm Unit"],
        ],
        "rewards": {"gold": 1_200, "shards": 80, "reroll_tokens": 6},
    },
    {
        "floor": 2,
        "name": "Cold Shelf",
        "blurb": "Ice that was never on the surface.",
        "level": 18,
        "min_roster_levels": 70,
        "chambers": [
            ["Frostblock", "Xender Enforcer"],
            ["Glacial Exterminator", "Xender Loyalist", "Xender Loyalist"],
        ],
        "rewards": {"gold": 1_800, "shards": 110, "permafrost_ore": 60, "reroll_tokens": 8},
    },
    {
        "floor": 3,
        "name": "The Sorting",
        "blurb": "Something down here has been categorising the dead.",
        "level": 24,
        "min_roster_levels": 110,
        "chambers": [
            ["Ledger Warden", "Xender Convoy"],
            ["Voidwarp Construct", "Ocellios Test Subject", "Xendium Overcharge Drone"],
        ],
        "rewards": {"gold": 2_400, "shards": 140, "crystal": 50, "reroll_tokens": 10},
    },
    {
        "floor": 4,
        "name": "Hollow Choir",
        "blurb": "Voices, arranged in rows, none of them speaking.",
        "level": 32,
        "min_roster_levels": 160,
        "chambers": [
            ["Propaganda Broadcast Unit", "Hater Ringleader"],
            ["Sir Vengeance", "Refense Hater", "Jynxzi"],
        ],
        "rewards": {"gold": 3_200, "shards": 180, "crystal": 70, "reroll_tokens": 12,
                    "item": "epic"},
    },
    {
        "floor": 5,
        "name": "The Long Ledger",
        "blurb": "Every name that was never printed.",
        "level": 40,
        "min_roster_levels": 220,
        "chambers": [
            ["The Lector of Ledgers"],
            ["Blightspire Adept", "Shatterjaw Reaver", "Ashplate Warden"],
        ],
        "rewards": {"gold": 4_200, "shards": 220, "xendium": 60, "reroll_tokens": 15},
    },
    {
        "floor": 6,
        "name": "Permafrost Gate",
        "blurb": "The doorman had a doorman.",
        "level": 48,
        "min_roster_levels": 300,
        "chambers": [
            ["Permafrost Guardian", "Frostblock"],
            ["Void Hydra"],
        ],
        "rewards": {"gold": 5_200, "shards": 260, "crystal": 110, "reroll_tokens": 18,
                    "item": "epic"},
    },
    {
        "floor": 7,
        "name": "Company Floor",
        "blurb": "Acatrya keeps its own things down here too.",
        "level": 56,
        "min_roster_levels": 400,
        "chambers": [
            ["The Auditor", "Acatrya Elite Guard"],
            ["The Censor", "Abyssal Custodian"],
        ],
        "rewards": {"gold": 6_500, "shards": 300, "xendium": 100, "reroll_tokens": 22},
    },
    {
        "floor": 8,
        "name": "The Quiet Machine",
        "blurb": "Still running. Nobody has been here to switch it off.",
        "level": 64,
        "min_roster_levels": 520,
        "chambers": [
            ["Boss John's Driller Prototype"],
            ["Ocellios Train", "Mech Gunpod", "Mech Gunpod"],
        ],
        "rewards": {"gold": 8_000, "shards": 360, "crystal": 160, "reroll_tokens": 26,
                    "item": "legendary"},
    },

    # ------------------------------------------------------------------
    # ROTATING FLOORS. Three chambers each -- twelve distinct characters.
    #
    # `rotations` replaces `chambers`: the service picks
    # rotations[rotation_index % len(rotations)]. Every variant of a
    # floor must have the same number of chambers, so the roster demand
    # doesn't move under a player mid-cycle. check_abyss asserts it.
    # ------------------------------------------------------------------
    {
        "floor": 9,
        "name": "Void Crest",
        "blurb": "The first floor that wants a third team.",
        "level": 72,
        "min_roster_levels": 650,
        "rotations": [
            [["Eris Sentinel"],
             ["The Chairman", "Ledger Warden"],
             ["Gatekeeper", "Borehole"]],
            [["Stubby's Failsafe"],
             ["Acatrya Prime Enforcer", "Acatrya Elite Guard"],
             ["Rupture", "The Auditor"]],
            [["X-RR"],
             ["Corrupted Bli", "Xendium Overcharge Drone"],
             ["Dorve", "Mech Gunpod", "Mech Gunpod"]],
        ],
        "rewards": {"gold": 11_000, "shards": 450, "crystal": 220, "xendium": 140,
                    "reroll_tokens": 30, "item": "legendary"},
    },
    {
        "floor": 10,
        "name": "The Undertow",
        "blurb": "Down far enough that the void is the floor.",
        "level": 80,
        "min_roster_levels": 800,
        "rotations": [
            [["Void Hydra", "Voidwarp Construct"],
             ["Eris Sentinel"],
             ["The Censor", "The Auditor"]],
            [["Boss John's Driller Prototype", "Xender Convoy"],
             ["X-RR"],
             ["The Chairman", "Abyssal Custodian"]],
            [["Gatekeeper", "Borehole"],
             ["Stubby's Failsafe"],
             ["Rupture", "Corrupted Eris Sentry"]],
        ],
        "rewards": {"gold": 14_000, "shards": 550, "crystal": 300, "xendium": 200,
                    "reroll_tokens": 36, "item": "legendary"},
    },
    {
        "floor": 11,
        "name": "Acatrya's Deep",
        "blurb": "The capital keeps its worst decisions where nobody visits.",
        "level": 88,
        "min_roster_levels": 950,
        "rotations": [
            [["Acatrya Prime Enforcer", "Acatrya Elite Guard"],
             ["The Chairman", "The Auditor"],
             ["Eris Sentinel"]],
            [["X-RR", "Ashplate Warden"],
             ["Stubby's Failsafe", "Ocellios Train"],
             ["Void Hydra", "Blightspire Adept"]],
            [["Gatekeeper", "The Censor"],
             ["Dorve", "Corrupted Bli"],
             ["Boss John's Driller Prototype", "Skybridge Sentinel"]],
        ],
        "rewards": {"gold": 18_000, "shards": 700, "crystal": 400, "xendium": 280,
                    "void": 60, "reroll_tokens": 44, "item": "mythic"},
    },
    {
        "floor": 12,
        "name": "The Bottom",
        "blurb": "There is a man down here who has been waiting a very long time.",
        "level": 95,
        "min_roster_levels": 1_100,
        "rotations": [
            [["Eris Sentinel", "Abyssal Custodian"],
             ["X-RR", "Ashplate Warden"],
             ["Rohan"]],
            [["Xender"],
             ["The Chairman", "The Auditor", "The Censor"],
             ["Rohan"]],
            [["Stubby's Failsafe", "Ocellios Train"],
             ["Acatrya Prime Enforcer", "Gatekeeper"],
             ["Rohan"]],
        ],
        # Rohan is in EVERY floor-12 rotation on purpose. The bottom of
        # the Abyss is not a random boss slot -- it is the same man, every
        # time, and the rest of the floor changes around him.
        "rewards": {"gold": 25_000, "shards": 900, "crystal": 550, "xendium": 400,
                    "void": 120, "entropy": 60, "reroll_tokens": 60, "item": "mythic"},
    },
]


# ----------------------------------------------------------------------
# Lookups
# ----------------------------------------------------------------------

def get_floor(number: int) -> dict | None:
    return next((f for f in FLOORS if f["floor"] == number), None)


def is_rotating(floor: dict) -> bool:
    return floor["floor"] >= FIRST_ROTATING_FLOOR


def chamber_count(floor: dict) -> int:
    if "chambers" in floor:
        return len(floor["chambers"])
    return len(floor["rotations"][0])


def characters_required(floor: dict) -> int:
    return chamber_count(floor) * TEAM_SIZE


def chambers_for(floor: dict, rotation_index: int) -> list[list[str]]:
    """The enemy lists for this floor in this rotation.

    Static floors ignore the rotation entirely, which is what makes them
    safe to hold one-time rewards."""
    if "chambers" in floor:
        return floor["chambers"]
    variants = floor["rotations"]
    return variants[rotation_index % len(variants)]


def max_stars() -> int:
    return len(FLOORS) * MAX_STARS_PER_FLOOR
