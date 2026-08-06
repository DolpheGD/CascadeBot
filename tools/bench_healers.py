"""
Is a dedicated healer actually required?

    python -m tools.bench_healers

The reported problem: players drop Sustains for healing GEAR, because
enemies don't hit hard enough to need a real healer and the healer's own
output was too small to notice.

So this measures survival, not damage: the same carry and the same two
supports, with the fourth slot being either a dedicated Sustain or
another damage character. If "no healer" survives about as often as
"healer", the class is optional and players are right to drop it.
"""

from __future__ import annotations

import random
import sys


def main() -> int:
    import os, tempfile
    os.environ.setdefault("DATABASE_URL", "sqlite:///" + tempfile.mktemp(suffix=".db"))
    from sqlalchemy.orm import sessionmaker

    from bot.database.db import engine
    from bot.database.db_init import init_db
    from bot.database.models.character_model import CharacterTemplate, PlayerCharacter
    from bot.game.combat.battle import Battle
    from bot.game.combat.enemies import get_template_by_name
    from bot.game.combat.factory import build_enemy_combatant, build_party_combatants
    from bot.services import character_template_service

    init_db()
    db = sessionmaker(bind=engine)()
    character_template_service.ensure_character_templates_seeded(db)
    db.commit()
    by_name = {t.name: t for t in db.query(CharacterTemplate).all()}

    def pc(t, level=70):
        r = PlayerCharacter(player_id=1, template_id=t.id, level=level, dupe_count=0)
        r.template = t; r.current_hp = None
        return r

    # "Sustain" means healer OR shielder -- both are the class, and both
    # have to be worth a slot. Jofrog and Bee Jee are the shielders.
    SQUADS = {
        "NO sustain":       ["Josh", "Caandy", "Caliper", "Aizer"],
        "Lily (max HP)":    ["Josh", "Caandy", "Caliper", "Lily Lovelace"],
        "Aura (ELE)":       ["Josh", "Caandy", "Caliper", "Aura"],
        "Refender (DEF)":   ["Josh", "Caandy", "Caliper", "Refender"],
        "Evz (percent)":    ["Josh", "Caandy", "Caliper", "Evz"],
        "Kotori (blood)":   ["Josh", "Caandy", "Caliper", "Kotori"],
        "Jofrog (shield)":  ["Josh", "Caandy", "Caliper", "Jofrog"],
        "Bee Jee (shield)": ["Josh", "Caandy", "Caliper", "Bee Jee"],
    }

    def survive(names, enemy, level, seed, atk_mult=1.0, hp_mult=1.0):
        rng = random.Random(seed)
        party = build_party_combatants([pc(by_name[n]) for n in names if n in by_name], {})
        foes = []
        for _ in range(3):
            f = build_enemy_combatant(get_template_by_name(enemy), level)
            # Applied to the BUILT combatant so the sweep changes only the
            # two axes being tested, not the template everything shares.
            f.base_stats["attack"] = f.base_stats["attack"] * atk_mult
            f.max_hp = f.current_hp = int(f.max_hp * hp_mult)
            foes.append(f)
        b = Battle(party, foes)
        for _ in range(400):
            if b.is_over():
                break
            a = b.current_actor()
            if a is None:
                break
            if a in b.enemies:
                b.take_enemy_turn(); continue
            if a.ultimate_ready():
                b.take_party_action("ultimate")
            else:
                ready = [x for x in a.active_abilities if a.ability_ready(x)]
                if ready and rng.random() < 0.7:
                    b.take_party_action("ability", ability_id=rng.choice(ready)["id"])
                else:
                    b.take_party_action("attack")
        return b.result == "won"

    ENEMY, LEVEL = "Xender Tank", 16

    # SWEEP FIRST. The point is to find a shape where Sustain MATTERS --
    # a band where no-sustain loses and sustain wins. Enemy damage was a
    # cliff (100% survival at lv14, 0% at lv20), so there was no such
    # band at any level and the class was correctly droppable.
    print(f"Sustain lift sweep -- 3x {ENEMY} lv{LEVEL}")
    print("(lift = best Sustain squad win% minus NO-sustain win%)\n")
    print(f"{'atk x':>7}{'hp x':>7}{'no-sustain':>13}{'best sustain':>15}{'lift':>8}")
    best_shape = None
    for atk in (1.0, 1.5, 2.0, 2.5):
        for hp in (1.0, 2.0, 3.5):
            base = sum(survive(SQUADS["NO sustain"], ENEMY, LEVEL, s, atk, hp)
                       for s in range(24)) / 24
            best = 0.0
            for label, names in SQUADS.items():
                if label == "NO sustain":
                    continue
                w = sum(survive(names, ENEMY, LEVEL, s, atk, hp) for s in range(24)) / 24
                best = max(best, w)
            lift = best - base
            print(f"{atk:>7.1f}{hp:>7.1f}{base:>12.0%}{best:>15.0%}{lift:>+8.0%}")
            if best_shape is None or lift > best_shape[0]:
                best_shape = (lift, atk, hp)

    lift, atk, hp = best_shape
    print(f"\nbiggest Sustain lift: {lift:+.0%} at attack x{atk}, HP x{hp}\n")
    print(f"{'squad':<18}{'win%':>8}   (at that shape)")
    for label, names in SQUADS.items():
        w = sum(survive(names, ENEMY, LEVEL, s, atk, hp) for s in range(30)) / 30
        print(f"{label:<18}{w:>8.0%}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, ".")
    sys.exit(main())
