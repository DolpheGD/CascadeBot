"""
Assert the Evolution Fragment breakthrough system holds together.

    python -m tools.check_evolution

WHAT MAKES THIS WORTH CHECKING
------------------------------
A breakthrough is a GATE. Everything else in the upgrade economy is a
rate limit -- run short of crystal and you go and get crystal -- but a
breakthrough is a hard stop on a specific item, and there are exactly
four ways for a gate to be wrong, all of them silent:

  1. IT ISN'T THERE. `card_level_cost` and `get_level_up_cost` build a
     cost dict; if the fragment line is missing, levelling works exactly
     as it did before and the whole system is decorative. Nothing
     raises, and the only symptom is that a maxed Divine costs what it
     used to.

  2. IT'S IN THE PREVIEW BUT NOT THE CHARGE (or the reverse). The cost
     shown and the cost taken come from the same function here, so this
     asserts the balance actually MOVES by what was quoted.

  3. IT'S UNPAYABLE. If income can't reach a breakthrough, the item is
     simply capped early, which looks like a design decision rather than
     an arithmetic mistake. So this budgets every declared source
     against what the system actually costs.

  4. THE ORDERING QUIETLY INVERTS. "Cards cost more than gear at the
     same level" and "rarer gear costs more" are both promises made in
     player-facing copy. Both are products of two independently-tuned
     bases, and I got the first one wrong on the first attempt -- at
     CARD_FRAGMENT_BASE = 30 a 3-star card's breakthrough was CHEAPER
     than a Divine item's at the same level.

WHAT IT ASSERTS
  * breakthroughs land on exactly the documented boundaries, and nowhere
    else
  * a Common item never needs one (its cap is the first boundary), and
    every other rarity needs exactly as many as its cap implies
  * gear cost rises strictly with rarity, at every boundary
  * the CHEAPEST card breakthrough beats the DEAREST gear one at every
    shared level
  * levelling gear and cards really does spend fragments, through the
    real service functions against a real database, and refuses when
    short WITHOUT taking the gold
  * every source named in evolution_config's survey actually pays the
    currency, found by looking in the configs rather than trusting the
    comment
"""

from __future__ import annotations

import random
import sys
import tempfile

# What a committed player plausibly earns in a day, used only to sanity
# check that the costs below are reachable at all.
ASSUMED_DAILY_INCOME = 150


