"""
Expedition lifecycle: starting a run, moving between dungeon nodes, and
resolving whatever each room type does. Combat rooms hand off to
combat_service. Every other room type -- Story, Treasure, Trap, Shrine,
Puzzle, Secret, Merchant -- is now resolved entirely through the
Encounter system (see bot/game/dungeon/encounter_config.py and
ROOM_ENCOUNTER_CHANCE below), at 100% odds. Trap and Puzzle used to be
genuinely interactive mini-games of their own (a random success/fail
decision and a basic multiple-choice quiz, respectively, defined in the
now-decommissioned bot/game/dungeon/interactive_config.py); that system
has been fully phased out in favor of Encounters so there's exactly one
interactive-room system in the game rather than two parallel ones.
Each room type below still keeps a small, plain (non-Encounter)
fallback resolution purely as a defensive safety net in case its
Encounter pool were ever empty -- see _maybe_roll_encounter -- it
should never actually trigger in practice with ENCOUNTERS populated for
every room type.
"""

from __future__ import annotations

import math
import random

from bot.database.models.enums import (
    ExpeditionStatus,
    MaterialType,
    Rarity,
    RoomType,
)
from bot.database.models.expedition_model import Expedition
from bot.game.combat import enemies as enemy_catalog
from bot.game.dungeon import graph_utils as gu
from bot.game.dungeon.encounter_config import get_encounter_by_id, get_encounters_for_room_type
from bot.game.dungeon.generator import DungeonGenerator
from bot.game.dungeon.region_config import get_region_difficulty
from bot.game.economy.lootbox_config import tier_for_floor_and_region
from bot.game.loot.generator import LootGenerator
from bot.services import character_service, combat_service, item_template_service, lootbox_service, quest_service
from bot.services.currency_service import add_currency, format_currency, spend_currency

# Which material tier drops from treasure/secret rooms at a given floor --
# mirrors the tier progression harvesters/upgrades use (see
# bot/database/models/enums.py::MaterialType.tier).
_MATERIAL_TIERS = [
    (MaterialType.WOOD, MaterialType.STONE),
    (MaterialType.METAL, MaterialType.CRYSTAL),
    (MaterialType.XENDIUM, MaterialType.PERMAFROST_ORE),
    (MaterialType.VOID, MaterialType.ENTROPY),
]


