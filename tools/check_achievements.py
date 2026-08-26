"""
Every achievement is earnable, and every title has a way to get it.

    python -m tools.check_achievements

THE FAILURE THIS CATCHES IS AN ACHIEVEMENT NOBODY CAN EVER EARN.

It is silent by construction. An achievement whose threshold is above
anything the game can produce -- "own 40 characters" when there are 35,
"earn 40 Abyss stars" when there are 36 -- renders perfectly, shows
sensible progress, and simply never completes. Nobody reports it, because
from the outside it is indistinguishable from not having got there yet.
The player just quietly stops believing the list means anything.

So every threshold is checked against the REAL ceiling for its metric,
computed from the game's own content rather than from a number typed
here. Add a character and the roster ceiling moves on its own.

ALSO ASSERTED

  * every metric an achievement names is one metrics() actually returns.
    A typo'd metric key reads as 0 forever, which is the same invisible
    failure wearing a different hat.
  * a brand-new player earns nothing, and a fully-progressed one earns
    everything that content allows. Both ends, because a condition that
    is accidentally always-true is as broken as one that is never true.
  * sync() is idempotent -- running it twice does not duplicate rows or
    re-announce anything.
  * every title is attached to an achievement, and a title nobody has
    earned cannot be equipped. The equip path is re-checked server-side
    because the select that offers it is client-supplied.
"""

from __future__ import annotations

import os
import sys
import tempfile


