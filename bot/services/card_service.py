"""
Character Cards: seeding, pulling, equipping and levelling.

The card catalog lives in bot/game/economy/card_config.py; this module is
the only thing that writes CardTemplate/PlayerCard rows.
"""

from __future__ import annotations

import json
import random

from bot.database.models.card_model import CardTemplate, PlayerCard
from bot.database.models.character_model import PlayerCharacter
from bot.game.economy import card_config as cc
from bot.game.loot import abilities as ability_pools
from bot.services import pull_service
from bot.services.currency_service import format_currency, spend_currency

_POOL_BY_NAME = {
    "weapon": ability_pools.WEAPON_SKILLS,
    "artifact": ability_pools.ARTIFACT_SKILLS,
    "armor": ability_pools.ARMOR_PASSIVES,
    "ultimate": ability_pools.ULTIMATE_ABILITIES,
}


# ----------------------------------------------------------------------
# Seeding
# ----------------------------------------------------------------------

def ensure_card_templates_seeded(db) -> None:
    """Upsert every card in the catalog, same startup pattern as the
    character/item/harvester seeders."""
    for data in cc.CARD_TEMPLATES:
        row = db.query(CardTemplate).filter_by(card_id=data["id"]).first()
        values = dict(
            card_id=data["id"], name=data["name"], star_rating=data["star_rating"],
            lore=data["lore"], stats_json=json.dumps(data["stats"]),
            ability_id=data["ability_id"], ability_pool=data["ability_pool"],
        )
        if row is None:
            db.add(CardTemplate(**values))
        else:
            for key, value in values.items():
                setattr(row, key, value)
    db.commit()


# ----------------------------------------------------------------------
# Reading a card
# ----------------------------------------------------------------------

def card_stats(card: PlayerCard) -> dict[str, float]:
    """The card's three stats AT ITS CURRENT LEVEL, star multiplier and
    level curve both applied. This is the single place those two combine
    -- a second one would drift."""
    base = json.loads(card.template.stats_json or "{}")
    star = cc.CARD_STAR_MULTIPLIER.get(card.template.star_rating, 1.0)
    level = cc.card_level_multiplier(card.level)
    return {stat: round(value * star * level, 1) for stat, value in base.items()}


def template_ability(template: CardTemplate) -> dict | None:
    """The ability a card TEMPLATE carries.

    Split out from card_ability because the Echo Exchange sells cards
    nobody owns yet, so it has a template and no PlayerCard. Written as
    the one definition with card_ability delegating to it rather than as
    a second `next(...)` over the same pools -- the card ability lookup
    has already been duplicated once in this codebase, and the failure
    mode is a card that equips fine and silently has no ability.
    """
    pool = _POOL_BY_NAME.get(template.ability_pool)
    if not pool:
        return None
    return next((a for a in pool if a["id"] == template.ability_id), None)


def card_ability(card: PlayerCard) -> dict | None:
    return template_ability(card.template)


def list_cards(db, player_id: int) -> list[PlayerCard]:
    return (
        db.query(PlayerCard)
        .filter_by(player_id=player_id)
        .order_by(PlayerCard.character_id.isnot(None).desc(), PlayerCard.id)
        .all()
    )


def get_equipped_card(db, character_id: int) -> PlayerCard | None:
    return db.query(PlayerCard).filter_by(character_id=character_id).first()


def cards_by_character(db, player_id: int) -> dict[int, PlayerCard]:
    """{character_id: card} for everything this player has equipped.

    One query for the whole squad. Every combatant-building call site
    needs this map, and doing it per character would put four extra
    round-trips on the path that already has the tightest deadline in
    the bot (see tools/check_interactions)."""
    return {
        card.character_id: card
        for card in db.query(PlayerCard).filter_by(player_id=player_id).all()
        if card.character_id is not None
    }


# ----------------------------------------------------------------------
# Equipping
# ----------------------------------------------------------------------

def equip_card(db, player, card: PlayerCard, character: PlayerCharacter) -> tuple[bool, str]:
    """One card per character, one character per card. Both directions
    are enforced here rather than in the schema -- see PlayerCard's
    comment -- and both need a readable refusal, not a constraint error.
    """
    if card.player_id != player.id:
        return False, "That isn't your card."
    if character.player_id != player.id:
        return False, "That isn't your character."

    if card.character_id == character.id:
        return False, f"**{card.display_name}** is already on {character.display_name}."

    # Whatever they were wearing comes off, and says so -- a silent swap
    # is how a player loses track of where their best card went.
    displaced = get_equipped_card(db, character.id)
    if displaced is not None and displaced.id != card.id:
        displaced.character_id = None

    card.character_id = character.id
    db.commit()

    note = f" (replacing **{displaced.display_name}**)" if displaced is not None else ""
    return True, f"Equipped **{card.display_name}** to {character.display_name}{note}."


def unequip_card(db, card: PlayerCard) -> tuple[bool, str]:
    if card.character_id is None:
        return False, f"**{card.display_name}** isn't equipped."
    card.character_id = None
    db.commit()
    return True, f"Unequipped **{card.display_name}**."


# ----------------------------------------------------------------------
# Levelling
# ----------------------------------------------------------------------

def level_up_cost(card: PlayerCard, levels: int = 1) -> dict[str, int]:
    """Summed per-level, so a multi-level upgrade charges exactly what
    doing them one at a time would -- including every Evolution Fragment
    breakthrough the run crosses, not just the first."""
    star = card.template.star_rating
    total: dict[str, int] = {}
    for step in range(levels):
        for currency, amount in cc.card_level_cost(card.level + step, star).items():
            total[currency] = total.get(currency, 0) + amount
    return total


