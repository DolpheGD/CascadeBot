import discord

from discord.ext import commands
from discord import app_commands

from bot.database.session import SessionLocal
from bot.services.player_service import get_player
from bot.services import character_service, combat_service, dungeon_service, relic_service
from bot.utils import combat_ui, embedder
from bot.utils.guild_decorator import guild_decorator
from bot.utils.ui_guard import OwnedView, require_feature


def _squad_hp_lines(db, player) -> list[str]:
    """Real, persisted per-character HP for the dungeon map view -- see
    PlayerCharacter.current_hp / combat_service.sync_party_hp_to_characters.

    Builds Combatant objects for each squad member, applies any built
    shrine bonuses (so max_hp reflects shrine effects outside of battle),
    then renders name and HP using those adjusted combatants.
    """
    from bot.game.combat.factory import build_character_combatant
    from bot.services import base_service

    squad = character_service.get_squad(db, player)
    if not squad:
        return []

    equipped_by_char = character_service.get_equipped_items_by_character(db, [pc.id for pc in squad])
    combatants = [build_character_combatant(pc, equipped_by_char.get(pc.id, [])) for pc in squad]

    # Apply shrine bonuses so max_hp / max_mana are up-to-date outside of battle
    base_service.apply_shrine_bonuses(db, player, combatants)

    lines = []
    for pc, combatant in zip(squad, combatants):
        lines.append(f"{pc.display_name}: {combatant.current_hp}/{combatant.max_hp}")
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

    @discord.ui.button(label="🗺️ Map", style=discord.ButtonStyle.secondary, custom_id="cascade_dungeon_map")
    async def map_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _handle_dungeon_map(interaction)

    @discord.ui.button(label="🏳️ Forfeit", style=discord.ButtonStyle.danger, custom_id="cascade_dungeon_forfeit")
    async def forfeit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _handle_forfeit_prompt(interaction)


class ForfeitConfirmView(OwnedView):
    """Shown in place of the normal DungeonView after tapping Forfeit --
    an are-you-sure step since ending the run is not undoable. Not a
    persistent view (like EncounterView): it's a short-lived confirmation
    step, not a menu that needs to keep working across a bot restart --
    if the bot restarts while one's on screen, cancel and re-open the
    adventure menu is exactly the graceful fallback."""

    def __init__(self, owner_id: int | None = None):
        super().__init__(timeout=120, owner_id=owner_id)

    @discord.ui.button(label="✅ Confirm Forfeit", style=discord.ButtonStyle.danger, custom_id="cascade_forfeit_confirm")
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _handle_forfeit_confirm(interaction)

    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.secondary, custom_id="cascade_forfeit_cancel")
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _handle_forfeit_cancel(interaction)


