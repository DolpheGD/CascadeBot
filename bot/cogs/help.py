"""
/help -- a paged guide.

This was ONE embed with seven long fields. It had two problems that a
rewrite fixes rather than a trim:

  1. It was out of date. It described a 50% damage Break bonus (now 35%
     and per-attacker), a shop selling "low-level gear" (the shop is a
     materials market now and sells no gear at all), and said nothing
     about raids, leaderboards, gacha pity, taunt, shields, cursed
     relics, ally targeting or domains' unlock rules -- most of which
     are things a player cannot discover on their own.
  2. It was too long to read. A single embed pushing Discord's 6000-char
     ceiling is not a reference, it's a wall, and the specific failure
     mode is that the useful part (the command list) sat below several
     screens of combat theory.

So: six short pages behind a dropdown, each one answering a single
question, plus prev/next for browsing. Every page is built to stay well
under the per-field limit -- see _PAGES.

The page CONTENT deliberately lives in this module as plain data rather
than being generated from the command tree. A generated list can only
ever say what a command is named; the value here is in saying what's
worth doing and in what order, which is authored knowledge.
"""

import discord

from discord.ext import commands
from bot.utils import responses
from discord import app_commands

from bot.utils.guild_decorator import guild_decorator


# Each page: (key, label, emoji, description, [(field name, field value)])
_PAGES: list[tuple[str, str, str, str, list[tuple[str, str]]]] = [
    (
        "start", "Getting Started", "🧭",
        "New here? This is the whole loop in order.",
        [
            (
                "The loop",
                "`/start` → **`/story`** → everything else unlocks as you play it.\n\n"
                "Story mode is the main game. It teaches you the systems, hands you a "
                "squad, and opens `/adventure`, `/pull` and the rest at the point you "
                "have a reason to use them. Expeditions are where you get strong enough "
                "for the next mission.",
            ),
            (
                "Your characters",
                "`/start` — create your profile and your own avatar character\n"
                "`/story` — **the main mode.** Start here.\n"
                "`/squad` — set your 4-character team (slot 1 is always your avatar)\n"

                "`/class` — switch your avatar between DPS / Support DPS / Amplifier / Sustain\n"
                "`/rename` — name your avatar\n"
                "`/profile` — your account: level, roster, power and currencies\n"
                "`/characters` — any character's full stats, equipment and abilities",
            ),
            (
                "Where to fight",
                "`/adventure` — a full dungeon run. Regions unlock in order; harder ones pay more.\n"
                "`/domains` — single fights for direct rewards, costs energy, no run commitment. "
                "Tiers unlock by clearing regions and by your total character levels.\n"
                "`/raid` — your server's co-op boss.",
            ),
        ],
    ),
    (
        "combat", "Combat Basics", "⚔️",
        "Your four characters act one at a time, fastest first.",
        [
            (
                "Your turn",
                "⚔️ **Attack** — builds Energy **and** SP. The only source of SP.\n"
                "🌀 **Skill** — costs SP. Also builds Energy.\n"
                "💥 **Ultimate** — costs 50 Energy **and** has a 2-turn cooldown after use. "
                "Every action you take charges it, and so does taking a hit — energy gear "
                "gets you there faster, but nothing shortens the cooldown.\n"
                "🛡️ **Guard** — halves incoming damage until your next turn and banks "
                "extra Energy if a hit lands. Read the 😈 Incoming panel and guard whoever is being aimed at.",
            ),
            (
                "Free actions (don't use your turn)",
                "🎯 **Switch target** — pick which enemy you're hitting.\n"
                "💚 **Support target** — pick which ally your heal/shield/buff lands on. "
                "Leave it on Auto and it goes to whoever needs it most.",
            ),
            (
                "Reading the screen",
                "**😈 Incoming** shows what each enemy will do *before* it happens, and it "
                "never lies — what's shown is what resolves. An attack hitting everyone "
                "says **ALL of you** rather than naming one target.\n"
                "**ℹ️ Info** pages through every combatant: full stats with buffs applied, "
                "their whole kit, and every effect on them. **📜 Log** is the full history.\n"
                "A fight that reaches **40 cycles** ends in a withdrawal — the counter starts "
                "showing from cycle 25, and no normal fight comes close.",
            ),
        ],
    ),
    (
        "mechanics", "Combat Mechanics", "💫",
        "The systems worth building a squad around.",
        [
            (
                "💫 Poise & Break",
                "Every enemy has Poise, chipped by each landed hit — 1 per Attack, 2 per "
                "Skill, 3 per Ultimate, and once *per hit or per target* for multi-hit and "
                "AOE, which makes those the best breaking tools.\n"
                "Empty it and the enemy is **Broken**: its telegraphed move is **cancelled**, "
                "it loses turns, and it takes extra damage.\n"
                "Each break makes the next one harder on that enemy, so breaking stays a "
                "repeatable tactic rather than a lock. Gear and relics can raise your break power.",
            ),
            (
                "🎯 Taunt",
                "A taunting character forces the other side's single-target attacks onto "
                "itself. Your tank taunts to protect the squad; an enemy taunts to stop you "
                "picking off the healer behind it. AOE ignores taunt.",
            ),
            (
                "🔷 Shields & 💚 Healing",
                "Shields absorb damage before HP and never expire — they just run out. "
                "Dedicated shielders make every shield they grant bigger.\n"
                "Healing is never secretly reduced: what an ability says it heals is what it "
                "heals, every time. **Whole-team** heals are the expensive ones — smaller "
                "percentages, higher SP, longer cooldowns — while single-target heals hit hard, "
                "so who you heal is a real decision.\n"
                "**HP carries between fights inside a run** and is only restored at campfires, "
                "so damage taken is a real cost. Domains and raids always start you at full HP.",
            ),
            (
                "Classes",
                "⚔️ **DPS** / 🎯 **Support DPS** deal the damage.\n"
                "📡 **Amplifier** buffs the squad's offence — a good one is worth more than a "
                "fourth attacker.\n"
                "💚 **Sustain** keeps you alive by healing, shielding, or hardening.\n"
                "Running at least one Amplifier and one Sustain is the strongest shape.",
            ),
        ],
    ),
    (
        "gear", "Gear & Characters", "🎒",
        "Getting stronger between runs.",
        [
            (
                "Items",
                "`/inventory` — browse, equip, level up, reroll or sell\n"
                "`/sell_rarity` — bulk-sell every unequipped item of one rarity\n"
                "`/stash` — currencies, materials and lootboxes\n"
                "Each character wears 1 Weapon, 1 Artifact, 2 Armor and 2 Accessories. "
                "Weapons and Artifacts grant active skills; Armor and Accessories grant passives.",
            ),
            (
                "Pulling",
                "`/pull` — spend Shards on characters (single or 10x)\n"
                "`/pull_rates` — odds, costs, and your live pity progress\n"
                "**Pity:** a 4★ or better is guaranteed every 10 pulls, and a 5★ is guaranteed "
                "by pull 50 — with the odds climbing steadily from pull 30, so most land sooner.",
            ),
            (
                "✴️ Duplicates, Resonance & Echoes",
                "Pulling someone you already own is never a wasted pull.\n"
                "`/resonance` — the first **5** copies of a character each permanently "
                "upgrade them: bigger damage stat, a cheaper skill, more HP and DEF, a stronger "
                "kit, and finally a shorter ultimate cooldown.\n"
                "`/exchange` — every duplicate also pays **Echoes**, and copies past Resonance 5 "
                "pay more than double. Save enough and you buy *exactly* the character you want — "
                "no rates, no pity, no luck.",
            ),
            (
                "✨ Relics (run-only)",
                "Drafted at campfires and dropped by bosses and elites. They're party-wide, "
                "last only that run, and are what makes two runs with the same squad play "
                "differently.\n"
                "**Cursed** relics are stronger than anything else on offer but carry a real "
                "drawback — big attack for less defence, and so on. Sometimes the right call.",
            ),
        ],
    ),
    (
        "base", "Economy & Base", "💰",
        "The between-runs game.",
        [
            (
                "Cascade HQ",
                "`/hq` — upgrade HQ; it gates everything else below\n"
                "`/harvesters` — buy, upgrade and collect passive income\n"
                "`/shrines` — permanent party-wide stat bonuses\n"
                "`/lab` — research permanent, account-wide upgrades\n"
                "`/forge` — craft gear in the slot and rarity you choose",
            ),
            (
                "Shop",
                "`/shop` — a **materials market**: buy or sell every material for gold, and "
                "refine materials into the tier above. Tabs split Sell / Buy / Refine / Special.\n"
                "Buying costs more than selling pays, so harvesting is always cheaper than "
                "shopping. It doesn't sell gear — that comes from adventuring.",
            ),
            (
                "Income",
                "`/daily` — daily reward with streak bonuses\n"
                "`/vote` — vote on top.gg every 12h for the biggest Shard payout in the game\n"
                "`/quests` — one-time beginner quests (they retire once finished) plus rerollable repeating ones\n"
                "`/open <tier>` — open all lootboxes of a tier",
            ),
        ],
    ),
    (
        "multiplayer", "Multiplayer", "🐉",
        "Everything that involves the rest of your server.",
        [
            (
                "🐉 Co-op raids",
                "`/raid` — one raid runs per server at a time, with a shared HP pool everyone "
                "chips away at on their own schedule. Nobody has to be online at the same time.\n"
                "You get a limited number of attacks, and **damage counts whether you win the "
                "fight or not** — a squad that can't beat the boss still contributes.\n"
                "`/raid_claim` — collect your share once it's down. Rewards scale to how much "
                "damage *you* did, so they never depend on who else turned up.",
            ),
            (
                "🎁 Gifting",
                "`/gift` — send another player materials or gold (3 gifts a day, "
                "account level 4+). Shards and Echoes can't be gifted.\n"
                "`/gifts` — collect what people have sent you. Gifts wait for you, "
                "so someone can send one before you've even started.",
            ),
            (
                "🏆 Leaderboards",
                "`/leaderboard` — four boards for your server: Squad Power, Roster Levels, "
                "Deepest Clear, and Collection. If you're outside the top 10 it still tells you "
                "where you stand.",
            ),
            (
                "📖 Reference",
                "`/encyclopedia` — characters, classes, enemies, abilities, items and materials. "
                "No profile needed.",
            ),
        ],
    ),
]

