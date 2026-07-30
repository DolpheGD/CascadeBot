"""
Profile embeds.

The 3-page /profile view: Overview, Equipment, Abilities.
"""

from __future__ import annotations

import discord

from bot.database.models.enums import (
    CLASS_DISPLAY_NAME,
    EquipmentSlot,
    SLOT_CAPACITY,
    SLOT_DISPLAY_NAME,
    SLOT_EMOJI,
)
from bot.database.models.character_model import LEVEL_CAP
from bot.game.combat.combatant import STAT_KEYS
from bot.game.combat.factory import base_character_stats, build_character_combatant
from bot.utils.embedder._shared import RARITY_EMOJI, _fmt_stat_with_base


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
        title=f"{player.username}'s Profile -- {character.display_name}",
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

    base_stats = base_character_stats(character)
    stat_lines = "\n".join(
        _fmt_stat_with_base(stat, combatant.base_stats[stat], base_stats[stat]) for stat in STAT_KEYS
    )
    embed.add_field(name="Stats -- (base) effective", value=stat_lines, inline=False)

    embed.set_footer(text="Use the buttons below to see Equipment and Abilities.")
    return embed


def _profile_equipment_page(player, character, equipped_items, avatar_url) -> discord.Embed:
    by_slot: dict[EquipmentSlot, list] = {slot: [] for slot in EquipmentSlot}
    for item in equipped_items:
        by_slot[item.slot].append(item)
    for slot_items in by_slot.values():
        slot_items.sort(key=lambda it: it.id)

    embed = discord.Embed(
        title=f"{character.display_name}'s Equipment",
        description=f"Page 2/{PROFILE_PAGE_COUNT} -- {PROFILE_PAGE_TITLES[1]}",
        color=discord.Color.dark_teal(),
    )
    if avatar_url:
        embed.set_thumbnail(url=avatar_url)

    for slot in EquipmentSlot:
        capacity = SLOT_CAPACITY[slot]
        items = by_slot[slot]
        lines = []
        for i in range(capacity):
            if i < len(items):
                match = items[i]
                rarity_emoji = RARITY_EMOJI.get(match.rarity.value, "⚪")
                lines.append(f"{rarity_emoji} {match.display_name}")
            else:
                lines.append("*Empty*")
        name = f"{SLOT_EMOJI[slot]} {SLOT_DISPLAY_NAME[slot]}" + (f" ({len(items)}/{capacity})" if capacity > 1 else "")
        embed.add_field(name=name, value="\n".join(lines), inline=True)

    embed.set_footer(text="Equip gear with /inventory. Weapon/Artifact hold 1 item; Armor/Accessory hold 2 each.")
    return embed


def _profile_abilities_page(player, character, equipped_items, avatar_url) -> discord.Embed:
    combatant = build_character_combatant(character, equipped_items)

    embed = discord.Embed(
        title=f"{character.display_name}'s Abilities",
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
