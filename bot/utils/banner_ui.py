"""
The banner screen, shared by /pull and /cardpull.

ONE menu, two banners. The character banner and the Card banner used to
be separate screens with separate buttons, separate rates displays and
separate everything -- so learning one taught you nothing about the
other, and the differences between them were accidents of when each was
written rather than decisions anyone made.

A BANNER here is a small descriptor (see BANNERS below): what it costs,
what currency, what the pity thresholds are, and two callables to roll
and to render results. Everything else -- the four buttons, the history
page, the rates page, the "you can afford N pulls" line -- is written
once and works for both. Adding a third banner is a dict entry.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import discord

from bot.database.session import SessionLocal
from bot.services import pull_service
from bot.services.currency_service import currency_emoji, format_currency
from bot.services.player_service import get_player
from bot.utils import responses
from bot.utils.embedder._shared import fit_field
from bot.utils.ui_guard import OwnedView, check_message_owner

STAR_EMOJI = {3: "⭐", 4: "🌟", 5: "💫"}


def stars(n: int) -> str:
    return f"{STAR_EMOJI.get(n, '⭐')} {n}★"


@dataclass(frozen=True)
class Banner:
    key: str                 # matches PullRecord.banner
    title: str
    currency: str
    single_cost: int
    multi_count: int
    rates: dict[int, float]  # star -> percent
    hard_pity: int
    soft_pity_start: int
    soft_pity_step: float
    four_star_pity: int
    blurb: str
    pity_attr_five: str
    pity_attr_four: str
    # (db, player, count) -> (ok, message, [result embeds])
    pull: Callable
    feature: str


def _banner(key: str) -> "Banner":
    return BANNERS[key]


# ----------------------------------------------------------------------
# Screens
# ----------------------------------------------------------------------

def banner_embed(banner: Banner, player) -> discord.Embed:
    balance = getattr(player, banner.currency, 0)
    affordable = balance // banner.single_cost
    since_five = getattr(player, banner.pity_attr_five, 0)
    since_four = getattr(player, banner.pity_attr_four, 0)

    embed = discord.Embed(title=banner.title, description=banner.blurb,
                          color=discord.Color.blurple())
    embed.add_field(
        name="Balance",
        value=(f"{format_currency(banner.currency, balance)}\n"
               f"{affordable} pull{'s' if affordable != 1 else ''} available"),
        inline=True,
    )
    # PITY IS SHOWN, not hidden. A guarantee the player cannot see the
    # progress of is a guarantee they do not believe in, and the whole
    # reason to have one is reassurance.
    embed.add_field(
        name="Pity",
        value=(f"{since_five}/{banner.hard_pity} to guaranteed 5★\n"
               f"{since_four}/{banner.four_star_pity} to guaranteed 4★"
               + ("\n*soft pity active*"
                  if since_five >= banner.soft_pity_start else "")),
        inline=True,
    )
    embed.set_footer(
        text=f"{banner.single_cost} {banner.currency} a pull · "
             f"same price per pull on the {banner.multi_count}x"
    )
    return embed


def rates_embed(banner: Banner) -> discord.Embed:
    embed = discord.Embed(
        title=f"{banner.title} — Rates",
        description="Base odds per pull, before any pity ramp.",
        color=discord.Color.blurple(),
    )
    embed.add_field(
        name="Base rates",
        value="\n".join(f"{stars(star)} — **{pct:g}%**"
                        for star, pct in sorted(banner.rates.items(), reverse=True)),
        inline=False,
    )
    embed.add_field(
        name="Pity",
        value=(
            f"**Guaranteed 5★** by pull {banner.hard_pity}.\n"
            f"From pull {banner.soft_pity_start} the 5★ chance rises by "
            f"**{banner.soft_pity_step:g} points per pull**, so most 5★s land "
            f"before the ceiling.\n"
            f"**Guaranteed 4★ or better** by pull {banner.four_star_pity}.\n\n"
            "Counters carry across single and 10x pulls, and each banner "
            "keeps its own — pulling here never advances the other."
        ),
        inline=False,
    )
    return embed


def history_embed(banner: Banner, records: list) -> discord.Embed:
    embed = discord.Embed(
        title=f"{banner.title} — History",
        description=f"Your last {pull_service.HISTORY_LIMIT} pulls, newest first.",
        color=discord.Color.blurple(),
    )
    if not records:
        embed.add_field(name="Nothing yet", value="No pulls on this banner.",
                        inline=False)
        return embed

    # A 5★/4★ summary first, because "how many have I had" is the
    # question the list itself answers only by counting.
    fives = [r for r in records if r.star_rating >= 5]
    fours = [r for r in records if r.star_rating == 4]
    embed.add_field(
        name="In this window",
        value=(f"{stars(5)} × **{len(fives)}** · {stars(4)} × **{len(fours)}** "
               f"· {len(records)} pulls"),
        inline=False,
    )
    embed.add_field(
        name="Recent",
        value=fit_field([
            f"{stars(r.star_rating)} **{r.name}**" + (" *(pity)*" if r.was_pity else "")
            for r in records
        ]),
        inline=False,
    )
    return embed


# ----------------------------------------------------------------------
# Buttons
# ----------------------------------------------------------------------

class BannerButton(discord.ui.DynamicItem[discord.ui.Button],
                   template=r"cascade_banner:(?P<banner>\w+):(?P<action>pull1|pull10|history|rates)"):
    LABELS = {
        "pull1": "Pull ×1", "pull10": "Pull ×{count}",
        "history": "📜 History", "rates": "📊 Rates",
    }

    def __init__(self, banner_key: str, action: str):
        banner = _banner(banner_key)
        label = self.LABELS[action].format(count=banner.multi_count)
        if action == "pull1":
            label += f" ({banner.single_cost})"
        elif action == "pull10":
            label += f" ({banner.single_cost * banner.multi_count})"
        style = (discord.ButtonStyle.primary if action == "pull1"
                 else discord.ButtonStyle.success if action == "pull10"
                 else discord.ButtonStyle.secondary)
        emoji = currency_emoji(banner.currency) if action.startswith("pull") else None
        super().__init__(discord.ui.Button(
            label=label, style=style, emoji=emoji,
            custom_id=f"cascade_banner:{banner_key}:{action}",
        ))
        self.banner_key = banner_key
        self.action = action

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(match["banner"], match["action"])

    async def callback(self, interaction: discord.Interaction):
        if not await check_message_owner(interaction):
            return
        banner = _banner(self.banner_key)
        db = SessionLocal()
        try:
            player = get_player(db, interaction.user.id)
            if player is None:
                await responses.send(interaction, "Use `/start` first.", ephemeral=True)
                return

            if self.action == "rates":
                await responses.send(interaction, embed=rates_embed(banner),
                                     ephemeral=True)
                return
            if self.action == "history":
                records = pull_service.history(db, player.id, banner.key)
                await responses.send(interaction,
                                     embed=history_embed(banner, records),
                                     ephemeral=True)
                return

            count = 1 if self.action == "pull1" else banner.multi_count
            ok, message, embeds = banner.pull(db, player, count)
            if not ok:
                await responses.send(interaction, message, ephemeral=True)
                return
            # The banner screen is REFRESHED underneath the results, so
            # the pity counters and balance the player just changed are
            # correct without them re-running the command.
            refreshed = banner_embed(banner, player)
            view = BannerView(banner.key, owner_id=player.id)
        finally:
            db.close()
        await responses.edit(interaction, embed=refreshed, view=view)
        for embed in embeds:
            await responses.send(interaction, embed=embed)


class BannerView(OwnedView):
    def __init__(self, banner_key: str, owner_id: int | None = None):
        super().__init__(timeout=None, owner_id=owner_id)
        for action in ("pull1", "pull10", "history", "rates"):
            self.add_item(BannerButton(banner_key, action))


# ----------------------------------------------------------------------
# The banners themselves. Populated at import time by register().
# ----------------------------------------------------------------------
BANNERS: dict[str, Banner] = {}


def register(banner: Banner) -> None:
    BANNERS[banner.key] = banner


# ----------------------------------------------------------------------
# Registration
#
# Done here rather than in each cog so the BANNERS dict is fully
# populated the moment this module imports -- a DynamicItem resolved from
# a custom_id after a restart looks its banner up by key, and a banner
# registered lazily by a cog that hasn't loaded yet would KeyError on the
# first button press after every deploy.
# ----------------------------------------------------------------------

def _pull_characters(db, player, count: int):
    from bot.services.character_gacha_service import pull_multi, pull_single
    from bot.utils import embedder

    ok, message, results = (pull_single(db, player) if count == 1
                            else pull_multi(db, player, count=count))
    if not ok:
        return False, message, []
    return True, message, [embedder.gacha_pull_embed(results, player=player)]


def _pull_cards(db, player, count: int):
    from bot.cogs.cards import pull_result_embed
    from bot.services import card_service

    ok, message, pulled = card_service.pull_cards(db, player, count)
    if not ok:
        return False, message, []
    return True, message, [pull_result_embed(pulled, message)]


def _register_all() -> None:
    from bot.game.economy import card_config as cc
    from bot.game.economy import character_gacha_config as gc

    register(Banner(
        key="character", title="🎴 Character Banner", currency="shards",
        single_cost=gc.SINGLE_PULL_COST_SHARDS, multi_count=gc.MULTI_PULL_COUNT,
        rates=gc.STAR_WEIGHTS, hard_pity=gc.FIVE_STAR_HARD_PITY,
        soft_pity_start=gc.FIVE_STAR_SOFT_PITY_START,
        soft_pity_step=gc.FIVE_STAR_SOFT_PITY_STEP,
        four_star_pity=gc.FOUR_STAR_PITY,
        blurb="Pull for the people who fight alongside you.",
        pity_attr_five="pity_since_five_star", pity_attr_four="pity_since_four_star",
        pull=_pull_characters, feature="pull",
    ))
    register(Banner(
        key="card", title="🃏 Character Card Banner", currency="cores",
        single_cost=cc.CARD_PULL_COST, multi_count=cc.CARD_MULTI_PULL_COUNT,
        rates=cc.CARD_STAR_WEIGHTS, hard_pity=cc.CARD_FIVE_STAR_HARD_PITY,
        soft_pity_start=cc.CARD_FIVE_STAR_SOFT_PITY_START,
        soft_pity_step=cc.CARD_FIVE_STAR_SOFT_PITY_STEP,
        four_star_pity=cc.CARD_FOUR_STAR_PITY,
        blurb="Pull for Cards — one per character, and the strongest "
              "abilities in the game.",
        pity_attr_five="card_pity_since_five_star",
        pity_attr_four="card_pity_since_four_star",
        pull=_pull_cards, feature="cards",
    ))


_register_all()
