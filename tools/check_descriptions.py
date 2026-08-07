"""
Assert that what an ability SAYS is what an ability DOES.

    python -m tools.check_descriptions

Every ability carries a hand-written description and a machine-read
effect dict. Nothing links them, so retuning a number changes the
behaviour and leaves the text describing the old one -- and the text is
the only thing the player ever sees.

This had drifted badly. Aura's skill read "cleanse all negative effects
and heal for 25% of their max HP" while actually healing 800% of Aura's
ELEMENTAL and cleansing nothing at all. Lily read 25% and healed 40%.
Kotori read "sacrifice 20%" and cost 10%. A player reading the roster to
choose a healer was reading fiction.

THE RULE: every percentage in a description must appear somewhere in
that ability's effect. That is deliberately one-directional -- an effect
key the text doesn't mention is fine (durations and chances are often
better left out of a one-line summary), but a NUMBER IN THE TEXT THAT
THE EFFECT DOESN'T CONTAIN is always either a lie or a stale edit.

It also checks that heals which scale off a STAT say which stat, since
"25% of max HP" and "800% of ELE" are wildly different promises and the
kind that scales off elemental was, at one point, described as the kind
that scales off max HP.
"""

from __future__ import annotations

import re
import sys

# Numbers in a description that are never effect magnitudes: turn counts
# read as bare integers, and the percent-of-HP thresholds that some
# descriptions phrase in words. Only used to explain a failure, never to
# excuse one.
PERCENT_IN_TEXT = re.compile(r"(\d+(?:\.\d+)?)\s*%")

# The multiplier form: "15.4x AURA's ELE" for an effect storing 1540.
#
# Effects that scale off a SMALL stat need enormous percentages -- ELE
# and DEF are a fraction of a health bar, so a heal worth half a bar is
# "1540% of ELE". That is arithmetically right and unreadable: the
# player's takeaway from four digits is "this number is broken", not
# "this is a strong heal". Percent is the wrong unit once it passes a
# few hundred, so those descriptions say 15.4x instead.
#
# Checked here in the same one-directional way as percentages, so the
# nicer unit doesn't become an excuse for the text to drift: whatever
# multiplier the description quotes, the effect must actually hold that
# number times 100.
MULTIPLIER_IN_TEXT = re.compile(r"(\d+(?:\.\d+)?)\s*[x×]\b")

# Above this, a percentage should be written as a multiplier instead.
# 300 is a genuine judgement call rather than a derived number: "300%
# ATK damage" is idiomatic for a big attack and reads fine, while
# "1540%" does not.
MULTIPLIER_THRESHOLD = 300

# Effect keys whose value is a percentage the player might see quoted.
def _effect_numbers(effect: dict) -> set[float]:
    out: set[float] = set()
    for key, value in (effect or {}).items():
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            # ABSOLUTE value: a debuff stored as -28 is correctly written
            # up as "reduce DEF by 28%".
            out.add(abs(float(value)))
            # A "damage 110 + bonus 105" pair is usually described as its
            # TOTAL ("or 200% if..."), so accept sums of the base with any
            # other numeric key.
    numbers = [v for v in (effect or {}).values()
               if isinstance(v, (int, float)) and not isinstance(v, bool)]
    for i, a in enumerate(numbers):
        for b in numbers[i + 1:]:
            out.add(abs(float(a + b)))
    return out


def _stat_word(stat: str) -> list[str]:
    return {
        "max_hp": ["max hp", "hp"],
        "elemental": ["ele", "elemental"],
        "defense": ["def", "defence", "defense"],
        "attack": ["atk", "attack"],
        "speed": ["spd", "speed"],
    }.get(stat, [stat])


def _check(label: str, ability: dict, failures: list[str]) -> None:
    description = ability.get("description") or ""
    effect = ability.get("effect") or {}
    if not description or not effect:
        return

    allowed = _effect_numbers(effect)
    for raw in PERCENT_IN_TEXT.findall(description):
        value = float(raw)
        if value not in allowed:
            failures.append(
                f"{label}: description says {raw}% but the effect has no such number "
                f"({', '.join(f'{k}={v}' for k, v in effect.items() if isinstance(v, (int, float)))})"
            )

    # Only for the stat-scaled family, which is the one that uses this
    # notation. Elsewhere "Nx" in English is a COUNT, not a magnitude --
    # "stacks up to 3x" means three stacks, and reading it as "300%"
    # produced the only false positives this check has ever raised.
    if "from_stat" in effect.get("kind", ""):
        for raw in MULTIPLIER_IN_TEXT.findall(description):
            value = round(float(raw) * 100, 6)
            if value not in allowed:
                failures.append(
                    f"{label}: description says {raw}x (i.e. {value:g}%) but the effect has no "
                    f"such number ({', '.join(f'{k}={v}' for k, v in effect.items() if isinstance(v, (int, float)))})"
                )

    # A heal that scales off a stat must not be quoted in four-digit
    # percentages -- see MULTIPLIER_THRESHOLD.
    if "from_stat" in effect.get("kind", ""):
        for raw in PERCENT_IN_TEXT.findall(description):
            if float(raw) >= MULTIPLIER_THRESHOLD:
                failures.append(
                    f"{label}: quotes {raw}% of a stat -- write it as "
                    f"{float(raw) / 100:g}x instead, four-digit percentages read as a bug"
                )
                break

    # A stat-scaled heal has to name its stat.
    if effect.get("kind", "").endswith("heal_from_stat"):
        stat = effect.get("stat", "")
        words = _stat_word(stat)
        if not any(word in description.lower() for word in words):
            failures.append(
                f"{label}: heals off {stat.upper()} but the description never says so "
                f"-- '{description[:60]}...'"
            )

    # Don't claim to cleanse if nothing cleanses.
    #
    # Only when the ability says IT cleanses. A kit reaction that fires
    # "whenever you cleanse an ally" is describing its TRIGGER, and
    # flagging that was the one false positive this check produced.
    kind = effect.get("kind", "")
    promises_cleanse = re.match(r"\s*(cleanse|purge)", description.strip(), re.I)
    if promises_cleanse and "cleanse" not in kind and effect.get("event") != "cleanse":
        failures.append(
            f"{label}: description promises a cleanse, but the effect kind is "
            f"'{kind}' which does not cleanse"
        )


def main() -> int:
    from bot.game.combat import skills
    from bot.game.loot import abilities as gear

    failures: list[str] = []
    checked = 0

    for key, kit in skills.CHARACTER_KIT_MAP.items():
        _check(f"kit {key}", kit, failures)
        checked += 1
    for pool_name in ("WEAPON_SKILLS", "ARTIFACT_SKILLS", "ARMOR_PASSIVES",
                      "ULTIMATE_ABILITIES"):
        for ability in getattr(gear, pool_name, []):
            _check(f"{pool_name.split('_')[0].lower()} {ability['id']}", ability, failures)
            checked += 1

    print(f"abilities : {checked} checked (character kits + every gear pool)")
    print("rule      : every % in a description must exist in its effect")
    print()
    if failures:
        for line in dict.fromkeys(failures):
            print(f"  FAIL  {line}")
        print(f"\n{len(failures)} description(s) disagree with their own effect.")
        return 1
    print("OK -- every ability does what it says.")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, ".")
    sys.exit(main())
