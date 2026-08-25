"""
Evolution never lets a character overtake one born at its rank.

    python -m tools.check_character_evolution

THE ONE RULE THIS PROTECTS. A native 5-star has to stay the strongest
thing a player can own. The gacha is the game's whole acquisition loop,
5-stars are what it sells, and an evolution system that quietly matched
or beat them would make the rarest pulls pointless -- not immediately,
but on the day somebody works out the maths and posts it.

It is a numbers rule, so it is checked with numbers rather than trusted
to a comment.

WHAT IS ASSERTED, AND AGAINST WHAT. The assertion is on the STAR
BASELINES, not on individual characters, and the distinction was learned
the hard way.

The first version compared real templates stat by stat and reported 26
failures -- a 3-star out-scaling a 5-star on `elemental` at every level.
That looked exactly like evolution breaking the rarity ladder. It was
not. Arkiver, a 3-star DPS, is authored with base_elemental 9 and growth
0.6; Josh, the 5-star DPS, has 8 and 0.4. The 3-star already beat the
5-star on that stat before evolution existed, because Arkiver is an
elemental specialist and that is a deliberate piece of design.

So a per-character, per-stat ladder is a property this game HAS NEVER
HAD and should not be asserted. What must hold is the system property:

    the bonus evolution grants is smaller than the gap between the star
    baselines it spans

That is what guarantees evolution cannot erase a rarity tier, and it
stays true no matter how any individual character is authored. On top of
it, characters are compared on TOTAL power rather than stat by stat --
specialists are allowed to beat their betters at the one thing they
specialise in, and are not allowed to be better overall.

Pre-existing native inversions are REPORTED rather than failed. They are
not evolution's doing and silencing them entirely would hide real
content bugs if one ever appears.
"""

from __future__ import annotations

import os
import sys
import tempfile


