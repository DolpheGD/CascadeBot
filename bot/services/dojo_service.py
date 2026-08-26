"""
The Dojo: building, publishing and playing player-authored challenges.

Tuning and the reasoning behind the limits live in
bot/game/economy/dojo_config.py. This module is the mechanism, and it
carries the three guarantees that make user-generated content safe to
show to strangers:

  1. AN AUTHOR CANNOT BUILD SOMETHING THE GAME CANNOT RUN. Every enemy
     name is checked against the live roster at save time AND resolved
     again at play time, because the roster can change underneath a
     saved challenge. A challenge that no longer resolves refuses to
     start with a message rather than raising in front of whoever
     clicked it.

  2. AN AUTHOR CANNOT WRITE ARBITRARY TEXT INTO SOMEBODY ELSE'S SCREEN.
     Names and descriptions go through the same allowlist the avatar
     rename uses, plus a length cap. Discord markdown and mentions are
     the specific thing being excluded: a name containing backticks or
     @everyone is a name that reformats or pings another player's
     client.

  3. AN AUTHOR CANNOT MAKE A FARM. See dojo_config -- a daily cap on
     rewarded clears, and a payout scaled by what the challenge actually
     fields, so the cheapest challenge is also the least rewarding.

The battle itself is held in memory, keyed by player id, exactly as
domain_service does it: one self-contained fight with no run state to
lose, where the worst failure is "start it again".
"""

from __future__ import annotations

import datetime as dt
import random
import re
import string

from bot.database.models.dojo_model import DojoChallenge, DojoClear
from bot.game.economy import dojo_config as cfg
from bot.services import combat_service
from bot.utils.time_utils import as_utc

# The same allowlist the avatar rename uses (character_service), for the
# same reason and with one addition: this text is shown to OTHER players,
# so the set stays deliberately small. Anything outside it -- backticks,
# underscores, asterisks, colons, at-signs -- is either Discord markup or
# a mention, and both let an author reach into somebody else's client.
TEXT_PATTERN = re.compile(r"^[A-Za-z0-9 '\-.,!?]+$")

_CODE_ALPHABET = string.ascii_uppercase + string.digits


class DojoError(Exception):
    """Any reason a dojo action can't proceed, phrased for the player."""


# ----------------------------------------------------------------------
# Authoring
# ----------------------------------------------------------------------

def clean_text(raw: str | None, limit: int, what: str) -> str | None:
    """Validate one piece of author-written text, or raise."""
    if raw is None or not raw.strip():
        if what == "name":
            raise DojoError("A challenge needs a name.")
        return None
    cleaned = " ".join(raw.split())
    if len(cleaned) > limit:
        raise DojoError(f"The {what} can be at most {limit} characters.")
    if not TEXT_PATTERN.match(cleaned):
        raise DojoError(
            f"The {what} can only contain letters, numbers, spaces and "
            f"`' - . , ! ?`")
    return cleaned


def known_enemy_names() -> list[str]:
    """Every enemy an author may put in a challenge.

    BOSSES AND ESCORTS ARE EXCLUDED. A boss is balanced around being the
    end of a run with a full squad and a level offset; dropped into a
    dojo fight at an author-chosen level it is either trivial or
    impossible, and neither is interesting. Escort templates
    (boss_group_member) are excluded because they are designed as
    somebody else's supporting cast and are nonsense alone.
    """
    from bot.game.combat.enemies import ENEMY_TEMPLATES

    return sorted(
        t["name"] for t in ENEMY_TEMPLATES
        if t.get("role") in ("combat", "elite")
    )


def validate_enemies(enemies: list[dict]) -> list[dict]:
    """Normalise and check an enemy recipe, or raise."""
    if not enemies:
        raise DojoError("A challenge needs at least one enemy.")
    if len(enemies) > cfg.MAX_ENEMY_STACKS:
        raise DojoError(f"At most {cfg.MAX_ENEMY_STACKS} different enemies.")

    allowed = set(known_enemy_names())
    cleaned: list[dict] = []
    total = 0
    for stack in enemies:
        name = stack.get("enemy")
        if name not in allowed:
            raise DojoError(f"`{name}` isn't an enemy you can use.")
        count = int(stack.get("count", 1))
        if not 1 <= count <= cfg.MAX_COUNT_PER_STACK:
            raise DojoError(
                f"Each enemy can appear 1-{cfg.MAX_COUNT_PER_STACK} times.")
        total += count
        cleaned.append({"enemy": name, "count": count})

    if total > cfg.MAX_TOTAL_ENEMIES:
        raise DojoError(f"At most {cfg.MAX_TOTAL_ENEMIES} enemies in total.")
    return cleaned


