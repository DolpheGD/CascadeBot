"""
Turn-based battle engine using an ATB-style (Active Time Battle) speed
gauge instead of a fixed once-per-round turn order. Every living combatant
has a `turn_gauge` (see combatant.py) that fills proportional to their
speed stat; whoever's gauge crosses TURN_THRESHOLD first gets to act, and
their gauge drops back by exactly the threshold (any overflow carries into
their next turn). This is what lets a much faster combatant act several
times before a much slower one gets even one turn.

Combat Overhaul: a full squad of up to 4 party members (built one per
PlayerCharacter -- see factory.build_party_combatants) vs 1+ enemies. Every
party member's turn can be Attack, their Character Skill (mana), Character
Ultimate (100 energy), a Weapon Skill (mana, if a weapon's equipped), or an
Artifact Skill (mana, if an artifact's equipped) -- see
bot/game/combat/skills.py and factory.py for how those are resolved onto
each Combatant. There is no fleeing and no defending.

Usage:

    battle = Battle(party_combatants, enemy_combatants)
    while not battle.is_over():
        actor = battle.current_actor()
        if actor.is_player:
            battle.take_party_action("attack")   # or "ability"/"ultimate", ability_id=...
        else:
            battle.take_enemy_turn()

    print(battle.result)  # "won" | "lost"
"""

from __future__ import annotations

import random

from bot.game.combat import effects
from bot.game.combat.combatant import Combatant

TURN_THRESHOLD = 100.0
MIN_SPEED = 0.01  # guards against a division by zero if speed is ever 0
MAX_PARTY_SIZE = 4


