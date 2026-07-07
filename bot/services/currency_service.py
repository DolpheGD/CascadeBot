"""
All currency mutation goes through here so nothing ever sets `player.gold`
directly and risks skipping a commit or going negative.
"""

from __future__ import annotations

VALID_CURRENCIES = {"gold", "shards"}


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
