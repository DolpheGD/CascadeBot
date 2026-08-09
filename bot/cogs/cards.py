"""
Character Cards: the browser, the banner, and equipping.

Deliberately its own command tree rather than a page inside /inventory.
A Card is not a piece of gear you sift through -- there is one slot per
character and the whole interaction is "which of my few good ones goes
on whom", which is a different screen from a 200-item list.
"""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from bot.database.models.card_model import PlayerCard
from bot.database.session import SessionLocal
from bot.game.economy import card_config as cc
from bot.services import card_service, character_service
from bot.services.currency_service import format_currency
from bot.services.player_service import get_player
from bot.database.models.character_model import PlayerCharacter
from bot.utils import banner_ui, paging, responses
from bot.utils.embedder._shared import _fmt_stat, fit_field
from bot.utils.guild_decorator import guild_decorator
from bot.utils.ui_guard import OwnedView, check_message_owner, require_feature

STAR_EMOJI = {3: "⭐", 4: "🌟", 5: "💫"}


def _stars(n: int) -> str:
    return STAR_EMOJI.get(n, "⭐") * 1 + f" {n}★"


# ----------------------------------------------------------------------
# Embeds
# ----------------------------------------------------------------------

CARDS_PER_LIST_PAGE = 10


def _ability_block(ability: dict | None) -> str:
    """An ability the way the rest of the game writes one: what it costs,
    how often, and what it does.

    The card screen used to print the description alone, so the single
    most important thing about a card -- whether you can afford to press
    it, and how often -- was the one thing it did not say. Gear shows
    this; cards were the outlier.
    """
    if not ability:
        return "*This card carries no ability.*"
    cost = ability.get("resource_cost")
    kind = ability.get("resource_type", "mana")
    cooldown = ability.get("cooldown")
    bits = []
    if cost:
        bits.append(f"{'🔵' if kind == 'mana' else '⚡'} **{cost}** {'SP' if kind == 'mana' else 'energy'}")
    if cooldown:
        bits.append(f"⏳ **{cooldown}** turn cooldown")
    header = " · ".join(bits)
    return (header + "\n" if header else "") + (ability.get("description") or "")


def _stat_line(stats: dict) -> str:
    """Stats with the same emoji and formatting the inventory uses, so a
    card's numbers read identically to a piece of gear's."""
    # _fmt_stat already carries the emoji AND the label -- wrapping it in
    # another emoji/label pair produced "ATK: +ATK: 7 ATK". Same helper
    # the inventory uses, called the same way, so the two screens format
    # a stat identically by construction rather than by coincidence.
    return "\n".join(f"+{_fmt_stat(stat, value)}" for stat, value in stats.items())


