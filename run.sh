#!/usr/bin/env bash
#
# One-command setup and launch for CascadeBot (Linux / macOS).
#
#   ./run.sh              set up if needed, then start the bot
#   ./run.sh --check      run the full tools/check_*.py suite, don't start
#   ./run.sh --update     force a reinstall of requirements.txt
#   ./run.sh --no-migrate skip the database migration step
#
# It is safe to run this every single time. Everything it does is
# idempotent: the venv is only created once, dependencies are only
# reinstalled when requirements.txt actually changes, and the migration
# is a no-op on an already-current database.
#
# ----------------------------------------------------------------------
# Why this script never runs `source .venv/bin/activate`
# ----------------------------------------------------------------------
# Activating a venv only edits the environment of the shell that does the
# activating. This script runs in its own shell, so an `activate` here
# would be undone the instant the script exits -- it would look like it
# worked while changing nothing you can see afterwards.
#
# What activation actually buys you is that `python` and `pip` resolve to
# the venv's copies. We get that directly and unambiguously by calling
# .venv/bin/python by path. Same result, no invisible state, and no way
# to accidentally install into the system Python because activation
# silently failed.
# ----------------------------------------------------------------------

set -euo pipefail

# Work from the project root no matter where the script is invoked from,
# so `~/run.sh` and `./run.sh` behave identically. Paths in .env (notably
# the default sqlite:///Cascadebot.db) are relative to the working
# directory, so getting this wrong points the bot at a second, empty
# database -- which looks exactly like losing all your data.
cd "$(dirname "${BASH_SOURCE[0]}")"

VENV=".venv"
PY="$VENV/bin/python"
STAMP="$VENV/.requirements-hash"

DO_CHECK=0
FORCE_UPDATE=0
DO_MIGRATE=1
for arg in "$@"; do
    case "$arg" in
        --check)      DO_CHECK=1 ;;
        --update)     FORCE_UPDATE=1 ;;
        --no-migrate) DO_MIGRATE=0 ;;
        -h|--help)    sed -n '2,9p' "${BASH_SOURCE[0]}" | sed 's/^# \?//'; exit 0 ;;
        *) echo "Unknown option: $arg (try --help)" >&2; exit 2 ;;
    esac
done

say() { printf '\n\033[1;36m==>\033[0m %s\n' "$1"; }
die() { printf '\n\033[1;31mx\033[0m %s\n\n' "$1" >&2; exit 1; }

# ----------------------------------------------------------------------
# 1. Find a usable Python.
#
# discord.py 2.4 and SQLAlchemy 2.x both need 3.9+, and the codebase uses
# 3.10 syntax throughout (`int | None` in annotations at runtime, match
# statements). Checking here turns a confusing SyntaxError from deep
# inside an import chain into one clear sentence.
# ----------------------------------------------------------------------
if [ ! -x "$PY" ]; then
    BOOTSTRAP=""
    for candidate in python3.13 python3.12 python3.11 python3.10 python3 python; do
        if command -v "$candidate" >/dev/null 2>&1 &&
           "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' 2>/dev/null; then
            BOOTSTRAP="$candidate"; break
        fi
    done
    [ -n "$BOOTSTRAP" ] || die "Need Python 3.10 or newer on PATH. Try: sudo apt install python3 python3-venv"

    say "Creating virtual environment in $VENV ($($BOOTSTRAP -V))"
    # Debian/Ubuntu ship python3 without the venv module in a separate
    # package, and its failure message is famously unhelpful, so say the
    # fix out loud rather than letting the raw error through.
    "$BOOTSTRAP" -m venv "$VENV" || die "Could not create the venv. On Debian/Ubuntu: sudo apt install python3-venv"
fi

# ----------------------------------------------------------------------
# 2. Install dependencies -- but only when they've actually changed.
#
# A plain `pip install -r` on every launch means every restart waits on
# the network to be told nothing has changed. That's slow at best, and on
# a flaky connection it turns a restart into a failure for no reason.
# Hashing requirements.txt and stamping the venv makes the common case
# (nothing changed) instant and completely offline.
# ----------------------------------------------------------------------
WANT="$(cksum requirements.txt | awk '{print $1"-"$2}')"
HAVE="$(cat "$STAMP" 2>/dev/null || echo none)"

if [ "$FORCE_UPDATE" = "1" ] || [ "$WANT" != "$HAVE" ]; then
    say "Installing dependencies from requirements.txt"
    "$PY" -m pip install --quiet --upgrade pip
    "$PY" -m pip install --quiet -r requirements.txt || die "Dependency install failed."
    echo "$WANT" > "$STAMP"
else
    say "Dependencies already current (requirements.txt unchanged)"
fi

# ----------------------------------------------------------------------
# 3. Configuration.
#
# Without this, a missing .env surfaces as a discord.py LoginFailure on
# a None token, several seconds and one stack trace later.
# ----------------------------------------------------------------------
if [ ! -f .env ]; then
    cp .env.example .env
    die ".env didn't exist, so I copied .env.example to .env.
   Open it, paste your bot token into DISCORD_TOKEN, and run this again."
fi
grep -Eq '^[[:space:]]*DISCORD_TOKEN[[:space:]]*=[[:space:]]*[^[:space:]]' .env \
    || die "DISCORD_TOKEN is empty in .env. Get one from the Discord Developer
   Portal (your application -> Bot -> Reset Token) and paste it in."

# ----------------------------------------------------------------------
# 4. Bring the database schema up to date.
#
# migrate_db.py takes its own backup first and is a no-op when there's
# nothing to do, so running it unconditionally costs nothing and means
# you can never start the bot against a schema older than the code.
# ----------------------------------------------------------------------
if [ "$DO_MIGRATE" = "1" ]; then
    say "Checking the database schema"
    "$PY" -m tools.migrate_db || die "Migration failed -- the bot was NOT started, and your
   database is untouched apart from the backup migrate_db.py took."
fi

# ----------------------------------------------------------------------
# 5. Either verify, or launch.
# ----------------------------------------------------------------------
if [ "$DO_CHECK" = "1" ]; then
    say "Running the check suite"
    failed=0
    for f in tools/check_*.py; do
        module="${f%.py}"; module="${module//\//.}"
        if out="$("$PY" -m "$module" 2>&1)"; then
            printf '  \033[32mok\033[0m   %s\n' "$(basename "$f")"
        else
            printf '  \033[31mFAIL\033[0m %s\n%s\n' "$(basename "$f")" "$out"
            failed=1
        fi
    done
    [ "$failed" = "0" ] || die "Check suite failed."
    say "All checks passed."
    exit 0
fi

say "Starting CascadeBot -- press Ctrl+C to stop"
exec "$PY" start_bot.py
