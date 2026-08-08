import discord

from discord.ext import commands
from discord import app_commands

from bot.utils import names, paging
from bot.database.models.enums import CLASS_EMOJI, CharacterClass
from bot.utils import responses
from bot.database.session import SessionLocal
from bot.services.player_service import get_or_create_player, get_player
from bot.services.currency_service import add_currency
from bot.services import (account_service, character_service, dungeon_service,
                          gift_service, inventory_service, story_service)
from bot.utils.ui_guard import OwnedView, require_feature, require_player
from bot.utils.guild_decorator import guild_decorator
from bot.utils import embedder

# STARTING_GOLD / STARTING_SHARDS are gone: /start no longer grants
# currency. The prologue hands out everything a new player needs, in
# the order they can use it. See bot/game/story/story_config.py.


# ----------------------------------------------------------------------
# Profile is 3 pages (Overview / Equipment / Abilities). A plain View is
# fine here (not a DynamicItem/persistent view) since Prev/Next just cycle
# a page index with no per-user target data that needs to survive a
# restart -- worst case the view expires and the player just re-runs
# /profile, which is a much smaller inconvenience than an in-progress fight
# or equip state would be.
# ----------------------------------------------------------------------

class CharacterProfileSelect(discord.ui.Select):
    """Lets the player switch which of their owned characters /profile is
    showing -- previously this only ever showed the avatar."""
    def __init__(self, page: int, current_character_id: int, owned: list):
        # SORTED so the character being viewed is always on the first
        # page, then by level. With more than 25 owned characters this
        # select can only show a window (Discord's ceiling), and the one
        # thing that must never fall off the edge is the one you're
        # looking at -- otherwise the menu shows no selection and looks
        # broken. Full paging lives on the squad picker, where being
        # unable to reach a character actually blocks play; here the
        # sort is enough, because switching to anyone is one more click
        # either way.
        ordered = sorted(
            owned,
            key=lambda pc: (pc.id != current_character_id, -pc.level,
                            -pc.template.star_rating, pc.display_name),
        )
        options = [
            discord.SelectOption(
                label=names.fit_suffix(
                    pc.display_name, f"(Lv{pc.level}, {pc.template.star_rating}★)", 100),
                value=str(pc.id),
                default=(pc.id == current_character_id),
            )
            for pc in paging.window(ordered, 0)
        ]
        super().__init__(
            placeholder=paging.placeholder_for("Switch character", 0, len(ordered)),
            options=options, min_values=1, max_values=1,
        )
        self.page = page

    async def callback(self, interaction: discord.Interaction):
        await _render_profile_page(interaction, self.page, character_id=int(self.values[0]))


class ProfilePageView(OwnedView):
    def __init__(self, page: int, character_id: int | None = None, owned: list | None = None, owner_id: int | None = None):
        super().__init__(timeout=120, owner_id=owner_id)
        self.page = page
        self.character_id = character_id
        if owned and len(owned) > 1 and character_id is not None:
            self.add_item(CharacterProfileSelect(page, character_id, owned))
        self.prev_button.disabled = page <= 0
        self.next_button.disabled = page >= embedder.PROFILE_PAGE_COUNT - 1

    @discord.ui.button(label="◀ Prev", style=discord.ButtonStyle.secondary, row=1)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _render_profile_page(interaction, max(0, self.page - 1), character_id=self.character_id)

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary, row=1)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _render_profile_page(interaction, min(embedder.PROFILE_PAGE_COUNT - 1, self.page + 1), character_id=self.character_id)


async def _render_profile_page(interaction: discord.Interaction, page: int, character_id: int | None = None):
    db = SessionLocal()
    try:
        player = get_player(db, interaction.user.id)
        if player is None:
            await responses.send(interaction, "Use `/start` first.", ephemeral=True)
            return

        owned = character_service.list_owned_characters(db, player)
        character = next((pc for pc in owned if pc.id == character_id), None) if character_id else None
        if character is None:
            character = character_service.ensure_avatar_character(db, player)

        embed = embedder.profile_embed(
            player,
            character,
            equipped_items=inventory_service.list_equipped(db, character.id),
            avatar_url=interaction.user.display_avatar.url,
            page=page,
            db=db,
        )
        view = ProfilePageView(page, character_id=character.id, owned=owned, owner_id=player.id)
    finally:
        db.close()

    await responses.edit(interaction, embed=embed, view=view)


