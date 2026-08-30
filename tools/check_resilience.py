"""
The safety nets that keep the bot answering are actually connected.

    python -m tools.check_resilience

WHY THIS CHECK EXISTS. Everything it asserts is defensive machinery --
error handlers, an error log, a loop watchdog. Defensive machinery has a
specific and nasty failure mode: it is only exercised when something goes
wrong, so if it is broken it stays broken and looks fine, and the day you
need it is the day you find out. Nothing else in the suite tests it,
because from the outside a bot with a dead watchdog behaves exactly like
a bot with a working one.

Every item here corresponds to a real production failure from this bot's
own logs:

    TypeError: expected view parameter ... not NoneType
        /adventure died AFTER deferring, because followup.send rejects
        view=None while response.send_message accepts it.

    TypeError: unsupported operand type(s) for +: 'bool' and 'str'
        three map tiles authored with `"repeat": True` where the code
        expects the repeat line.

    Can't keep up, shard ID None websocket is 20.4s behind
    interaction expired before component ... could edit
        the loop blocked by synchronous work; the interaction token dies
        at 3 seconds and the player sees a command that did nothing.

THE WATCHDOG IS TESTED BY ACTUALLY BLOCKING THE LOOP, not by checking
that the module imports. Two of its three designs fired at the right
moments and named the wrong thing, and both looked correct in review --
a ContextVar cannot be read across tasks, and "what is in flight" is
already empty by the time the loop resumes. Only running it catches that.
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import time


def main() -> int:
    sys.path.insert(0, ".")
    os.environ.setdefault(
        "DATABASE_URL", "sqlite:///" + tempfile.mktemp(suffix=".db"))
    # Keep the check's own log noise out of the real log directory.
    os.environ.setdefault("CASCADEBOT_LOG_DIR", tempfile.mkdtemp())

    failures: list[str] = []

    # ---- 1. responses.send tolerates view=None -----------------------
    #
    # TESTED THROUGH send(), NOT through the helper it calls. The first
    # version of this check asserted `_drop_none({"view": None}) == {}`,
    # which passes whether or not send() ever calls it -- and sabotaging
    # the call site left the check green. Presence is not effect, in a
    # check whose entire subject is presence not being effect.
    #
    # So this drives the real function against a stand-in interaction
    # that raises exactly as discord.py's followup.send does.
    from bot.utils import responses

    class _Followup:
        def __init__(self):
            self.kwargs = None

        async def send(self, *args, **kwargs):
            if "view" in kwargs and kwargs["view"] is None:
                raise TypeError(
                    "expected view parameter to be of type View or LayoutView, "
                    "not NoneType")
            self.kwargs = kwargs

    class _Response:
        def is_done(self):
            return True            # deferred, which every command here is

    class _Interaction:
        def __init__(self):
            self.response = _Response()
            self.followup = _Followup()
            self.command = None

    sent = _Interaction()
    try:
        asyncio.run(responses.send(sent, embed="E", view=None))
    except TypeError as exc:
        failures.append(
            f"responses.send still forwards view=None to followup.send ({exc}) -- "
            f"any command rendering a viewless screen dies after its defer. This "
            f"killed /adventure in production")

    kept = _Interaction()
    asyncio.run(responses.send(kept, view="V"))
    if (kept.followup.kwargs or {}).get("view") != "V":
        failures.append(
            "a real view is being dropped, which would remove every button from "
            "every screen")

    # ---- 2. map content is the type the renderer expects -------------
    #
    # Authored data with the wrong type crashes at render, in front of a
    # player, on a code path no other check walks.
    import bot.game.story.map_config as map_config

    wrong: list[str] = []

    def walk(node, path):
        if isinstance(node, dict):
            for key, value in node.items():
                if key in ("text", "repeat", "name", "emoji", "on_solve") \
                        and not isinstance(value, (str, type(None))):
                    wrong.append(f"{path}.{key} is {type(value).__name__}")
                walk(value, f"{path}.{key}")
        elif isinstance(node, (list, tuple)):
            for index, value in enumerate(node):
                walk(value, f"{path}[{index}]")

    for name in dir(map_config):
        if name.isupper():
            walk(getattr(map_config, name), name)
    if wrong:
        failures.append(
            f"{len(wrong)} map tile field(s) are the wrong type and will crash "
            f"the renderer: {wrong[:5]}")

    # ...and the renderer refuses to pass one on even if it appears.
    from bot.services import map_service

    class _Story:
        read_tiles: dict = {}

    text, _, _ = map_service.npc_line(None, _Story(), "a", "c",
                                      {"lines": [], "repeat": True})
    if not isinstance(text, str):
        failures.append(
            f"npc_line returned {type(text).__name__} for a boolean `repeat` -- "
            f"story.py concatenates this to a string and dies")

    # ---- 3. the error log is real and captures tracebacks -------------
    from bot.utils.logger import error_log_path, get_logger

    log = get_logger("resilience-probe")
    marker = f"probe-{time.time()}"
    try:
        raise RuntimeError(marker)
    except RuntimeError:
        log.exception("probe traceback")
    log.info("this INFO line must NOT reach errors.log")

    path = error_log_path()
    if not path.exists():
        failures.append(f"no error log was written at {path}")
    else:
        body = path.read_text(encoding="utf-8", errors="replace")
        if marker not in body:
            failures.append("the traceback did not reach errors.log")
        if "must NOT reach errors.log" in body:
            failures.append(
                "INFO lines are going into errors.log -- the file stops being a "
                "list of things that went wrong and becomes another console")

    # discord.py's own logger must be captured: a CommandInvokeError is
    # logged by discord.app_commands, not by anything under `cascadebot`,
    # so a handler attached only to our tree would miss every command
    # crash the bot has ever had.
    import logging

    discord_marker = f"discord-probe-{time.time()}"
    logging.getLogger("discord.app_commands.tree").error(discord_marker)
    if path.exists() and discord_marker not in path.read_text(
            encoding="utf-8", errors="replace"):
        failures.append(
            "discord.py's loggers are not captured -- command crashes are logged "
            "under `discord.*` and would never reach the file")

    # ---- 4. the watchdog actually catches a blocked loop --------------
    from bot.utils import watchdog

    async def probe() -> list[str]:
        seen: list[str] = []
        real_warning, real_error = watchdog.logger.warning, watchdog.logger.error

        def capture(message, *args, **kwargs):
            seen.append(message % args if args else message)

        watchdog.logger.warning = capture
        watchdog.logger.error = capture
        task = watchdog.start(None)
        try:
            await asyncio.sleep(0.4)
            with watchdog.track("/probe-command (user 1)"):
                time.sleep(1.6)          # synchronous, like every DB call
            await asyncio.sleep(0.6)
        finally:
            task.cancel()
            watchdog.logger.warning = real_warning
            watchdog.logger.error = real_error
        return seen

    seen = asyncio.run(probe())
    blocked = [line for line in seen if "event loop blocked" in line]
    if not blocked:
        failures.append(
            "the watchdog did not report a 1.6s synchronous block -- the one "
            "thing it exists to catch")
    elif not any("/probe-command" in line for line in blocked):
        failures.append(
            f"the watchdog reported a block but could not name what caused it: "
            f"{blocked[0][:110]!r}. Both earlier designs failed exactly here "
            f"while looking correct")

    print("responses  : view=None dropped, real views preserved")
    print(f"map data   : {len(wrong)} wrong-typed field(s)")
    print(f"error log  : {path}")
    print(f"watchdog   : {len(blocked)} block(s) reported, "
          f"named={'yes' if any('/probe-command' in b for b in blocked) else 'NO'}")

    if failures:
        print()
        for failure in dict.fromkeys(failures):
            print(f"  FAIL  {failure}")
        return 1
    print("\nOK -- the bot answers viewless screens, refuses bad map data, logs "
          "every error to disk, and names what blocks the loop.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
