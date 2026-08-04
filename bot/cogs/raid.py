"""
/raid and /leaderboard -- the multiplayer surface.

The combat UI here intentionally mirrors bot/cogs/domains.py rather than
importing from it, for the same reason domains.py doesn't import from
dungeon.py: the three flows have genuinely different persistence models
(expedition combat is in the DB, domain and raid combat are in memory
against different services), and sharing stateful View classes across
them couples things that need to stay independently changeable. The
duplication is a few dozen lines of button wiring; the coupling would be
a recurring source of "why did fixing domains break raids".

GUILD SCOPING. Every command here needs interaction.guild_id, so all of
them refuse to run in DMs. That's not a limitation to work around -- a
"server raid" in a DM is meaningless.
"""

import discord

from discord.ext import commands
from discord import app_commands

from bot.database.session import SessionLocal
from bot.services.player_service import get_player
from bot.services import domain_service, dungeon_service, leaderboard_service, raid_service
from bot.game.economy.raid_config import RAID_TIERS
from bot.utils import combat_ui, embedder
from bot.utils.guild_decorator import guild_decorator
from bot.utils.ui_guard import OwnedView, check_message_owner, require_player


async def _reject_dm(interaction: discord.Interaction) -> bool:
    if interaction.guild_id is None:
        await interaction.response.send_message(
            "Raids and leaderboards are per-server -- run this in a server channel, not a DM.",
            ephemeral=True,
        )
        return True
    return False


def _guild_member_ids(interaction: discord.Interaction) -> list[int]:
    """Discord ids of everyone in this server, used to scope leaderboards
    (see leaderboard_service's SCOPE note). Falls back to just the caller
    if the member cache isn't populated -- a board of one is a poor board
    but an intelligible one, which beats an error."""
    guild = interaction.guild
    if guild is None:
        return [interaction.user.id]
    ids = [m.id for m in guild.members if not m.bot]
    return ids or [interaction.user.id]


# ----------------------------------------------------------------------
# Raid views
# ----------------------------------------------------------------------

class RaidSummonButton(discord.ui.DynamicItem[discord.ui.Button], template=r"cascade_raid_summon:(?P<tier>\w+)"):
    def __init__(self, tier_id: str, label: str = "...", disabled: bool = False):
        super().__init__(discord.ui.Button(
            label=label[:80],
            style=discord.ButtonStyle.danger if not disabled else discord.ButtonStyle.secondary,
            custom_id=f"cascade_raid_summon:{tier_id}",
            disabled=disabled,
        ))
        self.tier_id = tier_id

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(match["tier"])

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
                raid = raid_service.start_raid(db, player, interaction.guild_id, self.tier_id)
            except raid_service.RaidError as exc:
                await interaction.response.send_message(str(exc), ephemeral=True)
                return

            embed = embedder.raid_status_embed(
                raid, raid_service.leaderboard(db, raid), viewer_id=player.id,
                attacks_left=raid_service.attacks_remaining(db, raid, player),
            )
            # Sent to the channel rather than edited in place: a summon is
            # a server-wide event, and the whole point is that other
            # people find out about it.
            await interaction.response.edit_message(
                content=f"🐉 **{interaction.user.display_name}** summoned a raid! Everyone can join in with `/raid`.",
                embed=embed, view=RaidActionView(owner_id=player.id),
            )
        finally:
            db.close()


class RaidMenuView(OwnedView):
    def __init__(self, available_tier_ids: set[str], owner_id: int | None = None):
        super().__init__(timeout=300, owner_id=owner_id)
        for tier in RAID_TIERS:
            unlocked = tier["id"] in available_tier_ids
            label = f"{tier['emoji']} Summon {tier['name']}" if unlocked else f"🔒 {tier['name']}"
            self.add_item(RaidSummonButton(tier["id"], label, disabled=not unlocked))


