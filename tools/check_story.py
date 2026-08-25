"""
Validate the whole story script without running it.

    python -m tools.check_story

Story content has the same property that made `tools/check_encounters.py`
necessary: it's pure data resolved by a generic interpreter, so a typo
doesn't fail at import or startup. It fails when a player reaches that
one beat -- which for a story mission might be the fourth mission of a
chapter, twenty minutes in, and the failure is a dead button in the
middle of a scripted scene.

Checked:

  * ids unique across every chapter, and every mission reachable
  * every beat has the keys its `kind` needs
  * every enemy name in a battle beat exists in the roster
  * every reward key is a real currency or a valid item rarity
  * every `unlock` names a real feature, and every feature that IS
    gated has exactly one unlock beat somewhere
  * every flag read by `requires`/`unless` is written by some choice --
    a beat gated on a flag nobody sets can never appear
  * a mission cannot be empty, and cannot end on a `choice` (the player
    would pick an option and see nothing happen)

Map density checks land here too once areas exist -- see
docs/STORY_MODE.md.
"""

from __future__ import annotations

import sys

BEAT_KINDS = {"dialogue", "choice", "battle", "encounter", "reward", "unlock",
              "puzzle"}

# Beat keys whose value is shown to the player as prose. Every one of
# them must be a STRING.
#
# This exists because of a one-character bug: a trailing comma after a
# parenthesised multi-line string makes it a TUPLE, and Python is
# perfectly happy with that. The beat still loads, every other check
# still passes, and the player is shown ("Twenty-four volumes...",) --
# brackets, quotes and all. Invisible in a diff, invisible at import,
# and only visible on the one screen it ruins.
TEXT_KEYS = ("text", "intro", "prompt", "on_win", "on_lose", "summary", "label")


