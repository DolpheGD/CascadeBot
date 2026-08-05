"""
The Void Abyss interpreter: rotations, team validation, runs and stars.

Knows nothing about any specific floor. Everything comes from
bot/game/abyss/abyss_config.py, so tools/check_abyss.py can validate the
whole ladder without a database.

----------------------------------------------------------------------
ROTATION IS A FUNCTION OF THE DATE
----------------------------------------------------------------------
`current_rotation()` is (today - epoch) // ROTATION_DAYS. Nothing is
scheduled, nothing is stored, and there is no job that can fail to run.
A rotation "happening" is just the calendar moving, which means the
system cannot drift, cannot double-fire, and behaves identically on a bot
that was offline for a month.

The cost of that choice is that a rotation boundary is not announced to
anybody -- it simply is. That's the right trade here: a missed
announcement is a cosmetic problem, a missed reset is a broken mode.

----------------------------------------------------------------------
TEAMS ARE LOCKED BEFORE THE FIRST FIGHT
----------------------------------------------------------------------
`begin_floor` takes EVERY chamber's team at once and refuses overlap.
Choosing your second team after seeing what beat your first is a
completely different and much easier game, and it would quietly delete
the only reason this mode exists.
"""

from __future__ import annotations

import datetime as dt

from bot.database.models.abyss_model import PlayerAbyss
from bot.game.abyss import abyss_config as ac


class AbyssError(Exception):
    """Any reason an Abyss action can't proceed, phrased for the player."""


# ----------------------------------------------------------------------
# State
# ----------------------------------------------------------------------