class AbilitySelect(discord.ui.Select):
    def __init__(self, options: list[discord.SelectOption]):
        super().__init__(
            placeholder="Use a skill (costs SP)...",
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


class AllySelect(discord.ui.Select):
    """Pick which squad member a single-ally support ability will land on
    (heals, cleanses, single-target buffs, resource restores).

    Only rendered when the acting character actually HAS such an ability
    (see effects.combatant_has_ally_targeting) -- a DPS character would
    otherwise get a dropdown that does nothing, and the battle view has no
    room to spare for controls that don't apply.

    Like target selection, choosing is a FREE action: it re-renders and
    waits, so a player can line up the recipient and still decide between
    their skill and their ultimate afterwards."""

    def __init__(self, options: list[discord.SelectOption]):
        super().__init__(
            placeholder="💚 Support target...",
            options=options,
            custom_id="cascade_ally_select",
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction):
        raw = self.values[0]
        await _handle_select_ally(interaction, None if raw == "auto" else int(raw))


class CombatView(OwnedView):
    def __init__(
        self,
        ability_options: list[discord.SelectOption] | None = None,
        target_options: list[discord.SelectOption] | None = None,
        ultimate_ready: bool = False,
        ultimate_exists: bool = False,
        ultimate_energy: int = 0,
        ultimate_cost: int = 100,
        ultimate_label: str | None = None,
        owner_id: int | None = None,
        ally_options: list[discord.SelectOption] | None = None,
    ):
        super().__init__(timeout=None, owner_id=owner_id)
        self.attack_button.disabled = False
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
            self.ultimate_button.label = "💥 No Ultimate"
        if not ultimate_exists:
            self.remove_item(self.ultimate_button)

        if ability_options:
            self.add_item(AbilitySelect(ability_options))
        if target_options:
            self.add_item(TargetSelect(target_options))
        if ally_options:
            self.add_item(AllySelect(ally_options))

    @discord.ui.button(label="⚔️ Attack", style=discord.ButtonStyle.danger, custom_id="cascade_attack")
    async def attack_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _handle_combat_action(interaction, "attack")

    @discord.ui.button(label="💥 Ultimate", style=discord.ButtonStyle.success, custom_id="cascade_ultimate")
    async def ultimate_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _handle_combat_action(interaction, "ultimate")

    @discord.ui.button(label="🛡️ Guard", style=discord.ButtonStyle.primary, custom_id="cascade_guard")
    async def guard_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _handle_combat_action(interaction, "guard")

    @discord.ui.button(label="ℹ️ Info", style=discord.ButtonStyle.secondary, custom_id="cascade_combat_info", row=4)
    async def info_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _handle_combat_info(interaction)

    @discord.ui.button(label="📜 Log", style=discord.ButtonStyle.secondary, custom_id="cascade_combat_log", row=4)
    async def log_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _handle_combat_log(interaction)


class StartBattleView(OwnedView):
    """Shown instead of the normal CombatView for a freshly-created battle,
    before any turns (including a faster enemy's opening turn) have been
    resolved -- see _combat_entry_view_and_embed."""

    def __init__(self, owner_id: int | None = None):
        super().__init__(timeout=None, owner_id=owner_id)

    @discord.ui.button(label="⚔️ Start Battle", style=discord.ButtonStyle.danger, custom_id="cascade_start_battle")
    async def start_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _handle_start_battle(interaction)


_BUTTON_STYLES = {
    "primary": discord.ButtonStyle.primary,
    "secondary": discord.ButtonStyle.secondary,
    "success": discord.ButtonStyle.success,
    "danger": discord.ButtonStyle.danger,
}


class EncounterChoiceButton(discord.ui.Button):
    def __init__(self, choice: dict):
        style = _BUTTON_STYLES.get(choice.get("style"), discord.ButtonStyle.secondary)
        super().__init__(label=choice["label"][:80], style=style, custom_id=f"cascade_encounter:{choice['id']}")
        self.choice_id = choice["id"]

    async def callback(self, interaction: discord.Interaction):
        await _handle_encounter_choice(interaction, self.choice_id)


class EncounterView(OwnedView):
    def __init__(self, choices: list[dict], owner_id: int | None = None):
        super().__init__(timeout=180, owner_id=owner_id)
        for choice in choices:
            self.add_item(EncounterChoiceButton(choice))


class CampfireRestButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="🔥 Rest", style=discord.ButtonStyle.success, custom_id="cascade_campfire_rest")

    async def callback(self, interaction: discord.Interaction):
        await _handle_campfire_choice(interaction, "rest")


class CampfireAttuneButton(discord.ui.Button):
    """One button per offered relic. Not a DynamicItem: the campfire view
    is always rebuilt from live expedition state on render (the offer is
    re-rolled deterministically from the expedition + node id -- see
    dungeon_service.get_campfire_offer), so there's nothing that needs to
    survive a restart baked into the custom_id."""

    def __init__(self, relic: dict):
        super().__init__(
            label=f"✨ {relic['name']}"[:80],
            style=discord.ButtonStyle.primary,
            custom_id=f"cascade_campfire_attune:{relic['id']}",
        )
        self.relic_id = relic["id"]

    async def callback(self, interaction: discord.Interaction):
        await _handle_campfire_choice(interaction, "attune", relic_id=self.relic_id)


class CampfireView(OwnedView):
    def __init__(self, offer: list[dict], owner_id: int | None = None):
        super().__init__(timeout=None, owner_id=owner_id)
        self.add_item(CampfireRestButton())
        for relic in offer:
            self.add_item(CampfireAttuneButton(relic))


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
            label=label[:100],
            value=ability["id"],
            description=ability["description"][:100],
        ))

    # Built by the shared helper so all three combat surfaces agree on
    # when targeting is unavailable -- notably while an enemy is taunting.
    target_options = combat_ui.enemy_target_options(battle)

    ally_options = combat_ui.ally_select_options(battle) if combat_ui.should_offer_ally_select(battle) else []

    return CombatView(
        ability_options or None,
        target_options or None,
        ultimate_ready=actor.ultimate_ready(),
        ultimate_exists=actor.ultimate_ability is not None,
        ultimate_energy=actor.energy,
        ultimate_cost=actor.ultimate_ability["resource_cost"] if actor.ultimate_ability else 100,
        ultimate_label=combat_ui.ultimate_button_label(actor),
        owner_id=owner_id,
        ally_options=ally_options or None,
    )


