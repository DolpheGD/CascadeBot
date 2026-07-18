"""
Everything about OWNING and organizing characters: granting the free avatar
character to new players, building/reading a player's 4-slot squad, and
converting gacha duplicates into resources instead of a wasted second copy.

The actual pull mechanics (rates, currency spend) live in
bot/services/character_gacha_service.py -- this module is what that will
call into once a character template has been chosen to grant.
"""

from __future__ import annotations

import re

from bot.database.models.character_model import PlayerCharacter, SquadSlot
from bot.database.models.equipment_model import InventoryItem
from bot.services.character_template_service import get_avatar_template
from bot.services.currency_service import add_currency

# Resources granted for pulling a duplicate of a character you already own,
# scaled by star rating -- higher star dupes are worth more since they're
# rarer to begin with. Tuned as a starting point; retune freely.
DUPE_REWARDS_BY_STAR: dict[int, dict[str, int]] = {
    3: {"gold": 200, "reroll_tokens": 5},
    4: {"gold": 500, "reroll_tokens": 12},
    5: {"gold": 1200, "reroll_tokens": 25},
}

# Rename validation -- matches PlayerCharacter.custom_name's column width
# (String(32)). Deliberately conservative on allowed characters: letters,
# digits, spaces, and a small set of punctuation. No backtick/asterisk/
# underscore/tilde/pipe (Discord markdown), no @ (pings), no newlines.
CUSTOM_NAME_MAX_LENGTH = 32
CUSTOM_NAME_PATTERN = re.compile(r"^[A-Za-z0-9 '\-.]+$")


def ensure_avatar_character(db, player) -> PlayerCharacter:
    """Every player owns exactly one copy of the free, class-switchable
    avatar character. Creates it (and seats it in squad slot 0) the first
    time it's needed -- e.g. on /profile, /squad, or before a battle."""
    template = get_avatar_template(db)
    existing = (
        db.query(PlayerCharacter)
        .filter_by(player_id=player.id, template_id=template.id)
        .first()
    )
    if existing is not None:
        return existing

    pc = PlayerCharacter(player_id=player.id, template_id=template.id, level=1)
    db.add(pc)
    db.commit()
    db.refresh(pc)

    slot0 = db.query(SquadSlot).filter_by(player_id=player.id, slot_index=0).first()
    if slot0 is None:
        db.add(SquadSlot(player_id=player.id, slot_index=0, character_id=pc.id))
    else:
        slot0.character_id = pc.id
    db.commit()
    return pc


def list_owned_characters(db, player) -> list[PlayerCharacter]:
    """Every character the player owns, not just the 4 in their active
    squad -- for the /squad picker and a future character-collection view."""
    ensure_avatar_character(db, player)
    return (
        db.query(PlayerCharacter)
        .filter_by(player_id=player.id)
        .order_by(PlayerCharacter.template_id)
        .all()
    )


def get_squad(db, player) -> list[PlayerCharacter]:
    """Ordered list (slot 0 first) of the player's active squad -- 1 to 4
    PlayerCharacters. Slot 0 (the avatar) is auto-created/seated if this is
    the player's first time calling this."""
    ensure_avatar_character(db, player)

    slots = (
        db.query(SquadSlot)
        .filter_by(player_id=player.id)
        .order_by(SquadSlot.slot_index)
        .all()
    )
    squad = [s.character for s in slots if s.character_id is not None]
    return squad


def get_squad_by_slot(db, player) -> dict[int, PlayerCharacter | None]:
    """Slot 0-3 -> occupant (or None) -- unlike get_squad(), this always has
    all 4 keys even for empty slots, which the /squad UI needs to render
    every slot (filled or not)."""
    ensure_avatar_character(db, player)
    slots = db.query(SquadSlot).filter_by(player_id=player.id).all()
    by_slot: dict[int, PlayerCharacter | None] = {i: None for i in range(4)}
    for slot in slots:
        by_slot[slot.slot_index] = slot.character
    return by_slot


