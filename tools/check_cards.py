"""
Validate the Character Card catalog.

    python -m tools.check_cards

Cards are pure data resolved by a generic service, which is the same
property that made check_story and check_encounters necessary: a typo
does not fail at import. It fails quietly, at the worst possible moment,
in the most expensive place in the game.

The specific failure this exists for: `ability_id` and `ability_pool` are
looked up with a `next(..., None)`. Name a pool the card isn't in, or
misspell an id, and card_ability() returns None -- so a 5-star Card the
player spent a hundred cores on equips successfully, shows its stats, and
silently has no ability. Nothing raises. Nothing logs. The only symptom
is that the best item in the game does slightly less than expected.

Checked:

  * every card's ability_id exists IN THE POOL it names
  * every card's ability is one of the Card-only abilities -- a card
    carrying an ability gear can still roll is a design error, not just
    a duplication
  * a card's STARS match its ability's rarity tier (3★ legendary, 4★
    mythic, 5★ divine), so the number on the card means something
  * every Card-only ability is carried by at least one card, so moving
    an ability off gear can't quietly delete it from the game
  * every stat is a real STAT_KEY that the combat factory will apply
  * exactly three stats per card, which is the printed promise
  * star ratings are 3-5 and every rating has cards, so no pull can roll
    a rarity with an empty pool
  * ids and names are unique, and names fit Discord's field-name limit
  * the level curve is monotonic and lands where the config claims
"""

from __future__ import annotations

import sys

# Discord's embed field NAME limit. A card's name is rendered into one
# alongside its stars and level, so the budget is smaller than 256.
NAME_BUDGET = 200


def main() -> int:
    from bot.game.combat.combatant import STAT_KEYS
    from bot.game.economy import card_config as cc
    from bot.game.loot import abilities as ability_pools

    pools = {
        "weapon": ability_pools.WEAPON_SKILLS,
        "artifact": ability_pools.ARTIFACT_SKILLS,
        "armor": ability_pools.ARMOR_PASSIVES,
        "ultimate": ability_pools.ULTIMATE_ABILITIES,
    }

    failures: list[str] = []
    seen_ids: set[str] = set()
    seen_names: set[str] = set()
    carried: set[str] = set()

    for card in cc.CARD_TEMPLATES:
        where = f"card '{card['name']}'"

        if card["id"] in seen_ids:
            failures.append(f"{where}: duplicate id {card['id']!r}")
        seen_ids.add(card["id"])
        if card["name"] in seen_names:
            failures.append(f"{where}: duplicate name")
        seen_names.add(card["name"])

        if len(card["name"]) > NAME_BUDGET:
            failures.append(
                f"{where}: name is {len(card['name'])} chars, over the "
                f"{NAME_BUDGET}-char embed field budget"
            )

        if card["star_rating"] not in (3, 4, 5):
            failures.append(f"{where}: star_rating {card['star_rating']} is not 3-5")

        # --- stats
        stats = card["stats"]
        if len(stats) != 3:
            failures.append(
                f"{where}: has {len(stats)} stats, not 3 -- three is what the "
                f"card screen and the design both promise"
            )
        for stat in stats:
            if stat not in STAT_KEYS:
                failures.append(
                    f"{where}: stat {stat!r} is not a real stat "
                    f"-- the combat factory would silently drop it"
                )

        # --- ability
        pool = pools.get(card["ability_pool"])
        if pool is None:
            failures.append(
                f"{where}: ability_pool {card['ability_pool']!r} is not one of "
                f"{', '.join(sorted(pools))}"
            )
            continue

        ability = next((a for a in pool if a["id"] == card["ability_id"]), None)
        if ability is None:
            failures.append(
                f"{where}: ability {card['ability_id']!r} is not in the "
                f"{card['ability_pool']} pool -- the card would equip with NO "
                f"ability at all, silently"
            )
            continue

        carried.add(card["ability_id"])

        # STARS MUST MATCH THE ABILITY'S TIER.
        #
        # Seven of the original sixteen cards failed this, including 3★
        # cards carrying mythic abilities and 5★ cards carrying mythic
        # ones. Nothing broke -- which is the problem. A 3★ pull handing
        # over the same class of ability as a 5★ pull silently makes the
        # rarity on the card meaningless, and the only way to notice is
        # to line all of them up and look, which nobody does twice.
        expected = cc.CARD_ABILITY_TIER_BY_STAR.get(card["star_rating"])
        actual = getattr(ability["min_rarity"], "value", ability["min_rarity"])
        if expected and actual != expected:
            failures.append(
                f"{where}: {card['star_rating']}★ should carry a {expected} "
                f"ability, but {card['ability_id']!r} is {actual} -- the star "
                f"rating and the power it buys have come apart"
            )

        if card["ability_id"] not in cc.CARD_ONLY_ABILITY_IDS:
            failures.append(
                f"{where}: carries {card['ability_id']!r}, which gear can still "
                f"roll -- a card's ability should be one only cards have"
            )

    # --- nothing lost in the move off gear
    for ability_id in sorted(cc.CARD_ONLY_ABILITY_IDS - carried):
        failures.append(
            f"ability {ability_id!r} was removed from gear rolls but no card "
            f"carries it -- it is now unobtainable by any means"
        )

    # --- every rollable star has something to roll
    for star in (3, 4, 5):
        if not cc.cards_of_star(star):
            failures.append(
                f"no {star}-star cards exist, but the banner can roll that "
                f"rating -- pull_cards would fall back to the whole catalog"
            )

    # --- the level curve does what the config says
    low = cc.card_level_multiplier(1)
    high = cc.card_level_multiplier(cc.CARD_MAX_LEVEL)
    if abs(low - cc.CARD_LEVEL_1_MULTIPLIER) > 1e-6:
        failures.append(f"level 1 multiplier is {low}, not {cc.CARD_LEVEL_1_MULTIPLIER}")
    if abs(high - cc.CARD_TOP_MULTIPLIER) > 1e-6:
        failures.append(f"level {cc.CARD_MAX_LEVEL} multiplier is {high}, "
                        f"not {cc.CARD_TOP_MULTIPLIER}")
    previous = -1.0
    for level in range(1, cc.CARD_MAX_LEVEL + 1):
        value = cc.card_level_multiplier(level)
        if value < previous:
            failures.append(f"level curve goes DOWN at level {level} -- levelling "
                            f"a card would make it worse")
            break
        previous = value

    by_star = {star: len(cc.cards_of_star(star)) for star in (3, 4, 5)}
    print(f"cards    : {len(cc.CARD_TEMPLATES)} "
          f"({by_star[3]} 3★, {by_star[4]} 4★, {by_star[5]} 5★)")
    print(f"abilities: {len(carried)}/{len(cc.CARD_ONLY_ABILITY_IDS)} "
          f"card-only abilities carried, all resolving in their pool")
    print(f"curve    : level 1 x{low:.2f} -> level {cc.CARD_MAX_LEVEL} x{high:.2f}, "
          f"monotonic")
    print("tiering  : " + " · ".join(
        f"{star}★={tier}" for star, tier in sorted(cc.CARD_ABILITY_TIER_BY_STAR.items())))
    print()
    if failures:
        for line in dict.fromkeys(failures):
            print(f"  FAIL  {line}")
        return 1
    print("OK -- every card resolves to a real, card-only ability and real stats.")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, ".")
    sys.exit(main())
