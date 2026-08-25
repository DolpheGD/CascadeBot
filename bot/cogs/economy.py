from __future__ import annotations

import discord

from discord.ext import commands
from discord import app_commands

from bot.utils import banner_ui, responses
from bot.database.session import SessionLocal
from bot.game.economy import resonance_config
from bot.services import character_service, dungeon_service, echo_exchange_service, lootbox_service
from bot.services.character_gacha_service import pull_multi, pull_single
from bot.services.currency_service import currency_emoji, format_currency
from bot.services.daily_service import DailyOnCooldown, claim_daily
from bot.services.player_service import get_player
from bot.utils import embedder
from bot.utils.guild_decorator import guild_decorator
from bot.utils.logger import get_logger
from bot.utils import names, paging
from bot.utils.ui_guard import require_feature, OwnedView, check_message_owner, require_player

logger = get_logger("economy")


@guild_decorator
class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        db = SessionLocal()
        try:
            lootbox_service.ensure_lootbox_templates_seeded(db)
        finally:
            db.close()

    # COMMAND: /daily
    # Claims the once-per-24h reward. Streak grows the gold bonus and grants
    # bonus shards + lootboxes every 7/30 days.
    @app_commands.command(name="daily", description="Claim your daily reward.")
    async def daily(self, ctx: discord.Interaction):
        await responses.defer(ctx)
        db = SessionLocal()
        try:
            player = get_player(db, ctx.user.id)
            if not await require_player(ctx, player):
                return
            if not await require_feature(ctx, db, player, 'daily'):
                return

            try:
                result = claim_daily(db, player)
            except DailyOnCooldown as exc:
                hours, remainder = divmod(int(exc.time_remaining.total_seconds()), 3600)
                minutes = remainder // 60
                await responses.send(ctx,
                    f"You've already claimed today. Come back in {hours}h {minutes}m.",
                    ephemeral=True,
                )
                return
        finally:
            db.close()

        message = f"Daily reward: **{format_currency('gold', result['gold'])}** (streak: {result['streak']} days)"
        if result["reroll_tokens"]:
            message += f", **{format_currency('reroll_tokens', result['reroll_tokens'])}**"
        if result["shards"]:
            message += f", **{format_currency('shards', result['shards'])}**"
        # CORES ON THE DAILY LINE. They were being granted and not
        # mentioned, so the source most likely to introduce a new player
        # to the currency was the one that never named it.
        if result.get("cores"):
            message += f", **{format_currency('cores', result['cores'])}**"
        tier_counts: dict[str, int] = {}
        for tier in result["lootbox_tiers"]:
            tier_counts[tier] = tier_counts.get(tier, 0) + 1
        boxes_text = ", ".join(f"{count}x {tier.title()} Lootbox" for tier, count in tier_counts.items())
        if boxes_text:
            message += f"\nAlso received: {boxes_text}"
        materials_text = ", ".join(
            format_currency(material, amount) for material, amount in result["materials"].items()
        )
        if materials_text:
            message += f"\nMaterials: {materials_text}"
        await responses.send(ctx, message)


    # COMMAND: /pull
    # Spends shards on a gacha pull -- characters only. Pulling a character
    # you already own raises their Resonance and pays Echoes instead
    # (bot/game/economy/resonance_config.py).
    @app_commands.command(name="pull", description="Pull for characters.")
    async def pull(self, ctx: discord.Interaction):
        """The character banner.

        No `count` argument any more -- the banner screen has the buttons,
        and both banners now share it (see bot/utils/banner_ui.py). A
        slash-command choice that duplicates a button on the screen it
        opens is two ways to do one thing, and the two drifted: /pull took
        a count, /cardpull did not.
        """
        await responses.defer(ctx)
        db = SessionLocal()
        try:
            player = get_player(db, ctx.user.id)
            if not await require_player(ctx, player):
                return
            if not await require_feature(ctx, db, player, "pull"):
                return

            expedition = dungeon_service.get_active_expedition(db, player.id)
            if dungeon_service.is_in_combat(expedition):
                await responses.send(ctx,
                    "You can't pull mid-battle -- finish the fight first!", ephemeral=True
                )
                return

            banner = banner_ui.BANNERS["character"]
            embed = banner_ui.banner_embed(banner, player)
            view = banner_ui.BannerView("character", owner_id=player.id, db=db, player=player)
        finally:
            db.close()
        await responses.send(ctx, embed=embed, view=view)

    # `/pull_rates` USED TO LIVE HERE, AND IS GONE.
    #
    # It opened a page restating numbers the banner screen already shows.
    # When /pull and /cardpull were merged into one screen (see
    # bot/utils/banner_ui.py) the odds, both pity counters and the
    # guarantee thresholds moved onto the front of the banner itself --
    # where they are useful, rather than one command away where they are
    # a footnote nobody types. The command survived that merge as a
    # duplicate of a screen the player was already looking at.
    #
    # Its embed (gacha_rates_embed) went with it: a rates table with no
    # caller is a second definition of the odds waiting to disagree with
    # banner_ui's.

    # COMMAND: /open
    # Opens every lootbox of the chosen tier at once, rolling gold/shards
    # and item(s) at that tier's boosted rarity odds.
    @app_commands.command(name="open", description="Open all your lootboxes of a given tier.")
    @app_commands.choices(tier=[
        app_commands.Choice(name="Common", value="common"),
        app_commands.Choice(name="Uncommon", value="uncommon"),
        app_commands.Choice(name="Rare", value="rare"),
        app_commands.Choice(name="Epic", value="epic"),
        app_commands.Choice(name="Legendary", value="legendary"),
        app_commands.Choice(name="Mythic", value="mythic"),
    ])
    async def open_lootbox(self, ctx: discord.Interaction, tier: str):
        await responses.defer(ctx)
        db = SessionLocal()
        try:
            player = get_player(db, ctx.user.id)
            if not await require_player(ctx, player):
                return
            if not await require_feature(ctx, db, player, 'inventory'):
                return

            expedition = dungeon_service.get_active_expedition(db, player.id)
            if dungeon_service.is_in_combat(expedition):
                await responses.send(ctx,
                    "You can't open lootboxes mid-battle -- finish the fight first!",
                    ephemeral=True,
                )
                return

            owned = lootbox_service.list_player_lootboxes(db, player.id)
            entry = next((o for o in owned if o.template.tier == tier), None)
            if entry is None:
                await responses.send(ctx,
                    f"You don't have any {tier.title()} Lootboxes.", ephemeral=True
                )
                return

            ok, message, rewards = lootbox_service.open_lootboxes(
                db, player, tier, count=entry.quantity
            )
            if not ok:
                await responses.send(ctx, message, ephemeral=True)
                return

            embed = discord.Embed(title=message, color=discord.Color.purple())
            embed.add_field(name="Gold", value=format_currency("gold", rewards["gold"]), inline=True)
            if rewards["shards"]:
                embed.add_field(name="Shards", value=format_currency("shards", rewards["shards"]), inline=True)
            if rewards["items"]:
                items_text = "\n".join(
                    f"{item.display_name} ({item.rarity.value})" for item in rewards["items"]
                )
                embed.add_field(name="Items", value=items_text, inline=False)
        finally:
            db.close()

        await responses.send(ctx, embed=embed)


    # COMMAND: /exchange
    # Spends Echoes -- the duplicate currency -- on a character of the
    # player's choosing. The deterministic counterpart to /pull.
    @app_commands.command(
        name="exchange",
        description="Spend Echoes from duplicate pulls on any character you want.",
    )
    async def exchange(self, ctx: discord.Interaction):
        await responses.defer(ctx)
        db = SessionLocal()
        try:
            player = get_player(db, ctx.user.id)
            if not await require_player(ctx, player):
                return
            if not await require_feature(ctx, db, player, "exchange"):
                return
            embed, view = _render_exchange(db, player, "characters", 0)
        finally:
            db.close()

        await responses.send(ctx, embed=embed, view=view)

    # COMMAND: /resonance
    # One character's duplicate-upgrade track. Separate from /profile
    # because it's the screen a player reads while deciding whether to
    # keep pulling, which is a different question from "how is this
    # character equipped".
    @app_commands.command(
        name="resonance",
        description="See what duplicate copies have unlocked for a character.",
    )
    async def resonance(self, ctx: discord.Interaction):
        await responses.defer(ctx)
        db = SessionLocal()
        try:
            player = get_player(db, ctx.user.id)
            if not await require_player(ctx, player):
                return
            # Resonance is a property of DUPLICATE PULLS, so it travels
            # with /pull rather than standing on its own.
            if not await require_feature(ctx, db, player, "pull"):
                return
            owned = character_service.list_owned_characters(db, player)
            embed = embedder.resonance_embed(owned[0])
            view = ResonancePickerView(owned, owned[0].id, owner_id=player.id)
        finally:
            db.close()

        await responses.send(ctx, embed=embed, view=view)


