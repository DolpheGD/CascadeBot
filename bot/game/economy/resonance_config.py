"""
Resonance -- what a duplicate character is FOR.

Pulling someone you already own used to hand over gold and reroll tokens
and nothing else. That's the worst possible outcome in a gacha: the thing
the whole system is built to make you want arrives, and it's a
consolation prize. Duplicates now do two things instead.

  1. The first five copies each raise that character's RESONANCE, making
     them permanently stronger. This is the direct analogue of
     constellations -- the reason to keep pulling on a character you
     already have.
  2. Every copy also pays ECHOES, and copies past Resonance 5 pay
     several times more. Echoes buy any character outright (see
     ECHO_CHARACTER_COST), so a run of duplicates you didn't want is
     still progress toward one you do -- and it's DETERMINISTIC progress,
     which is the thing a gacha otherwise never offers.

WHY THE LEVELS ARE GENERIC RATHER THAN PER-CHARACTER.

Genshin authors five bespoke constellations per character. At 24
characters that's 120 bespoke effects, and the honest version of that is
120 balance problems -- the earlier passive-diversity work is the
evidence for how much care one bespoke effect per character actually
takes. These five levels instead read off the character's OWN kit, so
they land differently on different characters without needing separate
authoring: R1 boosts whichever damage stat that character actually scales
from, R4 scales the numbers in their own skill and ultimate, and R5
shortens their own ultimate's cooldown. An ELE character gets ELE; a
healer's R4 is a bigger heal; a slow-charging unit feels R5 hardest.

The levels also alternate deliberately between STAT and KIT so the
progression doesn't feel like the same upgrade five times.
"""

from __future__ import annotations

MAX_RESONANCE = 5

# Each entry: what the level does, and the machine-readable knobs
# bot/game/combat/factory.py applies. `description` is what the player
# reads -- it must stay in step with the knobs, which
# tools/check_resonance.py verifies.
RESONANCE_LEVELS: list[dict] = [
    {
        "level": 1,
        "name": "First Echo",
        "description": "+12% to your main damage stat (ATK or ELE, whichever your kit scales from).",
        # Applied to whichever of attack/elemental the character's own
        # skill scales from -- see factory._resonance_damage_stat.
        "damage_stat_percent": 12,
    },
    {
        "level": 2,
        "name": "Steady Signal",
        "description": "Your character skill costs 25% less SP.",
        "skill_cost_percent": -25,
    },
    {
        "level": 3,
        "name": "Deep Resonance",
        "description": "+15% max HP and +12% DEF.",
        "max_hp_percent": 15,
        "defense_percent": 12,
    },
    {
        "level": 4,
        "name": "Amplified Pattern",
        "description": (
            "Your skill and ultimate hit 18% harder -- damage, healing, shields, "
            "buffs, debuffs and break power alike."
        ),
        "kit_magnitude_percent": 18,
    },
    {
        "level": 5,
        "name": "Perfect Cascade",
        "description": "Your ultimate's cooldown drops by 1 turn, and +25% Crit Damage.",
        "ultimate_cooldown_reduction": 1,
        "crit_damage_percent": 25,
    },
]


def levels_up_to(resonance: int) -> list[dict]:
    """Every level a character at `resonance` has unlocked. Levels stack:
    an R5 character has all five."""
    return [entry for entry in RESONANCE_LEVELS if entry["level"] <= resonance]


def bonus_total(resonance: int, key: str) -> float:
    """Summed value of `key` across every unlocked level. Returns 0 for a
    key no level grants, so callers can ask unconditionally."""
    return sum(entry.get(key, 0) for entry in levels_up_to(resonance))


def resonance_for(dupe_count: int) -> int:
    """Resonance level from a PlayerCharacter's dupe_count.

    DERIVED rather than stored, which matters for two reasons: existing
    players who already pulled duplicates get the resonance they earned
    the moment this ships, with no backfill migration; and the two numbers
    can never disagree, which a second column would eventually allow.

    dupe_count is 1 for the first copy -- that copy is the character, not
    a duplicate -- so resonance is one less, capped."""
    return max(0, min(MAX_RESONANCE, dupe_count - 1))


def is_maxed(dupe_count: int) -> bool:
    return resonance_for(dupe_count) >= MAX_RESONANCE


# ----------------------------------------------------------------------
# ECHOES -- the duplicate currency.
#
# Every duplicate pays; a duplicate past Resonance 5 pays the OVERFLOW
# rate instead, because at that point the copy does nothing else at all
# and would otherwise be the same dead pull this system exists to remove.
#
# Calibration, for whoever retunes this: 50 pulls (7,500 shards) is the
# 5-star hard pity, and over that many pulls a player with a reasonable
# roster banks very roughly 1,000-1,400 echoes from duplicates at these
# rates. So the echo path to a CHOSEN 5-star costs about what the gacha's
# guarantee costs for a RANDOM one. That's the intended trade: slower in
# expectation, but you pick.
# ----------------------------------------------------------------------
ECHOES_BY_STAR: dict[int, int] = {3: 20, 4: 50, 5: 120}
ECHOES_BY_STAR_MAXED: dict[int, int] = {3: 50, 4: 130, 5: 300}

ECHO_CHARACTER_COST: dict[int, int] = {3: 250, 4: 600, 5: 1500}


def echoes_for_dupe(star_rating: int, dupe_count: int) -> int:
    """What one duplicate pays. `dupe_count` is the count AFTER the pull,
    so the copy that takes a character to Resonance 5 still pays the
    normal rate, and the next one pays overflow."""
    table = ECHOES_BY_STAR_MAXED if is_maxed(dupe_count) else ECHOES_BY_STAR
    return table.get(star_rating, table[3])


def character_cost(star_rating: int) -> int:
    return ECHO_CHARACTER_COST.get(star_rating, ECHO_CHARACTER_COST[3])