def _check_maps() -> list[str]:
    """Validate every overworld area.

    The density rules here are the load-bearing ones. A grid map in a
    button UI does not fail by being too big, it fails by being SPARSE:
    every step costs a Discord round-trip, so a step that usually returns
    nothing is pure friction, and that gets worse the more room you have
    to wander. Density can't be eyeballed once areas vary in size, so it
    is asserted -- an area that fails is a design bug, not a preference.

    Also checked, in rough order of how badly each one ruins a session:

      * reachability -- content walled off from the spawn is content
        nobody will ever see, and it looks completely fine in the source
      * exits that land in a wall or a nonexistent area
      * lock ordering -- a tile requiring a mission that can only be
        started BEYOND that tile is a softlock, and the prologue is
        exactly where a softlock is unrecoverable
      * every mission in story_config placed on exactly one tile
      * glyph width, including variation selectors, which shear a column
        on mobile without looking wrong in an editor
    """
    from collections import deque

    from bot.game.story import map_config as mc
    from bot.game.story import story_config as sc

    from bot.database.models.enums import Rarity
    from bot.game.combat.enemies import ENEMY_TEMPLATES
    from bot.services.currency_service import VALID_CURRENCIES

    enemy_names = {t["name"] for t in ENEMY_TEMPLATES}
    rarities = {r.value for r in Rarity}
    failures: list[str] = []
    placed: dict[str, list[str]] = {}

    from bot.game.economy.lootbox_config import LOOTBOX_TEMPLATES
    lootbox_tiers = {t["tier"] for t in LOOTBOX_TEMPLATES}

    def check_grant(where: str, grant: dict) -> None:
        """Map rewards use the same block shape as story rewards, so they
        get the same validation -- a typo'd currency on a cache is exactly
        as invisible as one on a mission."""
        for key, value in (grant or {}).items():
            if key == "item":
                if value not in rarities:
                    failures.append(f"{where}: item rarity {value!r} does not exist")
            elif key == "character":
                continue
            elif key == "lootbox":
                # "epic", or ("epic", 3) for a stack.
                tier = value[0] if isinstance(value, (list, tuple)) else value
                if tier not in lootbox_tiers:
                    failures.append(
                        f"{where}: lootbox tier {tier!r} does not exist "
                        f"(have: {', '.join(sorted(lootbox_tiers))})"
                    )
            elif key == "xp":
                if not isinstance(value, int) or value <= 0:
                    failures.append(f"{where}: xp must be a positive int")
            elif key not in VALID_CURRENCIES:
                failures.append(f"{where}: '{key}' is not a currency or 'xp'")

    for area_id, area in mc.AREAS.items():
        grid = area.get("grid") or []
        if not grid:
            failures.append(f"area '{area_id}': no grid")
            continue

        width, height = mc.area_size(area)
        if width > mc.MAX_WIDTH or height > mc.MAX_HEIGHT:
            failures.append(
                f"area '{area_id}': {width}x{height} exceeds "
                f"{mc.MAX_WIDTH}x{mc.MAX_HEIGHT} (wraps on mobile)"
            )
        if len({len(row) for row in grid}) != 1:
            failures.append(f"area '{area_id}': rows are not all the same length")

        # The rendered grid goes into ONE embed field, and Discord
        # truncates a field over 1024 characters without complaining --
        # which on a map means invisible walls rather than a visible
        # error. Measured against the widest glyph any tile can draw.
        widest = max(
            [len(mc.EMOJI_WALL), len(mc.EMOJI_FLOOR), len(mc.EMOJI_PLAYER),
             len(mc.EMOJI_DONE), len(mc.EMOJI_LOCKED)]
            + [len(e.get("emoji", "")) for e in (area.get("legend") or {}).values()]
        )
        rendered = height * (width * widest + 1)
        if rendered > mc.MAX_FIELD_CHARS:
            failures.append(
                f"area '{area_id}': renders to ~{rendered} chars, over Discord's "
                f"{mc.MAX_FIELD_CHARS}-char field limit -- it would be silently truncated"
            )

        # ROOM SIZE. Small connected rooms beat a few big halls: easier to
        # read on a phone, and a journey through named places is what the
        # story actually is.
        walkable_count = len(mc.walkable_tiles(area))
        if walkable_count > mc.MAX_ROOM_TILES:
            failures.append(
                f"area '{area_id}': {walkable_count} walkable tiles (max "
                f"{mc.MAX_ROOM_TILES}) -- split it into connected rooms"
            )
        if not area.get("region"):
            failures.append(
                f"area '{area_id}': no `region` -- every room states where it is, so the "
                f"player always knows both the place and the part of the world it's in"
            )

        # Spawn
        spawns = sum(row.count(mc.SPAWN_CHAR) for row in grid)
        if spawns != 1:
            failures.append(f"area '{area_id}': {spawns} spawn tiles (needs exactly 1)")

        # Legend <-> grid agreement, both directions.
        used = {
            char for row in grid for char in row
            if char not in (mc.WALL_CHAR, mc.FLOOR_CHAR, mc.SPAWN_CHAR)
        }
        legend = area.get("legend") or {}
        for char in sorted(used - set(legend)):
            failures.append(f"area '{area_id}': '{char}' is on the grid with no legend entry")
        for char in sorted(set(legend) - used):
            failures.append(f"area '{area_id}': legend has '{char}', which is on no tile")
        for char in sorted(used):
            # DECORATION IS EXEMPT, and is the one kind that should be.
            # The rule exists because reusing 'D' for two NPCs would give
            # them the same dialogue silently -- but scenery has no
            # dialogue, no state and no interaction, so one 'i' standing
            # for every block of ice in the room is exactly the point.
            if (legend.get(char) or {}).get("kind") == "decor":
                continue
            count = sum(row.count(char) for row in grid)
            if count > 1:
                failures.append(
                    f"area '{area_id}': '{char}' appears {count} times -- one legend "
                    f"entry cannot describe two different tiles"
                )

        # Contents
        bonus = area.get("completion_bonus")
        if bonus:
            check_grant(f"area '{area_id}' completion_bonus", bonus)

        for char, content in legend.items():
            where = f"area '{area_id}' tile '{char}'"
            kind = content.get("kind")
            emoji = content.get("emoji", "")
            if "️" in emoji:
                failures.append(
                    f"{where}: emoji {emoji!r} contains a variation selector, which "
                    f"renders narrow and shears the column on mobile"
                )
            if kind == "decor":
                # Scenery: drawn and solid, never listed, never stood on
                # (see map_config.is_decor). It needs an emoji and
                # nothing else -- a name would have nowhere to appear.
                if not emoji:
                    failures.append(f"{where}: decoration with no emoji draws as nothing")
                continue
            if not content.get("name"):
                failures.append(f"{where}: no name")

            if kind == "mission":
                mission_id = content.get("mission")
                if sc.get_mission(mission_id) is None:
                    failures.append(f"{where}: no mission named {mission_id!r}")
                else:
                    placed.setdefault(mission_id, []).append(f"{area_id}/{char}")
            elif kind == "note":
                if not content.get("text"):
                    failures.append(f"{where}: note with no text")
            elif kind == "station":
                # A tile that opens a real panel (Forge, HQ, squad...).
                # Both keys matter: `panel` is what opens, `feature` is
                # the story gate, and a station with no gate would let a
                # player walk into the Research Lab before the story has
                # mentioned it exists.
                if not content.get("panel"):
                    failures.append(f"{where}: station with no panel to open")
                elif content["panel"] not in STATION_PANELS:
                    failures.append(
                        f"{where}: unknown panel {content['panel']!r} "
                        f"(have: {', '.join(sorted(STATION_PANELS))})"
                    )
                feature = content.get("feature")
                if not feature:
                    failures.append(f"{where}: station with no feature gate")
                elif feature not in sc.FEATURES:
                    failures.append(f"{where}: gates on unknown feature {feature!r}")
            elif kind == "npc":
                # An NPC's whole point is having more than one thing to
                # say, so an empty `lines` list is the same bug as a note
                # with no text -- a person you can walk up to and get
                # nothing from.
                lines_ = content.get("lines") or []
                if not lines_:
                    failures.append(f"{where}: npc with no lines")
                for i, line in enumerate(lines_):
                    if not line.get("text"):
                        failures.append(f"{where}: npc line {i} has no text")
                    if line.get("requires_flag") and line.get("unless_flag"):
                        failures.append(
                            f"{where}: npc line {i} has both requires_flag and "
                            f"unless_flag -- say which one you meant"
                        )
                if not content.get("repeat"):
                    # Not fatal, but worth saying: without it they fall
                    # back to a generic line once exhausted.
                    pass
            elif kind == "cache":
                if not content.get("grant"):
                    failures.append(f"{where}: cache with nothing in it")
                check_grant(where, content.get("grant") or {})
            elif kind == "hunt":
                enemies = content.get("enemies") or []
                if not enemies:
                    failures.append(f"{where}: hunt with no enemies")
                if len(enemies) > 5:
                    failures.append(f"{where}: {len(enemies)} enemies (engine allows 5)")
                for enemy in enemies:
                    if enemy not in enemy_names:
                        failures.append(f"{where}: no enemy template named {enemy!r}")
                if not isinstance(content.get("level"), int):
                    failures.append(f"{where}: hunt needs an integer level")
                if not content.get("grant"):
                    failures.append(
                        f"{where}: hunt with no reward -- an optional fight that pays "
                        f"nothing is a trap, not a choice"
                    )
                check_grant(where, content.get("grant") or {})
                if "Optional" not in (content.get("text") or ""):
                    failures.append(
                        f"{where}: hunt text must tell the player it's OPTIONAL and that "
                        f"losing is free, or it reads as required content they can fail"
                    )
            elif kind == "puzzle":
                # The puzzle's own validation (solvable, failable,
                # derivable from clues) lives in tools/check_puzzles.py,
                # which calls the real solver. Here we only assert the
                # things that make it a valid TILE.
                from bot.game.story.puzzles import PUZZLE_KINDS, kind_of
                if kind_of(content) not in PUZZLE_KINDS:
                    failures.append(
                        f"{where}: puzzle_kind {kind_of(content)!r} is not one of "
                        f"{PUZZLE_KINDS}")
                if not content.get("grant"):
                    failures.append(f"{where}: puzzle with no reward")
                check_grant(where, content.get("grant") or {})
            elif kind == "board":
                # The commission board. It carries no grant and no
                # mission -- everything it offers comes from
                # quest_config.COMMISSIONS, which tools/check_commissions.py
                # validates. All that matters here is that it reads as a
                # thing worth walking to.
                if not content.get("text"):
                    failures.append(f"{where}: board with no text")
            elif kind == "exit":
                target = content.get("to_area")
                destination = mc.AREAS.get(target)
                if destination is None:
                    failures.append(f"{where}: exits to unknown area {target!r}")
                else:
                    tx, ty = content.get("to", [None, None])
                    if not isinstance(tx, int) or not isinstance(ty, int):
                        failures.append(f"{where}: exit has no integer [x, y]")
                    elif mc.is_wall(destination, tx, ty):
                        failures.append(f"{where}: exit lands inside a wall at ({tx}, {ty})")
            else:
                failures.append(f"{where}: unknown tile kind {kind!r}")

            needed = content.get("requires_mission")
            if needed and sc.get_mission(needed) is None:
                failures.append(f"{where}: requires unknown mission {needed!r}")

            roster = content.get("requires_characters")
            if roster is not None and (not isinstance(roster, int) or roster < 1):
                failures.append(f"{where}: requires_characters must be a positive int")

            if (needed or roster) and not content.get("locked_text"):
                failures.append(
                    f"{where}: locked with no locked_text -- a door that won't say what "
                    f"opens it is a bug report waiting to happen"
                )

        # Reachability from the spawn, by orthogonal walking.
        walkable = set(mc.walkable_tiles(area))
        spawn = mc.spawn_of(area)
        seen = {spawn}
        queue = deque([spawn])
        while queue:
            x, y = queue.popleft()
            for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
                nxt = (x + dx, y + dy)
                if nxt in walkable and nxt not in seen:
                    seen.add(nxt)
                    queue.append(nxt)
        for x, y in sorted(walkable - seen):
            char = mc.tile_char(area, x, y)
            failures.append(
                f"area '{area_id}': ({x}, {y}) [{char}] is walled off from the spawn"
            )

        # DENSITY. Both halves of the rule.
        content_tiles = [
            (x, y) for (x, y) in walkable if mc.tile_content(area, x, y) is not None
        ]
        if walkable:
            density = len(content_tiles) / len(walkable)
            if density < mc.MIN_DENSITY:
                failures.append(
                    f"area '{area_id}': density {density:.0%} is below "
                    f"{mc.MIN_DENSITY:.0%} ({len(content_tiles)}/{len(walkable)} tiles do "
                    f"something) -- the map is mostly walking"
                )

        if content_tiles:
            # Multi-source BFS out from every interactive tile at once:
            # the distance that matters is to the NEAREST one.
            distance = {tile: 0 for tile in content_tiles}
            queue = deque(content_tiles)
            while queue:
                x, y = queue.popleft()
                for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
                    nxt = (x + dx, y + dy)
                    if nxt in walkable and nxt not in distance:
                        distance[nxt] = distance[(x, y)] + 1
                        queue.append(nxt)
            for tile in sorted(walkable):
                steps = distance.get(tile)
                if steps is None or steps > mc.MAX_DISTANCE_TO_CONTENT:
                    failures.append(
                        f"area '{area_id}': {tile} is {steps if steps is not None else 'infinitely'}"
                        f" steps from anything interactive (max {mc.MAX_DISTANCE_TO_CONTENT})"
                    )

    # Every mission placed exactly once.
    for mission in sc.all_missions():
        where = placed.get(mission["id"], [])
        if not where:
            failures.append(
                f"mission '{mission['id']}' is on no tile -- unreachable now that the "
                f"overworld is the way in"
            )
        elif len(where) > 1:
            failures.append(f"mission '{mission['id']}' is on {len(where)} tiles: {where}")

    # LOCK ORDERING. A tile gated behind a mission that lives further
    # along the same one-way path is a softlock; in the prologue it's an
    # unrecoverable one, since there's nothing else to go and do.
    reachable_missions: set[str] = set()
    frontier = [mc.STARTING_AREA]
    open_areas: set[str] = set()
    progressed = True
    while progressed:
        progressed = False
        for area_id in list(frontier):
            if area_id in open_areas:
                continue
            area = mc.AREAS.get(area_id)
            if area is None:
                continue
            open_areas.add(area_id)
            progressed = True
        for area_id in list(open_areas):
            for content in (mc.AREAS[area_id].get("legend") or {}).values():
                needed = content.get("requires_mission")
                if needed and needed not in reachable_missions:
                    continue
                if content.get("kind") == "mission":
                    if content["mission"] not in reachable_missions:
                        reachable_missions.add(content["mission"])
                        progressed = True
                elif content.get("kind") == "exit":
                    target = content.get("to_area")
                    if target in mc.AREAS and target not in open_areas:
                        frontier.append(target)
                        progressed = True

    for mission in sc.all_missions():
        if placed.get(mission["id"]) and mission["id"] not in reachable_missions:
            failures.append(
                f"mission '{mission['id']}' can never be started -- its tile, or the area "
                f"holding it, is locked behind a mission that isn't reachable first"
            )

    total_tiles = sum(len(mc.walkable_tiles(a)) for a in mc.AREAS.values())
    interactive = sum(
        1 for a in mc.AREAS.values() for (x, y) in mc.walkable_tiles(a)
        if mc.tile_content(a, x, y) is not None
    )
    print(f"areas    : {len(mc.AREAS)}")
    print(f"tiles    : {total_tiles} walkable, {interactive} interactive "
          f"({interactive / total_tiles:.0%} density)" if total_tiles else "tiles    : 0")
    return failures


