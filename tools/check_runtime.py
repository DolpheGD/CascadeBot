"""
Catch the bugs that importing a module cannot.

    python -m tools.check_runtime

Two failures shipped on the same day and neither was catchable by
anything already in tools/:

  * `/start` raised `NameError: name 'story_service' is not defined` --
    the module imported fine, because the missing import was only read
    inside a function body.
  * `_apply_gain` read a `difficulty` local that has never existed in
    its scope, so every encounter granting {"item": "natural"} crashed
    -- a crash on a REWARD, mid-run, after the player had already spent
    the time to earn it.

`compileall` passes both (they're valid syntax). Importing every module
passes both (the bad line never executes at import). `check_encounters`
passes the second one because it reads the config as data and never
calls the interpreter. The common shape is: valid code, valid data, and
a code path nothing exercises until a player walks onto it.

So this checker does the two things the others don't:

  1. UNDEFINED NAMES -- pyflakes over the whole tree, which finds a name
     read but never bound regardless of how deep in a function it is.
     Unused imports and unused locals are ignored on purpose; they're
     style, not breakage, and a checker that cries about them gets
     muted.
  2. ACTUAL EXECUTION -- every encounter outcome in the game is run
     against a real (temporary) database with a real player. Not
     inspected: run. If interpreting an outcome raises, this fails,
     which is precisely the guarantee check_encounters cannot give.

Failing to import pyflakes is not a failure here -- it's an optional
dependency and the execution pass is the load-bearing half.
"""

from __future__ import annotations

import random
import sys
import tempfile
import traceback

# Style-only pyflakes messages. Everything else is treated as a real
# finding, so a NEW class of pyflakes warning surfaces rather than being
# silently swallowed by an allowlist that was never revisited.
_IGNORED_SUBSTRINGS = (
    "imported but unused",
    "unable to detect undefined names",
    "redefinition of unused",
    "is assigned to but never used",
    "from __future__ imports must occur",
)


def _undefined_names() -> list[str]:
    try:
        from pyflakes.api import checkRecursive
        from pyflakes.reporter import Reporter
    except ImportError:
        print("names      : SKIPPED (pip install pyflakes to enable)")
        return []

    import io

    out, err = io.StringIO(), io.StringIO()
    checkRecursive(["bot", "tools"], Reporter(out, err))
    findings = [
        line for line in out.getvalue().splitlines()
        if line.strip() and not any(s in line for s in _IGNORED_SUBSTRINGS)
    ]
    print(f"names      : {len(findings)} real finding(s) across bot/ + tools/")
    return findings


# Commands that are DELIBERATELY reachable before the story introduces
# anything. Each one needs a reason, because "it was easier" is how the
# gate leaks -- which is exactly how it leaked the first time.
UNGATED_COMMANDS: dict[str, str] = {
    "start": "creates the player; gating it would gate the game",
    "story": "the thing every gate points at",
    "help": "how you find out what's going on",
    "profile": "your own account, always yours to look at",
    "characters": "stats for characters you already own",
    "class": "your avatar's role; needed before the first fight",
    "rename": "cosmetic, and offered during onboarding",
    "encyclopedia": "pure reference, like /help -- reads nothing you own",
    "vote": "top.gg voting is external to progression",
    "sync": "owner-only admin command",
    "admin_boosterkit": "admin-only, and enforces its own permission check",
    "admin_reset": ("admin-only, self-only, and enforces its own permission check; "
                    "story-gating the command that EXISTS to replay the story would "
                    "be circular"),
}