_PAGE_INDEX = {key: i for i, (key, *_rest) in enumerate(_PAGES)}


def _build_help_embed(page: int, avatar_url: str | None = None) -> discord.Embed:
    page = max(0, min(page, len(_PAGES) - 1))
    key, label, emoji, description, fields = _PAGES[page]

    embed = discord.Embed(
        title=f"{emoji} {label}",
        description=f"{description}\n*Page {page + 1}/{len(_PAGES)} — use the menu below to jump around.*",
        color=discord.Color.blurple(),
    )
    if avatar_url and page == 0:
        embed.set_thumbnail(url=avatar_url)
    for name, value in fields:
        embed.add_field(name=name, value=value, inline=False)
    embed.set_footer(text="Gold is the common currency; Shards are for the character gacha.")
    return embed


class HelpPageSelect(discord.ui.Select):
    def __init__(self, current: int):
        super().__init__(
            placeholder="Jump to a section...",
            options=[
                discord.SelectOption(label=label, value=key, emoji=emoji, description=desc[:100],
                                     default=(i == current))
                for i, (key, label, emoji, desc, _f) in enumerate(_PAGES)
            ],
            min_values=1, max_values=1,
        )

    async def callback(self, interaction: discord.Interaction):
        await self.view.show(interaction, _PAGE_INDEX[self.values[0]])


