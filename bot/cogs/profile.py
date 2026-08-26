import discord

from discord.ext import commands
from discord import app_commands

from bot.utils import names, paging
from bot.database.models.enums import CLASS_EMOJI, CharacterClass
from bot.utils import responses
from bot.database.session import SessionLocal
from bot.services.player_service import get_or_create_player, get_player
from bot.services.currency_service import add_currency
from bot.game.characters import talent_config
from bot.services import talent_service
from bot.services import (account_service, away_service, character_service, dungeon_service,
                          evolution_service, gift_service, inventory_service,
                          story_service)
from bot.services.currency_service import format_currency
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
                            -pc.effective_star, pc.display_name),
        )
        options = [
            discord.SelectOption(
                label=names.fit_suffix(
                    pc.display_name,
                    f"(Lv{pc.level}, {pc.star_label()})", 100),
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



# ----------------------------------------------------------------------
# TALENTS
#
# One screen per character. The rules (points, prerequisites, respec) all
# live in talent_service; this only draws them, for the same reason
# puzzles.solve lives outside the story cog -- a rule enforced in a view
# is a rule nothing can test.
# ----------------------------------------------------------------------

def _owned_character(db, player, character_id: int):
    """The player's character with this id, or None.

    Goes through list_owned_characters rather than a bare primary-key
    lookup: the id arrives from a component custom_id, which is client
    supplied, so fetching by id alone would let anyone edit anyone's
    talents by replaying a button. The ownership filter IS the check.
    """
    return next((c for c in character_service.list_owned_characters(db, player)
                 if c.id == character_id), None)


def talent_embed(character) -> discord.Embed:
    state = talent_service.summary(character)
    name = character.custom_name or character.template.name
    embed = discord.Embed(
        title=f"🌳 {name} — Talents",
        description=(
            f"**{state['available']}** point"
            f"{'s' if state['available'] != 1 else ''} to spend"
            f"  ·  {state['spent']}/{state['total']} used\n"
            f"*One point every {talent_config.POINTS_PER_LEVEL} levels. "
            f"Resetting is free.*"
        ),
        colour=discord.Colour.green(),
    )
    for branch_name, nodes in state["branches"].items():
        lines = []
        for node in nodes:
            mark = "✅" if node["bought"] else ("🔹" if node["buyable"] else "🔒")
            effect = node["effect"]
            amount = (f"+{effect['percent']:g}% {effect['stat'].replace('_', ' ')}"
                      if "percent" in effect
                      else f"+{effect['flat']:g} {effect['stat'].replace('_', ' ')}")
            star = " ★" if node.get("capstone") else ""
            lines.append(f"{mark} **{node['name']}**{star} — {amount} "
                         f"({node['cost']}pt)")
        embed.add_field(name=branch_name, value="\n".join(lines), inline=False)

    if state["percent"] or state["flat"]:
        parts = [f"+{v:g}% {k.replace('_', ' ')}" for k, v in state["percent"].items()]
        parts += [f"+{v:g} {k.replace('_', ' ')}" for k, v in state["flat"].items()]
        embed.add_field(name="Currently worth", value=", ".join(parts), inline=False)
    return embed


def evolve_embed(character) -> discord.Embed:
    """One character's evolution state, and exactly what the next step costs."""
    requirement = evolution_service.requirements(character)
    native = evolution_service.native_star(character)

    embed = discord.Embed(
        title=f"✨ {character.display_name} — Evolution",
        description=(
            f"**{character.star_label()}**  ·  Lv.{character.level}\n"
            f"*Originally {'★' * native}*"
        ),
        colour=discord.Colour.purple(),
    )

    if requirement is None:
        embed.add_field(
            name="Fully evolved",
            value=("This character has gone as far as evolution goes.\n"
                   "*A native 5★ is still stronger — evolution closes about "
                   "a third of that gap, not all of it.*"),
            inline=False)
        return embed

    allowed, reason = evolution_service.can_evolve(character)
    cost_lines = []
    for currency, amount in requirement["cost"].items():
        have = requirement["have"][currency]
        tick = "✅" if have >= amount else "❌"
        cost_lines.append(
            f"{tick} {format_currency(currency, amount)}  *(you have {have:,})*")

    level_tick = "✅" if requirement["level_met"] else "❌"
    embed.add_field(
        name=f"To reach {'★' * requirement['target_star']}",
        value=(f"{level_tick} Level {requirement['level_required']}"
               f"  *(currently {character.level})*\n" + "\n".join(cost_lines)),
        inline=False)

    if not allowed:
        embed.add_field(name="Not yet", value=reason, inline=False)

    # The honest pitch. Saying "+6% to every growing stat" is a smaller
    # number than a player expects from the word EVOLUTION, and telling
    # them up front is better than letting them spend 500 echoes and work
    # it out afterwards.
    embed.set_footer(
        text="Each evolution adds +6% to stats that grow with level. "
             "A native 5★ stays stronger.")
    return embed


class EvolveView(OwnedView):
    def __init__(self, character, owner_id: int | None = None,
                 roster: list | None = None):
        super().__init__(timeout=600, owner_id=owner_id)
        if roster:
            self.add_item(_EvolveCharacterSelect(roster, character.id))
        allowed, _ = evolution_service.can_evolve(character)
        if allowed:
            self.add_item(_EvolveButton(character.id))


class _EvolveCharacterSelect(discord.ui.Select):
    def __init__(self, roster: list, current_id: int):
        super().__init__(
            placeholder="Pick a character…",
            options=[
                discord.SelectOption(
                    label=names.fit_suffix(
                        pc.display_name, f"(Lv{pc.level}, {pc.star_label()})", 100),
                    value=str(pc.id),
                    default=(pc.id == current_id),
                )
                # Sliced to Discord's 25-option cap. A roster can exceed
                # it, and an over-long select fails with a 400 that shows
                # up only as a dead interaction.
                for pc in roster[:25]
            ],
        )

    async def callback(self, interaction: discord.Interaction):
        db = SessionLocal()
        try:
            player = get_player(db, interaction.user.id)
            if player is None:
                await responses.send(interaction, "Use `/start` first.", ephemeral=True)
                return
            roster = evolution_service.evolvable_characters(db, player)
            character = next((c for c in roster if c.id == int(self.values[0])), None)
            if character is None:
                await responses.send(interaction, "You don't own that character.",
                                     ephemeral=True)
                return
            await responses.edit(
                interaction,
                embed=evolve_embed(character),
                view=EvolveView(character, owner_id=player.id, roster=roster))
        finally:
            db.close()


class _EvolveButton(discord.ui.Button):
    def __init__(self, character_id: int):
        super().__init__(label="Evolve", emoji="✨",
                         style=discord.ButtonStyle.success)
        self.character_id = character_id

    async def callback(self, interaction: discord.Interaction):
        db = SessionLocal()
        try:
            player = get_player(db, interaction.user.id)
            if player is None:
                await responses.send(interaction, "Use `/start` first.", ephemeral=True)
                return
            character = next(
                (c for c in character_service.list_owned_characters(db, player)
                 if c.id == self.character_id), None)
            if character is None:
                await responses.send(interaction, "You don't own that character.",
                                     ephemeral=True)
                return
            try:
                result = evolution_service.evolve(db, player, character)
            except evolution_service.EvolutionError as exc:
                # Reached by pressing a button rendered before the player
                # spent the materials somewhere else. The service is the
                # real guard; this only says so out loud.
                await responses.send(interaction, str(exc), ephemeral=True)
                return

            done = discord.Embed(
                title="✨ Evolved",
                description=(
                    f"**{character.display_name}** is now "
                    f"**{character.star_label()}**\n"
                    f"{'★' * result['from_star']} → {'★' * result['to_star']}  ·  "
                    f"+{result['percent']:.1f}% to stats that grow with level"),
                colour=discord.Colour.gold(),
            )
            done.add_field(
                name="Spent",
                value=", ".join(format_currency(c, a)
                                for c, a in result["spent"].items()),
                inline=False)

            roster = evolution_service.evolvable_characters(db, player)
            await responses.edit(
                interaction,
                embed=evolve_embed(character),
                view=EvolveView(character, owner_id=player.id, roster=roster))
            await interaction.followup.send(embed=done)
        finally:
            db.close()


class TalentView(OwnedView):
    def __init__(self, character, owner_id: int | None = None):
        super().__init__(timeout=600, owner_id=owner_id)
        self.character_id = character.id
        state = talent_service.summary(character)
        buyable = [n for nodes in state["branches"].values() for n in nodes
                   if n["buyable"]]
        if buyable:
            self.add_item(_TalentBuySelect(buyable))
        self.add_item(_TalentResetButton())


class _TalentBuySelect(discord.ui.Select):
    def __init__(self, buyable: list[dict]):
        # Sliced to Discord's hard cap. There are 13 nodes in a tree and
        # at most a handful are ever buyable at once, so this will not
        # trigger -- it is here because an unpaged select is what took
        # the equip button down with a 400 that never surfaced as an
        # error, only as a dead interaction.
        super().__init__(
            placeholder="Learn a talent…",
            options=[
                discord.SelectOption(
                    label=f"{n['name']} ({n['cost']}pt)"[:100],
                    value=n["id"],
                    description=(f"{n['branch_name']} · "
                                 + (f"+{n['effect']['percent']:g}% "
                                    if 'percent' in n['effect']
                                    else f"+{n['effect']['flat']:g} ")
                                 + n['effect']['stat'].replace('_', ' '))[:100],
                )
                for n in buyable[:25]
            ],
        )

    async def callback(self, interaction: discord.Interaction):
        db = SessionLocal()
        try:
            player = get_player(db, interaction.user.id)
            character = _owned_character(db, player, self.view.character_id)
            if character is None:
                await responses.send(interaction, "That isn't your character.",
                                     ephemeral=True)
                return
            try:
                node = talent_service.buy(db, character, self.values[0])
            except talent_service.TalentError as exc:
                await responses.send(interaction, str(exc), ephemeral=True)
                return
            embed = talent_embed(character)
            embed.set_footer(text=f"Learned {node['name']}.")
            view = TalentView(character, owner_id=player.id)
        finally:
            db.close()
        await responses.edit(interaction, embed=embed, view=view)


class _TalentResetButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="↺ Unlearn everything",
                         style=discord.ButtonStyle.secondary)

    async def callback(self, interaction: discord.Interaction):
        db = SessionLocal()
        try:
            player = get_player(db, interaction.user.id)
            character = _owned_character(db, player, self.view.character_id)
            if character is None:
                await responses.send(interaction, "That isn't your character.",
                                     ephemeral=True)
                return
            refunded = talent_service.reset(db, character)
            embed = talent_embed(character)
            embed.set_footer(text=f"{refunded} point"
                                  f"{'s' if refunded != 1 else ''} back. "
                                  f"Respec is always free.")
            view = TalentView(character, owner_id=player.id)
        finally:
            db.close()
        await responses.edit(interaction, embed=embed, view=view)


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

    # COMMAND: /talents
    # The talent tree for one character. Defaults to the avatar; the
    # select on /characters is the other way in.
    @app_commands.command(
        name="talents",
        description="Spend talent points on a character. Respec is free."
    )
    async def talents(self, ctx: discord.Interaction):
        await responses.defer(ctx)
        db = SessionLocal()
        try:
            player = get_player(db, ctx.user.id)
            if not await require_player(ctx, player):
                return
            # Gated on `squad`, the feature that first asks the player to
            # care about individual characters. Talents before that is a
            # screen full of choices about a roster of one.
            if not await require_feature(ctx, db, player, "squad"):
                return
            character = character_service.ensure_avatar_character(db, player)
            embed = talent_embed(character)
            view = TalentView(character, owner_id=player.id)
        finally:
            db.close()
        await responses.send(ctx, embed=embed, view=view)

    # COMMAND: /achievements
    # What you've done, what you're missing, and what title you wear for
    # it. Screens live in bot/cogs/_achievement_ui.py; every number comes
    # from achievement_service.metrics, which derives from existing state
    # rather than from counters sprinkled through gameplay.
    @app_commands.command(
        name="achievements",
        description="What you've earned, your collection, and your titles.")
    async def achievements(self, ctx: discord.Interaction):
        await responses.defer(ctx)
        from bot.cogs import _achievement_ui
        from bot.services import achievement_service

        db = SessionLocal()
        try:
            player = get_player(db, ctx.user.id)
            if not await require_player(ctx, player):
                return
            # SYNC HERE, on the screen that displays them. Achievements
            # are derived, so this only records receipts and detects
            # what is new -- it is not what makes them earned.
            fresh = achievement_service.sync(db, player)
            embed = _achievement_ui.achievements_embed(db, player)
            view = _achievement_ui.AchievementView(db, player)
        finally:
            db.close()
        await responses.send(ctx, embed=embed, view=view)
        if fresh:
            unlocked = [a for a in fresh if a.title]
            note = "🏆 **Newly earned:** " + ", ".join(a.name for a in fresh[:6])
            if unlocked:
                note += ("\nNew title" + ("s" if len(unlocked) > 1 else "") + ": "
                         + ", ".join(f"**{a.title}**" for a in unlocked))
            await ctx.followup.send(note, ephemeral=True)

    # COMMAND: /notifications
    # Opt in or out of reminder DMs. Off by default -- see
    # bot/services/reminder_service.py for why that is not negotiable.
    @app_commands.command(
        name="notifications",
        description="Turn reminder DMs on or off. Off by default."
    )
    @app_commands.describe(enabled="On sends at most one DM a day. Off sends nothing.")
    async def notifications(self, ctx: discord.Interaction, enabled: bool):
        await responses.defer(ctx, ephemeral=True)
        db = SessionLocal()
        try:
            player = get_player(db, ctx.user.id)
            if not await require_player(ctx, player):
                return
            player.reminders_enabled = bool(enabled)
            # Turning them back on clears the failure counter -- the
            # player is explicitly telling us their DMs work now, and
            # without this a single blocked spell would be permanent.
            if enabled:
                player.reminder_failures = 0
            db.commit()

            if enabled:
                text = (
                    "🔔 **Reminders on.**\n\n"
                    "At most one DM a day, and only when something is actually "
                    "going to waste — full harvesters, capped energy, or a "
                    "challenge cycle about to expire. Nothing otherwise.\n\n"
                    "If your DMs are closed I'll stop trying rather than "
                    "retrying every night."
                )
            else:
                text = ("🔕 **Reminders off.** You'll still see a summary of what "
                        "you missed next time you play.")
        finally:
            db.close()
        await responses.send(ctx, text, ephemeral=True)

    # COMMAND: /evolve
    # Raise a 3★ or 4★ up the star ladder. See
    # bot/game/economy/character_evolution_config.py for why the bonuses
    # are as small as they are.
    @app_commands.command(
        name="evolve",
        description="Evolve a 3★ or 4★ character up the star ladder."
    )
    async def evolve(self, ctx: discord.Interaction):
        await responses.defer(ctx)
        db = SessionLocal()
        try:
            player = get_player(db, ctx.user.id)
            if not await require_player(ctx, player):
                return
            # Gated on `squad`, matching /talents: both are screens about
            # investing in one character, and neither means anything to a
            # player who still has a roster of one.
            if not await require_feature(ctx, db, player, "squad"):
                return
            roster = evolution_service.evolvable_characters(db, player)
            if not roster:
                embed = discord.Embed(
                    title="✨ Evolution",
                    description=(
                        "You don't have any characters that can evolve yet.\n\n"
                        "Only pulled 3★ and 4★ characters can — your avatar is "
                        "already 5★, and a native 5★ has nowhere to go."),
                    colour=discord.Colour.purple(),
                )
                view = None
            else:
                embed = evolve_embed(roster[0])
                view = EvolveView(roster[0], owner_id=player.id, roster=roster)
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
            # WHILE YOU WERE AWAY, on the screen a returning player opens
            # first. Rendered as a field on the existing embed rather than
            # a second message, so it cannot be missed and cannot be
            # dismissed before it is read.
            away = away_service.summarise(db, player)
            if away:
                embed.add_field(
                    name=f"⏳ While you were away ({away['away_text']})",
                    value="\n".join(away["lines"])[:1024],
                    inline=False)
                away_service.mark_shown(db, player)
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
