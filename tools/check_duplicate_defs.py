"""
No module may define the same top-level name twice.

    python -m tools.check_duplicate_defs

WHY THIS EXISTS, AND WHY IT IS NOT PARANOIA.

A duplicated `def` is not a syntax error. Python evaluates both and keeps
the second, silently. The module imports, every caller resolves, the test
suite passes, and the first definition -- the one you are looking at while
you reason about the code -- never runs.

This file exists because that happened here, to combat's amplified_percent.
A scripted edit spliced a reverted version of the function in at the wrong
anchor (`s.index("if stat in NO_FALLOFF_STATS:")` matched an earlier
occurrence inside a DIFFERENT function), leaving two complete definitions
in one file. The revert appeared to work: the file imported, the whole
31-check suite stayed green, and a balance benchmark was then run and
believed. It had in fact measured the version that was supposed to have
been removed, and the number it produced went into a decision.

That is the expensive part. A crash is cheap -- you fix it and move on. A
silently shadowed definition produces CONFIDENT WRONG MEASUREMENTS, and
those are indistinguishable from real results until something much later
fails to add up.

It is the same shape as this codebase's most persistent bug: two code
paths computing one value. Usually that is two functions in two modules
drifting apart. This is the degenerate case -- two functions with the same
name in the same file, where one of them cannot even be reached.

Scope: top-level functions and classes, per module. Methods are checked
per class too, since a duplicated method shadows exactly as quietly.
Deliberate re-binding (@overload, @property/@x.setter pairs, and
if/else or try/except definitions that pick one implementation) is NOT
flagged -- those are real Python idioms, and a check that cries wolf on
them would be turned off within a week.
"""

from __future__ import annotations

import ast
import pathlib
import sys

ROOTS = [pathlib.Path("bot"), pathlib.Path("tools")]

# Decorators that legitimately re-bind a name that already exists.
_REBINDING_DECORATORS = {"overload", "setter", "getter", "deleter",
                         "register", "default"}


def _decorator_names(node) -> set[str]:
    names = set()
    for decorator in getattr(node, "decorator_list", []):
        text = ast.unparse(decorator)
        names.add(text.split("(")[0].split(".")[-1])
    return names


def _definitions(body) -> list[tuple[str, int, object]]:
    """(name, lineno, node) for defs/classes DIRECTLY in this body.

    Only the body passed in -- never recursing into if/try, because a
    name defined once per branch is one definition, not several. That
    exemption is the whole reason this walks bodies by hand instead of
    using ast.walk.
    """
    found = []
    for node in body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            found.append((node.name, node.lineno, node))
    return found


def _check_body(body, where: str, failures: list[str]) -> int:
    seen: dict[str, int] = {}
    count = 0
    for name, lineno, node in _definitions(body):
        count += 1
        if _decorator_names(node) & _REBINDING_DECORATORS:
            continue
        if name in seen:
            failures.append(
                f"{where} defines {name!r} twice (lines {seen[name]} and "
                f"{lineno}) -- Python keeps the SECOND one and the first "
                f"never runs")
        else:
            seen[name] = lineno
        if isinstance(node, ast.ClassDef):
            count += _check_body(node.body, f"{where}:{name}", failures)
    return count


def main() -> int:
    failures: list[str] = []
    modules = 0
    definitions = 0

    for root in ROOTS:
        for path in sorted(root.rglob("*.py")):
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except SyntaxError as exc:
                failures.append(f"{path} does not parse: {exc}")
                continue
            modules += 1
            definitions += _check_body(tree.body, str(path), failures)

    print(f"modules    : {modules}")
    print(f"definitions: {definitions} top-level and class-level names checked")

    if failures:
        print()
        for failure in failures:
            print(f"  FAIL  {failure}")
        return 1
    print("\nOK -- no definition is shadowed by a later one of the same name.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
