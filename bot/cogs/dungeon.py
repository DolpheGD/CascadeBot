import discord

from discord.ext import commands
from discord import app_commands

from bot.database.session import SessionLocal
from bot.services.player_service import get_player
from bot.services import character_service, dungeon_service, combat_service
from bot.services.currency_service import currency_emoji
from bot.utils import embedder
from bot.utils.guild_decorator import guild_decorator
from bot.utils.ui_guard import OwnedView


def _squad_hp_lines(db, player) -> list[str]:
    """Real, persisted per-character HP for the dungeon map view -- see
    PlayerCharacter.current_hp / combat_service.sync_party_hp_to_characters."""
    from bot.game.combat.factory import build_character_combatant

    squad = character_service.get_squad(db, player)
    equipped_by_char = character_service.get_equipped_items_by_character(db, [pc.id for pc in squad])
    lines = []
    for pc in squad:
        combatant = build_character_combatant(pc, equipped_by_char.get(pc.id, []))
        lines.append(f"{pc.template.name}: {combatant.current_hp}/{combatant.max_hp}")
    return lines


# ----------------------------------------------------------------------
# Persistent Views
#
# These are registered ONCE at bot startup (see bot/client.py) and never
# expire (timeout=None). Every callback re-derives the player's actual
# state from the database using interaction.user.id -- nothing about which
# expedition/battle a message belongs to is stored on the View itself. That
# is what makes these buttons keep working correctly even after a full bot
# restart, or if the player doesn't touch the message for a week: the menu
# was never the source of truth, the database always was.
#
# Select components use a FIXED custom_id and are rebuilt with fresh
# options on every render -- Discord delivers whatever the user actually
# picked on THAT message regardless of what a freshly-registered dummy
# view's default options happen to be, so this survives restarts exactly
# like the button DynamicItems do.
# ----------------------------------------------------------------------

class MoveSelect(discord.ui.Select):
    def __init__(self, options: list[discord.SelectOption] | None = None):
        options = options or [discord.SelectOption(label="...", value="none")]
        super().__init__(
            placeholder="Choose your path...",
            options=options,
            custom_id="cascade_move_select",
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction):
        await _handle_move(interaction, self.values[0])


class DungeonView(OwnedView):
    def __init__(self, options: list[discord.SelectOption] | None = None, owner_id: int | None = None):
        super().__init__(timeout=None, owner_id=owner_id)
        self.add_item(MoveSelect(options))


class AbilitySelect(discord.ui.Select):
    def __init__(self, options: list[discord.SelectOption]):
        super().__init__(
            placeholder="Use a skill (costs Mana)...",
            options=options,
            custom_id="cascade_ability_select",
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction):
        await _handle_combat_action(interaction, "ability", ability_id=self.values[0])


class TargetSelect(discord.ui.Select):
    """Switching targets is a free action -- it does not end the player's
    turn, it just changes who Attack/Ability/Ultimate will hit next."""
    def __init__(self, options: list[discord.SelectOption]):
        super().__init__(
            placeholder="🎯 Switch target...",
            options=options,
            custom_id="cascade_target_select",
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction):
        await _handle_select_target(interaction, int(self.values[0]))


