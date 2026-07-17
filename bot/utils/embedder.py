"""
Every discord.Embed the bot renders lives here, kept separate from cogs so
presentation never gets tangled with interaction/DB plumbing.
"""

from __future__ import annotations

import discord

from bot.database.models.enums import (
    CLASS_DISPLAY_NAME,
    MATERIAL_DISPLAY_NAME,
    MATERIAL_EMOJI,
    SLOT_DISPLAY_NAME,
    SLOT_EMOJI,
    EquipmentSlot,
    ItemType,
    MaterialType,
)
from bot.database.models.character_model import LEVEL_CAP
from bot.game.combat.combatant import STAT_KEYS
from bot.game.combat.factory import base_character_stats as _base_character_stats
from bot.game.combat.factory import build_character_combatant
from bot.game.economy.quest_config import BASIC_QUEST_POOL, BEGINNER_QUESTS
from bot.services.currency_service import currency_emoji, format_currency

ROOM_TYPE_EMOJI = {
    "start": "🚪", "combat": "⚔️", "elite": "🔥", "treasure": "💰",
    "merchant": "🛒", "campfire": "🏕️", "story": "📜", "trap": "⚠️",
    "shrine": "⛩️", "puzzle": "🧩", "secret": "❓", "boss": "💀",
}

RARITY_COLORS = {
    "common": discord.Color.light_grey(),
    "uncommon": discord.Color.green(),
    "rare": discord.Color.blue(),
    "epic": discord.Color.purple(),
    "legendary": discord.Color.orange(),
    "mythic": discord.Color.red(),
    "divine": discord.Color.gold(),
}

RARITY_EMOJI = {
    "common": "⚪", "uncommon": "🟢", "rare": "🔵", "epic": "🟣",
    "legendary": "🟠", "mythic": "🔴", "divine": "🟡",
}

STAT_EMOJI = {
    "attack": "⚔️", "defense": "🛡️", "elemental": "🔮", "speed": "💨",
    "max_hp": "❤️", "max_mana": "💧", "crit_rate": "🎯", "crit_damage": "💥",
    "recharge": "🔋",
}

STAT_LABEL = {
    "attack": "ATK", "defense": "DEF", "elemental": "ELE", "speed": "SPD",
    "max_hp": "HP", "max_mana": "SP", "crit_rate": "Crit Rate",
    "crit_damage": "Crit DMG", "recharge": "Recharge",
}

PERCENT_STATS = {"crit_rate", "crit_damage"}


def _fmt_stat(stat: str, value: float) -> str:
    suffix = "%" if stat in PERCENT_STATS else ""
    label = STAT_LABEL.get(stat, stat.replace("_", " ").title())
    return f"{STAT_EMOJI.get(stat, '')} **{label}**: {value:g}{suffix}"


def _fmt_stat_with_base(stat: str, effective_value: float, base_value: float) -> str:
    """'HP: (100) 150' -- base value in parentheses, effective value (with
    gear) alongside it. Falls back to the plain form when gear hasn't
    changed the stat at all, so an unequipped character's page doesn't show
    a redundant '(100) 100' everywhere."""
    if round(base_value, 2) == round(effective_value, 2):
        return _fmt_stat(stat, effective_value)
    suffix = "%" if stat in PERCENT_STATS else ""
    label = STAT_LABEL.get(stat, stat.replace("_", " ").title())
    return f"{STAT_EMOJI.get(stat, '')} **{label}**: ({base_value:g}{suffix}) {effective_value:g}{suffix}"


def _bar(current: float, maximum: float, length: int = 10, fill: str = "█", empty: str = "░") -> str:
    if maximum <= 0:
        filled = 0
    else:
        filled = max(0, min(length, round(length * current / maximum)))
    return fill * filled + empty * (length - filled)


# ----------------------------------------------------------------------
# Profile -- 3 pages: Overview, Equipment, Abilities.
# ----------------------------------------------------------------------

PROFILE_PAGE_TITLES = ["📊 Overview", "🎒 Equipment", "✨ Abilities"]
PROFILE_PAGE_COUNT = len(PROFILE_PAGE_TITLES)


def profile_embed(
    player, character, equipped_items: list, avatar_url: str | None = None, page: int = 0, db=None
) -> discord.Embed:
    """`character` is the PlayerCharacter whose stats/gear/kit this profile
    shows -- normally the player's own avatar (see
    character_service.ensure_avatar_character). Full per-squad-member
    profile switching is a later UI pass; for now /profile always shows
    your avatar. `db`, if given, lets the overview page fold in built
    shrine bonuses (bot/services/base_service.py::apply_shrine_bonuses) on
    top of character+gear stats -- the same adjustment battles get."""
    page = max(0, min(page, PROFILE_PAGE_COUNT - 1))
    if page == 0:
        return _profile_overview_page(player, character, equipped_items, avatar_url, db)
    if page == 1:
        return _profile_equipment_page(player, character, equipped_items, avatar_url)
    return _profile_abilities_page(player, character, equipped_items, avatar_url)


