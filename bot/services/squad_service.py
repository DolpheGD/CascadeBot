"""
Named squad presets: save a lineup, swap to it later.

A preset is a SAVED COPY, not a second live squad. Loading one writes its
character ids into the player's SquadSlot rows, which every other system
already reads. See SquadPreset's docstring for why it is done that way
round.
"""

from __future__ import annotations

from bot.database.models.character_model import PlayerCharacter, SquadPreset, SquadSlot
from bot.services import character_service

# Enough for story / adventure / raid / a spare, and few enough that the
# preset list fits one select without paging.
MAX_PRESETS = 6
SQUAD_SIZE = 4


class SquadPresetError(Exception):
    """Any reason a preset action can't proceed, phrased for the player."""


def list_presets(db, player) -> list[SquadPreset]:
    return (
        db.query(SquadPreset)
        .filter_by(player_id=player.id)
        .order_by(SquadPreset.created_at)
        .all()
    )


def get_preset(db, player, preset_id: int) -> SquadPreset | None:
    """Looked up WITH the player filter, always.

    preset_id arrives from a component custom_id, which is client
    supplied -- fetching by primary key alone would let anyone load or
    delete anyone else's preset by replaying a button. The ownership
    filter is the check.
    """
    return (
        db.query(SquadPreset)
        .filter_by(id=preset_id, player_id=player.id)
        .one_or_none()
    )


def save_preset(db, player, name: str) -> SquadPreset:
    """Snapshot the CURRENT squad under `name`, overwriting a preset of
    the same name if one exists."""
    name = (name or "").strip()[:32]
    if not name:
        raise SquadPresetError("Give the preset a name.")

    by_slot = character_service.get_squad_by_slot(db, player)
    ids = [by_slot.get(i).id if by_slot.get(i) else None
           for i in range(SQUAD_SIZE)]
    if not any(ids):
        raise SquadPresetError("There's nobody in your squad to save.")

    existing = (
        db.query(SquadPreset)
        .filter_by(player_id=player.id, name=name)
        .one_or_none()
    )
    if existing is not None:
        # Overwrite rather than refuse. "That name is taken" on a save
        # button is a worse answer than doing the obvious thing, and
        # re-saving a tweaked lineup under its own name is the single
        # most common thing anybody will do here.
        existing.character_ids = ids
        db.commit()
        return existing

    if len(list_presets(db, player)) >= MAX_PRESETS:
        raise SquadPresetError(
            f"You can keep {MAX_PRESETS} presets. Delete one first.")

    preset = SquadPreset(player_id=player.id, name=name, character_ids=ids)
    db.add(preset)
    db.commit()
    return preset


def load_preset(db, player, preset_id: int) -> tuple[SquadPreset, list[str]]:
    """Seat a preset's characters. Returns (preset, warnings).

    STALE ENTRIES ARE DROPPED, NOT FATAL. A preset stores ids, and an id
    can stop resolving. Refusing to load the whole lineup because one
    slot went missing would strand the player on a screen that only says
    no; seating the three who are fine and saying so is strictly better.
    """
    preset = get_preset(db, player, preset_id)
    if preset is None:
        raise SquadPresetError("That preset isn't yours.")

    owned = {c.id: c for c in character_service.list_owned_characters(db, player)}
    avatar = character_service.ensure_avatar_character(db, player)

    warnings: list[str] = []
    wanted: list[int | None] = []
    for index, character_id in enumerate((preset.character_ids or [])[:SQUAD_SIZE]):
        if character_id is None:
            wanted.append(None)
            continue
        if character_id not in owned:
            warnings.append(f"slot {index + 1} was empty — that character is gone")
            wanted.append(None)
            continue
        wanted.append(character_id)
    while len(wanted) < SQUAD_SIZE:
        wanted.append(None)

    # SLOT 0 IS ALWAYS THE AVATAR. get_squad's contract says so, and a
    # preset saved before the avatar existed (or hand-edited) could
    # otherwise seat somebody else there and quietly break every caller
    # that assumes slot 0 is you.
    if wanted[0] != avatar.id:
        wanted[0] = avatar.id

    # A character may not occupy two slots.
    seen: set[int] = set()
    for index, character_id in enumerate(wanted):
        if character_id is not None and character_id in seen:
            wanted[index] = None
            warnings.append(f"slot {index + 1} was a duplicate and was cleared")
        elif character_id is not None:
            seen.add(character_id)

    slots = {s.slot_index: s for s in
             db.query(SquadSlot).filter_by(player_id=player.id).all()}
    for index in range(SQUAD_SIZE):
        slot = slots.get(index)
        if slot is None:
            slot = SquadSlot(player_id=player.id, slot_index=index)
            db.add(slot)
        slot.character_id = wanted[index]
    db.commit()
    return preset, warnings


def delete_preset(db, player, preset_id: int) -> str:
    preset = get_preset(db, player, preset_id)
    if preset is None:
        raise SquadPresetError("That preset isn't yours.")
    name = preset.name
    db.delete(preset)
    db.commit()
    return name


def describe(db, player, preset: SquadPreset) -> str:
    """One line naming who is in it, for the preset list."""
    owned = {c.id: c for c in character_service.list_owned_characters(db, player)}
    names = []
    for character_id in (preset.character_ids or []):
        if character_id is None:
            continue
        character = owned.get(character_id)
        if character is None:
            names.append("*(missing)*")
        else:
            names.append(character.custom_name or character.template.name)
    return ", ".join(names) or "*empty*"
