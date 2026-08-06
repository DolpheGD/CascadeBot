"""
/story -- the main game mode.

The cog is a thin renderer over story_service: it never decides what
happens next, it asks. That's what keeps the whole script validatable by
tools/check_story.py without a Discord connection.

BATTLE BEATS reuse the existing combat stack wholesale -- Battle, the
combat embed, the info/log views -- with one difference: a story battle
is persisted on PlayerStory.combat_state rather than an Expedition, so a
restart mid-fight resumes rather than losing the mission. Same
load -> mutate -> save discipline as expedition combat.

Views here are NOT persistent. A story beat is a moment you're reading
and responding to now; a stale button from yesterday resuming a mission
you've since finished is worse than one that quietly expires.
"""

from __future__ import annotations

import discord

from discord.ext import commands
from discord import app_commands

from bot.utils import responses
from bot.database.session import SessionLocal
from bot.game.combat.battle import Battle
from bot.game.combat.factory import build_enemy_combatant
from bot.game.combat.enemies import get_template_by_name
from bot.game.combat.serialization import battle_from_dict, battle_to_dict
from bot.services import combat_service, map_service, story_service
from bot.services.player_service import get_player
from bot.utils import combat_ui, embedder
from bot.utils.guild_decorator import guild_decorator
from bot.utils.ui_guard import OwnedView, require_player


# ----------------------------------------------------------------------
# Beat progression
# ----------------------------------------------------------------------

class ContinueView(OwnedView):
    """One button. Every non-interactive beat ends here."""

    def __init__(self, owner_id: int | None = None, label: str = "Continue ▶"):
        super().__init__(timeout=600, owner_id=owner_id)
        self.continue_button.label = label

    @discord.ui.button(label="Continue ▶", style=discord.ButtonStyle.primary)
    async def continue_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _advance_and_render(interaction)


