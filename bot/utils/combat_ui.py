"""
Small pieces of combat UI shared by all three battle surfaces
(bot/cogs/dungeon.py, domains.py, raid.py).

Those three cogs deliberately keep their own View CLASSES -- their
persistence models differ enough that sharing stateful components across
them couples things that need to change independently (see the module
docstring in raid.py). What they should NOT each own is the logic for
deciding what goes IN a component, because that's a game rule rather than
a plumbing detail: if the ally selector offers different choices in a
domain than it does in an expedition, that's a bug, and three copies of
the same loop is how it happens.
"""

from __future__ import annotations

import discord

from bot.utils import names
from bot.game.combat import effects
from bot.utils import embedder


class InfoPageView(discord.ui.View):
    """Pager for the ℹ️ Info readout (see embedder.battle_info_embed).

    Genuinely shared across all three combat surfaces, unlike the battle
    views themselves -- and safe to share precisely because it holds no
    game state: the Battle object is captured directly and the view is
    only ever attached to an EPHEMERAL message, which is per-player,
    short-lived, and never needs to survive a bot restart. That's what
    makes it different from the persistent combat views, which do.

    A jump dropdown sits alongside prev/next because with a 4-person
    squad plus up to 5 enemies there are 9 pages, and stepping through
    them one at a time to check one boss's buffs is exactly the friction
    this rework exists to remove."""

    def __init__(self, battle, page: int = 0):
        super().__init__(timeout=300)
        self.battle = battle
        self.total = embedder.info_page_count(battle)
        self.page = max(0, min(page, self.total - 1))

        self.prev_button.disabled = self.page == 0
        self.next_button.disabled = self.page >= self.total - 1

        options = []
        for i, c in enumerate(embedder.info_page_targets(battle)):
            side = "🧑" if c in battle.party else "👹"
            dead = " 💀" if not c.is_alive() else ""
            options.append(discord.SelectOption(
                label=names.fit_suffix(f"{side} {c.name}", dead, 100),
                value=str(i),
                default=(i == self.page),
            ))
        # Discord caps a select at 25 options; a battle is at most 9
        # combatants, so this can't overflow -- sliced anyway so a future
        # larger fight fails visibly rather than by API rejection.
        self.add_item(_InfoJumpSelect(options[:25]))

    async def _rerender(self, interaction: discord.Interaction, page: int):
        view = InfoPageView(self.battle, page)
        await interaction.response.edit_message(
            embed=embedder.battle_info_embed(self.battle, page), view=view
        )

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._rerender(interaction, self.page - 1)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._rerender(interaction, self.page + 1)


