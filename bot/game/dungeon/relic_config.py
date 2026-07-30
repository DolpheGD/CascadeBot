"""
Relics: run-scoped party-wide power, thrown away when the expedition ends.

WHY THESE EXIST. Permanent progression (levels, gear, HQ, shrines) is
monotonic -- it only ever goes up, and it's identical from one run to the
next, which is a large part of why runs start feeling the same after a few
hours. Relics are the opposite: temporary, drafted from a random offer,
and gone when the run is. Two runs with the same squad and the same gear
end up shaped differently because they picked up different relics. That's
what makes a fixed content pool stay interesting, and it's why the offer
is a CHOICE of three rather than a random grant.

They deliberately cost something to get. The main source is the campfire
before each boss, where taking one means NOT resting (see
dungeon_service's campfire handling) -- so every relic in your run is
paid for in HP you chose not to recover.

  * Stored on the (previously unused) Expedition.relics JSON column, as a
    list of relic ids. The catalog itself lives here in code, so a relic's
    numbers can be retuned without a migration and without touching
    anything already saved mid-run.
  * Applied at battle-build time by relic_service.apply_relic_effects,
    right after shrine bonuses -- same pattern, same place.

EFFECT SHAPES. A relic's "effect" is one of:

    {"kind": "stat", "stat": "attack", "percent": 15}
        Party-wide percent bonus to one stat, computed against each
        combatant's own value the way shrine and gear percentages already
        are, so relics never compound with each other.

    {"kind": "stat_flat", "stat": "defense", "amount": 40}
        Same but a flat addition -- used where a percent would scale
        absurdly (crit rate, recharge).

    {"kind": "passive", "passive_id": "iron_skin"}
        Grants an existing ARMOR_PASSIVES entry to every party member.
        This is the big one: it reuses the ~50 already-written, already
        battle-tested passive abilities, so relics get real mechanical
        variety (lifesteal, thornmail, extra turns on kill, shield regen)
        without inventing a second effect system alongside effects.py.

    {"kind": "poise_damage", "bonus": 1}
        Every hit the party lands chips this much extra poise -- ties
        relics directly into the break mechanic (see combatant.py).

    {"kind": "gold_multiplier", "percent": 25}
        Economy relic; read by dungeon_service when awarding run gold.

RARITY drives how often a relic shows up in an offer, nothing else -- a
Legendary relic is rarer, not mechanically special-cased.
"""

from __future__ import annotations

import random

# Relative weight of each rarity appearing in an offer.
RARITY_WEIGHTS: dict[str, float] = {
    "common": 55,
    "rare": 32,
    "legendary": 13,
}

RARITY_EMOJI: dict[str, str] = {
    "common": "⚪",
    "rare": "🔵",
    "legendary": "🟠",
}

# How many relics a campfire Attune offers to choose between.
OFFER_SIZE = 3

# Chance an ELITE victory drops a relic. Not 1.0, and that matters: a
# simulated run with guaranteed elite drops collected 8-14 relics out of a
# catalog of ~20, so by the back half of any run the player held most of
# the pool and every run converged on the same loadout -- the exact
# sameness relics exist to break up. Bosses stay guaranteed (there are
# only 2-4 non-final ones, and a boss kill should always feel like a
# milestone); elites are the frequent room type, so they're the one
# throttled.
ELITE_RELIC_DROP_CHANCE = 0.35

# Percent of max HP the squad recovers from the campfire Rest option.
# Deliberately NOT a full heal -- the whole point of the rework is that HP
# is a resource you spend across a run rather than a meter that resets for
# free before every boss. Tuned so resting twice roughly undoes one bad
# boss fight, which keeps "can I afford to take a relic instead?" a real
# question deep into a run rather than an obvious yes.
CAMPFIRE_REST_PERCENT = 50


