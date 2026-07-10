"""
Content for the three interactive room types the Adventure Overhaul spec
calls out specifically: Trap (a decision with randomized success/fail),
Puzzle (a basic multiple-choice puzzle), and Merchant (a basic shop).
Resolution logic lives in bot/services/dungeon_service.py; this module is
just the data each one draws from.
"""

from __future__ import annotations

# ---------------------------------------------------------------------
# Trap rooms: pick an approach, each with different odds and stakes.
# `fail_damage_percent`, if present, costs a random squad member that %
# of their max HP (persisted -- see PlayerCharacter.current_hp) instead of
# losing gold, so failure has a real cost besides "nothing happened."
# ---------------------------------------------------------------------
TRAP_CHOICES = [
    {
        "id": "careful",
        "label": "🐢 Disarm it carefully",
        "description": "Slow and steady. Good odds, a modest reward either way.",
        "success_chance": 0.8,
        "success_gold_mult": 1.0,
        "fail_gold_mult": 0.3,
    },
    {
        "id": "rush",
        "label": "⚡ Rush straight through",
        "description": "Fast and risky. Big payout if it works -- a nasty jolt if it doesn't.",
        "success_chance": 0.55,
        "success_gold_mult": 2.2,
        "fail_gold_mult": 0.0,
        "fail_damage_percent": 10,
    },
    {
        "id": "avoid",
        "label": "🧭 Search for a way around",
        "description": "Safe. Small guaranteed reward, no risk at all.",
        "success_chance": 1.0,
        "success_gold_mult": 0.5,
        "fail_gold_mult": 0.5,
    },
]

TRAP_INTRO = (
    "A pressure-plate trap blocks the corridor ahead, old Cascade tech still "
    "humming with charge. How do you want to handle it?"
)
TRAP_SUCCESS_FLAVOR = "You get through clean and salvage what the trap was guarding."
TRAP_FAIL_FLAVOR = "It goes off anyway -- not your finest moment, but you're still standing."

# ---------------------------------------------------------------------
# Puzzle rooms: a basic multiple-choice puzzle. Correct answer gives the
# full reward; a wrong answer still gives a small consolation reward so a
# bad guess never feels like a total waste of the room.
# ---------------------------------------------------------------------
PUZZLES = [
    {
        "id": "glacier_15_survivors",
        "question": "An old Team Cascade roster lists two names still marked ACTIVE after Glacier 15. Which two?",
        "options": ["Josh and Sader Vorae", "Nexus and FAX", "Bee Jee and Refender"],
        "correct_index": 0,
    },
    {
        "id": "material_tiers",
        "question": "A supply crate is labeled by rarity tier. Which pair belongs to the SAME tier?",
        "options": ["Wood and Xendium", "Metal and Crystal", "Void and Stone"],
        "correct_index": 1,
    },
    {
        "id": "refense_philosophy",
        "question": "A worn plaque reads: 'The Refense philosophy preaches a balance of...'",
        "options": ["Speed and stealth", "Offense and defense", "Wealth and status"],
        "correct_index": 1,
    },
    {
        "id": "class_roles",
        "question": "A tactical terminal asks: which class role is built around healing and shielding the team?",
        "options": ["Amplifier", "Sustain", "Support DPS"],
        "correct_index": 1,
    },
]

PUZZLE_SUCCESS_GOLD_MULT = 1.6
PUZZLE_FAIL_GOLD_MULT = 0.4

# ---------------------------------------------------------------------
# Merchant rooms: a basic shop. Per the spec, kept intentionally simple --
# a handful of gold-cost offers, no haggling/rotating inventory system.
# ---------------------------------------------------------------------
SHOP_OFFERS = [
    {
        "id": "lootbox_common",
        "name": "Common Lootbox",
        "description": "A simple satchel of supplies.",
        "cost_gold": 90,
        "kind": "lootbox",
        "tier": "common",
    },
    {
        "id": "lootbox_uncommon",
        "name": "Uncommon Lootbox",
        "description": "A sturdy sack, a small step up.",
        "cost_gold": 190,
        "kind": "lootbox",
        "tier": "uncommon",
    },
    {
        "id": "lootbox_rare",
        "name": "Rare Lootbox",
        "description": "A reinforced chest, guaranteed at least Uncommon.",
        "cost_gold": 340,
        "kind": "lootbox",
        "tier": "rare",
    },
    {
        "id": "shards_small",
        "name": "5 Shards",
        "description": "A small bundle of Cascade Shards.",
        "cost_gold": 480,
        "kind": "shards",
        "amount": 5,
    },
    {
        "id": "basic_item",
        "name": "Basic Gear Piece",
        "description": "A random, low-rarity item -- nothing special, but it's something.",
        "cost_gold": 70,
        "kind": "item",
    },
]
