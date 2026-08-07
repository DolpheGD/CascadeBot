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

# ----------------------------------------------------------------------
# ULTIMATE COOLDOWN -- the visible replacement for the energy throttle.
#
# Energy income is now uncapped (see gain_energy below), which on its own
# means a squad stacking energy gear reaches one ultimate roughly every
# turn: measured at 1.4 turns per ultimate for an ordinary squad and 0.9
# for a support-stacked one, i.e. most of the fight is ultimate
# animations.
#
# A cooldown solves that where the player can SEE it. "💥 Ultimate (ready
# in 2t)" on the button is a fact they can plan a turn around; an energy
# gain that silently stopped counting was not. It also can't be
# out-stacked -- no amount of gear shortens it -- so the ceiling on
# ultimate frequency is a design number again rather than an emergent
# property of somebody's inventory.
#
# At 2, each character ultimates at most every third turn. Energy still
# matters enormously: the cooldown sets the FLOOR on the gap, and a squad
# with no energy investment is nowhere near hitting it.
# ----------------------------------------------------------------------
ULTIMATE_COOLDOWN = 2


# ----------------------------------------------------------------------
# THE SHARED AMPLIFICATION BUDGET
# ----------------------------------------------------------------------
# Diminishing returns on STACKED POSITIVE buffs -- across every offensive
# stat at once, not one stat at a time.
#
# The measured problem: a squad running three supports who all buff ATK
# was 2.2x the damage of every other strategy, and no amount of buffing
# DoT/break/shred closed the gap, because those add damage while an ATK
# buff MULTIPLIES it -- and three of them multiplied together.
#
# Worth recording that the original diagnosis was wrong. It was called
# "crit stacking" for two rounds and crit buffs were nerfed twice with no
# effect, because crit_rate BASE is 5 and buffs are a percentage OF base:
# the entire support package moved Star's crit rate from 5% to 7%. The
# thing doing the work was always ATK.
#
# THE FALLOFF USED TO BE PER-STAT, AND THAT WAS THE LOOPHOLE.
#
# Taxing the Nth buff to ONE stat only taxes Amplifiers who happen to
# buff the same thing. The roster's Amplifiers buff ATK, ELE, Crit Rate,
# Crit DMG, SPD and recharge -- six different stats -- so three of them
# in one squad landed three untaxed multipliers on the carry and simply
# multiplied out. Measured over full expedition runs, "3 Amplifiers + 1
# DPS" beat "one of each role" in every region, and "no Amplifier" was
# the worst squad in the game by a distance. The class wasn't strong;
# STACKING the class was strong, which is a different bug and needs a
# different fix.
#
# So the budget is now shared. Every positive buff to any offensive stat
# competes for the same falloff ladder, ranked by SOURCE:
#
#     1st source: 100%    2nd: 45%    3rd: 20%    4th: 9%
#
# Ranked by source rather than by individual modifier so that ONE ability
# buffing two stats at once (team_double_buff -- Nexus's ultimate, the
# avatar Amplifier's Overdrive) is one entry on the ladder and lands in
# full. That is the deliberate reward for a well-designed single kit, and
# it is exactly what stacking three separate Amplifiers no longer gets.
# Re-applying the SAME buff to the SAME stat still steps down the ladder,
# so spamming one Amplifier's skill can't dodge the rule either.
#
# Note what this does NOT touch, all on purpose:
#   * DEBUFFS get their own, much gentler ladder (DEBUFF_STACK_FALLOFF).
#     DEF shred, vulnerability marks and break are the Support DPS's
#     multiplier and one of them should feel unrestricted -- but they
#     were originally exempt ENTIRELY, and that stopped being safe once
#     enemy defence scaled up. Two Support DPS could shred a target to
#     roughly zero DEF between them, and "1 DPS + 2 Support DPS +
#     Sustain" became the best squad at Voidcrest (69% against 60%).
#     Same bug as stacked Amplifiers, one class over.
#   * DEFENSIVE buffs are exempt (NO_FALLOFF_STATS), so Sustains stay
#     whole.
#   * A character's own ramping passives (stacking_buff, ramp_percent)
#     are not StatModifiers and never enter the ladder, so a DPS still
#     snowballs its own damage at full value.
#
# THE LADDER IS AUTHORED, NOT GEOMETRIC, AND THAT IS THE WHOLE POINT.
#
# A geometric falloff (0.65, then 0.45) cannot tell the difference
# between the two cases it most needs to separate:
#
#     one Amplifier pressing both of its buttons
#     two Amplifiers pressing one each
#
# Both land two buffs, so both were taxed identically -- which meant
# every attempt to make stacking worse also made a SINGLE Amplifier
# worse, and every attempt to make one Amplifier good made three good
# again. That tug-of-war is visible in this file's history: 0.65 left
# doubling up as the best play, 0.45 fixed that and left the class as
# the marginal slot at Voidcrest, where a squad that swapped its
# Amplifier for a second attacker cleared 70% against 62%.
#
# An explicit ladder separates them. The first two entries are generous
# because they are what ONE Amplifier brings -- a skill and an ultimate.
# Everything after that falls off a cliff, because that is what a SECOND
# Amplifier brings:
#
#     1st source 100%   2nd 80%   3rd 8%   4th 3%   5th+ 2%
#
# So one Amplifier is worth 1.8 buffs, three are worth 1.94 -- stacking
# the class buys about 8% more amplification for two entire squad slots,
# while the player who brings exactly one gets nearly all of it.
#
# The cliff also settles what happens to INCIDENTAL buffs -- a Support
# DPS's crit-rate kit reaction, a buff rolled on a weapon. Ranked by
# magnitude, those land at rank 2+ and are worth almost nothing next to
# a real Amplifier's buttons. That is intended: buffing is the
# Amplifier's job, and a squad without one should feel the absence
# rather than paper over it with gear.
BUFF_STACK_LADDER = (1.0, 0.8, 0.08, 0.03, 0.02)
BUFF_STACK_LADDER_TAIL = 0.01