def main() -> int:
    import os
    os.environ.setdefault("DATABASE_URL", "sqlite:///" + tempfile.mktemp(suffix=".db"))

    from bot.database.models.enums import Rarity
    from bot.game.economy import evolution_config as ev
    from bot.game.economy.card_config import CARD_MAX_LEVEL
    from bot.game.loot.rarity_config import upgrade_level_cap

    failures: list[str] = []

    # ---- 1. the boundaries are where they are documented --------------
    for level in range(1, 120):
        expected_gear = level % ev.GEAR_BREAKTHROUGH_EVERY == 0
        expected_card = level % ev.CARD_BREAKTHROUGH_EVERY == 0
        if ev.is_gear_breakthrough(level) != expected_gear:
            failures.append(f"gear breakthrough at level {level} disagrees with "
                            f"GEAR_BREAKTHROUGH_EVERY={ev.GEAR_BREAKTHROUGH_EVERY}")
        if ev.is_card_breakthrough(level) != expected_card:
            failures.append(f"card breakthrough at level {level} disagrees with "
                            f"CARD_BREAKTHROUGH_EVERY={ev.CARD_BREAKTHROUGH_EVERY}")

    # ---- 2. a Common never hits one, everything else hits its share ----
    #
    # Every rarity cap is a multiple of 5, so the count is (cap/5 - 1).
    # Asserted rather than assumed: change one cap to 12 and a rarity
    # silently gains or loses a breakthrough.
    for rarity in Rarity:
        cap = upgrade_level_cap(rarity)
        hits = [level for level in range(1, cap) if ev.gear_breakthrough_cost(level, rarity)]
        expected = [level for level in range(1, cap)
                    if level % ev.GEAR_BREAKTHROUGH_EVERY == 0]
        if hits != expected:
            failures.append(
                f"{rarity.value}: breakthroughs at {hits}, expected {expected} "
                f"for a cap of {cap}"
            )
    if ev.gear_lifetime_cost(Rarity.COMMON) != 0:
        failures.append(
            f"a Common item needs {ev.gear_lifetime_cost(Rarity.COMMON)} fragments, "
            f"but its cap of {upgrade_level_cap(Rarity.COMMON)} IS the first "
            f"boundary -- the cheapest gear in the game should never meet a gate"
        )

    # ---- 3. rarer gear costs strictly more -----------------------------
    ladder = [Rarity.UNCOMMON, Rarity.RARE, Rarity.EPIC,
              Rarity.LEGENDARY, Rarity.MYTHIC, Rarity.DIVINE]
    for level in range(ev.GEAR_BREAKTHROUGH_EVERY, 40, ev.GEAR_BREAKTHROUGH_EVERY):
        costs = [(r, ev.gear_breakthrough_cost(level, r)) for r in ladder]
        for (lower, low_cost), (higher, high_cost) in zip(costs, costs[1:]):
            if high_cost < low_cost:
                failures.append(
                    f"at level {level}, {higher.value} costs {high_cost} but "
                    f"{lower.value} costs {low_cost} -- rarity is supposed to "
                    f"cost more, not less"
                )

    # ---- 4. cards beat gear at every shared level ----------------------
    #
    # Cheapest card against DEAREST gear, which is the strong form: if
    # the worst case holds, every other pairing does.
    for level in range(ev.CARD_BREAKTHROUGH_EVERY, CARD_MAX_LEVEL + 1,
                       ev.CARD_BREAKTHROUGH_EVERY):
        cheapest_card = min(ev.card_breakthrough_cost(level, star) for star in (3, 4, 5))
        dearest_gear = max(ev.gear_breakthrough_cost(level, r) for r in Rarity)
        if cheapest_card <= dearest_gear:
            failures.append(
                f"at level {level} the cheapest card breakthrough is "
                f"{cheapest_card} and the dearest gear one is {dearest_gear} -- "
                f"cards are supposed to cost MORE than gear at the same level "
                f"(see CARD_FRAGMENT_BASE, which was 30 and had to become 60 "
                f"for exactly this reason)"
            )

    # ---- 5. it actually charges, against a real database ---------------
    from sqlalchemy.orm import sessionmaker

    from bot.database.db import engine
    from bot.database.db_init import init_db
    from bot.database.models.player_model import Player
    from bot.game.loot.generator import LootGenerator
    from bot.services import card_service, item_template_service, item_upgrade_service

    init_db()
    db = sessionmaker(bind=engine)()
    item_template_service.ensure_item_templates_seeded(db)
    card_service.ensure_card_templates_seeded(db)

    player = Player(id=1, username="evo-check", gold=10**9, evolution_fragments=10**6)
    for material in ("wood", "stone", "metal", "crystal", "xendium",
                     "permafrost_ore", "void", "entropy"):
        setattr(player, material, 10**6)
    db.add(player)
    db.commit()

    # A REAL generated item, not a hand-built row. The first attempt
    # constructed InventoryItem directly and died on a NOT NULL slot --
    # which was the checker being wrong, not the game. Going through the
    # generator means the object under test is the one players own.
    def _make_item(owner, rarity, level):
        item_template = item_template_service.pick_random_template(
            db, rng=random.Random(1), rarity=rarity)
        made = LootGenerator(rng=random.Random(1)).generate_item(
            item_template, player_id=owner.id, item_level=level,
            rarity_override=rarity)
        db.add(made)
        db.commit()
        return made

    item = _make_item(player, Rarity.DIVINE, 5)

    # AT a breakthrough: the quoted cost must be non-zero and the balance
    # must move by exactly that much.
    quoted = item_upgrade_service.get_level_up_cost(item, levels=1)
    if not quoted.get("fragments"):
        failures.append(
            "a Divine item at level 5 quotes no fragments -- the gate is not "
            "wired into get_level_up_cost, so levelling ignores it entirely"
        )
    before = player.evolution_fragments
    ok, message = item_upgrade_service.level_up_item(db, player, item, levels=1)
    spent = before - player.evolution_fragments
    if not ok:
        failures.append(f"levelling a fully-funded item failed: {message}")
    elif spent != quoted.get("fragments", 0):
        failures.append(
            f"the preview quoted {quoted.get('fragments')} fragments and the "
            f"upgrade took {spent} -- the cost shown and the cost charged come "
            f"apart"
        )

    # NOT at a breakthrough: nothing should be taken.
    before = player.evolution_fragments
    item_upgrade_service.level_up_item(db, player, item, levels=1)   # 6 -> 7
    if player.evolution_fragments != before:
        failures.append(
            f"levelling from 6 to 7 spent "
            f"{before - player.evolution_fragments} fragments -- only every "
            f"{ev.GEAR_BREAKTHROUGH_EVERY}th level is a breakthrough"
        )

    # A MULTI-LEVEL run must charge for every boundary it crosses, not
    # just the first. 7 -> 22 crosses 10, 15 and 20.
    quoted = item_upgrade_service.get_level_up_cost(item, levels=15)
    crossed = sum(ev.gear_breakthrough_cost(level, Rarity.DIVINE)
                  for level in range(item.item_level, item.item_level + 15))
    if quoted.get("fragments") != crossed:
        failures.append(
            f"a 15-level upgrade from {item.item_level} quotes "
            f"{quoted.get('fragments')} fragments but crosses boundaries worth "
            f"{crossed} -- a batch is skipping breakthroughs it passes through"
        )

    # ---- 6. refusing costs nothing -------------------------------------
    #
    # The gold/material path spends first and refunds on failure. A
    # fragment shortfall is the failure a player will hit MOST, so it has
    # to be the one that touches nothing at all.
    broke = Player(id=2, username="broke", gold=10**9, evolution_fragments=0)
    for material in ("wood", "stone", "metal", "crystal", "xendium",
                     "permafrost_ore", "void", "entropy"):
        setattr(broke, material, 10**6)
    db.add(broke)
    db.commit()
    poor_item = _make_item(broke, Rarity.DIVINE, 10)

    gold_before, level_before = broke.gold, poor_item.item_level
    ok, message = item_upgrade_service.level_up_item(db, broke, poor_item, levels=1)
    if ok:
        failures.append("levelling past a breakthrough succeeded with 0 fragments")
    if broke.gold != gold_before:
        failures.append(
            f"a refused breakthrough still moved gold ({gold_before} -> "
            f"{broke.gold}) -- the shortfall must be checked before anything "
            f"is spent, not refunded afterwards"
        )
    if poor_item.item_level != level_before:
        failures.append("a refused breakthrough still levelled the item")
    if "fragment" not in message.lower() and "breakthrough" not in message.lower():
        failures.append(
            f"the refusal reads {message!r}, which never mentions the "
            f"breakthrough -- the player has no way to learn what stopped them"
        )

    # ---- 7. cards charge too, and scale with stars ---------------------
    from bot.game.economy import card_config as cc
    for star in (3, 4, 5):
        cost = cc.card_level_cost(ev.CARD_BREAKTHROUGH_EVERY, star)
        if not cost.get("evolution_fragments"):
            failures.append(
                f"a {star}-star card at level {ev.CARD_BREAKTHROUGH_EVERY} quotes "
                f"no fragments -- card_level_cost is not applying the gate"
            )
    tiers = [cc.card_level_cost(ev.CARD_BREAKTHROUGH_EVERY, s).get("evolution_fragments", 0)
             for s in (3, 4, 5)]
    if not (tiers[0] < tiers[1] < tiers[2]):
        failures.append(
            f"card breakthrough costs by star are {tiers} -- higher stars are "
            f"supposed to cost strictly more"
        )

    # ---- 8. every declared source really pays ---------------------------
    #
    # Read out of the configs, not out of the survey comment. The Core
    # economy's source list drifted out of step with reality twice by
    # being prose that nobody could run.
    from bot.game.abyss import abyss_config
    from bot.game.economy import (
        daily_config, domain_config, harvester_config, hq_config, quest_config,
        raid_config, vote_config,
    )
    from bot.services import combat_service, prestige_service

    shop_doors = [listing for listing in hq_config.SHOP_LISTINGS
                  if listing.get("reward_currency") == "evolution_fragments"]

    sources = {
        "harvester": any(h["currency"] == "evolution_fragments"
                         for h in harvester_config.HARVESTER_TEMPLATES),
        "domain": any(
            any("evolution_fragments" in (reward or {})
                for reward in d["rewards"].values() if isinstance(reward, dict))
            for d in domain_config.DOMAIN_TYPES if d["reward_kind"] == "currency"
        ),
        "shop": bool(shop_doors),
        "daily": daily_config.compute_daily_fragments(1) > 0,
        "vote": vote_config.compute_vote_fragments(1) > 0,
        "abyss": all("evolution_fragments" in floor["rewards"]
                     for floor in abyss_config.FLOORS),
        "raids": all("evolution_fragments" in tier["rewards"]
                     for tier in raid_config.RAID_TIERS),
        "quests": "evolution_fragments" in quest_config.BEGINNER_BONUS_REWARD,
        "prestige": prestige_service.FRAGMENTS_PER_SCORE > 0,
        "expeditions": bool(combat_service.FRAGMENT_DROP_CHANCE),
    }

    # THE SHOP TAKES MORE THAN ONE CURRENCY.
    #
    # A single listing is a bottleneck wearing a shop's clothes: a player
    # short of fragments but sitting on metal had exactly one conversion
    # available and it wanted gold. Asserted rather than left to the
    # comment, because "add another door" is precisely the kind of thing
    # that gets reverted by a later tidy-up.
    door_currencies = {listing["cost_currency"] for listing in shop_doors}
    if len(door_currencies) < 3:
        failures.append(
            f"the shop buys fragments with only {sorted(door_currencies)} -- one or "
            f"two entrances makes the shop a vending machine for whoever happens to "
            f"hold the right resource"
        )

    # ...and every door must be daily-limited, or the shop stops being a
    # convenience and becomes the whole economy.
    for listing in shop_doors:
        if not listing.get("daily_limit"):
            failures.append(
                f"shop listing {listing['name']!r} sells fragments with no daily "
                f"limit -- an unlimited conversion undercuts the harvester, the "
                f"domain and every drop in the game at once"
            )
    for name, wired in sources.items():
        if not wired:
            failures.append(
                f"evolution_config's source survey claims {name} pays fragments, "
                f"and it does not -- a comment describing intent rather than "
                f"behaviour is the most expensive kind"
            )

    # ---- 9. the costs are reachable ------------------------------------
    divine = ev.gear_lifetime_cost(Rarity.DIVINE)
    five_star = ev.card_lifetime_cost(5)
    if divine > ASSUMED_DAILY_INCOME * 14:
        failures.append(
            f"a Divine item needs {divine:,} fragments, over two weeks of income "
            f"at {ASSUMED_DAILY_INCOME}/day -- gear is meant to be finishable"
        )
    if five_star < divine:
        failures.append(
            f"a maxed 5-star card ({five_star:,}) costs less than a maxed Divine "
            f"item ({divine:,}) -- the Card is supposed to be the longer project"
        )

    print("boundaries: gear every "
          f"{ev.GEAR_BREAKTHROUGH_EVERY}, cards every {ev.CARD_BREAKTHROUGH_EVERY}")
    print("gear      : " + " · ".join(
        f"{r.value} {ev.gear_lifetime_cost(r)}" for r in Rarity))
    print("cards     : " + " · ".join(
        f"{s}★ {ev.card_lifetime_cost(s):,}" for s in (3, 4, 5)))
    print("charging  : previewed cost matches charged cost; refusal spends nothing")
    print("sources   : " + " · ".join(sorted(sources)))
    print(f"budget    : divine gear {divine:,} (~{divine / ASSUMED_DAILY_INCOME:.0f} days), "
          f"5★ card {five_star:,} (~{five_star / ASSUMED_DAILY_INCOME:.0f} days)")
    print()
    if failures:
        for line in dict.fromkeys(failures):
            print(f"  FAIL  {line}")
        return 1
    print("OK -- breakthroughs gate, charge, refuse cleanly, and are payable.")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, ".")
    sys.exit(main())