def _material_for_floor(floor: int, rng: random.Random | None = None) -> MaterialType:
    rng = rng or random
    tier_index = min(floor // 7, len(_MATERIAL_TIERS) - 1)
    return rng.choice(_MATERIAL_TIERS[tier_index])


def _mark_completed(expedition: Expedition, node_id: str) -> None:
    """Marks a node completed without ever mutating expedition.graph (or
    its nested "nodes" dict) in place -- copies at each level first, then
    reassigns the whole attribute. graph is a plain JSON column (no
    MutableDict wrapper), so SQLAlchemy only detects a change here if the
    value assigned to expedition.graph is genuinely different in content
    from what it held before this call. Mutating in place and reassigning
    afterwards (e.g. `gu.mark_completed(expedition.graph, id); expedition.graph
    = dict(expedition.graph)`) does NOT work: the in-place mutation happens
    first, so the "old" and "new" snapshots are already equal by the time
    of reassignment, and the change is silently dropped on commit. Without
    this, "completed" never actually persists past the current session --
    e.g. the boss-defeated counter in dungeon_map_embed would show the
    right count immediately after beating a boss, then revert to the old
    count the next time the expedition is loaded fresh (a new /adventure
    invocation, a different button click, a restart)."""
    graph = dict(expedition.graph)
    nodes = dict(graph["nodes"])
    nodes[node_id] = {**nodes[node_id], "completed": True}
    graph["nodes"] = nodes
    expedition.graph = graph


# ----------------------------------------------------------------------
# Expedition ledger -- a running tally of everything gained/spent since
# the expedition started, surfaced as a whole-run summary when it ends
# (see resolve_battle_end's expedition_complete/defeat branches and
# bot/utils/embedder.py::expedition_summary_embed). Every helper below
# reassigns Expedition.loot_ledger wholesale rather than mutating the
# dict in place -- a plain JSON column doesn't pick up in-place mutation,
# only attribute reassignment.
# ----------------------------------------------------------------------

def _new_ledger() -> dict:
    return {
        "gold_gained": 0,
        "gold_spent": 0,
        "shards_gained": 0,
        "reroll_tokens_gained": 0,
        "reroll_tokens_spent": 0,
        "xp_gained": 0,
        "materials": {},        # material value -> qty gained
        "items_found": [],      # [{"name":, "rarity":}] -- combat/treasure drops
        "items_bought": [],     # [{"name":, "rarity":}] -- shop purchases
        "lootboxes_found": {},  # tier -> qty -- treasure/secret rooms
        "lootboxes_bought": {}, # tier -> qty -- shop purchases
        "level_ups": {},        # character name -> {"from":, "to":}
    }


def _ledger(expedition: Expedition) -> dict:
    ledger = dict(expedition.loot_ledger or {})
    for key, default in _new_ledger().items():
        ledger.setdefault(key, default)
    return ledger


def _ledger_add_gold(expedition: Expedition, amount: int, spent: bool = False) -> None:
    if not amount:
        return
    ledger = _ledger(expedition)
    key = "gold_spent" if spent else "gold_gained"
    ledger[key] = ledger[key] + amount
    expedition.loot_ledger = ledger


def _ledger_add_shards(expedition: Expedition, amount: int) -> None:
    if not amount:
        return
    ledger = _ledger(expedition)
    ledger["shards_gained"] = ledger["shards_gained"] + amount
    expedition.loot_ledger = ledger


def _ledger_add_reroll_tokens(expedition: Expedition, amount: int, spent: bool = False) -> None:
    if not amount:
        return
    ledger = _ledger(expedition)
    key = "reroll_tokens_spent" if spent else "reroll_tokens_gained"
    ledger[key] = ledger[key] + amount
    expedition.loot_ledger = ledger


def _ledger_add_xp(expedition: Expedition, amount: int) -> None:
    if not amount:
        return
    ledger = _ledger(expedition)
    ledger["xp_gained"] = ledger["xp_gained"] + amount
    expedition.loot_ledger = ledger


def _ledger_add_material(expedition: Expedition, material: str, amount: int) -> None:
    if not amount:
        return
    ledger = _ledger(expedition)
    materials = dict(ledger["materials"])
    materials[material] = materials.get(material, 0) + amount
    ledger["materials"] = materials
    expedition.loot_ledger = ledger


def _ledger_add_item(expedition: Expedition, item, bought: bool = False) -> None:
    ledger = _ledger(expedition)
    key = "items_bought" if bought else "items_found"
    entries = list(ledger[key])
    entries.append({"name": item.display_name, "rarity": item.rarity.value})
    ledger[key] = entries
    expedition.loot_ledger = ledger


def _ledger_add_lootbox(expedition: Expedition, tier: str, quantity: int = 1, bought: bool = False) -> None:
    ledger = _ledger(expedition)
    key = "lootboxes_bought" if bought else "lootboxes_found"
    boxes = dict(ledger[key])
    boxes[tier] = boxes.get(tier, 0) + quantity
    ledger[key] = boxes
    expedition.loot_ledger = ledger


def _ledger_record_level_ups(expedition: Expedition, level_ups: list[dict]) -> None:
    if not level_ups:
        return
    ledger = _ledger(expedition)
    tracked = dict(ledger["level_ups"])
    for lu in level_ups:
        name = lu["name"]
        if name in tracked:
            tracked[name] = {
                "from": min(tracked[name]["from"], lu["from"]),
                "to": max(tracked[name]["to"], lu["to"]),
            }
        else:
            tracked[name] = {"from": lu["from"], "to": lu["to"]}
    ledger["level_ups"] = tracked
    expedition.loot_ledger = ledger


ROOM_FLAVOR = {
    RoomType.SHRINE: "You find a stable shard of Void matter, still humming faintly. It offers a small blessing before going dark.",
}

# Story rooms used to always show one of these quiet, no-choice lore
# snippets. Now that Story rolls a named-NPC Encounter every time (see
# ROOM_ENCOUNTER_CHANCE below), these only ever surface as a defensive
# fallback -- if the Encounter pool for "story" were ever empty -- so the
# atmospheric world-lore beats still have somewhere to land rather than
# the room silently doing nothing. See docs/WORLD_LORE.md for the
# broader continuity these are drawn from.
STORY_FRAGMENTS = [
    "You find a weathered journal page. The handwriting shakes: '...my head hurt... I ran to check on friends and family but I can't find them...'",
    "A cracked terminal still holds a partial Ocellios Labs memo: 'GL-15 Batch ID -- Partial memory wipe success. Limited cognitive functionality.' You don't finish reading it.",
    "Scratched into a wall: 'THE SWORD ARE NOT FOR REVENGE. IT ARE FOR PROTECT.' Someone believed it enough to carve it twice.",
    "A maintenance log for a Voidwarp rift generator, dated well after this site was declared abandoned. Someone was still here.",
    "A torn evacuation order, unsigned, unsent. The date on it is the day everything here went quiet.",
    "A child's drawing, half-burned: a green city, a family, a sun. Nothing here looks like it anymore.",
    "An old news clipping, curled at the edges: 'ICON LEADERS MEET -- a mutualistic society, an equal division of rights over Eris remains.' It didn't last.",
    "A name is stenciled on a supply crate: TEAM CASCADE. Someone else has already been through here, looking for the same answers you are.",
]


def _story_fragment(rng: random.Random) -> str:
    return rng.choice(STORY_FRAGMENTS)


# Odds that a given room type rolls a full interactive NPC Encounter
# instead of that room's plain, no-choice fallback resolution. Every
# room type is a full replacement now (1.0) -- Encounters are the ONLY
# interactive-room system left in the game (see the module docstring):
# Story's old quiet lore-snippet, Merchant's old bespoke shop UI, and
# Trap/Puzzle's old standalone mini-games are all gone in favor of
# Encounters. STORY_FRAGMENTS/"the trading post is closed today"/the
# plain gold-only branches below are kept only as defensive fallbacks
# for an (in practice, never) empty pool -- see _maybe_roll_encounter.
ROOM_ENCOUNTER_CHANCE: dict[RoomType, float] = {
    RoomType.STORY: 1.0,
    RoomType.TREASURE: 1.0,
    RoomType.TRAP: 1.0,
    RoomType.SHRINE: 1.0,
    RoomType.PUZZLE: 1.0,
    RoomType.SECRET: 1.0,
    RoomType.MERCHANT: 1.0,
}


def _maybe_roll_encounter(room_type: RoomType, rng: random.Random) -> dict | None:
    """Picks a random encounter tagged for this room type, at that room
    type's configured odds -- or None if this roll/room type doesn't get
    one, in which case the caller falls back to that room's simpler
    (non-encounter) resolution, if it has one."""
    chance = ROOM_ENCOUNTER_CHANCE.get(room_type)
    if not chance or rng.random() >= chance:
        return None
    pool = get_encounters_for_room_type(room_type.value)
    if not pool:
        return None
    return rng.choice(pool)


def get_active_expedition(db, player_id: int) -> Expedition | None:
    return (
        db.query(Expedition)
        .filter_by(player_id=player_id, status=ExpeditionStatus.ACTIVE)
        .first()
    )


def is_in_combat(expedition: Expedition | None) -> bool:
    return expedition is not None and bool(expedition.combat_state)


def is_in_interaction(expedition: Expedition | None) -> bool:
    return expedition is not None and bool(expedition.pending_interaction)


def start_expedition(db, player, region: str, num_floors: int | None = None) -> Expedition:
    """`num_floors` is normally left unset so the generator rolls a random
    number of bosses (2-4 regular + 1 guaranteed final = 3-5 total) and
    floor count per the run-length spec item -- pass it explicitly to
    force the old fixed-length single-boss shape."""
    existing = get_active_expedition(db, player.id)
    if existing is not None:
        return existing

    graph = DungeonGenerator().generate(region, num_floors=num_floors)

    # Starting a brand new run always begins on full HP -- a squad member
    # left critically low from a PREVIOUS run shouldn't silently carry
    # that penalty into an unrelated new one. HP still persists normally
    # BETWEEN battles WITHIN a single run (see combat_service).
    for pc in character_service.get_squad(db, player):
        pc.current_hp = None  # None == full HP, see PlayerCharacter.current_hp

    expedition = Expedition(
        player_id=player.id,
        region=region,
        status=ExpeditionStatus.ACTIVE,
        graph=graph,
        current_node_id=graph["start_node"],
        current_hp=player.max_hp,
    )
    db.add(expedition)
    db.commit()
    db.refresh(expedition)
    return expedition


def enter_node(db, expedition: Expedition, player, rng: random.Random | None = None) -> dict:
    """Resolves whatever's at the expedition's current node. Returns a
    dict describing what happened; `kind` tells the cog which view to
    render ("combat" -> battle view, "trap"/"puzzle"/"encounter" -> their
    own interactive views, "resolved"/"expedition_complete" -> map view).
    """
    rng = rng or random.Random()
    node = expedition.graph["nodes"][expedition.current_node_id]
    room_type = RoomType(node["room_type"])
    difficulty = get_region_difficulty(expedition.region)

    if room_type in (RoomType.COMBAT, RoomType.ELITE, RoomType.BOSS):
        if expedition.combat_state:
            return {"kind": "combat", "message": "Battle already in progress."}

        if room_type == RoomType.BOSS:
            # Usually a single boss template; occasionally (see
            # enemy_catalog.BOSS_GROUP_CHANCE) a named multi-enemy group
            # like the Eruptor Trio instead. Only the LAST boss node of
            # the run draws from that region's "final" pool -- earlier
            # boss nodes are checkpoints and stay "regular" caliber even
            # though they're still full boss fights.
            is_final = expedition.current_node_id == expedition.graph.get(
                "boss_nodes", [expedition.graph.get("boss_node")]
            )[-1]
            chosen = enemy_catalog.get_boss_encounter(rng, region=expedition.region, final=is_final)
        else:
            templates = (
                enemy_catalog.get_templates_by_role(room_type.value, region=expedition.region)
                or enemy_catalog.get_templates_by_role("combat", region=expedition.region)
            )
            squad_weights = (
                difficulty["combat_squad_weights"] if room_type == RoomType.COMBAT
                else difficulty["elite_squad_weights"]
            )
            count = rng.choices(list(squad_weights.keys()), weights=list(squad_weights.values()), k=1)[0]
            chosen = [rng.choice(templates) for _ in range(count)]

        # Combat rework: normal COMBAT-room enemies scale off their own
        # (higher) combat_level_offset instead of the shared level_offset
        # that ELITE/BOSS still use -- otherwise normal enemies in the
        # harder regions lag badly behind how strong a player actually is
        # by the time they're fighting there.
        elite_offset = difficulty["level_offset"]
        combat_offset = difficulty["combat_level_offset"]
        elite_level = node["floor"] // 10 + 1 + elite_offset
        combat_level = node["floor"] // 10 + 1 + combat_offset

        # Allow 0-2 regular (combat-role) enemies to appear during an elite
        # encounter. 0 is common, 1 is uncommon, 2 is rare.
        if room_type == RoomType.ELITE:
            reg_weights = {0: 80, 1: 15, 2: 5}
            reg_count = rng.choices(list(reg_weights.keys()), weights=list(reg_weights.values()), k=1)[0]
            if reg_count > 0:
                combat_templates = enemy_catalog.get_templates_by_role("combat", region=expedition.region) or []
                reg_chosen = [rng.choice(combat_templates) for _ in range(reg_count)]
                # For these regular enemies, preserve their own scaling by
                # passing (template, level) pairs into start_battle.
                chosen = chosen + [(t, combat_level) for t in reg_chosen]

        # Decide which overall level to pass into start_battle for any
        # enemies that don't provide an explicit per-template level.
        level = elite_level if room_type in (RoomType.ELITE, RoomType.BOSS) else combat_level
        combat_service.start_battle(db, expedition, player, chosen, level=level)
        # Awaiting an explicit "Start Battle" press before any turns are
        # fast-forwarded (see _combat_entry_view_and_embed in
        # bot/cogs/dungeon.py) -- otherwise, facing enemies faster than
        # the whole party, the player's first-ever glimpse of the fight
        # would already be several turns in, with those opening enemy
        # turns having resolved before they saw anything.
        expedition.pending_interaction = {"kind": "start_battle"}

        def _template_name(item):
            return item[0]["name"] if isinstance(item, (list, tuple)) else item["name"]

        names = ", ".join(_template_name(c) for c in chosen)
        return {"kind": "combat", "message": f"{names} appears!"}

    if room_type == RoomType.CAMPFIRE:
        for pc in character_service.get_squad(db, player):
            pc.current_hp = None  # None == full HP, see PlayerCharacter.current_hp
        _mark_completed(expedition, expedition.current_node_id)
        db.commit()
        return {"kind": "resolved", "message": "You rest at the campfire. Your squad heals to full."}

    if room_type == RoomType.TREASURE:
        encounter = _maybe_roll_encounter(room_type, rng)
        if encounter is not None:
            intro = rng.choice(encounter["intros"])
            expedition.pending_interaction = {"kind": "encounter", "encounter_id": encounter["id"]}
            db.commit()
            return {"kind": "encounter", "message": intro}

        # Balancing pass: this used to be 20-60 gold * (floor+1), which at
        # floor 8 could hand out ~9x a combat room's reward for zero risk --
        # exactly the "treasure rooms give so much more" imbalance called
        # out in the spec. Still meaningfully better than a combat room
        # (no fight risked), just not absurdly so. Defensive fallback
        # only -- shouldn't happen with ENCOUNTERS populated for
        # "treasure", since RoomType.TREASURE rolls an encounter at 1.0
        # chance above (see ROOM_ENCOUNTER_CHANCE) -- but scaled up along
        # with everything else in the second balance pass regardless, so
        # it never reads as an anticlimactic downgrade from an Encounter
        # if it ever did trigger.
        gold = round(rng.randint(19, 38) * (node["floor"] + 1) // 2 * difficulty["reward_multiplier"])
        add_currency(db, player, "gold", gold)
        _ledger_add_gold(expedition, gold)
        message = f"You find a treasure chest containing {format_currency('gold', gold)}!"

        material = _material_for_floor(node["floor"])
        material_amount = rng.randint(4, 11)
        add_currency(db, player, material.value, material_amount)
        _ledger_add_material(expedition, material.value, material_amount)
        message += f" (+{format_currency(material.value, material_amount)})"

        drop_chance = min(0.4 + node["floor"] * 0.02, 0.65)
        if rng.random() < drop_chance:
            tier = tier_for_floor_and_region(node["floor"], difficulty["max_lootbox_tier"])
            lootbox_service.grant_lootbox(db, player, tier, quantity=1)
            _ledger_add_lootbox(expedition, tier, quantity=1)
            message += f" It also contains a {tier.title()} Lootbox!"

        _mark_completed(expedition, expedition.current_node_id)
        db.commit()
        return {"kind": "resolved", "message": message}

    if room_type == RoomType.SECRET:
        encounter = _maybe_roll_encounter(room_type, rng)
        if encounter is not None:
            intro = rng.choice(encounter["intros"])
            expedition.pending_interaction = {"kind": "encounter", "encounter_id": encounter["id"]}
            db.commit()
            return {"kind": "encounter", "message": intro}

        # Defensive fallback only -- shouldn't happen with ENCOUNTERS
        # populated for "secret", since RoomType.SECRET rolls an
        # encounter at 1.0 chance above (see ROOM_ENCOUNTER_CHANCE).
        gold = round(rng.randint(6, 31) * difficulty["reward_multiplier"])
        add_currency(db, player, "gold", gold)
        _ledger_add_gold(expedition, gold)
        tier = tier_for_floor_and_region(node["floor"], difficulty["max_lootbox_tier"])
        lootbox_service.grant_lootbox(db, player, tier, quantity=1)
        _ledger_add_lootbox(expedition, tier, quantity=1)
        _mark_completed(expedition, expedition.current_node_id)
        db.commit()
        return {
            "kind": "resolved",
            "message": (
                f"A hidden passage reveals a Cascade supply cache, forgotten but intact. "
                f"(+{format_currency('gold', gold)}, +1 {tier.title()} Lootbox)"
            ),
        }

    if room_type == RoomType.START:
        _mark_completed(expedition, expedition.current_node_id)
        db.commit()
        return {"kind": "resolved", "message": "Your expedition begins."}

    if room_type == RoomType.STORY:
        encounter = _maybe_roll_encounter(room_type, rng)
        if encounter is not None:
            intro = rng.choice(encounter["intros"])
            expedition.pending_interaction = {"kind": "encounter", "encounter_id": encounter["id"]}
            db.commit()
            return {"kind": "encounter", "message": intro}

        # Defensive fallback only -- shouldn't happen with ENCOUNTERS
        # populated, since RoomType.STORY rolls an encounter at 1.0
        # chance above (see ROOM_ENCOUNTER_CHANCE).
        gold = round(rng.randint(5, 19) * difficulty["reward_multiplier"])
        add_currency(db, player, "gold", gold)
        _ledger_add_gold(expedition, gold)
        _mark_completed(expedition, expedition.current_node_id)
        db.commit()
        return {"kind": "resolved", "message": f"{_story_fragment(rng)} (+{format_currency('gold', gold)})"}

    if room_type == RoomType.SHRINE:
        encounter = _maybe_roll_encounter(room_type, rng)
        if encounter is not None:
            intro = rng.choice(encounter["intros"])
            expedition.pending_interaction = {"kind": "encounter", "encounter_id": encounter["id"]}
            db.commit()
            return {"kind": "encounter", "message": intro}

        # Defensive fallback only -- shouldn't happen with ENCOUNTERS
        # populated for "shrine", since RoomType.SHRINE rolls an
        # encounter at 1.0 chance above (see ROOM_ENCOUNTER_CHANCE).
        gold = round(rng.randint(5, 19) * difficulty["reward_multiplier"])
        add_currency(db, player, "gold", gold)
        _ledger_add_gold(expedition, gold)
        _mark_completed(expedition, expedition.current_node_id)
        db.commit()
        return {"kind": "resolved", "message": f"{ROOM_FLAVOR[RoomType.SHRINE]} (+{format_currency('gold', gold)})"}

    if room_type == RoomType.TRAP:
        encounter = _maybe_roll_encounter(room_type, rng)
        if encounter is not None:
            intro = rng.choice(encounter["intros"])
            expedition.pending_interaction = {"kind": "encounter", "encounter_id": encounter["id"]}
            db.commit()
            return {"kind": "encounter", "message": intro}

        # Defensive fallback only -- shouldn't happen with ENCOUNTERS
        # populated for "trap", since RoomType.TRAP rolls an encounter at
        # 1.0 chance above (see ROOM_ENCOUNTER_CHANCE). Trap no longer
        # has a standalone mini-game of its own -- see the module
        # docstring.
        gold = round(rng.randint(6, 20) * (node["floor"] + 1) // 2 * difficulty["reward_multiplier"])
        add_currency(db, player, "gold", gold)
        _ledger_add_gold(expedition, gold)
        _mark_completed(expedition, expedition.current_node_id)
        db.commit()
        return {"kind": "resolved", "message": f"You pick your way past the trap unscathed. (+{format_currency('gold', gold)})"}

    if room_type == RoomType.PUZZLE:
        encounter = _maybe_roll_encounter(room_type, rng)
        if encounter is not None:
            intro = rng.choice(encounter["intros"])
            expedition.pending_interaction = {"kind": "encounter", "encounter_id": encounter["id"]}
            db.commit()
            return {"kind": "encounter", "message": intro}

        # Defensive fallback only -- shouldn't happen with ENCOUNTERS
        # populated for "puzzle", since RoomType.PUZZLE rolls an
        # encounter at 1.0 chance above (see ROOM_ENCOUNTER_CHANCE).
        # Puzzle no longer has a standalone mini-game of its own -- see
        # the module docstring.
        gold = round(rng.randint(6, 20) * (node["floor"] + 1) // 2 * difficulty["reward_multiplier"])
        add_currency(db, player, "gold", gold)
        _ledger_add_gold(expedition, gold)
        _mark_completed(expedition, expedition.current_node_id)
        db.commit()
        return {"kind": "resolved", "message": f"You find an old Cascade terminal, dark and unresponsive. (+{format_currency('gold', gold)})"}

    if room_type == RoomType.MERCHANT:
        encounter = _maybe_roll_encounter(room_type, rng)
        if encounter is not None:
            intro = rng.choice(encounter["intros"])
            expedition.pending_interaction = {"kind": "encounter", "encounter_id": encounter["id"]}
            db.commit()
            return {"kind": "encounter", "message": intro}

        # Defensive fallback only -- shouldn't happen with ENCOUNTERS
        # populated, since RoomType.MERCHANT rolls an encounter at 1.0
        # chance above (see ROOM_ENCOUNTER_CHANCE). Merchant rooms no
        # longer have a bespoke shop UI at all.
        _mark_completed(expedition, expedition.current_node_id)
        db.commit()
        return {"kind": "resolved", "message": "The trading post is closed today."}

    _mark_completed(expedition, expedition.current_node_id)
    db.commit()
    return {"kind": "resolved", "message": "Something happens."}


def move_to_node(db, expedition: Expedition, target_node_id: str) -> tuple[bool, str]:
    if expedition.combat_state:
        return False, "You can't leave -- you're in the middle of a battle!"
    if expedition.pending_interaction:
        return False, "Finish what you're doing here first!"

    if not gu.is_valid_move(expedition.graph, expedition.current_node_id, target_node_id):
        return False, "You can't go that way."

    expedition.current_node_id = target_node_id
    db.commit()
    return True, "Moved."


def abandon_expedition(db, expedition: Expedition, player) -> dict:
    """Voluntarily ends an active expedition early (the Forfeit button on
    the adventure menu). Blocked mid-battle or mid-encounter -- same
    guard as move_to_node -- so the run can't be pulled out from under an
    opponent mid-turn or a pending choice; in practice the Forfeit button
    is only ever shown when neither is true anyway (see
    bot.cogs.dungeon._build_dungeon_view), this is just the defensive
    belt-and-suspenders check.

    Nothing already earned this run is clawed back -- same as a defeat,
    the ledger just reflects wherever the run happened to stop. Does NOT
    record "complete_adventures" quest progress the way a real win/loss
    does: that quest is for runs that reached an actual conclusion in the
    dungeon, and counting a forfeit toward it would let it be farmed by
    immediately abandoning a freshly-started expedition.

    Returns {"ok": False, "message": ...} if blocked, else
    {"ok": True, "ledger": ...} on success.
    """
    if expedition.combat_state:
        return {"ok": False, "message": "You can't forfeit -- you're in the middle of a battle!"}
    if expedition.pending_interaction:
        return {"ok": False, "message": "Finish what you're doing here first!"}

    expedition.status = ExpeditionStatus.ABANDONED
    ledger = _ledger(expedition)
    db.commit()
    return {"ok": True, "ledger": ledger}


def resolve_battle_end(db, expedition: Expedition, player, battle) -> dict:
    """Call once battle.is_over(). Applies rewards/penalties, clears combat
    state, and returns a summary dict for the cog to render. A run can have
    3-5 bosses (see the generator) -- only defeating the FINAL one in
    graph['boss_nodes'] completes the expedition; earlier ones are big,
    rewarding checkpoints that let the run continue. Every win records
    "win_battles" quest progress, plus "defeat_boss" or "defeat_elite" on
    top of that if the room was a BOSS or ELITE encounter respectively."""
    combat_service.sync_party_hp_to_characters(db, battle)

    if battle.result == "won":
        room_type = expedition.graph["nodes"][expedition.current_node_id]["room_type"]
        rewards = combat_service.apply_victory_rewards(db, player, expedition, room_type=room_type)
        quest_service.record_progress(db, player, "win_battles")
        if room_type == RoomType.BOSS:
            quest_service.record_progress(db, player, "defeat_boss")
        elif room_type == RoomType.ELITE:
            quest_service.record_progress(db, player, "defeat_elite")
        _ledger_add_gold(expedition, rewards["gold"])
        _ledger_add_xp(expedition, rewards["xp"])
        for item in rewards["items"]:
            _ledger_add_item(expedition, item)
        if rewards.get("material"):
            _ledger_add_material(expedition, rewards["material"]["type"], rewards["material"]["amount"])
        if rewards.get("lootbox"):
            _ledger_add_lootbox(expedition, rewards["lootbox"]["tier"], rewards["lootbox"]["quantity"])
        if rewards.get("reroll_tokens"):
            _ledger_add_reroll_tokens(expedition, rewards["reroll_tokens"])
        _ledger_record_level_ups(expedition, rewards["level_ups"])
        _mark_completed(expedition, expedition.current_node_id)
        combat_service.clear_battle(db, expedition)

        final_boss = expedition.graph.get("boss_nodes", [expedition.graph.get("boss_node")])[-1]
        if expedition.current_node_id == final_boss:
            expedition.status = ExpeditionStatus.COMPLETED
            db.commit()
            quest_service.record_progress(db, player, "complete_adventures")
            return {"kind": "expedition_complete", "rewards": rewards, "ledger": _ledger(expedition)}

        db.commit()
        is_boss = expedition.current_node_id in expedition.graph.get("boss_nodes", [])
        return {"kind": "boss_cleared" if is_boss else "victory", "rewards": rewards}

    if battle.result == "lost":
        expedition.status = ExpeditionStatus.FAILED
        combat_service.clear_battle(db, expedition)
        ledger = _ledger(expedition)
        db.commit()
        quest_service.record_progress(db, player, "complete_adventures")
        return {"kind": "defeat", "ledger": ledger}

    return {"kind": "ongoing"}


# ----------------------------------------------------------------------
# Encounter room resolution -- a small generic interpreter for the data
# in encounter_config.py. See that module's docstring for the full shape
# of an encounter/choice/outcome; the short version is every choice is
# one of "leave" (no roll), "risk" (no cost, straight success_chance),
# "trade" (pay `cost` up front, then success_chance), or "gamble" (pay
# `cost`, then pick one of several weighted `tiers`).
#
# Every gain/loss/spend routed through here also feeds the expedition's
# loot ledger (see the _ledger_* helpers up top) so encounter rewards
# and merchant purchases show up in the whole-run summary exactly like
# combat/treasure/trap/puzzle rewards do.
# ----------------------------------------------------------------------

def get_pending_encounter(expedition: Expedition) -> dict | None:
    """Reconstructs the active encounter dict from
    Expedition.pending_interaction -- used when re-rendering an encounter
    room without going through enter_node again (e.g. resuming via
    /adventure after a restart)."""
    interaction = expedition.pending_interaction or {}
    if interaction.get("kind") != "encounter":
        return None
    return get_encounter_by_id(interaction.get("encounter_id"))


def get_encounter_choices(encounter: dict) -> list[dict]:
    return encounter["choices"]


def _can_afford(player, cost: dict) -> bool:
    """Checked BEFORE anything is spent -- if the player can't afford
    even one currency in `cost`, the trade/gamble never touches the
    player's balances at all (see resolve_encounter_choice's
    "cant_afford_text" branch)."""
    return all(getattr(player, currency, 0) >= amount for currency, amount in cost.items())

def _format_cost_shortfall(player, cost: dict) -> str:
    """Builds a 'you have X, need Y' readout for every currency a choice's
    cost calls for -- shown alongside cant_afford_text so the player can
    see exactly what they're short on without leaving the encounter to
    go check /stash themselves. Lists every currency in `cost`, not just
    the ones actually short, so it doubles as a quick "here's what this
    choice needs" reference too."""
    parts = []
    for currency, amount in cost.items():
        have = getattr(player, currency, 0)
        parts.append(f"{format_currency(currency, have)} (need {format_currency(currency, amount)})")
    return "You have: " + ", ".join(parts)

def _spend_cost(db, player, cost: dict, expedition: Expedition) -> None:
    """Only ever called after _can_afford has already confirmed the
    player can cover every currency in `cost` -- but spend_currency
    itself also refuses to take a balance negative (returns False,
    changes nothing) as a second, independent safety net, so this can
    never leave a currency below zero even if that pre-check were ever
    skipped or raced."""
    for currency, amount in cost.items():
        spend_currency(db, player, currency, amount)
        if currency == "gold":
            _ledger_add_gold(expedition, amount, spent=True)
        elif currency == "reroll_tokens":
            _ledger_add_reroll_tokens(expedition, amount, spent=True)


def _roll_amount(rng: random.Random, amount) -> int:
    if isinstance(amount, (list, tuple)):
        return rng.randint(amount[0], amount[1])
    return amount


def _apply_hp_damage(db, player, rng: random.Random, percent: int) -> str | None:
    """Knocks a random squad member for `percent`% of their (gear-adjusted)
    max HP. Clamped to a minimum of 1 HP -- an encounter can never itself
    knock a character out."""
    squad = character_service.get_squad(db, player)
    if not squad:
        return None

    from bot.game.combat.factory import build_character_combatant

    equipped_by_char = character_service.get_equipped_items_by_character(db, [pc.id for pc in squad])
    victim = rng.choice(squad)
    combatant = build_character_combatant(victim, equipped_by_char.get(victim.id, []))
    lost = max(1, round(combatant.max_hp * percent / 100))
    victim.current_hp = max(1, combatant.current_hp - lost)
    return f"{victim.display_name} takes {lost} damage!"


def _apply_gain(
    db, player, rng: random.Random, gain: dict, gold_mult: float, expedition: Expedition,
    max_item_rarity: Rarity | None = None, item_level: int = 1,
) -> list[str]:
    gain = dict(gain)
    lines: list[str] = []

    if "material_tier" in gain:
        tier = gain.pop("material_tier")
        amount = _roll_amount(rng, gain.pop("amount", [1, 3]))
        material = rng.choice(_MATERIAL_TIERS[tier])
        if amount > 0:
            add_currency(db, player, material.value, amount)
            _ledger_add_material(expedition, material.value, amount)
            lines.append(f"+{format_currency(material.value, amount)}")

    item_spec = gain.pop("item", False)
    if item_spec:
        # Rarity is rolled FIRST, then a template is picked to match it
        # (via item_template_service.pick_random_template's `rarity`
        # filter) -- the same decoupled roll-then-select order every
        # other item source in the game uses (see
        # combat_service.apply_victory_rewards), rather than picking a
        # random template up front and deriving/forcing a rarity onto it.
        generator = LootGenerator(rng=rng)
        if item_spec == "natural":
            # No rarity_override -- rolls the normal weighted rarity,
            # capped by the region's max_item_rarity, same as any other
            # in-run drop. Usually Common/Uncommon, rarely much better --
            # this is the "possible but rare higher tier reward" path for
            # encounter-granted gear.
            rarity = generator.roll_rarity(max_rarity=max_item_rarity)
        elif item_spec is True:
            # True -> guaranteed Common, like a basic shop item.
            rarity = Rarity.COMMON
        else:
            # An explicit rarity string ("uncommon"/"rare"/"epic"/
            # "legendary"/"mythic"). This is what the High Roller shop
            # (Colosseum Bookie) sells: a GUARANTEED rarity, no chance
            # involved -- deliberately bypasses the region's usual
            # rarity cap. Gold buys certainty here, not odds.
            rarity = Rarity(item_spec)

        template = item_template_service.pick_random_template(db, rng=rng, rarity=rarity)
        if template is not None:
            item = generator.generate_item(
                template, player_id=player.id, item_level=item_level, rarity_override=rarity,
            )
            db.add(item)
            db.commit()
            db.refresh(item)
            _ledger_add_item(expedition, item)
            lines.append(f"a {item.rarity.value.title()} {item.display_name}")

    lootbox_tier = gain.pop("lootbox", None)
    if lootbox_tier:
        lootbox_service.grant_lootbox(db, player, lootbox_tier, quantity=1)
        _ledger_add_lootbox(expedition, lootbox_tier, quantity=1)
        lines.append(f"a {lootbox_tier.title()} Lootbox")

    xp_spec = gain.pop("xp", None)
    if xp_spec:
        xp_amount = _roll_amount(rng, xp_spec)
        squad = character_service.get_squad(db, player)
        if squad and xp_amount > 0:
            level_ups = combat_service.apply_character_xp(db, squad, xp_amount)
            _ledger_add_xp(expedition, xp_amount)
            _ledger_record_level_ups(expedition, level_ups)
            suffix = " -- level up!" if level_ups else ""
            lines.append(f"+{xp_amount} XP (whole squad){suffix}")

    for currency, value in gain.items():
        amount = _roll_amount(rng, value)
        if currency == "gold":
            amount = round(amount * gold_mult)
        if amount <= 0:
            continue
        add_currency(db, player, currency, amount)
        if currency == "gold":
            _ledger_add_gold(expedition, amount)
        elif currency == "shards":
            _ledger_add_shards(expedition, amount)
        elif currency == "reroll_tokens":
            _ledger_add_reroll_tokens(expedition, amount)
        elif currency in {m.value for m in MaterialType}:
            _ledger_add_material(expedition, currency, amount)
        lines.append(f"+{format_currency(currency, amount)}")

    return lines


def _apply_loss(db, player, rng: random.Random, loss: dict, expedition: Expedition) -> list[str]:
    """Every loss is clamped to `min(what the player actually has, the
    rolled amount)` before spend_currency is ever called -- an encounter
    can only take what's really there, never push a balance negative."""
    loss = dict(loss)
    lines: list[str] = []

    if "material_tier" in loss:
        tier = loss.pop("material_tier")
        amount = _roll_amount(rng, loss.pop("amount", [1, 3]))
        material = rng.choice(_MATERIAL_TIERS[tier])
        actual = min(getattr(player, material.value), amount)
        if actual > 0:
            spend_currency(db, player, material.value, actual)
            lines.append(f"-{format_currency(material.value, actual)}")

    for currency, value in loss.items():
        amount = _roll_amount(rng, value)
        actual = min(getattr(player, currency, 0), amount)
        if actual > 0:
            spend_currency(db, player, currency, actual)
            if currency == "gold":
                _ledger_add_gold(expedition, actual, spent=True)
            elif currency == "reroll_tokens":
                _ledger_add_reroll_tokens(expedition, actual, spent=True)
            lines.append(f"-{format_currency(currency, actual)}")

    return lines


def _apply_heal(db, player, rng: random.Random, heal_spec) -> str | None:
    """Restores squad HP -- the reward-side counterpart to
    _apply_hp_damage. Unlike damage (which always lands on one random
    squad member), healing is applied to the WHOLE squad: it reads
    better as a reward, and there's no squad-wide damage path to mirror
    anyway. heal_spec is either the string "full" (same full-heal semantics as
    Campfire rooms -- current_hp = None) or an int percent of each
    member's own max HP."""
    squad = character_service.get_squad(db, player)
    if not squad:
        return None

    if heal_spec == "full":
        for pc in squad:
            pc.current_hp = None
        return "Your squad is fully healed!"

    from bot.game.combat.factory import build_character_combatant

    equipped_by_char = character_service.get_equipped_items_by_character(db, [pc.id for pc in squad])
    healed_any = False
    for pc in squad:
        combatant = build_character_combatant(pc, equipped_by_char.get(pc.id, []))
        if combatant.current_hp >= combatant.max_hp:
            continue
        restored = max(1, round(combatant.max_hp * heal_spec / 100))
        pc.current_hp = min(combatant.max_hp, combatant.current_hp + restored)
        healed_any = True

    return f"Your squad recovers {heal_spec}% HP." if healed_any else None


def _apply_outcome(
    db, player, rng: random.Random, outcome: dict, gold_mult: float, expedition: Expedition,
    max_item_rarity: Rarity | None = None, item_level: int = 1,
) -> list[str]:
    if not outcome:
        return []
    lines: list[str] = []
    if outcome.get("gain"):
        lines += _apply_gain(db, player, rng, outcome["gain"], gold_mult, expedition, max_item_rarity, item_level)
    if outcome.get("loss"):
        lines += _apply_loss(db, player, rng, outcome["loss"], expedition)
    if outcome.get("hp_damage_percent"):
        line = _apply_hp_damage(db, player, rng, outcome["hp_damage_percent"])
        if line:
            lines.append(line)
    if outcome.get("heal"):
        line = _apply_heal(db, player, rng, outcome["heal"])
        if line:
            lines.append(line)
    bonus = outcome.get("bonus")
    if bonus:
        # "bonus" can be a single {"chance": p, "gain": {...}} dict, or a
        # list of them -- each rolled independently. This is how a choice
        # can carry e.g. a small Shard chance AND a separate small
        # Lootbox chance without them competing for the same roll.
        for spec in (bonus if isinstance(bonus, list) else [bonus]):
            if rng.random() < spec.get("chance", 0):
                lines += _apply_gain(db, player, rng, spec.get("gain", {}), gold_mult, expedition, max_item_rarity, item_level)
    return lines


def resolve_encounter_choice(db, expedition: Expedition, player, choice_id: str, rng: random.Random | None = None) -> dict:
    rng = rng or random.Random()
    encounter = get_pending_encounter(expedition)
    if encounter is None:
        return {"kind": "encounter", "message": "Something's gone wrong with this encounter."}

    choice = next((c for c in encounter["choices"] if c["id"] == choice_id), None)
    if choice is None:
        return {"kind": "encounter", "message": "Not a valid choice."}

    node = expedition.graph["nodes"][expedition.current_node_id]
    difficulty = get_region_difficulty(expedition.region)
    gold_mult = difficulty["reward_multiplier"]
    max_item_rarity = difficulty["max_item_rarity"]
    item_level = node["floor"] + 1 + difficulty["level_offset"]
    action = choice["action"]

    if action == "leave":
        message = choice.get("text") or f"You leave {encounter['name']} behind."

    elif action == "risk":
        success = rng.random() < choice.get("success_chance", 0.5)
        outcome = choice.get("on_success" if success else "on_fail", {})
        message = choice.get("success_text" if success else "fail_text", "") or ""
        lines = _apply_outcome(db, player, rng, outcome, gold_mult, expedition, max_item_rarity, item_level)
        if lines:
            message = f"{message}\n{', '.join(lines)}" if message else ", ".join(lines)

    elif action in ("trade", "gamble"):
        # Affordability is checked BEFORE anything is spent -- if the
        # player can't cover the full cost, the choice just declines
        # and the encounter stays open: we return early here (kind
        # "encounter", pending_interaction untouched) instead of falling
        # through to the shared "mark completed" tail below, so the
        # player lands back on the same encounter and can pick a
        # different choice or explicitly Leave, rather than getting
        # booted out of the room for a choice they never actually took.
        cost = choice.get("cost", {})
        if not _can_afford(player, cost):
            base_msg = choice.get("cant_afford_text") or "You don't have enough for that."
            message = f"{base_msg}\n{_format_cost_shortfall(player, cost)}"
            return {"kind": "encounter", "message": message}

        _spend_cost(db, player, cost, expedition)
        if action == "trade":
            success = rng.random() < choice.get("success_chance", 1.0)
            outcome = choice.get("on_success" if success else "on_fail", {})
            message = choice.get("success_text" if success else "fail_text", "") or ""
        else:  # gamble
            tiers = choice.get("tiers", [])
            tier = rng.choices(tiers, weights=[t["chance"] for t in tiers], k=1)[0]
            outcome = tier.get("outcome", {})
            message = tier.get("text", "") or ""

        lines = _apply_outcome(db, player, rng, outcome, gold_mult, expedition, max_item_rarity, item_level)
        if lines:
            message = f"{message}\n{', '.join(lines)}" if message else ", ".join(lines)

    else:
        message = "Nothing happens."

    expedition.pending_interaction = None
    _mark_completed(expedition, expedition.current_node_id)
    db.commit()
    return {"kind": "resolved", "message": message}