RELICS: list[dict] = [
    # ------------------------------------------------------------------
    # Common -- straightforward stat bumps. The floor of an offer: never
    # exciting, never a wasted pick.
    # ------------------------------------------------------------------
    {
        "id": "whetstone",
        "name": "Cascade Whetstone",
        "emoji": "🗡️",
        "rarity": "common",
        "description": "+12% Attack for the whole squad, for this run.",
        "effect": {"kind": "stat", "stat": "attack", "percent": 12},
    },
    {
        "id": "focusing_lens",
        "name": "Focusing Lens",
        "emoji": "🔷",
        "rarity": "common",
        "description": "+12% Elemental damage for the whole squad, for this run.",
        "effect": {"kind": "stat", "stat": "elemental", "percent": 12},
    },
    {
        "id": "plated_lining",
        "name": "Plated Lining",
        "emoji": "🛡️",
        "rarity": "common",
        "description": "+15% Defense for the whole squad, for this run.",
        "effect": {"kind": "stat", "stat": "defense", "percent": 15},
    },
    {
        "id": "field_rations",
        "name": "Field Rations",
        "emoji": "🍖",
        "rarity": "common",
        "description": "+15% max HP for the whole squad, for this run.",
        "effect": {"kind": "stat", "stat": "max_hp", "percent": 15},
    },
    {
        "id": "spring_heels",
        "name": "Spring Heels",
        "emoji": "💨",
        "rarity": "common",
        "description": "+10% Speed -- act earlier in the cycle.",
        "effect": {"kind": "stat", "stat": "speed", "percent": 10},
    },
    {
        "id": "spare_cells",
        "name": "Spare Cells",
        "emoji": "🔋",
        "rarity": "common",
        "description": "+4 Recharge -- build Energy and SP faster on every Attack.",
        "effect": {"kind": "stat_flat", "stat": "recharge", "amount": 4},
    },
    {
        "id": "hairline_sight",
        "name": "Hairline Sight",
        "emoji": "🎯",
        "rarity": "common",
        "description": "+10 Crit Rate for the whole squad.",
        "effect": {"kind": "stat_flat", "stat": "crit_rate", "amount": 10},
    },

    # ------------------------------------------------------------------
    # Rare -- granted passives. These change how a fight PLAYS, not just
    # how big the numbers are, which is the point of drafting them.
    # ------------------------------------------------------------------
    {
        "id": "leeching_sigil",
        "name": "Leeching Sigil",
        "emoji": "🩸",
        "rarity": "rare",
        "description": "The whole squad gains Vampiric Edge -- heal for a portion of damage dealt.",
        "effect": {"kind": "passive", "passive_id": "vampiric_edge"},
    },
    {
        "id": "bramble_wardstone",
        "name": "Bramble Wardstone",
        "emoji": "🌵",
        "rarity": "rare",
        "description": "The whole squad gains Thornmail -- attackers take damage back.",
        "effect": {"kind": "passive", "passive_id": "thornmail"},
    },
    {
        "id": "ironhide_totem",
        "name": "Ironhide Totem",
        "emoji": "🪨",
        "rarity": "rare",
        "description": "The whole squad gains Iron Skin -- flat reduction on every hit taken.",
        "effect": {"kind": "passive", "passive_id": "iron_skin"},
    },
    {
        # NB: id is deliberately not "momentum_core" -- that's already an
        # ARMOR_PASSIVES id. Different namespaces, but the collision would
        # be needlessly confusing to read in a log or a save file.
        "id": "momentum_engine",
        "name": "Momentum Engine",
        "emoji": "📈",
        "rarity": "rare",
        "description": "The whole squad gains Momentum -- stacking power the longer the fight runs.",
        "effect": {"kind": "passive", "passive_id": "momentum"},
    },
    {
        "id": "arcane_cell",
        "name": "Arcane Cell",
        "emoji": "💧",
        "rarity": "rare",
        "description": "The whole squad gains Arcane Battery -- SP regenerates every turn.",
        "effect": {"kind": "passive", "passive_id": "arcane_battery"},
    },
    {
        "id": "second_breath",
        "name": "Second Breath",
        "emoji": "🌬️",
        "rarity": "rare",
        "description": "The whole squad gains Second Wind -- a heal when dropping low.",
        "effect": {"kind": "passive", "passive_id": "second_wind"},
    },
    {
        "id": "breaker_charge",
        "name": "Breaker's Charge",
        "emoji": "💫",
        "rarity": "rare",
        "description": "Every hit chips 1 extra Poise -- break enemies noticeably sooner.",
        "effect": {"kind": "poise_damage", "bonus": 1},
    },
    {
        "id": "prospectors_ledger",
        "name": "Prospector's Ledger",
        "emoji": "🪙",
        "rarity": "rare",
        "description": "+30% gold from everything for the rest of this run.",
        "effect": {"kind": "gold_multiplier", "percent": 30},
    },

    # ------------------------------------------------------------------
    # Legendary -- run-defining. Rare enough that seeing one in an offer
    # is itself the moment, and strong enough to be worth skipping a Rest.
    # ------------------------------------------------------------------
    {
        "id": "executioners_mark",
        "name": "Executioner's Mark",
        "emoji": "☠️",
        "rarity": "legendary",
        "description": "The whole squad gains Executioner -- greatly increased Crit Damage.",
        "effect": {"kind": "passive", "passive_id": "executioner"},
    },
    {
        "id": "undying_ember",
        "name": "Undying Ember",
        "emoji": "🔥",
        "rarity": "legendary",
        "description": "The whole squad gains Undying Will -- cheat death once per battle.",
        "effect": {"kind": "passive", "passive_id": "undying_will"},
    },
    {
        "id": "relentless_engine",
        "name": "Relentless Engine",
        "emoji": "⚡",
        "rarity": "legendary",
        "description": "The whole squad gains Soul Harvest -- restore resources on a kill.",
        "effect": {"kind": "passive", "passive_id": "soul_harvest"},
    },
    {
        "id": "shatterpoint_prism",
        "name": "Shatterpoint Prism",
        "emoji": "💠",
        "rarity": "legendary",
        "description": "Every hit chips 2 extra Poise -- shatter even bosses on schedule.",
        "effect": {"kind": "poise_damage", "bonus": 2},
    },
    {
        "id": "warlords_banner",
        "name": "Warlord's Banner",
        "emoji": "🚩",
        "rarity": "legendary",
        "description": "+20% Attack and +20% Elemental for the whole squad.",
        "effect": {"kind": "multi", "effects": [
            {"kind": "stat", "stat": "attack", "percent": 20},
            {"kind": "stat", "stat": "elemental", "percent": 20},
        ]},
    },
]

