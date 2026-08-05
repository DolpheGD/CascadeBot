"""
Tuning for co-op guild raids (bot/services/raid_service.py,
bot/database/models/raid_model.py).

Pure config, no imports from the rest of the game, same as every other
*_config module here -- so the numbers below can be retuned without a
migration and without touching any logic.

----------------------------------------------------------------------
How the HP pool is sized
----------------------------------------------------------------------
A raid boss's HP is NOT the enemy template's own HP. It's an independent
pool (GuildRaid.max_hp) sized so that clearing it takes a group rather
than a person: roughly EXPECTED_PARTICIPANTS players spending most of
their MAX_ATTACKS_PER_PLAYER attacks. The battle a player actually
fights uses a normal Combatant built from the template at
`boss_level` -- the shared pool is what their damage is subtracted from,
not what they're punching through in one sitting.

This split is deliberate. If the raid boss were simply an enemy with a
huge HP bar, a single attack could never meaningfully dent it and the
per-attack fight would feel pointless; conversely a boss a strong player
can solo isn't a raid. Separating "the fight you have" from "the pool
you contribute to" lets both be tuned for what they individually need to
feel like.

----------------------------------------------------------------------
Reward tiers
----------------------------------------------------------------------
CONTRIBUTION_TIERS pay out by SHARE OF TOTAL DAMAGE, not by rank. Rank
would mean a server's strongest player always takes the top prize and
everyone else is playing for scraps; share means a newer player who
genuinely showed up and did 10% of the work gets the 10% reward, no
matter who else was in the raid. Everyone who lands a single attack gets
at least the participation tier -- turning up is always worth something.
"""

from __future__ import annotations

import datetime as dt

# ----------------------------------------------------------------------
# PACING DEFAULTS.
#
# Each of these four is a DEFAULT that any tier may override with a key
# of the same lowercase name (see the accessors further down, and the
# Rift Patrol tier, which overrides all four). They're what decides how
# long a raid takes in wall-clock time, and a starter raid and a
# week-long endgame raid want very different answers -- a raid that a
# new server can't finish inside a sitting is a raid they watch expire.
# ----------------------------------------------------------------------

# How long a raid stays open before expiring unbeaten. Also matters
# because only ONE raid runs per server at a time: an over-long duration
# on an easy tier means a stale raid blocks the server from summoning
# anything else.
RAID_DURATION = dt.timedelta(days=7)

# Attacks one player may spend on one raid. The scarcity is the whole
# reason a raid is cooperative: nobody can clear the pool alone, so a
# server either coordinates or doesn't finish.
MAX_ATTACKS_PER_PLAYER = 10

# Sizing assumption for the HP pool -- see the module docstring. Tuned
# low on purpose: most Discord servers running a bot like this have a
# handful of active players, not dozens, and a pool sized for 20 people
# is a pool that never gets cleared.
EXPECTED_PARTICIPANTS = 4

# Cooldown between one player's attacks.
#
# Was 10 minutes, which was solving the wrong problem. The worry was that
# the fastest clicker would monopolise the contribution table before
# anyone else saw the announcement -- but ATTACKS are already the scarce
# resource, and rewards are paid by SHARE of damage, so someone spending
# all ten immediately doesn't take anything from anyone; they just finish
# early and stop. What ten minutes actually did was make a raid
# unfinishable in one sitting: a player with 10 attacks was looking at
# 90 minutes of waiting, and most of them simply never came back for the
# rest.
#
# 45 seconds keeps the one thing worth keeping -- you can't macro through
# a whole raid in five seconds, and a fight you're losing badly still
# costs you a beat to reconsider -- while letting a raid be a thing you
# sit down and do.
ATTACK_COOLDOWN = dt.timedelta(seconds=45)

