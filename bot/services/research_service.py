"""
Research Lab: starting, collecting and reading permanent perks.

PERK READS ARE THE POINT. A research project that grants a number nobody
looks at is a menu, not progression -- so `perk_value` below is called
from the systems each perk claims to affect (loot generation, relic
offers, upgrade costs, domain energy, gacha pity, XP, harvester yield,
shop prices, forge costs, starting combat energy). See the PERKS block in
bot/game/economy/research_config.py for the full map.

Perk reads happen on hot paths (every loot roll, every upgrade quote), so
completed research is fetched as a single grouped query and summed --
never one query per project.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import func

from bot.database.models.base_building_model import PlayerLab, PlayerResearch
from bot.game.economy.research_config import (
    RESEARCH_PROJECTS,
    concurrent_slots,
    get_project,
    is_max_lab_level,
    lab_upgrade_cost,
    research_duration,
)
from bot.services.currency_service import format_currency, spend_currency
from bot.utils.time_utils import as_utc


class ResearchError(Exception):
    """Any reason a research action can't proceed. Message is written to
    be shown to the player verbatim."""


def get_or_create_lab(db, player) -> PlayerLab:
    lab = db.get(PlayerLab, player.id)
    if lab is None:
        lab = PlayerLab(player_id=player.id, level=1)
        db.add(lab)
        db.commit()
        db.refresh(lab)
    return lab


# ----------------------------------------------------------------------
# Perks
# ----------------------------------------------------------------------

def completed_project_ids(db, player_id: int) -> set[str]:
    rows = (
        db.query(PlayerResearch.project_id)
        .filter(PlayerResearch.player_id == player_id,
                PlayerResearch.completed_at.isnot(None))
        .all()
    )
    return {pid for (pid,) in rows}


def perk_totals(db, player_id: int) -> dict[str, float]:
    """Every perk this player has researched, summed. One query.

    Perks stack ADDITIVELY -- a perk appearing at three tiers in the tree
    is three separate projects whose values add up, which is what lets a
    branch keep paying out instead of a single node capping it."""
    done = completed_project_ids(db, player_id)
    totals: dict[str, float] = {}
    for project in RESEARCH_PROJECTS:
        if project["id"] in done:
            totals[project["perk"]] = totals.get(project["perk"], 0) + project["value"]
    return totals


def perk_value(db, player_id: int, perk: str) -> float:
    """One perk's total. The single entry point every other system uses;
    returns 0 when the player has researched nothing, so callers can
    apply it unconditionally."""
    return perk_totals(db, player_id).get(perk, 0)


# ----------------------------------------------------------------------
# Availability
# ----------------------------------------------------------------------

def active_research(db, player_id: int) -> list[PlayerResearch]:
    return (
        db.query(PlayerResearch)
        .filter(PlayerResearch.player_id == player_id,
                PlayerResearch.completed_at.is_(None))
        .all()
    )


def is_finished(row: PlayerResearch) -> bool:
    return dt.datetime.now(dt.timezone.utc) >= as_utc(row.finishes_at)


def collectable(db, player_id: int) -> list[PlayerResearch]:
    return [r for r in active_research(db, player_id) if is_finished(r)]


def project_state(db, player, project: dict) -> tuple[str, str | None]:
    """(state, reason) for one project, where state is one of
    "done" / "running" / "available" / "locked". `reason` explains a
    lock so the UI never shows an unexplained closed door."""
    lab = get_or_create_lab(db, player)
    row = (
        db.query(PlayerResearch)
        .filter_by(player_id=player.id, project_id=project["id"])
        .first()
    )
    if row is not None:
        return ("done", None) if row.completed_at else ("running", None)

    if lab.level < project["lab_level"]:
        return "locked", f"Needs Research Lab Lv.{project['lab_level']}"

    done = completed_project_ids(db, player.id)
    missing = [p for p in project["requires"] if p not in done]
    if missing:
        names = ", ".join(get_project(m)["name"] for m in missing if get_project(m))
        return "locked", f"Requires {names}"

    return "available", None


# ----------------------------------------------------------------------
# Actions
# ----------------------------------------------------------------------

def start_research(db, player, project_id: str) -> dict:
    """Spends the project's cost and starts its timer. Raises
    ResearchError with a player-facing message for any refusal."""
    project = get_project(project_id)
    if project is None:
        raise ResearchError("No such research project.")

    state, reason = project_state(db, player, project)
    if state == "done":
        raise ResearchError(f"**{project['name']}** is already researched.")
    if state == "running":
        raise ResearchError(f"**{project['name']}** is already in progress.")
    if state == "locked":
        raise ResearchError(f"**{project['name']}** is locked -- {reason}.")

    lab = get_or_create_lab(db, player)
    running = active_research(db, player.id)
    slots = concurrent_slots(lab.level)
    if len(running) >= slots:
        raise ResearchError(
            f"Your Research Lab can only run {slots} project(s) at once. "
            "Collect a finished one or upgrade the Lab."
        )

    # Charge every currency, rolling back anything already taken if a
    # later one fails -- a partial charge would silently eat materials.
    spent: list[tuple[str, int]] = []
    for currency, amount in project["cost"].items():
        if not spend_currency(db, player, currency, amount):
            from bot.services.currency_service import add_currency
            for refund_currency, refund_amount in spent:
                add_currency(db, player, refund_currency, refund_amount)
            db.commit()
            raise ResearchError(
                f"Not enough {format_currency(currency, amount)} for **{project['name']}**."
            )
        spent.append((currency, amount))

    now = dt.datetime.now(dt.timezone.utc)
    row = PlayerResearch(
        player_id=player.id,
        project_id=project_id,
        started_at=now,
        finishes_at=now + research_duration(project, lab.level),
    )
    db.add(row)
    db.commit()
    return {"project": project, "finishes_at": row.finishes_at}


def collect_research(db, player) -> list[dict]:
    """Completes every finished project at once and returns what was
    unlocked. Collecting several at a time matters at higher Lab levels
    where multiple slots finish together."""
    finished = collectable(db, player.id)
    if not finished:
        raise ResearchError("Nothing is ready to collect yet.")

    now = dt.datetime.now(dt.timezone.utc)
    unlocked = []
    for row in finished:
        row.completed_at = now
        project = get_project(row.project_id)
        if project:
            unlocked.append(project)
    db.commit()
    return unlocked


def upgrade_lab(db, player) -> tuple[bool, str]:
    lab = get_or_create_lab(db, player)
    if is_max_lab_level(lab.level):
        return False, "Your Research Lab is already at its maximum level."

    cost = lab_upgrade_cost(lab.level)
    spent: list[tuple[str, int]] = []
    for currency, amount in cost.items():
        if not spend_currency(db, player, currency, amount):
            from bot.services.currency_service import add_currency
            for c, a in spent:
                add_currency(db, player, c, a)
            db.commit()
            return False, f"Not enough {format_currency(currency, amount)}."
        spent.append((currency, amount))

    lab.level += 1
    db.commit()
    return True, f"Research Lab upgraded to level {lab.level}!"


def research_progress(db, player_id: int) -> tuple[int, int]:
    """(completed, total) -- used by the HQ gate and the UI header."""
    completed = (
        db.query(func.count(PlayerResearch.id))
        .filter(PlayerResearch.player_id == player_id,
                PlayerResearch.completed_at.isnot(None))
        .scalar()
    ) or 0
    return int(completed), len(RESEARCH_PROJECTS)
