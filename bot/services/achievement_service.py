"""
Computing achievements, titles and collection progress.

EVERYTHING FLOWS FROM ONE FUNCTION: metrics(). It reads a player's whole
state and returns a flat dict of numbers. An achievement is then nothing
but a metric key and a threshold, and the collection screen is a few of
the same numbers presented differently.

That shape is the point. There is exactly one place that knows how to
count a player's regions cleared, and both the achievement that wants six
of them and the screen that displays them read it from there. The
alternative -- each caller doing its own query -- is how a profile ends
up disagreeing with an achievement about the same fact.

METRICS ARE DERIVED, NEVER RECORDED. Nothing in the game calls into this
module to report progress; it looks at the tables that already exist. See
the achievement_config docstring for why, and for what that rules out.
"""

from __future__ import annotations

import datetime as dt

from bot.game.achievements import achievement_config as cfg


def metrics(db, player) -> dict[str, int]:
    """Every number an achievement or the collection screen can use.

    One query pass, so a screen showing thirty achievements does thirty
    dictionary lookups rather than thirty round trips.
    """
    from bot.database.models.card_model import CardTemplate, PlayerCard
    from bot.database.models.character_model import CharacterTemplate, PlayerCharacter
    from bot.database.models.dojo_model import DojoChallenge, DojoClear
    from bot.database.models.equipment_model import InventoryItem
    from bot.database.models.expedition_model import Expedition, ExpeditionStatus
    from bot.database.models.enums import Rarity
    from bot.game.economy.resonance_config import MAX_RESONANCE, resonance_for

    characters = (db.query(PlayerCharacter)
                  .filter_by(player_id=player.id).all())
    completed_expeditions = (
        db.query(Expedition)
        .filter_by(player_id=player.id, status=ExpeditionStatus.COMPLETED).all())

    # Story state may not exist yet for a brand-new player.
    from bot.database.models.story_model import PlayerStory
    story = db.query(PlayerStory).filter_by(player_id=player.id).one_or_none()

    from bot.database.models.abyss_model import PlayerAbyss
    abyss = db.query(PlayerAbyss).filter_by(player_id=player.id).one_or_none()

    return {
        # ---- story
        "missions_completed": len((story.completed_missions or []) if story else []),
        "prologue_complete": 1 if (story and story.prologue_complete) else 0,

        # ---- expeditions
        #
        # Region clears are counted from FINISHED expeditions rather than
        # from a flag, because no flag exists -- and deriving it means it
        # cannot disagree with the run history the player can see.
        "expeditions_completed": len(completed_expeditions),
        "regions_cleared": len({e.region for e in completed_expeditions if e.region}),

        # ---- abyss
        "abyss_stars": int(abyss.stars or 0) if abyss else 0,

        # ---- roster
        "characters_owned": len(characters),
        "cards_owned": db.query(PlayerCard).filter_by(player_id=player.id).count(),
        "characters_total": db.query(CharacterTemplate).count(),
        "cards_total": db.query(CardTemplate).count(),

        # ---- mastery
        "highest_character_level": max((c.level for c in characters), default=0),
        "evolutions_done": sum(int(c.evolution_stage or 0) for c in characters),
        "max_resonance_characters": sum(
            1 for c in characters
            if resonance_for(int(c.dupe_count or 1) or 1) >= MAX_RESONANCE),
        "divine_items": (db.query(InventoryItem)
                         .filter_by(player_id=player.id, rarity=Rarity.DIVINE).count()),

        # ---- competition
        "challenge_wins": int(player.challenge_wins or 0),
        "dojo_published": (db.query(DojoChallenge)
                           .filter_by(author_id=player.id, published=True).count()),
        "dojo_clears": (db.query(DojoClear)
                        .filter_by(player_id=player.id).count()),

        # ---- dedication
        "daily_streak": int(player.daily_streak or 0),
        "prestige_count": int(player.prestige_count or 0),
    }


def earned_ids(db, player, values: dict[str, int] | None = None) -> set[str]:
    """Every achievement this player currently qualifies for."""
    values = values if values is not None else metrics(db, player)
    return {a.id for a in cfg.ACHIEVEMENTS
            if values.get(a.metric, 0) >= a.threshold}


