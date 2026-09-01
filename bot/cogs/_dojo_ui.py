"""
Dojo screens: build, browse, and fight player-authored challenges.

UNDERSCORE-PREFIXED ON PURPOSE. bot/client.py loads every *.py in
bot/cogs that does not start with "_", so a helper module in this
directory must be named this way or the loader tries to load_extension it
and fails on the missing setup(). The command itself lives in base.py,
inside the /base group, because the dojo is a room in your base.

Combat handling mirrors bot/cogs/challenge.py, which mirrors domains.py,
for the reason all three share: a dojo fight is one self-contained
in-memory battle with no run state to lose, so it follows the pattern
built for exactly that shape rather than the dungeon's.
"""

from __future__ import annotations

import discord

from bot.database.session import SessionLocal
from bot.game.economy import dojo_config as cfg
from bot.services import dojo_service
from bot.services.player_service import get_player
from bot.utils import combat_ui, embedder, paging, responses
from bot.utils.ui_guard import OwnedView

DOJO_COLOUR = discord.Colour.dark_teal()


# ----------------------------------------------------------------------
# Reading a challenge
# ----------------------------------------------------------------------

def describe_enemies(challenge) -> str:
    parts = []
    for stack in (challenge.enemies or []):
        count = int(stack.get("count", 1))
        parts.append(f"{stack.get('enemy')}" + (f" ×{count}" if count > 1 else ""))
    return ", ".join(parts) or "nothing"


def challenge_line(challenge, db=None) -> str:
    rate = dojo_service.clear_rate(challenge)
    rate_text = f"{rate:.0%} cleared" if rate is not None else "untried"
    return (f"`{challenge.share_code}` **{challenge.name}** — "
            f"Lv.{challenge.level}, {describe_enemies(challenge)} · {rate_text}")


def dojo_embed(db, player) -> discord.Embed:
    remaining = dojo_service.rewards_remaining(player)
    embed = discord.Embed(
        title="🥋 The Dojo",
        description=(
            "Build your own fights, and try what everyone else has built.\n\n"
            "Clearing somebody's challenge pays a little XP — "
            f"**{remaining}/{cfg.REWARDED_CLEARS_PER_DAY}** rewarded clears left "
            "today. It's not a place to grind; the XP is there so a win isn't "
            "worth nothing."
        ),
        colour=DOJO_COLOUR,
    )
    mine = dojo_service.list_own(db, player)
    if mine:
        embed.add_field(
            name=f"Yours ({len(mine)}/{cfg.MAX_CHALLENGES_PER_AUTHOR})",
            value="\n".join(
                ("📢 " if c.published else "📝 ") + challenge_line(c)
                for c in mine[:8])[:1024],
            inline=False)
    else:
        embed.add_field(
            name="Yours",
            value="*You haven't built anything yet. Press **Build** below.*",
            inline=False)

    published = dojo_service.list_published(db, limit=6)
    embed.add_field(
        name="Recently published",
        value=("\n".join(challenge_line(c) for c in published)[:1024]
               if published else "*Nothing published yet — be the first.*"),
        inline=False)
    embed.set_footer(text="📢 published · 📝 draft. Share a code with anyone.")
    return embed


# ----------------------------------------------------------------------
# Building
# ----------------------------------------------------------------------

class BuildModal(discord.ui.Modal, title="Build a dojo challenge"):
    """Name, description and level. The ENEMIES are picked from a select
    afterwards, because a modal cannot hold one and asking somebody to
    type enemy names exactly would be a spelling test."""

    name = discord.ui.TextInput(label="Name", max_length=cfg.MAX_NAME_LENGTH,
                                placeholder="Three Wraiths and a Bad Idea")
    description = discord.ui.TextInput(
        label="Description (optional)", required=False,
        max_length=cfg.MAX_DESCRIPTION_LENGTH, style=discord.TextStyle.paragraph)
    level = discord.ui.TextInput(label=f"Enemy level ({cfg.MIN_LEVEL}-{cfg.MAX_LEVEL})",
                                 max_length=3, placeholder="30")

    def __init__(self, enemies: list[dict]):
        super().__init__()
        self.enemies = enemies

    async def on_submit(self, interaction: discord.Interaction):
        await responses.defer(interaction, ephemeral=True)
        db = SessionLocal()
        try:
            player = get_player(db, interaction.user.id)
            if player is None:
                await responses.send(interaction, "Use `/start` first.", ephemeral=True)
                return
            try:
                level = int(str(self.level.value).strip())
            except ValueError:
                await responses.send(
                    interaction, "The level needs to be a number.", ephemeral=True)
                return
            try:
                challenge = dojo_service.create_challenge(
                    db, player, str(self.name.value), self.enemies, level,
                    str(self.description.value) or None)
            except dojo_service.DojoError as exc:
                await responses.send(interaction, str(exc), ephemeral=True)
                return

            await responses.send(
                interaction,
                f"🥋 Built **{challenge.name}** — `{challenge.share_code}`\n"
                f"Lv.{challenge.level} · {describe_enemies(challenge)}\n\n"
                f"It's a **draft**. Publish it from `/base dojo` when you're "
                f"happy with it, and anyone can play it with that code.",
                ephemeral=True)
        finally:
            db.close()


