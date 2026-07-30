"""
Encyclopedia embeds.

/encyclopedia -- read-only game-content reference.
"""

from __future__ import annotations

import discord

from bot.database.models.enums import (
    CLASS_DISPLAY_NAME,
    CLASS_EMOJI,
    MATERIAL_DISPLAY_NAME,
    MATERIAL_EMOJI,
    SLOT_DISPLAY_NAME,
    SLOT_EMOJI,
)
from bot.utils.embedder._shared import RARITY_COLORS, RARITY_EMOJI, STAT_LABEL, _fmt_stat


# ----------------------------------------------------------------------
# Encyclopedia (/encyclopedia) -- read-only game-content reference, built
# entirely from static data via bot.services.encyclopedia_service. No
# player/DB state involved, unlike everything else in this file.
# ----------------------------------------------------------------------

ENCYCLOPEDIA_ENTRIES_PER_PAGE = 12


def encyclopedia_categories_embed() -> discord.Embed:
    from bot.services import encyclopedia_service as enc

    embed = discord.Embed(
        title="📖 Cascade Encyclopedia",
        description="Pick a category from the dropdown below to browse.",
        color=discord.Color.dark_gold(),
    )
    for _key, label, blurb in enc.CATEGORIES:
        embed.add_field(name=label, value=blurb, inline=False)
    return embed


