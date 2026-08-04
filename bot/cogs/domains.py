"""
/domains -- energy-gated single-battle challenges against a fixed enemy
squad, for direct on-demand rewards (materials/shards/gold/lootboxes/XP)
without running a full expedition. All energy math and battle handling
lives in bot/services/domain_service.py; this cog is just the view layer.

Unlike dungeon combat, a domain battle is held ONLY in memory (see
domain_service's module docstring for why) -- so this cog's combat
handlers read/write domain_service._ACTIVE_BATTLES via
get_active_battle/resolve_challenge/abandon_challenge instead of loading
an Expedition's combat_state from the DB. The combat UI itself
(attack/ability/ultimate/target-select) intentionally mirrors
bot/cogs/dungeon.py's CombatView closely for a consistent feel, but is a
separate set of classes rather than a shared import, since the two
battle-persistence models are different enough that sharing stateful UI
classes across them would be more fragile than a bit of duplication.
"""

import discord

from discord.ext import commands
from discord import app_commands

from bot.database.session import SessionLocal
from bot.services.player_service import get_player
from bot.services import domain_service
from bot.game.economy.domain_config import DOMAIN_TYPES, DOMAIN_DIFFICULTY_TIERS, get_domain_type
from bot.utils import combat_ui, embedder
from bot.utils.guild_decorator import guild_decorator
from bot.utils.ui_guard import OwnedView, require_player


def _domain_select_options() -> list[discord.SelectOption]:
    return [
        discord.SelectOption(label=d["name"], value=d["id"], description=d["description"][:100], emoji=d["icon"])
        for d in DOMAIN_TYPES
    ]


class DomainSelect(discord.ui.Select):
    def __init__(self, options: list[discord.SelectOption]):
        super().__init__(
            placeholder="Choose a domain...", options=options,
            custom_id="cascade_domain_select", min_values=1, max_values=1,
        )

    async def callback(self, interaction: discord.Interaction):
        await _handle_show_tiers(interaction, self.values[0])


class DomainMenuView(OwnedView):
    def __init__(self, owner_id: int | None = None):
        super().__init__(timeout=180, owner_id=owner_id)
        self.add_item(DomainSelect(_domain_select_options()))


class TierButton(discord.ui.Button):
    def __init__(self, domain_id: str, tier: dict, player, lock_reason: str | None = None):
        """`lock_reason` comes from domain_service.tier_lock_reason and is
        resolved by the CALLER (which still has a live DB session), not
        here -- the unlock check needs to query expedition history and the
        character roster, and a view constructor is the wrong place to be
        opening a session."""
        unlocked = lock_reason is None
        affordable = domain_service.get_current_energy(player) >= tier["energy_cost"]
        label = f"{tier['name']} ({tier['energy_cost']}⚡)" if unlocked else f"🔒 {tier['name']}"
        style = discord.ButtonStyle.success if (unlocked and affordable) else discord.ButtonStyle.secondary
        super().__init__(
            label=label[:80], style=style, disabled=not (unlocked and affordable),
            custom_id=f"cascade_domain_tier:{domain_id}:{tier['id']}",
        )
        self.domain_id = domain_id
        self.tier_id = tier["id"]

    async def callback(self, interaction: discord.Interaction):
        await _handle_start_domain(interaction, self.domain_id, self.tier_id)


class BackToDomainsButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="⬅️ Back", style=discord.ButtonStyle.secondary, custom_id="cascade_domain_back", row=4)

    async def callback(self, interaction: discord.Interaction):
        await _handle_show_menu(interaction)


class DomainTierView(OwnedView):
    def __init__(self, domain_id: str, player, lock_reasons: dict[str, str | None], owner_id: int | None = None):
        super().__init__(timeout=180, owner_id=owner_id)
        for tier in DOMAIN_DIFFICULTY_TIERS:
            self.add_item(TierButton(domain_id, tier, player, lock_reasons.get(tier["id"])))
        self.add_item(BackToDomainsButton())


class DomainAbilitySelect(discord.ui.Select):
    def __init__(self, options: list[discord.SelectOption]):
        super().__init__(
            placeholder="Use a skill (costs SP)...", options=options,
            custom_id="cascade_domain_ability_select", min_values=1, max_values=1,
        )

    async def callback(self, interaction: discord.Interaction):
        await _handle_combat_action(interaction, "ability", ability_id=self.values[0])


