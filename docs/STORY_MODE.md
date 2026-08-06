# Story Mode — Design

*Design doc, not a spec of what's built. Written to be argued with before
any code exists.*

## The problem it solves

`/adventure` is not repetitive because runs are samey. There are 80
encounters, 118 enemy templates and a randomized graph. It's repetitive
because of three structural properties a generated dungeon can't escape:

1. **Nothing persists.** The world after run 50 is identical to the world
   after run 1. Only the player's numbers moved.
2. **It only serves itself.** Regions unlock by clearing the previous
   region, so the reward for adventuring is permission to adventure
   elsewhere. A closed loop with no outside.
3. **Nothing is authored.** Randomness produces variety but never
   *memory*. Nothing can be anticipated and no moment is about anything.

Story mode supplies exactly those three: **persistence, purpose,
authorship.**

The most important consequence is what it does to `/adventure` **without
changing a line of it**: once chapters gate region access, adventure
stops being the point and becomes preparation. A treadmill you're on for
a reason is not a treadmill.

## Shape

```
Chapter  →  Mission  →  Beat
```

A **beat** is the atom. Five kinds:

| Beat | What it does |
|---|---|
| `dialogue` | Authored text, a speaker, optional art. Continue button. |
| `choice` | 2–4 authored options. Sets flags. |
| `battle` | A fixed, named enemy list at a fixed level. Uses the existing battle engine. |
| `encounter` | Reuses an existing encounter by id, or an inline story-only one. |
| `reward` | Grants currency/items/characters. |

Beats carry optional `requires` / `unless` on flags, so a mission can
include or skip a beat based on what the player did earlier.

## The four decisions, settled

**Story gates progression.** Chapter completion unlocks the next region,
replacing `has_completed_region`. Adventure is where you get strong
enough for the next mission.

**Fully authored beats.** Every fight, line and choice is written. This
is the expensive answer and the only one that delivers the goal —
authored content *is* the product here.

**Persistent flags.** Choices set flags on `PlayerStory.flags`; later
beats read them to change dialogue, rewards, and occasionally whether a
beat happens at all. One storyline that remembers you, rather than N
storylines.

**Replayable at reduced rewards.** First clear pays in full and advances
the story. Replays pay a fraction — enough to re-fight a set-piece you
liked, never enough to make story the optimal farm.

## Chapters

Five chapters mapping onto the five regions, following the lore's own
spine (Glacier 15 cover-up → Ocellios → the regime → open war).

| # | Chapter | Region | Thread | Unlocks |
|---|---|---|---|---|
| 1 | **The Frozen Thread** | Glacier 15 | Josh, and an evacuation order that was never sent | The Wastelands |
| 2 | **Nothing to Report** | The Wastelands | The Daily Dolphe's shutdown; the people written off | The Hotlands |
| 3 | **Xendium** | The Hotlands | The supercomputer labs; Caliper's rogue Bt03 | Voidcrest Desert |
| 4 | **What Fell From Eris** | Voidcrest Desert | Void-matter, the rifts, Subject 29 | Abyssnia |
| 5 | **The Capital** | Abyssnia | Xender, and what Rohan is guarding | — (endgame) |

Named payoffs already planted in the lore and usable as reveals: **Rex**,
**Subject 29**, **Flux**.

4–6 missions per chapter, so roughly 25 missions total.

## What it reuses rather than rebuilds

This is why it's affordable:

- **The encounter interpreter.** `_apply_outcome` already resolves
  choices and rewards from data, and `tools/check_encounters.py` already
  validates them. Story choices are the same shape.
- **The battle engine.** `Battle` already takes an arbitrary enemy list,
  so an authored fight is a list of template names and a level.
- **Combat persistence.** Expeditions already serialize an in-progress
  battle; a story battle uses the same path.
- **The enemy roster.** Dorve, Rohan, the Josh Hater Army, Bt03 and
  Samuel were all built as set-pieces and have no authored home yet.
  Story mode is that home.

New code is small: a config module, one model, one service, one cog.

## Things that must not go wrong

**Existing players must not lose access.** Anyone who has already cleared
a region keeps it, permanently, regardless of story progress. The unlock
rule becomes "chapter cleared **OR** region already cleared" — never a
lockout for progress someone already made. This is the single highest-risk
detail in the whole feature.

**A mission in progress must survive a restart.** Same rule expeditions
follow: `PlayerStory` stores the active mission, the beat index, and any
serialized battle. Every interaction is load → mutate → save.

