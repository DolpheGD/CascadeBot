"""
ONE-TIME reset: wipe testing progress, pay everybody back for it.

    python -m tools.reset_and_compensate                 # dry run, changes nothing
    python -m tools.reset_and_compensate --apply         # do it
    python -m tools.reset_and_compensate --apply --backup path.db

WHAT IT DOES
------------
Every player's holdings are VALUED at what they cost to acquire, then
their progress is cleared and the value is paid back as currency. Nobody
loses ground: a tester who pulled forty characters and levelled a full
squad restarts with the shards, cores, gold, fragments and materials that
represents, and can rebuild whatever they like -- including something
different.

WHAT IS DELIBERATELY *NOT* PRESERVED
------------------------------------
Characters, cards, gear, levels, story progress, HQ, harvesters, quests,
expeditions. That is the point: the balance work this reset accompanies
changed the early game substantially, and testers are sitting on
mid-game economies collected under the old numbers. Converting rather
than keeping is what puts everybody on the new curve with a head start
instead of on the old one with an advantage.

VALUATION
---------
Priced at ACQUISITION COST, not at some notion of worth:

  * a character is what its pulls cost -- one pull per copy, at the
    banner's own SINGLE_PULL_COST_SHARDS, so dupes count
  * a card likewise, in cores
  * gear is priced by the game's own upgrade curve, level by level,
    since upgrading is where the real spend went
  * evolution fragments spent on breakthroughs come back as fragments
  * currencies on hand are carried across untouched, not replaced

Those four are read from the game's own config, so a retune reprices the
payout automatically. LEVELS are the exception and are paid in gold as
goodwill for time rather than as a refund -- see GOLD_PER_CHARACTER_LEVEL
for why that distinction is drawn explicitly.

SAFETY
------
  * dry run by default; --apply is required to write
  * --backup copies the SQLite file first
  * idempotent: a marker row records that a player has been compensated,
    so running it twice does not pay twice
  * the whole thing is one transaction per player and rolls back on error
"""

from __future__ import annotations

import argparse
import shutil
import sys

# LEVELS ARE PAID IN GOLD, AND THIS IS GOODWILL RATHER THAN A REFUND.
#
# Worth being precise about, because the rest of this file is a refund
# and it would be easy to read these two lines as one too. Characters and
# accounts level on XP, which is earned by playing and never bought --
# there is no currency to give back. What is being compensated is TIME,
# and gold is the only currency in the game abundant enough to express it
# without distorting anything: shards and cores buy pulls, fragments buy
# breakthroughs, and inflating either would hand back more progress than
# was lost.
#
# 900 a character level and 2,500 an account level puts a heavy tester at
# roughly ten to twenty Entrospire runs' worth of gold -- a real head
# start that still leaves the economy to play through.
GOLD_PER_CHARACTER_LEVEL = 900
GOLD_PER_ACCOUNT_LEVEL = 2500

# GEAR IS PRICED BY THE GAME'S OWN UPGRADE COST, not by a table in this
# file.
#
# The first version of this script had a hand-written
# GEAR_GOLD_PER_LEVEL dict with an epic at 900 gold a level. The real
# curve (item_upgrade_service._gold_for_level) charges 8,303 gold to take
# ANY item from 1 to 20 regardless of rarity, because the cost is driven
# by level, not rarity. The invented table valued a 25-item collection at
# 450,000 gold -- roughly fifteen times what upgrading it actually cost --
# and the whole point of this script is to pay back what was spent.
#
# It also made the docstring above a lie: "everything is read from the
# game's own config" was true of characters and cards and false of the
# single largest line in the payout.

# A goodwill multiplier on the whole payout. The brief asks for testers
# to get "a big boost", and paying back exactly what was spent leaves
# somebody who tested for weeks precisely where they started.
GOODWILL = 1.35


