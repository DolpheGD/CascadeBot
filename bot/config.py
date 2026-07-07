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

if not DISCORD_TOKEN:
    raise RuntimeError(
        "DISCORD_TOKEN is not set. Copy .env.example to .env and fill it in."
    )

if DEV_MODE and not SERVER_ID:
    raise RuntimeError("DEV_MODE is on but SERVER_ID is not set in .env.")
