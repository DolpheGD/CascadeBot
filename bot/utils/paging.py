"""
Paging for select menus that list things the player OWNS.

----------------------------------------------------------------------
WHY THIS EXISTS
----------------------------------------------------------------------
Discord allows 25 options in a select. The roster is 31 characters and
grows every time one is added. Every menu built from "your characters"
therefore ended in `options[:25]`, which does not fail, warn, or log --
it silently drops whatever sorted last.

That already shipped as a real bug once: the Echo Exchange lists every
character in the game, so its five most expensive entries were
unbuyable, and the storefront embed cheerfully listed all of them
anyway. It was reported as "the menu is too long so you can't buy some
of them".

The same slice was in four more places -- the squad slot picker, the
profile character switcher, the Echo resonance picker and the Abyss team
picker. Those only bite once a player owns more than 25 characters,
which is precisely the player who has been here longest, and the failure
is "I cannot put this character in my squad" with no explanation.

Slicing is the wrong shape of fix for a list that grows: it fails
silently, it fails worse with every character added, and what it drops
is never the thing the player cares least about. This module is the
alternative -- one window helper and one pair of buttons, so a menu can
be honest about having more than fits.
"""

from __future__ import annotations

import discord

# Discord's hard ceiling on options in a single select.
SELECT_OPTION_LIMIT = 25


def page_count(total: int, per_page: int = SELECT_OPTION_LIMIT) -> int:
    return max(1, -(-total // per_page)) if total else 1


def window(items: list, page: int, per_page: int = SELECT_OPTION_LIMIT) -> list:
    """The slice of `items` shown on `page`, clamped to a real page."""
    pages = page_count(len(items), per_page)
    page = max(0, min(page, pages - 1))
    return items[page * per_page:(page + 1) * per_page]


def placeholder_for(base: str, page: int, total: int,
                    per_page: int = SELECT_OPTION_LIMIT) -> str:
    """`base`, plus the page position when there is more than one page.

    Single-page menus read exactly as they did before this existed --
    the paging should be invisible to the players who never hit it.
    """
    pages = page_count(total, per_page)
    if pages <= 1:
        return base[:150]
    return f"{base} (page {min(page, pages - 1) + 1}/{pages})"[:150]


class PageButton(discord.ui.Button):
    """Prev/next for a paged view.

    The view is responsible for rebuilding itself -- it owns the data and
    the database session -- so this only carries the direction and calls
    back into it. Any view using these must expose `page` and an async
    `rerender(interaction, page)`.
    """

    def __init__(self, step: int, disabled: bool, row: int | None = None):
        super().__init__(
            label="◀" if step < 0 else "▶",
            style=discord.ButtonStyle.secondary,
            disabled=disabled,
            row=row,
        )
        self.step = step

    async def callback(self, interaction: discord.Interaction):
        await self.view.rerender(interaction, self.view.page + self.step)


def add_page_buttons(view, page: int, total: int,
                     per_page: int = SELECT_OPTION_LIMIT,
                     row: int | None = None) -> None:
    """Attach prev/next to `view`, but only when they'd do something.

    A disabled pair of arrows on a menu that fits in one page is UI
    clutter that tells the player nothing, so a single-page menu gets no
    buttons at all.
    """
    pages = page_count(total, per_page)
    if pages <= 1:
        return
    page = max(0, min(page, pages - 1))
    view.add_item(PageButton(-1, disabled=page == 0, row=row))
    view.add_item(PageButton(+1, disabled=page >= pages - 1, row=row))
