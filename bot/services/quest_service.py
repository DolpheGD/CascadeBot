"""
Quest assignment and progress tracking.

Two independent flows sharing one PlayerQuest table (see
bot/database/models/quest_model.py):

- Beginner quests: seeded all at once (ensure_beginner_quests_seeded),
  each completable exactly once. Call this before reading a player's
  quest state anywhere it's displayed, since it's a cheap no-op once
  they're already seeded.
- Basic quests: up to MAX_ACTIVE_BASIC_QUESTS active rows at once (was a
  hard cap of 1). Filling an EMPTY slot (roll_basic_quest) is always
  instant, no cooldown -- BASIC_QUEST_COOLDOWN_HOURS only gates
  abandoning a specific STILL-ACTIVE quest early for a fresh one
  (reroll_basic_quest), using that quest's own `assigned_at` rather than
  a single player-wide timestamp, so multiple slots can each be on their
  own independent cooldown. Player.last_basic_quest_assigned_at is no
  longer read or written by this module (kept in the schema, just
  unused here now) -- it was a single-slot-era field that can't express
  "N independent slots, each with their own timer" the way per-row
  assigned_at can.

Progress is reported from all over the bot via record_progress(), which
updates every ACTIVE quest (of either kind) matching a given goal_type --
so e.g. a single item level-up simultaneously advances both a beginner
"upgrade a piece of gear" quest and an in-progress basic "level up gear 2
times" quest, if both happen to be active. Call sites:

- item_upgrade_service.level_up_item -> "upgrade_gear"
- dungeon_service.resolve_battle_end -> "complete_adventures" (run ends,
  win or lose), "win_battles" (any combat win), "defeat_elite" (elite-room
  win), "defeat_boss" (boss-room win) -- an elite-room or boss-room win
  fires "win_battles" too, so a generic "win N battles" quest still
  advances no matter what kind of fight it was
- daily_service.claim_daily -> "claim_daily"
- gacha_service.pull_single/pull_multi -> "gacha_pulls"
- harvester_service.buy_harvester -> "buy_harvester"
- harvester_service.collect_harvester -> "collect_harvester"
- lootbox_service.open_lootboxes -> "open_lootboxes"

roll_basic_quest draws from BASIC_QUEST_POOL weighted by each entry's
optional "weight" key (default 10 if absent) rather than uniformly, so
quick/cheap quests surface more often than big multi-kill grinds -- see
quest_config.py's module docstring for the full weight convention.
"""

from __future__ import annotations

import datetime as dt
import random

from bot.database.models.quest_model import PlayerQuest
from bot.game.economy.quest_config import (
    BASIC_QUEST_COOLDOWN_HOURS,
    BASIC_QUEST_POOL,
    BEGINNER_BONUS_REWARD,
    BEGINNER_QUESTS,
    MAX_ACTIVE_BASIC_QUESTS,
)
from bot.services.currency_service import add_currency


class QuestOnCooldown(Exception):
    def __init__(self, time_remaining: dt.timedelta):
        self.time_remaining = time_remaining
        super().__init__(f"Basic quest reroll on cooldown for {time_remaining}")


class QuestSlotsFull(Exception):
    def __init__(self, max_slots: int):
        self.max_slots = max_slots
        super().__init__(f"All {max_slots} basic quest slots are already active")


def _grant_reward(db, player, reward: dict[str, int]) -> None:
    for currency, amount in reward.items():
        if amount:
            add_currency(db, player, currency, amount)


def ensure_beginner_quests_seeded(db, player) -> None:
    """Inserts any missing beginner-quest rows for this player. Safe to
    call repeatedly (e.g. every time /quests is opened) -- only creates
    rows that don't already exist, keyed by quest_id."""
    existing_ids = {
        q.quest_id for q in db.query(PlayerQuest)
        .filter_by(player_id=player.id, kind="beginner").all()
    }
    created = False
    for quest in BEGINNER_QUESTS:
        if quest["id"] in existing_ids:
            continue
        db.add(PlayerQuest(
            player_id=player.id,
            quest_id=quest["id"],
            kind="beginner",
            goal_type=quest["goal_type"],
            goal_count=quest["goal_count"],
        ))
        created = True
    if created:
        db.commit()


def get_beginner_quests(db, player) -> list[PlayerQuest]:
    ensure_beginner_quests_seeded(db, player)
    return (
        db.query(PlayerQuest)
        .filter_by(player_id=player.id, kind="beginner")
        .order_by(PlayerQuest.id)
        .all()
    )


def get_active_basic_quests(db, player) -> list[PlayerQuest]:
    """All currently-active (incomplete) basic quest rows, oldest first --
    up to MAX_ACTIVE_BASIC_QUESTS of them."""
    return (
        db.query(PlayerQuest)
        .filter_by(player_id=player.id, kind="basic", is_completed=False)
        .order_by(PlayerQuest.assigned_at)
        .all()
    )


