"""
Dispatch board: send characters out, get them back, pay them.

THE ONE RULE THAT MAKES THIS A DECISION: a character on a contract is
unavailable for combat. `busy_character_ids` is the single source of that
truth and every consumer -- the squad editor, expeditions, raids, the
abyss, the dojo -- asks it rather than keeping its own idea of who is
free. Two code paths computing one value is the bug that has cost this
project the most time; this is the value most likely to grow a second
one, so it gets exactly one home.

Time is UTC throughout, and `ends_at` is stored rather than recomputed --
see the model. Everything here is defensive about naive datetimes,
because SQLite hands back naive values even for timezone-aware columns
and comparing those to an aware `now` raises TypeError at exactly the
moment somebody tries to claim a reward.
"""

from __future__ import annotations

import datetime as dt

from bot.database.models.character_model import PlayerCharacter, SquadSlot
from bot.database.models.dispatch_model import PlayerDispatch
from bot.game.economy import dispatch_config as dc


def _utc(value: dt.datetime | None) -> dt.datetime | None:
    """SQLite returns naive datetimes even from timezone-aware columns.

    Comparing one to an aware `now` raises TypeError, and it would do it
    inside the claim path -- the one place a player has already spent the
    time and is owed something.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=dt.timezone.utc)
    return value


def now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


# ----------------------------------------------------------------------
# Who is away
# ----------------------------------------------------------------------

def active_dispatches(db, player) -> list[PlayerDispatch]:
    return (db.query(PlayerDispatch)
            .filter_by(player_id=player.id, claimed=False)
            .order_by(PlayerDispatch.ends_at)
            .all())


def busy_character_ids(db, player) -> set[int]:
    """PlayerCharacter ids currently on a contract.

    INCLUDES FINISHED-BUT-UNCLAIMED contracts on purpose. A character
    whose job ended an hour ago is still standing in the depot until the
    player collects them, and letting them fight while their reward is
    pending would mean the lock could be dodged by simply not pressing
    claim.
    """
    busy: set[int] = set()
    for row in active_dispatches(db, player):
        busy.update(int(cid) for cid in (row.character_ids or []))
    return busy


def is_busy(db, player, character_id: int) -> bool:
    return int(character_id) in busy_character_ids(db, player)


# ----------------------------------------------------------------------
# Sending
# ----------------------------------------------------------------------

def slots(db, player) -> tuple[int, int]:
    """(used, total) contract slots."""
    from bot.services import base_service

    hq_level = base_service.get_hq_level(db, player)
    return len(active_dispatches(db, player)), dc.slots_for_hq(hq_level)


def can_send(db, player, contract_id: str, character_ids: list[int]) -> tuple[bool, str]:
    """Every reason a dispatch may be refused, checked SERVER-SIDE.

    The UI offers a filtered character list, but the ids arrive from a
    Discord select the client controls, so nothing here may assume the
    list was honest -- the same reasoning as achievement_service.set_title.
    """
    contract = dc.contract(contract_id)
    if contract is None:
        return False, "That contract is no longer on the board."

    used, total = slots(db, player)
    if total <= 0:
        return False, (f"The Dispatch Board opens at HQ level "
                       f"{dc.DISPATCH_UNLOCK_HQ_LEVEL}.")
    if used >= total:
        return False, (f"All {total} dispatch slot{'s' if total > 1 else ''} are "
                       f"in use. Claim one first.")

    ids = [int(c) for c in character_ids]
    if len(set(ids)) != len(ids):
        return False, "You cannot send the same character twice."
    if len(ids) != contract["party"]:
        return False, (f"**{contract['name']}** needs exactly "
                       f"{contract['party']} character(s).")

    owned = {c.id: c for c in db.query(PlayerCharacter)
             .filter_by(player_id=player.id).all()}
    for cid in ids:
        if cid not in owned:
            return False, "You do not own one of those characters."

    busy = busy_character_ids(db, player)
    clash = [owned[c].template.name for c in ids if c in busy]
    if clash:
        return False, f"Already on a contract: {', '.join(clash)}."

    return True, ""


def send(db, player, contract_id: str, character_ids: list[int]):
    """Start a contract. Returns (dispatch, error_message)."""
    ok, message = can_send(db, player, contract_id, character_ids)
    if not ok:
        return None, message

    contract = dc.contract(contract_id)
    ids = [int(c) for c in character_ids]
    members = (db.query(PlayerCharacter)
               .filter(PlayerCharacter.id.in_(ids)).all())

    fit = dc.fit_multiplier(contract, members)

    row = PlayerDispatch(
        player_id=player.id,
        contract_id=contract_id,
        character_ids=ids,
        started_at=now(),
        ends_at=now() + dt.timedelta(hours=contract["hours"]),
        fit=int(round(fit * 100)),
        claimed=False,
    )
    db.add(row)

    # PULL THEM OUT OF THE SQUAD AS THEY LEAVE.
    #
    # Leaving a dispatched character sitting in a squad slot would mean
    # the next fight either silently benches them or brings somebody who
    # is meant to be three regions away. Clearing the slot here makes the
    # consequence visible at the moment the player causes it, rather than
    # as a surprise when they next press attack.
    for slot in db.query(SquadSlot).filter_by(player_id=player.id).all():
        if slot.character_id in ids:
            slot.character_id = None

    db.commit()
    return row, ""


# ----------------------------------------------------------------------
# Claiming
# ----------------------------------------------------------------------

def ready(row: PlayerDispatch) -> bool:
    ends = _utc(row.ends_at)
    return ends is not None and now() >= ends


def remaining(row: PlayerDispatch) -> dt.timedelta:
    ends = _utc(row.ends_at)
    if ends is None:
        return dt.timedelta(0)
    return max(dt.timedelta(0), ends - now())


def payout(row: PlayerDispatch) -> dict[str, int]:
    """What this dispatch pays, using the fit frozen at send time."""
    contract = dc.contract(row.contract_id)
    if contract is None:
        return {}
    scale = max(1, int(row.fit or 100)) / 100.0
    return {key: max(1, int(round(amount * scale)))
            for key, amount in contract["rewards"].items()}


def claim(db, player, dispatch_id: int) -> tuple[dict[str, int], str]:
    """Collect a finished contract. Returns (rewards, error)."""
    row = db.get(PlayerDispatch, dispatch_id)
    if row is None or row.player_id != player.id or row.claimed:
        return {}, "That contract is not waiting for you."
    if not ready(row):
        left = remaining(row)
        hours, rest = divmod(int(left.total_seconds()), 3600)
        return {}, (f"Still out — back in "
                    f"{hours}h {rest // 60}m." if hours else
                    f"Still out — back in {rest // 60}m.")

    rewards = payout(row)

    # XP GOES TO THE CHARACTERS WHO WENT, and that is the interesting
    # half of the whole system.
    #
    # It sets the fit multiplier against itself in a useful way: a strong
    # team earns more materials and gold, a weak team earns less of those
    # but gains proportionally far more from the levels. So "send the
    # best" and "send the ones who need it" are both defensible, and
    # which is right depends on what the player is short of that week.
    # A flat account-XP payout would have collapsed that into one answer.
    #
    # Routed through combat_service.apply_character_xp rather than
    # touching pc.xp here, because that function owns level-up, the level
    # cap and the Research Lab's character_xp_percent perk. A second
    # implementation of levelling is the "two code paths computing one
    # value" failure this project keeps paying for.
    from bot.services import combat_service, currency_service

    levelled: list[dict] = []
    for key, amount in rewards.items():
        if key == "xp":
            members = (db.query(PlayerCharacter)
                       .filter(PlayerCharacter.id.in_(
                           [int(c) for c in (row.character_ids or [])]))
                       .all())
            levelled = combat_service.apply_character_xp(
                db, members, amount, player=player)
        else:
            currency_service.add_currency(db, player, key, amount)

    db.delete(row)      # working list, not an audit trail -- see the model
    db.commit()
    rewards = dict(rewards)
    if levelled:
        rewards["_levelled"] = levelled
    return rewards, ""


# ----------------------------------------------------------------------
# The board
# ----------------------------------------------------------------------

def board(db, player) -> list[dict]:
    """The contracts on offer.

    Deterministic per player per refresh window rather than random on
    every open: a board that reshuffles each time you look at it cannot
    be planned around, and the whole appeal of dispatch is planning.
    """
    import random

    from bot.services import base_service

    hq_level = base_service.get_hq_level(db, player)
    pool = dc.available_contracts(hq_level)
    if not pool:
        return []

    window = int(now().timestamp() // (dc.BOARD_REFRESH_HOURS * 3600))
    rng = random.Random(f"{player.id}:{window}")
    running = {r.contract_id for r in active_dispatches(db, player)}

    offered = rng.sample(pool, min(dc.BOARD_SIZE, len(pool)))
    # A contract already running is still shown, greyed by the caller,
    # rather than silently swapped out -- otherwise sending one contract
    # appears to reroll the board.
    return [c for c in offered if c["id"] not in running] or offered


def next_refresh() -> dt.datetime:
    period = dc.BOARD_REFRESH_HOURS * 3600
    return dt.datetime.fromtimestamp(
        (int(now().timestamp() // period) + 1) * period, dt.timezone.utc)
