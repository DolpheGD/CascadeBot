"""
Validate every encounter against the interpreter that runs it.

    python -m tools.check_encounters

WHY. Encounters are pure DATA resolved generically by
dungeon_service._apply_outcome. That's the right design -- one
interpreter, no bespoke code per event -- but it means a typo in a
reward key doesn't fail at import, or at startup, or in any test. It
fails the first time a player happens to roll that one encounter and
picks that one button, and what they get is a crash or a silently
skipped reward.

With 70 encounters and several choices each, nobody is clicking every
path by hand. So this walks all of them and checks the things the
interpreter would trip over:

  * ids are unique, and every encounter is reachable from some room type
  * every choice has the keys its `action` needs (a "trade" without a
    cost, a "risk" without a success_chance, a "gamble" whose tier
    chances don't sum to 1)
  * every `gain` key is a real currency, a known shorthand
    (material_tier/lootbox/item), and every lootbox tier exists
  * `heal` is "full" or a number, and hp_damage_percent is a number --
    both are easy to nest inside "gain" by mistake, which would silently
    do nothing
"""

from __future__ import annotations

import sys

# Verified against dungeon_service._apply_gain rather than guessed --
# the first version of this list omitted "xp" and flagged six
# perfectly good encounters.
KNOWN_GAIN_SHORTHANDS = {"material_tier", "amount", "lootbox", "item", "xp"}
VALID_ACTIONS = {"leave", "risk", "trade", "gamble"}


