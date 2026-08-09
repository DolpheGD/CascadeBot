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
from bot.utils import paging, responses
from bot.utils.embedder._shared import fit_field
from bot.utils.guild_decorator import guild_decorator
from bot.utils.ui_guard import OwnedView, check_message_owner, require_feature

STAR_EMOJI = {3: "⭐", 4: "🌟", 5: "💫"}


def _stars(n: int) -> str:
    return STAR_EMOJI.get(n, "⭐") * 1 + f" {n}★"


# ----------------------------------------------------------------------
# Embeds
# ----------------------------------------------------------------------

def cards_embed(db, player, cards: list[PlayerCard], page: int = 0,
                holders: dict[int, str] | None = None,
                selected: PlayerCard | None = None,
                note: str | None = None) -> discord.Embed:
    embed = discord.Embed(
        title="Character Cards",
        description=(
            f"{format_currency('cores', player.cores)} · "
            f"one card per character · `/cardpull` for more"
        ),
        color=discord.Color.purple(),
    )
    if note:
        # The result of the last press, on the SAME message. A separate
        # ephemeral "equipped!" is a second thing to dismiss before you
        # can see the screen it is talking about.
        embed.description += f"\n\n{note}"

    if not cards:
        embed.add_field(
            name="Nothing yet",
            value=("Cards come from their own banner, paid in "
                   f"{format_currency('cores', cc.CARD_PULL_COST)} a pull. "
                   "They carry the strongest abilities in the game — the ones "
                   "gear no longer rolls."),
            inline=False,
        )
        return embed

    holders = holders or {}

    # THE SELECTED CARD IN FULL, then the rest as one-liners.
    #
    # The first version listed every card at full detail, which at ten
    # cards is four screens of lore nobody scrolls and, past about
    # fourteen, silently truncated fields. Detail-for-one plus a roster
    # is the shape that stays readable at any collection size.
    if selected is not None:
        stats = card_service.card_stats(selected)
        stat_text = " · ".join(f"**+{v:g}** {s.replace('_', ' ')}"
                               for s, v in stats.items())
        ability = card_service.card_ability(selected)
        worn = holders.get(selected.character_id) if selected.character_id else None
        cost = card_service.level_up_cost(selected)
        cost_text = " / ".join(format_currency(c, a) for c, a in cost.items())
        embed.add_field(
            name=f"{_stars(selected.template.star_rating)} {selected.template.name} "
                 f"— Lv{selected.level}/{cc.CARD_MAX_LEVEL}",
            value=fit_field([
                f"*{selected.template.lore}*",
                "",
                stat_text,
                f"**{ability['name']}** — {ability.get('description', '')}"
                if ability else "*No ability.*",
                "",
                f"On **{worn}**" if worn else "*Not equipped.*",
                f"Next level: {cost_text}"
                if selected.level < cc.CARD_MAX_LEVEL else "**Maxed.**",
            ]),
            inline=False,
        )

    others = [c for c in cards if selected is None or c.id != selected.id]
    if others:
        embed.add_field(
            name=f"Collection ({len(cards)})",
            value=fit_field([
                f"{_stars(c.template.star_rating)} **{c.template.name}** Lv{c.level}"
                + (f" — on {holders[c.character_id]}"
                   if c.character_id in holders else "")
                for c in others
            ]),
            inline=False,
        )
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
                 selected: int | None = None):
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
            for card in paging.window(cards, 0)
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
                       template=r"cascade_card_act:(?P<action>unequip|level|level10):(?P<card_id>\d+)"):
    LABELS = {"unequip": "Unequip", "level": "Level +1", "level10": "Level +10"}

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
                levels = 10 if self.action == "level10" else 1
                _, message = card_service.level_up_card(db, player, card, levels)
        finally:
            db.close()
        await _render_cards(interaction, selected=self.card_id, note=message)


class CardsView(OwnedView):
    def __init__(self, cards: list[PlayerCard], holders: dict[int, str],
                 characters: list, selected: PlayerCard | None = None,
                 owner_id: int | None = None):
        super().__init__(timeout=None, owner_id=owner_id)
        if cards:
            self.add_item(CardSelect(cards, holders, selected.id if selected else None))
        if selected is not None:
            self.add_item(CardCharacterSelect(selected.id, characters))
            if selected.character_id is not None:
                self.add_item(CardActionButton("unequip", selected.id))
            maxed = selected.level >= cc.CARD_MAX_LEVEL
            self.add_item(CardActionButton("level", selected.id, disabled=maxed))
            self.add_item(CardActionButton("level10", selected.id, disabled=maxed))


async def _render_cards(interaction: discord.Interaction, selected: int | None = None,
                        note: str | None = None) -> None:
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
        embed = cards_embed(db, player, cards, holders=holders,
                            selected=chosen, note=note)
        view = CardsView(cards, holders, characters, chosen, owner_id=player.id)
    finally:
        db.close()
    await responses.edit(interaction, content=None, embed=embed, view=view)


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
            cards = card_service.list_cards(db, player.id)
            characters = character_service.list_owned_characters(db, player)
            holders = {pc.id: pc.display_name for pc in characters}
            chosen = cards[0] if cards else None
            embed = cards_embed(db, player, cards, holders=holders, selected=chosen)
            view = CardsView(cards, holders, characters, chosen, owner_id=player.id)
        finally:
            db.close()
        await responses.send(ctx, embed=embed, view=view)

    @app_commands.command(name="cardpull", description="Pull for Character Cards with cores.")
    async def cardpull(self, ctx: discord.Interaction):
        await responses.defer(ctx)
        db = SessionLocal()
        try:
            player = get_player(db, ctx.user.id)
            if player is None:
                await responses.send(ctx, "Use `/start` first.", ephemeral=True)
                return
            if not await require_feature(ctx, db, player, "cards"):
                return
            embed = discord.Embed(
                title="Card Banner",
                description=(
                    f"You have {format_currency('cores', player.cores)}.\n\n"
                    f"**{cc.CARD_PULL_COST} cores** a pull. A 5★ is guaranteed by "
                    f"pull {cc.CARD_PITY_FIVE_STAR}, a 4★ or better by pull "
                    f"{cc.CARD_PITY_FOUR_STAR}.\n\n"
                    "This banner keeps its own count — pulling here never touches "
                    "your character pity, and vice versa."
                ),
                color=discord.Color.purple(),
            )
            view = CardBannerView(owner_id=player.id)
        finally:
            db.close()
        await responses.send(ctx, embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(Cards(bot))
