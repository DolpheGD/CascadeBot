"""
/squad -- view your roster and choose which characters ride along on
expeditions.

EVERY slot is free. Slot 0 used to be locked to your own avatar, which
meant a player who had pulled four characters they preferred was still
forced to field the avatar and effectively played with three slots. The
avatar is still granted free and still auto-seated the first time you
play (see character_service.ensure_avatar_character) -- it's a starter
character now, not a mandatory one, and it can be benched like anyone
else. The only rule left is that the squad can't be emptied completely.

One dropdown per slot, four selects on one message (Discord allows five
components, so this fits).
"""

import discord

from discord.ext import commands
from discord import app_commands

from bot.utils import names
from bot.database.models.enums import CLASS_DISPLAY_NAME
from bot.utils import responses
from bot.database.session import SessionLocal
from bot.services.player_service import get_player
from bot.services import character_service, dungeon_service, squad_service
from bot.utils.guild_decorator import guild_decorator
from bot.utils import paging
from bot.utils.ui_guard import require_feature, OwnedView, require_player

SLOT_LABELS = ["Slot 1", "Slot 2", "Slot 3", "Slot 4"]


def _character_label(pc) -> str:
    # effective_class(), NOT template.character_class -- the player's own
    # avatar can switch class freely (PlayerCharacter.current_class), and
    # reading the template here made "You" show as DPS forever no matter
    # what role was actually equipped. Pulled characters have
    # current_class NULL, so this falls back to the template for them.
    # star_label(), not template.star_rating -- an evolved character
    # must show the rank it paid for, and the "Evolved" tag has to read
    # identically here and on every other screen.
    stars = pc.star_label()
    class_label = CLASS_DISPLAY_NAME[pc.effective_class()]
    # fit_suffix, not a raw slice: the metadata is always appended, so a
    # plain [:100] would cut the CLASS off a long name -- or, for a
    # 32-character /rename, the name itself. Dropping the parenthetical
    # keeps the row identifiable, which is the whole job of a label.
    return names.fit_suffix(pc.display_name, f"{stars} Lv{pc.level} ({class_label})", 100)


def _build_squad_embed(db, player) -> discord.Embed:
    by_slot = character_service.get_squad_by_slot(db, player)
    embed = discord.Embed(title=f"{player.username}'s Squad", color=discord.Color.dark_gold())
    for i in range(4):
        pc = by_slot[i]
        value = _character_label(pc) if pc else "*Empty*"
        embed.add_field(name=SLOT_LABELS[i], value=value, inline=False)
    embed.set_footer(text="Bring up to 4 characters into every expedition. Any character can go in any slot.")
    return embed


class SquadSlotSelect(discord.ui.Select):
    """One per slot (0-3 -- every slot is changeable now that slot 0 is
    no longer reserved for the avatar). Fixed custom_id per slot so
    re-rendering doesn't collide; options rebuilt fresh every render from
    the player's current roster."""
    def __init__(self, slot_index: int, options: list[discord.SelectOption]):
        super().__init__(
            placeholder=f"Slot {slot_index + 1}: choose a character...",
            options=options, min_values=1, max_values=1,
            custom_id=f"cascade_squad_slot:{slot_index}",
        )
        self.slot_index = slot_index

    async def callback(self, interaction: discord.Interaction):
        db = SessionLocal()
        try:
            player = get_player(db, interaction.user.id)
            if player is None:
                await responses.send(interaction, "Use `/start` first.", ephemeral=True)
                return

            expedition = dungeon_service.get_active_expedition(db, player.id)
            if expedition is not None:
                await responses.send(interaction,
                    "You can't change your squad during an active run -- finish or abandon your expedition first.",
                    ephemeral=True,
                )
                return

            value = self.values[0]
            character = None
            if value != "empty":
                character = next(
                    (pc for pc in character_service.list_owned_characters(db, player) if pc.id == int(value)),
                    None,
                )
            ok, message = character_service.set_squad_slot(db, player, self.slot_index, character)

            embed = _build_squad_embed(db, player)
            view = _build_squad_view(db, player)
            await responses.edit(interaction, content=message if not ok else None, embed=embed, view=view)
        finally:
            db.close()


