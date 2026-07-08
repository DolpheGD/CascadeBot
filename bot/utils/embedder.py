"""
Every discord.Embed the bot renders lives here, kept separate from cogs so
presentation never gets tangled with interaction/DB plumbing.
"""

from __future__ import annotations

import discord

from bot.database.models.enums import (
    SLOT_CAPACITY,
    SLOT_DISPLAY_NAME,
    SLOT_EMOJI,
    EquipmentSlot,
    ItemType,
    slot_index_label,
)
from bot.game.combat.combatant import STAT_KEYS
from bot.game.combat.factory import build_player_combatant

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
    "ancient": discord.Color.dark_gold(),
    "divine": discord.Color.gold(),
}

RARITY_EMOJI = {
    "common": "⚪", "uncommon": "🟢", "rare": "🔵", "epic": "🟣",
    "legendary": "🟠", "mythic": "🔴", "ancient": "🟤", "divine": "🟡",
}

STAT_EMOJI = {
    "attack": "⚔️", "defense": "🛡️", "elemental": "🔮", "speed": "💨",
    "max_hp": "❤️", "max_mana": "💧", "crit_rate": "🎯", "crit_damage": "💥",
    "recharge": "🔋",
}

STAT_LABEL = {
    "attack": "ATK", "defense": "DEF", "elemental": "ELE", "speed": "SPD",
    "max_hp": "HP", "max_mana": "MP", "crit_rate": "Crit Rate",
    "crit_damage": "Crit DMG", "recharge": "Recharge",
}

ITEM_TYPE_EMOJI = {
    ItemType.WEAPON: "⚔️", ItemType.ARMOR: "🛡️", ItemType.ARTIFACT: "🔮", ItemType.SCROLL: "📜",
}

PERCENT_STATS = {"crit_rate", "crit_damage"}


def _fmt_stat(stat: str, value: float) -> str:
    suffix = "%" if stat in PERCENT_STATS else ""
    label = STAT_LABEL.get(stat, stat.replace("_", " ").title())
    return f"{STAT_EMOJI.get(stat, '')} **{label}**: {value:g}{suffix}"


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
    player, equipped_items: list, avatar_url: str | None = None, page: int = 0
) -> discord.Embed:
    page = max(0, min(page, PROFILE_PAGE_COUNT - 1))
    if page == 0:
        return _profile_overview_page(player, equipped_items, avatar_url)
    if page == 1:
        return _profile_equipment_page(player, equipped_items, avatar_url)
    return _profile_abilities_page(player, equipped_items, avatar_url)


def _profile_overview_page(player, equipped_items, avatar_url) -> discord.Embed:
    combatant = build_player_combatant(player, equipped_items)

    embed = discord.Embed(
        title=f"{player.username}'s Profile",
        description=f"Page 1/{PROFILE_PAGE_COUNT} -- {PROFILE_PAGE_TITLES[0]}",
        color=discord.Color.blurple(),
    )
    if avatar_url:
        embed.set_thumbnail(url=avatar_url)

    embed.add_field(name="⭐ Level", value=str(player.level), inline=True)
    embed.add_field(name="✨ XP", value=f"{player.xp} / {player.xp_to_next_level()}", inline=True)
    embed.add_field(name="🪙 Gold", value=str(player.gold), inline=True)
    embed.add_field(name="💎 Shards", value=str(player.shards), inline=True)

    base_lines = "\n".join(_fmt_stat(stat, getattr(player, stat)) for stat in STAT_KEYS)
    embed.add_field(name="Base Stats", value=base_lines, inline=True)

    effective_lines = "\n".join(
        _fmt_stat(stat, combatant.base_stats[stat]) for stat in STAT_KEYS
    )
    embed.add_field(name="Effective Stats (with gear)", value=effective_lines, inline=True)

    embed.set_footer(text="Use the buttons below to see Equipment and Abilities.")
    return embed


def _profile_equipment_page(player, equipped_items, avatar_url) -> discord.Embed:
    by_slot: dict[EquipmentSlot, list] = {slot: [] for slot in EquipmentSlot}
    for item in equipped_items:
        by_slot[item.slot].append(item)
    for slot in by_slot:
        by_slot[slot].sort(key=lambda i: i.equip_slot_index)

    embed = discord.Embed(
        title=f"{player.username}'s Equipment",
        description=f"Page 2/{PROFILE_PAGE_COUNT} -- {PROFILE_PAGE_TITLES[1]}",
        color=discord.Color.dark_teal(),
    )
    if avatar_url:
        embed.set_thumbnail(url=avatar_url)

    for slot in EquipmentSlot:
        capacity = SLOT_CAPACITY[slot]
        items = by_slot[slot]
        lines = []
        for index in range(capacity):
            label = slot_index_label(slot, index) if capacity > 1 else None
            match = next((i for i in items if i.equip_slot_index == index), None)
            prefix = f"**{label}**: " if label else ""
            if match:
                rarity_emoji = RARITY_EMOJI.get(match.rarity.value, "⚪")
                lines.append(f"{prefix}{rarity_emoji} {match.display_name}")
            else:
                lines.append(f"{prefix}*Empty*")
        embed.add_field(
            name=f"{SLOT_EMOJI[slot]} {SLOT_DISPLAY_NAME[slot]}",
            value="\n".join(lines),
            inline=True,
        )

    embed.set_footer(text="Equip gear with /inventory. Weapons and Artifacts each hold 2.")
    return embed


