import discord

from discord.ext import commands
from discord import app_commands

from bot.database.session import SessionLocal
from bot.services.player_service import get_player
from bot.services import dungeon_service, combat_service
from bot.utils import embedder
from bot.utils.guild_decorator import guild_decorator


# ----------------------------------------------------------------------
# Persistent Views
#
# These are registered ONCE at bot startup (see bot/client.py) and never
# expire (timeout=None). Every callback re-derives the player's actual
# state from the database using interaction.user.id -- nothing about which
# expedition/battle a message belongs to is stored on the View itself. That
# is what makes these buttons keep working correctly even after a full bot
# restart, or if the player doesn't touch the message for a week: the menu
# was never the source of truth, the database always was.
#
# Select components use a FIXED custom_id and are rebuilt with fresh
# options on every render -- Discord delivers whatever the user actually
# picked on THAT message regardless of what a freshly-registered dummy
# view's default options happen to be, so this survives restarts exactly
# like the button DynamicItems do.
# ----------------------------------------------------------------------

class MoveSelect(discord.ui.Select):
    def __init__(self, options: list[discord.SelectOption] | None = None):
        options = options or [discord.SelectOption(label="...", value="none")]
        super().__init__(
            placeholder="Choose your path...",
            options=options,
            custom_id="cascade_move_select",
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction):
        await _handle_move(interaction, self.values[0])


class DungeonView(discord.ui.View):
    def __init__(self, options: list[discord.SelectOption] | None = None):
        super().__init__(timeout=None)
        self.add_item(MoveSelect(options))


class AbilitySelect(discord.ui.Select):
    def __init__(self, options: list[discord.SelectOption]):
        super().__init__(
            placeholder="Use a skill (costs Mana)...",
            options=options,
            custom_id="cascade_ability_select",
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction):
        await _handle_combat_action(interaction, "ability", ability_id=self.values[0])


class TargetSelect(discord.ui.Select):
    """Switching targets is a free action -- it does not end the player's
    turn, it just changes who Attack/Ability/Ultimate will hit next."""
    def __init__(self, options: list[discord.SelectOption]):
        super().__init__(
            placeholder="🎯 Switch target...",
            options=options,
            custom_id="cascade_target_select",
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction):
        await _handle_select_target(interaction, int(self.values[0]))


class CombatView(discord.ui.View):
    def __init__(
        self,
        ability_options: list[discord.SelectOption] | None = None,
        target_options: list[discord.SelectOption] | None = None,
        ultimate_ready: bool = False,
        ultimate_exists: bool = False,
    ):
        super().__init__(timeout=None)
        self.attack_button.disabled = False
        self.ultimate_button.disabled = not ultimate_ready
        self.ultimate_button.label = "💥 Ultimate" if ultimate_exists else "💥 No Ultimate"
        if not ultimate_exists:
            self.remove_item(self.ultimate_button)

        if ability_options:
            self.add_item(AbilitySelect(ability_options))
        if target_options:
            self.add_item(TargetSelect(target_options))

    @discord.ui.button(label="⚔️ Attack", style=discord.ButtonStyle.danger, custom_id="cascade_attack")
    async def attack_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _handle_combat_action(interaction, "attack")

    @discord.ui.button(label="💥 Ultimate", style=discord.ButtonStyle.success, custom_id="cascade_ultimate")
    async def ultimate_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _handle_combat_action(interaction, "ultimate")


def _build_dungeon_view(expedition) -> DungeonView | None:
    if expedition.status.value != "active":
        return None
    node = expedition.graph["nodes"][expedition.current_node_id]
    moves = node["edges"]
    if not moves:
        return None

    options = []
    for node_id in moves:
        target = expedition.graph["nodes"][node_id]
        emoji = embedder.ROOM_TYPE_EMOJI.get(target["room_type"], "❔")
        options.append(discord.SelectOption(
            label=f"{target['room_type'].title()} (Floor {target['floor']})",
            value=node_id,
            emoji=emoji,
        ))
    return DungeonView(options)


