"""
Character gacha embeds.

/pull results, and the Echo Exchange storefronts.
"""

from __future__ import annotations

import discord

from bot.services.currency_service import currency_emoji

from bot.database.models.enums import (
    CLASS_DISPLAY_NAME,
)
from bot.game.economy import resonance_config
from bot.utils.embedder._shared import fit_field


# ----------------------------------------------------------------------
# Character gacha
# ----------------------------------------------------------------------

STAR_EMOJI = {3: "⭐⭐⭐", 4: "⭐⭐⭐⭐", 5: "⭐⭐⭐⭐⭐"}


def star_label(star: int) -> str:
    """Compact "5★" form, for places that MENTION a rarity rather than
    LABEL one.

    The full ⭐ run is the strongest signal in the gacha UI: a row of
    five is meant to be recognisable at a glance, without reading. That
    only works if five stars in a row is rare on screen. The pity panel
    and the odds table were both printing full runs several times each,
    so a menu could show three or four "5-star" shapes none of which was
    a 5-star character -- which is exactly the glance the signal is for.

    So: ⭐ runs stay on things that ARE a character of that rarity, and
    everything that merely refers to a tier uses this instead."""
    return f"{star}★"


def gacha_pull_embed(results: list[dict], player=None) -> discord.Embed:
    """`results` is the list of per-pull dicts returned by
    character_gacha_service (template/is_new/dupe_reward/from_pity).

    `player` is optional and only used to append the post-pull pity
    status -- passing it lets the player see how close the next
    guarantee is without leaving the banner, which is the
    single most-wanted piece of information right after a pull."""
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
            # A duplicate now leads with what it DID -- the resonance
            # level it unlocked, named -- rather than the currency it
            # converted to. "Duplicate (+500 gold)" read as a miss; "R3
            # Deep Resonance" reads as the upgrade it actually is.
            dupe = r["dupe_reward"] or {}
            echoes = dupe.get("echoes", 0)
            level = dupe.get("level")
            if level is not None:
                tag = f"**R{level['level']} {level['name']}!** +{echoes} ✴️"
            elif dupe.get("maxed"):
                tag = f"Duplicate — R{resonance_config.MAX_RESONANCE} maxed, +{echoes} ✴️"
            else:
                tag = f"Duplicate — +{echoes} ✴️"
        pity_tag = " 🎟️ *guaranteed*" if r.get("from_pity") else ""
        lines.append(f"{stars} **{template.name}** ({class_label}) -- {tag}{pity_tag}")

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

    if player is not None:
        embed.add_field(name="🎟️ Pity", value=_pity_status_lines(player), inline=False)

    # Echoes earned, and what they're for. Shown on every pull that
    # produced a duplicate, because the whole point of the currency is
    # that a duplicate-heavy pull is still progress -- and a player who
    # doesn't know the exchange exists just sees a number.
    earned = sum((r["dupe_reward"] or {}).get("echoes", 0) for r in results)
    if earned:
        balance = f" (you have {player.echoes:,})" if player is not None else ""
        embed.add_field(
            name=f"✴️ +{earned} Echoes{balance}",
            value="Spend them in `/exchange` on any character you want.",
            inline=False,
        )

    new_count = sum(1 for r in results if r["is_new"])
    if multi:
        embed.set_footer(text=f"{new_count}/{len(results)} new characters. Use /squad to update your active team.")
    else:
        embed.set_footer(text="Use /squad to bring your new character on expeditions.")
    return embed


# ----------------------------------------------------------------------
# THE ECHO EXCHANGE
#
# THE EMBED SHOWS ONE PAGE, NOT THE WHOLE CATALOG.
#
# It used to list all 29 characters at once while the select underneath
# was paged 25 at a time -- so the screen was already an enormous wall of
# text, and the wall didn't even agree with the menu below it about what
# was on offer. Adding the 26-card catalog to the same screen would have
# made it 55 rows: past the 6,000-character embed budget, and long before
# that, past the point anyone reads it.
#
# So the embed renders exactly the window the select is showing. The page
# controls now move BOTH, which also means the two can no longer disagree
# about what page you are on.
# ----------------------------------------------------------------------