# Kept for _stacked_percent's bare-list callers (serialisation
# round-trips, tooling), which have no source information and so can't
# use the ladder.
BUFF_STACK_FALLOFF = 0.45


def buff_stack_weight(rank: int) -> float:
    """How much the Nth buff source counts for. See the ladder above."""
    if rank < len(BUFF_STACK_LADDER):
        return BUFF_STACK_LADDER[rank]
    return BUFF_STACK_LADDER_TAIL


# Debuffs to the SAME stat, ranked by size: 100%, 50%, 25%...
#
# Deliberately much gentler than the buff ladder, and applied per stat
# rather than across all of them, because the two cases are different.
# Buffs from three Amplifiers multiply one carry's damage without limit;
# debuffs are self-limiting -- defence can only be stripped to zero --
# so the FIRST shred should land in full and be worth building around.
# What this stops is the second and third landing in full as well, which
# is what turned doubling up on Support DPS into the best squad.
DEBUFF_STACK_FALLOFF = 0.5

# The stats that compete for the shared budget above: everything a buff
# can touch that makes the squad hit HARDER. Kept as an explicit set
# rather than "not NO_FALLOFF_STATS" so that adding a new stat to the
# game is a deliberate decision about which side of the line it sits on.
AMPLIFICATION_STATS = frozenset({
    "attack", "elemental", "crit_rate", "crit_damage", "speed", "recharge",
})


# DEFENSIVE stats are exempt. The problem being solved is stacked
# OFFENSIVE buffs; taxing DEF and max HP as well knocked every Sustain
# down with it (Bee Jee 43% -> 13%, Kotori 40% -> 7%) and undid the
# healer work rather than the damage work.
NO_FALLOFF_STATS = frozenset({"defense", "max_hp"})