def _profile_abilities_page(player, equipped_items, avatar_url) -> discord.Embed:
    combatant = build_player_combatant(player, equipped_items)

    embed = discord.Embed(
        title=f"{player.username}'s Abilities",
        description=f"Page 3/{PROFILE_PAGE_COUNT} -- {PROFILE_PAGE_TITLES[2]}",
        color=discord.Color.dark_purple(),
    )
    if avatar_url:
        embed.set_thumbnail(url=avatar_url)

    weapon_skills = [a for a in combatant.active_abilities if a.get("source") == "weapon"]
    artifact_skills = [a for a in combatant.active_abilities if a.get("source") == "artifact"]

    def _skill_lines(skills: list) -> str:
        if not skills:
            return "*None equipped.*"
        return "\n".join(
            f"**{a['name']}** ({a['resource_cost']} MP): {a['description']}"
            for a in skills
        )

    embed.add_field(name="⚔️ Weapon Skills", value=_skill_lines(weapon_skills), inline=False)
    embed.add_field(name="🔮 Artifact Skills", value=_skill_lines(artifact_skills), inline=False)

    if combatant.ultimate_ability:
        u = combatant.ultimate_ability
        embed.add_field(
            name="💥 Ultimate", value=f"**{u['name']}** (100 Energy): {u['description']}", inline=False
        )
    else:
        embed.add_field(name="💥 Ultimate", value="*No scroll equipped.*", inline=False)

    if combatant.passive_abilities:
        lines = "\n".join(
            f"**{p['name']}**: {p['description']}" for p in combatant.passive_abilities
        )
    else:
        lines = "*No armor passives active.*"
    embed.add_field(name="🛡️ Passives (from Armor)", value=lines, inline=False)

    embed.set_footer(text="Basic Attack always builds Energy + Mana by your Recharge stat.")
    return embed


# ----------------------------------------------------------------------
# Dungeon map
# ----------------------------------------------------------------------

def dungeon_map_embed(
    expedition, message: str | None = None, avatar_url: str | None = None
) -> discord.Embed:
    """Shows the current node and, if given, a one-line result of what just
    happened (e.g. 'You find a treasure chest...')."""
    node = expedition.graph["nodes"][expedition.current_node_id]
    emoji = ROOM_TYPE_EMOJI.get(node["room_type"], "❔")

    embed = discord.Embed(
        title=f"{expedition.region} -- Floor {node['floor']}",
        description=message or "",
        color=discord.Color.dark_green(),
    )
    if avatar_url:
        embed.set_thumbnail(url=avatar_url)

    embed.add_field(name="Current Room", value=f"{emoji} {node['room_type'].title()}", inline=True)
    embed.add_field(name="❤️ HP", value=f"{expedition.current_hp}", inline=True)

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


def combat_embed(battle, avatar_url: str | None = None) -> discord.Embed:
    """Renders the current battle state: HP/resource bars for everyone, the
    turn order preview, current target marker, and the last few log lines,
    so a Discord message can be edited in place turn after turn."""
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

    player = battle.player
    ult_flag = " | 💥 ULTIMATE READY" if player.ultimate_ready() else ""
    player_value = (
        f"❤️ {player.current_hp}/{player.max_hp} {_bar(player.current_hp, player.max_hp)}\n"
        f"💧 {player.mana}/{player.max_mana} | 🔋 {player.energy}/{player.max_energy}{ult_flag}"
    )
    embed.add_field(name=f"🧑 {player.name}", value=player_value, inline=False)

    living_enemies = battle.living_enemies()
    for enemy in battle.enemies:
        is_target = enemy.is_alive() and living_enemies.index(enemy) == battle.player_target_index
        target_tag = " 🎯" if is_target else ""
        status = "💀 Defeated" if not enemy.is_alive() else (
            f"❤️ {enemy.current_hp}/{enemy.max_hp} {_bar(enemy.current_hp, enemy.max_hp)}"
        )
        embed.add_field(name=f"👹 {enemy.name}{target_tag}", value=status, inline=True)

    log_tail = battle.log[-6:]
    if log_tail:
        embed.add_field(name="📜 Battle Log", value="\n".join(log_tail), inline=False)

    if battle.is_over():
        result_text = {"won": "🏆 Victory!", "lost": "💀 Defeat..."}[battle.result]
        embed.add_field(name="Result", value=result_text, inline=False)

    return embed


