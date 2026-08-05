"""
The Echo Exchange: buy a specific character with duplicate currency.

This is the deterministic half of the gacha. `/pull` gives you a random
character; this gives you the one you actually want, at a price paid for
by every duplicate you've ever pulled. Nothing here rolls dice.

Deliberately routed through character_service.grant_character rather than
creating a PlayerCharacter directly, so a purchased copy behaves exactly
like a pulled one: buying someone you already own raises their Resonance
and pays the duplicate Echo rate back, same as a lucky pull would. That
matters more than it sounds -- it's what makes the exchange a way to
finish a Resonance track for a favourite character, not just a way to
fill gaps in the roster.
"""

from __future__ import annotations

from bot.database.models.character_model import CharacterTemplate, PlayerCharacter
from bot.game.economy import resonance_config
from bot.services import character_service
from bot.services.currency_service import spend_currency


class ExchangeError(Exception):
    """A reason a purchase can't proceed, phrased for the player."""


def purchasable_templates(db) -> list[CharacterTemplate]:
    """Every character the exchange sells: the same pool `/pull` draws
    from, minus nothing. The free avatar is excluded because every player
    already has exactly one and a second would be meaningless."""
    return (
        db.query(CharacterTemplate)
        .filter_by(is_player_avatar=False)
        .order_by(CharacterTemplate.star_rating.desc(), CharacterTemplate.name)
        .all()
    )


def offers(db, player) -> list[dict]:
    """Display rows for the storefront -- cost, affordability, and the
    player's current Resonance on anyone they already own."""
    owned = {
        pc.template_id: pc
        for pc in db.query(PlayerCharacter).filter_by(player_id=player.id).all()
    }
    rows = []
    for template in purchasable_templates(db):
        pc = owned.get(template.id)
        cost = resonance_config.character_cost(template.star_rating)
        rows.append({
            "template": template,
            "template_id": template.id,
            "name": template.name,
            "star_rating": template.star_rating,
            "cost": cost,
            "affordable": player.echoes >= cost,
            "owned": pc is not None,
            "resonance": resonance_config.resonance_for(pc.dupe_count) if pc else 0,
        })
    return rows


def purchase(db, player, template_id: int) -> dict:
    """Buys one copy of `template_id`. Returns the same shape the pull
    screen already understands, plus what it cost.

    Echoes are spent BEFORE the grant and the grant can pay some back (a
    duplicate purchase earns the duplicate Echo rate) -- that ordering is
    deliberate, so a player can never fund a purchase with the refund
    from the purchase itself."""
    template = db.get(CharacterTemplate, template_id)
    if template is None or template.is_player_avatar:
        raise ExchangeError("That character isn't available in the exchange.")

    cost = resonance_config.character_cost(template.star_rating)
    if player.echoes < cost:
        short = cost - player.echoes
        raise ExchangeError(
            f"**{template.name}** costs {cost:,} ✴️ and you have {player.echoes:,} "
            f"-- {short:,} short. Every duplicate you pull pays Echoes."
        )

    spend_currency(db, player, "echoes", cost)
    pc, is_new, dupe = character_service.grant_character(db, player, template)

    return {
        "template": template,
        "player_character": pc,
        "is_new": is_new,
        "dupe_reward": dupe,
        "cost": cost,
        "resonance": resonance_config.resonance_for(pc.dupe_count),
    }
