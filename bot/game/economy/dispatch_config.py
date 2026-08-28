"""
The Dispatch Board: send characters you AREN'T fighting with on timed jobs.

WHY THIS EXISTS. Everything else in the base is a clock or a wallet --
harvesters convert time into currency, research converts time and
materials into modifiers, the shop converts one resource into another.
None of them care that you own 30 characters, and none of them give a
character you never field anything to do. A collection game where two
thirds of the collection is inert is a collection game with a hole in it.

Dispatch is the one base system whose input is the ROSTER. That single
change is what makes it a new mechanic rather than a ninth harvester.

THE DECISION IT CREATES. Assigned characters are LOCKED OUT OF COMBAT
until the contract returns. So the question is never "do I want free
stuff" -- it is "which four characters can I afford to lose for six
hours", and that question only gets interesting if you have depth to
spend. Breadth is the stat being rewarded, deliberately: it is the one
form of progress the rest of the game never paid for.

WHY IT CANNOT REPLACE PLAYING. Three separate ceilings, because an idle
system that out-earns the active game quietly deletes the active game:

  * rewards are per-contract and the board holds a fixed number of slots
  * contracts pay materials, gold and XP -- never shards, cores or
    characters, so the gacha is untouched
  * the best characters are the ones you most want in your squad, so
    every good dispatch costs you a real fight

WHY REQUIREMENTS ARE CLASS-SHAPED RATHER THAN POWER-SHAPED. A contract
that just wanted "high level" would be satisfied by the same four
characters every time, and the board would become a checklist. Asking
for a Sustain and two Support DPS means a wide roster finishes more
contracts than a strong narrow one -- which is the entire point.
"""

from __future__ import annotations

from bot.database.models.enums import CharacterClass

# ---------------------------------------------------------------------
# Board size. Slots come from the HQ, so dispatch grows with the base
# rather than being handed over complete.
# ---------------------------------------------------------------------
DISPATCH_UNLOCK_HQ_LEVEL = 3

# HQ level -> how many contracts may run at once. Capped at 4 because
# each running contract locks characters away, and a board that can hold
# six of them at 20 characters owned would make the squad screen a
# leftovers screen.
SLOTS_BY_HQ_LEVEL = {3: 1, 4: 2, 6: 3, 8: 4}

MAX_SLOTS = max(SLOTS_BY_HQ_LEVEL.values())

# How many contracts the board offers to choose from. More than the
# slots, so there is always something to turn down.
BOARD_SIZE = 5

# The board rerolls on this cadence. Long enough that the choice matters,
# short enough that a bad board is not a lost day.
BOARD_REFRESH_HOURS = 8


def slots_for_hq(hq_level: int) -> int:
    """Slots unlocked at this HQ level. Below the unlock, zero."""
    earned = [slots for level, slots in SLOTS_BY_HQ_LEVEL.items()
              if hq_level >= level]
    return max(earned) if earned else 0


# ---------------------------------------------------------------------
# Reward scaling
# ---------------------------------------------------------------------
#
# A contract's payout is its base reward multiplied by how well the team
# fits. Fit is the only lever the player has after choosing the contract,
# so it has to be worth optimising without being worth agonising over --
# hence a range of 0.6x to 1.6x rather than something explosive.

MIN_FIT_MULTIPLIER = 0.60
MAX_FIT_MULTIPLIER = 1.60

# Each satisfied class requirement is worth this much fit.
CLASS_MATCH_BONUS = 0.18

# Average star rating above 3 adds a little, below 3 removes a little.
# Small on purpose: this is the term that would otherwise make dispatch a
# pure "send your best" button, which is the thing class requirements
# exist to prevent.
STAR_WEIGHT = 0.06

# Average level, measured against the level the contract is written for.
LEVEL_WEIGHT = 0.35


def fit_multiplier(contract: dict, members: list) -> float:
    """How well this team suits this contract, as a payout multiplier.

    `members` are PlayerCharacter rows. Reads level, star rating and
    class -- never equipment or combat power, because dispatch is not a
    fight and pretending otherwise would just make it a second squad
    screen with worse feedback.
    """
    if not members:
        return MIN_FIT_MULTIPLIER

    fit = 1.0

    # ---- class requirements -----------------------------------------
    #
    # Counted as a MULTISET. A contract asking for two Support DPS is not
    # satisfied by one Support DPS twice over, and an earlier version
    # that used sets said it was.
    wanted = list(contract.get("prefers", []))
    available = [m.template.character_class for m in members]
    for want in wanted:
        if want in available:
            available.remove(want)
            fit += CLASS_MATCH_BONUS

    # ---- star rating -------------------------------------------------
    stars = sum(int(m.template.star_rating or 3) for m in members) / len(members)
    fit += (stars - 3.0) * STAR_WEIGHT

    # ---- level against the contract's intended level ------------------
    target = max(1, int(contract.get("level", 20)))
    levels = sum(max(1, int(m.level or 1)) for m in members) / len(members)
    fit += (min(levels / target, 1.5) - 1.0) * LEVEL_WEIGHT

    return max(MIN_FIT_MULTIPLIER, min(MAX_FIT_MULTIPLIER, fit))


