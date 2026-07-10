"""
Bridges the pure combat engine (bot.game.combat) to persistence. A battle's
entire state lives in Expedition.combat_state as JSON: load it, mutate it
through the Battle API, save it back. This is what lets a fight survive a
bot restart or the player disappearing for a week -- nothing is held only
in memory between Discord interactions.

Combat Overhaul: battles now run a full squad (see character_service.get_squad)
instead of a single player Combatant, and each squad member's HP persists
on their PlayerCharacter row between battles (sync_party_hp_to_characters) --
the "HP isn't just 100 all the time" balancing note.
"""

from __future__ import annotations

import random

from bot.database.models.equipment_model import ItemTemplate
from bot.game.combat.battle import Battle
from bot.game.combat.factory import build_enemy_combatant, build_party_combatants
from bot.game.combat.serialization import battle_from_dict, battle_to_dict
from bot.game.loot.generator import LootGenerator
from bot.services import character_service
from bot.services.currency_service import add_currency

# Chance of an item dropping on victory, and how much better the room type
# makes item_level relative to floor depth -- elites and bosses feel worth
# fighting instead of just being harder versions of a regular encounter.
ITEM_DROP_CHANCE = {"combat": 0.4, "elite": 0.7, "boss": 1.0}
ITEM_LEVEL_BONUS = {"combat": 0, "elite": 2, "boss": 5}

# Gold/XP multiplier by room type on top of the base per-floor formula --
# "Defeating the boss should grant great rewards" from the spec.
ROOM_TYPE_REWARD_MULTIPLIER = {"combat": 1.0, "elite": 1.5, "boss": 3.0}


def start_battle(db, expedition, player, enemy_templates: list[dict], level: int) -> Battle:
    squad = character_service.get_squad(db, player)
    equipped_by_char = character_service.get_equipped_items_by_character(
        db, [pc.id for pc in squad]
    )
    party_combatants = build_party_combatants(squad, equipped_by_char)
    enemy_combatants = [build_enemy_combatant(t, level=level) for t in enemy_templates]

    battle = Battle(party_combatants, enemy_combatants)
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


def sync_party_hp_to_characters(db, battle: Battle) -> None:
    """Writes each surviving/defeated party Combatant's HP back onto its
    PlayerCharacter row, so the next battle (or the profile/squad view)
    reflects real HP instead of resetting to full every time."""
    from bot.database.models.character_model import PlayerCharacter

    character_ids = [c.character_id for c in battle.party if c.character_id is not None]
    if not character_ids:
        return
    rows = {
        pc.id: pc
        for pc in db.query(PlayerCharacter).filter(PlayerCharacter.id.in_(character_ids)).all()
    }
    for combatant in battle.party:
        pc = rows.get(combatant.character_id)
        if pc is not None:
            pc.current_hp = combatant.current_hp
    db.commit()


def apply_character_xp(db, squad: list, xp_reward: int) -> list[dict]:
    """Splits `xp_reward` evenly across every squad member (not just who
    landed the killing blow -- simpler and keeps off-action support/sustain
    characters from falling behind). Level cap is 100 per the leveling spec."""
    from bot.database.models.character_model import LEVEL_CAP

    summaries = []
    for pc in squad:
        if pc.level >= LEVEL_CAP:
            continue
        pc.xp += xp_reward
        leveled_from = pc.level
        while pc.level < LEVEL_CAP and pc.xp >= pc.xp_to_next_level():
            pc.xp -= pc.xp_to_next_level()
            pc.level += 1
        if pc.level >= LEVEL_CAP:
            pc.xp = 0
        if pc.level != leveled_from:
            summaries.append({"name": pc.template.name, "from": leveled_from, "to": pc.level})
    db.commit()
    return summaries


def apply_victory_rewards(
    db, player, expedition, room_type: str = "combat", rng: random.Random | None = None
) -> dict:
    from bot.game.dungeon.region_config import get_region_difficulty

    rng = rng or random.Random()
    floor = expedition.graph["nodes"][expedition.current_node_id]["floor"]
    difficulty = get_region_difficulty(expedition.region)
    multiplier = ROOM_TYPE_REWARD_MULTIPLIER.get(room_type, 1.0) * difficulty["reward_multiplier"]

    # Balancing pass: overall progression should feel slower / more grindy
    # than the original per-floor payout.
    gold_reward = round((12 + floor * 6) * multiplier)
    xp_reward = round((10 + floor * 5) * multiplier)

    add_currency(db, player, "gold", gold_reward)
    squad = character_service.get_squad(db, player)
    level_ups = apply_character_xp(db, squad, xp_reward)

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

    return {"gold": gold_reward, "xp": xp_reward, "items": items, "level_ups": level_ups}
