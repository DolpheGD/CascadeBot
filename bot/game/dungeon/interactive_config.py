"""
DEPRECATED / phased out.

Trap and Puzzle rooms used to have their own bespoke mini-games here
(TRAP_CHOICES + PUZZLES, resolved by bot/services/dungeon_service.py's
resolve_trap_choice/resolve_puzzle_choice). Merchant's old bespoke shop
table was removed from this module earlier, in favor of "merchant"-
tagged Encounters -- see bot/game/dungeon/encounter_config.py.

Trap and Puzzle have now been folded into that same Encounter system:
every non-combat/campfire/start room type (Story, Treasure, Trap,
Shrine, Puzzle, Secret, Merchant) resolves entirely through
encounter_config.py's ENCOUNTERS pool now, at 100% odds (see
dungeon_service.ROOM_ENCOUNTER_CHANCE). There is no more standalone
Trap or Puzzle mini-game, no TrapView/PuzzleView in bot/cogs/dungeon.py,
and nothing in the codebase should import TRAP_CHOICES, PUZZLES, or any
of the other names this module used to export -- if something still
does, it's stale and should be updated to use encounter_config.py
instead.

This file is kept as an (intentionally empty) placeholder rather than
deleted outright, in case anything still references the module path
directly; it exports nothing.
"""

from __future__ import annotations