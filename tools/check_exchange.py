"""
Run the Echo Exchange for real, against a real database.

    python -m tools.check_exchange

THE BUGS THIS EXISTS FOR
------------------------
The exchange sells three different things through one screen, and every
one of them is a shape this codebase has already been bitten by:

  1. A SELECT THAT SILENTLY DROPS ITS TAIL. The character counter did
     exactly this: `options[:25]` against a roster that grew past 25, so
     the five most expensive characters were unbuyable and the storefront
     embed listed them anyway. It was reported as "the menu is too long
     so you can't buy some of them". The catalog now has 29 characters
     AND 26 cards, so there are two lists to lose the end of.

  2. AN OFFER NOBODY CAN BUY. Every row in a select carries a `value`,
     and the purchase function has to be able to turn that value back
     into the thing on sale. If they disagree -- a row id where a
     catalog id is expected, say -- the shop renders perfectly and every
     purchase fails. Nothing raises until a player clicks.

  3. A PRICE WITH NO STOCK. `resonance_config` prices by star rating. A
     rating with no price silently falls back to the 3-star cost, which
     would sell 5-star cards for 250 echoes and never once look wrong.

So this doesn't inspect the config -- it BUYS things. Every character,
every card, and a core conversion, through the same service functions
the buttons call.

WHAT IT ASSERTS
  * every offer's select value round-trips back through the purchase
    path -- the shop can sell everything it displays
  * every rating on sale has its own explicit price
  * paging covers the whole catalog with nothing dropped and nothing
    shown twice
  * every card bought here reaches a real combatant with its ability
    intact, through whichever of the factory's three routing branches
    its pool uses
  * selling cores pays the advertised rate, returns the change, and
    cannot mint echoes out of a balance too small to trade
  * the conversion rate still matches the card banner's hard pity, which
    is the number the whole price table is calibrated against

VERIFIED BY BREAKING IT. Every assertion above was confirmed to go red
with the bug it names deliberately reintroduced -- the options[:25]
slice, the row-id-for-catalog-id swap, a rounding-up conversion, a
duplicated price table, an unresolvable ability_id, and the factory
dropping armor-pool routing. A check nobody has watched fail is a check
nobody should trust; three in this directory previously passed with the
exact bug they were written for still in place.
"""

from __future__ import annotations

import sys
import tempfile

# Discord's ceiling on options in one select. Every window the exchange
# renders has to fit under this.
SELECT_OPTION_LIMIT = 25


