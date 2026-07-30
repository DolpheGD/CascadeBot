"""
Character gacha embeds.

/pull results and the /pull_rates odds table.
"""

from __future__ import annotations

import discord

from bot.database.models.enums import (
    CLASS_DISPLAY_NAME,
)


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
