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
# ----------------------------------------------------------------------
# A CARD'S STARS MATCH ITS ABILITY'S TIER.
#
#     3★ card -> a LEGENDARY ability
#     4★ card -> a MYTHIC ability
#     5★ card -> a DIVINE ability
#
# This was not true at first and it made rarity meaningless: seven of the
# original sixteen cards were mismatched, including 3★ cards carrying
# mythic abilities and 5★ cards carrying mythic ones. A 3★ pull that
# hands over the same class of ability as a 5★ pull is a 5★ pull with a
# worse number printed on it.
#
# The tiers line up exactly -- eight mythic and eight divine card-only
# abilities -- so 4★ and 5★ are fully populated, and the 3★ pool (which
# is 73% of all pulls, and so the one a player actually sees) is backed
# by legendary abilities lifted off gear for the purpose.
#
# tools/check_cards.py asserts the mapping, so a card added at the wrong
# rarity fails loudly instead of quietly devaluing its own tier.
# ----------------------------------------------------------------------
CARD_ABILITY_TIER_BY_STAR: dict[int, str] = {
    3: "legendary", 4: "mythic", 5: "divine",
}

CARD_ONLY_ABILITY_IDS: frozenset[str] = frozenset({
    # --- MYTHIC -> 4-star cards
    "ruin_breaker", "voidpiercer",
    "astral_cascade", "overmind_surge",
    "ascension", "world_ender",
    "arcane_battery", "regen_field_generator",
    # --- DIVINE -> 5-star cards
    "apex_predator", "cataclysms_edge",
    "absolute_zero", "genesis_wellspring",
    "undying_will", "temporal_capacitor",
    "momentum_core", "grand_maestro_score",
    # --- LEGENDARY -> 3-star cards.
    #
    # Ten of the twenty legendary abilities moved up; the other ten stay
    # on gear on purpose. Equipment still needs abilities worth finding,
    # and stripping the whole tier would have left dropped gear as pure
    # stat sticks -- which is the opposite failure to the one this system
    # was built to fix.
    "sunder_the_weak", "phoenix_dive",
    "starfall", "sanctuary_bell", "wellspring_surge", "twin_current",
    "bulwark_protocol", "guard_breaker", "resonance_prism",
    "executioners_ledger",

    # --- CATALOG EXPANSION -------------------------------------------
    # Authored FOR cards rather than lifted off gear, so nothing was
    # taken away from equipment to pay for them. Built on effect kinds
    # the engine already resolves -- see the banner in
    # bot/game/loot/abilities.py for why that matters.
    "tidebreaker_arc", "standing_order", "emberline",       # legendary -> 3★
    "last_ward", "quartermasters_seal",
    "riven_horizon", "chorus_of_thorns",                    # mythic    -> 4★
    "deepwater_cadence", "hollow_reprisal",
    "sovereign_gambit", "the_long_count", "unbroken_line",  # divine    -> 5★
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


# ----------------------------------------------------------------------
# LEVELLING COSTS GOLD AND MATERIALS -- never Cores.
#
# It used to charge Cores every tenth level, on the theory that making
# levelling compete with pulling was an interesting decision. It isn't:
# both sides of that decision are the same currency doing the same job,
# so "level the card I have or roll for one I don't" is just a worse
# version of "roll now or roll later". Worse, it meant a player saving
# for a pull was penalised for using the card they already had.
#
# Materials make it a decision between DIFFERENT things -- the gear you
# are upgrading and the card you are levelling both want the same
# harvester output -- and they plug Cards into the economy the rest of
# the game already runs on.
#
# The material BAND rises with card level, exactly like gear upgrades
# (item_upgrade_service._MATERIAL_BANDS), so an early card is fed wood
# and stone and a level-90 card is eating Void and Entropy.
#
# ...and EVOLUTION FRAGMENTS every 10th level, which is the actual gate.
# Gold and materials are a rate limit -- they slow levelling down but any
# amount of play eventually produces them. A breakthrough is a wall you
# stop at, and the 90 levels of a Card are punctuated by nine of them.
# See bot/game/economy/evolution_config.py.
# ----------------------------------------------------------------------
CARD_LEVEL_GOLD_BASE = 90
CARD_LEVEL_GOLD_EXPONENT = 1.55

CARD_LEVEL_MATERIAL_BASE = 2       # units at level 1
CARD_LEVELS_PER_MATERIAL_STEP = 6  # +1 unit every N levels

# (max_level_inclusive, materials). Same overlapping-bands shape as gear:
# consecutive bands share a material so crossing one is a shift, not a
# wall, and three at once means no single resource gates a card.
CARD_MATERIAL_BANDS: list[tuple[int, tuple[str, ...]]] = [
    (15,  ("wood", "stone")),
    (30,  ("wood", "stone", "metal")),
    (45,  ("stone", "metal", "crystal")),
    (60,  ("metal", "crystal", "xendium")),
    (75,  ("crystal", "xendium", "permafrost_ore")),
    (90,  ("xendium", "permafrost_ore", "void")),
    (999, ("permafrost_ore", "void", "entropy")),
]


def card_materials_for_level(level: int) -> tuple[str, ...]:
    for ceiling, materials in CARD_MATERIAL_BANDS:
        if level <= ceiling:
            return materials
    return CARD_MATERIAL_BANDS[-1][1]


def card_level_cost(level: int, star_rating: int) -> dict[str, int]:
    """Cost to go from `level` to `level + 1`: gold, materials from this
    level's band, and -- every 10th level -- Evolution Fragments.

    `star_rating` is REQUIRED, with no default, on purpose. The obvious
    signature was `star_rating: int = 3`, and every caller that forgot to
    pass it would have quietly priced a 5-star card's breakthroughs at
    the 3-star rate: less than half, with nothing raising and nothing
    looking wrong on screen. This codebase's most expensive recurring bug
    is a value computed two ways; a default argument is the cheapest way
    to write one.
    """
    gold = int(round(CARD_LEVEL_GOLD_BASE * (level ** CARD_LEVEL_GOLD_EXPONENT) / 10))
    cost: dict[str, int] = {"gold": max(CARD_LEVEL_GOLD_BASE, gold)}

    total = CARD_LEVEL_MATERIAL_BASE + max(0, level - 1) // CARD_LEVELS_PER_MATERIAL_STEP
    materials = card_materials_for_level(level)
    per, extra = divmod(total, len(materials))
    for index, material in enumerate(materials):
        amount = per + (1 if index < extra else 0)
        if amount:
            cost[material] = amount

    # Imported here rather than at module scope: evolution_config imports
    # CARD_MAX_LEVEL from this module for its lifetime-cost helper, and a
    # top-level import either way is a cycle.
    from bot.game.economy.evolution_config import card_breakthrough_cost
    fragments = card_breakthrough_cost(level, star_rating)
    if fragments:
        cost["evolution_fragments"] = fragments
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
    # ==================================================================
    # 3-STAR -- legendary abilities, and the pool you actually pull.
    #
    # Ten of them, against four originally. At a 73% 3-star rate a
    # four-card pool means the same face three times in a ten-pull, which
    # reads as the game being small rather than as bad luck. The three
    # tiers are sized against their own rates, not against each other.
    #
    # Stat trios are deliberately varied rather than all attack/defence/
    # HP: a card is supposed to suggest a build, and three cards with the
    # same three stats are one card with three names.
    # ==================================================================
    _card(
        "A Steady Hand On A Bad Day", 3,
        "Somebody's field notes, annotated twice in two different inks. The "
        "second hand is calmer than the first.",
        {"attack": 9, "defense": 6, "max_hp": 40},
        "bulwark_protocol", "armor",
    ),
    _card(
        "The Long Way Round", 3,
        "A route drawn the wrong way across a map, and a note underneath: "
        "*this one everybody survives*.",
        {"speed": 5, "max_hp": 55, "defense": 7},
        "sanctuary_bell", "artifact",
    ),
    _card(
        "Ledger, Balanced At Last", 3,
        "Every column reconciled. The final entry is a name, crossed out, "
        "with the amount left blank.",
        {"attack": 8, "crit_rate": 4, "elemental": 8},
        "executioners_ledger", "armor",
    ),
    _card(
        "Nothing Left To Trade", 3,
        "An empty case, fitted for something specific. Whatever it held is "
        "not coming back.",
        {"elemental": 10, "attack": 7, "recharge": 4},
        "starfall", "artifact",
    ),
    _card(
        "Twelve Hours Of Nothing", 3,
        "A watch log with nothing in it, kept immaculately anyway. Somebody "
        "cared about the hours where nothing happened.",
        {"max_hp": 60, "recharge": 5, "defense": 6},
        "wellspring_surge", "artifact",
    ),
    _card(
        "The Argument In The Stairwell", 3,
        "Two sets of footprints in the dust, facing each other, and a long "
        "gap before either of them moves.",
        {"attack": 10, "crit_damage": 10, "speed": 4},
        "sunder_the_weak", "weapon",
    ),
    _card(
        "Rations For Four, Split Five Ways", 3,
        "The arithmetic is in the margin. It has been done twice and it "
        "does not work either time.",
        {"max_hp": 50, "defense": 8, "max_mana": 20},
        "twin_current", "artifact",
    ),
    _card(
        "Something Left Running", 3,
        "A machine nobody switched off, still doing its one job in a room "
        "that no longer needs it done.",
        {"recharge": 6, "elemental": 9, "speed": 5},
        "resonance_prism", "armor",
    ),
    _card(
        "The Door That Held", 3,
        "Scored, buckled, and shut. Whatever was on the other side did not "
        "get through, and the door is very pleased about it.",
        {"defense": 11, "max_hp": 45, "attack": 6},
        "guard_breaker", "armor",
    ),
    _card(
        "Up, Somehow", 3,
        "A medical chart with an outcome nobody predicted, and a second "
        "signature underneath the first, added later, in relief.",
        {"max_hp": 65, "speed": 6, "crit_rate": 4},
        "phoenix_dive", "weapon",
    ),

    # ==================================================================
    # 4-STAR -- mythic abilities.
    # ==================================================================
    _card(
        "The Balance Of Offense And Defense", 4,
        "A training diagram worn soft at the folds. Both halves are circled. "
        "Neither is labelled correct.",
        {"attack": 12, "defense": 10, "max_hp": 60},
        "arcane_battery", "armor",
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
        "regen_field_generator", "armor",
    ),
    _card(
        "Everything He Keeps An Inventory Of", 4,
        "A list. It is very long, and very neat, and your name has been "
        "added at the bottom in fresh ink.",
        {"attack": 13, "elemental": 13, "crit_damage": 13},
        "world_ender", "ultimate",
    ),
    _card(
        "Somebody Has To", 4,
        "Not addressed to anyone. Left where the next person would find it.",
        {"attack": 11, "defense": 11, "speed": 7},
        "ascension", "ultimate",
    ),
    _card(
        "The Frequency Nobody Assigned", 4,
        "It carries a signal at all hours. Refender has logged it for two "
        "years and refuses to say what she thinks it is.",
        {"elemental": 15, "recharge": 6, "max_mana": 30},
        "astral_cascade", "artifact",
    ),
    _card(
        "Nine Days Of Nothing In That Building", 4,
        "A power draw graph, flat for a week and a half, and then one spike "
        "somebody has circled hard enough to tear the paper.",
        {"elemental": 12, "crit_rate": 7, "attack": 10},
        "overmind_surge", "artifact",
    ),

    # ==================================================================
    # 5-STAR -- divine abilities. The ceiling.
    # ==================================================================
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
        "What The Camera Log Saw", 5,
        "No weapons record. No engagement. Forty minutes of footage of one "
        "person, from a distance, held very steady.",
        {"defense": 18, "max_hp": 95, "crit_rate": 7},
        "undying_will", "armor",
    ),
    _card(
        "The Comma After Good Luck", 5,
        "Rubbed almost out, and still legible if you know to look. Nobody "
        "in the building will tell you whose name it was.",
        {"max_hp": 90, "recharge": 9, "speed": 9},
        "temporal_capacitor", "armor",
    ),

    # ==================================================================
    # THE EXPANSION -- twelve more, five 3★, four 4★, three 5★.
    #
    # Sized against the RATES rather than against each other, same as
    # the original catalog: at a 73% 3-star rate the low tier is what a
    # player actually sees, so it gets the most new faces. Fifteen 3★
    # against ten before means a ten-pull repeats itself noticeably less.
    #
    # Stat trios stay varied on purpose. Three cards sharing one trio is
    # one card with three names, and the point of a bigger catalog is
    # that a pull can surprise you.
    # ==================================================================

    # ---- 3-STAR ------------------------------------------------------
    _card(
        "Everything The Tide Gave Back", 3,
        "An inventory of what washed up, in three different hands. The last "
        "column is what nobody claimed.",
        {"attack": 11, "speed": 5, "crit_rate": 4},
        "tidebreaker_arc", "weapon",
    ),
    _card(
        "Orders Nobody Countermanded", 3,
        "Posted once and never taken down. People still form up under it out "
        "of habit, which is most of what an order is.",
        {"attack": 8, "speed": 6, "max_mana": 24},
        "standing_order", "artifact",
    ),
    _card(
        "The Long Dry Summer", 3,
        "A rainfall log with eleven blank months and a single underlined "
        "entry. Somebody circled the date twice.",
        {"elemental": 11, "crit_damage": 9, "recharge": 4},
        "emberline", "artifact",
    ),
    _card(
        "Held At The Narrow Place", 3,
        "A sketch of a corridor, with the width measured and written in. It "
        "is not very wide. That was the whole plan.",
        {"defense": 10, "max_hp": 55, "speed": 4},
        "last_ward", "armor",
    ),
    _card(
        "Signed For, In Triplicate", 3,
        "Somebody accounted for every last round of it. The requisition is "
        "dated after the battle it was for.",
        {"max_mana": 34, "recharge": 6, "attack": 7},
        "quartermasters_seal", "armor",
    ),

    # ---- 4-STAR ------------------------------------------------------
    _card(
        "The Gap In The Weather", 4,
        "Four hours of clear sky, forecast a week out and hit exactly. "
        "Everything afterward depended on it.",
        {"attack": 15, "crit_damage": 14, "crit_rate": 6},
        "riven_horizon", "weapon",
    ),
    _card(
        "What Grew Over The Wire", 4,
        "The fence is still there under it. You would have to know to look, "
        "and by now almost nobody does.",
        {"defense": 13, "max_hp": 75, "elemental": 9},
        "chorus_of_thorns", "artifact",
    ),
    _card(
        "The Well That Kept Its Level", 4,
        "Measured every morning for nine years by a man who never explained "
        "why. The number does not move.",
        {"max_hp": 85, "recharge": 6, "defense": 10},
        "deepwater_cadence", "artifact",
    ),
    _card(
        "Whoever Swung Second", 4,
        "Two dents in the same plate, and the second one is deeper. The "
        "report records only the first.",
        {"defense": 14, "max_hp": 70, "attack": 11},
        "hollow_reprisal", "armor",
    ),

    # ---- 5-STAR ------------------------------------------------------
    _card(
        "Everything It Cost To Stand There", 5,
        "A field dressing kit, used down to the last of it, and a position "
        "that did not move on any map drawn afterward.",
        {"attack": 19, "max_hp": 80, "crit_damage": 18},
        "sovereign_gambit", "weapon",
    ),
    _card(
        "The Tally Nobody Would Keep", 5,
        "Started in pencil, continued in whatever came to hand. It runs to "
        "four pages and it is still going.",
        {"elemental": 21, "crit_rate": 9, "recharge": 8},
        "the_long_count", "artifact",
    ),
    _card(
        "Nobody Fell Out Of Step", 5,
        "A column photographed at the ninth hour and again at the fourteenth. "
        "The same number of people are in both.",
        {"max_hp": 105, "defense": 17, "speed": 8},
        "unbroken_line", "armor",
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
# 120 CORES A PULL -- the same number as a character pull's Shards.
#
# It was 10, which made a Card pull cost a twelfth of a character pull in
# raw units. Nothing was actually cheaper (the payouts were scaled to
# match) but every number a player saw was in a different order of
# magnitude, so "is 40 cores a lot?" had no answer without doing
# arithmetic against a price they had to go and look up.
#
# Matching the price makes the two currencies directly comparable at a
# glance: 600 of either is five pulls, and a reward paying 240 of both is
# obviously paying the same amount twice. Every core payout in the game
# was multiplied by 12 in the same pass -- see CORE_SOURCES at the
# bottom, which lists them all.
CARD_PULL_COST = 120              # cores per pull
CARD_MULTI_PULL_COUNT = 10
CARD_MULTI_PULL_COST = CARD_PULL_COST * CARD_MULTI_PULL_COUNT

# RATES AND PITY MIRROR THE CHARACTER BANNER EXACTLY.
#
# They did not, at first. Cards had a flat 1% with a hard 70-pull
# ceiling and no soft-pity ramp, while characters ramp from pull 30 --
# so two banners advertised as "the same system" behaved differently in
# the one place a player pays attention. Anyone who learned the rhythm
# of one banner would have been quietly wrong about the other.
#
# Percentages, not fractions, to match character_gacha_config's
# STAR_WEIGHTS -- see pull_service.soft_pity_rate, which both banners
# now share.
CARD_STAR_WEIGHTS: dict[int, float] = {3: 73.0, 4: 22.0, 5: 5.0}
assert abs(sum(CARD_STAR_WEIGHTS.values()) - 100.0) < 1e-9

CARD_FIVE_STAR_HARD_PITY = 50
CARD_FIVE_STAR_SOFT_PITY_START = 30
CARD_FIVE_STAR_SOFT_PITY_STEP = 5.0
CARD_FOUR_STAR_PITY = 10


# ----------------------------------------------------------------------
# WHERE CORES COME FROM
#
# Documentation, not logic -- each system pays them out itself. Kept here
# so the whole economy can be read in one place, because the thing that
# goes wrong with a second currency is that it ends up available
# everywhere (and so meaningless) or nowhere (and so unusable).
#
# EVERY LINE BELOW IS WIRED. An earlier version of this block listed the
# Void Abyss and a core domain that did not exist -- a comment describing
# intent rather than behaviour, which is the most expensive kind to
# leave lying around, because the next person reads it as a survey of
# what happens.
#
#   RECURRING
#     /daily          40 every claim, +300 on the 7-day milestone
#     voting          120 a vote, +4 per streak step, doubled on a
#                     top.gg weekend -- two votes a day is the bulk of
#                     a committed player's income
#     Core Domain     60 (trivial) to 900 (nightmare) per run, the one
#                     place you can go specifically FOR cores
#     Core Reactor    the harvester, ~0.85 pulls a day at max level
#     raids           elite 420, nightmare 1,080 -- endgame tiers only
#     Void Abyss      40 (floor 1) to 450 (floor 12); floors 1-8 pay
#                     once, 9-12 pay once per rotation
#
#   ONE-TIME
#     prologue        600, exactly five pulls, matching the five
#                     character pulls the prologue also pays
#     beginner quests 360 across two quests plus a 600 completion bonus
#     prestige        half the shard payout, so a reset seeds BOTH
#                     banners rather than only the character one
#
# MEASURED against the shard economy at a capped streak:
#
#     cores    475/day  =  4.0 card pulls a day
#     shards   961/day  =  8.0 character pulls a day
#
# Cards deliberately accrue at half the rate. One slot per character, no
# rolls, permanent, and carrying the strongest abilities in the game --
# the same number of pulls on both banners would make Cards the faster
# power curve as well as the higher one.
#
# ----------------------------------------------------------------------
# WHERE CORES GO, besides pulls
# ----------------------------------------------------------------------
# The Echo Exchange buys them back at 4 cores to 1 Echo (see
# resonance_config.CORES_PER_ECHO). That exists because cores bought
# exactly one thing, so a player who had the cards they wanted was
# holding a currency that did nothing -- the same dead end duplicate
# characters were in before Echoes.
#
# The rate is calibrated so that converting everything and buying a
# chosen card costs about what pulling to the 5-star guarantee costs.
# Selling is therefore never the OBVIOUS play, which is the point: if it
# were, the card banner would quietly become a currency-conversion
# screen.
# ----------------------------------------------------------------------
