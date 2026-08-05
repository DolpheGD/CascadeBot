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

from bot.database.session import SessionLocal
from bot.game.combat.battle import Battle
from bot.game.combat.factory import build_enemy_combatant, build_party_combatants
from bot.game.combat.enemies import get_template_by_name
from bot.game.combat.serialization import battle_from_dict, battle_to_dict
from bot.services import character_service, story_service
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
                await interaction.response.send_message("Use `/start` first.", ephemeral=True)
                return
            story = story_service.get_or_create(db, player)
            if not story.active_mission:
                nxt = story_service.next_mission(db, player)
                if nxt is None:
                    await interaction.response.send_message(
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
        await interaction.response.edit_message(
            content="Mission abandoned. Anything you decided along the way still stands.",
            embed=None, view=None,
        )


# ----------------------------------------------------------------------
# Rendering
# ----------------------------------------------------------------------

async def _render_current(interaction: discord.Interaction, edit: bool, extra_text: str | None = None):
    """Draw whatever beat the player is now sitting on."""
    db = SessionLocal()
    try:
        player = get_player(db, interaction.user.id)
        if player is None:
            await interaction.response.send_message("Use `/start` first.", ephemeral=True)
            return

        state = story_service.current_beat(db, player)
        if state is None:
            await _send_menu(interaction, db, player, edit=edit)
            return

        mission, beat = state
        if beat.get("kind") == "battle":
            embed, view = _open_battle(db, player, mission, beat)
        else:
            embed = embedder.story_beat_embed(mission, beat, text=extra_text)
            view = (ChoiceView(beat, owner_id=player.id) if beat.get("kind") == "choice"
                    else ContinueView(owner_id=player.id))
    finally:
        db.close()

    if edit:
        await interaction.response.edit_message(embed=embed, view=view)
    else:
        await interaction.response.send_message(embed=embed, view=view)


async def _advance_and_render(interaction: discord.Interaction, choice_id: str | None = None):
    db = SessionLocal()
    finished = None
    mission = None
    try:
        player = get_player(db, interaction.user.id)
        if player is None:
            await interaction.response.send_message("Use `/start` first.", ephemeral=True)
            return
        state = story_service.current_beat(db, player)
        mission = state[0] if state else None
        try:
            result = story_service.advance(db, player, choice_id=choice_id)
        except story_service.StoryError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        if result["finished"]:
            finished = result
    finally:
        db.close()

    if finished is not None and mission is not None:
        await interaction.response.edit_message(
            embed=embedder.story_mission_complete_embed(mission, finished), view=None
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
        await interaction.response.edit_message(embed=embed, view=view)
    else:
        await interaction.response.send_message(embed=embed, view=view)


# ----------------------------------------------------------------------
# Battle beats
# ----------------------------------------------------------------------

def _open_battle(db, player, mission: dict, beat: dict):
    """Build (or resume) the fight for a battle beat."""
    story = story_service.get_or_create(db, player)
    if story.combat_state:
        battle = battle_from_dict(story.combat_state)
    else:
        squad = character_service.get_squad(db, player)
        equipped = character_service.get_equipped_items_by_character(db, [c.id for c in squad])
        party = build_party_combatants(squad, equipped)
        # Story fights always start the squad at full HP. A scripted
        # beat you must clear to progress is the wrong place to inherit
        # attrition from an unrelated expedition.
        for member in party:
            member.current_hp = member.max_hp
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
            self.add_item(_StoryAbilitySelect(options))

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
                await interaction.response.send_message("No fight in progress.", ephemeral=True)
                return
            battle = battle_from_dict(story.combat_state)
        finally:
            db.close()
        embed, view = combat_ui.info_response(battle)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class _StoryAbilitySelect(discord.ui.Select):
    def __init__(self, options: list[discord.SelectOption]):
        super().__init__(placeholder="Use a skill...", options=options,
                         min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        await _story_combat_action(interaction, "ability", ability_id=self.values[0])


async def _story_combat_action(interaction: discord.Interaction, action: str,
                               ability_id: str | None = None):
    db = SessionLocal()
    outcome = None
    try:
        player = get_player(db, interaction.user.id)
        if player is None:
            await interaction.response.send_message("Use `/start` first.", ephemeral=True)
            return
        story = story_service.get_or_create(db, player)
        if not story.combat_state:
            await interaction.response.send_message("No fight in progress.", ephemeral=True)
            return

        battle = battle_from_dict(story.combat_state)
        if battle.current_actor() not in battle.party:
            await interaction.response.send_message("It's not your turn.", ephemeral=True)
            return

        battle.take_party_action(action, ability_id=ability_id)
        _advance_to_player_turn(battle)
        story.combat_state = battle_to_dict(battle)
        db.commit()

        if battle.is_over():
            state = story_service.current_beat(db, player)
            beat = state[1] if state else {}
            won = battle.result == "won"
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
        await interaction.response.edit_message(embed=embed, view=view)
        return

    status, text, result, mission = outcome
    if status == "lost":
        await interaction.response.edit_message(
            embed=discord.Embed(
                title="💀 Driven back",
                description=(text or "You're forced back.") + "\n\nTry the fight again.",
                color=discord.Color.dark_red(),
            ),
            view=ContinueView(owner_id=interaction.user.id, label="Try again ▶"),
        )
        return

    if result and result.get("finished") and mission is not None:
        await interaction.response.edit_message(
            embed=embedder.story_mission_complete_embed(mission, result), view=None
        )
        return
    await _render_current(interaction, edit=True, extra_text=text)


@guild_decorator
class Story(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="story", description="Play the story -- the main mode.")
    async def story(self, ctx: discord.Interaction):
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
        db = SessionLocal()
        try:
            player = get_player(db, ctx.user.id)
            await _send_menu(ctx, db, player, edit=False)
        finally:
            db.close()


async def setup(bot):
    await bot.add_cog(Story(bot))
