"""
Every player-facing command must be findable in /help.

    python -m tools.check_help_coverage

THE FAILURE THIS CATCHES IS SILENT AND PERMANENT.

A command that works perfectly and is mentioned nowhere is, for most
players, a command that does not exist. Discord's own slash-command
picker helps only if you already suspect the thing is there -- nobody
scrolls the full list looking for features, and nothing in the game
points at them.

Two shipped that way in one pass: /presets and /challenge. Both fully
built, both tested, both green across the whole suite, and both invisible
to anyone who did not already know to type them. That is the same shape
as Entrospire Deepworks shipping without an /adventure entry: the feature
was finished and unreachable, and the check suite had no opinion because
no single file was wrong.

ADMIN COMMANDS ARE EXEMPT from /help, by name, with a reason recorded.
They are not for players and listing them in /help would be worse than not
listing them -- it advertises a door nobody can open and invites people to
ask why.

THE README IS CHECKED TOO, and it is not exempt from anything.

/help is what a player reads; the README is what everybody else reads --
the person deciding whether to host the bot, the person setting it up, the
person picking up the code. It had drifted badly by release: twenty of
forty-two commands missing, including whole systems (`/story`, the main
mode), and it advertised `/mailbox`, which does not exist and never runs.

That drift is invisible from inside the game. Nothing points at it, no
player reports it, and the only symptom is that the front door describes
a different bot than the one in the repository. Admin commands ARE listed
in the README, because the person reading it is the person who would use
them.
"""

from __future__ import annotations

import os
import re
import sys

# Commands deliberately absent from /help, and why.
EXEMPT = {
    "admin_boosterkit": "admin tooling; not player-facing",
    "grant": "owner-only; listing it invites requests nobody can grant",
    "sync": "owner-only command sync",
}



def _referenced(text: str, backticked_only: bool = False) -> set[str]:
    """Command names a document refers to, group prefixes included.

    Matches `/base forge` as the single name "base forge" as well as the
    bare "base", so a document that says `/base` in passing still counts
    as mentioning the group without being credited for every subcommand.
    """
    pattern = r"`/(\w+)(?:\s+(\w+))?`" if backticked_only else r"/(\w+)(?:\s+(\w+))?"
    found: set[str] = set()
    for head, tail in re.findall(pattern, text):
        found.add(head)
        if tail:
            found.add(f"{head} {tail}")
    return found


def main() -> int:
    sys.path.insert(0, ".")

    cogs_dir = os.path.join("bot", "cogs")
    commands: dict[str, str] = {}
    # A command inside a GroupCog is NOT invoked by its own name.
    #
    # bot/cogs/base.py is `class Base(commands.GroupCog, name="base")`, so
    # its six commands are typed `/base forge`, `/base hq` and so on --
    # `/forge` does nothing at all. Both /help and the README documented
    # them as top-level for a long time, and this check passed the whole
    # time, because it extracted the bare name from the decorator and
    # then found that same bare name in the docs. It was comparing two
    # copies of one mistake and reporting agreement.
    #
    # So the group prefix is resolved here and the QUALIFIED name is what
    # the docs must contain.
    group_names: dict[str, str] = {}
    for filename in sorted(os.listdir(cogs_dir)):
        if not filename.endswith(".py") or filename == "__init__.py":
            continue
        source = open(os.path.join(cogs_dir, filename), encoding="utf-8").read()
        group = re.search(
            r'class\s+\w+\s*\(\s*commands\.GroupCog[^)]*name=["\'](\w+)["\']', source)
        if group:
            group_names[filename] = group.group(1)
        prefix = f"{group.group(1)} " if group else ""
        for match in re.finditer(
                r'app_commands\.command\(\s*name=["\'](\w+)["\']', source):
            commands[prefix + match.group(1)] = filename

    help_source = open(os.path.join(cogs_dir, "help.py"), encoding="utf-8").read()
    mentioned = _referenced(help_source)

    failures: list[str] = []
    for name, filename in sorted(commands.items()):
        if name in EXEMPT:
            continue
        if name not in mentioned:
            failures.append(
                f"/{name} ({filename}) is player-facing and appears nowhere in "
                f"/help -- players will never find it")

    # And the reverse: /help promising something that does not exist.
    # A dead reference is worse than a missing one, because the player
    # types it and the bot says nothing at all.
    # Group names themselves are real things to type -- Discord shows
    # `/base` and then its subcommands -- so a doc referring to `/base`
    # is correct, not a dead reference.
    known = set(commands) | set(EXEMPT) | set(group_names.values())
    # Words after a slash that are not commands (URLs, fractions in
    # prose) would produce noise, so only flag things formatted as a
    # command reference: `/word`.
    referenced = _referenced(help_source, backticked_only=True)
    for name in sorted(referenced - known):
        failures.append(
            f"/help refers to `/{name}`, which is not a real command")

    # ---- the README, which has no exemptions ------------------------
    readme_path = "README.md"
    if os.path.exists(readme_path):
        readme = open(readme_path, encoding="utf-8").read()
        readme_mentions = _referenced(readme)
        for name in sorted(commands):
            if name not in readme_mentions:
                failures.append(
                    f"/{name} is a real command and appears nowhere in README.md "
                    f"-- the front door describes a different bot than this one")
        for name in sorted(_referenced(readme, backticked_only=True)
                           - set(commands) - set(group_names.values())):
            failures.append(
                f"README.md advertises `/{name}`, which is not a real command")
        print(f"in README  : {len(set(commands) & readme_mentions)}/{len(commands)}")

    exempt_present = sorted(n for n in EXEMPT if n in commands)
    print(f"commands   : {len(commands)} total, "
          f"{len(commands) - len(exempt_present)} player-facing")
    print(f"in /help   : {len(set(commands) & mentioned)}")
    print(f"exempt     : {', '.join(exempt_present) or 'none'}")

    if failures:
        print()
        for failure in failures:
            print(f"  FAIL  {failure}")
        return 1
    print("\nOK -- every player-facing command is discoverable, and /help "
          "promises nothing that isn't there.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