def _profile_overview_page(player, character, equipped_items, avatar_url, db=None) -> discord.Embed:
    combatant = build_character_combatant(character, equipped_items)
    if db is not None:
        from bot.services import base_service
        base_service.apply_shrine_bonuses(db, player, [combatant])

    embed = discord.Embed(
        title=f"{player.username}'s Profile -- {character.template.name}",
        description=f"Page 1/{PROFILE_PAGE_COUNT} -- {PROFILE_PAGE_TITLES[0]}",
        color=discord.Color.blurple(),
    )
    if avatar_url:
        embed.set_thumbnail(url=avatar_url)

    embed.add_field(name="⭐ Char. Level", value=f"{character.level}/{LEVEL_CAP}", inline=True)
    embed.add_field(name="✨ XP", value=f"{character.xp} / {character.xp_to_next_level()}", inline=True)
    embed.add_field(name="🪙 Gold", value=str(player.gold), inline=True)
    embed.add_field(name="💎 Shards", value=str(player.shards), inline=True)
    embed.add_field(name="🎭 Class", value=CLASS_DISPLAY_NAME[character.effective_class()], inline=True)

    base_stats = _base_character_stats(character)
    stat_lines = "\n".join(
        _fmt_stat_with_base(stat, combatant.base_stats[stat], base_stats[stat]) for stat in STAT_KEYS
    )
    embed.add_field(name="Stats -- (base) effective", value=stat_lines, inline=False)

    embed.set_footer(text="Use the buttons below to see Equipment and Abilities.")
    return embed


def _profile_equipment_page(player, character, equipped_items, avatar_url) -> discord.Embed:
    by_slot: dict[EquipmentSlot, object] = {slot: None for slot in EquipmentSlot}
    for item in equipped_items:
        by_slot[item.slot] = item

    embed = discord.Embed(
        title=f"{character.template.name}'s Equipment",
        description=f"Page 2/{PROFILE_PAGE_COUNT} -- {PROFILE_PAGE_TITLES[1]}",
        color=discord.Color.dark_teal(),
    )
    if avatar_url:
        embed.set_thumbnail(url=avatar_url)

    for slot in EquipmentSlot:
        match = by_slot[slot]
        if match:
            rarity_emoji = RARITY_EMOJI.get(match.rarity.value, "⚪")
            value = f"{rarity_emoji} {match.display_name}"
        else:
            value = "*Empty*"
        embed.add_field(name=f"{SLOT_EMOJI[slot]} {SLOT_DISPLAY_NAME[slot]}", value=value, inline=True)

    embed.set_footer(text="Equip gear with /inventory. Each slot holds one item.")
    return embed


def _profile_abilities_page(player, character, equipped_items, avatar_url) -> discord.Embed:
    combatant = build_character_combatant(character, equipped_items)

    embed = discord.Embed(
        title=f"{character.template.name}'s Abilities",
        description=f"Page 3/{PROFILE_PAGE_COUNT} -- {PROFILE_PAGE_TITLES[2]}",
        color=discord.Color.dark_purple(),
    )
    if avatar_url:
        embed.set_thumbnail(url=avatar_url)

    character_skill = next((a for a in combatant.active_abilities if a.get("source") == "character"), None)
    weapon_skills = [a for a in combatant.active_abilities if a.get("source") == "weapon"]
    artifact_skills = [a for a in combatant.active_abilities if a.get("source") == "artifact"]
    character_passive = next((p for p in combatant.passive_abilities if p.get("source") == "character"), None)
    gear_passives = [p for p in combatant.passive_abilities if p.get("source") != "character"]

    def _skill_lines(skills: list) -> str:
        if not skills:
            return "*None equipped.*"
        return "\n".join(
            f"**{a['name']}** ({a['resource_cost']} SP): {a['description']}"
            for a in skills
        )

    if character_skill:
        embed.add_field(
            name="🌀 Character Skill",
            value=f"**{character_skill['name']}** ({character_skill['resource_cost']} SP): {character_skill['description']}",
            inline=False,
        )
    embed.add_field(name="⚔️ Weapon Skill", value=_skill_lines(weapon_skills), inline=False)
    embed.add_field(name="🔮 Artifact Skill", value=_skill_lines(artifact_skills), inline=False)

    if combatant.ultimate_ability:
        u = combatant.ultimate_ability
        embed.add_field(
        name="💥 Character Ultimate", value=f"**{u['name']}** ({combatant.max_energy} Energy): {u['description']}", inline=False
        )

    if character_passive:
        embed.add_field(
            name="🧬 Character Passive",
            value=f"**{character_passive['name']}**: {character_passive['description']}",
            inline=False,
        )

    if gear_passives:
        lines = "\n".join(f"**{p['name']}**: {p['description']}" for p in gear_passives)
    else:
        lines = "*No armor passives active.*"
    embed.add_field(name="🛡️ Passives (from Armor/Accessory)", value=lines, inline=False)

    embed.set_footer(text="Basic Attack always builds Energy + SP by your Recharge stat.")
    return embed


# ----------------------------------------------------------------------
# Dungeon map
# ----------------------------------------------------------------------

