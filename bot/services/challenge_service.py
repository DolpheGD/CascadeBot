"""
Async squad challenges: fight other players' squads, offline.

WHAT THIS IS AND IS NOT
-----------------------
It is a single-player fight whose enemies were assembled by somebody
else. The defender is not playing, is not notified, loses nothing, and
their squad is rebuilt from their CURRENT roster at the moment the fight
starts. There is no queue, no timing, no real-time anything.

WHY THE DEFENDER IS BUILT LIVE RATHER THAN SNAPSHOTTED
------------------------------------------------------
A stored snapshot is the obvious design and it introduces a whole bug
class: the snapshot goes stale, and now there are two answers to "what is
this player's squad" -- the live one and the frozen one. This codebase's
recurring failure is exactly that shape.

Building from the live squad through combat_service.build_player_party --
the same function that builds a party for story, adventure, raids and the
Abyss -- means a defender's gear, talents, cards and shrines are always
whatever they actually are, and there is nothing to keep in sync. The
cost is one extra query at challenge start, which is nothing.

`Player.challenge_power` IS cached, because matchmaking has to compare
everybody without loading everybody. It is a matchmaking hint, not a
source of truth: it is refreshed whenever its owner fights, so it tracks
active players and only drifts for inactive ones.
"""

from __future__ import annotations

import datetime as dt

from bot.database.models.player_model import Player
from bot.game.economy.challenge_config import (
    CUMULATIVE_MILESTONES,
    CYCLE_LENGTH_DAYS,
    DEFENDER_HP_PERCENT,
    LOSS_REWARD,
    MILESTONES,
    OPPONENT_CHOICES,
    OVERDOG_PENALTY_MIN,
    POINTS_PER_LOSS,
    POINTS_PER_WIN,
    POWER_BAND,
    REWARDED_CHALLENGES_PER_DAY,
    UNDERDOG_BONUS_MAX,
    WIN_REWARD,
)
from bot.services import character_service, combat_service
from bot.services.currency_service import add_currency
from bot.utils.time_utils import as_utc


class ChallengeError(Exception):
    """Any reason a challenge can't proceed, phrased for the player."""


def squad_power(db, player) -> int:
    """A single number summarising how strong a squad is.

    Deliberately crude -- level, gear level and star rating. It only has
    to ORDER players for matchmaking, and anything more precise would be
    a second combat model to keep in step with the real one.
    """
    from bot.services import inventory_service

    total = 0
    for character in character_service.get_squad(db, player):
        total += character.level * 10
        # effective_star: an evolved character is genuinely stronger,
        # so matchmaking has to price it that way or an evolved squad
        # is matched against opponents it outclasses.
        total += (character.effective_star or 3) * 25
        for item in inventory_service.list_equipped(db, character.id):
            total += item.item_level * 3
    return int(total)


def refresh_power(db, player) -> int:
    power = squad_power(db, player)
    player.challenge_power = power
    db.commit()
    return power


# ----------------------------------------------------------------------
# Cycles
#
# The cycle is a GLOBAL INDEX derived from the clock, not a per-player
# timer started when they first fought. Everyone's week begins and ends
# at the same instant, which is what lets the UI say "ends in 2 days" and
# have it be true for the person reading it.
#
# The alternative -- storing each player's cycle start and rolling it
# forward from there -- drifts: a player who first fought on a Thursday
# has a Thursday week forever, two players comparing notes disagree about
# when the cycle ends, and the answer to "when does it reset" becomes
# "when did YOU start", which nobody can be told in advance.
# ----------------------------------------------------------------------

# Monday, 1 January 2024, 00:00 UTC. A Monday on purpose: with a 7-day
# cycle every boundary then lands on a Monday midnight UTC, which is a
# sentence that can be put in front of a player.
CYCLE_EPOCH = dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc)


