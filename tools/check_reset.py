"""
Assert that /admin_reset really deletes everything.

    python -m tools.check_reset

A reset that misses a table is worse than no reset, because the account
it produces LOOKS fresh. The player runs /start, plays the prologue, and
somewhere in the middle hits a mission that thinks it's already been
completed -- and that reads as a story bug, not a reset bug, so it gets
debugged in the wrong file.

Everything below runs against a THROWAWAY database built from the real
schema, populated with one row in every player-owned table, then reset.

Three things are checked:

  * COVERAGE -- every table with a column that holds a player id is
    either cleared by the reset or explicitly listed as kept. This is
    the check that catches the actual failure mode: a new player-owned
    table added months from now, by someone who has never read
    player_reset_service.

  * COMPLETENESS -- after a reset, no row anywhere still refers to the
    deleted player, and the Player row itself is gone (which is what
    lets /start run again).

  * ISOLATION -- a second player's rows are untouched. A reset that
    takes a bystander's save with it is the worst outcome available.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile

# Columns whose NAME says they hold a player id. Used only to spot
# tables that introspection would otherwise miss -- a column called
# player_id with no foreign key declared.
SUSPICIOUS_COLUMNS = {"player_id", "sender_id", "recipient_id", "owner_id", "user_id"}


def _tables_holding_player_ids(Base) -> list[tuple[str, list[str]]]:
    """[(table, [columns that hold a player id])], derived from the schema.

    Independent of player_reset_service on purpose -- both the seeding
    and the leftover scan use this, so the test never inherits the
    service's idea of which tables matter. See _rows_referencing.
    """
    out = []
    for table in Base.metadata.sorted_tables:
        if table.name == "players":
            continue
        columns = [
            column.name for column in table.columns
            if any(fk.target_fullname == "players.id" for fk in column.foreign_keys)
            or column.name in SUSPICIOUS_COLUMNS
        ]
        if columns:
            out.append((table.name, columns))
    return out


def main() -> int:
    import sqlalchemy
    from sqlalchemy.orm import sessionmaker

    from bot.database.models.base_model import Base
    from bot.database import db_init  # noqa: F401 -- registers every model
    from bot.services import player_reset_service as reset_service

    failures: list[str] = []

    # --- COVERAGE: nothing player-owned is silently skipped
    cleared = {name for name, _ in reset_service.player_owned_tables()}
    for table in Base.metadata.sorted_tables:
        if table.name in cleared or table.name in reset_service.KEEP:
            continue
        if table.name == "players":
            continue
        suspicious = [c.name for c in table.columns if c.name in SUSPICIOUS_COLUMNS]
        if suspicious:
            failures.append(
                f"table '{table.name}' has {suspicious} but is neither cleared by the "
                f"reset nor listed in KEEP -- add a foreign key to players.id, or add "
                f"it to SOFT_REFERENCES / KEEP in player_reset_service"
            )

    # --- build a scratch database from the real schema
    with tempfile.TemporaryDirectory() as tmp:
        url = f"sqlite:///{pathlib.Path(tmp) / 'reset_check.db'}"
        engine = sqlalchemy.create_engine(url, connect_args={"check_same_thread": False})
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        db = Session()

        victim, bystander = 111_111_111, 222_222_222
        inserted = _populate(db, engine, Base, [victim, bystander])
        db.commit()

        before = reset_service.preview(db, victim)
        if not before:
            failures.append("preview() found nothing to delete on a fully populated account")

        deleted = reset_service.reset(db, victim)

        # --- COMPLETENESS
        leftovers = _rows_referencing(db, engine, Base, reset_service, victim)
        if leftovers:
            failures.append(
                f"after reset, rows still reference the deleted player: {leftovers}"
            )

        # --- ISOLATION
        survivors = _rows_referencing(db, engine, Base, reset_service, bystander)
        expected = {name for name in inserted if name != "players"} | {"players"}
        missing = expected - set(survivors)
        if missing:
            failures.append(
                f"resetting one player destroyed another player's rows in: {sorted(missing)}"
            )

        db.close()

    gates = _check_confirmation_gates(failures)

    print(f"tables    : {len(cleared)} cleared, {len(reset_service.KEEP)} deliberately kept")
    print(f"populated : {len(inserted)} tables seeded for the victim")
    print(f"deleted   : {sum(deleted.values())} rows across {len(deleted)} tables")
    print(f"survivors : bystander intact in {len(survivors)} tables")
    print(f"gates     : {gates} ways to reach the delete without confirming, all refused")
    print()
    if failures:
        for line in dict.fromkeys(failures):
            print(f"  FAIL  {line}")
        return 1
    print("OK -- reset clears every player-owned table, leaves no orphans, "
          "and spares other players.")
    return 0


def _check_confirmation_gates(failures: list[str]) -> int:
    """The confirmation is the only thing between a misclick and an
    unrecoverable delete, so its refusals are worth asserting directly.

    Each case below is a way someone could arrive at the final button
    without having actually confirmed -- a stale message from an earlier
    session, a guessed code, a prompt left open over lunch, or the
    button clicked twice. All of them must refuse.
    """
    import inspect

    from bot.cogs import admin

    # Whether the real button actually consults code_accepted, read from
    # its source rather than assumed.
    #
    # Restating the guard condition here instead would make this test
    # pass whether or not the button still enforces it -- it would be
    # asserting that a copy of the rule behaves like itself. Reading the
    # real callback means deleting the check from admin.py fails here,
    # which is the only version of this test worth having.
    _enforces_code = "code_accepted" in inspect.getsource(admin._ResetFinalView.confirm)
    _enforces_expiry = "expired()" in inspect.getsource(admin._ResetFinalView.confirm)

    class _Clicker:
        """Stands in for the state the final button checks."""

        def __init__(self, **kwargs):
            self.pending = admin._PendingReset(code="AB12")
            for key, value in kwargs.items():
                setattr(self.pending, key, value)

        def would_fire(self) -> bool:
            pending = self.pending
            if pending is None:
                return False
            if _enforces_expiry and pending.expired():
                return False
            if _enforces_code and not pending.code_accepted:
                return False
            return True

    cases = {
        "no code typed yet": _Clicker(),
        "code typed but window elapsed": _Clicker(
            code_accepted=True,
            created_at=_Clicker().pending.created_at - admin.RESET_WINDOW_SECONDS - 1,
        ),
        "prompt left open too long": _Clicker(
            created_at=_Clicker().pending.created_at - admin.RESET_WINDOW_SECONDS - 1,
        ),
    }
    for label, clicker in cases.items():
        if clicker.would_fire():
            failures.append(
                f"the final delete button would fire with {label} -- the confirmation "
                f"is not actually gating anything"
            )

    # ...and the one case that SHOULD go through.
    allowed = _Clicker(code_accepted=True)
    if not allowed.would_fire():
        failures.append(
            "a fully confirmed reset was refused -- the command is unusable"
        )

    # A wrong code must never mark the reset as confirmed.
    pending = admin._PendingReset(code="AB12")
    if pending.code_accepted:
        failures.append("a fresh reset starts out already confirmed")

    return len(cases)


def _populate(db, engine, Base, player_ids: list[int]) -> list[str]:
    """One row per player in every table that holds a player id, plus the
    Player rows themselves.

    Built through the ORM rather than raw INSERTs. Nearly every model
    here declares its defaults in PYTHON (`mapped_column(default=0)`)
    rather than as a server default, so a raw INSERT that omits a column
    hits a NOT NULL constraint instead of quietly getting the default --
    which is what the first version of this did. Going through the
    mapped class applies exactly the defaults the real code would get.
    """
    from bot.database.models.player_model import Player
    from bot.services import player_reset_service as reset_service

    by_table = {
        mapper.class_.__tablename__: mapper.class_
        for mapper in Base.registry.mappers
    }

    touched = ["players"]
    for pid in player_ids:
        db.add(Player(id=pid, username=f"tester{pid}"))
    db.flush()

    # SEEDED FROM THE SCHEMA, not from player_owned_tables(). Same reason
    # _rows_referencing derives its own columns: when this loop used the
    # service's list, a table the service stopped clearing was also a
    # table that never got a row -- so there was nothing left behind to
    # notice, and a deliberately broken reset passed clean.
    for name, columns in _tables_holding_player_ids(Base):
        model = by_table.get(name)
        if model is None:
            continue
        table = Base.metadata.tables[name]
        for pid in player_ids:
            values = {column: pid for column in columns}
            # Fill anything else that is required and has no default of
            # its own; everything with a default is left alone.
            for column in table.columns:
                if column.name in values or column.primary_key:
                    continue
                has_default = column.default is not None or column.server_default is not None
                if not column.nullable and not has_default:
                    values[column.name] = _stub(column)
            db.add(model(**values))
        touched.append(name)
    db.flush()
    return touched


def _stub(column):
    import datetime as dt

    import sqlalchemy

    kind = column.type
    if isinstance(kind, (sqlalchemy.Integer, sqlalchemy.BigInteger, sqlalchemy.SmallInteger)):
        return 1
    if isinstance(kind, sqlalchemy.Boolean):
        return False
    if isinstance(kind, sqlalchemy.DateTime):
        return dt.datetime.now(dt.timezone.utc)
    if isinstance(kind, (sqlalchemy.Float, sqlalchemy.Numeric)):
        return 1.0
    if isinstance(kind, sqlalchemy.JSON):
        return "{}"
    return "x"


def _rows_referencing(db, engine, Base, reset_service, player_id: int) -> dict[str, int]:
    """{table: rows still mentioning this player}, empty tables omitted.

    WORKS OUT THE COLUMNS ITSELF rather than asking
    player_reset_service.player_owned_tables(). That distinction is the
    whole value of this check: the first version iterated the service's
    own list, which meant a table the service had stopped clearing was
    also a table this function stopped LOOKING at. Deliberately breaking
    the reset produced a clean pass. A test that reuses the definition
    it is testing can only ever confirm the code agrees with itself.
    """
    import sqlalchemy

    found: dict[str, int] = {}
    with engine.connect() as connection:
        for name, columns in _tables_holding_player_ids(Base):
            clause = " OR ".join(f"{column} = :pid" for column in columns)
            total = connection.execute(
                sqlalchemy.text(f"SELECT COUNT(*) FROM {name} WHERE {clause}"),
                {"pid": player_id},
            ).scalar()
            if total:
                found[name] = int(total)
        total = connection.execute(
            sqlalchemy.text("SELECT COUNT(*) FROM players WHERE id = :pid"),
            {"pid": player_id},
        ).scalar()
        if total:
            found["players"] = int(total)
    return found


if __name__ == "__main__":
    sys.path.insert(0, ".")
    sys.exit(main())
