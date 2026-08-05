"""
Catch the bugs that importing a module cannot.

    python -m tools.check_runtime

Two failures shipped on the same day and neither was catchable by
anything already in tools/:

  * `/start` raised `NameError: name 'story_service' is not defined` --
    the module imported fine, because the missing import was only read
    inside a function body.
  * `_apply_gain` read a `difficulty` local that has never existed in
    its scope, so every encounter granting {"item": "natural"} crashed
    -- a crash on a REWARD, mid-run, after the player had already spent
    the time to earn it.

`compileall` passes both (they're valid syntax). Importing every module
passes both (the bad line never executes at import). `check_encounters`
passes the second one because it reads the config as data and never
calls the interpreter. The common shape is: valid code, valid data, and
a code path nothing exercises until a player walks onto it.

So this checker does the two things the others don't:

  1. UNDEFINED NAMES -- pyflakes over the whole tree, which finds a name
     read but never bound regardless of how deep in a function it is.
     Unused imports and unused locals are ignored on purpose; they're
     style, not breakage, and a checker that cries about them gets
     muted.
  2. ACTUAL EXECUTION -- every encounter outcome in the game is run
     against a real (temporary) database with a real player. Not
     inspected: run. If interpreting an outcome raises, this fails,
     which is precisely the guarantee check_encounters cannot give.

Failing to import pyflakes is not a failure here -- it's an optional
dependency and the execution pass is the load-bearing half.
"""

from __future__ import annotations

import random
import sys
import tempfile
import traceback

# Style-only pyflakes messages. Everything else is treated as a real
# finding, so a NEW class of pyflakes warning surfaces rather than being
# silently swallowed by an allowlist that was never revisited.
_IGNORED_SUBSTRINGS = (
    "imported but unused",
    "unable to detect undefined names",
    "redefinition of unused",
    "is assigned to but never used",
    "from __future__ imports must occur",
)


def _undefined_names() -> list[str]:
    try:
        from pyflakes.api import checkRecursive
        from pyflakes.reporter import Reporter
    except ImportError:
        print("names      : SKIPPED (pip install pyflakes to enable)")
        return []

    import io

    out, err = io.StringIO(), io.StringIO()
    checkRecursive(["bot", "tools"], Reporter(out, err))
    findings = [
        line for line in out.getvalue().splitlines()
        if line.strip() and not any(s in line for s in _IGNORED_SUBSTRINGS)
    ]
    print(f"names      : {len(findings)} real finding(s) across bot/ + tools/")
    return findings


def _execute_every_outcome() -> list[str]:
    """Run every outcome block in every encounter for real.

    Uses a throwaway SQLite file and one throwaway player. Gold, items
    and materials really are granted -- that's the point, since the
    crash being guarded against happened inside the granting code.
    """
    from sqlalchemy.orm import sessionmaker

    from bot.database.db import engine
    from bot.database.db_init import init_db
    from bot.database.models.enums import Rarity
    from bot.database.models.player_model import Player
    from bot.game.dungeon.encounter_config import ENCOUNTERS
    from bot.services import dungeon_service, item_template_service, lootbox_service

    init_db()
    db = sessionmaker(bind=engine)()
    # Seed EVERY catalog an outcome can reach. A missing catalog shows up
    # as "No lootbox template for tier 'common'", which reads exactly like
    # a content bug and isn't one -- same trap as the stub Expedition.
    item_template_service.ensure_item_templates_seeded(db)
    lootbox_service.ensure_lootbox_templates_seeded(db)
    player = Player(id=1, username="runtime-check", gold=10**9, shards=10**9)
    db.add(player)
    db.commit()

    # A REAL Expedition row and a REAL squad, not stubs.
    #
    # The first version of this checker used a hand-written stand-in and
    # it "failed" 40-odd encounters -- every one of them because the stub
    # lacked `loot_ledger` or the player had no squad. That is a checker
    # bug reported as a game bug, which is worse than no checker: it
    # trains you to skim the output. Building the real objects costs a
    # few lines and makes every failure printed here a genuine one.
    from bot.database.models.expedition_model import Expedition
    from bot.services import character_service, character_template_service

    character_template_service.ensure_character_templates_seeded(db)
    avatar = character_template_service.get_avatar_template(db)
    pc, _, _ = character_service.grant_character(db, player, avatar)
    character_service.set_squad_slot(db, player, 0, pc)
    db.commit()

    def fresh_expedition() -> Expedition:
        exp = Expedition(
            player_id=player.id,
            region="glacier",
            graph={"nodes": {}},
            loot_ledger={},
            relics=[],
        )
        db.add(exp)
        db.flush()
        return exp

    failures: list[str] = []
    outcomes_run = 0

    def collect(encounter: dict) -> list[tuple[str, dict]]:
        found: list[tuple[str, dict]] = []
        name = encounter.get("id", encounter.get("name", "?"))
        for choice in encounter.get("choices", []) or []:
            label = f"{name}/{choice.get('id', '?')}"
            for key in ("on_success", "on_fail", "outcome"):
                if isinstance(choice.get(key), dict):
                    found.append((f"{label}:{key}", choice[key]))
            for tier in choice.get("tiers", []) or []:
                if isinstance(tier.get("outcome"), dict):
                    found.append((f"{label}:tier", tier["outcome"]))
        return found

    # Seeded so a failure is reproducible, and looped so probabilistic
    # branches (bonus rolls, gamble tiers) actually get taken.
    for seed in range(12):
        rng = random.Random(seed)
        for encounter in ENCOUNTERS:
            for label, outcome in collect(encounter):
                outcomes_run += 1
                try:
                    dungeon_service._apply_outcome(
                        db, player, rng, outcome, 1.0, fresh_expedition(),
                        max_item_rarity=Rarity.LEGENDARY,
                        item_level=1,
                        rarity_weight_bonus=130,
                    )
                except Exception as exc:  # noqa: BLE001 -- reporting, not handling
                    failures.append(
                        f"{label} raised {type(exc).__name__}: {exc}\n"
                        + "".join(traceback.format_exc(limit=3).splitlines(True)[-3:])
                    )
                db.rollback()

    print(f"outcomes   : {outcomes_run} executed against a real database")
    return failures


def main() -> int:
    import os

    os.environ.setdefault("DATABASE_URL", "sqlite:///" + tempfile.mktemp(suffix=".db"))

    failures = _undefined_names() + _execute_every_outcome()

    print()
    if failures:
        for line in dict.fromkeys(failures):
            print(f"  FAIL  {line}")
        return 1
    print("OK -- no undefined names, and every encounter outcome ran without raising.")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, ".")
    sys.exit(main())
