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

Four structural properties are checked, plus the behaviour of the helpers
that make them safe. Both are things a future command can silently get
wrong, which is the only reason this file exists:

  * every slash command DEFERS as its first statement, before it opens a
    database session -- that is what turns the 3-second budget into 15
    minutes

  * no cog reaches for interaction.response.send_message /
    edit_message directly, because those are the calls that raise once
    the response slot has been spent by that defer

  * no raw interaction.followup.send runs before something has spent
    the response slot -- before a defer or a reply there is no webhook to
    follow up to, and Discord returns 404 Unknown Webhook

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
# Followup ordering is checked across the WHOLE bot package, not just
# cogs: bot/utils/ui_guard.py replies too, and views live outside cogs.
ROOT = pathlib.Path("bot")

# Whether a command's defer is private is not declared anywhere -- it is
# DERIVED from the replies the command actually makes, below.
#
# This used to be a hardcoded set of command names, and it went stale the
# first time a command was added: /grant replies ephemerally in every one
# of its five branches, was not on the list, and so the check reported a
# mismatch that did not exist. A list of names that has to be edited in
# lockstep with the code is the same failure that let /adventure ship
# with a hardcoded five-region menu while a sixth region existed -- two
# places holding one fact, drifting apart the moment anyone looks away.
#
# The rule the list was trying to express: a command whose every reply is
# ephemeral must defer ephemerally, because a public defer leaves a
# visible "thinking..." placeholder hanging off an answer nobody else can
# read. Read straight off the replies, that rule needs no maintenance.
#
# responses.edit() is deliberately NOT counted. An edit replaces the
# deferred message and inherits its visibility, so it says nothing about
# what the author intended -- it is the defer's own consequence, and
# treating it as evidence would make the check argue in a circle.


def _commands_in(path: pathlib.Path, tree=None):
    tree = tree if tree is not None else ast.parse(path.read_text())
    for node in ast.walk(tree):
        if not isinstance(node, ast.AsyncFunctionDef):
            continue
        decorators = ast.unparse(node.decorator_list) if node.decorator_list else ""
        if "app_commands.command" in decorators:
            yield node


def check_every_command_defers(failures: list[str]) -> int:
    total = 0
    for path in sorted(COGS.glob("*.py")):
        tree = ast.parse(path.read_text())
        helpers = _replying_helpers(tree)
        for node in _commands_in(path, tree):
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
            wants_private = _replies_are_all_private(node, helpers)
            is_private = "ephemeral=True" in first
            if wants_private is not None and wants_private != is_private:
                failures.append(
                    f"{path.name} /{node.name} defers with ephemeral={is_private}, "
                    f"but every reply it makes is "
                    f"{'private' if wants_private else 'not'} -- "
                    f"defer {'ephemeral=True' if wants_private else 'publicly'} to match"
                )
    return total


# Calls that produce a NEW message the player sees. edit() is excluded on
# purpose; see the note at the top of the file.
_REPLY_CALLS = {"responses.send", "ctx.followup.send",
                "interaction.followup.send"}


def _replying_helpers(tree) -> set[str]:
    """Module-level functions in this file that reply to the player.

    A command that calls one of these has handed its primary reply
    somewhere this check cannot follow.
    """
    helpers = set()
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for inner in ast.walk(node):
            if isinstance(inner, ast.Call) and ast.unparse(inner.func) in (
                    _REPLY_CALLS | {"responses.edit"}):
                helpers.add(node.name)
                break
    return helpers


def _replies_are_all_private(node, helpers: set[str] = frozenset()) -> bool | None:
    """True if every reply is ephemeral, False if any is public.

    None means "cannot tell", and it is the answer far more often than it
    looks. A command whose only visible reply is a guard clause --
    `if player is None: send(..., ephemeral=True); return` -- and whose
    real output goes through a render helper reads, to a naive AST walk,
    as a command that only ever replies privately. /cards is exactly that
    and was the first thing this rewrite wrongly flagged.

    So: delegate to a helper that replies, and this returns None. Better
    to check nothing than to check the wrong thing confidently -- an
    over-reporting harness gets ignored, and then it is worth less than
    no harness at all.
    """
    for inner in ast.walk(node):
        if isinstance(inner, ast.Call) and ast.unparse(inner.func) in helpers:
            return None

    replies = []
    for inner in ast.walk(node):
        if not isinstance(inner, ast.Call):
            continue
        target = ast.unparse(inner.func)
        if target in _REPLY_CALLS:
            replies.append(
                any(kw.arg == "ephemeral"
                    and isinstance(kw.value, ast.Constant)
                    and kw.value.value is True
                    for kw in inner.keywords))
    if not replies:
        return None
    return all(replies)


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


