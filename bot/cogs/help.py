import discord

from discord.ext import commands
from discord import app_commands

from bot.utils.guild_decorator import guild_decorator


@guild_decorator
class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # COMMAND: /help
    # A getting-started guide plus a categorized command reference.
    @app_commands.command(name="help", description="Get a guide to CascadeBot's commands.")
    async def help(self, ctx: discord.Interaction):
        embed = discord.Embed(
            title="Welcome to CascadeBot",
            description=(
                "A quick path to get going:\n"
                "`/start` -> `/adventure` -> fight your way to gear -> `/inventory` to equip it -> repeat."
            ),
            color=discord.Color.blurple(),
        )
        embed.set_thumbnail(url=ctx.client.user.display_avatar.url)

        embed.add_field(
            name="🧑 Getting Started",
            value=(
                "`/start` -- create your character\n"
                "`/profile` -- 3-page view: Overview, Equipment (every slot), and Abilities"
            ),
            inline=False,
        )
        embed.add_field(
            name="⚔️ Adventuring",
            value=(
                "`/adventure` -- start or resume a dungeon run. Every floor "
                "offers several room choices, not just two.\n"
                "Combat and room choices happen through buttons/menus on "
                "the message -- no extra commands needed mid-run."
            ),
            inline=False,
        )
        embed.add_field(
            name="🥊 How Combat Works",
            value=(
                "**Turn order is speed-based, not fixed** -- see the 🔀 Turn "
                "Order line on the battle message. Everyone has a gauge that "
                "fills according to SPD; whoever fills up first acts, and a "
                "much faster combatant can act several times in a row.\n\n"
                "**Actions (no defending, no fleeing):**\n"
                "⚔️ **Attack** -- always available, builds Energy and Mana "
                "equal to your Recharge stat.\n"
                "✨ **Skill** -- up to 2 Weapon Skills + 2 Artifact Skills "
                "from your equipped gear, costs Mana.\n"
                "💥 **Ultimate** -- from your equipped Scroll, usable once "
                "Energy reaches 100.\n"
                "🎯 Use the target dropdown to switch which enemy you're aiming at -- "
                "switching targets is free and doesn't use your turn.\n\n"
                "**Stats:** ❤️ HP, ⚔️ ATK, 🛡️ DEF, 💧 MP, 🔮 ELE (elemental "
                "damage), 💨 SPD, 🎯 Crit Rate%, 💥 Crit DMG%, 🔋 Recharge. "
                "There is no Dodge -- every hit lands, and DEF reduces damage "
                "by a percentage rather than fully blocking it."
            ),
            inline=False,
        )
        embed.add_field(
            name="🎒 Gear",
            value=(
                "`/inventory` -- browse a compact List of everything you own "
                "(items + lootboxes together), or open any entry in Detail "
                "mode to see full stats/abilities and Equip, Level Up, "
                "Reroll, or Open it. Use 🔍 Jump to # to go straight to a "
                "specific entry.\n"
                "2 Weapons, Helmet/Necklace, Chestplate, Leggings, Boots, "
                "2 Artifacts, and 1 Scroll (your ultimate) -- 9 slots total."
            ),
            inline=False,
        )
        embed.add_field(
            name="💰 Economy",
            value=(
                "`/daily` -- claim your daily reward (streak bonuses + lootboxes)\n"
                "`/harvesters` -- buy, upgrade, and collect passive income, all in one place\n"
                "`/pull` -- gacha pull with Shards\n"
                "`/lootboxes` -- view what you're holding\n"
                "`/open <tier>` -- open all lootboxes of a tier"
            ),
            inline=False,
        )
        embed.set_footer(text="Gold is common currency; Shards are rarer, used for gacha and premium rewards.")

        await ctx.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Help(bot))