class CombatView(OwnedView):
    def __init__(
        self,
        ability_options: list[discord.SelectOption] | None = None,
        target_options: list[discord.SelectOption] | None = None,
        ultimate_ready: bool = False,
        ultimate_exists: bool = False,
        ultimate_energy: int = 0,
        ultimate_cost: int = 100,
        owner_id: int | None = None,
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
            self.add_item(AbilitySelect(ability_options))
        if target_options:
            self.add_item(TargetSelect(target_options))

    @discord.ui.button(label="⚔️ Attack", style=discord.ButtonStyle.danger, custom_id="cascade_attack")
    async def attack_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _handle_combat_action(interaction, "attack")

    @discord.ui.button(label="💥 Ultimate", style=discord.ButtonStyle.success, custom_id="cascade_ultimate")
    async def ultimate_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _handle_combat_action(interaction, "ultimate")

    @discord.ui.button(label="ℹ️ Info", style=discord.ButtonStyle.secondary, custom_id="cascade_combat_info", row=4)
    async def info_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _handle_combat_info(interaction)


class TrapChoiceButton(discord.ui.Button):
    def __init__(self, choice: dict):
        super().__init__(label=choice["label"][:80], style=discord.ButtonStyle.secondary, custom_id=f"cascade_trap:{choice['id']}")
        self.choice_id = choice["id"]

    async def callback(self, interaction: discord.Interaction):
        await _handle_trap_choice(interaction, self.choice_id)


class TrapView(OwnedView):
    def __init__(self, choices: list[dict], owner_id: int | None = None):
        super().__init__(timeout=180, owner_id=owner_id)
        for choice in choices:
            self.add_item(TrapChoiceButton(choice))


class PuzzleOptionButton(discord.ui.Button):
    def __init__(self, index: int, label: str):
        super().__init__(label=f"{index + 1}. {label}"[:80], style=discord.ButtonStyle.primary, custom_id=f"cascade_puzzle:{index}")
        self.option_index = index

    async def callback(self, interaction: discord.Interaction):
        await _handle_puzzle_choice(interaction, self.option_index)


class PuzzleView(OwnedView):
    def __init__(self, puzzle: dict, owner_id: int | None = None):
        super().__init__(timeout=180, owner_id=owner_id)
        for i, option in enumerate(puzzle["options"]):
            self.add_item(PuzzleOptionButton(i, option))


class ShopBuyButton(discord.ui.Button):
    def __init__(self, offer: dict):
        super().__init__(
            label=f"Buy {offer['name']} ({offer['cost_gold']}{currency_emoji('gold')})"[:80],
            style=discord.ButtonStyle.success,
            custom_id=f"cascade_shop_buy:{offer['id']}",
        )
        self.offer_id = offer["id"]

    async def callback(self, interaction: discord.Interaction):
        await _handle_shop_buy(interaction, self.offer_id)


class ShopLeaveButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="🚪 Leave", style=discord.ButtonStyle.danger, custom_id="cascade_shop_leave")

    async def callback(self, interaction: discord.Interaction):
        await _handle_shop_leave(interaction)


class ShopView(OwnedView):
    def __init__(self, offers: list[dict], owner_id: int | None = None):
        super().__init__(timeout=180, owner_id=owner_id)
        for offer in offers:
            self.add_item(ShopBuyButton(offer))
        self.add_item(ShopLeaveButton())


def _build_dungeon_view(expedition) -> DungeonView | None:
    if expedition.status.value != "active":
        return None
    node = expedition.graph["nodes"][expedition.current_node_id]
    moves = node["edges"]
    if not moves:
        return None

    options = []
    for node_id in moves:
        target = expedition.graph["nodes"][node_id]
        emoji = embedder.ROOM_TYPE_EMOJI.get(target["room_type"], "❔")
        options.append(discord.SelectOption(
            label=f"{target['room_type'].title()} (Floor {target['floor']})",
            value=node_id,
            emoji=emoji,
        ))
    return DungeonView(options, owner_id=expedition.player_id)