def cards_list_embed(cards: list[PlayerCard], page: int, player_name: str,
                     holders: dict[int, str], note: str | None = None) -> discord.Embed:
    """The LIST screen, deliberately the same shape as
    embedder.inventory_list_embed: numbered rows, page counter in the
    description, a footer explaining how to get to detail.

    Cards started with a bespoke layout -- one card expanded, the rest as
    a blob -- which meant the two collection screens in the game taught
    different habits for the same job. Matching the inventory means the
    numbering, the paging and the Jump button all behave the way a player
    has already learned once.
    """
    total_pages = max(1, (len(cards) + CARDS_PER_LIST_PAGE - 1) // CARDS_PER_LIST_PAGE)
    page = max(0, min(page, total_pages - 1))
    start = page * CARDS_PER_LIST_PAGE
    page_cards = cards[start:start + CARDS_PER_LIST_PAGE]

    embed = discord.Embed(
        title=f"🃏 {player_name}'s Character Cards",
        description=f"Page {page + 1}/{total_pages} -- {len(cards)} total cards",
        color=discord.Color.purple(),
    )
    if note:
        embed.description += f"\n\n{note}"

    if not page_cards:
        embed.add_field(
            name="Empty",
            value="Nothing here yet -- try `/cardpull`.",
            inline=False,
        )
        return embed

    lines = []
    for i, card in enumerate(page_cards, start=start + 1):
        worn = holders.get(card.character_id) if card.character_id else None
        tag = f" ✅ *{worn}*" if worn else ""
        lines.append(
            f"`{i:>3}.` {_stars(card.template.star_rating)} "
            f"{card.template.name} (Lv{card.level}){tag}"
        )
    embed.add_field(name="Cards", value=fit_field(lines), inline=False)
    embed.set_footer(
        text="Pick one from the menu to equip, unequip or level it. "
             "Cards are not in /inventory -- one slot per character, "
             "separate from gear."
    )
    return embed


def card_detail_embed(card: PlayerCard, index: int, total: int,
                      holders: dict[int, str], note: str | None = None) -> discord.Embed:
    """The DETAIL screen -- one card, everything about it."""
    stats = card_service.card_stats(card)
    ability = card_service.card_ability(card)
    worn = holders.get(card.character_id) if card.character_id else None

    embed = discord.Embed(
        title=f"{_stars(card.template.star_rating)} {card.template.name}",
        description=f"*{card.template.lore}*",
        color=discord.Color.purple(),
    )
    if note:
        embed.description += f"\n\n{note}"

    embed.add_field(
        name=f"Level {card.level}/{cc.CARD_MAX_LEVEL}",
        value=_stat_line(stats)[:1024],
        inline=False,
    )
    embed.add_field(
        name=f"⚡ {ability['name']}" if ability else "⚡ Ability",
        value=_ability_block(ability)[:1024],
        inline=False,
    )
    embed.add_field(name="Equipped to", value=f"**{worn}**" if worn else "*Nobody*",
                    inline=True)
    if card.level < cc.CARD_MAX_LEVEL:
        cost = card_service.level_up_cost(card)
        embed.add_field(
            name="Next level",
            value=" / ".join(format_currency(c, a) for c, a in cost.items()),
            inline=True,
        )
    else:
        embed.add_field(name="Next level", value="**Maxed**", inline=True)
    embed.set_footer(text=f"Card {index}/{total}")
    return embed


def pull_result_embed(pulled: list[PlayerCard], message: str) -> discord.Embed:
    best = max((c.template.star_rating for c in pulled), default=3)
    embed = discord.Embed(
        title="Card Banner",
        description=message,
        color=discord.Color.gold() if best >= 5 else discord.Color.purple(),
    )
    for card in pulled:
        embed.add_field(
            name=f"{_stars(card.template.star_rating)} {card.template.name}",
            value=f"*{card.template.lore}*"[:1024],
            inline=False,
        )
    return embed


# ----------------------------------------------------------------------
# Views
# ----------------------------------------------------------------------

class CardPullButton(discord.ui.DynamicItem[discord.ui.Button],
                     template=r"cascade_card_pull:(?P<count>\d+)"):
    def __init__(self, count: int):
        cost = cc.CARD_PULL_COST * count
        super().__init__(discord.ui.Button(
            label=f"Pull x{count} ({cost} cores)",
            style=discord.ButtonStyle.primary if count == 1 else discord.ButtonStyle.success,
            custom_id=f"cascade_card_pull:{count}",
        ))
        self.count = count

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(int(match["count"]))

    async def callback(self, interaction: discord.Interaction):
        if not await check_message_owner(interaction):
            return
        db = SessionLocal()
        try:
            player = get_player(db, interaction.user.id)
            if player is None:
                await responses.send(interaction, "Use `/start` first.", ephemeral=True)
                return
            ok, message, pulled = card_service.pull_cards(db, player, self.count)
            if not ok:
                await responses.send(interaction, message, ephemeral=True)
                return
            embed = pull_result_embed(pulled, message)
        finally:
            db.close()
        await responses.send(interaction, embed=embed)


class CardSelect(discord.ui.Select):
    """Pick a card to act on. Fixed custom_id, options rebuilt per render
    -- the same persistence pattern the inventory browser uses."""

    def __init__(self, cards: list[PlayerCard], holders: dict[int, str],
                 selected: int | None = None, page: int = 0):
        window = cards[page * CARDS_PER_LIST_PAGE:(page + 1) * CARDS_PER_LIST_PAGE]
        options = [
            discord.SelectOption(
                label=f"{card.template.name[:70]} · Lv{card.level}",
                value=str(card.id),
                description=(f"{card.template.star_rating}★ · on "
                             f"{holders.get(card.character_id, '—')}"
                             if card.character_id else
                             f"{card.template.star_rating}★ · unequipped")[:100],
                default=(card.id == selected),
            )
            for card in window
        ] or [discord.SelectOption(label="(no cards yet)", value="none")]
        super().__init__(placeholder="Choose a card...", options=options,
                         custom_id="cascade_card_select", min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            await interaction.response.defer()
            return
        await _render_cards(interaction, selected=int(self.values[0]))


class CardCharacterSelect(discord.ui.Select):
    """Who the selected card goes on. Only rendered once a card is
    chosen, so the screen never asks 'equip what, to whom' at once."""

    def __init__(self, card_id: int, characters: list):
        options = [
            discord.SelectOption(label=pc.display_name[:100], value=f"{card_id}:{pc.id}")
            for pc in paging.window(characters, 0)
        ] or [discord.SelectOption(label="(no characters)", value="none")]
        super().__init__(placeholder="Equip it to...", options=options,
                         custom_id="cascade_card_equip", min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            await interaction.response.defer()
            return
        card_id, character_id = (int(part) for part in self.values[0].split(":"))
        db = SessionLocal()
        try:
            player = get_player(db, interaction.user.id)
            if player is None:
                await responses.send(interaction, "Use `/start` first.", ephemeral=True)
                return
            card = db.get(PlayerCard, card_id)
            character = db.get(PlayerCharacter, character_id)
            if card is None or character is None:
                await responses.send(interaction, "That's gone.", ephemeral=True)
                return
            ok, message = card_service.equip_card(db, player, card, character)
        finally:
            db.close()
        await _render_cards(interaction, selected=card_id, note=message)


class CardActionButton(discord.ui.DynamicItem[discord.ui.Button],
                       template=r"cascade_card_act:(?P<action>unequip|level):(?P<card_id>\d+)"):
    LABELS = {"unequip": "Unequip", "level": "Level +1"}

    def __init__(self, action: str, card_id: int, label: str | None = None,
                 disabled: bool = False):
        super().__init__(discord.ui.Button(
            label=label or self.LABELS[action],
            style=discord.ButtonStyle.secondary if action == "unequip"
            else discord.ButtonStyle.success,
            custom_id=f"cascade_card_act:{action}:{card_id}", disabled=disabled,
        ))
        self.action = action
        self.card_id = card_id

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(match["action"], int(match["card_id"]))

    async def callback(self, interaction: discord.Interaction):
        if not await check_message_owner(interaction):
            return
        db = SessionLocal()
        try:
            player = get_player(db, interaction.user.id)
            if player is None:
                await responses.send(interaction, "Use `/start` first.", ephemeral=True)
                return
            card = db.get(PlayerCard, self.card_id)
            if card is None or card.player_id != player.id:
                await responses.send(interaction, "That card is gone.", ephemeral=True)
                return
            if self.action == "unequip":
                _, message = card_service.unequip_card(db, card)
            else:
                _, message = card_service.level_up_card(db, player, card, 1)
        finally:
            db.close()
        await _render_cards(interaction, selected=self.card_id, note=message)


class CardPageButton(discord.ui.DynamicItem[discord.ui.Button],
                     template=r"cascade_card_page:(?P<direction>prev|next):(?P<page>\d+)"):
    def __init__(self, direction: str, page: int, disabled: bool = False):
        super().__init__(discord.ui.Button(
            label="◀ Prev Page" if direction == "prev" else "Next Page ▶",
            style=discord.ButtonStyle.secondary, disabled=disabled,
            custom_id=f"cascade_card_page:{direction}:{page}",
        ))
        self.direction = direction
        self.page = page

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(match["direction"], int(match["page"]))

    async def callback(self, interaction: discord.Interaction):
        if not await check_message_owner(interaction):
            return
        target = self.page - 1 if self.direction == "prev" else self.page + 1
        await _render_cards(interaction, selected=None, page=max(0, target))


class CardNavButton(discord.ui.DynamicItem[discord.ui.Button],
                    template=r"cascade_card_nav:(?P<direction>prev|next):(?P<card_id>\d+)"):
    """Step to the previous/next card WITHOUT going back to the list.

    The inventory's detail mode has this and the card screen did not, so
    comparing two cards meant list, pick, read, back, pick, read. The
    whole point of a detail view is that you can walk it.
    """

    def __init__(self, direction: str, card_id: int, disabled: bool = False):
        super().__init__(discord.ui.Button(
            label="◀ Prev" if direction == "prev" else "Next ▶",
            style=discord.ButtonStyle.secondary, disabled=disabled,
            custom_id=f"cascade_card_nav:{direction}:{card_id}",
        ))
        self.direction = direction
        self.card_id = card_id

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(match["direction"], int(match["card_id"]))

    async def callback(self, interaction: discord.Interaction):
        if not await check_message_owner(interaction):
            return
        await _render_cards(interaction, selected=self.card_id)


class CardBackButton(discord.ui.DynamicItem[discord.ui.Button],
                     template=r"cascade_card_back"):
    def __init__(self):
        super().__init__(discord.ui.Button(
            label="◀ All cards", style=discord.ButtonStyle.secondary,
            custom_id="cascade_card_back",
        ))

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls()

    async def callback(self, interaction: discord.Interaction):
        if not await check_message_owner(interaction):
            return
        await _render_cards(interaction, selected=None)


class CardsView(OwnedView):
    def __init__(self, cards: list[PlayerCard], holders: dict[int, str],
                 characters: list, selected: PlayerCard | None = None,
                 owner_id: int | None = None, page: int = 0):
        super().__init__(timeout=None, owner_id=owner_id)
        if cards:
            self.add_item(CardSelect(cards, holders,
                                     selected.id if selected else None, page))
        if selected is None and cards:
            pages = max(1, (len(cards) + CARDS_PER_LIST_PAGE - 1) // CARDS_PER_LIST_PAGE)
            self.add_item(CardPageButton("prev", page, disabled=page <= 0))
            self.add_item(CardPageButton("next", page, disabled=page >= pages - 1))
        if selected is not None:
            index = next((i for i, c in enumerate(cards) if c.id == selected.id), 0)
            prev_card = cards[index - 1] if index > 0 else None
            next_card = cards[index + 1] if index < len(cards) - 1 else None
            self.add_item(CardNavButton("prev", (prev_card or selected).id,
                                        disabled=prev_card is None))
            self.add_item(CardNavButton("next", (next_card or selected).id,
                                        disabled=next_card is None))
            self.add_item(CardBackButton())
            self.add_item(CardCharacterSelect(selected.id, characters))
            if selected.character_id is not None:
                self.add_item(CardActionButton("unequip", selected.id))
            # NO +10 button. Card levels cost materials from a band that
            # shifts as the card climbs, so a ten-level jump can span two
            # bands and quietly spend a resource the player was saving --
            # and the cost preview can only honestly show one step.
            self.add_item(CardActionButton(
                "level", selected.id,
                disabled=selected.level >= cc.CARD_MAX_LEVEL))


async def _render_cards(interaction: discord.Interaction, selected: int | None = None,
                        note: str | None = None, page: int = 0,
                        edit: bool = True) -> None:
    """LIST mode with nothing selected, DETAIL mode with something --
    the same two modes /inventory has, reached the same way."""
    db = SessionLocal()
    try:
        player = get_player(db, interaction.user.id)
        if player is None:
            await responses.send(interaction, "Use `/start` first.", ephemeral=True)
            return
        cards = card_service.list_cards(db, player.id)
        characters = character_service.list_owned_characters(db, player)
        holders = {pc.id: pc.display_name for pc in characters}
        chosen = next((c for c in cards if c.id == selected), None)

        if chosen is None:
            embed = cards_list_embed(cards, page, player.username, holders, note)
        else:
            index = next((i for i, c in enumerate(cards, 1) if c.id == chosen.id), 1)
            embed = card_detail_embed(chosen, index, len(cards), holders, note)
            page = (index - 1) // CARDS_PER_LIST_PAGE
        view = CardsView(cards, holders, characters, chosen,
                         owner_id=player.id, page=page)
    finally:
        db.close()
    sender = responses.edit if edit else responses.send
    await sender(interaction, content=None, embed=embed, view=view)


class CardBannerView(OwnedView):
    def __init__(self, owner_id: int | None = None):
        super().__init__(timeout=None, owner_id=owner_id)
        self.add_item(CardPullButton(1))
        self.add_item(CardPullButton(cc.CARD_MULTI_PULL_COUNT))


@guild_decorator
class Cards(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        db = SessionLocal()
        try:
            card_service.ensure_card_templates_seeded(db)
        finally:
            db.close()

    @app_commands.command(name="cards", description="Your Character Cards.")
    async def cards(self, ctx: discord.Interaction):
        await responses.defer(ctx)
        db = SessionLocal()
        try:
            player = get_player(db, ctx.user.id)
            if player is None:
                await responses.send(ctx, "Use `/start` first.", ephemeral=True)
                return
            if not await require_feature(ctx, db, player, "cards"):
                return
        finally:
            db.close()
        await _render_cards(ctx, selected=None, edit=False)

    @app_commands.command(name="cardpull", description="Pull for Character Cards with cores.")
    async def cardpull(self, ctx: discord.Interaction):
        """Same screen as /pull, different banner -- see banner_ui."""
        await responses.defer(ctx)
        db = SessionLocal()
        try:
            player = get_player(db, ctx.user.id)
            if player is None:
                await responses.send(ctx, "Use `/start` first.", ephemeral=True)
                return
            if not await require_feature(ctx, db, player, "cards"):
                return
            banner = banner_ui.BANNERS["card"]
            embed = banner_ui.banner_embed(banner, player)
            view = banner_ui.BannerView("card", owner_id=player.id)
        finally:
            db.close()
        await responses.send(ctx, embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(Cards(bot))
