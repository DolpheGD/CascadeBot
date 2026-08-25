"""
/challenge -- fight another player's squad, offline.

The opponent is not playing. Their squad is rebuilt from their current
roster at the moment the fight starts and handed to the ordinary enemy
AI; nothing happens on their side, they are not notified, and they cannot
lose anything. It is a single-player fight whose enemies somebody else
assembled.

Battle handling mirrors bot/cogs/domains.py closely and for the same
reason: a challenge is one self-contained in-memory battle, not an
expedition with persisted combat_state, so it follows the pattern built
for exactly that shape rather than the dungeon's.
"""

import discord

from discord.ext import commands
from discord import app_commands

from bot.database.session import SessionLocal
from bot.game.economy.challenge_config import (
    MILESTONES,
    REWARDED_CHALLENGES_PER_DAY,
)
from bot.services import challenge_service
from bot.services.currency_service import format_currency
from bot.services.player_service import get_player
from bot.utils import combat_ui, embedder, responses
from bot.utils.guild_decorator import guild_decorator
from bot.utils.ui_guard import OwnedView, require_feature, require_player


# ----------------------------------------------------------------------
# Opponent selection
# ----------------------------------------------------------------------

def _cycle_field(player) -> tuple[str, str]:
    """This cycle's progress, as (field name, field value).

    THE MILESTONE LADDER IS SHOWN IN FULL, not just the next rung. The
    whole reason the mode uses milestones rather than a leaderboard is
    that the deal is knowable in advance -- hiding all but the next step
    would turn a contract back into a surprise, which is the thing it was
    chosen instead of.
    """
    points = int(player.challenge_points or 0)
    ends = challenge_service.cycle_ends_at()
    lines = [
        f"**{points:,} points** this cycle  ·  "
        f"resets {discord.utils.format_dt(ends, 'R')}",
        "",
    ]
    for threshold, label, _ in MILESTONES:
        if points >= threshold:
            lines.append(f"✅ **{label}** — {threshold:,}")
        else:
            lines.append(f"▫️ {label} — {threshold:,}  "
                         f"*({threshold - points:,} to go)*")
    return "This cycle", "\n".join(lines)


def _lobby_embed(db, player, opponents) -> discord.Embed:
    # ROLL THE CYCLE OVER BEFORE READING ANYTHING OFF THE PLAYER.
    #
    # sync_cycle moves a finished cycle's points into the bank, and until
    # it runs, `challenge_points` still holds last week's total. This
    # function used to read the points first and call claimable() second
    # -- so on the one screen that matters, the week you just finished
    # was rendered TWICE: 175 points "this cycle", and 175 points waiting
    # to be claimed, which reads as 350 points and one of them about to
    # vanish.
    #
    # Refreshing first makes every field below agree, because they are
    # all reading the same state instead of straddling the moment it
    # changes. refresh_power commits, which persists the rollover.
    challenge_service.sync_cycle(player)
    power = challenge_service.refresh_power(db, player)
    remaining = challenge_service.rewards_remaining(player)
    wins = int(player.challenge_wins or 0)
    losses = int(player.challenge_losses or 0)

    embed = discord.Embed(
        title="🥊 Squad Challenges",
        description=(
            "Fight another player's squad. They aren't online for it — you're "
            "facing however their team is built right now, run by the same AI "
            "as any other enemy.\n\n"
            f"**Your power:** {power:,}  ·  **Record:** {wins}W / {losses}L\n"
            f"**Rewarded fights left today:** {remaining}/"
            f"{REWARDED_CHALLENGES_PER_DAY}"
        ),
        colour=discord.Colour.red(),
    )

    name, value = _cycle_field(player)
    embed.add_field(name=name, value=value[:1024], inline=False)

    banked, earned = challenge_service.claimable(player)
    if earned:
        embed.add_field(
            name="🎁 Last cycle is ready to claim",
            value=(f"You finished on **{banked:,} points** and earned "
                   f"**{earned[-1][1]}**.\nPress **Claim** below."),
            inline=False)
    if opponents:
        lines = []
        for opponent in opponents:
            multiplier = challenge_service.reward_multiplier(
                power, int(opponent.challenge_power or 0))
            lines.append(
                f"**{opponent.username or 'Someone'}** — power "
                f"{int(opponent.challenge_power or 0):,} · rewards ×{multiplier:.2f}")
        embed.add_field(name="Opponents", value="\n".join(lines), inline=False)
    else:
        embed.add_field(
            name="Opponents",
            value="*Nobody to fight yet — more players need to build a squad.*",
            inline=False)
    return embed