def _new_share_code(db) -> str:
    """A short unique code. Retries rather than trusting randomness."""
    for _ in range(20):
        code = "".join(random.choice(_CODE_ALPHABET) for _ in range(6))
        if db.query(DojoChallenge).filter_by(share_code=code).first() is None:
            return code
    raise DojoError("Couldn't allocate a share code. Try again.")


def create_challenge(db, player, name: str, enemies: list[dict],
                     level: int, description: str | None = None) -> DojoChallenge:
    owned = db.query(DojoChallenge).filter_by(author_id=player.id).count()
    if owned >= cfg.MAX_CHALLENGES_PER_AUTHOR:
        raise DojoError(
            f"You already have {owned} challenges (max "
            f"{cfg.MAX_CHALLENGES_PER_AUTHOR}). Delete one first.")

    level = int(level)
    if not cfg.MIN_LEVEL <= level <= cfg.MAX_LEVEL:
        raise DojoError(f"Level must be between {cfg.MIN_LEVEL} and {cfg.MAX_LEVEL}.")

    challenge = DojoChallenge(
        author_id=player.id,
        name=clean_text(name, cfg.MAX_NAME_LENGTH, "name"),
        description=clean_text(description, cfg.MAX_DESCRIPTION_LENGTH, "description")
        if description else None,
        enemies=validate_enemies(enemies),
        level=level,
        published=False,
        share_code=_new_share_code(db),
    )
    db.add(challenge)
    db.commit()
    return challenge


def set_published(db, player, challenge: DojoChallenge, published: bool) -> None:
    if challenge.author_id != player.id:
        raise DojoError("That isn't your challenge.")
    if challenge.removed_by_owner and published:
        # An author must not be able to undo a takedown by toggling the
        # same switch that performed it.
        raise DojoError("This challenge was removed and can't be republished.")
    challenge.published = bool(published)
    db.commit()


def delete_challenge(db, player, challenge: DojoChallenge) -> None:
    if challenge.author_id != player.id:
        raise DojoError("That isn't your challenge.")
    db.query(DojoClear).filter_by(challenge_id=challenge.id).delete()
    db.delete(challenge)
    db.commit()


def take_down(db, challenge: DojoChallenge) -> None:
    """Owner-only removal. Callers gate on BOT_OWNER_IDS."""
    challenge.published = False
    challenge.removed_by_owner = True
    db.commit()


# ----------------------------------------------------------------------
# Finding
# ----------------------------------------------------------------------

def by_code(db, code: str) -> DojoChallenge | None:
    """Look up a share code, case-insensitively.

    Normalised because a code travels through chat, gets copied with a
    stray space, and arrives lowercase as often as not. Refusing those
    would be a puzzle with no upside.
    """
    if not code:
        return None
    return (db.query(DojoChallenge)
            .filter(DojoChallenge.share_code == code.strip().upper())
            .one_or_none())


def list_published(db, limit: int = 25, offset: int = 0) -> list[DojoChallenge]:
    return (db.query(DojoChallenge)
            .filter(DojoChallenge.published.is_(True))
            .order_by(DojoChallenge.created_at.desc())
            .offset(offset).limit(limit).all())


def list_own(db, player) -> list[DojoChallenge]:
    return (db.query(DojoChallenge)
            .filter_by(author_id=player.id)
            .order_by(DojoChallenge.created_at.desc()).all())


def clear_rate(challenge: DojoChallenge) -> float | None:
    attempts = int(challenge.attempts or 0)
    return (int(challenge.clears or 0) / attempts) if attempts else None


# ----------------------------------------------------------------------
# Playing
# ----------------------------------------------------------------------

_ACTIVE_BATTLES: dict[int, object] = {}
_ACTIVE_CHALLENGE: dict[int, int] = {}


def get_active_battle(player_id: int):
    return _ACTIVE_BATTLES.get(player_id)


def resolve_enemies(challenge: DojoChallenge) -> list[dict]:
    """The live templates this challenge's recipe names.

    Resolved fresh every play, deliberately -- see the model docstring.
    An enemy that has been renamed or removed since the challenge was
    saved raises here, which is what turns a stale challenge into a
    refusal instead of a crash.
    """
    from bot.game.combat.enemies import get_template_by_name

    templates = []
    for stack in (challenge.enemies or []):
        try:
            template = get_template_by_name(stack["enemy"])
        except KeyError:
            raise DojoError(
                f"This challenge uses `{stack.get('enemy')}`, which no longer "
                f"exists. Ask the author to rebuild it.")
        templates.extend([template] * int(stack.get("count", 1)))
    if not templates:
        raise DojoError("This challenge has no enemies.")
    return templates


