"""
Assert that a slow or dead interaction can't crash a command.

    python -m tools.check_interactions

Discord allows THREE SECONDS to make the first response to an
interaction. Every command in this bot queries SQLite synchronously on
the event loop before replying, and SQLite takes a database-wide write
lock -- so any command can block past the deadline while an expedition
or a raid attack commits. When that happened the token died and the
handler crashed with 404 Unknown interaction (10062), which is what
took out /gift, /squad and the inventory paginator in one evening.

Three structural properties are checked, plus the behaviour of the helpers
that make them safe. Both are things a future command can silently get
wrong, which is the only reason this file exists:

  * every slash command DEFERS as its first statement, before it opens a
    database session -- that is what turns the 3-second budget into 15
    minutes

  * no cog reaches for interaction.response.send_message /
    edit_message directly, because those are the calls that raise once
    the response slot has been spent by that defer

  * no command defers TWICE -- the second call raises
    InteractionResponded, which is not an HTTPException and so is caught
    by nothing at all

The helpers are then exercised against a fake interaction that fails the
same way Discord's does.
"""

from __future__ import annotations

import ast
import asyncio
import logging
import pathlib
import sys

COGS = pathlib.Path("bot/cogs")

# Commands whose primary reply is private, and which must therefore
# defer privately -- a public defer would leave a visible "thinking..."
# placeholder attached to an answer nobody else should see.
EPHEMERAL_PRIMARY = {"admin_boosterkit", "admin_reset", "help", "sell_rarity",
                     "gifts", "vote"}


def _commands_in(path: pathlib.Path):
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if not isinstance(node, ast.AsyncFunctionDef):
            continue
        decorators = ast.unparse(node.decorator_list) if node.decorator_list else ""
        if "app_commands.command" in decorators:
            yield node


def check_every_command_defers(failures: list[str]) -> int:
    total = 0
    for path in sorted(COGS.glob("*.py")):
        for node in _commands_in(path):
            total += 1
            body = list(node.body)
            # Skip a docstring if the command has one.
            if body and isinstance(body[0], ast.Expr) \
                    and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                body = body[1:]
            first = ast.unparse(body[0]) if body else ""
            if not first.startswith("await responses.defer("):
                failures.append(
                    f"{path.name} /{node.name} does not defer first (starts with "
                    f"{first[:50]!r}) -- it will die on a slow query"
                )
                continue
            wants_private = node.name in EPHEMERAL_PRIMARY
            is_private = "ephemeral=True" in first
            if wants_private != is_private:
                failures.append(
                    f"{path.name} /{node.name} defers with ephemeral={is_private}, "
                    f"but its primary reply is {'private' if wants_private else 'public'}"
                )
    return total


def check_no_raw_responses(failures: list[str]) -> None:
    for path in sorted(COGS.glob("*.py")):
        source = path.read_text()
        for call in ("response.send_message(", "response.edit_message("):
            if call in source:
                line = next(i + 1 for i, text in enumerate(source.splitlines())
                            if call in text)
                failures.append(
                    f"{path.name}:{line} calls {call} directly -- it raises once the "
                    f"command has deferred; use responses.send / responses.edit"
                )


def check_no_double_defer(failures: list[str]) -> None:
    """A command that defers TWICE raises InteractionResponded.

    Worth its own check because that exception is not an HTTPException,
    so neither responses.py nor the tree's error handler absorbs it --
    it surfaces as a raw crash. It is also easy to reintroduce: adding
    the automatic defer left two hand-written `ctx.response.defer()`
    calls behind in commands that had always had one, and both would
    have crashed on first use.

    Component callbacks may still call response.defer() directly -- they
    are never auto-deferred, so theirs is the only one.
    """
    for path in sorted(COGS.glob("*.py")):
        tree = ast.parse(path.read_text())
        for node in _commands_in(path):
            body = ast.unparse(node)
            if "response.defer(" in body:
                failures.append(
                    f"{path.name} /{node.name} calls response.defer() directly on top of "
                    f"responses.defer() -- the second raises InteractionResponded, which "
                    f"nothing catches"
                )


def check_helpers_survive_a_dead_token(failures: list[str]) -> None:
    import discord

    from bot.utils import responses

    def dead(code: int) -> discord.HTTPException:
        class _Response:
            status = 404
            reason = "Not Found"
        return discord.NotFound(_Response(), {"code": code, "message": "Unknown interaction"})

    class _Slot:
        def __init__(self, done=False, code=responses.UNKNOWN_INTERACTION):
            self._done, self._code = done, code
            self.calls = []

        def is_done(self):
            return self._done

        async def defer(self, ephemeral=False):
            self.calls.append("defer")
            raise dead(self._code)

        async def send_message(self, *a, **k):
            self.calls.append("send_message")
            raise dead(self._code)

        async def edit_message(self, *a, **k):
            self.calls.append("edit_message")
            raise dead(self._code)

    class _Followup:
        def __init__(self, code):
            self._code = code
            self.calls = []

        async def send(self, *a, **k):
            self.calls.append("send")
            raise dead(self._code)

    class _Interaction:
        def __init__(self, done=False, code=responses.UNKNOWN_INTERACTION):
            self.response = _Slot(done, code)
            self.followup = _Followup(code)
            self.command = None
            self.channel_id = 1

        async def edit_original_response(self, *a, **k):
            raise dead(responses.UNKNOWN_INTERACTION)

    async def run():
        # An expired token must be absorbed, on every helper and on both
        # sides of a defer.
        for done in (False, True):
            await responses.defer(_Interaction(done))
            await responses.send(_Interaction(done))
            await responses.edit(_Interaction(done))

        # Anything that is NOT an expiry has to keep raising -- a
        # malformed embed is a bug, and swallowing it hides the bug.
        for helper in (responses.defer, responses.send, responses.edit):
            try:
                await helper(_Interaction(code=50035))
            except discord.HTTPException:
                pass
            else:
                failures.append(
                    f"responses.{helper.__name__} swallowed a 50035 -- only 10062 "
                    f"(expired) should ever be absorbed"
                )

        # send() has to pick the right transport: response before a
        # defer, followup after one.
        after = _Interaction(done=True)
        await responses.send(after)
        if after.followup.calls != ["send"]:
            failures.append("responses.send did not route through followup after a defer")
        before = _Interaction(done=False)
        await responses.send(before)
        if before.response.calls != ["send_message"]:
            failures.append("responses.send did not use the response slot before a defer")

    asyncio.run(run())


def main() -> int:
    # The helpers log a warning every time they absorb an expiry, which
    # is right in production and pure noise here -- absorbing expiries is
    # the thing being tested.
    logging.getLogger("bot.utils.responses").setLevel(logging.ERROR)
    failures: list[str] = []
    total = check_every_command_defers(failures)
    check_no_raw_responses(failures)
    check_no_double_defer(failures)
    check_helpers_survive_a_dead_token(failures)

    print(f"commands  : {total} slash commands, all deferring before any DB work")
    print("raw calls : 0 direct response.send_message / edit_message left in cogs")
    print("helpers   : absorb 10062, re-raise everything else, route either side of a defer")
    print()
    if failures:
        for line in dict.fromkeys(failures):
            print(f"  FAIL  {line}")
        return 1
    print("OK -- a slow database or a dead token can no longer crash a command.")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, ".")
    sys.exit(main())