def encyclopedia_list_embed(category: str, entries: list, page: int) -> discord.Embed:
    from bot.services.encyclopedia_service import CATEGORY_LABELS

    total_pages = max(1, (len(entries) + ENCYCLOPEDIA_ENTRIES_PER_PAGE - 1) // ENCYCLOPEDIA_ENTRIES_PER_PAGE)
    page = max(0, min(page, total_pages - 1))
    start = page * ENCYCLOPEDIA_ENTRIES_PER_PAGE
    page_entries = entries[start:start + ENCYCLOPEDIA_ENTRIES_PER_PAGE]

    embed = discord.Embed(
        title=CATEGORY_LABELS[category],
        description=f"Page {page + 1}/{total_pages} -- {len(entries)} entries",
        color=discord.Color.dark_gold(),
    )
    if not page_entries:
        embed.add_field(name="Nothing here", value="No entries in this category.", inline=False)
        return embed

    lines = [f"`{i:>3}.` **{e.name}** -- {e.summary}" for i, e in enumerate(page_entries, start=start + 1)]
    # Discord caps a single embed field's value at 1024 chars. A page of
    # 12 entries normally fits comfortably, but categories with longer
    # per-entry summaries (e.g. enemies -- boss-group members get a
    # "fought alongside X, Y, Z" suffix) can push the joined text over
    # that limit and make the whole message fail to send. Chunk lines
    # across as many fields as needed instead of assuming one field is
    # always enough, so this holds for any category/page combination.
    DISCORD_FIELD_VALUE_LIMIT = 1024
    chunks: list[str] = []
    current = ""
    for line in lines:
        candidate = f"{current}\n{line}" if current else line
        if len(candidate) > DISCORD_FIELD_VALUE_LIMIT:
            if current:
                chunks.append(current)
            current = line
        else:
            current = candidate
    if current:
        chunks.append(current)

    for i, chunk in enumerate(chunks):
        embed.add_field(name="Entries" if i == 0 else "\u200b", value=chunk, inline=False)
    embed.set_footer(text="Pick an entry from the dropdown below to see full details.")
    return embed


def _encyclopedia_character_embed(entry, position, total) -> discord.Embed:
    from bot.services.encyclopedia_service import CHARACTER_BASE_STAT_KEYS

    t = entry.data["template"]
    kit = entry.data["kit"]
    stars = "⭐" * t["star_rating"]
    embed = discord.Embed(title=f"{stars} {t['name']}", description=t.get("bio", ""), color=discord.Color.gold())

    embed.add_field(
        name="Class",
        value=f"{CLASS_EMOJI.get(t['character_class'], '')} {CLASS_DISPLAY_NAME[t['character_class']]}",
        inline=True,
    )
    embed.add_field(name="Star Rating", value=stars, inline=True)

    stat_lines = [_fmt_stat(dest, t[src]) for src, dest in CHARACTER_BASE_STAT_KEYS if src in t]
    embed.add_field(name="Base Stats (Lv1)", value="\n".join(stat_lines), inline=False)

    if kit.get("skill"):
        s = kit["skill"]
        embed.add_field(
            name=f"🌀 Skill: {s['name']}",
            value=f"{s['description']}\nCost: {s['resource_cost']} SP | Cooldown: {s['cooldown']} turn(s)",
            inline=False,
        )
    if kit.get("ultimate"):
        u = kit["ultimate"]
        embed.add_field(
            name=f"💥 Ultimate: {u['name']}",
            value=f"{u['description']}\nCost: {u['resource_cost']} Energy",
            inline=False,
        )
    if kit.get("passive"):
        p = kit["passive"]
        embed.add_field(
            name=f"🛡️ Passive: {p['name']}",
            value=f"{p['description']}\nTriggers: {p['trigger'].replace('_', ' ')}",
            inline=False,
        )

    if position is not None and total is not None:
        embed.set_footer(text=f"Character {position + 1} of {total}")
    return embed


def _encyclopedia_class_embed(entry, position, total) -> discord.Embed:
    cls = entry.data["character_class"]
    kit = entry.data["kit"]
    embed = discord.Embed(
        title=f"{CLASS_EMOJI.get(cls, '')} {CLASS_DISPLAY_NAME[cls]}",
        description=entry.summary,
        color=discord.Color.teal(),
    )
    embed.add_field(
        name="Applies To",
        value="Your own avatar (`/start`) can freely switch between all four classes -- pulled characters have a fixed class instead.",
        inline=False,
    )
    s, u, p = kit["skill"], kit["ultimate"], kit["passive"]
    embed.add_field(
        name=f"🌀 Skill: {s['name']}",
        value=f"{s['description']}\nCost: {s['resource_cost']} SP | Cooldown: {s['cooldown']} turn(s)",
        inline=False,
    )
    embed.add_field(
        name=f"💥 Ultimate: {u['name']}",
        value=f"{u['description']}\nCost: {u['resource_cost']} Energy",
        inline=False,
    )
    embed.add_field(
        name=f"🛡️ Passive: {p['name']}",
        value=f"{p['description']}\nTriggers: {p['trigger'].replace('_', ' ')}",
        inline=False,
    )
    if position is not None and total is not None:
        embed.set_footer(text=f"Class {position + 1} of {total}")
    return embed


def _encyclopedia_enemy_embed(entry, position, total) -> discord.Embed:
    from bot.services.encyclopedia_service import ENEMY_STAT_KEYS, ROLE_LABELS, enemy_region_text

    t = entry.data["template"]
    embed = discord.Embed(
        title=f"👹 {t['name']}",
        description=ROLE_LABELS.get(t["role"], t["role"].title()),
        color=discord.Color.dark_red(),
    )
    embed.add_field(name="Found In", value=enemy_region_text(t), inline=False)

    stats = t["base_stats"]
    stat_lines = [_fmt_stat(k, stats[k]) for k in ENEMY_STAT_KEYS if k in stats]
    embed.add_field(name="Base Stats (Lv1)", value="\n".join(stat_lines), inline=False)
    embed.add_field(name="Level Scaling", value=f"+{t.get('level_scale_percent', 0)}% per level", inline=True)

    for a in t.get("active_abilities", []):
        cost = f"Cost: {a['resource_cost']} SP | Cooldown: {a['cooldown']} turn(s)"
        embed.add_field(name=f"⚔️ {a['name']}", value=f"{a['description']}\n{cost}", inline=False)

    ultimate = t.get("ultimate_ability")
    if ultimate:
        cost = f"Cost: {ultimate['resource_cost']} Energy"
        embed.add_field(name=f"💥 {ultimate['name']}", value=f"{ultimate['description']}\n{cost}", inline=False)

    for p in t.get("passive_abilities", []):
        embed.add_field(
            name=f"🛡️ {p['name']}",
            value=f"{p['description']}\nTriggers: {p['trigger'].replace('_', ' ')}",
            inline=False,
        )

    if position is not None and total is not None:
        embed.set_footer(text=f"Enemy {position + 1} of {total}")
    return embed


def _encyclopedia_ability_embed(entry, position, total) -> discord.Embed:
    a = entry.data["ability"]
    color = RARITY_COLORS.get(a["min_rarity"].value, discord.Color.light_grey())
    embed = discord.Embed(
        title=f"{entry.data['pool_emoji']} {a['name']}",
        description=f"{entry.data['pool_label']} -- min rarity {RARITY_EMOJI.get(a['min_rarity'].value, '')} {a['min_rarity'].value.title()}",
        color=color,
    )
    embed.add_field(name="Effect", value=a["description"], inline=False)
    if "resource_cost" in a:
        resource = "Energy" if a.get("resource_type") == "energy" else "SP"
        embed.add_field(name="Cost", value=f"{a['resource_cost']} {resource}", inline=True)
        embed.add_field(name="Cooldown", value=f"{a['cooldown']} turn(s)", inline=True)
    elif "trigger" in a:
        embed.add_field(name="Triggers", value=a["trigger"].replace("_", " ").title(), inline=True)
    if position is not None and total is not None:
        embed.set_footer(text=f"Ability {position + 1} of {total}")
    return embed


def _encyclopedia_material_embed(entry, position, total) -> discord.Embed:
    m = entry.data["material"]
    embed = discord.Embed(
        title=f"{MATERIAL_EMOJI.get(m, '')} {MATERIAL_DISPLAY_NAME[m]}",
        description=entry.data.get("blurb", ""),
        color=discord.Color.dark_grey(),
    )
    embed.add_field(name="Tier", value=str(m.tier), inline=True)
    embed.add_field(name="Used For", value="Leveling up equipment of a matching tier, alongside gold.", inline=False)
    if position is not None and total is not None:
        embed.set_footer(text=f"Material {position + 1} of {total}")
    return embed


def _encyclopedia_item_embed(entry, position, total) -> discord.Embed:
    t = entry.data["template"]
    embed = discord.Embed(
        title=f"{SLOT_EMOJI[t['slot']]} {entry.name}",
        description=t.get("flavor_text", ""),
        color=discord.Color.blurple(),
    )
    embed.add_field(name="Slot", value=f"{SLOT_EMOJI[t['slot']]} {SLOT_DISPLAY_NAME[t['slot']]}", inline=True)
    embed.add_field(name="Rarity Range", value=f"{t['min_rarity'].value.title()} - {t['max_rarity'].value.title()}", inline=True)
    embed.add_field(name="Main Stat", value=STAT_LABEL.get(t["main_stat"], t["main_stat"].replace("_", " ").title()), inline=True)
    if t.get("set_name"):
        embed.add_field(name="Set", value=t["set_name"], inline=True)
    linked_ability = entry.data.get("linked_ability")
    if linked_ability:
        embed.add_field(name=f"Grants: {linked_ability['name']}", value=linked_ability["description"], inline=False)
    if t.get("is_ultra_rare"):
        embed.add_field(name="✨ Ultra Rare", value="An especially rare piece, even among its set.", inline=False)
    if position is not None and total is not None:
        embed.set_footer(text=f"Item {position + 1} of {total}")
    return embed


_ENCYCLOPEDIA_DETAIL_RENDERERS = {
    "characters": _encyclopedia_character_embed,
    "classes": _encyclopedia_class_embed,
    "enemies": _encyclopedia_enemy_embed,
    "abilities": _encyclopedia_ability_embed,
    "materials": _encyclopedia_material_embed,
    "items": _encyclopedia_item_embed,
}


def encyclopedia_detail_embed(entry, position: int | None = None, total: int | None = None) -> discord.Embed:
    return _ENCYCLOPEDIA_DETAIL_RENDERERS[entry.category](entry, position, total)
