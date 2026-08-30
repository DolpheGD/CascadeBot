"""
Each region is a fixed difficulty tier -- picking where to go (the
`region` choice on /adventure) IS the difficulty choice, per the spec:
"Each location could have a different difficulty, with higher difficulty
locations giving more rewards. You should always have to choose where to
go." `level_offset` pushes enemy scaling harder than floor depth alone
would, and `reward_multiplier` scales gold/XP from every source in that
region (see bot/services/combat_service.py and dungeon_service.py).

Progression pacing: `max_item_rarity` and `max_lootbox_tier` STRICTLY cap
what a region can drop -- Glacier 15 (tier 1) can never produce anything
above Rare, full stop, so a new player has to actually work through
Common/Uncommon/Rare gear before the higher regions even have a chance to
hand them something better. Higher-tier regions aren't guaranteed-better
though -- they roll the FULL range up to their cap (a genuine mix of low
and high, still weighted toward common via RARITY_WEIGHTS/
LOOTBOX_RARITY_WEIGHTS), not an exclusively-high-tier firehose.

`combat_squad_weights`/`elite_squad_weights` control how many enemies show
up in a single COMBAT/ELITE fight in that region -- easier regions skew
toward smaller fights, harder regions toward bigger ones (see
dungeon_service.enter_node). Which enemy TEMPLATES can even appear in a
region at all (and which boss templates count as "final boss" caliber
there) is a separate axis controlled by each template's own `regions`/
`region_roles` fields in bot/game/combat/enemies.py.

Combat rework: `level_offset` still drives ELITE/BOSS scaling in a region
(unchanged). `combat_level_offset` is a new, higher offset used ONLY for
normal "combat"-room enemy scaling (see dungeon_service.enter_node) --
normal enemies in the harder regions were badly underscaled relative to
how strong a player actually is by the time they reach those regions, so
they now get pushed harder than elites/bosses do in that same region
rather than just inheriting `level_offset`. `combat_squad_weights` were
also bumped up across every region for a significantly higher average
enemy count per normal fight.

RARITY ODDS, NOT JUST A RARITY CEILING.

`max_item_rarity` is a hard CAP -- it decides what a region can produce
at all. On its own that turned out to be a weak progression lever,
because the base weights (see rarity_config.RARITY_WEIGHTS) are steeply
tilted toward Common: reaching Abyssnia unlocked Divine drops at 0.5%,
which is unlocking a rarity in name only. A player who had beaten the
hardest content in the game was still opening Commons.

`rarity_weight_bonus` fixes that by tilting the DISTRIBUTION as well as
raising the ceiling. It feeds rarity_config's existing weighting
mechanism (the same one the Research Lab's Salvage branch uses), which
scales each rarity's weight by its own position -- so the bonus lifts the
top of the table hardest and never touches what the cap already excluded.
Endgame regions become genuinely good places to farm the top rarities
rather than places where they are merely legal.
"""

from __future__ import annotations

from bot.database.models.enums import Rarity

