"""
The Research Lab -- permanent, account-wide progression.

WHY THIS REPLACED THE MAILBOX. The mailbox was a building you waited on
and then collected from, which is exactly what harvesters already are --
two systems occupying one design slot, so players correctly ignored the
weaker one. Making its numbers bigger wouldn't have fixed that; it would
just have been a better version of a redundant thing.

The Research Lab is deliberately the opposite shape:

  * You CHOOSE what to work toward, from a tree with prerequisites.
  * Each project completes ONCE and its effect is PERMANENT, so progress
    accumulates instead of resetting every collection.
  * The rewards are things no other system grants -- better loot odds,
    a wider relic draft, cheaper upgrades, softer gacha pity. They change
    how the rest of the game behaves rather than adding to a pile.

The time cost is a gate on a one-time unlock, not an income tick. That's
the distinction from harvesters: a harvester you collect forever, a
project you finish and never think about again except that the game is
permanently better afterward.

----------------------------------------------------------------------
PERKS
----------------------------------------------------------------------
Every project grants exactly one `perk` with a numeric `value`. Perks
STACK ADDITIVELY across projects (that's why a perk appears at several
tiers in the tree -- each tier is a separate project). The read points
live in the systems they affect, all going through
research_service.perk_value:

    loot_rarity_weight    LootGenerator -- shifts the rarity roll upward
    relic_offer_size      relic_service -- extra relic choices at campfires
    upgrade_cost_percent  item_upgrade_service -- cheaper gear levelling
    domain_energy         domain_service -- flat bonus to the energy cap
    gacha_pity_reduction  character_gacha_service -- earlier 5-star pity
    character_xp_percent  combat_service -- more XP per battle
    harvester_percent     harvester_service -- better passive income
    shop_discount_percent base_service -- cheaper shop purchases
    forge_cost_percent    forge_service -- cheaper crafting
    starting_energy       factory -- squad begins battles with energy

A perk with no read point is dead content, so every one above is wired.
"""

from __future__ import annotations

import datetime as dt

# Research is gated by the LAB's level, which is itself gated by HQ level
# -- so the tree can't be rushed ahead of the rest of the base.
MAX_LAB_LEVEL = 5

LAB_UPGRADE_COST: dict[int, dict[str, int]] = {
    1: {"gold": 1200, "wood": 120, "stone": 120},
    2: {"gold": 4500, "stone": 300, "metal": 140},
    3: {"gold": 14000, "metal": 400, "crystal": 160},
    4: {"gold": 42000, "crystal": 500, "xendium": 200},
}

# Lab level -> how many projects may run AT ONCE. The real upgrade
# incentive: a level-1 lab is a strict queue of one, so choosing what to
# research first actually matters, while a maxed lab lets you push three
# branches in parallel.
LAB_CONCURRENT_SLOTS: dict[int, int] = {1: 1, 2: 1, 3: 2, 4: 2, 5: 3}

# Lab level -> research speed multiplier. Upgrading makes every project
# faster, so the investment pays back across everything still unbuilt.
LAB_SPEED_MULTIPLIER: dict[int, float] = {1: 1.0, 2: 0.85, 3: 0.72, 4: 0.6, 5: 0.5}


def lab_upgrade_cost(level: int) -> dict[str, int] | None:
    return LAB_UPGRADE_COST.get(level)


def is_max_lab_level(level: int) -> bool:
    return level >= MAX_LAB_LEVEL


def concurrent_slots(level: int) -> int:
    return LAB_CONCURRENT_SLOTS.get(level, LAB_CONCURRENT_SLOTS[MAX_LAB_LEVEL])


def speed_multiplier(level: int) -> float:
    return LAB_SPEED_MULTIPLIER.get(level, LAB_SPEED_MULTIPLIER[MAX_LAB_LEVEL])


