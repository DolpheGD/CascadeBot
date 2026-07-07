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
            placeholder="Use an ability...",
            options=options,
            custom_id="cascade_ability_select",
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction):
        await _handle_combat_action(interaction, "ability", ability_id=self.values[0])


class CombatView(discord.ui.View):
    def __init__(self, ability_options: list[discord.SelectOption] | None = None):
        super().__init__(timeout=None)
        if ability_options:
            self.add_item(AbilitySelect(ability_options))

    @discord.ui.button(label="Attack", style=discord.ButtonStyle.danger, custom_id="cascade_attack")
    async def attack_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _handle_combat_action(interaction, "attack")

    @discord.ui.button(label="Defend", style=discord.ButtonStyle.secondary, custom_id="cascade_defend")
    async def defend_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _handle_combat_action(interaction, "defend")

    @discord.ui.button(label="Flee", style=discord.ButtonStyle.gray, custom_id="cascade_flee")
    async def flee_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _handle_combat_action(interaction, "flee")


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
        label = ability["name"] if ready else f"{ability['name']} (not ready)"
        ability_options.append(discord.SelectOption(
            label=label[:100],
            value=ability["id"],
            description=ability["description"][:100],
        ))
    return CombatView(ability_options or None)


def _battle_end_message(summary: dict) -> str | None:
    kind = summary["kind"]
    if kind == "victory":
        r = summary["rewards"]
        text = f"You return to the path, {r['gold']} gold and {r['xp']} XP richer."
        if r["items"]:
            names = ", ".join(f"**{i.display_name}** ({i.rarity.value})" for i in r["items"])
            text += f"\nYou also found: {names}!"
        return text
    if kind == "expedition_complete":
        r = summary["rewards"]
        text = f"You defeated the boss! Expedition complete. (+{r['gold']} gold, +{r['xp']} XP)"
        if r["items"]:
            names = ", ".join(f"**{i.display_name}** ({i.rarity.value})" for i in r["items"])
            text += f"\nBoss drop: {names}!"
        return text
    if kind == "defeat":
        return "You have fallen. The expedition ends here."
    if kind == "fled":
        return "You flee back to the path."
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

        if result["kind"] == "combat":
            battle = combat_service.load_battle(expedition)
            await interaction.response.edit_message(
                embed=embedder.combat_embed(battle), view=_build_combat_view(battle)
            )
        else:
            await interaction.response.edit_message(
                embed=embedder.dungeon_map_embed(expedition, result["message"]),
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
        while not battle.is_over() and battle.current_actor() is not battle.player:
            battle.take_enemy_turn()

        if battle.is_over():
            summary = dungeon_service.resolve_battle_end(db, expedition, player, battle)
            await interaction.response.edit_message(
                embed=embedder.combat_embed(battle), view=None
            )

            follow_up_text = _battle_end_message(summary)
            if follow_up_text:
                await interaction.followup.send(
                    embed=embedder.dungeon_map_embed(expedition, follow_up_text),
                    view=_build_dungeon_view(expedition),
                )
        else:
            combat_service.save_battle(db, expedition, battle)
            await interaction.response.edit_message(
                embed=embedder.combat_embed(battle), view=_build_combat_view(battle)
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
        app_commands.Choice(name="Whispering Forest", value="Whispering Forest"),
        app_commands.Choice(name="Crystal Caverns", value="Crystal Caverns"),
        app_commands.Choice(name="Forgotten Kingdom", value="Forgotten Kingdom"),
    ])
    async def adventure(self, ctx: discord.Interaction, region: str = "Whispering Forest"):
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

            if expedition.combat_state:
                battle = combat_service.load_battle(expedition)
                embed = embedder.combat_embed(battle)
                view = _build_combat_view(battle)
            else:
                embed = embedder.dungeon_map_embed(expedition, message)
                view = _build_dungeon_view(expedition)
        finally:
            db.close()

        await ctx.response.send_message(embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(Dungeon(bot))