def dungeon_map_embed(
    expedition, message: str | None = None, avatar_url: str | None = None,
    squad_hp_lines: list[str] | None = None,
) -> discord.Embed:
    """Shows the current node and, if given, a one-line result of what just
    happened (e.g. 'You find a treasure chest...'). `squad_hp_lines` --
    build with cogs.dungeon._squad_hp_lines() -- shows each squad member's
    actual persisted HP instead of a flat, always-100 placeholder."""
    from bot.game.dungeon.region_config import get_region_difficulty

    node = expedition.graph["nodes"][expedition.current_node_id]
    emoji = ROOM_TYPE_EMOJI.get(node["room_type"], "❔")
    difficulty = get_region_difficulty(expedition.region)

    num_floors = expedition.graph.get("num_floors", node["floor"] + 1)
    boss_nodes = expedition.graph.get("boss_nodes", [expedition.graph.get("boss_node")])
    bosses_cleared = sum(
        1 for b in boss_nodes if expedition.graph["nodes"].get(b, {}).get("completed")
    )

    embed = discord.Embed(
        title=f"{expedition.region} ({difficulty['difficulty_label']}) -- Floor {node['floor']}/{num_floors - 1}",
        description=message or "",
        color=discord.Color.dark_green(),
    )
    if avatar_url:
        embed.set_thumbnail(url=avatar_url)

    embed.add_field(name="Current Room", value=f"{emoji} {node['room_type'].title()}", inline=True)
    embed.add_field(name="👹 Bosses", value=f"{bosses_cleared}/{len(boss_nodes)} defeated", inline=True)
    if squad_hp_lines:
        embed.add_field(name="❤️ Squad HP", value="\n".join(squad_hp_lines), inline=True)

    if expedition.status.value == "completed":
        embed.add_field(name="Status", value="🏆 Expedition Complete!", inline=False)
    elif expedition.status.value == "failed":
        embed.add_field(name="Status", value="💀 Expedition Failed", inline=False)
    else:
        moves = node["edges"]
        if moves:
            options = "\n".join(
                f"{ROOM_TYPE_EMOJI.get(expedition.graph['nodes'][n]['room_type'], '❔')} "
                f"{expedition.graph['nodes'][n]['room_type'].title()} (Floor {expedition.graph['nodes'][n]['floor']})"
                for n in moves
            )
            embed.add_field(name=f"🗺️ Paths Ahead ({len(moves)} options)", value=options, inline=False)

    return embed


# ----------------------------------------------------------------------
# Combat
# ----------------------------------------------------------------------

def _turn_order_line(battle, count: int = 6) -> str:
    icons = []
    for c in battle.preview_turn_order(count):
        icon = "🧑" if c.is_player else "👹"
        icons.append(f"{icon} {c.name}")
    return " ➜ ".join(icons) if icons else "--"


def dungeon_map_graph_embed(expedition) -> discord.Embed:
    """The 🗺️ Map button's view: a floor-by-floor breakdown of every room
    between here and the NEXT boss (not the whole multi-boss run --
    anything past that boss hasn't been reached yet and would just be
    noise). Marks the current room and anything already cleared."""
    graph = expedition.graph
    current_node_id = expedition.current_node_id
    current_floor = graph["nodes"][current_node_id]["floor"]

    boss_nodes = graph.get("boss_nodes", [graph.get("boss_node")])
    boss_floors = sorted(graph["nodes"][b]["floor"] for b in boss_nodes if b in graph["nodes"])
    next_boss_floor = next((f for f in boss_floors if f >= current_floor), None)
    if next_boss_floor is None:
        next_boss_floor = max(n["floor"] for n in graph["nodes"].values())
    is_final_stretch = not boss_floors or next_boss_floor == boss_floors[-1]

    by_floor: dict[int, list[tuple[str, dict]]] = {}
    for node_id, node in graph["nodes"].items():
        if current_floor <= node["floor"] <= next_boss_floor:
            by_floor.setdefault(node["floor"], []).append((node_id, node))

    lines = []
    for floor in sorted(by_floor):
        room_strs = []
        for node_id, node in sorted(by_floor[floor]):
            emoji = ROOM_TYPE_EMOJI.get(node["room_type"], "❔")
            if node_id == current_node_id:
                room_strs.append(f"[{emoji}]")
            elif node.get("completed"):
                room_strs.append(f"~~{emoji}~~")
            else:
                room_strs.append(emoji)
        if floor == next_boss_floor:
            floor_label = "🐲 FINAL BOSS" if is_final_stretch else "🐲 Boss"
        else:
            floor_label = f"Floor {floor}"
        lines.append(f"**{floor_label}**  " + "  ".join(room_strs))

    embed = discord.Embed(
        title="🗺️ Map to the Next Boss",
        description="\n".join(lines) if lines else "*Nothing charted yet.*",
        color=discord.Color.blurple(),
    )
    embed.set_footer(text="[bracketed] = you are here. ~~struck-through~~ = already cleared.")
    return embed