def set_squad_slot(db, player, slot_index: int, character: PlayerCharacter | None) -> tuple[bool, str]:
    if not 0 <= slot_index <= 3:
        return False, "Squad slots are numbered 0-3."
    if slot_index == 0 and character is not None and not character.template.is_player_avatar:
        return False, "Slot 0 is reserved for your own avatar character."
    if character is not None and character.player_id != player.id:
        return False, "You don't own that character."

    if character is not None:
        # A character can only occupy one slot at a time -- bump it out of
        # wherever else it was seated.
        other = (
            db.query(SquadSlot)
            .filter(SquadSlot.player_id == player.id, SquadSlot.character_id == character.id,
                    SquadSlot.slot_index != slot_index)
            .first()
        )
        if other is not None:
            other.character_id = None

    slot = db.query(SquadSlot).filter_by(player_id=player.id, slot_index=slot_index).first()
    if slot is None:
        slot = SquadSlot(player_id=player.id, slot_index=slot_index)
        db.add(slot)
    slot.character_id = character.id if character else None
    db.commit()
    return True, "Squad updated."


def get_equipped_items_by_character(db, character_ids: list[int]) -> dict[int, list[InventoryItem]]:
    if not character_ids:
        return {}
    rows = (
        db.query(InventoryItem)
        .filter(InventoryItem.character_id.in_(character_ids), InventoryItem.is_equipped.is_(True))
        .all()
    )
    by_character: dict[int, list[InventoryItem]] = {cid: [] for cid in character_ids}
    for item in rows:
        by_character.setdefault(item.character_id, []).append(item)
    return by_character


def get_progression_level(db, player) -> int:
    """Player.level/xp are vestigial now that leveling lives on
    PlayerCharacter (see the Combat Overhaul) -- anything that used to use
    the player's own level as a rough 'how far along are they' proxy (e.g.
    picking item_level for a lootbox drop) should use this instead: the
    level of their strongest squad character."""
    squad = get_squad(db, player)
    return max((pc.level for pc in squad), default=1)


def grant_character(db, player, template) -> tuple[PlayerCharacter, bool, dict[str, int] | None]:
    """Grants `template` to `player`. Returns (player_character, is_new,
    dupe_reward). If the player already owns this template, no new row is
    created -- dupe_count goes up and a resource reward is paid out instead
    (per the 'duplicates grant resources' spec requirement)."""
    existing = (
        db.query(PlayerCharacter)
        .filter_by(player_id=player.id, template_id=template.id)
        .first()
    )
    if existing is not None:
        existing.dupe_count += 1
        reward = dict(DUPE_REWARDS_BY_STAR.get(template.star_rating, {"gold": 150, "reroll_tokens": 3}))
        for currency, amount in reward.items():
            add_currency(db, player, currency, amount)
        db.commit()
        return existing, False, reward

    pc = PlayerCharacter(player_id=player.id, template_id=template.id, level=1)
    db.add(pc)
    db.commit()
    db.refresh(pc)
    return pc, True, None


def rename_avatar(db, player, new_name: str | None) -> tuple[bool, str]:
    """Sets (or, if `new_name` is None/blank, clears) the custom_name on
    the player's own avatar PlayerCharacter -- lets them go by something
    other than the "You" template name everywhere it's shown (profile,
    squad, combat logs). Returns (success, message); on success `message`
    is a friendly confirmation, on failure it's why the name was rejected.

    Only the avatar can be renamed this way for now -- slot 0 is "who you
    are" (see squad.py), pulled characters keep their own identity."""
    avatar = ensure_avatar_character(db, player)

    if new_name is None or not new_name.strip():
        avatar.custom_name = None
        db.commit()
        return True, f"Reset your name back to **{avatar.template.name}**."

    cleaned = " ".join(new_name.split())  # collapse/strip whitespace
    if len(cleaned) > CUSTOM_NAME_MAX_LENGTH:
        return False, f"Names can be at most {CUSTOM_NAME_MAX_LENGTH} characters."
    if not CUSTOM_NAME_PATTERN.match(cleaned):
        return False, "Names can only contain letters, numbers, spaces, and `' - .`"

    avatar.custom_name = cleaned
    db.commit()
    return True, f"You're now known as **{cleaned}**."