class RetryBattleView(OwnedView):
    """The button shown after LOSING a required fight.

    It re-renders the beat you are already on. ContinueView was used
    here, and ContinueView calls _advance_and_render -- so the button
    labelled "Try again" walked you PAST the fight you had just lost,
    collected the on_win text, and carried on. Losing was strictly
    faster than winning.

    The beat pointer was never moved on a loss (advance() only runs when
    won), so re-rendering is all that's needed: the player lands back on
    the same battle intro and fights it again.
    """

    def __init__(self, owner_id: int | None = None):
        super().__init__(timeout=600, owner_id=owner_id)

    @discord.ui.button(label="⚔️ Try again", style=discord.ButtonStyle.primary)
    async def retry(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _render_current(interaction, edit=True)

    @discord.ui.button(label="◀ Back to the map", style=discord.ButtonStyle.secondary)
    async def leave(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _render_map(interaction, edit=True)


class ChoiceView(OwnedView):
    def __init__(self, beat: dict, owner_id: int | None = None):
        super().__init__(timeout=600, owner_id=owner_id)
        for option in beat.get("options", []):
            self.add_item(_ChoiceButton(option))


class _ChoiceButton(discord.ui.Button):
    def __init__(self, option: dict):
        super().__init__(label=option["label"][:80], style=discord.ButtonStyle.secondary)
        self.option_id = option["id"]

    async def callback(self, interaction: discord.Interaction):
        await _advance_and_render(interaction, choice_id=self.option_id)


class StoryMenuView(OwnedView):
    def __init__(self, has_active: bool, has_next: bool, owner_id: int | None = None):
        super().__init__(timeout=600, owner_id=owner_id)
        if not has_next and not has_active:
            self.remove_item(self.begin_button)
            self.remove_item(self.abandon_button)
            return
        self.begin_button.label = "▶ Resume" if has_active else "▶ Begin"
        if not has_active:
            self.remove_item(self.abandon_button)

    @discord.ui.button(label="▶ Begin", style=discord.ButtonStyle.primary)
    async def begin_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        db = SessionLocal()
        try:
            player = get_player(db, interaction.user.id)
            if player is None:
                await responses.send(interaction, "Use `/start` first.", ephemeral=True)
                return
            story = story_service.get_or_create(db, player)
            if not story.active_mission:
                nxt = story_service.next_mission(db, player)
                if nxt is None:
                    await responses.send(interaction,
                        "Nothing left to play just yet.", ephemeral=True
                    )
                    return
                story_service.start_mission(db, player, nxt["id"])
        finally:
            db.close()
        await _render_current(interaction, edit=True)

    @discord.ui.button(label="✖ Abandon", style=discord.ButtonStyle.secondary)
    async def abandon_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        db = SessionLocal()
        try:
            player = get_player(db, interaction.user.id)
            if player is None:
                return
            story_service.abandon(db, player)
        finally:
            db.close()
        await responses.edit(interaction,
            content="Mission abandoned. Anything you decided along the way still stands.",
            embed=None, view=None,
        )


def _reward_block(rewards, bonus) -> str:
    """Reward lines appended to the tile's own text.

    Deliberately part of the SAME message rather than a follow-up: a
    separate 'you got X' embed reads like a system notification, and the
    thing being rewarded here is having bothered to look."""
    out = ""
    if rewards:
        out += "\n\n" + "\n".join(rewards)
    if bonus:
        out += ("\n\n**🏅 You've seen everything in this area.**\n"
                + "\n".join(bonus))
    return out


class HuntOfferView(OwnedView):
    """Optional fights are OPTED INTO. Walking onto a tile and being
    dropped straight into combat is an ambush, not a choice."""

    def __init__(self, owner_id: int | None = None):
        super().__init__(timeout=600, owner_id=owner_id)

    @discord.ui.button(label="⚔️ Take it on", style=discord.ButtonStyle.danger)
    async def fight(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _render_hunt(interaction)

    @discord.ui.button(label="◀ Leave it", style=discord.ButtonStyle.secondary)
    async def leave(self, interaction: discord.Interaction, button: discord.ui.Button):
        db = SessionLocal()
        try:
            player = get_player(db, interaction.user.id)
            story = story_service.get_or_create(db, player)
            story.pending_hunt = None
            db.commit()
        finally:
            db.close()
        await _render_map(interaction, edit=True)


def _open_hunt(db, player):
    """Build or resume the optional fight. Mirrors _open_battle, but the
    state lives on `pending_hunt` so a lost hunt can never disturb a
    mission in progress."""
    story = story_service.get_or_create(db, player)
    hunt = story.pending_hunt
    if not hunt:
        return None, None
    if story.combat_state:
        battle = battle_from_dict(story.combat_state)
    else:
        # Shrines, gear and Research Lab energy, exactly as adventure
        # builds them -- see combat_service.build_player_party.
        party = combat_service.build_player_party(db, player, full_hp=True)
        enemies = [build_enemy_combatant(get_template_by_name(n), hunt["level"])
                   for n in hunt["enemies"]]
        battle = Battle(party, enemies)
        story.combat_state = battle_to_dict(battle)
        db.commit()
    _advance_to_player_turn(battle)
    story.combat_state = battle_to_dict(battle)
    db.commit()
    embed = embedder.combat_embed(battle)
    embed.set_author(name="Optional — losing costs you nothing")
    return embed, HuntCombatView(owner_id=player.id, battle=battle)


async def _render_hunt(interaction: discord.Interaction, edit: bool = True):
    db = SessionLocal()
    try:
        player = get_player(db, interaction.user.id)
        embed, view = _open_hunt(db, player)
    finally:
        db.close()
    if embed is None:
        await _render_map(interaction, edit=True)
        return
    await responses.edit(interaction, embed=embed, view=view)


async def _hunt_action(interaction: discord.Interaction, action: str,
                       ability_id: str | None = None):
    db = SessionLocal()
    finished = None
    embed = view = None
    try:
        player = get_player(db, interaction.user.id)
        story = story_service.get_or_create(db, player)
        if not story.combat_state or not story.pending_hunt:
            await responses.send(interaction, "No fight in progress.", ephemeral=True)
            return
        battle = battle_from_dict(story.combat_state)
        if battle.current_actor() not in battle.party:
            await responses.send(interaction, "It's not your turn.", ephemeral=True)
            return
        battle.take_party_action(action, ability_id=ability_id)
        _advance_to_player_turn(battle)
        story.combat_state = battle_to_dict(battle)
        db.commit()
        if battle.is_over():
            hunt = dict(story.pending_hunt)
            combat_service.sync_party_hp_to_characters(db, battle)
            story.combat_state = None
            db.commit()
            rewards = map_service.finish_hunt(
                db, story, hunt["area"], hunt["char"], won=(battle.result == "won"))
            finished = (battle.result == "won", rewards)
        else:
            embed = embedder.combat_embed(battle)
            view = HuntCombatView(owner_id=player.id, battle=battle)
    finally:
        db.close()

    if finished is None:
        await responses.edit(interaction, embed=embed, view=view)
        return
    won, rewards = finished
    if not won:
        await responses.edit(interaction,
            embed=discord.Embed(
                title="Driven off",
                description=("You back out of it. Nothing is lost — it was optional, and "
                             "it'll still be there."),
                color=discord.Color.dark_grey()),
            view=BackToMapView(owner_id=interaction.user.id))
        return
    await responses.edit(interaction,
        embed=discord.Embed(
            title="⚔️ Cleared",
            description=_reward_block(rewards, None).strip() or "Done.",
            color=discord.Color.gold()),
        view=BackToMapView(owner_id=interaction.user.id))


# ----------------------------------------------------------------------
# The overworld
#
# The map is the LANDING SCREEN for /story, not a sub-page. With no
# mission in progress you're standing somewhere, and the chapter list
# moved to a Journal button.
#
# That ordering is the whole point of the map: a menu asks "which of
# these do you pick", a map asks "where do you go", and only the second
# one produces a place you remember. The Journal still exists because
# "what have I actually done" is a question a menu answers better than a
# grid ever will.
# ----------------------------------------------------------------------

# Discord packs buttons LEFT within a row, so a d-pad written as
# up / left-interact-right / down comes out as a left-justified staircase
# rather than a cross. There's no alignment property to set; the only way
# to centre a control is to occupy the cells beside it.
#
# So rows 0 and 2 carry a disabled, blank-labelled spacer on either side
# of the arrow. They're inert by construction -- disabled, zero-width
# label, no callback that does anything -- and they cost 4 of the 25
# components a view gets, which is affordable at 11 total.
_SPACER_LABEL = "\u200b"  # zero-width space: Discord requires a non-empty label


class _Spacer(discord.ui.Button):
    def __init__(self, row: int):
        super().__init__(label=_SPACER_LABEL, style=discord.ButtonStyle.secondary,
                         disabled=True, row=row)

    async def callback(self, interaction: discord.Interaction):  # pragma: no cover
        return


class MapView(OwnedView):
    """A d-pad and an interact button, laid out as an actual cross.

    Directions that would walk into a wall are DISABLED rather than
    missing: a button that moves position between renders is a button
    you misclick. Same reason the cross is fixed even when only one
    direction is legal.
    """

    def __init__(self, state: dict, owner_id: int | None = None):
        super().__init__(timeout=900, owner_id=owner_id)
        available = set(state.get("directions", []))
        self.north_button.disabled = "north" not in available
        self.south_button.disabled = "south" not in available
        self.west_button.disabled = "west" not in available
        self.east_button.disabled = "east" not in available
        # Nothing under your feet means nothing to interact with, and a
        # live button that always answers "nothing here" trains the
        # player to stop pressing it.
        self.interact_button.disabled = state.get("content") is None

        # Inserted rather than declared so they sit either side of the
        # arrow: decorator order fixes position within a row.
        self.add_item(_Spacer(row=0))
        self.add_item(_Spacer(row=0))
        self.add_item(_Spacer(row=2))
        self.add_item(_Spacer(row=2))
        self._centre_row(0, self.north_button)
        self._centre_row(2, self.south_button)

    def _centre_row(self, row: int, control: discord.ui.Button) -> None:
        """Reorder `row` to spacer / control / spacer."""
        in_row = [item for item in self.children if getattr(item, "row", None) == row]
        others = [item for item in self.children if getattr(item, "row", None) != row]
        spacers = [item for item in in_row if item is not control]
        ordered = others + [spacers[0], control, spacers[1]] if len(spacers) >= 2 else None
        if ordered is None:
            return
        self.clear_items()
        for item in ordered:
            self.add_item(item)

    @discord.ui.button(label="⬆️", style=discord.ButtonStyle.secondary, row=0)
    async def north_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _move(interaction, "north")

    @discord.ui.button(label="⬅️", style=discord.ButtonStyle.secondary, row=1)
    async def west_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _move(interaction, "west")

    @discord.ui.button(label="✋", style=discord.ButtonStyle.primary, row=1)
    async def interact_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _interact(interaction)

    @discord.ui.button(label="➡️", style=discord.ButtonStyle.secondary, row=1)
    async def east_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _move(interaction, "east")

    @discord.ui.button(label="⬇️", style=discord.ButtonStyle.secondary, row=2)
    async def south_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _move(interaction, "south")

    @discord.ui.button(label="📖 Journal", style=discord.ButtonStyle.secondary, row=3)
    async def journal_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        db = SessionLocal()
        try:
            player = get_player(db, interaction.user.id)
            if player is None:
                await responses.send(interaction, "Use `/start` first.", ephemeral=True)
                return
            story = story_service.get_or_create(db, player)
            nxt = story_service.next_mission(db, player)
            embed = embedder.story_menu_embed(story, nxt, player)
        finally:
            db.close()
        # Ephemeral so the map message stays put -- the journal is a
        # thing you glance at, not a place you navigate to.
        await responses.send(interaction, embed=embed, ephemeral=True)


class BackToMapView(OwnedView):
    """Shown under a note. One way back, so a flavour tile can never
    become a place the player is stuck."""

    def __init__(self, owner_id: int | None = None):
        super().__init__(timeout=900, owner_id=owner_id)

    @discord.ui.button(label="◀ Back", style=discord.ButtonStyle.secondary)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _render_map(interaction, edit=True)


def _map_screen(db, player):
    story = story_service.get_or_create(db, player)
    state = map_service.look(db, story)
    content = state["content"]
    standing_on = None
    if content:
        standing_on = f"{content.get('emoji', '')} **{content.get('name', '')}**".strip()
        if state["done"]:
            standing_on += " — already done"
    embed = embedder.story_map_embed(
        area=state["area"],
        grid=map_service.render(db, story),
        legend=map_service.legend_lines(db, story),
        standing_on=standing_on,
        locked=state["locked"],
    )
    return embed, MapView(state, owner_id=player.id)


async def _render_map(interaction: discord.Interaction, edit: bool):
    db = SessionLocal()
    try:
        player = get_player(db, interaction.user.id)
        if player is None:
            await responses.send(interaction, "Use `/start` first.", ephemeral=True)
            return
        embed, view = _map_screen(db, player)
    finally:
        db.close()
    if edit:
        await responses.edit(interaction, embed=embed, view=view)
    else:
        await responses.send(interaction, embed=embed, view=view)


async def _move(interaction: discord.Interaction, direction: str):
    db = SessionLocal()
    try:
        player = get_player(db, interaction.user.id)
        if player is None:
            await responses.send(interaction, "Use `/start` first.", ephemeral=True)
            return
        story = story_service.get_or_create(db, player)
        try:
            map_service.move(db, story, direction)
        except map_service.MapError as exc:
            await responses.send(interaction, str(exc), ephemeral=True)
            return
        embed, view = _map_screen(db, player)
    finally:
        db.close()
    await responses.edit(interaction, embed=embed, view=view)


async def _interact(interaction: discord.Interaction):
    """Resolve the tile underfoot.

    map_service decides WHAT the tile is; starting a mission still goes
    through story_service.start_mission, the same call the Journal's
    Begin button makes. One start path, one place for the beat index to
    be set.
    """
    db = SessionLocal()
    started = False
    note = None
    try:
        player = get_player(db, interaction.user.id)
        if player is None:
            await responses.send(interaction, "Use `/start` first.", ephemeral=True)
            return
        story = story_service.get_or_create(db, player)
        result = map_service.interact(db, story)
        kind = result["kind"]

        if kind == "nothing":
            await responses.send(interaction, "There's nothing here.", ephemeral=True)
            return

        if kind in ("locked", "done", "spent"):
            await responses.send(interaction, result["text"], ephemeral=True)
            return

        if kind == "cache":
            note = {
                "name": result["name"], "emoji": result["emoji"],
                "text": (result.get("text") or "")
                        + _reward_block(result.get("rewards"), result.get("bonus")),
            }
        elif kind == "hunt":
            # Accepting an optional fight is a deliberate press, so the
            # tile shows what it is FIRST and the player opts in. An
            # optional fight you're dropped into is just an ambush.
            story.pending_hunt = {
                "area": result["area_id"], "char": result["char"],
                "enemies": result["enemies"], "level": result["level"],
            }
            story.combat_state = None
            db.commit()
            hunt = result


        if kind == "note":
            note = {
                "name": result["name"], "emoji": result["emoji"],
                "text": (result.get("text") or "") + _reward_block(None, result.get("bonus")),
            }
        elif kind == "exit":
            map_service.travel(db, story, result["to_area"], result["to"])
        elif kind == "mission":
            try:
                story_service.start_mission(db, player, result["mission"])
                started = True
            except story_service.StoryError as exc:
                await responses.send(interaction, str(exc), ephemeral=True)
                return

        if kind == "hunt":
            embed = embedder.story_note_embed(hunt["name"], hunt["emoji"], hunt["text"])
            view = HuntOfferView(owner_id=player.id)
        elif not started:
            embed, view = (
                (embedder.story_note_embed(note["name"], note["emoji"], note["text"]),
                 BackToMapView(owner_id=player.id))
                if note else _map_screen(db, player)
            )
    finally:
        db.close()

    if started:
        await _render_current(interaction, edit=True)
        return
    await responses.edit(interaction, embed=embed, view=view)


# ----------------------------------------------------------------------
# Rendering
# ----------------------------------------------------------------------

async def _render_current(interaction: discord.Interaction, edit: bool, extra_text: str | None = None):
    """Draw whatever beat the player is now sitting on."""
    db = SessionLocal()
    try:
        player = get_player(db, interaction.user.id)
        if player is None:
            await responses.send(interaction, "Use `/start` first.", ephemeral=True)
            return

        state = story_service.current_beat(db, player)
        if state is None:
            # Falling out of a mission puts you back on the map, not in a
            # menu. The map is where the game lives now; the menu would
            # be a detour on the way to the same place.
            need_map = True
        else:
            need_map = False

        if need_map:
            embed, view = _map_screen(db, player)
            mission = beat = None
        else:
            mission, beat = state
        if not need_map and beat.get("kind") == "battle":
            embed, view = _open_battle(db, player, mission, beat)
        elif not need_map:
            embed = embedder.story_beat_embed(mission, beat, text=extra_text)
            view = (ChoiceView(beat, owner_id=player.id) if beat.get("kind") == "choice"
                    else ContinueView(owner_id=player.id))
    finally:
        db.close()

    if edit:
        await responses.edit(interaction, embed=embed, view=view)
    else:
        await responses.send(interaction, embed=embed, view=view)


async def _advance_and_render(interaction: discord.Interaction, choice_id: str | None = None):
    db = SessionLocal()
    finished = None
    mission = None
    try:
        player = get_player(db, interaction.user.id)
        if player is None:
            await responses.send(interaction, "Use `/start` first.", ephemeral=True)
            return
        state = story_service.current_beat(db, player)
        mission = state[0] if state else None
        try:
            result = story_service.advance(db, player, choice_id=choice_id)
        except story_service.StoryError as exc:
            await responses.send(interaction, str(exc), ephemeral=True)
            return
        if result["finished"]:
            finished = result
    finally:
        db.close()

    if finished is not None and mission is not None:
        await responses.edit(interaction,
            embed=embedder.story_mission_complete_embed(mission, finished),
            view=BackToMapView(owner_id=interaction.user.id),
        )
        return
    # The result TEXT of a choice belongs on the next screen, so the
    # player sees what their pick actually did rather than it flashing
    # past on the way to the following beat.
    await _render_current(interaction, edit=True,
                          extra_text=(result.get("text") if choice_id else None))


async def _send_menu(interaction: discord.Interaction, db, player, edit: bool):
    story = story_service.get_or_create(db, player)
    nxt = story_service.next_mission(db, player)
    embed = embedder.story_menu_embed(story, nxt, player)
    view = StoryMenuView(bool(story.active_mission), nxt is not None, owner_id=player.id)
    if edit:
        await responses.edit(interaction, embed=embed, view=view)
    else:
        await responses.send(interaction, embed=embed, view=view)


# ----------------------------------------------------------------------
# Battle beats
# ----------------------------------------------------------------------

def _open_battle(db, player, mission: dict, beat: dict):
    """Build (or resume) the fight for a battle beat."""
    story = story_service.get_or_create(db, player)
    if story.combat_state:
        battle = battle_from_dict(story.combat_state)
    else:
        # Story fights always start the squad at full HP. A scripted
        # beat you must clear to progress is the wrong place to inherit
        # attrition from an unrelated expedition.
        #
        # Built through combat_service so shrine bonuses and the Research
        # Lab's starting energy apply here too -- building the party
        # inline meant every shrine level the player had paid for did
        # nothing in story mode, which is why story stats didn't match
        # adventure stats for the same character.
        party = combat_service.build_player_party(db, player, full_hp=True)
        enemies = [
            build_enemy_combatant(get_template_by_name(name), beat.get("level", 5))
            for name in beat["enemies"]
        ]
        battle = Battle(party, enemies)
        story.combat_state = battle_to_dict(battle)
        db.commit()

    _advance_to_player_turn(battle)
    story.combat_state = battle_to_dict(battle)
    db.commit()

    embed = embedder.combat_embed(battle)
    return embed, StoryCombatView(owner_id=player.id, battle=battle)


def _advance_to_player_turn(battle: Battle) -> bool:
    while not battle.is_over() and battle.current_actor() in battle.enemies:
        battle.take_enemy_turn()
    return battle.is_over()


class StoryCombatView(OwnedView):
    # Which resolver every control in this view reports to. Subclasses
    # override it once here instead of re-listing every component.
    combat_handler = staticmethod(lambda *a, **k: _story_combat_action(*a, **k))

    def __init__(self, owner_id: int | None = None, battle: Battle | None = None):
        super().__init__(timeout=900, owner_id=owner_id)
        if battle is None:
            return
        actor = battle.current_actor()
        if actor is None or actor not in battle.party:
            return
        self.ultimate_button.disabled = not actor.ultimate_ready()
        self.ultimate_button.label = combat_ui.ultimate_button_label(actor)
        options = []
        for ability in actor.active_abilities:
            ready = actor.ability_ready(ability)
            unit = "SP" if ability["resource_type"] == "mana" else "EN"
            status = "Ready" if ready else f"{ability['resource_cost']} {unit}"
            options.append(discord.SelectOption(
                label=f"{ability['name']} -- {status}"[:100],
                value=ability["id"], description=ability["description"][:100],
            ))
        if options:
            self.add_item(_StoryAbilitySelect(options, self.combat_handler))

    @discord.ui.button(label="⚔️ Attack", style=discord.ButtonStyle.danger)
    async def attack_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _story_combat_action(interaction, "attack")

    @discord.ui.button(label="💥 Ultimate", style=discord.ButtonStyle.success)
    async def ultimate_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _story_combat_action(interaction, "ultimate")

    @discord.ui.button(label="🛡️ Guard", style=discord.ButtonStyle.primary)
    async def guard_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _story_combat_action(interaction, "guard")

    @discord.ui.button(label="ℹ️ Info", style=discord.ButtonStyle.secondary, row=4)
    async def info_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        db = SessionLocal()
        try:
            player = get_player(db, interaction.user.id)
            story = story_service.get_or_create(db, player) if player else None
            if story is None or not story.combat_state:
                await responses.send(interaction, "No fight in progress.", ephemeral=True)
                return
            battle = battle_from_dict(story.combat_state)
        finally:
            db.close()
        embed, view = combat_ui.info_response(battle)
        await responses.send(interaction, embed=embed, view=view, ephemeral=True)


class _StoryAbilitySelect(discord.ui.Select):
    """The skill dropdown, told WHICH resolver it belongs to.

    It used to hardcode _story_combat_action. HuntCombatView overrides
    the three buttons to use _hunt_action but inherits this Select from
    StoryCombatView.__init__ -- so clearing an OPTIONAL fight with a
    skill ran the MISSION resolver, which calls story_service.advance()
    and reads on_win off whatever beat you happened to be sitting on.
    An optional side fight advanced the main story.

    Attack/Ultimate/Guard were fine, which is why it looked intermittent:
    it only broke when the killing blow was a skill.
    """

    def __init__(self, options: list[discord.SelectOption], handler):
        super().__init__(placeholder="Use a skill...", options=options,
                         min_values=1, max_values=1)
        self._handler = handler

    async def callback(self, interaction: discord.Interaction):
        await self._handler(interaction, "ability", ability_id=self.values[0])


async def _story_combat_action(interaction: discord.Interaction, action: str,
                               ability_id: str | None = None):
    db = SessionLocal()
    outcome = None
    try:
        player = get_player(db, interaction.user.id)
        if player is None:
            await responses.send(interaction, "Use `/start` first.", ephemeral=True)
            return
        story = story_service.get_or_create(db, player)
        if not story.combat_state:
            await responses.send(interaction, "No fight in progress.", ephemeral=True)
            return

        battle = battle_from_dict(story.combat_state)
        if battle.current_actor() not in battle.party:
            await responses.send(interaction, "It's not your turn.", ephemeral=True)
            return

        battle.take_party_action(action, ability_id=ability_id)
        _advance_to_player_turn(battle)
        story.combat_state = battle_to_dict(battle)
        db.commit()

        if battle.is_over():
            state = story_service.current_beat(db, player)
            beat = state[1] if state else {}
            won = battle.result == "won"
            # Write HP back: downed characters get up at 1 HP after a
            # fight the squad survived, and a WIPE writes 0 through so the
            # roster actually shows them dead. Story fights start at full
            # HP regardless (see _open_battle), so this costs the player
            # nothing mechanically -- it just stops the display lying
            # about who is standing.
            combat_service.sync_party_hp_to_characters(db, battle)
            story.combat_state = None
            db.commit()
            if won:
                result = story_service.advance(db, player)
                outcome = ("won", beat.get("on_win"), result,
                           state[0] if state else None)
            else:
                # A scripted beat you must clear to progress is the wrong
                # place to end a run. Losing retries the fight rather than
                # dumping the player out of the mission -- see
                # `retry_on_loss` in story_config.
                outcome = ("lost", beat.get("on_lose"), None, None)
        else:
            embed = embedder.combat_embed(battle)
            view = StoryCombatView(owner_id=player.id, battle=battle)
    finally:
        db.close()

    if outcome is None:
        await responses.edit(interaction, embed=embed, view=view)
        return

    status, text, result, mission = outcome
    if status == "lost":
        await responses.edit(interaction,
            embed=discord.Embed(
                title="💀 Driven back",
                description=(text or "You're forced back.")
                            + "\n\n**You have to clear this one to go on.**",
                color=discord.Color.dark_red(),
            ),
            view=RetryBattleView(owner_id=interaction.user.id),
        )
        return

    if result and result.get("finished") and mission is not None:
        await responses.edit(interaction,
            embed=embedder.story_mission_complete_embed(mission, result),
            view=BackToMapView(owner_id=interaction.user.id),
        )
        return
    await _render_current(interaction, edit=True, extra_text=text)


@guild_decorator
class Story(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="story", description="Play the story -- the main mode.")
    async def story(self, ctx: discord.Interaction):
        await responses.defer(ctx)
        db = SessionLocal()
        try:
            player = get_player(db, ctx.user.id)
            if not await require_player(ctx, player):
                return
            state = story_service.current_beat(db, player)
        finally:
            db.close()

        if state is not None:
            await _render_current(ctx, edit=False)
            return
        await _render_map(ctx, edit=False)




class HuntCombatView(StoryCombatView):
    """Identical controls to a story fight; only the resolution differs."""

    combat_handler = staticmethod(lambda *a, **k: _hunt_action(*a, **k))

    @discord.ui.button(label="⚔️ Attack", style=discord.ButtonStyle.danger)
    async def attack_button(self, interaction, button):
        await _hunt_action(interaction, "attack")

    @discord.ui.button(label="💥 Ultimate", style=discord.ButtonStyle.success)
    async def ultimate_button(self, interaction, button):
        await _hunt_action(interaction, "ultimate")

    @discord.ui.button(label="🛡️ Guard", style=discord.ButtonStyle.primary)
    async def guard_button(self, interaction, button):
        await _hunt_action(interaction, "guard")


async def setup(bot):
    await bot.add_cog(Story(bot))