def combat_embed(battle, avatar_url: str | None = None) -> discord.Embed:
    """Renders the current battle state: HP/resource bars for everyone, the
    turn order preview, current target marker, and the last few log lines,
    so a Discord message can be edited in place turn after turn.

    Party and enemies are each ONE consolidated field (a line per member)
    rather than one Discord field per combatant -- with a full 4-person
    squad plus several enemies, one-field-each was wrapping into a bunched,
    hard-to-scan 3-per-row grid. A single readable block per side reads
    top-to-bottom instead."""
    color = discord.Color.red()
    if battle.result == "won":
        color = discord.Color.gold()
    elif battle.result == "lost":
        color = discord.Color.dark_gray()

    embed = discord.Embed(title="⚔️ Battle!", color=color)
    if avatar_url:
        embed.set_thumbnail(url=avatar_url)

    if not battle.is_over():
        embed.add_field(name="🔀 Turn Order", value=_turn_order_line(battle), inline=False)

    party_lines = []
    for member in battle.party:
        acting_tag = " 🔸" if not battle.is_over() and member is battle.current_actor() else ""
        if not member.is_alive():
            party_lines.append(f"**{member.name}**{acting_tag} -- 💀 Down")
            continue
        ult_flag = " 💥" if member.ultimate_ready() else ""
        party_lines.append(
            f"**{member.name}**{acting_tag}{ult_flag}\n"
            f"┗ ❤️{member.current_hp}/{member.max_hp} {_bar(member.current_hp, member.max_hp, length=8)}"
            f"  💧{member.mana}/{member.max_mana}  🔋{member.energy}/{member.max_energy}"
        )
    embed.add_field(name="🧑 Your Squad", value="\n".join(party_lines), inline=False)

    enemy_lines = []
    living_i = 0
    for enemy in battle.enemies:
        if not enemy.is_alive():
            enemy_lines.append(f"**{enemy.name}** -- 💀 Defeated")
            continue
        is_target = living_i == battle.target_index
        living_i += 1
        target_tag = " 🎯" if is_target else ""
        enemy_lines.append(
            f"**{enemy.name}**{target_tag}\n"
            f"┗ ❤️{enemy.current_hp}/{enemy.max_hp} {_bar(enemy.current_hp, enemy.max_hp, length=8)}"
        )
    embed.add_field(name="👹 Enemies", value="\n".join(enemy_lines), inline=False)

    if battle.is_over():
        result_text = {"won": "🏆 Victory!", "lost": "💀 Defeat..."}[battle.result]
        embed.add_field(name="Result", value=result_text, inline=False)
    else:
        embed.set_footer(text="Tap ℹ️ Info for status effects/cooldowns, 📜 Log for the full battle log.")

    return embed


def battle_log_embed(battle) -> discord.Embed:
    """The full battle log, shown via the 📜 Log button -- unlike the main
    battle message's brief in-line tail (now removed entirely in favor of
    this button, since the two purposes were fighting for the same
    limited embed space), this shows everything that's happened so far,
    trimmed from the oldest end only if it would overflow an embed
    description (4096 chars)."""
    embed = discord.Embed(title="📜 Battle Log", color=discord.Color.dark_grey())
    if not battle.log:
        embed.description = "*Nothing has happened yet.*"
        return embed

    lines = list(battle.log)
    text = "\n".join(lines)
    if len(text) > 4000:
        while lines and len("\n".join(lines)) > 3900:
            lines.pop(0)
        text = "*(earlier entries truncated)*\n" + "\n".join(lines)
    embed.description = text
    return embed


def battle_info_embed(battle) -> discord.Embed:
    """The ephemeral 'ℹ️ Info' view -- everything combat_embed leaves out
    to stay uncluttered: every combatant's active status effects
    (buffs/debuffs/DoTs/stun) and ability cooldowns."""
    embed = discord.Embed(title="ℹ️ Battlefield Info", color=discord.Color.blurple())

    def _status_lines(c) -> str:
        lines = []
        for p in c.passive_abilities:
            lines.append(f"🧬 **{p['name']}**: {p['description']}")
        for m in c.modifiers:
            sign = "+" if m.percent >= 0 else ""
            lines.append(f"{sign}{m.percent:g}% {m.stat} ({m.duration}t) -- {m.source}")
        for d in c.dots:
            lines.append(f"🔥 {d.flat_amount:g} dmg/turn ({d.duration}t) -- {d.source}")
        for h in c.heals:
            lines.append(f"🌿 {h.percent_max_hp:g}% max HP/turn ({h.duration}t) -- {h.source}")
        if c.stunned_turns > 0:
            lines.append(f"😵 Stunned ({c.stunned_turns}t)")
        for ability_id, remaining in c.cooldowns.items():
            if remaining > 0:
                ability = next(
                    (a for a in c.active_abilities if a["id"] == ability_id),
                    {"name": ability_id},
                )
                lines.append(f"⏳ {ability['name']} ready in {remaining}t")
        return "\n".join(lines) if lines else "*No active effects.*"

    for member in battle.party:
        if not member.is_alive():
            continue
        embed.add_field(name=f"🧑 **{member.name}**", value=_status_lines(member), inline=True)

    for enemy in battle.living_enemies():
        embed.add_field(name=f"👹 **{enemy.name}**", value=_status_lines(enemy), inline=True)

    embed.add_field(name="Turn", value=str(battle.turn_count), inline=False)
    return embed