def _build_combat_view(battle) -> CombatView:
    ability_options = []
    for ability in battle.player.active_abilities:
        ready = battle.player.ability_ready(ability)
        source_icon = "⚔️" if ability.get("source") == "weapon" else "🔮"
        label = f"{source_icon} {ability['name']}" if ready else f"{source_icon} {ability['name']} (not ready)"
        ability_options.append(discord.SelectOption(
            label=label[:100],
            value=ability["id"],
            description=ability["description"][:100],
        ))

    living = battle.living_enemies()
    target_options = []
    if len(living) > 1:
        for i, enemy in enumerate(living):
            marker = "🎯 " if i == battle.player_target_index else ""
            target_options.append(discord.SelectOption(
                label=f"{marker}{enemy.name} ({enemy.current_hp}/{enemy.max_hp} HP)"[:100],
                value=str(i),
                default=(i == battle.player_target_index),
            ))

    return CombatView(
        ability_options or None,
        target_options or None,
        ultimate_ready=battle.player.ultimate_ready(),
        ultimate_exists=battle.player.ultimate_ability is not None,
    )


def _battle_end_message(summary: dict) -> str | None:
    kind = summary["kind"]
    if kind == "victory":
        r = summary["rewards"]
        text = f"You return to the path, 🪙 {r['gold']} gold and ✨ {r['xp']} XP richer."
        if r["items"]:
            names = ", ".join(f"**{i.display_name}** ({i.rarity.value})" for i in r["items"])
            text += f"\nYou also found: {names}!"
        return text
    if kind == "expedition_complete":
        r = summary["rewards"]
        text = f"🏆 You defeated the boss! Expedition complete. (+🪙{r['gold']} gold, +✨{r['xp']} XP)"
        if r["items"]:
            names = ", ".join(f"**{i.display_name}** ({i.rarity.value})" for i in r["items"])
            text += f"\nBoss drop: {names}!"
        return text
    if kind == "defeat":
        return "💀 You have fallen. The expedition ends here."
    return None


def _advance_to_player_or_end(db, expedition, player, battle) -> dict | None:
    """Resolves every enemy turn (including a faster enemy acting before the
    player ever gets to move) until it's the player's turn or the battle
    ends. Without this, a battle where an enemy outspeeds the player would
    render the CombatView with the enemy's turn still pending, and the
    player's first click would be rejected as 'not your turn' with nothing
    left to advance it -- a deadlock. Returns the end-of-battle summary if
    the fight ended during this drive, else None (and the battle is saved)."""
    while not battle.is_over() and battle.current_actor() is not battle.player:
        battle.take_enemy_turn()

    if battle.is_over():
        return dungeon_service.resolve_battle_end(db, expedition, player, battle)

    combat_service.save_battle(db, expedition, battle)
    return None


# ----------------------------------------------------------------------
# Interaction handlers -- own their own DB session, exactly like a cog
# command would. Views call into these rather than talking to the
# database directly, keeping the persistence pattern in one place.
# ----------------------------------------------------------------------

async def _handle_move(interaction: discord.Interaction, target_node_id: str):
    db = SessionLocal()
    try:
        player = get_player(db, interaction.user.id)
        if player is None:
            await interaction.response.send_message("Use `/start` first.", ephemeral=True)
            return

        expedition = dungeon_service.get_active_expedition(db, player.id)
        if expedition is None:
            await interaction.response.send_message(
                "You don't have an active expedition. Use `/adventure`.", ephemeral=True
            )
            return

        ok, msg = dungeon_service.move_to_node(db, expedition, target_node_id)
        if not ok:
            await interaction.response.send_message(msg, ephemeral=True)
            return

        result = dungeon_service.enter_node(db, expedition, player)
        avatar_url = interaction.user.display_avatar.url

        if result["kind"] == "combat":
            battle = combat_service.load_battle(expedition)
            summary = _advance_to_player_or_end(db, expedition, player, battle)

            if summary is not None:
                await interaction.response.edit_message(
                    embed=embedder.combat_embed(battle, avatar_url=avatar_url), view=None
                )
                follow_up_text = _battle_end_message(summary)
                if follow_up_text:
                    await interaction.followup.send(
                        embed=embedder.dungeon_map_embed(expedition, follow_up_text, avatar_url=avatar_url),
                        view=_build_dungeon_view(expedition),
                    )
            else:
                await interaction.response.edit_message(
                    embed=embedder.combat_embed(battle, avatar_url=avatar_url), view=_build_combat_view(battle)
                )
        else:
            await interaction.response.edit_message(
                embed=embedder.dungeon_map_embed(expedition, result["message"], avatar_url=avatar_url),
                view=_build_dungeon_view(expedition),
            )
    finally:
        db.close()