def main() -> int:
    from bot.database.models.enums import RoomType
    from bot.game.dungeon.encounter_config import ENCOUNTERS
    from bot.game.economy.lootbox_config import LOOTBOX_TEMPLATES
    from bot.services.currency_service import VALID_CURRENCIES

    lootbox_tiers = {t["tier"] for t in LOOTBOX_TEMPLATES}
    room_values = {r.value for r in RoomType}
    failures: list[str] = []

    def check_outcome(where: str, outcome: dict) -> None:
        if not isinstance(outcome, dict):
            failures.append(f"{where}: outcome is {type(outcome).__name__}, not a dict")
            return
        for key, value in outcome.items():
            if key == "gain":
                for gain_key, gain_value in value.items():
                    if gain_key in KNOWN_GAIN_SHORTHANDS:
                        if gain_key == "lootbox" and gain_value not in lootbox_tiers:
                            failures.append(f"{where}: unknown lootbox tier {gain_value!r}")
                        continue
                    if gain_key not in VALID_CURRENCIES:
                        failures.append(f"{where}: '{gain_key}' is not a currency or shorthand")
            elif key == "loss":
                for loss_key in value:
                    if loss_key not in VALID_CURRENCIES and loss_key not in KNOWN_GAIN_SHORTHANDS:
                        failures.append(f"{where}: loss key '{loss_key}' is not a currency")
            elif key == "heal":
                if value != "full" and not isinstance(value, (int, float)):
                    failures.append(f"{where}: heal must be 'full' or a number, got {value!r}")
            elif key == "hp_damage_percent":
                if not isinstance(value, (int, float)):
                    failures.append(f"{where}: hp_damage_percent must be a number")
            elif key == "bonus":
                # A single {"chance", "gain"} dict OR a list of them, each
                # rolled independently -- see _apply_outcome.
                for i, spec in enumerate(value if isinstance(value, list) else [value]):
                    if "chance" not in spec or "gain" not in spec:
                        failures.append(f"{where}: bonus[{i}] needs both 'chance' and 'gain'")
                    else:
                        check_outcome(f"{where}/bonus{i}", {"gain": spec["gain"]})
            else:
                failures.append(f"{where}: unknown outcome key '{key}'")

        # The single easiest mistake to make, and completely silent: heal
        # and hp_damage_percent are SIBLINGS of gain, not entries in it.
        gain = outcome.get("gain") or {}
        for misplaced in ("heal", "hp_damage_percent", "bonus"):
            if misplaced in gain:
                failures.append(f"{where}: '{misplaced}' is inside 'gain' -- it belongs beside it")

    ids = [e["id"] for e in ENCOUNTERS]
    for encounter_id in {i for i in ids if ids.count(i) > 1}:
        failures.append(f"duplicate encounter id: {encounter_id}")

    for encounter in ENCOUNTERS:
        name = encounter["id"]
        rooms = encounter.get("room_types") or ()
        if not rooms:
            failures.append(f"{name}: no room_types, so it can never be rolled")
        for room in rooms:
            if room not in room_values:
                failures.append(f"{name}: room type '{room}' does not exist")
        if not encounter.get("intros"):
            failures.append(f"{name}: no intros")
        if not encounter.get("choices"):
            failures.append(f"{name}: no choices")

        for choice in encounter.get("choices", []):
            where = f"{name}/{choice.get('id', '?')}"
            action = choice.get("action")
            if action not in VALID_ACTIONS:
                failures.append(f"{where}: action {action!r} is not one of {sorted(VALID_ACTIONS)}")
                continue

            if action == "leave":
                if "text" not in choice:
                    failures.append(f"{where}: a 'leave' choice needs 'text'")
                continue

            if action == "gamble":
                tiers = choice.get("tiers") or []
                if not tiers:
                    failures.append(f"{where}: 'gamble' with no tiers")
                total = sum(t.get("chance", 0) for t in tiers)
                if abs(total - 1.0) > 0.02:
                    failures.append(f"{where}: gamble tier chances sum to {total:.3f}, not 1.0")
                for i, tier in enumerate(tiers):
                    check_outcome(f"{where}/tier{i}", tier.get("outcome") or {})
                continue

            if action == "trade" and "cost" not in choice:
                failures.append(f"{where}: 'trade' with no cost")
            if "success_chance" not in choice:
                failures.append(f"{where}: no success_chance")
            else:
                chance = choice["success_chance"]
                if not 0 <= chance <= 1:
                    failures.append(f"{where}: success_chance {chance} out of range")
            for key in ("cost",):
                for currency in (choice.get(key) or {}):
                    if currency not in VALID_CURRENCIES:
                        failures.append(f"{where}: cost in '{currency}', which is not a currency")
            check_outcome(f"{where}/success", choice.get("on_success") or {})
            check_outcome(f"{where}/fail", choice.get("on_fail") or {})

    # ------------------------------------------------------------------
    # EVERY ENEMY TEMPLATE MUST BE SPAWNABLE.
    #
    # A boss_group_member is never rolled on its own -- it appears only
    # via another boss's "escorts" list or as part of a BOSS_GROUPS
    # entry. So one that appears in neither is dead content: fully
    # statted, given a kit, a short name and balance comments, and
    # unreachable by any code path.
    #
    # This is not hypothetical. The Ocellios Train and Broskm sat
    # unreachable while NF -- the Wastelands FINAL boss, whose own stats
    # had been deliberately reduced to pay for three companions -- went
    # into the fight with one. The region's capstone was quietly a
    # weakened boss with a single escort, and nothing in the config
    # looked wrong, because each template was individually fine.
    # ------------------------------------------------------------------
    from bot.game.combat.enemies import BOSS_GROUPS, ENEMY_TEMPLATES

    spawnable: set[str] = set()
    known = {t["name"] for t in ENEMY_TEMPLATES}
    for template in ENEMY_TEMPLATES:
        for escort in template.get("escorts") or ():
            spawnable.add(escort)
            if escort not in known:
                failures.append(
                    f"{template['name']} escorts '{escort}', which is not an enemy template")
    for group, members in BOSS_GROUPS.items():
        for member in members:
            spawnable.add(member)
            if member not in known:
                failures.append(f"BOSS_GROUPS[{group}] lists '{member}', which is not a template")

    orphans = [t["name"] for t in ENEMY_TEMPLATES
               if t.get("role") == "boss_group_member" and t["name"] not in spawnable]
    for name in orphans:
        failures.append(
            f"'{name}' is a boss_group_member that no boss escorts and no BOSS_GROUPS "
            f"entry includes -- nothing in the game can ever spawn it")

    by_room = {
        room: sum(1 for e in ENCOUNTERS if room in (e.get("room_types") or ()))
        for room in sorted(room_values)
    }
    illustrated = sum(1 for e in ENCOUNTERS if e.get("image_url"))
    print(f"encounters : {len(ENCOUNTERS)} total, {illustrated} illustrated, "
          f"{len(ENCOUNTERS) - illustrated} text-only")
    print("per room   : " + ", ".join(f"{r}={n}" for r, n in by_room.items() if n))
    print(f"choices    : {sum(len(e.get('choices', [])) for e in ENCOUNTERS)}")
    print(f"escorts    : {len(spawnable)} template(s) reachable only as escorts/group members, "
          f"{len(orphans)} unreachable")

    print()
    if failures:
        for line in dict.fromkeys(failures):
            print(f"  FAIL  {line}")
        return 1
    print("OK -- every encounter is reachable and every outcome is interpretable.")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, ".")
    sys.exit(main())
