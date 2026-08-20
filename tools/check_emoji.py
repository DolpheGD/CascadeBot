"""
Assert no custom emoji is hardcoded outside currency_service.

    python -m tools.check_emoji

Custom Discord emoji are written `<:name:id>`, and the id is the part
that changes when the emoji is re-uploaded or moved between servers.

This exists because changing the Shard emoji id took SEVEN edits and
only some of them happened. `currency_service.SHARD_EMOJI` was updated
correctly, and the literal `<:shard:1534383382924890192>` was still
sitting in the profile page, the stash's currency block, the gacha rates
embed, the admin booster message, the lootbox result line and a domain
icon. The bot rendered a dead emoji in half its screens and there was
nothing to notice it -- a broken custom emoji does not error, it just
shows up as raw text or a blank square, and only for players.

The rule is therefore: one definition per emoji, in currency_service,
reached through `currency_emoji()` or `format_currency()`. Modules that
genuinely cannot import it (pure config with a no-bot-imports rule) may
hold a NAMED constant, which is listed below and asserted to match.
"""

from __future__ import annotations

import pathlib
import re
import sys

EMOJI = re.compile(r"<a?:\w+:\d+>")

# The one file allowed to define custom emoji literals.
SOURCE = pathlib.Path("bot/services/currency_service.py")

# Modules that mirror a constant instead of importing. Each entry is
# (path, constant name, the currency_service attribute it must equal).
MIRRORS = [
    ("bot/game/economy/domain_config.py", "SHARD_ICON", "SHARD_EMOJI"),
    ("bot/game/economy/domain_config.py", "CORE_ICON", "CORE_EMOJI"),
    ("bot/game/economy/domain_config.py", "EVO_ICON", "EVO_EMOJI"),
]


def main() -> int:
    failures: list[str] = []
    checked = 0

    # PER-CONSTANT, NOT PER-FILE.
    #
    # This used to skip a mirror FILE entirely, which quietly exempted
    # every emoji in it rather than the one declared line. domain_config
    # declared SHARD_ICON, CORE_ICON and (later) EVO_ICON; only SHARD_ICON
    # was in MIRRORS, so the other two were checked by nothing at all --
    # a blanket exemption earned by one honest entry. That is the same
    # bug this checker exists to catch, one level up: a rule with a hole
    # in it that nothing reports.
    #
    # Now only the exact `NAME = "<:...>"` lines are exempt, and any
    # OTHER literal in a mirror file fails like it would anywhere else.
    allowed_lines: dict[str, set[str]] = {}
    for path, constant, _ in MIRRORS:
        allowed_lines.setdefault(path, set()).add(constant)

    for path in sorted(pathlib.Path("bot").rglob("*.py")):
        as_posix = path.as_posix()
        if as_posix == SOURCE.as_posix():
            continue
        text = path.read_text(encoding="utf-8")
        declared = allowed_lines.get(as_posix, set())
        for number, line in enumerate(text.splitlines(), start=1):
            for match in EMOJI.findall(line):
                checked += 1
                assignment = re.match(r'\s*(\w+)\s*=\s*"', line)
                if assignment and assignment.group(1) in declared:
                    continue  # verified against the source below
                failures.append(
                    f"{as_posix}:{number} hardcodes {match} -- use "
                    f"currency_emoji()/format_currency() so there is one "
                    f"definition to change"
                )

    # Mirrors must actually match.
    from bot.services import currency_service
    for path, constant, source_attr in MIRRORS:
        module_text = pathlib.Path(path).read_text(encoding="utf-8")
        found = re.search(rf'{constant}\s*=\s*"([^"]+)"', module_text)
        expected = getattr(currency_service, source_attr)
        if found is None:
            failures.append(f"{path}: expected a {constant} constant, found none")
        elif found.group(1) != expected:
            failures.append(
                f"{path}: {constant} is {found.group(1)} but "
                f"currency_service.{source_attr} is {expected} -- they have drifted"
            )

    print(f"literals : {checked} custom emoji found outside currency_service")
    print(f"mirrors  : {len(MIRRORS)} declared, checked against their source")
    print()
    if failures:
        for line in dict.fromkeys(failures):
            print(f"  FAIL  {line}")
        return 1
    print("OK -- every custom emoji has exactly one definition.")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, ".")
    sys.exit(main())
