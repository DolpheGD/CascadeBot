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
                "`/start` -> `/pull` a couple characters -> `/squad` to set your team -> "
                "`/adventure` -> gear up with `/inventory` -> repeat."
            ),
            color=discord.Color.blurple(),
        )
        embed.set_thumbnail(url=ctx.client.user.display_avatar.url)

        embed.add_field(
            name="🧑 Getting Started",
            value=(
                "`/start` -- create your profile (grants your own class-switchable avatar character)\n"
                "`/profile` -- 3-page view of your avatar: Overview, Equipment, and Abilities\n"
                "`/squad` -- view/assign your 4-character active team (slot 1 is always your avatar)\n"
                "`/characters` -- list every character you own"
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
                "You fight with your full 4-character squad against enemies, one "
                "party member's turn at a time. **Turn order is speed-based, not "
                "fixed** -- see the 🔀 Turn Order line on the battle message.\n\n"
                "**Each character's actions (no defending, no fleeing):**\n"
                "⚔️ **Attack** -- always available, builds Energy and SP equal "
                "to a % of each pool's max (scaled by Recharge).\n"
                "🌀 **Character Skill** -- fixed to that character (or your class, "
                "for your own avatar), costs SP.\n"
                "💥 **Character Ultimate** -- also fixed to the character/class, "
                "usable once Energy reaches 100.\n"
                "⚔️🔮 **Weapon/Artifact Skill** -- from equipped gear, if any, costs SP.\n"
                "🎯 Use the target dropdown to switch which enemy you're aiming at -- "
                "switching targets is free and doesn't use your turn.\n\n"
                "**Stats:** ❤️ HP, ⚔️ ATK, 🛡️ DEF, 💧 SP, 🔮 ELE (elemental "
                "damage), 💨 SPD, 🎯 Crit Rate%, 💥 Crit DMG%, 🔋 Recharge. "
                "There is no Dodge -- every hit lands, and DEF reduces damage "
                "by a percentage rather than fully blocking it."
            ),
            inline=False,
        )
        embed.add_field(
            name="🎒 Gear",
            value=(
                "`/inventory` -- browse your ITEMS: a compact List of everything "
                "you own, or open any entry in Detail mode to see full "
                "stats/abilities and Equip, Level Up, Reroll, or Sell it. "
                "Use 🔍 Jump to # to go straight to a specific entry.\n"
                "`/stash` -- your general inventory: gold, shards, reroll "
                "tokens, materials, and lootboxes (open them right there). "
                "Nothing in `/stash` can be sold.\n"
                "Each character has 4 slots: Weapon, Artifact, Armor, and Accessory -- "
                "equipping asks which of your squad members should wear it. "
                "Ultimates come from characters now, not gear."
            ),
            inline=False,
        )
        embed.add_field(
            name="💰 Economy",
            value=(
                "`/daily` -- claim your daily reward (gold, reroll tokens, streak bonuses + lootboxes)\n"
                "`/quests` -- one-time beginner quests (300 Shards for finishing them all) plus a repeating basic quest, rerollable every 5 hours\n"
                "`/harvesters` -- buy, upgrade, and collect passive income, all in one place\n"
                "`/base hq` -- view and upgrade Cascade HQ\n"
                "`/base shrines` -- build/upgrade party-wide stat shrines\n"
                "`/base mailbox` -- collect a package of basic supplies every 30min-1hr\n"
                "`/base shop` -- material exchanges and low-level gear\n"
                "`/pull` -- spend Shards to pull a new character (single or 10x)\n"
                "`/pull_rates` -- view gacha odds and costs\n"
                "`/open <tier>` -- open all lootboxes of a tier (or use `/stash`)"
            ),
            inline=False,
        )
        embed.set_footer(text="Gold is common currency; Shards are rarer, used for the character gacha.")

        await ctx.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Help(bot))
