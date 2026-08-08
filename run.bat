@echo off
rem ---------------------------------------------------------------------
rem One-command setup and launch for CascadeBot (Windows).
rem
rem   run.bat              set up if needed, then start the bot
rem   run.bat --check      run the full tools\check_*.py suite, don't start
rem   run.bat --update     force a reinstall of requirements.txt
rem   run.bat --no-migrate skip the database migration step
rem
rem Double-clicking it in Explorer works too, and is the same as running
rem it with no arguments.
rem
rem Safe to run every time: the venv is created once, dependencies are
rem reinstalled only when requirements.txt changes, and the migration is a
rem no-op on an already-current database. This is the exact counterpart of
rem run.sh -- keep the two in step.
rem
rem Note it never calls `.venv\Scripts\activate`. Activation only edits the
rem environment of the shell doing it, which this script's own shell throws
rem away on exit; calling .venv\Scripts\python.exe by path gets the same
rem result with no invisible state and no chance of silently installing
rem into the system Python.
rem ---------------------------------------------------------------------
setlocal enabledelayedexpansion

rem Was this double-clicked from Explorer rather than run from a prompt?
rem It matters: on a double-click the console window is destroyed the
rem instant the script ends, so every error message below would flash past
rem unread and the whole thing would look like "nothing happened". When
rem that's how we were started, we pause before exiting.
rem
rem The tell is %cmdcmdline%, the literal command line of this cmd.exe: a
rem double-click produces `cmd /c ""...\run.bat" "`, while an interactive
rem prompt's own command line never contains the script's path.
set "PAUSE_ON_EXIT="
echo %cmdcmdline% | find /i "%~nx0" >nul && set "PAUSE_ON_EXIT=1"

rem Run from the project root regardless of where this was launched from
rem -- and Explorer launches with a working directory of anywhere. The
rem default DATABASE_URL is a RELATIVE sqlite path, so the wrong working
rem directory silently creates a second, empty database, which looks
rem exactly like losing all your data.
cd /d "%~dp0"

set "VENV=.venv"
set "PY=%VENV%\Scripts\python.exe"
set "STAMP=%VENV%\.requirements-hash"

set "DO_CHECK=0"
set "FORCE_UPDATE=0"
set "DO_MIGRATE=1"
for %%a in (%*) do (
    if /i "%%~a"=="--check"      set "DO_CHECK=1"
    if /i "%%~a"=="--update"     set "FORCE_UPDATE=1"
    if /i "%%~a"=="--no-migrate" set "DO_MIGRATE=0"
)

rem =====================================================================
rem 1. Virtual environment
rem =====================================================================
if not exist "%PY%" (
    echo.
    echo ==^> Creating virtual environment in %VENV%
    rem The `py` launcher is what a python.org install provides and is the
    rem reliable way to ask for a specific version; bare `python` on
    rem Windows may be the Microsoft Store stub, which prints an ad for
    rem the Store instead of running anything.
    where py >nul 2>&1
    if not errorlevel 1 (
        py -3 -m venv "%VENV%"
    ) else (
        python -m venv "%VENV%"
    )
    if not exist "%PY%" (
        set "ERR1=Could not create the virtual environment."
        set "ERR2=Install Python 3.10 or newer from python.org, and tick"
        set "ERR3=the 'Add python.exe to PATH' box during setup."
        goto :abort
    )
)

rem The codebase uses 3.10 syntax throughout (`int ^| None` annotations
rem evaluated at runtime, match statements). Checking here turns a
rem confusing SyntaxError from deep inside an import chain into one
rem sentence.
"%PY%" -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)"
if errorlevel 1 (
    set "ERR1=The virtual environment's Python is older than 3.10, which this"
    set "ERR2=code needs. Delete the .venv folder, install Python 3.10+ from"
    set "ERR3=python.org, and run this again."
    goto :abort
)

rem =====================================================================
rem 2. Dependencies -- only when requirements.txt has actually changed
rem
rem A plain `pip install -r` on every launch means every restart waits on
rem the network to be told nothing changed. Slow at best; on a flaky
rem connection it turns a restart into a failure for no reason. Hashing
rem requirements.txt and stamping the venv makes the common case instant
rem and fully offline.
rem
rem certutil is the one hashing tool present on every Windows install.
rem Its output is three lines and the middle one is the hex digest.
rem =====================================================================
set "WANT="
for /f "skip=1 delims=" %%h in ('certutil -hashfile requirements.txt MD5 2^>nul') do (
    if not defined WANT set "WANT=%%h"
)
set "HAVE=none"
if exist "%STAMP%" set /p HAVE=<"%STAMP%"
if "%FORCE_UPDATE%"=="1" set "HAVE=force-reinstall"