def expedition_summary_embed(ledger: dict, won: bool) -> discord.Embed:
    """The whole-run tally shown once when an expedition ends -- win or
    lose -- on top of that final battle's own reward message. Everything
    here accumulated across every room of the run (combat rewards,
    treasure/secret/story/shrine rooms, trap/puzzle outcomes, encounter
    trades/gambles -- including merchant purchases, which are now just
    "trade"-action encounter choices), not just the last fight; see the
    `_ledger_*` helpers in bot/services/dungeon_service.py. Nothing is
    actually taken away on a loss -- gains from earlier in the run are
    kept -- so "lost" here means gold spent on encounter trades, not gold
    clawed back on defeat."""
    title = "🏆 Expedition Complete -- Summary" if won else "💀 Expedition Ended -- Summary"
    embed = discord.Embed(
        title=title,
        color=discord.Color.gold() if won else discord.Color.dark_gray(),
    )

    gained_lines = []
    if ledger["gold_gained"]:
        gained_lines.append(f"{format_currency('gold', ledger['gold_gained'])}")
    if ledger["shards_gained"]:
        gained_lines.append(f"{format_currency('shards', ledger['shards_gained'])}")
    if ledger["reroll_tokens_gained"]:
        gained_lines.append(f"{format_currency('reroll_tokens', ledger['reroll_tokens_gained'])}")
    if ledger["xp_gained"]:
        gained_lines.append(f"✨ {ledger['xp_gained']} XP")
    for material, qty in ledger["materials"].items():
        gained_lines.append(format_currency(material, qty))
    embed.add_field(
        name="📈 Gained",
        value="\n".join(gained_lines) if gained_lines else "*Nothing.*",
        inline=True,
    )

    spent_lines = []
    if ledger["gold_spent"]:
        spent_lines.append(f"{format_currency('gold', ledger['gold_spent'])} on trades")
    if ledger["reroll_tokens_spent"]:
        spent_lines.append(f"{format_currency('reroll_tokens', ledger['reroll_tokens_spent'])} on trades")
    embed.add_field(
        name="📉 Spent",
        value="\n".join(spent_lines) if spent_lines else "*Nothing.*",
        inline=True,
    )

    loot_lines = []
    for entry in ledger["items_found"]:
        loot_lines.append(f"{entry['name']} ({entry['rarity'].title()})")
    for entry in ledger["items_bought"]:
        loot_lines.append(f"{entry['name']} ({entry['rarity'].title()}, bought)")
    for tier, qty in ledger["lootboxes_found"].items():
        loot_lines.append(f"{qty}x {tier.title()} Lootbox")
    for tier, qty in ledger["lootboxes_bought"].items():
        loot_lines.append(f"{qty}x {tier.title()} Lootbox (bought)")
    if loot_lines:
        embed.add_field(name="🎒 Items & Lootboxes", value="\n".join(loot_lines), inline=False)

    if ledger["level_ups"]:
        level_lines = [
            f"{name} Lv.{lu['from']} → Lv.{lu['to']}" for name, lu in ledger["level_ups"].items()
        ]
        embed.add_field(name="📈 Level Ups", value="\n".join(level_lines), inline=False)

    return embed


# ----------------------------------------------------------------------
# Inventory -- detail mode (one item/lootbox at a time)
# ----------------------------------------------------------------------

def item_detail_embed(item, position: int | None = None, total: int | None = None) -> discord.Embed:
    """One item shown in full detail: main stat, substats, ability, and
    flavor text -- used by the /inventory detail browser."""
    color = RARITY_COLORS.get(item.rarity.value, discord.Color.light_grey())
    type_icon = SLOT_EMOJI[item.slot]
    embed = discord.Embed(title=f"{type_icon} {item.display_name}", color=color)

    embed.add_field(name="Rarity", value=f"{RARITY_EMOJI.get(item.rarity.value, '')} {item.rarity.value.title()}", inline=True)
    slot_label = SLOT_DISPLAY_NAME[item.slot]
    embed.add_field(name="Slot", value=f"{SLOT_EMOJI[item.slot]} {slot_label}", inline=True)
    embed.add_field(name="Item Level", value=str(item.item_level), inline=True)

    embed.add_field(
        name="Main Stat",
        value=_fmt_stat(item.main_stat_type, item.main_stat_value),
        inline=False,
    )

    if item.substats:
        lines = []
        for s in item.substats:
            suffix = "%" if s.get("value_type") == "percent" else ("%" if s["stat"] in PERCENT_STATS else "")
            label = STAT_LABEL.get(s["stat"], s["stat"].replace("_", " ").title())
            lines.append(f"{STAT_EMOJI.get(s['stat'], '')} +{s['value']:g}{suffix} {label}")
        embed.add_field(name="Substats", value="\n".join(lines), inline=False)

    if item.active_ability:
        a = item.active_ability
        if item.item_type == ItemType.ARTIFACT:
            heading = f"🔮 Artifact Skill: {a['name']}"
            cost_line = f"Cost: {a['resource_cost']} SP | Cooldown: {a['cooldown']} turn(s)"
        else:
            heading = f"⚔️ Weapon Skill: {a['name']}"
            cost_line = f"Cost: {a['resource_cost']} SP | Cooldown: {a['cooldown']} turn(s)"
        embed.add_field(name=heading, value=f"{a['description']}\n{cost_line}", inline=False)

    if item.passive_ability:
        p = item.passive_ability
        trigger_text = (
            "Always active" if p["trigger"] == "always"
            else f"Triggers: {p['trigger'].replace('_', ' ')}"
        )
        embed.add_field(name=f"🛡️ Passive: {p['name']}", value=f"{p['description']}\n{trigger_text}", inline=False)

    embed.add_field(
        name="Status", value="✅ Equipped" if item.is_equipped else "⬜ Not equipped", inline=True
    )

    from bot.game.loot.rarity_config import (
        add_substat_cost, reroll_cost, upgrade_level_cap, MAX_SUBSTATS,
    )
    from bot.services.inventory_service import get_sell_value
    from bot.services.item_upgrade_service import get_level_up_cost

    cap = upgrade_level_cap(item.rarity)
    if item.item_level < cap:
        next_cost = get_level_up_cost(item, levels=1)
        if next_cost["levels"] > 0:
            mat_text = ", ".join(
                format_currency(name, qty)
                for name, qty in next_cost["materials"].items() if qty > 0
            )
            value = format_currency("gold", next_cost["gold"]) + (f" + {mat_text}" if mat_text else "")
            embed.add_field(name=f"⬆️ Level Up Cost (Lv{item.item_level}→{item.item_level + 1}, cap {cap})", value=value, inline=False)
    else:
        embed.add_field(name="⬆️ Level Up", value=f"At cap ({cap}) for {item.rarity.value} rarity", inline=True)

    if item.substats:
        r_cost = reroll_cost(item.rarity)
        embed.add_field(name="🎲 Reroll Cost", value=f"{format_currency('reroll_tokens', r_cost['tokens'])} + {format_currency('gold', r_cost['gold'])}", inline=True)
    if len(item.substats) < MAX_SUBSTATS:
        a_cost = add_substat_cost(item.rarity)
        embed.add_field(name="➕ Add Substat Cost", value=f"{format_currency('reroll_tokens', a_cost['tokens'])} + {format_currency('gold', a_cost['gold'])}", inline=True)

    if not item.is_equipped:
        embed.add_field(name="💰 Sell Value", value=format_currency("gold", get_sell_value(item)), inline=True)

    if item.template is not None and item.template.flavor_text:
        embed.set_footer(text=item.template.flavor_text)

    if position is not None and total is not None:
        embed.description = f"Item {position + 1} of {total}"

    return embed