def _gates_on_commands() -> list[str]:
    """Every slash command must be gated, or listed above with a reason.

    This exists because of a real report: after the prologue's second
    mission a new player could open the HQ, the shop, the Forge, the
    Research Lab and the quest log -- none of which the story had
    introduced. Two separate causes, and only one of them was visible in
    the gating code:

      1. features with no unlock beat written yet defaulted to OPEN
      2. six cogs simply never called require_feature at all

    The first was one line in story_service. The second is the kind of
    thing that comes back every time a command is added, because nothing
    fails when you forget. So it's asserted here: a new command is locked
    by default and adding it to UNGATED_COMMANDS is a deliberate act with
    a written justification next to it.
    """
    import ast
    import pathlib

    failures: list[str] = []
    checked = 0

    for path in sorted(pathlib.Path("bot/cogs").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            name = None
            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call):
                    continue
                target = decorator.func
                attr = getattr(target, "attr", None)
                if attr != "command":
                    continue
                for keyword in decorator.keywords:
                    if keyword.arg == "name" and isinstance(keyword.value, ast.Constant):
                        name = keyword.value.value
            if name is None:
                continue

            checked += 1
            if name in UNGATED_COMMANDS:
                continue

            # The gate may live in the command body OR in a helper it
            # delegates to (raid.py does this), so search the whole
            # module for the handler rather than only this function.
            body = ast.dump(node)
            if "require_feature" in body:
                continue
            source = path.read_text(encoding="utf-8")
            called = [
                child.func.id for child in ast.walk(node)
                if isinstance(child, ast.Call) and isinstance(child.func, ast.Name)
            ]
            if any(
                f"def {helper}" in source
                and "require_feature" in source.split(f"def {helper}", 1)[1][:4000]
                for helper in called
            ):
                continue

            failures.append(
                f"/{name} in {path.name} has no require_feature gate and is not in "
                f"UNGATED_COMMANDS -- a new player can reach it before the story "
                f"introduces it"
            )

    print(f"commands   : {checked} checked, {len(UNGATED_COMMANDS)} deliberately ungated")
    return failures


def _execute_every_outcome() -> list[str]:
    """Run every outcome block in every encounter for real.

    Uses a throwaway SQLite file and one throwaway player. Gold, items
    and materials really are granted -- that's the point, since the
    crash being guarded against happened inside the granting code.
    """
    from sqlalchemy.orm import sessionmaker

    from bot.database.db import engine
    from bot.database.db_init import init_db
    from bot.database.models.enums import Rarity
    from bot.database.models.player_model import Player
    from bot.game.dungeon.encounter_config import ENCOUNTERS
    from bot.services import dungeon_service, item_template_service, lootbox_service

    init_db()
    db = sessionmaker(bind=engine)()
    # Seed EVERY catalog an outcome can reach. A missing catalog shows up
    # as "No lootbox template for tier 'common'", which reads exactly like
    # a content bug and isn't one -- same trap as the stub Expedition.
    item_template_service.ensure_item_templates_seeded(db)
    lootbox_service.ensure_lootbox_templates_seeded(db)
    player = Player(id=1, username="runtime-check", gold=10**9, shards=10**9)
    db.add(player)
    db.commit()

    # A REAL Expedition row and a REAL squad, not stubs.
    #
    # The first version of this checker used a hand-written stand-in and
    # it "failed" 40-odd encounters -- every one of them because the stub
    # lacked `loot_ledger` or the player had no squad. That is a checker
    # bug reported as a game bug, which is worse than no checker: it
    # trains you to skim the output. Building the real objects costs a
    # few lines and makes every failure printed here a genuine one.
    from bot.database.models.expedition_model import Expedition
    from bot.services import character_service, character_template_service

    character_template_service.ensure_character_templates_seeded(db)
    avatar = character_template_service.get_avatar_template(db)
    pc, _, _ = character_service.grant_character(db, player, avatar)
    character_service.set_squad_slot(db, player, 0, pc)
    db.commit()

    def fresh_expedition() -> Expedition:
        exp = Expedition(
            player_id=player.id,
            region="glacier",
            graph={"nodes": {}},
            loot_ledger={},
            relics=[],
        )
        db.add(exp)
        db.flush()
        return exp

    failures: list[str] = []
    outcomes_run = 0

    def collect(encounter: dict) -> list[tuple[str, dict]]:
        found: list[tuple[str, dict]] = []
        name = encounter.get("id", encounter.get("name", "?"))
        for choice in encounter.get("choices", []) or []:
            label = f"{name}/{choice.get('id', '?')}"
            for key in ("on_success", "on_fail", "outcome"):
                if isinstance(choice.get(key), dict):
                    found.append((f"{label}:{key}", choice[key]))
            for tier in choice.get("tiers", []) or []:
                if isinstance(tier.get("outcome"), dict):
                    found.append((f"{label}:tier", tier["outcome"]))
        return found

    # Seeded so a failure is reproducible, and looped so probabilistic
    # branches (bonus rolls, gamble tiers) actually get taken.
    for seed in range(12):
        rng = random.Random(seed)
        for encounter in ENCOUNTERS:
            for label, outcome in collect(encounter):
                outcomes_run += 1
                try:
                    dungeon_service._apply_outcome(
                        db, player, rng, outcome, 1.0, fresh_expedition(),
                        max_item_rarity=Rarity.LEGENDARY,
                        item_level=1,
                        rarity_weight_bonus=130,
                    )
                except Exception as exc:  # noqa: BLE001 -- reporting, not handling
                    failures.append(
                        f"{label} raised {type(exc).__name__}: {exc}\n"
                        + "".join(traceback.format_exc(limit=3).splitlines(True)[-3:])
                    )
                db.rollback()

    print(f"outcomes   : {outcomes_run} executed against a real database")
    return failures