def _exchange_header(player) -> str:
    return (
        f"**{player.echoes:,} ✴️ Echoes** · **{player.cores:,} "
        f"{currency_emoji('cores')} Cores**"
    )


def echo_exchange_embed(player, offers: list[dict], page: int = 0,
                        per_page: int = 25, total: int | None = None) -> discord.Embed:
    """The Characters counter: what a character costs in Echoes and
    whether you can afford it.

    `offers` is the WINDOW being shown, already sorted and sliced by the
    view; `total` is how many exist overall, for the page footer. Owned
    characters are still listed rather than hidden, because buying a
    duplicate of someone you already have is a legitimate (and for a
    favourite character, the ONLY deterministic) way to push their
    Resonance -- see resonance_config."""
    embed = discord.Embed(
        title="✴️ Echo Exchange — Characters",
        description=(
            f"{_exchange_header(player)}\n"
            "Every duplicate you pull pays Echoes. Spend them here on exactly the "
            "character you want -- no rates, no pity, no luck.\n"
            "Buying someone you already own raises their **Resonance** instead."
        ),
        color=discord.Color.purple(),
    )
    by_star: dict[int, list[str]] = {}
    for offer in offers:
        mark = "✅" if offer["affordable"] else "🔒"
        owned = ""
        if offer["owned"]:
            owned = (f" · R{offer['resonance']}"
                     if offer["resonance"] < resonance_config.MAX_RESONANCE
                     else f" · R{resonance_config.MAX_RESONANCE} MAX")
        by_star.setdefault(offer["star_rating"], []).append(
            f"{mark} **{offer['name']}** — {offer['cost']:,} ✴️{owned}"
        )
    for star in sorted(by_star, reverse=True):
        embed.add_field(
            name=f"{STAR_EMOJI.get(star, '⭐' * star)}",
            value=fit_field(by_star[star]),
            inline=False,
        )
    embed.set_footer(text=_page_footer(
        page, per_page, total if total is not None else len(offers),
        "Duplicates past Resonance 5 pay more than double the Echoes."))
    return embed


def echo_card_exchange_embed(player, offers: list[dict], page: int = 0,
                             per_page: int = 25,
                             total: int | None = None) -> discord.Embed:
    """The Cards counter.

    Each row carries the card's ABILITY rather than just its name. Card
    names are deliberately lore phrases -- "The Comma After Good Luck"
    tells a player nothing about whether it is the one they are saving
    for, and a shop you cannot shop in is a list.
    """
    embed = discord.Embed(
        title="✴️ Echo Exchange — Character Cards",
        description=(
            f"{_exchange_header(player)}\n"
            "The card banner's deterministic half. Buy the exact Card you want "
            "instead of rolling for it.\n"
            "A second copy of a card you own is **not** wasted — one card sits on "
            "one character, so two copies run the same ability on two of them."
        ),
        color=discord.Color.purple(),
    )
    by_star: dict[int, list[str]] = {}
    for offer in offers:
        mark = "✅" if offer["affordable"] else "🔒"
        owned = f" · owned ×{offer['owned']}" if offer["owned"] else ""
        by_star.setdefault(offer["star_rating"], []).append(
            f"{mark} **{offer['name']}** — {offer['cost']:,} ✴️{owned}\n"
            f"　*{offer['ability_name']}*"
        )
    for star in sorted(by_star, reverse=True):
        embed.add_field(
            name=f"{STAR_EMOJI.get(star, '⭐' * star)}",
            value=fit_field(by_star[star]),
            inline=False,
        )
    embed.set_footer(text=_page_footer(
        page, per_page, total if total is not None else len(offers),
        "Cards cost the same as characters of the same rating."))
    return embed


