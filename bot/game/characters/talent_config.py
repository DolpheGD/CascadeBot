"""
Per-character talent trees.

    points = level // POINTS_PER_LEVEL     (level 40 -> 8, level 100 -> 20)

Every character has their own tree: three branches, eleven nodes, and a
capstone at the end of each branch that only they have. Respec is free
(see talent_service.reset) because a tree you are afraid to touch is a
tree nobody experiments with, and experimenting is the entire appeal.

----------------------------------------------------------------------
HOW 35 TREES ARE AUTHORED WITHOUT 35 SEPARATE BALANCE PROBLEMS
----------------------------------------------------------------------
Each tree is COMPOSED, not hand-written:

  * the SHAPE and the stat nodes come from the character's class spine
    (see CLASS_SPINES). A DPS tree and a Sustain tree branch differently
    because those roles want different things, and every DPS gets the
    same skeleton.
  * the NAMES and the three CAPSTONES are per character (see
    CHARACTER_TALENTS), and the capstone is tied to what that character
    actually does.

This is a deliberate trade. Fully hand-authoring 35 trees means 35
independent power budgets, and the fifth time somebody adds "+8% attack"
where the spine says 6 the roster quietly stops being balanced against
itself -- with no error anywhere, because a number in a config is always
valid. Composing from a spine means the budget is defined once, in one
table, and tools/check_talents.py asserts every tree respects it.

What the player sees is still a tree with their character's name on it,
their character's flavour, and three capstones nobody else has.

----------------------------------------------------------------------
THE POWER BUDGET
----------------------------------------------------------------------
Talents are a MULTIPLIER ON BASE STATS, applied in
factory.base_character_stats alongside level_power_multiplier -- so they
scale with the character rather than washing out, and gear percentages
still compute against the pre-gear number.

MEASURED, not asserted -- and the first version of this paragraph was
wrong, which is why it is now a quoted number from a tool rather than a
claim. tools/check_talents.py brute-forces every affordable, prerequisite-
respecting subset of all 35 trees and reports the best case:

    +30% in one stat at level 40 (8 points), +30% at level 100

The level-40 figure is one branch bought all the way down INCLUDING its
capstone, which is the whole of a story-finishing character's points
spent on a single line. That is meant to be strong: it costs them both
other branches. It is also why the two figures are the same -- a branch
caps out at 8 points, and the extra 12 points at level 100 buy breadth
rather than more of the same stat.

This paragraph originally claimed +12%, and it was describing one branch
while the tables allowed the same stat to appear in all three. The check
existed, ran, and printed 30. Numbers in docstrings are worth what the
tool that verifies them is worth.

The ladder consequence is real: the story's 28 fights, its 3 hunts and
all five adventure regions were tuned against characters with no talents.
check_story's difficulty model now buys a realistic branch for every
simulated character, and the enemy levels were re-solved against it.
"""

from __future__ import annotations

from bot.database.models.enums import CharacterClass

# One talent point per this many character levels.
POINTS_PER_LEVEL = 5

# A node may never cost more than this, and a whole tree may never cost
# less than the points a level-100 character has -- if it could be fully
# bought, there is no choice being made and the tree is just a stat
# bonus with extra clicks.
MAX_NODE_COST = 3
MIN_TREE_COST_ABOVE_MAX_POINTS = 4


