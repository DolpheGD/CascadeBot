"""
The Dispatch Board pays fairly, locks who it says it locks, and cannot
out-earn playing the game.

    python -m tools.check_dispatch

THREE THINGS ARE BEING DEFENDED, and they fail in different directions.

1. THE ECONOMY. The first draft of this board was written by feel and
   measured afterwards at a theoretical 147,200 gold a day -- more than
   the entire forge upgrade path in one sitting, and about 60x a fully
   levelled Gold Mine. Idle income that beats active income does not add
   a system, it removes one. The payouts are now anchored to TOTAL
   VALUE per character-hour -- gold plus materials plus XP -- and that
   band is asserted here, because the way this regresses is not a
   rewrite, it is one generous contract added later.

2. THE LOCK. "Assigned characters cannot fight" is the entire reason
   dispatch is a decision rather than a free-money button. It is
   enforced in character_service.set_squad_slot, one layer below the UI,
   and the point of testing it here is that the interesting paths are
   the ones that do NOT go through the dispatch screen -- loading a
   squad preset, in particular.

3. THE GACHA. Contracts may not pay shards, cores or characters. The
   argument that dispatch cannot replace playing rests on that, and a
   single shard reward slipped in later would quietly turn the base into
   a second gacha.
"""

from __future__ import annotations

import datetime as dt
import os
import sys
import tempfile

# TOTAL VALUE per character-hour, not gold per character-hour.
#
# The first version of this check banded on gold alone and was blind to
# most of what a contract pays: Deep Core Dig's gold was 50 per
# character-hour, and the materials stapled to it were worth another
# 9,440 gold. It flagged four material-heavy contracts as underpaid
# while ignoring the actual inflation risk, which is somebody adding a
# contract that pays 400 xendium and reads as modest.
#
# Materials are priced at hq_config.MATERIAL_GOLD_VALUE -- the game's own
# number, so a repricing of the economy moves this with it rather than
# leaving a stale constant here.
MIN_VALUE_PER_CHARACTER_HOUR = 170
MAX_VALUE_PER_CHARACTER_HOUR = 320

# XP in gold. Rough by nature, which is why it is small: it exists so an
# XP-only contract is not scored as if it paid nothing, not to price
# levelling accurately.
XP_GOLD_VALUE = 0.5

# The theoretical ceiling: every slot, best contract, chained around the
# clock. Unreachable in practice, which is why it is allowed to be well
# above the realistic figure -- but it is the number that grows without
# anybody noticing when a contract is added.
MAX_THEORETICAL_GOLD_PER_DAY = 80_000


def _value_per_character_hour(contract: dict) -> float:
    """Everything a contract pays, in gold, divided by what it costs.

    The cost of a contract to the player is party size times hours -- the
    character-hours they cannot spend fighting. That is the denominator
    the design actually trades against.
    """
    from bot.game.economy.hq_config import MATERIAL_GOLD_VALUE

    rewards = contract["rewards"]
    total = float(rewards.get("gold", 0))
    total += sum(MATERIAL_GOLD_VALUE.get(key, 0) * amount
                 for key, amount in rewards.items()
                 if key in MATERIAL_GOLD_VALUE)
    total += rewards.get("xp", 0) * XP_GOLD_VALUE
    return total / max(1, contract["party"] * contract["hours"])