def main() -> int:
    import os
    os.environ.setdefault("DATABASE_URL", "sqlite:///" + tempfile.mktemp(suffix=".db"))

    from sqlalchemy.orm import sessionmaker

    from bot.database.db import engine
    from bot.database.db_init import init_db
    from bot.database.models.player_model import Player
    from bot.game.economy import card_config as cc
    from bot.game.economy import resonance_config as rc
    from bot.services import (
        card_service, character_template_service, echo_exchange_service,
    )
    from bot.utils import paging

    init_db()
    db = sessionmaker(bind=engine)()
    character_template_service.ensure_character_templates_seeded(db)
    card_service.ensure_card_templates_seeded(db)

    # Rich enough to afford everything: this checker is about whether a
    # purchase WORKS, and "you can't afford it" would mask every real
    # failure behind a refusal that looks like correct behaviour.
    player = Player(id=1, username="exchange-check",
                    gold=10**9, shards=10**9, echoes=10**9, cores=10**9)
    db.add(player)
    db.commit()

    failures: list[str] = []
    bought_characters = 0
    bought_cards = 0

    # ---- 1. every offer THE SCREEN SHOWS can actually be bought -------
    #
    # THROUGH THE RENDERED VIEW, and bought with the VALUE THE OPTION
    # ITSELF CARRIES. Both halves of that are load-bearing, and I got
    # both wrong on the first draft.
    #
    # The first draft walked the service's offer list and bought each row
    # with the handle the service had just handed back. That passes with
    # the select wired to the wrong field entirely -- I proved it: with
    # the card select carrying the template's ROW id instead of the
    # catalog id, the shop rendered perfectly, every purchase in the
    # checker succeeded, and clicking the first card in the real menu
    # raised "That card isn't available in the exchange."
    #
    # The value on the option is the ONLY thing a click gives the
    # callback. So that is the only thing worth testing, and the option
    # has to come off a view that was actually built.
    import discord

    from bot.cogs.economy import _render_exchange

    counters = (
        ("characters", echo_exchange_service.offers(db, player),
         lambda value: echo_exchange_service.purchase(db, player, int(value))),
        ("cards", echo_exchange_service.card_offers(db, player),
         lambda value: echo_exchange_service.purchase_card(db, player, value)),
    )

    for counter, rows, buy in counters:
        total = len(rows)
        for offer in rows:
            if offer["star_rating"] not in rc.ECHO_COST_BY_STAR:
                failures.append(
                    f"{counter}: '{offer['name']}' is {offer['star_rating']}-star, "
                    f"which has no price -- it would silently sell at the 3-star cost"
                )
            if counter == "cards" and offer["ability_name"] in ("", "—", None):
                failures.append(
                    f"card '{offer['name']}' shows no ability in the shop -- its "
                    f"ability_id does not resolve, so the card sells with nothing on it"
                )

        seen: set[str] = set()
        rendered = 0
        for page in range(paging.page_count(total)):
            _, view = _render_exchange(db, player, counter, page)
            selects = [item for item in view.children
                       if isinstance(item, discord.ui.Select)]
            if len(selects) != 1:
                failures.append(
                    f"{counter}: page {page} rendered {len(selects)} selects, not 1"
                )
                continue
            options = selects[0].options
            if len(options) > SELECT_OPTION_LIMIT:
                failures.append(
                    f"{counter}: page {page} rendered {len(options)} options, over "
                    f"Discord's ceiling of {SELECT_OPTION_LIMIT} -- discord.py "
                    f"raises on send, so this screen would not open at all"
                )
            rendered += len(options)
            seen.update(option.value for option in options)

            for option in options:
                try:
                    buy(option.value)
                    if counter == "cards":
                        bought_cards += 1
                    else:
                        bought_characters += 1
                except Exception as exc:               # noqa: BLE001
                    failures.append(
                        f"{counter}: '{option.label}' is on the shelf, but clicking "
                        f"it raises {type(exc).__name__}: {exc} -- the value the "
                        f"option carries is not one the purchase path understands"
                    )

        if len(seen) != total:
            failures.append(
                f"{counter}: the screen offers {len(seen)} of {total} -- part of "
                f"the catalog is unreachable by clicking, which is exactly the "
                f"bug the old options[:25] shipped"
            )
        if rendered != total:
            failures.append(
                f"{counter}: pages render {rendered} rows for {total} offers -- "
                f"something is shown on two pages or on none"
            )

    # The convert counter has no select, and must not render a button
    # the player cannot pay for.
    broke = Player(id=2, username="broke", cores=rc.CORES_PER_ECHO - 1)
    db.add(broke)
    db.commit()
    _, view = _render_exchange(db, broke, "convert", 0)
    if any(isinstance(item, discord.ui.Button) and getattr(item, "amount", 0)
           for item in view.children):
        failures.append(
            "the convert counter offers a trade to a player who cannot afford "
            "one -- the button would refuse when clicked"
        )

    # ---- 3. what you bought actually works ----------------------------
    #
    # Every card in the catalog, equipped to a real character, built into
    # a real combatant, and its ability found on the result.
    #
    # This is the shop's whole promise -- you paid 1,500 Echoes for a
    # specific ability instead of gambling for it -- and it rests on a
    # routing branch in the combat factory that sends the ability to a
    # different place depending on which pool it came from: weapon and
    # artifact abilities become buttons, armor ones become passives, and
    # ultimate-pool ones fall through to passives too.
    #
    # Nothing raises if that routing drops one. The card equips, shows
    # its three stats, and does nothing -- and I briefly believed it HAD
    # dropped all ten armor cards, because I checked the wrong attribute
    # on the combatant. A checker that reads the real field is cheaper
    # than making that mistake twice.
    from bot.game.combat.factory import build_party_combatants
    from bot.services import character_service

    avatar = character_template_service.get_avatar_template(db)
    holder, _, _ = character_service.grant_character(db, player, avatar)
    character_service.set_squad_slot(db, player, 0, holder)
    db.commit()

    # WHERE it lands is asserted, not just THAT it lands somewhere.
    #
    # The looser version of this check ("is it in actives or passives?")
    # passed while two cards were completely dead. Both are ultimate-pool
    # cards, and the factory's fall-through put them in
    # `passive_abilities` -- a list only ever read by find_passive(kind),
    # which no ultimate's kind matches. They were present, so the check
    # was satisfied, and they did nothing in every fight.
    #
    # A slot is only correct relative to the ability's POOL, so that is
    # what gets asserted. An ultimate must be on the ultimate button; a
    # weapon or artifact skill must be a usable button; an armor passive
    # must be in the passive list.
    SLOT_FOR_POOL = {
        "weapon": "active", "artifact": "active",
        "armor": "passive", "ultimate": "ultimate",
    }
    reached = 0
    for template in cc.CARD_TEMPLATES:
        for owned in card_service.list_cards(db, player.id):
            card_service.unequip_card(db, owned)
        card = card_service.grant_card(db, player, template["id"])
        card_service.equip_card(db, player, card, holder)

        combatant = build_party_combatants(
            [holder], {},
            cards_by_character=card_service.cards_by_character(db, player.id),
        )[0]
        ultimate = combatant.ultimate_ability or {}
        landed = {
            "active": any(a.get("source") == "card" for a in combatant.active_abilities),
            "passive": any(a.get("source") == "card" for a in combatant.passive_abilities),
            "ultimate": ultimate.get("source") == "card",
        }
        expected_slot = SLOT_FOR_POOL[template["ability_pool"]]
        if landed[expected_slot]:
            reached += 1
        elif any(landed.values()):
            wrong = next(slot for slot, hit in landed.items() if hit)
            failures.append(
                f"card '{template['name']}' carries a {template['ability_pool']}-pool "
                f"ability, which belongs in the {expected_slot} slot, but it landed "
                f"in {wrong} -- an ability in the wrong slot is read by nothing that "
                f"knows how to fire it"
            )
        else:
            failures.append(
                f"card '{template['name']}' ({template['ability_pool']} pool) equips "
                f"and applies its stats, but its ability reaches no slot at all -- "
                f"it is a stat stick that cost 1,500 echoes"
            )

    # ---- 4. selling cores ---------------------------------------------
    before_cores, before_echoes = player.cores, player.echoes
    result = echo_exchange_service.sell_cores(db, player, cc.CARD_PULL_COST)
    expected = cc.CARD_PULL_COST // rc.CORES_PER_ECHO
    if result["echoes"] != expected:
        failures.append(
            f"selling {cc.CARD_PULL_COST} cores paid {result['echoes']} echoes, "
            f"not the advertised {expected}"
        )
    if player.cores != before_cores - result["cores"]:
        failures.append("selling cores did not deduct what it charged")
    if player.echoes != before_echoes + result["echoes"]:
        failures.append("selling cores did not pay what it promised")

    # CHANGE IS RETURNED, not swallowed. An amount that doesn't divide
    # evenly must cost only what it actually paid for.
    odd = cc.CARD_PULL_COST + (rc.CORES_PER_ECHO - 1)
    result = echo_exchange_service.sell_cores(db, player, odd)
    if result["change"] != rc.CORES_PER_ECHO - 1:
        failures.append(
            f"selling {odd} cores kept {result['change']} as change, not "
            f"{rc.CORES_PER_ECHO - 1} -- the remainder is being swallowed"
        )

    # ...and a balance too small to trade cannot mint an echo.
    player.cores = rc.CORES_PER_ECHO - 1
    db.commit()
    try:
        echo_exchange_service.sell_cores(db, player, player.cores)
        failures.append(
            f"selling {rc.CORES_PER_ECHO - 1} cores succeeded, but "
            f"{rc.CORES_PER_ECHO} are needed for one echo -- this rounds up, "
            f"so repeatedly selling the remainder is free echoes"
        )
    except echo_exchange_service.ExchangeError:
        pass

    # ---- 5. the rate is still calibrated -------------------------------
    #
    # The whole price table rests on one claim: converting a hard-pity
    # run of cores yields exactly what a chosen 5-star costs. If either
    # side moves and nobody moves the other, the shop quietly becomes
    # either the obvious play or a trap, and neither announces itself.
    pity_cores = cc.CARD_FIVE_STAR_HARD_PITY * cc.CARD_PULL_COST
    converted = rc.echoes_for_cores(pity_cores)
    chosen = rc.card_cost(5)
    if converted != chosen:
        failures.append(
            f"pulling to the 5-star guarantee costs {pity_cores:,} cores, which "
            f"converts to {converted:,} echoes, but a chosen 5-star card costs "
            f"{chosen:,} -- see resonance_config.CORES_PER_ECHO, these are "
            f"supposed to be the same number"
        )

    if rc.ECHO_CHARACTER_COST is not rc.ECHO_COST_BY_STAR:
        failures.append(
            "ECHO_CHARACTER_COST is a COPY of ECHO_COST_BY_STAR rather than the "
            "same object -- two price tables will drift, and this codebase has "
            "lost a week to that shape of bug three times"
        )

    print(f"characters: {bought_characters} bought through the select's own value")
    print(f"cards     : {bought_cards} bought, every ability resolving")
    print(f"equipped  : {reached}/{len(cc.CARD_TEMPLATES)} card abilities reach a real combatant")
    print(f"paging    : every offer reachable, {SELECT_OPTION_LIMIT} per page")
    print(f"conversion: {rc.CORES_PER_ECHO} cores -> 1 echo, change returned, "
          f"no rounding up")
    print(f"calibrated: {pity_cores:,} cores (5★ pity) = {converted:,} echoes "
          f"= one chosen 5★")
    print()
    if failures:
        for line in dict.fromkeys(failures):
            print(f"  FAIL  {line}")
        return 1
    print("OK -- the exchange sells everything it displays, at the right price.")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, ".")
    sys.exit(main())