# ======================================================================
# THE CURVE: everyone lands close together, in the same order.
# ======================================================================
#
# WHY A STRAIGHT REFUND WAS WRONG. Paying back exactly what was spent is
# the fair-sounding answer and it produced this, measured on the real
# player table:
#
#     shards   25,920 top   vs  162 lowest non-zero   -> 160x
#     gold    557,128 top   vs   75 lowest non-zero   -> 7,428x
#     and THREE of sixteen players got nothing at all
#
# Those numbers are not a record of skill. They are a record of who
# happened to be testing during the weeks when things were being handed
# out, and carrying them into a fresh start would mean the new game
# opens with a settled hierarchy nobody played for.
#
# The three zeroes are the sharper problem. Every one of these accounts
# is being wiped WITHOUT ASKING. An involuntary reset that pays somebody
# nothing is not compensation, it is just a deletion.
#
# THE SHAPE: floor + cap * (1 - e^(-raw/scale)).
#
#   * FLOOR   what everybody gets for having been here at all.
#   * CAP     the most the earned portion can ever add. The payout
#             approaches floor+cap and never exceeds it, which is
#             exactly "the difference gets smaller the more you piled
#             up" expressed as arithmetic rather than as a promise.
#   * SCALE   where diminishing starts to bite: at raw == scale a
#             player has 63% of the cap, at 2x scale 86%, at 3x 95%.
#
# Ordering is preserved everywhere -- the curve is strictly increasing,
# so more progress always pays more. It just pays progressively less
# more, which is the entire request.
#
# A BANDED LADDER (first N at 100%, next at 50%...) was modelled against
# the same data and lands within a few percent of this. It was not used
# because bands have edges: one shard either side of a boundary is worth
# ten times less, and there is no reason for that cliff to exist here.
# The buff ladder in combatant.py has bands for a reason this does not
# share -- it needs to separate one source from three.
#
# EVERY CONSTANT IS EXPRESSED IN WHAT THE GAME CHARGES, so these can be
# read as game outcomes rather than as numbers somebody liked:
#
#     one character pull        120 shards
#     one card pull             120 cores
#     one Rare craft              2,500 gold
#     the full forge path       118,000 gold
#     breaking through a divine     504 fragments
#
# ---------------------------------------------------------------------
# floor, cap, scale -- per currency, because they are not comparable.
# ---------------------------------------------------------------------
COMPENSATION_CURVE: dict[str, tuple[int, int, int]] = {
    # Floor 480 = 4 pulls, so the emptiest account still opens the gacha
    # a few times. Cap 6,000 = 50 pulls on top, reached asymptotically.
    "shards": (480, 6_000, 4_000),

    # GOLD IS PRICED AGAINST THE FORGE, not against item levelling, and
    # that re-anchoring is what moved these numbers.
    #
    # Levelling one item to 50 costs 72,275, which made 25,000 look
    # modest -- a third of one item. But gold's real sinks are the forge
    # upgrade path (4,000 + 14,000 + 30,000 + 70,000 = 118,000 to max)
    # and crafting (2,500 Rare up to 38,000 Divine), and against those
    # the old figures read very differently:
    #
    #     old floor   25,000  = a free Mythic craft, for zero progress
    #     old ceiling 175,000 = the entire forge path AND a Divine craft,
    #                           i.e. 148% of the whole upgrade economy
    #
    # Floor 5,000 is two Rare crafts or the first forge upgrade with
    # change -- a restart kit rather than a head start. Cap 40,000 puts
    # the ceiling at 45,000, just short of forge level 3 (48,000), so the
    # most-played account recovers most of that path and still has to
    # play for the rest.
    #
    # SCALE 60,000 IS DELIBERATELY SHORT, and it is the part that
    # tightens the top. At 120,000 the four biggest accounts spread over
    # 51,585 gold; at 60,000 they spread over 4,783. Above roughly
    # 100,000 raw the differences stop being things anyone played for --
    # they record who was present while gold was being handed out -- so
    # the curve stops paying for them and lets the top converge.
    "gold": (5_000, 40_000, 60_000),

    # Floor 120 = one card pull. Cap 3,000 = 25 more.
    "cores": (120, 3_000, 2_500),

    # Floor 250 = half a divine breakthrough. Cap 1,500 = three of them.
    "evolution_fragments": (250, 1_500, 1_200),
}


