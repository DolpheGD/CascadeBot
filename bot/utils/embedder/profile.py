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
    embed.add_field(name="<:shard:1534383382924890192> Shards", value=str(player.shards), inline=True)
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


# ----------------------------------------------------------------------
# ACCOUNT PROFILE
#
# /profile used to be a per-character sheet, which duplicated what
# /characters is now for. It's the ACCOUNT view instead: one screen
# answering "how far along am I", with nothing on it that belongs to a
# single character.
# ----------------------------------------------------------------------

def account_profile_embed(player, summary: dict, avatar_url: str | None = None) -> discord.Embed:
    """The account overview. `summary` comes from
    account_service.account_summary -- the embed does no querying of its
    own, so the same numbers can back a leaderboard or an achievement
    check without being recomputed differently."""
    from bot.services.currency_service import format_currency

    level = summary["level"]
    embed = discord.Embed(
        title=f"{player.username}",
        color=discord.Color.blurple(),
    )
    if avatar_url:
        embed.set_thumbnail(url=avatar_url)

    if summary["maxed"]:
        progress_line = f"**Account Level {level}** — max"
    else:
        filled = int(summary["fraction"] * 12)
        bar = "█" * filled + "░" * (12 - filled)
        progress_line = (
            f"**Account Level {level}**\n"
            f"{bar}  {summary['into']}/{summary['needed']} to level {level + 1}"
        )
    embed.description = (
        f"{progress_line}\n"
        f"*Account level comes from your total character levels "
        f"({summary['total_levels']:,}) — the same measure domains and raids gate on.*"
    )

    embed.add_field(
        name="👥 Roster",
        value=(
            f"**{summary['characters_owned']}/{summary['characters_total']}** characters collected\n"
            f"Highest character: **Lv{summary['highest_character']}**\n"
            f"Fully resonated: **{summary['resonance_maxed']}**"
        ),
        inline=True,
    )
    embed.add_field(
        name="⚔️ Power",
        value=(
            f"Squad power: **{summary['squad_power']:,}**\n"
            f"Items owned: **{summary['items_owned']:,}**\n"
            f"Cascade HQ: **Lv{summary['hq_level']}**"
        ),
        inline=True,
    )
    embed.add_field(
        name="💰 Currencies",
        value=(
            f"{format_currency('gold', player.gold)} · {format_currency('shards', player.shards)}\n"
            f"{format_currency('echoes', player.echoes)} · "
            f"{format_currency('reroll_tokens', player.reroll_tokens)}"
        ),
        inline=False,
    )
    embed.set_footer(text="/characters for per-character stats · /stash for materials")
    return embed


# ----------------------------------------------------------------------
# GIFTS
# ----------------------------------------------------------------------

def gift_sent_embed(gift, recipient_mention: str, sends_left: int) -> discord.Embed:
    from bot.services.currency_service import format_currency

    embed = discord.Embed(
        title="🎁 Gift sent",
        description=f"On its way to {recipient_mention}. They collect it with `/gifts`.",
        color=discord.Color.green(),
    )
    embed.add_field(
        name="Contents",
        value="\n".join(format_currency(c, a) for c, a in gift.contents.items()),
        inline=False,
    )
    if gift.note:
        embed.add_field(name="Your note", value=gift.note, inline=False)
    embed.set_footer(text=f"{sends_left} gift(s) left to send today.")
    return embed


def gift_inbox_embed(player, pending: list) -> discord.Embed:
    """What's waiting to be collected. Shows the SENDER for each package
    rather than merging everything into one total -- a gift is from
    somebody, and stripping that out would make it indistinguishable from
    a system payout."""
    from bot.services.currency_service import format_currency

    embed = discord.Embed(title="🎁 Your Gifts", color=discord.Color.green())
    if not pending:
        embed.description = "Nothing waiting right now."
        return embed

    embed.description = f"**{len(pending)}** package(s) waiting."
    for gift in pending[:10]:
        sender = gift.sender.username if gift.sender else str(gift.sender_id)
        contents = " · ".join(format_currency(c, a) for c, a in (gift.contents or {}).items())
        value = contents or "*empty*"
        if gift.note:
            value += f"\n*“{gift.note}”*"
        embed.add_field(name=f"From {sender}", value=value, inline=False)
    if len(pending) > 10:
        embed.set_footer(text=f"...and {len(pending) - 10} more. Collect to see them all.")
    return embed


def gift_collected_embed(result: dict) -> discord.Embed:
    from bot.services.currency_service import format_currency

    totals = result["totals"]
    embed = discord.Embed(
        title="🎁 Gifts collected",
        description=f"Collected **{len(result['gifts'])}** package(s).",
        color=discord.Color.gold(),
    )
    embed.add_field(
        name="Received",
        value="\n".join(format_currency(c, a) for c, a in totals.items()) or "*Nothing.*",
        inline=False,
    )
    senders = sorted({(g.sender.username if g.sender else str(g.sender_id)) for g in result["gifts"]})
    embed.set_footer(text="Thanks to: " + ", ".join(senders[:8]))
    return embed