# ----------------------------------------------------------------------
# BOSS HP MULTIPLIER -- and the bug it fixes.
#
# An attack contributes "damage dealt to the boss", which is computed as
# (boss max HP - boss current HP). That number is CEILINGED by the boss's
# own max HP: once it's dead, extra damage has nowhere to go. Raid boss
# templates are ordinary enemies with 1,200-1,600 HP at their tier's
# level, so before this existed the most any single attack could ever
# contribute was ~1,500 -- while `hp_per_attack` assumed 4,000-26,000.
#
# The result was that every raid above the starter tier was
# ARITHMETICALLY unclearable: a 160,000 pool against a hard ceiling of
# ~1,500 per attack needs 106 attacks, and 4 players x 10 attacks is 40.
# Nobody would ever have seen a raid die, no matter how strong they got.
#
# Multiplying only HP is the narrow fix: the boss doesn't hit harder or
# move faster than its template says, it just has the health bar a raid
# boss ought to have -- which also gives the fight enough turns for a
# squad's kit to actually come online.
# ----------------------------------------------------------------------
RAID_BOSS_HP_MULTIPLIER = 8.0

# ----------------------------------------------------------------------
# SIZING RULE for hp_per_attack.
#
# Because an attack's contribution is hard-capped at the boss's max HP,
# `hp_per_attack` is only meaningful as a FRACTION of that bar -- set it
# above 100% and the tier is unclearable however many people show up.
# Every tier below sits in the 25-55% band: an attack that strips about
# half the boss is a good attack, and a squad that can actually kill it
# banks roughly two attacks' worth of credit in one go.
#
# tools/check_raid_pools.py asserts this holds for every tier, so a
# retune that quietly recreates the unclearable-pool bug fails loudly
# instead of shipping.
# ----------------------------------------------------------------------
MAX_HEALTHY_ATTACK_FRACTION = 0.60


# ----------------------------------------------------------------------
# PER-ATTACK DIFFICULTY.
#
# The raid TIER is chosen once by whoever summons it and fixes the boss
# for everyone. That's a problem in a co-op feature: a server's strongest
# and weakest players share one raid, and a single boss level is either
# unbeatable for one of them or trivial for the other. Since damage is
# what counts (see raid_service), a player who can't survive the fight
# contributes almost nothing and stops bothering.
#
# So each ATTACK picks its own difficulty. The boss is rebuilt at
# `level_offset` relative to the raid's own level, and the damage that
# attack contributes is multiplied by `contribution_multiplier`.
#
# The multiplier is the whole point and has to exist explicitly: damage
# dealt does NOT naturally rise with boss level -- if anything a
# higher-level boss has more DEF and takes LESS, so without this, picking
# the hard version would be strictly worse. Rewarding the harder fight is
# what makes "fight above your weight for more credit" a real decision
# rather than a trap.
#
# Deliberately sub-linear at the bottom and super-linear at the top: a
# Skirmish contributes 0.55x for a much easier fight (so a weak player
# still meaningfully moves the bar rather than being locked out), while
# Apex pays 2.6x for a boss 30 levels up.
# ----------------------------------------------------------------------
RAID_DIFFICULTIES: list[dict] = [
    {
        # Below Skirmish, for players who can't clear even that. A boss 40
        # levels down is beatable by almost any squad, and 0.3x still
        # moves the shared bar -- which is the point: the failure mode
        # this prevents is a player who cannot contribute AT ALL deciding
        # raids aren't for them. Contributing slowly is a rung on a
        # ladder; contributing nothing is a closed door.
        "id": "recon", "name": "Recon", "emoji": "⚪",
        "level_offset": -40, "contribution_multiplier": 0.3,
        "description": "The weakest version there is. Slow credit, but anyone can finish it.",
    },
    {
        "id": "skirmish", "name": "Skirmish", "emoji": "🟢",
        "level_offset": -20, "contribution_multiplier": 0.55,
        "description": "Much weaker boss. Contributes less, but anyone can clear it.",
    },
    {
        "id": "standard", "name": "Standard", "emoji": "🔵",
        "level_offset": 0, "contribution_multiplier": 1.0,
        "description": "The raid as summoned.",
    },
    {
        "id": "elite", "name": "Elite", "emoji": "🟠",
        "level_offset": 15, "contribution_multiplier": 2.0,
        "description": "A tougher boss for a well-geared squad.",
    },
    {
        "id": "apex", "name": "Apex", "emoji": "🔴",
        "level_offset": 30, "contribution_multiplier": 3.5,
        "description": "Punishing. Only worth attempting if you can actually win it.",
    },
]

DEFAULT_RAID_DIFFICULTY = "standard"

