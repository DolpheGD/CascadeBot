"""
Every region's FINAL boss must be beatable.

    python -m tools.check_final_bosses

THIS EXISTS BECAUSE TWO OF THEM WERE NOT, FOR MONTHS, AND NOTHING NOTICED.

Abyssnia's designated final bosses -- Xender and Rohan -- measured 0%
against a full-HP endgame squad at the level and gear the region is
played at. Not "hard": arithmetically impossible. Rohan had 64,742 HP and
1,011 attack over four actions per cycle, against a reference squad with
5,515 TOTAL health and ~230 attack each. He out-damaged the party's
entire health pool in about two cycles and had twelve times their pool to
chew through.

Every existing tool said the region was fine:

  * tools/check_progression asserts final-boss HP is non-decreasing
    across regions and that regular-boss pools are not lopsided. Both
    were true. "The numbers rise smoothly" and "a player can win" are
    different claims and only the second one matters.

  * tools/bench_roles reported Abyssnia at a healthy 23-28% clear rate,
    because it selected bosses with get_templates_by_role("boss"), which
    returns the CHECKPOINT bosses. The game uses
    get_boss_encounter(final=True). The benchmark had never once fought
    the enemy that ends a run.

So this file fights them. It builds the region's reference squad the way
factory does -- real templates, real generated gear, real talents -- and
runs the actual final-boss encounter, including boss groups. Twice: once
at full health, and once arriving at 60%, which is what the last room of
a real run actually looks like.

A final boss that cannot be beaten from full health is a region nobody
can finish, and that should be impossible to ship quietly.
"""

from __future__ import annotations

import os
import random
import sys
import tempfile

# A final boss must be winnable at least this often by a full-health
# reference squad. Deliberately low: these are meant to be the hardest
# fights in the game, and a player brings relics, consumables and a
# better-chosen team than this squad has. It is a floor on POSSIBILITY,
# not a target.
MIN_WIN_FROM_FULL = 0.15
# Above this a final boss is a formality. Reported as a WARNING, not a
# failure, and deliberately so: "unbeatable" is a bug -- nobody can finish
# the region -- while "too easy" is a design judgement about how climactic
# a region finale should be, and this tool has not been given that call.
#
# Measured today: Glacier 100%, Wastelands 100%, Hotlands 100%,
# Voidcrest 100%, Abyssnia 67% from full health. The first four are
# anticlimactic, and the reason is structural rather than per-boss -- a
# region's reference squad is level 8/22/38/52/70 while its final boss
# sits at floor//10 + 1 + level_offset, i.e. level 6/20/25/29/45. The
# party out-levels the boss by more the deeper the region goes.
#
# Note this does NOT mean the regions are easy: bench_roles has the full
# runs at 80/74/75/61/32%. The difficulty lives in 18 fights of
# attrition, not in the boss at the end. Whether that is the intended
# shape is a call for a human.
# JUDGED ON THE WORN COLUMN, NOT THE FULL-HEALTH ONE.
#
# "Too easy from full health" turned out to be a badly misleading test,
# and Glacier proved it with numbers. Its finale reads 100% won from full
# health at almost every setting -- and raising the boss's HP from 510 to
# 700 (still "trivial" by that measure) halved the region's whole run
# clear rate, from 71% to 47%. A level-8 squad has almost no sustain and
# arrives at its finale badly hurt, so a fight that is free at full HP
# can still be the thing that ends most runs.
#
# Nobody fights a final boss at full health. The 60% column is the one
# that describes the fight players actually have, so that is what the
# "formality" warning reads. The full-health column is kept as the
# UNBEATABLE floor, where it is the right question: if you cannot win it
# even fresh, nobody can finish the region.
MAX_WIN_WHEN_WORN = 0.90
SEEDS = 24
# The depth a final boss actually sits at. Runs are ~45 rooms after the
# map rewrite; the enemy level formula only reads floor // 10, so any
# floor in the low 40s gives the same answer.
FINAL_FLOOR = 45