# ---------------------------------------------------------------------
# The contracts
# ---------------------------------------------------------------------
#
# Every one names a place or a job from the world rather than being
# "Gather Wood II", because the board is read far more often than it is
# optimised and a list of tiers is a list nobody reads.
#
# `party` is how many characters it takes. `hours` is how long they are
# gone. `level` is the level the payout is balanced around. `prefers` is
# the class multiset that pays the fit bonus.
#
# SHAPE OF THE SET, deliberately mixed so the board is a choice:
#   * short cheap jobs for a thin roster (1-2 characters, 2-4 hours)
#   * long expensive jobs that lock four characters overnight
#   * a few that want an AWKWARD class mix, so breadth beats power
#   * material-focused, gold-focused and XP-focused, so what you need
#     changes which contract is best rather than one always winning
#
# ---------------------------------------------------------------------
# HOW THE PAYOUTS WERE SET, because the first pass was wildly wrong.
# ---------------------------------------------------------------------
#
# Written by feel first, then measured, and the measurement was ugly:
# the board's theoretical ceiling came to 147,200 gold a day. That is
# more than the ENTIRE forge upgrade path (118,000) in a single day, and
# roughly 60x a fully-levelled Gold Mine harvester at 2,400/day. An idle
# system paying that much does not supplement the game, it replaces it.
#
# The anchor is TOTAL VALUE PER CHARACTER-HOUR -- party size times
# duration, against gold plus materials priced at hq_config's
# MATERIAL_GOLD_VALUE plus XP at half a gold each.
#
# BANDING ON GOLD ALONE WAS THE SECOND MISTAKE, and it was worse than it
# looked. It flagged the four material-heavy contracts as underpaid
# while being structurally blind to the thing that actually needed
# watching: Deep Core Dig's gold was a quiet 50/char-hour, and its
# materials were worth 9,440 gold on top. A rule that cannot see 80% of
# a contract's value is not a budget, it is a decoration.
#
# Measured properly the set ran 144 to 410, and the richest contracts
# were the SHORT ones -- Timber Run paid 410 per character-hour because
# 210 wood is worth more than it reads. Levelled to 200-285, a 1.4x
# spread, so no contract is strictly better than another and the choice
# stays about what you need rather than which one is secretly best.
#
# That puts the theoretical ceiling at 64,000/day, and the REALISTIC
# figure far below it -- claiming every slot the moment it lands, with
# 16 characters spare, on a board that only offers five random contracts.
# In practice it lands around 10-15k/day, which is several harvesters'
# worth (fair: it costs you your roster) and about ten days to fund the
# forge path (fair: it should not be the fast route).
#
# tools/check_dispatch.py asserts the band and the daily ceiling, so this
# cannot drift back by adding one generous contract later.