class Battle:
    def __init__(self, party: list[Combatant], enemies: list[Combatant], rng: random.Random | None = None):
        if not 1 <= len(party) <= MAX_PARTY_SIZE:
            raise ValueError(f"Battle supports 1-{MAX_PARTY_SIZE} party members")
        if not 1 <= len(enemies) <= 5:
            raise ValueError("Battle supports 1-5 enemies")

        self.party = party
        self.enemies = enemies
        self.rng = rng or random.Random()

        self.turn_count = 0
        self.log: list[str] = []
        self.result: str | None = None  # "won" | "lost" | None while ongoing

        # Which living enemy (by index into living_enemies()) the currently
        # acting party member is targeting. Selecting a target does not
        # consume a turn.
        self.target_index = 0

        self._current_actor: Combatant | None = None
        self._begin_next_turn()

    # ------------------------------------------------------------------
    def all_combatants(self) -> list[Combatant]:
        return self.party + self.enemies

    def living_party(self) -> list[Combatant]:
        return [c for c in self.party if c.is_alive()]

    def living_enemies(self) -> list[Combatant]:
        return [e for e in self.enemies if e.is_alive()]

    def is_over(self) -> bool:
        return self.result is not None

    def current_actor(self) -> Combatant:
        return self._current_actor

    def select_target(self, target_index: int) -> None:
        """Switch which living enemy the current party actor is aiming at.
        Free action -- does not consume a turn."""
        living = self.living_enemies()
        if not living:
            return
        self.target_index = max(0, min(target_index, len(living) - 1))

    # ------------------------------------------------------------------
    # Turn order preview -- a best-effort projection of the next `count`
    # actors, purely for UI display (see bot/utils/embedder.py). It reads
    # current speed/gauges but never mutates real combatant state, and
    # uses a stable (non-random) tie-break so re-rendering the same state
    # doesn't visually jitter between calls.
    # ------------------------------------------------------------------
    def preview_turn_order(self, count: int = 6) -> list[Combatant]:
        living = [c for c in self.all_combatants() if c.is_alive()]
        if not living:
            return []

        gauges = {id(c): c.turn_gauge for c in living}
        order: list[Combatant] = []

        for _ in range(count):
            ready = [c for c in living if gauges[id(c)] >= TURN_THRESHOLD]
            if not ready:
                deltas = []
                for c in living:
                    speed = max(c.effective_stat("speed"), MIN_SPEED)
                    deltas.append((TURN_THRESHOLD - gauges[id(c)]) / speed)
                dt = min(deltas)
                for c in living:
                    speed = max(c.effective_stat("speed"), MIN_SPEED)
                    gauges[id(c)] += speed * dt
                ready = [c for c in living if gauges[id(c)] >= TURN_THRESHOLD]

            ready.sort(key=lambda c: (-gauges[id(c)], c.name))
            actor = ready[0]
            order.append(actor)
            gauges[id(actor)] -= TURN_THRESHOLD

        return order

    # ------------------------------------------------------------------
    # Turn gauge scheduling
    # ------------------------------------------------------------------
    def _select_next_actor(self) -> Combatant | None:
        """Advances every living combatant's turn_gauge until someone
        crosses TURN_THRESHOLD, then returns them. Uses an analytic jump
        (compute exactly how much time until the soonest combatant is
        ready, advance everyone by that amount) rather than ticking one
        unit at a time, so it's exact regardless of how large the speed
        gap between combatants is."""
        living = [c for c in self.all_combatants() if c.is_alive()]
        if not living:
            return None

        while True:
            ready = [c for c in living if c.turn_gauge >= TURN_THRESHOLD]
            if ready:
                ready.sort(key=lambda c: (c.turn_gauge, self.rng.random()), reverse=True)
                return ready[0]

            deltas = []
            for c in living:
                speed = max(c.effective_stat("speed"), MIN_SPEED)
                deltas.append((TURN_THRESHOLD - c.turn_gauge) / speed)
            dt = min(deltas)

            for c in living:
                speed = max(c.effective_stat("speed"), MIN_SPEED)
                c.turn_gauge += speed * dt

    def _begin_next_turn(self) -> None:
        actor = self._select_next_actor()
        if actor is None:
            self._check_end_conditions()
            return

        self._current_actor = actor
        self.turn_count += 1
        self.log.append(f"--- Turn {self.turn_count}: {actor.name} ---")
        self._begin_turn(actor)

    def _begin_turn(self, combatant: Combatant) -> None:
        # Damage-over-time ticks at the start of the affected combatant's own turn.
        for dot in list(combatant.dots):
            dealt = combatant.take_raw_hp_loss(dot.flat_amount)
            self.log.append(f"🔥 {combatant.name} takes {dealt} damage from {dot.source}.")
            dot.duration -= 1
        combatant.dots = [d for d in combatant.dots if d.duration > 0]

        if not combatant.is_alive():
            self._check_end_conditions()
            if not self.is_over():
                self._begin_next_turn()
            return

        effects.trigger_on_turn_start(combatant, self.log)
        if not combatant.is_alive():
            self._check_end_conditions()
            if not self.is_over():
                self._begin_next_turn()
            return

        for ability_id in list(combatant.cooldowns.keys()):
            if combatant.cooldowns[ability_id] > 0:
                combatant.cooldowns[ability_id] -= 1

        if combatant.stunned_turns > 0:
            combatant.stunned_turns -= 1
            self.log.append(f"😵 {combatant.name} is stunned and can't act!")
            self._end_turn(combatant)

    def _end_turn(self, combatant: Combatant) -> None:
        for modifier in list(combatant.modifiers):
            modifier.duration -= 1
        combatant.modifiers = [m for m in combatant.modifiers if m.duration > 0]

        # Consume the turn; any overflow above the threshold carries into
        # the combatant's next cycle rather than being discarded, so a
        # very fast combatant that jumped well past 100 stays "ahead."
        combatant.turn_gauge -= TURN_THRESHOLD

        # Keep the active target pointing at a still-living enemy.
        living = self.living_enemies()
        if living:
            self.target_index = min(self.target_index, len(living) - 1)

        self._check_end_conditions()
        if self.is_over():
            return
        self._begin_next_turn()

    def _check_end_conditions(self) -> None:
        if not self.living_party():
            self.result = "lost"
            self.log.append("💀 Your party has fallen...")
        elif not self.living_enemies():
            self.result = "won"
            self.log.append("🏆 Victory!")

    # ------------------------------------------------------------------
    # Party actions -- Attack (builds energy+mana), Ability (character
    # skill, weapon skill, or artifact skill -- costs mana), or Ultimate
    # (character ultimate, costs 100 energy). No defend, no flee. Always
    # acts as whichever party member `current_actor()` currently is.
    # ------------------------------------------------------------------
    def take_party_action(self, action: str, ability_id: str | None = None, target_index: int | None = None) -> None:
        actor = self.current_actor()
        if self.is_over() or actor not in self.party:
            return

        if target_index is not None:
            self.select_target(target_index)
        target = self._pick_enemy_target(self.target_index)
        allies = [c for c in self.party if c is not actor and c.is_alive()]

        if action == "attack":
            effects.resolve_basic_attack(actor, target, self.rng, self.log)
        elif action == "ability":
            ability = self._find_active_ability(actor, ability_id)
            if ability is None or not actor.ability_ready(ability):
                self.log.append(f"{actor.name} can't use that ability right now.")
                return
            effects.resolve_active_ability(actor, target, ability, self.rng, self.log, allies=allies)
        elif action == "ultimate":
            ability = actor.ultimate_ability
            if ability is None or not actor.ability_ready(ability):
                self.log.append(f"{actor.name}'s ultimate isn't ready yet.")
                return
            effects.resolve_active_ability(actor, target, ability, self.rng, self.log, allies=allies)
        else:
            self.log.append(f"Unknown action: {action}")
            return

        self._end_turn(actor)

    def _pick_enemy_target(self, target_index: int) -> Combatant:
        living = self.living_enemies()
        if not living:
            return self.enemies[0]
        return living[min(target_index, len(living) - 1)]

    def _pick_party_target(self) -> Combatant:
        """Default enemy AI target -- a random living party member."""
        living = self.living_party()
        if not living:
            return self.party[0]
        return self.rng.choice(living)

    def _find_active_ability(self, combatant: Combatant, ability_id: str | None):
        if ability_id is None:
            return None
        for ability in combatant.active_abilities:
            if ability["id"] == ability_id:
                return ability
        return None

    # ------------------------------------------------------------------
    # Enemy turn: prefers the ultimate when ready, then an off-cooldown
    # affordable skill about half the time, otherwise a basic attack.
    # Targets a random living party member.
    # ------------------------------------------------------------------
    def take_enemy_turn(self) -> None:
        if self.is_over():
            return

        enemy = self.current_actor()
        if enemy not in self.enemies or not enemy.is_alive():
            return

        target = self._pick_party_target()
        allies = [e for e in self.enemies if e is not enemy and e.is_alive()]

        if enemy.ultimate_ready() and self.rng.random() < 0.5:
            effects.resolve_active_ability(enemy, target, enemy.ultimate_ability, self.rng, self.log, allies=allies)
            self._end_turn(enemy)
            return

        usable = [a for a in enemy.active_abilities if enemy.ability_ready(a)]
        if usable and self.rng.random() < 0.5:
            ability = self.rng.choice(usable)
            effects.resolve_active_ability(enemy, target, ability, self.rng, self.log, allies=allies)
        else:
            effects.resolve_basic_attack(enemy, target, self.rng, self.log)

        self._end_turn(enemy)
