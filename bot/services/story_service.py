"""
The story interpreter: advancing beats, resolving flags, gating features.

Knows nothing about any specific mission. Everything it runs comes from
bot/game/story/story_config.py, which is why `tools/check_story.py` can
validate the entire script without executing a line of it.

----------------------------------------------------------------------
THE ONE RULE THAT MATTERS MOST
----------------------------------------------------------------------
**Nobody loses access to something they already had.**

Story mode gates features that, until now, every player has had from the
moment they ran `/start`. Getting that wrong doesn't produce a bug
report, it produces someone with a level-50 roster who can't open their
own inventory. So `feature_unlocked` is deliberately generous: a feature
is on if the story unlocked it, OR the player is grandfathered, OR they
already have evidence of using it. Three independent yeses, one no.

Grandfathering is decided ONCE, by the migration, which marks every
existing player prologue-complete. `is_grandfathered` additionally
catches anyone the migration missed (a player created between the
migration running and the deploy finishing) by looking for progress that
could only exist pre-story.
"""

from __future__ import annotations

import random

from bot.database.models.story_model import PlayerStory
from bot.game.story import story_config as sc
from bot.services.currency_service import add_currency


class StoryError(Exception):
    """Any reason a story action can't proceed, phrased for the player."""


# ----------------------------------------------------------------------
# State
# ----------------------------------------------------------------------