# STATS THAT ARE ALREADY MEASURED IN PERCENTAGE POINTS.
#
# crit_rate 5 means "5% of hits crit"; crit_damage 50 means "+50% damage
# on a crit"; recharge 20 means "+20% energy gain". They are not
# magnitudes like ATK -- they ARE percentages.
#
# So a buff reading "+30% Crit Rate" has to ADD 30 points, not multiply
# the existing value by 1.30. Multiplying was what the code did, and on
# a 5-point base it delivered 5 -> 6.5: an advertised +30% that was
# worth +1.5% in practice, and which got BETTER the more crit you
# already had -- the exact opposite of how every player reads it. It
# also made crit buffs nearly worthless early and quietly strong late.
#
# Everything else stays multiplicative, which is right: +30% ATK on 200
# ATK should be +60, not +30.
ADDITIVE_POINT_STATS = frozenset({"crit_rate", "crit_damage", "recharge"})


def _stacked_percent(percents: list[float], stat: str | None = None) -> float:
    """Same-stat falloff, kept for callers that only have a bare list of
    percentages (serialisation round-trips, tests, tooling). The live
    combat path uses amplified_percent below, which sees every modifier
    at once and can therefore apply the SHARED budget."""
    if stat in NO_FALLOFF_STATS:
        return sum(percents)
    positives = sorted((p for p in percents if p > 0), reverse=True)
    negatives = [p for p in percents if p <= 0]
    total = sum(negatives)
    for index, value in enumerate(positives):
        total += value * (BUFF_STACK_FALLOFF ** index)
    return total


