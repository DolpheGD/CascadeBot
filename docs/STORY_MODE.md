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
4. **Chapters 1-5.** <- next

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
