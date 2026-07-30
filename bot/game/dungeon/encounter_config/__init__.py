"""
Story-room (and, now, Treasure/Trap/Shrine/Puzzle/Secret-room) "Encounters":
interactive, choice-driven run-ins with recurring Cascade-world characters,
adapted from the original JS bot's explore.js (the old /explore command's
`events` array). That system had one bespoke JS function per button; this
one is pure data, resolved generically by a small interpreter in
dungeon_service.py (see
resolve_encounter_choice / _apply_outcome).

Each encounter has:
  - id / name / image_url: identity + flavor art. Encounters ported from
    explore.js keep its original `imageUrl`; brand new encounters (added
    to cover themes the old cast didn't reach) leave image_url as None --
    there's no source art for a character that never existed before.
  - room_types: which RoomType value(s) (see bot/database/models/enums.py)
    this encounter is eligible to be rolled for. dungeon_service picks
    from whichever pool matches the node the player is actually standing
    on -- a "shrine"-tagged encounter only ever shows up in a Shrine room,
    etc. Most of the original cast stayed STORY-flavored (they're
    character run-ins, not environmental set-pieces); a few were
    re-themed to rooms they fit better (Duko's loot-crate gambling ->
    Treasure, Triv's ambush -> Trap, thedoggyp's looted shack -> Secret),
    and a handful of brand new encounters were written to give
    Shrine/Puzzle/Secret a dedicated NPC-flavored option too.

    "merchant" is a special case: Merchant rooms no longer have their own
    bespoke shop UI at all (see dungeon_service.py's ROOM_ENCOUNTER_CHANCE
    -- Merchant rolls an encounter 100% of the time, with a defensive
    "trading post is closed" fallback message if that pool were ever
    empty). A merchant-tagged encounter's choices are almost always plain
    "trade" actions with success_chance 1.0 and a flat (non-range) `gain`
    amount -- a real shop sells you exactly what the price tag says, no
    scam roll, unlike Xender's lottery or a "sell materials" trade
    elsewhere that still carries a little risk. Tbnr's shop covers cheap
    tier-0/tier-1 bulk goods; Boss John's covers the expensive end
    (tier-2/tier-3 materials, pricier lootboxes, and the one deliberately
    steep way to buy Shards outright with gold instead of hoping for a
    rare bonus roll).
  - intros: a few randomized opening lines (old code picked one of these
    with Math.random() per visit; same idea here via rng.choice).
  - choices: 1-5 buttons. Every choice has an "action":
      - "leave"  -- no cost, no roll, just flavor text.
      - "risk"   -- no upfront cost; success_chance rolls between
                    on_success/on_fail outcomes.
      - "trade"  -- pay `cost` upfront (skipped entirely if unaffordable),
                    then success_chance rolls between on_success/on_fail.
                    Trades that amount to "sell materials for a reward"
                    are intentionally generous and near-guaranteed --
                    per a balance pass, a trade should clearly be in the
                    player's favor, not a coin flip.
      - "gamble" -- pay `cost` (can be empty), then pick one of `tiers`
                    (weighted by "chance") for its outcome. Good for
                    lottery/lootcrate-style choices with more than two
                    possible results, including rare high-tier ones.

An "outcome" (on_success / on_fail / a gamble tier's "outcome") is a dict
with any of:
  - "gain": currency/material amounts to add (see _apply_gain) --
    supports plain currency keys ("gold", "shards", "wood", ...), a
    random pick from a material tier via {"material_tier": int,
    "amount": n_or_[lo, hi]}, {"lootbox": tier_str}, or {"item": True}
    for a guaranteed random Common item, or {"item": "natural"} for a
    naturally-rolled item (any rarity up to the region's cap -- rare,
    but how a lucky forge/terminal/shrine choice can occasionally hand
    out something much better than Common).
  - "loss": currency/material amounts to subtract, clamped to what the
    player actually has (see _apply_loss). Same material_tier shorthand
    as gain.
  - "hp_damage_percent": knocks a random squad member for that % of
    their max HP, same mechanic TRAP_CHOICES' fail_damage_percent uses.
  - "bonus": {"chance": p, "gain": {...}} -- an independent, usually-low
    chance of an EXTRA reward on top of whatever else the outcome gave.
    This is how Shards and rare Lootboxes are sprinkled across a wide
    variety of encounters while staying rare at any single one of them:
    a plain "gain" of shards is only ever used inside an already-rare
    gamble tier (<=10% chance); everywhere else, a shard reward rides
    along as a small "bonus" (~4-10% chance for 1-2) on top of a
    reward that's guaranteed or near-guaranteed on its own. NEVER give
    shards as a flat guaranteed "gain" behind a high success_chance --
    that's how they'd stop being rare. (Boss John's merchant shop is the
    one deliberate exception: a guaranteed, expensive, explicit "buy a
    Shard" purchase -- see that encounter's comment.)
  - "heal": "full" or an int percent (a sibling of "gain"/"loss"/
    "hp_damage_percent"/"bonus", not something that goes inside "gain")
    -- restores the WHOLE squad's HP, either fully (same current_hp =
    None sentinel a Campfire room uses) or by that percent of each
    member's own max HP. Unlike damage, which always lands on one
    random squad member, healing applies to everyone -- it reads better
    as a reward, and there's no per-member damage mechanic to mirror.

A "gain" dict can also include "xp": n_or_[lo, hi], which splits that
much XP across the WHOLE squad via combat_service.apply_character_xp
(the same function combat victories use), including any resulting
level-ups.

Amount values can be a flat int or an inclusive [min, max] range.

Some encounters/choices are also written with deliberately harsher
failure states than the rest of the roster on purpose -- bigger
hp_damage_percent (30%+), and even a "loss" of Shards on failure
(normally shards only ever move in the *gain* direction) -- as the
high-stakes end of the risk/reward curve. These are flagged in their
own comments; they're not oversights.

Original character/story content and image links are preserved from
explore.js; the resource types and numbers have been re-tuned to this
project's current economy (gold/shards/reroll_tokens + 8 tiered
materials instead of the old wood/stone/rope/ruby/etc. inventory), and
rewards across the board were bumped up in a balance pass so Encounters
read as clearly worthwhile next to a plain Treasure/Secret room instead
of just a novelty detour.

SECOND BALANCE PASS (post-Encounter-only migration): with Trap/Puzzle
now folded into this same Encounter system (see dungeon_service.py --
the old TRAP_CHOICES/PUZZLES tables are gone entirely, every
non-combat/campfire/start room resolves through here now), rewards were
scaled up again across the board: material gain amounts (both the
material_tier/amount pattern and any directly-named material key) are
roughly +35%, gold gains roughly +25%, XP gains roughly +15%. Every
existing "bonus" chance (shards or lootbox) was also increased --
common-lootbox bonus chances especially, since the goal of this pass
was specifically to make Common lootboxes a frequent, expected drop
rather than a rare one -- and most success outcomes that previously
carried no bonus at all now carry a small (8%) chance of a bonus Common
Lootbox on top of their normal reward. Choices whose payout is
deliberately tied to their cost by a fixed ratio (Josh's betting table:
literal double-or-nothing) were deliberately left alone so that
mechanic stays honest -- don't blanket-rescale those without also
rescaling the cost they're a multiple of.

Layout: this used to be one ~3000-line module. The encounter data is now
split one module per room type (every encounter is tagged with exactly one),
with this __init__ concatenating them back into the single ENCOUNTERS list
the rest of the game reads. `from bot.game.dungeon.encounter_config import
ENCOUNTERS` (or get_encounter_by_id / get_encounters_for_room_type) works
exactly as before; add a new encounter to the module matching its room type.
"""

