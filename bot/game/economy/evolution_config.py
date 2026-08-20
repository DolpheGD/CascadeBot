"""
Evolution Fragments: the breakthrough material for gear and Cards.

----------------------------------------------------------------------
WHAT A BREAKTHROUGH IS
----------------------------------------------------------------------
Gear cannot pass a level divisible by 5. A Card cannot pass a level
divisible by 10. Crossing one costs Evolution Fragments on top of the
ordinary gold and materials.

    gear    5 -> 6, 10 -> 11, 15 -> 16, 20 -> 21, 25 -> 26, 30 -> 31
    cards   10 -> 11, 20 -> 21, ... 90 -> 91

Levelling ran on gold and materials alone, which every system in the
game already pays out -- so the only thing gating a maxed item was time
spent doing anything at all. A breakthrough is a checkpoint you go and
earn on purpose, and it is what makes "level 25" a different sentence
from "level 24".

----------------------------------------------------------------------
WHY THE GEAR BOUNDARIES LAND WHERE THEY DO
----------------------------------------------------------------------
Every rarity's level cap is already a multiple of 5 (rarity_config's
UPGRADE_LEVEL_CAP: Common 5, Uncommon 10, ... Divine 35). So the
breakthroughs line up with the caps exactly, and the number of them an
item will EVER need falls straight out of its rarity:

    common      cap  5     0 breakthroughs      0 fragments, ever
    uncommon    cap 10     1                    2
    rare        cap 15     2                   12
    epic        cap 20     3                   36
    legendary   cap 25     4                  100
    mythic      cap 30     5                  240
    divine      cap 35     6                  504

That is the requested "lower rarity needs very little": a Common needs
literally none, and an Uncommon needs two. It also means fragments never
gate the early game -- a new player's first drops are Common and
Uncommon, and both are effectively free to max.

The 250x spread from Uncommon to Divine is intentional and is the whole
reason this is per-rarity. A Divine item is worth roughly twice a Common
in raw stats but is meant to be the project you finish LAST, and before
this the only difference between levelling the two was that the Divine
had further to go at the same price per level.

----------------------------------------------------------------------
CARDS COST MORE THAN GEAR AT THE SAME LEVEL
----------------------------------------------------------------------
Asserted, not hoped for. Both costs are linear in level, so it is enough
that the CHEAPEST card breakthrough beats the DEAREST gear one:

    dearest gear at level L   = GEAR_FRAGMENT_BASE * 12 * (L / 5)  = 4.8 L
    cheapest card at level L  = CARD_FRAGMENT_BASE * 1.0 * (L / 10) = 6.0 L

tools/check_evolution.py asserts this across every level and every
rarity/star combination, because it is the kind of relationship that
holds when written and quietly stops holding the first time either base
is retuned in isolation.

Totals, for scale:

    divine gear, 1 -> 35        504 fragments
    3-star card, 1 -> 100     2,700
    4-star card, 1 -> 100     4,050
    5-star card, 1 -> 100     5,940

A maxed 5-star Card is roughly twelve Divine weapons' worth of
breakthroughs, which is the intended shape: a Card is one slot per
character, permanent, and the thing you are still working on when
everything else is finished.
"""

from __future__ import annotations

from bot.database.models.enums import Rarity

# ----------------------------------------------------------------------
# The boundaries
# ----------------------------------------------------------------------
GEAR_BREAKTHROUGH_EVERY = 5
CARD_BREAKTHROUGH_EVERY = 10


def is_gear_breakthrough(level: int) -> bool:
    """True if going from `level` to `level + 1` crosses a breakthrough."""
    return level > 0 and level % GEAR_BREAKTHROUGH_EVERY == 0


def is_card_breakthrough(level: int) -> bool:
    return level > 0 and level % CARD_BREAKTHROUGH_EVERY == 0


# ----------------------------------------------------------------------
# Gear
# ----------------------------------------------------------------------
GEAR_FRAGMENT_BASE = 2

# Per-rarity multiplier. Common is listed even though its cap of 5 means
# it can never reach a breakthrough -- an absent key would fall back to a
# default, and a silent default is how a new rarity would end up priced
# as a Common without anyone noticing.
GEAR_FRAGMENTS_BY_RARITY: dict[Rarity, int] = {
    Rarity.COMMON: 1,
    Rarity.UNCOMMON: 1,
    Rarity.RARE: 2,
    Rarity.EPIC: 3,
    Rarity.LEGENDARY: 5,
    Rarity.MYTHIC: 8,
    Rarity.DIVINE: 12,
}


def gear_breakthrough_cost(level: int, rarity: Rarity) -> int:
    """Fragments to take gear of `rarity` from `level` to `level + 1`.

    0 when the step isn't a breakthrough, which is four levels in five --
    callers can add this unconditionally.
    """
    if not is_gear_breakthrough(level):
        return 0
    multiplier = GEAR_FRAGMENTS_BY_RARITY.get(rarity, GEAR_FRAGMENTS_BY_RARITY[Rarity.COMMON])
    step = level // GEAR_BREAKTHROUGH_EVERY
    return GEAR_FRAGMENT_BASE * multiplier * step


