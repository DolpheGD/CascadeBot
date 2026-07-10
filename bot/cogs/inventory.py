import discord

from discord.ext import commands
from discord import app_commands

from bot.database.session import SessionLocal
from bot.services.player_service import get_player
from bot.services import character_service, dungeon_service, inventory_service, item_upgrade_service, lootbox_service
from bot.database.models.enums import ItemType
from bot.utils import embedder
from bot.utils.guild_decorator import guild_decorator


# ----------------------------------------------------------------------
# Two browsing modes over one unified list of items + lootboxes
# (bot.services.inventory_service.list_combined_entries):
#
#   LIST mode   -- compact, many-per-page, for skimming a big inventory.
#                  A Select lets you jump straight into Detail mode for
#                  any entry on the current page.
#   DETAIL mode -- one entry at a time, full stats/ability text, with
#                  Equip/Unequip/Level Up/Reroll (items) or Open All
#                  (lootboxes).
#
# A "🔍 Jump to #" button (either mode) opens a modal so you can type an
# exact entry number and land on its Detail page directly, without paging
# through everything in between.
#
# Every button is a DynamicItem carrying whatever it needs (direction +
# entry id, or a page number) in its custom_id, exactly like the original
# nav/equip buttons -- see bot/cogs/dungeon.py for why that's what makes
# these survive a bot restart.
# ----------------------------------------------------------------------

def _in_combat_guard(db, player) -> str | None:
    expedition = dungeon_service.get_active_expedition(db, player.id)
    if dungeon_service.is_in_combat(expedition):
        return "You can't manage your inventory mid-battle -- finish the fight first!"
    return None


# ------------------------------------------------------------------
# Detail mode components
# ------------------------------------------------------------------

class EntryNavButton(discord.ui.DynamicItem[discord.ui.Button], template=r"cascade_entry_nav:(?P<direction>prev|next):(?P<entry_id>.+)"):
    def __init__(self, direction: str, entry_id: str, disabled: bool = False):
        label = "◀ Prev" if direction == "prev" else "Next ▶"
        super().__init__(discord.ui.Button(
            label=label, style=discord.ButtonStyle.secondary,
            custom_id=f"cascade_entry_nav:{direction}:{entry_id}", disabled=disabled,
        ))
        self.direction = direction
        self.entry_id = entry_id

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(match["direction"], match["entry_id"])

    async def callback(self, interaction: discord.Interaction):
        await _handle_nav(interaction, self.entry_id, self.direction)


class ToListButton(discord.ui.DynamicItem[discord.ui.Button], template=r"cascade_to_list:(?P<entry_id>.+)"):
    def __init__(self, entry_id: str):
        super().__init__(discord.ui.Button(
            label="📋 List View", style=discord.ButtonStyle.secondary,
            custom_id=f"cascade_to_list:{entry_id}",
        ))
        self.entry_id = entry_id

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(match["entry_id"])

    async def callback(self, interaction: discord.Interaction):
        db = SessionLocal()
        try:
            player = get_player(db, interaction.user.id)
            if player is None:
                await interaction.response.send_message("Use `/start` first.", ephemeral=True)
                return
            idx, _total = inventory_service.entry_index_and_total(db, player.id, self.entry_id)
            page = idx // embedder.ITEMS_PER_LIST_PAGE
            embed, view = await _render_list_page(db, player, page)
        finally:
            db.close()
        await interaction.response.edit_message(content=None, embed=embed, view=view)


class EquipTargetSelect(discord.ui.Select):
    """Short-lived (not a DynamicItem -- doesn't need to survive a bot
    restart) picker shown when the player has more than just their avatar
    in their squad, so equipping doesn't silently always target the avatar."""
    def __init__(self, item_id: int, options: list[discord.SelectOption]):
        super().__init__(
            placeholder="Choose which character to equip onto...",
            options=options, min_values=1, max_values=1,
        )
        self.item_id = item_id

    async def callback(self, interaction: discord.Interaction):
        db = SessionLocal()
        try:
            player = get_player(db, interaction.user.id)
            if player is None:
                await interaction.response.send_message("Use `/start` first.", ephemeral=True)
                return

            item = inventory_service.get_item(db, self.item_id, player.id)
            if item is None:
                await interaction.response.send_message("Item not found.", ephemeral=True)
                return

            if self.values[0] == "cancel":
                embed, view = await _render_detail_page(db, player, f"item:{item.id}")
                await interaction.response.edit_message(content=None, embed=embed, view=view)
                return

            character = next(
                (pc for pc in character_service.get_squad(db, player) if pc.id == int(self.values[0])),
                None,
            )
            if character is None:
                await interaction.response.send_message("That character isn't in your squad anymore.", ephemeral=True)
                return

            ok, message = inventory_service.equip_item(db, character, item)
            embed, view = await _render_detail_page(db, player, f"item:{item.id}")
            await interaction.response.edit_message(content=message, embed=embed, view=view)
        finally:
            db.close()