def basic_quest_reroll_cooldown_remaining(quest: PlayerQuest) -> dt.timedelta | None:
    """None if THIS specific still-active quest can be abandoned and
    rerolled right now (see reroll_basic_quest). Only meaningful for an
    unfinished quest -- a completed one frees its slot immediately, no
    cooldown involved (see roll_basic_quest)."""
    assigned = quest.assigned_at
    if assigned.tzinfo is None:
        assigned = assigned.replace(tzinfo=dt.timezone.utc)
    elapsed = dt.datetime.now(dt.timezone.utc) - assigned
    remaining = dt.timedelta(hours=BASIC_QUEST_COOLDOWN_HOURS) - elapsed
    return remaining if remaining > dt.timedelta(0) else None


def _new_basic_quest_row(player, rng: random.Random) -> PlayerQuest:
    quest_data = rng.choices(
        BASIC_QUEST_POOL,
        weights=[q.get("weight", 10) for q in BASIC_QUEST_POOL],
        k=1,
    )[0]
    return PlayerQuest(
        player_id=player.id,
        quest_id=quest_data["id"],
        kind="basic",
        goal_type=quest_data["goal_type"],
        goal_count=quest_data["goal_count"],
    )


def roll_basic_quest(db, player, rng: random.Random | None = None) -> PlayerQuest:
    """Fills an EMPTY basic-quest slot with a new random quest. Always
    succeeds instantly if there's a free slot (fewer than
    MAX_ACTIVE_BASIC_QUESTS currently active) -- no cooldown for this;
    completing a quest (or never having rolled one at all) should let a
    player jump straight back in. Raises QuestSlotsFull if every slot is
    already occupied by an unfinished quest -- reroll_basic_quest a
    specific one instead if you want a different quest in an occupied
    slot."""
    active = get_active_basic_quests(db, player)
    if len(active) >= MAX_ACTIVE_BASIC_QUESTS:
        raise QuestSlotsFull(MAX_ACTIVE_BASIC_QUESTS)

    rng = rng or random.Random()
    quest = _new_basic_quest_row(player, rng)
    db.add(quest)
    db.commit()
    db.refresh(quest)
    return quest


def reroll_basic_quest(db, player, quest_id: int, rng: random.Random | None = None) -> PlayerQuest:
    """Abandons one SPECIFIC still-active basic quest (identified by its
    PlayerQuest.id, not its quest_id string) and immediately rolls a new
    one into that same slot -- gated by BASIC_QUEST_COOLDOWN_HOURS since
    THAT quest was assigned (see basic_quest_reroll_cooldown_remaining),
    so a player can't cherry-pick an easy quest by spamming rerolls.
    Raises QuestOnCooldown if it's not old enough yet, or ValueError if
    quest_id doesn't match an active basic quest owned by this player."""
    quest = (
        db.query(PlayerQuest)
        .filter_by(id=quest_id, player_id=player.id, kind="basic", is_completed=False)
        .first()
    )
    if quest is None:
        raise ValueError("That quest isn't one of your active basic quests.")

    remaining = basic_quest_reroll_cooldown_remaining(quest)
    if remaining is not None:
        raise QuestOnCooldown(remaining)

    rng = rng or random.Random()
    db.delete(quest)
    new_quest = _new_basic_quest_row(player, rng)
    db.add(new_quest)
    db.commit()
    db.refresh(new_quest)
    return new_quest


def _quest_config_by_id(quest_id: str) -> dict | None:
    for quest in BEGINNER_QUESTS:
        if quest["id"] == quest_id:
            return quest
    for quest in BASIC_QUEST_POOL:
        if quest["id"] == quest_id:
            return quest
    return None


def record_progress(db, player, goal_type: str, amount: int = 1) -> list[PlayerQuest]:
    """Advances every active quest (beginner or basic) matching goal_type
    by `amount`, completing (and immediately rewarding) any that cross
    their goal_count. Also grants the one-time beginner completion bonus
    if this was the last remaining beginner quest. Returns the list of
    quests that were newly completed by this call, in case a caller wants
    to notify the player (currently none do -- quests are checked via
    /quests rather than announced inline, to avoid spamming combat/
    dungeon messages)."""
    ensure_beginner_quests_seeded(db, player)

    quests = (
        db.query(PlayerQuest)
        .filter_by(player_id=player.id, goal_type=goal_type, is_completed=False)
        .all()
    )
    if not quests:
        return []

    newly_completed = []
    for quest in quests:
        quest.progress = min(quest.progress + amount, quest.goal_count)
        if quest.progress >= quest.goal_count:
            quest.is_completed = True
            quest.completed_at = dt.datetime.now(dt.timezone.utc)
            newly_completed.append(quest)
    db.commit()

    for quest in newly_completed:
        config = _quest_config_by_id(quest.quest_id)
        if config:
            _grant_reward(db, player, config["reward"])

    if any(q.kind == "beginner" for q in newly_completed):
        _maybe_grant_beginner_bonus(db, player)

    return newly_completed


def _maybe_grant_beginner_bonus(db, player) -> None:
    if player.beginner_quest_bonus_claimed:
        return
    beginner_quests = db.query(PlayerQuest).filter_by(player_id=player.id, kind="beginner").all()
    if len(beginner_quests) < len(BEGINNER_QUESTS):
        return  # not all seeded yet somehow -- shouldn't happen, but don't false-positive
    if not all(q.is_completed for q in beginner_quests):
        return

    player.beginner_quest_bonus_claimed = True
    db.commit()
    _grant_reward(db, player, BEGINNER_BONUS_REWARD)
