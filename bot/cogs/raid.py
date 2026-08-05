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
from bot.game.economy.raid_config import (
    DEFAULT_RAID_DIFFICULTY,
    RAID_DIFFICULTIES,
    RAID_TIERS,
    get_tier as get_raid_tier,
    raid_boss_level,
)
from bot.utils import combat_ui, embedder
from bot.utils.guild_decorator import guild_decorator
from bot.utils.time_utils import describe_wait
from bot.utils.ui_guard import require_feature, OwnedView, check_message_owner, require_player


async def _reject_dm(interaction: discord.Interaction) -> bool:
    if interaction.guild_id is None:
        await interaction.response.send_message(
            "Raids and leaderboards are per-server -- run this in a server channel, not a DM.",
            ephemeral=True,
        )
        return True
    return False


def _guild_member_ids(db, interaction: discord.Interaction) -> list[int]:
    """Player ids eligible for this server's leaderboards.

    Read from OUR OWN record of who has played here (see
    presence_service), not from `guild.members`. The member cache is
    empty without the privileged `members` intent, which this bot
    doesn't request -- so the old version fell through to "just the
    caller" every single time and every board showed exactly one player.

    Anyone who has used the bot in this guild is included, plus the
    caller unconditionally so a brand-new player still sees themselves.
    If the members intent ever IS enabled, cached members are folded in
    as a bonus rather than being required."""
    from bot.services import presence_service

    if interaction.guild_id is None:
        return [interaction.user.id]

    ids = set(presence_service.player_ids_in_guild(
        db, interaction.guild_id, include=interaction.user.id
    ))
    guild = interaction.guild
    if guild is not None:
        ids.update(m.id for m in guild.members if not m.bot)
    return list(ids)


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
        await _handle_choose_difficulty(interaction)

    @discord.ui.button(label="🎁 Claim Rewards", style=discord.ButtonStyle.success, custom_id="cascade_raid_claim")
    async def claim_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _handle_raid_claim(interaction)

    @discord.ui.button(label="🔄 Refresh", style=discord.ButtonStyle.secondary, custom_id="cascade_raid_refresh")
    async def refresh_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _handle_raid_refresh(interaction)

    @discord.ui.button(label="📊 Rewards", style=discord.ButtonStyle.secondary, custom_id="cascade_raid_tiers")
    async def tiers_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Shows the real payout per band for the raid actually running,
        falling back to bare multipliers only if there's somehow no raid
        (e.g. a stale message from a raid that has since expired)."""
        tier = None
        if interaction.guild_id is not None:
            db = SessionLocal()
            try:
                raid = raid_service.get_active_raid(db, interaction.guild_id)
                if raid is not None:
                    tier = get_raid_tier(raid.tier)
            finally:
                db.close()
        await interaction.response.send_message(
            embed=embedder.raid_tiers_help_embed(tier), ephemeral=True
        )


# ----------------------------------------------------------------------
# Raid combat views (mirrors domains.py -- see the module docstring)
# ----------------------------------------------------------------------

class RaidDifficultySelect(discord.ui.Select):
    """Difficulty picker, shown ephemerally when Attack is pressed.

    Per-ATTACK rather than per-raid: one shared boss is fought by a whole
    server's worth of differently-geared players, so a single level is
    either unbeatable for the weakest or trivial for the strongest. See
    the block in bot/game/economy/raid_config.py."""

    def __init__(self, raid):
        options = []
        for d in RAID_DIFFICULTIES:
            level = raid_boss_level(raid.boss_level, d)
            options.append(discord.SelectOption(
                label=f"{d['name']} — Lv.{level} · {d['contribution_multiplier']}x credit",
                value=d["id"],
                emoji=d["emoji"],
                description=d["description"][:100],
                default=(d["id"] == DEFAULT_RAID_DIFFICULTY),
            ))
        super().__init__(placeholder="Choose your difficulty...", options=options,
                         min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        await _handle_raid_attack(interaction, self.values[0])


class RaidDifficultyView(discord.ui.View):
    """Short-lived and ephemeral -- it's a one-shot prompt, so there's
    nothing worth surviving a restart."""

    def __init__(self, raid):
        super().__init__(timeout=120)
        self.add_item(RaidDifficultySelect(raid))


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
        ultimate_label: str | None = None,
        owner_id: int | None = None,
        ally_options: list[discord.SelectOption] | None = None,
    ):
        super().__init__(timeout=None, owner_id=owner_id)
        self.ultimate_button.disabled = not ultimate_ready
        if ultimate_exists:
            # ultimate_label is built by combat_ui.ultimate_button_label,
            # which knows about the ultimate COOLDOWN as well as energy.
            # The energy-only fallback is for the persistent-view rebuild
            # path, which has no actor to ask.
            self.ultimate_button.label = ultimate_label or (
                f"💥 Ultimate ({'Ready!' if ultimate_ready else f'{ultimate_energy}/{ultimate_cost} EN'})"
            )
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
        ultimate_label=combat_ui.ultimate_button_label(actor),
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

async def _resume_raid_attack(interaction: discord.Interaction, db, player, battle) -> None:
    """Re-render an attack that's already in progress.

    A raid attack is shown in an EPHEMERAL message, and dismissing an
    ephemeral message is a completely ordinary thing to do -- but the
    battle lives on in raid_service._ACTIVE_BATTLES, so before this
    existed the player was simply locked out: `/raid` -> Attack raised
    "you're already in the middle of a raid attack", with no surface
    anywhere to finish it, retreat from it, or clear it. The attack had
    already been debited too, so it cost them a charge as well.

    Domains already handled exactly this case (see `/domains`); raids
    just never got the equivalent."""
    over = _advance_raid_battle(battle)
    embed = embedder.combat_embed(battle, avatar_url=interaction.user.display_avatar.url)
    if over:
        result = raid_service.resolve_attack(db, player)
        await interaction.response.send_message(
            content="Your raid attack had already finished.", embed=embed, ephemeral=True
        )
        await interaction.followup.send(embed=embedder.raid_attack_result_embed(result))
        return
    await interaction.response.send_message(
        content="Picking up your raid attack where you left off.",
        embed=embed, view=_build_raid_combat_view(battle, player.id), ephemeral=True,
    )


async def _handle_choose_difficulty(interaction: discord.Interaction):
    """Attack now opens a difficulty prompt rather than starting the fight
    directly. Every guard the attack itself would apply is checked here
    too, so a player is told they're out of attacks (or on cooldown)
    BEFORE picking a difficulty rather than after."""
    if await _reject_dm(interaction):
        return
    db = SessionLocal()
    try:
        player = get_player(db, interaction.user.id)
        if player is None:
            await interaction.response.send_message("Use `/start` first.", ephemeral=True)
            return

        existing = raid_service.get_active_battle(player.id)
        if existing is not None:
            await _resume_raid_attack(interaction, db, player, existing)
            return

        raid = raid_service.get_active_raid(db, interaction.guild_id)
        if raid is None:
            await interaction.response.send_message("There's no raid running right now.", ephemeral=True)
            return

        left = raid_service.attacks_remaining(db, raid, player)
        if left <= 0:
            await interaction.response.send_message(
                "You've used all your attacks on this raid. Someone else will have to finish it.",
                ephemeral=True,
            )
            return
        cooldown = raid_service.time_until_next_attack(db, raid, player)
        if cooldown is not None:
            await interaction.response.send_message(
                f"You're still regrouping -- {describe_wait(cooldown)} before your next attack.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            content=(
                f"**{raid.boss_name}** — pick how hard you want to fight it.\n"
                "Higher difficulty means a stronger boss but more contribution credit; "
                "lower means an easier fight that still counts.\n"
                f"*{left} attack(s) left.*"
            ),
            view=RaidDifficultyView(raid),
            ephemeral=True,
        )
    finally:
        db.close()


async def _handle_raid_attack(interaction: discord.Interaction, difficulty_id: str = DEFAULT_RAID_DIFFICULTY):
    if await _reject_dm(interaction):
        return
    db = SessionLocal()
    try:
        player = get_player(db, interaction.user.id)
        if player is None:
            await interaction.response.send_message("Use `/start` first.", ephemeral=True)
            return

        # Already mid-attack (usually: they dismissed the ephemeral combat
        # message). Resume rather than refusing -- refusing was a dead end.
        existing = raid_service.get_active_battle(player.id)
        if existing is not None:
            await _resume_raid_attack(interaction, db, player, existing)
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
            battle = raid_service.start_attack(db, player, raid, difficulty_id)
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
        if not await require_feature(interaction, db, player, "raids"):
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
        # The leaderboard is gated with the raids it ranks. Seeing where
        # you place among people playing systems you haven't been shown
        # yet is the opposite of the prologue's job.
        player = get_player(db, interaction.user.id)
        if player is None:
            await interaction.response.send_message("Use `/start` first.", ephemeral=True)
            return
        if not await require_feature(interaction, db, player, "raids"):
            return

        member_ids = _guild_member_ids(db, interaction)
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
            if not await require_feature(ctx, db, player, "raids"):
                return

            # An attack still open in memory takes priority over the raid
            # board -- otherwise `/raid` shows a board whose Attack button
            # can only refuse, which is the dead end this resume path
            # exists to close. See _resume_raid_attack.
            existing = raid_service.get_active_battle(player.id)
            if existing is not None:
                await _resume_raid_attack(ctx, db, player, existing)
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