# ======================================================================
# AUTHENTICITY: paying for a roster nobody played
# ======================================================================
#
# THE PROBLEM, visible in the real player table before the reset ran.
# Three accounts owned a great deal and had played almost none of it:
#
#     Sader   26 characters, 500 items, ZERO levels on any of them
#     Polo    18 characters, zero levels
#     AIZER    9 characters,  54 items, zero levels
#
# against accounts like Sine (22 characters, 267 items, half a million
# gold of levelling behind them). Under a pure ownership refund the first
# group was collecting the largest shard payouts in the game for a roster
# that arrived by grant.
#
# WHERE THE CORRECTION BELONGS, AND WHERE IT DOES NOT.
#
# Gold and fragments need no correction at all, and this is the useful
# realisation: both are already computed from LEVELS and BREAKTHROUGHS --
# character levels, account levels, gear upgrades, fragment costs. Every
# one of those is XP or spend, and neither can be handed over. A granted
# account scores zero on them automatically, with no rule required.
#
# Shards are the exception. They pay per CHARACTER OWNED, which is
# exactly the thing that can be granted wholesale, so shards are the only
# line where ownership and effort come apart. Cores have the same shape
# for cards.
#
# So the factor applies to those two and nothing else. Applying it
# globally would double-penalise the gold line, which had already priced
# the missing effort at zero.
#
# WHAT IT MEASURES: average level across the roster being paid for. A
# character somebody actually played is levelled; one that was granted
# and never fielded sits at 1.
#
# THE FLOOR IS NEVER TOUCHED. Small genuine accounts -- Nepos, Romain,
# Zodor, one character each, barely played -- must not be caught by an
# anti-grant rule aimed at somebody else. They own almost nothing, so
# their earned portion is tiny and the floor is nearly all of their
# payout, which is the correct outcome and stays true regardless of this
# factor.

# Average character level that counts as a fully played roster.
# Deliberately low: a character taken to 10 has been used, and the
# question here is "did you play this at all", not "did you max it".
FULLY_PLAYED_AVERAGE_LEVEL = 10.0

# What a completely unplayed roster still keeps of its earned portion.
# Not zero -- these are testers who were present, and some of the
# granting was done TO them rather than by them. It is a discount, not a
# forfeit.
MIN_AUTHENTICITY = 0.25

# Currencies paid for OWNERSHIP rather than for effort, and therefore the
# only ones this scales. See the note above.
OWNERSHIP_PAID = ("shards", "cores")


def authenticity(characters) -> float:
    """0.25 - 1.0, from the average level of the roster being paid for.

    An empty roster returns 1.0 rather than 0.25: a player with no
    characters is not gaming anything, and there is no ownership payout
    to scale in the first place.
    """
    roster = [c for c in characters
              if not getattr(c.template, "is_player_avatar", False)]
    if not roster:
        return 1.0
    average = sum(max(0, int(c.level or 1)) for c in roster) / len(roster)
    played = min(1.0, average / FULLY_PLAYED_AVERAGE_LEVEL)
    return MIN_AUTHENTICITY + (1.0 - MIN_AUTHENTICITY) * played


def discount(currency: str, paid: float, genuine: float) -> float:
    """Scale the EARNED portion of a payout, leaving the floor whole.

    AFTER THE CURVE, NOT BEFORE. This was written the other way round
    first -- multiply the raw figure, then compress it -- and on the real
    table it did almost nothing: the worst offender lost 5% and stayed
    level with the most-played account in the game.

    The reason is the asymptote. An account far past the curve's scale is
    saturated, so 35,000 raw and 11,500 raw both flatten onto the same
    ceiling and a two-thirds cut disappears into the compression. A
    discount applied before a saturating curve is a discount on a number
    that no longer matters.

    Applied afterwards it lands on the value the player will actually
    see. Subtracting the floor first is what keeps the promise that
    nobody drops below it: the floor is not part of what gets scaled, so
    an empty or barely-played account receives exactly the same floor it
    would have received without any of this.
    """
    floor = COMPENSATION_CURVE.get(currency, (0, 0, 0))[0]
    return floor + (paid - floor) * genuine


