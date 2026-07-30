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

# Discord user IDs (comma-separated) allowed to use /admin_boosterkit
# regardless of server permissions -- e.g. "111111111111111111,222222222222222222".
# A user with the "Administrator" permission in the server they're using the
# command in is always allowed too, so this is mainly for bot owners/devs
# testing in a server they don't otherwise admin.
ADMIN_USER_IDS = {
    int(uid.strip())
    for uid in os.getenv("ADMIN_USER_IDS", "").split(",")
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