def _build_combat_view(battle, owner_id: int) -> CombatView:
    actor = battle.current_actor()
    ability_options = []
    for ability in actor.active_abilities:
        ready = actor.ability_ready(ability)
        source_icon = {"character": "🌀", "weapon": "⚔️", "artifact": "🔮"}.get(ability.get("source"), "✨")
        unit = "MP" if ability["resource_type"] == "mana" else "EN"
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
            label=label[:100],
            value=ability["id"],
            description=ability["description"][:100],
        ))

    living = battle.living_enemies()
    target_options = []
    if len(living) > 1:
        for i, enemy in enumerate(living):
            marker = "🎯 " if i == battle.target_index else ""
            target_options.append(discord.SelectOption(
                label=f"{marker}{enemy.name} ({enemy.current_hp}/{enemy.max_hp} HP)"[:100],
                value=str(i),
                default=(i == battle.target_index),
            ))

    return CombatView(
        ability_options or None,
        target_options or None,
        ultimate_ready=actor.ultimate_ready(),
        ultimate_exists=actor.ultimate_ability is not None,
        ultimate_energy=actor.energy,
        ultimate_cost=actor.ultimate_ability["resource_cost"] if actor.ultimate_ability else 100,
        owner_id=owner_id,
    )


def _battle_end_message(summary: dict) -> str | None:
    kind = summary["kind"]
    if kind == "victory":
        r = summary["rewards"]
        text = f"You return to the path, 🪙 {r['gold']} gold and ✨ {r['xp']} XP (split across your squad) richer."
        if r["items"]:
            names = ", ".join(f"**{i.display_name}** ({i.rarity.value})" for i in r["items"])
            text += f"\nYou also found: {names}!"
        if r.get("level_ups"):
            level_text = ", ".join(f"{lu['name']} → Lv.{lu['to']}" for lu in r["level_ups"])
            text += f"\n📈 Level up! {level_text}"
        return text
    if kind == "boss_cleared":
        r = summary["rewards"]
        text = f"👹 Boss defeated! Great rewards: 🪙 {r['gold']} gold, ✨ {r['xp']} XP. The path continues onward."
        if r["items"]:
            names = ", ".join(f"**{i.display_name}** ({i.rarity.value})" for i in r["items"])
            text += f"\nBoss drop: {names}!"
        if r.get("level_ups"):
            level_text = ", ".join(f"{lu['name']} → Lv.{lu['to']}" for lu in r["level_ups"])
            text += f"\n📈 Level up! {level_text}"
        return text
    if kind == "expedition_complete":
        r = summary["rewards"]
        text = f"🏆 You defeated the boss! Expedition complete. (+🪙{r['gold']} gold, +✨{r['xp']} XP)"
        if r["items"]:
            names = ", ".join(f"**{i.display_name}** ({i.rarity.value})" for i in r["items"])
            text += f"\nBoss drop: {names}!"
        if r.get("level_ups"):
            level_text = ", ".join(f"{lu['name']} → Lv.{lu['to']}" for lu in r["level_ups"])
            text += f"\n📈 Level up! {level_text}"
        return text
    if kind == "defeat":
        return "💀 Your party has fallen. The expedition ends here."
    return None


def _advance_to_player_or_end(db, expedition, player, battle) -> dict | None:
    """Resolves every enemy turn (including a faster enemy acting before any
    party member ever gets to move) until it's a party member's turn or the
    battle ends. Without this, a battle where an enemy outspeeds the whole
    party would render the CombatView with an enemy turn still pending, and
    the player's first click would be rejected as 'not your turn' with
    nothing left to advance it -- a deadlock. Returns the end-of-battle
    summary if the fight ended during this drive, else None (and the battle
    is saved)."""
    while not battle.is_over() and battle.current_actor() in battle.enemies:
        battle.take_enemy_turn()

    if battle.is_over():
        return dungeon_service.resolve_battle_end(db, expedition, player, battle)

    combat_service.save_battle(db, expedition, battle)
    return None


# ----------------------------------------------------------------------
# Interaction handlers -- own their own DB session, exactly like a cog
# command would. Views call into these rather than talking to the
# database directly, keeping the persistence pattern in one place.
# ----------------------------------------------------------------------