def lootbox_detail_embed(owned_lootbox, position: int | None = None, total: int | None = None) -> discord.Embed:
    from bot.game.economy.lootbox_config import LOOTBOX_RARITY_WEIGHTS

    template = owned_lootbox.template
    embed = discord.Embed(
        title=f"📦 {template.name}",
        description=template.description,
        color=discord.Color.purple(),
    )
    embed.add_field(name="Quantity Owned", value=str(owned_lootbox.quantity), inline=True)
    gold_range = f"{template.min_gold}-{template.max_gold} {currency_emoji('gold')}"
    embed.add_field(name="Contains", value=gold_range, inline=True)
    if template.max_shards:
        embed.add_field(name="Shards", value=f"{template.min_shards}-{template.max_shards} {currency_emoji('shards')}", inline=True)
    embed.add_field(name="Items per box", value=str(template.item_count), inline=True)

    weights = LOOTBOX_RARITY_WEIGHTS.get(template.tier)
    if weights:
        total_weight = sum(weights.values())
        odds_lines = [
            f"{RARITY_EMOJI.get(rarity.value, '⚪')} {rarity.value.title()}: {weight / total_weight * 100:.1f}%"
            for rarity, weight in sorted(weights.items(), key=lambda kv: -kv[1])
        ]
        embed.add_field(name="Item Rarity Odds", value="\n".join(odds_lines), inline=False)

    if position is not None and total is not None:
        embed.description = f"{template.description}\n\nEntry {position + 1} of {total}"

    return embed


def entry_detail_embed(entry, position: int, total: int) -> discord.Embed:
    if entry.kind == "lootbox":
        return lootbox_detail_embed(entry.obj, position, total)
    return item_detail_embed(entry.obj, position, total)


# ----------------------------------------------------------------------
# Inventory -- big list mode (compact, many-per-page)
# ----------------------------------------------------------------------

ITEMS_PER_LIST_PAGE = 12