@guild_decorator
class Profile(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # COMMAND: /start
    # Creates a new player profile for the user, if one doesn't already exist.
    @app_commands.command(
        name="start",
        description="Begin your CascadeBot journey."
    )
    async def start(self, ctx: discord.Interaction):
        await responses.defer(ctx)
        db = SessionLocal()
        try:
            existing = get_player(db, ctx.user.id)
            if existing is not None:
                await responses.send(ctx,
                    f"You've already begun your journey, {existing.username}. "
                    "Use `/profile` to check your progress.",
                    ephemeral=True,
                )
                return

            get_or_create_player(db, ctx.user.id, ctx.user.display_name)
            player = get_player(db, ctx.user.id)
            character_service.ensure_avatar_character(db, player)
            story_service.get_or_create(db, player)
        finally:
            db.close()

        # /start NO LONGER HANDS OUT CURRENCY.
        #
        # It used to grant gold and shards and drop the player into a game
        # with ~30 commands and no basis for choosing between them. The
        # prologue does that job now, and does it better: it teaches
        # combat, hands you a weapon, gives you a squadmate and opens each
        # system at the point you have a reason to care about it. Handing
        # over a pile of currency the player can't yet spend on anything
        # was never the welcome it looked like.
        await responses.send(ctx,
            embed=discord.Embed(
                title=f"Welcome to the Cascade, {ctx.user.display_name}",
                description=(
                    "Somebody has been trying to reach you.\n\n"
                    "Use **`/story`** to answer."
                ),
                color=discord.Color.from_rgb(88, 101, 242),
            )
        )

    # COMMAND: /rename
    # Lets the player rename their own avatar character -- it shows up as
    # "You" everywhere (profile, squad, combat logs) until they set a
    # custom name. Runs with no argument to reset back to "You".
    @app_commands.command(
        name="rename",
        description="Rename your avatar character (leave blank to reset to \"You\")."
    )
    @app_commands.describe(name="Your new name (letters, numbers, spaces, ' - . -- max 32 characters)")
    async def rename(self, ctx: discord.Interaction, name: str | None = None):
        await responses.defer(ctx)
        db = SessionLocal()
        try:
            player = get_player(db, ctx.user.id)
            if not await require_player(ctx, player):
                return

            ok, message = character_service.rename_avatar(db, player, name)
        finally:
            db.close()

        await responses.send(ctx, message, ephemeral=not ok)

    # COMMAND: /class
    # Lets the player freely switch their own avatar between the 4 roles
    # (DPS, Support DPS, Amplifier, Sustain) -- see /encyclopedia's Classes
    # category for what each role's kit does. Locked during an active
    # expedition, same restriction /squad already applies to squad changes:
    # role should be settled before a run starts, not swapped mid-fight.
    @app_commands.command(
        name="class",
        description="Switch your avatar's role: DPS, Support DPS, Amplifier, or Sustain."
    )
    @app_commands.describe(role="The role to switch to")
    @app_commands.choices(role=[
        app_commands.Choice(name="DPS", value=CharacterClass.DPS.value),
        app_commands.Choice(name="Support DPS", value=CharacterClass.SUPPORT_DPS.value),
        app_commands.Choice(name="Amplifier", value=CharacterClass.AMPLIFIER.value),
        app_commands.Choice(name="Sustain", value=CharacterClass.SUSTAIN.value),
    ])
    async def class_(self, ctx: discord.Interaction, role: app_commands.Choice[str]):
        await responses.defer(ctx)
        db = SessionLocal()
        try:
            player = get_player(db, ctx.user.id)
            if not await require_player(ctx, player):
                return

            expedition = dungeon_service.get_active_expedition(db, player.id)
            if expedition is not None:
                await responses.send(ctx,
                    "You can't switch roles during an active run -- finish or abandon your expedition first.",
                    ephemeral=True,
                )
                return

            ok, message = character_service.set_avatar_class(db, player, CharacterClass(role.value))
            if ok:
                emoji = CLASS_EMOJI.get(CharacterClass(role.value), "")
                message = f"{emoji} {message}"
        finally:
            db.close()

        await responses.send(ctx, message, ephemeral=not ok)

    # COMMAND: /characters
    # The full per-character sheet: Overview, Equipment (every slot, empty
    # or filled) and Abilities, with a dropdown to switch character.
    #
    # This used to be /profile, and /characters was a flat one-line-per-
    # character list. That split was backwards -- the list couldn't tell
    # you anything about a character, and /profile could only ever show
    # you one. Now /characters is where characters live, and /profile is
    # the account (see below).
    @app_commands.command(
        name="characters",
        description="View any character you own: stats, equipment, and abilities."
    )
    async def characters(self, ctx: discord.Interaction):
        await responses.defer(ctx)
        db = SessionLocal()
        try:
            player = get_player(db, ctx.user.id)
            if not await require_player(ctx, player):
                return

            owned = character_service.list_owned_characters(db, player)
            character = character_service.ensure_avatar_character(db, player)
            embed = embedder.profile_embed(
                player,
                character,
                equipped_items=inventory_service.list_equipped(db, character.id),
                avatar_url=ctx.user.display_avatar.url,
                page=0,
                db=db,
            )
            view = ProfilePageView(0, character_id=character.id, owned=owned, owner_id=player.id)
        finally:
            db.close()

        await responses.send(ctx, embed=embed, view=view)

    # COMMAND: /profile
    # The ACCOUNT view -- account level, roster completion, power, and
    # currencies. Deliberately holds nothing that belongs to a single
    # character; that's what /characters is for.
    @app_commands.command(
        name="profile",
        description="Your account: level, roster, power and currencies."
    )
    async def profile(self, ctx: discord.Interaction):
        await responses.defer(ctx)
        db = SessionLocal()
        try:
            player = get_player(db, ctx.user.id)
            if not await require_player(ctx, player):
                return
            summary = account_service.account_summary(db, player)
            embed = embedder.account_profile_embed(
                player, summary, avatar_url=ctx.user.display_avatar.url
            )
        finally:
            db.close()

        await responses.send(ctx, embed=embed)

    # COMMAND: /gift
    # Sends another player a package of materials or gold. See
    # bot/services/gift_service.py for the caps and why they exist.
    @app_commands.command(
        name="gift",
        description="Send another player some materials or gold."
    )
    @app_commands.describe(
        player="Who to send it to.",
        currency="What to send.",
        amount="How much.",
        note="Optional short message.",
    )
    @app_commands.choices(currency=[
        app_commands.Choice(name=c.replace("_", " ").title(), value=c)
        for c in gift_service.GIFTABLE
    ])
    async def gift(self, ctx: discord.Interaction, player: discord.User,
                   currency: str, amount: int, note: str | None = None):
        await responses.defer(ctx)
        if player.bot:
            await responses.send(ctx, "Bots have no use for materials.", ephemeral=True)
            return
        db = SessionLocal()
        try:
            sender = get_player(db, ctx.user.id)
            if not await require_player(ctx, sender):
                return
            # SENDER, not `player` -- `player` is the discord.User being
            # gifted TO, so this gated the feature on the RECIPIENT.
            # A discord.User has no story row at all, which means the
            # check was relying entirely on require_feature's deliberate
            # fail-open to not explode: the gate was doing nothing, and
            # a player who hadn't unlocked gifting could still gift.
            if not await require_feature(ctx, db, sender, 'gifting'):
                return
            try:
                sent = gift_service.send_gift(db, sender, player.id, {currency: amount}, note)
            except gift_service.GiftError as exc:
                await responses.send(ctx, str(exc), ephemeral=True)
                return
            embed = embedder.gift_sent_embed(
                sent, player.mention, gift_service.sends_remaining(db, sender.id)
            )
        finally:
            db.close()

        await responses.send(ctx, embed=embed)

    # COMMAND: /gifts
    # The inbox. Shows what's waiting, then collects it all on a button.
    @app_commands.command(name="gifts", description="See and collect gifts other players sent you.")
    async def gifts(self, ctx: discord.Interaction):
        await responses.defer(ctx, ephemeral=True)
        db = SessionLocal()
        try:
            player = get_player(db, ctx.user.id)
            if not await require_player(ctx, player):
                return
            if not await require_feature(ctx, db, player, 'gifting'):
                return
            pending = gift_service.pending_for(db, player.id)
            embed = embedder.gift_inbox_embed(player, pending)
            view = GiftCollectView(owner_id=player.id) if pending else None
        finally:
            db.close()

        await responses.send(ctx, embed=embed, view=view, ephemeral=True)


class GiftCollectView(OwnedView):
    """One button, owner-locked, short-lived. Deliberately NOT persistent:
    collecting is idempotent-ish but a stale button from a week ago
    re-collecting a fresh gift the player hadn't read yet is a worse
    outcome than the button expiring."""

    def __init__(self, owner_id: int | None = None):
        super().__init__(timeout=300, owner_id=owner_id)

    @discord.ui.button(label="🎁 Collect all", style=discord.ButtonStyle.success)
    async def collect(self, interaction: discord.Interaction, button: discord.ui.Button):
        db = SessionLocal()
        try:
            player = get_player(db, interaction.user.id)
            if player is None:
                await responses.send(interaction, "Use `/start` first.", ephemeral=True)
                return
            try:
                result = gift_service.collect_all(db, player)
            except gift_service.GiftError as exc:
                await responses.edit(interaction, content=str(exc), embed=None, view=None)
                return
            embed = embedder.gift_collected_embed(result)
        finally:
            db.close()
        await responses.edit(interaction, embed=embed, view=None)


async def setup(bot):
    await bot.add_cog(Profile(bot))