class EnemyPickView(OwnedView):
    """Pick up to MAX_ENEMY_STACKS enemies, then open the modal."""

    def __init__(self, owner_id: int, page: int = 0):
        super().__init__(timeout=300, owner_id=owner_id)
        self.add_item(_EnemySelect(page))


class _EnemySelect(discord.ui.Select):
    def __init__(self, page: int = 0):
        names = dojo_service.known_enemy_names()
        # Discord's hard 25-option cap. There are ~100 buildable enemies,
        # so this is a WINDOW, and the placeholder says so -- an unpaged
        # select silently drops everything past 25 and looks like the
        # roster is smaller than it is.
        window = names[page * 25:(page + 1) * 25]
        super().__init__(
            placeholder=f"Pick enemies ({page * 25 + 1}-{page * 25 + len(window)} "
                        f"of {len(names)})…",
            min_values=1, max_values=min(cfg.MAX_ENEMY_STACKS, len(window)),
            options=[discord.SelectOption(label=n[:100], value=n[:100]) for n in window],
        )

    async def callback(self, interaction: discord.Interaction):
        # Every pick becomes one copy. Counts beyond that are a
        # deliberate omission: a second dropdown for "how many of each"
        # is three more clicks for something the author can express by
        # picking a smaller level, and the modal is already three fields.
        enemies = [{"enemy": name, "count": 1} for name in self.values]
        await interaction.response.send_modal(BuildModal(enemies))


# ----------------------------------------------------------------------
# The main panel
# ----------------------------------------------------------------------

class DojoView(OwnedView):
    def __init__(self, db, player, page: int = 0):
        super().__init__(timeout=300, owner_id=player.id)
        self.page = page
        self.db = db
        self.player = player
        mine = dojo_service.list_own(db, player)
        playable = dojo_service.list_published(db, limit=250)
        if playable:
            self.add_item(_PlaySelect(playable, page=page))
            paging.add_page_buttons(self, page, len(playable), _PlaySelect.PER_PAGE, row=2)
        if mine:
            self.add_item(_ManageSelect(mine, page=page))

    async def rerender(self, interaction: discord.Interaction, page: int):
        await responses.edit(interaction, embed=dojo_embed(self.db, self.player), view=DojoView(self.db, self.player, page=page))


class _PlaySelect(discord.ui.Select):
    PER_PAGE = paging.SELECT_OPTION_LIMIT

    def __init__(self, challenges, page: int = 0):
        shown = paging.window(challenges, page, self.PER_PAGE)
        super().__init__(
            placeholder=paging.placeholder_for("Play a published challenge…", page, len(challenges), self.PER_PAGE),
            options=[
                discord.SelectOption(
                    label=f"{c.name}"[:100],
                    value=str(c.id),
                    description=f"Lv.{c.level} · {describe_enemies(c)}"[:100])
                for c in shown
            ],
        )
        self.page = page

    async def callback(self, interaction: discord.Interaction):
        await _start_challenge(interaction, int(self.values[0]))


