"""
After the reset, a player's wallet is EXACTLY their compensation.

    python -m tools.check_reset_balances

THE BUG THIS EXISTS FOR.

The reset added the compensation to whatever the player was already
holding instead of replacing it. On the live run that produced an account
with 241,000 gold against a curve whose ceiling is 45,000: roughly
236,000 of held gold, plus the 5,000 floor. The only part the reset
actually decided was the floor.

Nothing caught it because every existing check reasoned about the PAYOUT.
tools/check_compensation.py verifies the curve pays everyone, preserves
order, compresses the spread and stays bounded -- and all of that was
true. The payout was correct. It was simply not what ended up in the
player's wallet, and no check had ever compared the two.

That gap also silently disabled two features built on top of the payout:

  * the saturating curve bounds what anybody carries into the fresh
    start, which does nothing while an unbounded balance survives beside
    it
  * the authenticity discount exists to stop granted hoards carrying
    over, and the granted hoard IS the held balance

So both of those were passing their own checks while having no effect,
which is the same "presence is not effect" failure in a new place.

WHAT IS ASSERTED

  * every compensated currency ends at exactly its payout, not payout
    plus whatever was there before
  * a rich account and a poor account with IDENTICAL progress come out
    with IDENTICAL balances -- the sharpest form of the above, since it
    fails loudly if any part of the old wallet leaks through
  * uncompensated resources (materials, echoes, reroll tokens) end at
    zero
  * no numeric Player column is left unclassified. A new currency added
    later is a new way to smuggle a hoard through the reset, and the
    only reliable defence is to fail on anything nobody has thought
    about yet.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile

# Columns that are numeric but are not wealth or progress, so the reset
# is right to leave them (or to handle them elsewhere). Listed so that
# anything NOT here and not in WIPED_RESOURCES/RESET_TO_DEFAULT fails.
NOT_A_RESOURCE = {
    # identity and gating
    "id", "discord_id", "level", "xp",
    # gacha pity -- reset by _wipe_progress's explicit block
    "pity_since_five_star", "pity_since_four_star",
    "card_pity_since_five_star", "card_pity_since_four_star",
    # challenge and dojo bookkeeping -- reset by _wipe_progress
    "challenge_power", "challenge_wins", "challenge_losses",
    "challenges_today", "challenge_cycle", "challenge_points",
    "challenge_banked_points", "challenge_claimed_cycle",
    "dojo_clears_today",
    # avatar stat block: derived from the avatar character, not held
    "max_hp", "attack", "defense", "max_mana", "elemental", "speed",
    "crit_rate", "crit_damage", "recharge", "max_energy",
    # regenerating, not bankable
    "domain_energy",
    # notification plumbing
    "reminder_failures",
}

SEED = r"""
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

# TWO ACCOUNTS WITH IDENTICAL PROGRESS AND WILDLY DIFFERENT WALLETS.
#
# Same characters, same levels, same account level -- so the payout
# calculation, which reads progress and nothing else, must produce the
# same number for both. Any difference in their final balances is old
# money leaking through the reset.
for pid, name, wallet in ((1, "Hoarder", 500_000), (2, "Pauper", 0)):
    p = player_service.get_or_create_player(db, pid, name)
    character_service.ensure_avatar_character(db, p)
    for t in templates[:10]:
        db.add(PlayerCharacter(player_id=p.id, template_id=t.id,
                               level=30, talents=[], dupe_count=1))
    p.level = 12
    p.gold = wallet
    p.shards = wallet // 10
    p.cores = wallet // 20
    p.evolution_fragments = wallet // 50
    p.wood = p.stone = p.metal = p.crystal = wallet // 100
    p.xendium = p.permafrost_ore = p.void = p.entropy = wallet // 200
    p.echoes = p.reroll_tokens = wallet // 500
    p.daily_streak = 40 if wallet else 0
    p.prestige_count = 3 if wallet else 0
db.commit(); db.close()
"""

REPORT = r"""
import sys, os, json; sys.path.insert(0, ".")
import bot.config as cfg; cfg.DATABASE_URL = os.environ["DATABASE_URL"]
from bot.database.db_init import init_db; init_db()
from bot.database.session import SessionLocal
from bot.database.models.player_model import Player
from tools.reset_and_compensate import WIPED_RESOURCES, RESET_TO_DEFAULT
db = SessionLocal()
out = {}
for p in db.query(Player).all():
    key = (p.username or "").split(" [")[0]
    out[key] = {f: int(getattr(p, f) or 0)
                for f in list(WIPED_RESOURCES) + list(RESET_TO_DEFAULT)}