if "!WANT!"=="!HAVE!" (
    echo.
    echo ==^> Dependencies already current ^(requirements.txt unchanged^)
) else (
    echo.
    echo ==^> Installing dependencies from requirements.txt
    "%PY%" -m pip install --quiet --upgrade pip
    "%PY%" -m pip install --quiet -r requirements.txt
    if errorlevel 1 (
        set "ERR1=Dependency install failed -- see the pip output above."
        set "ERR2=If it mentions a network or proxy problem, check your connection"
        set "ERR3=and run this again; nothing else has been changed."
        goto :abort
    )
    rem Only stamp AFTER a successful install, so a failed run retries
    rem next time instead of recording a lie and skipping forever.
    > "%STAMP%" echo !WANT!
)

rem =====================================================================
rem 3. Configuration
rem
rem Without this, a missing .env surfaces as a discord.py LoginFailure on
rem a None token, several seconds and one stack trace later.
rem =====================================================================
if not exist ".env" (
    copy /y ".env.example" ".env" >nul
    set "ERR1=.env didn't exist, so I copied .env.example to .env."
    set "ERR2=Open it in Notepad, paste your bot token after DISCORD_TOKEN="
    set "ERR3=and run this again."
    goto :abort
)
findstr /r /c:"^ *DISCORD_TOKEN *= *[^ ]" ".env" >nul
if errorlevel 1 (
    set "ERR1=DISCORD_TOKEN is empty in .env."
    set "ERR2=Get one from the Discord Developer Portal: your application,"
    set "ERR3=then Bot, then Reset Token. Paste it into .env and run again."
    goto :abort
)

rem =====================================================================
rem 4. Database schema
rem
rem migrate_db.py takes its own backup first and does nothing when already
rem current, so running it unconditionally costs nothing and means you can
rem never start the bot against a schema older than the code.
rem =====================================================================
if "%DO_MIGRATE%"=="1" (
    echo.
    echo ==^> Checking the database schema
    "%PY%" -m tools.migrate_db
    if errorlevel 1 (
        set "ERR1=Migration failed -- see the output above."
        set "ERR2=The bot was NOT started, and your database is untouched apart"
        set "ERR3=from the backup migrate_db.py took before it began."
        goto :abort
    )
)

rem =====================================================================
rem 5. Verify, or launch
rem =====================================================================
if "%DO_CHECK%"=="1" (
    echo.
    echo ==^> Running the check suite
    set "FAILED=0"
    for %%f in (tools\check_*.py) do (
        "%PY%" -m tools.%%~nf >nul 2>&1
        if errorlevel 1 (
            echo   FAIL %%~nxf
            rem Re-run the failure visibly: the quiet pass above keeps a
            rem green run to one line per check, but a red one is the
            rem whole reason you ran this, so show all of it.
            "%PY%" -m tools.%%~nf
            set "FAILED=1"
        ) else (
            echo   ok   %%~nxf
        )
    )
    if "!FAILED!"=="1" (
        set "ERR1=Check suite failed -- details above."
        set "ERR2="
        set "ERR3="
        goto :abort
    )
    echo.
    echo ==^> All checks passed.
    if defined PAUSE_ON_EXIT pause
    exit /b 0
)

echo.
echo ==^> Starting CascadeBot -- press Ctrl+C to stop
"%PY%" start_bot.py
set "RC=%ERRORLEVEL%"
rem A crashed bot on a double-click would otherwise vanish with its
rem traceback, which is the single most useless failure mode there is.
if not "%RC%"=="0" (
    echo.
    echo ==^> The bot exited with code %RC% ^(traceback above, if any^).
    if defined PAUSE_ON_EXIT pause
)
exit /b %RC%

:abort
echo.
echo  x  %ERR1%
if defined ERR2 if not "%ERR2%"=="" echo     %ERR2%
if defined ERR3 if not "%ERR3%"=="" echo     %ERR3%
echo.
if defined PAUSE_ON_EXIT pause
exit /b 1