class DomainTargetSelect(discord.ui.Select):
    """Switching targets is a free action -- it does not end the player's
    turn, it just changes who Attack/Ability/Ultimate will hit next."""
    def __init__(self, options: list[discord.SelectOption]):
        super().__init__(
            placeholder="🎯 Switch target...", options=options,
            custom_id="cascade_domain_target_select", min_values=1, max_values=1,
        )

    async def callback(self, interaction: discord.Interaction):
        await _handle_select_target(interaction, int(self.values[0]))


class DomainAllySelect(discord.ui.Select):
    """Support-target picker -- see AllySelect in bot/cogs/dungeon.py for
    what this is and why it's a free action."""

    def __init__(self, options: list[discord.SelectOption]):
        super().__init__(
            placeholder="💚 Support target...", options=options,
            custom_id="cascade_domain_ally_select", min_values=1, max_values=1,
        )

    async def callback(self, interaction: discord.Interaction):
        raw = self.values[0]
        await _handle_select_ally(interaction, None if raw == "auto" else int(raw))


class DomainCombatView(OwnedView):
    def __init__(
        self,
        ability_options: list[discord.SelectOption] | None = None,
        target_options: list[discord.SelectOption] | None = None,
        ultimate_ready: bool = False,
        ultimate_exists: bool = False,
        ultimate_energy: int = 0,
        ultimate_cost: int = 100,
        owner_id: int | None = None,
        ally_options: list[discord.SelectOption] | None = None,
    ):
        super().__init__(timeout=None, owner_id=owner_id)
        self.attack_button.disabled = False
        self.ultimate_button.disabled = not ultimate_ready
        if ultimate_exists:
            status = "Ready!" if ultimate_ready else f"{ultimate_energy}/{ultimate_cost} EN"
            self.ultimate_button.label = f"💥 Ultimate ({status})"
        else:
            self.ultimate_button.label = "💥 No Ultimate"
        if not ultimate_exists:
            self.remove_item(self.ultimate_button)

        if ability_options:
            self.add_item(DomainAbilitySelect(ability_options))
        if target_options:
            self.add_item(DomainTargetSelect(target_options))
        if ally_options:
            self.add_item(DomainAllySelect(ally_options))

    @discord.ui.button(label="⚔️ Attack", style=discord.ButtonStyle.danger, custom_id="cascade_domain_attack")
    async def attack_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _handle_combat_action(interaction, "attack")

    @discord.ui.button(label="💥 Ultimate", style=discord.ButtonStyle.success, custom_id="cascade_domain_ultimate")
    async def ultimate_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _handle_combat_action(interaction, "ultimate")

    @discord.ui.button(label="🛡️ Guard", style=discord.ButtonStyle.primary, custom_id="cascade_domain_guard")
    async def guard_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _handle_combat_action(interaction, "guard")

    @discord.ui.button(label="ℹ️ Info", style=discord.ButtonStyle.secondary, custom_id="cascade_domain_info", row=4)
    async def info_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _handle_combat_info(interaction)

    @discord.ui.button(label="📜 Log", style=discord.ButtonStyle.secondary, custom_id="cascade_domain_log", row=4)
    async def log_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _handle_combat_log(interaction)

    @discord.ui.button(label="🏳️ Forfeit", style=discord.ButtonStyle.secondary, custom_id="cascade_domain_forfeit", row=4)
    async def forfeit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _handle_forfeit(interaction)


def _build_domain_combat_view(battle, owner_id: int) -> DomainCombatView:
    actor = battle.current_actor()
    ability_options = []
    for ability in actor.active_abilities:
        ready = actor.ability_ready(ability)
        source_icon = {"character": "🌀", "weapon": "⚔️", "artifact": "🔮"}.get(ability.get("source"), "✨")
        unit = "SP" if ability["resource_type"] == "mana" else "EN"
        cost_str = f"{ability['resource_cost']} {unit}"

        if ready:
            status = "Ready"
        else:
            cooldown_remaining = actor.cooldowns.get(ability["id"], 0)
            if cooldown_remaining > 0:
                status = f"ready in {cooldown_remaining}t"
            else:
                pool = actor.mana if ability["resource_type"] == "mana" else actor.energy
                status = f"need {ability['resource_cost'] - pool} more {unit}"

        label = f"{source_icon} {ability['name']} -- {cost_str} ({status})"
        ability_options.append(discord.SelectOption(
            label=label[:100], value=ability["id"], description=ability["description"][:100],
        ))

    # Shared helper -- see combat_ui.enemy_target_options (returns none
    # while an enemy is taunting, which forces the target).
    target_options = combat_ui.enemy_target_options(battle)

    ally_options = combat_ui.ally_select_options(battle) if combat_ui.should_offer_ally_select(battle) else []

    return DomainCombatView(
        ability_options or None,
        target_options or None,
        ultimate_ready=actor.ultimate_ready(),
        ultimate_exists=actor.ultimate_ability is not None,
        ultimate_energy=actor.energy,
        ultimate_cost=actor.ultimate_ability["resource_cost"] if actor.ultimate_ability else 100,
        owner_id=owner_id,
        ally_options=ally_options or None,
    )