class _ManageSelect(discord.ui.Select):
    PER_PAGE = paging.SELECT_OPTION_LIMIT

    def __init__(self, challenges, page: int = 0):
        shown = paging.window(challenges, page, self.PER_PAGE)
        super().__init__(
            placeholder=paging.placeholder_for("Publish or unpublish one of yours…", page, len(challenges), self.PER_PAGE),
            options=[
                discord.SelectOption(
                    label=f"{'📢' if c.published else '📝'} {c.name}"[:100],
                    value=str(c.id),
                    description=(f"`{c.share_code}` · "
                                 f"{'published' if c.published else 'draft'}")[:100])
                for c in shown
            ],
        )
        self.page = page

    async def callback(self, interaction: discord.Interaction):
        db = SessionLocal()
        try:
            player = get_player(db, interaction.user.id)
            from bot.database.models.dojo_model import DojoChallenge
            challenge = db.query(DojoChallenge).filter_by(
                id=int(self.values[0])).one_or_none()
            if player is None or challenge is None:
                await responses.send(interaction, "That challenge is gone.",
                                     ephemeral=True)
                return
            try:
                dojo_service.set_published(db, player, challenge,
                                           not challenge.published)
            except dojo_service.DojoError as exc:
                await responses.send(interaction, str(exc), ephemeral=True)
                return
            await responses.edit(interaction, embed=dojo_embed(db, player),
                                 view=DojoView(db, player, page=getattr(self.view, 'page', 0)))
            await interaction.followup.send(
                f"{'📢 Published' if challenge.published else '📝 Unpublished'} "
                f"**{challenge.name}** (`{challenge.share_code}`).",
                ephemeral=True)
        finally:
            db.close()


# ----------------------------------------------------------------------
# Fighting
# ----------------------------------------------------------------------

async def _start_challenge(interaction: discord.Interaction, challenge_id: int):
    db = SessionLocal()
    try:
        player = get_player(db, interaction.user.id)
        from bot.database.models.dojo_model import DojoChallenge
        challenge = db.query(DojoChallenge).filter_by(id=challenge_id).one_or_none()
        if player is None or challenge is None:
            await responses.send(interaction, "That challenge is gone.", ephemeral=True)
            return
        try:
            battle = dojo_service.start(db, player, challenge)
        except dojo_service.DojoError as exc:
            await responses.send(interaction, str(exc), ephemeral=True)
            return

        summary = _advance(db, player, battle)
        avatar_url = interaction.user.display_avatar.url
        if summary is not None:
            await responses.edit(
                interaction, embed=embedder.combat_embed(battle, avatar_url=avatar_url),
                view=None)
            await interaction.followup.send(embed=result_embed(summary))
        else:
            await responses.edit(
                interaction, embed=embedder.combat_embed(battle, avatar_url=avatar_url),
                view=build_combat_view(battle, player.id))
    finally:
        db.close()


def _advance(db, player, battle):
    """Resolve enemy turns until it's the player's move or it's over."""
    while not battle.is_over() and battle.current_actor() in battle.enemies:
        battle.take_enemy_turn()
    if battle.is_over():
        return dojo_service.finish(db, player)
    return None


def result_embed(summary: dict) -> discord.Embed:
    challenge = summary.get("challenge")
    won = summary["won"]
    title = "🥋 Cleared" if won else "🥋 Beaten"
    name = challenge.name if challenge is not None else "the challenge"
    embed = discord.Embed(
        title=title,
        description=(f"You cleared **{name}**." if won
                     else f"**{name}** held. Nothing lost — try again."),
        colour=discord.Colour.green() if won else discord.Colour.dark_red(),
    )
    if won:
        if summary.get("paid") and summary.get("xp"):
            line = f"**+{summary['xp']:,} XP**"
            if summary.get("first_clear"):
                line += "  *(first clear bonus)*"
            embed.add_field(name="Training", value=line, inline=False)
        elif challenge is not None and summary.get("xp") == 0 and not summary.get("paid"):
            embed.add_field(
                name="No XP",
                value=("You've had your rewarded clears today, or this is your "
                       "own challenge. The fight still counts."),
                inline=False)
    return embed


def build_combat_view(battle, owner_id: int):
    actor = battle.current_actor()
    if actor is None or actor not in battle.party:
        return None
    ability_options = combat_ui.ability_select_options(actor)
    target_options = combat_ui.enemy_target_options(battle)
    ally_options = (combat_ui.ally_select_options(battle)
                    if combat_ui.should_offer_ally_select(battle) else [])
    return DojoCombatView(
        ability_options or None, target_options or None,
        ultimate_ready=actor.ultimate_ready(),
        ultimate_exists=actor.ultimate_ability is not None,
        ultimate_energy=actor.energy,
        ultimate_cost=(actor.ultimate_ability["resource_cost"]
                       if actor.ultimate_ability else 100),
        owner_id=owner_id, ally_options=ally_options or None,
    )


