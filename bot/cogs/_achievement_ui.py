"""
Screens for /achievements: what you've done, and what you wear for it.

UNDERSCORE-PREFIXED so bot/client.py's cog loader skips it -- the command
itself lives in profile.py, next to the other account screens.

TWO PAGES, NOT ONE. Achievements and collection answer different
questions ("what have I done" and "what am I missing") and a single embed
holding both was pushing Discord's field budget with the useful part at
the bottom. The dropdown switches between them.

UNEARNED ACHIEVEMENTS SHOW THEIR PROGRESS, deliberately. A locked row
that says only "Own 20 characters" is a wall; one that says "14/20" is a
target. The number comes from the same metrics() call that decides
whether it is earned, so the progress bar and the tick can never
disagree.
"""

from __future__ import annotations

import discord

from bot.database.session import SessionLocal
from bot.game.achievements.achievement_config import TIER_EMOJI
from bot.services import achievement_service
from bot.services.player_service import get_player
from bot.utils import responses
from bot.utils.ui_guard import OwnedView

ACHIEVEMENT_COLOUR = discord.Colour.gold()


def _bar(fraction: float, width: int = 10) -> str:
    filled = max(0, min(width, round(fraction * width)))
    return "▰" * filled + "▱" * (width - filled)


def achievements_embed(db, player) -> discord.Embed:
    state = achievement_service.summary(db, player)
    values, earned = state["metrics"], state["earned"]

    embed = discord.Embed(
        title=f"🏆 {player.username}'s Achievements",
        description=(
            f"**{len(earned)}/{state['total']}** earned"
            + (f"  ·  wearing **{player.active_title}**" if player.active_title else "")
        ),
        colour=ACHIEVEMENT_COLOUR,
    )

    for category, items in state["by_category"].items():
        if not items:
            continue
        lines = []
        for achievement in items:
            done = achievement.id in earned
            if done:
                mark = TIER_EMOJI.get(achievement.tier, "🥉")
                extra = f"  ·  *{achievement.title}*" if achievement.title else ""
                lines.append(f"{mark} **{achievement.name}**{extra}")
            else:
                have = values.get(achievement.metric, 0)
                lines.append(
                    f"🔒 {achievement.name} — {achievement.description} "
                    f"*({min(have, achievement.threshold):,}/{achievement.threshold:,})*")
        got = sum(1 for a in items if a.id in earned)
        embed.add_field(name=f"{category} — {got}/{len(items)}",
                        value="\n".join(lines)[:1024], inline=False)
    return embed


def collection_embed(db, player) -> discord.Embed:
    data = achievement_service.collection(db, player)
    embed = discord.Embed(
        title=f"📚 {player.username}'s Collection",
        description="Everything there is, and how much of it you have.",
        colour=ACHIEVEMENT_COLOUR,
    )
    labels = {
        "characters": "Characters", "cards": "Character Cards",
        "missions": "Story missions", "regions": "Regions cleared",
        "abyss": "Abyss stars",
    }
    for key, label in labels.items():
        entry = data[key]
        embed.add_field(
            name=label,
            value=(f"{_bar(entry['percent'] / 100)}  "
                   f"**{entry['owned']:,}/{entry['total']:,}**  "
                   f"({entry['percent']:.0f}%)"),
            inline=False)

    # THE ONE THING THIS SCREEN DOES NOT TRACK, said out loud rather than
    # quietly missing. Nothing in the game records which enemies a player
    # has fought, so a bestiary would need a write at every place a
    # battle can start. /encyclopedia lists them all as reference.
    embed.set_footer(text="Enemies aren't tracked per-player — see /encyclopedia "
                          "for the full bestiary.")
    return embed


class AchievementView(OwnedView):
    def __init__(self, db, player, page: str = "achievements"):
        super().__init__(timeout=300, owner_id=player.id)
        self.add_item(_PageSelect(page))
        titles = achievement_service.available_titles(db, player)
        if titles:
            self.add_item(_TitleSelect(titles, player.active_title))


class _PageSelect(discord.ui.Select):
    def __init__(self, current: str):
        super().__init__(
            placeholder="View…",
            options=[
                discord.SelectOption(label="Achievements", value="achievements",
                                     emoji="🏆", default=current == "achievements"),
                discord.SelectOption(label="Collection", value="collection",
                                     emoji="📚", default=current == "collection"),
            ],
        )

    async def callback(self, interaction: discord.Interaction):
        db = SessionLocal()
        try:
            player = get_player(db, interaction.user.id)
            if player is None:
                await responses.send(interaction, "Use `/start` first.", ephemeral=True)
                return
            page = self.values[0]
            embed = (achievements_embed(db, player) if page == "achievements"
                     else collection_embed(db, player))
            await responses.edit(interaction, embed=embed,
                                 view=AchievementView(db, player, page))
        finally:
            db.close()


class _TitleSelect(discord.ui.Select):
    def __init__(self, titles: list[str], current: str | None):
        # A STATE select: it shows what you are wearing and switches it.
        # `default` on the worn title is correct here, and re-picking it
        # being inert is also correct -- choosing what is already chosen
        # changes nothing. See tools/check_selects for why the same
        # pattern on an ACTION select is the raid-difficulty bug.
        options = [discord.SelectOption(label="(no title)", value="__none__",
                                        default=not current)]
        # Sliced to Discord's cap. There are fourteen titles in the game
        # so this cannot trigger today; it is here because an over-long
        # select fails with a 400 that shows up only as a dead button.
        for title in titles[:24]:
            options.append(discord.SelectOption(
                label=title[:100], value=title[:100], default=title == current))
        super().__init__(placeholder="Wear a title…", options=options)

    async def callback(self, interaction: discord.Interaction):
        db = SessionLocal()
        try:
            player = get_player(db, interaction.user.id)
            if player is None:
                await responses.send(interaction, "Use `/start` first.", ephemeral=True)
                return
            choice = self.values[0]
            ok, message = achievement_service.set_title(
                db, player, None if choice == "__none__" else choice)
            if not ok:
                await responses.send(interaction, message, ephemeral=True)
                return
            await responses.edit(interaction, embed=achievements_embed(db, player),
                                 view=AchievementView(db, player))
            await interaction.followup.send(message, ephemeral=True)
        finally:
            db.close()
