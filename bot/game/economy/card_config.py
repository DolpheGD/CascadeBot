"""
Character Cards: the catalog, the level curve, and the banner.

----------------------------------------------------------------------
WHAT A CARD IS, AND WHY IT ISN'T EQUIPMENT
----------------------------------------------------------------------
One slot per character, filled by at most one Card, browsed through
`/cards` rather than `/inventory`. Three main stats and one powerful
ability, levellable to 100.

The separation from equipment is the whole point, so it's worth being
explicit about what each is now FOR:

  * EQUIPMENT is horizontal and plentiful. Six slots per character, rolled
    substats, constant churn, and -- after this pass -- abilities that are
    useful rather than decisive. You are always finding some.
  * A CARD is vertical and scarce. One per character, no rolls, and it
    carries an ability strong enough to define how that character plays.
    You are choosing which character deserves it.

That distinction was made real by MOVING the sixteen strongest abilities
off gear entirely (see CARD_ABILITY_MIGRATION below). Before, a lucky
Divine drop could hand a new player Cataclysm's Edge on a weapon whose
stats they'd outgrow in a week -- the best ability in the game attached
to the most disposable object in it. Those abilities now only exist on
Cards, and the equipment pools keep the ones that are good without being
the reason you win.

----------------------------------------------------------------------
WHY A SECOND CURRENCY
----------------------------------------------------------------------
Cards are pulled with CORES, not Shards. One currency across two banners
means every Card pull is a character pull you didn't make, so the banners
cannibalise each other and the player's only real decision is which one
to feel worse about skipping. Two pools make them two separate hobbies.

Sources deliberately overlap in places and diverge in others -- see
CORE_SOURCES at the bottom -- so a player who lives in raids and a player
who lives in the story end up with differently-shaped stashes rather than
the same stash at different sizes.
"""

from __future__ import annotations

# ----------------------------------------------------------------------
# ABILITIES MOVED OFF EQUIPMENT
#
# Every ability that was gated to mythic/divine is now Card-only. That
# was the natural line to draw: those were already the abilities the
# rarity system was trying to make rare, and it was doing it by making
# them a lottery on top of a lottery.
#
# bot/game/loot/abilities.py keeps the entries (Cards reference them by
# id) but they are excluded from gear rolls -- see
# abilities.abilities_for_rarity.
# ----------------------------------------------------------------------
CARD_ONLY_ABILITY_IDS: frozenset[str] = frozenset({
    # weapon skills
    "ruin_breaker", "voidpiercer", "apex_predator", "cataclysms_edge",
    # artifact skills
    "astral_cascade", "overmind_surge", "absolute_zero", "genesis_wellspring",
    # ultimates
    "ascension", "world_ender",
    # armor passives
    "arcane_battery", "undying_will", "regen_field_generator",
    "temporal_capacitor", "momentum_core", "grand_maestro_score",
})


# ----------------------------------------------------------------------
# THE LEVEL CURVE
#
# 1 to 100, and deliberately a long road. A Card is the one piece of
# power a character keeps forever, so it should be the thing you are
# still working on when everything else is finished.
#
# Stats scale the same shape gear now does (see
# stat_pools.main_stat_level_multiplier): weak at 1, several times that
# at 100, back-loaded so the late levels are the ones worth chasing.
# ----------------------------------------------------------------------
CARD_MAX_LEVEL = 100
CARD_LEVEL_1_MULTIPLIER = 0.40
CARD_TOP_MULTIPLIER = 4.0
CARD_CURVE_EXPONENT = 1.35


def card_level_multiplier(level: int) -> float:
    """How much of its printed stats a Card of this level carries."""
    level = max(1, min(level, CARD_MAX_LEVEL))
    progress = ((level - 1) / (CARD_MAX_LEVEL - 1)) ** CARD_CURVE_EXPONENT
    return CARD_LEVEL_1_MULTIPLIER + (
        CARD_TOP_MULTIPLIER - CARD_LEVEL_1_MULTIPLIER
    ) * progress


