"""
Every enemy has an identity glyph, and the glyphs are actually varied.

    python -m tools.check_enemy_emoji

THE FAILURE THIS EXISTS FOR IS NOT A MISSING EMOJI. A missing one falls
back by role and renders fine. The real failure is the one nobody
notices: reaching for the obvious glyph over and over until a hundred and
forty enemies are 🤖 and the column that was supposed to make a fight
scannable is a vertical stripe of the same picture. That degrades
silently, looks deliberate, and no other check has any opinion about it.

So coverage is asserted (cheap, and catches a new template that forgot
one), and so is DIVERSITY -- a floor on distinct glyphs, and a ceiling on
how much of the roster any single glyph may claim.

ALSO ASSERTED

  * bosses do not share a glyph with their own escorts. A boss group
    renders as one line per body, and if the boss and its four minions
    are all the same picture, the line that matters is camouflaged by
    the lines that do not.
  * the glyph survives a save/load round trip. It is carried on the
    Combatant rather than looked up at render time, which is the right
    call for restored battles and is also exactly how it could silently
    become empty for everyone mid-fight.
  * every mapped name is a real enemy. A typo'd key is a glyph that
    never appears and a template that quietly falls back forever.
"""

from __future__ import annotations

import os
import sys
import tempfile
from collections import Counter

# At least this many distinct glyphs across the roster. Set well below
# what the map currently achieves so it is a floor, not a target -- the
# point is to catch collapse toward one glyph, not to force novelty.
MIN_DISTINCT_GLYPHS = 60

# No single glyph may cover more than this share of all templates.
# Shared glyphs are DELIBERATE here (every medic is 💉), so this is
# generous; it exists to catch "everything is a robot", not to punish
# the mechanic-first grouping that makes the map useful.
MAX_SHARE_PER_GLYPH = 0.08


def main() -> int:
    sys.path.insert(0, ".")
    os.environ.setdefault(
        "DATABASE_URL", "sqlite:///" + tempfile.mktemp(suffix=".db"))

    from bot.database.db_init import init_db
    init_db()
    from bot.game.combat import enemies as E
    from bot.game.combat.enemies_emoji import ENEMY_EMOJI, ROLE_FALLBACK, emoji_for
    from bot.game.combat.factory import build_enemy_combatant
    from bot.game.combat.serialization import combatant_from_dict, combatant_to_dict
    from bot.utils import names

    failures: list[str] = []
    templates = E.ENEMY_TEMPLATES

    # ---- 1. coverage --------------------------------------------------
    missing = [t["name"] for t in templates if t["name"] not in ENEMY_EMOJI]
    if missing:
        failures.append(
            f"{len(missing)} enemy template(s) have no authored emoji and would "
            f"fall back to a role glyph: {sorted(missing)[:8]}"
            + (" ..." if len(missing) > 8 else ""))

    # ---- 2. no dead keys ---------------------------------------------
    real = {t["name"] for t in templates}
    ghosts = sorted(set(ENEMY_EMOJI) - real)
    if ghosts:
        failures.append(
            f"{len(ghosts)} emoji key(s) name no enemy that exists -- a typo here "
            f"is a template silently falling back forever: {ghosts[:8]}")

    # ---- 3. diversity -------------------------------------------------
    used = Counter(emoji_for(t["name"], t.get("role", "combat")) for t in templates)
    if len(used) < MIN_DISTINCT_GLYPHS:
        failures.append(
            f"only {len(used)} distinct glyphs across {len(templates)} enemies "
            f"(floor {MIN_DISTINCT_GLYPHS}) -- the column stops distinguishing "
            f"anything once they converge")

    ceiling = max(2, int(len(templates) * MAX_SHARE_PER_GLYPH))
    hogs = [(glyph, count) for glyph, count in used.items() if count > ceiling]
    for glyph, count in sorted(hogs, key=lambda pair: -pair[1]):
        failures.append(
            f"{glyph} is used by {count} enemies, over the {ceiling} allowed "
            f"({MAX_SHARE_PER_GLYPH:.0%} of the roster) -- shared glyphs are fine "
            f"in small groups, but this one has stopped meaning anything")

    # ---- 4. a boss does not look like its own escorts ------------------
    for boss in templates:
        escorts = boss.get("escorts") or []
        if not escorts:
            continue
        boss_glyph = emoji_for(boss["name"], "boss")
        clashing = [e for e in escorts
                    if emoji_for(e, "boss_group_member") == boss_glyph]
        if clashing:
            failures.append(
                f"'{boss['name']}' shares its glyph {boss_glyph} with its own "
                f"escort(s) {clashing} -- the boss line is camouflaged by the "
                f"minion lines in the one fight where telling them apart matters")

    for group, members in E.BOSS_GROUPS.items():
        glyphs = [emoji_for(m, "boss_group_member") for m in members]
        if len(set(glyphs)) == 1 and len(members) > 1:
            failures.append(
                f"every member of boss group '{group}' uses {glyphs[0]} -- the "
                f"whole encounter renders as one repeated picture")

    # ---- 5. it survives the round trip --------------------------------
    #
    # The glyph is stored on the Combatant, not looked up at render time.
    # That is right for restored battles and is also the exact mechanism
    # by which it could come back empty for everybody after a reload.
    sample = build_enemy_combatant(E.get_template_by_name("Void Hydra"), 30)
    if not sample.emoji:
        failures.append("a freshly built enemy has no emoji on its Combatant")
    restored = combatant_from_dict(combatant_to_dict(sample))
    if restored.emoji != sample.emoji:
        failures.append(
            f"the emoji does not survive serialization: {sample.emoji!r} became "
            f"{restored.emoji!r} -- every reloaded battle would lose them")
    if sample.emoji not in names.display_name(sample):
        failures.append("display_name does not show the emoji")

    # ---- 6. party members are NOT prefixed -----------------------------
    from bot.game.combat.combatant import Combatant

    ally = Combatant(name="Josh", is_player=True, base_stats={}, current_hp=1, max_hp=1)
    if names.display_name(ally).strip().startswith(("👾", "🔱", "👑")):
        failures.append(
            "a party member is being given an enemy glyph -- the prefix stops "
            "meaning 'this is an enemy' the moment allies have one too")

    print(f"templates : {len(templates)}")
    print(f"authored  : {len(ENEMY_EMOJI)} names mapped, "
          f"{len(ROLE_FALLBACK)} role fallbacks")
    print(f"distinct  : {len(used)} glyphs (floor {MIN_DISTINCT_GLYPHS})")
    print("busiest   : " + ", ".join(
        f"{glyph}x{count}" for glyph, count in used.most_common(6))
        + f"   (ceiling {ceiling})")

    if failures:
        print()
        for failure in dict.fromkeys(failures):
            print(f"  FAIL  {failure}")
        return 1
    print("\nOK -- every enemy has a glyph, the glyphs are varied, and bosses "
          "do not look like their own minions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