class ChallengeLobbyView(OwnedView):
    def __init__(self, opponents, owner_id: int | None = None,
                 can_claim: bool = False):
        super().__init__(timeout=300, owner_id=owner_id)
        if opponents:
            self.add_item(_OpponentSelect(opponents))
        if can_claim:
            self.add_item(_ClaimButton())


class _ClaimButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Claim last cycle", emoji="🎁",
                         style=discord.ButtonStyle.success)

    async def callback(self, interaction: discord.Interaction):
        db = SessionLocal()
        try:
            player = get_player(db, interaction.user.id)
            if player is None:
                await responses.send(interaction, "Use `/start` first.",
                                     ephemeral=True)
                return
            try:
                result = challenge_service.claim_cycle(db, player)
            except challenge_service.ChallengeError as exc:
                # Reached by pressing a stale button from a message that
                # is still sitting in the channel from last week. The
                # service refuses it; this is only how the refusal gets
                # said out loud.
                await responses.send(interaction, str(exc), ephemeral=True)
                return

            embed = discord.Embed(
                title="🎁 Cycle claimed",
                description=(
                    f"**{result['points']:,} points** — "
                    + ", ".join(m[1] for m in result["milestones"])),
                colour=discord.Colour.gold(),
            )
            embed.add_field(
                name="Rewards",
                value=", ".join(format_currency(c, a)
                                for c, a in result["rewards"].items()),
                inline=False)
            opponents = challenge_service.find_opponents(db, player)
            await responses.edit(
                interaction,
                embed=_lobby_embed(db, player, opponents),
                view=ChallengeLobbyView(opponents, player.id, can_claim=False))
            await interaction.followup.send(embed=embed)
        finally:
            db.close()


class _OpponentSelect(discord.ui.Select):
    def __init__(self, opponents):
        # Sliced to Discord's cap even though matchmaking returns three --
        # an unpaged select is what took the equip button down with a 400
        # that surfaced only as a dead interaction.
        super().__init__(
            placeholder="Pick an opponent…",
            options=[
                discord.SelectOption(
                    label=(o.username or f"Player {o.id}")[:100],
                    value=str(o.id),
                    description=f"Power {int(o.challenge_power or 0):,}"[:100],
                )
                for o in opponents[:25]
            ],
        )

    async def callback(self, interaction: discord.Interaction):
        db = SessionLocal()
        try:
            player = get_player(db, interaction.user.id)
            if player is None:
                await responses.send(interaction, "Use `/start` first.", ephemeral=True)
                return
            from bot.database.models.player_model import Player
            defender = db.query(Player).filter_by(id=int(self.values[0])).one_or_none()
            if defender is None:
                await responses.send(interaction, "That player is gone.", ephemeral=True)
                return
            try:
                battle = challenge_service.start_challenge(db, player, defender)
            except challenge_service.ChallengeError as exc:
                await responses.send(interaction, str(exc), ephemeral=True)
                return

            # An opponent faster than the whole squad would otherwise act
            # before the player ever sees the screen.
            summary = _advance(db, player, battle)
            avatar_url = interaction.user.display_avatar.url
            if summary is not None:
                await responses.edit(
                    interaction,
                    embed=embedder.combat_embed(battle, avatar_url=avatar_url),
                    view=None)
                await interaction.followup.send(embed=_result_embed(summary))
            else:
                await responses.edit(
                    interaction,
                    embed=embedder.combat_embed(battle, avatar_url=avatar_url),
                    view=_build_combat_view(battle, player.id))
        finally:
            db.close()


# ----------------------------------------------------------------------
# Combat
# ----------------------------------------------------------------------

def _advance(db, player, battle):
    """Resolve enemy turns until it's the player's move or it's over."""
    while not battle.is_over() and battle.current_actor() in battle.enemies:
        battle.take_enemy_turn()
    if battle.is_over():
        return challenge_service.finish_challenge(db, player)
    return None


