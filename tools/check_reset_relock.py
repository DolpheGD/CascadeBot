"""
A reset account stays locked out of the game, even after a migration runs.

    python -m tools.check_reset_relock

WHY THIS EXISTS, AND WHY THE OTHER CHECKS MISSED IT.

The reset was verified by asking story_service whether each feature was
unlocked, immediately after wiping an account. It answered 0/15 and that
looked like proof. It was proof of the wrong thing: it tested the gate in
isolation, at one instant, on a database nothing else had touched since.

In practice the reset is followed by a deploy, and the deploy runs
tools/migrate_db.py. Its grandfather_story step exists to stop veterans
being locked out of their own inventory, and it identifies a veteran as
"a player with no PlayerStory row". The reset signalled a wipe by
DELETING that row. So the two steps used one representation for two
opposite meanings -- "veteran to protect" and "just wiped, start over" --
and the one that ran last won:

    after the reset      0/15 features unlocked
    after migrate_db    15/15 features unlocked

Neither component was wrong when read on its own, which is exactly why
reading them on their own found nothing. The bug only exists in the
ORDER, so the check has to run the order.

WHAT IS ASSERTED

  * a wiped account has no features, before anything else runs
  * it STILL has none after migrate_db, which is the regression
  * the story is reachable -- relocking everything is only correct if
    the way back in is open, otherwise the account is bricked
  * a genuine pre-story veteran is still grandfathered, because the
    fix must not break the lockout protection it sits next to
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

FEATURE_PROBE = r"""
import sys, os; sys.path.insert(0, ".")
import bot.config as cfg; cfg.DATABASE_URL = os.environ["DATABASE_URL"]
from bot.database.db_init import init_db; init_db()
from bot.database.session import SessionLocal
from bot.database.models.player_model import Player
from bot.services import story_service
import bot.game.story.story_config as sc
db = SessionLocal()
for player in db.query(Player).all():
    unlocked = sum(1 for f in sc.FEATURES if story_service.feature_unlocked(db, player, f))
    reachable = story_service.next_mission(db, player) is not None
    print(f"{player.username}|{unlocked}|{len(sc.FEATURES)}|{reachable}")
db.close()
"""

SEED = r"""
import sys, os; sys.path.insert(0, ".")
import bot.config as cfg; cfg.DATABASE_URL = os.environ["DATABASE_URL"]
from bot.database.db_init import init_db; init_db()
from bot.database.session import SessionLocal
from bot.services import (player_service, character_template_service,
                          character_service)
from bot.database.models.character_model import CharacterTemplate, PlayerCharacter
from bot.database.models.story_model import PlayerStory
db = SessionLocal()
character_template_service.ensure_character_templates_seeded(db)
templates = db.query(CharacterTemplate).filter_by(is_player_avatar=False).all()

# A veteran the ORIGINAL story migration grandfathered: exactly the shape
# tools/migrate_db.py leaves behind.
veteran = player_service.get_or_create_player(db, 1, "Veteran")
character_service.ensure_avatar_character(db, veteran)
for t in templates[:12]:
    db.add(PlayerCharacter(player_id=veteran.id, template_id=t.id,
                           level=40, talents=[], dupe_count=1))
veteran.level = 25
db.add(PlayerStory(player_id=veteran.id, flags=[], completed_missions=[],
                   prologue_complete=True, grandfathered=True))

db.commit(); db.close()
"""

# A genuine pre-story account: a Player row and NO story row at all,
# which is the exact shape grandfather_story was written to rescue. It
# lives in its own database because the reset wipes every player in the
# one it is pointed at, so a control account cannot share a file with
# the account being reset.
SEED_PRESTORY = r"""
import sys, os; sys.path.insert(0, ".")
import bot.config as cfg; cfg.DATABASE_URL = os.environ["DATABASE_URL"]
from bot.database.db_init import init_db; init_db()
from bot.database.session import SessionLocal
from bot.services import (player_service, character_template_service,
                          character_service)
from bot.database.models.character_model import CharacterTemplate, PlayerCharacter
db = SessionLocal()
character_template_service.ensure_character_templates_seeded(db)
templates = db.query(CharacterTemplate).filter_by(is_player_avatar=False).all()
keeper = player_service.get_or_create_player(db, 2, "PreStory")
character_service.ensure_avatar_character(db, keeper)
for t in templates[:8]:
    db.add(PlayerCharacter(player_id=keeper.id, template_id=t.id,
                           level=30, talents=[], dupe_count=1))