# XP-style levelling would need a second progression currency nobody
# asked for, so Cards level with GOLD and CORES: gold makes it a sink,
# cores make it compete with pulling, which is the interesting decision.
#
# Measured, taking one card from 1 to each milestone:
#
#     Lv 10        1,295 gold      10 cores
#     Lv 25       12,501 gold      20 cores
#     Lv 50       74,143 gold      50 cores
#     Lv100      438,870 gold     100 cores
#
# Two numbers worth defending there. 439k gold is roughly 35 maxed
# Legendary gear pieces, which is what "a big grind" has to mean for the
# one item a character keeps forever. And 100 cores is EXACTLY one
# ten-pull -- so maxing a card you have costs the same as rolling for a
# card you don't, which is the decision this is supposed to create.
#
# The core charge was 2 per step in the first pass, totalling 20 over
# the whole climb. That was a rounding error against a 100-core pull and
# made the comment above simply untrue: nothing competed with anything.
CARD_LEVEL_GOLD_BASE = 90
CARD_LEVEL_GOLD_EXPONENT = 1.55
CARD_LEVEL_CORE_EVERY = 10        # cores are charged every Nth level
CARD_LEVEL_CORE_AMOUNT = 10


def card_level_cost(level: int) -> dict[str, int]:
    """Cost to go from `level` to `level + 1`."""
    gold = int(round(CARD_LEVEL_GOLD_BASE * (level ** CARD_LEVEL_GOLD_EXPONENT) / 10))
    cost = {"gold": max(CARD_LEVEL_GOLD_BASE, gold)}
    if (level + 1) % CARD_LEVEL_CORE_EVERY == 0:
        cost["cores"] = CARD_LEVEL_CORE_AMOUNT
    return cost


# ----------------------------------------------------------------------
# STAR RATINGS
#
# 3-5, matching characters so the pull result reads the same way. The
# multiplier is applied to every stat on the card.
# ----------------------------------------------------------------------
CARD_STAR_MULTIPLIER: dict[int, float] = {3: 1.0, 4: 1.45, 5: 2.1}


def _card(name, star, lore, stats, ability_id, ability_pool):
    return {
        "id": name.lower().replace(" ", "_").replace("'", "").replace(",", ""),
        "name": name,
        "star_rating": star,
        "lore": lore,
        # Three main stats, always. A card with one big number is a stat
        # stick; three is a build direction.
        "stats": stats,
        "ability_id": ability_id,
        "ability_pool": ability_pool,
    }


