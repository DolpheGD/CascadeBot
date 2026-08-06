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

from bot.database.models.enums import MATERIAL_TIERS, MaterialType
from bot.game.combat.battle import Battle
from bot.game.combat.factory import build_enemy_combatant, build_party_combatants
from bot.game.combat.serialization import battle_from_dict, battle_to_dict
from bot.game.economy.lootbox_config import tier_for_floor_and_region
from bot.game.loot.generator import LootGenerator
from bot.services import (
    base_service,
    character_service,
    item_template_service,
    lootbox_service,
    relic_service,
)
from bot.services.currency_service import add_currency

# Chance of an item dropping on victory -- elites and bosses feel worth
# fighting instead of just being harder versions of a regular encounter.
ITEM_DROP_CHANCE = {"combat": 0.5, "elite": 0.75, "boss": 1.0}

# Combat rework: materials and a lootbox chance now drop from EVERY combat
# victory (previously only treasure/secret rooms handed those out, so
# fighting was a strictly worse source of them than just walking around a
# fight). Elites guarantee both -- at minimum a Common lootbox, per spec --
# so they read as clearly worth seeking out rather than just a harder
# regular fight for a similar payout.
MATERIAL_DROP_CHANCE = {"combat": 0.55, "elite": 1.0, "boss": 1.0}
LOOTBOX_DROP_CHANCE = {"combat": 0.35, "elite": 1.0, "boss": 1.0}

# Gold/XP multiplier by room type on top of the base per-floor formula --
# "Defeating the boss should grant great rewards"
# just the guaranteed material/lootbox.
ROOM_TYPE_REWARD_MULTIPLIER = {"combat": 1.0, "elite": 1.5, "boss": 2.0}

# Combat reroll token drop chance and reward sizes. These are a small
# additional source of reroll tokens to make combat feel directly useful
# for the item re-roll economy.
REROLL_DROP_CHANCE = {"combat": 0.25, "elite": 0.5, "boss": 1.0}
REROLL_DROP_AMOUNTS = {"combat": (1, 1), "elite": (1, 3), "boss": (2, 3)}

# How many floors it takes to step up one material tier for COMBAT drops.
# Deliberately slower than the treasure/encounter track
# (dungeon_service.FLOORS_PER_MATERIAL_TIER == 7): combat is the most
# frequent material source in a run, so it climbs tiers more grudgingly to
# keep exploration rooms worth taking.
FLOORS_PER_MATERIAL_TIER = 9