print(json.dumps(out))
db.close()
"""


def _run(code: str, url: str) -> str:
    env = {**os.environ, "DATABASE_URL": url, "PYTHONDONTWRITEBYTECODE": "1"}
    result = subprocess.run([sys.executable, "-c", code], capture_output=True,
                            text=True, env=env, cwd=".")
    if result.returncode != 0:
        raise RuntimeError(result.stderr[-2000:])
    return result.stdout


def main() -> int:
    sys.path.insert(0, ".")
    import json

    from tools.reset_and_compensate import (
        COMPENSATION_CURVE, RESET_TO_DEFAULT, WIPED_RESOURCES)

    failures: list[str] = []

    # ---- nothing numeric is unclassified -----------------------------
    from bot.database.db_init import init_db  # noqa: F401 registers models
    from bot.database.models.player_model import Player

    numeric = {
        c.name for c in Player.__table__.columns
        if any(t in str(c.type).upper() for t in ("INTEGER", "FLOAT", "NUMERIC"))
    }
    classified = set(WIPED_RESOURCES) | set(RESET_TO_DEFAULT) | NOT_A_RESOURCE
    unclassified = sorted(numeric - classified)
    if unclassified:
        failures.append(
            f"unclassified numeric Player column(s) {unclassified} -- if any of "
            f"these is a currency it survives the reset untouched, which is the "
            f"exact bug this check exists for. Add to WIPED_RESOURCES, "
            f"RESET_TO_DEFAULT, or NOT_A_RESOURCE")

    compensated = set(COMPENSATION_CURVE)

    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "balances.db")
        url = f"sqlite:///{path}"
        _run(SEED, url)

        env = {**os.environ, "DATABASE_URL": url, "PYTHONDONTWRITEBYTECODE": "1"}
        result = subprocess.run(
            [sys.executable, "-m", "tools.reset_and_compensate", "--apply"],
            capture_output=True, text=True, env=env, cwd=".")
        if result.returncode != 0:
            raise RuntimeError(f"the reset failed:\n{result.stderr[-2000:]}")

        after = json.loads(_run(REPORT, url))

    rich, poor = after["Hoarder"], after["Pauper"]

    # ---- identical progress must give identical balances -------------
    for field in list(WIPED_RESOURCES) + list(RESET_TO_DEFAULT):
        if rich[field] != poor[field]:
            failures.append(
                f"'{field}': an account that started with a large balance came out "
                f"with {rich[field]:,} and one with identical PROGRESS but an empty "
                f"wallet came out with {poor[field]:,} -- the old balance is "
                f"leaking through the reset")

    # ---- uncompensated resources end at zero -------------------------
    for field in WIPED_RESOURCES:
        if field in compensated:
            continue
        if poor[field] or rich[field]:
            failures.append(
                f"'{field}' has no compensation line but survived the reset "
                f"({rich[field]:,} / {poor[field]:,}) -- it should be zero")

    # ---- compensated currencies sit inside their own curve -----------
    #
    # The payout cannot exceed floor+cap by construction, so a balance
    # above the ceiling proves something was added to it afterwards.
    # This is the assertion that would have caught 241,000 gold.
    for currency in compensated:
        floor, cap, _ = COMPENSATION_CURVE[currency]
        ceiling = floor + cap
        for who, snap in (("rich", rich), ("poor", poor)):
            if not floor <= snap[currency] <= ceiling:
                failures.append(
                    f"'{currency}' for the {who} account is {snap[currency]:,}, "
                    f"outside the curve's own range of {floor:,}-{ceiling:,} -- "
                    f"the payout is being added to a held balance rather than "
                    f"replacing it")

    # ---- progress counters really did reset --------------------------
    for field, expected in RESET_TO_DEFAULT.items():
        if rich[field] != expected:
            failures.append(
                f"'{field}' is {rich[field]} after the reset, expected {expected}")

    print(f"{'field':<24}{'rich account':>16}{'poor account':>16}")
    print("-" * 56)
    for field in list(WIPED_RESOURCES) + list(RESET_TO_DEFAULT):
        mark = "" if rich[field] == poor[field] else "   <-- LEAK"
        print(f"{field:<24}{rich[field]:>16,}{poor[field]:>16,}{mark}")
    print(f"\nnumeric Player columns: {len(numeric)} "
          f"({len(WIPED_RESOURCES)} wealth, {len(RESET_TO_DEFAULT)} progress, "
          f"{len(NOT_A_RESOURCE)} not-a-resource)")

    if failures:
        print()
        for failure in dict.fromkeys(failures):
            print(f"  FAIL  {failure}")
        return 1
    print("\nOK -- the reset replaces the wallet rather than topping it up, and "
          "starting rich buys nothing.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