# ----------------------------------------------------------------------
# HOW MANY CHARACTERS DOES THE PLAYER ACTUALLY HAVE?
#
# The climax check below simulates every fight against a FABRICATED party
# of four, which is right for a chapter and catastrophically wrong for a
# prologue: for the first three missions the player has ONE level-1
# character, because /pull hasn't been unlocked yet.
#
# That gap shipped an unwinnable game. The prologue's second fight was
# two enemies at level 3 against a solo level-2 avatar -- measured at a
# 0% win rate over 60 runs -- and the checker reported it as costing "2%"
# of a squad's health, because it was pricing a party that did not exist.
#
# So the prologue is measured against the roster the script itself hands
# out: count the `character` grants and `pull` unlocks that happen BEFORE
# each fight, and assume a player who has pulled once per 120 shards
# granted. Anything the story hasn't given you yet, you don't have.
# ----------------------------------------------------------------------
SHARDS_PER_PULL = 120


def _roster_before(missions: list[dict], upto_mission: str, upto_beat: int) -> tuple[int, int]:
    """(characters, rough level) the player holds at that point."""
    characters = 1        # the avatar, granted by /start
    shards = 0
    fights = 0
    for mission in missions:
        for index, beat in enumerate(mission["beats"]):
            if mission["id"] == upto_mission and index >= upto_beat:
                break
            grant = beat.get("grant") or {}
            if grant.get("character"):
                characters += 1
            shards += int(grant.get("shards", 0) or 0)
            if beat.get("kind") == "battle":
                fights += 1
        if mission["id"] == upto_mission:
            break
    characters += shards // SHARDS_PER_PULL
    # Levels come from fights, roughly one per two won.
    return characters, 1 + fights // 2


def _level_from_story_xp(through_chapter_id: str) -> int:
    """The character level a story-only player has by the END of a
    chapter, from the XP the story has actually granted them.

    This is the anchor the whole difficulty model hangs off, and it
    exists because the previous anchor was circular -- squad level was
    derived from the enemy levels, so making a fight harder also made the
    player stronger and the fight measured easier.

    Uses the game's own curve (character_model.XP_BASE / XP_GROWTH), and
    counts XP the way apply_character_xp actually pays it: every squad
    member receives the full grant, not a share of it.
    """
    from bot.game.story import story_config as sc

    XP_BASE, XP_GROWTH = 90, 1.055

    earned = 0
    for chapter in sc.CHAPTERS:
        for mission in chapter["missions"]:
            for beat in mission["beats"]:
                earned += int((beat.get("grant") or {}).get("xp", 0) or 0)
        if chapter["id"] == through_chapter_id:
            break

    return _level_for_xp(earned)


def _level_for_xp(earned: int) -> int:
    """The level the game's own curve produces for a total XP figure."""
    XP_BASE, XP_GROWTH = 90, 1.055
    level, spent = 1, 0
    while True:
        needed = round(XP_BASE * (XP_GROWTH ** (level - 1)))
        if spent + needed > earned:
            return max(3, level)
        spent += needed
        level += 1


def build_difficulty_model(failures: list[str] | None = None) -> dict:
    """The story's difficulty simulator, as a reusable object.

    Exposed rather than kept private because `tools/tune_story.py` SOLVES
    the story's enemy levels against exactly this model. If the tuner had
    its own copy of the party, the levels in story_config would be
    correct with respect to a simulator nobody ever runs -- which is
    precisely the failure that produced the levels this replaced.

    Returns {"cost", "level_from_story_xp"}.
    """
    failures = [] if failures is None else failures
    return _build_difficulty_model(failures)


def _mission_id_of(sc, chapter: dict, mission_name: str) -> str:
    """The mission id behind a display name, within one chapter."""
    for mission in chapter["missions"]:
        if mission["name"] == mission_name:
            return mission["id"]
    return ""


def _level_before_mission(mission_id: str) -> int:
    """The level a story-only player has when they START a given mission.

    THE CHAPTER-END LEVEL IS THE WRONG ANCHOR FOR THE FIRST FIGHT OF A
    CHAPTER, and using it hid a real difficulty cliff.

    _level_from_story_xp answers "what level are you when this chapter is
    OVER", so every fight in Chapter One was measured against a level-16
    squad. A player arriving from the prologue is level 6, and the first
    thing Chapter One puts in front of them is a 974 HP Warden -- roughly
    three times the health of anything in the prologue. The model said
    100% win, 14% health; the player said the game just spiked.

    Counting XP up to the mission that is actually being fought is what
    makes the opening of a chapter measurable at all.
    """
    from bot.game.story import story_config as sc

    earned = 0
    for chapter in sc.CHAPTERS:
        for mission in chapter["missions"]:
            if mission["id"] == mission_id:
                return _level_for_xp(earned)
            for beat in mission["beats"]:
                earned += int((beat.get("grant") or {}).get("xp", 0) or 0)
    return _level_for_xp(earned)


def _check_chapter_climaxes(failures: list[str]) -> list[tuple[str, str, float, float]]:
    """A chapter's LAST fight must be its hardest.

    This was not true of either written chapter, and it was invisible
    from the data: Chapter 2's boss sat at level 12 after two missions
    at 14 and 16, and Chapter 1's capstone at 11 after a level-4 pack of
    three. Level alone doesn't reveal it either -- a solo boss at a
    higher level can still be gentler than three mobs at a lower one,
    because three bodies act three times a cycle and one acts once.

    So difficulty is MEASURED, by simulating each fight against a
    level-appropriate squad and recording the share of the squad's
    health it costs. Measured that way, both chapters ended on their
    easiest encounter: 8.9% for Chapter 2's boss against 22-26% for the
    trash leading to it.

    Cheap to compute and worth the seconds: a chapter that ends on its
    easiest fight has no payoff, and nothing else in this file could
    ever have told you so.

    ----------------------------------------------------------------
    THESE NUMBERS ARE SYSTEMATICALLY PESSIMISTIC. READ THEM AS RANKS.
    ----------------------------------------------------------------
    The simulated party only ever calls take_party_action("attack"). It
    never casts a skill, never spends an ultimate, never guards, never
    heals, and it carries no gear, no cards and no character kit.

    So every percentage below is the cost of a fight to four people
    hitting things with the flat of their hand. A real party at the same
    level has skills, an ultimate every few turns, a healer, equipment
    main stats several times these base numbers, and a Character Card.

    That has one consequence worth writing down, found while calibrating
    Chapter Five: `Rohan` measures 100% at EVERY level -- including level
    20 against a level-42 squad -- because he carries a flat 9,999 HP and
    four actions per cycle. Re-levelling cannot move it, because the
    auto-attacking model cannot get through the pool before he kills
    them. He is the Abyssnia final boss and is tuned for an endgame party
    using its whole kit.

    So use this output for ORDERING, not for absolute difficulty: within
    a chapter the fights should climb and the last should be the biggest.
    A story fight reading 90% here is hard, not unwinnable. A fight
    reading 100% is one this model cannot finish -- a real warning for a
    normal encounter, but for a BOSS template it may mean "needs a real
    kit" rather than "is impossible", and only a human can tell those
    apart.
    """
    model = _build_difficulty_model(failures)
    return _report_climaxes(failures, model)