class DojoCombatView(OwnedView):
    def __init__(self, ability_options=None, target_options=None,
                 ultimate_ready=False, ultimate_exists=False,
                 ultimate_energy=0, ultimate_cost=100, owner_id=None,
                 ally_options=None):
        super().__init__(timeout=None, owner_id=owner_id)
        self.ultimate_button.disabled = not ultimate_ready
        if ultimate_exists:
            self.ultimate_button.label = (
                f"💥 Ultimate ({'Ready!' if ultimate_ready else f'{ultimate_energy}/{ultimate_cost} EN'})")
        else:
            self.remove_item(self.ultimate_button)
        if ability_options:
            self.add_item(_DojoAbilitySelect(ability_options))
        if target_options:
            self.add_item(_DojoTargetSelect(target_options))
        if ally_options:
            self.add_item(_DojoAllySelect(ally_options))

    @discord.ui.button(label="⚔️ Attack", style=discord.ButtonStyle.danger,
                       custom_id="cascade_dojo_attack")
    async def attack_button(self, interaction, button):
        await handle_action(interaction, "attack")

    @discord.ui.button(label="💥 Ultimate", style=discord.ButtonStyle.success,
                       custom_id="cascade_dojo_ultimate")
    async def ultimate_button(self, interaction, button):
        await handle_action(interaction, "ultimate")

    @discord.ui.button(label="🛡️ Guard", style=discord.ButtonStyle.primary,
                       custom_id="cascade_dojo_guard")
    async def guard_button(self, interaction, button):
        await handle_action(interaction, "guard")


class _DojoAbilitySelect(discord.ui.Select):
    def __init__(self, options):
        super().__init__(placeholder="Use an ability…", options=options[:25])

    async def callback(self, interaction):
        await handle_action(interaction, "ability", ability_id=self.values[0])


class _DojoTargetSelect(discord.ui.Select):
    def __init__(self, options):
        super().__init__(placeholder="🎯 Switch target…", options=options[:25])

    async def callback(self, interaction):
        battle = dojo_service.get_active_battle(interaction.user.id)
        if battle is None or battle.current_actor() not in battle.party:
            await responses.send(interaction, "It's not your turn yet.", ephemeral=True)
            return
        battle.select_target(int(self.values[0]))
        await responses.edit(
            interaction,
            embed=embedder.combat_embed(
                battle, avatar_url=interaction.user.display_avatar.url),
            view=build_combat_view(battle, interaction.user.id))


class _DojoAllySelect(discord.ui.Select):
    def __init__(self, options):
        super().__init__(placeholder="💚 Support target…", options=options[:25])

    async def callback(self, interaction):
        battle = dojo_service.get_active_battle(interaction.user.id)
        if battle is None or battle.current_actor() not in battle.party:
            await responses.send(interaction, "It's not your turn yet.", ephemeral=True)
            return
        value = self.values[0]
        battle.select_ally_target(None if value == "auto" else int(value))
        await responses.edit(
            interaction,
            embed=embedder.combat_embed(
                battle, avatar_url=interaction.user.display_avatar.url),
            view=build_combat_view(battle, interaction.user.id))


async def handle_action(interaction: discord.Interaction, action: str,
                        ability_id: str | None = None):
    db = SessionLocal()
    try:
        player = get_player(db, interaction.user.id)
        battle = (dojo_service.get_active_battle(interaction.user.id)
                  if player else None)
        if player is None or battle is None:
            await responses.send(interaction, "You're not in a dojo fight right now.",
                                 ephemeral=True)
            return
        if battle.current_actor() not in battle.party:
            await responses.send(interaction, "It's not your turn yet.", ephemeral=True)
            return

        battle.take_party_action(action, ability_id=ability_id)
        summary = _advance(db, player, battle)
        avatar_url = interaction.user.display_avatar.url
        if summary is not None:
            await responses.edit(
                interaction, embed=embedder.combat_embed(battle, avatar_url=avatar_url),
                view=None)
            await interaction.followup.send(embed=result_embed(summary))
        else:
            await responses.edit(
                interaction, embed=embedder.combat_embed(battle, avatar_url=avatar_url),
                view=build_combat_view(battle, player.id))
    finally:
        db.close()