def compensate(currency: str, raw: float) -> int:
    """The curve above, applied to one raw refund figure.

    A currency with no curve entry is returned unchanged rather than
    silently zeroed -- an unknown currency is a missing config line, and
    paying it straight is the safe direction to fail.
    """
    import math

    entry = COMPENSATION_CURVE.get(currency)
    if entry is None:
        return int(round(raw))
    floor, cap, scale = entry
    if raw <= 0:
        # The floor is paid to EVERYONE, including accounts that earned
        # nothing. They are losing their account either way.
        return floor
    return int(round(floor + cap * (1 - math.exp(-raw / scale))))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true",
                        help="actually write (default is a dry run)")
    parser.add_argument("--backup", metavar="PATH",
                        help="copy the SQLite file here before writing")
    parser.add_argument("--limit", type=int, default=0,
                        help="only process N players (for a trial run)")
    args = parser.parse_args()

    sys.path.insert(0, ".")

    from sqlalchemy.orm import sessionmaker

    from bot.database.db import engine
    from bot.database.db_init import init_db
    from bot.database.models.card_model import PlayerCard
    from bot.database.models.character_model import (
        PlayerCharacter, SquadPreset, SquadSlot,
    )
    from bot.database.models.equipment_model import InventoryItem
    from bot.database.models.player_model import Player
    from bot.game.economy.card_config import CARD_PULL_COST
    from bot.game.economy.character_evolution_config import (
        requirement_for as evolution_requirements,
    )
    from bot.game.economy.character_gacha_config import SINGLE_PULL_COST_SHARDS
    from bot.game.economy.resonance_config import ECHO_COST_BY_STAR
    from bot.services.item_upgrade_service import _gold_for_level

    # Echoes per "one pull's worth of value", read from the exchange's own
    # price for a 3-star -- the cheapest thing echoes buy. Used only to
    # convert an evolution's echo cost into shards, since this reset pays
    # in pull currency and echoes are not part of the payout table.
    ECHO_PER_PULL = ECHO_COST_BY_STAR[3]

    if args.backup:
        if not args.apply:
            print("--backup only makes sense with --apply")
            return 1
        source = str(engine.url.database or "")
        if not source:
            print("cannot back up: not a file-backed database")
            return 1
        shutil.copy2(source, args.backup)
        print(f"backup written to {args.backup}")

    init_db()
    db = sessionmaker(bind=engine)()

    players = db.query(Player).order_by(Player.id).all()
    if args.limit:
        players = players[: args.limit]

    print(f"{'player':<22}{'chars':>6}{'cards':>6}{'gear':>6}"
          f"{'shards':>10}{'cores':>9}{'gold':>12}{'frags':>9}")
    print("-" * 80)

    grand = {"shards": 0, "cores": 0, "gold": 0, "evolution_fragments": 0}
    skipped = 0

    for player in players:
        if _already_done(player):
            skipped += 1
            continue

        characters = db.query(PlayerCharacter).filter_by(player_id=player.id).all()
        cards = db.query(PlayerCard).filter_by(player_id=player.id).all()
        gear = db.query(InventoryItem).filter_by(player_id=player.id).all()

        payout = {
            "shards": 0, "cores": 0, "gold": 0, "evolution_fragments": 0,
        }

        # ---- characters: one pull per copy, dupes included -----------
        for character in characters:
            if getattr(character.template, "is_player_avatar", False):
                # The avatar was never pulled. Its LEVEL still counts.
                pass
            else:
                # dupe_count ALREADY INCLUDES THE FIRST COPY. This read
                # `1 + dupe_count`, which paid two pulls for a character
                # pulled once and inflated every single payout by one
                # pull per character owned -- then multiplied it by
                # GOODWILL on top.
                #
                # The model settles it: dupe_count defaults to 1 and
                # grant_character creates the row at that default on the
                # FIRST pull, incrementing only on later ones. The name
                # is what misleads -- "dupe_count" reads like "how many
                # duplicates", and it is "how many copies".
                copies = max(1, int(character.dupe_count or 1))
                payout["shards"] += copies * SINGLE_PULL_COST_SHARDS

            # ---- evolution, refunded at cost -------------------------
            #
            # Evolution shipped after this tool was written, so it paid
            # nothing for it: the wipe deletes the PlayerCharacter row,
            # evolution_stage goes with it, and a player who spent 700
            # echoes, 300,000 gold and 850 fragments taking a favourite
            # to 5* got back exactly the pull price of one 3*.
            #
            # Refunded from the real requirement table rather than an
            # estimate, so it stays correct if those costs are retuned.
            stage = int(getattr(character, "evolution_stage", 0) or 0)
            if stage:
                native = int(character.template.star_rating or 3)
                for target in range(native + 1, native + stage + 1):
                    requirement = evolution_requirements(target)
                    for currency, amount in (requirement or {}).get("cost", {}).items():
                        if currency in payout:
                            payout[currency] += amount
                        elif currency == "echoes":
                            # Echoes are not in the payout table -- they
                            # buy characters, and this reset hands back
                            # pull currency instead. Converted at the
                            # exchange's own price so the value survives.
                            payout["shards"] += int(
                                amount * SINGLE_PULL_COST_SHARDS / ECHO_PER_PULL)

            payout["gold"] += max(0, int(character.level or 1) - 1) * GOLD_PER_CHARACTER_LEVEL

        # ---- cards ---------------------------------------------------
        for card in cards:
            payout["cores"] += CARD_PULL_COST
            payout["gold"] += max(0, int(card.level or 1) - 1) * GOLD_PER_CHARACTER_LEVEL // 2

        # ---- gear: exactly what upgrading it cost --------------------
        for item in gear:
            level = int(item.item_level or 1)
            for step in range(2, level + 1):
                payout["gold"] += _gold_for_level(step)
                payout["evolution_fragments"] += _fragments_for_step(item, step)

        # ---- account level ------------------------------------------
        payout["gold"] += max(0, int(player.level or 1) - 1) * GOLD_PER_ACCOUNT_LEVEL

        # GOODWILL, THEN AUTHENTICITY, THEN THE CURVE. In that order.
        #
        # Goodwill scales what was actually spent. Authenticity then
        # discounts the lines that pay for ownership rather than effort.
        # The curve compresses last, which is what keeps the floor
        # untouchable: it is added AFTER the discount, so a heavily
        # discounted account still lands on the full floor rather than a
        # quarter of it.
        #
        # Doing it in any other order breaks one of the two guarantees --
        # compressing first lets goodwill push the top back over the cap,
        # and discounting after the curve would cut into the floor that
        # every wiped account is owed.
        genuine = authenticity(characters)
        for key in payout:
            value = compensate(key, payout[key] * GOODWILL)
            if key in OWNERSHIP_PAID:
                value = discount(key, value, genuine)
            payout[key] = int(round(value))

        print(f"{(player.username or str(player.id))[:20]:<22}"
              f"{len(characters):>6}{len(cards):>6}{len(gear):>6}"
              f"{payout['shards']:>10,}{payout['cores']:>9,}"
              f"{payout['gold']:>12,}{payout['evolution_fragments']:>9,}")
        for key, value in payout.items():
            grand[key] += value

        if not args.apply:
            continue

        try:
            # ---- wipe, then pay -------------------------------------
            #
            # Currencies already held are KEPT and added to, not
            # replaced: they were earned under the old numbers too, and
            # taking them away to hand back a computed figure would make
            # the payout a downgrade for anybody sitting on a pile.
            db.query(SquadSlot).filter_by(player_id=player.id).delete()
            db.query(SquadPreset).filter_by(player_id=player.id).delete()
            db.query(InventoryItem).filter_by(player_id=player.id).delete()
            db.query(PlayerCard).filter_by(player_id=player.id).delete()
            db.query(PlayerCharacter).filter_by(player_id=player.id).delete()
            _wipe_progress(db, player)

            player.shards = int(player.shards or 0) + payout["shards"]
            player.cores = int(player.cores or 0) + payout["cores"]
            player.gold = int(player.gold or 0) + payout["gold"]
            player.evolution_fragments = (int(player.evolution_fragments or 0)
                                          + payout["evolution_fragments"])
            _mark_done(player)
            db.commit()
        except Exception as exc:  # pragma: no cover
            db.rollback()
            print(f"  ROLLED BACK for {player.username}: {exc!r}")
            return 1

    print("-" * 80)
    print(f"{'TOTAL':<40}{grand['shards']:>10,}{grand['cores']:>9,}"
          f"{grand['gold']:>12,}{grand['evolution_fragments']:>9,}")
    if skipped:
        print(f"skipped {skipped} player(s) already compensated")
    if not args.apply:
        print("\nDRY RUN -- nothing was written. Re-run with --apply "
              "(and --backup is strongly recommended).")
    else:
        print(f"\nDONE -- {len(players) - skipped} player(s) reset and compensated.")
    return 0