class HelpView(discord.ui.View):
    """Not a persistent view: /help is read once and closed, so there's
    nothing worth surviving a restart. Timing out after 5 minutes leaves
    a readable embed with dead buttons, which is the right failure mode
    for a reference."""

    def __init__(self, page: int = 0):
        super().__init__(timeout=300)
        self.page = page
        self.prev_button.disabled = page == 0
        self.next_button.disabled = page >= len(_PAGES) - 1
        self.add_item(HelpPageSelect(page))

    async def show(self, interaction: discord.Interaction, page: int):
        await responses.edit(interaction,
            embed=_build_help_embed(page, interaction.client.user.display_avatar.url),
            view=HelpView(page),
        )

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.show(interaction, self.page - 1)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.show(interaction, self.page + 1)


@guild_decorator
class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="help", description="A paged guide to CascadeBot.")
    @app_commands.choices(section=[
        app_commands.Choice(name=label, value=key) for key, label, *_r in _PAGES
    ])
    async def help(self, ctx: discord.Interaction, section: str | None = None):
        """`section` lets a returning player jump straight to the page
        they want instead of paging through the intro every time."""
        await responses.defer(ctx, ephemeral=True)
        page = _PAGE_INDEX.get(section, 0)
        await responses.send(ctx,
            embed=_build_help_embed(page, ctx.client.user.display_avatar.url),
            view=HelpView(page),
            ephemeral=True,
        )


async def setup(bot):
    await bot.add_cog(Help(bot))