# ----------------------------------------------------------------------
# THE ECHO EXCHANGE
#
# Short-lived and owner-locked rather than persistent: a menu a player
# opens, acts on and closes, holding no state worth surviving a restart.
# EVERY callback re-reads the player and their balances from the
# database, so a stale message can't spend money that isn't there.
#
# ----------------------------------------------------------------------
# THREE COUNTERS ON ONE SCREEN, RATHER THAN ONE ENORMOUS LIST
# ----------------------------------------------------------------------
# The shop now sells 29 characters and 26 cards, and converts cores. As
# one page that is 55 rows of storefront -- past Discord's 6,000-char
# embed budget, and long past the point anyone reads it.
#
# So it is TABBED. One counter is visible at a time, each counter is
# paged, and the tab row is always on the last row where it stays put
# while the contents above it change. The alternative -- three separate
# commands -- was rejected for the reason the two pull banners were
# merged into one screen (see bot/utils/banner_ui.py): learning one
# would teach you nothing about the others, and the differences between
# them would be accidents of when each was written.
#
# ONE RENDER FUNCTION builds all three. The old exchange had the shop
# embed constructed in three separate places (the command, the purchase
# callback and the page button), which is how the embed and its select
# ended up disagreeing about which page was showing.
# ----------------------------------------------------------------------