**Flags must be additive.** A flag that doesn't exist reads as false, so
adding a new flag never invalidates a save.

**Story must not become the farm.** Replay rewards are a fraction, and
story pays progression (region access, characters, one-off perks) rather
than volume currency.

## Settled: the overworld

Story mode is played on a **2D grid map**, not a linear beat list. You
move up/down/left/right one tile at a time and interact with what you're
standing on.

The map is the **container**; beats are the **contents of a tile**. Step
on an NPC tile and you get a dialogue/choice beat sequence; step on a
battle tile and you get an authored fight. The two models compose --
nothing about beats is wasted by adding the map.

Why a map rather than a list: a linear beat sequence is a visual novel.
A map makes the player choose a route, lets optional content exist off
the critical path, and creates spatial memory ("the terminal was north of
the bridge"). Flags do real structural work here too -- a door that stays
shut until you have the keycard makes the map a small puzzle instead of a
walk.

**Map size is variable per area** -- tight indoor maps stay small, open
ones can breathe.

### DENSITY IS THE THING THAT MATTERS

The failure mode of a grid map in a button UI is not size, it's
**sparseness**. Every step costs a Discord round-trip and returns
whatever is on the new tile; if that's usually nothing, movement is pure
friction. A small dense map beats a large interesting-in-places one every
single time.

Because size is variable, density can't be guaranteed by eye. It's
enforced: `tools/check_story.py` asserts that every area meets a minimum
fraction of non-empty tiles and that no walkable tile is more than one
step from something interactive. An area that fails is a design bug, not
a style preference.

Discord's component budget is not a constraint here -- 5 rows x 5 buttons
is 25 components and movement needs 5 (four directions plus interact).
Rendering is an emoji grid in the embed; past roughly 7 wide it starts
wrapping badly on mobile, which is the practical ceiling regardless of
what an area "wants".

## Settled: the prologue

New players do a hand-authored prologue before anything else unlocks.
This replaces `/start`'s current behaviour of granting 250 gold + 150
shards and exposing ~30 commands at once.

The prologue is not only onboarding -- it fixes **legibility**. A new
player's first decision is currently "which of thirty things do I press",
with no basis for choosing, which is why systems like the Forge and the
Research Lab go unnoticed for a long time. Meeting each system at the
moment you have a reason to care about it is strictly better than being
shown all of them at once.

**Unlock order:** combat -> gear -> one guided pull + squad -> `/adventure`.
Base, domains, raids, forge and lab arrive across Chapters 1-2.

**Existing players skip it.** Anyone already in the database is marked
prologue-complete by the migration, and every gate reads "prologue done
**OR** the player already has progress". Nobody loses access to something
they already had -- this is the same rule as region grandfathering and
carries the same risk if it's got wrong.

## Settled: tone and voice

**Serious, with dry humour.** The cover-up, the disappearances and the
resistance play straight; humour comes from characters rather than from
undercutting premises. The existing comedy encounters stay as texture in
`/adventure` -- they don't set the register for story mode.

**The avatar is silent** and speaks through choices. Avatars are
renameable and class-switchable, so writing lines for them means writing
lines for someone the player defined. Everyone else talks; the player
acts.

## Build order

1. ~~**Beat engine + `/story`**~~ -- DONE.
2. ~~**The prologue**~~ -- DONE.
3. ~~**The overworld**~~ -- DONE. `bot/game/story/map_config.py` (areas),
   `bot/services/map_service.py` (movement), map checks in
   `tools/check_story.py`. The map is the landing screen for `/story`;
   the chapter list moved to a Journal button.
4. **Chapters 1-5.** Chapter 1 (*The Frozen Thread*) is written: 5
   missions, 3 areas, and the last five gated features. Chapters 2-5
   are next.

## CANON (read this before writing a single line)

The lore PDFs in `docs/Detailed Official world lore/` are the source of
truth. An entire prologue and chapter were written before they were
read, and had to be thrown away. Do not repeat that.

**Facts that were got wrong the first time:**

- **Dolphe is HE.** File C-000. An earlier draft used "she" in every
  scene he appeared in.
- **Josh speaks in broken English.** Canon, not characterisation: *"Im
  just try to live, but people say it bad."* An earlier draft wrote him
  fluent and clipped, which quietly turned the roster's most distinctive
  character into a generic soldier.
- **Josh's motive is Rex.** He is driven by "the debt of Rex's death".
  Rex is dead before the game starts.
- **Dolphe News became Team Cascade in 107 IC**, right after Glacier 15.
  There is no newspaper left to be recruited into by 109 IC.
- **The Player is canonically a cat** — "a self-insert, a cat icon with
  player colors". The map marker was already 🐱 by luck.
- **The Player** resonates with electricity and void matter, foresees
  and parries attacks, and is *extremely fragile* — 1-2 hits.

**The canon opening (Jul 26, 109 IC):** the Player wakes in Ocellios Lab
mid-collapse with Stubby's mechs hacked hostile, neutralises them with
electricity, escapes east into Glacier 15, survives by powering **heat
beacons**, is intercepted by **Nebula and Gostley** (sent by Dolphe to
investigate an anomaly on Cascade's radar — the anomaly is the Player),
narrowly escapes a **mechanical worm**, and joins Team Cascade at their
forward base.

## The arc: Rohan

Rohan — **Mr. R** — is the primary antagonist, and this is a deliberate
divergence: he appears nowhere in the PDFs, where the spine is Xender vs
HHyper. In the bot he was the Abyssnia endgame boss and a comedy fruit
vendor who hates Josh and Rex. The story mode promotes him.

Xender stays as **political backdrop** — real, dangerous, and not what
the story is about. The personal line is Player / Josh / Rohan, with Rex
as the debt underneath it.

**Rohan is not seen in Chapter 1.** He is established by what he can
afford to abandon: a boss-tier driller cut in one pass and signed with a
single letter, nineteen Xender survey teams that went in and never filed
out, and an Eris-frame Guardian he *found* rather than built. He is
named only at the end, and by Josh, who has been calling it in for two
years and being told he was grieving.

### Every feature now has a real unlock beat

13/13. The prologue opens 8 (inventory, quests, pull, squad, adventure,
base, daily, domains); Chapter 1 opens the remaining 5 (gifting and the
Echo Exchange on the flight north, the Forge at the workshop, the
Research Lab at the reveal, raids under the chapter boss).

Raids specifically wait until C1M5 because that is the first thing in
the story a squad of four demonstrably cannot finish. Handing someone a
co-op system in a safehouse is a menu tour; handing it to them under a
thing that just walked through a wall is an argument.

This means the "no unlock beat -> opens at prologue end" fallback in
story_service is now dead code in practice. It stays, because the next
chapter will add features before it adds the missions that grant them.

### Missions run once

Story rewards are fixed and authored, and story fights are tuned to be
winnable, so a replayable mission is strictly the best farm in the game
and hollows out the mode. Refused in `start_mission` and surfaced early
by the map tile. Repeatable content is expeditions, domains and raids.

### Combat tuning is simulated, never guessed

Chapter 1's fights were authored by eye and all three were wrong -- the
opener won 100% at every squad level from 5 to 25, and the boss was 0%
winnable at every level tested. The lesson that came out of the sweep is
that difficulty in this engine is driven by **composition**, not level:
three Recon Scouts are free at level 15, while a lone Permafrost
Guardian is a wall at level 5. Final numbers, measured over 80 seeded
fights per cell:

**Enemy TIER is a hard wall, not a curve.** Measured base HP: a
`combat` template is 40-58, an `elite` is 200, a `boss` is 520. A
two-character party at level 1-8 beats *every* combat template at 100%
and *no* elite or boss at any level. There is no amount of level tuning
that bridges that, so an early fight must use combat-tier enemies —
full stop.

That killed the prologue's worm as a fight. Canon says the Player
*narrowly escapes* it, and the engine agrees, so the worm is now the
hazard and its two minders are the encounter. It returns as a boss later,
when a squad can actually meet it.

| fight | party | result |
|---|---|---|
| PR1 Rogue Security Drone (lv2) | 1 char, lv1 | 100% |
| PR5 Concussion Drone + Recon Scout (lv3) | 2 chars, lv1 | 98% |
| C1M2 Tank + 2 Henchmen (lv4) | 4 chars | 47% @10, 78% @12, 100% @15 |
| C1M5 Permafrost Guardian, alone (lv11) | 4 chars | 17% @10, 40% @15, 75% @20 |

The C1M5 boss lost its two escorts along the way. It reads better as well
as playing better: one enormous thing that came through a wall is a boss,
one enormous thing with two blocks of ice is a patrol.

Each stage is independently playable. The container/contents split held:
converting the prologue onto the map changed zero beats.

### What stage 3 changed about the prologue

Two things came out of playing stages 1-2, and both are worth recording
because they were invisible on paper:

**The prologue no longer gifts Josh.** It grants 480 Shards (four pulls)
and unlocks `/pull`, and the player brings whoever answers. Gifting the
squadmate removed the softlock but also removed the tutorial -- being
handed the reward for a mechanic is a reliable way never to learn the
mechanic. The softlock guard moved to the lane door, which won't open
below two characters (`requires_characters` in map_config). Safe because
the avatar is excluded from the gacha pool, so a player who owns only
their avatar *cannot* roll a duplicate: the first pull is always somebody
new.

P4 was re-simulated against all 29 possible partners at level 1 and
dropped from enemy level 4 to 3 -- at 4 the worst partner won 70% and
four fell below 90%; at 3 the mean is 99%.

**Features with no unlock beat are no longer open by default.** They now
wait for the end of the prologue. The old default was correct when the
prologue was the only content and wrong the moment anyone played it: a
player who had just been handed their inventory in mission 2 could open
the HQ, the shop, the Forge and the Research Lab, none of which the story
had introduced. Six cogs also never called `require_feature` at all.
`tools/check_runtime.py` now asserts every command is gated or listed in
`UNGATED_COMMANDS` with a written reason, because forgetting the gate on
a new command fails silently.

## Open questions

- **Chapter length.** 4–6 missions each is still a guess. Shorter
  chapters mean more frequent payoffs; longer ones mean weightier ones.
  Worth revisiting once Chapter 1 is playable rather than deciding now.


## Adventure rebalance (driven by the prologue)

The prologue now delivers a **level 1-5 squad with one Uncommon item**
into Glacier 15. That exposed balance problems that predate story mode
and were invisible until somebody measured the region a beginner
actually lands in.

**Per-fight win rates are misleading here.** HP carries between fights
inside a run, so Glacier 15 measured 98-100% per combat room and **32%
per run** — you win every fight and still die of accumulated attrition.
Anything tuned off single fights is wrong in the same direction.
`tools/sim_expedition.py` models whole runs: 9 floors, weighted room
types, the forced pre-boss campfire, revive-to-1-HP between fights.

**The ladder was inverted.** Final-boss HP ran 700 → 420 → 950 → 1050 →
1500. Glacier's capstone was two thirds bigger than the region *after*
it, and since a region only unlocks by clearing the previous one, the
first rung gated the whole game. Every number inside Glacier's own config
looked fine; the bug only existed *between* regions, which nothing
compared.

Changes, all data-only:

| change | why |
|---|---|
| Void Hydra 700 → 380 HP | Glacier's capstone, entered at level 1-5. Still the hardest thing in the region by a distance (regular bosses cap at 300). |
| Driller (520) and Corrupted Bli (420) out of Glacier's regular pool | They sat beside 270-300 HP bosses, so the *draw* decided the run. Both keep every later region. |
| Loona (170) out of The Hotlands | Same failure: a 3.1x spread against the 520 Driller. |

Glacier 15 full-run clear rate went **3% → 28% at squad level 1** and
**16% → 62% at level 5**, reaching 100% by level 20 — a first region that
asks you to grow rather than one that refuses you.

`tools/check_progression.py` now asserts the ladder rises and that no
boss pool is a coin flip. It caught the Hotlands case immediately.

### Harder regions, funded by the story

Difficulty was raised across tiers 1-4 and the story was made to pay for
it. Doing either alone would have been a regression: harder regions with
the old rewards is a wall, and better rewards with the old regions is a
walkover.

**Gear had to go into the simulator first.** Every earlier reading was
taken naked, which is a floor nobody plays at, and it inverted the
conclusion — Glacier 15 read as brutally hard naked and 100% clear with
gear. `tools/sim_expedition.py` now equips a squad and takes rarity and
item level as parameters.

**The story now kits you out.** The prologue grants 5 items (2 Uncommon,
3 Rare) and Chapter 1 four more (2 Rare, 2 Epic), so a player reaches
`/adventure` with a full five-slot kit rather than the single Uncommon
they used to get. Measured handoff into Glacier 15:

| squad level | naked | with the story's kit |
|---|---|---|
| 3 | 8% | 32% |
| 5 | 18% | 40% |
| 8 | 30% | 64% |
| 18 | 68% | 88% |

**New offsets**, measured at the level and gear each region is actually
reached:

| region | was | now | clear at entry |
|---|---|---|---|
| Glacier 15 | 2 / 0 | 8 / 5 | 82% -> 62% |
| The Wastelands | 10 / 7 | 22 / 18 | 98% -> 82% |
| The Hotlands | 20 / 15 | 24 / 19 | 75% -> 57% |
| Voidcrest Desert | 35 / 25 | 38 / 28 | 72% -> 70% |
| Abyssnia | 48 / 35 | 42 / 30 | 18% -> 32% (lv100) |

**Abyssnia went the other way, on purpose.** At 18% fully geared it was
not a hard region, it was a closed door — raising it "across the board"
would have made the endgame unreachable rather than difficult. It now
measures 14% at level 70 and 32% at 100 with Legendary gear, and the sim
models neither Mythic/Divine gear nor Resonance, so real endgame players
sit above that.

### Resolved: the multi-boss capstone scare

An earlier pass recorded that capstones could roll a 2,656 HP four-body
group and concluded deep regions were unclearable. Half right. Boss
GROUPS are real (`BOSS_GROUP_CHANCE = 0.2`) and The Wastelands can roll
NF + Ocellios Train + Broskm + Duko, but Abyssnia's capstone is a solo
1,500 HP Xender in 100% of rolls — the earlier 0% reading was
small-sample noise at 40 runs, not a group problem. At 120 runs it is
14%. Sample size, not mechanics.

### Historical note: the original multi-boss diagnosis

`get_boss_encounter(final=True)` can return a **group**. The Wastelands
capstone rolled NF + Ocellios Train + Broskm + Duko — **2,656 HP across
four bodies**, which no squad clears without gear at any level tested.
That is why regions past Glacier still read near-0% above.

This is a real pre-existing problem and it deserves its own pass rather
than a guess. One change was made on a wrong diagnosis during this work
(NF 420 → 560, on the theory that the capstone ladder needed raising)
and was **reverted** once the group encounter turned out to be the actual
wall. Deeper regions should be re-measured *with gear modelled* before
anything else is touched.


## Chapter 2: Two Hundred Crates

Five missions, two areas (The Wastelands line, Entrospire Underside), and
**no feature unlocks** — everything is open by the end of Chapter 1, which
frees Chapter 2 to be about people instead of menus. That is the pacing
working, not a gap in it.

The turn: the two hundred sealed crates leaving Glacier 15 are **ballast**.
Rohan ran a two-year decoy because two hundred crates leaving a dead city
in daylight is the story any journalist would chase — he built Dolphe a
headline and pointed it away from wherever the people actually went.

**Rohan appears in person** and does not fight you. He sits on a crate,
gestures at one thing, watches you kill it, and applauds. He leaves the
north gate key behind on purpose. The scene works because he does not
consider it an engagement — and he lets slip "Ocellios put you in the
frame", which means he knows what the Player is and Team Cascade doesn't.

Chary carries the chapter's read on him: she dealt to him years ago and
he was the worst player she ever sat across from, not because he was bad
at cards but because he could not accept that the deck didn't owe him.

### Combat notes

The Lector of Ledgers shipped with a Xender Convoy escort at level 18 and
measured **0% at every squad level tested** — the same mistake Chapter 1's
Permafrost Guardian taught: an elite or boss template is already harder
than most three-enemy groups, so an escort is not difficulty, it is
unwinnability. Alone at level 12 it runs 60% at squad 22 and 82% at 25.

**A caveat on these numbers.** Repeated runs of the fight simulator
disagreed with each other on the same inputs (one pass read c2m5 at 40%
where another read 0%), which is why the escort was removed on the finding
both passes agreed on rather than tuned against a single reading. The
partner squad is randomly sampled per seed, so small sample counts move a
lot. Treat any single-fight percentage under ~50 samples as directional.


## Sustain is mandatory now (measured)

Players were dropping dedicated healers and shielders for healing GEAR.
`tools/bench_healers.py` showed exactly why: a squad with **no Sustain at
all** still won 46% of fights, so the class was optional and a trinket
was a fine substitute.

Two changes, both measured rather than guessed:

**Enemies hit 1.5x harder** (`factory.ENEMY_ATTACK_MULTIPLIER`). A sweep
across attack and HP multipliers found this is the shape where a Sustain
stops being a preference: at 1.5x a no-Sustain squad wins **0%** while a
squad with a healer or shielder still wins ~54%. Raising enemy HP instead
did nothing useful -- every squad hit the 40-cycle stalemate and lost.

**Healing scales off the HEALER now**, via two new effect kinds,
`heal_from_stat` and `team_heal_from_stat`. Every heal used to be "% of
the TARGET's max HP", which is precisely why gear could replace a healer:
the person casting it changed nothing about the result.

| healer | scales off |
|---|---|
| Lily Lovelace | max HP (25% single / 17% team) |
| Aura | elemental |
| Refender | defense |
| Evz | percent (kept, as a gear-independent floor) |
| Kotori | percent, sacrificial |

**A calibration trap worth remembering.** DEF and ELE sit around 30-45 at
level 70 while max HP is ~620, so a stat-scaling heal needs a percentage
roughly 10-20x larger than a max-HP one to restore the same amount. The
first pass used percentages that looked sane and healed 6% of a bar --
Aura measured *worse than bringing nobody* (17% vs 46%). Corrected, she
is 90%.

**The whole region ladder was re-cut** after the attack change, because
1.5x damage invalidated every difficulty number at a stroke (Glacier 15
fell from 62% to 6% at squad 5). Offsets are now 3/1, 13/10, 16/12,
26/19, 30/22. With gear, at the level each region is actually reached:
Glacier 92%, Wastelands 80%, Hotlands 70%, Voidcrest 32%, Abyssnia 8%.

### Healers brought up to shielders

Shielders initially out-performed healers badly (53%/37% vs 3-20%),
because a shield is PRE-EMPTIVE and a heal is REACTIVE -- burst kills
before a heal can answer it. Raising every healer's output ~1.6x closed
it, which means the gap was magnitude rather than shape:

| Sustain | win% |
|---|---|
| NO Sustain | 7% |
| Jofrog (shield) | 57% |
| Evz (percent) | 53% |
| Aura (ELE) | 47% |
| Bee Jee (shield) | 43% |
| Kotori (blood) | 40% |
| Lily (max HP) | 37% |
| Refender (DEF) | 27% |

Two individual fixes fell out of the same measurement:

* **Kotori** pays HP to heal, which was survivable before enemies hit
  1.5x harder and afterwards had her killing herself to keep others up
  (7%). Self-cost halved -- she still pays, the payment is no longer
  lethal.
* **Evz** measured at exactly the no-Sustain rate. Her ultimate was a
  pure DEF buff: on the class contract, but it keeps nobody alive. It is
  now a team heal with the brace riding on it, which also suits "a
  trauma surgeon who traded scalpels for throttle levers".

The region ladder was re-checked afterwards -- stronger healers move it
too -- and The Wastelands went to 18/14 because at 13/10 it measured
*easier* than Glacier 15 before it (98% vs 68%). With gear at the entry
level: Glacier 60%, Wastelands 82%, Hotlands 60%, Voidcrest 68%,
Abyssnia 12%.


## The "crit dominance" was never crit

One strategy -- three supports stacking buffs on one carry -- measured
2.4x the damage of every alternative. It was called crit stacking, and
crit buffs were nerfed twice with **no measurable effect**, because the
diagnosis was wrong.

Measured directly: applying the entire support package to Star moved his
crit rate from **5% to 7%**. Crit BASE is 5 and buffs are a percentage of
base, so a "+30% crit rate" buff is worth +1.5 points. His ATTACK went
**68 -> 106**. The thing doing the work was always ATK, and every round
spent tuning crit was spent on the wrong number.

**Fix: diminishing returns on stacked positive buffs to the same stat**
(`combatant.BUFF_STACK_FALLOFF = 0.65`). The Nth buff counts 100%, 65%,
42%, 27%... so a second ATK buffer is still good, a third is marginal,
and a fourth is a wasted slot. Chosen over a hard cap, which would make
the second buffer worthless rather than merely weaker.

Two exemptions, both load-bearing:

* **Debuffs stack in full.** DEF shred is one of the strategies this is
  meant to make competitive; taxing it here would undo the fix while
  applying it.
* **DEF and max HP are exempt.** The first version taxed them too and
  knocked every Sustain down with the carry (Bee Jee 43% -> 13%, Kotori
  40% -> 7%), undoing the healer work. The problem is stacked OFFENCE.

Result: strategy spread **2.4x -> 1.6x**, with the alternatives moving
from 42-45% of the best comp to 61-64%.

### Caveat

Overall player power is now lower than when the region ladder was last
cut, and the geared clear rates have drifted (Hotlands ~38% at entry).
The ladder wants one more compensating pass against the post-falloff
numbers.