keeper.level = 18
db.commit(); db.close()
"""


def _run(code: str, url: str) -> str:
    env = {**os.environ, "DATABASE_URL": url, "PYTHONDONTWRITEBYTECODE": "1"}
    result = subprocess.run([sys.executable, "-c", code], capture_output=True,
                            text=True, env=env, cwd=".")
    if result.returncode != 0:
        raise RuntimeError(result.stderr[-2000:])
    return result.stdout


def _probe(path: str) -> dict[str, tuple[int, int, bool]]:
    """Measure feature access WITHOUT touching the database under test.

    THE PROBE MUTATES. story_service.feature_unlocked calls get_or_create,
    which writes a PlayerStory row if none exists. Reading the gate is
    therefore a write, and that quietly destroyed the whole point of this
    check: probing between the reset and migrate_db created the very row
    whose absence causes the bug, so grandfather_story took its "already
    has a row" branch and the check reported a clean 0/15 while the real
    sequence -- reset, deploy, no probe in between -- still handed back
    all 15 features.

    The check was measuring a state its own measurement had repaired.
    Confirmed by reintroducing the bug: manual runs reproduced 15/15 and
    this check kept passing.

    So every probe runs against a COPY. The database under test is only
    ever advanced by the real tools, in the real order, and observing it
    cannot change it.
    """
    scratch = path + ".probe"
    shutil.copy(path, scratch)
    try:
        out = {}
        for line in _run(FEATURE_PROBE, f"sqlite:///{scratch}").strip().splitlines():
            name, unlocked, total, reachable = line.rsplit("|", 3)
            out[name] = (int(unlocked), int(total), reachable == "True")
        return out
    finally:
        for suffix in ("", "-wal", "-shm"):
            if os.path.exists(scratch + suffix):
                os.remove(scratch + suffix)


def _tool(module: str, url: str, *args: str) -> None:
    """Run a migration tool, and INSIST it succeeded.

    The return code was originally ignored, which made this check
    incapable of failing. Both steps it runs grant features on success
    and grant nothing on a crash -- so a crashed migrate_db produced "the
    wiped account has 0/15 features", which is precisely the result the
    check treats as correct. Verified by deliberately reintroducing the
    original bug: the check passed anyway, because the tool never ran.

    A harness that reports success when its subject never executed is
    worse than no harness, because it is trusted.
    """
    env = {**os.environ, "DATABASE_URL": url, "PYTHONDONTWRITEBYTECODE": "1"}
    result = subprocess.run([sys.executable, "-m", module, *args],
                            capture_output=True, text=True, env=env, cwd=".")
    if result.returncode != 0:
        raise RuntimeError(
            f"{module} exited {result.returncode} -- this check is meaningless "
            f"if the tool it is checking did not run:\n{result.stderr[-2000:]}")


def main() -> int:
    failures: list[str] = []

    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "relock.db")
        url = f"sqlite:///{path}"

        _run(SEED, url)
        before = _probe(path)
        if before["Veteran"][0] != before["Veteran"][1]:
            failures.append(
                f"the fixture is wrong -- a grandfathered veteran should start with "
                f"every feature, not {before['Veteran'][0]}/{before['Veteran'][1]}")

        # Only the veteran is reset. Untouched keeps everything.
        _tool("tools.reset_and_compensate", url, "--apply")
        after_reset = _probe(path)

        wiped = next(n for n in after_reset if n.startswith("Veteran"))
        unlocked, total, reachable = after_reset[wiped]
        if unlocked:
            failures.append(
                f"straight after the reset the wiped account still has "
                f"{unlocked}/{total} features")
        if not reachable:
            failures.append(
                "the wiped account has no next story mission -- relocking every "
                "feature is only correct if the way back in is open, and this "
                "account is bricked rather than reset")

        # THE REGRESSION. A deploy runs this; it must change nothing.
        _tool("tools.migrate_db", url)
        after_migrate = _probe(path)

        unlocked_after, total_after, reachable_after = after_migrate[wiped]
        if unlocked_after:
            failures.append(
                f"migrate_db re-granted {unlocked_after}/{total_after} features to a "
                f"wiped account -- grandfather_story is reading a missing story row "
                f"as 'predates story mode' when it now also means 'just reset'")
        if not reachable_after:
            failures.append(
                "after migrate_db the wiped account can no longer reach the story")

        # THE PROTECTION THIS SITS NEXT TO MUST STILL WORK.
        #
        # Separate database on purpose. Skipping reset accounts is one
        # `if` away from skipping everybody, and a grandfather_story that
        # quietly stops grandfathering is a worse bug than the one being
        # fixed -- it locks established players out of their own
        # inventory, which is the thing that function exists to prevent.
        pre_path = os.path.join(tmp, "prestory.db")
        pre_url = f"sqlite:///{pre_path}"
        _run(SEED_PRESTORY, pre_url)
        _tool("tools.migrate_db", pre_url)
        keeper_unlocked, keeper_total, _ = _probe(pre_path)["PreStory"]
        if keeper_unlocked != keeper_total:
            failures.append(
                f"a genuine pre-story veteran came out of migrate_db with "
                f"{keeper_unlocked}/{keeper_total} features -- the reset-skip has "
                f"broken the lockout protection it was added beside")

        print(f"{'stage':<30}{'wiped account':>16}")
        print("-" * 46)
        for label, snap in (("seeded (grandfathered)", before),
                            ("after reset", after_reset),
                            ("after migrate_db", after_migrate)):
            w = next(v for k, v in snap.items() if k.startswith("Veteran"))
            print(f"{label:<30}{f'{w[0]}/{w[1]}':>16}")
        print(f"\nstory reachable for the wiped account : {after_migrate[wiped][2]}")
        print(f"pre-story veteran (separate db)       : "
              f"{keeper_unlocked}/{keeper_total} features kept")

    if failures:
        print()
        for failure in failures:
            print(f"  FAIL  {failure}")
        return 1
    print("\nOK -- a reset account stays locked and can still reach the story, "
          "and untouched veterans keep their features.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