def main() -> int:
    sys.path.insert(0, ".")
    os.environ.setdefault(
        "DATABASE_URL", "sqlite:///" + tempfile.mktemp(suffix=".db"))
    import bot.config as cfg
    cfg.DATABASE_URL = os.environ["DATABASE_URL"]

    from bot.database.db_init import init_db
    init_db()
    from bot.database.session import SessionLocal
    from bot.database.models.character_model import CharacterTemplate, PlayerCharacter
    from bot.database.models.enums import CharacterClass
    from bot.game.combat.factory import base_character_stats
    from bot.game.economy import character_evolution_config as evo
    from bot.services import character_template_service, player_service

    db = SessionLocal()
    character_template_service.ensure_character_templates_seeded(db)
    player = player_service.get_or_create_player(db, 95_001, "EvoCheck")

    failures: list[str] = []

    def template(star: int, cls) -> CharacterTemplate | None:
        return (db.query(CharacterTemplate)
                .filter_by(star_rating=star, character_class=cls,
                           is_player_avatar=False)
                .first())

    def power(tmpl, stage: int, level: int) -> dict:
        character = PlayerCharacter(
            player_id=player.id, template_id=tmpl.id,
            level=level, evolution_stage=stage)
        character.template = tmpl
        character.talents = []
        return base_character_stats(character)

    STATS = ("attack", "max_hp", "defense", "elemental")
    LEVELS = (1, 25, 50, 70, 90, 100)
    compared = 0
    classes_checked = 0
    notes: list[str] = []

    # ---- 1. THE SYSTEM PROPERTY, on the star baselines ---------------
    #
    # Independent of how any character is authored: the bonus evolution
    # grants must be smaller than the baseline gap it spans. If this
    # holds, evolution cannot promote a character past the tier above it
    # for any character built on these baselines.
    from bot.game.characters.character_seed_data import _BASELINE_BY_STAR

    def baseline_at(star: int, key: str, level: int) -> float:
        block = _BASELINE_BY_STAR[star]
        return block[f"base_{key}"] + block[f"growth_{key}"] * (level - 1)

    BASELINE_KEYS = ("hp", "attack", "defense", "elemental", "speed")
    for level in LEVELS:
        for key in BASELINE_KEYS:
            for native, stages, target in ((3, 1, 4), (3, 2, 5), (4, 1, 5)):
                compared += 1
                evolved = baseline_at(native, key, level) * (
                    1 + evo.stage_percent(stages) / 100)
                genuine = baseline_at(target, key, level)
                if evolved >= genuine:
                    failures.append(
                        f"baseline L{level} {key}: a {native}★ evolved to "
                        f"{target}★ reaches {evolved:.1f}, at or above a native "
                        f"{target}★ at {genuine:.1f} -- the bonus is bigger "
                        f"than the rarity gap it spans")

    # ---- 2. REAL CHARACTERS, compared on TOTAL power -----------------
    for cls in CharacterClass:
        three, four, five = (template(s, cls) for s in (3, 4, 5))
        if not all((three, four, five)):
            continue
        classes_checked += 1

        for level in LEVELS:
            def total(tmpl, stage):
                stats = power(tmpl, stage, level)
                return sum(stats[s] for s in STATS)

            cases = [
                ("3★ evolved to 4★", total(three, 1), "native 4★", total(four, 0)),
                ("3★ evolved to 5★", total(three, 2), "native 5★", total(five, 0)),
                ("4★ evolved to 5★", total(four, 1), "native 5★", total(five, 0)),
            ]
            for lower_label, lower, upper_label, upper in cases:
                compared += 1
                if lower >= upper:
                    failures.append(
                        f"{cls.value} L{level} TOTAL: {lower_label} "
                        f"({lower:.0f}) is NOT below {upper_label} "
                        f"({upper:.0f}) -- evolution overtook a native rank")

            # Evolution has to actually do something.
            for tmpl, label in ((three, "3★"), (four, "4★")):
                compared += 1
                if total(tmpl, 1) <= total(tmpl, 0):
                    failures.append(
                        f"{cls.value} L{level}: evolving a {label} changed "
                        f"nothing ({total(tmpl, 0):.0f})")

        # ---- 3. Pre-existing native inversions: REPORTED -------------
        for stat in STATS:
            for lower_star, upper_star, low, high in (
                    (3, 4, three, four), (4, 5, four, five), (3, 5, three, five)):
                if power(low, 0, 90)[stat] > power(high, 0, 90)[stat]:
                    notes.append(
                        f"{cls.value}: native {lower_star}★ {low.name} beats "
                        f"native {upper_star}★ {high.name} on {stat} "
                        f"(authored specialisation, not evolution)")

    # The avatar must be excluded -- it is a free 5-star everyone owns.
    from bot.services import evolution_service
    avatar_template = (db.query(CharacterTemplate)
                       .filter_by(is_player_avatar=True).first())
    if avatar_template is not None:
        avatar = PlayerCharacter(player_id=player.id,
                                 template_id=avatar_template.id, level=100)
        avatar.template = avatar_template
        avatar.talents = []
        allowed, _ = evolution_service.can_evolve(avatar)
        if allowed:
            failures.append(
                "the player's own avatar can be evolved -- it is a free 5★ "
                "that every player owns and has nothing to evolve toward")

    # Cost sanity: evolving all the way must cost fewer echoes than simply
    # buying a native 5-star, since the result is weaker.
    from bot.game.economy.resonance_config import ECHO_COST_BY_STAR
    echo_total = sum(r["cost"].get("echoes", 0) for r in evo.REQUIREMENTS.values())
    native_price = ECHO_COST_BY_STAR[5]
    if echo_total >= native_price:
        failures.append(
            f"evolving 3★ to 5★ costs {echo_total:,} echoes but a NATIVE 5★ "
            f"costs {native_price:,} at the exchange -- paying more for the "
            f"weaker result is a trap")

    db.close()

    print(f"classes    : {classes_checked} with a full 3/4/5 set")
    print(f"comparisons: {compared} across 6 levels and {len(STATS)} stats")
    print(f"stages     : +{evo.PERCENT_PER_STAGE:g}%/stage "
          f"(2 stages = +{evo.stage_percent(2):.1f}%)")
    print(f"echoes     : {echo_total:,} to evolve 3★→5★ vs "
          f"{native_price:,} to buy a native 5★")

    if notes:
        print("\nnative roster inversions (pre-existing, not caused by evolution):")
        for note in sorted(set(notes)):
            print(f"  note  {note}")

    if failures:
        print()
        for failure in sorted(set(failures))[:20]:
            print(f"  FAIL  {failure}")
        if len(set(failures)) > 20:
            print(f"  ... and {len(set(failures)) - 20} more")
        return 1
    print("\nOK -- evolution is an upgrade, and never overtakes a native rank.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
