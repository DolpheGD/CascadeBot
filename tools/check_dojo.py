"""
The dojo cannot be farmed, and cannot be used to reach another player.

    python -m tools.check_dojo

USER-GENERATED CONTENT IS A DIFFERENT KIND OF RISK to everything else in
this game. Every other system fails in front of the person who triggered
it. This one lets one player put text and fights in front of STRANGERS,
and pays out for clearing them -- so its failure modes are somebody
else's problem, and they are the two oldest problems in the genre:

  1. THE FARM. Author-controlled content plus rewards is an XP printer
     unless something stops it. The specific exploit is not subtle:
     publish the weakest thing the validator permits, clear it in one
     turn, repeat. Three separate things have to hold, and this asserts
     all three rather than trusting any one of them:

        * a daily cap on rewarded clears
        * XP scaled to what the challenge actually FIELDS, so the
          cheapest build is also the worst-paying
        * authors are not paid for their own challenges at all

  2. THE INJECTION. A challenge name is rendered in somebody else's
     Discord client. Backticks and asterisks reformat the message,
     @everyone pings a server, and a URL turns a challenge listing into
     a link somebody did not ask for. The allowlist is what stops all of
     that, and it is asserted here against the real strings people try.

Also asserted: an author cannot exceed the build limits, a challenge
whose enemies no longer exist refuses to start instead of raising, and a
challenge taken down by the owner cannot be republished by its author.
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
    from bot.game.economy import dojo_config as dc
    from bot.services import (character_service, character_template_service,
                              dojo_service, player_service)

    failures: list[str] = []
    db = SessionLocal()
    character_template_service.ensure_character_templates_seeded(db)

    author = player_service.get_or_create_player(db, 70_001, "Author")
    visitor = player_service.get_or_create_player(db, 70_002, "Visitor")
    for player in (author, visitor):
        character_service.ensure_avatar_character(db, player)

    # ---- 1. text that must never reach another player's client -------
    HOSTILE = [
        ("**bold**", "markdown"),
        ("`code`", "backticks"),
        ("@everyone", "mention"),
        ("<@70001>", "user mention"),
        ("https://example.com", "url"),
        ("||spoiler||", "spoiler pipes"),
        ("#channel", "channel reference"),
    ]
    for text, label in HOSTILE:
        try:
            dojo_service.clean_text(text, dc.MAX_NAME_LENGTH, "name")
            failures.append(
                f"a challenge name containing {label} ({text!r}) was ACCEPTED -- "
                f"that renders in another player's client")
        except dojo_service.DojoError:
            pass

    # WHITESPACE IS NORMALISED, NOT REFUSED, and that distinction is
    # deliberate. A newline in a name is dangerous because it breaks the
    # layout of a list somebody else is reading -- but refusing the whole
    # name over it would be hostile to someone who pasted from a text
    # editor. clean_text collapses runs of whitespace the same way the
    # avatar rename does, so the newline never survives to be rendered.
    #
    # The first version of this check asserted REFUSAL and failed against
    # correct code. What matters is the output, so that is what is
    # checked.
    for text, label in (("line\nbreak", "newline"),
                        ("tab\tseparated", "tab"),
                        ("lots     of   spaces", "repeated spaces")):
        cleaned = dojo_service.clean_text(text, dc.MAX_NAME_LENGTH, "name") or ""
        if any(ch in cleaned for ch in "\n\r\t") or "  " in cleaned:
            failures.append(
                f"a name containing a {label} survived cleaning as {cleaned!r} -- "
                f"it would break the layout of a list other players read")

    # And ordinary names must still work, or the filter is useless.
    for good in ("Three Wraiths", "Josh's Revenge", "Hard mode - no healer!",
                 "Level 40, good luck."):
        try:
            dojo_service.clean_text(good, dc.MAX_NAME_LENGTH, "name")
        except dojo_service.DojoError as exc:
            failures.append(f"a reasonable name {good!r} was refused: {exc}")

    # ---- 2. build limits ---------------------------------------------
    usable = dojo_service.known_enemy_names()
    if not usable:
        failures.append("no enemies are buildable at all")

    from bot.game.combat.enemies import ENEMY_TEMPLATES
    roles = {t["name"]: t.get("role") for t in ENEMY_TEMPLATES}
    leaked = [n for n in usable if roles.get(n) not in ("combat", "elite")]
    if leaked:
        failures.append(
            f"bosses/escorts are buildable: {leaked[:3]} -- they are balanced "
            f"around a full run, not an author-chosen level")

    over = [{"enemy": usable[0], "count": dc.MAX_COUNT_PER_STACK + 1}]
    try:
        dojo_service.validate_enemies(over)
        failures.append("a stack over MAX_COUNT_PER_STACK was accepted")
    except dojo_service.DojoError:
        pass

    # ---- 3. the farm -------------------------------------------------
    cheapest = dc.xp_for_clear([{"enemy": usable[0], "count": 1}], dc.MIN_LEVEL, False)
    dearest = dc.xp_for_clear(
        [{"enemy": usable[0], "count": dc.MAX_COUNT_PER_STACK},
         {"enemy": usable[1], "count": dc.MAX_TOTAL_ENEMIES - dc.MAX_COUNT_PER_STACK}],
        dc.MAX_LEVEL, False)
    if cheapest >= dearest:
        failures.append(
            f"the cheapest possible challenge pays {cheapest} and the dearest "
            f"pays {dearest} -- with a daily cap, that makes the most trivial "
            f"build the correct one")

    challenge = dojo_service.create_challenge(
        db, author, "Farm Test", [{"enemy": usable[0], "count": 1}], dc.MIN_LEVEL)
    dojo_service.set_published(db, author, challenge, True)

    def force_clear(player):
        battle = dojo_service.start(db, player, challenge)
        for enemy in battle.enemies:
            enemy.current_hp = 0
        battle.result = "won"
        dojo_service._ACTIVE_BATTLES[player.id] = battle
        return dojo_service.finish(db, player)

    own = force_clear(author)
    if own["xp"] or own["paid"]:
        failures.append(
            f"the AUTHOR was paid {own['xp']} XP for clearing their own challenge "
            f"-- that is the entire exploit in one move")

    paid_clears = 0
    total_xp = 0
    for _ in range(dc.REWARDED_CLEARS_PER_DAY + 5):
        result = force_clear(visitor)
        paid_clears += 1 if result["paid"] else 0
        total_xp += result["xp"]
    if paid_clears > dc.REWARDED_CLEARS_PER_DAY:
        failures.append(
            f"{paid_clears} clears were paid against a cap of "
            f"{dc.REWARDED_CLEARS_PER_DAY}")

    # The whole point: a day of farming the cheapest build is negligible.
    if total_xp > dc.max_daily_xp():
        failures.append(
            f"a day of farming paid {total_xp} XP, above the declared ceiling "
            f"of {dc.max_daily_xp()}")

    # ---- 4. a stale challenge refuses rather than raising ------------
    challenge.enemies = [{"enemy": "An Enemy That Was Deleted", "count": 1}]
    db.commit()
    try:
        dojo_service.resolve_enemies(challenge)
        failures.append("a challenge naming a non-existent enemy resolved anyway")
    except dojo_service.DojoError:
        pass
    except Exception as exc:
        failures.append(
            f"a stale challenge raised {type(exc).__name__} instead of a "
            f"DojoError -- that surfaces as a crash to whoever clicked it")

    # ---- 5. a takedown sticks ---------------------------------------
    dojo_service.take_down(db, challenge)
    try:
        dojo_service.set_published(db, author, challenge, True)
        failures.append(
            "an author republished a challenge the owner had taken down")
    except dojo_service.DojoError:
        pass

    db.close()

    print(f"buildable  : {len(usable)} enemies (bosses and escorts excluded)")
    print(f"limits     : {dc.MAX_TOTAL_ENEMIES} enemies, levels "
          f"{dc.MIN_LEVEL}-{dc.MAX_LEVEL}, {dc.MAX_CHALLENGES_PER_AUTHOR} per author")
    print(f"payout     : cheapest {cheapest} XP, dearest {dearest} XP, "
          f"daily ceiling {dc.max_daily_xp()}")
    print(f"farm test  : {paid_clears} paid clears, {total_xp} XP for a day of "
          f"grinding the cheapest build")
    print(f"text       : {len(HOSTILE)} hostile strings refused")

    if failures:
        print()
        for failure in failures:
            print(f"  FAIL  {failure}")
        return 1
    print("\nOK -- the dojo can't be farmed and can't reach another player's client.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