def inventory_list_embed(entries: list, page: int, player_name: str) -> discord.Embed:
    total_pages = max(1, (len(entries) + ITEMS_PER_LIST_PAGE - 1) // ITEMS_PER_LIST_PAGE)
    page = max(0, min(page, total_pages - 1))
    start = page * ITEMS_PER_LIST_PAGE
    page_entries = entries[start:start + ITEMS_PER_LIST_PAGE]

    embed = discord.Embed(
        title=f"🎒 {player_name}'s Item Inventory",
        description=f"Page {page + 1}/{total_pages} -- {len(entries)} total items",
        color=discord.Color.dark_teal(),
    )

    if not page_entries:
        embed.add_field(name="Empty", value="Nothing here yet -- try `/adventure`, `/pull`, or `/open`.", inline=False)
        return embed

    lines = []
    for i, entry in enumerate(page_entries, start=start + 1):
        item = entry.obj
        rarity_emoji = RARITY_EMOJI.get(item.rarity.value, "⚪")
        type_icon = SLOT_EMOJI[item.slot]
        equipped_tag = " ✅" if item.is_equipped else ""
        lines.append(f"`{i:>3}.` {rarity_emoji} {type_icon} {item.display_name} (Lv{item.item_level}){equipped_tag}")

    embed.add_field(name="Items", value="\n".join(lines), inline=False)
    embed.set_footer(text="Use 🔍 Jump to # to go straight to an entry, or switch to Detail Mode to equip/sell/upgrade. Currencies, materials, and lootboxes are in /stash.")
    return embed


def general_inventory_embed(player, owned_lootboxes: list) -> discord.Embed:
    """The general inventory (/stash): currencies, tiered materials, and
    lootboxes -- everything that isn't a rolled item and so can't be
    equipped, sold, leveled, or rerolled the way /inventory's items can.
    Deliberately simpler than the item browser (one embed, no pagination
    or detail mode) since the set of currencies/materials is small and
    fixed and lootboxes only really need an Open action."""
    embed = discord.Embed(
        title=f"🎒 {player.username}'s General Inventory",
        description="Currencies, materials, and lootboxes -- can't be sold, only spent or opened.",
        color=discord.Color.dark_gold(),
    )

    embed.add_field(
        name="💰 Currencies",
        value=(
            f"🪙 Gold: {player.gold}\n"
            f"💎 Shards: {player.shards}\n"
            f"🎲 Reroll Tokens: {player.reroll_tokens}"
        ),
        inline=False,
    )

    tier_lines = {0: [], 1: [], 2: [], 3: []}
    for material in MaterialType:
        amount = getattr(player, material.value)
        emoji = MATERIAL_EMOJI.get(material, "◽")
        name = MATERIAL_DISPLAY_NAME.get(material, material.value.replace("_", " ").title())
        tier_lines[material.tier].append(f"{emoji} {name}: {amount}")

    tier_titles = {0: "Common Materials", 1: "Uncommon Materials", 2: "Rare Materials", 3: "Rarest Materials"}
    for tier in (0, 1, 2, 3):
        embed.add_field(name=f"🧱 {tier_titles[tier]}", value="\n".join(tier_lines[tier]), inline=True)

    if owned_lootboxes:
        lines = [f"📦 {o.template.name}: x{o.quantity}" for o in owned_lootboxes if o.quantity > 0]
        embed.add_field(
            name="🎁 Lootboxes",
            value="\n".join(lines) if lines else "*None.*",
            inline=False,
        )
        embed.set_footer(text="Tap a tier below to open all of your lootboxes of that tier.")
    else:
        embed.add_field(name="🎁 Lootboxes", value="*None yet -- try `/daily` or explore a dungeon!*", inline=False)
        embed.set_footer(text="Gear and rolled items live in /inventory instead.")

    return embed


# ----------------------------------------------------------------------
# Character gacha
# ----------------------------------------------------------------------

STAR_EMOJI = {3: "⭐⭐⭐", 4: "⭐⭐⭐⭐", 5: "⭐⭐⭐⭐⭐"}


def gacha_pull_embed(results: list[dict]) -> discord.Embed:
    """`results` is the list of per-pull dicts returned by
    character_gacha_service (template/is_new/dupe_reward)."""
    multi = len(results) > 1
    embed = discord.Embed(
        title="🎰 Gacha Results" if multi else "🎰 Gacha Result",
        color=discord.Color.gold(),
    )

    # Best pull first so a 10-pull doesn't bury its highlight at the bottom.
    ordered = sorted(results, key=lambda r: (-r["template"].star_rating, not r["is_new"]))

    lines = []
    for r in ordered:
        template = r["template"]
        stars = STAR_EMOJI.get(template.star_rating, "⭐" * template.star_rating)
        class_label = CLASS_DISPLAY_NAME[template.character_class]
        if r["is_new"]:
            tag = "**NEW!**"
        else:
            reward = r["dupe_reward"] or {}
            reward_text = ", ".join(f"+{v} {k.replace('_', ' ')}" for k, v in reward.items())
            tag = f"Duplicate ({reward_text})"
        lines.append(f"{stars} **{template.name}** ({class_label}) -- {tag}")

    # Discord field values cap at 1024 chars -- chunk a big 10-pull if needed.
    chunk, chunks, length = [], [], 0
    for line in lines:
        if length + len(line) + 1 > 1000:
            chunks.append("\n".join(chunk))
            chunk, length = [], 0
        chunk.append(line)
        length += len(line) + 1
    if chunk:
        chunks.append("\n".join(chunk))

    for i, text in enumerate(chunks):
        embed.add_field(name="Pulled" if i == 0 else "\u200b", value=text, inline=False)

    new_count = sum(1 for r in results if r["is_new"])
    if multi:
        embed.set_footer(text=f"{new_count}/{len(results)} new characters. Use /squad to update your active team.")
    else:
        embed.set_footer(text="Use /squad to bring your new character on expeditions.")
    return embed


def gacha_rates_embed() -> discord.Embed:
    from bot.game.economy.character_gacha_config import (
        MULTI_PULL_COST_SHARDS,
        SINGLE_PULL_COST_SHARDS,
        STAR_WEIGHTS,
    )

    total = sum(STAR_WEIGHTS.values())
    embed = discord.Embed(title="🎰 Gacha Rates", color=discord.Color.gold())
    lines = [
        f"{STAR_EMOJI[star]}: {weight / total * 100:.1f}%"
        for star, weight in sorted(STAR_WEIGHTS.items(), reverse=True)
    ]
    embed.add_field(name="Odds by Star Rating", value="\n".join(lines), inline=False)
    embed.add_field(
        name="Cost",
        value=f"Single pull: {SINGLE_PULL_COST_SHARDS} 💎 Shards\n10x pull: {MULTI_PULL_COST_SHARDS} 💎 Shards (10% off)",
        inline=False,
    )
    embed.add_field(
        name="Duplicates",
        value="Pulling a character you already own converts to gold + reroll tokens instead of a second copy.",
        inline=False,
    )
    embed.set_footer(text="Only characters drop from the gacha -- gear comes from dungeon runs and lootboxes.")
    return embed


# ----------------------------------------------------------------------
# Interactive dungeon rooms: Trap, Puzzle, Encounter
# ----------------------------------------------------------------------

def trap_embed(node: dict, choices: list[dict], message: str | None = None) -> discord.Embed:
    embed = discord.Embed(
        title=f"⚠️ Trap -- Floor {node['floor']}",
        description=message or "",
        color=discord.Color.dark_red(),
    )
    for choice in choices:
        odds = f"{int(choice['success_chance'] * 100)}% success"
        embed.add_field(name=choice["label"], value=f"{choice['description']}\n*{odds}*", inline=False)
    return embed


def puzzle_embed(node: dict, puzzle: dict, message: str | None = None) -> discord.Embed:
    embed = discord.Embed(
        title=f"🧩 Puzzle -- Floor {node['floor']}",
        description=(message or "") + f"\n\n**{puzzle['question']}**",
        color=discord.Color.dark_blue(),
    )
    for i, option in enumerate(puzzle["options"]):
        embed.add_field(name=f"Option {i + 1}", value=option, inline=False)
    return embed


def encounter_embed(node: dict, encounter: dict, message: str | None = None, player=None) -> discord.Embed:
    """Story-room NPC encounters (bot/game/dungeon/encounter_config.py) --
    unlike a plain fallback room, these carry their own flavor art (ported
    from the old JS bot's explore.js `imageUrl` fields), rendered full-size
    via set_image rather than as the usual avatar set_thumbnail.

    `player` is optional (only needed to show "you have" holdings) so
    this still works anywhere it's called without one on hand."""
    embed = discord.Embed(
        title=f"📜 {encounter['name']} -- Floor {node['floor']}",
        description=message or "",
        color=discord.Color.dark_purple(),
    )
    for choice in encounter["choices"]:
        value = choice["description"] or "\u200b"
        cost = choice.get("cost")
        if player is not None and cost:
            holdings = ", ".join(format_currency(currency, getattr(player, currency, 0)) for currency in cost)
            value = f"{value}\nYou have: {holdings}" if value != "\u200b" else f"You have: {holdings}"
        embed.add_field(name=choice["label"], value=value, inline=False)
    image_url = encounter.get("image_url")
    if image_url:
        embed.set_image(url=image_url)
    return embed


def quest_board_embed(beginner_quests: list, basic_quest, cooldown_remaining, player) -> discord.Embed:
    """`beginner_quests` is the full list of PlayerQuest rows (kind=
    "beginner") for this player, `basic_quest` is their current active
    basic PlayerQuest or None, and `cooldown_remaining` is a
    datetime.timedelta (or None if a new basic quest can be rolled right
    now) -- see quest_service.get_beginner_quests /
    get_active_basic_quest / basic_quest_cooldown_remaining."""
    embed = discord.Embed(title="📋 Quests", color=discord.Color.teal())

    descriptions_by_id = {q["id"]: q["description"] for q in BEGINNER_QUESTS}
    beginner_lines = []
    completed_count = 0
    for quest in beginner_quests:
        desc = descriptions_by_id.get(quest.quest_id, quest.quest_id)
        if quest.is_completed:
            completed_count += 1
            beginner_lines.append(f"✅ ~~{desc}~~")
        else:
            beginner_lines.append(f"⬜ {desc} ({quest.progress}/{quest.goal_count})")
    beginner_title = f"🌱 Beginner Quests ({completed_count}/{len(beginner_quests)})"
    if player.beginner_quest_bonus_claimed:
        beginner_title += " -- bonus claimed!"
    embed.add_field(name=beginner_title, value="\n".join(beginner_lines), inline=False)
    if not player.beginner_quest_bonus_claimed:
        embed.add_field(
            name="🎁 Completion Bonus",
            value=f"Finish every beginner quest above for {format_currency('shards', 300)}!",
            inline=False,
        )

    if basic_quest is not None:
        desc = next((q["description"] for q in BASIC_QUEST_POOL if q["id"] == basic_quest.quest_id), basic_quest.quest_id)
        reward = next((q["reward"] for q in BASIC_QUEST_POOL if q["id"] == basic_quest.quest_id), {})
        reward_text = ", ".join(format_currency(c, a) for c, a in reward.items())
        status = "✅ Complete!" if basic_quest.is_completed else f"{basic_quest.progress}/{basic_quest.goal_count}"
        embed.add_field(
            name="🎯 Basic Quest",
            value=f"{desc}\nProgress: {status}\nReward: {reward_text}",
            inline=False,
        )
    else:
        embed.add_field(name="🎯 Basic Quest", value="*No quest active.*", inline=False)

    if cooldown_remaining is None:
        embed.set_footer(text="A new basic quest is ready to roll!")
    else:
        hours, remainder = divmod(int(cooldown_remaining.total_seconds()), 3600)
        minutes = remainder // 60
        embed.set_footer(text=f"Next basic quest reroll available in {hours}h {minutes}m.")

    return embed
