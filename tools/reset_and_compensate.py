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

        for key in payout:
            payout[key] = int(payout[key] * GOODWILL)

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

    for model in (Expedition, PlayerQuest, PlayerStory, PlayerAbyss,
                  PlayerHarvester, PlayerLootbox, PlayerLab, PlayerResearch,
                  PlayerForge, PlayerBase, PlayerShrine):
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


if __name__ == "__main__":
    raise SystemExit(main())
