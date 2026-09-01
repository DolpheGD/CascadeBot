"""
The Echo Exchange: buy a specific thing with duplicate currency.

This is the deterministic half of BOTH gachas. `/pull` gives you a random
character and `/cardpull` gives you a random Card; this gives you the one
you actually want, at a price paid for by every duplicate you've ever
pulled. Nothing here rolls dice.

----------------------------------------------------------------------
THREE COUNTERS, ONE SHOP
----------------------------------------------------------------------
  * CHARACTERS -- the original exchange.
  * CARDS      -- the same idea for the Card banner. A card is the one
                  piece of power a character keeps forever, and until
                  now the ONLY way to get a specific one was to roll for
                  it against a 26-card catalog. That is the exact
                  dead-end Echoes were invented to remove, and it was
                  left in place on the newer of the two banners.
  * CONVERSION -- cores into Echoes, so a player who is done with the
                  card banner isn't holding a currency that buys
                  nothing. See resonance_config.CORES_PER_ECHO for why
                  the rate is what it is, and why it only goes one way.

Character purchases are deliberately routed through
character_service.grant_character rather than creating a PlayerCharacter
directly, so a purchased copy behaves exactly like a pulled one: buying
someone you already own raises their Resonance and pays the duplicate
Echo rate back, same as a lucky pull would. That matters more than it
sounds -- it's what makes the exchange a way to finish a Resonance track
for a favourite character, not just a way to fill gaps in the roster.

Card purchases go through card_service.grant_card for the same reason,
and buying a card you ALREADY own is allowed on purpose: one card sits
on one character, so a second copy is how you run the same ability on
two of them. It is the only duplicate in the shop that isn't a mistake,
so the storefront says so rather than blocking it.
"""

from __future__ import annotations

from bot.database.models.card_model import CardTemplate, PlayerCard
from bot.database.models.character_model import CharacterTemplate, PlayerCharacter
from bot.game.economy import card_config, resonance_config
from bot.services import card_service, character_service
from bot.services.currency_service import add_currency, spend_currency

# The shop's sections, in the order the tabs appear. Each is (key,
# label, emoji) and everything else -- which offers to build, which
# select to render, which page count applies -- is looked up from the
# key, so adding a fourth counter is a tuple plus an offers function.
COUNTERS: list[tuple[str, str, str]] = [
    ("characters", "Characters", "👤"),
    ("cards", "Cards", "🃏"),
    ("convert", "Sell Cores", "💱"),
]


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


# ----------------------------------------------------------------------
# The Card counter
# ----------------------------------------------------------------------

def card_offers(db, player) -> list[dict]:
    """Display rows for every Character Card in the catalog.

    Ordered highest-star first to match the character counter, and the
    ABILITY is carried through rather than just the name: a card is
    bought for what it does, and "The Comma After Good Luck" tells a
    player nothing about whether it is the one they want.
    """
    owned_counts: dict[int, int] = {}
    for card in db.query(PlayerCard).filter_by(player_id=player.id).all():
        owned_counts[card.template_id] = owned_counts.get(card.template_id, 0) + 1

    templates = (
        db.query(CardTemplate)
        .order_by(CardTemplate.star_rating.desc(), CardTemplate.name)
        .all()
    )
    rows = []
    for template in templates:
        cost = resonance_config.card_cost(template.star_rating)
        ability = card_service.template_ability(template)
        rows.append({
            "template": template,
            "card_template_id": template.id,
            "card_id": template.card_id,
            "name": template.name,
            "star_rating": template.star_rating,
            "cost": cost,
            "affordable": player.echoes >= cost,
            "owned": owned_counts.get(template.id, 0),
            "ability_name": (ability or {}).get("name", "—"),
        })
    return rows


def purchase_card(db, player, card_id: str) -> dict:
    """Buys one copy of the card whose catalog id is `card_id`.

    Takes the STRING catalog id rather than the row id, so the select
    that calls this carries a value that means the same thing in every
    database -- a card template's row id depends on seed order and would
    silently point at a different card on a rebuilt database.
    """
    template = db.query(CardTemplate).filter_by(card_id=card_id).first()
    if template is None:
        raise ExchangeError("That card isn't available in the exchange.")

    cost = resonance_config.card_cost(template.star_rating)
    if player.echoes < cost:
        short = cost - player.echoes
        raise ExchangeError(
            f"**{template.name}** costs {cost:,} ✴️ and you have {player.echoes:,} "
            f"-- {short:,} short. Duplicate pulls pay Echoes, and so does "
            f"selling spare cores at the Sell Cores counter."
        )

    spend_currency(db, player, "echoes", cost)
    card = card_service.grant_card(db, player, template.card_id)
    if card is None:                                    # pragma: no cover
        raise ExchangeError("That card isn't available in the exchange.")

    return {"template": template, "card": card, "cost": cost}


def sell_card(db, player, card: PlayerCard | int) -> dict:
    """Sell a card back to Echoes at the same value used by the shop.

    This is the player-facing mirror of card_service.sell_card: both use
    the same catalog price table, so buying and selling a 5★ card always
    loop through the same number.
    """
    if isinstance(card, int):
        card = db.get(PlayerCard, card)
    if card is None:
        raise ExchangeError("That card isn't available.")
    if card.player_id != player.id:
        raise ExchangeError("That isn't your card.")

    ok, message = card_service.sell_card(db, player, card)
    if not ok:
        raise ExchangeError(message)

    return {
        "card": card,
        "echoes": resonance_config.card_cost(card.template.star_rating),
        "message": message,
    }


# ----------------------------------------------------------------------
# The conversion counter
# ----------------------------------------------------------------------

def sell_cores(db, player, cores: int) -> dict:
    """Trade `cores` for Echoes at resonance_config's rate.

    Charges only what the conversion actually PAYS FOR -- a player
    selling 130 cores at 4:1 gets 32 Echoes and keeps the leftover 2,
    rather than having the remainder swallowed. Silently eating change is
    the kind of thing nobody reports and everybody notices.
    """
    cores = int(cores)
    if cores <= 0:
        raise ExchangeError("Nothing to sell.")
    if player.cores < cores:
        raise ExchangeError(
            f"You only have {player.cores:,} cores."
        )

    echoes = resonance_config.echoes_for_cores(cores)
    if echoes <= 0:
        raise ExchangeError(
            f"{resonance_config.CORES_PER_ECHO} cores make 1 ✴️ Echo, so "
            f"{cores:,} isn't enough to trade yet."
        )

    spent = resonance_config.cores_for_echoes(echoes)
    spend_currency(db, player, "cores", spent)
    add_currency(db, player, "echoes", echoes)
    return {"cores": spent, "echoes": echoes, "change": cores - spent}


def sellable_batches(player) -> list[int]:
    """The core amounts the convert counter offers as buttons.

    Fixed batches plus "everything", rather than a free-text amount: a
    modal costs an interaction round-trip and the useful amounts are all
    multiples of a pull anyway. Batches the player cannot afford are
    filtered out here so the view never renders a button that refuses.
    """
    pull = card_config.CARD_PULL_COST
    batches = [b for b in (pull, pull * 5, pull * 10) if player.cores >= b]
    everything = resonance_config.cores_for_echoes(
        resonance_config.echoes_for_cores(player.cores))
    if everything > 0 and everything not in batches:
        batches.append(everything)
    return batches