# ----------------------------------------------------------------------
# DIFFICULTY WAS RAISED ACROSS TIERS 1-4, AND LOWERED FOR TIER 5.
#
# Measured with GEAR modelled (tools/sim_expedition.py), which changed the
# answer completely -- a naked squad is a floor nobody plays at, and every
# earlier reading off it was misleading. At the level and gear a player
# actually arrives with, the old offsets gave:
#
# RE-CUT AFTER ENEMY ATTACK WENT TO 1.5x (see factory.py). Enemies
# hitting half again as hard made every one of these numbers wrong at a
# stroke -- Glacier 15 fell from 62% to 6% at squad 5 -- so the whole
# ladder shifted down to hold the same curve against deadlier enemies.
#     Glacier 15   @lv8  rare gear   82%      -> now 62%
#     Wastelands   @lv22 rare gear   98%      -> now 82%
#     Hotlands     @lv38 epic gear   75%      -> now 57%
#     Voidcrest    @lv52 legendary   72%      -> now 70%
#     Abyssnia     @lv70 legendary   18%      -> now ~32%
#
# The first four were too easy for regions that are supposed to be the
# whole progression curve. Abyssnia went the OTHER way on purpose: at
# 18% fully geared it was not a hard region, it was a closed door, and
# raising it "across the board" would have made the endgame unreachable
# rather than difficult.
#
# The story funds this. The prologue now hands out five pieces of gear
# (2 Uncommon + 3 Rare) and Chapter 1 four more (2 Rare + 2 Epic), so a
# player reaches Glacier 15 with a full five-slot kit instead of one
# Uncommon. Difficulty and preparation moved together; either alone
# would have been a regression.
# ----------------------------------------------------------------------
# THE LATE LADDER WAS RECALIBRATED FOR REAL RUN LENGTH.
#
# Wastelands 18/24 -> 15/20, Hotlands 26/33 -> 20/27, Voidcrest
# 30/39 -> 24/33.
#
# Not a nerf on its own terms -- a correction for run length. Every
# region's offsets were calibrated against tools/bench_roles when that
# benchmark walked a hard-coded 9 floors; it now walks a real generated
# map, which is ~45 rooms and 18 fights. Voidcrest measured a 15% clear
# rate for the reference comp under the honest model and 45% at these
# offsets, which is where it was always meant to sit.
#
# ABYSSNIA IS DELIBERATELY NOT ADJUSTED HERE, and it currently measures
# about 2%. Its offsets are not what is wrong with it: dropping them by
# 12 moved the clear rate by nothing, while the same change took
# Voidcrest from 15% to 77%. What changed for Abyssnia is BOSS COUNT --
# a run is now 3-4 boss fights rather than the ~1 the old benchmark
# measured, and Abyssnia's bosses are the hardest in the game. That is a
# content problem (its boss pool), not a scaling constant, and it wants
# its own pass rather than a number nudged until the benchmark goes
# green.
#
# ----------------------------------------------------------------------
# THAT DIAGNOSIS WAS WRONG, AND SO WAS THE BENCHMARK IT CAME FROM.
# ----------------------------------------------------------------------
#
# Abyssnia never had a boss-pool problem. tools/sim_expedition had THREE
# independent bugs, each of which alone made its output unusable, and the
# paragraph above is what happens when you reason carefully from numbers
# that were never measurements:
#
#   1. BOSS ROOMS WERE NOT THE GAME'S BOSS ROOMS. The sim drew 1-3
#      templates at random from the boss pool, the way it builds a combat
#      room. dungeon_service calls get_boss_encounter, which returns ONE
#      boss or a curated group. Abyssnia's elite_squad_weights are
#      {1:10, 2:35, 3:55}, so the sim stacked THREE random bosses 55% of
#      the time. The runs were dying to "Dorve, Rohan" -- a pairing the
#      game cannot generate. That is the "boss count" the note above was
#      describing.
#
#   2. EVERY BATTLE ROLLED ITS OWN DICE. fight() built Battle(party,
#      enemies) with no rng, and Battle falls back to an unseeded
#      random.Random(). The same seed returned
#      [False, True, False, True, True] across five identical repeats.
#      Every figure ever printed by this tool was one sample from an
#      unknown distribution.
#
#   3. THE DEFAULT TABLE WAS GEARLESS. run() supports gear; __main__
#      never passed any. The headline numbers were for a naked squad,
#      which the docstring warns is "a floor nobody plays at" -- and were
#      then read as though they were forecasts.
#
# With all three fixed and every region measured at its OWN
# expected_squad_level and expected_gear_rarity, reproducibly and across
# processes:
#
#   before this pass    100  100  100   80   92   30   60
#   after               100  100  100   80   78   65   60
#                       Gla  Was  Hot  Voi  VLd  Aby  Ent
#
# So the two real faults were much smaller than "the endgame is
# unreachable": the Voidlands was EASIER than Voidcrest (92% vs 80%) and
# Abyssnia was harder than the region after it (30% vs 60%). The
# Voidlands went 27/35 -> 30/39 and Abyssnia 40/50 -> 33/42, which is the
# first time either number has been set against a benchmark that
# reproduces.
#
# The lesson is worth more than the numbers: three separate people-hours
# of tuning went into offsets chosen to satisfy a tool that was rolling
# dice. Before trusting a benchmark, run it twice.
# EXPECTED SQUAD LEVEL / GEAR: what a player is assumed to bring here.
#
# The game had no such concept, and both tools/bench_roles.py and
# tools/check_final_bosses.py carried a private copy of it called
# REGION_PROFILE. Two benchmarks with their own idea of who plays a
# region, and a game with none at all, is the same two-sources-of-truth
# shape that has produced most of the bugs in this project -- so it lives
# here now and both tools read it.
#
# It is also what a FINAL BOSS should be levelled against. Enemy level is
# floor // 10 + 1 + level_offset, which tops out near 5 + offset and
# drifts further below the squad the deeper the region goes: measured,
# final bosses sat at level 12/23/33/32/45/51 against squads of
# 8/22/38/52/70/85. Voidcrest's finale was TWENTY levels under the party
# that reaches it, which is why it was won every single time.
#
# FINAL-BOSS LEVEL DELTA, relative to expected_squad_level.
#
# The ANCHOR is the structural fix; this delta only absorbs how strong a
# region's particular finale template is, which genuinely varies -- the
# Wastelands finale is a FOUR-enemy boss group and Glacier's is a single
# weak hydra, so the same level means very different things.
#
# Solved per region against a full-health reference squad:
#
#   region              -16   -12    -8    -4    +0    +4    +8   +12
#   Glacier 15         100%  100%  100%  100%  100%  100%  100%   70%
#   The Wastelands     100%  100%  100%  100%   85%   50%   10%    0%
#   The Hotlands       100%  100%  100%   75%   55%   40%   15%    5%
#   Voidcrest Desert    60%   30%   25%   20%   20%   10%    5%    0%
#   Abyssnia            55%   55%   45%   45%   35%   25%   15%    0%
#
# Note Glacier is flat at 100% until +12: its finale is not under-
# levelled, its TEMPLATE is weak, and no amount of anchoring fixes that.
# That is the honest reason its delta is large and everyone else's is
# negative.
#
# Enemy level is floor // 10 + 1 + level_offset, which tops out near
# 5 + offset -- so a region's final boss arrived at level 6/20/25/29/45
# while the squad reaching it is level 8/22/38/52/70. The gap widens with
# depth, and tools/check_final_bosses measured four of five region
# finales at a 100% win rate from full health. The run was hard; the
# fight that ends it was a formality.
#
# Swept per region (win rate from full health, by bonus):
#
#     region             +0    +6   +12   +18   +24   +30
#     Glacier 15        100%  100%   90%   45%   10%    0%
#     The Wastelands    100%   50%    0%    0%    0%    0%
#     The Hotlands      100%  100%   65%   40%    5%    5%
#     Voidcrest Desert  100%   60%   30%   20%   15%    0%
#     Abyssnia           60%   55%   55%   45%   40%   25%
#
# THE SWEEP ABOVE IS THE WRONG TARGET, AND IS KEPT AS A WARNING.
#
# Tuning to 55-65% from FULL health gave +16/+5/+12/+6/+0 and looked
# right in isolation. Measured as a whole run, Glacier's clear rate fell
# from 80% to 10%: players do not arrive at a finale at full health, or
# even at the 60% the check's second column models. The isolated-fight
# number is a useful floor ("is this winnable at all") and a bad target.
#
# So the shipped values are solved against the RUN clear rate in
# tools/bench_roles instead, which is the number a player experiences:
#
#     bonuses          Glacier  Wastelands  Hotlands  Voidcrest  Abyssnia
#     +16/5/12/6/0        10%       52%       60%       30%       32%
#     +6/3/6/3/0          74%       68%       75%       42%       28%
#     +6/3/8/3/0        <- shipped
#
# The values still differ widely because the curves do -- the Wastelands
# finale is a FOUR-enemy boss group, so every level is worth four times
# as much there, and Abyssnia needs none at all now that its bosses have
# been rescaled.
#
# Deliberately a LEVEL bonus rather than a stat multiplier: levels run
# through the same level_scale_percent curve as every other enemy, so a
# boss stays recognisably itself and does not become a bespoke stat block
# that has to be retuned separately forever.
REGION_DIFFICULTY: dict[str, dict] = {
    "Glacier 15": {
        "expected_squad_level": 8, "expected_gear_rarity": Rarity.RARE, "expected_gear_level": 12,
        "tier": 1, "difficulty_label": "Easy",
        "final_boss_level_delta": 4, "level_offset": 1, "combat_level_offset": 2, "reward_multiplier": 1.3,
        "gold_multiplier": 1.3,
        "max_item_rarity": Rarity.RARE, "max_lootbox_tier": "rare",
        "rarity_weight_bonus": 0,
        "combat_squad_weights": {1: 30, 2: 40, 3: 25, 4: 5},
        "elite_squad_weights": {1: 100},
    },
    "The Wastelands": {
        "expected_squad_level": 22, "expected_gear_rarity": Rarity.EPIC, "expected_gear_level": 18,
        "tier": 2, "difficulty_label": "Normal",
        "final_boss_level_delta": 0, "level_offset": 15, "combat_level_offset": 20, "reward_multiplier": 1.8,
        "gold_multiplier": 3.0,
        "max_item_rarity": Rarity.EPIC, "max_lootbox_tier": "epic",
        "rarity_weight_bonus": 60,
        "combat_squad_weights": {1: 10, 2: 30, 3: 35, 4: 20, 5: 5},
        "elite_squad_weights": {1: 80, 2: 20},
    },
    "The Hotlands": {
        # OFFSETS RAISED (17/22 -> 22/29). The Hotlands asked the player
        # no question: measured over full runs, every one of nine squad
        # compositions cleared it 100% of the time, including four
        # deliberately bad ones. A region where the comp doesn't matter
        # is a region with no difficulty, and this is the THIRD of five
        # -- the point where the ladder is supposed to start biting.
        #
        # Its enemies were simply too low-level for the squad that
        # arrives: a level-38 party against level 22-23 enemies. Raising
        # the offsets is the region's own difficulty dial and scales
        # every stat at once, rather than hand-editing the templates it
        # shares with four other regions. Kept below Voidcrest's 27/36 so
        # the ladder still rises.
        "expected_squad_level": 38, "expected_gear_rarity": Rarity.LEGENDARY, "expected_gear_level": 22,
        "tier": 3, "difficulty_label": "Hard",
        "final_boss_level_delta": -4, "level_offset": 20, "combat_level_offset": 27, "reward_multiplier": 2.8,
        "gold_multiplier": 8.0,
        "max_item_rarity": Rarity.LEGENDARY, "max_lootbox_tier": "legendary",
        "rarity_weight_bonus": 130,
        "combat_squad_weights": {2: 20, 3: 35, 4: 30, 5: 15},
        "elite_squad_weights": {1: 50, 2: 50},
    },
    "Voidcrest Desert": {
        "expected_squad_level": 52, "expected_gear_rarity": Rarity.MYTHIC, "expected_gear_level": 28,
        "tier": 4, "difficulty_label": "Insane",
        "final_boss_level_delta": -20, "level_offset": 24, "combat_level_offset": 33, "reward_multiplier": 4.5,
        "gold_multiplier": 20.0,
        "max_item_rarity": Rarity.MYTHIC, "max_lootbox_tier": "mythic",
        "rarity_weight_bonus": 220,
        "combat_squad_weights": {2: 10, 3: 25, 4: 35, 5: 30},
        "elite_squad_weights": {1: 30, 2: 50, 3: 20},
    },
    "The Voidlands": {
        # REGION FIVE, INSERTED RATHER THAN APPENDED.
        #
        # The ladder's expected squad levels ran 8, 22, 38, 52, 70, 85 --
        # steps of 14, 16, 14, 18, 15. The 52 -> 70 jump into Abyssnia was
        # the widest in the game and it sat at the worst possible place:
        # the point where Mythic gear stops being enough and Divine has
        # not started dropping yet, so the only way across was grinding
        # Voidcrest for levels rather than progressing.
        #
        # 61 splits it into 9 and 9. Nothing else in the ladder needed
        # touching, and Abyssnia and Entrospire keep every number they
        # had -- only their `tier` moved, because tier is purely the sort
        # key that ordered_regions() and the unlock chain derive from.
        #
        # WHY IT DOES NOT RAISE THE LOOT CEILING. Mythic, same as
        # Voidcrest, with a higher rarity_weight_bonus (270 against 220).
        # Divine is Abyssnia's threshold and moving it earlier would make
        # this region a strictly-better Voidcrest and Abyssnia a
        # strictly-worse one. What this tier sells is BETTER ODDS at the
        # same ceiling, which is the honest version of a bridge region.
        #
        # The squad weights lean harder than Voidcrest's but stop short
        # of Abyssnia's 55% five-stacks -- this is where a player learns
        # to handle a five-enemy room, not where they are punished for
        # not already being able to.
        #
        # OFFSETS SOLVED, NOT INTERPOLATED. The obvious answer -- split
        # the difference between Voidcrest's 24/33 and Abyssnia's 40/50
        # -- gave 32/41, and tools/sim_expedition put the region at 4%
        # against Abyssnia's own 4%: a "bridge" exactly as hard as the
        # thing it was bridging to. 29/37 did not move it either. 27/35
        # is where the ordering finally came out right:
        #
        #     squad 60, no gear     Voidcrest  Voidlands  Abyssnia
        #     three sim runs         42-50%      4-16%       0%
        #
        # Treat those as an ORDERING, not as targets. That sim models a
        # gearless squad, which the note at the top of this file already
        # warns is a floor nobody plays at, and its run-to-run spread on
        # this region alone is 4% to 16%. The authoritative number for
        # the finale is check_final_bosses, which puts The Quorum Eternal
        # at 71% from full health and 46% from 60% -- between Voidcrest's
        # 79/58 and Abyssnia's 58/42, which is the whole brief.
        "expected_squad_level": 61, "expected_gear_rarity": Rarity.MYTHIC, "expected_gear_level": 31,
        "tier": 5, "difficulty_label": "Merciless",
        "final_boss_level_delta": -18, "level_offset": 30, "combat_level_offset": 39,
        "reward_multiplier": 5.4,
        "gold_multiplier": 30.0,
        "max_item_rarity": Rarity.MYTHIC, "max_lootbox_tier": "mythic",
        "rarity_weight_bonus": 270,
        "combat_squad_weights": {2: 5, 3: 20, 4: 35, 5: 40},
        "elite_squad_weights": {1: 20, 2: 45, 3: 35},
    },
    "Abyssnia": {
        # The glittering capital of Acatrya itself (see docs/WORLD_LORE.md)
        # -- named in the world doc from the start but never actually
        # built as a playable region until now. The true endgame tier:
        # Rarity.DIVINE and lootbox tier "mythic" are already the hard
        # ceiling of what either system can produce (touching either
        # further would mean a new Rarity value, which needs a DB schema
        # change -- off the table), so this region escalates entirely
        # through harder fights and bigger payouts instead of a higher
        # loot ceiling: a genuine "hardest content in the game" tier
        # rather than a "strictly better loot" tier.
        "expected_squad_level": 70, "expected_gear_rarity": Rarity.DIVINE, "expected_gear_level": 34,
        "tier": 6, "difficulty_label": "Nightmare",
        "final_boss_level_delta": -16, "level_offset": 33, "combat_level_offset": 42, "reward_multiplier": 6.5,
        "gold_multiplier": 45.0,
        "max_item_rarity": Rarity.DIVINE, "max_lootbox_tier": "mythic",
        "rarity_weight_bonus": 320,
        "combat_squad_weights": {3: 10, 4: 35, 5: 55},
        "elite_squad_weights": {1: 10, 2: 35, 3: 55},
    },
    "Entrospire Deepworks": {
        # REGION SIX. The company the story keeps naming and never shows:
        # Entrospire hired two of Josh's people nine years ago (the
        # photograph in the Cascade bunks) and this is where that work was
        # done -- a facility still running its own process with nobody
        # left to stop it.
        #
        # WHAT IT ESCALATES, given it cannot escalate loot.
        #
        # Rarity.DIVINE and lootbox tier "mythic" are already the hard
        # ceiling (raising either needs a new Rarity value and a schema
        # change). Abyssnia hit that ceiling, so region six cannot be a
        # "better loot" tier either -- and stacking difficulty alone on
        # top of a region that already clears at 28% would just be a wall.
        #
        # So the step is deliberately SHALLOW in difficulty and steep in
        # VOLUME: +6/+7 level offsets over Abyssnia rather than the +10
        # every earlier gap used, and a much higher rarity_weight_bonus
        # plus reward multiplier. It is the place you farm divines once
        # you can survive Abyssnia, not a fresh difficulty cliff.
        #
        # The enemy roster is machinery rather than soldiers (see
        # enemies.py) -- sustained pressure and inevitability instead of
        # burst, which is also what makes it survivable at these offsets.
        #
        # OFFSETS CUT 46/57 -> 43/52, AND THIS IS THE FIX FOR THE REGION'S
        # SQUAD-COMP PROBLEM. Nine attempts; this was the ninth.
        #
        # Entrospire preferred "1 DPS + 2 Support DPS + Sustain" over "one
        # of each" by 27% to 20% over 600 runs, and eight fixes aimed at
        # the boss, the enemies, the crowds and the debuff ladder either
        # did nothing or made it worse (all eight are listed above The
        # Process in enemies.py). The pattern across them was the answer:
        # every change that ADDED pressure widened the gap, and the only
        # one that ever narrowed it REMOVED pressure.
        #
        # Which means the cause was never the shape of any fight. A
        # Support DPS's debuffs reduce incoming damage, so two of them are
        # two layers of mitigation, and the harder the content the more
        # that is worth. At a 20% clear rate for a balanced squad -- the
        # lowest in the game, BELOW Abyssnia's 29% -- nothing survived
        # except the most defensive comp available.
        #
        # Cutting the offsets took "one of each" from 20% to 29% while the
        # stacked comp barely moved (27% -> 28%), closing the gap from
        # 0.13 to 0.02 and putting all six regions on target for the first
        # time.
        #
        # It also makes the code match the design stated three paragraphs
        # up. This region is documented as "deliberately SHALLOW in
        # difficulty and steep in VOLUME... not a fresh difficulty cliff",
        # and at 46/57 it was measurably the hardest content in the game.
        # The comment was right and the numbers were wrong.
        "expected_squad_level": 85, "expected_gear_rarity": Rarity.DIVINE, "expected_gear_level": 35,
        "tier": 7, "difficulty_label": "Terminal",
        "final_boss_level_delta": -24, "level_offset": 43, "combat_level_offset": 52,
        "reward_multiplier": 8.5,
        "gold_multiplier": 70.0,
        "max_item_rarity": Rarity.DIVINE, "max_lootbox_tier": "mythic",
        "rarity_weight_bonus": 420,
        # LESS CROWDED THAN ABYSSNIA, not more.
        #
        # These started at {3:8, 4:32, 5:60} / {1:8, 2:32, 3:60} -- more
        # enemies per room than the region before it. Combined with a
        # roster built around sustained chip damage, that made the whole
        # region one long attrition check, and attrition rewards exactly
        # one thing: measured over 200 runs, "double support" cleared 28%
        # where "1 of each" cleared 14%. A region where the answer is
        # always two healers is a region with one strategy.
        #
        # Region six's identity is meant to be relentlessness, not
        # swarms, so the crowd sizes come DOWN and the pressure stays in
        # the enemy kits where it belongs.
        "combat_squad_weights": {3: 22, 4: 40, 5: 38},
        "elite_squad_weights": {1: 22, 2: 40, 3: 38},
    },
    "Ocellios Labs": {
        # REGION EIGHT. THE END OF THE LADDER, AND THE START OF THE STORY.
        #
        # Ocellios is where the game opens: the Player wakes here mid-
        # collapse with Stubby's mechs hacked hostile and escapes east
        # into Glacier 15 (docs/STORY_MODE.md). Axel was a test subject
        # here. It is the source of Void-matter synthesis and of every
        # rumour in the setting -- unauthorised experiments,
        # disappearances, research that pushed too close to whatever
        # killed Eris.
        #
        # So the last region is the first room. A player who reaches it
        # is walking back into the place that made them, at level 100,
        # to meet what was still in there.
        #
        # EXISTS FOR DIFFICULTY, NOT FOR PROGRESSION. Every other region
        # is a rung: it gates the next one and drops gear you need. This
        # one gates nothing, because there is nothing after it. Its
        # rarity ceiling is Divine and its lootbox tier Mythic -- exactly
        # Entrospire's, exactly the hard ceiling of both systems -- so it
        # cannot be a mandatory farm. What it offers is the biggest
        # reward and gold multipliers in the game for the hardest content
        # in the game, which is the honest shape for optional endgame:
        # worth doing, never required.
        #
        # EXPECTED SQUAD LEVEL IS THE LEVEL CAP. 100, with Divine gear at
        # 35 (upgrade_level_cap(DIVINE) -- the actual maximum a player can
        # reach). Every other region assumes you arrive mid-growth; this
        # one assumes you have finished growing and asks whether that is
        # enough.
        #
        # OFFSETS SOLVED, NOT PICKED -- see the note below the table.
        "expected_squad_level": 100, "expected_gear_rarity": Rarity.DIVINE,
        "expected_gear_level": 35,
        "tier": 8, "difficulty_label": "Absolute",
        "final_boss_level_delta": -20, "level_offset": 52,
        "combat_level_offset": 62, "reward_multiplier": 11.0,
        "gold_multiplier": 110.0,
        "max_item_rarity": Rarity.DIVINE, "max_lootbox_tier": "mythic",
        "rarity_weight_bonus": 560,
        # The heaviest crowds in the game, but only just -- Entrospire
        # learned the hard way that piling on bodies makes a region an
        # attrition check with exactly one answer (two healers). The
        # difficulty here lives in the enemy kits, not the head count.
        "combat_squad_weights": {3: 18, 4: 40, 5: 42},
        "elite_squad_weights": {1: 18, 2: 40, 3: 42},
    },
}