_MODEL_CACHE: dict = {}


def _build_difficulty_model(failures: list[str]) -> dict:
    # Seeding a database and generating gear is the expensive part and it
    # does not depend on which fight is being measured, so it happens
    # once per process. tune_story measures ~200 fights in a run and this
    # is the difference between a minute and an afternoon.
    if _MODEL_CACHE:
        return _MODEL_CACHE

    import random

    from bot.game.combat.battle import Battle
    from bot.game.combat.enemies import get_template_by_name
    from bot.game.combat.factory import build_enemy_combatant, build_party_combatants
    from bot.game.story import story_config as sc

    # ------------------------------------------------------------------
    # THE SIMULATED PARTY IS A REAL PARTY, BUILT THE WAY THE GAME BUILDS
    # ONE.
    #
    # Two earlier versions of this were wrong in opposite directions and
    # both of them shipped numbers that were read as difficulty.
    #
    #   1. Four stat-blocks that only auto-attacked. Pessimistic by an
    #      unknown margin, and the margin was not small -- it reported the
    #      final boss as 100% impossible at every level, which was a fact
    #      about the model, not about the boss.
    #
    #   2. The "fix" for (1): the same four stat-blocks, given one skill
    #      and one ultimate, with stats invented inline as
    #      `(18 + level * 4) * 1.55`. That formula appears NOWHERE in the
    #      game. Measured against a real squad built by
    #      factory.build_party_combatants, it was 3-5x too much attack and
    #      2-3x too much HP:
    #
    #        level 14  fake atk 115 vs real 34   (3.3x)
    #        level 22  fake atk 164 vs real 44   (3.8x)
    #        level 29  fake atk 208 vs real 52   (4.0x)
    #        level 40  fake atk 276 vs real 55   (5.0x)
    #
    #      Every difficulty number this file printed was therefore a large
    #      understatement, and the 19 enemy levels tuned against it were
    #      tuned against a fiction. This is the same bug class as the
    #      squad-level circularity fixed just above and as the raid
    #      `default=` bug: TWO CODE PATHS COMPUTING ONE VALUE, where only
    #      one of them is the one players experience.
    #
    # So there is now one path. Characters come from CharacterTemplate
    # with their authored growth and their real skill/ultimate ids; gear
    # comes from the real LootGenerator at the rarity the story actually
    # grants; both are assembled by factory.build_party_combatants, which
    # is the same function the bot calls. bench_roles.py already did this
    # correctly and this is deliberately modelled on it.
    # ------------------------------------------------------------------
    import os
    import tempfile

    os.environ.setdefault("DATABASE_URL", "sqlite:///" + tempfile.mktemp(suffix=".db"))
    import bot.config as _cfg

    _cfg.DATABASE_URL = os.environ["DATABASE_URL"]
    from sqlalchemy.orm import sessionmaker

    from bot.database.db import engine
    from bot.database.db_init import init_db
    from bot.database.models.character_model import CharacterTemplate, PlayerCharacter
    from bot.database.models.enums import Rarity
    from bot.game.loot.generator import LootGenerator
    from bot.game.loot.rarity_config import upgrade_level_cap
    from bot.services import character_template_service, item_template_service

    init_db()
    _db = sessionmaker(bind=engine)()
    character_template_service.ensure_character_templates_seeded(_db)
    item_template_service.ensure_item_templates_seeded(_db)
    _db.commit()
    _by_name = {t.name: t for t in _db.query(CharacterTemplate).all()}

    # One of each role, which is the composition the game's own role
    # benchmark reports as the strongest general-purpose team. Naming the
    # characters rather than picking by class means a roster change that
    # deletes one of them fails here loudly instead of quietly measuring
    # a three-person party.
    STORY_SQUAD = ["Josh", "Caliper", "Dolphe", "Refender"]
    _missing = [n for n in STORY_SQUAD if n not in _by_name]
    if _missing:  # pragma: no cover
        failures.append(
            f"check_story's reference squad names characters that no longer "
            f"exist ({', '.join(_missing)}) -- every difficulty number below "
            f"was measured with a short party"
        )

    # A FULL LOADOUT IS SIX PIECES: 1 weapon + 1 artifact + 2 armor +
    # 2 accessories, per enums.SLOT_CAPACITY. Asking for five (which is
    # what bench_roles does, for its own historical reasons) quietly
    # under-gears every character by one slot.
    _gear_cache: dict = {}

    def _kit(rarity, item_level: int, draw: int, slots: int = 6) -> list:
        """A reproducible loadout. `draw` selects between alternative
        rolls of the SAME rarity and level, so `cost` can average over
        several equally plausible sets of gear instead of betting the
        whole measurement on one lucky or unlucky main-stat roll -- a
        single draw of 6 legendaries measured LOWER attack than a single
        draw of 6 epics, which is variance, not a balance fact."""
        key = (rarity, item_level, draw, slots)
        if key not in _gear_cache:
            seed = (rarity.sort_order * 100_000) + (item_level * 1_000) + draw
            gen = LootGenerator(rng=random.Random(seed))
            items = []
            for _ in range(slots):
                tpl = item_template_service.pick_random_template(
                    _db, rng=gen.rng, rarity=rarity)
                if tpl is None:
                    continue
                items.append(gen.generate_item(
                    tpl, player_id=1, item_level=item_level, rarity_override=rarity))
            _gear_cache[key] = items
        return list(_gear_cache[key])

    # THE GEAR THE STORY ITSELF HANDS OUT, read off the reward beats
    # rather than assumed. `_chapter_gear` returns the rarity that
    # chapter grants most often; the item level is that rarity's upgrade
    # cap or the squad's level, whichever is lower, which is the most a
    # player could have and still be playing only the story.
    from bot.game.economy import evolution_config as _ev

    # A full loadout, per enums.SLOT_CAPACITY: 1 weapon + 1 artifact +
    # 2 armor + 2 accessories.
    _SLOTS = 6

    def _fragment_income_through(chapter_id: str) -> int:
        """Every evolution fragment the story hands out up to and
        including this chapter, from mission rewards and map caches."""
        from bot.game.story import map_config as mc

        total = 0
        for chapter in sc.CHAPTERS:
            for mission in chapter.get("missions", []):
                for beat in mission.get("beats", []):
                    total += int((beat.get("grant") or {}).get(
                        "evolution_fragments", 0) or 0)
            if chapter["id"] == chapter_id:
                break
        # Map caches are one-time pickups and a player walking the story
        # will find them, so they count. They are not chapter-scoped, so
        # they are pro-rated by how far through the story this chapter is
        # -- crediting all of them to Chapter One would overstate the
        # early game, which is exactly where overstating power hurts most.
        cache_total = 0
        for area in mc.AREAS.values():
            for entry in (area.get("legend") or {}).values():
                cache_total += int((entry.get("grant") or {}).get(
                    "evolution_fragments", 0) or 0)
        ids = [c["id"] for c in sc.CHAPTERS]
        share = (ids.index(chapter_id) + 1) / len(ids) if chapter_id in ids else 1
        return total + int(cache_total * share)

    def _chapter_gear(chapter_id: str, squad_level: int):
        chapter = next((c for c in sc.CHAPTERS if c["id"] == chapter_id), None)
        counts: dict[str, int] = {}
        for mission in (chapter or {}).get("missions", []):
            for beat in mission.get("beats", []):
                grant = beat.get("grant") or {}
                for key in ("item", "lootbox"):
                    value = grant.get(key)
                    if value is None:
                        continue
                    name = value[0] if isinstance(value, tuple) else value
                    count = value[1] if isinstance(value, tuple) and len(value) > 1 else 1
                    if isinstance(name, str):
                        counts[name] = counts.get(name, 0) + (
                            count if isinstance(count, int) else 1)
        if not counts:
            return Rarity.COMMON, 1
        best = max(counts, key=lambda r: counts[r])
        rarity = getattr(Rarity, best.upper(), Rarity.COMMON)

        # THE ITEM LEVEL IS WHAT THE STORY CAN PAY FOR, not what the
        # squad's level would allow.
        #
        # This used to be min(squad_level, rarity cap), which quietly
        # assumed the player had bought every breakthrough up to their own
        # level. Audited against the story's actual evolution-fragment
        # grants, Chapters Three and Four were roughly 2,500 fragments
        # short of the gear the model was equipping -- so those two
        # chapters were measured against a squad the story does not fund,
        # and their real difficulty was higher than the number printed.
        #
        # Deriving the level from the budget makes that impossible: if a
        # chapter cannot pay for the gear, the model does not get the
        # gear, the fights measure harder, and the tuner lowers them. The
        # story can then be made easier EITHER by lowering enemies OR by
        # granting more fragments, and both show up here.
        budget = _fragment_income_through(chapter_id) / (_SLOTS * len(STORY_SQUAD))
        affordable, spent = 1, 0
        for level in range(2, upgrade_level_cap(rarity) + 1):
            spent += _ev.gear_breakthrough_cost(level, rarity)
            if spent > budget:
                break
            affordable = level
        return rarity, max(1, min(squad_level, affordable))

    # TALENTS ARE PART OF A LEVEL-40 CHARACTER, so the model buys them.
    #
    # Talent points come free with character level -- there is no
    # currency and no gate -- so a story-only player at level 40 has 8 of
    # them whether they think about it or not. Simulating a squad with
    # none is simulating a player who does not exist, which is the same
    # class of mistake as the invented stat formula this model replaced.
    #
    # A REALISTIC build, not the best case. check_talents reports a
    # best case of +30% by pouring every point down one branch; a player
    # doing that has given up both other branches, and assuming it of all
    # four squad members at once would over-tune the whole ladder against
    # a build almost nobody runs. This buys down the character's PRIMARY
    # branch in order and stops when the points run out, which is what
    # someone clicking sensibly ends up with.
    from bot.game.characters import talent_config as _tc

    def _sensible_talents(template, level: int) -> list[str]:
        nodes = _tc.tree_for(template.name, template.character_class)
        points = _tc.points_for_level(level)
        chosen: list[str] = []
        for node in sorted((n for n in nodes if n["branch"] == "a"),
                           key=lambda n: n["tier"]):
            if node["cost"] > points:
                break
            points -= node["cost"]
            chosen.append(node["id"])
        return chosen

    def squad(level: int, size: int, rarity, item_level: int, draw: int) -> list:
        members = []
        for index, name in enumerate(STORY_SQUAD[:size]):
            template = _by_name.get(name)
            if template is None:
                continue
            row = PlayerCharacter(player_id=1, template_id=template.id,
                                  level=level, dupe_count=0)
            row.template = template
            row.current_hp = None
            row.id = index + 1
            row.talents = _sensible_talents(template, level)
            members.append(row)
        return build_party_combatants(
            members, {m.id: _kit(rarity, item_level, draw) for m in members})

    # Buff/heal kinds worth filtering on, so the simulated player does not
    # waste turns re-casting a running buff or healing a full-HP ally.
    # Copied in spirit from bench_roles, which found that a bot doing
    # either of those reads as a BALANCE result and isn't one.
    _BUFF_KINDS = {"team_buff", "team_double_buff", "ally_buff", "buff_self",
                   "team_buff_and_resource", "team_heal_and_buff",
                   "team_shield_and_buff"}
    _HEAL_KINDS = {"heal_lowest_ally_percent_max_hp", "team_heal_percent_max_hp",
                   "heal_from_stat", "team_heal_from_stat", "cleanse_ally_and_heal",
                   "sacrifice_hp_heal_lowest_ally_percent_max_hp",
                   "sacrifice_hp_heal_team_percent_max_hp", "team_heal_and_buff",
                   "team_regen_over_time"}

    def _worth_casting(actor, ability, party) -> bool:
        kind = (ability.get("effect") or {}).get("kind", "")
        if kind in _BUFF_KINDS and any(
                m.source == ability["name"] for m in actor.modifiers):
            return False
        if kind in _HEAL_KINDS and not [
                m for m in party if m.is_alive() and m.current_hp < m.max_hp * 0.85]:
            return False
        return True

    def _party_turn(battle, actor) -> None:
        """Ultimate when it is up and useful, then any ready ability that
        would actually do something, then punch."""
        ultimate = actor.ultimate_ability
        if actor.ultimate_ready() and (
                ultimate is None or _worth_casting(actor, ultimate, battle.party)):
            battle.take_party_action("ultimate")
            return
        for ability in actor.active_abilities:
            if actor.ability_ready(ability) and _worth_casting(
                    actor, ability, battle.party):
                battle.take_party_action("ability", ability_id=ability["id"])
                return
        battle.take_party_action("attack")

    # 96, NOT 24.
    #
    # The estimate is deterministic for a given seed count (seeds are
    # 0..n-1) which makes it LOOK stable -- re-running gives the identical
    # number every time. It is not stable in n. Measured on three fights:
    #
    #   seeds        24     48     96    160
    #   ch3 climax  66.4   68.4   69.4   69.7
    #   ch4 climax  66.1   69.4   67.5   67.3
    #   finale      82.5   84.3   83.1   84.2
    #
    # At 24 seeds a fight can read 3 points off its converged value, and
    # the cross-chapter ramp is decided by margins of exactly that size --
    # the first version of the ramp check failed on a 66-vs-66 pair that
    # was noise. Worse, the tuner searched at 12 seeds and the check
    # verified at 24, so the two disagreed by 7 points on the same fight
    # and levels were being "solved" against a number nobody else saw.
    # Both now use this default.
    DEFAULT_SEEDS = 96

    # The smallest cost difference worth calling a difficulty difference.
    # Sized from the table above: ~3 points of drift between 24 and 160
    # seeds, so anything under that is the simulator, not the design.
    # Same reasoning as bench_roles.MIN_MEANINGFUL_GAP, learned the same
    # way -- by believing a regression that turned out to be noise.
    MIN_MEANINGFUL_GAP = 3.0

    def simulate(enemies: list[str], level: int, squad_level: int, size: int = 4,
                 seeds: int = DEFAULT_SEEDS,
                 chapter_id: str = "chapter5") -> tuple[float, float]:
        """(mean % of squad health spent, fraction of runs won).

        Both come out of the SAME battles. An earlier version returned
        only the cost, and cost alone cannot tell a hard fight from an
        unwinnable one: a wipe and a narrow win can both read 85%, and
        the story's final boss is exactly where that distinction is the
        whole question.
        """
        rarity, item_level = _chapter_gear(chapter_id, squad_level)
        losses, wins = [], 0
        for seed in range(seeds):
            # Four gear draws across the seeds, so no single main-stat
            # roll decides the verdict for a fight.
            party = squad(squad_level, size, rarity, item_level, seed % 4)
            if not party:
                return 100.0, 0.0
            total = sum(m.max_hp for m in party)
            built = [build_enemy_combatant(get_template_by_name(n), level) for n in enemies]
            battle = Battle(party, built, rng=random.Random(seed))
            for _ in range(400):
                if battle.is_over():
                    break
                actor = battle.current_actor()
                if actor in battle.party:
                    _party_turn(battle, actor)
                else:
                    battle.take_enemy_turn()
            standing = sum(max(0, m.current_hp) for m in battle.party)
            losses.append((total - standing) / total * 100)
            if battle.result == "won":
                wins += 1
        return sum(losses) / len(losses), wins / seeds

    def cost(enemies: list[str], level: int, squad_level: int, size: int = 4,
             seeds: int = DEFAULT_SEEDS, chapter_id: str = "chapter5") -> float:
        return simulate(enemies, level, squad_level, size, seeds, chapter_id)[0]

    _MODEL_CACHE.update({
        "cost": cost,
        "simulate": simulate,
        "level_from_story_xp": _level_from_story_xp,
        # The honest anchor: the level a player has when they START a
        # given mission, rather than when they finish its chapter.
        "level_before_mission": _level_before_mission,
        "default_seeds": DEFAULT_SEEDS,
        "min_meaningful_gap": MIN_MEANINGFUL_GAP,
    })
    return _MODEL_CACHE


