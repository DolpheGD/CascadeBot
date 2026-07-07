"""
Combatant is the one representation combat works with, whether the
underlying thing is a Player+equipment or an enemy template -- the engine
never needs to know which. See bot/game/combat/factory.py for how each is
built.
"""

from __future__ import annotations

from dataclasses import dataclass, field

STAT_KEYS = [
    "attack", "defense", "magic", "speed", "luck", "max_hp",
    "crit_chance", "crit_damage", "dodge", "healing_bonus",
]


@dataclass
class Combatant:
    name: str
    is_player: bool
    base_stats: dict  # one entry per STAT_KEYS, already includes equipment bonuses

    current_hp: int
    max_hp: int

    mana: int = 0
    max_mana: int = 0
    energy: int = 0
    max_energy: int = 0

    active_abilities: list = field(default_factory=list)   # ability dicts, see loot/abilities.py
    passive_abilities: list = field(default_factory=list)

    cooldowns: dict = field(default_factory=dict)     # ability_id -> turns remaining
    charges_used: dict = field(default_factory=dict)  # ability_id -> times triggered this battle
    stacks: dict = field(default_factory=dict)         # ability_id -> current stack count

    modifiers: list = field(default_factory=list)  # list[StatModifier]
    dots: list = field(default_factory=list)        # list[DamageOverTime]

    stunned_turns: int = 0
    is_defending: bool = False

    def is_alive(self) -> bool:
        return self.current_hp > 0

    def effective_stat(self, stat: str) -> float:
        """Base stat, adjusted by every active percent modifier and any
        stacking passive buffs (e.g. Momentum) affecting that stat."""
        base = self.base_stats.get(stat, 0)
        percent_total = sum(m.percent for m in self.modifiers if m.stat == stat)

        for ability in self.passive_abilities:
            effect = ability["effect"]
            if effect["kind"] == "stacking_buff" and effect["buff_stat"] == stat:
                stacks = self.stacks.get(ability["id"], 0)
                percent_total += effect["percent_per_stack"] * stacks

        return max(0.0, base * (1 + percent_total / 100))

    def take_raw_hp_loss(self, amount: float) -> int:
        """Reduce HP by an already-computed damage amount. Returns actual loss."""
        amount = max(0, int(round(amount)))
        actual = min(self.current_hp, amount)
        self.current_hp -= actual
        return actual

    def heal(self, amount: float) -> int:
        amount = max(0, int(round(amount)))
        healed = min(self.max_hp - self.current_hp, amount)
        self.current_hp += healed
        return healed

    def find_passive(self, effect_kind: str) -> list:
        return [a for a in self.passive_abilities if a["effect"]["kind"] == effect_kind]

    def ability_ready(self, ability: dict) -> bool:
        if self.cooldowns.get(ability["id"], 0) > 0:
            return False
        pool = self.mana if ability["resource_type"] == "mana" else self.energy
        return pool >= ability["resource_cost"]

    def spend_resource(self, ability: dict) -> None:
        if ability["resource_type"] == "mana":
            self.mana -= ability["resource_cost"]
        else:
            self.energy -= ability["resource_cost"]
        self.cooldowns[ability["id"]] = ability.get("cooldown", 0)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Combatant {self.name!r} hp={self.current_hp}/{self.max_hp}>"