TAB_ROW = 3  # tabs always last, so they don't move when a counter does


def _sorted_offers(offers: list[dict]) -> list[dict]:
    """Cheapest affordable first: a player with few Echoes wants to see
    what they can actually buy without scrolling past 5-stars they
    can't."""
    return sorted(offers, key=lambda o: (not o["affordable"], o["cost"]))


def _render_exchange(db, player, counter: str, page: int):
    """(embed, view) for one counter at one page. THE single place the
    exchange screen is built."""
    view = ExchangeView(owner_id=player.id, counter=counter, page=page)

    if counter == "cards":
        offers = _sorted_offers(echo_exchange_service.card_offers(db, player))
        shown = paging.window(offers, page)
        view.add_item(ExchangeCardSelect(shown, page, len(offers)))
        paging.add_page_buttons(view, page, len(offers), row=1)
        embed = embedder.echo_card_exchange_embed(
            player, shown, page=page, total=len(offers))
    elif counter == "convert":
        batches = echo_exchange_service.sellable_batches(player)
        for amount in batches:
            view.add_item(SellCoresButton(amount))
        embed = embedder.echo_convert_embed(player, batches)
    else:
        offers = _sorted_offers(echo_exchange_service.offers(db, player))
        shown = paging.window(offers, page)
        view.add_item(ExchangeCharacterSelect(shown, page, len(offers)))
        paging.add_page_buttons(view, page, len(offers), row=1)
        embed = embedder.echo_exchange_embed(
            player, shown, page=page, total=len(offers))

    return embed, view


async def _refresh_exchange(interaction, counter: str, page: int,
                            result_embed: discord.Embed | None = None):
    """Re-render the shop in place, optionally following up with what the
    player just bought. Re-reads everything -- the balances a purchase
    just changed are the whole point of the refresh."""
    db = SessionLocal()
    try:
        player = get_player(db, interaction.user.id)
        if player is None:
            await responses.send(interaction, "Use `/start` first.", ephemeral=True)
            return
        embed, view = _render_exchange(db, player, counter, page)
    finally:
        db.close()
    await responses.edit(interaction, embed=embed, view=view)
    if result_embed is not None:
        await interaction.followup.send(embed=result_embed, ephemeral=True)


class ExchangeView(OwnedView):
    def __init__(self, owner_id: int | None = None,
                 counter: str = "characters", page: int = 0):
        super().__init__(timeout=300, owner_id=owner_id)
        self.counter = counter
        self.page = max(0, page)
        for key, label, emoji in echo_exchange_service.COUNTERS:
            self.add_item(ExchangeTabButton(key, label, emoji, active=key == counter))

    async def rerender(self, interaction, page: int):
        """The contract bot/utils/paging.PageButton calls back into."""
        if not await check_message_owner(interaction):
            return
        await _refresh_exchange(interaction, self.counter, page)


