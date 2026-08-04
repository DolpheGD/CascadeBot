"""
Co-op guild raids: lifecycle, attacks, contribution accounting and
rewards. See bot/database/models/raid_model.py for the data shape and
bot/game/economy/raid_config.py for the tuning.

CONCURRENCY IS THE INTERESTING PART. GuildRaid.current_hp is the only
piece of state in this game that two different people can write to, and
they can do it at the same time -- two members of a server can finish a
raid battle in the same second. Everything here is written with that in
mind:

  * record_attack_damage re-reads and clamps the pool inside the same
    transaction that decrements it, and returns the damage ACTUALLY
    applied (which may be less than the damage dealt, if someone else
    emptied the pool first). Contribution is banked from that clamped
    number, so the sum of every participant's damage can never exceed
    max_hp and the contribution shares can never sum above 1.0.
  * The raid is marked defeated by whoever's write takes the pool to 0,
    inside that same transaction -- so exactly one attack ever gets to be
    the killing blow, no matter how many land simultaneously.
  * Rewards are computed from shares at CLAIM time, not at defeat time,
    so a late-arriving contribution can't retroactively change a reward
    someone has already been paid.

BATTLES ARE IN-MEMORY. Like domains (and unlike expeditions), an
in-progress raid attack lives only in _ACTIVE_BATTLES, not the database
-- same trade-off and same reasoning as domain_service: one short,
self-contained fight isn't worth a second persistence path, and a bot
restart mid-attack costs one attempt rather than hours of progress. The
attack is only debited from the player's allowance when they START it,
so a lost battle can't be retried for free.
"""

from __future__ import annotations

import datetime as dt
import random

from bot.database.models.raid_model import GuildRaid, RaidParticipant
from bot.game.combat.battle import Battle
from bot.game.combat.enemies import get_template_by_name
from bot.game.combat.factory import build_enemy_combatant, build_party_combatants
from bot.game.economy.raid_config import (
    ATTACK_COOLDOWN,
    MAX_ATTACKS_PER_PLAYER,
    RAID_DURATION,
    RAID_TIERS,
    contribution_tier,
    get_tier,
    pool_hp_for,
)
from bot.services import base_service, character_service, combat_service
from bot.services.currency_service import add_currency
from bot.utils.time_utils import as_utc

# player_id -> Battle, and player_id -> raid_id. In-memory only; see the
# module docstring.
_ACTIVE_BATTLES: dict[int, Battle] = {}
_ACTIVE_RAID_ID: dict[int, int] = {}


class RaidError(Exception):
    """Any reason a raid action can't proceed. The message is written to
    be shown to the player verbatim."""


# ----------------------------------------------------------------------
# Lifecycle
# ----------------------------------------------------------------------

def get_active_raid(db, guild_id: int) -> GuildRaid | None:
    """The guild's current raid, expiring it first if its window has
    passed. Returns None if there isn't one (or it just expired)."""
    raid = (
        db.query(GuildRaid)
        .filter_by(guild_id=guild_id, status="active")
        .order_by(GuildRaid.started_at.desc())
        .first()
    )
    if raid is None:
        return None
    if as_utc(raid.ends_at) <= dt.datetime.now(dt.timezone.utc):
        raid.status = "expired"
        db.commit()
        return None
    return raid


def get_raid(db, raid_id: int) -> GuildRaid | None:
    return db.get(GuildRaid, raid_id)


def available_tiers(db, player) -> list[dict]:
    """Raid tiers this player's roster is strong enough to start. Uses
    the same total-character-levels measure the domain unlocks use (see
    domain_service.roster_total_levels), so "how far along am I" means
    one consistent thing across the whole game."""
    from bot.services import domain_service

    total = domain_service.roster_total_levels(db, player)
    return [t for t in RAID_TIERS if total >= t["min_roster_levels"]]


def start_raid(db, player, guild_id: int, tier_id: str, rng: random.Random | None = None) -> GuildRaid:
    """Summons a new raid for the guild. Anyone in the server may do this
    -- there's no leader role -- but only one raid can be active at a
    time, so it's first-come."""
    rng = rng or random.Random()

    if get_active_raid(db, guild_id) is not None:
        raise RaidError("This server already has a raid in progress. Use `/raid` to join it.")

    tier = get_tier(tier_id)
    if tier is None:
        raise RaidError("No such raid tier.")
    if tier not in available_tiers(db, player):
        raise RaidError(
            f"**{tier['name']}** needs {tier['min_roster_levels']} total character levels "
            "across your roster before you can summon it."
        )

    now = dt.datetime.now(dt.timezone.utc)
    pool = pool_hp_for(tier)
    raid = GuildRaid(
        guild_id=guild_id,
        boss_name=rng.choice(tier["boss_pool"]),
        boss_level=tier["boss_level"],
        max_hp=pool,
        current_hp=pool,
        status="active",
        tier=tier["id"],
        started_at=now,
        ends_at=now + RAID_DURATION,
    )
    db.add(raid)
    db.commit()
    db.refresh(raid)
    return raid


