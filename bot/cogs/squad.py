"""
/squad -- view your roster and choose which characters ride along on
expeditions. Slot 0 is always your own avatar (locked, can't be changed
here -- it's who you are); slots 1-3 are any of your other owned
characters, picked one dropdown per slot so re-rendering doesn't require
juggling more than 3 selects on one message.
"""

import discord

from discord.ext import commands
from discord import app_commands

from bot.database.session import SessionLocal
from bot.services.player_service import get_player
from bot.services import character_service, dungeon_service
from bot.utils.guild_decorator import guild_decorator

SLOT_LABELS = ["Slot 1 (Avatar -- locked)", "Slot 2", "Slot 3", "Slot 4"]


def _character_label(pc) -> str:
    stars = "★" * pc.template.star_rating
    class_label = pc.template.character_class.value.replace("_", " ").title()
    return f"{pc.template.name} {stars} Lv{pc.level} ({class_label})"[:100]


def _build_squad_embed(db, player) -> discord.Embed:
    by_slot = character_service.get_squad_by_slot(db, player)
    embed = discord.Embed(title=f"{player.username}'s Squad", color=discord.Color.dark_gold())
    for i in range(4):
        pc = by_slot[i]
        value = _character_label(pc) if pc else "*Empty*"
        embed.add_field(name=SLOT_LABELS[i], value=value, inline=False)
    embed.set_footer(text="Bring up to 4 characters into every expedition. Use the dropdowns to change slots 2-4.")
    return embed


class SquadSlotSelect(discord.ui.Select):
    """One per changeable slot (1-3, i.e. slot_index 1-3). Fixed custom_id
    per slot so re-rendering doesn't collide; options rebuilt fresh every
    render from the player's current roster."""
    def __init__(self, slot_index: int, options: list[discord.SelectOption]):
        super().__init__(
            placeholder=f"Slot {slot_index + 1}: choose a character...",
            options=options, min_values=1, max_values=1,
            custom_id=f"cascade_squad_slot:{slot_index}",
        )
        self.slot_index = slot_index

    async def callback(self, interaction: discord.Interaction):
        db = SessionLocal()
        try:
            player = get_player(db, interaction.user.id)
            if player is None:
                await interaction.response.send_message("Use `/start` first.", ephemeral=True)
                return

            expedition = dungeon_service.get_active_expedition(db, player.id)
            if dungeon_service.is_in_combat(expedition):
                await interaction.response.send_message(
                    "You can't change your squad mid-battle -- finish the fight first!",
                    ephemeral=True,
                )
                return

            value = self.values[0]
            character = None
            if value != "empty":
                character = next(
                    (pc for pc in character_service.list_owned_characters(db, player) if pc.id == int(value)),
                    None,
                )
            ok, message = character_service.set_squad_slot(db, player, self.slot_index, character)

            embed = _build_squad_embed(db, player)
            view = _build_squad_view(db, player)
            await interaction.response.edit_message(content=message if not ok else None, embed=embed, view=view)
        finally:
            db.close()


def _build_squad_view(db, player) -> discord.ui.View:
    owned = character_service.list_owned_characters(db, player)
    by_slot = character_service.get_squad_by_slot(db, player)
    view = discord.ui.View(timeout=180)

    for slot_index in (1, 2, 3):
        current = by_slot[slot_index]
        options = [discord.SelectOption(label="Empty", value="empty", default=current is None)]
        for pc in owned:
            if pc.template.is_player_avatar:
                continue
            options.append(discord.SelectOption(
                label=_character_label(pc), value=str(pc.id), default=(current is not None and current.id == pc.id),
            ))
        view.add_item(SquadSlotSelect(slot_index, options[:25]))

    return view


@guild_decorator
class Squad(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # COMMAND: /squad
    # View your 4-character active squad and reassign slots 2-4 from your
    # owned roster. Slot 1 is always your own avatar.
    @app_commands.command(name="squad", description="View and manage your 4-character active squad.")
    async def squad(self, ctx: discord.Interaction):
        db = SessionLocal()
        try:
            player = get_player(db, ctx.user.id)
            if player is None:
                await ctx.response.send_message(
                    "You haven't started your journey yet. Use `/start` first.",
                    ephemeral=True,
                )
                return

            embed = _build_squad_embed(db, player)
            view = _build_squad_view(db, player)
        finally:
            db.close()

        await ctx.response.send_message(embed=embed, view=view)

    # COMMAND: /characters
    # Lists every character you own, whether or not they're in your active squad.
    @app_commands.command(name="characters", description="View every character you own.")
    async def characters(self, ctx: discord.Interaction):
        db = SessionLocal()
        try:
            player = get_player(db, ctx.user.id)
            if player is None:
                await ctx.response.send_message(
                    "You haven't started your journey yet. Use `/start` first.",
                    ephemeral=True,
                )
                return

            owned = character_service.list_owned_characters(db, player)
            in_squad_ids = {pc.id for pc in character_service.get_squad(db, player)}

            embed = discord.Embed(title=f"{player.username}'s Characters", color=discord.Color.dark_gold())
            if not owned:
                embed.description = "You don't own any characters yet -- try `/pull`!"
            else:
                lines = []
                for pc in owned:
                    squad_tag = " 🔹" if pc.id in in_squad_ids else ""
                    dupe_tag = f" (x{pc.dupe_count})" if pc.dupe_count > 1 else ""
                    lines.append(f"{_character_label(pc)}{dupe_tag}{squad_tag}")
                embed.description = "\n".join(lines)
                embed.set_footer(text="🔹 = currently in your squad. Use /squad to change your team.")
        finally:
            db.close()

        await ctx.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Squad(bot))
