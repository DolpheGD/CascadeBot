import os

from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
COMMAND_PREFIX = os.getenv("COMMAND_PREFIX", "!")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///Cascadebot.db")
DEBUG = os.getenv("DEBUG") == "1"

# Dev-mode guild command syncing: when DEV_MODE is on, slash commands sync
# instantly to SERVER_ID instead of waiting on Discord's global command
# propagation delay. Leave DEV_MODE off (default) for production.
DEV_MODE = os.getenv("DEV_MODE") == "True"
SERVER_ID = int(os.getenv("SERVER_ID")) if os.getenv("SERVER_ID") else None

# ----------------------------------------------------------------------
# BOT OWNER(S) -- the bot's only permission gate.
#
# There used to be a second, broader one: ADMIN_USER_IDS, which also let
# through anyone holding Discord's "Administrator" permission in the
# server they were typing in. It was removed with /admin_boosterkit, the
# only command that used it, and it is worth recording why rather than
# just deleting it.
#
# It admitted the entire internet. Anyone can create a server, add the
# bot, and be an administrator of it in about thirty seconds, so
# "Administrator here" is a permission that grants itself. That was a
# tolerable trade for a fixed, once-per-player bundle. It is not a gate,
# and a config knob that reads like one is worse than none at all --
# somebody will eventually put a dangerous command behind it.
#
# So owner-only means owner-only: an explicit allowlist of Discord user
# IDs, checked with no fallback. If this is empty the command refuses
# EVERYONE, which is the correct failure direction for a money printer.
#
# Set it in .env:
#     BOT_OWNER_IDS=123456789012345678
# ----------------------------------------------------------------------
BOT_OWNER_IDS = {
    int(uid.strip())
    for uid in os.getenv("BOT_OWNER_IDS", "").split(",")
    if uid.strip()
}

# ----------------------------------------------------------------------
# Top.gg voting (/vote -- see bot/services/topgg_client.py)
#
# Entirely optional: with TOPGG_TOKEN unset the /vote command still loads,
# but tells the player voting isn't set up rather than erroring, and no
# network calls are ever made. Nothing else in the bot depends on it.
#
# TOPGG_TOKEN comes from your bot's listing page on top.gg, under
# "Integrations & API" (older listings call this tab "Webhooks"). It's a
# read token for *your own* bot's vote data -- treat it like the Discord
# token and keep it out of source control.
#
# TOPGG_BOT_ID only needs setting in the unusual case where the top.gg
# listing isn't for this bot's own application ID; normally it's left
# blank and resolved from the logged-in bot user at runtime.
# ----------------------------------------------------------------------
TOPGG_TOKEN = os.getenv("TOPGG_TOKEN") or None
TOPGG_BOT_ID = int(os.getenv("TOPGG_BOT_ID")) if os.getenv("TOPGG_BOT_ID") else None

if not DISCORD_TOKEN:
    raise RuntimeError(
        "DISCORD_TOKEN is not set. Copy .env.example to .env and fill it in."
    )

if DEV_MODE and not SERVER_ID:
    raise RuntimeError("DEV_MODE is on but SERVER_ID is not set in .env.")