# ----------------------------------------------------------------------
# CLASS SPINES
#
# `tier` is the depth in its branch; a node needs every earlier node in
# the same branch bought first (talent_service enforces this, not the
# config). `effect` is {stat, percent} or {stat, flat}.
#
# Percentages are on BASE stats, so they compose additively within a
# branch and never compound -- two +6% nodes are +12%, not +12.36%.
# Compounding is how a tree that looks modest in the config turns out to
# be worth 60% in play.
#
# A STAT APPEARS IN AT MOST ONE BRANCH PER SPINE. The first version of
# these tables let max_hp appear in two branches AND the capstone, so a
# Sustain could stack 7 + 9 + 6 + 14 and tools/check_talents.py measured
# a best case of +30% at level 40 against a docstring in this very file
# claiming "roughly +12%". The docstring was not lying on purpose; it was
# describing one branch while the tree allowed three. Keeping each stat
# to one branch is what makes the per-branch budget the real budget.
# ----------------------------------------------------------------------
CLASS_SPINES: dict[CharacterClass, list[dict]] = {
    CharacterClass.DPS: [
        # branch A -- raw damage
        {"branch": "a", "tier": 1, "cost": 1, "effect": {"stat": "attack", "percent": 4}},
        {"branch": "a", "tier": 2, "cost": 1, "effect": {"stat": "crit_rate", "flat": 3}},
        {"branch": "a", "tier": 3, "cost": 2, "effect": {"stat": "attack", "percent": 6}},
        {"branch": "a", "tier": 4, "cost": 3, "effect": {"stat": "crit_damage", "flat": 18}},
        # branch B -- staying alive long enough to use it
        {"branch": "b", "tier": 1, "cost": 1, "effect": {"stat": "max_hp", "percent": 5}},
        {"branch": "b", "tier": 2, "cost": 1, "effect": {"stat": "defense", "percent": 5}},
        {"branch": "b", "tier": 3, "cost": 2, "effect": {"stat": "max_hp", "percent": 7}},
        # branch C -- tempo
        {"branch": "c", "tier": 1, "cost": 1, "effect": {"stat": "speed", "percent": 4}},
        {"branch": "c", "tier": 2, "cost": 2, "effect": {"stat": "recharge", "flat": 6}},
        {"branch": "c", "tier": 3, "cost": 2, "effect": {"stat": "speed", "percent": 5}},
    ],
    CharacterClass.SUPPORT_DPS: [
        {"branch": "a", "tier": 1, "cost": 1, "effect": {"stat": "elemental", "percent": 4}},
        {"branch": "a", "tier": 2, "cost": 1, "effect": {"stat": "crit_rate", "flat": 3}},
        {"branch": "a", "tier": 3, "cost": 2, "effect": {"stat": "elemental", "percent": 6}},
        {"branch": "a", "tier": 4, "cost": 3, "effect": {"stat": "crit_damage", "flat": 16}},
        {"branch": "b", "tier": 1, "cost": 1, "effect": {"stat": "max_hp", "percent": 5}},
        {"branch": "b", "tier": 2, "cost": 1, "effect": {"stat": "defense", "percent": 5}},
        {"branch": "b", "tier": 3, "cost": 2, "effect": {"stat": "max_mana", "percent": 10}},
        {"branch": "c", "tier": 1, "cost": 1, "effect": {"stat": "speed", "percent": 4}},
        {"branch": "c", "tier": 2, "cost": 2, "effect": {"stat": "recharge", "flat": 7}},
        {"branch": "c", "tier": 3, "cost": 2, "effect": {"stat": "speed", "percent": 5}},
    ],
    CharacterClass.AMPLIFIER: [
        {"branch": "a", "tier": 1, "cost": 1, "effect": {"stat": "elemental", "percent": 4}},
        {"branch": "a", "tier": 2, "cost": 1, "effect": {"stat": "recharge", "flat": 5}},
        {"branch": "a", "tier": 3, "cost": 2, "effect": {"stat": "elemental", "percent": 6}},
        {"branch": "a", "tier": 4, "cost": 3, "effect": {"stat": "recharge", "flat": 10}},
        {"branch": "b", "tier": 1, "cost": 1, "effect": {"stat": "max_hp", "percent": 6}},
        {"branch": "b", "tier": 2, "cost": 1, "effect": {"stat": "defense", "percent": 6}},
        {"branch": "b", "tier": 3, "cost": 2, "effect": {"stat": "max_hp", "percent": 8}},
        {"branch": "c", "tier": 1, "cost": 1, "effect": {"stat": "speed", "percent": 5}},
        {"branch": "c", "tier": 2, "cost": 2, "effect": {"stat": "max_mana", "percent": 12}},
        {"branch": "c", "tier": 3, "cost": 2, "effect": {"stat": "speed", "percent": 5}},
    ],
    CharacterClass.SUSTAIN: [
        {"branch": "a", "tier": 1, "cost": 1, "effect": {"stat": "elemental", "percent": 5}},
        {"branch": "a", "tier": 2, "cost": 1, "effect": {"stat": "max_mana", "percent": 10}},
        {"branch": "a", "tier": 3, "cost": 2, "effect": {"stat": "elemental", "percent": 7}},
        {"branch": "a", "tier": 4, "cost": 3, "effect": {"stat": "recharge", "flat": 9}},
        {"branch": "b", "tier": 1, "cost": 1, "effect": {"stat": "max_hp", "percent": 7}},
        {"branch": "b", "tier": 2, "cost": 1, "effect": {"stat": "defense", "percent": 7}},
        {"branch": "b", "tier": 3, "cost": 2, "effect": {"stat": "max_hp", "percent": 9}},
        {"branch": "c", "tier": 1, "cost": 1, "effect": {"stat": "speed", "percent": 4}},
        {"branch": "c", "tier": 2, "cost": 2, "effect": {"stat": "speed", "percent": 6}},
        {"branch": "c", "tier": 3, "cost": 2, "effect": {"stat": "recharge", "flat": 6}},
    ],
}

