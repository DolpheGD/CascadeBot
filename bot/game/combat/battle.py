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
bot/utils/embedder/combat.py's _intent_lines for where that gets rendered.

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

# ----------------------------------------------------------------------
# Enemy energy economy (bug fix: enemies never used their ultimates).
#
# Enemies are built with a real ultimate_ability and a 50-energy gate
# (see factory.build_enemy_combatant), but energy was only ever granted
# by Combatant.gain_energy_and_mana, which only fires on a BASIC ATTACK
# (effects.resolve_basic_attack). Enemy AI picks an off-cooldown ability
# ~95% of the time and enemies have effectively infinite mana, so they
# basic-attacked roughly one turn in twenty -- at ~5 energy a pop that's
# ~200 turns to a single ultimate. In practice no enemy ultimate had
# ever fired in a real fight.
#
# Enemies now build energy on EVERY action they take instead, at a flat
# rate per action. This is deliberately NOT the player's rule (players
# still only charge on Attack/Guard -- that trade-off is the player's
# resource decision and is meant to stay a decision); enemies have no
# such decision to make, so tying their charge to a specific action only
# ever produced the dead mechanic above.
#
# At 10 per action against a 50 cap, a normal enemy ults about every 5th
# turn and a boss with actions_per_cycle=2 about every 2.5 cycles --
# frequent enough to be a real, recurring threat the player has to read
# and answer (Guard or break the wind-up), rare enough to stay a moment.
# ----------------------------------------------------------------------
ENEMY_ENERGY_PER_ACTION = 10

# How likely an enemy is to fire its ultimate on a turn where it's fully
# charged. Was 0.3, which -- on top of the energy bug above -- meant even
# a hypothetically-charged enemy usually sat on it. A charged ultimate is
# the single most interesting thing an enemy can telegraph, so it should
# essentially always be the move; the residual chance of doing something
# else keeps it from being perfectly clockwork.
ENEMY_ULTIMATE_USE_CHANCE = 0.85

