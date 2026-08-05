"""
Assert every Resonance level does something, for every character.

    python -m tools.check_resonance

WHY. Resonance levels are GENERIC -- they read off whatever the
character's own kit happens to contain (see resonance_config's module
docstring). That's what makes 24 characters affordable to support, and
it's also the failure mode: a level that works by recognising effect keys
silently does nothing for a character whose kit uses a key nobody listed.

That is not hypothetical. The first version of the magnitude allowlist
covered `damage_percent` but not `base_damage_percent`, so Resonance 4 --
"your skill and ultimate hit 18% harder" -- did precisely nothing for
Josh, the strongest DPS on the roster. Nothing errored. The level just
wasn't there, and only a before/after diff of his skill numbers would
have shown it.

So each of the five levels is checked against every character:

  R1  the character's damage stat actually rises, and rises on the stat
      their kit scales from (ELE for the elemental characters, not ATK)
  R2  the character skill's SP cost actually falls
  R3  max HP and DEF rise
  R4  at least one number in the skill AND the ultimate changes
  R5  the ultimate's cooldown falls, crit damage rises

It also checks the two things that would be quietly destructive: that the
shared kit registries are never mutated, and that no self-cost or
duration got scaled along with the magnitudes.
"""

from __future__ import annotations

import copy
import sys


class FakeCharacter:
    """Enough of a PlayerCharacter for build_character_combatant."""

    def __init__(self, template, dupe_count: int, level: int = 60):
        self.id = 1
        self.template = template
        self.template_id = template.id
        self.level = level
        self.dupe_count = dupe_count
        self.custom_name = None
        self.current_class = None
        self.current_hp = None

    @property
    def display_name(self):
        return self.template.name

    def effective_class(self):
        return self.template.character_class


class FakeTemplate:
    def __init__(self, data, index: int):
        self.id = index
        self.is_player_avatar = False
        for key, value in data.items():
            setattr(self, key, value)


def main() -> int:
    from bot.game.characters.character_seed_data import CHARACTER_TEMPLATES
    from bot.game.combat.factory import (
        build_character_combatant, _KIT_MAGNITUDE_KEYS, _KIT_POISE_KEYS)
    from bot.game.combat.skills import CHARACTER_KIT_MAP
    from bot.game.economy.resonance_config import MAX_RESONANCE, RESONANCE_LEVELS

    registry_before = copy.deepcopy(CHARACTER_KIT_MAP)
    failures: list[str] = []

    templates = [
        FakeTemplate(data, i)
        for i, data in enumerate(CHARACTER_TEMPLATES, start=1)
        if not data.get("is_player_avatar")
    ]

    def built(template, resonance: int):
        return build_character_combatant(FakeCharacter(template, resonance + 1), [])

    def character_skill(combatant):
        return next(
            (a for a in combatant.active_abilities if a.get("source") == "character"), None
        )

    print(f"{'character':<16}{'R1 stat':>18}{'R2 cost':>12}{'R3 hp/def':>14}"
          f"{'R4 changes':>12}{'R5 ult cd':>11}")

    for template in templates:
        base = built(template, 0)
        top = built(template, MAX_RESONANCE)
        name = template.name

        # R1 -- the damage stat the kit actually scales from.
        stat = "elemental" if any(
            (a.get("effect") or {}).get("damage_stat") == "elemental"
            for a in list(base.active_abilities) + ([base.ultimate_ability] if base.ultimate_ability else [])
        ) else "attack"
        r1_ok = top.base_stats[stat] > base.base_stats[stat]
        if not r1_ok:
            failures.append(f"{name}: R1 did not raise {stat}")

        # R2 -- the character skill's cost.
        base_skill, top_skill = character_skill(base), character_skill(top)
        r2_ok = base_skill is not None and top_skill["resource_cost"] < base_skill["resource_cost"]
        if not r2_ok:
            failures.append(f"{name}: R2 did not reduce the skill's SP cost")

        # R3 -- survivability.
        r3_ok = top.max_hp > base.max_hp and top.base_stats["defense"] > base.base_stats["defense"]
        if not r3_ok:
            failures.append(f"{name}: R3 did not raise max HP and DEF")

        # R4 -- magnitudes in BOTH the skill and the ultimate.
        def changed(before, after):
            b, a = (before.get("effect") or {}), (after.get("effect") or {})
            keys = _KIT_MAGNITUDE_KEYS + _KIT_POISE_KEYS
            return sum(1 for k in keys if k in b and b[k] != a.get(k))

        skill_changes = changed(base_skill, top_skill)
        ult_changes = (changed(base.ultimate_ability, top.ultimate_ability)
                       if base.ultimate_ability else 0)
        if skill_changes == 0:
            failures.append(f"{name}: R4 changed nothing in the skill ({base_skill['id']})")
        if base.ultimate_ability and ult_changes == 0:
            failures.append(f"{name}: R4 changed nothing in the ultimate")

        # R4 must NOT have touched durations, chances or self-costs.
        for label, before, after in (("skill", base_skill, top_skill),
                                     ("ultimate", base.ultimate_ability, top.ultimate_ability)):
            if before is None:
                continue
            b, a = (before.get("effect") or {}), (after.get("effect") or {})
            for key in ("duration", "hits", "max_stacks", "self_cost_percent",
                        "hp_threshold_percent", "debuff_chance_percent",
                        "dot_chance_percent", "poise_chance_percent"):
                if key in b and b[key] != a.get(key):
                    failures.append(f"{name}: R4 scaled {label} '{key}' ({b[key]} -> {a.get(key)})")

        # R5 -- cooldown and crit damage.
        base_cd = base.ultimate_ability["cooldown"] if base.ultimate_ability else None
        top_cd = top.ultimate_ability["cooldown"] if top.ultimate_ability else None
        r5_ok = base_cd is None or top_cd < base_cd
        if not r5_ok:
            failures.append(f"{name}: R5 did not shorten the ultimate cooldown")
        if top.base_stats["crit_damage"] <= base.base_stats["crit_damage"]:
            failures.append(f"{name}: R5 did not raise crit damage")

        print(f"{name[:15]:<16}"
              f"{stat + ' ' + ('ok' if r1_ok else 'FAIL'):>18}"
              f"{str(base_skill['resource_cost']) + '->' + str(top_skill['resource_cost']):>12}"
              f"{('ok' if r3_ok else 'FAIL'):>14}"
              f"{f'{skill_changes}+{ult_changes}':>12}"
              f"{f'{base_cd}->{top_cd}':>11}")

    # The kit registries are module-level dicts shared by every character
    # in the process. Scaling one in place would permanently buff that
    # ability for everyone, and would compound every time a Combatant was
    # built -- which for the profile screen is every page view.
    if CHARACTER_KIT_MAP != registry_before:
        failures.append("the shared kit registry was mutated by applying resonance")

    print(f"\nchecked {len(templates)} characters x {len(RESONANCE_LEVELS)} levels")
    if failures:
        for line in dict.fromkeys(failures):
            print(f"  FAIL  {line}")
        return 1
    print("OK -- every resonance level does something for every character, "
          "and nothing shared was mutated.")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, ".")
    sys.exit(main())