# Branch names by class -- what the three lines of a tree are ABOUT.
BRANCH_NAMES: dict[CharacterClass, dict[str, str]] = {
    CharacterClass.DPS: {"a": "Edge", "b": "Footing", "c": "Tempo"},
    CharacterClass.SUPPORT_DPS: {"a": "Pressure", "b": "Footing", "c": "Cadence"},
    CharacterClass.AMPLIFIER: {"a": "Reach", "b": "Anchor", "c": "Flow"},
    CharacterClass.SUSTAIN: {"a": "Mercy", "b": "Bulwark", "c": "Vigil"},
}

# Node names by class and branch tier, so a tree reads as prose rather
# than as a stat sheet. Index is tier - 1.
NODE_NAMES: dict[CharacterClass, dict[str, list[str]]] = {
    CharacterClass.DPS: {
        "a": ["Follow Through", "Find The Gap", "Commit", "No Second Swing"],
        "b": ["Planted", "Brace", "Hold The Line"],
        "c": ["First Move", "Wind Up", "Keep Going"],
    },
    CharacterClass.SUPPORT_DPS: {
        "a": ["Mark It", "Read The Room", "Lean On It", "Nowhere Left"],
        "b": ["Planted", "Brace", "Deep Reserve"],
        "c": ["First Move", "Second Wind", "Press It"],
    },
    CharacterClass.AMPLIFIER: {
        "a": ["Carry", "Prompt", "Amplify", "Never Off Beat"],
        "b": ["Anchored", "Set", "Immovable"],
        "c": ["Light Feet", "Deep Reserve", "Quicker Still"],
    },
    CharacterClass.SUSTAIN: {
        "a": ["Steady Hands", "Deep Reserve", "Better Hands", "Always There"],
        "b": ["Rooted", "Set", "Unmoved"],
        "c": ["Light Feet", "Guarded", "Still Standing"],
    },
}

