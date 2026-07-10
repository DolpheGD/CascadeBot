"""
Every discord.Embed the bot renders lives here, kept separate from cogs so
presentation never gets tangled with interaction/DB plumbing.
"""

from __future__ import annotations

import discord

from bot.database.models.enums import (
    CLASS_DISPLAY_NAME,
    SLOT_DISPLAY_NAME,
    SLOT_EMOJI,
    EquipmentSlot,
    ItemType,
)
from bot.database.models.character_model import LEVEL_CAP
from bot.game.combat.combatant import STAT_KEYS
from bot.game.combat.factory import base_character_stats as _base_character_stats
from bot.game.combat.factory import build_character_combatant

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
    "max_hp": "HP", "max_mana": "MP", "crit_rate": "Crit Rate",
    "crit_damage": "Crit DMG", "recharge": "Recharge",
}

ITEM_TYPE_EMOJI = {
    ItemType.WEAPON: "⚔️", ItemType.ARMOR: "🛡️", ItemType.ARTIFACT: "🔮",
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
    player, character, equipped_items: list, avatar_url: str | None = None, page: int = 0
) -> discord.Embed:
    """`character` is the PlayerCharacter whose stats/gear/kit this profile
    shows -- normally the player's own avatar (see
    character_service.ensure_avatar_character). Full per-squad-member
    profile switching is a later UI pass; for now /profile always shows
    your avatar."""
    page = max(0, min(page, PROFILE_PAGE_COUNT - 1))
    if page == 0:
        return _profile_overview_page(player, character, equipped_items, avatar_url)
    if page == 1:
        return _profile_equipment_page(player, character, equipped_items, avatar_url)
    return _profile_abilities_page(player, character, equipped_items, avatar_url)


def _profile_overview_page(player, character, equipped_items, avatar_url) -> discord.Embed:
    combatant = build_character_combatant(character, equipped_items)

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
    base_lines = "\n".join(_fmt_stat(stat, base_stats[stat]) for stat in STAT_KEYS)
    embed.add_field(name="Base Stats", value=base_lines, inline=True)

    effective_lines = "\n".join(
        _fmt_stat_with_base(stat, combatant.base_stats[stat], base_stats[stat]) for stat in STAT_KEYS
    )
    embed.add_field(name="Effective Stats (with gear)", value=effective_lines, inline=True)

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

    def _skill_lines(skills: list) -> str:
        if not skills:
            return "*None equipped.*"
        return "\n".join(
            f"**{a['name']}** ({a['resource_cost']} MP): {a['description']}"
            for a in skills
        )

    if character_skill:
        embed.add_field(
            name="🌀 Character Skill",
            value=f"**{character_skill['name']}** ({character_skill['resource_cost']} MP): {character_skill['description']}",
            inline=False,
        )
    embed.add_field(name="⚔️ Weapon Skill", value=_skill_lines(weapon_skills), inline=False)
    embed.add_field(name="🔮 Artifact Skill", value=_skill_lines(artifact_skills), inline=False)

    if combatant.ultimate_ability:
        u = combatant.ultimate_ability
        embed.add_field(
            name="💥 Character Ultimate", value=f"**{u['name']}** (100 Energy): {u['description']}", inline=False
        )

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

    living_enemies = battle.living_enemies()
    enemy_lines = []
    for enemy in battle.enemies:
        if not enemy.is_alive():
            enemy_lines.append(f"**{enemy.name}** -- 💀 Defeated")
            continue
        is_target = living_enemies.index(enemy) == battle.target_index
        target_tag = " 🎯" if is_target else ""
        enemy_lines.append(
            f"**{enemy.name}**{target_tag}\n"
            f"┗ ❤️{enemy.current_hp}/{enemy.max_hp} {_bar(enemy.current_hp, enemy.max_hp, length=8)}"
        )
    embed.add_field(name="👹 Enemies", value="\n".join(enemy_lines), inline=False)

    log_tail = battle.log[-5:]
    if log_tail:
        embed.add_field(name="📜 Battle Log", value="\n".join(log_tail), inline=False)

    if battle.is_over():
        result_text = {"won": "🏆 Victory!", "lost": "💀 Defeat..."}[battle.result]
        embed.add_field(name="Result", value=result_text, inline=False)
    else:
        embed.set_footer(text="Tap ℹ️ Info for full status effects and cooldowns.")

    return embed


def battle_info_embed(battle) -> discord.Embed:
    """The ephemeral 'ℹ️ Info' view -- everything combat_embed leaves out
    to stay uncluttered: every combatant's active status effects
    (buffs/debuffs/DoTs/stun) and ability cooldowns."""
    embed = discord.Embed(title="ℹ️ Battlefield Info", color=discord.Color.blurple())

    def _status_lines(c) -> str:
        lines = []
        for m in c.modifiers:
            sign = "+" if m.percent >= 0 else ""
            lines.append(f"{sign}{m.percent:g}% {m.stat} ({m.duration}t) -- {m.source}")
        for d in c.dots:
            lines.append(f"🔥 {d.flat_amount:g} dmg/turn ({d.duration}t) -- {d.source}")
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
        embed.add_field(name=f"🧑 {member.name}", value=_status_lines(member), inline=True)

    for enemy in battle.living_enemies():
        embed.add_field(name=f"👹 {enemy.name}", value=_status_lines(enemy), inline=True)

    embed.add_field(name="Turn", value=str(battle.turn_count), inline=False)
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

    from bot.game.loot.rarity_config import (
        add_substat_cost, reroll_cost, upgrade_level_cap, MAX_SUBSTATS,
    )
    from bot.services.inventory_service import get_sell_value

    cap = upgrade_level_cap(item.rarity)
    if item.item_level < cap:
        embed.add_field(name="⬆️ Level Up Cost", value=f"~{15 * item.item_level} gold + materials / level (cap: {cap})", inline=True)
    else:
        embed.add_field(name="⬆️ Level Up", value=f"At cap ({cap}) for {item.rarity.value} rarity", inline=True)

    if item.substats:
        r_cost = reroll_cost(item.rarity)
        embed.add_field(name="🎲 Reroll Cost", value=f"{r_cost['tokens']} tokens + {r_cost['gold']} gold", inline=True)
    if len(item.substats) < MAX_SUBSTATS:
        a_cost = add_substat_cost(item.rarity)
        embed.add_field(name="➕ Add Substat Cost", value=f"{a_cost['tokens']} tokens + {a_cost['gold']} gold", inline=True)

    if not item.is_equipped:
        embed.add_field(name="💰 Sell Value", value=f"{get_sell_value(item)} gold", inline=True)

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
    gold_range = f"{template.min_gold}-{template.max_gold} gold"
    embed.add_field(name="Contains", value=gold_range, inline=True)
    if template.max_shards:
        embed.add_field(name="Shards", value=f"{template.min_shards}-{template.max_shards}", inline=True)
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
# Interactive dungeon rooms: Trap, Puzzle, Merchant
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


def shop_embed(player, offers: list[dict], message: str | None = None) -> discord.Embed:
    embed = discord.Embed(
        title="🛒 Cascade Quartermaster",
        description=message or "A basic supply cache -- gold only, no haggling.",
        color=discord.Color.dark_gold(),
    )
    embed.add_field(name="🪙 Your Gold", value=str(player.gold), inline=False)
    for offer in offers:
        embed.add_field(
            name=f"{offer['name']} -- {offer['cost_gold']} gold",
            value=offer["description"],
            inline=False,
        )
    embed.set_footer(text="Buy as many as you can afford, then Leave when you're done.")
    return embed