def _advance_domain_battle(db, player, battle) -> dict | None:
    """Resolves every enemy turn (including a faster enemy acting before
    any party member ever gets to move) until it's a party member's turn
    or the battle ends. Returns domain_service.resolve_challenge's summary
    if the fight just ended, else None."""
    while not battle.is_over() and battle.current_actor() in battle.enemies:
        battle.take_enemy_turn()
    if battle.is_over():
        return domain_service.resolve_challenge(db, player)
    return None


async def _handle_show_menu(interaction: discord.Interaction):
    db = SessionLocal()
    try:
        player = get_player(db, interaction.user.id)
        if player is None:
            await interaction.response.send_message("Use `/start` first.", ephemeral=True)
            return
        embed = embedder.domain_menu_embed(player)
        view = DomainMenuView(owner_id=player.id)
        await interaction.response.edit_message(embed=embed, view=view)
    finally:
        db.close()


async def _handle_show_tiers(interaction: discord.Interaction, domain_id: str):
    db = SessionLocal()
    try:
        player = get_player(db, interaction.user.id)
        if player is None:
            await interaction.response.send_message("Use `/start` first.", ephemeral=True)
            return
        domain = get_domain_type(domain_id)
        if domain is None:
            await interaction.response.send_message("No such domain.", ephemeral=True)
            return
        # Resolved once here and passed down to both the embed and the
        # view, so the two can never disagree about what's locked and the
        # unlock queries only run once per render.
        lock_reasons = {
            tier["id"]: domain_service.tier_lock_reason(db, player, tier)
            for tier in DOMAIN_DIFFICULTY_TIERS
        }
        embed = embedder.domain_tier_embed(domain, player, lock_reasons)
        view = DomainTierView(domain_id, player, lock_reasons, owner_id=player.id)
        await interaction.response.edit_message(embed=embed, view=view)
    finally:
        db.close()


async def _handle_start_domain(interaction: discord.Interaction, domain_id: str, tier_id: str):
    db = SessionLocal()
    try:
        player = get_player(db, interaction.user.id)
        if player is None:
            await interaction.response.send_message("Use `/start` first.", ephemeral=True)
            return

        try:
            battle = domain_service.start_challenge(db, player, domain_id, tier_id)
        except domain_service.DomainChallengeError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        avatar_url = interaction.user.display_avatar.url
        summary = _advance_domain_battle(db, player, battle)
        embed = embedder.combat_embed(battle, avatar_url=avatar_url)

        if summary is not None:
            await interaction.response.edit_message(embed=embed, view=None)
            await interaction.followup.send(embed=embedder.domain_result_embed(summary))
        else:
            await interaction.response.edit_message(embed=embed, view=_build_domain_combat_view(battle, player.id))
    finally:
        db.close()


async def _handle_combat_info(interaction: discord.Interaction):
    player_id = interaction.user.id
    battle = domain_service.get_active_battle(player_id)
    if battle is None:
        await interaction.response.send_message("You're not in a domain battle right now.", ephemeral=True)
        return
    embed, view = combat_ui.info_response(battle)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def _handle_combat_log(interaction: discord.Interaction):
    player_id = interaction.user.id
    battle = domain_service.get_active_battle(player_id)
    if battle is None:
        await interaction.response.send_message("You're not in a domain battle right now.", ephemeral=True)
        return
    await interaction.response.send_message(embed=embedder.battle_log_embed(battle), ephemeral=True)