def _resolve_every_ability_on_a_kill() -> list[str]:
    """Fire every ability in the game at a defender who is about to die.

    Abilities routinely branch on the hit KILLING the target -- execute
    heals, on-kill energy, cascade effects. Those branches are invisible
    to a test that pits healthy combatants against each other, which is
    how Gostley's `Grave Tithe` shipped reading `heal_percent_on_kill`
    from an effect that spelled it `heal_percent`: a KeyError that fires
    only on success, so the ability worked right up until it worked.

    So the defender starts at 1 HP and every ability is resolved against
    them. Anything that raises is a crash a player would hit by winning.
    """
    import random as _random

    from bot.game.combat.combatant import Combatant
    from bot.game.combat.effects import resolve_active_ability
    from bot.game.combat.skills import CHARACTER_KIT_MAP, CLASS_KIT_MAP
    from bot.game.loot.abilities import (ARTIFACT_SKILLS, ULTIMATE_ABILITIES,
                                         WEAPON_SKILLS)

    def combatant(name: str, hp: int, poise: int = 6) -> Combatant:
        return Combatant(
            name=name, is_player=True,
            base_stats={"attack": 100, "defense": 40, "elemental": 100, "speed": 10,
                        "max_hp": 5000, "max_mana": 300, "crit_rate": 10,
                        "crit_damage": 150, "recharge": 10},
            current_hp=hp, max_hp=5000, mana=300, max_mana=300, energy=50,
            max_poise=poise, poise=poise,
        )

    abilities: list[dict] = list(CHARACTER_KIT_MAP.values())
    for kit in CLASS_KIT_MAP.values():
        abilities += [kit["skill"], kit["ultimate"]]
    for pool in (WEAPON_SKILLS, ARTIFACT_SKILLS, ULTIMATE_ABILITIES):
        abilities += list(pool)

    failures: list[str] = []
    tested = 0

    for ability in abilities:
        if not isinstance(ability, dict) or "effect" not in ability:
            continue
        for seed in range(3):
            rng = _random.Random(seed)
            attacker = combatant("Attacker", 2500)
            defender = combatant("Victim", 1)   # one hit from dead, whatever lands
            ally = combatant("Ally", 2500)
            tested += 1
            try:
                resolve_active_ability(
                    attacker, defender, ability, rng, [],
                    allies=[attacker, ally], opponents=[defender],
                    chosen_ally=None,
                )
            except Exception as exc:  # noqa: BLE001 -- reporting, not handling
                failures.append(
                    f"ability {ability.get('name', ability.get('id', '?'))!r} raised "
                    f"{type(exc).__name__}: {exc} when the hit killed the target"
                )
                break

    print(f"abilities  : {tested} resolutions against a dying defender")
    return failures


def main() -> int:
    import os

    os.environ.setdefault("DATABASE_URL", "sqlite:///" + tempfile.mktemp(suffix=".db"))

    failures = (_undefined_names() + _gates_on_commands()
                + _resolve_every_ability_on_a_kill() + _execute_every_outcome())

    print()
    if failures:
        for line in dict.fromkeys(failures):
            print(f"  FAIL  {line}")
        return 1
    print("OK -- no undefined names, every command is gated, and every encounter "
          "outcome ran without raising.")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, ".")
    sys.exit(main())