# Boss level can never drop below this however far a Skirmish offsets it
# -- a level-1 raid boss would be a free contribution farm.
MIN_RAID_BOSS_LEVEL = 5


def get_difficulty(difficulty_id: str) -> dict | None:
    return next((d for d in RAID_DIFFICULTIES if d["id"] == difficulty_id), None)


def raid_boss_level(raid_level: int, difficulty: dict) -> int:
    """The level the boss is actually built at for one attack."""
    return max(MIN_RAID_BOSS_LEVEL, min(100, raid_level + difficulty["level_offset"]))


# ----------------------------------------------------------------------
# SUMMON COOLDOWN -- the anti-farm rule.
#
# `start_raid` used to refuse only if a raid was ALREADY ACTIVE, so the
# loop was: clear Rift Patrol, immediately summon another Rift Patrol,
# repeat. At 60 shards a clear that is an unbounded shard faucet gated
# only by how fast a server can press buttons -- and the EASIEST tier
# paid it, which is exactly backwards.
#
# So the cooldown runs INVERSELY to difficulty: the cheap tiers are
# rate-limited hardest, and Nightmare is nearly free to re-summon because
# clearing it is the limiting factor all by itself.
#
# Measured from the previous raid of that tier ENDING in that guild, so a
# long raid doesn't also serve its own cooldown.
# ----------------------------------------------------------------------
SUMMON_COOLDOWNS: dict[str, dt.timedelta] = {
    "patrol":    dt.timedelta(hours=20),
    "skirmish":  dt.timedelta(hours=20),
    "incursion": dt.timedelta(hours=16),
    "standard":  dt.timedelta(hours=12),
    "elite":     dt.timedelta(hours=8),
    "nightmare": dt.timedelta(hours=6),
}


def summon_cooldown(tier_id: str) -> dt.timedelta:
    return SUMMON_COOLDOWNS.get(tier_id, dt.timedelta(hours=12))


