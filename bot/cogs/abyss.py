"""
/abyss -- the Void Abyss, the endgame mode.

A thin renderer over abyss_service: the cog never decides what happens,
it asks. Same discipline as /story, and the reason tools/check_abyss.py
can validate the whole ladder without Discord.

THE TEAM PICKER IS THE MODE. Everything else here is combat plumbing
reused from the story cog. What makes the Abyss the Abyss is that you
assign every chamber's team before the first fight and no character may
appear twice -- so the picker deliberately shows you, at all times, who
is already committed elsewhere.
"""

from __future__ import annotations

import discord

from discord.ext import commands
from discord import app_commands

from bot.database.session import SessionLocal
from bot.game.abyss import abyss_config as ac
from bot.game.combat.battle import Battle
from bot.game.combat.enemies import get_template_by_name
from bot.game.combat.factory import build_enemy_combatant, build_party_combatants
from bot.game.combat.serialization import battle_from_dict, battle_to_dict
from bot.services import abyss_service, character_service
from bot.services.player_service import get_player
from bot.utils import combat_ui, embedder
from bot.utils.guild_decorator import guild_decorator
from bot.utils.ui_guard import OwnedView, require_feature, require_player

ABYSS_COLOR = discord.Color.from_rgb(88, 24, 120)


def _overview_embed(db, player) -> discord.Embed:
    state = abyss_service.get_or_create(db, player)
    rotation = abyss_service.current_rotation()
    embed = discord.Embed(
        title="🕳️ The Void Abyss",
        description=(
            "Every floor is several chambers, and **no character may fight twice on the "
            "same floor**. Bring more than one team or don't come down.\n\n"
            f"⭐ **{abyss_service.total_stars(state)}/{ac.max_stars()}** stars"
        ),
        color=ABYSS_COLOR,
    )
    lines = []
    for floor in ac.FLOORS:
        stars = abyss_service.stars_on(state, floor["floor"])
        mark = "⭐" * stars + "▫️" * (ac.MAX_STARS_PER_FLOOR - stars)
        locked = abyss_service.floor_locked_reason(db, player, floor)
        tag = "🔒" if locked else ("🔁" if ac.is_rotating(floor) else "")
        reward = "" if not abyss_service.reward_available(state, floor) else " 🎁"
        lines.append(
            f"{mark} **{floor['floor']}. {floor['name']}** "
            f"({ac.chamber_count(floor)}×{ac.TEAM_SIZE}) {tag}{reward}"
        )
    embed.add_field(name="Floors", value="\n".join(lines)[:1024], inline=False)
    embed.add_field(
        name="🔁 Rotating floors",
        value=(
            f"Floors {ac.FIRST_ROTATING_FLOOR}–{ac.FLOORS[-1]['floor']} change every "
            f"**{ac.ROTATION_DAYS} days** and their rewards can be claimed once per "
            f"rotation.\n"
            f"Current rotation ends **{abyss_service.rotation_ends():%d %b}**.\n"
            "🎁 marks a floor whose reward is still unclaimed."
        ),
        inline=False,
    )
    embed.set_footer(text="⭐ clear · ⭐ under 12 cycles · ⭐ nobody dies")
    return embed


class AbyssView(OwnedView):
    def __init__(self, db, player, owner_id: int | None = None):
        super().__init__(timeout=600, owner_id=owner_id)
        options = []
        for floor in ac.FLOORS:
            locked = abyss_service.floor_locked_reason(db, player, floor)
            options.append(discord.SelectOption(
                label=f"{floor['floor']}. {floor['name']}"[:100],
                value=str(floor["floor"]),
                description=(("🔒 " if locked else "") +
                             f"{ac.chamber_count(floor)} chambers · lv{floor['level']}")[:100],
            ))
        self.add_item(_FloorSelect(options[:25]))