class EquipTargetView(discord.ui.View):
    def __init__(self, item_id: int, options: list[discord.SelectOption]):
        super().__init__(timeout=120)
        self.add_item(EquipTargetSelect(item_id, options))


class EntryEquipToggleButton(discord.ui.DynamicItem[discord.ui.Button], template=r"cascade_entry_equip:(?P<item_id>\d+)"):
    def __init__(self, item_id: int, label: str = "Equip", style: discord.ButtonStyle = discord.ButtonStyle.success):
        super().__init__(discord.ui.Button(
            label=label, style=style, custom_id=f"cascade_entry_equip:{item_id}",
        ))
        self.item_id = item_id

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(int(match["item_id"]))

    async def callback(self, interaction: discord.Interaction):
        await _handle_equip_toggle(interaction, self.item_id)


class EntryLevelUpButton(discord.ui.DynamicItem[discord.ui.Button], template=r"cascade_entry_levelup:(?P<item_id>\d+)"):
    def __init__(self, item_id: int, label: str = "⬆️ Level Up"):
        super().__init__(discord.ui.Button(
            label=label, style=discord.ButtonStyle.primary, custom_id=f"cascade_entry_levelup:{item_id}",
        ))
        self.item_id = item_id

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(int(match["item_id"]))

    async def callback(self, interaction: discord.Interaction):
        await _handle_level_up(interaction, self.item_id)


class EntryRerollButton(discord.ui.DynamicItem[discord.ui.Button], template=r"cascade_entry_reroll:(?P<item_id>\d+)"):
    def __init__(self, item_id: int, label: str = "🎲 Reroll Substats"):
        super().__init__(discord.ui.Button(
            label=label, style=discord.ButtonStyle.primary, custom_id=f"cascade_entry_reroll:{item_id}",
        ))
        self.item_id = item_id

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(int(match["item_id"]))

    async def callback(self, interaction: discord.Interaction):
        await _handle_reroll(interaction, self.item_id)


class EntrySellButton(discord.ui.DynamicItem[discord.ui.Button], template=r"cascade_entry_sell:(?P<item_id>\d+)"):
    def __init__(self, item_id: int, label: str = "💰 Sell"):
        super().__init__(discord.ui.Button(
            label=label, style=discord.ButtonStyle.danger, custom_id=f"cascade_entry_sell:{item_id}",
        ))
        self.item_id = item_id

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(int(match["item_id"]))

    async def callback(self, interaction: discord.Interaction):
        await _handle_sell(interaction, self.item_id)


class EntryOpenLootboxButton(discord.ui.DynamicItem[discord.ui.Button], template=r"cascade_entry_open:(?P<tier>[a-z]+)"):
    def __init__(self, tier: str):
        super().__init__(discord.ui.Button(
            label=f"📦 Open All {tier.title()}", style=discord.ButtonStyle.success,
            custom_id=f"cascade_entry_open:{tier}",
        ))
        self.tier = tier

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(match["tier"])

    async def callback(self, interaction: discord.Interaction):
        await _handle_open_lootbox(interaction, self.tier)


class JumpModal(discord.ui.Modal, title="Jump to Item #"):
    entry_number = discord.ui.TextInput(
        label="Entry number (see the List view)", placeholder="e.g. 7", max_length=5,
    )

    async def on_submit(self, interaction: discord.Interaction):
        db = SessionLocal()
        try:
            player = get_player(db, interaction.user.id)
            if player is None:
                await interaction.response.send_message("Use `/start` first.", ephemeral=True)
                return

            entries = inventory_service.list_combined_entries(db, player.id)
            try:
                number = int(str(self.entry_number.value).strip())
            except ValueError:
                await interaction.response.send_message("That's not a number.", ephemeral=True)
                return

            if not entries or not (1 <= number <= len(entries)):
                await interaction.response.send_message(
                    f"Enter a number between 1 and {len(entries)}.", ephemeral=True
                )
                return

            entry = entries[number - 1]
            embed, view = await _render_detail_page(db, player, entry.entry_id)
        finally:
            db.close()

        await interaction.response.edit_message(content=None, embed=embed, view=view)


class JumpButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="🔍 Jump to #", style=discord.ButtonStyle.secondary, custom_id="cascade_inv_jump")

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(JumpModal())


class EntryDetailView(discord.ui.View):
    def __init__(self, buttons: list[discord.ui.Item]):
        super().__init__(timeout=None)
        for b in buttons:
            self.add_item(b)


# ------------------------------------------------------------------
# List mode components
# ------------------------------------------------------------------

class InventorySelectEntry(discord.ui.Select):
    """Fixed custom_id, options rebuilt per-render -- same persistence
    trick as MoveSelect/AbilitySelect in bot/cogs/dungeon.py: Discord
    delivers whatever the user actually picked on THIS message regardless
    of what a freshly-registered dummy view's default options were."""
    def __init__(self, options: list[discord.SelectOption] | None = None):
        options = options or [discord.SelectOption(label="(nothing on this page)", value="none")]
        super().__init__(
            placeholder="View an entry in detail...", options=options,
            custom_id="cascade_inv_select_entry", min_values=1, max_values=1,
        )

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            await interaction.response.defer()
            return
        db = SessionLocal()
        try:
            player = get_player(db, interaction.user.id)
            if player is None:
                await interaction.response.send_message("Use `/start` first.", ephemeral=True)
                return
            embed, view = await _render_detail_page(db, player, self.values[0])
        finally:
            db.close()
        await interaction.response.edit_message(content=None, embed=embed, view=view)


class ListPageButton(discord.ui.DynamicItem[discord.ui.Button], template=r"cascade_list_page:(?P<direction>prev|next):(?P<page>\d+)"):
    def __init__(self, direction: str, page: int, disabled: bool = False):
        label = "◀ Prev Page" if direction == "prev" else "Next Page ▶"
        super().__init__(discord.ui.Button(
            label=label, style=discord.ButtonStyle.secondary,
            custom_id=f"cascade_list_page:{direction}:{page}", disabled=disabled,
        ))
        self.direction = direction
        self.page = page

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(match["direction"], int(match["page"]))

    async def callback(self, interaction: discord.Interaction):
        db = SessionLocal()
        try:
            player = get_player(db, interaction.user.id)
            if player is None:
                await interaction.response.send_message("Use `/start` first.", ephemeral=True)
                return
            target_page = self.page - 1 if self.direction == "prev" else self.page + 1
            embed, view = await _render_list_page(db, player, target_page)
        finally:
            db.close()
        await interaction.response.edit_message(content=None, embed=embed, view=view)


class InventoryListView(discord.ui.View):
    def __init__(self, select: InventorySelectEntry, page_buttons: list[discord.ui.Item]):
        super().__init__(timeout=None)
        self.add_item(select)
        for b in page_buttons:
            self.add_item(b)
        self.add_item(JumpButton())


# ------------------------------------------------------------------
# Renderers
# ------------------------------------------------------------------