def _report_climaxes(failures: list[str], model: dict) -> list[tuple[str, str, float, float]]:
    """Measure every story fight and assert the ramp."""
    from bot.game.story import story_config as sc

    simulate = model["simulate"]
    cost = model["cost"]

    # TWO NUMBERS, ASSERTED SEPARATELY, BECAUSE NEITHER WORKS ALONE.
    #
    # This asserted on health cost first, and the two disagree badly
    # enough that the cost-based version was passing a story it should
    # have failed. Chapter Two's climax was its most EXPENSIVE fight
    # (47% of the squad's health) and a 96% win -- a fight the party
    # comfortably wins still spends health winning it. Chapter Four's
    # climax read 73% cost and was a 50% coin flip. The player does not
    # experience "I spent 73% of my health"; they experience losing half
    # the time.
    #
    # Health cost is also capped by something that is not difficulty:
    # once the healer keeps pace, a longer fight costs no more health
    # than a short one. That ceiling makes the late chapters
    # indistinguishable from each other no matter how they are tuned.
    # WIN RATE decides whether a fight is FAIR. Health cost decides
    # whether it is in the right PLACE. Asserting only one of them passed
    # a story that was wrong, twice, in opposite directions.
    WIN_FLOOR = 65.0
    min_gap = model["min_meaningful_gap"]

    # THE PROLOGUE IS MEASURED AGAINST ITS REAL ROSTER, not against the
    # party of four the loop below assumes. See _roster_before.
    prologue = next((c for c in sc.CHAPTERS if c["id"] == "prologue"), None)
    if prologue is not None:
        for mission in prologue["missions"]:
            for index, beat in enumerate(mission["beats"]):
                if beat.get("kind") != "battle":
                    continue
                size, level = _roster_before(prologue["missions"], mission["id"], index)
                share = cost(beat["enemies"], beat.get("level", 1), level, size,
                             chapter_id="prologue") / 100
                if share >= 1.0:
                    failures.append(
                        f"{mission['id']}: UNWINNABLE -- costs {share:.0%} of a "
                        f"{size}-character level-{level} party, which is everything "
                        f"they have at that point"
                    )
                elif share > 0.75:
                    failures.append(
                        f"{mission['id']}: costs {share:.0%} of a {size}-character "
                        f"level-{level} party -- the prologue should not be a knife-edge"
                    )

    measured: list[tuple[str, str, float, float]] = []
    climaxes: list[tuple[str, str, float]] = []
    for chapter in sc.CHAPTERS:
        # OPTIONAL MISSIONS ARE EXCLUDED FROM THE CHAPTER'S SHAPE.
        #
        # The climax rule reads the LAST fight in mission order as the
        # chapter's climax. Side missions are appended after the finale
        # in the config, so including them would make a side mission the
        # climax of every chapter that has one -- and the check would
        # then start failing the main story for not being harder than its
        # own optional content. They are still measured, below, against
        # their own floor.
        fights = [
            (mission["name"], beat)
            for mission in chapter["missions"]
            if not mission.get("optional")
            for beat in mission.get("beats", [])
            if beat.get("kind") == "battle"
        ]
        if len(fights) < 2:
            continue
        # SQUAD LEVEL COMES FROM THE STORY'S OWN XP BUDGET.
        #
        # It used to be the mean of the chapter's own enemy levels, which
        # is circular: raising an enemy's level to make a fight harder
        # also raised the assumed player level, which made it easier
        # again. Tuning chased its own tail -- a retune that raised
        # nineteen fights by 15-25 levels each came out MEASURING LOWER
        # than before it was applied.
        #
        # Now that story missions grant XP (see story_service's `xp`
        # grant), there is a real answer: add up every XP grant up to and
        # including this chapter and convert it with the game's own
        # levelling curve. That is the level a player who has done the
        # story and nothing else actually arrives at, which is the only
        # player the story is allowed to assume.
        squad_level = _level_from_story_xp(chapter["id"])
        scored = []
        for name, beat in fights:
            # PER-MISSION LEVEL, not the chapter-end level. See
            # _level_before_mission -- measuring Chapter One's opening
            # fight against the level you finish Chapter One at reported
            # 100% win on a fight that is, in fact, the first real
            # difficulty spike in the game.
            at_level = _level_before_mission(_mission_id_of(sc, chapter, name))
            fight_cost, win = simulate(beat["enemies"], beat.get("level", 1),
                                       at_level, chapter_id=chapter["id"])
            scored.append((name, beat, win * 100, fight_cost))
        for name, _b, win, fight_cost in scored:
            measured.append((chapter["name"], name, win, fight_cost))

            # NOTHING IN THE STORY IS A COIN FLIP. The story is the one
            # part of the game everybody has to get through, so a fight
            # the player loses as often as they win is a wall, not a
            # difficulty curve -- and two of them shipped before this
            # assertion existed.
            if win < WIN_FLOOR:
                failures.append(
                    f"'{chapter['name']}' / '{name}' is won {win:.0f}% of the time "
                    f"by a squad at the level the story's own XP produces "
                    f"(level {squad_level}) -- below the {WIN_FLOOR:.0f}% floor"
                )

        # Hardest = most expensive. Ordering is asserted on COST because
        # win rate saturates: everything comfortable reads 100%, so it
        # cannot rank the first three chapters at all.
        hardest = max(scored, key=lambda row: row[3])
        finale = scored[-1]
        if finale[3] < hardest[3] - min_gap:
            failures.append(
                f"'{chapter['name']}' ends on '{finale[0]}' costing {finale[3]:.0f}% of "
                f"the squad's health, but '{hardest[0]}' earlier in the chapter costs "
                f"{hardest[3]:.0f}% -- the chapter's climax is easier than its corridor"
            )
        climaxes.append((chapter["name"], finale[0], finale[3]))

    # THE STORY AS A WHOLE HAS TO RAMP, not just each chapter separately.
    #
    # Every chapter can pass the check above while the story still gets
    # EASIER in the middle, and it did: after the first honest solve,
    # Chapter Two's climax measured 57% and Chapter Three's 52%. Both
    # chapters were internally well-shaped, and the player would still
    # have felt the game slacken right after the halfway point, then
    # tighten again -- which reads as inconsistency rather than as a
    # difficulty curve.
    #
    # A per-chapter check cannot see this by construction. It needs its
    # own assertion, and it is the one the brief actually asked for: the
    # story should power the player up toward Rohan, so each chapter's
    # last fight should ask more of them than the last one did.
    for (prev_chapter, prev_name, prev_cost), (name_of, name, value) in zip(
            climaxes, climaxes[1:]):
        if value < prev_cost - min_gap:
            failures.append(
                f"'{name_of}' ends on '{name}' costing {value:.0f}% of the squad's "
                f"health, but '{prev_chapter}' already ended on '{prev_name}' at "
                f"{prev_cost:.0f}% -- the story gets easier as it goes"
            )

    _check_hunts(failures, model, measured)
    return measured