# ----------------------------------------------------------------------
# Participation
# ----------------------------------------------------------------------

def get_participant(db, raid_id: int, player_id: int) -> RaidParticipant | None:
    return (
        db.query(RaidParticipant)
        .filter_by(raid_id=raid_id, player_id=player_id)
        .first()
    )


def _get_or_create_participant(db, raid: GuildRaid, player) -> RaidParticipant:
    row = get_participant(db, raid.id, player.id)
    if row is None:
        row = RaidParticipant(raid_id=raid.id, player_id=player.id)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def attacks_remaining(db, raid: GuildRaid, player) -> int:
    row = get_participant(db, raid.id, player.id)
    used = row.attacks_used if row else 0
    return max(0, MAX_ATTACKS_PER_PLAYER - used)


def time_until_next_attack(db, raid: GuildRaid, player) -> dt.timedelta | None:
    """None when the player can attack right now."""
    row = get_participant(db, raid.id, player.id)
    if row is None or row.last_attack_at is None:
        return None
    ready_at = as_utc(row.last_attack_at) + ATTACK_COOLDOWN
    now = dt.datetime.now(dt.timezone.utc)
    return None if ready_at <= now else ready_at - now


def leaderboard(db, raid: GuildRaid) -> list[RaidParticipant]:
    return (
        db.query(RaidParticipant)
        .filter_by(raid_id=raid.id)
        .order_by(RaidParticipant.damage_dealt.desc())
        .all()
    )


def has_active_attack(player_id: int) -> bool:
    return player_id in _ACTIVE_BATTLES


def get_active_battle(player_id: int) -> Battle | None:
    return _ACTIVE_BATTLES.get(player_id)


