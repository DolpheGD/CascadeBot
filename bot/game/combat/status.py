"""
Lightweight, battle-scoped status effect records. These live only on a
Combatant for the duration of one battle -- nothing here is persisted.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class StatModifier:
    """A temporary percent buff (positive) or debuff (negative) on one stat."""
    stat: str
    percent: float
    duration: int  # turns remaining; decremented at the end of the owner's turn
    source: str = ""


@dataclass
class DamageOverTime:
    """A damage-per-turn effect (e.g. burn). `flat_amount` is frozen at the
    moment the DOT is applied (based on the caster's stat at cast time),
    so buffing the caster later doesn't retroactively strengthen it."""
    flat_amount: float
    duration: int
    source: str = ""
    stat_source: str = ""  # metadata only, for logging/flavor


@dataclass
class HealOverTime:
    """A heal-per-turn effect (regen). `percent_max_hp` is evaluated against
    the *owner's own* max_hp each tick (unlike DamageOverTime's frozen flat
    amount) so a regen effect stays meaningful even if max_hp changes
    mid-battle -- and because a "heal 5% max HP a turn" support ability
    reads far more naturally than a frozen flat number."""
    percent_max_hp: float
    duration: int
    source: str = ""