async def _handle_combat_action(interaction: discord.Interaction, action: str, ability_id: str | None = None):
    db = SessionLocal()
    try:
        player = get_player(db, interaction.user.id)
        if player is None:
            await interaction.response.send_message("Use `/start` first.", ephemeral=True)
            return

        expedition = dungeon_service.get_active_expedition(db, player.id)
        if expedition is None or not expedition.combat_state:
            await interaction.response.send_message(
                "You're not in a battle right now.", ephemeral=True
            )
            return

        battle = combat_service.load_battle(expedition)
        if battle.current_actor() is not battle.player:
            await interaction.response.send_message("It's not your turn yet.", ephemeral=True)
            return

        battle.take_player_action(action, ability_id=ability_id)
        summary = _advance_to_player_or_end(db, expedition, player, battle)
        avatar_url = interaction.user.display_avatar.url

        if summary is not None:
            await interaction.response.edit_message(
                embed=embedder.combat_embed(battle, avatar_url=avatar_url), view=None
            )

            follow_up_text = _battle_end_message(summary)
            if follow_up_text:
                await interaction.followup.send(
                    embed=embedder.dungeon_map_embed(expedition, follow_up_text, avatar_url=avatar_url),
                    view=_build_dungeon_view(expedition),
                )
        else:
            await interaction.response.edit_message(
                embed=embedder.combat_embed(battle, avatar_url=avatar_url), view=_build_combat_view(battle)
            )
    finally:
        db.close()


async def _handle_select_target(interaction: discord.Interaction, target_index: int):
    """Switching targets is free -- it does not consume the player's turn."""
    db = SessionLocal()
    try:
        player = get_player(db, interaction.user.id)
        if player is None:
            await interaction.response.send_message("Use `/start` first.", ephemeral=True)
            return

        expedition = dungeon_service.get_active_expedition(db, player.id)
        if expedition is None or not expedition.combat_state:
            await interaction.response.send_message("You're not in a battle right now.", ephemeral=True)
            return

        battle = combat_service.load_battle(expedition)
        if battle.current_actor() is not battle.player:
            await interaction.response.send_message("It's not your turn yet.", ephemeral=True)
            return

        battle.select_target(target_index)
        combat_service.save_battle(db, expedition, battle)

        avatar_url = interaction.user.display_avatar.url
        await interaction.response.edit_message(
            embed=embedder.combat_embed(battle, avatar_url=avatar_url), view=_build_combat_view(battle)
        )
    finally:
        db.close()


# ----------------------------------------------------------------------
# Cog
# ----------------------------------------------------------------------

@guild_decorator
class Dungeon(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # COMMAND: /adventure
    # Starts a new expedition (if none active) or resumes the current one
    # exactly where it was left -- including mid-battle.
    @app_commands.command(name="adventure", description="Start or resume your dungeon expedition.")
    @app_commands.choices(region=[
        app_commands.Choice(name="Glacier 15", value="Glacier 15"),
        app_commands.Choice(name="The Wastelands", value="The Wastelands"),
        app_commands.Choice(name="The Hotlands", value="The Hotlands"),
        app_commands.Choice(name="Voidcrest Desert", value="Voidcrest Desert"),
    ])
    async def adventure(self, ctx: discord.Interaction, region: str = "Glacier 15"):
        db = SessionLocal()
        try:
            player = get_player(db, ctx.user.id)
            if player is None:
                await ctx.response.send_message("Use `/start` first.", ephemeral=True)
                return

            expedition = dungeon_service.get_active_expedition(db, player.id)
            if expedition is None:
                expedition = dungeon_service.start_expedition(db, player, region)
                result = dungeon_service.enter_node(db, expedition, player)
                message = result["message"]
            else:
                message = "Resuming your expedition..."

            avatar_url = ctx.user.display_avatar.url
            if expedition.combat_state:
                battle = combat_service.load_battle(expedition)
                summary = _advance_to_player_or_end(db, expedition, player, battle)
                if summary is not None:
                    embed = embedder.combat_embed(battle, avatar_url=avatar_url)
                    view = None
                else:
                    embed = embedder.combat_embed(battle, avatar_url=avatar_url)
                    view = _build_combat_view(battle)
            else:
                embed = embedder.dungeon_map_embed(expedition, message, avatar_url=avatar_url)
                view = _build_dungeon_view(expedition)
        finally:
            db.close()

        await ctx.response.send_message(embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(Dungeon(bot))