# ----------------------------------------------------------------------
# THE CATALOG
#
# Named as objects and moments rather than as equipment. A card is
# supposed to read like something recovered, not something bought --
# which is also why every one of them is a phrase rather than a noun.
# ----------------------------------------------------------------------
CARD_TEMPLATES: list[dict] = [
    # --- 3-star: the ones you will actually see -----------------------
    _card(
        "A Steady Hand On A Bad Day", 3,
        "Somebody's field notes, annotated twice in two different inks. The "
        "second hand is calmer than the first.",
        {"attack": 9, "defense": 6, "max_hp": 40},
        "regen_field_generator", "armor",
    ),
    _card(
        "The Long Way Round", 3,
        "A route drawn the wrong way across a map, and a note underneath: "
        "*this one everybody survives*.",
        {"speed": 5, "max_hp": 55, "defense": 7},
        "arcane_battery", "armor",
    ),
    _card(
        "Ledger, Balanced At Last", 3,
        "Every column reconciled. The final entry is a name, crossed out, "
        "with the amount left blank.",
        {"attack": 8, "crit_rate": 4, "elemental": 8},
        "astral_cascade", "artifact",
    ),
    _card(
        "Nothing Left To Trade", 3,
        "An empty case, fitted for something specific. Whatever it held is "
        "not coming back.",
        {"elemental": 10, "attack": 7, "recharge": 4},
        "overmind_surge", "artifact",
    ),

    # --- 4-star ------------------------------------------------------
    _card(
        "The Balance Of Offense And Defense", 4,
        "A training diagram worn soft at the folds. Both halves are circled. "
        "Neither is labelled correct.",
        {"attack": 12, "defense": 10, "max_hp": 60},
        "undying_will", "armor",
    ),
    _card(
        "Ship Sailing Into The Void", 4,
        "A hull with no wake behind it. Painted by someone who watched it go "
        "and kept watching after there was nothing to see.",
        {"elemental": 14, "crit_damage": 12, "speed": 5},
        "voidpiercer", "weapon",
    ),
    _card(
        "A Blighted Figure", 4,
        "Photographed at distance, badly. It is standing in a yard. It has "
        "been standing there for some time.",
        {"attack": 14, "crit_rate": 6, "defense": 8},
        "ruin_breaker", "weapon",
    ),
    _card(
        "Good Luck, In Marker", 4,
        "Two words on the inside of a door, and a comma after them where a "
        "name used to be.",
        {"max_hp": 80, "defense": 12, "recharge": 5},
        "temporal_capacitor", "armor",
    ),

    # --- 5-star: the ceiling -----------------------------------------
    _card(
        "Memories Of Rex", 5,
        "Not a photograph. Somebody sat down and drew him from memory, "
        "carefully, more than once, getting the jaw wrong every time.",
        {"attack": 20, "crit_damage": 20, "max_hp": 70},
        "apex_predator", "weapon",
    ),
    _card(
        "The Hour The Lab Came Down", 5,
        "A timestamp, a floor plan, and one route out marked in a hand that "
        "was shaking.",
        {"elemental": 22, "speed": 8, "crit_rate": 8},
        "cataclysms_edge", "weapon",
    ),
    _card(
        "Everything He Keeps An Inventory Of", 5,
        "A list. It is very long, and very neat, and your name has been "
        "added at the bottom in fresh ink.",
        {"attack": 18, "elemental": 18, "crit_damage": 18},
        "world_ender", "ultimate",
    ),
    _card(
        "The Pot That Is Never Empty", 5,
        "Nobody has seen it filled. Everybody has eaten from it. Both of "
        "these things are true and only one of them is comforting.",
        {"max_hp": 110, "defense": 16, "recharge": 7},
        "genesis_wellspring", "artifact",
    ),
    _card(
        "The Winter That Did Not Break", 5,
        "A season recorded in one long unbroken line, and a marginal note in "
        "the same hand every month: *still here*.",
        {"elemental": 20, "defense": 15, "max_hp": 85},
        "absolute_zero", "artifact",
    ),
    _card(
        "Every Name In The Chorus", 5,
        "A score for more voices than the room could hold. Somebody has "
        "pencilled in the missing parts anyway.",
        {"attack": 15, "speed": 10, "recharge": 8},
        "grand_maestro_score", "armor",
    ),
    _card(
        "The Long Run Home", 5,
        "Distance, time, and a note underneath in a different pen: *faster "
        "than last time, and it still was not enough*.",
        {"speed": 12, "attack": 16, "crit_rate": 9},
        "momentum_core", "armor",
    ),
    _card(
        "Somebody Has To", 5,
        "Not addressed to anyone. Left where the next person would find it.",
        {"attack": 16, "defense": 14, "speed": 9},
        "ascension", "ultimate",
    ),
]


def get_card(card_id: str) -> dict | None:
    return next((c for c in CARD_TEMPLATES if c["id"] == card_id), None)


def cards_of_star(star: int) -> list[dict]:
    return [c for c in CARD_TEMPLATES if c["star_rating"] == star]


# ----------------------------------------------------------------------
# THE BANNER
#
# Rates and pity mirror the character gacha's shape so the two read the
# same, but they run on their OWN counters (Player.card_pity_*) -- a pull
# on one banner must never advance a guarantee on the other.
# ----------------------------------------------------------------------
CARD_PULL_COST = 10               # cores per pull
CARD_MULTI_PULL_COUNT = 10
CARD_MULTI_PULL_COST = CARD_PULL_COST * CARD_MULTI_PULL_COUNT

CARD_RATE_FIVE_STAR = 0.010
CARD_RATE_FOUR_STAR = 0.075
CARD_PITY_FIVE_STAR = 70          # guaranteed 5-star by this pull
CARD_PITY_FOUR_STAR = 10          # guaranteed 4-star-or-better by this pull


# ----------------------------------------------------------------------
# WHERE CORES COME FROM
#
# Documentation, not logic -- each system pays them out itself. Kept here
# so the whole economy can be read in one place, because the thing that
# goes wrong with a second currency is that it ends up available
# everywhere (and so meaningless) or nowhere (and so unusable).
#
# OVERLAPPING with shards -- big, infrequent milestones pay both:
#     story mission rewards        prologue and chapter finales
#     beginner quest completion    the one-time bonus
#     raid rewards                 elite and nightmare tiers only
#
# CORE-ONLY -- so there is content whose whole point is Cards:
#     the Void Abyss               deep floors
#     domains                      a dedicated core domain
#     daily streak milestones      every 7th day
#
# SHARD-ONLY -- so characters keep sources Cards can't touch:
#     voting, the Echo Exchange, ordinary raid tiers
# ----------------------------------------------------------------------