async def _handle_combat_action(interaction: discord.Interaction, action: str, ability_id: str | None = None):
    db = SessionLocal()
    try:
        player = get_player(db, interaction.user.id)
        battle = domain_service.get_active_battle(interaction.user.id) if player else None
        if player is None or battle is None:
            await interaction.response.send_message("You're not in a domain battle right now.", ephemeral=True)
            return
        if battle.current_actor() not in battle.party:
            await interaction.response.send_message("It's not your turn yet.", ephemeral=True)
            return

        battle.take_party_action(action, ability_id=ability_id)
        summary = _advance_domain_battle(db, player, battle)
        avatar_url = interaction.user.display_avatar.url

        if summary is not None:
            await interaction.response.edit_message(embed=embedder.combat_embed(battle, avatar_url=avatar_url), view=None)
            await interaction.followup.send(embed=embedder.domain_result_embed(summary))
        else:
            await interaction.response.edit_message(
                embed=embedder.combat_embed(battle, avatar_url=avatar_url),
                view=_build_domain_combat_view(battle, player.id),
            )
    finally:
        db.close()


async def _handle_select_target(interaction: discord.Interaction, target_index: int):
    player_id = interaction.user.id
    battle = domain_service.get_active_battle(player_id)
    if battle is None:
        await interaction.response.send_message("You're not in a domain battle right now.", ephemeral=True)
        return
    if battle.current_actor() not in battle.party:
        await interaction.response.send_message("It's not your turn yet.", ephemeral=True)
        return

    battle.select_target(target_index)
    avatar_url = interaction.user.display_avatar.url
    await interaction.response.edit_message(
        embed=embedder.combat_embed(battle, avatar_url=avatar_url),
        view=_build_domain_combat_view(battle, player_id),
    )


async def _handle_select_ally(interaction: discord.Interaction, party_index: int | None):
    """Free action, same as target selection -- see
    dungeon.py::_handle_select_ally. No DB write here: a domain battle is
    held in memory only (see domain_service's module docstring), so
    mutating the live Battle is the whole persistence step."""
    player_id = interaction.user.id
    battle = domain_service.get_active_battle(player_id)
    if battle is None:
        await interaction.response.send_message("You're not in a domain battle right now.", ephemeral=True)
        return
    if battle.current_actor() not in battle.party:
        await interaction.response.send_message("It's not your turn yet.", ephemeral=True)
        return

    battle.select_ally_target(party_index)
    avatar_url = interaction.user.display_avatar.url
    await interaction.response.edit_message(
        embed=embedder.combat_embed(battle, avatar_url=avatar_url),
        view=_build_domain_combat_view(battle, player_id),
    )


async def _handle_forfeit(interaction: discord.Interaction):
    db = SessionLocal()
    try:
        player = get_player(db, interaction.user.id)
        if player is None or not domain_service.has_active_challenge(interaction.user.id):
            await interaction.response.send_message("You're not in a domain battle right now.", ephemeral=True)
            return
        domain_service.abandon_challenge(db, player)
        embed = embedder.domain_menu_embed(player)
        view = DomainMenuView(owner_id=player.id)
        await interaction.response.edit_message(
            content="You forfeit the domain challenge. No reward, but nothing further lost.",
            embed=embed, view=view,
        )
    finally:
        db.close()


@guild_decorator
class Domains(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="domains", description="Spend energy on single-battle challenges for direct rewards.")
    async def domains(self, ctx: discord.Interaction):
        db = SessionLocal()
        try:
            player = get_player(db, ctx.user.id)
            if not await require_player(ctx, player):
                return

            if domain_service.has_active_challenge(player.id):
                battle = domain_service.get_active_battle(player.id)
                # Every code path that touches an active battle already
                # advances it to a party turn (or resolves it) before
                # returning -- see _advance_domain_battle -- so this
                # should be a no-op in practice. Called anyway as a
                # defensive guard so resuming here can never hand back a
                # view with no usable buttons.
                summary = _advance_domain_battle(db, player, battle)
                avatar_url = ctx.user.display_avatar.url
                if summary is not None:
                    await ctx.response.send_message(
                        content="Your domain challenge just resolved.",
                        embed=embedder.domain_result_embed(summary),
                    )
                    return
                embed = embedder.combat_embed(battle, avatar_url=avatar_url)
                view = _build_domain_combat_view(battle, player.id)
                await ctx.response.send_message(
                    content="You're already mid-challenge -- picking up where you left off.",
                    embed=embed, view=view,
                )
                return

            embed = embedder.domain_menu_embed(player)
            view = DomainMenuView(owner_id=player.id)
        finally:
            db.close()
        await ctx.response.send_message(embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(Domains(bot))
