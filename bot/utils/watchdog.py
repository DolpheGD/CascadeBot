"""
Event-loop watchdog: turns "the bot feels slow" into a named line in a log.

THE PROBLEM THIS EXISTS FOR, taken from a real production log:

    WARNING  discord.gateway Can't keep up, shard ID None websocket is
             20.4s behind.
    interaction expired before component on 704530416475832342 could edit
    interaction expired before component on 704530416475832342 could reply

Those three lines are the same fault wearing different hats. Discord
gives an interaction THREE SECONDS to be acknowledged; if the event loop
is busy, the acknowledgement never goes out, the token dies, and the
player sees a command that did nothing. The gateway warning is the same
blockage seen from the other side.

WHAT IS ACTUALLY BLOCKING. Every database call in this bot is
synchronous SQLAlchemy executed directly inside an async handler --
around a hundred and twenty `SessionLocal()` blocks across the cogs --
plus combat resolution, map generation and loot rolls, which are pure
CPU. None of that yields. While any of it runs, the loop cannot send a
heartbeat, cannot answer an interaction, and cannot read the socket.

That is a large refactor to fix properly (thread executors, or an async
driver) and not something to attempt blind. What this module does is the
step that has to come first: MAKE IT VISIBLE. A blocked loop currently
produces a discord.py warning that names no cause; after this it produces

    WARNING  cascadebot.watchdog  event loop blocked for 4.２s
             during /adventure (user 704530416475832342)

which points at the command to fix.

HOW IT WORKS, and why it is this and not asyncio's debug mode.
asyncio has `loop.slow_callback_duration`, but the warning it drives only
fires when `loop.set_debug(True)`, and full debug mode adds per-callback
overhead to a bot that is already CPU-bound. This is a single coroutine
that sleeps in short ticks and measures how late each wake-up was. If a
tick that asked for 0.25s took 4 seconds, the loop was blocked for the
difference, and nothing else needs instrumenting to know that.

ATTRIBUTION IS BY TIME OVERLAP, and it took three attempts to get right
-- see the long note above `_recent`. The short version: a ContextVar
cannot be read across tasks, and "whatever is in flight" is empty by the
time the loop resumes, so both of the obvious designs report every block
as "background work" while looking completely correct. What works is
recording each piece of work as a window and asking which windows
overlapped the blocked one.
"""

from __future__ import annotations

import asyncio
import contextvars
import time

from bot.utils.logger import get_logger

logger = get_logger("watchdog")

# How often the watchdog wakes. Short enough to catch a block inside one
# interaction's 3-second budget, long enough to be free: this is one
# timer callback four times a second.
TICK_SECONDS = 0.25

# A tick this much later than requested means the loop was blocked.
# 1.0s is deliberately well under Discord's 3s interaction deadline --
# the point is to catch the blocks that are ON THE WAY to breaking an
# interaction, not only the ones that already did.
BLOCK_THRESHOLD_SECONDS = 1.0

# Anything past this is logged at ERROR rather than WARNING: at three
# seconds an interaction token is already dead, so it is not a warning
# about future trouble, it is a report of a failure that happened.
SEVERE_THRESHOLD_SECONDS = 3.0

# Everything currently in flight, keyed by the task running it.
#
# A CONTEXTVAR WAS THE FIRST DESIGN AND IT DOES NOT WORK HERE. The
# reasoning was sound in isolation -- handlers interleave, so a module
# global would name whichever command started last -- but ContextVars do
# not propagate ACROSS tasks. asyncio.create_task snapshots the context
# at creation, so the watchdog's own task holds a frozen copy and can
# never observe a set() made later by a command's task.
#
# It failed exactly as quietly as that implies: the watchdog fired at the
# right times with the right severity and reported every single block as
# "no command (background work)", including ones raised inside an
# explicit track() block. Correct-looking output, no error, no cause
# named -- caught by reading the test output rather than by anything
# going wrong.
#
# A dict keyed by asyncio task is what the ContextVar was reaching for:
# it survives across tasks because it is ordinary module state, and it
# still distinguishes interleaved handlers because the key is the task.
_in_flight: dict[object, str] = {}

# Kept only so `watchdog.current_action.set(...)` in older call sites is
# not a NameError. It is not read by the watchdog -- see above.
current_action: contextvars.ContextVar[str] = contextvars.ContextVar(
    "current_action", default="")