# ----------------------------------------------------------------------
# PER-CHARACTER CAPSTONES
#
# One per branch, bought last, costing 3. This is the part that is
# genuinely per character: the name is theirs, and the effect leans into
# what their kit already does rather than adding a generic slab of stat.
#
# Characters not listed here fall back to a generated capstone from their
# class (see tree_for). That fallback exists so a newly-added character
# is playable the moment they are seeded rather than crashing the talent
# screen -- but tools/check_talents.py reports how many are relying on it,
# because a roster that is 80% fallback has stopped being per-character
# in anything but name.
# ----------------------------------------------------------------------
CHARACTER_CAPSTONES: dict[str, dict[str, dict]] = {
    "Josh": {
        "a": {"name": "Sixteen Freight", "effect": {"stat": "attack", "percent": 10}},
        "b": {"name": "Somebody Has To", "effect": {"stat": "max_hp", "percent": 12}},
        "c": {"name": "The Long Way Round", "effect": {"stat": "speed", "percent": 8}},
    },
    "Refender": {
        "a": {"name": "Read It Twice", "effect": {"stat": "elemental", "percent": 10}},
        "b": {"name": "Kept In The Pocket", "effect": {"stat": "max_hp", "percent": 13}},
        "c": {"name": "Before I Tell Them", "effect": {"stat": "recharge", "flat": 12}},
    },
    "Jofrog": {
        "a": {"name": "Every List, Every Year", "effect": {"stat": "elemental", "percent": 9}},
        "b": {"name": "Four Years Carrying It", "effect": {"stat": "defense", "percent": 14}},
        "c": {"name": "The Fifth Name", "effect": {"stat": "speed", "percent": 9}},
    },
    "Blueflame": {
        "a": {"name": "Paranoid, Correctly", "effect": {"stat": "crit_rate", "flat": 8}},
        "b": {"name": "Walked Past It All Week", "effect": {"stat": "defense", "percent": 12}},
        "c": {"name": "Nine Degrees Off", "effect": {"stat": "speed", "percent": 9}},
    },
    "Dolphe": {
        "a": {"name": "What He Sent", "effect": {"stat": "elemental", "percent": 11}},
        "b": {"name": "The Weight Of It", "effect": {"stat": "max_hp", "percent": 12}},
        "c": {"name": "Ahead Of The Convoy", "effect": {"stat": "recharge", "flat": 12}},
    },
    "Blastix": {
        "a": {"name": "It Spreads", "effect": {"stat": "elemental", "percent": 12}},
        "b": {"name": "Still Burning", "effect": {"stat": "max_hp", "percent": 10}},
        "c": {"name": "Faster Than It Heals", "effect": {"stat": "speed", "percent": 9}},
    },
    "Nebula": {
        "a": {"name": "Break It Open", "effect": {"stat": "elemental", "percent": 11}},
        "b": {"name": "Held Together", "effect": {"stat": "defense", "percent": 12}},
        "c": {"name": "One More Window", "effect": {"stat": "recharge", "flat": 11}},
    },
    "Kotori": {
        "a": {"name": "Paid In Advance", "effect": {"stat": "elemental", "percent": 12}},
        "b": {"name": "What It Costs", "effect": {"stat": "max_hp", "percent": 14}},
        "c": {"name": "Standing Anyway", "effect": {"stat": "speed", "percent": 9}},
    },
    "Caliper": {
        "a": {"name": "Measured Twice", "effect": {"stat": "crit_damage", "flat": 22}},
        "b": {"name": "Within Tolerance", "effect": {"stat": "max_hp", "percent": 10}},
        "c": {"name": "To The Micron", "effect": {"stat": "elemental", "percent": 8}},
    },
    "Virtual": {
        "a": {"name": "Run It Again", "effect": {"stat": "elemental", "percent": 10}},
        "b": {"name": "Cached", "effect": {"stat": "max_hp", "percent": 11}},
        "c": {"name": "No Latency", "effect": {"stat": "recharge", "flat": 13}},
    },
    "Chary": {
        "a": {"name": "The Backlog", "effect": {"stat": "elemental", "percent": 9}},
        "b": {"name": "Bring Me Materials", "effect": {"stat": "defense", "percent": 13}},
        "c": {"name": "Booth Hours", "effect": {"stat": "speed", "percent": 8}},
    },
    "Bee Jee": {
        "a": {"name": "On The Hour", "effect": {"stat": "elemental", "percent": 11}},
        "b": {"name": "Never Off Shift", "effect": {"stat": "max_hp", "percent": 13}},
        "c": {"name": "Rounds Again", "effect": {"stat": "recharge", "flat": 11}},
    },
    "Star": {
        "a": {"name": "All At Once", "effect": {"stat": "attack", "percent": 11}},
        "b": {"name": "Burn Long", "effect": {"stat": "max_hp", "percent": 10}},
        "c": {"name": "Collapse Inward", "effect": {"stat": "crit_damage", "flat": 20}},
    },
    "Aizer": {
        "a": {"name": "Straight Through", "effect": {"stat": "attack", "percent": 12}},
        "b": {"name": "Take The Hit", "effect": {"stat": "defense", "percent": 12}},
        "c": {"name": "Again, Faster", "effect": {"stat": "speed", "percent": 9}},
    },
}


# ----------------------------------------------------------------------
# Tree assembly
# ----------------------------------------------------------------------