def amplified_percent(modifiers: list, stat: str) -> float:
    """Total percent modification to `stat`, after the shared
    amplification budget described above.

    `modifiers` is the owner's WHOLE StatModifier list, not just the
    entries for `stat` -- seeing all of them at once is the entire point,
    since the budget is shared across stats.
    """
    # Debuffs on this stat, biggest first, each subsequent one halved.
    negatives = 0.0
    for index, modifier in enumerate(
        sorted((m for m in modifiers if m.stat == stat and m.percent < 0),
               key=lambda m: m.percent)
    ):
        negatives += modifier.percent * (DEBUFF_STACK_FALLOFF ** index)

    if stat in NO_FALLOFF_STATS:
        return negatives + sum(m.percent for m in modifiers
                               if m.stat == stat and m.percent > 0)

    # Group every positive OFFENSIVE buff by the ability that applied it.
    by_source: dict[str, list] = {}
    for modifier in modifiers:
        if modifier.percent > 0 and modifier.stat in AMPLIFICATION_STATS:
            by_source.setdefault(modifier.source, []).append(modifier)

    # Biggest contributor takes rank 0 (the untaxed slot). Sorting
    # player-favourably is a deliberate choice: the ladder is meant to
    # cap how much total amplification a squad can hold, not to punish
    # the player for the order their turns happened to come up in.
    order = sorted(by_source, key=lambda src: -max(m.percent for m in by_source[src]))

    total = negatives
    for rank, source in enumerate(order):
        # Within one source, buffs to DIFFERENT stats share the rank
        # (one ability, one slot on the ladder); a repeat buff to the
        # SAME stat steps down, so re-casting can't dodge the budget.
        seen: dict[str, int] = {}
        for modifier in sorted(by_source[source], key=lambda m: -m.percent):
            duplicate = seen.get(modifier.stat, 0)
            seen[modifier.stat] = duplicate + 1
            if modifier.stat == stat:
                total += modifier.percent * buff_stack_weight(rank + duplicate)
    return total



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

    # A shorter label for width-limited views (turn order, telegraph
    # lines). Empty means "the full name is already short enough" -- see
    # bot/utils/names.py and enemies.ENEMY_SHORT_NAMES. Carried on the
    # Combatant rather than looked up at render time so a saved battle
    # renders identically to a live one without the renderer needing
    # access to the template catalog.
    short_name: str = ""

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
    vulnerabilities: list = field(default_factory=list)  # list[Vulnerability]
    # QUEUE of this combatant's decided-but-not-yet-executed actions for
    # the current cycle, in order -- each {"ability": dict|None,
    # "target": Combatant}. See Battle.peek_enemy_intent_schedule.
    #
    # A queue rather than a single intent because the battle screen
    # telegraphs the WHOLE rest of the cycle, and every move it shows has
    # to be the move that actually happens. Deciding a later slot fresh
    # at display time can't achieve that: the decision is random, so it
    # would re-roll on every re-render and disagree with whatever the
    # real turn eventually rolled (measured at ~45% agreement). Deciding
    # once and popping from the front makes every telegraphed move
    # binding, however far ahead it was shown.
    pending_intents: list = field(default_factory=list)

    # The level this combatant was built at. Feeds the defence formula
    # (see formulas.mitigation_k): mitigation has to know how strong the
    # ATTACKER is, or defence quietly outscales the whole game.
    level: int = 1

    # ENEMY-ONLY sustain decay counters. See heal() / gain_shield().
    # Named for what they are so a save file is readable; they stay 0 for
    # every player character because nothing ever increments them there.
    enemy_heals_used: int = 0
    enemy_shields_used: int = 0

    @property
    def pending_intent(self) -> dict | None:
        """The next queued action, or None. Kept as a read-only alias so
        the older single-intent call sites and saves keep reading
        correctly."""
        return self.pending_intents[0] if self.pending_intents else None

    stunned_turns: int = 0

    # ------------------------------------------------------------------
    # TAUNT -- forced targeting, in both directions.
    #
    # While taunt_turns > 0, every SINGLE-TARGET attack from the OPPOSING
    # side must aim at this combatant. Deliberately one symmetric
    # mechanic rather than two:
    #
    #   * A party member taunting pulls enemy attacks onto themself --
    #     the classic tank play, and the thing that makes a shielded,
    #     high-DEF character worth a squad slot rather than just a
    #     survivable one. It's also the counterplay to the enemy intent
    #     telegraph that Guard couldn't be: Guard blunts a hit on the
    #     character being aimed at, taunt moves that hit onto someone who
    #     wants it.
    #   * An enemy taunting forces the PLAYER's attacks onto it -- a
    #     "deal with me first" bodyguard, which is what finally makes
    #     enemy positioning matter. Without it, the player could always
    #     ignore a defensive enemy and burst the healer behind it.
    #
    # AOE is deliberately unaffected: an ability that hits everything
    # already hits the taunter, and letting taunt shrink an AOE to a
    # single target would make it a debuff on the player's own kit.
    #
    # Ticks down at the end of the TAUNTER's own turn (battle._end_turn),
    # same cadence as StatModifier durations, so "3 turns" means three of
    # the taunter's turns rather than three of anyone's.
    # ------------------------------------------------------------------
    taunt_turns: int = 0

    def is_taunting(self) -> bool:
        return self.taunt_turns > 0

    # ------------------------------------------------------------------
    # Poise / Break -- the counterplay layer for enemy intent telegraphing.
    #
    # Enemies decide their next move BEFORE it happens and the UI shows it
    # (see battle.py's _decide_enemy_intent / pending_intent). Poise is
    # what lets the player DO something about it: every landed hit chips a
    # point or two off the target's poise, and when it hits zero the enemy
    # is BROKEN -- its telegraphed move is cancelled outright, it loses its
    # turns for break_turns, and it takes amplified damage the whole time.
    #
    # This is deliberately asymmetric: only enemies have poise (max_poise
    # stays 0 for players, and 0 means "cannot be broken"). The player's
    # side of the mechanic is Guard (see `guarding` below). Making both
    # sides breakable would double the state to reason about for very
    # little added depth, and being stun-locked by a boss is not fun.
    #
    # Poise refills to full when a break ends, so breaking is a repeatable
    # tactic across a long fight rather than a one-shot resource -- but the
    # refill means chip damage between breaks is wasted, which is what
    # makes "commit to the break now vs. save cooldowns" an actual choice.
    #
    # ------------------------------------------------------------------
    # BREAK RESISTANCE (rebalance pass).
    #
    # The refill-to-full rule above was the ONLY thing limiting how often
    # a target could be broken, and it turned out not to be a limit at
    # all once poise-damage bonuses entered the picture. The relics stack
    # additively and apply PER LANDED HIT, so a squad holding both
    # Breaker's Charge (+1) and Shatterpoint Prism (+2) chipped 4 poise
    # with a plain basic attack and 12+ with a single multi-hit ultimate.
    # Against a 16-poise boss that is a guaranteed break every cycle --
    # and since a break cancels the telegraphed move AND skips the
    # target's turns AND amplifies damage taken, "permanently broken"
    # meant the boss never acted again. The counterplay mechanic had
    # become a win condition on its own.
    #
    # So a broken combatant now comes back TOUGHER: every break
    # permanently raises its max_poise by BREAK_RESISTANCE_PERCENT for
    # the rest of the battle (compounding). The first break is as easy as
    # it ever was -- nothing about the opening play is nerfed -- but the
    # second costs ~1.5x, the third ~2.2x, and so on, so break frequency
    # decays toward a floor instead of running away. This deliberately
    # scales WITH the player's investment: more poise-damage bonuses
    # still mean more breaks, they just can't compound into a lock.
    #
    # Implemented as a growing max_poise rather than a cap on bonuses
    # because it leaves the relics feeling exactly as strong as they read
    # on the tin, and because it's legible in the UI for free -- the
    # player watches the poise bar get longer and understands why.
    # ------------------------------------------------------------------
    max_poise: int = 0
    poise: int = 0
    break_turns: int = 0
    # How many times this combatant has been broken so far this battle.
    # Drives the max_poise escalation in recover_from_break().
    break_count: int = 0

    # Guards against a break being spent without the player ever getting
    # to cash it in. break_turns counts the BROKEN combatant's own skipped
    # turns, but the +damage window is only worth anything on the
    # ATTACKER's turns -- and those don't reliably interleave. A boss with
    # actions_per_cycle=2 that's also the fastest thing in the fight takes
    # the last turn of one cycle and the first of the next back-to-back,
    # which would burn the entire break with no party turn in between.
    #
    # So a break tick is "armed" only once an opposing combatant has
    # actually acted since the break started (battle.py arms it after
    # every party action). Broken turns are therefore always paid for with
    # a real opportunity to capitalise, whatever the turn order does.
    break_tick_armed: bool = False

    # Extra poise chipped by every hit THIS combatant lands, on top of the
    # per-action baseline. Granted by run-scoped poise_damage relics (see
    # bot/services/relic_service.py) and baked onto the Combatant at
    # battle-build time rather than looked up per hit, so effects.py stays
    # unaware of expeditions and the bonus survives serialization the same
    # way every other combat value does. Always 0 in Domains, which have
    # no expedition and therefore no relics.
    bonus_poise_damage: int = 0

    # Set by the Guard action, cleared at the start of this combatant's
    # next turn. Halves incoming damage (see effects._resolve_hit) and
    # pays out bonus energy if a hit actually lands while it's up -- so
    # correctly reading a telegraphed heavy attack is rewarded, and
    # guarding on a hunch that doesn't pan out simply costs you the turn.
    guarding: bool = False

    # Flat HP-equivalent pool that absorbs incoming damage before current_hp
    # does (see self_shield_percent_max_hp / team_shield_percent_max_hp /
    # shield_regen in bot/game/combat/effects.py). Consumed first, in full
    # or in part, on every hit; never expires on its own -- it just runs out.
    # INT, not float. The shield pool is displayed next to HP and is
    # spent in whole points of damage, so it has no business carrying
    # a fractional part -- every call site was already round()-ing it
    # for display, which is the tell that the type was wrong.
    shield: int = 0

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

    # ------------------------------------------------------------------
    # NO HIDDEN DIMINISHING RETURNS. (Removed: enemy_heal_stacks,
    # enemy_shield_stacks, player_heal_stacks, heal_fatigue_stacks, and
    # the per-turn energy throttle.)
    #
    # Sustain used to be reined in by four separate invisible curves --
    # every heal a combatant received made the next one weaker, shields
    # decayed the same way, healing weakened globally past cycle 12, and
    # energy income was silently capped per turn. They worked, in that the
    # numbers came out fine. The problem is that none of them were
    # LEGIBLE: a player watching a 40%-of-max-HP team heal restore 14% had
    # no way to find out why, and no decision they could make about it.
    # A balance mechanism a player can't see is one they can only
    # experience as the game being broken.
    #
    # Everything that limits sustain now lives on the ability card the
    # player is already reading: SP cost, cooldown, and the fact that SP
    # comes only from basic attacks. Those are numbers you can plan
    # around. See ability_ready() and the RESOURCE ECONOMY block in
    # effects.py.
    #
    # The attack ramp above deliberately STAYS. It's the anti-softlock
    # floor of last resort, it applies to both sides, it's an offence
    # buff rather than a stealth nerf to the player's own abilities, and
    # it's surfaced in the Info panel.
    # ------------------------------------------------------------------

    def is_alive(self) -> bool:
        return self.current_hp > 0

    # ------------------------------------------------------------------
    # Poise / Break
    # ------------------------------------------------------------------
    def can_be_broken(self) -> bool:
        """Whether this combatant participates in the poise system at all.
        False for players and for any enemy explicitly given max_poise 0
        (useful for a scripted "unbreakable" fight)."""
        return self.max_poise > 0

    def is_broken(self) -> bool:
        return self.break_turns > 0

    def damage_poise(self, amount: int) -> bool:
        """Chips `amount` off this combatant's poise. Returns True only on
        the hit that actually triggers the break, so the caller can log it
        once -- further hits while already broken return False rather than
        re-breaking (and deliberately don't chip poise at all, since it's
        held at 0 until the break expires and refills it)."""
        if not self.can_be_broken() or self.is_broken() or amount <= 0:
            return False
        self.poise = max(0, self.poise - amount)
        return self.poise == 0

    # Percent by which max_poise grows after EACH break, compounding --
    # see the BREAK RESISTANCE block above. At 40%, a 16-poise boss needs
    # 16 / 22 / 31 / 44 poise for its first four breaks.
    BREAK_RESISTANCE_PERCENT = 40

    def enter_break(self, duration: int) -> None:
        """Puts this combatant into the broken state. Cancels whatever
        move it had telegraphed -- that cancellation is the whole point of
        the mechanic, and it's why breaking a wind-up is worth doing
        rather than just racing the damage."""
        self.break_turns = duration
        self.break_tick_armed = False
        self.break_count += 1
        # Breaking cancels EVERY queued move, not just the next one --
        # that cancellation is the whole point of the mechanic.
        self.pending_intents = []
        self.guarding = False

    def recover_from_break(self) -> None:
        """Ends the break and refills poise -- but to a HIGHER maximum
        than last time (see the BREAK RESISTANCE block above). This is
        the one thing standing between the poise system and a permanent
        stunlock once poise-damage bonuses stack up."""
        self.break_turns = 0
        self.break_tick_armed = False
        self.max_poise = max(
            self.max_poise,
            round(self.max_poise * (1 + self.BREAK_RESISTANCE_PERCENT / 100)),
        )
        self.poise = self.max_poise

    def poise_fraction(self) -> float:
        """0.0-1.0 for UI bars. 1.0 when the combatant has no poise system
        at all, so a caller that renders unconditionally shows a full bar
        rather than an alarming empty one."""
        if not self.can_be_broken():
            return 1.0
        return max(0.0, min(1.0, self.poise / self.max_poise))

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
        percent_total = amplified_percent(self.modifiers, stat)

        if stat in ("attack", "elemental") and self.ramp_percent_per_turn and self.ramp_stacks:
            percent_total += self.ramp_percent_per_turn * self.ramp_stacks

        for ability in self.passive_abilities:
            effect = ability["effect"]
            if effect["kind"] == "stacking_buff" and effect["buff_stat"] == stat:
                stacks = self.stacks.get(ability["id"], 0)
                percent_total += effect["percent_per_stack"] * stacks

        # POINT STATS ARE ADDITIVE. See ADDITIVE_POINT_STATS.
        if stat in ADDITIVE_POINT_STATS:
            value = max(0.0, base + percent_total)
        else:
            value = max(0.0, base * (1 + percent_total / 100))

        # Stat conversion: gain a percentage of one stat as another (e.g.
        # Refender turning DEF into ATK). Added AFTER percent modifiers so
        # it converts the stat's real current value, which is the whole
        # point -- buffing the source stat should feed the converted one.
        #
        # Reads the SOURCE stat's base plus its own modifiers rather than
        # calling effective_stat recursively, which two mutually
        # converting passives would turn into infinite recursion.
        for ability in self.passive_abilities:
            effect = ability["effect"]
            if effect["kind"] != "stat_conversion" or effect["to_stat"] != stat:
                continue
            src = effect["from_stat"]
            src_base = self.base_stats.get(src, 0)
            # Budgeted, like every other read of a buffed stat -- summing
            # raw here would have made stat_conversion a way to launder
            # stacked buffs past the falloff ladder.
            src_percent = amplified_percent(self.modifiers, src)
            src_value = max(0.0, src_base * (1 + src_percent / 100))
            value += src_value * effect["percent"] / 100

        return round(value, 2)

    def take_raw_hp_loss(self, amount: float) -> int:
        """Reduce HP by an already-computed damage amount. Returns actual loss."""
        amount = max(0, int(round(amount)))
        actual = min(self.current_hp, amount)
        self.current_hp -= actual
        return actual

    def heal(self, amount: float) -> int:
        """Applies healing, in HP, and returns what actually landed.

        Still the single choke point every heal effect routes through
        (heal_percent_max_hp, team heals, HealOverTime regen ticks,
        lifesteal -- see bot/game/combat/effects.py and battle.py), but it
        no longer TOUCHES the amount. A heal that says 40% of max HP heals
        40% of max HP, every time, for both sides.

        The choke point is kept even though it currently does no
        arithmetic: it's what makes "heal for real" a single call rather
        than 20 copies of `current_hp = min(max_hp, current_hp + n)`
        scattered through the effect dispatcher, and it's where the
        overheal clamp lives."""
        # ROUNDED AFTER the falloff, not before. Rounding first and then
        # multiplying by 0.45 puts the fraction straight back (1000 ->
        # 450.0 -> 202.5), which is how "202.5 HP restored" reached the
        # combat log. HP is a whole number everywhere else in the game.
        amount = self._enemy_sustain_falloff(max(0.0, amount), "heal")
        amount = max(0, int(round(amount)))
        healed = min(self.max_hp - self.current_hp, amount)
        self.current_hp += healed
        return healed

    # ------------------------------------------------------------------
    # ENEMY SUSTAIN DECAY -- asymmetric on purpose.
    #
    # PLAYERS HAVE NO DECAY AT ALL. What an ability says it heals or
    # shields is what it does, every time, forever. That transparency was
    # a deliberate decision and is not being walked back: a player who
    # cannot predict their own healer cannot plan around them.
    #
    # ENEMIES DECAY HARD. An enemy that can heal or shield on a loop
    # doesn't make a fight difficult, it makes it LONG -- the player has
    # already won on damage and is now just clicking until the arithmetic
    # agrees. Repeated enemy sustain is therefore punished steeply:
    #
    #     1st  100%     2nd   45%     3rd   20%
    #     4th    9%     5th+   4%  (floored, never zero)
    #
    # So an enemy healer is a real threat the first time and a nuisance
    # by the third, which is the shape that keeps a boss dangerous
    # without making it a war of attrition.
    #
    # Counters live per-combatant and are serialized, so a fight resumed
    # after a restart doesn't hand the boss a fresh set of full heals.
    # ------------------------------------------------------------------
    ENEMY_SUSTAIN_FALLOFF = 0.45
    ENEMY_SUSTAIN_FLOOR = 0.04

    def _enemy_sustain_falloff(self, amount: float, kind: str) -> float:
        if self.is_player or amount <= 0:
            return amount
        if kind == "heal":
            used = self.enemy_heals_used
            self.enemy_heals_used = used + 1
        else:
            used = self.enemy_shields_used
            self.enemy_shields_used = used + 1
        multiplier = max(self.ENEMY_SUSTAIN_FLOOR, self.ENEMY_SUSTAIN_FALLOFF ** used)
        return amount * multiplier

    def gain_shield(self, amount: float) -> float:
        """Adds to this combatant's shield pool -- sibling choke point to
        heal(), and likewise no longer scaled. Returns the amount added so
        callers can log the real number."""
        # Same rounding rule as heal(): the shield pool is displayed as a
        # number beside HP, so it has to BE a number. This never rounded
        # at all, so a 15%-of-max-HP shield on an odd HP total produced
        # trailing decimals that then accumulated across every stack.
        amount = self._enemy_sustain_falloff(max(0.0, amount), "shield")
        amount = max(0, int(round(amount)))
        self.shield += amount
        return amount

    def gain_energy(self, amount: float) -> int:
        """The single choke point every energy gain routes through --
        basic attacks, ability use, being hit, guarding, team restores,
        auras and kit reactions alike. Returns the amount actually
        granted, which is limited only by the pool's own ceiling.

        The per-turn throttle that used to live here is gone. Stacking
        energy gear now does exactly what it says: more energy, faster.
        What stops that from becoming one ultimate every turn is the
        ultimate's own COOLDOWN, which the player can see on the button
        -- see ULTIMATE_COOLDOWN in effects.py."""
        amount = max(0, int(round(amount)))
        granted = min(amount, self.max_energy - self.energy)
        if granted <= 0:
            return 0
        self.energy += granted
        return granted

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

        before_mana = self.mana
        # Energy routes through the throttle (see gain_energy); mana does
        # not, because mana is spent on skills every turn rather than
        # banked toward one big payoff, so a mana surplus doesn't compound
        # into the same runaway loop.
        energy_gained = self.gain_energy(self.max_energy * pct / 100)
        mana_gain = int(round(self.max_mana * pct / 100))
        self.mana = min(self.max_mana, self.mana + mana_gain)
        return energy_gained, self.mana - before_mana

    def find_passive(self, effect_kind: str) -> list:
        return [a for a in self.passive_abilities if a["effect"]["kind"] == effect_kind]

    def total_vulnerability_percent(self, damage_stat: str) -> float:
        """Sum of every stacked Vulnerability's (percent_per_stack * stacks)
        matching `damage_stat` -- see status.Vulnerability. Multiple
        independent sources (different abilities) stack additively with
        each other; only repeat applications from the SAME source stack
        onto one instance (handled where Vulnerability instances are
        created/refreshed, in effects.py)."""
        return sum(
            v.percent_per_stack * v.stacks for v in self.vulnerabilities if v.damage_stat == damage_stat
        )

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
