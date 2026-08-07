"""
ROLE COMPOSITION benchmark -- "is one of each actually the best squad?"

    python -m tools.bench_roles
    python -m tools.bench_roles --runs 40

bench_comps.py compares NAMED comps on a damage dummy. bench_healers.py
asks whether a Sustain is worth a slot. This asks the question those two
can't, because it is a question about the CLASS SYSTEM rather than about
any character: given four slots, what does the ideal ROLE SPLIT look
like, and does the answer change as the game scales?

The design target, stated up front so the output can be read against it:

    1 DPS + 1 Support DPS + 1 Amplifier + 1 Sustain should be the best
    squad, or within noise of the best, in EVERY region.

Anything else winning is a balance bug, and the two specific failures
this tool exists to catch are:

  * "3 Amplifiers + 1 DPS" beating one-of-each. Amplifier buffs multiply
    the carry's damage; if three of them stack better than a Sustain and
    a Support DPS contribute, the game has one strategy.
  * "no Sustain" comps staying viable deep into the game, because gear
    (lifesteal, regen, shield passives) substitutes for the class and
    enemy damage doesn't scale fast enough to punish it.

MODELLED WITH GEAR AND OVER FULL RUNS, both of which change the answer:

  * Gear is the biggest multiplier in the game, and the "healers are
    obsolete because of equipment" claim is unmeasurable without it.
  * HP carries between fights inside an expedition, so a comp that wins
    every fight at 20% HP is not the same as one that wins at 80%. Per
    fight, everything looks fine; per RUN, attrition is what kills you,
    and attrition is exactly what a Sustain answers.

Every comp in a given region is run against the SAME seeds, the same
floors and the same gear, so the only variable is the role split.
"""

from __future__ import annotations

import argparse
import os
import random
import sys
import tempfile
import time

# ----------------------------------------------------------------------
# ROLE ROSTERS
#
# Deliberately picked so every comp averages the same star rating and no
# comp is carried by a single outlier character -- the thing being
# measured is the ROLE, not the roster slot. Each list is ordered
# best-first; a comp asking for two Amplifiers takes the first two.
# ----------------------------------------------------------------------
ROSTER = {
    "dps":         ["Josh", "Star", "Blastix", "Aizer"],
    "support_dps": ["Caliper", "Nyrvite", "Sader Vorae", "Blueflame"],
    "amplifier":   ["Dolphe", "Virtual", "Nebula", "Chary"],
    "sustain":     ["Refender", "Bee Jee", "Kotori", "Jofrog"],
}

# The comps under test. Keys are display labels; values are role counts.
COMPS: dict[str, dict[str, int]] = {
    "1 of each":        {"dps": 1, "support_dps": 1, "amplifier": 1, "sustain": 1},
    "3 amp + 1 dps":    {"dps": 1, "amplifier": 3},
    "2 amp + dps + sus": {"dps": 1, "amplifier": 2, "sustain": 1},
    "no sustain":       {"dps": 1, "support_dps": 1, "amplifier": 2},
    "no support dps":   {"dps": 2, "amplifier": 1, "sustain": 1},
    "no amplifier":     {"dps": 2, "support_dps": 1, "sustain": 1},
    "4 dps":            {"dps": 4},
    "double support":   {"dps": 1, "support_dps": 2, "sustain": 1},
    # The mirror of "3 amp + 1 dps", and it has to be here for the same
    # reason. Debuffs are deliberately exempt from the amplification
    # budget, which makes them the one multiplier in the game that isn't
    # taxed for stacking -- so the obvious way this pass could go wrong
    # is by moving the one-strategy problem from Amplifiers onto Support
    # DPS instead of removing it. If this column ever tops the table,
    # that is exactly what happened.
    "3 support + 1 dps": {"dps": 1, "support_dps": 3},
}

# Region -> (squad level, gear rarity name, gear item level). Roughly
# what a player actually arrives with, matching sim_expedition's model
# and region_config's own notes.
REGION_PROFILE = {
    "Glacier 15":       (8, "RARE", 12),
    "The Wastelands":   (22, "EPIC", 18),
    "The Hotlands":     (38, "LEGENDARY", 22),
    "Voidcrest Desert": (52, "MYTHIC", 28),
    "Abyssnia":         (70, "DIVINE", 34),
}

