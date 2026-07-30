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

extra_turn_on_kill (a passive checked here, not in effects.py -- see
_maybe_grant_extra_turn): if an action drops the opposing side's living
count, the killer is re-queued at the FRONT of cycle_order for an
immediate bonus turn, ahead of whoever was up next, instead of just
handing play onward. Checked by diffing the opposing side's living count
before/after the action rather than a return value from effects.py, so it
fires correctly regardless of which effect kind (single-target, AOE,
multi-hit) landed the killing blow, and at most once per action even if
an AOE finishes off several targets at once.

Enemy intent telegraphing (see peek_upcoming_enemy_intents /
Combatant.pending_intent): an enemy's target + move for its turn is
decided ahead of the turn actually happening, and then REUSED (not
re-rolled) once that turn arrives, so whatever the UI showed the player
beforehand is guaranteed to be exactly what happens -- see
bot/utils/embedder.py's _enemy_intent_lines for where that gets rendered.

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

    def preview_turn_order_with_cycle_offsets(self, count: int = 6) -> list[tuple[Combatant, int]]:
        """Same projection as preview_turn_order, but each actor is paired
        with how many cycles from NOW it belongs to: 0 for the rest of the
        current (already in-progress) cycle, 1 for the next full cycle
        projected after that, 2 for the one after that, and so on. Add
        this to battle.cycle_number to get the real cycle number an entry
        belongs to -- see embedder._turn_order_line, which uses this to
        show WHERE one cycle's turns end and the next begins, instead of
        a flat, undifferentiated list of names that reads like one long
        turn order rather than the cycle system it actually is."""
        preview: list[tuple[Combatant, int]] = [
            (c, 0) for c in self.cycle_order if c.is_alive()
        ]

        guard = 0
        offset = 0
        while len(preview) < count and guard < 25:
            living = [c for c in self.all_combatants() if c.is_alive()]
            if not living:
                break
            offset += 1
            preview.extend((c, offset) for c in self._build_cycle_order(living, rng=None))
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
        self.log.append(f"--- Cycle {self.cycle_number}, Turn {self.turn_count}: {actor.name} ---")
        self._begin_turn(actor)

    def _begin_turn(self, combatant: Combatant) -> None:
        # Damage-over-time ticks at the start of the affected combatant's own turn.
        for dot in list(combatant.dots):
            dealt = combatant.take_raw_hp_loss(dot.flat_amount)
            self.log.append(f"🔥 {combatant.name} takes {dealt} damage from {dot.source}.")
            dot.duration -= 1
        combatant.dots = [d for d in combatant.dots if d.duration > 0]

        # Regen (heal-over-time) ticks the same way, on the healed
        # combatant's own turn. This is for ABILITY-granted heals only now
        # (e.g. team_regen_over_time) -- enemies no longer get a free
        # innate regen; see the attack ramp-up block just below instead.
        for regen in list(combatant.heals):
            healed = combatant.heal(combatant.max_hp * regen.percent_max_hp / 100)
            if healed:
                self.log.append(f"🌿 {combatant.name} regenerates {healed} HP from {regen.source}.")
            regen.duration -= 1
        combatant.heals = [h for h in combatant.heals if h.duration > 0]

        # Anti-stalemate attack ramp-up (replaces the old innate enemy HP
        # regen) -- ticks on this combatant's own turn, same cadence the
        # regen used to. Stacks permanently and never resets; see
        # Combatant.ramp_percent_per_turn / effective_stat and
        # factory.ATTACK_RAMP_PERCENT_PER_TURN_BY_ROLE. Only logged every
        # few stacks so a long fight's log doesn't get spammed with a
        # barely-perceptible bonus every single turn.
        if combatant.ramp_percent_per_turn:
            combatant.ramp_stacks += 1
            if combatant.ramp_stacks % 5 == 0:
                total_bonus = round(combatant.ramp_percent_per_turn * combatant.ramp_stacks, 1)
                self.log.append(
                    f"😤 {combatant.name} grows increasingly aggressive! (+{total_bonus}% ATK/ELE)"
                )

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

        # Guard only ever covers the gap between this combatant's turns --
        # exactly the window a telegraphed enemy move lands in -- so it
        # expires the moment they act again, whatever they do next.
        combatant.guarding = False

        # Break: a combatant whose poise was shattered loses its turns for
        # the duration, then recovers with poise refilled. Ticked here,
        # before the stun check, so the two never double-skip a turn.
        if combatant.is_broken():
            # Only consume a break turn if the other side has had a chance
            # to act on it since the break (see break_tick_armed). An
            # unarmed tick still costs this combatant its turn -- it just
            # doesn't shorten the break.
            if not combatant.break_tick_armed:
                self.log.append(f"💫 {combatant.name} is broken and can't act!")
                self._end_turn(combatant)
                return

            combatant.break_tick_armed = False
            combatant.break_turns -= 1
            if combatant.break_turns <= 0:
                # Last skipped turn: poise refills now, so the damage
                # amplification window closes with it and the combatant
                # acts again on its next turn.
                combatant.recover_from_break()
                self.log.append(
                    f"💫 {combatant.name} is broken and can't act -- it recovers its footing next turn."
                )
            else:
                self.log.append(f"💫 {combatant.name} is broken and can't act!")
            self._end_turn(combatant)
            return

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
    # skill, weapon skill, or artifact skill -- costs mana), Ultimate
    # (character ultimate, costs 50 energy), or Guard (halves incoming
    # damage until this character's next turn). No fleeing. Always acts as
    # whichever party member `current_actor()` currently is.
    #
    # Guard is the player's half of the intent-telegraphing mechanic: the
    # UI shows which enemy is about to do what to whom, and Guard is the
    # answer when breaking the enemy's poise isn't on the table (see
    # effects.py's Poise/Break/Guard tuning block). It costs the turn's
    # damage, so the interesting question every turn is whether the
    # incoming hit is worth spending a turn to blunt.
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
        living_opponents_before = len(opponents)

        if action == "guard":
            effects.resolve_guard(actor, self.log)
        elif action == "attack":
            defender_allies = [o for o in opponents if o is not target and o.is_alive()]
            effects.resolve_basic_attack(actor, target, self.rng, self.log, defender_allies=defender_allies)
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

        # Extra turn on kill (see status.Vulnerability's sibling mechanic,
        # the extra_turn_on_kill passive) -- if this action dropped the
        # opposing side's living count, re-queue the actor at the front of
        # the current cycle for an immediate bonus turn instead of handing
        # play to whoever's next. Checked by count rather than a return
        # value from effects.py, so it works no matter which effect kind
        # (single-target, AOE, multi-hit) landed the killing blow, and
        # fires at most once per action even if several targets died at
        # once (e.g. a wide AOE finishing multiple weakened enemies).
        self._maybe_grant_extra_turn(actor, living_opponents_before)

        # A party turn has now happened, so every broken enemy's next
        # skipped turn is allowed to count toward ending its break -- see
        # Combatant.break_tick_armed.
        for enemy in self.enemies:
            if enemy.is_broken():
                enemy.break_tick_armed = True

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
    # Enemy turn / intent telegraphing: an enemy's action for its turn is
    # DECIDED (target + ability, no execution) as soon as it's knowable,
    # and REUSED at execution time rather than re-rolled -- so whatever
    # peek_upcoming_enemy_intents() showed the player is guaranteed to be
    # exactly what happens. See Combatant.pending_intent.
    # ------------------------------------------------------------------
    def _decide_enemy_intent(self, enemy: Combatant) -> dict:
        """Pure decision, no execution: prefers the ultimate when ready
        (30% of the time), then an off-cooldown affordable ability about
        95% of the time, otherwise a basic attack. Targets a random living
        party member. Returns {"ability": dict|None, "target": Combatant}
        -- None ability means a basic attack."""
        target = self._pick_party_target()
        if enemy.ultimate_ready() and self.rng.random() < 0.3:
            return {"ability": enemy.ultimate_ability, "target": target}
        usable = [a for a in enemy.active_abilities if enemy.ability_ready(a)]
        if usable and self.rng.random() < 0.95:
            return {"ability": self.rng.choice(usable), "target": target}
        return {"ability": None, "target": target}

    def peek_upcoming_enemy_intents(self) -> list[tuple[Combatant, dict | None]]:
        """(enemy, intent) for every enemy queued to act before the NEXT
        party member's turn -- exactly the batch that will resolve the
        instant the current party member's action is submitted (see
        _advance_to_player_or_end in bot/cogs/dungeon.py, which burns
        through consecutive enemy turns with no rendering pause in
        between -- this is what lets the player see them coming first).

        Also covers the one case where the very NEXT actor is itself an
        enemy that hasn't acted yet: right when a battle starts, if an
        enemy out-speeds the whole party, current_actor() is already that
        enemy (popped off cycle_order into _current_actor) before
        anything has happened -- see _combat_entry_view_and_embed's
        pre-battle preview, which renders before any advance-to-player-turn
        loop runs. Without checking current_actor() too, that enemy's
        opening move wouldn't show up here at all.

        intent is None for a currently-stunned enemy, since _begin_turn
        skips their action entirely when their turn arrives -- showing a
        decided move for them would be misleading. For every other queued
        enemy, this DECIDES AND LOCKS IN (via pending_intent) a fresh
        intent if one isn't already stored, rather than just previewing
        one -- take_enemy_turn reuses whatever's already been decided
        instead of re-rolling, so this is intentionally not side-effect
        free the way preview_turn_order is."""
        candidates: list[Combatant] = []
        if self._current_actor is not None and self._current_actor in self.enemies and self._current_actor.is_alive():
            candidates.append(self._current_actor)
        candidates.extend(self.cycle_order)

        result: list[tuple[Combatant, dict | None]] = []
        for c in candidates:
            if not c.is_alive():
                continue
            if c in self.party:
                break
            if c.stunned_turns > 0:
                result.append((c, None))
                continue
            if c.pending_intent is None:
                c.pending_intent = self._decide_enemy_intent(c)
            result.append((c, c.pending_intent))
        return result

    def take_enemy_turn(self) -> None:
        if self.is_over():
            return

        enemy = self.current_actor()
        if enemy not in self.enemies or not enemy.is_alive():
            return

        intent = enemy.pending_intent or self._decide_enemy_intent(enemy)
        enemy.pending_intent = None

        target = intent["target"]
        if not target.is_alive():
            # Died since the intent was decided/shown (e.g. a teammate's
            # extra_turn_on_kill finished them off first) -- re-pick.
            target = self._pick_party_target()
        ability = intent["ability"]

        allies = [e for e in self.enemies if e is not enemy and e.is_alive()]
        opponents = self.living_party()
        living_opponents_before = len(opponents)

        if ability is not None and enemy.ability_ready(ability):
            effects.resolve_active_ability(enemy, target, ability, self.rng, self.log, allies=allies, opponents=opponents)
        else:
            # Basic attack -- either that was the decided intent, or the
            # decided ability/ultimate is no longer usable (resource spent
            # or cooldown started some other way since it was decided).
            defender_allies = [o for o in opponents if o is not target and o.is_alive()]
            effects.resolve_basic_attack(enemy, target, self.rng, self.log, defender_allies=defender_allies)

        self._maybe_grant_extra_turn(enemy, living_opponents_before)
        self._end_turn(enemy)

    def _maybe_grant_extra_turn(self, actor: Combatant, living_opponents_before: int) -> None:
        """Shared by take_party_action/take_enemy_turn -- see
        extra_turn_on_kill's docstring note in take_party_action."""
        opponents_now = self.living_enemies() if actor in self.party else self.living_party()
        if len(opponents_now) < living_opponents_before and actor.is_alive() \
                and actor.find_passive("extra_turn_on_kill"):
            self.log.append(f"⚡ {actor.name} doesn't stop moving -- another turn, right now!")
            self.cycle_order.insert(0, actor)