def _expedition_summary_kwargs(summary: dict | None) -> tuple[dict, bool] | None:
    """If `summary` represents the expedition actually ending (won by
    clearing the final boss, or lost to a defeat), returns
    (ledger, won) for embedder.expedition_summary_embed. Returns None for
    an ordinary in-run combat win, where the expedition continues."""
    if summary is None:
        return None
    if summary["kind"] == "expedition_complete":
        return summary["ledger"], True
    if summary["kind"] == "defeat":
        return summary["ledger"], False
    return None


def _reward_extras_text(r: dict) -> str:
    """Combat rework: material/lootbox drops now come back on every combat
    victory (see combat_service.apply_victory_rewards) -- render them the
    same way regardless of which battle-end message is showing them."""
    extras = ""
    if r.get("material"):
        m = r["material"]
        extras += f"\n+{m['amount']} {m['type'].replace('_', ' ').title()}"
    if r.get("lootbox"):
        lb = r["lootbox"]
        extras += f"\n+{lb['quantity']} {lb['tier'].title()} Lootbox!"
    if r.get("reroll_tokens"):
        extras += f"\n+{r['reroll_tokens']} 🎲"
    # Relic drops (elites and non-final bosses) get their own emphasised
    # line -- they're the rarest and most run-shaping thing a fight can
    # produce, so they shouldn't read as one more item in a loot list.
    if r.get("relic"):
        relic = r["relic"]
        extras += f"\n\n✨ **Relic acquired: {relic['emoji']} {relic['name']}**\n*{relic['description']}*"
    return extras


def _battle_end_message(summary: dict) -> str | None:
    kind = summary["kind"]
    if kind == "victory":
        r = summary["rewards"]
        text = f"You return to the path, 🪙 {r['gold']} gold and ✨ {r['xp']} XP (split across your squad) richer."
        if r["items"]:
            names = ", ".join(f"**{i.display_name}** ({i.rarity.value})" for i in r["items"])
            text += f"\nYou also found: {names}!"
        text += _reward_extras_text(r)
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
        text += _reward_extras_text(r)
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
        text += _reward_extras_text(r)
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


def _combat_entry_view_and_embed(db, expedition, player, avatar_url: str):
    """Builds the embed+view to show whenever a COMBAT/ELITE/BOSS room is
    entered or resumed. If this is a freshly-created battle the player
    hasn't pressed Start Battle for yet (expedition.pending_interaction ==
    {"kind": "start_battle"}, set by dungeon_service.enter_node), returns
    a pre-battle preview with StartBattleView instead of immediately
    fast-forwarding through any enemies faster than the whole party --
    without this, facing faster enemies, the player's first-ever glimpse
    of the fight would already be several turns in, with those opening
    enemy turns having resolved before they saw anything. Otherwise
    (already started, resuming an ongoing fight) behaves exactly like
    before: fast-forward to the player's turn or the battle's end.
    Returns (embed, view, summary) -- summary is None unless the battle
    ended during this call, exactly like _advance_to_player_or_end."""
    battle = combat_service.load_battle(expedition)

    if (expedition.pending_interaction or {}).get("kind") == "start_battle":
        return embedder.combat_embed(battle, avatar_url=avatar_url), StartBattleView(owner_id=expedition.player_id), None

    summary = _advance_to_player_or_end(db, expedition, player, battle)
    embed = embedder.combat_embed(battle, avatar_url=avatar_url)
    if summary is not None:
        return embed, None, summary
    return embed, _build_combat_view(battle, expedition.player_id), None


