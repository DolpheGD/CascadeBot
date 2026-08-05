"""
Damage benchmark for DPS-class characters.

    python -m tools.bench_dps

Every DPS is put in the SAME squad shell (one Amplifier, one Sustain, one
filler) against the same durable target, and the only thing that changes
between runs is which DPS is in the carry slot. Anything left over is
that character's contribution.

Two numbers, and the gap between them is the point:

    plain    a healthy target, nothing set up, no debuffs, full HP
    setup    the conditions a conditional kit wants -- target already
             debuffed, target below half HP, the DPS itself hurt

A well-designed roster should show conditional carries LOSING the plain
column and WINNING the setup column by a wide margin. A carry that tops
both is not a design, it's a default pick.
"""

from __future__ import annotations

import random
import sys


def main() -> int:
    import os
    import tempfile

    os.environ.setdefault("DATABASE_URL", "sqlite:///" + tempfile.mktemp(suffix=".db"))
    from sqlalchemy.orm import sessionmaker

    from bot.database.db import engine
    from bot.database.db_init import init_db
    from bot.database.models.character_model import CharacterTemplate, PlayerCharacter
    from bot.database.models.enums import CharacterClass
    from bot.game.combat.battle import Battle
    from bot.game.combat.enemies import get_template_by_name
    from bot.game.combat.factory import build_enemy_combatant, build_party_combatants
    from bot.services import character_template_service

    init_db()
    db = sessionmaker(bind=engine)()
    character_template_service.ensure_character_templates_seeded(db)
    db.commit()

    def pc(template, level=80):
        row = PlayerCharacter(player_id=1, template_id=template.id, level=level, dupe_count=0)
        row.template = template
        row.current_hp = None
        return row

    everyone = db.query(CharacterTemplate).filter_by(is_player_avatar=False).all()
    by_class = {c: [t for t in everyone if t.character_class == c] for c in CharacterClass}
    carries = by_class[CharacterClass.DPS]
    shell = [by_class[CharacterClass.AMPLIFIER][0],
             by_class[CharacterClass.SUSTAIN][0],
             by_class[CharacterClass.SUPPORT_DPS][0]]

    def run(carry, setup: bool, seed: int, dummies: int = 1) -> int:
        """One carry, one shell, one dummy. Returns damage dealt.

        The dummy is built DEFENCELESS and HARMLESS on purpose. An earlier
        version used a real boss and let it fight back, which produced two
        lies at once: its defence flattened every number into the low
        hundreds, and in the `setup` case the 40%-HP party simply wiped,
        ending the run early and scoring conditional carries BELOW their
        plain runs. A benchmark that punishes the thing it is measuring is
        worse than no benchmark.
        """
        rng = random.Random(seed)
        party = build_party_combatants([pc(carry)] + [pc(t) for t in shell], {})
        targets = []
        for _ in range(dummies):
            d = build_enemy_combatant(get_template_by_name("Eris Sentinel"), 60)
            d.max_hp = d.current_hp = 50_000_000
            d.base_stats["defense"] = 0
            d.base_stats["attack"] = 0
            d.max_poise = d.poise = 9_999   # never breaks; break is a separate axis
            targets.append(d)
        dummy = targets[0]
        battle = Battle(party, targets)

        hp_fraction = 0.35 if setup else 1.0
        if setup:
            from bot.game.combat.status import StatModifier
            # The conditions a conditional kit is written for.
            for t in targets:
                t.current_hp = int(t.max_hp * 0.40)
                t.modifiers.append(StatModifier("defense", -30, 999, "bench"))
                t.modifiers.append(StatModifier("attack", -30, 999, "bench"))

        def pin_party():
            for member in party:
                member.current_hp = max(1, int(member.max_hp * hp_fraction))

        pin_party()
        start = sum(t.current_hp for t in targets)
        for _ in range(160):
            if battle.is_over():
                break
            actor = battle.current_actor()
            if actor is None:
                break
            if actor in battle.enemies:
                battle.take_enemy_turn()
                pin_party()          # held at the tested HP, never allowed to die
                continue
            if actor.ultimate_ready():
                battle.take_party_action("ultimate")
            else:
                ready = [a for a in actor.active_abilities if actor.ability_ready(a)]
                if ready and rng.random() < 0.75:
                    battle.take_party_action("ability", ability_id=rng.choice(ready)["id"])
                else:
                    battle.take_party_action("attack")
            pin_party()
        return max(0, start - sum(t.current_hp for t in targets))

    rows = []
    for carry in carries:
        plain = sum(run(carry, False, s) for s in range(12)) // 12
        setup = sum(run(carry, True, s) for s in range(12)) // 12
        crowd = sum(run(carry, False, s, dummies=4) for s in range(12)) // 12
        rows.append((carry.name, carry.star_rating, plain, setup, crowd))

    rows.sort(key=lambda r: -r[2])
    best_plain = max(r[2] for r in rows) or 1
    print(f"{'carry':<14}{'★':>2}{'plain':>9}{'setup':>9}{'crowd':>9}"
          f"{'setup/plain':>13}{'crowd/plain':>13}")
    for name, stars, plain, setup, crowd in rows:
        sr = (setup / plain) if plain else 0
        cr = (crowd / plain) if plain else 0
        print(f"{name:<14}{stars:>2}{plain:>9,}{setup:>9,}{crowd:>9,}{sr:>12.2f}x{cr:>12.2f}x")

    spread = best_plain / max(1, min(r[2] for r in rows))
    print(f"\nplain-damage spread across the DPS roster: {spread:.1f}x "
          f"(top {rows[0][0]}, bottom {rows[-1][0]})")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, ".")
    sys.exit(main())