def _render_room(db, expedition, player, kind: str, message: str, avatar_url: str) -> tuple[discord.Embed, discord.ui.View | None]:
    """Builds the (embed, view) pair for whatever room state the expedition
    is currently in -- shop/trap/puzzle get their own interactive views;
    everything else falls back to the normal dungeon map."""
    node = expedition.graph["nodes"][expedition.current_node_id]

    if kind == "trap":
        choices = dungeon_service.get_trap_choices()
        return embedder.trap_embed(node, choices, message), TrapView(choices, owner_id=expedition.player_id)

    if kind == "puzzle":
        puzzle = dungeon_service.get_pending_puzzle(expedition)
        if puzzle is None:
            # Interaction state was lost somehow -- fail safe back to the map.
            return _render_room(db, expedition, player, "resolved", message, avatar_url)
        return embedder.puzzle_embed(node, puzzle, message), PuzzleView(puzzle, owner_id=expedition.player_id)

    if kind == "shop":
        offers = dungeon_service.get_shop_offers()
        return embedder.shop_embed(player, offers, message), ShopView(offers, owner_id=expedition.player_id)

    return (
        embedder.dungeon_map_embed(
            expedition, message, avatar_url=avatar_url, squad_hp_lines=_squad_hp_lines(db, player)
        ),
        _build_dungeon_view(expedition),
    )


async def _handle_trap_choice(interaction: discord.Interaction, choice_id: str):
    db = SessionLocal()
    try:
        player = get_player(db, interaction.user.id)
        expedition = dungeon_service.get_active_expedition(db, player.id) if player else None
        if player is None or expedition is None or not expedition.pending_interaction:
            await interaction.response.send_message("There's nothing to resolve here right now.", ephemeral=True)
            return

        result = dungeon_service.resolve_trap_choice(db, expedition, player, choice_id)
        avatar_url = interaction.user.display_avatar.url
        embed, view = _render_room(db, expedition, player, result["kind"], result["message"], avatar_url)
        await interaction.response.edit_message(embed=embed, view=view)
    finally:
        db.close()


async def _handle_puzzle_choice(interaction: discord.Interaction, option_index: int):
    db = SessionLocal()
    try:
        player = get_player(db, interaction.user.id)
        expedition = dungeon_service.get_active_expedition(db, player.id) if player else None
        if player is None or expedition is None or not expedition.pending_interaction:
            await interaction.response.send_message("There's nothing to resolve here right now.", ephemeral=True)
            return

        result = dungeon_service.resolve_puzzle_choice(db, expedition, player, option_index)
        avatar_url = interaction.user.display_avatar.url
        embed, view = _render_room(db, expedition, player, result["kind"], result["message"], avatar_url)
        await interaction.response.edit_message(embed=embed, view=view)
    finally:
        db.close()


async def _handle_shop_buy(interaction: discord.Interaction, offer_id: str):
    db = SessionLocal()
    try:
        player = get_player(db, interaction.user.id)
        expedition = dungeon_service.get_active_expedition(db, player.id) if player else None
        if player is None or expedition is None or not expedition.pending_interaction:
            await interaction.response.send_message("There's nothing to buy here right now.", ephemeral=True)
            return

        ok, message = dungeon_service.buy_shop_item(db, expedition, player, offer_id)
        avatar_url = interaction.user.display_avatar.url
        embed, view = _render_room(db, expedition, player, "shop", message, avatar_url)
        await interaction.response.edit_message(embed=embed, view=view)
        if not ok:
            await interaction.followup.send(message, ephemeral=True)
    finally:
        db.close()


async def _handle_shop_leave(interaction: discord.Interaction):
    db = SessionLocal()
    try:
        player = get_player(db, interaction.user.id)
        expedition = dungeon_service.get_active_expedition(db, player.id) if player else None
        if player is None or expedition is None:
            await interaction.response.send_message("You're not shopping right now.", ephemeral=True)
            return

        result = dungeon_service.leave_shop(db, expedition)
        avatar_url = interaction.user.display_avatar.url
        embed, view = _render_room(db, expedition, player, result["kind"], result["message"], avatar_url)
        await interaction.response.edit_message(embed=embed, view=view)
    finally:
        db.close()


