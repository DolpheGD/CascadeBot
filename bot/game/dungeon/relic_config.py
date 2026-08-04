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
Legendary relic is rarer, not mechanically special-cased. The one
near-exception is "cursed", which is still just an offer weight, but is
used exclusively for relics that pair a large upside with a real
drawback (see the CURSED block at the end of the catalog). Nothing in
the code branches on it; it exists so those relics read as a distinct
category to the player before they commit.

A negative percent in a "stat"/"stat_flat" effect is fully supported and
needs no special handling -- relic_service applies it through the exact
same multiply-and-add path as a positive one, and _sync_pools clamps
current HP/SP into any reduced maximum. That's what lets the cursed tier
express its drawbacks as ordinary data rather than new machinery.
"""

from __future__ import annotations

import random

# Relative weight of each rarity appearing in an offer.
#
# "cursed" is a rarity in the offer-weighting sense only -- mechanically
# it means "powerful, WITH a real downside" rather than "rarer". See the
# CURSED RELICS block below the catalog for the design reasoning. Weighted
# to show up a little less often than rare so an offer is usually a
# straight choice and only sometimes a gamble.
RARITY_WEIGHTS: dict[str, float] = {
    "common": 42,
    "rare": 27,
    "cursed": 19,
    "legendary": 12,
}

RARITY_EMOJI: dict[str, str] = {
    "common": "⚪",
    "rare": "🔵",
    "cursed": "🟣",
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
        # Rebalance pass: was a flat +2 poise per hit, which stacked with
        # Breaker's Charge into a permanent stunlock (see the BREAK
        # RESISTANCE block in bot/game/combat/combatant.py). Re-pointed at
        # the new poise-SHRED lever instead of yet more per-hit chip:
        # shred is the direct counter to break resistance, so this stays
        # the best break relic in the game without being additive with
        # the common one.
        "id": "shatterpoint_prism",
        "name": "Shatterpoint Prism",
        "emoji": "💠",
        "rarity": "legendary",
        "description": "Every hit chips 1 extra Poise, and the whole squad's Breaks deal +25% bonus damage.",
        "effect": {"kind": "multi", "effects": [
            {"kind": "poise_damage", "bonus": 1},
            {"kind": "passive", "passive_id": "shatterpoint_focus"},
        ]},
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

    # ------------------------------------------------------------------
    # CURSED -- larger numbers than any Legendary, paid for with a real,
    # permanent-for-the-run downside.
    #
    # WHY THIS TIER EXISTS. Every relic above is a strict upgrade: taking
    # one is never worse than not taking one, so the only question an
    # offer asks is "which of these three is biggest for my squad?"
    # That's a preference, not a decision. A cursed relic asks an actual
    # question, and the answer legitimately changes run to run -- +45%
    # Attack for -35% Defense is an obvious yes on a squad that's ending
    # fights in three turns and an obvious no on one that's limping into
    # the next boss at half HP.
    #
    # They're built from PAIRED stat effects rather than new machinery,
    # so the drawback is applied by exactly the same code path as the
    # upside (relic_service.apply_relic_effects) and can't desync from
    # it. A negative "stat" percent works out of the box there -- it's
    # the same multiply-and-add every positive relic uses.
    #
    # The one rule they all follow: a drawback may never be lethal on its
    # own. Nothing here reduces max HP below the squad's current HP or
    # zeroes a stat, because "you took a relic and instantly lost the
    # run" is a trap, not a trade-off -- see _sync_pools in
    # relic_service.py, which clamps current HP into any new maximum.
    # ------------------------------------------------------------------
    {
        "id": "berserkers_pact",
        "name": "Berserker's Pact",
        "emoji": "🩸",
        "rarity": "cursed",
        "description": "+45% Attack for the whole squad -- but -35% Defense. Hit like a truck, fold like paper.",
        "effect": {"kind": "multi", "effects": [
            {"kind": "stat", "stat": "attack", "percent": 45},
            {"kind": "stat", "stat": "defense", "percent": -35},
        ]},
    },
    {
        "id": "glass_reactor",
        "name": "Glass Reactor",
        "emoji": "💥",
        "rarity": "cursed",
        "description": "+50% Elemental and +25 Crit Rate -- but -30% max HP. Everything you have, all at once.",
        "effect": {"kind": "multi", "effects": [
            {"kind": "stat", "stat": "elemental", "percent": 50},
            {"kind": "stat_flat", "stat": "crit_rate", "amount": 25},
            {"kind": "stat", "stat": "max_hp", "percent": -30},
        ]},
    },
    {
        "id": "leaden_bulwark",
        "name": "Leaden Bulwark",
        "emoji": "🗿",
        "rarity": "cursed",
        "description": "+60% Defense and +35% max HP -- but -30% Speed. Unmovable, and unhurried.",
        "effect": {"kind": "multi", "effects": [
            {"kind": "stat", "stat": "defense", "percent": 60},
            {"kind": "stat", "stat": "max_hp", "percent": 35},
            {"kind": "stat", "stat": "speed", "percent": -30},
        ]},
    },
    {
        "id": "hollow_crown",
        "name": "Hollow Crown",
        "emoji": "👑",
        "rarity": "cursed",
        "description": "The squad gains Vampiric Edge and +30% Attack -- but -40% healing capacity from SP (max SP).",
        "effect": {"kind": "multi", "effects": [
            {"kind": "passive", "passive_id": "vampiric_edge"},
            {"kind": "stat", "stat": "attack", "percent": 30},
            {"kind": "stat", "stat": "max_mana", "percent": -40},
        ]},
    },
    {
        "id": "gamblers_coin",
        "name": "Gambler's Coin",
        "emoji": "🪙",
        "rarity": "cursed",
        "description": "+80% gold from everything -- but -20% Attack and -20% Elemental. You came here to get paid, not to fight.",
        "effect": {"kind": "multi", "effects": [
            {"kind": "gold_multiplier", "percent": 80},
            {"kind": "stat", "stat": "attack", "percent": -20},
            {"kind": "stat", "stat": "elemental", "percent": -20},
        ]},
    },
    {
        "id": "overclocked_core",
        "name": "Overclocked Core",
        "emoji": "⚡",
        "rarity": "cursed",
        "description": "+35% Speed and +8 Recharge -- but -25% max HP. Act first, and often; survive less.",
        "effect": {"kind": "multi", "effects": [
            {"kind": "stat", "stat": "speed", "percent": 35},
            {"kind": "stat_flat", "stat": "recharge", "amount": 8},
            {"kind": "stat", "stat": "max_hp", "percent": -25},
        ]},
    },
    {
        "id": "executioners_bargain",
        "name": "Executioner's Bargain",
        "emoji": "⚖️",
        "rarity": "cursed",
        "description": "The squad gains Executioner and every hit chips 2 extra Poise -- but -30% max HP.",
        "effect": {"kind": "multi", "effects": [
            {"kind": "passive", "passive_id": "executioner"},
            {"kind": "poise_damage", "bonus": 2},
            {"kind": "stat", "stat": "max_hp", "percent": -30},
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