def _result_embed(summary: dict) -> discord.Embed:
    won = summary["won"]
    defender = summary["defender"]
    embed = discord.Embed(
        title="🏆 Challenge won" if won else "💀 Challenge lost",
        description=(f"You beat **{defender.username or 'them'}**'s squad."
                     if won else
                     f"**{defender.username or 'Their'}** squad held."),
        colour=discord.Colour.green() if won else discord.Colour.dark_red(),
    )
    rewards = summary.get("rewards") or {}
    if rewards:
        embed.add_field(
            name=f"Rewards (×{summary['multiplier']:.2f})",
            value=", ".join(format_currency(c, a) for c, a in rewards.items()),
            inline=False)

    # The points line matters more than the reward line now that most of
    # the mode's value sits in the cycle claim -- it is the part that
    # accumulates, and a fight that only showed its gold would understate
    # what it was actually worth.
    if summary.get("points"):
        cycle_points = summary.get("cycle_points", 0)
        upcoming = challenge_service.next_milestone(cycle_points)
        line = f"**+{summary['points']} points** · {cycle_points:,} this cycle"
        if upcoming:
            line += (f"\n{upcoming[0] - cycle_points:,} more to "
                     f"**{upcoming[1]}**")
        else:
            line += "\nEvery milestone this cycle is earned."
        embed.add_field(name="Cycle", value=line, inline=False)
    elif not summary.get("paid"):
        embed.add_field(
            name="No rewards",
            value=(f"You've had your {REWARDED_CHALLENGES_PER_DAY} rewarded "
                   f"fights today. You can keep fighting for fun."),
            inline=False)
    return embed


def _build_combat_view(battle, owner_id: int):
    actor = battle.current_actor()
    if actor is None or actor not in battle.party:
        return None
    ability_options = combat_ui.ability_select_options(actor)
    target_options = combat_ui.enemy_target_options(battle)
    ally_options = (combat_ui.ally_select_options(battle)
                    if combat_ui.should_offer_ally_select(battle) else [])
    return ChallengeCombatView(
        ability_options or None,
        target_options or None,
        ultimate_ready=actor.ultimate_ready(),
        ultimate_exists=actor.ultimate_ability is not None,
        ultimate_energy=actor.energy,
        ultimate_cost=(actor.ultimate_ability["resource_cost"]
                       if actor.ultimate_ability else 100),
        ultimate_label=combat_ui.ultimate_button_label(actor),
        owner_id=owner_id,
        ally_options=ally_options or None,
    )