from __future__ import annotations

from bot.game.dungeon.encounter_config.story import STORY_ENCOUNTERS
from bot.game.dungeon.encounter_config.treasure import TREASURE_ENCOUNTERS
from bot.game.dungeon.encounter_config.trap import TRAP_ENCOUNTERS
from bot.game.dungeon.encounter_config.shrine import SHRINE_ENCOUNTERS
from bot.game.dungeon.encounter_config.puzzle import PUZZLE_ENCOUNTERS
from bot.game.dungeon.encounter_config.secret import SECRET_ENCOUNTERS
from bot.game.dungeon.encounter_config.merchant import MERCHANT_ENCOUNTERS

# One flat list, in the order the modules are listed above. Nothing depends
# on that order -- callers always filter by room type or look up by id.
ENCOUNTERS: list[dict] = [
    *STORY_ENCOUNTERS,
    *TREASURE_ENCOUNTERS,
    *TRAP_ENCOUNTERS,
    *SHRINE_ENCOUNTERS,
    *PUZZLE_ENCOUNTERS,
    *SECRET_ENCOUNTERS,
    *MERCHANT_ENCOUNTERS,
]

def get_encounter_by_id(encounter_id: str) -> dict | None:
    return next((e for e in ENCOUNTERS if e["id"] == encounter_id), None)


def get_encounters_for_room_type(room_type_value: str) -> list[dict]:
    return [e for e in ENCOUNTERS if room_type_value in e.get("room_types", ())]