def start_attack(db, player, raid: GuildRaid) -> Battle:
    """Spends one attack and opens an in-memory battle against the raid
    boss. The attack is debited HERE, before a single blow is struck --
    a player who bails on a bad opening cannot re-roll the fight for
    free."""
    if player.id in _ACTIVE_BATTLES:
        raise RaidError("You're already in the middle of a raid attack.")
    if raid.status != "active":
        raise RaidError("That raid is already over.")

    row = _get_or_create_participant(db, raid, player)
    if row.attacks_used >= MAX_ATTACKS_PER_PLAYER:
        raise RaidError(
            f"You've used all {MAX_ATTACKS_PER_PLAYER} of your attacks on this raid. "
            "Someone else will have to finish it."
        )

    remaining_cooldown = time_until_next_attack(db, raid, player)
    if remaining_cooldown is not None:
        minutes = int(remaining_cooldown.total_seconds() // 60) + 1
        raise RaidError(f"You're still regrouping -- {minutes} more minute(s) before your next attack.")

    squad = character_service.get_squad(db, player)
    if not squad:
        raise RaidError("You need at least one character in your squad first.")

    # Every raid attack starts on full HP. The attack itself is the scarce
    # resource here (MAX_ATTACKS_PER_PLAYER), so HP attrition on top would
    # be a second, hidden limit -- and one that punishes exactly the
    # players a co-op raid wants participating, since a weaker squad both
    # takes more damage and has fewer ways to heal it. See
    # combat_service.restore_squad_to_full_hp.
    combat_service.restore_squad_to_full_hp(db, squad)

    equipped_by_char = character_service.get_equipped_items_by_character(db, [pc.id for pc in squad])
    party = build_party_combatants(squad, equipped_by_char)
    base_service.apply_shrine_bonuses(db, player, party)

    boss = build_enemy_combatant(get_template_by_name(raid.boss_name), level=raid.boss_level)

    row.attacks_used += 1
    row.last_attack_at = dt.datetime.now(dt.timezone.utc)
    db.commit()

    battle = Battle(party, [boss])
    _ACTIVE_BATTLES[player.id] = battle
    _ACTIVE_RAID_ID[player.id] = raid.id
    return battle


def damage_dealt_in(battle: Battle) -> int:
    """How much HP the party stripped off the boss this attack.

    Counted as (boss max HP - boss current HP) rather than by summing the
    combat log, so it's correct regardless of which effect kinds landed
    and needs no cooperation from effects.py. A boss that was killed
    outright reads as its full max_hp, which is exactly the contribution
    that attack deserves."""
    boss = battle.enemies[0]
    return max(0, boss.max_hp - boss.current_hp)


def record_attack_damage(db, player, raid: GuildRaid, damage: int) -> dict:
    """Applies one attack's damage to the shared pool and banks the
    player's contribution. See the CONCURRENCY block in the module
    docstring -- the clamp and the defeat check both happen here, in one
    transaction, so simultaneous attacks can't over-subtract the pool or
    both claim the kill.

    Returns a summary dict for the cog to render."""
    db.refresh(raid)

    # Clamp to what's actually left: if someone else emptied the pool
    # while this player was mid-fight, only the remainder counts. Banking
    # the raw number instead would let total contributions exceed max_hp
    # and push the reward shares above 100%.
    applied = max(0, min(int(damage), raid.current_hp))
    raid.current_hp -= applied

    row = _get_or_create_participant(db, raid, player)
    row.damage_dealt += applied

    just_defeated = False
    if raid.current_hp <= 0 and raid.status == "active":
        raid.current_hp = 0
        raid.status = "defeated"
        raid.defeated_at = dt.datetime.now(dt.timezone.utc)
        just_defeated = True

    db.commit()

    return {
        "damage_dealt": int(damage),
        "damage_applied": applied,
        "just_defeated": just_defeated,
        "raid": raid,
        "participant": row,
    }


def resolve_attack(db, player) -> dict:
    """Call once the attack's battle is over (win OR lose -- damage
    counts either way, which is the point of a contribution-based raid:
    a player whose squad can't beat the boss still helps by chipping it).
    Syncs squad HP back, clears the in-memory battle, and applies the
    damage to the shared pool."""
    battle = _ACTIVE_BATTLES.get(player.id)
    if battle is None:
        raise RaidError("You're not in a raid attack right now.")

    raid = db.get(GuildRaid, _ACTIVE_RAID_ID[player.id])
    damage = damage_dealt_in(battle)

    # HP is deliberately NOT written back -- same reasoning as domains
    # (see domain_service.resolve_challenge). The scarce resource for a
    # raid is the attack count, not HP, and every attack starts fresh.
    _ACTIVE_BATTLES.pop(player.id, None)
    _ACTIVE_RAID_ID.pop(player.id, None)

    result = record_attack_damage(db, player, raid, damage)
    result["won"] = battle.result == "won"
    return result


def abandon_attack(db, player) -> None:
    """Bail out of an attack in progress. Damage already dealt STILL
    counts -- the boss doesn't heal because you walked away, and letting
    a player forfeit to erase a bad attack would just be a reroll. The
    attack itself remains spent."""
    if player.id not in _ACTIVE_BATTLES:
        return
    resolve_attack(db, player)


# ----------------------------------------------------------------------
# Rewards
# ----------------------------------------------------------------------

def contribution_share(db, raid: GuildRaid, participant: RaidParticipant) -> float:
    """This participant's fraction of all damage banked against the raid.
    Divides by the SUM OF BANKED CONTRIBUTIONS rather than by max_hp, so
    the shares of everyone involved always total exactly 1.0 even if the
    raid expired only part-cleared."""
    total = sum(p.damage_dealt for p in raid.participants) or 1
    return participant.damage_dealt / total


def claim_reward(db, player, raid: GuildRaid) -> dict:
    """Pays out one participant's share of a DEFEATED raid. Idempotent by
    the reward_claimed flag -- a double-tapped button can't pay twice."""
    if raid.status != "defeated":
        raise RaidError("That raid hasn't been defeated yet.")

    row = get_participant(db, raid.id, player.id)
    if row is None or row.damage_dealt <= 0:
        raise RaidError("You didn't take part in this raid, so there's nothing to claim.")
    if row.reward_claimed:
        raise RaidError("You've already claimed your reward for this raid.")

    tier = get_tier(raid.tier) or RAID_TIERS[0]
    share = contribution_share(db, raid, row)
    multiplier, label = contribution_tier(share)

    reward_lines = []
    for currency, base_amount in tier["rewards"].items():
        amount = int(round(base_amount * multiplier))
        if amount <= 0:
            continue
        add_currency(db, player, currency, amount)
        reward_lines.append(f"+{amount} {currency.replace('_', ' ')}")

    row.reward_claimed = True
    db.commit()

    return {
        "share": share,
        "label": label,
        "multiplier": multiplier,
        "reward_lines": reward_lines,
        "damage_dealt": row.damage_dealt,
    }


def claimable_raids(db, player, guild_id: int) -> list[GuildRaid]:
    """Defeated raids in this guild where the player contributed and
    hasn't yet claimed. Exists because a raid can be finished by someone
    else while the player is offline -- without this they'd have no way
    to find out they're owed anything."""
    return (
        db.query(GuildRaid)
        .join(RaidParticipant, RaidParticipant.raid_id == GuildRaid.id)
        .filter(
            GuildRaid.guild_id == guild_id,
            GuildRaid.status == "defeated",
            RaidParticipant.player_id == player.id,
            RaidParticipant.reward_claimed.is_(False),
            RaidParticipant.damage_dealt > 0,
        )
        .all()
    )