def sync(db, player) -> list[cfg.Achievement]:
    """Record newly-earned achievements. Returns what is NEW this call.

    Only ever inserts -- see the model docstring on why nothing is
    revoked. Called from the screens that display achievements rather
    than from gameplay, which means "when did I earn this" is really
    "when was it first noticed". That is a deliberate trade for not
    threading calls through every system in the game, and the only place
    it shows is a timestamp.
    """
    from bot.database.models.achievement_model import PlayerAchievement

    qualifying = earned_ids(db, player)
    already = {row.achievement_id for row in
               db.query(PlayerAchievement).filter_by(player_id=player.id).all()}

    fresh = sorted(qualifying - already)
    for achievement_id in fresh:
        db.add(PlayerAchievement(player_id=player.id, achievement_id=achievement_id))
    if fresh:
        db.commit()
    return [cfg.BY_ID[i] for i in fresh if i in cfg.BY_ID]


def earned_rows(db, player) -> dict[str, dt.datetime]:
    """achievement_id -> when it was recorded."""
    from bot.database.models.achievement_model import PlayerAchievement

    return {row.achievement_id: row.earned_at
            for row in db.query(PlayerAchievement).filter_by(player_id=player.id).all()}


# ----------------------------------------------------------------------
# Titles
# ----------------------------------------------------------------------

def available_titles(db, player) -> list[str]:
    """Titles this player has unlocked, in config order."""
    earned = earned_ids(db, player)
    return [a.title for a in cfg.ACHIEVEMENTS if a.title and a.id in earned]


def set_title(db, player, title: str | None) -> tuple[bool, str]:
    """Equip a title, or clear it with None.

    RE-CHECKED AGAINST WHAT THEY HAVE EARNED, every time. The title
    arrives from a select whose options were rendered from a state that
    may be minutes old, and a component value is client-supplied -- so
    the list that built the menu is a hint, not a permission.
    """
    if title is None:
        player.active_title = None
        db.commit()
        return True, "Title cleared."
    if title not in available_titles(db, player):
        return False, "You haven't earned that title."
    player.active_title = title
    db.commit()
    return True, f"You are now **{title}**."


def display_name(player) -> str:
    """Username with the equipped title, for profiles and leaderboards."""
    name = player.username or str(player.id)
    title = (player.active_title or "").strip()
    return f"{name} — {title}" if title else name


# ----------------------------------------------------------------------
# Collection
# ----------------------------------------------------------------------

def collection(db, player) -> dict:
    """Character and card completion.

    DELIBERATELY NOT AN ENEMY BESTIARY. Nothing in the game records which
    enemies a player has fought, and adding it would mean a write at
    every one of the seven places a battle can start -- story, dungeon,
    domains, abyss, raids, challenges and the dojo. Seven call sites for
    one counter is exactly the shape that ends up with six of them
    working, so collection covers what ownership already answers.
    """
    values = metrics(db, player)
    characters = values["characters_owned"], values["characters_total"]
    cards = values["cards_owned"], values["cards_total"]

    def pct(owned: int, total: int) -> float:
        return (owned / total * 100) if total else 0.0

    return {
        "characters": {"owned": characters[0], "total": characters[1],
                       "percent": pct(*characters)},
        "cards": {"owned": cards[0], "total": cards[1], "percent": pct(*cards)},
        "missions": {"owned": values["missions_completed"], "total": 48,
                     "percent": pct(values["missions_completed"], 48)},
        "regions": {"owned": values["regions_cleared"], "total": 6,
                    "percent": pct(values["regions_cleared"], 6)},
        "abyss": {"owned": values["abyss_stars"], "total": 36,
                  "percent": pct(values["abyss_stars"], 36)},
    }


def summary(db, player) -> dict:
    """Everything the /achievements screen needs, in one pass."""
    values = metrics(db, player)
    earned = earned_ids(db, player, values)
    rows = earned_rows(db, player)
    return {
        "metrics": values,
        "earned": earned,
        "earned_at": rows,
        "total": len(cfg.ACHIEVEMENTS),
        "by_category": cfg.by_category(),
        "collection": collection(db, player),
        "titles": [a.title for a in cfg.ACHIEVEMENTS if a.title and a.id in earned],
    }