def echo_convert_embed(player, batches: list[int]) -> discord.Embed:
    """The Sell Cores counter."""
    rate = resonance_config.CORES_PER_ECHO
    embed = discord.Embed(
        title="✴️ Echo Exchange — Sell Cores",
        description=(
            f"{_exchange_header(player)}\n"
            f"**{rate} {currency_emoji('cores')} → 1 ✴️**\n"
            "Cores buy card pulls and nothing else, so a player who is done with "
            "the card banner is holding a currency that does nothing. Trade the "
            "spares for Echoes and buy the Card — or the character — you actually "
            "want."
        ),
        color=discord.Color.purple(),
    )
    if batches:
        embed.add_field(
            name="Available trades",
            value="\n".join(
                f"{amount:,} {currency_emoji('cores')} → "
                f"**{resonance_config.echoes_for_cores(amount):,} ✴️**"
                for amount in batches
            ),
            inline=False,
        )
    else:
        embed.add_field(
            name="Nothing to sell",
            value=f"You need at least {rate} cores to make a single Echo.",
            inline=False,
        )
    # THE RATE IS UNFAVOURABLE AND SAYS SO. A conversion that quietly
    # pays less than pulling would is the kind of thing a player works
    # out three weeks later and feels cheated by.
    embed.set_footer(
        text="One-way, and deliberately not generous: converting everything and "
             "buying the card you want costs about what pulling to the guarantee does."
    )
    return embed


def _page_footer(page: int, per_page: int, total: int, note: str) -> str:
    """`note`, with the page position appended only when there is more
    than one page -- so a shop that fits on one screen reads exactly as
    it did before paging existed."""
    pages = max(1, -(-total // per_page)) if total else 1
    if pages <= 1:
        return note
    return f"Page {min(page, pages - 1) + 1}/{pages} · {total} in stock · {note}"


def resonance_embed(character) -> discord.Embed:
    """One character's Resonance track: what each of the five levels does
    and which are unlocked. Every level is listed, locked ones included --
    the point of the screen is to be a reason to keep pulling, which it
    can't be if it only shows what you already have."""
    resonance = resonance_config.resonance_for(character.dupe_count)
    embed = discord.Embed(
        title=f"✴️ {character.display_name} — Resonance {resonance}/{resonance_config.MAX_RESONANCE}",
        description=(
            f"Copies pulled: **{character.dupe_count}**\n"
            + ("Fully resonated — every further copy pays bonus Echoes instead."
               if resonance >= resonance_config.MAX_RESONANCE
               else "One more copy unlocks the next level.")
        ),
        color=discord.Color.purple(),
    )
    for entry in resonance_config.RESONANCE_LEVELS:
        unlocked = entry["level"] <= resonance
        embed.add_field(
            name=f"{'✅' if unlocked else '🔒'} R{entry['level']} — {entry['name']}",
            value=entry["description"],
            inline=False,
        )
    return embed


def _pity_status_lines(player) -> str:
    """How far each pity counter has to go, phrased as pulls REMAINING
    rather than pulls accumulated -- "8 pulls to a guaranteed 5★" is the
    question a player actually has, and making them subtract from a
    threshold to get it is needless friction."""
    from bot.game.economy.character_gacha_config import (
        FIVE_STAR_HARD_PITY,
        FIVE_STAR_SOFT_PITY_START,
        FOUR_STAR_PITY,
        five_star_chance_percent,
    )

    five_left = max(0, FIVE_STAR_HARD_PITY - player.pity_since_five_star)
    four_left = max(0, FOUR_STAR_PITY - player.pity_since_four_star)
    current_rate = five_star_chance_percent(player.pity_since_five_star)

    lines = [
        f"**{star_label(5)}** guaranteed in **{five_left}** pull{'s' if five_left != 1 else ''} "
        f"({player.pity_since_five_star}/{FIVE_STAR_HARD_PITY})",
        f"**{star_label(4)}** guaranteed in **{four_left}** pull{'s' if four_left != 1 else ''} "
        f"({player.pity_since_four_star}/{FOUR_STAR_PITY})",
    ]
    if player.pity_since_five_star + 1 > FIVE_STAR_SOFT_PITY_START:
        lines.append(f"🔥 Soft pity active -- next pull is **{current_rate:.0f}%** for a 5★.")
    else:
        soft_left = FIVE_STAR_SOFT_PITY_START - player.pity_since_five_star
        lines.append(f"Soft pity (rising odds) starts in {soft_left} pull{'s' if soft_left != 1 else ''}.")
    return "\n".join(lines)


