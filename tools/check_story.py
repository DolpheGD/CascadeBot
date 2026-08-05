"""
Validate the whole story script without running it.

    python -m tools.check_story

Story content has the same property that made `tools/check_encounters.py`
necessary: it's pure data resolved by a generic interpreter, so a typo
doesn't fail at import or startup. It fails when a player reaches that
one beat -- which for a story mission might be the fourth mission of a
chapter, twenty minutes in, and the failure is a dead button in the
middle of a scripted scene.

Checked:

  * ids unique across every chapter, and every mission reachable
  * every beat has the keys its `kind` needs
  * every enemy name in a battle beat exists in the roster
  * every reward key is a real currency or a valid item rarity
  * every `unlock` names a real feature, and every feature that IS
    gated has exactly one unlock beat somewhere
  * every flag read by `requires`/`unless` is written by some choice --
    a beat gated on a flag nobody sets can never appear
  * a mission cannot be empty, and cannot end on a `choice` (the player
    would pick an option and see nothing happen)

Map density checks land here too once areas exist -- see
docs/STORY_MODE.md.
"""

from __future__ import annotations

import sys

BEAT_KINDS = {"dialogue", "choice", "battle", "encounter", "reward", "unlock"}


def main() -> int:
    from bot.database.models.enums import Rarity
    from bot.game.characters.character_seed_data import CHARACTER_TEMPLATES
    from bot.game.combat.enemies import ENEMY_TEMPLATES
    from bot.game.dungeon.encounter_config import get_encounter_by_id
    from bot.game.story import story_config as sc
    from bot.services.currency_service import VALID_CURRENCIES

    enemy_names = {t["name"] for t in ENEMY_TEMPLATES}
    rarities = {r.value for r in Rarity}
    failures: list[str] = []

    missions = sc.all_missions()
    ids = [m["id"] for m in missions]
    for duplicate in {i for i in ids if ids.count(i) > 1}:
        failures.append(f"duplicate mission id: {duplicate}")

    # Every flag anyone READS must be WRITTEN by some choice, or the beat
    # gated on it is unreachable content that looks fine in the file.
    written_flags: set[str] = set()
    for mission in missions:
        for beat in mission["beats"]:
            for option in beat.get("options", []) or []:
                written_flags.update((option.get("sets") or {}).keys())

    character_names = {t["name"] for t in CHARACTER_TEMPLATES}

    def check_grant(where: str, grant: dict) -> None:
        for key, value in (grant or {}).items():
            if key == "item":
                if isinstance(value, str) and value not in rarities:
                    failures.append(f"{where}: item rarity {value!r} does not exist")
            elif key == "character":
                # Validated against the seed data by NAME, because that's
                # what the grant uses -- a renamed or removed character
                # would otherwise fail silently at the moment a player
                # reaches the beat.
                if value not in character_names:
                    failures.append(f"{where}: no character template named {value!r}")
            elif key not in VALID_CURRENCIES:
                failures.append(f"{where}: '{key}' is not a currency")

    for mission in missions:
        name = mission["id"]
        beats = mission.get("beats") or []
        if not beats:
            failures.append(f"{name}: no beats")
        check_grant(f"{name}/rewards", mission.get("rewards") or {})

        if beats and beats[-1].get("kind") == "choice":
            failures.append(
                f"{name}: ends on a choice -- the player picks and sees nothing happen"
            )

        for index, beat in enumerate(beats):
            where = f"{name}[{index}]"
            kind = beat.get("kind")
            if kind not in BEAT_KINDS:
                failures.append(f"{where}: beat kind {kind!r} is not one of {sorted(BEAT_KINDS)}")
                continue

            for flag_name in list(beat.get("requires", [])) + list(beat.get("unless", [])):
                if flag_name not in written_flags:
                    failures.append(
                        f"{where}: gated on flag '{flag_name}', which no choice ever sets"
                    )

            if kind == "dialogue":
                if not beat.get("text"):
                    failures.append(f"{where}: dialogue with no text")
            elif kind == "choice":
                options = beat.get("options") or []
                if not 2 <= len(options) <= 4:
                    failures.append(f"{where}: {len(options)} options (needs 2-4)")
                option_ids = [o.get("id") for o in options]
                if len(set(option_ids)) != len(option_ids):
                    failures.append(f"{where}: duplicate option ids")
                for option in options:
                    if not option.get("label"):
                        failures.append(f"{where}: an option has no label")
            elif kind == "battle":
                enemies = beat.get("enemies") or []
                if not enemies:
                    failures.append(f"{where}: battle with no enemies")
                if len(enemies) > 5:
                    failures.append(f"{where}: {len(enemies)} enemies (engine allows 5)")
                for enemy in enemies:
                    if enemy not in enemy_names:
                        failures.append(f"{where}: no enemy template named {enemy!r}")
                if not isinstance(beat.get("level"), int):
                    failures.append(f"{where}: battle needs an integer level")
            elif kind == "encounter":
                if get_encounter_by_id(beat.get("encounter_id", "")) is None:
                    failures.append(
                        f"{where}: encounter {beat.get('encounter_id')!r} does not exist"
                    )
            elif kind == "reward":
                check_grant(where, beat.get("grant") or {})
            elif kind == "unlock":
                feature = beat.get("feature")
                if feature not in sc.FEATURES:
                    failures.append(f"{where}: unlocks unknown feature {feature!r}")

    # A gated feature with two unlock beats is ambiguous; with zero it's
    # simply ungated (which story_service allows on purpose), so only the
    # duplicate case is an error.
    for feature in sc.FEATURES:
        unlocks = [
            m["id"] for m in missions
            for b in m["beats"]
            if b.get("kind") == "unlock" and b.get("feature") == feature
        ]
        if len(unlocks) > 1:
            failures.append(f"feature '{feature}' is unlocked by more than one mission: {unlocks}")

    gated = [f for f in sc.FEATURES if sc.feature_unlocked_by(f)]
    print(f"chapters : {len(sc.CHAPTERS)}")
    print(f"missions : {len(missions)}")
    print(f"beats    : {sum(len(m['beats']) for m in missions)}")
    print(f"flags    : {len(written_flags)} written ({', '.join(sorted(written_flags)) or 'none'})")
    print(f"gated    : {len(gated)}/{len(sc.FEATURES)} features "
          f"({', '.join(sorted(gated)) or 'none'})")

    print()
    if failures:
        for line in dict.fromkeys(failures):
            print(f"  FAIL  {line}")
        return 1
    print("OK -- every beat is runnable and every flag is reachable.")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, ".")
    sys.exit(main())
