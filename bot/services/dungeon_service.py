"""
Expedition lifecycle: starting a run, moving between dungeon nodes, and
resolving whatever each room type does. Combat rooms hand off to
combat_service; every other room type resolves immediately since a
prototype doesn't need a full minigame per room type yet -- that's a
natural place to expand later without touching this module's shape.
"""

from __future__ import annotations

import random

from bot.database.models.enums import ExpeditionStatus, RoomType
from bot.database.models.expedition_model import Expedition
from bot.game.combat import enemies as enemy_catalog
from bot.game.dungeon import graph_utils as gu
from bot.game.dungeon.generator import DungeonGenerator
from bot.game.economy.lootbox_config import tier_for_floor
from bot.services import combat_service, lootbox_service
from bot.services.currency_service import add_currency

ROOM_FLAVOR = {
    RoomType.TRAP: "A dormant security drone flickers on and takes a swing before you disable it, but you salvage its parts.",
    RoomType.SHRINE: "You find a stable shard of Void matter, still humming faintly. It offers a small blessing before going dark.",
    RoomType.PUZZLE: "An old terminal, somehow still powered, resists your access -- until it doesn't. It clicks satisfyingly.",
    RoomType.MERCHANT: "A Cascade quartermaster has set up a supply cache here. (Full shop coming soon.)",
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


def start_expedition(db, player, region: str, num_floors: int = 9) -> Expedition:
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
    dict describing what happened; `kind` tells the cog which view to render
    ("combat" -> battle view, "resolved"/"expedition_complete" -> map view)."""
    rng = rng or random.Random()
    node = expedition.graph["nodes"][expedition.current_node_id]
    room_type = RoomType(node["room_type"])

    if room_type in (RoomType.COMBAT, RoomType.ELITE, RoomType.BOSS):
        if expedition.combat_state:
            return {"kind": "combat", "message": "Battle already in progress."}

        templates = (
            enemy_catalog.get_templates_by_role(room_type.value)
            or enemy_catalog.get_templates_by_role("combat")
        )
        count = rng.choice([1, 1, 2]) if room_type == RoomType.COMBAT else 1
        chosen = [rng.choice(templates) for _ in range(min(count, 3))]
        combat_service.start_battle(db, expedition, player, chosen, level=node["floor"] + 1)

        names = ", ".join(c["name"] for c in chosen)
        return {"kind": "combat", "message": f"{names} appears!"}

    if room_type == RoomType.CAMPFIRE:
        expedition.current_hp = player.max_hp
        gu.mark_completed(expedition.graph, expedition.current_node_id)
        db.commit()
        return {"kind": "resolved", "message": "You rest at the campfire and heal to full."}

    if room_type == RoomType.TREASURE:
        gold = rng.randint(20, 60) * (node["floor"] + 1)
        add_currency(db, player, "gold", gold)
        message = f"You find a treasure chest containing {gold} gold!"

        drop_chance = min(0.35 + node["floor"] * 0.02, 0.6)
        if rng.random() < drop_chance:
            tier = tier_for_floor(node["floor"])
            lootbox_service.grant_lootbox(db, player, tier, quantity=1)
            message += f" It also contains a {tier.title()} Lootbox!"

        gu.mark_completed(expedition.graph, expedition.current_node_id)
        db.commit()
        return {"kind": "resolved", "message": message}

    if room_type == RoomType.SECRET:
        gold = rng.randint(5, 25)
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
        gold = rng.randint(5, 25)
        add_currency(db, player, "gold", gold)
        gu.mark_completed(expedition.graph, expedition.current_node_id)
        db.commit()
        return {"kind": "resolved", "message": f"{_story_fragment(rng)} (+{gold} gold)"}

    # Trap/Shrine/Puzzle/Merchant: flavor text + a small reward.
    flavor = ROOM_FLAVOR.get(room_type, "Something happens.")
    gold = rng.randint(5, 25)
    add_currency(db, player, "gold", gold)
    gu.mark_completed(expedition.graph, expedition.current_node_id)
    db.commit()
    return {"kind": "resolved", "message": f"{flavor} (+{gold} gold)"}


def move_to_node(db, expedition: Expedition, target_node_id: str) -> tuple[bool, str]:
    if expedition.combat_state:
        return False, "You can't leave -- you're in the middle of a battle!"

    if not gu.is_valid_move(expedition.graph, expedition.current_node_id, target_node_id):
        return False, "You can't go that way."

    expedition.current_node_id = target_node_id
    db.commit()
    return True, "Moved."


def resolve_battle_end(db, expedition: Expedition, player, battle) -> dict:
    """Call once battle.is_over(). Applies rewards/penalties, clears combat
    state, and returns a summary dict for the cog to render."""
    if battle.result == "won":
        room_type = expedition.graph["nodes"][expedition.current_node_id]["room_type"]
        rewards = combat_service.apply_victory_rewards(db, player, expedition, room_type=room_type)
        gu.mark_completed(expedition.graph, expedition.current_node_id)
        combat_service.clear_battle(db, expedition)

        if expedition.current_node_id == expedition.graph["boss_node"]:
            expedition.status = ExpeditionStatus.COMPLETED
            db.commit()
            return {"kind": "expedition_complete", "rewards": rewards}

        db.commit()
        return {"kind": "victory", "rewards": rewards}

    if battle.result == "lost":
        expedition.status = ExpeditionStatus.FAILED
        combat_service.clear_battle(db, expedition)
        db.commit()
        return {"kind": "defeat"}

    return {"kind": "ongoing"}