class ChallengeAbilitySelect(discord.ui.Select):
    def __init__(self, options):
        super().__init__(placeholder="✨ Ability...", options=options,
                         custom_id="cascade_challenge_ability",
                         min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        await _handle_action(interaction, "ability", ability_id=self.values[0])


class ChallengeTargetSelect(discord.ui.Select):
    def __init__(self, options):
        super().__init__(placeholder="🎯 Target...", options=options,
                         custom_id="cascade_challenge_target",
                         min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        await _handle_target(interaction, int(self.values[0]))


class ChallengeAllySelect(discord.ui.Select):
    def __init__(self, options):
        super().__init__(placeholder="💚 Support target...", options=options,
                         custom_id="cascade_challenge_ally",
                         min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        raw = self.values[0]
        await _handle_ally(interaction, None if raw == "auto" else int(raw))


class ChallengeCombatView(OwnedView):
    def __init__(self, ability_options=None, target_options=None,
                 ultimate_ready=False, ultimate_exists=False,
                 ultimate_energy=0, ultimate_cost=100, ultimate_label=None,
                 owner_id=None, ally_options=None):
        super().__init__(timeout=None, owner_id=owner_id)
        self.attack_button.disabled = False
        self.ultimate_button.disabled = not ultimate_ready
        if ultimate_exists:
            self.ultimate_button.label = ultimate_label or (
                f"💥 Ultimate ({'Ready!' if ultimate_ready else f'{ultimate_energy}/{ultimate_cost} EN'})")
        else:
            self.remove_item(self.ultimate_button)
        if ability_options:
            self.add_item(ChallengeAbilitySelect(ability_options))
        if target_options:
            self.add_item(ChallengeTargetSelect(target_options))
        if ally_options:
            self.add_item(ChallengeAllySelect(ally_options))

    @discord.ui.button(label="⚔️ Attack", style=discord.ButtonStyle.danger,
                       custom_id="cascade_challenge_attack")
    async def attack_button(self, interaction, button):
        await _handle_action(interaction, "attack")

    @discord.ui.button(label="💥 Ultimate", style=discord.ButtonStyle.success,
                       custom_id="cascade_challenge_ultimate")
    async def ultimate_button(self, interaction, button):
        await _handle_action(interaction, "ultimate")

    @discord.ui.button(label="🛡️ Guard", style=discord.ButtonStyle.primary,
                       custom_id="cascade_challenge_guard")
    async def guard_button(self, interaction, button):
        await _handle_action(interaction, "guard")


async def _handle_action(interaction: discord.Interaction, action: str,
                         ability_id: str | None = None):
    db = SessionLocal()
    try:
        player = get_player(db, interaction.user.id)
        battle = (challenge_service.get_active_battle(interaction.user.id)
                  if player else None)
        if player is None or battle is None:
            await responses.send(interaction, "You're not in a challenge right now.",
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
                interaction,
                embed=embedder.combat_embed(battle, avatar_url=avatar_url), view=None)
            await interaction.followup.send(embed=_result_embed(summary))
        else:
            await responses.edit(
                interaction,
                embed=embedder.combat_embed(battle, avatar_url=avatar_url),
                view=_build_combat_view(battle, player.id))
    finally:
        db.close()


async def _handle_target(interaction: discord.Interaction, target_index: int):
    battle = challenge_service.get_active_battle(interaction.user.id)
    if battle is None or battle.current_actor() not in battle.party:
        await responses.send(interaction, "It's not your turn yet.", ephemeral=True)
        return
    battle.select_target(target_index)
    await responses.edit(
        interaction,
        embed=embedder.combat_embed(battle,
                                    avatar_url=interaction.user.display_avatar.url),
        view=_build_combat_view(battle, interaction.user.id))


async def _handle_ally(interaction: discord.Interaction, party_index: int | None):
    battle = challenge_service.get_active_battle(interaction.user.id)
    if battle is None or battle.current_actor() not in battle.party:
        await responses.send(interaction, "It's not your turn yet.", ephemeral=True)
        return
    battle.select_ally_target(party_index)
    await responses.edit(
        interaction,
        embed=embedder.combat_embed(battle,
                                    avatar_url=interaction.user.display_avatar.url),
        view=_build_combat_view(battle, interaction.user.id))


@guild_decorator
class Challenge(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # COMMAND: /challenge
    # Pick an opponent near your power and fight their squad.
    @app_commands.command(
        name="challenge",
        description="Fight another player's squad. They don't need to be online."
    )
    async def challenge(self, ctx: discord.Interaction):
        await responses.defer(ctx)
        db = SessionLocal()
        try:
            player = get_player(db, ctx.user.id)
            if not await require_player(ctx, player):
                return
            # Gated on `adventure`, NOT `squad`.
            #
            # `squad` unlocks at pr5_ops_deck -- roughly a third of the
            # way through the prologue, when the player owns one
            # character and has never chosen a team. Challenges would
            # technically work there (matchmaking bands by power, so they
            # would face other beginners) and would teach them nothing:
            # a one-character "squad" versus another is not the mode.
            #
            # `adventure` opens at pr11_the_gate, the end of the
            # prologue, by which point they have a real four-slot team,
            # some gear, and a reason to care how it compares.
            if not await require_feature(ctx, db, player, "adventure"):
                return

            existing = challenge_service.get_active_battle(player.id)
            if existing is not None and not existing.is_over():
                await responses.send(
                    ctx,
                    embed=embedder.combat_embed(
                        existing, avatar_url=ctx.user.display_avatar.url),
                    view=_build_combat_view(existing, player.id))
                return

            opponents = challenge_service.find_opponents(db, player)
            embed = _lobby_embed(db, player, opponents)
            # The claim button appears only when there is something to
            # claim. A button that exists year-round and refuses most of
            # the time trains people to ignore it, and this one is the
            # payoff for a week of play.
            _, earned = challenge_service.claimable(player)
            view = ChallengeLobbyView(opponents, owner_id=player.id,
                                      can_claim=bool(earned))
        finally:
            db.close()
        await responses.send(ctx, embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(Challenge(bot))
