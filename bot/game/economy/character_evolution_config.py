"""
Character evolution -- taking a 3-star or 4-star up the star ladder.

WHAT THIS IS FOR. Most of the roster is 3s and 4s (10 and 16 of them
against 9 fives), and past the midgame every one of them is strictly
worse than a 5-star you already own. Evolution gives the character you
actually like a path forward instead of a retirement date.

WHAT IT IS NOT FOR, and this is the whole balance question: it does not
make a 3-star into the 5-star you failed to pull. A native 5-star has to
stay the strongest thing a player owns, or the gacha it comes from stops
meaning anything -- and this is a game whose entire acquisition loop is
that gacha.

THE NUMBERS, MEASURED RATHER THAN CHOSEN.

At level 90 a native 5-star leads on attack by 36.2% over a 3-star and
15.3% over a 4-star. Each evolution stage grants +6% to the stats that
grow with level, which closes about a THIRD of that gap:

    evolved 3-star (2 stages)   21.2% below a native 5-star
    evolved 4-star (1 stage)     8.8% below a native 5-star

Worth being precise about, because "a third of the gap" and "a third of
the way to parity" sound alike and are not: closing a third of a 36% gap
still leaves a 3-star more than a fifth behind. That is the intent. The
evolved character is a real upgrade over what it was and is never
mistaken for the real thing.

THE LADDER HOLDS AT EVERY RANK, not just at the top. A 3-star evolved to
4 sits ~10% below a NATIVE 4-star, exactly as it sits below a native 5
after the second stage. Evolution never lets a character overtake one
that was born at the rank it just reached, so the original rarity of
everything in the roster still means something.

WHY +6% PER STAGE, COMPOUNDING. Stages compound (1.06 x 1.06 = +12.4%)
rather than adding to +12%, so the second stage is worth slightly more
than the first in absolute terms -- which matches its much higher cost.
The difference is small enough not to matter for balance and large
enough that the expensive stage does not feel like the cheap one.

PRICING IS ANCHORED TO REAL SINKS, not invented:

    a native 5-star at the Echo exchange     1,500 echoes
    levelling one item to 50                ~72,000 gold
    fully breaking through one divine item   ~1,584 fragments

A full 3-star to 5-star run costs 700 echoes -- deliberately LESS than
the 1,500 that buys a real 5-star outright, because what you get is
weaker than a real 5-star. Paying more for the inferior result would be
a trap, and a player who worked that out afterwards would be right to be
annoyed.
"""

from __future__ import annotations

# The highest star an evolution can reach. Nothing evolves past 5 because
# the stat baselines, the gacha tables, the Echo prices and the card
# system all stop there -- a 6-star would be a new column in five places.
MAX_STAR = 5

# Percent added to every stat that grows with level, per stage. Applied
# in factory.base_character_stats, PRE-GEAR, for the same reason talents
# are: percent substats on gear are computed against that block, and a
# bonus applied after it would be invisible to them and to every
# simulation the difficulty ladder is tuned against.
PERCENT_PER_STAGE = 6.0

# Which stats it touches: the six that grow with level.
#
# crit_rate, crit_damage and recharge are deliberately excluded, matching
# the levelling spec's rule that those three are gear's job to move. An
# evolution that raised crit would also be worth wildly different amounts
# to different classes, since crit damage on a Sustain is close to dead
# weight -- a flat boost to the growing six is worth roughly the same to
# everybody, which is what a rarity upgrade should be.
EVOLVED_STATS = ("attack", "defense", "elemental", "speed", "max_hp", "max_mana")

# Requirements to reach each star. Keyed by the star being reached.
#
# The level gates are the real gate; the currencies are the cost. A
# player cannot rush a favourite to 5 in an afternoon because levelling
# to 70 is itself the long part, and that is intentional -- evolution is
# meant to reward a character you have actually been playing, not one you
# decided to like this morning.
REQUIREMENTS: dict[int, dict] = {
    4: {
        "level": 40,
        "cost": {"echoes": 200, "gold": 80_000, "evolution_fragments": 250},
    },
    5: {
        "level": 70,
        "cost": {"echoes": 500, "gold": 220_000, "evolution_fragments": 600},
    },
}


def requirement_for(target_star: int) -> dict | None:
    """What it takes to reach `target_star`, or None if unreachable."""
    return REQUIREMENTS.get(target_star)


def stage_percent(stages: int) -> float:
    """Total percent bonus from `stages` evolutions, compounded.

    Returned as a percentage (12.36 for two stages), not a multiplier,
    because that is the shape base_character_stats and the talent bonuses
    already speak in.
    """
    if stages <= 0:
        return 0.0
    return ((1 + PERCENT_PER_STAGE / 100) ** stages - 1) * 100


def max_stages_for(native_star: int) -> int:
    """How many times a character born at `native_star` can evolve."""
    return max(0, MAX_STAR - native_star)