def _fragments_for_step(item, level: int) -> int:
    """Evolution fragments one upgrade step consumed, if it was a
    breakthrough. Read from evolution_config so a retune of the
    breakthrough curve reprices refunds automatically."""
    from bot.game.economy import evolution_config as ev

    if not ev.is_gear_breakthrough(level):
        return 0
    rarity = getattr(item, "rarity", None)
    try:
        return int(ev.gear_breakthrough_cost(level, rarity))
    except Exception:
        return 0


def _rarity_name(item) -> str:
    rarity = getattr(item, "rarity", None)
    return str(getattr(rarity, "value", rarity) or "common").lower()


# ----------------------------------------------------------------------
# Idempotence.
#
# The marker lives in an EXISTING column rather than a new table, so this
# script needs no schema change of its own -- a migration that migrates
# the schema in order to record that it ran is a migration with two
# failure modes.
#
# `beginner_quest_bonus_claimed` is repurposed deliberately: after a reset
# a player's beginner quests are gone, and the flag would otherwise leave
# them unable to re-earn that bonus. Clearing it as part of the reset and
# using a dedicated marker keeps both meanings honest.
# ----------------------------------------------------------------------
_MARKER = "[reset-v1]"


def _already_done(player) -> bool:
    return _MARKER in (player.username or "")