class RaidActionView(OwnedView):
    """The live-raid controls. NOT owner-locked in the usual sense --
    every member of the server is supposed to be able to attack the same
    raid, so Attack/Refresh deliberately re-derive the acting player from
    interaction.user rather than trusting who opened the message."""

    def __init__(self, owner_id: int | None = None, defeated: bool = False):
        super().__init__(timeout=None, owner_id=None)  # owner_id=None -> anyone may press
        self._defeated = defeated
        if defeated:
            self.remove_item(self.attack_button)
        else:
            self.remove_item(self.claim_button)

    @discord.ui.button(label="⚔️ Attack", style=discord.ButtonStyle.danger, custom_id="cascade_raid_attack")
    async def attack_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _handle_raid_attack(interaction)

    @discord.ui.button(label="🎁 Claim Rewards", style=discord.ButtonStyle.success, custom_id="cascade_raid_claim")
    async def claim_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _handle_raid_claim(interaction)

    @discord.ui.button(label="🔄 Refresh", style=discord.ButtonStyle.secondary, custom_id="cascade_raid_refresh")
    async def refresh_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _handle_raid_refresh(interaction)

    @discord.ui.button(label="📊 Reward Tiers", style=discord.ButtonStyle.secondary, custom_id="cascade_raid_tiers")
    async def tiers_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(embed=embedder.raid_tiers_help_embed(), ephemeral=True)


# ----------------------------------------------------------------------
# Raid combat views (mirrors domains.py -- see the module docstring)
# ----------------------------------------------------------------------

class RaidAbilitySelect(discord.ui.Select):
    def __init__(self, options: list[discord.SelectOption]):
        super().__init__(
            placeholder="Use a skill (costs SP)...", options=options,
            custom_id="cascade_raid_ability_select", min_values=1, max_values=1,
        )

    async def callback(self, interaction: discord.Interaction):
        await _handle_combat_action(interaction, "ability", ability_id=self.values[0])


class RaidAllySelect(discord.ui.Select):
    """Support-target picker -- see AllySelect in bot/cogs/dungeon.py."""

    def __init__(self, options: list[discord.SelectOption]):
        super().__init__(
            placeholder="💚 Support target...", options=options,
            custom_id="cascade_raid_ally_select", min_values=1, max_values=1,
        )

    async def callback(self, interaction: discord.Interaction):
        raw = self.values[0]
        await _handle_select_ally(interaction, None if raw == "auto" else int(raw))


class RaidCombatView(OwnedView):
    def __init__(
        self,
        ability_options: list[discord.SelectOption] | None = None,
        ultimate_ready: bool = False,
        ultimate_exists: bool = False,
        ultimate_energy: int = 0,
        ultimate_cost: int = 50,
        owner_id: int | None = None,
        ally_options: list[discord.SelectOption] | None = None,
    ):
        super().__init__(timeout=None, owner_id=owner_id)
        self.ultimate_button.disabled = not ultimate_ready
        if ultimate_exists:
            status = "Ready!" if ultimate_ready else f"{ultimate_energy}/{ultimate_cost} EN"
            self.ultimate_button.label = f"💥 Ultimate ({status})"
        else:
            self.remove_item(self.ultimate_button)
        if ability_options:
            self.add_item(RaidAbilitySelect(ability_options))
        if ally_options:
            self.add_item(RaidAllySelect(ally_options))

    @discord.ui.button(label="⚔️ Attack", style=discord.ButtonStyle.danger, custom_id="cascade_raid_c_attack")
    async def attack_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _handle_combat_action(interaction, "attack")

    @discord.ui.button(label="💥 Ultimate", style=discord.ButtonStyle.success, custom_id="cascade_raid_c_ultimate")
    async def ultimate_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _handle_combat_action(interaction, "ultimate")

    @discord.ui.button(label="🛡️ Guard", style=discord.ButtonStyle.primary, custom_id="cascade_raid_c_guard")
    async def guard_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _handle_combat_action(interaction, "guard")

    @discord.ui.button(label="ℹ️ Info", style=discord.ButtonStyle.secondary, custom_id="cascade_raid_c_info", row=4)
    async def info_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        battle = raid_service.get_active_battle(interaction.user.id)
        if battle is None:
            await interaction.response.send_message("You're not in a raid attack right now.", ephemeral=True)
            return
        embed, view = combat_ui.info_response(battle)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="📜 Log", style=discord.ButtonStyle.secondary, custom_id="cascade_raid_c_log", row=4)
    async def log_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        battle = raid_service.get_active_battle(interaction.user.id)
        if battle is None:
            await interaction.response.send_message("You're not in a raid attack right now.", ephemeral=True)
            return
        await interaction.response.send_message(embed=embedder.battle_log_embed(battle), ephemeral=True)

    @discord.ui.button(label="🏳️ Retreat", style=discord.ButtonStyle.secondary, custom_id="cascade_raid_c_retreat", row=4)
    async def retreat_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _handle_retreat(interaction)


