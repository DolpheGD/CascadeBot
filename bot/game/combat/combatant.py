"""
Combatant is the one representation combat works with, whether the
underlying thing is a Player+equipment or an enemy template -- the engine
never needs to know which. See bot/game/combat/factory.py for how each is
built.

Stat design: attack (ATK), defense (DEF), elemental (ELE), speed (SPD),
max_hp, max_mana (MP), crit_rate%, crit_damage%, recharge (energy AND mana
gained per basic attack). No luck, no dodge -- nothing in combat can miss.
"""

from __future__ import annotations

from dataclasses import dataclass, field

STAT_KEYS = [
    "attack", "defense", "elemental", "speed", "max_hp", "max_mana",
    "crit_rate", "crit_damage", "recharge",
]


@dataclass
class Combatant:
    name: str
    is_player: bool  # True for any of the player's up-to-4 squad members, False for enemies
    base_stats: dict  # one entry per STAT_KEYS, already includes equipment bonuses

    current_hp: int
    max_hp: int

    # Which PlayerCharacter this Combatant was built from (None for
    # enemies) -- lets combat_service map battle results (HP left, XP)
    # back to the right owned character afterward.
    character_id: int | None = None
    character_class: str | None = None  # display only (CharacterClass.value)

    mana: int = 0
    max_mana: int = 0
    energy: int = 0
    max_energy: int = 50

    # Skills granted by equipped weapons + artifacts (player), or a fixed
    # moveset (enemy). Each costs mana (resource_type == "mana"). Ability
    # dicts carry a "source" tag ("weapon"/"artifact"/"enemy") purely for
    # UI flavor.
    active_abilities: list = field(default_factory=list)
    # The single ultimate ability granted by an equipped scroll (player) or
    # a boss's signature move (enemy, optional). Gated by energy == 50
    # (resource_type == "energy", resource_cost == 50) rather than mana.
    ultimate_ability: dict | None = None
    # Passive abilities, granted only by armor (player) or innate (enemy).
    passive_abilities: list = field(default_factory=list)

    cooldowns: dict = field(default_factory=dict)     # ability_id -> turns remaining
    charges_used: dict = field(default_factory=dict)  # ability_id -> times triggered this battle
    stacks: dict = field(default_factory=dict)         # ability_id -> current stack count

    modifiers: list = field(default_factory=list)  # list[StatModifier]
    dots: list = field(default_factory=list)        # list[DamageOverTime]
    heals: list = field(default_factory=list)       # list[HealOverTime]

    stunned_turns: int = 0

    # Flat HP-equivalent pool that absorbs incoming damage before current_hp
    # does (see self_shield_percent_max_hp / team_shield_percent_max_hp /
    # shield_regen in bot/game/combat/effects.py). Consumed first, in full
    # or in part, on every hit; never expires on its own -- it just runs out.
    shield: float = 0.0

    # Cycle-based turn order (see battle.py): every living combatant gets
    # exactly one action per cycle by default, ordered fastest-to-slowest,
    # with Speed only ever deciding WHEN a combatant goes, never WHETHER it
    # goes. This is the number of actions this combatant gets in each
    # cycle before that base ordering repeats -- set on enemy templates
    # (e.g. "actions_per_cycle": 2 for a boss that should act twice per
    # cycle) via factory.build_enemy_combatant, and/or granted by a
    # "bonus_actions_per_cycle" passive (see actions_per_cycle() below).
    base_actions_per_cycle: int = 1

    # Anti-stalemate attack ramp-up (replaces the old innate HP-regen
    # system -- see factory.build_enemy_combatant's
    # ATTACK_RAMP_PERCENT_PER_TURN_BY_ROLE). `ramp_percent_per_turn` is set
    # once at construction (0 for players -- this is enemy-only); each
    # turn this combatant takes, battle.py's _begin_turn bumps
    # `ramp_stacks` by 1, and effective_stat() folds the accumulated
    # stacks into attack/elemental as a small, PERMANENT (never expires,
    # never resets) percent bonus. Starts small enough to be
    # irrelevant in a normal fight and only becomes noticeable in a fight
    # that's dragged on far longer than intended, gently forcing a
    # resolution instead of letting two sides that can't quite out-damage
    # each other stalemate forever.
    ramp_percent_per_turn: float = 0.0
    ramp_stacks: int = 0

    def is_alive(self) -> bool:
        return self.current_hp > 0

    def actions_per_cycle(self) -> int:
        """Total actions this combatant takes each cycle: its configured
        base (usually 1, higher for a "goes twice/three times per cycle"
        enemy) plus any stacking bonus from "bonus_actions_per_cycle"
        passives (armor passive, enemy passive, or -- if ever wired onto
        that gear slot -- a weapon/artifact passive). Always at least 1;
        everyone acts at least once per cycle."""
        bonus = sum(
            passive["effect"].get("count", 1)
            for passive in self.find_passive("bonus_actions_per_cycle")
        )
        return max(1, self.base_actions_per_cycle + bonus)

    def effective_stat(self, stat: str) -> float:
        """Base stat, adjusted by every active percent modifier and any
        stacking passive buffs (e.g. Momentum) affecting that stat.
        Rounded to 2 decimal places -- chained float multiplication across
        several modifiers/passives was producing long, ugly decimals in
        combat logs and UI (e.g. 143.79999999999998); nothing in this game
        needs sub-cent precision on a stat value."""
        base = self.base_stats.get(stat, 0)
        percent_total = sum(m.percent for m in self.modifiers if m.stat == stat)

        if stat in ("attack", "elemental") and self.ramp_percent_per_turn and self.ramp_stacks:
            percent_total += self.ramp_percent_per_turn * self.ramp_stacks

        for ability in self.passive_abilities:
            effect = ability["effect"]
            if effect["kind"] == "stacking_buff" and effect["buff_stat"] == stat:
                stacks = self.stacks.get(ability["id"], 0)
                percent_total += effect["percent_per_stack"] * stacks

        return round(max(0.0, base * (1 + percent_total / 100)), 2)

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

    def gain_energy_and_mana(self, percent: float | None = None) -> tuple[int, int]:
        """Called after a basic attack: the default attack builds both
        energy (toward the ultimate) and mana (to spend on skills), by a
        PERCENT of each pool's max, scaled by the combatant's Recharge stat
        (recharge is itself a % value, e.g. 5 = +5% of max per basic
        attack). This -- rather than the old flat-amount version -- is what
        keeps Recharge from letting a high-level character reach their
        ultimate in 1-2 turns: a bigger max_mana/max_energy pool from
        leveling doesn't make each attack refill it any faster in absolute
        terms, only relative to that bigger pool. Returns (energy_gained, mana_gained)."""
        pct = percent if percent is not None else self.effective_stat("recharge")
        pct = max(0.0, pct)

        before_energy, before_mana = self.energy, self.mana
        energy_gain = int(round(self.max_energy * pct / 100))
        mana_gain = int(round(self.max_mana * pct / 100))
        self.energy = min(self.max_energy, self.energy + energy_gain)
        self.mana = min(self.max_mana, self.mana + mana_gain)
        return self.energy - before_energy, self.mana - before_mana

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

    def ultimate_ready(self) -> bool:
        return self.ultimate_ability is not None and self.ability_ready(self.ultimate_ability)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Combatant {self.name!r} hp={self.current_hp}/{self.max_hp}>"