def note(label: str) -> None:
    """Name the work this task is doing, until it finishes.

    For call sites that are not a neat block -- a command handler whose
    work continues past any one `with`. The entry is dropped when the
    task ends, so nothing leaks.
    """
    try:
        task = asyncio.current_task()
    except RuntimeError:
        return
    if task is None:
        return
    _in_flight[task] = label
    task.add_done_callback(_in_flight.pop)


class track:
    """Context manager naming the work in progress, for watchdog reports.

        with track(f"/{name} (user {interaction.user.id})"):
            ...
    """

    __slots__ = ("_label", "_task", "_previous", "_started")

    def __init__(self, label: str):
        self._label = label
        self._task = None
        self._previous = None
        self._started = 0.0

    def __enter__(self):
        self._started = time.perf_counter()
        try:
            self._task = asyncio.current_task()
        except RuntimeError:
            self._task = None
        if self._task is not None:
            self._previous = _in_flight.get(self._task)
            _in_flight[self._task] = self._label
        return self

    def __exit__(self, *exc):
        ended = time.perf_counter()
        if self._task is not None:
            if self._previous is None:
                _in_flight.pop(self._task, None)
            else:
                _in_flight[self._task] = self._previous
        # Remembered whether or not it was slow -- the watchdog decides
        # what counts as slow, and it needs the window to attribute a
        # block that this block caused.
        _remember(self._label, self._started, ended)
        return False


# Recently-finished work, as (label, started, ended) windows.
#
# THE SECOND DESIGN WAS ALSO WRONG, in a way that only shows up when you
# read the output. Reporting whatever is IN FLIGHT cannot work for the
# commonest case: the handler blocks, the `with` block exits, and only
# THEN does the loop get to run the watchdog. By that point the entry has
# been removed and every block is attributed to "background work" again
# -- which is precisely what the first (ContextVar) version did, for a
# completely different reason.
#
# Two wrong designs with identical symptoms is a good argument for
# reading the output rather than the code.
#
# Attribution is therefore by TIME OVERLAP: the watchdog knows the window
# it was blocked across, and anything whose own window overlapped it is a
# candidate. That covers work still running AND work that finished during
# the block, which between them is every case.
_recent: list[tuple[str, float, float]] = []
_RECENT_KEEP = 32


def _remember(label: str, started: float, ended: float) -> None:
    _recent.append((label, started, ended))
    if len(_recent) > _RECENT_KEEP:
        del _recent[:-_RECENT_KEEP]


def _describe_block(window_start: float, window_end: float) -> str:
    """Whatever was running during the blocked window."""
    labels: list[str] = []

    # Still running: it blocked and has not returned yet.
    labels.extend(dict.fromkeys(_in_flight.values()))

    # Finished during the block: overlap test against the window.
    for label, started, ended in reversed(_recent):
        if ended >= window_start and started <= window_end and label not in labels:
            labels.append(label)

    if not labels:
        return "no command (background work)"
    if len(labels) == 1:
        return labels[0]
    return f"{labels[0]} (+{len(labels) - 1} other candidate(s))"


async def _loop(stop: asyncio.Event) -> None:
    worst = 0.0
    while not stop.is_set():
        started = time.perf_counter()
        try:
            await asyncio.wait_for(stop.wait(), timeout=TICK_SECONDS)
            return                      # asked to stop
        except asyncio.TimeoutError:
            pass
        late = (time.perf_counter() - started) - TICK_SECONDS
        if late < BLOCK_THRESHOLD_SECONDS:
            continue

        # WHAT WAS RUNNING is read AFTER the block, which is the best
        # available answer rather than a perfect one: the blocking
        # callback has already finished by the time this coroutine gets
        # to run again. A command handler that blocked for seconds is
        # normally still in flight (it blocked, it did not finish), and
        # when nothing is, the message says "background work" rather
        # than guessing.
        during = _describe_block(started, time.perf_counter())
        level = logger.error if late >= SEVERE_THRESHOLD_SECONDS else logger.warning
        level("event loop blocked for %.1fs during %s -- interactions cannot be "
              "answered while this runs (Discord's deadline is 3s)", late, during)
        if late > worst:
            worst = late
            logger.info("new worst block this session: %.1fs", worst)


def start(bot) -> asyncio.Task:
    """Begin watching. Returns the task so a caller can cancel it."""
    stop = asyncio.Event()
    task = asyncio.create_task(_loop(stop), name="cascadebot-watchdog")
    task._cascadebot_stop = stop        # type: ignore[attr-defined]
    logger.info("event-loop watchdog running (warns over %.1fs, errors over %.1fs)",
                BLOCK_THRESHOLD_SECONDS, SEVERE_THRESHOLD_SECONDS)
    return task