# ----------------------------------------------------------------------
# CYCLE LIMIT -- the honest replacement for battle fatigue.
#
# Two sides that can't finish each other used to be handled by silently
# weakening healing until someone died. That worked, but the player
# experienced it as their heals mysteriously failing. This is the same
# guarantee stated out loud: a battle has a length, and when it runs out
# the squad withdraws.
#
# It is also a genuine robustness fix, not only a balance one. A party
# of four supports with no damage output CANNOT win and could not lose
# either -- measured at 80+ cycles and still going, which in real play is
# a player pressing buttons forever with no way out but Retreat.
#
# 40 is deliberately far above any real fight: an unsupported 4-DPS squad
# finishes a hard boss in ~16 cycles and a support-heavy one in ~13, so
# nothing that is actually progressing ever meets this. The UI starts
# showing the cycle count at CYCLE_WARNING_THRESHOLD so it can never
# arrive as a surprise.
# ----------------------------------------------------------------------
MAX_BATTLE_CYCLES = 40
CYCLE_WARNING_THRESHOLD = 25


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

        # Which party member (by index into `party`, so it's stable even
        # as members die) the single-ally SUPPORT kinds will land on --
        # heals, cleanses, single-target buffs and resource restores. See
        # effects._pick_ally.
        #
        # None means "no explicit choice", which falls back to each
        # effect's own "whoever needs it most" heuristic -- so this is
        # purely additive: an untouched battle behaves exactly as it did
        # before, and enemies never set it at all.
        #
        # Reset to None at the end of every party turn (see _end_turn) on
        # purpose. A stale pick is worse than no pick: the player chose
        # "heal Josh" three turns ago for reasons that no longer hold, and
        # silently honouring it later is precisely the kind of invisible
        # state that makes a support turn feel like it did the wrong
        # thing.
        self.ally_target_index: int | None = None

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

    def select_ally_target(self, party_index: int | None) -> None:
        """Choose which squad member the next single-ally support ability
        will land on (see ally_target_index). Free action -- like enemy
        targeting, picking a recipient does not consume a turn, so a
        player can line the choice up and still decide what to cast.

        Indexes into `self.party` rather than a filtered living list, so
        the meaning of a stored index can't shift when someone dies.
        Passing None clears the choice back to automatic."""
        if party_index is None:
            self.ally_target_index = None
            return
        if 0 <= party_index < len(self.party):
            self.ally_target_index = party_index

    def current_ally_target(self) -> Combatant | None:
        """The chosen recipient, or None for automatic. Returns None for a
        dead pick too -- effects._pick_ally would fall back anyway, and
        this keeps the UI from rendering a corpse as the current target."""
        if self.ally_target_index is None:
            return None
        target = self.party[self.ally_target_index]
        return target if target.is_alive() else None

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
        # Damage-over-time ticks at the start of the affected combatant's
        # own turn, scaled by any DoT-amplification marks on it (see
        # effects.DOT_VULNERABILITY_STAT -- the target-side counterpart of
        # the attacker-side `dot_amplifier` passive, and part of what
        # replaced the removed energy-drain mechanic). Applied HERE at
        # tick time rather than frozen into flat_amount at application
        # time, deliberately: that's what lets a mark applied AFTER a burn
        # already landed still amplify it, which is the whole point of
        # having a separate setup piece.
        dot_amplify = 1 + combatant.total_vulnerability_percent(effects.DOT_VULNERABILITY_STAT) / 100
        for dot in list(combatant.dots):
            dealt = combatant.take_raw_hp_loss(dot.flat_amount * dot_amplify)
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

        # Taunt ticks at the START of the taunter's turn, NOT the end.
        # Ending it would decrement on the very turn the taunt was cast,
        # so a "2 turn" taunt only ever covered ONE round of enemy turns
        # and the ability description was off by one. Ticking here means
        # the count is spent on rounds the taunt was actually up for.
        if combatant.taunt_turns > 0:
            combatant.taunt_turns -= 1
            if combatant.taunt_turns == 0:
                self.log.append(f"🎯 {combatant.name} is no longer drawing attacks.")

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


        # An explicit ally pick lasts exactly the turn it was made for --
        # see ally_target_index. Carrying it into the NEXT character's
        # turn would silently apply one character's decision to another's
        # ability, which is the sort of thing a player only notices after
        # it has already healed the wrong person.
        if combatant in self.party:
            self.ally_target_index = None

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
        elif self.cycle_number > MAX_BATTLE_CYCLES:
            self.result = "lost"
            self.log.append(
                f"⏳ {MAX_BATTLE_CYCLES} cycles gone and neither side has broken -- "
                "your squad is spent and pulls back."
            )

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
    def take_party_action(self, action: str, ability_id: str | None = None,
                          target_index: int | None = None,
                          ally_target_index: int | None = None) -> None:
        actor = self.current_actor()
        if self.is_over() or actor not in self.party:
            return

        if target_index is not None:
            self.select_target(target_index)
        if ally_target_index is not None:
            self.select_ally_target(ally_target_index)
        target = self._pick_enemy_target(self.target_index)
        chosen_ally = self.current_ally_target()
        allies = [c for c in self.party if c is not actor and c.is_alive()]
        opponents = self.living_enemies()
        living_opponents_before = len(opponents)

        if action == "guard":
            effects.resolve_guard(actor, self.log)
        elif action == "attack":
            defender_allies = [o for o in opponents if o is not target and o.is_alive()]
            effects.resolve_basic_attack(actor, target, self.rng, self.log, defender_allies=defender_allies, attacker_allies=allies)
        elif action == "ability":
            ability = self._find_active_ability(actor, ability_id)
            if ability is None or not actor.ability_ready(ability):
                self.log.append(f"{actor.name} can't use that ability right now.")
                return
            effects.resolve_active_ability(actor, target, ability, self.rng, self.log, allies=allies, opponents=opponents, chosen_ally=chosen_ally)
        elif action == "ultimate":
            ability = actor.ultimate_ability
            if ability is None or not actor.ability_ready(ability):
                self.log.append(f"{actor.name}'s ultimate isn't ready yet.")
                return
            effects.resolve_active_ability(actor, target, ability, self.rng, self.log, allies=allies, opponents=opponents, chosen_ally=chosen_ally)
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

    def taunting_enemy(self) -> Combatant | None:
        """The living enemy currently forcing the party's single-target
        attacks onto it, if any (see Combatant.taunt_turns). With several
        taunting at once the FIRST is used -- deterministic rather than
        random, because the UI has to show the player which enemy their
        attack is locked to before they commit, and a re-rolled answer
        between render and execution would make that display a lie."""
        return next((e for e in self.living_enemies() if e.is_taunting()), None)

    def taunting_ally(self) -> Combatant | None:
        """The living party member currently drawing enemy attacks."""
        return next((p for p in self.living_party() if p.is_taunting()), None)

    def _pick_enemy_target(self, target_index: int) -> Combatant:
        living = self.living_enemies()
        if not living:
            return self.enemies[0]
        # A taunting enemy overrides the player's chosen target. The UI
        # disables target selection and says why while this holds, so the
        # override is never a silent surprise.
        taunter = self.taunting_enemy()
        if taunter is not None:
            return taunter
        return living[min(target_index, len(living) - 1)]

    def _pick_party_target(self) -> Combatant:
        """Enemy AI target: the taunting party member if one is drawing
        fire, otherwise a random living party member."""
        living = self.living_party()
        if not living:
            return self.party[0]
        taunter = self.taunting_ally()
        if taunter is not None:
            return taunter
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
        """Pure decision, no execution: prefers the ultimate when charged
        (ENEMY_ULTIMATE_USE_CHANCE), then an off-cooldown affordable
        ability about 95% of the time, otherwise a basic attack. Targets a
        random living party member. Returns {"ability": dict|None,
        "target": Combatant} -- None ability means a basic attack."""
        target = self._pick_party_target()
        if enemy.ultimate_ready() and self.rng.random() < ENEMY_ULTIMATE_USE_CHANCE:
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
        return [
            (row["enemy"], row["intent"])
            for row in self.peek_enemy_intent_schedule()
            if row["imminent"] and row["slot"] == 0
        ]

    def _projected_intent(self, enemy: Combatant, sim: dict) -> dict:
        """Decide what `enemy` does on a FUTURE slot, against simulated
        resource state rather than its live state.

        `sim` carries the enemy's projected cooldowns and energy after the
        moves already predicted for it earlier in this cycle. Without
        this, predicting a multi-action enemy's second slot would just
        re-run the same decision against its CURRENT state and confidently
        show an ability it will actually have on cooldown by then -- which
        is worse than showing nothing.

        Mirrors _decide_enemy_intent's preference order exactly; the only
        difference is where it reads readiness from."""
        def ready(ability: dict) -> bool:
            if sim["cooldowns"].get(ability["id"], 0) > 0:
                return False
            if ability["resource_type"] == "energy":
                return sim["energy"] >= ability["resource_cost"]
            return True  # enemies are never mana-constrained (see factory)

        target = self._pick_party_target()
        ult = enemy.ultimate_ability
        if ult is not None and ready(ult) and self.rng.random() < ENEMY_ULTIMATE_USE_CHANCE:
            return {"ability": ult, "target": target}
        usable = [a for a in enemy.active_abilities if ready(a)]
        if usable and self.rng.random() < 0.95:
            return {"ability": self.rng.choice(usable), "target": target}
        return {"ability": None, "target": target}

    def _sim_for(self, enemy: Combatant, sims: dict) -> dict:
        """Projected cooldown/energy state for `enemy`, built once per
        peek: its LIVE state, advanced through every move already sitting
        in its queue. So a slot decided now correctly accounts for what
        its own earlier slots will have spent by the time it arrives --
        without which a two-action boss would be shown using the same
        cooldown-bound ability twice."""
        sim = sims.get(id(enemy))
        if sim is not None:
            return sim
        sim = {
            "cooldowns": dict(enemy.cooldowns),
            "energy": enemy.energy,
            "max_energy": enemy.max_energy,
        }
        for queued in enemy.pending_intents:
            self._advance_sim(sim, queued)
        sims[id(enemy)] = sim
        return sim

    @staticmethod
    def _advance_sim(sim: dict, intent: dict) -> None:
        """Apply one predicted action to the simulated state: tick
        cooldowns down a turn, charge the action's energy, then spend
        whatever the chosen move costs."""
        for key in list(sim["cooldowns"]):
            if sim["cooldowns"][key] > 0:
                sim["cooldowns"][key] -= 1
        sim["energy"] = min(sim["max_energy"], sim["energy"] + ENEMY_ENERGY_PER_ACTION)
        ability = intent.get("ability")
        if ability is None:
            return
        if ability["resource_type"] == "energy":
            sim["energy"] -= ability["resource_cost"]
        sim["cooldowns"][ability["id"]] = ability.get("cooldown", 0)

    # Most rows the Incoming panel will ever show. A fight can field five
    # enemies plus escorts, and one row each was pushing the panel past
    # the point where it can be read at a glance on a phone -- which
    # defeats the purpose of a telegraph. Anything beyond this is
    # summarised as a count instead.
    MAX_INTENT_ROWS = 5

    def peek_enemy_intent_schedule(self, max_entries: int = MAX_INTENT_ROWS) -> list[dict]:
        """ONE ROW PER LIVING ENEMY: what that enemy does on its next turn.

        Returns a list of dicts, in the order the enemies will act:
            {"enemy", "intent", "extra_actions", "imminent", "locked"}
          * `intent`        -- the move, pinned and binding. None if the
            enemy is stunned or broken and will lose the turn.
          * `extra_actions` -- how many FURTHER actions this enemy takes
            back-to-back before any party member moves, for
            actions_per_cycle >= 2 enemies. 0 for everyone else.
          * `imminent`      -- resolves the moment you submit this turn.

        WHY PER-ENEMY RATHER THAN PER-CYCLE. This used to enumerate every
        enemy action queued for the rest of the cycle, then project into
        the next one, and group the result under "later this cycle" /
        "next cycle" headers. It was accurate and it was unreadable: a
        four-enemy fight produced eight or more rows, the same enemy
        appeared several times, and the player had to reconstruct "what
        is about to hit me" from a schedule.

        The question the panel exists to answer is "what does each enemy
        do next", and that has exactly one answer per enemy. So each
        enemy appears once, showing its next move; when it acts, the row
        advances to its following move. Cycle boundaries stop being
        something the player has to think about at all -- which is right,
        because they were never the thing being decided.

        Intents are still DECIDED ONCE AND PINNED (Combatant.pending_intents),
        so a telegraphed move cannot change between renders. The only
        things that alter one are breaking the enemy, which cancels it,
        and killing it -- both of which the player did deliberately."""
        # Walk the upcoming turn order, but record only the FIRST
        # appearance of each enemy. Future cycles are projected the same
        # deterministic way preview_turn_order does it, so an enemy that
        # has already acted this cycle still shows its next move instead
        # of vanishing from the panel until the cycle turns over.
        upcoming: list[Combatant] = []
        if self._current_actor is not None and self._current_actor in self.enemies \
                and self._current_actor.is_alive():
            upcoming.append(self._current_actor)
        upcoming.extend(self.cycle_order)

        living_enemies = [e for e in self.enemies if e.is_alive()]
        guard = 0
        while guard < 6 and not all(any(e is c for c in upcoming) for e in living_enemies):
            living = [c for c in self.all_combatants() if c.is_alive()]
            if not living:
                break
            upcoming.extend(self._build_cycle_order(living, rng=None))
            guard += 1

        result: list[dict] = []
        sims: dict[int, dict] = {}
        seen: set[int] = set()
        imminent = True
        party_seen = False

        for index, actor in enumerate(upcoming):
            if len(result) >= max_entries:
                break
            if not actor.is_alive():
                continue
            if actor in self.party:
                party_seen = True
                imminent = False
                continue
            if id(actor) in seen:
                continue
            seen.add(id(actor))

            # Consecutive actions: how many more times this same enemy
            # acts before ANY party member does. That's the one case
            # where showing more than one move per enemy is worth the
            # row, because they all land without a chance to respond.
            extra = 0
            for follower in upcoming[index + 1:]:
                if follower in self.party:
                    break
                if follower is actor:
                    extra += 1
            total_actions = 1 + extra

            if actor.stunned_turns > 0 or actor.is_broken():
                result.append({"enemy": actor, "intent": None, "extra_actions": 0,
                               "imminent": imminent, "locked": False})
                continue

            # Pin every action we're about to show, so each one is
            # binding rather than a guess that re-rolls next render.
            while len(actor.pending_intents) < total_actions:
                sim = self._sim_for(actor, sims)
                actor.pending_intents.append(self._projected_intent(actor, sim))
                self._advance_sim(sim, actor.pending_intents[-1])

            result.append({
                "enemy": actor,
                "intent": actor.pending_intents[0],
                "extra_actions": extra,
                "imminent": imminent,
                "locked": True,
            })

        return result

    def hidden_intent_count(self, shown: list[dict]) -> int:
        """How many living enemies didn't fit in the panel. Reported as a
        count rather than dropped silently -- "and 3 more" is honest;
        a panel that just stops is not."""
        return max(0, len([e for e in self.enemies if e.is_alive()]) - len(shown))

    def take_enemy_turn(self) -> None:
        if self.is_over():
            return

        enemy = self.current_actor()
        if enemy not in self.enemies or not enemy.is_alive():
            return

        # Pop the front of the queue -- the move the UI already showed.
        # Falls back to deciding fresh only when nothing was queued (an
        # enemy acting before anything rendered).
        if enemy.pending_intents:
            intent = enemy.pending_intents.pop(0)
        else:
            intent = self._decide_enemy_intent(enemy)

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
            # decided ability is no longer usable by the time its turn
            # arrived (a resource or cooldown moved under it).
            #
            # Falling back to a plain attack is the DELIBERATE behaviour
            # here rather than an error path: an enemy that can't afford
            # its planned move should still act, not forfeit its turn.
            # Logged in-fiction rather than as a warning, because from
            # the player's side this is just a thing that happened --
            # often something they caused.
            if ability is not None:
                self.log.append(
                    f"{enemy.name} can't muster {ability['name']} and lashes out instead."
                )
            defender_allies = [o for o in opponents if o is not target and o.is_alive()]
            effects.resolve_basic_attack(enemy, target, self.rng, self.log, defender_allies=defender_allies, attacker_allies=allies)

        # Enemies charge toward their ultimate on EVERY action, not just
        # basic attacks -- see ENEMY_ENERGY_PER_ACTION. Granted after the
        # action resolves so an ultimate can't pay for itself on the same
        # turn it fires.
        if enemy.energy < enemy.max_energy:
            enemy.gain_energy(ENEMY_ENERGY_PER_ACTION)

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
