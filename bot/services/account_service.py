"""
Account-level progression: the "how far along is this player" numbers.

WHY AN ACCOUNT LEVEL AT ALL. Player.level and Player.xp still exist on
the model but have been vestigial since the Combat Overhaul moved
levelling onto PlayerCharacter -- they barely move and nothing reads
them, so a profile built on them reports "Level 3" to someone with a
fully-levelled roster. Deleting the columns would be a migration for no
benefit; the fix is to stop treating them as the account's progression
and DERIVE that instead.

Account level is derived from TOTAL CHARACTER LEVELS, the same measure
domains and raids already gate on (domain_service.roster_total_levels).
That's deliberate: the game already tells the player this number matters,
so making it the visible account level means one axis of progression
rather than two that disagree.

Derived rather than stored, for the same reason resonance is: existing
players get their real account level the moment this ships, with no
backfill, and it can never drift out of sync with the roster it
describes.
"""

from __future__ import annotations

# Total character levels needed for each account level. Super-linear, so
# early account levels come quickly (a new player should see the number
# move in their first session) and later ones represent real investment.
# Level 1 is 0 so everyone starts at 1 rather than 0.
ACCOUNT_LEVEL_STEP = 24
ACCOUNT_LEVEL_CURVE = 1.35
MAX_ACCOUNT_LEVEL = 60


def levels_required_for(account_level: int) -> int:
    """Total character levels needed to REACH `account_level`."""
    if account_level <= 1:
        return 0
    return int(ACCOUNT_LEVEL_STEP * ((account_level - 1) ** ACCOUNT_LEVEL_CURVE))


def account_level_for(total_character_levels: int) -> int:
    level = 1
    while level < MAX_ACCOUNT_LEVEL and total_character_levels >= levels_required_for(level + 1):
        level += 1
    return level


def account_progress(total_character_levels: int) -> dict:
    """Everything a profile needs to render the account level and its
    progress bar: the level, and how far through the current one."""
    level = account_level_for(total_character_levels)
    current_floor = levels_required_for(level)
    if level >= MAX_ACCOUNT_LEVEL:
        return {"level": level, "into": 0, "needed": 0, "fraction": 1.0, "maxed": True,
                "total_levels": total_character_levels}
    next_floor = levels_required_for(level + 1)
    span = max(1, next_floor - current_floor)
    into = total_character_levels - current_floor
    return {
        "level": level,
        "into": into,
        "needed": span,
        "fraction": min(1.0, into / span),
        "maxed": False,
        "total_levels": total_character_levels,
    }


def account_summary(db, player) -> dict:
    """One read of everything the account profile shows.

    Gathered here rather than in the embed so the view stays a view, and
    so a future /leaderboard entry or achievement check can ask the same
    question and get the same answer."""
    from bot.database.models.character_model import CharacterTemplate, PlayerCharacter
    from bot.database.models.equipment_model import InventoryItem
    from bot.game.economy.resonance_config import MAX_RESONANCE, resonance_for
    from bot.services import base_service, character_service, domain_service

    characters = db.query(PlayerCharacter).filter_by(player_id=player.id).all()
    total_levels = sum(c.level for c in characters)
    pullable = db.query(CharacterTemplate).filter_by(is_player_avatar=False).count()
    # The avatar is granted free and isn't in the pullable pool, so it
    # would make "collected" read as 1/24 before a single pull.
    collected = sum(1 for c in characters if not c.template.is_player_avatar)

    squad = character_service.get_squad(db, player)
    equipped = character_service.get_equipped_items_by_character(db, [c.id for c in squad])
    squad_power = 0
    for member in squad:
        items = equipped.get(member.id, [])
        squad_power += member.level * 10 + sum(i.item_level for i in items)

    base = base_service.get_or_create_base(db, player)
    progress = account_progress(total_levels)

    return {
        **progress,
        "characters_owned": collected,
        "characters_total": pullable,
        "resonance_maxed": sum(1 for c in characters if resonance_for(c.dupe_count) >= MAX_RESONANCE),
        "highest_character": max((c.level for c in characters), default=0),
        "squad_power": squad_power,
        "items_owned": db.query(InventoryItem).filter_by(player_id=player.id).count(),
        "hq_level": base.hq_level,
        "roster_levels_for_gates": domain_service.roster_total_levels(db, player),
    }