CONTRACTS: list[dict] = [
    # ---- short, thin-roster friendly ---------------------------------
    {
        "id": "timber_run",
        "name": "Timber Run",
        "description": "The mill south of town is behind on its quota and paying "
                       "for hands. Unglamorous, close, and back before dark.",
        "party": 1, "hours": 2, "level": 10,
        "prefers": [],
        "rewards": {"wood": 130, "gold": 170},
    },
    {
        "id": "quarry_shift",
        "name": "Quarry Shift",
        "description": "Cutting stone on the north face. The foreman does not ask "
                       "questions and does not give references.",
        "party": 1, "hours": 3, "level": 12,
        "prefers": [],
        "rewards": {"stone": 190, "gold": 270},
    },
    {
        "id": "courier_route",
        "name": "Courier Route",
        "description": "Six sealed packages, four districts, one afternoon. "
                       "Whoever goes should be quick and incurious.",
        "party": 1, "hours": 2, "level": 14,
        "prefers": [CharacterClass.DPS],
        "rewards": {"gold": 430},
    },
    {
        "id": "clinic_rotation",
        "name": "Clinic Rotation",
        "description": "The free clinic in the lower ward is short-staffed again. "
                       "Someone who can keep people alive would be useful.",
        "party": 2, "hours": 4, "level": 16,
        "prefers": [CharacterClass.SUSTAIN],
        "rewards": {"gold": 950, "xp": 1_300},
    },

    # ---- mid, awkward class mixes ------------------------------------
    {
        "id": "survey_the_shelf",
        "name": "Survey The Shelf",
        "description": "Map the ice shelf before the season closes it. Wants "
                       "somebody who reads terrain and somebody who can carry them "
                       "out if it goes wrong.",
        "party": 2, "hours": 6, "level": 24,
        "prefers": [CharacterClass.AMPLIFIER, CharacterClass.SUSTAIN],
        "rewards": {"stone": 260, "metal": 110, "gold": 1_000},
    },
    {
        "id": "escort_the_assessor",
        "name": "Escort The Assessor",
        "description": "An insurance assessor needs to reach three sites and come "
                       "back with all her fingers. Bring people who can discourage "
                       "trouble without starting it.",
        "party": 3, "hours": 6, "level": 28,
        "prefers": [CharacterClass.SUPPORT_DPS, CharacterClass.SUPPORT_DPS,
                    CharacterClass.SUSTAIN],
        "rewards": {"gold": 1_500, "metal": 140, "xp": 1_800},
    },
    {
        "id": "salvage_the_relay",
        "name": "Salvage The Relay",
        "description": "A comms relay went dark eleven months ago. Whatever is "
                       "still bolted to it is worth more than the relay was.",
        "party": 3, "hours": 8, "level": 32,
        "prefers": [CharacterClass.AMPLIFIER, CharacterClass.DPS],
        "rewards": {"metal": 210, "crystal": 120, "gold": 1_300},
    },
    {
        "id": "night_market_security",
        "name": "Night Market Security",
        "description": "The market runs from dusk to dawn and the stallholders have "
                       "pooled a purse. Long, dull, occasionally violent.",
        "party": 3, "hours": 8, "level": 30,
        "prefers": [CharacterClass.DPS, CharacterClass.SUSTAIN],
        "rewards": {"gold": 3_400, "xp": 2_800},
    },
    {
        "id": "tutor_the_intake",
        "name": "Tutor The Intake",
        "description": "A dozen new recruits and nobody to drill them. Whoever goes "
                       "will learn as much as they teach.",
        "party": 2, "hours": 6, "level": 26,
        "prefers": [CharacterClass.SUPPORT_DPS],
        "rewards": {"xp": 4_200, "gold": 500},
    },

    # ---- long, expensive, four characters gone overnight --------------
    {
        "id": "deep_core_dig",
        "name": "Deep Core Dig",
        "description": "Twelve hours below the frost line. The seam is rich and the "
                       "air is not. Send people who can take a shift each.",
        "party": 4, "hours": 12, "level": 40,
        "prefers": [CharacterClass.SUSTAIN, CharacterClass.SUSTAIN],
        "rewards": {"crystal": 250, "xendium": 95, "metal": 280, "gold": 2_400},
    },
    {
        "id": "the_long_convoy",
        "name": "The Long Convoy",
        "description": "Four regions, no relief, and a cargo manifest nobody will "
                       "read aloud. Pays accordingly.",
        "party": 4, "hours": 12, "level": 44,
        "prefers": [CharacterClass.DPS, CharacterClass.AMPLIFIER,
                    CharacterClass.SUSTAIN, CharacterClass.SUPPORT_DPS],
        "rewards": {"gold": 5_000, "xendium": 85, "xp": 4_800},
    },
    {
        "id": "permafrost_prospect",
        "name": "Permafrost Prospect",
        "description": "The old prospectors' charts are wrong, which is why the ore "
                       "is still there. Ten hours of being wrong carefully.",
        "party": 3, "hours": 10, "level": 42,
        "prefers": [CharacterClass.AMPLIFIER, CharacterClass.AMPLIFIER],
        "rewards": {"permafrost_ore": 110, "crystal": 200, "gold": 2_000},
    },
    {
        "id": "the_quiet_archive",
        "name": "The Quiet Archive",
        "description": "Catalogue what the Lab could not. Nothing in there is "
                       "dangerous. That is what the last team reported.",
        "party": 4, "hours": 14, "level": 48,
        "prefers": [CharacterClass.AMPLIFIER, CharacterClass.SUPPORT_DPS,
                    CharacterClass.SUSTAIN],
        "rewards": {"void": 42, "xendium": 110, "gold": 3_200, "xp": 6_000},
    },
    {
        "id": "hold_the_line",
        "name": "Hold The Line",
        "description": "A relief garrison, sixteen hours, at the edge of somewhere "
                       "that keeps getting closer. Bring everyone you can spare.",
        "party": 4, "hours": 16, "level": 52,
        "prefers": [CharacterClass.DPS, CharacterClass.DPS,
                    CharacterClass.SUSTAIN, CharacterClass.SUSTAIN],
        "rewards": {"gold": 6_200, "entropy": 36, "permafrost_ore": 95, "xp": 7_500},
    },
]

CONTRACTS_BY_ID = {c["id"]: c for c in CONTRACTS}

# Currencies a contract is allowed to pay. Enforced by
# tools/check_dispatch.py rather than trusted, because the whole argument
# that dispatch cannot replace playing rests on this list -- one shard
# reward slipped in later would quietly turn the board into a gacha.
PAYABLE = {"gold", "xp", "wood", "stone", "metal", "crystal",
           "xendium", "permafrost_ore", "void", "entropy"}


def contract(contract_id: str) -> dict | None:
    return CONTRACTS_BY_ID.get(contract_id)


def available_contracts(hq_level: int) -> list[dict]:
    """Contracts whose party size the HQ can actually staff.

    Filtered by SLOTS rather than by level so the board never advertises
    a job the player cannot take -- a board that is mostly greyed out
    reads as a paywall, not as progression.
    """
    return [c for c in CONTRACTS if c["party"] <= max(1, slots_for_hq(hq_level) + 2)]