# ----------------------------------------------------------------------
# Inventory -- detail mode (one item/lootbox at a time)
# ----------------------------------------------------------------------

def item_detail_embed(item, position: int | None = None, total: int | None = None) -> discord.Embed:
    """One item shown in full detail: main stat, substats, ability, and
    flavor text -- used by the /inventory detail browser."""
    color = RARITY_COLORS.get(item.rarity.value, discord.Color.light_grey())
    type_icon = ITEM_TYPE_EMOJI.get(item.item_type, "📦")
    embed = discord.Embed(title=f"{type_icon} {item.display_name}", color=color)

    embed.add_field(name="Rarity", value=f"{RARITY_EMOJI.get(item.rarity.value, '')} {item.rarity.value.title()}", inline=True)
    slot_label = SLOT_DISPLAY_NAME[item.slot]
    if item.is_equipped and SLOT_CAPACITY[item.slot] > 1:
        slot_label += f" ({slot_index_label(item.slot, item.equip_slot_index)})"
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
            kind_tag = " (of base)" if s.get("value_type") == "percent" else ""
            label = STAT_LABEL.get(s["stat"], s["stat"].replace("_", " ").title())
            lines.append(f"{STAT_EMOJI.get(s['stat'], '')} +{s['value']:g}{suffix} {label}{kind_tag}")
        embed.add_field(name="Substats", value="\n".join(lines), inline=False)

    if item.active_ability:
        a = item.active_ability
        if item.item_type == ItemType.SCROLL:
            heading = f"💥 Ultimate: {a['name']}"
            cost_line = f"Cost: {a['resource_cost']} Energy (usable once Energy reaches 100)"
        elif item.item_type == ItemType.ARTIFACT:
            heading = f"🔮 Artifact Skill: {a['name']}"
            cost_line = f"Cost: {a['resource_cost']} Mana | Cooldown: {a['cooldown']} turn(s)"
        else:
            heading = f"⚔️ Weapon Skill: {a['name']}"
            cost_line = f"Cost: {a['resource_cost']} Mana | Cooldown: {a['cooldown']} turn(s)"
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

    if item.template is not None and item.template.flavor_text:
        embed.set_footer(text=item.template.flavor_text)

    if position is not None and total is not None:
        embed.description = f"Item {position + 1} of {total}"

    return embed


def lootbox_detail_embed(owned_lootbox, position: int | None = None, total: int | None = None) -> discord.Embed:
    template = owned_lootbox.template
    embed = discord.Embed(
        title=f"📦 {template.name}",
        description=template.description,
        color=discord.Color.purple(),
    )
    embed.add_field(name="Quantity Owned", value=str(owned_lootbox.quantity), inline=True)
    gold_range = f"{template.min_gold}-{template.max_gold} gold"
    embed.add_field(name="Contains", value=gold_range, inline=True)
    if template.max_shards:
        embed.add_field(name="Shards", value=f"{template.min_shards}-{template.max_shards}", inline=True)
    embed.add_field(name="Items per box", value=str(template.item_count), inline=True)

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
        title=f"🎒 {player_name}'s Inventory",
        description=f"Page {page + 1}/{total_pages} -- {len(entries)} total entries",
        color=discord.Color.dark_teal(),
    )

    if not page_entries:
        embed.add_field(name="Empty", value="Nothing here yet -- try `/adventure`, `/pull`, or `/daily`.", inline=False)
        return embed

    lines = []
    for i, entry in enumerate(page_entries, start=start + 1):
        if entry.kind == "lootbox":
            template = entry.obj.template
            lines.append(f"`{i:>3}.` 📦 {template.name} x{entry.obj.quantity}")
        else:
            item = entry.obj
            rarity_emoji = RARITY_EMOJI.get(item.rarity.value, "⚪")
            type_icon = ITEM_TYPE_EMOJI.get(item.item_type, "📦")
            equipped_tag = " ✅" if item.is_equipped else ""
            lines.append(f"`{i:>3}.` {rarity_emoji} {type_icon} {item.display_name} (Lv{item.item_level}){equipped_tag}")

    embed.add_field(name="Items", value="\n".join(lines), inline=False)
    embed.set_footer(text="Use 🔍 Jump to # to go straight to an entry, or switch to Detail Mode to equip/open/upgrade.")
    return embed