DEFAULT_DIFFICULTY = REGION_DIFFICULTY["Glacier 15"]

def get_region_difficulty(region: str) -> dict:
    return REGION_DIFFICULTY.get(region, DEFAULT_DIFFICULTY)


# ----------------------------------------------------------------------
# Region progression gating: regions unlock in `tier` order. The lowest
# tier (Glacier 15) is always available; every other region requires the
# player to have COMPLETED (see ExpeditionStatus.COMPLETED --
# bot/services/dungeon_service.py's resolve_battle_end, set only when the
# FINAL boss of a run is defeated) an expedition in the region immediately
# below it in tier. Derived from REGION_DIFFICULTY's own `tier` values
# rather than a hardcoded chain, so adding a new region here is enough to
# slot it into the unlock order without touching the gating logic itself.
# ----------------------------------------------------------------------

def ordered_regions() -> list[str]:
    """Every region name, sorted easiest (lowest tier) to hardest."""
    return sorted(REGION_DIFFICULTY, key=lambda name: REGION_DIFFICULTY[name]["tier"])


def region_unlock_requirement(region: str) -> str | None:
    """The region that must be COMPLETED before `region` unlocks, or None
    if `region` is the lowest tier (always unlocked)."""
    order = ordered_regions()
    if region not in order or order.index(region) == 0:
        return None
    return order[order.index(region) - 1]