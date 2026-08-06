"""
Domains embeds.

/domains -- energy-gated single-battle challenges.
"""

from __future__ import annotations

import discord

from bot.services import domain_service
from bot.game.economy.domain_config import DOMAIN_DIFFICULTY_TIERS, DOMAIN_TYPES
from bot.services.currency_service import format_currency
from bot.utils.embedder._shared import _bar


# ----------------------------------------------------------------------
# Domains (/domains) -- energy-gated single-battle challenges against a
# fixed enemy squad, for direct on-demand rewards. See
# bot/services/domain_service.py and bot/game/economy/domain_config.py.
# ----------------------------------------------------------------------

def _energy_bar_line(db, player) -> str:
    """Energy cap is per-player now (it scales with Cascade HQ level --
    see domain_config.DOMAIN_ENERGY_BY_HQ_LEVEL), so this needs a session
    to look it up rather than reading a module constant."""
    current = domain_service.get_current_energy(db, player)
    cap = domain_service.energy_cap(db, player)
    bar = _bar(current, cap, length=12)
    line = f"⚡ {current}/{cap} {bar}"
    next_point = domain_service.time_until_next_energy_point(db, player)
    if next_point is not None:
        minutes = int(next_point.total_seconds() // 60) + 1
        line += f"\n*Next point in {minutes}m*"
    return line


def _energy_source_line(db, player) -> str:
    """WHERE THE CEILING COMES FROM, AND HOW TO RAISE IT.

    The cap has scaled with Cascade HQ since it stopped being a flat 120
    (see the block above DOMAIN_ENERGY_BY_HQ_LEVEL), but nothing on any
    screen ever said so. From the player's side the number just sat
    there: no stated source, no way to tell it could move, and no hint
    that the base -- a completely different command -- was the lever. A
    stat you can upgrade but can't discover is one nobody upgrades.

    So this itemises the bar the way a receipt does: what each source
    contributes now, and what the next step of each is worth. The regen
    rate is stated too, because it is the most common wrong assumption
    about the system -- a bigger bar stores more attempts, it does not
    earn energy faster, and a player who upgrades HQ expecting a faster
    refill has been misled by the bar alone."""
    from bot.services import base_service, research_service
    from bot.game.economy.domain_config import (
        DOMAIN_ENERGY_BY_HQ_LEVEL, ENERGY_REGEN_MINUTES_PER_POINT, max_domain_energy,
    )

    hq_level = base_service.get_hq_level(db, player)
    from_hq = max_domain_energy(hq_level)
    from_lab = int(research_service.perk_value(db, player.id, "domain_energy"))

    parts = [f"🏠 **Cascade HQ level {hq_level}** — {from_hq} energy"]
    if from_lab:
        parts.append(f"🔬 **Research Lab** (Expansion branch) — +{from_lab}")

    # What the next rung of each track is actually worth, in energy.
    top_hq = max(DOMAIN_ENERGY_BY_HQ_LEVEL)
    if hq_level < top_hq:
        gain = max_domain_energy(hq_level + 1) - from_hq
        parts.append(
            f"→ `/base hq` — upgrading to HQ {hq_level + 1} adds **+{gain}**"
        )
    else:
        parts.append("→ HQ is maxed for energy purposes.")
    if from_lab < _MAX_LAB_DOMAIN_ENERGY:
        parts.append(
            f"→ `/base lab` — the Expansion branch adds up to "
            f"**+{_MAX_LAB_DOMAIN_ENERGY}** in total"
        )

    hours = cap_refill_hours(domain_service.energy_cap(db, player))
    parts.append(
        f"*Regen is a flat 1 per {ENERGY_REGEN_MINUTES_PER_POINT} min at every HQ "
        f"level — a full bar takes ~{hours}h. Upgrading stores more attempts, "
        f"it doesn't earn faster.*"
    )
    return "\n".join(parts)


def cap_refill_hours(cap: int) -> int:
    from bot.game.economy.domain_config import ENERGY_REGEN_MINUTES_PER_POINT
    return round(cap * ENERGY_REGEN_MINUTES_PER_POINT / 60)


def _max_lab_domain_energy() -> int:
    from bot.game.economy.research_config import RESEARCH_PROJECTS
    return sum(p.get("value", 0) for p in RESEARCH_PROJECTS
               if p.get("perk") == "domain_energy")


_MAX_LAB_DOMAIN_ENERGY = _max_lab_domain_energy()


def domain_menu_embed(db, player) -> discord.Embed:
    """Top-level /domains screen: energy status + every domain type."""
    embed = discord.Embed(title="🌀 Domains", color=discord.Color.dark_purple())
    embed.add_field(name="Energy", value=_energy_bar_line(db, player), inline=False)
    # The menu is where a player decides whether domains are worth their
    # time, so it's where the ceiling needs explaining. The tier screen
    # gets the short version -- by then they're already spending.
    embed.add_field(name="Where your energy cap comes from",
                    value=_energy_source_line(db, player), inline=False)
    for domain in DOMAIN_TYPES:
        embed.add_field(name=f"{domain['icon']} {domain['name']}", value=domain["description"], inline=False)
    embed.set_footer(text="Pick a domain below to see its difficulty tiers.")
    return embed


def domain_tier_embed(db, domain: dict, player, lock_reasons: dict[str, str | None] | None = None) -> discord.Embed:
    """Shown after picking a domain type: energy status + every
    difficulty tier for THIS domain, with its reward, unlock requirement,
    and energy cost. Locked tiers are still shown (so the player can see
    what's coming) but marked with WHY they're locked -- affordability is
    conveyed by the tier buttons themselves, not here.

    `lock_reasons` maps tier_id -> None (unlocked) or a short reason
    string, resolved by the caller via domain_service.tier_lock_reason
    (which needs a DB session; this module deliberately has none)."""
    lock_reasons = lock_reasons or {}
    embed = discord.Embed(
        title=f"{domain['icon']} {domain['name']}", description=domain["description"],
        color=discord.Color.dark_purple(),
    )
    embed.add_field(name="Energy", value=_energy_bar_line(db, player), inline=False)

    for tier in DOMAIN_DIFFICULTY_TIERS:
        reward = domain["rewards"][tier["id"]]
        if domain["reward_kind"] == "currency":
            reward_text = ", ".join(format_currency(c, a) for c, a in reward.items())
        elif domain["reward_kind"] == "lootbox":
            lootbox_tier, quantity = reward
            reward_text = f"{quantity}x {lootbox_tier.title()} Lootbox"
        else:
            reward_text = f"{reward} XP (split across squad)"

        reason = lock_reasons.get(tier["id"])
        if reason is not None:
            name = f"🔒 {tier['name']}"
            reward_text = f"*Locked: {reason}*\n{reward_text}"
        else:
            name = f"{tier['name']} -- {tier['energy_cost']} ⚡"
            offset = tier.get("level_offset", 0)
            sign = "+" if offset >= 0 else ""
            reward_text = f"*Enemies at squad Lv{sign}{offset}*\n{reward_text}"
        embed.add_field(name=name, value=reward_text, inline=True)

    # Short form of the source note. The menu screen itemises it; here
    # the player is mid-decision and only needs to know the ceiling isn't
    # fixed and which command moves it.
    embed.set_footer(
        text="Domain enemies scale to your squad's average level -- levelling up raises the "
             "challenge as well as your power.\n"
             "Energy capacity comes from your Cascade HQ level -- raise it with /base hq."
    )
    return embed


def domain_result_embed(result: dict) -> discord.Embed:
    """Shown once a domain battle ends -- see domain_service.resolve_challenge."""
    domain, tier = result["domain"], result["tier"]
    if result["won"]:
        title = f"✅ {tier['name']} {domain['name']} cleared!"
        color = discord.Color.green()
        body = "\n".join(result["reward_lines"]) if result["reward_lines"] else "*Nothing this time.*"
    else:
        title = f"💀 {tier['name']} {domain['name']} failed"
        color = discord.Color.red()
        body = "No reward this attempt -- the energy spent isn't refunded, but nothing else is lost. Try a lower tier, or gear up and come back."
    embed = discord.Embed(title=title, description=body, color=color)
    return embed