def _build_raid_combat_view(battle, owner_id: int) -> RaidCombatView:
    actor = battle.current_actor()
    ability_options = []
    for ability in actor.active_abilities:
        ready = actor.ability_ready(ability)
        unit = "SP" if ability["resource_type"] == "mana" else "EN"
        if ready:
            status = "Ready"
        else:
            cd = actor.cooldowns.get(ability["id"], 0)
            if cd > 0:
                status = f"ready in {cd}t"
            else:
                pool = actor.mana if ability["resource_type"] == "mana" else actor.energy
                status = f"need {ability['resource_cost'] - pool} more {unit}"
        ability_options.append(discord.SelectOption(
            label=f"{ability['name']} -- {ability['resource_cost']} {unit} ({status})"[:100],
            value=ability["id"], description=ability["description"][:100],
        ))

    ally_options = combat_ui.ally_select_options(battle) if combat_ui.should_offer_ally_select(battle) else []

    return RaidCombatView(
        ability_options or None,
        ultimate_ready=actor.ultimate_ready(),
        ultimate_exists=actor.ultimate_ability is not None,
        ultimate_energy=actor.energy,
        ultimate_cost=actor.ultimate_ability["resource_cost"] if actor.ultimate_ability else 50,
        owner_id=owner_id,
        ally_options=ally_options or None,
    )


def _advance_raid_battle(battle) -> bool:
    """Burns through consecutive enemy turns until it's a party member's
    turn or the fight ends. Returns True if the battle is over."""
    while not battle.is_over() and battle.current_actor() in battle.enemies:
        battle.take_enemy_turn()
    return battle.is_over()


# ----------------------------------------------------------------------
# Handlers
# ----------------------------------------------------------------------

async def _handle_raid_attack(interaction: discord.Interaction):
    if await _reject_dm(interaction):
        return
    db = SessionLocal()
    try:
        player = get_player(db, interaction.user.id)
        if player is None:
            await interaction.response.send_message("Use `/start` first.", ephemeral=True)
            return

        expedition = dungeon_service.get_active_expedition(db, player.id)
        if dungeon_service.is_in_combat(expedition):
            await interaction.response.send_message(
                "You're already in an expedition battle -- finish that first.", ephemeral=True
            )
            return

        raid = raid_service.get_active_raid(db, interaction.guild_id)
        if raid is None:
            await interaction.response.send_message("There's no raid running right now.", ephemeral=True)
            return

        try:
            battle = raid_service.start_attack(db, player, raid)
        except raid_service.RaidError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        over = _advance_raid_battle(battle)
        embed = embedder.combat_embed(battle, avatar_url=interaction.user.display_avatar.url)

        if over:
            result = raid_service.resolve_attack(db, player)
            # Ephemeral: the fight is this one player's, but the RESULT
            # is server news, so the outcome embed goes to the channel.
            await interaction.response.send_message(embed=embed, ephemeral=True)
            await interaction.followup.send(embed=embedder.raid_attack_result_embed(result))
        else:
            await interaction.response.send_message(
                embed=embed, view=_build_raid_combat_view(battle, player.id), ephemeral=True
            )
    finally:
        db.close()