def main() -> int:
    sys.path.insert(0, ".")
    os.environ.setdefault(
        "DATABASE_URL", "sqlite:///" + tempfile.mktemp(suffix=".db"))
    import bot.config as cfg
    cfg.DATABASE_URL = os.environ["DATABASE_URL"]

    from bot.database.db_init import init_db
    init_db()
    from bot.database.session import SessionLocal
    from bot.game.achievements import achievement_config as ac
    from bot.services import achievement_service as A
    from bot.services import (card_service, character_service,
                              character_template_service, player_service)

    failures: list[str] = []
    db = SessionLocal()
    character_template_service.ensure_character_templates_seeded(db)
    card_service.ensure_card_templates_seeded(db)

    # ---- the real ceiling for every bounded metric -------------------
    from bot.database.models.card_model import CardTemplate
    from bot.database.models.character_model import CharacterTemplate, LEVEL_CAP
    from bot.game.abyss import abyss_config as abc
    from bot.game.dungeon.region_config import ordered_regions
    from bot.game.economy.resonance_config import MAX_RESONANCE
    import bot.game.story.story_config as sc

    missions = sum(len(ch.get("missions", [])) for ch in sc.CHAPTERS)
    ceilings = {
        "characters_owned": db.query(CharacterTemplate).count(),
        "cards_owned": db.query(CardTemplate).count(),
        "missions_completed": missions,
        "regions_cleared": len(ordered_regions()),
        "abyss_stars": len(abc.FLOORS) * abc.MAX_STARS_PER_FLOOR,
        "highest_character_level": LEVEL_CAP,
        "prologue_complete": 1,
        "max_resonance_characters": db.query(CharacterTemplate).count(),
    }

    valid_metrics = set(A.metrics(db, player_service.get_or_create_player(
        db, 60_001, "MetricProbe")))

    for achievement in ac.ACHIEVEMENTS:
        if achievement.metric not in valid_metrics:
            failures.append(
                f"'{achievement.id}' uses metric {achievement.metric!r}, which "
                f"metrics() does not return -- it will read as 0 forever")
            continue
        ceiling = ceilings.get(achievement.metric)
        if ceiling is not None and achievement.threshold > ceiling:
            failures.append(
                f"'{achievement.id}' needs {achievement.threshold} "
                f"{achievement.metric} but the game only contains {ceiling} "
                f"-- it can never be earned")

    # ---- titles ------------------------------------------------------
    for title, achievement in ac.TITLES.items():
        if achievement not in ac.ACHIEVEMENTS:
            failures.append(f"title {title!r} is not attached to a real achievement")
    if len(ac.TITLES) != len({a.title for a in ac.ACHIEVEMENTS if a.title}):
        failures.append("two achievements grant the same title")

    # ---- a brand-new player earns nothing -----------------------------
    fresh = player_service.get_or_create_player(db, 60_002, "Fresh")
    character_service.ensure_avatar_character(db, fresh)
    earned_fresh = A.earned_ids(db, fresh)
    if earned_fresh:
        failures.append(
            f"a brand-new player already qualifies for {sorted(earned_fresh)} "
            f"-- a condition is accidentally always true")

    # ---- a maxed player earns everything content allows ---------------
    from bot.database.models.abyss_model import PlayerAbyss
    from bot.database.models.character_model import PlayerCharacter
    from bot.database.models.expedition_model import Expedition, ExpeditionStatus
    from bot.database.models.story_model import PlayerStory
    from bot.database.models.card_model import PlayerCard

    maxed = player_service.get_or_create_player(db, 60_003, "Maxed")
    character_service.ensure_avatar_character(db, maxed)
    for template in db.query(CharacterTemplate).all():
        if not db.query(PlayerCharacter).filter_by(
                player_id=maxed.id, template_id=template.id).first():
            db.add(PlayerCharacter(player_id=maxed.id, template_id=template.id,
                                   level=LEVEL_CAP, talents=[], dupe_count=MAX_RESONANCE + 1,
                                   evolution_stage=1))
    for card in db.query(CardTemplate).all():
        db.add(PlayerCard(player_id=maxed.id, template_id=card.id))
    db.add(PlayerStory(player_id=maxed.id, flags=[], prologue_complete=True,
                       completed_missions=[f"m{i}" for i in range(missions)]))
    db.add(PlayerAbyss(player_id=maxed.id, stars=ceilings["abyss_stars"]))
    for region in ordered_regions() * 20:
        db.add(Expedition(player_id=maxed.id, region=region,
                          status=ExpeditionStatus.COMPLETED, graph={}))
    maxed.challenge_wins = 999
    maxed.daily_streak = 999
    maxed.prestige_count = 99
    db.commit()

    # Everything except what needs another player or a Divine drop.
    NEEDS_OTHERS = {"dojo_built", "dojo_cleared", "divine_item"}
    earned_maxed = A.earned_ids(db, maxed)
    unreachable = {a.id for a in ac.ACHIEVEMENTS} - earned_maxed - NEEDS_OTHERS
    if unreachable:
        failures.append(
            f"a fully-progressed player still cannot earn {sorted(unreachable)} "
            f"-- check the threshold against what the game can produce")

    # ---- sync is idempotent ------------------------------------------
    first = A.sync(db, maxed)
    second = A.sync(db, maxed)
    if not first:
        failures.append("sync recorded nothing for a fully-progressed player")
    if second:
        failures.append(
            f"sync re-announced {len(second)} achievements on a second call "
            f"-- every screen open would claim they were just earned")

    # ---- titles cannot be forged -------------------------------------
    ok, _ = A.set_title(db, fresh, next(iter(ac.TITLES)))
    if ok:
        failures.append("a player equipped a title they had not earned")
    ok, _ = A.set_title(db, maxed, "Abyssal")
    if not ok:
        failures.append("a player could not equip a title they HAD earned")
    if "Abyssal" not in A.display_name(maxed):
        failures.append("an equipped title does not appear in display_name")

    db.close()

    print(f"achievements : {len(ac.ACHIEVEMENTS)} across "
          f"{len(ac.by_category())} categories")
    print(f"titles       : {len(ac.TITLES)}")
    print("ceilings     : " + ", ".join(f"{k}={v}" for k, v in sorted(ceilings.items())))
    print(f"maxed player : earns {len(earned_maxed)}/{len(ac.ACHIEVEMENTS)} "
          f"({len(NEEDS_OTHERS)} need other players or a Divine drop)")

    if failures:
        print()
        for failure in failures:
            print(f"  FAIL  {failure}")
        return 1
    print("\nOK -- every achievement is earnable and every title has a source.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