async def _handle_start_battle(interaction: discord.Interaction):
    db = SessionLocal()
    try:
        player = get_player(db, interaction.user.id)
        expedition = dungeon_service.get_active_expedition(db, player.id) if player else None
        if player is None or expedition is None or not expedition.combat_state:
            await interaction.response.send_message("You're not in a battle right now.", ephemeral=True)
            return

        expedition.pending_interaction = None
        db.commit()

        avatar_url = interaction.user.display_avatar.url
        embed, view, summary = _combat_entry_view_and_embed(db, expedition, player, avatar_url)
        await interaction.response.edit_message(embed=embed, view=view)

        if summary is not None:
            follow_up_text = _battle_end_message(summary)
            if follow_up_text:
                embed2, view2 = _render_room(db, expedition, player, "resolved", follow_up_text, avatar_url)
                if view2 is None:
                    await interaction.followup.send(embed=embed2)
                else:
                    await interaction.followup.send(embed=embed2, view=view2)
            exp_summary = _expedition_summary_kwargs(summary)
            if exp_summary:
                ledger, won = exp_summary
                await interaction.followup.send(embed=embedder.expedition_summary_embed(ledger, won))
    finally:
        db.close()


# ----------------------------------------------------------------------
# Interaction handlers -- own their own DB session, exactly like a cog
# command would. Views call into these rather than talking to the
# database directly, keeping the persistence pattern in one place.
# ----------------------------------------------------------------------

def _render_room(db, expedition, player, kind: str, message: str, avatar_url: str) -> tuple[discord.Embed, discord.ui.View | None]:
    """Builds the (embed, view) pair for whatever room state the expedition
    is currently in -- an active encounter gets its own interactive view;
    everything else falls back to the normal dungeon map. Trap and Puzzle
    rooms no longer have standalone mini-games of their own -- they're
    Encounter-driven now, same as every other non-combat room type."""
    node = expedition.graph["nodes"][expedition.current_node_id]

    if kind == "encounter":
        encounter = dungeon_service.get_pending_encounter(expedition)
        if encounter is None:
            # Interaction state was lost somehow -- fail safe back to the map.
            return _render_room(db, expedition, player, "resolved", message, avatar_url)
        return (
            embedder.encounter_embed(node, encounter, message, player=player),
            EncounterView(dungeon_service.get_encounter_choices(encounter), owner_id=expedition.player_id),
        )

    if kind == "campfire":
        offer = dungeon_service.get_campfire_offer(expedition)
        return (
            embedder.campfire_embed(node, offer, relic_service.held_relics(expedition), message),
            CampfireView(offer, owner_id=expedition.player_id),
        )

    return (
        embedder.dungeon_map_embed(
            expedition, message, avatar_url=avatar_url, squad_hp_lines=_squad_hp_lines(db, player)
        ),
        _build_dungeon_view(expedition),
    )


async def _handle_encounter_choice(interaction: discord.Interaction, choice_id: str):
    db = SessionLocal()
    try:
        player = get_player(db, interaction.user.id)
        expedition = dungeon_service.get_active_expedition(db, player.id) if player else None
        if player is None or expedition is None or not expedition.pending_interaction:
            await interaction.response.send_message("There's nothing to resolve here right now.", ephemeral=True)
            return

        result = dungeon_service.resolve_encounter_choice(db, expedition, player, choice_id)
        avatar_url = interaction.user.display_avatar.url
        embed, view = _render_room(db, expedition, player, result["kind"], result["message"], avatar_url)
        await interaction.response.edit_message(embed=embed, view=view)
    finally:
        db.close()


async def _handle_campfire_choice(interaction: discord.Interaction, choice: str, relic_id: str | None = None):
    db = SessionLocal()
    try:
        player = get_player(db, interaction.user.id)
        expedition = dungeon_service.get_active_expedition(db, player.id) if player else None
        if player is None or expedition is None or not expedition.pending_interaction:
            await interaction.response.send_message("There's nothing to resolve here right now.", ephemeral=True)
            return

        result = dungeon_service.resolve_campfire_choice(db, expedition, player, choice, relic_id=relic_id)
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
            embed, view, summary = _combat_entry_view_and_embed(db, expedition, player, avatar_url)
            await interaction.response.edit_message(embed=embed, view=view)

            if summary is not None:
                follow_up_text = _battle_end_message(summary)
                if follow_up_text:
                    embed2, view2 = _render_room(db, expedition, player, "resolved", follow_up_text, avatar_url)
                    if view2 is None:
                        await interaction.followup.send(embed=embed2)
                    else:
                        await interaction.followup.send(embed=embed2, view=view2)
                exp_summary = _expedition_summary_kwargs(summary)
                if exp_summary:
                    ledger, won = exp_summary
                    await interaction.followup.send(embed=embedder.expedition_summary_embed(ledger, won))
        else:
            embed, view = _render_room(db, expedition, player, result["kind"], result["message"], avatar_url)
            await interaction.response.edit_message(embed=embed, view=view)
    finally:
        db.close()