# ----------------------------------------------------------------------
# The project tree.
#
# `requires` is a list of project ids that must be COMPLETE first, which
# is what makes this a tree rather than a shopping list -- an early
# cheap node is the price of admission to the branch behind it.
#
# `minutes` is base research time before the lab's speed multiplier.
# Tuned so tier-1 nodes finish inside a play session and the deepest
# ones are a genuine overnight commitment.
# ----------------------------------------------------------------------
RESEARCH_PROJECTS: list[dict] = [
    # --- Branch: SALVAGE (loot quality) -----------------------------
    {
        "id": "field_cataloguing", "name": "Field Cataloguing", "branch": "Salvage",
        "description": "Sort recovered gear properly. Slightly better rarity on every drop.",
        "requires": [], "lab_level": 1, "minutes": 30,
        "cost": {"gold": 500, "wood": 60, "stone": 60},
        "perk": "loot_rarity_weight", "value": 6,
    },
    {
        "id": "assay_protocols", "name": "Assay Protocols", "branch": "Salvage",
        "description": "Identify what's worth keeping before it's melted down.",
        "requires": ["field_cataloguing"], "lab_level": 2, "minutes": 90,
        "cost": {"gold": 2200, "stone": 150, "metal": 80},
        "perk": "loot_rarity_weight", "value": 9,
    },
    {
        "id": "deep_provenance", "name": "Deep Provenance", "branch": "Salvage",
        "description": "Trace an artifact's origin to find the good ones first.",
        "requires": ["assay_protocols"], "lab_level": 4, "minutes": 300,
        "cost": {"gold": 18000, "crystal": 220, "xendium": 90},
        "perk": "loot_rarity_weight", "value": 14,
    },
    {
        "id": "salvage_reclamation", "name": "Salvage Reclamation", "branch": "Salvage",
        "description": "Strip more usable material out of every scrapped item.",
        "requires": ["field_cataloguing"], "lab_level": 2, "minutes": 75,
        "cost": {"gold": 1800, "stone": 200, "metal": 60},
        "perk": "forge_cost_percent", "value": 10,
    },
    {
        "id": "matter_recompiler", "name": "Matter Recompiler", "branch": "Salvage",
        "description": "Rebuild components from raw stock. Forging costs far less.",
        "requires": ["salvage_reclamation"], "lab_level": 4, "minutes": 280,
        "cost": {"gold": 20000, "xendium": 160, "permafrost_ore": 90},
        "perk": "forge_cost_percent", "value": 18,
    },

    # --- Branch: LOGISTICS (economy) --------------------------------
    {
        "id": "supply_routing", "name": "Supply Routing", "branch": "Logistics",
        "description": "Harvesters produce more per cycle.",
        "requires": [], "lab_level": 1, "minutes": 40,
        "cost": {"gold": 700, "wood": 90},
        "perk": "harvester_percent", "value": 10,
    },
    {
        "id": "bulk_contracts", "name": "Bulk Contracts", "branch": "Logistics",
        "description": "The quartermaster owes you a favour. Everything in the shop costs less.",
        "requires": ["supply_routing"], "lab_level": 2, "minutes": 100,
        "cost": {"gold": 3000, "stone": 220, "metal": 90},
        "perk": "shop_discount_percent", "value": 8,
    },
    {
        "id": "automated_haulers", "name": "Automated Haulers", "branch": "Logistics",
        "description": "Harvesters run themselves better than you ever did.",
        "requires": ["supply_routing"], "lab_level": 3, "minutes": 180,
        "cost": {"gold": 9000, "metal": 320, "crystal": 110},
        "perk": "harvester_percent", "value": 18,
    },
    {
        "id": "cascade_brokerage", "name": "Cascade Brokerage", "branch": "Logistics",
        "description": "You set the going rate now.",
        "requires": ["bulk_contracts"], "lab_level": 4, "minutes": 320,
        "cost": {"gold": 26000, "crystal": 400, "xendium": 140},
        "perk": "shop_discount_percent", "value": 14,
    },
    {
        "id": "tempered_tooling", "name": "Tempered Tooling", "branch": "Logistics",
        "description": "Better tools mean levelling gear costs less material and gold.",
        "requires": [], "lab_level": 2, "minutes": 120,
        "cost": {"gold": 3500, "metal": 150, "crystal": 50},
        "perk": "upgrade_cost_percent", "value": 8,
    },
    {
        "id": "precision_fabrication", "name": "Precision Fabrication", "branch": "Logistics",
        "description": "Nothing is wasted on a failed upgrade any more.",
        "requires": ["tempered_tooling"], "lab_level": 4, "minutes": 340,
        "cost": {"gold": 30000, "crystal": 450, "permafrost_ore": 130},
        "perk": "upgrade_cost_percent", "value": 15,
    },

    # --- Branch: FIELDWORK (expeditions) ----------------------------
    {
        "id": "relic_attunement", "name": "Relic Attunement", "branch": "Fieldwork",
        "description": "Campfires offer one extra relic to choose from.",
        "requires": [], "lab_level": 2, "minutes": 150,
        "cost": {"gold": 4000, "metal": 180, "crystal": 60},
        "perk": "relic_offer_size", "value": 1,
    },
    {
        "id": "resonance_mapping", "name": "Resonance Mapping", "branch": "Fieldwork",
        "description": "Read the Cascade before you walk into it. Another relic on offer.",
        "requires": ["relic_attunement"], "lab_level": 5, "minutes": 480,
        "cost": {"gold": 55000, "xendium": 300, "void": 90},
        "perk": "relic_offer_size", "value": 1,
    },
    {
        "id": "combat_debriefs", "name": "Combat Debriefs", "branch": "Fieldwork",
        "description": "Characters learn faster from every fight.",
        "requires": [], "lab_level": 1, "minutes": 45,
        "cost": {"gold": 900, "wood": 80, "stone": 80},
        "perk": "character_xp_percent", "value": 12,
    },
    {
        "id": "simulation_drills", "name": "Simulation Drills", "branch": "Fieldwork",
        "description": "Run the fight before the fight.",
        "requires": ["combat_debriefs"], "lab_level": 3, "minutes": 200,
        "cost": {"gold": 11000, "metal": 300, "crystal": 130},
        "perk": "character_xp_percent", "value": 20,
    },
    {
        "id": "pre_charge_cells", "name": "Pre-Charge Cells", "branch": "Fieldwork",
        "description": "The squad walks into every battle with energy already banked.",
        "requires": ["combat_debriefs"], "lab_level": 3, "minutes": 240,
        "cost": {"gold": 13000, "crystal": 160, "xendium": 60},
        "perk": "starting_energy", "value": 8,
    },
    {
        "id": "overcharged_reserves", "name": "Overcharged Reserves", "branch": "Fieldwork",
        "description": "Start every fight closer to an ultimate.",
        "requires": ["pre_charge_cells"], "lab_level": 5, "minutes": 500,
        "cost": {"gold": 60000, "xendium": 280, "entropy": 80},
        "perk": "starting_energy", "value": 12,
    },

    # --- Branch: EXPANSION (domains + gacha) ------------------------
    {
        "id": "domain_survey", "name": "Domain Survey", "branch": "Expansion",
        "description": "Chart the domains properly. Your energy ceiling rises.",
        "requires": [], "lab_level": 1, "minutes": 60,
        "cost": {"gold": 1100, "stone": 120},
        "perk": "domain_energy", "value": 15,
    },
    {
        "id": "leyline_tap", "name": "Leyline Tap", "branch": "Expansion",
        "description": "Draw domain energy straight from the source.",
        "requires": ["domain_survey"], "lab_level": 3, "minutes": 220,
        "cost": {"gold": 12000, "crystal": 200, "xendium": 70},
        "perk": "domain_energy", "value": 25,
    },
    {
        "id": "deep_leyline_array", "name": "Deep Leyline Array", "branch": "Expansion",
        "description": "The ceiling stops being the problem.",
        "requires": ["leyline_tap"], "lab_level": 5, "minutes": 520,
        "cost": {"gold": 70000, "permafrost_ore": 320, "void": 110},
        "perk": "domain_energy", "value": 40,
    },
    {
        "id": "signal_triangulation", "name": "Signal Triangulation", "branch": "Expansion",
        "description": "Narrow the search. Guaranteed 5-star pulls arrive sooner.",
        "requires": [], "lab_level": 3, "minutes": 260,
        "cost": {"gold": 15000, "crystal": 240, "xendium": 80},
        "perk": "gacha_pity_reduction", "value": 3,
    },
    {
        "id": "beacon_lock", "name": "Beacon Lock", "branch": "Expansion",
        "description": "You know roughly where they are before you call.",
        "requires": ["signal_triangulation"], "lab_level": 4, "minutes": 400,
        "cost": {"gold": 38000, "xendium": 220, "permafrost_ore": 120},
        "perk": "gacha_pity_reduction", "value": 4,
    },
    {
        "id": "cascade_resonance", "name": "Cascade Resonance", "branch": "Expansion",
        "description": "The capstone. Everything the Lab has learned, applied at once.",
        "requires": ["deep_leyline_array", "resonance_mapping", "precision_fabrication"],
        "lab_level": 5, "minutes": 720,
        "cost": {"gold": 120000, "void": 260, "entropy": 260},
        "perk": "loot_rarity_weight", "value": 20,
    },
]

PROJECTS_BY_ID: dict[str, dict] = {p["id"]: p for p in RESEARCH_PROJECTS}

BRANCHES: list[str] = []
for _p in RESEARCH_PROJECTS:
    if _p["branch"] not in BRANCHES:
        BRANCHES.append(_p["branch"])
del _p


def get_project(project_id: str) -> dict | None:
    return PROJECTS_BY_ID.get(project_id)


def research_duration(project: dict, lab_level: int) -> dt.timedelta:
    """How long `project` takes at `lab_level` -- base minutes scaled by
    the lab's speed multiplier."""
    return dt.timedelta(minutes=project["minutes"] * speed_multiplier(lab_level))
