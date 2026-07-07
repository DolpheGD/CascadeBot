"""
Turn-based battle engine. 1 player vs 1-3 enemies; strict speed-initiative
turn order recomputed at the start of every round (buffs/debuffs can change
speed mid-fight, so a fixed order from round 1 wouldn't stay accurate).

Usage:

    battle = Battle(player_combatant, [enemy1, enemy2])
    while not battle.is_over():
        actor = battle.current_actor()
        if actor.is_player:
            battle.take_player_action("attack")            # or "ability"/"defend"/"flee"
        else:
            battle.take_enemy_turn()

    print(battle.result)  # "won" | "lost" | "fled"
"""

from __future__ import annotations

import random

from bot.game.combat import effects
from bot.game.combat.combatant import Combatant


class Battle:
    def __init__(self, player: Combatant, enemies: list[Combatant], rng: random.Random | None = None):
        if not 1 <= len(enemies) <= 3:
            raise ValueError("Battle supports 1-3 enemies")

        self.player = player
        self.enemies = enemies
        self.rng = rng or random.Random()

        self.round_number = 0
        self.log: list[str] = []
        self.result: str | None = None  # "won" | "lost" | "fled" | None while ongoing

        self._turn_order: list[Combatant] = []
        self._turn_index = 0
        self._start_round()

    # ------------------------------------------------------------------
    def all_combatants(self) -> list[Combatant]:
        return [self.player] + self.enemies

    def living_enemies(self) -> list[Combatant]:
        return [e for e in self.enemies if e.is_alive()]

    def is_over(self) -> bool:
        return self.result is not None

    def current_actor(self) -> Combatant:
        return self._turn_order[self._turn_index]

    # ------------------------------------------------------------------
    # Round / turn bookkeeping
    # ------------------------------------------------------------------
    def _start_round(self) -> None:
        self.round_number += 1
        living = [c for c in self.all_combatants() if c.is_alive()]
        self._turn_order = sorted(
            living, key=lambda c: (c.effective_stat("speed"), self.rng.random()), reverse=True
        )
        self._turn_index = 0
        self.log.append(f"--- Round {self.round_number} ---")

        if self._turn_order:
            self._begin_turn(self._turn_order[0])

    def _begin_turn(self, combatant: Combatant) -> None:
        # Damage-over-time ticks at the start of the affected combatant's own turn.
        for dot in list(combatant.dots):
            dealt = combatant.take_raw_hp_loss(dot.flat_amount)
            self.log.append(f"{combatant.name} takes {dealt} damage from {dot.source}.")
            dot.duration -= 1
        combatant.dots = [d for d in combatant.dots if d.duration > 0]

        if not combatant.is_alive():
            self._check_end_conditions()
            return

        effects.trigger_on_turn_start(combatant, self.log)
        combatant.is_defending = False

        for ability_id in list(combatant.cooldowns.keys()):
            if combatant.cooldowns[ability_id] > 0:
                combatant.cooldowns[ability_id] -= 1

        if combatant.stunned_turns > 0:
            combatant.stunned_turns -= 1
            self.log.append(f"{combatant.name} is stunned and can't act!")
            self._end_turn(combatant)

    def _end_turn(self, combatant: Combatant) -> None:
        for modifier in list(combatant.modifiers):
            modifier.duration -= 1
        combatant.modifiers = [m for m in combatant.modifiers if m.duration > 0]
        self._advance_turn()

    def _advance_turn(self) -> None:
        self._check_end_conditions()
        if self.is_over():
            return

        self._turn_index += 1
        if self._turn_index >= len(self._turn_order):
            self._start_round()
        else:
            self._begin_turn(self._turn_order[self._turn_index])

    def _check_end_conditions(self) -> None:
        if not self.player.is_alive():
            self.result = "lost"
            self.log.append(f"{self.player.name} has fallen...")
        elif not self.living_enemies():
            self.result = "won"
            self.log.append("Victory!")

    # ------------------------------------------------------------------
    # Player actions
    # ------------------------------------------------------------------
    def take_player_action(self, action: str, ability_id: str | None = None, target_index: int = 0) -> None:
        if self.is_over() or self.current_actor() is not self.player:
            return

        target = self._pick_enemy_target(target_index)

        if action == "attack":
            effects.resolve_basic_attack(self.player, target, self.rng, self.log)
        elif action == "ability":
            ability = self._find_active_ability(self.player, ability_id)
            if ability is None or not self.player.ability_ready(ability):
                self.log.append(f"{self.player.name} can't use that ability right now.")
            else:
                effects.resolve_active_ability(self.player, target, ability, self.rng, self.log)
        elif action == "defend":
            self.player.is_defending = True
            self.log.append(f"{self.player.name} braces for impact.")
        elif action == "flee":
            self._attempt_flee(self.player)
            if self.result == "fled":
                return
        else:
            self.log.append(f"Unknown action: {action}")

        self._end_turn(self.player)

    def _pick_enemy_target(self, target_index: int) -> Combatant:
        living = self.living_enemies()
        if not living:
            return self.enemies[0]
        return living[min(target_index, len(living) - 1)]

    def _find_active_ability(self, combatant: Combatant, ability_id: str | None):
        if ability_id is None:
            return None
        for ability in combatant.active_abilities:
            if ability["id"] == ability_id:
                return ability
        return None

    def _attempt_flee(self, combatant: Combatant) -> None:
        chance = 40 + combatant.effective_stat("speed") * 0.5 + combatant.effective_stat("luck") * 0.5
        chance = min(90, chance)
        if self.rng.uniform(0, 100) < chance:
            self.result = "fled"
            self.log.append(f"{combatant.name} flees the battle!")
        else:
            self.log.append(f"{combatant.name} fails to escape!")

    # ------------------------------------------------------------------
    # Enemy turn (simple AI: prefer an off-cooldown, affordable ability
    # half the time, otherwise basic attack; always targets the player)
    # ------------------------------------------------------------------
    def take_enemy_turn(self) -> None:
        if self.is_over():
            return

        enemy = self.current_actor()
        if enemy is self.player or not enemy.is_alive():
            self._advance_turn()
            return

        usable = [a for a in enemy.active_abilities if enemy.ability_ready(a)]
        if usable and self.rng.random() < 0.5:
            ability = self.rng.choice(usable)
            effects.resolve_active_ability(enemy, self.player, ability, self.rng, self.log)
        else:
            effects.resolve_basic_attack(enemy, self.player, self.rng, self.log)

        self._end_turn(enemy)
