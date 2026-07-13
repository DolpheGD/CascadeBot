"""
All currency mutation goes through here so nothing ever sets `player.gold`
directly and risks skipping a commit or going negative.
"""

from __future__ import annotations

from bot.database.models.enums import MATERIAL_EMOJI as _MATERIAL_EMOJI

VALID_CURRENCIES = {
    "gold", "shards", "reroll_tokens",
    "wood", "stone", "metal", "crystal",
    "xendium", "permafrost_ore", "void", "entropy",
}

# Single source of truth for "what emoji represents this currency" -- reused
# everywhere a currency amount is shown to the player (shop, mailbox, HQ/
# shrine costs, harvester production, daily rewards, treasure finds, gear
# upgrade costs...) so the same currency always renders the same way instead
# of drifting into ad hoc "50 gold" text in some places and an emoji in
# others. Materials reuse enums.MATERIAL_EMOJI (the same emoji already used
# for MaterialType) so there's one definition per material, not two.
CURRENCY_EMOJI: dict[str, str] = {
    "gold": "🪙",
    "shards": "💎",
    "reroll_tokens": "🎲",
    **{material.value: emoji for material, emoji in _MATERIAL_EMOJI.items()},
}


def currency_emoji(currency: str) -> str:
    return CURRENCY_EMOJI.get(currency, "")


def format_currency(currency: str, amount: int) -> str:
    """Renders an amount with its emoji instead of spelling the currency
    name out -- e.g. `50 🪙` rather than `50 gold`. Falls back to the raw
    currency name if it somehow has no emoji mapped."""
    emoji = currency_emoji(currency)
    return f"{amount} {emoji}" if emoji else f"{amount} {currency}"


def _check_currency(currency: str) -> None:
    if currency not in VALID_CURRENCIES:
        raise ValueError(f"Unknown currency: {currency!r}")


def get_balance(player, currency: str) -> int:
    _check_currency(currency)
    return getattr(player, currency)


def add_currency(db, player, currency: str, amount: int) -> int:
    """returns the new balance"""
    _check_currency(currency)
    if amount < 0:
        raise ValueError("amount must be non-negative; use spend_currency to deduct")

    setattr(player, currency, getattr(player, currency) + amount)
    db.commit()
    db.refresh(player)
    return getattr(player, currency)


def spend_currency(db, player, currency: str, amount: int) -> bool:
    """
    attempts to deduct `amount` of `currency` from player.
    returns True and commits if the player could afford it, False (no changes) otherwise.
    """
    _check_currency(currency)
    if amount < 0:
        raise ValueError("amount must be non-negative")

    balance = getattr(player, currency)
    if balance < amount:
        return False

    setattr(player, currency, balance - amount)
    db.commit()
    db.refresh(player)
    return True