def current_cycle(now: dt.datetime | None = None) -> int:
    """Which cycle we are in. Deterministic from the clock alone."""
    now = now or dt.datetime.now(dt.timezone.utc)
    return int((now - CYCLE_EPOCH).days // CYCLE_LENGTH_DAYS)


def cycle_ends_at(index: int | None = None) -> dt.datetime:
    """When a cycle closes (i.e. when the next one opens)."""
    index = current_cycle() if index is None else index
    return CYCLE_EPOCH + dt.timedelta(days=CYCLE_LENGTH_DAYS * (index + 1))


def sync_cycle(player) -> None:
    """Move the player onto the current cycle, banking the last one.

    Called at the top of every read AND every write, because a player who
    has been away for three weeks must see the right thing on the first
    screen they open -- not after they fight something.

    A player away for MULTIPLE cycles banks only the most recent one they
    actually played. There is nowhere to put a second bank, and inventing
    per-cycle history to pay out weeks nobody claimed would be generous
    to the point of dishonesty: the offer was to claim at the end of the
    cycle, and cycles that came and went unclaimed have ended.
    """
    cycle = current_cycle()
    if int(player.challenge_cycle or 0) == cycle:
        return
    # The finished cycle's points become claimable. If a previous bank was
    # never claimed it is REPLACED, not added to -- see the docstring.
    player.challenge_banked_points = int(player.challenge_points or 0)
    player.challenge_points = 0
    player.challenge_cycle = cycle


def milestones_for(points: int) -> list[tuple[int, str, dict]]:
    """Which milestones `points` has earned."""
    reached = [m for m in MILESTONES if points >= m[0]]
    if not reached:
        return []
    return reached if CUMULATIVE_MILESTONES else [reached[-1]]


def next_milestone(points: int) -> tuple[int, str, dict] | None:
    """The next one to aim at, or None if they are all earned."""
    for milestone in MILESTONES:
        if points < milestone[0]:
            return milestone
    return None


def claimable(player) -> tuple[int, list[tuple[int, str, dict]]]:
    """(banked points, milestones earned) if there is a claim waiting.

    Returns (0, []) when there is nothing to claim -- including when the
    bank holds points that earned no milestone at all, because offering a
    claim button that pays nothing is worse than not offering one.
    """
    sync_cycle(player)
    if int(player.challenge_claimed_cycle or -1) >= int(player.challenge_cycle or 0) - 1:
        return 0, []          # already settled the cycle that just ended
    points = int(player.challenge_banked_points or 0)
    return points, milestones_for(points)


def claim_cycle(db, player) -> dict:
    """Pay out the finished cycle. Safe to call twice.

    IDEMPOTENT BY DESIGN, and not by hoping the button is only pressed
    once. Every Discord message stays live and clickable forever, so a
    claim button from last week is still there to be pressed -- this is
    the same shape as the finish_hunt double-payout bug, which was a
    missing guard on exactly this kind of "way out" path.
    """
    points, earned = claimable(player)
    if not earned:
        raise ChallengeError("There's nothing to claim yet.")

    granted: dict[str, int] = {}
    for _, _, rewards in earned:
        for currency, amount in rewards.items():
            add_currency(db, player, currency, amount)
            granted[currency] = granted.get(currency, 0) + amount

    # Mark BEFORE the commit that matters, and mark the cycle that was
    # actually claimed rather than "the current one".
    player.challenge_claimed_cycle = int(player.challenge_cycle or 0) - 1
    player.challenge_banked_points = 0
    db.commit()
    return {"points": points, "milestones": earned, "rewards": granted}


def _roll_over_day(player) -> None:
    """Reset the daily counter when the calendar day changes."""
    last = as_utc(player.last_challenge_at) if player.last_challenge_at else None
    today = dt.datetime.now(dt.timezone.utc).date()
    if last is None or last.date() != today:
        player.challenges_today = 0


def rewards_remaining(player) -> int:
    _roll_over_day(player)
    return max(0, REWARDED_CHALLENGES_PER_DAY - int(player.challenges_today or 0))


def find_opponents(db, player, limit: int = OPPONENT_CHOICES) -> list[Player]:
    """Players within the power band, nearest first.

    Excludes the challenger and anyone with no squad worth fighting. Falls
    back to widening the band rather than returning nothing -- an empty
    opponent list on a small server is a dead feature, and a slightly
    mismatched fight is better than no fight.
    """
    power = refresh_power(db, player)
    candidates = (
        db.query(Player)
        .filter(Player.id != player.id)
        .filter(Player.challenge_power > 0)
        .all()
    )
    if not candidates:
        return []

    def within(band: float) -> list[Player]:
        low, high = power * (1 - band), power * (1 + band)
        return [c for c in candidates if low <= c.challenge_power <= high]

    pool = within(POWER_BAND) or within(POWER_BAND * 3) or candidates
    pool.sort(key=lambda c: abs(c.challenge_power - power))
    return pool[:limit]


def build_opponent_party(db, defender) -> list:
    """The defender's squad, as ENEMIES.

    Built through the same build_player_party every other mode uses, then
    flipped to the enemy side. Flipping rather than rebuilding is what
    guarantees a defender fights with exactly the stats they would have
    fighting for themselves -- gear, talents, cards, shrines and all.
    """
    party = combat_service.build_player_party(db, defender, full_hp=True)
    if not party:
        return []
    for combatant in party:
        combatant.is_player = False
        # A challenge enemy must not be mistaken for one of the
        # attacker's own characters by anything keying off character_id
        # -- persistence, HP sync, victory rewards. Clearing it makes the
        # snapshot inert: it is a stat block for one fight and nothing
        # else in the game will try to write to it.
        combatant.character_id = None
        if DEFENDER_HP_PERCENT != 100:
            combatant.max_hp = max(1, round(combatant.max_hp * DEFENDER_HP_PERCENT / 100))
        combatant.current_hp = combatant.max_hp
    return party


def reward_multiplier(attacker_power: int, defender_power: int) -> float:
    """Beating somebody stronger pays more; farming somebody weaker pays
    very little. Clamped at both ends so neither becomes a strategy."""
    if attacker_power <= 0:
        return 1.0
    ratio = defender_power / attacker_power
    return max(OVERDOG_PENALTY_MIN, min(UNDERDOG_BONUS_MAX, ratio))


def resolve(db, player, defender, won: bool) -> dict:
    """Pay out a finished challenge and record it.

    Returns {"rewards": {...}, "paid": bool, "multiplier": float}.
    """
    _roll_over_day(player)
    sync_cycle(player)
    paid = int(player.challenges_today or 0) < REWARDED_CHALLENGES_PER_DAY

    multiplier = reward_multiplier(
        int(player.challenge_power or 0), int(defender.challenge_power or 0))
    base = WIN_REWARD if won else LOSS_REWARD
    granted: dict[str, int] = {}
    points = 0
    if paid:
        for currency, amount in base.items():
            value = max(1, int(round(amount * (multiplier if won else 1.0))))
            add_currency(db, player, currency, value)
            granted[currency] = value

        # POINTS RIDE THE SAME `paid` GATE AS THE GOLD, deliberately.
        #
        # If points accrued on unpaid fights, the daily cap would stop
        # capping anything that matters: a player could fight forty times
        # a day, take no gold, and still bank a full cycle's points. The
        # milestones are sized against REWARDED_CHALLENGES_PER_DAY, so
        # letting points escape the cap would quietly invalidate every
        # number in the milestone table.
        #
        # Fighting beyond the cap is still allowed and still free -- the
        # fights are the content. It just does not advance the ladder.
        points = max(1, int(round(
            (POINTS_PER_WIN if won else POINTS_PER_LOSS)
            * (multiplier if won else 1.0))))
        player.challenge_points = int(player.challenge_points or 0) + points

    if won:
        player.challenge_wins = int(player.challenge_wins or 0) + 1
    else:
        player.challenge_losses = int(player.challenge_losses or 0) + 1
    player.challenges_today = int(player.challenges_today or 0) + 1
    player.last_challenge_at = dt.datetime.now(dt.timezone.utc)
    refresh_power(db, player)
    db.commit()
    return {"rewards": granted, "paid": paid, "multiplier": multiplier,
            "points": points,
            "cycle_points": int(player.challenge_points or 0)}


# ----------------------------------------------------------------------
# The active fight.
#
# Held in memory, keyed by player id, exactly as domain_service does. A
# challenge is one self-contained battle with no map, no run state and no
# progress to lose -- persisting it through a restart would mean a schema
# and a serialization path for something whose worst failure is "start it
# again".
# ----------------------------------------------------------------------
_ACTIVE_BATTLES: dict[int, object] = {}
_ACTIVE_DEFENDER: dict[int, int] = {}


def get_active_battle(player_id: int):
    return _ACTIVE_BATTLES.get(player_id)


def active_defender_id(player_id: int) -> int | None:
    return _ACTIVE_DEFENDER.get(player_id)


def start_challenge(db, player, defender):
    """Build both squads and open the fight."""
    from bot.game.combat.battle import Battle

    if defender.id == player.id:
        raise ChallengeError("You can't challenge yourself.")

    attackers = combat_service.build_player_party(db, player, full_hp=True)
    if not attackers:
        raise ChallengeError("You need a squad before you can challenge anyone.")
    enemies = build_opponent_party(db, defender)
    if not enemies:
        raise ChallengeError("That player doesn't have a squad to fight.")

    battle = Battle(attackers, enemies)
    _ACTIVE_BATTLES[player.id] = battle
    _ACTIVE_DEFENDER[player.id] = defender.id
    return battle


def finish_challenge(db, player) -> dict:
    """Call once battle.is_over(). Pays out and clears the fight.

    HP IS NOT SYNCED BACK to the attacker's characters. Every other
    self-contained mode (domains, story, Abyss) fights at full health and
    writes the result back; a challenge deliberately does not, because
    losing one would otherwise leave a player unable to run an expedition
    until they healed -- a real cost imposed by an optional side mode
    they entered for fun.
    """
    battle = _ACTIVE_BATTLES.pop(player.id, None)
    defender_id = _ACTIVE_DEFENDER.pop(player.id, None)
    if battle is None:
        raise ChallengeError("No challenge in progress.")

    defender = db.query(Player).filter_by(id=defender_id).one_or_none()
    if defender is None:
        # The opponent vanished mid-fight. Pay the result rather than
        # dropping it: the player fought it either way.
        defender = player

    won = battle.result == "won"
    outcome = resolve(db, player, defender, won)
    outcome["won"] = won
    outcome["defender"] = defender
    return outcome