async def _handle_dungeon_map(interaction: discord.Interaction):
    """Free, non-committal: shows the floor-by-floor path to the next
    boss ephemerally, without touching or re-sending the shared message."""
    db = SessionLocal()
    try:
        player = get_player(db, interaction.user.id)
        expedition = dungeon_service.get_active_expedition(db, player.id) if player else None
        if player is None or expedition is None:
            await interaction.response.send_message("You don't have an active expedition.", ephemeral=True)
            return

        await interaction.response.send_message(embed=embedder.dungeon_map_graph_embed(expedition), ephemeral=True)
    finally:
        db.close()


async def _handle_forfeit_prompt(interaction: discord.Interaction):
    """Are-you-sure step for the Forfeit button -- ending the run early
    isn't undoable, so it gets a confirmation like any other destructive
    action rather than firing on the first click."""
    db = SessionLocal()
    try:
        player = get_player(db, interaction.user.id)
        expedition = dungeon_service.get_active_expedition(db, player.id) if player else None
        if player is None or expedition is None:
            await interaction.response.send_message("You don't have an active expedition.", ephemeral=True)
            return
        if expedition.combat_state or expedition.pending_interaction:
            await interaction.response.send_message(
                "You can't forfeit right now -- finish what you're doing first.", ephemeral=True
            )
            return

        embed = discord.Embed(
            title="🏳️ Forfeit Expedition?",
            description=(
                "This ends your run right here and you'll head back empty-handed "
                "from this point on. Everything you've already earned this run "
                "is kept, but you'll miss out on whatever's further down the "
                "path -- including the next boss's rewards.\n\nAre you sure?"
            ),
            color=discord.Color.orange(),
        )
        await interaction.response.edit_message(embed=embed, view=ForfeitConfirmView(owner_id=expedition.player_id))
    finally:
        db.close()


async def _handle_forfeit_confirm(interaction: discord.Interaction):
    db = SessionLocal()
    try:
        player = get_player(db, interaction.user.id)
        expedition = dungeon_service.get_active_expedition(db, player.id) if player else None
        if player is None or expedition is None:
            await interaction.response.send_message("You don't have an active expedition.", ephemeral=True)
            return

        result = dungeon_service.abandon_expedition(db, expedition, player)
        if not result["ok"]:
            await interaction.response.send_message(result["message"], ephemeral=True)
            return

        avatar_url = interaction.user.display_avatar.url
        embed, view = _render_room(
            db, expedition, player, "resolved",
            "🏳️ You forfeit the expedition and make your way back.", avatar_url,
        )
        await interaction.response.edit_message(embed=embed, view=view)
        await interaction.followup.send(
            embed=embedder.expedition_summary_embed(result["ledger"], won=False, forfeited=True)
        )
    finally:
        db.close()


async def _handle_forfeit_cancel(interaction: discord.Interaction):
    db = SessionLocal()
    try:
        player = get_player(db, interaction.user.id)
        expedition = dungeon_service.get_active_expedition(db, player.id) if player else None
        if player is None or expedition is None:
            await interaction.response.send_message("You don't have an active expedition.", ephemeral=True)
            return

        avatar_url = interaction.user.display_avatar.url
        embed, view = _render_room(db, expedition, player, "resolved", "Forfeit cancelled.", avatar_url)
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
        embed, view = combat_ui.info_response(battle)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    finally:
        db.close()


async def _handle_combat_log(interaction: discord.Interaction):
    """Free, non-turn-consuming: shows the full battle log (not just the
    short tail on the main battle message), ephemerally, without touching
    the shared battle message."""
    db = SessionLocal()
    try:
        player = get_player(db, interaction.user.id)
        expedition = dungeon_service.get_active_expedition(db, player.id) if player else None
        if player is None or expedition is None or not expedition.combat_state:
            await interaction.response.send_message("You're not in a battle right now.", ephemeral=True)
            return

        battle = combat_service.load_battle(expedition)
        await interaction.response.send_message(embed=embedder.battle_log_embed(battle), ephemeral=True)
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
                if view is None:
                    await interaction.followup.send(embed=embed)
                else:
                    await interaction.followup.send(embed=embed, view=view)
            exp_summary = _expedition_summary_kwargs(summary)
            if exp_summary:
                ledger, won = exp_summary
                await interaction.followup.send(embed=embedder.expedition_summary_embed(ledger, won))
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


