"""
Assert no name is truncated in any menu, and no label breaks Discord.

    python -m tools.check_ui_labels

WHY. Truncation is a silent failure. Nothing throws, nothing logs -- the
player just sees "Boss John's Drill…" and, in the 9-character turn order
the battle view used to use, two different Wasteland enemies rendering as
the identical "Wastelan…". Only someone reading that exact screen with
that exact enemy would ever notice.

So the guarantee is checked rather than hoped for. Three things:

  1. Every enemy name longer than the turn-order budget has an authored
     short name (enemies.ENEMY_SHORT_NAMES), that short name fits, and no
     two of them collide -- a collision is worse than a truncation, since
     it doesn't even look wrong.
  2. Rendering a real battle produces no "…" anywhere in the combat
     embed. This is the end-to-end version: it would catch a name that
     reaches the UI through a path nobody thought about.
  3. Every worst-case select/button label fits Discord's hard limits
     (100 for a select label or description, 80 for a button), built from
     the LONGEST real content in the catalogs rather than a guess.
"""

from __future__ import annotations

import sys
from collections import Counter

SELECT_LABEL_LIMIT = 100
BUTTON_LABEL_LIMIT = 80


def main() -> int:
    from bot.game.combat.battle import Battle
    from bot.game.combat.enemies import ENEMY_SHORT_NAMES, ENEMY_TEMPLATES, short_name_for
    from bot.game.combat.factory import build_enemy_combatant
    from bot.game.combat.combatant import Combatant
    from bot.utils import names as name_utils
    from bot.utils import embedder

    failures: list[str] = []
    enemy_names = sorted({t["name"] for t in ENEMY_TEMPLATES})

    # 1. Short names: complete, in budget, unique, not stale.
    budget = name_utils.TURN_ORDER_BUDGET
    for name in enemy_names:
        if len(name) > budget and name not in ENEMY_SHORT_NAMES:
            failures.append(f"'{name}' ({len(name)}) has no short name and exceeds {budget}")
    for full, short in ENEMY_SHORT_NAMES.items():
        if len(short) > budget:
            failures.append(f"short name '{short}' ({len(short)}) exceeds {budget}")
        if full not in enemy_names:
            failures.append(f"short name for '{full}' refers to no template")
    collisions = [n for n, count in Counter(short_name_for(n) for n in enemy_names).items() if count > 1]
    for name in collisions:
        failures.append(f"short name '{name}' is used by more than one enemy")

    longest = max(enemy_names, key=lambda n: len(short_name_for(n)))
    print(f"enemies            : {len(enemy_names)} templates, "
          f"{len(ENEMY_SHORT_NAMES)} with authored short names")
    print(f"longest short name : '{short_name_for(longest)}' "
          f"({len(short_name_for(longest))}/{budget}) for '{longest}'")

    # 2. A real battle, using the longest-named enemies there are, renders
    #    with no ellipsis anywhere.
    worst = sorted(enemy_names, key=len, reverse=True)[:3]
    party = [
        Combatant(
            name=who, is_player=True,
            base_stats={"attack": 50, "defense": 20, "elemental": 50, "speed": 10,
                        "max_hp": 900, "max_mana": 90, "crit_rate": 5,
                        "crit_damage": 150, "recharge": 10},
            current_hp=900, max_hp=900, mana=90, max_mana=90,
        )
        # 32 characters is the /rename ceiling (character_service.
        # CUSTOM_NAME_MAX_LENGTH) -- the worst name a player can create.
        for who in ("A" * 32, "Lily Lovelace", "Sader Vorae", "You")
    ]
    enemies = [build_enemy_combatant(next(t for t in ENEMY_TEMPLATES if t["name"] == n), 30)
               for n in worst]
    battle = Battle(party, enemies)
    embed = embedder.combat_embed(battle)

    rendered = [embed.description or ""] + [f"{f.name}\n{f.value}" for f in embed.fields]
    for chunk in rendered:
        for line in chunk.split("\n"):
            # The player-chosen 32-character name is EXPECTED to shorten --
            # that's what the fallback is for. Authored content is not.
            if "…" in line and "A" * 10 not in line:
                failures.append(f"battle view truncated a name: {line.strip()!r}")

    print(f"battle render      : {sum(len(c.split(chr(10))) for c in rendered)} lines, "
          f"{len(enemies)} longest-named enemies + a 32-char player name")

    # 3. Worst-case labels fit Discord's limits.
    from bot.game.combat.skills import CHARACTER_KIT_MAP
    from bot.game.loot.abilities import ARTIFACT_SKILLS, WEAPON_SKILLS
    from bot.game.loot.item_seed_data import ITEM_TEMPLATES
    from bot.game.loot.naming import GENERIC_PREFIX_BY_RARITY

    longest_item = max(ITEM_TEMPLATES, key=lambda t: len(t["name"]))["name"]
    longest_prefix = max(
        (p for group in GENERIC_PREFIX_BY_RARITY.values() for p in group), key=len)
    longest_ability = max(
        [a for pool in (list(CHARACTER_KIT_MAP.values()), WEAPON_SKILLS, ARTIFACT_SKILLS) for a in pool],
        key=lambda a: len(a["name"]),
    )["name"]

    cases = [
        ("inventory entry", name_utils.fit_suffix("999.", f"{longest_prefix} {longest_item} +15", 100),
         SELECT_LABEL_LIMIT),
        ("character select", name_utils.fit_suffix("A" * 32, "(Lv100, Support DPS)", 100),
         SELECT_LABEL_LIMIT),
        ("squad label", name_utils.fit_suffix("A" * 32, "★★★★★ Lv100 (Amplifier)", 100),
         SELECT_LABEL_LIMIT),
        ("combat ability", f"{longest_ability} -- 50 SP (need 12 more SP)", SELECT_LABEL_LIMIT),
        ("ultimate button", "💥 Ultimate (ready in 2t)", BUTTON_LABEL_LIMIT),
        ("raid summon", f"🟩 Summon {'Rift Patrol'}", BUTTON_LABEL_LIMIT),
    ]
    print("\nworst-case labels:")
    for label, text, limit in cases:
        status = "ok" if len(text) <= limit else "TOO LONG"
        print(f"  {label:<17} {len(text):>3}/{limit}  {status}  {text[:60]}")
        if len(text) > limit:
            failures.append(f"{label} label is {len(text)} chars, over the {limit} limit")

    print()
    if failures:
        for line in dict.fromkeys(failures):
            print(f"  FAIL  {line}")
        return 1
    print("OK -- no authored name truncates, no short name collides, every label fits.")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, ".")
    sys.exit(main())
