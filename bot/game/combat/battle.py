"""
Turn-based battle engine using a CYCLE turn order instead of a pure ATB
speed race. Every living combatant acts exactly once per cycle -- Speed
only ever decides the ORDER combatants act in (fastest first), never
whether a slower combatant gets to act at all. This fixes the old ATB
gauge's runaway-speed problem, where either the party or the enemies
having a much higher Speed stat than the other side could let them act
several times before the other side got even one turn.

A combatant can be configured to act more than once per cycle (see
Combatant.actions_per_cycle()) -- e.g. an elite or boss enemy template with
"actions_per_cycle": 2 goes twice every cycle, or a "bonus_actions_per_cycle"
passive (armor/enemy passive today; wireable onto a weapon/artifact passive
too) grants extra actions. This is built as waves: wave 1 is everyone (by
Speed, fastest first), wave 2 is only combatants with 2+ actions_per_cycle
(again by Speed), wave 3 only those with 3+, and so on -- so a
multi-action combatant's extra turns land spread through the cycle rather
than firing back-to-back, while everyone still gets their one guaranteed
turn in wave 1 regardless of Speed.

Combat Overhaul: a full squad of up to 4 party members (built one per
PlayerCharacter -- see factory.build_party_combatants) vs 1+ enemies. Every
party member's turn can be Attack, their Character Skill (mana), Character
Ultimate (50 energy), a Weapon Skill (mana, if a weapon's equipped), or an
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

        # Cycle turn order state. `cycle_order` is the remaining queue of
        # actors for the CURRENT cycle (already decided -- see
        # _build_cycle_order); it's consumed from the front as turns
        # happen and rebuilt from scratch (bumping cycle_number) whenever
        # it runs dry. A combatant that dies before its queued slot comes
        # up simply has that slot skipped.
        self.cycle_number = 0
        self.cycle_order: list[Combatant] = []

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
    # actors, purely for UI display (see bot/utils/embedder.py). Shows
    # whatever's left of the real, already-decided queue for the current
    # cycle, then projects further cycles from who's currently alive.
    # Never mutates real combatant state, and (by building those future
    # cycles with rng=None) uses a stable, non-random tie-break so
    # re-rendering the same state doesn't visually jitter between calls.
    # ------------------------------------------------------------------
    def preview_turn_order(self, count: int = 6) -> list[Combatant]:
        preview = [c for c in self.cycle_order if c.is_alive()]

        guard = 0
        while len(preview) < count and guard < 25:
            living = [c for c in self.all_combatants() if c.is_alive()]
            if not living:
                break
            preview.extend(self._build_cycle_order(living, rng=None))
            guard += 1

        return preview[:count]

    # ------------------------------------------------------------------
    # Cycle scheduling
    # ------------------------------------------------------------------
    def _build_cycle_order(
        self, living: list[Combatant], rng: random.Random | None
    ) -> list[Combatant]:
        """Builds one cycle's worth of turns from `living`: wave 1 is
        every living combatant once, fastest Speed first; wave 2 is only
        those with actions_per_cycle() >= 2 (again fastest first); wave 3
        only those >= 3; and so on. Everyone always gets their wave-1
        turn regardless of Speed -- Speed only ever moves a combatant
        earlier or later within a wave, and multi-action combatants'
        extra turns land in later waves instead of firing back-to-back.

        `rng`, when given, breaks Speed ties randomly (used for the real
        battle); when omitted, ties are broken by name instead, so the UI
        preview is side-effect-free and stable across re-renders."""
        if not living:
            return []

        max_actions = max(c.actions_per_cycle() for c in living)
        order: list[Combatant] = []
        for wave in range(max_actions):
            eligible = [c for c in living if c.actions_per_cycle() > wave]
            if rng is not None:
                eligible.sort(key=lambda c: (c.effective_stat("speed"), rng.random()), reverse=True)
            else:
                eligible.sort(key=lambda c: (-c.effective_stat("speed"), c.name))
            order.extend(eligible)
        return order

    def _pop_next_actor(self) -> Combatant | None:
        """Pops (and returns) the next actor from the current cycle's
        queue, rebuilding a fresh cycle whenever the queue runs dry.
        Skips any queued combatant that's since died -- their slot for
        this cycle just doesn't happen."""
        while True:
            if not self.cycle_order:
                living = [c for c in self.all_combatants() if c.is_alive()]
                if not living:
                    return None
                self.cycle_order = self._build_cycle_order(living, rng=self.rng)
                self.cycle_number += 1
                self.log.append(f"🔄 Cycle {self.cycle_number} begins.")

            actor = self.cycle_order.pop(0)
            if actor.is_alive():
                return actor

    def _begin_next_turn(self) -> None:
        actor = self._pop_next_actor()
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

        # Regen (heal-over-time) ticks the same way, on the healed
        # combatant's own turn.
        for regen in list(combatant.heals):
            healed = combatant.heal(combatant.max_hp * regen.percent_max_hp / 100)
            if healed:
                self.log.append(f"🌿 {combatant.name} regenerates {healed} HP from {regen.source}.")
            regen.duration -= 1
        combatant.heals = [h for h in combatant.heals if h.duration > 0]

        if not combatant.is_alive():
            self._check_end_conditions()
            if not self.is_over():
                self._begin_next_turn()
            return

        own_side = self.party if combatant.is_player else self.enemies
        allies = [c for c in own_side if c is not combatant and c.is_alive()]
        effects.trigger_on_turn_start(combatant, self.log, allies=allies)
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
    # (character ultimate, costs 50 energy). No defend, no flee. Always
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
        opponents = self.living_enemies()

        if action == "attack":
            effects.resolve_basic_attack(actor, target, self.rng, self.log)
        elif action == "ability":
            ability = self._find_active_ability(actor, ability_id)
            if ability is None or not actor.ability_ready(ability):
                self.log.append(f"{actor.name} can't use that ability right now.")
                return
            effects.resolve_active_ability(actor, target, ability, self.rng, self.log, allies=allies, opponents=opponents)
        elif action == "ultimate":
            ability = actor.ultimate_ability
            if ability is None or not actor.ability_ready(ability):
                self.log.append(f"{actor.name}'s ultimate isn't ready yet.")
                return
            effects.resolve_active_ability(actor, target, ability, self.rng, self.log, allies=allies, opponents=opponents)
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
        opponents = self.living_party()

        if enemy.ultimate_ready() and self.rng.random() < 0.5:
            effects.resolve_active_ability(enemy, target, enemy.ultimate_ability, self.rng, self.log, allies=allies, opponents=opponents)
            self._end_turn(enemy)
            return

        usable = [a for a in enemy.active_abilities if enemy.ability_ready(a)]
        if usable and self.rng.random() < 0.5:
            ability = self.rng.choice(usable)
            effects.resolve_active_ability(enemy, target, ability, self.rng, self.log, allies=allies, opponents=opponents)
        else:
            effects.resolve_basic_attack(enemy, target, self.rng, self.log)

        self._end_turn(enemy)