async def _handle_combat_action(interaction: discord.Interaction, action: str, ability_id: str | None = None):
    db = SessionLocal()
    try:
        player = get_player(db, interaction.user.id)
        battle = raid_service.get_active_battle(interaction.user.id) if player else None
        if player is None or battle is None:
            await interaction.response.send_message("You're not in a raid attack right now.", ephemeral=True)
            return
        if battle.current_actor() not in battle.party:
            await interaction.response.send_message("It's not your turn yet.", ephemeral=True)
            return

        battle.take_party_action(action, ability_id=ability_id)
        over = _advance_raid_battle(battle)
        embed = embedder.combat_embed(battle, avatar_url=interaction.user.display_avatar.url)

        if over:
            result = raid_service.resolve_attack(db, player)
            await interaction.response.edit_message(embed=embed, view=None)
            await interaction.followup.send(embed=embedder.raid_attack_result_embed(result))
        else:
            await interaction.response.edit_message(
                embed=embed, view=_build_raid_combat_view(battle, player.id)
            )
    finally:
        db.close()


async def _handle_select_ally(interaction: discord.Interaction, party_index: int | None):
    """Free action -- see dungeon.py::_handle_select_ally. Like domains,
    a raid attack's Battle lives in memory only, so mutating it is the
    whole persistence step."""
    battle = raid_service.get_active_battle(interaction.user.id)
    if battle is None:
        await interaction.response.send_message("You're not in a raid attack right now.", ephemeral=True)
        return
    if battle.current_actor() not in battle.party:
        await interaction.response.send_message("It's not your turn yet.", ephemeral=True)
        return

    battle.select_ally_target(party_index)
    await interaction.response.edit_message(
        embed=embedder.combat_embed(battle, avatar_url=interaction.user.display_avatar.url),
        view=_build_raid_combat_view(battle, interaction.user.id),
    )


async def _handle_retreat(interaction: discord.Interaction):
    db = SessionLocal()
    try:
        player = get_player(db, interaction.user.id)
        if player is None or not raid_service.has_active_attack(player.id):
            await interaction.response.send_message("You're not in a raid attack right now.", ephemeral=True)
            return
        result = raid_service.resolve_attack(db, player)
        await interaction.response.edit_message(
            content="You pull back -- but the damage you already did still counts.",
            embed=embedder.raid_attack_result_embed(result), view=None,
        )
    finally:
        db.close()


async def _handle_raid_refresh(interaction: discord.Interaction):
    if await _reject_dm(interaction):
        return
    db = SessionLocal()
    try:
        player = get_player(db, interaction.user.id)
        if player is None:
            await interaction.response.send_message("Use `/start` first.", ephemeral=True)
            return
        raid = raid_service.get_active_raid(db, interaction.guild_id)
        if raid is None:
            await interaction.response.send_message(
                "That raid is over. Use `/raid` to see what's next.", ephemeral=True
            )
            return
        embed = embedder.raid_status_embed(
            raid, raid_service.leaderboard(db, raid), viewer_id=player.id,
            attacks_left=raid_service.attacks_remaining(db, raid, player),
        )
        await interaction.response.edit_message(
            embed=embed, view=RaidActionView(defeated=raid.status == "defeated")
        )
    finally:
        db.close()


async def _handle_raid_claim(interaction: discord.Interaction):
    if await _reject_dm(interaction):
        return
    db = SessionLocal()
    try:
        player = get_player(db, interaction.user.id)
        if player is None:
            await interaction.response.send_message("Use `/start` first.", ephemeral=True)
            return

        claimable = raid_service.claimable_raids(db, player, interaction.guild_id)
        if not claimable:
            await interaction.response.send_message(
                "You've got nothing to claim right now.", ephemeral=True
            )
            return

        embeds = []
        for raid in claimable:
            try:
                result = raid_service.claim_reward(db, player, raid)
            except raid_service.RaidError:
                continue
            embeds.append(embedder.raid_claim_embed(result, raid))

        if not embeds:
            await interaction.response.send_message("You've got nothing to claim right now.", ephemeral=True)
            return
        await interaction.response.send_message(embeds=embeds[:10], ephemeral=True)
    finally:
        db.close()