RAID_TIERS: list[dict] = [
    {
        # ------------------------------------------------------------------
        # THE STARTER RAID.
        #
        # Every other tier is sized as a multi-day project for a whole
        # server, which is right for a raid but wrong for a player's FIRST
        # one: a new server met a level-45 boss behind a 160,000 HP pool and
        # a week-long timer, and most of them simply never saw a raid get
        # cleared. A feature nobody has finished once is a feature nobody
        # understands.
        #
        # So this tier is deliberately small in every dimension at once --
        # that's why the four pacing values are overridden together rather
        # than just dropping the HP:
        #   * 2 expected participants and 4 attacks each -> an 8-attack
        #     pool, so a PAIR can finish it, and one determined player gets
        #     most of the way alone.
        #   * a 3-minute attack cooldown instead of 10, so those 4 attacks
        #     fit inside one sitting rather than an afternoon.
        #   * 2 days instead of 7, because only one raid runs per server:
        #     a starter raid that lingers all week is a starter raid that
        #     BLOCKS the real ones.
        #
        # Rewards are deliberately generous FOR THIS LEVEL -- see the
        # REWARDS block below.
        # ------------------------------------------------------------------
        "id": "patrol",
        "name": "Rift Patrol",
        "emoji": "🟩",
        "boss_pool": [
            "Rogue Security Drone", "Concussion Drone",
            "Ad-Drone Swarm Unit", "Xender Enforcer", "Xender Loyalist",
            "Mech Gunpod", "Alan", "Jynxzi", "Refense Hater",
            "Illusion of Rex"
        ],
        "boss_level": 18,
        # ~50% of the boss's (multiplied) health bar per attack -- see the
        # SIZING RULE below. Measured: a roster-15 squad with no gear at
        # all credits ~1,000 per attack here, so this clears in about four
        # -- one player's entire allowance, or an easy afternoon for two.
        "hp_per_attack": 520,
        "min_roster_levels": 0,
        "expected_participants": 2,
        "attacks_per_player": 4,
        "attack_cooldown": dt.timedelta(seconds=20),
        "duration": dt.timedelta(days=2),
        "description": "A quick first raid. Two people can finish it in one sitting.",
        "rewards": {
            "gold": 900,
            "shards": 22,
            "wood": 150,
            "stone": 150,
            "metal": 40,
            "reroll_tokens": 10,
        },
        # Lootboxes as a raid reward exist for this tier in particular: at
        # the point a player is clearing it, a piece of gear is a bigger
        # deal than any amount of currency, and "I got something I can
        # equip" is the tangible payoff that makes them come back for the
        # next raid.
        "reward_lootbox": ("uncommon", 1),
    },
    {
        # ------------------------------------------------------------------
        # SKIRMISH and INCURSION exist because the ladder had a CLIFF.
        #
        # The pools ran 4,160 -> 160,000 -> 440,000 -> 880,000: a 38x jump
        # followed by 2.8x and 2.0x. All three sizing axes moved at once
        # between the first two tiers (hp_per_attack 520 -> 4,000,
        # participants 2 -> 4, attacks 4 -> 10), so a server that cleared
        # the starter raid in an afternoon met a wall it could not
        # meaningfully chip at.
        #
        # The ladder is now 4.2k -> 13.2k -> 42k -> 125k -> 400k -> 880k,
        # which is 3.2x / 3.2x / 3.0x / 3.2x / 2.2x. tools/check_raid_pools.py
        # asserts both clearability and the step ratio.
        # ------------------------------------------------------------------
        "id": "skirmish",
        "name": "Border Skirmish",
        "emoji": "🟨",
        "boss_pool": [
            "Ocellios Test Subject", "Voidwarp Construct",
            "Xendium Overcharge Drone", "Xender Airship", "MianotAI",
            "Xender Tank", "Xender Convoy", "Glacial Exterminator",
            "Kiradmj", "Frostblock", "Loona", "Dolpo", "Xero",
            "Bulwark Sentinel"
        ],
        "boss_level": 28,
        "hp_per_attack": 1_100,
        "min_roster_levels": 25,
        "expected_participants": 3,
        "attacks_per_player": 4,
        "attack_cooldown": dt.timedelta(seconds=30),
        "duration": dt.timedelta(days=3),
        "description": "A step up from the patrol. Three people, one evening.",
        "rewards": {
            "gold": 1_700,
            "shards": 45,
            "wood": 220,
            "stone": 220,
            "metal": 90,
            "reroll_tokens": 18,
        },
        "reward_lootbox": ("uncommon", 2),
    },
    {
        "id": "incursion",
        "name": "Frontier Incursion",
        "emoji": "🟧",
        "boss_pool": [
            "H-Nation Vanguard", "HHyper Airship", "Shatterjaw Reaver",
            "Permafrost Guardian", "Blightspire Adept",
            "Wasteland Colosseum Champion", "Sir Vengeance", "Samuel",
            "Triv", "Thedoggyp", "Bt03", "XG-23 Heavy Drone", "The Giveaway",
            "Ledger Warden", "Hater Ringleader"
        ],
        "boss_level": 38,
        "hp_per_attack": 1_750,
        "min_roster_levels": 70,
        "expected_participants": 4,
        "attacks_per_player": 6,
        "attack_cooldown": dt.timedelta(seconds=40),
        "duration": dt.timedelta(days=3),
        "description": "The first raid that really wants a full server.",
        "rewards": {
            "gold": 2_900,
            "shards": 80,
            "crystal": 45,
            "metal": 140,
            "xendium": 18,
            "reroll_tokens": 26,
        },
        "reward_lootbox": ("rare", 1),
    },
    {
        "id": "standard",
        "name": "Cascade Offensive",
        "emoji": "🌀",
        # Boss templates are drawn from bot/game/combat/enemies.py by
        # name. Several are listed per tier so consecutive raids in the
        # same server aren't identical.
        "boss_pool": [
            "Corrupted Bli", "Corrupted Eris Sentry", "Aerion Mk1",
            "Void Hydra", "Dorve", "SAJ II", "NF", "Ashplate Warden",
            "Propaganda Broadcast Unit", "The Revengeance Block",
            "Skybridge Sentinel", "Acatrya Elite Guard", "Abyssal Custodian",
            "Broskm", "Duko"
        ],
        "boss_level": 45,
        # Pool = this, times EXPECTED_PARTICIPANTS, times
        # MAX_ATTACKS_PER_PLAYER. i.e. "the damage we expect one average
        # attack to do".
        "hp_per_attack": 3_125,
        # Raised from 0 when Rift Patrol was added. With both at 0 a brand
        # new server would summon this one first -- and it's a level-45
        # boss -- which is exactly the problem the starter tier exists to
        # solve. 60 is about four level-15 characters: reachable within a
        # first session or two, so this is a "next step", not a wall.
        "min_roster_levels": 150,
        "description": "The standard server raid. A few days of chipping away.",
        "rewards": {
            # Multiplied by the player's contribution tier below.
            "gold": 5_600,
            "shards": 170,
            "crystal": 85,
            "xendium": 36,
            "reroll_tokens": 35,
        },
        "reward_lootbox": ("rare", 1),
    },
    {
        "id": "elite",
        "name": "Voidcrest Breach",
        "emoji": "🕳️",
        "boss_pool": [
            "Borehole", "Rupture", "Gatekeeper", "The Chairman",
            "The Auditor", "The Censor", "The Lector of Ledgers",
            "Stubby's Failsafe", "Acatrya Prime Enforcer",
            "Boss John's Driller Prototype", "Ocellios Train", "X-RR"
        ],
        "boss_level": 70,
        "hp_per_attack": 10_000,
        "min_roster_levels": 300,
        "description": "A tougher boss and a much bigger pool. Bring the server.",
        "rewards": {
            "gold": 17_000,
            "shards": 460,
            "crystal": 220,
            "xendium": 110,
            "void": 50,
            "reroll_tokens": 90,
        },
        "reward_lootbox": ("epic", 1),
    },
    {
        "id": "nightmare",
        "name": "The Xender Protocol",
        "emoji": "☠️",
        # Rohan joins Xender as a nightmare-tier raid boss -- he was
        # authored as the hardest template on the roster (4 actions a
        # cycle, 34 poise) and a raid is the only place a squad gets to
        # fight something that size cooperatively.
        "boss_pool": [
            "Xender", "Rohan", "X-RR", "Eris Sentinel",
            "Acatrya Prime Enforcer", "Stubby's Failsafe", "The Chairman",
            "Gatekeeper", "Ocellios Train", "Boss John's Driller Prototype"
        ],
        "boss_level": 95,
        # Sized against ROHAN, not Xender: the pool has to be clearable
        # whichever boss rolls, and Rohan's bar is the smaller of the
        # two (he is dangerous through 4 actions a cycle, not bulk).
        # tools/check_raid_pools.py caught this the moment he was added
        # to the pool -- at 26,000 an on-target attack needed 66% of his
        # health bar, over the healthy limit.
        "hp_per_attack": 17_500,
        "min_roster_levels": 650,
        "description": "Xender himself. The hardest thing in the game.",
        "rewards": {
            "gold": 44_000,
            "shards": 1_150,
            "crystal": 520,
            "xendium": 280,
            "void": 160,
            "entropy": 160,
            "reroll_tokens": 230,
        },
        "reward_lootbox": ("legendary", 1),
    },
]