# ----------------------------------------------------------------------
# Cards
# ----------------------------------------------------------------------
# 60, not 30. At 30 a 3-star card's breakthrough at level 10 cost 30
# fragments against a Divine item's 48 at the same level -- so the
# cheapest card was cheaper than the dearest gear, which is backwards and
# was the FIRST number I wrote here. 60 is the smallest base that keeps
# the promised ordering at every level; see the module docstring.
CARD_FRAGMENT_BASE = 60

CARD_FRAGMENTS_BY_STAR: dict[int, float] = {3: 1.0, 4: 1.5, 5: 2.2}


def card_breakthrough_cost(level: int, star_rating: int) -> int:
    """Fragments to take a `star_rating` Card from `level` to `level + 1`."""
    if not is_card_breakthrough(level):
        return 0
    multiplier = CARD_FRAGMENTS_BY_STAR.get(star_rating, CARD_FRAGMENTS_BY_STAR[3])
    step = level // CARD_BREAKTHROUGH_EVERY
    return int(round(CARD_FRAGMENT_BASE * multiplier * step))


# ----------------------------------------------------------------------
# Totals -- used by the shop/help copy and by the income budget below, so
# the numbers a player is quoted come from the same arithmetic they pay.
# ----------------------------------------------------------------------

def gear_lifetime_cost(rarity: Rarity) -> int:
    """Every fragment an item of `rarity` will need, level 1 to its cap."""
    from bot.game.loot.rarity_config import upgrade_level_cap
    return sum(gear_breakthrough_cost(level, rarity)
               for level in range(1, upgrade_level_cap(rarity)))


def card_lifetime_cost(star_rating: int) -> int:
    from bot.game.economy.card_config import CARD_MAX_LEVEL
    return sum(card_breakthrough_cost(level, star_rating)
               for level in range(1, CARD_MAX_LEVEL))


# ----------------------------------------------------------------------
# WHERE FRAGMENTS COME FROM
#
# Documentation, not logic -- each system pays them out itself. Kept here
# so the whole budget can be read in one place, and because the last time
# a currency's sources lived only in the systems that paid them, the
# survey comment drifted out of step with reality twice.
#
# EVERY LINE BELOW IS WIRED, and tools/check_evolution.py asserts it by
# looking for the currency in each config rather than trusting this list.
#
#   RECURRING
#     Evolution Cradle   the harvester (HQ 1). ~186/day at max level,
#                        and the dependable backbone
#     Evolution Domain   14 (trivial) to 260 (nightmare) per run -- the
#                        one place to go specifically FOR fragments
#     /daily             6 a claim, +40 on the 7-day milestone. Small on
#                        purpose: it exists so an early player can always
#                        cross a 2-fragment Uncommon breakthrough
#     /vote              25 a vote, +2 per streak step, doubled on a
#                        top.gg weekend -- ~100/day at two capped votes
#     expeditions        EVERY combat victory, guaranteed on elites and
#                        bosses, plus a third of all encounter outcomes.
#                        68/run at Glacier rising to 344 at Abyssnia,
#                        and the largest source for anyone actually
#                        playing
#     raids              3 (patrol) to 80 (nightmare) per raid
#     Void Abyss         12 (floor 1) to 135 (floor 12)
#
#   ONE-TIME
#     beginner quests    40 on the floor-20 quest, +120 completion bonus
#     prestige           the same rate as Cores, because a reset wipes
#                        every breakthrough already paid for
#
#   PURCHASABLE (all daily-limited; ~155/day if every door is used)
#     Salvage Contract   gold     -> 5,  HQ 1, x4/day. The floor under
#                        the whole system: a player who is short can
#                        always close the gap
#     Scrap Line         metal    -> 16, HQ 2, x4/day
#     Attunement Salvage tokens   -> 22, HQ 3, x3/day
#     Fragment Foundry   crystal  -> 40, HQ 4, x3/day
#     Entropy Loom       entropy  -> 60, HQ 5, x2/day
#
# The shop deliberately takes FIVE different currencies. One listing is
# a bottleneck wearing a shop's clothes -- a player short of fragments
# but sitting on metal had exactly one conversion and it wanted gold.
#
# BUDGET. An engaged player runs perhaps 400-600 fragments a day once
# adventuring is counted, and adventuring is where most of it comes from
# by design: fragments unlock the next level of the gear you are
# wearing, and the gear you are wearing came from a run.
#
#     a Divine item, 1 -> 35     504    ~1 day of play
#     a 5-star Card, 1 -> 100  5,940   ~two weeks
#
# Which is the intended split. Gear is a thing you finish; a Card is a
# thing you are still finishing.
# ----------------------------------------------------------------------
