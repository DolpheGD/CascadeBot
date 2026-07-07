import discord

from discord.ext import commands
from discord import app_commands

from bot.database.session import SessionLocal
from bot.services.player_service import get_player
from bot.services import inventory_service, dungeon_service
from bot.utils.guild_decorator import guild_decorator


def _item_line(item) -> str:
    equipped_tag = " [EQUIPPED]" if item.is_equipped else ""
    return (
        f"`#{item.id}` **{item.display_name}** ({item.rarity.value}, "
        f"{item.slot.value}, ilvl {item.item_level}){equipped_tag}"
    )


@guild_decorator
class Inventory(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # COMMAND: /inventory
    # Lists every item the player owns, marking which are currently equipped.
    @app_commands.command(name="inventory", description="View your items.")
    async def inventory(self, ctx: discord.Interaction):
        db = SessionLocal()
        try:
            player = get_player(db, ctx.user.id)
            if player is None:
                await ctx.response.send_message(
                    "You haven't started your journey yet. Use `/start` first.",
                    ephemeral=True,
                )
                return

            items = inventory_service.list_inventory(db, player.id)
            if not items:
                await ctx.response.send_message(
                    "Your inventory is empty. Try `/adventure`, `/pull`, or `/open`.",
                    ephemeral=True,
                )
                return

            # Discord embeds cap at 25 fields; keep this simple for the prototype
            # and just show the first 25, most recently acquired last.
            lines = [_item_line(item) for item in items[:25]]
            embed = discord.Embed(
                title=f"{player.username}'s Inventory",
                description="\n".join(lines),
                color=discord.Color.blue(),
            )
            if len(items) > 25:
                embed.set_footer(text=f"Showing 25 of {len(items)} items.")
        finally:
            db.close()

        await ctx.response.send_message(embed=embed)

    # COMMAND: /equip
    # Equips an item by its #id (shown in /inventory). Non-ring slots
    # auto-swap out whatever was equipped there; ring slots hold two at once.
    @app_commands.command(name="equip", description="Equip an item by its #id.")
    async def equip(self, ctx: discord.Interaction, item_id: int):
        db = SessionLocal()
        try:
            player = get_player(db, ctx.user.id)
            if player is None:
                await ctx.response.send_message(
                    "You haven't started your journey yet. Use `/start` first.",
                    ephemeral=True,
                )
                return

            expedition = dungeon_service.get_active_expedition(db, player.id)
            if dungeon_service.is_in_combat(expedition):
                await ctx.response.send_message(
                    "You can't change equipment mid-battle -- finish the fight first!",
                    ephemeral=True,
                )
                return

            item = inventory_service.get_item(db, item_id, player.id)
            if item is None:
                await ctx.response.send_message("No item with that #id.", ephemeral=True)
                return

            ok, message = inventory_service.equip_item(db, player, item)
        finally:
            db.close()

        await ctx.response.send_message(message, ephemeral=not ok)

    # COMMAND: /unequip
    # Unequips an item by its #id.
    @app_commands.command(name="unequip", description="Unequip an item by its #id.")
    async def unequip(self, ctx: discord.Interaction, item_id: int):
        db = SessionLocal()
        try:
            player = get_player(db, ctx.user.id)
            if player is None:
                await ctx.response.send_message(
                    "You haven't started your journey yet. Use `/start` first.",
                    ephemeral=True,
                )
                return

            expedition = dungeon_service.get_active_expedition(db, player.id)
            if dungeon_service.is_in_combat(expedition):
                await ctx.response.send_message(
                    "You can't change equipment mid-battle -- finish the fight first!",
                    ephemeral=True,
                )
                return

            item = inventory_service.get_item(db, item_id, player.id)
            if item is None:
                await ctx.response.send_message("No item with that #id.", ephemeral=True)
                return

            ok, message = inventory_service.unequip_item(db, player, item)
        finally:
            db.close()

        await ctx.response.send_message(message, ephemeral=not ok)


async def setup(bot):
    await bot.add_cog(Inventory(bot))