def get_or_create(db, player) -> PlayerStory:
    row = db.get(PlayerStory, player.id)
    if row is None:
        row = PlayerStory(
            player_id=player.id, completed_missions=[], flags={},
            active_mission=None, beat_index=0, prologue_complete=False,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def flag(story: PlayerStory, name: str) -> bool:
    """A flag that was never set reads False. This is what makes adding a
    new flag safe for existing saves."""
    return bool((story.flags or {}).get(name))


def set_flags(db, story: PlayerStory, values: dict) -> None:
    # Reassigned wholesale -- SQLAlchemy does not detect in-place mutation
    # of a plain JSON column, so `story.flags[k] = v` would silently not
    # persist.
    story.flags = {**(story.flags or {}), **values}
    db.commit()


def has_completed(story: PlayerStory, mission_id: str) -> bool:
    return mission_id in (story.completed_missions or [])


def _mark_completed(db, story: PlayerStory, mission_id: str) -> None:
    if mission_id not in (story.completed_missions or []):
        story.completed_missions = [*(story.completed_missions or []), mission_id]
    db.commit()


# ----------------------------------------------------------------------
# Feature gating
# ----------------------------------------------------------------------

def is_grandfathered(db, player) -> bool:
    """Whether this player predates story mode.

    The migration marks existing players prologue-complete, so this is
    the belt-and-braces check for anyone it missed: a player with an
    expedition, a pulled character, or a levelled roster could only have
    got that way before features were gated. Cheap and read-only.
    """
    from bot.database.models.character_model import PlayerCharacter
    from bot.database.models.expedition_model import Expedition

    # A player who is PLAYING THE STORY is not a pre-story player, and the
    # heuristics below must not be consulted for them.
    #
    # This is not defensive tidiness, it's a measured bug: the prologue
    # grants Josh in mission 3, which pushed the owned-character count to
    # 2 and made a brand-new account match "they must have pulled before
    # gating existed". The result was /adventure unlocking a whole
    # mission early -- the story handing out the key to a door it hadn't
    # written the scene for yet. Any future story-granted character would
    # have re-broken it the same way, so the fix is to stop asking the
    # question rather than to raise the threshold.
    story = db.query(PlayerStory).filter_by(player_id=player.id).first()
    if story is not None and (story.completed_missions or story.active_mission):
        return False

    if db.query(Expedition).filter_by(player_id=player.id).first() is not None:
        return True
    # More than one character means they pulled at least once, which the
    # prologue is what teaches.
    owned = db.query(PlayerCharacter).filter_by(player_id=player.id).count()
    return owned > 1


def feature_unlocked(db, player, feature: str) -> bool:
    """Whether `player` may use `feature` right now.

    Generous by construction -- see the module docstring. Anything not
    listed in story_config.FEATURES is always on, so adding a command
    never accidentally locks it."""
    if feature in sc.ALWAYS_AVAILABLE or feature not in sc.FEATURES:
        return True

    story = get_or_create(db, player)

    # A feature NO written mission unlocks opens when the PROLOGUE ends.
    #
    # This used to return True -- ungated entirely -- to avoid a door
    # with no key. That was right when the prologue was the only content,
    # and wrong as soon as anyone played it: a new player who had just
    # been handed their inventory in mission 2 could immediately open the
    # HQ, the Forge, the Research Lab and the shop, none of which the
    # story had introduced or explained. The whole reason the prologue
    # exists is that meeting one system at a time beats meeting thirty at
    # once, and an unwritten unlock beat was silently opting features out
    # of that.
    #
    # Falling back to the END OF THE PROLOGUE rather than to "open" keeps
    # both properties:
    #
    #   * no softlock -- the prologue requires none of these features to
    #     complete, so the key always exists and is always reachable
    #   * no permanent lock when a chapter is unwritten -- the feature
    #     arrives at a defined moment instead of never
    #
    # When Chapter 1 later adds a real unlock beat for, say, the Forge,
    # that beat takes over automatically and this branch stops applying
    # to it. Content and gating still ship together; the default is just
    # no longer "wide open".
    if sc.feature_unlocked_by(feature) is None:
        return bool(story.prologue_complete) or is_grandfathered(db, player)

    if _unlocked_by_story(story, feature):
        return True

    # PROLOGUE_COMPLETE IS AUTHORITATIVE for anything the prologue gates.
    #
    # This is the check that grandfathering actually runs on, and leaving
    # it out is a real lockout, not a theoretical one: the migration
    # marks every existing player prologue-complete, but a player who had
    # only ever run /start (no pulls, no expeditions) failed the
    # is_grandfathered heuristics below and was refused their own
    # inventory. Caught by the migration test, which is the only place it
    # WOULD have been caught -- it looks completely fine in isolation.
    #
    # Scoped to the prologue on purpose: a feature gated by a LATER
    # chapter still needs that chapter, so this can't accidentally hand
    # out content the player hasn't reached.
    unlocking_mission = sc.feature_unlocked_by(feature)
    if story.prologue_complete and unlocking_mission in sc.prologue_mission_ids():
        return True

    return is_grandfathered(db, player)


def _unlocked_by_story(story: PlayerStory, feature: str) -> bool:
    """Has a mission the player completed contained an unlock beat for
    this feature? Read from the SCRIPT rather than from a stored list, so
    moving an unlock between missions doesn't need a migration."""
    completed = set(story.completed_missions or [])
    for mission in sc.all_missions():
        if mission["id"] not in completed:
            continue
        for beat in mission["beats"]:
            if beat.get("kind") == "unlock" and beat.get("feature") == feature:
                return True
    return False


def locked_message(feature: str) -> str:
    """What to tell a player who tried a locked command. Names the
    mission, because "not yet" without a "when" is just a wall."""
    label = sc.FEATURES.get(feature, feature)
    mission_id = sc.feature_unlocked_by(feature)
    mission = sc.get_mission(mission_id) if mission_id else None
    if mission is None:
        # No unlock beat written yet, so this feature arrives when the
        # prologue does. Say that, rather than "isn't available yet" --
        # a player who can't tell whether the wall is temporary or
        # permanent has no reason to keep playing toward it.
        return (
            f"**{label}** opens once you've finished the Prologue. "
            "Use `/story` to keep going."
        )
    return (
        f"**{label}** unlocks during **{mission['name']}**. "
        "Use `/story` to pick up where you left off."
    )


# ----------------------------------------------------------------------
# Availability
# ----------------------------------------------------------------------

def next_mission(db, player) -> dict | None:
    """The first mission the player hasn't cleared, in script order.
    None when they've finished everything written so far."""
    story = get_or_create(db, player)
    completed = set(story.completed_missions or [])
    for mission in sc.all_missions():
        if mission["id"] not in completed:
            return mission
    return None


def visible_beats(story: PlayerStory, mission: dict) -> list[dict]:
    """The mission's beats with flag-gated ones filtered out.

    Computed fresh on every read rather than frozen at mission start, so
    a flag set by a choice EARLIER IN THE SAME MISSION can still remove a
    later beat. That's the whole point of `requires`/`unless`."""
    out = []
    for beat in mission["beats"]:
        if any(not flag(story, name) for name in beat.get("requires", [])):
            continue
        if any(flag(story, name) for name in beat.get("unless", [])):
            continue
        out.append(beat)
    return out


def current_beat(db, player) -> tuple[dict, dict] | None:
    """(mission, beat) the player is sitting on, or None if no mission is
    active. Clamps a beat index that has run off the end, which can
    happen if a flag removed beats after the index was stored."""
    story = get_or_create(db, player)
    if not story.active_mission:
        return None
    mission = sc.get_mission(story.active_mission)
    if mission is None:
        # Content was removed under a save. Drop the mission rather than
        # crashing every time they open /story.
        story.active_mission = None
        story.beat_index = 0
        db.commit()
        return None
    beats = visible_beats(story, mission)
    if story.beat_index >= len(beats):
        return mission, {"kind": "_finish"}
    return mission, beats[story.beat_index]


# ----------------------------------------------------------------------
# Running a mission
# ----------------------------------------------------------------------

def start_mission(db, player, mission_id: str) -> dict:
    story = get_or_create(db, player)
    mission = sc.get_mission(mission_id)
    if mission is None:
        raise StoryError("That mission doesn't exist.")
    if story.active_mission and story.active_mission != mission_id:
        raise StoryError(
            "You're already partway through a mission. Finish or abandon it first."
        )

    # A CLEARED MISSION CANNOT BE REPLAYED.
    #
    # Replays used to be allowed at a quarter rewards, on the theory that
    # re-running a set-piece you liked is harmless. It isn't: story
    # missions hand out fixed, authored payouts and their fights are
    # tuned to be winnable, so the optimal play was to stand on one tile
    # and re-clear the same battle forever. That's a worse grind than
    # /adventure and it hollows out the thing story mode exists to be.
    #
    # Repeatable content belongs in expeditions, domains and raids, which
    # are randomised and balanced for it. A mission is a thing that
    # happened to you; it doesn't happen twice.
    if has_completed(story, mission_id) and not mission.get("repeatable"):
        raise StoryError(
            f"**{mission['name']}** is already done. That one's behind you."
        )

    story.active_mission = mission_id
    story.beat_index = 0
    story.combat_state = None
    db.commit()
    return mission


def abandon(db, player) -> None:
    """Drop the mission in progress. Deliberately loses nothing but the
    position -- flags already set stay set, because they represent
    decisions the player actually made."""
    story = get_or_create(db, player)
    story.active_mission = None
    story.beat_index = 0
    story.combat_state = None
    db.commit()


def advance(db, player, choice_id: str | None = None) -> dict:
    """Resolve the current beat and move to the next one.

    Returns a dict describing what happened, for the cog to render:
        {"text": str|None, "rewards": list[str], "finished": bool}
    """
    state = current_beat(db, player)
    if state is None:
        raise StoryError("You don't have a mission in progress.")
    mission, beat = state
    story = get_or_create(db, player)
    result: dict = {"text": None, "rewards": [], "finished": False}

    kind = beat.get("kind")

    if kind == "choice":
        option = next(
            (o for o in beat.get("options", []) if o["id"] == choice_id), None
        )
        if option is None:
            raise StoryError("That isn't one of the options.")
        if option.get("sets"):
            set_flags(db, story, option["sets"])
        result["text"] = option.get("text")

    elif kind == "reward":
        result["rewards"] = _grant(db, player, beat.get("grant") or {})
        result["text"] = beat.get("text")

    elif kind == "unlock":
        result["text"] = beat.get("text")

    elif kind == "dialogue":
        result["text"] = beat.get("text")

    elif kind == "battle":
        # Battles are advanced by the combat UI, not by this function --
        # reaching here means the fight is already resolved.
        result["text"] = beat.get("on_win")

    story.beat_index += 1
    db.commit()

    if story.beat_index >= len(visible_beats(story, mission)):
        result.update(_finish_mission(db, player, mission))
        result["finished"] = True
    return result


def _finish_mission(db, player, mission: dict) -> dict:
    """Pay out and close the mission.

    A mission marked `repeatable` still pays a fraction on re-clears, but
    nothing in the script is marked that way -- see the block in
    start_mission for why. The fraction is kept so that a genuinely
    repeatable mission (a training-hall type) can exist later without
    also being a money printer."""
    story = get_or_create(db, player)
    replay = has_completed(story, mission["id"])

    grant = dict(mission.get("rewards") or {})
    if replay:
        grant = {
            currency: max(1, int(amount * REPLAY_REWARD_FRACTION))
            for currency, amount in grant.items()
        }
    lines = _grant(db, player, grant)

    _mark_completed(db, story, mission["id"])
    if mission.get("completes_prologue"):
        story.prologue_complete = True

    story.active_mission = None
    story.beat_index = 0
    story.combat_state = None
    db.commit()
    return {"rewards": lines, "replay": replay}


REPLAY_REWARD_FRACTION = 0.25


def _seat_in_free_slot(db, player, template) -> None:
    """Put a story-granted character straight into the squad if there's
    room.

    Granting someone and leaving them on the bench means the very next
    story fight is still fought solo, which defeats the point of granting
    them. Only fills an EMPTY slot -- it never displaces a character the
    player deliberately seated."""
    from bot.database.models.character_model import PlayerCharacter
    from bot.services import character_service

    by_slot = character_service.get_squad_by_slot(db, player)
    free = next((index for index, occupant in sorted(by_slot.items()) if occupant is None), None)
    if free is None:
        return
    pc = (
        db.query(PlayerCharacter)
        .filter_by(player_id=player.id, template_id=template.id)
        .first()
    )
    if pc is not None:
        character_service.set_squad_slot(db, player, free, pc)


def _grant(db, player, grant: dict) -> list[str]:
    """Apply a reward block. Deliberately narrow: currencies and a single
    item. Anything more elaborate belongs in an `encounter` beat, which
    gets the full encounter interpreter for free."""
    from bot.database.models.enums import Rarity
    from bot.services import item_template_service
    from bot.services.currency_service import CURRENCY_EMOJI, VALID_CURRENCIES

    lines: list[str] = []
    for key, amount in grant.items():
        if key == "character":
            # A story-granted character. The prologue needs this: it can
            # unlock /pull, but it cannot make anyone actually press it,
            # and a player who skips pulling reaches the prologue's last
            # fight with a solo level-1 avatar -- which measured 0% win
            # rate at every enemy level tried. A tutorial you cannot pass
            # is worse than no tutorial.
            #
            # Granted through character_service so a story character
            # behaves exactly like a pulled one, including raising
            # Resonance and paying Echoes if it's a duplicate.
            from bot.database.models.character_model import CharacterTemplate
            from bot.services import character_service

            template = db.query(CharacterTemplate).filter_by(name=amount).first()
            if template is None:
                continue
            _, is_new, dupe = character_service.grant_character(db, player, template)
            if is_new:
                _seat_in_free_slot(db, player, template)
                lines.append(f"👥 **{template.name}** joined your squad")
            else:
                echoes = (dupe or {}).get("echoes", 0)
                lines.append(f"👥 **{template.name}** — already with you (+{echoes} ✴️)")
        elif key == "item":
            rarity = Rarity(amount) if isinstance(amount, str) else Rarity.COMMON
            template = item_template_service.pick_random_template(
                db, rng=random.Random(), rarity=rarity
            )
            if template is None:
                continue
            from bot.game.loot.generator import LootGenerator

            item = LootGenerator().generate_item(
                template, player_id=player.id, item_level=1, rarity_override=rarity
            )
            db.add(item)
            db.commit()
            lines.append(f"🎁 **{item.display_name}** ({rarity.value})")
        elif key in VALID_CURRENCIES:
            add_currency(db, player, key, int(amount))
            emoji = CURRENCY_EMOJI.get(key, "")
            lines.append(f"+{int(amount):,} {emoji or key.replace('_', ' ')}")
    return lines