class _InfoJumpSelect(discord.ui.Select):
    def __init__(self, options: list[discord.SelectOption]):
        super().__init__(placeholder="Jump to a combatant...", options=options,
                         min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        await self.view._rerender(interaction, int(self.values[0]))


class LogPageView(discord.ui.View):
    """Pager for the 📜 Battle Log.

    Same shape and same reasoning as InfoPageView above: no game state,
    only ever attached to an ephemeral per-player message, so capturing
    the Battle directly is safe and it never needs to survive a restart.

    Exists because the log used to be one embed that dropped its OLDEST
    lines when it outgrew Discord's 4096-character description -- so the
    longer a fight ran, the more of its opening vanished. Paging keeps
    all of it and defaults to the newest page, which is what someone
    hitting the button mid-fight is looking for.
    """

    def __init__(self, battle, page: int | None = None):
        super().__init__(timeout=300)
        self.battle = battle
        self.pages = embedder.log_pages(battle)
        self.total = len(self.pages)
        self.page = self.total - 1 if page is None else max(0, min(page, self.total - 1))

        self.first_button.disabled = self.page == 0
        self.prev_button.disabled = self.page == 0
        self.next_button.disabled = self.page >= self.total - 1
        self.last_button.disabled = self.page >= self.total - 1
        # A single-page log doesn't need controls at all.
        if self.total <= 1:
            self.clear_items()

    async def _rerender(self, interaction: discord.Interaction, page: int):
        view = LogPageView(self.battle, page)
        await interaction.response.edit_message(
            embed=embedder.battle_log_embed(self.battle, page), view=view
        )

    @discord.ui.button(label="⏮", style=discord.ButtonStyle.secondary)
    async def first_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._rerender(interaction, 0)

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._rerender(interaction, self.page - 1)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._rerender(interaction, self.page + 1)

    @discord.ui.button(label="⏭", style=discord.ButtonStyle.secondary)
    async def last_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._rerender(interaction, self.total - 1)


def log_response(battle, page: int | None = None) -> tuple[discord.Embed, LogPageView]:
    """(embed, view) for the 📜 Log button. One call site per cog, the
    same way info_response is."""
    view = LogPageView(battle, page)
    return embedder.battle_log_embed(battle, view.page), view


def info_response(battle, page: int = 0) -> tuple[discord.Embed, InfoPageView]:
    """(embed, view) for the Info button. One call site per cog."""
    return embedder.battle_info_embed(battle, page), InfoPageView(battle, page)

# Value used by the "let the game decide" entry in the ally selector.
# Not an index, so it can't collide with a party position.
AUTO_ALLY_VALUE = "auto"


def ultimate_button_label(actor) -> str:
    """The Ultimate button's label for `actor`.

    Exists because ultimates now have a COOLDOWN (see ULTIMATE_COOLDOWN
    in combatant.py) and that cooldown is the mechanism keeping a
    resource-stacked squad from ultimate-ing every turn. A limit the
    player can't see is exactly the kind of thing this rework removed
    everywhere else, so a charged-but-cooling ultimate has to say so
    rather than sitting there greyed out and unexplained.

    Precedence is deliberate: cooldown is reported BEFORE energy, since a
    character at 50/50 energy who still can't fire needs to know why, and
    "50/50 EN" on a disabled button reads as a bug."""
    ultimate = actor.ultimate_ability
    if ultimate is None:
        return "💥 Ultimate"
    if actor.ultimate_ready():
        return "💥 Ultimate (Ready!)"
    cooldown = actor.cooldowns.get(ultimate["id"], 0)
    if cooldown > 0:
        return f"💥 Ultimate (ready in {cooldown}t)"
    return f"💥 Ultimate ({actor.energy}/{ultimate['resource_cost']} EN)"


def enemy_target_options(battle) -> list[discord.SelectOption]:
    """Options for the enemy-target dropdown.

    Returns [] when there's nothing to choose -- either only one enemy is
    alive, or one of them is TAUNTING, which forces every single-target
    attack onto it (see Combatant.taunt_turns). Removing the dropdown
    outright while taunted is deliberate: leaving an enabled control that
    silently doesn't work is the worst of the options, and a disabled one
    with no explanation is barely better. The battle embed states the
    reason in its description instead, where the player is already
    reading."""
    if battle.taunting_enemy() is not None:
        return []

    living = battle.living_enemies()
    if len(living) <= 1:
        return []

    options = []
    for i, enemy in enumerate(living):
        marker = "🎯 " if i == battle.target_index else ""
        options.append(discord.SelectOption(
            label=f"{marker}{enemy.name} ({enemy.current_hp}/{enemy.max_hp} HP)"[:100],
            value=str(i),
            default=(i == battle.target_index),
        ))
    return options


def should_offer_ally_select(battle) -> bool:
    """Whether the currently-acting character has any ability that lands
    on a single chosen ally. False for a pure DPS character, whose battle
    view would otherwise carry a dropdown that changes nothing."""
    actor = battle.current_actor()
    if actor is None or actor not in battle.party:
        return False
    return effects.combatant_has_ally_targeting(actor)


def ally_select_options(battle) -> list[discord.SelectOption]:
    """Options for the support-target dropdown: every LIVING squad member
    (the caster included -- self-targeting a heal is a legitimate and
    often correct play), plus an explicit "Auto" entry.

    Auto is offered rather than assumed because the old automatic
    behaviour is genuinely good most of the time -- "whoever is lowest"
    is the right answer often enough that forcing a manual pick every
    turn would be busywork. The choice exists for the turns where the
    player knows better, e.g. shielding whoever the telegraphed enemy
    intent is about to hit rather than whoever happens to be lowest.

    Dead members are omitted: none of the single-ally kinds can revive,
    so offering a corpse would just be a wasted turn. Returns [] when
    fewer than two options would be shown, which keeps a solo squad from
    rendering a pointless one-entry dropdown."""
    current = battle.ally_target_index
    options: list[discord.SelectOption] = [
        discord.SelectOption(
            label="Auto -- whoever needs it most",
            value=AUTO_ALLY_VALUE,
            emoji="✨",
            default=(current is None),
        )
    ]

    for i, member in enumerate(battle.party):
        if not member.is_alive():
            continue
        hp_pct = round(member.current_hp / max(1, member.max_hp) * 100)
        is_actor = member is battle.current_actor()
        label = f"{member.name}{' (you)' if is_actor else ''} -- {hp_pct}% HP"
        options.append(discord.SelectOption(
            label=label[:100],
            value=str(i),
            description=f"{member.current_hp}/{member.max_hp} HP"[:100],
            default=(current == i),
        ))

    # Just Auto + one living member means there's nothing to choose.
    return options if len(options) > 2 else []
