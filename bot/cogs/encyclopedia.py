import discord

from discord.ext import commands
from discord import app_commands

from bot.services import encyclopedia_service as enc
from bot.utils import embedder
from bot.utils.guild_decorator import guild_decorator
from bot.utils.ui_guard import OwnedView

# ----------------------------------------------------------------------
# /encyclopedia -- a read-only reference browser for game content
# (characters, classes, enemies, abilities, equipment, materials). Unlike
# every other paginated browser in this codebase, none of this touches the
# database or a Player row -- it's all static content pulled straight from
# bot.services.encyclopedia_service, so there's no "Use /start first" gate
# and no per-request DB session.
#
# Three levels, same List/Detail split as /inventory:
#   CATEGORY picker -- a Select choosing which catalog to browse.
#   LIST mode        -- compact, paginated, with a Select to jump into any
#                        entry on the current page.
#   DETAIL mode       -- one entry at a time with Prev/Next to cycle
#                        through the whole category, full stats/abilities.
#
# Plain (non-Dynamic) Views, same reasoning as ProfilePageView in
# bot/cogs/profile.py: this is disposable browsing state with no target
# data that needs to survive a bot restart, so it doesn't need to be
# registered in bot/client.py.
# ----------------------------------------------------------------------


def _render_categories(owner_id: int) -> tuple[discord.Embed, discord.ui.View]:
    embed = embedder.encyclopedia_categories_embed()
    view = EncyclopediaCategoryView(owner_id=owner_id)
    return embed, view


def _render_list(category: str, page: int, owner_id: int) -> tuple[discord.Embed, discord.ui.View]:
    entries = enc.list_entries(category)
    total_pages = max(1, (len(entries) + embedder.ENCYCLOPEDIA_ENTRIES_PER_PAGE - 1) // embedder.ENCYCLOPEDIA_ENTRIES_PER_PAGE)
    page = max(0, min(page, total_pages - 1))
    embed = embedder.encyclopedia_list_embed(category, entries, page)
    view = EncyclopediaListView(category, page, entries, owner_id=owner_id)
    return embed, view


def _render_detail(category: str, key: str, owner_id: int) -> tuple[discord.Embed, discord.ui.View]:
    entries = enc.list_entries(category)
    entry = next((e for e in entries if e.key == key), None)
    if entry is None:
        # Shouldn't normally happen (keys are stable across a session),
        # but fall back to the first entry rather than erroring out.
        if not entries:
            embed = discord.Embed(title="Nothing here", description="No entries in this category.")
            return embed, EncyclopediaListView(category, 0, entries, owner_id=owner_id)
        entry = entries[0]
    idx = entries.index(entry)
    embed = embedder.encyclopedia_detail_embed(entry, idx, len(entries))
    view = EncyclopediaDetailView(category, entry.key, entries, owner_id=owner_id)
    return embed, view


# ------------------------------------------------------------------
# Category picker
# ------------------------------------------------------------------

class CategorySelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=label.split(" ", 1)[1] if " " in label else label, value=key, emoji=label.split(" ", 1)[0])
            for key, label, _blurb in enc.CATEGORIES
        ]
        super().__init__(placeholder="Choose a category to browse...", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        embed, view = _render_list(self.values[0], 0, interaction.user.id)
        await interaction.response.edit_message(embed=embed, view=view)


class EncyclopediaCategoryView(OwnedView):
    def __init__(self, owner_id: int | None = None):
        super().__init__(timeout=180, owner_id=owner_id)
        self.add_item(CategorySelect())


# ------------------------------------------------------------------
# List mode
# ------------------------------------------------------------------

class EntrySelect(discord.ui.Select):
    """Jumps straight into Detail mode for an entry shown on the current
    list page."""
    def __init__(self, category: str, page_entries: list):
        options = [
            discord.SelectOption(label=e.name[:100], description=e.summary[:100], value=e.key)
            for e in page_entries
        ]
        super().__init__(placeholder="View an entry...", options=options, min_values=1, max_values=1)
        self.category = category

    async def callback(self, interaction: discord.Interaction):
        embed, view = _render_detail(self.category, self.values[0], interaction.user.id)
        await interaction.response.edit_message(embed=embed, view=view)


class EncyclopediaListView(OwnedView):
    def __init__(self, category: str, page: int, entries: list, owner_id: int | None = None):
        super().__init__(timeout=180, owner_id=owner_id)
        self.category = category
        self.page = page
        total_pages = max(1, (len(entries) + embedder.ENCYCLOPEDIA_ENTRIES_PER_PAGE - 1) // embedder.ENCYCLOPEDIA_ENTRIES_PER_PAGE)

        start = page * embedder.ENCYCLOPEDIA_ENTRIES_PER_PAGE
        page_entries = entries[start:start + embedder.ENCYCLOPEDIA_ENTRIES_PER_PAGE]
        if page_entries:
            self.add_item(EntrySelect(category, page_entries))

        self.prev_button.disabled = page <= 0
        self.next_button.disabled = page >= total_pages - 1

    @discord.ui.button(label="◀ Prev", style=discord.ButtonStyle.secondary, row=1)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed, view = _render_list(self.category, self.page - 1, interaction.user.id)
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary, row=1)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed, view = _render_list(self.category, self.page + 1, interaction.user.id)
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="🏷️ Categories", style=discord.ButtonStyle.primary, row=1)
    async def categories_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed, view = _render_categories(interaction.user.id)
        await interaction.response.edit_message(embed=embed, view=view)


# ------------------------------------------------------------------
# Detail mode
# ------------------------------------------------------------------

class EncyclopediaDetailView(OwnedView):
    def __init__(self, category: str, key: str, entries: list, owner_id: int | None = None):
        super().__init__(timeout=180, owner_id=owner_id)
        self.category = category
        self.key = key
        self.keys = [e.key for e in entries]
        idx = self.keys.index(key) if key in self.keys else 0
        self.idx = idx

        self.prev_button.disabled = len(self.keys) <= 1
        self.next_button.disabled = len(self.keys) <= 1

    @discord.ui.button(label="◀ Prev", style=discord.ButtonStyle.secondary, row=0)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        new_key = self.keys[(self.idx - 1) % len(self.keys)]
        embed, view = _render_detail(self.category, new_key, interaction.user.id)
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary, row=0)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        new_key = self.keys[(self.idx + 1) % len(self.keys)]
        embed, view = _render_detail(self.category, new_key, interaction.user.id)
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="📋 List View", style=discord.ButtonStyle.secondary, row=0)
    async def list_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        page = self.idx // embedder.ENCYCLOPEDIA_ENTRIES_PER_PAGE
        embed, view = _render_list(self.category, page, interaction.user.id)
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="🏷️ Categories", style=discord.ButtonStyle.primary, row=0)
    async def categories_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed, view = _render_categories(interaction.user.id)
        await interaction.response.edit_message(embed=embed, view=view)


# ----------------------------------------------------------------------
# Cog
# ----------------------------------------------------------------------

@guild_decorator
class Encyclopedia(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # COMMAND: /encyclopedia
    # Opens the category picker for browsing characters, classes, enemies,
    # abilities, equipment, and materials. No player profile required --
    # this is pure game-content reference, open to anyone.
    @app_commands.command(name="encyclopedia", description="Browse info on characters, enemies, abilities, items, and more.")
    async def encyclopedia(self, ctx: discord.Interaction):
        embed, view = _render_categories(ctx.user.id)
        await ctx.response.send_message(embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(Encyclopedia(bot))
