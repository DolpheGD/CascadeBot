"""
Assert the three combat promises the UI makes to the player.

    python -m tools.check_combat_contracts

These are not balance questions. They're contracts: the screen tells the
player something, and the engine has to honour it. Each one below was a
live bug, and each was invisible to every other checker in this folder --
the modules all imported fine, every ability resolved, no exception was
ever raised. They only show up if you compare what the player was TOLD
against what actually happened.

  1. TELEGRAPHED INTENT IS BINDING. The Incoming panel names each enemy's
     next move. That move must survive the save/reload cycle that happens
     between every single Discord interaction.

     How it broke: peek_enemy_intent_schedule() is what DECIDES an
     enemy's move (it pins into Combatant.pending_intents), and its only
     caller is the combat embed. But every cog renders AFTER saving --
     `state.combat_state = battle_to_dict(battle)` then
     `embed = combat_embed(battle)` -- so the decision landed on an
     object that was immediately discarded. The next interaction reloaded
     the un-pinned blob and re-rolled against fresh RNG and a fuller
     energy bar, which is how a telegraphed skill became an ultimate
     mid-fight. 44 of 60 renders changed across a single reload.

  2. ENEMY SUSTAIN DECAYS. PLAYER SUSTAIN DOES NOT. Enemy heals and
     shields fall off hard with repeated use so a fight can't stall
     forever; the player's never do, because a healer whose heals
     silently shrink is a healer the player can't reason about.

  3. DOWNED IS NOT DEAD -- UNLESS EVERYONE IS. A character on 0 HP gets
     up at 1 HP after a fight the squad survived. If the WHOLE squad went
     down, 0 is written through, because the roster showing survivors
     after a wipe is a lie about the thing that just happened.

     How it broke: only the expedition path ever called
     sync_party_hp_to_characters. Story missions, optional hunts and
     Abyss chambers never wrote HP back at all, so deaths there did
     neither half of the rule.
"""

from __future__ import annotations

import random
import sys

# Renders to compare. Each one saves, renders, reloads from what was
# saved, and re-renders -- the exact sequence a player produces by
# pressing a button.
SAMPLES = 60


def _party(size: int = 4, hp: int = 9000) -> list:
    from bot.game.combat.combatant import Combatant
    return [
        Combatant(
            name=f"Hero{i}", is_player=True,
            base_stats={"attack": 100, "defense": 80, "speed": 90, "elemental": 80,
                        "crit_rate": 5, "crit_damage": 50, "max_hp": hp},
            current_hp=hp, max_hp=hp, character_id=i + 1,
        )
        for i in range(size)
    ]


def _incoming(embed) -> list[str]:
    return [f.value for f in embed.fields if "Incoming" in (f.name or "")]


def check_intents_are_binding(failures: list[str]) -> str:
    from bot.game.combat.battle import Battle
    from bot.game.combat.enemies import ENEMY_TEMPLATES
    from bot.game.combat.factory import build_enemy_combatant
    from bot.game.combat.serialization import battle_from_dict, battle_to_dict
    from bot.utils.embedder import combat as combat_embedder

    # Enemies with a real choice to make. A template with one ability
    # can't drift, so testing it proves nothing.
    names = [t["name"] for t in ENEMY_TEMPLATES
             if len(t.get("active_abilities") or []) >= 2]

    drift = mismatch = renders = 0
    for seed in range(SAMPLES):
        picker = random.Random(seed)
        enemies = [
            build_enemy_combatant(
                next(t for t in ENEMY_TEMPLATES if t["name"] == name), 30)
            for name in picker.sample(names, 3)
        ]
        battle = Battle(_party(), enemies, rng=random.Random(seed))

        for step in range(120):
            if battle.is_over():
                break
            if battle.current_actor() in battle.party:
                blob = battle_to_dict(battle)
                shown = _incoming(combat_embedder.combat_embed(battle))
                # A DIFFERENT rng on reload, deliberately: if anything is
                # still being decided at render time rather than restored,
                # this is what exposes it.
                battle = battle_from_dict(blob, rng=random.Random(seed * 7 + step))
                again = _incoming(combat_embedder.combat_embed(battle))
                renders += 1
                if shown != again:
                    drift += 1
                battle.take_party_action("attack")
            else:
                enemy = battle.current_actor()
                told = None
                if enemy.pending_intents:
                    told = (enemy.pending_intents[0]["ability"] or {}).get("name")
                mark = len(battle.log)
                battle.take_enemy_turn()
                after = battle.log[mark:]
                # "can't muster" is the legitimate fallback: the move was
                # telegraphed honestly and then became unaffordable.
                if told and not any(told in line for line in after) \
                        and not any("can't muster" in line for line in after):
                    mismatch += 1

    if drift:
        failures.append(
            f"{drift} of {renders} renders showed a DIFFERENT enemy intent after a "
            f"save/reload -- the Incoming panel is telling the player something the "
            f"engine will not honour"
        )
    if mismatch:
        failures.append(
            f"{mismatch} enemy turns did something other than the move that was "
            f"telegraphed for them"
        )
    return f"intents   : {renders} renders, {drift} drifted, {mismatch} mis-executed"