def start(db, player, challenge: DojoChallenge):
    """Open a dojo fight. Returns the Battle."""
    from bot.game.combat.battle import Battle
    from bot.game.combat.factory import build_enemy_combatant
    from bot.services import character_service

    if not challenge.published and challenge.author_id != player.id:
        raise DojoError("That challenge isn't published.")

    squad = character_service.get_squad(db, player)
    if not squad:
        raise DojoError("You need a squad before you can train.")

    # Full HP, like a domain challenge: this is a self-contained fight,
    # not a step in a run, so it must not be decided by what an
    # expedition left the squad on.
    combat_service.restore_squad_to_full_hp(db, squad)
    party = combat_service.build_player_party(db, player, squad=squad)

    enemies = [build_enemy_combatant(t, level=int(challenge.level))
               for t in resolve_enemies(challenge)]

    # ATTEMPTS COUNT AT THE START, not at the end. A challenge people
    # quit half way through is information about that challenge, and a
    # clear rate computed only from finished fights would report every
    # unbeatable challenge as 100%.
    challenge.attempts = int(challenge.attempts or 0) + 1
    db.commit()

    battle = Battle(party, enemies)
    _ACTIVE_BATTLES[player.id] = battle
    _ACTIVE_CHALLENGE[player.id] = challenge.id
    return battle


def abandon(db, player) -> None:
    _ACTIVE_BATTLES.pop(player.id, None)
    _ACTIVE_CHALLENGE.pop(player.id, None)


def _roll_over_day(player) -> None:
    last = as_utc(player.last_dojo_clear_at) if player.last_dojo_clear_at else None
    today = dt.datetime.now(dt.timezone.utc).date()
    if last is None or last.date() != today:
        player.dojo_clears_today = 0


def rewards_remaining(player) -> int:
    _roll_over_day(player)
    return max(0, cfg.REWARDED_CLEARS_PER_DAY - int(player.dojo_clears_today or 0))


def finish(db, player) -> dict:
    """Resolve a finished dojo fight. Safe to call once per battle."""
    battle = _ACTIVE_BATTLES.pop(player.id, None)
    challenge_id = _ACTIVE_CHALLENGE.pop(player.id, None)
    if battle is None:
        raise DojoError("No dojo fight in progress.")

    challenge = db.query(DojoChallenge).filter_by(id=challenge_id).one_or_none()
    won = battle.result == "won"
    if challenge is None:
        return {"won": won, "xp": 0, "paid": False, "challenge": None,
                "first_clear": False}

    if not won:
        db.commit()
        return {"won": False, "xp": 0, "paid": False, "challenge": challenge,
                "first_clear": False}

    # ---- record the clear ------------------------------------------
    record = (db.query(DojoClear)
              .filter_by(player_id=player.id, challenge_id=challenge.id)
              .one_or_none())
    first_clear = record is None or not record.times_cleared
    now = dt.datetime.now(dt.timezone.utc)
    if record is None:
        record = DojoClear(player_id=player.id, challenge_id=challenge.id,
                           times_cleared=0)
        db.add(record)
    record.times_cleared = int(record.times_cleared or 0) + 1
    record.last_cleared_at = now
    if record.first_cleared_at is None:
        record.first_cleared_at = now
    challenge.clears = int(challenge.clears or 0) + 1

    # ---- pay, if the daily cap allows -------------------------------
    _roll_over_day(player)
    paid = int(player.dojo_clears_today or 0) < cfg.REWARDED_CLEARS_PER_DAY
    xp = 0
    if paid:
        xp = cfg.xp_for_clear(challenge.enemies or [], int(challenge.level),
                              first_clear)
        # AUTHORS ARE NOT PAID FOR THEIR OWN CHALLENGES.
        #
        # Otherwise the whole system collapses to one move: build the
        # cheapest thing the validator allows and clear it five times a
        # day forever. Every other limit here is a bound on how bad that
        # is; this one removes it.
        if challenge.author_id == player.id:
            xp = 0
            paid = False
        else:
            from bot.services import character_service
            squad = character_service.get_squad(db, player)
            combat_service.apply_character_xp(db, squad, xp, player=player)
            player.dojo_clears_today = int(player.dojo_clears_today or 0) + 1
            player.last_dojo_clear_at = now

    db.commit()
    return {"won": True, "xp": xp, "paid": paid, "challenge": challenge,
            "first_clear": first_clear}