def main() -> int:
    sys.path.insert(0, ".")
    os.environ.setdefault("DATABASE_URL", "sqlite:///" + tempfile.mktemp(suffix=".db"))
    import bot.config as cfg
    cfg.DATABASE_URL = os.environ["DATABASE_URL"]

    from sqlalchemy.orm import sessionmaker

    from bot.database.db import engine
    from bot.database.db_init import init_db
    from bot.database.models.character_model import CharacterTemplate, PlayerCharacter
    from bot.database.models.enums import Rarity
    from bot.game.characters import talent_config as tc
    from bot.game.combat import enemies as catalog
    from bot.game.combat.battle import Battle
    from bot.game.combat.factory import build_enemy_combatant, build_party_combatants
    from bot.game.dungeon.region_config import REGION_DIFFICULTY, ordered_regions
    from bot.game.loot.generator import LootGenerator
    from bot.game.loot.rarity_config import upgrade_level_cap
    from bot.services import character_template_service, item_template_service

    init_db()
    db = sessionmaker(bind=engine)()
    character_template_service.ensure_character_templates_seeded(db)
    item_template_service.ensure_item_templates_seeded(db)
    db.commit()
    by_name = {t.name: t for t in db.query(CharacterTemplate).all()}

    # READ FROM THE GAME'S OWN CONFIG. This used to be a private copy
    # called PROFILE, and bench_roles carried a second one -- two tools
    # with their own idea of who plays a region, and a game with none.
    PROFILE = {
        region: (d["expected_squad_level"], d["expected_gear_rarity"],
                 d["expected_gear_level"])
        for region, d in REGION_DIFFICULTY.items()
    }
    SQUAD = ["Josh", "Caliper", "Dolphe", "Refender"]

    gear_cache: dict = {}

    def kit(rarity, item_level, draw):
        key = (rarity, item_level, draw)
        if key not in gear_cache:
            gen = LootGenerator(rng=random.Random(
                rarity.sort_order * 1000 + item_level * 10 + draw))
            items = []
            for _ in range(6):
                template = item_template_service.pick_random_template(
                    db, rng=gen.rng, rarity=rarity)
                if template is not None:
                    items.append(gen.generate_item(
                        template, player_id=1, item_level=item_level,
                        rarity_override=rarity))
            gear_cache[key] = items
        return list(gear_cache[key])

    def squad(level, rarity, gear_level, draw):
        members = []
        for index, name in enumerate(SQUAD):
            template = by_name.get(name)
            if template is None:
                continue
            row = PlayerCharacter(player_id=1, template_id=template.id,
                                  level=level, dupe_count=0)
            row.template = template
            row.current_hp = None
            row.id = index + 1
            nodes = tc.tree_for(template.name, template.character_class)
            points = tc.points_for_level(level)
            chosen = []
            for node in sorted((n for n in nodes if n["branch"] == "a"),
                               key=lambda n: n["tier"]):
                if node["cost"] > points:
                    break
                points -= node["cost"]
                chosen.append(node["id"])
            row.talents = chosen
            members.append(row)
        item_level = max(1, min(gear_level, upgrade_level_cap(rarity)))
        return build_party_combatants(
            members, {m.id: kit(rarity, item_level, draw) for m in members})

    def win_rate(region, hp_fraction):
        level, rarity, gear_level = PROFILE[region]
        offset = REGION_DIFFICULTY[region]["level_offset"]
        wins = 0
        for seed in range(SEEDS):
            rng = random.Random(seed)
            party = squad(level, rarity, gear_level, seed % 4)
            if not party:
                return 0.0
            for member in party:
                member.current_hp = max(1, int(member.max_hp * hp_fraction))
            # THE REAL SELECTOR, final=True -- the whole point of this file.
            templates = catalog.get_boss_encounter(rng, region=region, final=True)
            # ENEMY LEVEL COMES FROM THE SAME FORMULA THE GAME USES:
            # floor // 10 + 1 + level_offset (see dungeon_service.enter_node
            # and bench_roles). NOT the squad's level plus the offset --
            # the first version of this line computed
            # `level + offset - level + level`, which is squad level plus
            # offset, and fought Abyssnia's boss at level 110 instead of
            # 45. It duly reported every region in the game as
            # unbeatable, including three that are fine. A harness that
            # over-reports is exactly as useless as one that under-
            # reports, and rather more alarming.
            # Mirrors dungeon_service exactly: the floor-derived level,
            # floored at the region's expected squad level plus the delta.
            boss_level = max(
                FINAL_FLOOR // 10 + 1 + offset,
                REGION_DIFFICULTY[region]["expected_squad_level"]
                + REGION_DIFFICULTY[region].get("final_boss_level_delta", 0))
            enemies = [build_enemy_combatant(t, boss_level) for t in templates]
            battle = Battle(party, enemies, rng=rng)
            for _ in range(600):
                if battle.is_over():
                    break
                actor = battle.current_actor()
                if actor is None:
                    break
                if actor in battle.party:
                    hurt = [m for m in battle.party
                            if m.is_alive() and m.current_hp < m.max_hp * 0.7]
                    if actor.ultimate_ready():
                        battle.take_party_action("ultimate")
                        continue
                    ready = [a for a in actor.active_abilities
                             if actor.ability_ready(a)]
                    heals = [a for a in ready
                             if (a.get("effect") or {}).get("kind", "").startswith("heal")]
                    if heals and hurt:
                        battle.take_party_action("ability", ability_id=heals[0]["id"])
                    elif ready:
                        battle.take_party_action("ability", ability_id=rng.choice(ready)["id"])
                    else:
                        battle.take_party_action("attack")
                else:
                    battle.take_enemy_turn()
            wins += battle.result == "won"
        return wins / SEEDS

    failures: list[str] = []
    warnings: list[str] = []
    print(f"{'region':<20}{'final boss(es)':<38}{'full HP':>9}{'at 60%':>9}")
    for region in ordered_regions():
        names = ", ".join(
            t["name"] for t in catalog.get_boss_encounter(
                random.Random(0), region=region, final=True))
        full = win_rate(region, 1.0)
        worn = win_rate(region, 0.6)
        flag = ""
        if full < MIN_WIN_FROM_FULL:
            flag = "  <-- UNBEATABLE"
            failures.append(
                f"'{region}': its final boss ({names}) is won {full:.0%} of the time "
                f"by a full-health reference squad at level {PROFILE[region][0]} -- "
                f"under the {MIN_WIN_FROM_FULL:.0%} floor. Nobody can finish this "
                f"region.")
        elif worn > MAX_WIN_WHEN_WORN:
            flag = "  <-- trivial"
            warnings.append(
                f"'{region}': its final boss ({names}) is won {worn:.0%} of the time "
                f"even by a squad arriving at 60% health -- a formality.")
        print(f"{region:<20}{names[:36]:<38}{full:>8.0%}{worn:>9.0%}{flag}")

    if warnings:
        print()
        for warning in warnings:
            print(f"  WARN  {warning}")
    if failures:
        print()
        for failure in failures:
            print(f"  FAIL  {failure}")
        return 1
    print("\nOK -- every region's final boss can actually be beaten.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