# (minimum share of total damage, multiplier on the tier's reward table,
#  label). Checked highest-first. The top band deliberately pays 2.5x
# rather than 10x: a raid where the top contributor takes almost
# everything teaches everyone else not to bother next time.
# Thresholds are set against the EVEN SPLIT, not against domination.
#
# A raid sized for EXPECTED_PARTICIPANTS (4) splits evenly at 25% each --
# which meant the old 30% top band was unreachable by a group that
# cooperated normally. Exactly one player per raid could ever hit it, and
# only by taking share away from teammates. For a co-op feature that's
# backwards: it made helping zero-sum, and it made the headline reward a
# thing most players would simply never see.
#
# The bands now reward PULLING YOUR WEIGHT rather than out-competing your
# server. At a 4-way even split everyone clears Vanguard; someone doing
# half the average still reaches Striker; someone who turned up for one
# attack still gets Contributor. The ladder punishes freeloading instead
# of punishing cooperation.
CONTRIBUTION_TIERS: list[tuple[float, float, str]] = [
    (0.22, 2.5, "🥇 Vanguard"),
    (0.14, 2.0, "🥈 Spearhead"),
    (0.07, 1.5, "🥉 Striker"),
    (0.03, 1.15, "Contributor"),
    (0.0, 0.8, "Participant"),
]