def _build_squad_view(db, player, page: int = 0) -> discord.ui.View:
    """All FOUR slots are editable and every owned character (avatar
    included) is offered for every one of them.

    Slot 0 used to be locked to the player's own avatar and excluded from
    the pickers entirely, so a player who had pulled four characters they
    preferred was still forced to field the avatar and effectively played
    with three slots. The avatar is still free and still auto-seated on
    first use -- it's a starter character now, not a mandatory one.

    Discord allows at most 5 components per message and a select counts
    as one, so four selects fit with one row spare -- which is exactly
    where the paging arrows go.

    PAGED, not sliced. Each select can hold 25 options and one of those
    is "Empty", so 24 characters fit; the roster is 31 and grows. The
    previous `options[:25]` meant a player who owned more than that
    simply COULD NOT FIELD their last few characters, with nothing on
    screen to say why. All four slots page together, so the four menus
    always show the same window and "next" means one thing."""
    owned = character_service.list_owned_characters(db, player)
    by_slot = character_service.get_squad_by_slot(db, player)
    view = SquadView(db, player, owned, by_slot, page=page)
    return view


class SquadView(OwnedView):
    """The four slot pickers plus their shared paging."""

    # One option in every select is "Empty", so a page of characters is
    # one short of Discord's ceiling.
    PER_PAGE = paging.SELECT_OPTION_LIMIT - 1

    def __init__(self, db, player, owned: list, by_slot: dict, page: int = 0):
        super().__init__(timeout=180, owner_id=player.id)
        self.page = max(0, min(page, paging.page_count(len(owned), self.PER_PAGE) - 1))
        self._owned_total = len(owned)

        shown = paging.window(owned, self.page, self.PER_PAGE)
        for slot_index in range(4):
            current = by_slot[slot_index]
            options = [discord.SelectOption(label="Empty", value="empty",
                                            default=current is None)]
            for pc in shown:
                options.append(discord.SelectOption(
                    label=_character_label(pc), value=str(pc.id),
                    default=(current is not None and current.id == pc.id),
                ))
            view_select = SquadSlotSelect(slot_index, options)
            view_select.placeholder = paging.placeholder_for(
                f"Slot {slot_index + 1}", self.page, len(owned), self.PER_PAGE)
            self.add_item(view_select)

        paging.add_page_buttons(self, self.page, len(owned), self.PER_PAGE, row=4)

    async def rerender(self, interaction: discord.Interaction, page: int) -> None:
        db = SessionLocal()
        try:
            player = get_player(db, interaction.user.id)
            if player is None:
                await responses.send(interaction, "Use `/start` first.", ephemeral=True)
                return
            embed = _build_squad_embed(db, player)
            view = _build_squad_view(db, player, page=page)
        finally:
            db.close()
        await responses.edit(interaction, embed=embed, view=view)



# ----------------------------------------------------------------------
# SQUAD PRESETS
#
# Their own screen rather than controls bolted onto /squad, for a boring
# reason: SquadView already uses all five of Discord's action rows (four
# slot selects plus paging). There is no room, and squeezing presets in
# would have meant dropping paging -- which breaks the roster browser for
# anyone with more than 24 characters.
# ----------------------------------------------------------------------

def _presets_embed(db, player) -> discord.Embed:
    presets = squad_service.list_presets(db, player)
    current = ", ".join(
        (c.custom_name or c.template.name)
        for c in character_service.get_squad(db, player)
    ) or "*empty*"

    embed = discord.Embed(
        title="🗂️ Squad Presets",
        description=(f"**Right now:** {current}\n\n"
                     f"Save the lineup you're running, then swap back to it "
                     f"later without rebuilding it slot by slot."),
        colour=discord.Colour.blurple(),
    )
    if presets:
        embed.add_field(
            name=f"Saved ({len(presets)}/{squad_service.MAX_PRESETS})",
            value="\n".join(
                f"**{p.name}** — {squad_service.describe(db, player, p)}"
                for p in presets),
            inline=False,
        )
    else:
        embed.add_field(name="Saved (0)",
                        value="*Nothing saved yet.*", inline=False)
    return embed


class PresetsView(OwnedView):
    def __init__(self, db, player, owner_id: int | None = None):
        super().__init__(timeout=300, owner_id=owner_id)
        presets = squad_service.list_presets(db, player)
        if presets:
            self.add_item(_PresetLoadSelect(db, player, presets))
            self.add_item(_PresetDeleteSelect(presets))
        self.add_item(_PresetSaveButton())