async def _render_list_page(db, player, page: int):
    entries = inventory_service.list_combined_entries(db, player.id)
    total_pages = max(1, (len(entries) + embedder.ITEMS_PER_LIST_PAGE - 1) // embedder.ITEMS_PER_LIST_PAGE)
    page = max(0, min(page, total_pages - 1))
    start = page * embedder.ITEMS_PER_LIST_PAGE
    page_entries = entries[start:start + embedder.ITEMS_PER_LIST_PAGE]

    options = []
    for i, entry in enumerate(page_entries, start=start + 1):
        if entry.kind == "lootbox":
            label = f"{i}. {entry.obj.template.name} x{entry.obj.quantity}"
            emoji = "📦"
        else:
            item = entry.obj
            label = f"{i}. {item.display_name}"[:100]
            emoji = embedder.RARITY_EMOJI.get(item.rarity.value, "⚪")
        options.append(discord.SelectOption(label=label[:100], value=entry.entry_id, emoji=emoji))

    select = InventorySelectEntry(options or None)
    page_buttons = [
        ListPageButton("prev", page, disabled=page <= 0),
        ListPageButton("next", page, disabled=page >= total_pages - 1),
    ]

    embed = embedder.inventory_list_embed(entries, page, player.username)
    view = InventoryListView(select, page_buttons)
    return embed, view


async def _render_detail_page(db, player, entry_id: str):
    entry = inventory_service.get_combined_entry(db, player.id, entry_id)
    if entry is None:
        entries = inventory_service.list_combined_entries(db, player.id)
        entry = entries[0] if entries else None
    if entry is None:
        embed = discord.Embed(title="Inventory", description="Your inventory is empty.")
        return embed, InventoryListView(InventorySelectEntry(), [])

    idx, total = inventory_service.entry_index_and_total(db, player.id, entry.entry_id)
    prev_id = inventory_service.get_neighbor_entry_id(db, player.id, entry.entry_id, "prev")
    next_id = inventory_service.get_neighbor_entry_id(db, player.id, entry.entry_id, "next")

    buttons: list[discord.ui.Item] = [
        EntryNavButton("prev", prev_id or entry.entry_id, disabled=prev_id is None),
        EntryNavButton("next", next_id or entry.entry_id, disabled=next_id is None),
        ToListButton(entry.entry_id),
    ]

    if entry.kind == "lootbox":
        buttons.append(EntryOpenLootboxButton(entry.obj.template.tier))
    else:
        item = entry.obj
        buttons.append(EntryEquipToggleButton(
            item.id,
            label="Unequip" if item.is_equipped else "Equip",
            style=discord.ButtonStyle.danger if item.is_equipped else discord.ButtonStyle.success,
        ))
        buttons.append(EntryLevelUpButton(item.id))
        buttons.append(EntryRerollButton(item.id))
        if not item.is_equipped:
            buttons.append(EntrySellButton(item.id))

    buttons.append(JumpButton())

    embed = embedder.entry_detail_embed(entry, idx, total)
    view = EntryDetailView(buttons)
    return embed, view


# ------------------------------------------------------------------
# Interaction handlers
# ------------------------------------------------------------------

async def _handle_nav(interaction: discord.Interaction, entry_id: str, direction: str):
    db = SessionLocal()
    try:
        player = get_player(db, interaction.user.id)
        if player is None:
            await interaction.response.send_message("Use `/start` first.", ephemeral=True)
            return
        embed, view = await _render_detail_page(db, player, entry_id)
        await interaction.response.edit_message(content=None, embed=embed, view=view)
    finally:
        db.close()


async def _handle_equip_toggle(interaction: discord.Interaction, item_id: int):
    db = SessionLocal()
    try:
        player = get_player(db, interaction.user.id)
        if player is None:
            await interaction.response.send_message("Use `/start` first.", ephemeral=True)
            return

        guard = _in_combat_guard(db, player)
        if guard:
            await interaction.response.send_message(guard, ephemeral=True)
            return

        item = inventory_service.get_item(db, item_id, player.id)
        if item is None:
            await interaction.response.send_message("Item not found.", ephemeral=True)
            return

        if item.is_equipped:
            ok, message = inventory_service.unequip_item(db, item)
            embed, view = await _render_detail_page(db, player, f"item:{item.id}")
            await interaction.response.edit_message(content=message, embed=embed, view=view)
            return

        squad = character_service.get_squad(db, player)
        if len(squad) <= 1:
            character = character_service.ensure_avatar_character(db, player)
            ok, message = inventory_service.equip_item(db, character, item)
            embed, view = await _render_detail_page(db, player, f"item:{item.id}")
            await interaction.response.edit_message(content=message, embed=embed, view=view)
            return

        options = [
            discord.SelectOption(
                label=f"{pc.template.name} (Lv{pc.level}, {pc.template.character_class.value.replace('_', ' ').title()})"[:100],
                value=str(pc.id),
            )
            for pc in squad
        ]
        options.append(discord.SelectOption(label="Cancel", value="cancel", emoji="✖️"))
        view = EquipTargetView(item.id, options)
        embed = embedder.item_detail_embed(item)
        await interaction.response.edit_message(
            content=f"Which squad member should equip {item.display_name}?",
            embed=embed, view=view,
        )
        return
    finally:
        db.close()


async def _handle_level_up(interaction: discord.Interaction, item_id: int):
    db = SessionLocal()
    try:
        player = get_player(db, interaction.user.id)
        if player is None:
            await interaction.response.send_message("Use `/start` first.", ephemeral=True)
            return

        item = inventory_service.get_item(db, item_id, player.id)
        if item is None:
            await interaction.response.send_message("Item not found.", ephemeral=True)
            return

        ok, message = item_upgrade_service.level_up_item(db, player, item)
        db.refresh(item)

        embed, view = await _render_detail_page(db, player, f"item:{item.id}")
        await interaction.response.edit_message(content=message, embed=embed, view=view)
    finally:
        db.close()


async def _handle_reroll(interaction: discord.Interaction, item_id: int):
    db = SessionLocal()
    try:
        player = get_player(db, interaction.user.id)
        if player is None:
            await interaction.response.send_message("Use `/start` first.", ephemeral=True)
            return

        item = inventory_service.get_item(db, item_id, player.id)
        if item is None:
            await interaction.response.send_message("Item not found.", ephemeral=True)
            return

        ok, message = item_upgrade_service.reroll_item(db, player, item)
        db.refresh(item)

        embed, view = await _render_detail_page(db, player, f"item:{item.id}")
        await interaction.response.edit_message(content=message, embed=embed, view=view)
    finally:
        db.close()


async def _handle_sell(interaction: discord.Interaction, item_id: int):
    db = SessionLocal()
    try:
        player = get_player(db, interaction.user.id)
        if player is None:
            await interaction.response.send_message("Use `/start` first.", ephemeral=True)
            return

        item = inventory_service.get_item(db, item_id, player.id)
        if item is None:
            await interaction.response.send_message("Item not found.", ephemeral=True)
            return

        ok, message = inventory_service.sell_item(db, player, item)
        # After a successful sale the item row is gone -- _render_detail_page
        # gracefully falls back to the next available entry (or an empty
        # state) when asked for an entry_id that no longer exists.
        embed, view = await _render_detail_page(db, player, f"item:{item_id}")
        await interaction.response.edit_message(content=message, embed=embed, view=view)
    finally:
        db.close()


async def _handle_open_lootbox(interaction: discord.Interaction, tier: str):
    db = SessionLocal()
    try:
        player = get_player(db, interaction.user.id)
        if player is None:
            await interaction.response.send_message("Use `/start` first.", ephemeral=True)
            return

        guard = _in_combat_guard(db, player)
        if guard:
            await interaction.response.send_message(guard, ephemeral=True)
            return

        owned = next(
            (o for o in lootbox_service.list_player_lootboxes(db, player.id) if o.template.tier == tier),
            None,
        )
        if owned is None or owned.quantity <= 0:
            await interaction.response.send_message(f"You don't have any {tier.title()} Lootboxes.", ephemeral=True)
            return

        ok, message, rewards = lootbox_service.open_lootboxes(
            db, player, tier, count=owned.quantity, item_level=character_service.get_progression_level(db, player)
        )
        if not ok:
            await interaction.response.send_message(message, ephemeral=True)
            return

        if rewards["items"]:
            names = ", ".join(f"**{i.display_name}** ({i.rarity.value})" for i in rewards["items"])
            message += f"\n🪙 {rewards['gold']} gold"
            if rewards["shards"]:
                message += f", 💎 {rewards['shards']} shards"
            message += f"\nItems: {names}"

        entries = inventory_service.list_combined_entries(db, player.id)
        first_id = entries[0].entry_id if entries else None
        if first_id:
            embed, view = await _render_detail_page(db, player, first_id)
        else:
            embed, view = await _render_list_page(db, player, 0)
        await interaction.response.edit_message(content=message, embed=embed, view=view)
    finally:
        db.close()


# ----------------------------------------------------------------------
# Cog
# ----------------------------------------------------------------------

@guild_decorator
class Inventory(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # COMMAND: /inventory
    # Opens the big List view: a compact, paginated overview of every item
    # and lootbox stack you own. Pick one from the dropdown (or use 🔍 Jump
    # to #) to see it in full detail, equip it, level it up, reroll its
    # substats, or open a lootbox stack.
    @app_commands.command(name="inventory", description="Browse your items and lootboxes.")
    async def inventory(self, ctx: discord.Interaction):
        db = SessionLocal()
        try:
            player = get_player(db, ctx.user.id)
            if player is None:
                await ctx.response.send_message(
                    "You haven't started your journey yet. Use `/start` first.",
                    ephemeral=True,
                )
                return

            entries = inventory_service.list_combined_entries(db, player.id)
            if not entries:
                await ctx.response.send_message(
                    "Your inventory is empty. Try `/adventure`, `/pull`, or `/open`.",
                    ephemeral=True,
                )
                return

            embed, view = await _render_list_page(db, player, 0)
        finally:
            db.close()

        await ctx.response.send_message(embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(Inventory(bot))
