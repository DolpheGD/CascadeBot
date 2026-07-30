"""
Inventory embeds.

Both /inventory modes (detail and compact list) plus the /stash
general-inventory view.
"""

from __future__ import annotations

import discord

from bot.database.models.enums import (
    ItemType,
    MATERIAL_DISPLAY_NAME,
    MATERIAL_EMOJI,
    MaterialType,
    SLOT_DISPLAY_NAME,
    SLOT_EMOJI,
)
from bot.services.currency_service import currency_emoji, format_currency
from bot.utils.embedder._shared import PERCENT_STATS, RARITY_COLORS, RARITY_EMOJI, STAT_EMOJI, STAT_LABEL, _fmt_stat


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

    if item.is_equipped and item.character is not None:
        status_value = f"✅ Equipped on {item.character.display_name}"
    elif item.is_equipped:
        status_value = "✅ Equipped"
    else:
        status_value = "⬜ Not equipped"
    embed.add_field(name="Status", value=status_value, inline=True)

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
        if item.is_equipped and item.character is not None:
            equipped_tag = f" ✅ *{item.character.display_name}*"
        elif item.is_equipped:
            equipped_tag = " ✅"
        else:
            equipped_tag = ""
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