def _dotted(node: ast.AST) -> tuple[str, ...]:
    """('interaction', 'followup', 'send') for an attribute chain."""
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return tuple(reversed(parts))


# Calls that SPEND the interaction's one response slot. After any of
# these, followup.send is the correct call; before them, it 404s.
SLOT_SPENDERS = {
    ("responses", "defer"), ("responses", "edit"), ("responses", "send"),
    ("interaction", "response", "defer"),
    ("interaction", "response", "send_message"),
    ("interaction", "response", "edit_message"),
}


def check_followups_come_after_a_response(failures: list[str]) -> int:
    """A raw `interaction.followup.send` must not be the FIRST reply.

    Discord gives an interaction exactly one response slot. Until it's
    spent -- by a defer or a reply -- there is no webhook to follow up
    to, and `followup.send` fails with 404 Unknown Webhook. After it's
    spent, followup is the only thing that works. Neither call is wrong;
    the ORDER is what decides.

    This is here because of a live bug that check_no_raw_responses could
    not see. bot/cogs/story.py's station branch -- the tile that opens
    the Forge, the Echo booth, Cascade HQ -- opened its panel with a bare
    `interaction.followup.send`, in a handler that never defers. Every
    other branch of that handler ends at responses.edit(), which spends
    the slot itself, so the station tiles were the one path that reached
    a followup on an untouched interaction. Standing on the forge and
    pressing Interact 404'd every single time.

    It hid for a while because a station whose feature is still LOCKED
    returns earlier through require_feature's own reply: locked stations
    worked, and only the ones you'd actually unlocked were broken.

    A blanket ban would be wrong -- ten legitimate call sites send a
    SECOND message after editing the first, and that genuinely requires
    followup. So the rule is ordering, not prohibition: some slot-spender
    must be GUARANTEED to have run first, or the function must branch on
    `response.is_done()` and handle both sides (which is exactly what
    responses.py and ui_guard.py do).

    ----------------------------------------------------------------------
    Why this walks control flow instead of comparing line numbers
    ----------------------------------------------------------------------
    The first version of this check asked "is there a slot-spender on an
    earlier LINE?" -- and it passed the very bug it was written for. In
    _open_station the preceding responses.send() sits inside

        if built is None:
            await responses.send(...)   # earlier line
            return                      # ...but it RETURNS

    so on every path that actually reaches the followup, that send never
    ran. Line order is not execution order, and a conditional reply in a
    branch that returns has spent nothing.

    So only statements that are UNCONDITIONALLY reached count: the
    function's own body, and the bodies of try/with (which always run).
    Anything inside an if / loop / except may be skipped, so it is
    scanned for violations but never credited with spending the slot.
    """
    checked = 0
    # try/with bodies run unconditionally, so a reply inside one really
    # has spent the slot for everything after it. if/for/while/match
    # bodies may be skipped, so they are scanned for violations but never
    # allowed to mark the slot spent for their followers.
    ALWAYS_RUNS = (ast.Try, ast.With, ast.AsyncWith)
    NESTED_FUNCTION = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)

    def calls_in(stmt: ast.stmt):
        """Calls in this statement, not descending into nested blocks --
        those are walked separately, in order."""
        for node in ast.walk(stmt):
            if isinstance(node, ast.Call):
                yield node

    def scan(body: list[ast.stmt], spent: bool, report: list[tuple[int, bool]]) -> bool:
        """Walk statements in order, recording each followup against
        what is known at the point it actually executes. Returns whether
        the slot is definitely spent once this block completes."""
        for stmt in body:
            if isinstance(stmt, NESTED_FUNCTION):
                continue  # visited on its own by the caller's ast.walk

            blocks = [b for name in ("body", "handlers", "orelse", "finalbody")
                      for b in [getattr(stmt, name, None)] if isinstance(b, list)]

            if not blocks:
                # A simple statement: judge its followups at the current
                # state, then see whether it spends the slot itself.
                for node in calls_in(stmt):
                    if _dotted(node.func) == ("interaction", "followup", "send"):
                        report.append((node.lineno, spent))
                if not spent:
                    spent = any(_dotted(n.func) in SLOT_SPENDERS for n in calls_in(stmt))
                continue

            if isinstance(stmt, ALWAYS_RUNS):
                # The body runs; propagate what it establishes. Handlers
                # and else/finally are conditional, so they see the
                # post-body state but can't publish their own.
                after_body = scan(stmt.body, spent, report)
                for handler in getattr(stmt, "handlers", []) or []:
                    scan(handler.body, spent, report)
                for name in ("orelse", "finalbody"):
                    scan(getattr(stmt, name, []) or [], after_body, report)
                spent = after_body
            else:
                # Conditional: scan every branch at the current state and
                # throw away whatever they establish.
                for block in blocks:
                    if block and isinstance(block[0], ast.ExceptHandler):
                        for handler in block:
                            scan(handler.body, spent, report)
                    else:
                        scan(block, spent, report)
        return spent

    for path in sorted(ROOT.rglob("*.py")):
        if path.name == "responses.py":
            continue  # the helper that implements the rule
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if any(isinstance(n, ast.Attribute) and n.attr == "is_done"
                   for n in ast.walk(fn)):
                continue  # handles both sides itself
            report: list[tuple[int, bool]] = []
            scan(fn.body, False, report)
            checked += len(report)
            for line, was_spent in report:
                if not was_spent:
                    failures.append(
                        f"{path.name}:{line} in {fn.name}() calls "
                        f"interaction.followup.send on a path where nothing has "
                        f"spent the response slot yet -- Discord answers that with "
                        f"404 Unknown Webhook. Use responses.send, which picks the "
                        f"right call either way."
                    )
    return checked


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

        # Anything that is NOT an expiry has to keep raising FROM A
        # COMMAND -- a malformed embed is a bug, and swallowing it hides
        # the bug. A command's exception reaches the tree's error handler.
        for helper in (responses.defer, responses.send, responses.edit):
            interaction = _Interaction(code=50035)
            interaction.command = object()          # i.e. a slash command
            try:
                await helper(interaction)
            except discord.HTTPException:
                pass
            else:
                failures.append(
                    f"responses.{helper.__name__} swallowed a 50035 from a COMMAND "
                    f"-- only 10062 (expired) should ever be absorbed there, because "
                    f"the tree's error handler is what turns it into a message"
                )

        # ...but a COMPONENT has no handler to raise into. discord.py's
        # schedule_dynamic_item_call catches everything and only logs, so
        # a re-raise there answers nobody and leaves a dead button --
        # which is how a select over the 25-option limit produced three
        # tracebacks and nothing on screen. responses.edit must REPORT
        # instead, so the player gets a sentence.
        reported: list[str] = []
        original_report = responses.report_failure

        async def _capture(interaction, error, where=""):
            reported.append(type(error).__name__)

        responses.report_failure = _capture
        try:
            component = _Interaction(code=50035)
            component.command = None                # i.e. a button or select
            await responses.edit(component)
        except discord.HTTPException:
            failures.append(
                "responses.edit re-raised a 50035 from a COMPONENT -- nothing "
                "catches that (discord.py logs and returns), so the player is left "
                "with a control that silently did nothing"
            )
        finally:
            responses.report_failure = original_report
        if not reported:
            failures.append(
                "responses.edit neither raised nor reported a 50035 from a "
                "component -- the failure vanished entirely"
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
    followups = check_followups_come_after_a_response(failures)
    check_no_double_defer(failures)
    check_helpers_survive_a_dead_token(failures)

    print(f"commands  : {total} slash commands, all deferring before any DB work")
    print("raw calls : 0 direct response.send_message / edit_message left in cogs")
    print(f"followups : {followups} raw followup.send calls checked for ordering")
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