def level_up_card(db, player, card: PlayerCard, levels: int = 1) -> tuple[bool, str]:
    if card.player_id != player.id:
        return False, "That isn't your card."
    if card.level >= cc.CARD_MAX_LEVEL:
        return False, f"**{card.display_name}** is already at level {cc.CARD_MAX_LEVEL}."

    levels = max(1, min(levels, cc.CARD_MAX_LEVEL - card.level))
    cost = level_up_cost(card, levels)

    for currency, amount in cost.items():
        if getattr(player, currency, 0) >= amount:
            continue
        if currency == "evolution_fragments":
            # Worth its own sentence. This is the one cost a player is
            # MEANT to be short of, and "Not enough <emoji> 264" about a
            # resource that has never appeared on this screen before
            # explains nothing about why levelling just stopped.
            from bot.game.economy.evolution_config import CARD_BREAKTHROUGH_EVERY
            return False, (
                f"**{card.display_name}** is at a breakthrough. Every "
                f"{CARD_BREAKTHROUGH_EVERY} levels a Card needs "
                f"{format_currency('evolution_fragments', amount)} to go further, "
                f"and you have {getattr(player, currency, 0)}. Cards cost more "
                f"than gear at the same level, and higher stars cost more again."
            )
        return False, f"Not enough {format_currency(currency, amount)}."
    for currency, amount in cost.items():
        spend_currency(db, player, currency, amount)

    card.level += levels
    db.commit()
    price = " / ".join(format_currency(c, a) for c, a in cost.items())
    return True, f"**{card.display_name}** is now level {card.level}. Spent {price}."


# ----------------------------------------------------------------------
# The banner
# ----------------------------------------------------------------------

def _roll_star(player, rng: random.Random) -> tuple[int, bool]:
    """(star rating, whether pity produced it) for one pull.

    Same shape as the character banner -- hard ceiling, soft ramp, then
    the 4-star floor -- via the shared pull_service.soft_pity_rate. This
    banner keeps its OWN counters (Player.card_pity_*); only the maths
    is shared.
    """
    if player.card_pity_since_five_star + 1 >= cc.CARD_FIVE_STAR_HARD_PITY:
        return 5, True

    five_chance = pull_service.soft_pity_rate(
        cc.CARD_STAR_WEIGHTS[5], player.card_pity_since_five_star,
        cc.CARD_FIVE_STAR_SOFT_PITY_START, cc.CARD_FIVE_STAR_SOFT_PITY_STEP,
    )
    if rng.random() * 100 < five_chance:
        # Soft pity counts as pity once the ramp is doing the work --
        # a 5-star at pull 44 was not luck and should not claim to be.
        ramped = player.card_pity_since_five_star + 1 > cc.CARD_FIVE_STAR_SOFT_PITY_START
        return 5, ramped

    if player.card_pity_since_four_star + 1 >= cc.CARD_FOUR_STAR_PITY:
        return 4, True
    if rng.random() * 100 < cc.CARD_STAR_WEIGHTS[4]:
        return 4, False
    return 3, False


def pull_cards(db, player, count: int = 1,
               rng: random.Random | None = None) -> tuple[bool, str, list[PlayerCard]]:
    """Spend cores, roll `count` cards, grant them. Returns
    (ok, message, new cards)."""
    rng = rng or random.Random()
    cost = cc.CARD_PULL_COST * count
    if player.cores < cost:
        return False, (
            f"You need {format_currency('cores', cost)} for {count} "
            f"pull{'s' if count > 1 else ''} — you have "
            f"{format_currency('cores', player.cores)}."
        ), []

    spend_currency(db, player, "cores", cost)

    pulled: list[PlayerCard] = []
    for _ in range(count):
        star, was_pity = _roll_star(player, rng)
        # Pity is a COUNT OF PULLS SINCE, so it resets on the rarity it
        # guards and advances on everything else -- including a rarity
        # above it, which is why a 5-star also clears the 4-star counter.
        if star >= 5:
            player.card_pity_since_five_star = 0
            player.card_pity_since_four_star = 0
        elif star == 4:
            player.card_pity_since_five_star += 1
            player.card_pity_since_four_star = 0
        else:
            player.card_pity_since_five_star += 1
            player.card_pity_since_four_star += 1

        choices = cc.cards_of_star(star) or cc.CARD_TEMPLATES

        # Targeting, via the SAME rule the character banner uses -- see
        # pull_service.resolve_five_star. The two banners keep separate
        # targets and separate guarantee flags, but sharing the rule is
        # what stops "my guarantee works on characters but not cards"
        # from ever being true, which is a bug nobody could distinguish
        # from bad luck and therefore nobody would report.
        if star >= 5:
            chosen, _hit, player.target_card_guaranteed = (
                pull_service.resolve_five_star(
                    rng, choices, player.target_card,
                    lambda c: c["id"], bool(player.target_card_guaranteed))
            )
        else:
            chosen = rng.choice(choices)
        template = db.query(CardTemplate).filter_by(card_id=chosen["id"]).first()
        if template is None:
            continue
        card = PlayerCard(player_id=player.id, template_id=template.id, level=1)
        db.add(card)
        pulled.append(card)
        pull_service.record_pull(db, player, "card", template.name, star, was_pity)

    db.commit()
    return True, f"Spent {format_currency('cores', cost)}.", pulled


def grant_card(db, player, card_id: str) -> PlayerCard | None:
    """Hand over a specific card, no roll and no cost -- used by story
    rewards. Returns None if the id isn't in the catalog."""
    template = db.query(CardTemplate).filter_by(card_id=card_id).first()
    if template is None:
        return None
    card = PlayerCard(player_id=player.id, template_id=template.id, level=1)
    db.add(card)
    db.commit()
    return card
