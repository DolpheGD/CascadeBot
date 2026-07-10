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
    MATERIAL_DISPLAY_NAME,
    ExpeditionStatus,
    MaterialType,
    Rarity,
    RoomType,
)
from bot.database.models.equipment_model import ItemTemplate
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
from bot.game.economy.lootbox_config import tier_for_floor
from bot.game.loot.generator import LootGenerator
from bot.services import character_service, combat_service, lootbox_service
from bot.services.currency_service import add_currency, spend_currency

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
    number of bosses (1-4) and floor count per the run-length spec item --
    pass it explicitly to force the old fixed-length single-boss shape."""
    existing = get_active_expedition(db, player.id)
    if existing is not None:
        return existing

    graph = DungeonGenerator().generate(region, num_floors=num_floors)

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

        templates = (
            enemy_catalog.get_templates_by_role(room_type.value)
            or enemy_catalog.get_templates_by_role("combat")
        )
        count = rng.choice([1, 1, 2]) if room_type == RoomType.COMBAT else 1
        chosen = [rng.choice(templates) for _ in range(min(count, 3))]
        level = node["floor"] + 1 + difficulty["level_offset"]
        combat_service.start_battle(db, expedition, player, chosen, level=level)

        names = ", ".join(c["name"] for c in chosen)
        return {"kind": "combat", "message": f"{names} appears!"}

    if room_type == RoomType.CAMPFIRE:
        for pc in character_service.get_squad(db, player):
            pc.current_hp = None  # None == full HP, see PlayerCharacter.current_hp
        gu.mark_completed(expedition.graph, expedition.current_node_id)
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
        message = f"You find a treasure chest containing {gold} gold!"

        material = _material_for_floor(node["floor"])
        material_amount = rng.randint(3, 8)
        add_currency(db, player, material.value, material_amount)
        message += f" (+{material_amount} {MATERIAL_DISPLAY_NAME[material]})"

        drop_chance = min(0.25 + node["floor"] * 0.015, 0.45)
        if rng.random() < drop_chance:
            tier = tier_for_floor(node["floor"])
            lootbox_service.grant_lootbox(db, player, tier, quantity=1)
            message += f" It also contains a {tier.title()} Lootbox!"

        gu.mark_completed(expedition.graph, expedition.current_node_id)
        db.commit()
        return {"kind": "resolved", "message": message}

    if room_type == RoomType.SECRET:
        gold = round(rng.randint(5, 25) * difficulty["reward_multiplier"])
        add_currency(db, player, "gold", gold)
        tier = tier_for_floor(node["floor"])
        lootbox_service.grant_lootbox(db, player, tier, quantity=1)
        gu.mark_completed(expedition.graph, expedition.current_node_id)
        db.commit()
        return {
            "kind": "resolved",
            "message": (
                f"A hidden passage reveals a Cascade supply cache, forgotten but intact. "
                f"(+{gold} gold, +1 {tier.title()} Lootbox)"
            ),
        }

    if room_type == RoomType.START:
        gu.mark_completed(expedition.graph, expedition.current_node_id)
        db.commit()
        return {"kind": "resolved", "message": "Your expedition begins."}

    if room_type == RoomType.STORY:
        gold = round(rng.randint(4, 15) * difficulty["reward_multiplier"])
        add_currency(db, player, "gold", gold)
        gu.mark_completed(expedition.graph, expedition.current_node_id)
        db.commit()
        return {"kind": "resolved", "message": f"{_story_fragment(rng)} (+{gold} gold)"}

    if room_type == RoomType.SHRINE:
        gold = round(rng.randint(4, 15) * difficulty["reward_multiplier"])
        add_currency(db, player, "gold", gold)
        gu.mark_completed(expedition.graph, expedition.current_node_id)
        db.commit()
        return {"kind": "resolved", "message": f"{ROOM_FLAVOR[RoomType.SHRINE]} (+{gold} gold)"}

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

    gu.mark_completed(expedition.graph, expedition.current_node_id)
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
    1-4 bosses (see the generator) -- only defeating the FINAL one in
    graph['boss_nodes'] completes the expedition; earlier ones are big,
    rewarding checkpoints that let the run continue."""
    combat_service.sync_party_hp_to_characters(db, battle)

    if battle.result == "won":
        room_type = expedition.graph["nodes"][expedition.current_node_id]["room_type"]
        rewards = combat_service.apply_victory_rewards(db, player, expedition, room_type=room_type)
        gu.mark_completed(expedition.graph, expedition.current_node_id)
        combat_service.clear_battle(db, expedition)

        final_boss = expedition.graph.get("boss_nodes", [expedition.graph.get("boss_node")])[-1]
        if expedition.current_node_id == final_boss:
            expedition.status = ExpeditionStatus.COMPLETED
            db.commit()
            return {"kind": "expedition_complete", "rewards": rewards}

        db.commit()
        is_boss = expedition.current_node_id in expedition.graph.get("boss_nodes", [])
        return {"kind": "boss_cleared" if is_boss else "victory", "rewards": rewards}

    if battle.result == "lost":
        expedition.status = ExpeditionStatus.FAILED
        combat_service.clear_battle(db, expedition)
        db.commit()
        return {"kind": "defeat"}

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
        message = f"{TRAP_SUCCESS_FLAVOR} (+{gold} gold)"
    else:
        gold = round(base_gold * choice["fail_gold_mult"])
        if gold:
            add_currency(db, player, "gold", gold)
        message = TRAP_FAIL_FLAVOR
        if gold:
            message += f" (+{gold} gold)"

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
    gu.mark_completed(expedition.graph, expedition.current_node_id)
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
        message = f"Correct! The terminal unlocks a small cache. (+{gold} gold)"
    else:
        gold = round(base_gold * PUZZLE_FAIL_GOLD_MULT)
        answer = puzzle["options"][puzzle["correct_index"]]
        message = f"Not quite -- the answer was '{answer}'. You still scavenge a little on your way out. (+{gold} gold)"

    add_currency(db, player, "gold", gold)
    expedition.pending_interaction = None
    gu.mark_completed(expedition.graph, expedition.current_node_id)
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
        return False, f"Not enough gold (need {offer['cost_gold']})."

    if offer["kind"] == "lootbox":
        lootbox_service.grant_lootbox(db, player, offer["tier"], quantity=1)
        message = f"Bought a {offer['tier'].title()} Lootbox!"
    elif offer["kind"] == "shards":
        add_currency(db, player, "shards", offer["amount"])
        message = f"Bought {offer['amount']} Shards!"
    else:  # "item" -- a random basic (Common) item
        templates = db.query(ItemTemplate).all()
        if not templates:
            spend_currency(db, player, "gold", -offer["cost_gold"])  # refund, nothing to give
            return False, "The quartermaster is out of stock."
        template = rng.choice(templates)
        node = expedition.graph["nodes"][expedition.current_node_id]
        item = LootGenerator(rng=rng).generate_item(
            template, player_id=player.id, item_level=max(1, node["floor"]), rarity_override=Rarity.COMMON,
        )
        db.add(item)
        db.commit()
        message = f"Bought {item.display_name}!"

    db.commit()
    return True, message


def leave_shop(db, expedition: Expedition) -> dict:
    expedition.pending_interaction = None
    gu.mark_completed(expedition.graph, expedition.current_node_id)
    db.commit()
    return {"kind": "resolved", "message": "You head back out onto the path."}
