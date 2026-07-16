"""
Expedition lifecycle: starting a run, moving between dungeon nodes, and
resolving whatever each room type does. Combat rooms hand off to
combat_service. Trap/Puzzle/Merchant rooms are genuinely interactive --
they set Expedition.pending_interaction and hand off to the resolver
functions at the bottom of this module (called from cogs/dungeon.py's
button/select handlers), rather than resolving instantly like the simpler
flavor rooms (Story/Shrine/Secret) still do.
"""

from __future__ import annotations

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
from bot.game.dungeon.generator import DungeonGenerator
from bot.game.dungeon.interactive_config import (
    PUZZLE_FAIL_GOLD_MULT,
    PUZZLE_SUCCESS_GOLD_MULT,
    PUZZLES,
    SHOP_OFFERS,
    TRAP_CHOICES,
    TRAP_FAIL_FLAVOR,
    TRAP_INTRO,
    TRAP_SUCCESS_FLAVOR,
)
from bot.game.dungeon.region_config import get_region_difficulty
from bot.game.economy.lootbox_config import tier_for_floor_and_region
from bot.game.loot.generator import LootGenerator
from bot.services import character_service, combat_service, item_template_service, lootbox_service
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
    tier_index = min(floor // 4, len(_MATERIAL_TIERS) - 1)
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

# Story rooms reveal fragments of the world's history one piece at a time,
# never the whole picture at once -- see docs/WORLD_LORE.md for the
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
    render ("combat" -> battle view, "trap"/"puzzle"/"shop" -> their own
    interactive views, "resolved"/"expedition_complete" -> map view)."""
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

        level = node["floor"] + 1 + difficulty["level_offset"]
        combat_service.start_battle(db, expedition, player, chosen, level=level)
        # Awaiting an explicit "Start Battle" press before any turns are
        # fast-forwarded (see _combat_entry_view_and_embed in
        # bot/cogs/dungeon.py) -- otherwise, facing enemies faster than
        # the whole party, the player's first-ever glimpse of the fight
        # would already be several turns in, with those opening enemy
        # turns having resolved before they saw anything.
        expedition.pending_interaction = {"kind": "start_battle"}

        names = ", ".join(c["name"] for c in chosen)
        return {"kind": "combat", "message": f"{names} appears!"}

    if room_type == RoomType.CAMPFIRE:
        for pc in character_service.get_squad(db, player):
            pc.current_hp = None  # None == full HP, see PlayerCharacter.current_hp
        _mark_completed(expedition, expedition.current_node_id)
        db.commit()
        return {"kind": "resolved", "message": "You rest at the campfire. Your squad heals to full."}

    if room_type == RoomType.TREASURE:
        # Balancing pass: this used to be 20-60 gold * (floor+1), which at
        # floor 8 could hand out ~9x a combat room's reward for zero risk --
        # exactly the "treasure rooms give so much more" imbalance called
        # out in the spec. Still meaningfully better than a combat room
        # (no fight risked), just not absurdly so.
        gold = round(rng.randint(15, 30) * (node["floor"] + 1) // 2 * difficulty["reward_multiplier"])
        add_currency(db, player, "gold", gold)
        _ledger_add_gold(expedition, gold)
        message = f"You find a treasure chest containing {format_currency('gold', gold)}!"

        material = _material_for_floor(node["floor"])
        material_amount = rng.randint(3, 8)
        add_currency(db, player, material.value, material_amount)
        _ledger_add_material(expedition, material.value, material_amount)
        message += f" (+{format_currency(material.value, material_amount)})"

        drop_chance = min(0.25 + node["floor"] * 0.015, 0.45)
        if rng.random() < drop_chance:
            tier = tier_for_floor_and_region(node["floor"], difficulty["max_lootbox_tier"])
            lootbox_service.grant_lootbox(db, player, tier, quantity=1)
            _ledger_add_lootbox(expedition, tier, quantity=1)
            message += f" It also contains a {tier.title()} Lootbox!"

        _mark_completed(expedition, expedition.current_node_id)
        db.commit()
        return {"kind": "resolved", "message": message}

    if room_type == RoomType.SECRET:
        gold = round(rng.randint(5, 25) * difficulty["reward_multiplier"])
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
        gold = round(rng.randint(4, 15) * difficulty["reward_multiplier"])
        add_currency(db, player, "gold", gold)
        _ledger_add_gold(expedition, gold)
        _mark_completed(expedition, expedition.current_node_id)
        db.commit()
        return {"kind": "resolved", "message": f"{_story_fragment(rng)} (+{format_currency('gold', gold)})"}

    if room_type == RoomType.SHRINE:
        gold = round(rng.randint(4, 15) * difficulty["reward_multiplier"])
        add_currency(db, player, "gold", gold)
        _ledger_add_gold(expedition, gold)
        _mark_completed(expedition, expedition.current_node_id)
        db.commit()
        return {"kind": "resolved", "message": f"{ROOM_FLAVOR[RoomType.SHRINE]} (+{format_currency('gold', gold)})"}

    if room_type == RoomType.TRAP:
        expedition.pending_interaction = {"kind": "trap"}
        db.commit()
        return {"kind": "trap", "message": TRAP_INTRO}

    if room_type == RoomType.PUZZLE:
        puzzle = rng.choice(PUZZLES)
        expedition.pending_interaction = {"kind": "puzzle", "puzzle_id": puzzle["id"]}
        db.commit()
        return {"kind": "puzzle", "message": "You find an old Cascade terminal, still active.", "puzzle": puzzle}

    if room_type == RoomType.MERCHANT:
        expedition.pending_interaction = {"kind": "shop"}
        db.commit()
        return {"kind": "shop", "message": "A Cascade quartermaster has set up a supply cache here."}

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


def resolve_battle_end(db, expedition: Expedition, player, battle) -> dict:
    """Call once battle.is_over(). Applies rewards/penalties, clears combat
    state, and returns a summary dict for the cog to render. A run can have
    3-5 bosses (see the generator) -- only defeating the FINAL one in
    graph['boss_nodes'] completes the expedition; earlier ones are big,
    rewarding checkpoints that let the run continue."""
    combat_service.sync_party_hp_to_characters(db, battle)

    if battle.result == "won":
        room_type = expedition.graph["nodes"][expedition.current_node_id]["room_type"]
        rewards = combat_service.apply_victory_rewards(db, player, expedition, room_type=room_type)
        _ledger_add_gold(expedition, rewards["gold"])
        _ledger_add_xp(expedition, rewards["xp"])
        for item in rewards["items"]:
            _ledger_add_item(expedition, item)
        _ledger_record_level_ups(expedition, rewards["level_ups"])
        _mark_completed(expedition, expedition.current_node_id)
        combat_service.clear_battle(db, expedition)

        final_boss = expedition.graph.get("boss_nodes", [expedition.graph.get("boss_node")])[-1]
        if expedition.current_node_id == final_boss:
            expedition.status = ExpeditionStatus.COMPLETED
            db.commit()
            return {"kind": "expedition_complete", "rewards": rewards, "ledger": _ledger(expedition)}

        db.commit()
        is_boss = expedition.current_node_id in expedition.graph.get("boss_nodes", [])
        return {"kind": "boss_cleared" if is_boss else "victory", "rewards": rewards}

    if battle.result == "lost":
        expedition.status = ExpeditionStatus.FAILED
        combat_service.clear_battle(db, expedition)
        ledger = _ledger(expedition)
        db.commit()
        return {"kind": "defeat", "ledger": ledger}

    return {"kind": "ongoing"}


# ----------------------------------------------------------------------
# Trap room resolution
# ----------------------------------------------------------------------

def get_pending_puzzle(expedition: Expedition) -> dict | None:
    """Reconstructs the active puzzle dict from Expedition.pending_interaction
    -- used when re-rendering a puzzle room without going through enter_node
    again (e.g. resuming via /adventure after a restart)."""
    interaction = expedition.pending_interaction or {}
    if interaction.get("kind") != "puzzle":
        return None
    return next((p for p in PUZZLES if p["id"] == interaction.get("puzzle_id")), None)


def get_trap_choices() -> list[dict]:
    return TRAP_CHOICES


def resolve_trap_choice(db, expedition: Expedition, player, choice_id: str, rng: random.Random | None = None) -> dict:
    rng = rng or random.Random()
    node = expedition.graph["nodes"][expedition.current_node_id]
    difficulty = get_region_difficulty(expedition.region)
    choice = next((c for c in TRAP_CHOICES if c["id"] == choice_id), None)
    if choice is None:
        return {"kind": "trap", "message": "Not a valid choice."}

    base_gold = round((10 + node["floor"] * 5) * difficulty["reward_multiplier"])
    success = rng.random() < choice["success_chance"]

    if success:
        gold = round(base_gold * choice["success_gold_mult"])
        add_currency(db, player, "gold", gold)
        _ledger_add_gold(expedition, gold)
        message = f"{TRAP_SUCCESS_FLAVOR} (+{format_currency('gold', gold)})"
    else:
        gold = round(base_gold * choice["fail_gold_mult"])
        if gold:
            add_currency(db, player, "gold", gold)
            _ledger_add_gold(expedition, gold)
        message = TRAP_FAIL_FLAVOR
        if gold:
            message += f" (+{format_currency('gold', gold)})"

        fail_damage_percent = choice.get("fail_damage_percent")
        if fail_damage_percent:
            squad = character_service.get_squad(db, player)
            if squad:
                from bot.game.combat.factory import build_character_combatant

                equipped_by_char = character_service.get_equipped_items_by_character(db, [pc.id for pc in squad])
                victim = rng.choice(squad)
                combatant = build_character_combatant(victim, equipped_by_char.get(victim.id, []))
                lost = max(1, round(combatant.max_hp * fail_damage_percent / 100))
                victim.current_hp = max(1, combatant.current_hp - lost)
                message += f"\n{victim.template.name} takes {lost} damage from the blast!"

    expedition.pending_interaction = None
    _mark_completed(expedition, expedition.current_node_id)
    db.commit()
    return {"kind": "resolved", "message": message}


# ----------------------------------------------------------------------
# Puzzle room resolution
# ----------------------------------------------------------------------

def resolve_puzzle_choice(db, expedition: Expedition, player, option_index: int, rng: random.Random | None = None) -> dict:
    rng = rng or random.Random()
    node = expedition.graph["nodes"][expedition.current_node_id]
    difficulty = get_region_difficulty(expedition.region)

    interaction = expedition.pending_interaction or {}
    puzzle = next((p for p in PUZZLES if p["id"] == interaction.get("puzzle_id")), None)
    if puzzle is None:
        return {"kind": "puzzle", "message": "Something's gone wrong with this puzzle."}

    base_gold = round((12 + node["floor"] * 5) * difficulty["reward_multiplier"])
    correct = option_index == puzzle["correct_index"]

    if correct:
        gold = round(base_gold * PUZZLE_SUCCESS_GOLD_MULT)
        message = f"Correct! The terminal unlocks a small cache. (+{format_currency('gold', gold)})"
    else:
        gold = round(base_gold * PUZZLE_FAIL_GOLD_MULT)
        answer = puzzle["options"][puzzle["correct_index"]]
        message = f"Not quite -- the answer was '{answer}'. You still scavenge a little on your way out. (+{format_currency('gold', gold)})"

    add_currency(db, player, "gold", gold)
    _ledger_add_gold(expedition, gold)
    expedition.pending_interaction = None
    _mark_completed(expedition, expedition.current_node_id)
    db.commit()
    return {"kind": "resolved", "message": message}


# ----------------------------------------------------------------------
# Merchant / shop resolution
# ----------------------------------------------------------------------

def get_shop_offers() -> list[dict]:
    return SHOP_OFFERS


def buy_shop_item(db, expedition: Expedition, player, offer_id: str, rng: random.Random | None = None) -> tuple[bool, str]:
    rng = rng or random.Random()
    offer = next((o for o in SHOP_OFFERS if o["id"] == offer_id), None)
    if offer is None:
        return False, "That's not for sale here."

    if not spend_currency(db, player, "gold", offer["cost_gold"]):
        return False, f"Not enough {format_currency('gold', offer['cost_gold'])}."

    if offer["kind"] == "lootbox":
        lootbox_service.grant_lootbox(db, player, offer["tier"], quantity=1)
        _ledger_add_gold(expedition, offer["cost_gold"], spent=True)
        _ledger_add_lootbox(expedition, offer["tier"], quantity=1, bought=True)
        message = f"Bought a {offer['tier'].title()} Lootbox!"
    elif offer["kind"] == "shards":
        add_currency(db, player, "shards", offer["amount"])
        _ledger_add_gold(expedition, offer["cost_gold"], spent=True)
        _ledger_add_shards(expedition, offer["amount"])
        message = f"Bought {format_currency('shards', offer['amount'])}!"
    else:  # "item" -- a random basic (Common) item
        template = item_template_service.pick_random_template(db, rng=rng, rarity=Rarity.COMMON)
        if template is None:
            add_currency(db, player, "gold", offer["cost_gold"])  # refund, nothing to give
            return False, "The quartermaster is out of stock."
        item = LootGenerator(rng=rng).generate_item(
            template, player_id=player.id, item_level=1, rarity_override=Rarity.COMMON,
        )
        db.add(item)
        db.commit()
        _ledger_add_gold(expedition, offer["cost_gold"], spent=True)
        _ledger_add_item(expedition, item, bought=True)
        message = f"Bought {item.display_name}!"

    db.commit()
    return True, message


def leave_shop(db, expedition: Expedition) -> dict:
    expedition.pending_interaction = None
    _mark_completed(expedition, expedition.current_node_id)
    db.commit()
    return {"kind": "resolved", "message": "You head back out onto the path."}
