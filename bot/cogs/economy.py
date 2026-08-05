from __future__ import annotations

import discord

from discord.ext import commands
from discord import app_commands

from bot.database.session import SessionLocal
from bot.game.economy import resonance_config
from bot.services import character_service, dungeon_service, echo_exchange_service, lootbox_service
from bot.services.character_gacha_service import pull_multi, pull_single
from bot.services.currency_service import format_currency
from bot.services.daily_service import DailyOnCooldown, claim_daily
from bot.services.player_service import get_player
from bot.utils import embedder
from bot.utils.guild_decorator import guild_decorator
from bot.utils.logger import get_logger
from bot.utils import names
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
        db = SessionLocal()
        try:
            player = get_player(db, ctx.user.id)
            if not await require_player(ctx, player):
                return

            try:
                result = claim_daily(db, player)
            except DailyOnCooldown as exc:
                hours, remainder = divmod(int(exc.time_remaining.total_seconds()), 3600)
                minutes = remainder // 60
                await ctx.response.send_message(
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
            message += f" and **{format_currency('shards', result['shards'])}** for your streak milestone!"
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
        await ctx.response.send_message(message)


    # COMMAND: /pull
    # Spends shards on a gacha pull -- characters only. Pulling a character
    # you already own raises their Resonance and pays Echoes instead
    # (bot/game/economy/resonance_config.py).
    @app_commands.command(name="pull", description="Spend shards to pull a new character.")
    @app_commands.choices(count=[
        app_commands.Choice(name="Single Pull", value=1),
        app_commands.Choice(name="10x Pull", value=10),
    ])
    async def pull(self, ctx: discord.Interaction, count: int = 1):
        db = SessionLocal()
        try:
            player = get_player(db, ctx.user.id)
            if not await require_player(ctx, player):
                return
            if not await require_feature(ctx, db, player, "pull"):
                return

            expedition = dungeon_service.get_active_expedition(db, player.id)
            if dungeon_service.is_in_combat(expedition):
                await ctx.response.send_message(
                    "You can't pull mid-battle -- finish the fight first!", ephemeral=True
                )
                return

            try:
                if count == 1:
                    success, message, results = pull_single(db, player)
                else:
                    success, message, results = pull_multi(db, player, count=count)

                if not success:
                    await ctx.response.send_message(message, ephemeral=True)
                    return

                embed = embedder.gacha_pull_embed(results, player=player)
            except Exception:
                # Surface the real error instead of a silent "This
                # interaction failed" -- makes any future regression here
                # immediately diagnosable instead of a mystery report.
                logger.exception("`/pull` failed for player %s (count=%s)", player.id, count)
                await ctx.response.send_message(
                    "Something went wrong generating your pull results. This has been logged -- "
                    "please report it if it keeps happening.",
                    ephemeral=True,
                )
                return
        finally:
            db.close()

        await ctx.response.send_message(embed=embed)

    # COMMAND: /pull_rates
    # Shows gacha odds by star rating, cost, and the duplicate-conversion rule.
    @app_commands.command(name="pull_rates", description="View gacha odds, pity progress, and pull costs.")
    async def pull_rates(self, ctx: discord.Interaction):
        db = SessionLocal()
        try:
            # Player is optional here on purpose -- someone who hasn't run
            # /start yet should still be able to read the odds table, they
            # just don't get a personal pity readout with it.
            player = get_player(db, ctx.user.id)
            embed = embedder.gacha_rates_embed(player=player)
        except Exception:
            logger.exception("`/pull_rates` failed to build its embed")
            await ctx.response.send_message(
                "Something went wrong loading gacha rates. This has been logged -- "
                "please report it if it keeps happening.",
                ephemeral=True,
            )
            return
        finally:
            db.close()
        await ctx.response.send_message(embed=embed, ephemeral=True)

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
        db = SessionLocal()
        try:
            player = get_player(db, ctx.user.id)
            if not await require_player(ctx, player):
                return

            expedition = dungeon_service.get_active_expedition(db, player.id)
            if dungeon_service.is_in_combat(expedition):
                await ctx.response.send_message(
                    "You can't open lootboxes mid-battle -- finish the fight first!",
                    ephemeral=True,
                )
                return

            owned = lootbox_service.list_player_lootboxes(db, player.id)
            entry = next((o for o in owned if o.template.tier == tier), None)
            if entry is None:
                await ctx.response.send_message(
                    f"You don't have any {tier.title()} Lootboxes.", ephemeral=True
                )
                return

            ok, message, rewards = lootbox_service.open_lootboxes(
                db, player, tier, count=entry.quantity
            )
            if not ok:
                await ctx.response.send_message(message, ephemeral=True)
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

        await ctx.response.send_message(embed=embed)


    # COMMAND: /exchange
    # Spends Echoes -- the duplicate currency -- on a character of the
    # player's choosing. The deterministic counterpart to /pull.
    @app_commands.command(
        name="exchange",
        description="Spend Echoes from duplicate pulls on any character you want.",
    )
    async def exchange(self, ctx: discord.Interaction):
        db = SessionLocal()
        try:
            player = get_player(db, ctx.user.id)
            if not await require_player(ctx, player):
                return
            if not await require_feature(ctx, db, player, "exchange"):
                return
            offers = echo_exchange_service.offers(db, player)
            embed = embedder.echo_exchange_embed(player, offers)
            view = EchoExchangeView(offers, owner_id=player.id)
        finally:
            db.close()

        await ctx.response.send_message(embed=embed, view=view)

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
        db = SessionLocal()
        try:
            player = get_player(db, ctx.user.id)
            if not await require_player(ctx, player):
                return
            owned = character_service.list_owned_characters(db, player)
            embed = embedder.resonance_embed(owned[0])
            view = ResonancePickerView(owned, owned[0].id, owner_id=player.id)
        finally:
            db.close()

        await ctx.response.send_message(embed=embed, view=view)


# ----------------------------------------------------------------------
# Echo exchange views
#
# Both are short-lived and owner-locked rather than persistent: they're
# menus a player opens, acts on, and closes, and neither holds state
# worth surviving a restart -- every callback re-reads the player and
# their echo balance from the database, so a stale message can't spend
# money that isn't there.
# ----------------------------------------------------------------------

class EchoExchangeSelect(discord.ui.Select):
    def __init__(self, offers: list[dict]):
        options = []
        # Cheapest affordable first: the list is 24 characters against
        # Discord's 25-option ceiling, and a player with few echoes wants
        # to see what they can actually buy without scrolling past six
        # 5-stars they can't.
        for offer in sorted(offers, key=lambda o: (not o["affordable"], o["cost"])):
            mark = "✅" if offer["affordable"] else "🔒"
            owned = f" · R{offer['resonance']}" if offer["owned"] else " · NEW"
            options.append(discord.SelectOption(
                label=names.fit_suffix(
                    f"{mark} {offer['name']}", f"— {offer['cost']:,} ✴️{owned}", 100),
                value=str(offer["template_id"]),
                description=("Raises their Resonance" if offer["owned"]
                             else "You don't own this character yet")[:100],
            ))
        super().__init__(placeholder="Buy a character...", options=options[:25],
                         min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        if not await check_message_owner(interaction):
            return
        db = SessionLocal()
        try:
            player = get_player(db, interaction.user.id)
            if player is None:
                await interaction.response.send_message("Use `/start` first.", ephemeral=True)
                return
            try:
                result = echo_exchange_service.purchase(db, player, int(self.values[0]))
            except echo_exchange_service.ExchangeError as exc:
                await interaction.response.send_message(str(exc), ephemeral=True)
                return

            # The purchase renders through the ordinary pull embed, so a
            # bought character and a pulled one report themselves the same
            # way -- including a duplicate purchase announcing the
            # resonance level it just unlocked.
            result_embed = embedder.gacha_pull_embed([result], player=player)
            result_embed.title = f"✴️ Echo Exchange — {result['cost']:,} spent"

            offers = echo_exchange_service.offers(db, player)
            shop_embed = embedder.echo_exchange_embed(player, offers)
            view = EchoExchangeView(offers, owner_id=player.id)
        finally:
            db.close()

        await interaction.response.edit_message(embed=shop_embed, view=view)
        await interaction.followup.send(embed=result_embed, ephemeral=True)


class EchoExchangeView(OwnedView):
    def __init__(self, offers: list[dict], owner_id: int | None = None):
        super().__init__(timeout=300, owner_id=owner_id)
        self.add_item(EchoExchangeSelect(offers))


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
            for pc in owned
        ][:25]
        super().__init__(placeholder="Switch character...", options=options,
                         min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        if not await check_message_owner(interaction):
            return
        db = SessionLocal()
        try:
            player = get_player(db, interaction.user.id)
            if player is None:
                await interaction.response.send_message("Use `/start` first.", ephemeral=True)
                return
            owned = character_service.list_owned_characters(db, player)
            chosen = next((pc for pc in owned if pc.id == int(self.values[0])), owned[0])
            embed = embedder.resonance_embed(chosen)
            view = ResonancePickerView(owned, chosen.id, owner_id=player.id)
        finally:
            db.close()
        await interaction.response.edit_message(embed=embed, view=view)


class ResonancePickerView(OwnedView):
    def __init__(self, owned: list, current_id: int, owner_id: int | None = None):
        super().__init__(timeout=300, owner_id=owner_id)
        self.add_item(ResonancePickerSelect(owned, current_id))


async def setup(bot):
    await bot.add_cog(Economy(bot))
