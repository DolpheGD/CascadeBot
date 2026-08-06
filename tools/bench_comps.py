"""
Squad ARCHETYPE benchmark.

    python -m tools.bench_comps

bench_dps.py answers "which carry is strongest". This answers the more
important question: **which strategy is worth playing at all.**

Every comp gets the same carry slot and the same target; only the three
support slots change. If one column wins by a mile, the game has one
strategy and the rest of the roster is decoration.
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

    def pc(t, level=80):
        row = PlayerCharacter(player_id=1, template_id=t.id, level=level, dupe_count=0)
        row.template = t; row.current_hp = None
        return row

    # Named comps. The carry is FIXED so the only variable is support.
    COMPS = {
        "crit/ATK stack": ["Star", "Caandy", "Dolphe", "Chary"],
        "DoT team":       ["Star", "Blueflame", "Nyrvite", "Sader Vorae"],
        "break team":     ["Star", "Nyrvite", "Sader Vorae", "Caliper"],
        "support DPS x3": ["Star", "Caliper", "Andy", "Slikrz"],
        "DEF shred":      ["Star", "Sader Vorae", "Arkiver", "Caandy"],
        "no support":     ["Star", "Josh", "Aizer", "Gostley"],
    }

    def run(names, seed):
        rng = random.Random(seed)
        squad = [pc(by_name[n]) for n in names if n in by_name]
        party = build_party_combatants(squad, {})
        dummy = build_enemy_combatant(get_template_by_name("Eris Sentinel"), 60)
        dummy.max_hp = dummy.current_hp = 50_000_000
        dummy.base_stats["attack"] = 0
        battle = Battle(party, [dummy])
        start = dummy.current_hp
        for _ in range(160):
            if battle.is_over():
                break
            actor = battle.current_actor()
            if actor is None:
                break
            if actor in battle.enemies:
                battle.take_enemy_turn()
                for m in party:
                    m.current_hp = m.max_hp
                continue
            if actor.ultimate_ready():
                battle.take_party_action("ultimate")
            else:
                ready = [a for a in actor.active_abilities if actor.ability_ready(a)]
                if ready and rng.random() < 0.75:
                    battle.take_party_action("ability", ability_id=rng.choice(ready)["id"])
                else:
                    battle.take_party_action("attack")
            for m in party:
                m.current_hp = m.max_hp
        return max(0, start - dummy.current_hp)

    rows = [(label, sum(run(names, s) for s in range(14)) // 14)
            for label, names in COMPS.items()]
    rows.sort(key=lambda r: -r[1])
    best = rows[0][1] or 1
    print(f"{'comp':<18}{'damage':>10}{'vs best':>10}")
    for label, dmg in rows:
        print(f"{label:<18}{dmg:>10,}{dmg / best:>9.0%}")
    spread = best / max(1, rows[-1][1])
    print(f"\ntop comp is {spread:.1f}x the bottom  ({rows[0][0]} vs {rows[-1][0]})")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, ".")
    sys.exit(main())