def main() -> int:
    sys.path.insert(0, ".")
    os.environ.setdefault(
        "DATABASE_URL", "sqlite:///" + tempfile.mktemp(suffix=".db"))
    import bot.config as cfg
    cfg.DATABASE_URL = os.environ["DATABASE_URL"]

    from bot.database.db_init import init_db
    init_db()
    from bot.database.models.character_model import CharacterTemplate, PlayerCharacter
    from bot.database.models.hq_model import PlayerBase
    from bot.database.session import SessionLocal
    from bot.game.economy import dispatch_config as dc
    from bot.services import (character_service, character_template_service,
                              dispatch_service as D, player_service, squad_service)

    failures: list[str] = []

    # ---- 1. contract definitions are well formed ---------------------
    seen_ids: set[str] = set()
    for contract in dc.CONTRACTS:
        cid = contract["id"]
        if cid in seen_ids:
            failures.append(f"duplicate contract id {cid!r}")
        seen_ids.add(cid)

        for key in ("name", "description", "party", "hours", "level",
                    "prefers", "rewards"):
            if key not in contract:
                failures.append(f"{cid!r} is missing {key!r}")

        if not 1 <= contract["party"] <= 4:
            failures.append(
                f"{cid!r} wants a party of {contract['party']} -- the squad is 4, "
                f"so anything larger can never be staffed")
        if len(contract.get("prefers", [])) > contract["party"]:
            failures.append(
                f"{cid!r} prefers {len(contract['prefers'])} classes but only takes "
                f"{contract['party']} characters -- the extra bonuses are unreachable "
                f"and the contract advertises a payout nobody can hit")

        # ---- the gacha stays untouched -------------------------------
        for currency in contract["rewards"]:
            if currency not in dc.PAYABLE:
                failures.append(
                    f"{cid!r} pays {currency!r}, which is not in PAYABLE -- dispatch "
                    f"must never pay shards, cores or characters, or the base "
                    f"becomes a second gacha")

        # ---- the economic band ---------------------------------------
        per = _value_per_character_hour(contract)
        if not MIN_VALUE_PER_CHARACTER_HOUR <= per <= MAX_VALUE_PER_CHARACTER_HOUR:
            failures.append(
                f"{cid!r} pays {per:.0f} gold-equivalent per character-hour, "
                f"outside the {MIN_VALUE_PER_CHARACTER_HOUR}-"
                f"{MAX_VALUE_PER_CHARACTER_HOUR} band. Contracts sit close "
                f"together on purpose -- one well outside it is either strictly "
                f"better than every other contract or strictly worse, and both "
                f"remove a choice")

    # ---- the daily ceiling -------------------------------------------
    best = max((c["rewards"].get("gold", 0) * dc.MAX_FIT_MULTIPLIER) / c["hours"]
               for c in dc.CONTRACTS)
    ceiling = best * 24 * dc.MAX_SLOTS
    if ceiling > MAX_THEORETICAL_GOLD_PER_DAY:
        failures.append(
            f"a full board chained for 24h yields {ceiling:,.0f} gold, above the "
            f"{MAX_THEORETICAL_GOLD_PER_DAY:,} ceiling -- idle income is overtaking "
            f"the active game")

    # ---- fit multiplier behaves --------------------------------------
    db = SessionLocal()
    character_template_service.ensure_character_templates_seeded(db)
    player = player_service.get_or_create_player(db, 90_001, "DispatchProbe")
    character_service.ensure_avatar_character(db, player)
    templates = db.query(CharacterTemplate).filter_by(is_player_avatar=False).all()
    for template in templates[:16]:
        db.add(PlayerCharacter(player_id=player.id, template_id=template.id,
                               level=40, talents=[], dupe_count=1))
    base = db.query(PlayerBase).filter_by(player_id=player.id).first()
    if base is None:
        base = PlayerBase(player_id=player.id)
        db.add(base)
    base.hq_level = 8
    db.commit()

    contract = dc.contract("escort_the_assessor")
    mine = db.query(PlayerCharacter).filter_by(player_id=player.id).all()
    empty = dc.fit_multiplier(contract, [])
    if empty != dc.MIN_FIT_MULTIPLIER:
        failures.append(
            f"an empty team scores {empty}, not the {dc.MIN_FIT_MULTIPLIER} floor")
    for members in (mine[:1], mine[:3], mine[:4]):
        value = dc.fit_multiplier(contract, members)
        if not dc.MIN_FIT_MULTIPLIER <= value <= dc.MAX_FIT_MULTIPLIER:
            failures.append(
                f"fit of {value:.2f} is outside "
                f"[{dc.MIN_FIT_MULTIPLIER}, {dc.MAX_FIT_MULTIPLIER}]")

    # A CONTRACT WANTING TWO OF A CLASS IS NOT SATISFIED BY ONE.
    # The multiset rule -- an earlier version used a set and paid both
    # bonuses for a single matching character.
    from bot.database.models.enums import CharacterClass

    class _Fake:
        def __init__(self, cls, level=40, star=4):
            self.level = level
            self.template = type("T", (), {
                "character_class": cls, "star_rating": star})()

    doubled = {"party": 2, "level": 40,
               "prefers": [CharacterClass.SUSTAIN, CharacterClass.SUSTAIN]}
    one = dc.fit_multiplier(doubled, [_Fake(CharacterClass.SUSTAIN),
                                      _Fake(CharacterClass.DPS)])
    two = dc.fit_multiplier(doubled, [_Fake(CharacterClass.SUSTAIN),
                                      _Fake(CharacterClass.SUSTAIN)])
    if not two > one:
        failures.append(
            f"a contract wanting two Sustains pays the same for one ({one:.2f}) as "
            f"for two ({two:.2f}) -- class matching is using a set, not a multiset")

    # ---- 2. the lock ------------------------------------------------
    #
    # THE CONTRACT IS CHOSEN, NOT DRAWN FROM THE BOARD.
    #
    # This used to take whatever D.board() offered, and the board is
    # seeded on an 8-hour window -- so which characters ended up locked,
    # and therefore whether they overlapped the saved preset, changed
    # depending on the hour the check ran. It passed for a day and then
    # failed, and the bug it was meant to catch (load_preset writing
    # slot.character_id directly, straight past the lock) had been there
    # the whole time.
    #
    # A fixed four-character contract makes the overlap certain. A check
    # whose result depends on the clock is not a check.
    target = max(dc.CONTRACTS, key=lambda c: c["party"])
    crew = [m.id for m in mine[:target["party"]]]

    # SEAT AND SAVE THE PRESET **BEFORE** DISPATCHING, which is the only
    # order that tests anything.
    #
    # The first version saved the preset after the send, and by then
    # set_squad_slot was already refusing to seat the dispatched crew --
    # so the preset contained only free characters and loading it could
    # not possibly leak. Reverting the fix in squad_service left the
    # check green, which is how it was found.
    #
    # A preset is a snapshot of a squad from BEFORE the contract went
    # out. That is the real situation, and it is the only one where
    # load_preset can put somebody back who should be away.
    for index, member in enumerate(mine[:target["party"]]):
        character_service.set_squad_slot(db, player, index, member)
    db.commit()
    preset = squad_service.save_preset(db, player, "pre-dispatch")

    row, error = D.send(db, player, target["id"], crew)
    if row is None:
        failures.append(f"a valid dispatch was refused: {error}")
    else:
        busy = D.busy_character_ids(db, player)
        if set(crew) - busy:
            failures.append("a dispatched character is not marked busy")

        # the direct path
        ok, message = character_service.set_squad_slot(
            db, player, 1, db.get(PlayerCharacter, crew[0]))
        if ok:
            failures.append(
                "a character out on a contract was seated in the squad -- the lock "
                "is the only thing making dispatch a decision")

        # THE INDIRECT PATH, which is the one that matters. The preset
        # saved above still names the crew that is now away, and loading
        # it must not put them back. load_preset writes slot.character_id
        # directly rather than going through set_squad_slot, so it does
        # not inherit that function's lock and needs its own.
        #
        # No try/except around any of this. Swallowing exceptions here
        # would turn "load_preset crashed" into a pass, which is the same
        # class of blind spot as the ordering bug above.
        squad_service.load_preset(db, player, preset.id)

        from bot.database.models.character_model import SquadSlot
        seated = {s.character_id for s in
                  db.query(SquadSlot).filter_by(player_id=player.id).all()}
        leaked = seated & D.busy_character_ids(db, player)
        if leaked:
            failures.append(
                f"loading a squad preset re-seated {len(leaked)} dispatched "
                f"character(s) -- the lock is enforced in set_squad_slot but "
                f"load_preset writes slot.character_id directly and bypasses it")

        # double-booking
        _, second = D.send(db, player, target["id"], crew)
        if not second:
            failures.append("the same characters were sent on two contracts at once")

        # ---- claiming ------------------------------------------------
        _, early = D.claim(db, player, row.id)
        if not early:
            failures.append("a contract was claimable before it finished")

        row.ends_at = D.now() - dt.timedelta(minutes=1)
        db.commit()
        rewards, error = D.claim(db, player, row.id)
        if error or not rewards:
            failures.append(f"a finished contract paid nothing: {error}")
        if set(crew) & D.busy_character_ids(db, player):
            failures.append("characters are still marked busy after claiming")

        # claiming twice
        again, _ = D.claim(db, player, row.id)
        if again:
            failures.append("a contract paid out twice")

    # ---- you can always still field a squad ---------------------------
    #
    # Sending a four-character contract while owning four characters
    # emptied the squad outright, and get_squad() returning [] breaks
    # every combat entry point in the game. The player could not fight
    # until the contract returned.
    solo = player_service.get_or_create_player(db, 90_002, "ThinRoster")
    character_service.ensure_avatar_character(db, solo)
    for template in templates[:3]:
        db.add(PlayerCharacter(player_id=solo.id, template_id=template.id,
                               level=30, talents=[], dupe_count=1))
    thin_base = db.query(PlayerBase).filter_by(player_id=solo.id).first()
    if thin_base is None:
        thin_base = PlayerBase(player_id=solo.id)
        db.add(thin_base)
    thin_base.hq_level = 8
    db.commit()

    everyone = [c.id for c in db.query(PlayerCharacter)
                .filter_by(player_id=solo.id).all()]
    four = max(dc.CONTRACTS, key=lambda c: c["party"])
    if len(everyone) == four["party"]:
        row_all, error_all = D.send(db, solo, four["id"], everyone)
        if row_all is not None:
            failures.append(
                "a player was allowed to send their entire roster -- get_squad() "
                "then returns nothing and no fight can be started at all")
        elif "everybody" not in error_all.lower():
            failures.append(
                f"sending the whole roster was refused, but with an unhelpful "
                f"reason: {error_all!r}")

    # ---- slots track the HQ ------------------------------------------
    for level in range(1, 10):
        base.hq_level = level
        db.commit()
        expected = dc.slots_for_hq(level)
        _, total = D.slots(db, player)
        if total != expected:
            failures.append(
                f"HQ level {level} gives {total} slots, expected {expected}")
    if dc.slots_for_hq(dc.DISPATCH_UNLOCK_HQ_LEVEL - 1) != 0:
        failures.append("dispatch has slots below its own unlock level")

    db.close()

    print(f"contracts : {len(dc.CONTRACTS)}  "
          f"({sum(1 for c in dc.CONTRACTS if c['party'] == 1)} solo, "
          f"{sum(1 for c in dc.CONTRACTS if c['party'] == 4)} full-squad)")
    values = [_value_per_character_hour(c) for c in dc.CONTRACTS]
    print(f"value band: {min(values):.0f}-{max(values):.0f} gold-equivalent per "
          f"character-hour (limit {MIN_VALUE_PER_CHARACTER_HOUR}-"
          f"{MAX_VALUE_PER_CHARACTER_HOUR}, spread {max(values)/min(values):.1f}x)")
    print(f"ceiling   : {ceiling:,.0f} gold/day theoretical "
          f"(limit {MAX_THEORETICAL_GOLD_PER_DAY:,})")
    print("slots     : " + ", ".join(
        f"HQ{level}={dc.slots_for_hq(level)}" for level in (2, 3, 4, 6, 8)))

    if failures:
        print()
        for failure in dict.fromkeys(failures):
            print(f"  FAIL  {failure}")
        return 1
    print("\nOK -- payouts are inside the band, the combat lock holds through "
          "presets, and the gacha is untouched.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