def get_or_create(db, player) -> PlayerAbyss:
    row = db.get(PlayerAbyss, player.id)
    if row is None:
        row = PlayerAbyss(player_id=player.id, stars={}, claimed_static={},
                          claimed_rotation={}, chamber_index=0)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def current_rotation(today: dt.date | None = None) -> int:
    today = today or dt.date.today()
    return max(0, (today - ac.ROTATION_EPOCH).days // ac.ROTATION_DAYS)


def rotation_ends(today: dt.date | None = None) -> dt.date:
    today = today or dt.date.today()
    return ac.ROTATION_EPOCH + dt.timedelta(
        days=(current_rotation(today) + 1) * ac.ROTATION_DAYS
    )


def stars_on(state: PlayerAbyss, floor_number: int) -> int:
    return int((state.stars or {}).get(str(floor_number), 0))


def total_stars(state: PlayerAbyss) -> int:
    return sum(int(v) for v in (state.stars or {}).values())


# ----------------------------------------------------------------------
# Availability
# ----------------------------------------------------------------------

def roster_levels(db, player) -> int:
    """Total levels across every character the player owns.

    The same measure raids gate on, so "how strong am I" means one thing
    everywhere in the game."""
    from bot.database.models.character_model import PlayerCharacter
    from sqlalchemy import func as sqlfunc

    total = (
        db.query(sqlfunc.coalesce(sqlfunc.sum(PlayerCharacter.level), 0))
        .filter(PlayerCharacter.player_id == player.id)
        .scalar()
    )
    return int(total or 0)


def owned_count(db, player) -> int:
    from bot.database.models.character_model import PlayerCharacter

    return db.query(PlayerCharacter).filter_by(player_id=player.id).count()


def floor_locked_reason(db, player, floor: dict) -> str | None:
    """Why this floor can't be entered, or None if it can.

    Two independent gates, and they fail with DIFFERENT messages on
    purpose: "get stronger" and "get more characters" are completely
    different pieces of advice, and a mode built on roster depth must
    never blur them."""
    needed_chars = ac.characters_required(floor)
    if owned_count(db, player) < needed_chars:
        return (
            f"**Floor {floor['floor']}** needs **{needed_chars} different characters** "
            f"— {ac.chamber_count(floor)} chambers of {ac.TEAM_SIZE}, and nobody may "
            f"fight twice.\n\nYou have {owned_count(db, player)}."
        )
    have = roster_levels(db, player)
    if have < floor["min_roster_levels"]:
        return (
            f"**Floor {floor['floor']}** opens at **{floor['min_roster_levels']:,}** "
            f"total roster levels. You're at {have:,}."
        )
    return None


def available_floors(db, player) -> list[dict]:
    return [f for f in ac.FLOORS if floor_locked_reason(db, player, f) is None]


# ----------------------------------------------------------------------
# Running a floor
# ----------------------------------------------------------------------

def validate_teams(teams: list[list[int]], floor: dict) -> None:
    """Right shape, right size, and NO CHARACTER TWICE."""
    expected = ac.chamber_count(floor)
    if len(teams) != expected:
        raise AbyssError(
            f"Floor {floor['floor']} has {expected} chambers; you gave {len(teams)} teams."
        )
    for index, team in enumerate(teams, start=1):
        if not team:
            raise AbyssError(f"Chamber {index} has no team.")
        if len(team) > ac.TEAM_SIZE:
            raise AbyssError(
                f"Chamber {index} has {len(team)} characters (max {ac.TEAM_SIZE})."
            )
        if len(set(team)) != len(team):
            raise AbyssError(f"Chamber {index} lists the same character twice.")

    seen: dict[int, int] = {}
    for index, team in enumerate(teams, start=1):
        for character_id in team:
            if character_id in seen:
                raise AbyssError(
                    f"A character is in both chamber {seen[character_id]} and "
                    f"chamber {index}. The Abyss does not allow anyone to fight twice."
                )
            seen[character_id] = index


def begin_floor(db, player, floor_number: int, teams: list[list[int]]) -> dict:
    floor = ac.get_floor(floor_number)
    if floor is None:
        raise AbyssError("That floor doesn't exist.")
    reason = floor_locked_reason(db, player, floor)
    if reason:
        raise AbyssError(reason)

    state = get_or_create(db, player)
    if state.active_floor is not None:
        raise AbyssError(
            f"You're partway through floor {state.active_floor}. Finish or abandon it first."
        )
    validate_teams(teams, floor)

    # Ownership is re-checked here rather than trusted from the UI: the
    # team picker is a Discord component and components can be replayed.
    from bot.database.models.character_model import PlayerCharacter

    owned = {
        pc.id for pc in db.query(PlayerCharacter).filter_by(player_id=player.id).all()
    }
    for team in teams:
        for character_id in team:
            if character_id not in owned:
                raise AbyssError("That isn't one of your characters.")

    state.active_floor = floor_number
    state.active_rotation = current_rotation()
    state.chamber_index = 0
    state.run_teams = [list(t) for t in teams]
    state.combat_state = None
    state.run_flawless = 1
    state.run_fast = 1
    db.commit()
    return floor


def abandon(db, player) -> None:
    state = get_or_create(db, player)
    state.active_floor = None
    state.active_rotation = None
    state.chamber_index = 0
    state.run_teams = None
    state.combat_state = None
    db.commit()


def current_chamber(db, player) -> dict | None:
    """{"floor", "index", "total", "enemies", "team"} or None."""
    state = get_or_create(db, player)
    if state.active_floor is None:
        return None
    floor = ac.get_floor(state.active_floor)
    if floor is None:
        abandon(db, player)
        return None
    chambers = ac.chambers_for(floor, state.active_rotation or 0)
    if state.chamber_index >= len(chambers):
        return None
    return {
        "floor": floor,
        "index": state.chamber_index,
        "total": len(chambers),
        "enemies": chambers[state.chamber_index],
        "team": (state.run_teams or [[]])[state.chamber_index],
    }


def record_chamber_result(db, player, won: bool, cycles: int, deaths: int) -> dict:
    """Resolve a finished chamber.

    Returns {"floor_done": bool, "won": bool, "stars": int|None,
             "rewards": list[str]}.

    A LOSS ENDS THE WHOLE FLOOR. That is the point of locking teams up
    front -- if a failed chamber could be retried in isolation, the floor
    would be a series of independent fights rather than one commitment.
    """
    state = get_or_create(db, player)
    if state.active_floor is None:
        raise AbyssError("You don't have a floor in progress.")
    floor = ac.get_floor(state.active_floor)
    chambers = ac.chambers_for(floor, state.active_rotation or 0)

    if deaths:
        state.run_flawless = 0
    if cycles > ac.STAR_CYCLE_LIMIT:
        state.run_fast = 0

    if not won:
        abandon(db, player)
        return {"floor_done": True, "won": False, "stars": None, "rewards": []}

    state.chamber_index += 1
    db.commit()
    if state.chamber_index < len(chambers):
        return {"floor_done": False, "won": True, "stars": None, "rewards": []}

    earned = 1 + int(bool(state.run_fast)) + int(bool(state.run_flawless))
    key = str(floor["floor"])
    best = dict(state.stars or {})
    # Stars only ever go UP. A worse attempt must not cost a rating the
    # player already has, or experimenting is punished.
    best[key] = max(int(best.get(key, 0)), earned)
    state.stars = best

    rewards = _claim_if_due(db, player, state, floor)
    abandon(db, player)
    return {"floor_done": True, "won": True, "stars": earned, "rewards": rewards}


def reward_available(state: PlayerAbyss, floor: dict, rotation: int | None = None) -> bool:
    key = str(floor["floor"])
    if not ac.is_rotating(floor):
        return not (state.claimed_static or {}).get(key)
    rotation = current_rotation() if rotation is None else rotation
    claimed = (state.claimed_rotation or {}).get(key)
    return claimed is None or int(claimed) != int(rotation)


def _claim_if_due(db, player, state: PlayerAbyss, floor: dict) -> list[str]:
    if not reward_available(state, floor):
        return []
    key = str(floor["floor"])
    if ac.is_rotating(floor):
        state.claimed_rotation = {**(state.claimed_rotation or {}),
                                  key: int(state.active_rotation or current_rotation())}
    else:
        state.claimed_static = {**(state.claimed_static or {}), key: True}
    db.commit()
    return _grant(db, player, floor.get("rewards") or {})


def _grant(db, player, grant: dict) -> list[str]:
    """Same narrow shape as the story's grant block: currencies plus at
    most one item, so there is exactly one place in the codebase that
    knows how to turn a reward dict into things a player owns."""
    import random

    from bot.database.models.enums import Rarity
    from bot.services import item_template_service
    from bot.services.currency_service import CURRENCY_EMOJI, VALID_CURRENCIES, add_currency

    lines: list[str] = []
    for key, amount in (grant or {}).items():
        if key == "item":
            rarity = Rarity(amount) if isinstance(amount, str) else Rarity.RARE
            template = item_template_service.pick_random_template(
                db, rng=random.Random(), rarity=rarity
            )
            if template is None:
                continue
            from bot.game.loot.generator import LootGenerator

            item = LootGenerator().generate_item(
                template, player_id=player.id, item_level=1, rarity_override=rarity
            )
            db.add(item)
            db.commit()
            lines.append(f"🎁 **{item.name}** ({rarity.value.title()})")
        elif key in VALID_CURRENCIES:
            add_currency(db, player, key, amount)
            lines.append(f"{CURRENCY_EMOJI.get(key, '')} +{amount:,} {key.replace('_', ' ')}")
    return lines
