"""
Evolving a character up the star ladder.

Rules, requirements and pricing all live in
bot/game/economy/character_evolution_config.py; this module is only the
mechanism. Read the config first -- it explains why the numbers are what
they are, and in particular why a fully evolved 3-star is deliberately
still well short of a native 5-star.
"""

from __future__ import annotations

from bot.game.economy import character_evolution_config as cfg
from bot.services.currency_service import spend_currency


class EvolutionError(Exception):
    """Any reason a character can't evolve, phrased for the player."""


def native_star(character) -> int:
    return int(character.template.star_rating or 3)


def next_star(character) -> int | None:
    """The star this character would reach next, or None if it can't."""
    target = character.effective_star + 1
    if target > cfg.MAX_STAR:
        return None
    return target


def requirements(character) -> dict | None:
    """What the NEXT evolution needs, with progress filled in.

    Returns None when there is no next evolution. Otherwise a dict the UI
    can render without doing any of this arithmetic itself -- the point
    being that "can they afford it" is answered in exactly one place, so
    the button and the service can never disagree about it.
    """
    target = next_star(character)
    if target is None:
        return None
    requirement = cfg.requirement_for(target)
    if requirement is None:
        return None

    player = character.player
    cost = requirement["cost"]
    have = {currency: int(getattr(player, currency, 0) or 0) for currency in cost}
    return {
        "target_star": target,
        "level_required": requirement["level"],
        "level_met": character.level >= requirement["level"],
        "cost": dict(cost),
        "have": have,
        "affordable": all(have[c] >= amount for c, amount in cost.items()),
    }


def can_evolve(character) -> tuple[bool, str]:
    """(allowed, why not). The single source of truth for the answer."""
    if character.template.is_player_avatar:
        # THE AVATAR IS EXCLUDED, and not by oversight. It is already a
        # 5-star, it is granted free to every player, and it is the one
        # character nobody can fail to obtain -- so there is nothing for
        # an evolution to fix and no scarcity for it to respect.
        return False, "Your avatar is already 5★ and can't be evolved."

    target = next_star(character)
    if target is None:
        return False, f"{character.display_name} is already {cfg.MAX_STAR}★."

    requirement = requirements(character)
    if requirement is None:
        return False, f"{character.display_name} can't evolve any further."

    if not requirement["level_met"]:
        return False, (
            f"{character.display_name} must reach level "
            f"{requirement['level_required']} to evolve "
            f"(currently {character.level}).")

    if not requirement["affordable"]:
        missing = [
            f"{amount - requirement['have'][currency]:,} more {currency.replace('_', ' ')}"
            for currency, amount in requirement["cost"].items()
            if requirement["have"][currency] < amount
        ]
        return False, "You need " + ", ".join(missing) + "."

    return True, ""


def evolve(db, player, character) -> dict:
    """Spend the cost and raise the star. Returns a summary for the UI.

    THE GUARD IS RE-CHECKED HERE, not trusted from the caller. The button
    that leads here was rendered from a state that may be minutes old --
    every Discord message stays live and clickable forever -- so the
    view's opinion that this was affordable is a hint, not a fact. This
    is the same shape as the stale-claim and stale-hunt paths elsewhere:
    the way IN is guarded, and the way OUT has to be guarded too.
    """
    allowed, reason = can_evolve(character)
    if not allowed:
        raise EvolutionError(reason)

    requirement = requirements(character)
    before = character.effective_star

    # EVERY BALANCE IS RE-CHECKED BEFORE ANYTHING IS SPENT.
    #
    # spend_currency RETURNS FALSE when the player cannot afford it -- it
    # does not raise. Spending in a loop and ignoring those return values
    # would take the first two currencies, fail silently on the third,
    # and evolve the character anyway: the player pays gold and echoes
    # and gets the upgrade without the fragments. Checking all three
    # first makes the whole thing all-or-nothing.
    player_balances = {
        currency: int(getattr(player, currency, 0) or 0)
        for currency in requirement["cost"]
    }
    short = [c for c, amount in requirement["cost"].items()
             if player_balances[c] < amount]
    if short:
        raise EvolutionError(
            "You can't afford that any more — check your "
            + ", ".join(c.replace("_", " ") for c in short) + ".")

    for currency, amount in requirement["cost"].items():
        if not spend_currency(db, player, currency, amount):
            # Unreachable given the check above, and still handled: the
            # alternative is a partial spend that leaves the player worse
            # off than before with nothing to show for it.
            raise EvolutionError(
                f"Couldn't spend {amount:,} {currency.replace('_', ' ')}.")

    character.evolution_stage = int(character.evolution_stage or 0) + 1
    db.commit()

    return {
        "character": character,
        "from_star": before,
        "to_star": character.effective_star,
        "spent": dict(requirement["cost"]),
        "stage": int(character.evolution_stage),
        "percent": cfg.stage_percent(int(character.evolution_stage)),
    }


def evolvable_characters(db, player) -> list:
    """Every character that COULD evolve right now, best candidates first.

    Ordered by how close they are to affording it rather than by star or
    level, because the screen's job is to answer "what can I do now".
    """
    from bot.services import character_service

    ready, waiting = [], []
    for character in character_service.list_owned_characters(db, player):
        if character.template.is_player_avatar:
            continue
        if next_star(character) is None:
            continue
        allowed, _ = can_evolve(character)
        (ready if allowed else waiting).append(character)

    ready.sort(key=lambda c: (-c.effective_star, -c.level))
    waiting.sort(key=lambda c: (-c.level, -c.effective_star))
    return ready + waiting