RELICS_BY_ID: dict[str, dict] = {relic["id"]: relic for relic in RELICS}


def get_relic(relic_id: str) -> dict | None:
    return RELICS_BY_ID.get(relic_id)


def roll_offer(
    rng: random.Random,
    exclude_ids: set[str] | None = None,
    size: int = OFFER_SIZE,
) -> list[dict]:
    """Rolls `size` DISTINCT relics to choose between, weighted by rarity
    and skipping anything in `exclude_ids` (normally the relics already
    held this run -- a duplicate offer is a wasted choice, and stacking
    identical relics isn't supported by the effect application anyway).

    Falls back to however many are left if the pool runs dry late in a
    long run, and returns an empty list only if the player somehow holds
    everything."""
    exclude_ids = exclude_ids or set()
    pool = [r for r in RELICS if r["id"] not in exclude_ids]
    offer: list[dict] = []

    while pool and len(offer) < size:
        weights = [RARITY_WEIGHTS.get(r["rarity"], 1) for r in pool]
        pick = rng.choices(pool, weights=weights, k=1)[0]
        offer.append(pick)
        pool.remove(pick)

    return offer


def format_relic(relic: dict) -> str:
    """One-line display form, used by both the offer buttons and the
    run-summary listing so they can never drift apart."""
    rarity_emoji = RARITY_EMOJI.get(relic["rarity"], "")
    return f"{relic['emoji']} **{relic['name']}** {rarity_emoji}\n{relic['description']}"