async def _handle_select_ally(interaction: discord.Interaction, party_index: int | None):
    """Choosing the recipient for a single-ally support ability. Free, in
    exactly the same sense as switching enemy targets: it re-renders and
    hands the turn back rather than consuming it, so the player can pick
    the recipient and then still choose which ability to cast on them.

    `party_index` is None for the "Auto" entry, which clears the choice
    back to the original whoever-needs-it-most behaviour."""
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

        battle.select_ally_target(party_index)
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
        app_commands.Choice(name="Voidcrest Desert (Insane)", value="Voidcrest Desert"),
        app_commands.Choice(name="Abyssnia (Nightmare)", value="Abyssnia"),
    ])
    async def adventure(self, ctx: discord.Interaction, region: str = "Glacier 15"):
        db = SessionLocal()
        try:
            player = get_player(db, ctx.user.id)
            if player is None:
                await ctx.response.send_message("Use `/start` first.", ephemeral=True)
                return
            if not await require_feature(ctx, db, player, "adventure"):
                return

            expedition = dungeon_service.get_active_expedition(db, player.id)
            avatar_url = ctx.user.display_avatar.url

            resume_region_note = None
            if expedition is None:
                unlocked, required_region = dungeon_service.is_region_unlocked(db, player.id, region)
                if not unlocked:
                    await ctx.response.send_message(
                        f"**{region}** is locked -- fully clear an expedition in "
                        f"**{required_region}** (defeat its final boss) to unlock it.",
                        ephemeral=True,
                    )
                    return
                expedition = dungeon_service.start_expedition(db, player, region)
                result = dungeon_service.enter_node(db, expedition, player)
                message = result["message"]
                entry_kind = result["kind"]
            else:
                # There's no such thing as two concurrent expeditions for
                # the same player (start_expedition itself just returns
                # the existing one) -- but silently resuming without
                # saying so, especially when the person picked a
                # DIFFERENT region than the one they're actually about to
                # see, reads as "I asked for a new adventure and got stuck
                # on the old one". Always say plainly which is happening.
                if region != expedition.region:
                    resume_region_note = (
                        f"You already have an expedition underway in **{expedition.region}** -- "
                        f"resuming that instead of starting a new one in {region}. "
                        f"Finish or lose that run first to adventure somewhere else."
                    )
                    message = resume_region_note
                else:
                    message = "Resuming your expedition..."
                entry_kind = None  # figure out from expedition state below

            if expedition.combat_state:
                embed, view, summary = _combat_entry_view_and_embed(db, expedition, player, avatar_url)
                if summary is not None:
                    follow_up_text = _battle_end_message(summary)
                    exp_summary = _expedition_summary_kwargs(summary)
                else:
                    follow_up_text = None
                    exp_summary = None
            else:
                if entry_kind is None:
                    interaction_kind = (expedition.pending_interaction or {}).get("kind")
                    entry_kind = interaction_kind or "resolved"
                embed, view = _render_room(db, expedition, player, entry_kind, message, avatar_url)
                follow_up_text = None
                exp_summary = None
        finally:
            db.close()

        await ctx.response.send_message(embed=embed, view=view)
        if resume_region_note and expedition.combat_state:
            await ctx.followup.send(resume_region_note, ephemeral=True)
        if follow_up_text:
            if exp_summary:
                # The expedition itself has ended (won or lost) -- there's no
                # active expedition left to fetch/render a map for, so just
                # send the plain battle-end message, then the whole-run
                # summary, rather than routing through _render_room.
                ledger, won = exp_summary
                await ctx.followup.send(embed=discord.Embed(description=follow_up_text))
                await ctx.followup.send(embed=embedder.expedition_summary_embed(ledger, won))
            else:
                db = SessionLocal()
                try:
                    player = get_player(db, ctx.user.id)
                    expedition = dungeon_service.get_active_expedition(db, player.id)
                    embed, view = _render_room(db, expedition, player, "resolved", follow_up_text, avatar_url)
                    if view is None:
                        await ctx.followup.send(embed=embed)
                    else:
                        await ctx.followup.send(embed=embed, view=view)
                finally:
                    db.close()


async def setup(bot):
    await bot.add_cog(Dungeon(bot))