def _fallback_capstone(character_class: CharacterClass, branch: str) -> dict:
    """A generic capstone for a character with no authored one.

    Exists so adding a character to the roster cannot break the talent
    screen. Reported by tools/check_talents.py rather than left silent --
    a fallback that nobody counts is a fallback that becomes the norm.
    """
    stat = {
        CharacterClass.DPS: {"a": "attack", "b": "max_hp", "c": "speed"},
        CharacterClass.SUPPORT_DPS: {"a": "elemental", "b": "max_hp", "c": "recharge"},
        CharacterClass.AMPLIFIER: {"a": "elemental", "b": "defense", "c": "recharge"},
        CharacterClass.SUSTAIN: {"a": "elemental", "b": "max_hp", "c": "defense"},
    }[character_class][branch]
    generic = {"a": "Mastery", "b": "Endurance", "c": "Momentum"}[branch]
    if stat in ("recharge",):
        return {"name": generic, "effect": {"stat": stat, "flat": 10}}
    return {"name": generic, "effect": {"stat": stat, "percent": 10}}


def tree_for(name: str, character_class: CharacterClass) -> list[dict]:
    """The full node list for one character.

    Node ids are `<branch><tier>` -- stable, short, and independent of
    the character, which is what lets a player's bought-node list survive
    a rename. They are NOT globally unique across characters, and do not
    need to be: a talent row is always scoped to one PlayerCharacter.
    """
    spine = CLASS_SPINES[character_class]
    branch_names = BRANCH_NAMES[character_class]
    node_names = NODE_NAMES[character_class]
    capstones = CHARACTER_CAPSTONES.get(name, {})

    nodes: list[dict] = []
    for entry in spine:
        branch, tier = entry["branch"], entry["tier"]
        names = node_names[branch]
        nodes.append({
            "id": f"{branch}{tier}",
            "branch": branch,
            "branch_name": branch_names[branch],
            "tier": tier,
            "name": names[tier - 1] if tier - 1 < len(names) else f"Tier {tier}",
            "cost": entry["cost"],
            "effect": dict(entry["effect"]),
            "capstone": False,
        })

    # One capstone per branch, one tier past that branch's deepest spine
    # node, so it is always the last thing bought.
    for branch in sorted(branch_names):
        deepest = max((n["tier"] for n in nodes if n["branch"] == branch), default=0)
        capstone = capstones.get(branch) or _fallback_capstone(character_class, branch)
        nodes.append({
            "id": f"{branch}{deepest + 1}",
            "branch": branch,
            "branch_name": branch_names[branch],
            "tier": deepest + 1,
            "name": capstone["name"],
            "cost": 3,
            "effect": dict(capstone["effect"]),
            "capstone": True,
            "authored": branch in capstones,
        })
    return nodes


def points_for_level(level: int) -> int:
    return max(0, int(level) // POINTS_PER_LEVEL)


def node_by_id(nodes: list[dict], node_id: str) -> dict | None:
    return next((n for n in nodes if n["id"] == node_id), None)


def prerequisites(nodes: list[dict], node_id: str) -> list[str]:
    """Every earlier node in the same branch. A branch is a line, not a
    web -- you buy down it in order."""
    node = node_by_id(nodes, node_id)
    if node is None:
        return []
    return [n["id"] for n in nodes
            if n["branch"] == node["branch"] and n["tier"] < node["tier"]]


def total_tree_cost(nodes: list[dict]) -> int:
    return sum(n["cost"] for n in nodes)


def stat_multipliers(nodes: list[dict], bought: list[str]) -> tuple[dict, dict]:
    """(percent bonuses by stat, flat bonuses by stat) for a bought set.

    Percentages are summed, NOT compounded -- see the module docstring.
    """
    percent: dict[str, float] = {}
    flat: dict[str, float] = {}
    for node_id in bought or []:
        node = node_by_id(nodes, node_id)
        if node is None:
            continue
        effect = node["effect"]
        stat = effect["stat"]
        if "percent" in effect:
            percent[stat] = percent.get(stat, 0.0) + float(effect["percent"])
        if "flat" in effect:
            flat[stat] = flat.get(stat, 0.0) + float(effect["flat"])
    return percent, flat