class ExchangeTabButton(discord.ui.Button):
    def __init__(self, key: str, label: str, emoji: str, active: bool):
        super().__init__(
            label=label, emoji=emoji, row=TAB_ROW,
            # The active tab is highlighted AND disabled: a button that
            # re-renders the page you are already on is an interaction
            # that looks like it did nothing.
            style=discord.ButtonStyle.primary if active else discord.ButtonStyle.secondary,
            disabled=active,
        )
        self.key = key

    async def callback(self, interaction: discord.Interaction):
        if not await check_message_owner(interaction):
            return
        # Switching counters resets to page 0 -- carrying page 3 from a
        # 29-entry counter into a 5-entry one lands on an empty screen.
        await _refresh_exchange(interaction, self.key, 0)


class ExchangeCharacterSelect(discord.ui.Select):
    """One page of the character counter.

    THIS USED TO SILENTLY TRUNCATE. The options list was built for every
    character and then cut with `options[:25]`, with a comment noting the
    roster was 24 against Discord's ceiling of 25. The roster is now 29,
    so the five most expensive characters simply weren't in the menu --
    reported as "the menu is too long so you can't buy some of them",
    and invisible from the storefront embed, which listed all 29 happily.

    Slicing to fit is the wrong shape of fix for a list that grows: it
    fails silently, it fails worse every time a character is added, and
    the things it drops are the expensive ones a player is most likely to
    be saving for. Paging can't lose anything.
    """

    def __init__(self, window: list[dict], page: int, total: int):
        options = []
        for offer in window:
            mark = "✅" if offer["affordable"] else "🔒"
            owned = f" · R{offer['resonance']}" if offer["owned"] else " · NEW"
            options.append(discord.SelectOption(
                label=names.fit_suffix(
                    f"{mark} {offer['name']}", f"— {offer['cost']:,} ✴️{owned}", 100),
                value=str(offer["template_id"]),
                description=("Raises their Resonance" if offer["owned"]
                             else "You don't own this character yet")[:100],
            ))
        super().__init__(
            placeholder=paging.placeholder_for("Buy a character...", page, total),
            options=options, min_values=1, max_values=1, row=0)

    async def callback(self, interaction: discord.Interaction):
        if not await check_message_owner(interaction):
            return
        db = SessionLocal()
        try:
            player = get_player(db, interaction.user.id)
            if player is None:
                await responses.send(interaction, "Use `/start` first.", ephemeral=True)
                return
            try:
                result = echo_exchange_service.purchase(db, player, int(self.values[0]))
            except echo_exchange_service.ExchangeError as exc:
                await responses.send(interaction, str(exc), ephemeral=True)
                return
            # The purchase renders through the ordinary pull embed, so a
            # bought character and a pulled one report themselves the same
            # way -- including a duplicate purchase announcing the
            # resonance level it just unlocked.
            result_embed = embedder.gacha_pull_embed([result], player=player)
            result_embed.title = f"✴️ Echo Exchange — {result['cost']:,} spent"
        finally:
            db.close()
        await _refresh_exchange(interaction, "characters", self.view.page, result_embed)


class ExchangeCardSelect(discord.ui.Select):
    """One page of the Card counter.

    The option's DESCRIPTION carries the ability, not flavour text. A
    card is bought for what it does, and the catalog is named in lore
    phrases -- so the name alone can't tell you whether this is the card
    you have been saving for.
    """

    def __init__(self, window: list[dict], page: int, total: int):
        options = []
        for offer in window:
            mark = "✅" if offer["affordable"] else "🔒"
            owned = f" · ×{offer['owned']}" if offer["owned"] else ""
            options.append(discord.SelectOption(
                label=names.fit_suffix(
                    f"{mark} {offer['name']}", f"— {offer['cost']:,} ✴️{owned}", 100),
                # The CATALOG id, not the row id: a card template's row id
                # depends on seed order and would point at a different
                # card on a rebuilt database.
                value=offer["card_id"],
                description=f"{offer['star_rating']}★ · {offer['ability_name']}"[:100],
            ))
        super().__init__(
            placeholder=paging.placeholder_for("Buy a Character Card...", page, total),
            options=options, min_values=1, max_values=1, row=0)

    async def callback(self, interaction: discord.Interaction):
        if not await check_message_owner(interaction):
            return
        db = SessionLocal()
        try:
            player = get_player(db, interaction.user.id)
            if player is None:
                await responses.send(interaction, "Use `/start` first.", ephemeral=True)
                return
            try:
                result = echo_exchange_service.purchase_card(
                    db, player, self.values[0])
            except echo_exchange_service.ExchangeError as exc:
                await responses.send(interaction, str(exc), ephemeral=True)
                return
            # Rendered through the CARD BANNER's own result embed, so a
            # bought card and a pulled one report themselves identically
            # -- the same reason the character counter reuses the pull
            # embed rather than inventing a purchase embed.
            from bot.cogs.cards import pull_result_embed
            result_embed = pull_result_embed(
                [result["card"]],
                f"Bought from the Echo Exchange for {result['cost']:,} ✴️.")
            result_embed.title = "✴️ Echo Exchange"
        finally:
            db.close()
        await _refresh_exchange(interaction, "cards", self.view.page, result_embed)


