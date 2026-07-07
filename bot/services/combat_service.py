"""
Bridges the pure combat engine (bot.game.combat) to persistence. A battle's
entire state lives in Expedition.combat_state as JSON: load it, mutate it
through the Battle API, save it back. This is what lets a fight survive a
bot restart or the player disappearing for a week -- nothing is held only
in memory between Discord interactions.
"""

from __future__ import annotations

import random

from bot.database.models.equipment_model import InventoryItem, ItemTemplate
from bot.game.combat.battle import Battle
from bot.game.combat.factory import build_enemy_combatant, build_player_combatant
from bot.game.combat.serialization import battle_from_dict, battle_to_dict
from bot.game.loot.generator import LootGenerator
from bot.services.currency_service import add_currency

# Chance of an item dropping on victory, and how much better the room type
# makes item_level relative to floor depth -- elites and bosses feel worth
# fighting instead of just being harder versions of a regular encounter.
ITEM_DROP_CHANCE = {"combat": 0.4, "elite": 0.7, "boss": 1.0}
ITEM_LEVEL_BONUS = {"combat": 0, "elite": 2, "boss": 5}


def start_battle(db, expedition, player, enemy_templates: list[dict], level: int) -> Battle:
    equipped = (
        db.query(InventoryItem)
        .filter_by(player_id=player.id, is_equipped=True)
        .all()
    )
    player_combatant = build_player_combatant(player, equipped)
    enemy_combatants = [build_enemy_combatant(t, level=level) for t in enemy_templates]

    battle = Battle(player_combatant, enemy_combatants)
    expedition.combat_state = battle_to_dict(battle)
    db.commit()
    return battle


def load_battle(expedition) -> Battle | None:
    if not expedition.combat_state:
        return None
    return battle_from_dict(expedition.combat_state, rng=random.Random())


def save_battle(db, expedition, battle: Battle) -> None:
    expedition.combat_state = battle_to_dict(battle)
    db.commit()


def clear_battle(db, expedition) -> None:
    expedition.combat_state = None
    db.commit()


def apply_victory_rewards(
    db, player, expedition, room_type: str = "combat", rng: random.Random | None = None
) -> dict:
    rng = rng or random.Random()
    floor = expedition.graph["nodes"][expedition.current_node_id]["floor"]

    gold_reward = 20 + floor * 10
    xp_reward = 15 + floor * 8

    add_currency(db, player, "gold", gold_reward)
    player.xp += xp_reward
    while player.xp >= player.xp_to_next_level():
        player.xp -= player.xp_to_next_level()
        player.level += 1
    db.commit()

    items = []
    drop_chance = ITEM_DROP_CHANCE.get(room_type, 0.4)
    if rng.random() < drop_chance:
        templates = db.query(ItemTemplate).all()
        if templates:
            template = rng.choice(templates)
            item_level = max(1, floor + ITEM_LEVEL_BONUS.get(room_type, 0))
            item = LootGenerator(rng=rng).generate_item(
                template, player_id=player.id, item_level=item_level
            )
            db.add(item)
            db.commit()
            db.refresh(item)
            items.append(item)

    return {"gold": gold_reward, "xp": xp_reward, "items": items}