NUM_FLOORS = 9


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=30,
                        help="expedition runs per comp per region")
    parser.add_argument("--region", default=None, help="only this region")
    # A full sweep takes many minutes, which is longer than some shells
    # will hold a foreground process. --cache/--budget make the sweep
    # RESUMABLE: each invocation works until its time budget runs out,
    # appends what it finished to the cache file, and the next
    # invocation picks up where it left off. Re-running with the same
    # cache is therefore free once the sweep is complete, which also
    # makes before/after comparisons cheap.
    parser.add_argument("--cache", default=None,
                        help="TSV file of finished results; resumes and appends")
    parser.add_argument("--budget", type=float, default=0,
                        help="seconds to work for before stopping early (0 = no limit)")
    # The four single-swap comps ("1 of each" plus each role replaced by
    # a duplicate of another) are the ones that actually decide the
    # question; the rest are context. --comps runs just those when
    # iterating on a number, which is roughly a 2x speedup per reading.
    parser.add_argument("--comps", default=None,
                        help="comma-separated comp labels to run (default: all)")
    args = parser.parse_args()

    if args.comps:
        wanted = {label.strip() for label in args.comps.split(",")}
        unknown = wanted - set(COMPS)
        if unknown:
            print(f"unknown comp(s): {', '.join(sorted(unknown))}", file=sys.stderr)
            return 2
        for label in list(COMPS):
            if label not in wanted:
                del COMPS[label]

    os.environ.setdefault("DATABASE_URL", "sqlite:///" + tempfile.mktemp(suffix=".db"))
    import bot.config as cfg
    cfg.DATABASE_URL = os.environ["DATABASE_URL"]

    from sqlalchemy.orm import sessionmaker

    from bot.database.db import engine
    from bot.database.db_init import init_db
    from bot.database.models.character_model import CharacterTemplate, PlayerCharacter
    from bot.database.models.enums import Rarity, RoomType
    from bot.game.combat import enemies as catalog
    from bot.game.combat.battle import Battle
    from bot.game.combat.factory import build_enemy_combatant, build_party_combatants
    from bot.game.dungeon.region_config import REGION_DIFFICULTY, ordered_regions
    from bot.game.dungeon.relic_config import CAMPFIRE_REST_PERCENT
    from bot.game.dungeon.room_config import ROOM_WEIGHTS_BY_STAGE
    from bot.game.loot.generator import LootGenerator
    from bot.game.loot.rarity_config import upgrade_level_cap
    from bot.services import character_template_service, item_template_service

    init_db()
    db = sessionmaker(bind=engine)()
    character_template_service.ensure_character_templates_seeded(db)
    item_template_service.ensure_item_templates_seeded(db)
    db.commit()
    by_name = {t.name: t for t in db.query(CharacterTemplate).all()}

    gear_cache: dict = {}

    def kit(rarity, item_level, slots=5):
        """A fixed loadout for (rarity, level), independent of when it was
        first requested.

        This used to draw from ONE shared RNG stream, which quietly made
        the benchmark non-reproducible across invocations: the items a
        squad got depended on the order regions and comps happened to be
        evaluated in, so `--region Voidcrest` on its own produced
        different gear than the same region inside a full sweep. Two runs
        of the identical build then disagreed by 25 points of clear rate,
        which is indistinguishable from a balance change and was very
        nearly read as one.

        Seeding per cache key makes a given (rarity, level) always
        produce the same five items, so before/after comparisons differ
        only by the thing being compared.
        """
        key = (rarity, item_level, slots)
        if key not in gear_cache:
            # NOT hash(): Python randomises string hashing per process
            # unless PYTHONHASHSEED is pinned, so seeding off it makes
            # every invocation draw different gear -- the same
            # irreproducibility this is meant to remove, just with a
            # different cause. Rarity.sort_order is a stable small int.
            seed = (rarity.sort_order * 10_000) + (item_level * 100) + slots
            seeded = LootGenerator(rng=random.Random(seed))
            items = []
            for _ in range(slots):
                tpl = item_template_service.pick_random_template(
                    db, rng=seeded.rng, rarity=rarity)
                if tpl is None:
                    continue
                items.append(seeded.generate_item(
                    tpl, player_id=1, item_level=item_level, rarity_override=rarity))
            gear_cache[key] = items
        return list(gear_cache[key])

    def pc(template, level):
        row = PlayerCharacter(player_id=1, template_id=template.id,
                              level=level, dupe_count=0)
        row.template = template
        row.current_hp = None
        return row

    def build_squad(comp, level, rotation):
        """`rotation` slides which characters fill each role.

        Without it this benchmark silently measures CHARACTERS, not
        roles. Fixing the Support DPS slot to Caliper and the Amplifier
        slot to Virtual and concluding "the Amplifier role is stronger"
        is a claim about two characters -- and an early version of this
        tool did exactly that, reporting a 20-point swing in one region
        and the opposite swing in another, which is the signature of
        having measured the wrong thing. Rotating over the whole roster
        for each role averages the individual kits out and leaves the
        role itself as the only variable.
        """
        names = []
        for role, count in comp.items():
            pool = ROSTER[role]
            names.extend(pool[(rotation + offset) % len(pool)]
                         for offset in range(count))
        members = [pc(by_name[n], level) for n in names if n in by_name]
        for index, member in enumerate(members):
            member.id = index + 1
        return members

    # ------------------------------------------------------------------
    # The simulated player has to be COMPETENT, or the benchmark measures
    # the bot instead of the balance.
    #
    # The naive version of this loop -- "fire a random ready ability" --
    # systematically understated both support roles, in a way that looks
    # like a balance result and isn't:
    #
    #   * It re-cast buffs that were already running. Under the shared
    #     amplification budget a duplicate buff to the same stat steps
    #     down the falloff ladder, so a spamming bot spent an Amplifier's
    #     turns on ~25%-value buffs and the class read as weak.
    #   * It healed allies who were on full HP, which is simply a wasted
    #     turn, and a Sustain that wastes turns reads as not worth a slot.
    #
    # Neither is a decision a player makes. Both are filtered out below,
    # which is the smallest change that stops the AI from being the thing
    # under test.
    # ------------------------------------------------------------------
    BUFF_KINDS = {"team_buff", "team_double_buff", "ally_buff", "buff_self",
                  "team_buff_and_resource", "team_heal_and_buff",
                  "team_shield_and_buff"}
    HEAL_KINDS = {"heal_lowest_ally_percent_max_hp", "team_heal_percent_max_hp",
                  "heal_from_stat", "team_heal_from_stat", "cleanse_ally_and_heal",
                  "sacrifice_hp_heal_lowest_ally_percent_max_hp",
                  "sacrifice_hp_heal_team_percent_max_hp", "team_heal_and_buff",
                  "team_regen_over_time"}

    def worth_casting(actor, ability, party):
        effect = ability.get("effect") or {}
        kind = effect.get("kind", "")
        if kind in BUFF_KINDS:
            # Already running on the caster? Then the ability's only
            # effect right now would be a discounted duplicate.
            if any(m.source == ability["name"] for m in actor.modifiers):
                return False
        if kind in HEAL_KINDS:
            hurt = [m for m in party if m.is_alive()
                    and m.current_hp < m.max_hp * 0.85]
            if not hurt:
                return False
        return True

    def fight(party, enemy_list, rng):
        # `rng` is passed to the Battle, not just used for ability picks.
        # Without it Battle falls back to random.Random() seeded from OS
        # entropy, so every crit, every debuff roll and every enemy intent
        # in the entire benchmark was unseeded -- two runs of the SAME
        # build differed by 10 points of clear rate, which is larger than
        # most of the balance changes being measured.
        battle = Battle(party, enemy_list, rng=rng)
        for _ in range(600):
            if battle.is_over():
                break
            actor = battle.current_actor()
            if actor is None:
                break
            if actor in battle.enemies:
                battle.take_enemy_turn()
                continue
            ultimate = actor.ultimate_ability
            if actor.ultimate_ready() and (ultimate is None
                                           or worth_casting(actor, ultimate, party)):
                battle.take_party_action("ultimate")
                continue
            ready = [a for a in actor.active_abilities
                     if actor.ability_ready(a) and worth_casting(actor, a, party)]
            if ready and rng.random() < 0.85:
                battle.take_party_action("ability", ability_id=rng.choice(ready)["id"])
            else:
                battle.take_party_action("attack")
        return battle.result == "won"

    def stage_of(floor):
        return ("early" if floor < NUM_FLOORS / 3
                else "mid" if floor < 2 * NUM_FLOORS / 3 else "late")

    def run(region, comp, seed):
        """One full expedition. Returns (cleared, hp_fraction_at_end)."""
        rng = random.Random(seed)
        difficulty = REGION_DIFFICULTY[region]
        level, rarity_name, gear_level = REGION_PROFILE[region]
        rarity = getattr(Rarity, rarity_name)

        members = build_squad(comp, level, seed)
        item_level = max(1, min(gear_level, upgrade_level_cap(rarity)))
        equipped = {m.id: kit(rarity, item_level) for m in members}
        party = build_party_combatants(members, equipped)

        for floor in range(NUM_FLOORS):
            if floor == NUM_FLOORS - 2:
                for m in party:
                    m.current_hp = min(m.max_hp, m.current_hp
                                       + max(1, round(m.max_hp * CAMPFIRE_REST_PERCENT / 100)))
                continue
            if floor == NUM_FLOORS - 1:
                room = RoomType.BOSS
            else:
                weights = ROOM_WEIGHTS_BY_STAGE[stage_of(floor)]
                room = rng.choices(list(weights.keys()),
                                   weights=list(weights.values()), k=1)[0]
            if room not in (RoomType.COMBAT, RoomType.ELITE, RoomType.BOSS):
                continue
            role = {RoomType.COMBAT: "combat", RoomType.ELITE: "elite",
                    RoomType.BOSS: "boss"}[room]
            templates = catalog.get_templates_by_role(role, region=region) or []
            if not templates:
                continue
            offset = (difficulty["combat_level_offset"] if room == RoomType.COMBAT
                      else difficulty["level_offset"])
            squad_weights = (difficulty["combat_squad_weights"] if room == RoomType.COMBAT
                             else difficulty["elite_squad_weights"])
            count = rng.choices(list(squad_weights.keys()),
                                weights=list(squad_weights.values()), k=1)[0]
            enemy_list = [build_enemy_combatant(rng.choice(templates), floor // 10 + 1 + offset)
                          for _ in range(count)]
            if not fight(party, enemy_list, rng):
                return False, 0.0
            for m in party:
                if m.current_hp <= 0:
                    m.current_hp = 1

        total = sum(m.max_hp for m in party) or 1
        return True, sum(max(0, m.current_hp) for m in party) / total

    regions = [args.region] if args.region else list(REGION_PROFILE)
    regions = [r for r in ordered_regions() if r in regions]

    # ---- resumable cache -------------------------------------------
    # Two numbers per cell, because clear rate ALONE is blind in the
    # regions the player says are already correct: at Glacier every comp
    # clears 100% of the time, so a change there registers as no change
    # at all right up until it registers as a catastrophe. Average party
    # HP at the end of a cleared run is the continuous version of the
    # same question -- it moves smoothly, so it can show that a change
    # left the early game alone (or didn't).
    results: dict[str, dict[str, float]] = {}
    health: dict[str, dict[str, float]] = {}
    if args.cache and os.path.exists(args.cache):
        for line in open(args.cache):
            parts = line.rstrip("\n").split("\t")
            if len(parts) != 5 or int(parts[2]) != args.runs:
                continue
            results.setdefault(parts[0], {})[parts[1]] = float(parts[3])
            health.setdefault(parts[0], {})[parts[1]] = float(parts[4])

    started = time.time()
    ran_out = False
    for label, comp in COMPS.items():
        for region in regions:
            if results.get(label, {}).get(region) is not None:
                continue
            if args.budget and time.time() - started > args.budget:
                ran_out = True
                break
            outcomes = [run(region, comp, seed) for seed in range(args.runs)]
            rate = sum(1 for ok, _ in outcomes if ok) / args.runs
            # Averaged over EVERY run, with a wipe counting as 0 -- not
            # over cleared runs only. Averaging over survivors is a
            # survivorship bias that inverts the metric: a comp that
            # clears twice in twenty runs, barely, reads as "97% HP
            # left" and outranks a comp that clears every time at 80%.
            hp_left = sum(hp for _, hp in outcomes) / args.runs
            results.setdefault(label, {})[region] = rate
            health.setdefault(label, {})[region] = hp_left
            if args.cache:
                with open(args.cache, "a") as handle:
                    handle.write(f"{label}\t{region}\t{args.runs}\t{rate}\t{hp_left}\n")
        if ran_out:
            break

    print(f"FULL-RUN clear rate by ROLE SPLIT ({args.runs} runs/comp, gear modelled)")
    print("target: '1 of each' should be at or near the top of every column\n")

    print("each cell: clear rate (avg party HP left, wipes counted as 0)\n")
    header = f"{'comp':<20}" + "".join(f"{r.split()[0][:11]:>15}" for r in regions)
    print(header)
    print("-" * len(header))
    for label in COMPS:
        row = ""
        for region in regions:
            if results.get(label, {}).get(region) is None:
                row += f"{'--':>15}"
            else:
                row += f"{results[label][region]:>8.0%} ({health[label][region]:>3.0%})"
        print(f"{label:<20}{row}")

    # SCORE, not clear rate, decides the winner. Clear rate saturates --
    # eight comps all reading 100% in the first three regions says
    # nothing about which of them is stronger, and a balance pass judged
    # on a saturated metric will happily wreck the early game while the
    # number sits still. Adding HP-left breaks the tie in the direction
    # that matches how the region actually feels to play.
    print()
    for region in regions:
        have = {label: byregion[region] for label, byregion in results.items()
                if byregion.get(region) is not None}
        if "1 of each" not in have or len(have) < len(COMPS):
            print(f"{region:<18} incomplete ({len(have)}/{len(COMPS)} comps)")
            continue
        score = {label: have[label] + health[label][region] for label in have}
        best_label = max(score, key=lambda k: score[k])
        gap = score[best_label] - score["1 of each"]
        verdict = "OK" if gap <= 0.05 else "OFF-TARGET"
        print(f"{region:<18} best={best_label:<18} score {score[best_label]:>4.2f}   "
              f"1-of-each {score['1 of each']:>4.2f}   [{verdict}]")

    if ran_out:
        print("\n(time budget hit -- re-run with the same --cache to continue)")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, ".")
    sys.exit(main())
