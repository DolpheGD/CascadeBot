"""
Verify every relic measurably changes a battle.

    python -m tools.check_relics

A relic is the easiest thing in the game to get wrong invisibly. It has a
name, an emoji, a rarity and a description; it appears in the offer, the
player takes it, it shows in their relic list, and if its effect uses a
`kind` that relic_service.apply_relic_effects does not handle, it does
absolutely nothing for the rest of the run. Nothing logs. Nothing fails.
The player just has a worse run than they think they're having.

The card system had exactly this bug -- two cards whose abilities went
into a list nothing read -- and it was found by measuring, not by
reading. So each relic here is APPLIED to a real squad through the real
applier, and the before/after state is compared:

  1. IT CHANGES SOMETHING. Stats moved, a passive was granted, poise
     damage went up, or the gold multiplier moved. A relic that changes
     nothing fails, and the failure names the effect kind so the cause is
     obvious.

  2. ITS EFFECT KIND IS ONE THE APPLIER HANDLES. Checked directly against
     the branches in apply_relic_effects, so a typo'd kind is caught even
     if some other part of the same multi-effect happens to work.

  3. PASSIVES EXIST. A relic pointing at a renamed passive is caught here
     rather than logged at runtime and shrugged off.

  4. CURSED RELICS ACTUALLY COST SOMETHING. A "cursed" relic with no
     downside is a free legendary with scary flavour text.

  5. THE OFFER IS SANE: every rarity can actually be rolled, ids are
     unique, and descriptions exist.
"""

from __future__ import annotations

import random
import sys


def main() -> int:
    sys.path.insert(0, ".")

    from bot.game.combat.combatant import Combatant
    from bot.game.dungeon.relic_config import RARITY_WEIGHTS, RELICS, RELICS_BY_ID
    from bot.game.loot.abilities import ARMOR_PASSIVES
    from bot.services import relic_service

    failures: list[str] = []
    HANDLED = {"stat", "stat_flat", "passive", "poise_damage", "gold_multiplier",
               "multi"}
    passive_ids = {a["id"] for a in ARMOR_PASSIVES}

    def fresh_squad():
        squad = []
        for i in range(4):
            member = Combatant(
                name=f"P{i}", is_player=True,
                base_stats={"attack": 100.0, "defense": 100.0, "elemental": 100.0,
                            "speed": 100.0, "max_hp": 1000.0, "max_mana": 100.0,
                            "crit_rate": 10.0, "crit_damage": 100.0,
                            "recharge": 20.0},
                current_hp=1000, max_hp=1000, character_id=i + 1, level=40,
            )
            squad.append(member)
        return squad

    class FakeExpedition:
        """Just enough of an Expedition for relic_service to read.

        `relics` is the attribute held_ids actually reads -- the ledger's
        own relic list is a display copy. Getting this wrong made the
        first run of this check report every relic as doing nothing,
        which is worth recording: a harness that under-reports is
        indistinguishable from the bug it is looking for.
        """
        def __init__(self, relic_ids):
            self.relics = list(relic_ids)
            self.ledger = {"relics": list(relic_ids)}

    def snapshot(squad):
        return [
            (dict(c.base_stats), sorted(p["id"] for p in c.passive_abilities),
             getattr(c, "bonus_poise_damage", 0))
            for c in squad
        ]

    changed_by_kind: dict[str, int] = {}
    for relic in RELICS:
        where = f"relic '{relic['id']}'"
        if not relic.get("description", "").strip():
            failures.append(f"{where}: no description")
        if relic.get("rarity") not in RARITY_WEIGHTS:
            failures.append(f"{where}: rarity {relic.get('rarity')!r} can never be rolled")

        parts = relic_service._flatten(relic["effect"])
        for part in parts:
            kind = part.get("kind")
            if kind not in HANDLED:
                failures.append(
                    f"{where}: effect kind {kind!r} is not handled by "
                    f"relic_service.apply_relic_effects -- taking this relic would "
                    f"do nothing")
            if kind == "passive" and part.get("passive_id") not in passive_ids:
                failures.append(
                    f"{where}: passive {part.get('passive_id')!r} does not exist in "
                    f"ARMOR_PASSIVES")
            changed_by_kind[kind] = changed_by_kind.get(kind, 0) + 1

        # ---- 1: measured effect on a real squad ----
        squad = fresh_squad()
        before = snapshot(squad)
        expedition = FakeExpedition([relic["id"]])
        relic_service.apply_relic_effects(expedition, squad)
        after = snapshot(squad)
        gold = relic_service.gold_multiplier(expedition)

        if before == after and abs(gold - 1.0) < 1e-9:
            failures.append(
                f"{where}: applying it changed NOTHING -- no stat moved, no passive "
                f"was granted, no poise bonus, no gold multiplier")

        # ---- 4: cursed relics must have a downside ----
        if relic.get("rarity") == "cursed":
            worse = any(
                after[i][0][stat] < before[i][0][stat] - 1e-9
                for i in range(len(squad)) for stat in before[i][0]
            )
            if not worse:
                failures.append(
                    f"{where}: marked cursed but no stat got worse -- that is a free "
                    f"legendary wearing a warning label")

    # ---- 5: ids unique ----
    ids = [r["id"] for r in RELICS]
    for relic_id in {i for i in ids if ids.count(i) > 1}:
        failures.append(f"duplicate relic id {relic_id!r}")
    if len(RELICS_BY_ID) != len(RELICS):
        failures.append("RELICS_BY_ID lost entries -- ids collide")

    # ---- offers actually reach every rarity ----
    seen_rarities: set[str] = set()
    rng = random.Random(11)
    for _ in range(400):
        for relic in relic_service.offer_relics(FakeExpedition([]), rng=rng):
            seen_rarities.add(relic["rarity"])
    missing = set(RARITY_WEIGHTS) - seen_rarities
    if missing:
        failures.append(
            f"rarities {sorted(missing)} never appeared in 400 offers -- they are "
            f"configured and unreachable")

    import collections
    by_rarity = collections.Counter(r["rarity"] for r in RELICS)
    print(f"relics     : {len(RELICS)} "
          f"({', '.join(f'{n} {r}' for r, n in sorted(by_rarity.items()))})")
    print(f"effects    : {sum(changed_by_kind.values())} parts, "
          f"kinds {sorted(k for k in changed_by_kind if k != 'multi')}")
    print(f"passives   : {len({p.get('passive_id') for r in RELICS for p in relic_service._flatten(r['effect']) if p.get('passive_id')})} "
          f"distinct armour passives reachable through relics")

    if failures:
        print()
        for failure in failures:
            print(f"  FAIL  {failure}")
        return 1
    print("\nOK -- every relic measurably changes a battle, and every curse costs "
          "something.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
