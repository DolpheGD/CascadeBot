"""
Timezone handling for persisted datetimes.

Every DateTime column in this project is declared `DateTime(timezone=True)`,
but SQLite has no native timezone-aware type -- it stores the value and
hands it back *naive*. So anything read off a model and compared against
`datetime.now(timezone.utc)` will raise
`TypeError: can't subtract offset-naive and offset-aware datetimes`
unless it's normalized first.

`as_utc()` is that normalization, in one place. It used to be copy-pasted
as a three-line `if x.tzinfo is None: x = x.replace(tzinfo=utc)` block
across daily/domain/harvester/quest/base services -- same fix, five
different files, easy to forget in the sixth.

Note this *assumes* a naive value is already UTC rather than converting
it, which is correct here because everything is written with
`datetime.now(timezone.utc)` (or `func.now()` on a UTC-configured engine)
in the first place -- the tzinfo is only lost on the way back out.
"""

from __future__ import annotations

import datetime as dt


def utcnow() -> dt.datetime:
    """Timezone-aware "now". Use this instead of `datetime.utcnow()`, which
    returns a naive value and is deprecated in 3.12+."""
    return dt.datetime.now(dt.timezone.utc)


def as_utc(value: dt.datetime | None) -> dt.datetime | None:
    """Returns `value` guaranteed timezone-aware in UTC. A naive value is
    assumed to already be UTC and simply tagged as such; an aware value is
    converted. Passes None straight through so callers can handle
    nullable columns without an extra guard."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=dt.timezone.utc)
    return value.astimezone(dt.timezone.utc)