class SellCoresButton(discord.ui.Button):
    def __init__(self, amount: int):
        echoes = resonance_config.echoes_for_cores(amount)
        super().__init__(
            label=f"{amount:,} → {echoes:,} ✴️",
            emoji=currency_emoji("cores"),
            style=discord.ButtonStyle.success,
            row=0,
        )
        self.amount = amount

    async def callback(self, interaction: discord.Interaction):
        if not await check_message_owner(interaction):
            return
        db = SessionLocal()
        try:
            player = get_player(db, interaction.user.id)
            if player is None:
                await responses.send(interaction, "Use `/start` first.", ephemeral=True)
                return
            try:
                result = echo_exchange_service.sell_cores(db, player, self.amount)
            except echo_exchange_service.ExchangeError as exc:
                await responses.send(interaction, str(exc), ephemeral=True)
                return
            note = (f"\nKept **{result['change']:,}** cores as change."
                    if result["change"] else "")
            result_embed = discord.Embed(
                title="✴️ Sold",
                description=(
                    f"**{result['cores']:,}** {currency_emoji('cores')} → "
                    f"**{result['echoes']:,} ✴️**{note}\n"
                    f"Balance: **{player.echoes:,} ✴️** · "
                    f"**{player.cores:,}** {currency_emoji('cores')}"
                ),
                color=discord.Color.purple(),
            )
        finally:
            db.close()
        await _refresh_exchange(interaction, "convert", 0, result_embed)


def _resonance_order(owned: list, current_id: int) -> list:
    """Current character first, then closest to their next Resonance --
    which is what someone opening this menu is shopping for."""
    return sorted(owned, key=lambda pc: (pc.id != current_id, -pc.dupe_count,
                                         -pc.effective_star, pc.display_name))


class ResonancePickerSelect(discord.ui.Select):
    def __init__(self, owned: list, current_id: int):
        options = [
            discord.SelectOption(
                label=names.fit_suffix(
                    pc.display_name,
                    f"— R{resonance_config.resonance_for(pc.dupe_count)}"
                    f"/{resonance_config.MAX_RESONANCE}",
                    100,
                ),
                value=str(pc.id),
                default=(pc.id == current_id),
            )
            # Sorted so the character being viewed is always present --
            # with 25+ owned this can only show a window, and a picker
            # whose current selection fell off the edge looks broken.
            for pc in paging.window(_resonance_order(owned, current_id), 0)
        ]
        super().__init__(
            placeholder=paging.placeholder_for("Switch character", 0, len(owned)),
            options=options, min_values=1, max_values=1,
        )

    async def callback(self, interaction: discord.Interaction):
        if not await check_message_owner(interaction):
            return
        db = SessionLocal()
        try:
            player = get_player(db, interaction.user.id)
            if player is None:
                await responses.send(interaction, "Use `/start` first.", ephemeral=True)
                return
            owned = character_service.list_owned_characters(db, player)
            chosen = next((pc for pc in owned if pc.id == int(self.values[0])), owned[0])
            embed = embedder.resonance_embed(chosen)
            view = ResonancePickerView(owned, chosen.id, owner_id=player.id)
        finally:
            db.close()
        await responses.edit(interaction, embed=embed, view=view)


class ResonancePickerView(OwnedView):
    def __init__(self, owned: list, current_id: int, owner_id: int | None = None):
        super().__init__(timeout=300, owner_id=owner_id)
        self.add_item(ResonancePickerSelect(owned, current_id))


async def setup(bot):
    await bot.add_cog(Economy(bot))