# ----------------------------------------------------------------------
# Leaderboard view
# ----------------------------------------------------------------------

class LeaderboardSelect(discord.ui.Select):
    def __init__(self, current: str):
        super().__init__(
            placeholder="Switch board...",
            options=[
                discord.SelectOption(label=label, value=key, description=desc[:100], default=(key == current))
                for key, label, desc in leaderboard_service.BOARDS
            ],
            custom_id="cascade_leaderboard_select", min_values=1, max_values=1,
        )

    async def callback(self, interaction: discord.Interaction):
        await _handle_leaderboard(interaction, self.values[0], edit=True)


class LeaderboardView(OwnedView):
    def __init__(self, current: str, owner_id: int | None = None):
        super().__init__(timeout=300, owner_id=owner_id)
        self.add_item(LeaderboardSelect(current))


async def _handle_leaderboard(interaction: discord.Interaction, board: str, edit: bool = False):
    if await _reject_dm(interaction):
        return
    db = SessionLocal()
    try:
        member_ids = _guild_member_ids(interaction)
        data = leaderboard_service.get_board(db, board, member_ids, viewer_id=interaction.user.id)
        data["viewer_id"] = interaction.user.id
        label, desc = next(
            ((lbl, d) for key, lbl, d in leaderboard_service.BOARDS if key == board),
            ("Leaderboard", ""),
        )
        embed = embedder.leaderboard_embed(data, label, desc, interaction.guild.name)
        view = LeaderboardView(board, owner_id=interaction.user.id)
        if edit:
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            await interaction.response.send_message(embed=embed, view=view)
    finally:
        db.close()


@guild_decorator
class Raids(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="raid", description="Take on this server's co-op raid boss with everyone else.")
    async def raid(self, ctx: discord.Interaction):
        if await _reject_dm(ctx):
            return
        db = SessionLocal()
        try:
            player = get_player(db, ctx.user.id)
            if not await require_player(ctx, player):
                return

            raid = raid_service.get_active_raid(db, ctx.guild_id)
            if raid is not None:
                embed = embedder.raid_status_embed(
                    raid, raid_service.leaderboard(db, raid), viewer_id=player.id,
                    attacks_left=raid_service.attacks_remaining(db, raid, player),
                )
                view = RaidActionView(defeated=False)
                await ctx.response.send_message(embed=embed, view=view)
                return

            # No active raid -- but there may be a finished one still owing
            # this player a reward. Surfacing it here is the only way
            # someone who was offline when it died ever finds out.
            claimable = raid_service.claimable_raids(db, player, ctx.guild_id)
            available = raid_service.available_tiers(db, player)
            roster = domain_service.roster_total_levels(db, player)
            embed = embedder.raid_menu_embed(available, roster)
            if claimable:
                embed.add_field(
                    name="🎁 Unclaimed rewards",
                    value=f"You have rewards waiting from {len(claimable)} finished raid(s) -- use `/raid_claim`.",
                    inline=False,
                )
            view = RaidMenuView({t["id"] for t in available}, owner_id=player.id)
            await ctx.response.send_message(embed=embed, view=view)
        finally:
            db.close()

    @app_commands.command(name="raid_claim", description="Claim your share of rewards from finished raids.")
    async def raid_claim(self, ctx: discord.Interaction):
        await _handle_raid_claim(ctx)

    @app_commands.command(name="leaderboard", description="See how you rank against everyone else in this server.")
    @app_commands.choices(board=[
        app_commands.Choice(name="Squad Power", value="squad_power"),
        app_commands.Choice(name="Roster Levels", value="roster"),
        app_commands.Choice(name="Deepest Clear", value="deepest"),
        app_commands.Choice(name="Collection", value="collection"),
    ])
    async def leaderboard(self, ctx: discord.Interaction, board: str = leaderboard_service.DEFAULT_BOARD):
        await _handle_leaderboard(ctx, board)


async def setup(bot):
    await bot.add_cog(Raids(bot))