async def _handle_move(interaction: discord.Interaction, target_node_id: str):
    db = SessionLocal()
    try:
        player = get_player(db, interaction.user.id)
        if player is None:
            await interaction.response.send_message("Use `/start` first.", ephemeral=True)
            return

        expedition = dungeon_service.get_active_expedition(db, player.id)
        if expedition is None:
            await interaction.response.send_message(
                "You don't have an active expedition. Use `/adventure`.", ephemeral=True
            )
            return

        ok, msg = dungeon_service.move_to_node(db, expedition, target_node_id)
        if not ok:
            await interaction.response.send_message(msg, ephemeral=True)
            return

        result = dungeon_service.enter_node(db, expedition, player)
        avatar_url = interaction.user.display_avatar.url

        if result["kind"] == "combat":
            battle = combat_service.load_battle(expedition)
            summary = _advance_to_player_or_end(db, expedition, player, battle)

            if summary is not None:
                await interaction.response.edit_message(
                    embed=embedder.combat_embed(battle, avatar_url=avatar_url), view=None
                )
                follow_up_text = _battle_end_message(summary)
                if follow_up_text:
                    embed, view = _render_room(db, expedition, player, "resolved", follow_up_text, avatar_url)
                    await interaction.followup.send(embed=embed, view=view)
            else:
                await interaction.response.edit_message(
                    embed=embedder.combat_embed(battle, avatar_url=avatar_url), view=_build_combat_view(battle, expedition.player_id)
                )
        else:
            embed, view = _render_room(db, expedition, player, result["kind"], result["message"], avatar_url)
            await interaction.response.edit_message(embed=embed, view=view)
    finally:
        db.close()


async def _handle_combat_info(interaction: discord.Interaction):
    """Free, non-turn-consuming: shows every combatant's active status
    effects and ability cooldowns, ephemerally, without touching the
    shared battle message. Any squad member can check this on anyone
    else's turn too -- it's read-only."""
    db = SessionLocal()
    try:
        player = get_player(db, interaction.user.id)
        expedition = dungeon_service.get_active_expedition(db, player.id) if player else None
        if player is None or expedition is None or not expedition.combat_state:
            await interaction.response.send_message("You're not in a battle right now.", ephemeral=True)
            return

        battle = combat_service.load_battle(expedition)
        await interaction.response.send_message(embed=embedder.battle_info_embed(battle), ephemeral=True)
    finally:
        db.close()


async def _handle_combat_action(interaction: discord.Interaction, action: str, ability_id: str | None = None):
    db = SessionLocal()
    try:
        player = get_player(db, interaction.user.id)
        if player is None:
            await interaction.response.send_message("Use `/start` first.", ephemeral=True)
            return

        expedition = dungeon_service.get_active_expedition(db, player.id)
        if expedition is None or not expedition.combat_state:
            await interaction.response.send_message(
                "You're not in a battle right now.", ephemeral=True
            )
            return

        battle = combat_service.load_battle(expedition)
        if battle.current_actor() not in battle.party:
            await interaction.response.send_message("It's not your turn yet.", ephemeral=True)
            return

        battle.take_party_action(action, ability_id=ability_id)
        summary = _advance_to_player_or_end(db, expedition, player, battle)
        avatar_url = interaction.user.display_avatar.url

        if summary is not None:
            await interaction.response.edit_message(
                embed=embedder.combat_embed(battle, avatar_url=avatar_url), view=None
            )

            follow_up_text = _battle_end_message(summary)
            if follow_up_text:
                embed, view = _render_room(db, expedition, player, "resolved", follow_up_text, avatar_url)
                await interaction.followup.send(embed=embed, view=view)
        else:
            await interaction.response.edit_message(
                embed=embedder.combat_embed(battle, avatar_url=avatar_url), view=_build_combat_view(battle, expedition.player_id)
            )
    finally:
        db.close()