def check_sustain_decay_is_enemy_only(failures: list[str]) -> str:
    from bot.game.combat.combatant import Combatant

    def series(is_player: bool, kind: str) -> list[float]:
        big = 100_000
        c = Combatant(
            name="X", is_player=is_player,
            base_stats={"attack": 1, "defense": 1, "speed": 1, "elemental": 1,
                        "crit_rate": 0, "crit_damage": 0, "max_hp": big},
            current_hp=1 if kind == "heal" else big, max_hp=big,
        )
        out = []
        for _ in range(5):
            if kind == "heal":
                before = c.current_hp
                c.heal(1000)
                out.append(round(c.current_hp - before, 1))
            else:
                before = c.shield
                c.gain_shield(1000)
                out.append(round(c.shield - before, 1))
        return out

    for kind in ("heal", "shield"):
        player = series(True, kind)
        enemy = series(False, kind)
        if len(set(player)) != 1:
            failures.append(
                f"PLAYER {kind}s decay ({player}) -- player sustain must never fall "
                f"off, or a healer stops being something the player can reason about"
            )
        if enemy[-1] >= enemy[0]:
            failures.append(
                f"ENEMY {kind}s do not decay ({enemy}) -- an enemy that can sustain "
                f"indefinitely turns a fight into a stall"
            )
    return ("sustain   : player flat, enemy "
            + " -> ".join(str(v) for v in series(False, "heal")))


def check_revive_rule(failures: list[str]) -> str:
    from bot.game.combat.battle import Battle
    from bot.game.combat.enemies import ENEMY_TEMPLATES
    from bot.game.combat.factory import build_enemy_combatant
    from bot.services import combat_service

    class _Rows(list):
        def filter(self, *a, **k):
            return self

        def all(self):
            return list(self)

    class _PC:
        def __init__(self, pk, mx):
            self.id, self.max_hp, self.current_hp = pk, mx, None

    class _DB:
        def __init__(self, rows):
            self._rows = rows

        def query(self, *a, **k):
            return _Rows(self._rows)

        def commit(self):
            pass

    template = next(t for t in ENEMY_TEMPLATES if t["role"] == "combat")

    def stored(hps: list[int]) -> list:
        party = _party()
        for combatant, hp in zip(party, hps):
            combatant.current_hp = hp
        battle = Battle(party, [build_enemy_combatant(template, 10)],
                        rng=random.Random(0))
        rows = [_PC(c.character_id, c.max_hp) for c in party]
        combat_service.sync_party_hp_to_characters(_DB(rows), battle)
        # None is the "untouched, therefore full" sentinel.
        return [r.current_hp for r in rows]

    survived = stored([4000, 0, 0, 120])
    if survived[1] != combat_service.REVIVE_HP_AFTER_BATTLE:
        failures.append(
            f"a character downed in a fight the squad SURVIVED was stored as "
            f"{survived[1]!r}, not {combat_service.REVIVE_HP_AFTER_BATTLE} -- they "
            f"would be unable to act, and unrevivable, for every fight after it"
        )

    wiped = stored([0, 0, 0, 0])
    if any(hp != 0 for hp in wiped):
        failures.append(
            f"after a FULL WIPE the squad was stored as {wiped} -- the roster would "
            f"show survivors from a fight nobody survived"
        )
    return f"revive    : survived -> {survived}, wiped -> {wiped}"


def main() -> int:
    failures: list[str] = []
    lines = [
        check_intents_are_binding(failures),
        check_sustain_decay_is_enemy_only(failures),
        check_revive_rule(failures),
    ]
    for line in lines:
        print(line)
    print()
    if failures:
        for line in dict.fromkeys(failures):
            print(f"  FAIL  {line}")
        return 1
    print("OK -- telegraphed moves are binding, only enemies decay, and the "
          "dead stay down only when everyone does.")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, ".")
    sys.exit(main())