class _FloorSelect(discord.ui.Select):
    def __init__(self, options):
        super().__init__(placeholder="Choose a floor...", options=options,
                         min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        await _open_floor(interaction, int(self.values[0]))


async def _open_floor(interaction: discord.Interaction, floor_number: int):
    db = SessionLocal()
    try:
        player = get_player(db, interaction.user.id)
        if player is None:
            await interaction.response.send_message("Use `/start` first.", ephemeral=True)
            return
        floor = ac.get_floor(floor_number)
        locked = abyss_service.floor_locked_reason(db, player, floor)
        if locked:
            await interaction.response.send_message(locked, ephemeral=True)
            return
        state = abyss_service.get_or_create(db, player)
        rotation = abyss_service.current_rotation()
        chambers = ac.chambers_for(floor, rotation)
        embed = discord.Embed(
            title=f"🕳️ Floor {floor['floor']} — {floor['name']}",
            description=floor["blurb"],
            color=ABYSS_COLOR,
        )
        for index, enemies in enumerate(chambers, start=1):
            embed.add_field(
                name=f"Chamber {index}",
                value="\n".join(f"• {name}" for name in enemies) + f"\n*Level {floor['level']}*",
                inline=True,
            )
        embed.add_field(
            name="Requirement",
            value=(f"**{ac.characters_required(floor)} different characters** — "
                   f"{len(chambers)} teams of {ac.TEAM_SIZE}, no repeats."),
            inline=False,
        )
        if not abyss_service.reward_available(state, floor):
            embed.set_footer(text="Reward already claimed. Stars can still be improved.")
        view = _FloorEntryView(floor_number, owner_id=player.id)
    finally:
        db.close()
    await interaction.response.edit_message(embed=embed, view=view)


class _FloorEntryView(OwnedView):
    def __init__(self, floor_number: int, owner_id: int | None = None):
        super().__init__(timeout=600, owner_id=owner_id)
        self.floor_number = floor_number

    @discord.ui.button(label="⚔️ Assign teams", style=discord.ButtonStyle.primary)
    async def assign(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _render_picker(interaction, self.floor_number, {}, 0)

    @discord.ui.button(label="◀ Back", style=discord.ButtonStyle.secondary)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _render_overview(interaction, edit=True)


# ----------------------------------------------------------------------
# The team picker.
#
# One chamber at a time, and every character already committed to an
# EARLIER chamber is simply absent from the list. Showing them greyed out
# was the other option and it's worse: a 25-option Discord select filled
# with names you can't pick is harder to read than a short list of names
# you can.
# ----------------------------------------------------------------------

_PENDING: dict[tuple[int, int], dict[int, list[int]]] = {}


async def _render_picker(interaction: discord.Interaction, floor_number: int,
                         picked: dict[int, list[int]], chamber: int):
    db = SessionLocal()
    try:
        player = get_player(db, interaction.user.id)
        floor = ac.get_floor(floor_number)
        total = ac.chamber_count(floor)
        _PENDING[(interaction.user.id, floor_number)] = picked

        committed = {cid for team in picked.values() for cid in team}
        owned = [pc for pc in character_service.list_owned_characters(db, player)
                 if pc.id not in committed]
        rotation = abyss_service.current_rotation()
        enemies = ac.chambers_for(floor, rotation)[chamber]

        embed = discord.Embed(
            title=f"Chamber {chamber + 1} of {total} — Floor {floor_number}",
            description=(
                "**" + ", ".join(enemies) + f"** · Level {floor['level']}\n\n"
                f"Pick up to {ac.TEAM_SIZE}. Anyone you commit here cannot be used in "
                "another chamber."
            ),
            color=ABYSS_COLOR,
        )
        if picked:
            done = []
            for index in sorted(picked):
                names = [pc.display_name for pc in
                         character_service.list_owned_characters(db, player)
                         if pc.id in picked[index]]
                done.append(f"**Chamber {index + 1}:** " + ", ".join(names))
            embed.add_field(name="Committed", value="\n".join(done)[:1024], inline=False)
        embed.set_footer(text=f"{len(owned)} characters still available")
        view = _PickerView(floor_number, chamber, total, owned, owner_id=player.id)
    finally:
        db.close()
    await interaction.response.edit_message(embed=embed, view=view)


class _PickerView(OwnedView):
    def __init__(self, floor_number: int, chamber: int, total: int, owned: list,
                 owner_id: int | None = None):
        super().__init__(timeout=600, owner_id=owner_id)
        self.floor_number, self.chamber, self.total = floor_number, chamber, total
        options = [
            discord.SelectOption(
                label=f"{pc.display_name} (Lv{pc.level})"[:100],
                value=str(pc.id),
                description=f"{pc.template.star_rating}★ {pc.template.character_class.value}"[:100],
            )
            for pc in owned[:25]
        ]
        if options:
            self.add_item(_TeamSelect(options, min(ac.TEAM_SIZE, len(options))))


class _TeamSelect(discord.ui.Select):
    def __init__(self, options, max_values: int):
        super().__init__(placeholder="Choose this chamber's team...", options=options,
                         min_values=1, max_values=max_values)

    async def callback(self, interaction: discord.Interaction):
        view: _PickerView = self.view  # type: ignore[assignment]
        picked = _PENDING.get((interaction.user.id, view.floor_number), {})
        picked[view.chamber] = [int(v) for v in self.values]
        if view.chamber + 1 < view.total:
            await _render_picker(interaction, view.floor_number, picked, view.chamber + 1)
            return

        db = SessionLocal()
        try:
            player = get_player(db, interaction.user.id)
            teams = [picked[i] for i in sorted(picked)]
            try:
                abyss_service.begin_floor(db, player, view.floor_number, teams)
            except abyss_service.AbyssError as exc:
                await interaction.response.send_message(str(exc), ephemeral=True)
                return
        finally:
            db.close()
        _PENDING.pop((interaction.user.id, view.floor_number), None)
        await _render_chamber(interaction, edit=True)


# ----------------------------------------------------------------------
# Combat -- same load/mutate/save discipline as story battles.
# ----------------------------------------------------------------------

def _open_battle(db, player):
    chamber = abyss_service.current_chamber(db, player)
    if chamber is None:
        return None, None
    state = abyss_service.get_or_create(db, player)
    if state.combat_state:
        battle = battle_from_dict(state.combat_state)
    else:
        owned = {pc.id: pc for pc in character_service.list_owned_characters(db, player)}
        squad = [owned[cid] for cid in chamber["team"] if cid in owned]
        equipped = character_service.get_equipped_items_by_character(db, [c.id for c in squad])
        party = build_party_combatants(squad, equipped)
        for member in party:
            member.current_hp = member.max_hp
        enemies = [build_enemy_combatant(get_template_by_name(n), chamber["floor"]["level"])
                   for n in chamber["enemies"]]
        battle = Battle(party, enemies)
        state.combat_state = battle_to_dict(battle)
        db.commit()

    while not battle.is_over() and battle.current_actor() in battle.enemies:
        battle.take_enemy_turn()
    state.combat_state = battle_to_dict(battle)
    db.commit()
    embed = embedder.combat_embed(battle)
    embed.set_author(
        name=f"Void Abyss · Floor {chamber['floor']['floor']} · "
             f"Chamber {chamber['index'] + 1}/{chamber['total']}"
    )
    return embed, AbyssCombatView(owner_id=player.id, battle=battle)


class AbyssCombatView(OwnedView):
    def __init__(self, owner_id: int | None = None, battle: Battle | None = None):
        super().__init__(timeout=900, owner_id=owner_id)
        if battle is None:
            return
        actor = battle.current_actor()
        if actor is None or actor not in battle.party:
            return
        self.ultimate_button.disabled = not actor.ultimate_ready()
        self.ultimate_button.label = combat_ui.ultimate_button_label(actor)
        options = []
        for ability in actor.active_abilities:
            unit = "SP" if ability["resource_type"] == "mana" else "EN"
            status = "Ready" if actor.ability_ready(ability) else f"{ability['resource_cost']} {unit}"
            options.append(discord.SelectOption(
                label=f"{ability['name']} -- {status}"[:100],
                value=ability["id"], description=ability["description"][:100]))
        if options:
            self.add_item(_AbyssAbilitySelect(options))

    @discord.ui.button(label="⚔️ Attack", style=discord.ButtonStyle.danger)
    async def attack_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _combat_action(interaction, "attack")

    @discord.ui.button(label="💥 Ultimate", style=discord.ButtonStyle.success)
    async def ultimate_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _combat_action(interaction, "ultimate")

    @discord.ui.button(label="🛡️ Guard", style=discord.ButtonStyle.primary)
    async def guard_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _combat_action(interaction, "guard")


class _AbyssAbilitySelect(discord.ui.Select):
    def __init__(self, options):
        super().__init__(placeholder="Use a skill...", options=options,
                         min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        await _combat_action(interaction, "ability", ability_id=self.values[0])


async def _combat_action(interaction: discord.Interaction, action: str,
                         ability_id: str | None = None):
    db = SessionLocal()
    outcome = None
    embed = view = None
    try:
        player = get_player(db, interaction.user.id)
        state = abyss_service.get_or_create(db, player)
        if not state.combat_state:
            await interaction.response.send_message("No fight in progress.", ephemeral=True)
            return
        battle = battle_from_dict(state.combat_state)
        if battle.current_actor() not in battle.party:
            await interaction.response.send_message("It's not your turn.", ephemeral=True)
            return

        battle.take_party_action(action, ability_id=ability_id)
        while not battle.is_over() and battle.current_actor() in battle.enemies:
            battle.take_enemy_turn()
        state.combat_state = battle_to_dict(battle)
        db.commit()

        if battle.is_over():
            deaths = sum(1 for m in battle.party if m.current_hp <= 0)
            cycles = getattr(battle, "cycle", 0) or 0
            state.combat_state = None
            db.commit()
            outcome = abyss_service.record_chamber_result(
                db, player, won=(battle.result == "won"), cycles=cycles, deaths=deaths
            )
        else:
            embed = embedder.combat_embed(battle)
            view = AbyssCombatView(owner_id=player.id, battle=battle)
    finally:
        db.close()

    if outcome is None:
        await interaction.response.edit_message(embed=embed, view=view)
        return
    if not outcome["won"]:
        await interaction.response.edit_message(
            embed=discord.Embed(
                title="🕳️ The floor takes it back",
                description=(
                    "A chamber lost is the whole floor. Your teams were locked before the "
                    "first fight — that's the deal.\n\nTry a different split."
                ),
                color=discord.Color.dark_red()),
            view=None)
        return
    if not outcome["floor_done"]:
        await _render_chamber(interaction, edit=True)
        return

    stars = outcome["stars"] or 0
    done = discord.Embed(
        title=f"🕳️ Floor cleared — {'⭐' * stars}{'▫️' * (ac.MAX_STARS_PER_FLOOR - stars)}",
        description="Every chamber, with a different team in each.",
        color=discord.Color.gold())
    if outcome["rewards"]:
        done.add_field(name="Rewards", value="\n".join(outcome["rewards"])[:1024], inline=False)
    else:
        done.set_footer(text="Reward already claimed — stars still counted.")
    await interaction.response.edit_message(embed=done, view=None)


async def _render_chamber(interaction: discord.Interaction, edit: bool):
    db = SessionLocal()
    try:
        player = get_player(db, interaction.user.id)
        embed, view = _open_battle(db, player)
    finally:
        db.close()
    if embed is None:
        await _render_overview(interaction, edit=edit)
        return
    if edit:
        await interaction.response.edit_message(embed=embed, view=view)
    else:
        await interaction.response.send_message(embed=embed, view=view)


async def _render_overview(interaction: discord.Interaction, edit: bool):
    db = SessionLocal()
    try:
        player = get_player(db, interaction.user.id)
        embed = _overview_embed(db, player)
        view = AbyssView(db, player, owner_id=player.id)
    finally:
        db.close()
    if edit:
        await interaction.response.edit_message(embed=embed, view=view)
    else:
        await interaction.response.send_message(embed=embed, view=view)


@guild_decorator
class Abyss(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="abyss",
                          description="The Void Abyss -- the hardest content in the game.")
    async def abyss(self, ctx: discord.Interaction):
        db = SessionLocal()
        try:
            player = get_player(db, ctx.user.id)
            if not await require_player(ctx, player):
                return
            if not await require_feature(ctx, db, player, "abyss"):
                return
            resuming = abyss_service.current_chamber(db, player) is not None
        finally:
            db.close()
        if resuming:
            await _render_chamber(ctx, edit=False)
            return
        await _render_overview(ctx, edit=False)


async def setup(bot):
    await bot.add_cog(Abyss(bot))