# An optional fight may be harder than the mandatory ones around it --
# that is what makes it worth finding -- but not by so much that it is
# really a gear check wearing a side-content costume. The floor is lower
# than the story's own 65% because losing a hunt costs the player
# NOTHING (map_service.finish_hunt returns empty on a loss and does not
# touch the party), so the fairness argument that justifies the story
# floor does not apply with the same force here.
HUNT_WIN_FLOOR = 55.0

# ...and a hunt that is EASIER than the chapter it sits in is not a
# reward for exploring, it is a detour. It has to be meaningfully harder
# than the fights around it or there is no reason to have built it.
HUNT_MUST_EXCEED_CHAPTER_BY = 5.0


def _check_hunts(failures: list[str], model: dict,
                 measured: list[tuple[str, str, float, float]]) -> None:
    """Measure every optional `hunt` tile the same way story fights are
    measured.

    Hunts went in unmeasured the first time and that is exactly how the
    main story ladder ended up with level-34 enemies in a chapter reached
    at level 14: a number sitting next to a list of enemy names looks
    fine in a diff no matter what it says. Optional content is not exempt
    from that -- it is more exposed to it, because nobody play-tests the
    room they did not have to enter.
    """
    from bot.game.story import map_config as mc
    from bot.game.story import story_config as sc

    simulate = model["simulate"]
    level_from_xp = model["level_from_story_xp"]

    # Which chapter a hunt belongs to is decided by the mission that
    # UNLOCKS THE DOOR to its room -- that is the earliest a player can
    # possibly be standing there, so it is the level the fight has to be
    # fair at. Derived rather than authored, so moving a door moves the
    # difficulty target with it.
    chapter_of_mission = {
        mission["id"]: chapter["id"]
        for chapter in sc.CHAPTERS
        for mission in chapter["missions"]
    }
    gate_into: dict[str, str] = {}
    for area in mc.AREAS.values():
        for entry in (area.get("legend") or {}).values():
            if entry.get("kind") == "exit" and entry.get("requires_mission"):
                gate_into.setdefault(entry["to_area"], entry["requires_mission"])

    for area_id, area in mc.AREAS.items():
        for char, entry in (area.get("legend") or {}).items():
            if entry.get("kind") != "hunt":
                continue
            gate = gate_into.get(area_id)
            chapter_id = chapter_of_mission.get(gate, "chapter1")
            squad_level = level_from_xp(chapter_id)
            fight_cost, win = simulate(
                entry["enemies"], entry.get("level", 1), squad_level,
                chapter_id=chapter_id)
            win *= 100
            measured.append((f"{area['name']} (optional)", entry.get("name", char),
                             win, fight_cost))

            if win < HUNT_WIN_FLOOR:
                failures.append(
                    f"hunt '{entry.get('name', char)}' in '{area_id}' is won "
                    f"{win:.0f}% of the time by the squad that can first reach it "
                    f"(level {squad_level}, via {gate or 'no gate'}) -- below the "
                    f"{HUNT_WIN_FLOOR:.0f}% floor for optional fights"
                )

            # Compare against the chapter the player is in when the door
            # opens. `measured` already holds every story fight.
            chapter_name = next(
                (c["name"] for c in sc.CHAPTERS if c["id"] == chapter_id), None)
            siblings = [row[3] for row in measured if row[0] == chapter_name]
            if siblings:
                hardest = max(siblings)
                if fight_cost < hardest - HUNT_MUST_EXCEED_CHAPTER_BY:
                    failures.append(
                        f"hunt '{entry.get('name', char)}' in '{area_id}' costs "
                        f"{fight_cost:.0f}% of the squad's health, but the hardest "
                        f"fight in {chapter_name} already costs {hardest:.0f}% -- "
                        f"an optional fight easier than the required ones is a "
                        f"detour, not a reward"
                    )