def _material_for_floor(floor: int, rng: random.Random) -> MaterialType:
    tier_index = min(floor // FLOORS_PER_MATERIAL_TIER, len(MATERIAL_TIERS) - 1)
    return rng.choice(MATERIAL_TIERS[tier_index])


def start_battle(db, expedition, player, enemy_templates: list, level: int) -> Battle:
    """Start a battle.

    `enemy_templates` may be either a list of template dicts (legacy behavior)
    in which case every enemy uses the shared `level` parameter, or a list of
    (template, level) pairs to allow per-enemy level overrides (used for
    mixing regular enemies into elite encounters so normal enemies can scale
    off the region's combat_level_offset while elites use the standard
    level_offset).
    """
    squad = character_service.get_squad(db, player)
    equipped_by_char = character_service.get_equipped_items_by_character(
        db, [pc.id for pc in squad]
    )
    from bot.services import research_service
    party_combatants = build_party_combatants(squad, equipped_by_char,
        starting_energy=research_service.perk_value(db, player.id, "starting_energy"))
    base_service.apply_shrine_bonuses(db, player, party_combatants)
    # Run-scoped relics, applied after shrines so their percentages are
    # computed against the fully-equipped, fully-shrined stat line -- the
    # same ordering gear substats already use.
    relic_service.apply_relic_effects(expedition, party_combatants)

    enemy_combatants = []
    for entry in enemy_templates:
        if isinstance(entry, (list, tuple)) and len(entry) == 2:
            tpl, tpl_level = entry
            enemy_combatants.append(build_enemy_combatant(tpl, level=tpl_level))
        else:
            enemy_combatants.append(build_enemy_combatant(entry, level=level))

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


# HP a downed character is revived to after a battle the run SURVIVED.
# Deliberately 1, not a heal: they're back on their feet and can act, but
# they are one hit from going down again and the player still has to
# spend a campfire or a heal on them. Dying costs something either way.
REVIVE_HP_AFTER_BATTLE = 1


def sync_party_hp_to_characters(db, battle: Battle, revive_downed: bool | None = None) -> None:
    """Writes each surviving/defeated party Combatant's HP back onto its
    PlayerCharacter row, so the next battle (or the profile/squad view)
    reflects real HP instead of resetting to full every time.

    `revive_downed` decides what happens to a character on 0 HP:

      * True (the default, and every ONGOING run) -- they come back at
        REVIVE_HP_AFTER_BATTLE. Without this, one death mid-run left that
        character on 0 HP for every remaining fight, unable to act and
        unrevivable until the run ended: an invisible, permanent squad
        wipe that the player couldn't do anything about.
      * False -- 0 is written through as 0. Used for the run-ENDING
        defeat, where the loss screen reports who fell and a character
        quietly standing back up at 1 HP would contradict it.

    That's the whole distinction: a death you fought past, versus the
    death that ended the run.

    DEFAULT IS AUTO (`None`), and it should stay that way. The rule the
    game actually wants is "you get up unless EVERYONE went down", and
    that's derivable from the party itself -- so callers don't have to
    remember to pass the right flag, and can't get it wrong. Every mode
    (expedition, story, hunt, Abyss) therefore behaves identically:
    survive with anyone standing and the fallen are back at 1 HP; wipe
    and the whole squad reads 0/max on the roster, which is the only
    honest thing to show after a wipe.

    The explicit boolean remains for the rare caller that needs to force
    the outcome."""
    from bot.database.models.character_model import PlayerCharacter

    character_ids = [c.character_id for c in battle.party if c.character_id is not None]
    if not character_ids:
        return
    if revive_downed is None:
        # A wipe is "nobody is left standing", not "the Battle object said
        # lost" -- results can also be set by fleeing or a cycle timeout,
        # and a squad that walked away with survivors should not have
        # those survivors' corpses displayed.
        revive_downed = any(c.current_hp > 0 for c in battle.party)
    rows = {
        pc.id: pc
        for pc in db.query(PlayerCharacter).filter(PlayerCharacter.id.in_(character_ids)).all()
    }
    for combatant in battle.party:
        pc = rows.get(combatant.character_id)
        if pc is None:
            continue
        if combatant.current_hp <= 0 and revive_downed:
            pc.current_hp = REVIVE_HP_AFTER_BATTLE
        else:
            # Preserve the full-HP sentinel when a combatant ends a battle at max HP.
            # This keeps characters at true full health when future max HP changes
            # from leveling, shrine bonuses, or other effects are applied.
            pc.current_hp = None if combatant.current_hp >= combatant.max_hp else combatant.current_hp
    db.commit()


def restore_squad_to_full_hp(db, squad: list) -> None:
    """Resets every squad member to full HP by clearing the persisted
    value back to the None sentinel (see PlayerCharacter.current_hp).

    Called before starting any SELF-CONTAINED fight -- a domain challenge
    or a raid attack. Those are one-off battles you pay an entry cost for
    (energy, or one of a limited number of raid attacks), not steps
    within a longer run, so carrying HP into them was doing real damage
    to both features: one bad domain fight left the squad too hurt to
    attempt another, and there is no way to heal outside an expedition
    campfire, so the only fix available to the player was to go run a
    whole expedition first. That's backwards -- domains exist precisely
    as the "I don't want to commit to a full run" option.

    Expeditions deliberately do NOT use this between rooms: HP as a
    resource spent across a run is the entire point of the campfire
    Rest-vs-Relic decision (see dungeon_service's campfire block).
    start_expedition does reset at the START of a run, for the same
    reason this exists -- a fresh piece of content shouldn't inherit an
    unrelated one's damage."""
    for pc in squad:
        pc.current_hp = None  # None == full HP
    db.commit()


def apply_character_xp(db, squad: list, xp_reward: int, player=None) -> list[dict]:
    """Splits `xp_reward` evenly across every squad member (not just who
    landed the killing blow -- simpler and keeps off-action support/sustain
    characters from falling behind). Level cap is 100 per the leveling spec."""
    from bot.database.models.character_model import LEVEL_CAP

    # Research Lab's Fieldwork branch (character_xp_percent).
    if player is not None:
        from bot.services import research_service
        bonus = research_service.perk_value(db, player.id, "character_xp_percent")
        if bonus:
            xp_reward = int(round(xp_reward * (1 + bonus / 100)))

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
            summaries.append({"name": pc.display_name, "from": leveled_from, "to": pc.level})
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

    # Combat rework: base gold/xp payout raised across the board so combat
    # rewards feel worth it on their own, on top of the new material/
    # lootbox drops below.
    gold_reward = round((20 + (floor // 5) * 8) * multiplier * relic_service.gold_multiplier(expedition))
    xp_reward = round((15 + (floor // 5) * 7) * multiplier)

    add_currency(db, player, "gold", gold_reward)
    squad = character_service.get_squad(db, player)
    level_ups = apply_character_xp(db, squad, xp_reward)

    items = []
    drop_chance = ITEM_DROP_CHANCE.get(room_type, 0.4)
    if rng.random() < drop_chance:
        generator = LootGenerator(rng=rng)
        # Research Lab's Salvage branch (loot_rarity_weight) tilts the
        # roll upward. Applied HERE rather than inside generate_item
        # because these call sites pass rarity_override, which bypasses
        # roll_rarity entirely -- putting it only in the generator would
        # have made the perk silently do nothing on real drops.
        from bot.services import research_service
        # Region tilt PLUS the research perk, added together: a deep
        # region should be a better place to farm top rarities, not just
        # a place where they're legal (see region_config's RARITY ODDS
        # block). Both feed the same weighting mechanism, so they stack
        # smoothly rather than one overriding the other.
        rarity = generator.roll_rarity(
            max_rarity=difficulty["max_item_rarity"],
            rarity_weight_bonus=(
                difficulty.get("rarity_weight_bonus", 0)
                + research_service.perk_value(db, player.id, "loot_rarity_weight")
            ),
        )
        template = item_template_service.pick_random_template(db, rng=rng, rarity=rarity)
        if template is not None:
            # Equipment always starts at level 1 -- the player levels it up
            # themselves. Power at drop time comes from RARITY (capped by
            # region difficulty, and by the template's own tier window)
            # instead of a floor-scaled starting level.
            item = generator.generate_item(
                template, player_id=player.id, item_level=1, rarity_override=rarity,
            )
            db.add(item)
            db.commit()
            db.refresh(item)
            items.append(item)

    # Combat rework: materials drop from combat victories at scaling odds,
    # guaranteed for elites/bosses. Amount scales up with room type so
    # elites/bosses feel like a meaningfully better material source, not
    # just a better shot at one.
    material = None
    if rng.random() < MATERIAL_DROP_CHANCE.get(room_type, 0.5):
        material_type = _material_for_floor(floor, rng)
        material_amount = round(rng.randint(2, 6) * difficulty["reward_multiplier"])
        if room_type == "elite":
            material_amount = round(material_amount * 1.5)
        elif room_type == "boss":
            material_amount = material_amount * 2
        material_amount = max(1, material_amount)
        add_currency(db, player, material_type.value, material_amount)
        material = {"type": material_type.value, "amount": material_amount}

    # Combat rework: lootbox chance on every combat victory -- guaranteed
    # (at minimum a Common lootbox, since tier_for_floor_and_region never
    # returns below that) for elites and bosses.
    lootbox = None
    if rng.random() < LOOTBOX_DROP_CHANCE.get(room_type, 0.2):
        tier = tier_for_floor_and_region(floor, difficulty["max_lootbox_tier"])
        lootbox_service.grant_lootbox(db, player, tier, quantity=1)
        lootbox = {"tier": tier, "quantity": 1}

    return {
        "gold": gold_reward, "xp": xp_reward, "items": items, "level_ups": level_ups,
        "material": material, "lootbox": lootbox,
    }