class _PresetLoadSelect(discord.ui.Select):
    def __init__(self, db, player, presets):
        # NO `default=` on any option. Discord treats an already-selected
        # option as needing no interaction, so re-picking it dispatches
        # nothing and the control looks dead -- the bug that made raid
        # "Standard" unfightable.
        super().__init__(
            placeholder="Load a preset…",
            options=[
                discord.SelectOption(
                    label=p.name[:100],
                    value=str(p.id),
                    description=squad_service.describe(db, player, p)[:100],
                )
                for p in presets[:25]
            ],
        )

    async def callback(self, interaction: discord.Interaction):
        db = SessionLocal()
        try:
            player = get_player(db, interaction.user.id)
            try:
                preset, warnings = squad_service.load_preset(
                    db, player, int(self.values[0]))
            except squad_service.SquadPresetError as exc:
                await responses.send(interaction, str(exc), ephemeral=True)
                return
            embed = _presets_embed(db, player)
            note = f"Loaded **{preset.name}**."
            if warnings:
                note += " " + "; ".join(warnings) + "."
            embed.set_footer(text=note)
            view = PresetsView(db, player, owner_id=player.id)
        finally:
            db.close()
        await responses.edit(interaction, embed=embed, view=view)


class _PresetDeleteSelect(discord.ui.Select):
    def __init__(self, presets):
        super().__init__(
            placeholder="Delete a preset…",
            options=[discord.SelectOption(label=p.name[:100], value=str(p.id))
                     for p in presets[:25]],
        )

    async def callback(self, interaction: discord.Interaction):
        db = SessionLocal()
        try:
            player = get_player(db, interaction.user.id)
            try:
                name = squad_service.delete_preset(db, player, int(self.values[0]))
            except squad_service.SquadPresetError as exc:
                await responses.send(interaction, str(exc), ephemeral=True)
                return
            embed = _presets_embed(db, player)
            embed.set_footer(text=f"Deleted {name}.")
            view = PresetsView(db, player, owner_id=player.id)
        finally:
            db.close()
        await responses.edit(interaction, embed=embed, view=view)


class _PresetSaveButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="💾 Save current squad",
                         style=discord.ButtonStyle.primary)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(_PresetNameModal())


class _PresetNameModal(discord.ui.Modal, title="Save this squad"):
    name = discord.ui.TextInput(label="Preset name", max_length=32,
                                placeholder="e.g. Boss killers")

    async def on_submit(self, interaction: discord.Interaction):
        db = SessionLocal()
        try:
            player = get_player(db, interaction.user.id)
            try:
                preset = squad_service.save_preset(db, player, str(self.name))
            except squad_service.SquadPresetError as exc:
                await responses.send(interaction, str(exc), ephemeral=True)
                return
            embed = _presets_embed(db, player)
            embed.set_footer(text=f"Saved {preset.name}.")
            view = PresetsView(db, player, owner_id=player.id)
        finally:
            db.close()
        await responses.edit(interaction, embed=embed, view=view)


@guild_decorator
class Squad(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # COMMAND: /presets
    # Save and swap named squad lineups.
    @app_commands.command(
        name="presets",
        description="Save named squad lineups and swap between them."
    )
    async def presets(self, ctx: discord.Interaction):
        await responses.defer(ctx)
        db = SessionLocal()
        try:
            player = get_player(db, ctx.user.id)
            if not await require_player(ctx, player):
                return
            if not await require_feature(ctx, db, player, "squad"):
                return
            embed = _presets_embed(db, player)
            view = PresetsView(db, player, owner_id=player.id)
        finally:
            db.close()
        await responses.send(ctx, embed=embed, view=view)

    # COMMAND: /squad
    # View your 4-character active squad and reassign any slot from your
    # owned roster.
    @app_commands.command(name="squad", description="View and manage your 4-character active squad.")
    async def squad(self, ctx: discord.Interaction):
        await responses.defer(ctx)
        db = SessionLocal()
        try:
            player = get_player(db, ctx.user.id)
            if not await require_player(ctx, player):
                return
            if not await require_feature(ctx, db, player, "squad"):
                return

            embed = _build_squad_embed(db, player)
            view = _build_squad_view(db, player)
        finally:
            db.close()

        await responses.send(ctx, embed=embed, view=view)

    # NOTE: /characters used to live here as a flat list of names and
    # levels. It's now the full per-character sheet in bot/cogs/profile.py
    # -- a list that can't tell you a character's stats isn't what anyone
    # opens /characters to find out.


async def setup(bot):
    await bot.add_cog(Squad(bot))