def _check_doorways_line_up(failures: list[str]) -> tuple[int, int]:
    """A two-way doorway must be the SAME doorway from both sides.

    map_service.travel derives the landing tile from the destination's
    door back, precisely so this can't be got wrong by hand -- but the
    property is worth asserting, because it's the one a player feels
    immediately and nobody would think to re-test after editing a grid.

    Before it was derived, the hand-authored coordinates had drifted:
    entering a side room from the Atrium landed on that room's door
    correctly, but coming back out put the player 5, 6 and 7 tiles from
    the door they'd just used, standing in the middle of the Atrium.
    Doors read as teleporters rather than doors.

    One-way exits are exempt and counted separately -- the prologue lab
    collapses behind you, so there is deliberately no door to arrive on.

    This calls map_service.landing_tile -- the function travel() actually
    uses -- rather than re-deriving the answer from map_config. The first
    version of this check did the latter, comparing map data against map
    data, and passed unchanged when the fix was deleted from travel(). A
    check that stays green while the behaviour it names is removed is
    worse than no check, so this one goes through the real code.
    """
    from bot.game.story import map_config as mc
    from bot.services import map_service

    exits: list[tuple[str, int, int, dict]] = []
    for area_id, area in mc.AREAS.items():
        legend = area.get("legend") or {}
        for y, row in enumerate(area["grid"]):
            for x, char in enumerate(row):
                content = legend.get(char)
                if content and content.get("kind") == "exit":
                    exits.append((area_id, x, y, content))

    two_way = one_way = 0
    for area_id, x, y, content in exits:
        destination = content.get("to_area")
        # Is there a door in `destination` that leads back here?
        back = [(bx, by, c) for (a, bx, by, c) in exits
                if a == destination and c.get("to_area") == area_id]
        if not back:
            one_way += 1
            continue
        two_way += 1

        # Walk through, then walk back, using the real function.
        arrived = map_service.landing_tile(area_id, destination, content["to"])
        bx, by, back_content = back[0]
        if arrived != (bx, by):
            failures.append(
                f"doorway '{area_id}'({x},{y}) -> '{destination}': you arrive at "
                f"{arrived}, but the door back to '{area_id}' is at ({bx},{by}) -- "
                f"you land in the middle of the room instead of in the doorway"
            )
            continue
        returned = map_service.landing_tile(destination, area_id, back_content["to"])
        if returned != (x, y):
            failures.append(
                f"doorway '{area_id}'({x},{y}) -> '{destination}' does not round-trip: "
                f"coming back lands at {returned}, not the door you left by"
            )
    return two_way, one_way


def _check_map_is_navigable(failures: list[str]) -> tuple[int, int]:
    """Every room must be REACHABLE and LEAVABLE in both directions.

    The map was a one-way linked list: 15 of 16 rooms had exactly one
    exit, forward, and the last had none. You could not walk back to a
    cache you'd skipped, re-read a note, or revisit a room whose meaning
    changed once you knew something -- and a map you can only ever move
    forward through is a corridor with extra steps, not a place.

    So: every room except the first has a way back to the room that
    leads to it. That's the minimum for the grid to be worth having.
    """
    from bot.game.story import map_config as mc

    # Exits the author has DECLARED one-way with `"one_way": True`.
    #
    # The rule below exists so a player can't walk into a dead end and be
    # stuck, and it should stay strict -- but "you cannot go back" is
    # sometimes the point rather than an oversight. The prologue's lab
    # collapses behind you one room at a time; adding return doors to a
    # building that no longer exists would be a worse map, not a safer
    # one. Declaring it is the difference between a decision and a bug,
    # and an undeclared one-way still fails.
    declared_one_way: dict[str, set[str]] = {}
    for area_id, area in mc.AREAS.items():
        declared_one_way[area_id] = {
            content["to_area"]
            for content in (area.get("legend") or {}).values()
            if content.get("kind") == "exit" and content.get("one_way")
        }

    forward: dict[str, list[str]] = {}
    for area_id, area in mc.AREAS.items():
        forward[area_id] = [
            content["to_area"]
            for content in (area.get("legend") or {}).values()
            if content.get("kind") == "exit" and content.get("to_area")
        ]

    one_way = 0
    for area_id, destinations in forward.items():
        for destination in destinations:
            if destination not in mc.AREAS:
                failures.append(f"area '{area_id}' exits to unknown area '{destination}'")
                continue
            if area_id not in forward.get(destination, []) and destination not in declared_one_way.get(area_id, ()):
                failures.append(
                    f"'{area_id}' -> '{destination}' is ONE-WAY: once the player walks "
                    f"through, they can never return to '{area_id}'"
                )
                one_way += 1

    links = sum(len(v) for v in forward.values())
    return links, one_way


# Panels a station tile may open. Kept as a literal rather than imported
# from bot/cogs/story.py because importing a cog pulls in discord.py's
# whole UI layer for what is a five-item list -- but tools/check_runtime
# exercises the real builder, so a name here that the cog can't build
# still gets caught.
STATION_PANELS = frozenset({
    "hq", "base", "shrines", "harvesters", "shop", "lab", "forge",
    "squad", "exchange",
})