async def _handle_select_target(interaction: discord.Interaction, target_index: int):
    """Switching targets is free -- it does not consume the player's turn."""
    db = SessionLocal()
    try:
        player = get_player(db, interaction.user.id)
        if player is None:
            await interaction.response.send_message("Use `/start` first.", ephemeral=True)
            return

        expedition = dungeon_service.get_active_expedition(db, player.id)
        if expedition is None or not expedition.combat_state:
            await interaction.response.send_message("You're not in a battle right now.", ephemeral=True)
            return

        battle = combat_service.load_battle(expedition)
        if battle.current_actor() not in battle.party:
            await interaction.response.send_message("It's not your turn yet.", ephemeral=True)
            return

        battle.select_target(target_index)
        combat_service.save_battle(db, expedition, battle)

        avatar_url = interaction.user.display_avatar.url
        await interaction.response.edit_message(
            embed=embedder.combat_embed(battle, avatar_url=avatar_url), view=_build_combat_view(battle, expedition.player_id)
        )
    finally:
        db.close()


# ----------------------------------------------------------------------
# Cog
# ----------------------------------------------------------------------

@guild_decorator
class Dungeon(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # COMMAND: /adventure
    # Starts a new expedition (if none active) or resumes the current one
    # exactly where it was left -- including mid-battle.
    @app_commands.command(name="adventure", description="Start or resume your dungeon expedition. Harder regions give bigger rewards.")
    @app_commands.choices(region=[
        app_commands.Choice(name="Glacier 15 (Easy)", value="Glacier 15"),
        app_commands.Choice(name="The Wastelands (Normal)", value="The Wastelands"),
        app_commands.Choice(name="The Hotlands (Hard)", value="The Hotlands"),
        app_commands.Choice(name="Voidcrest Desert (Nightmare)", value="Voidcrest Desert"),
    ])
    async def adventure(self, ctx: discord.Interaction, region: str = "Glacier 15"):
        db = SessionLocal()
        try:
            player = get_player(db, ctx.user.id)
            if player is None:
                await ctx.response.send_message("Use `/start` first.", ephemeral=True)
                return

            expedition = dungeon_service.get_active_expedition(db, player.id)
            avatar_url = ctx.user.display_avatar.url

            if expedition is None:
                expedition = dungeon_service.start_expedition(db, player, region)
                result = dungeon_service.enter_node(db, expedition, player)
                message = result["message"]
                entry_kind = result["kind"]
            else:
                message = "Resuming your expedition..."
                entry_kind = None  # figure out from expedition state below

            if expedition.combat_state:
                battle = combat_service.load_battle(expedition)
                summary = _advance_to_player_or_end(db, expedition, player, battle)
                if summary is not None:
                    embed = embedder.combat_embed(battle, avatar_url=avatar_url)
                    view = None
                    follow_up_text = _battle_end_message(summary)
                else:
                    embed = embedder.combat_embed(battle, avatar_url=avatar_url)
                    view = _build_combat_view(battle, expedition.player_id)
                    follow_up_text = None
            else:
                if entry_kind is None:
                    interaction_kind = (expedition.pending_interaction or {}).get("kind")
                    entry_kind = interaction_kind or "resolved"
                embed, view = _render_room(db, expedition, player, entry_kind, message, avatar_url)
                follow_up_text = None
        finally:
            db.close()

        await ctx.response.send_message(embed=embed, view=view)
        if follow_up_text:
            db = SessionLocal()
            try:
                player = get_player(db, ctx.user.id)
                expedition = dungeon_service.get_active_expedition(db, player.id)
                embed, view = _render_room(db, expedition, player, "resolved", follow_up_text, avatar_url)
                await ctx.followup.send(embed=embed, view=view)
            finally:
                db.close()


async def setup(bot):
    await bot.add_cog(Dungeon(bot))