# ----------------------------------------------------------------------
# DIFFICULTY REWARD BONUS -- paying more for the harder fight, in
# ABSOLUTE terms rather than relative ones.
#
# `contribution_multiplier` already rewards difficulty, but only
# RELATIVELY: it inflates your damage credit, which raises your SHARE of
# the total. If everybody picks Apex, everybody's share is unchanged and
# nobody is paid a penny more for a much harder fight.
#
# This is the absolute half. A player's best difficulty across the raid
# is recorded (RaidParticipant.best_difficulty) and multiplies their
# final payout, so choosing the hard version is worth something even if
# the whole server chose it too.
# ----------------------------------------------------------------------
DIFFICULTY_REWARD_BONUS: dict[str, float] = {
    "recon": 0.85,
    "skirmish": 0.95,
    "standard": 1.0,
    "elite": 1.25,
    "apex": 1.6,
}


def difficulty_reward_bonus(difficulty_id: str | None) -> float:
    return DIFFICULTY_REWARD_BONUS.get(difficulty_id or DEFAULT_RAID_DIFFICULTY, 1.0)


def get_tier(tier_id: str) -> dict | None:
    return next((t for t in RAID_TIERS if t["id"] == tier_id), None)


# ----------------------------------------------------------------------
# Per-tier pacing accessors.
#
# Every one of these takes a tier dict (or None, for callers that only
# have a raid row from before a tier was renamed) and falls back to the
# module default. Going through accessors rather than reading the
# constants directly is what lets a single tier be paced differently
# without every call site growing a special case -- and means adding a
# fifth tier with its own pacing needs no code change at all.
# ----------------------------------------------------------------------

def attacks_per_player(tier: dict | None) -> int:
    return int((tier or {}).get("attacks_per_player", MAX_ATTACKS_PER_PLAYER))


def expected_participants(tier: dict | None) -> int:
    return int((tier or {}).get("expected_participants", EXPECTED_PARTICIPANTS))


def attack_cooldown(tier: dict | None) -> dt.timedelta:
    return (tier or {}).get("attack_cooldown", ATTACK_COOLDOWN)


def raid_duration(tier: dict | None) -> dt.timedelta:
    return (tier or {}).get("duration", RAID_DURATION)


def boss_hp_multiplier(tier: dict | None) -> float:
    return float((tier or {}).get("boss_hp_multiplier", RAID_BOSS_HP_MULTIPLIER))


def pool_hp_for(tier: dict) -> int:
    """Total shared HP for a raid of this tier -- see the module
    docstring for why this is independent of the boss template's own
    max_hp."""
    return tier["hp_per_attack"] * expected_participants(tier) * attacks_per_player(tier)


def contribution_tier(share: float) -> tuple[float, str]:
    """(reward multiplier, label) for a damage share in 0.0-1.0."""
    for minimum, multiplier, label in CONTRIBUTION_TIERS:
        if share >= minimum:
            return multiplier, label
    return CONTRIBUTION_TIERS[-1][1], CONTRIBUTION_TIERS[-1][2]


# ----------------------------------------------------------------------
# REWARDS.
#
# rewards_for is the single place a payout is computed, and both the
# PREVIEW the player reads before committing and the ACTUAL grant call
# it. That's deliberate: a preview computed separately from the payout is
# a preview that eventually lies, and "the raid promised me X and gave me
# Y" is worse than showing nothing at all.
# ----------------------------------------------------------------------

def rewards_for(tier: dict, multiplier: float) -> dict[str, int]:
    """{currency: amount} for one participant at `multiplier`. Amounts
    that round to zero are dropped rather than shown as "+0"."""
    out = {}
    for currency, base in (tier.get("rewards") or {}).items():
        amount = int(round(base * multiplier))
        if amount > 0:
            out[currency] = amount
    return out


def lootbox_for(tier: dict, multiplier: float) -> tuple[str, int] | None:
    """(lootbox tier, quantity) for one participant, or None if this raid
    tier doesn't grant boxes. Quantity floors at 1 rather than rounding to
    0 -- anyone who contributed enough to claim at all should get the box,
    since it's the part of the payout they can actually equip."""
    entry = tier.get("reward_lootbox")
    if not entry:
        return None
    box_tier, quantity = entry
    return box_tier, max(1, int(round(quantity * multiplier)))