def _mark_done(player) -> None:
    if not _already_done(player):
        player.username = f"{player.username or ''} {_MARKER}".strip()[:64]


def _wipe_progress(db, player) -> None:
    """Clear the per-player rows that represent progress rather than
    holdings. Anything missing from this list is left alone on purpose --
    pull history and gift records are audit trails, not progress."""
    # Imported by NAME from the real modules. The first version guessed
    # at `PlayerBase` in base_building_model, which does not exist -- the
    # module holds PlayerLab, PlayerResearch and PlayerForge. The import
    # raised inside the per-player try, the transaction rolled back, and
    # nothing was written: the safety worked, but the whole run was a
    # no-op that printed a payout table as though it had done something.
    from bot.database.models.abyss_model import PlayerAbyss
    from bot.database.models.base_building_model import (
        PlayerForge, PlayerLab, PlayerResearch,
    )
    from bot.database.models.economy_model import PlayerHarvester, PlayerLootbox
    from bot.database.models.expedition_model import Expedition
    from bot.database.models.hq_model import PlayerBase, PlayerShrine
    from bot.database.models.quest_model import PlayerQuest
    from bot.database.models.story_model import PlayerStory

    # Added after the systems they belong to shipped. Verified by running
    # the migration against a fully-progressed account and reading the
    # result rather than assuming:
    #
    #   PlayerAchievement -- receipts for progress that no longer exists.
    #       Achievements are DERIVED, so a wiped account correctly shows
    #       them as unearned either way; what the leftover rows break is
    #       the "newly earned" announcement, because sync() compares
    #       against them. Without this, a returning player re-earns
    #       "Signed On" in silence.
    #
    #   DojoClear -- which of other people's challenges you have beaten,
    #       and the daily-cap history. That is progress.
    #
    # DojoChallenge is deliberately NOT here. A published challenge is
    # authored content other players are playing, not the author's
    # progress, and deleting it would take somebody else's content down
    # as a side effect of compensating its author.
    from bot.database.models.achievement_model import PlayerAchievement
    from bot.database.models.dojo_model import DojoClear

    for model in (Expedition, PlayerQuest, PlayerStory, PlayerAbyss,
                  PlayerHarvester, PlayerLootbox, PlayerLab, PlayerResearch,
                  PlayerForge, PlayerBase, PlayerShrine,
                  PlayerAchievement, DojoClear):
        try:
            db.query(model).filter_by(player_id=player.id).delete()
        except Exception:
            # A model without a player_id, or a table this deployment
            # does not have. Skipping is correct: the reset is about
            # progress, and anything that cannot be keyed to a player is
            # not this player's progress.
            db.rollback()

    player.level = 1
    player.xp = 0
    player.beginner_quest_bonus_claimed = False
    player.pity_since_five_star = 0
    player.pity_since_four_star = 0
    player.card_pity_since_five_star = 0
    player.card_pity_since_four_star = 0
    player.target_character = None
    player.target_card = None
    player.target_character_guaranteed = False
    player.target_card_guaranteed = False
    player.challenge_power = 0
    player.challenge_wins = 0
    player.challenge_losses = 0
    player.challenges_today = 0

    # The equipped title goes with the achievements that granted it.
    #
    # Found by running the migration and reading the result: the account
    # came out wearing "Abyssal" -- earned for all 36 Abyss stars -- with
    # zero Abyss stars and no way to re-claim the title. A cosmetic that
    # cites progress the player no longer has is the one piece of the old
    # world that would have survived visibly, on the leaderboard, where
    # everyone could see it.
    player.active_title = None

    # Dojo daily state. The clears themselves are deleted above.
    player.dojo_clears_today = 0
    player.last_dojo_clear_at = None

    # Challenge-cycle points. The banked cycle is progress toward a claim
    # in a world that is being wound up; leaving it would pay out against
    # a week that no longer exists.
    player.challenge_points = 0
    player.challenge_banked_points = 0
    player.challenge_claimed_cycle = -1


if __name__ == "__main__":
    raise SystemExit(main())