def main() -> int:
    from bot.database.models.enums import Rarity
    from bot.game.characters.character_seed_data import CHARACTER_TEMPLATES
    from bot.game.combat.enemies import ENEMY_TEMPLATES
    from bot.game.dungeon.encounter_config import get_encounter_by_id
    from bot.game.story import story_config as sc
    from bot.services.currency_service import VALID_CURRENCIES

    enemy_names = {t["name"] for t in ENEMY_TEMPLATES}
    rarities = {r.value for r in Rarity}
    failures: list[str] = []

    for _mission in sc.all_missions():
        for _key in ("summary",):
            if _mission.get(_key) is not None and not isinstance(_mission[_key], str):
                failures.append(
                    f"mission '{_mission['id']}' {_key} is a "
                    f"{type(_mission[_key]).__name__}, not a string -- a trailing comma "
                    f"after a parenthesised string makes it a tuple"
                )
        for _beat in _mission.get("beats", []):
            for _key in TEXT_KEYS:
                _value = _beat.get(_key)
                if _value is not None and not isinstance(_value, str):
                    failures.append(
                        f"mission '{_mission['id']}' {_beat.get('kind')} beat: {_key} is a "
                        f"{type(_value).__name__}, not a string -- a trailing comma after "
                        f"a parenthesised string makes it a tuple"
                    )
            for _option in _beat.get("options", []) or []:
                for _key in TEXT_KEYS:
                    _value = _option.get(_key)
                    if _value is not None and not isinstance(_value, str):
                        failures.append(
                            f"mission '{_mission['id']}' option '{_option.get('id')}': "
                            f"{_key} is a {type(_value).__name__}, not a string"
                        )

    map_links, _one_way = _check_map_is_navigable(failures)
    two_way_doors, one_way_doors = _check_doorways_line_up(failures)
    climax = _check_chapter_climaxes(failures)
    missions = sc.all_missions()
    ids = [m["id"] for m in missions]
    for duplicate in {i for i in ids if ids.count(i) > 1}:
        failures.append(f"duplicate mission id: {duplicate}")

    # Every flag anyone READS must be WRITTEN by some choice, or the beat
    # gated on it is unreachable content that looks fine in the file.
    written_flags: set[str] = set()
    for mission in missions:
        for beat in mission["beats"]:
            for option in beat.get("options", []) or []:
                written_flags.update((option.get("sets") or {}).keys())

    # ------------------------------------------------------------------
    # AN OPTION KEY THE ENGINE NEVER READS.
    #
    # story_service.resolve_choice reads exactly one key for flags:
    # `option["sets"]`, a dict. Writing `"flag": "some_name"` instead is
    # valid Python, reads perfectly in the source, renders identically in
    # the game -- and sets nothing at all.
    #
    # That shipped. Sixty options across three chapters used "flag",
    # including nine in the prologue that predated them, so every choice
    # in Chapters One through Three recorded no consequence whatsoever.
    # The failure is invisible from both directions: the writer sees a
    # flag next to the option, and the checker's own "is this flag ever
    # written" pass looked only at `sets` and so reported the file as
    # clean while sixty flags did not exist.
    #
    # This is the same shape as tools/check_effect_keys.py, one system
    # over: a config key nothing consumes. Whitelisting the keys the
    # engine actually honours is the only version of this check that
    # cannot be fooled by a plausible-looking name.
    # ------------------------------------------------------------------
    OPTION_KEYS = {"id", "label", "text", "sets"}
    for mission in missions:
        for index, beat in enumerate(mission["beats"]):
            for option in beat.get("options", []) or []:
                for key in option:
                    if key not in OPTION_KEYS:
                        failures.append(
                            f"{mission['id']} beat {index} option "
                            f"{option.get('id', '?')!r}: key {key!r} is not one of "
                            f"{sorted(OPTION_KEYS)} -- story_service reads none of it, "
                            f"so it is silently ignored. Flags are set with "
                            f'\'"sets": {{"name": True}}\', not \'"flag": "name"\''
                        )

    character_names = {t["name"] for t in CHARACTER_TEMPLATES}

    from bot.game.economy.lootbox_config import LOOTBOX_TEMPLATES
    lootbox_tiers = {t["tier"] for t in LOOTBOX_TEMPLATES}

    def check_grant(where: str, grant: dict) -> None:
        for key, value in (grant or {}).items():
            if key == "item":
                if isinstance(value, str) and value not in rarities:
                    failures.append(f"{where}: item rarity {value!r} does not exist")
            elif key == "character":
                # Validated against the seed data by NAME, because that's
                # what the grant uses -- a renamed or removed character
                # would otherwise fail silently at the moment a player
                # reaches the beat.
                if value not in character_names:
                    failures.append(f"{where}: no character template named {value!r}")
            elif key == "lootbox":
                # "epic", or ("epic", 3) for a stack -- see
                # story_service._grant.
                tier = value[0] if isinstance(value, (list, tuple)) else value
                if tier not in lootbox_tiers:
                    failures.append(
                        f"{where}: lootbox tier {tier!r} does not exist "
                        f"(have: {', '.join(sorted(lootbox_tiers))})"
                    )
            elif key == "xp":
                if not isinstance(value, int) or value <= 0:
                    failures.append(f"{where}: xp must be a positive int")
            elif key not in VALID_CURRENCIES:
                failures.append(f"{where}: '{key}' is not a currency or 'xp'")

    for mission in missions:
        name = mission["id"]
        beats = mission.get("beats") or []
        if not beats:
            failures.append(f"{name}: no beats")
        check_grant(f"{name}/rewards", mission.get("rewards") or {})

        if beats and beats[-1].get("kind") == "choice":
            failures.append(
                f"{name}: ends on a choice -- the player picks and sees nothing happen"
            )

        for index, beat in enumerate(beats):
            where = f"{name}[{index}]"
            kind = beat.get("kind")
            if kind not in BEAT_KINDS:
                failures.append(f"{where}: beat kind {kind!r} is not one of {sorted(BEAT_KINDS)}")
                continue

            for flag_name in list(beat.get("requires", [])) + list(beat.get("unless", [])):
                if flag_name not in written_flags:
                    failures.append(
                        f"{where}: gated on flag '{flag_name}', which no choice ever sets"
                    )

            if kind == "dialogue":
                if not beat.get("text"):
                    failures.append(f"{where}: dialogue with no text")
            elif kind == "choice":
                options = beat.get("options") or []
                if not 2 <= len(options) <= 4:
                    failures.append(f"{where}: {len(options)} options (needs 2-4)")
                option_ids = [o.get("id") for o in options]
                if len(set(option_ids)) != len(option_ids):
                    failures.append(f"{where}: duplicate option ids")
                for option in options:
                    if not option.get("label"):
                        failures.append(f"{where}: an option has no label")
            elif kind == "battle":
                enemies = beat.get("enemies") or []
                if not enemies:
                    failures.append(f"{where}: battle with no enemies")
                if len(enemies) > 5:
                    failures.append(f"{where}: {len(enemies)} enemies (engine allows 5)")
                for enemy in enemies:
                    if enemy not in enemy_names:
                        failures.append(f"{where}: no enemy template named {enemy!r}")
                if not isinstance(beat.get("level"), int):
                    failures.append(f"{where}: battle needs an integer level")
            elif kind == "encounter":
                if get_encounter_by_id(beat.get("encounter_id", "")) is None:
                    failures.append(
                        f"{where}: encounter {beat.get('encounter_id')!r} does not exist"
                    )
            elif kind == "reward":
                check_grant(where, beat.get("grant") or {})
            elif kind == "unlock":
                feature = beat.get("feature")
                if feature not in sc.FEATURES:
                    failures.append(f"{where}: unlocks unknown feature {feature!r}")

    # A gated feature with two unlock beats is ambiguous; with zero it's
    # simply ungated (which story_service allows on purpose), so only the
    # duplicate case is an error.
    for feature in sc.FEATURES:
        unlocks = [
            m["id"] for m in missions
            for b in m["beats"]
            if b.get("kind") == "unlock" and b.get("feature") == feature
        ]
        if len(unlocks) > 1:
            failures.append(f"feature '{feature}' is unlocked by more than one mission: {unlocks}")

    failures += _check_maps()

    gated = [f for f in sc.FEATURES if sc.feature_unlocked_by(f)]
    print(f"chapters : {len(sc.CHAPTERS)}")
    from bot.game.story import map_config as _mc
    print(f"map      : {len(_mc.AREAS)} rooms, {map_links} exits "
          f"({map_links / max(1, len(_mc.AREAS)):.1f} per room, all two-way)")
    print(f"doorways : {two_way_doors} line up door-to-door both ways, "
          f"{one_way_doors} declared one-way")
    if climax:
        print("fights   : measured against a squad at the level the story's own "
              "XP grants produce")
        last_chapter = None
        for chapter_name, fight_name, win, fight_cost in climax:
            if chapter_name != last_chapter:
                print(f"           {chapter_name}")
                last_chapter = chapter_name
            print(f"             {fight_name[:30]:32}"
                  f"won {win:>3.0f}%   costs {fight_cost:>3.0f}% health")
    print(f"missions : {len(missions)}")
    print(f"beats    : {sum(len(m['beats']) for m in missions)}")
    print(f"flags    : {len(written_flags)} written ({', '.join(sorted(written_flags)) or 'none'})")
    print(f"gated    : {len(gated)}/{len(sc.FEATURES)} features "
          f"({', '.join(sorted(gated)) or 'none'})")

    print()
    if failures:
        for line in dict.fromkeys(failures):
            print(f"  FAIL  {line}")
        return 1
    print("OK -- every beat is runnable and every flag is reachable.")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, ".")
    sys.exit(main())
