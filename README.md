# CascadeBot

A Discord roguelite: procedurally generated dungeons, turn-based combat,
loot, an economy (gold/shards, harvesters, gacha, lootboxes),
all driven by slash commands and buttons.

## Setup

1. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

2. **Create a Discord application**

   - Go to the [Discord Developer Portal](https://discord.com/developers/applications) → New Application.
   - Under **Bot**, click "Reset Token" and copy it -- this is your `DISCORD_TOKEN`.
   - No privileged intents are required (the bot is entirely slash commands
     and button/select interactions, never raw message content).
   - Under **OAuth2 → URL Generator**, select scopes `bot` and
     `applications.commands`, and bot permissions `Send Messages`,
     `Embed Links`, `Use Slash Commands`. Use the generated URL to invite
     the bot to your test server.

3. **Configure environment**

   ```bash
   cp .env.example .env
   ```

   Fill in `.env`:
   - `DISCORD_TOKEN` -- from step 2.
   - `DATABASE_URL` -- defaults to a local `Cascadebot.db` SQLite file, fine for a test server.
   - `DEV_MODE=True` + `SERVER_ID=<your test server's ID>` -- makes slash
     commands sync instantly to that one server instead of waiting up to an
     hour for global propagation. **Recommended for testing.** Set
     `DEV_MODE=False` (and remove `SERVER_ID`) once you're ready for the
     bot to run in multiple servers.

4. **Run**

   ```bash
   python start_bot.py
   ```

   On first run this creates all database tables and seeds the starter
   item/harvester/lootbox catalogs automatically -- no manual migration step.

## Playing

- `/start` -- create your character (grants starting gold)
- `/adventure` -- start or resume a dungeon expedition
- `/inventory`, `/equip <id>`, `/unequip <id>` -- manage gear
- `/profile` -- view stats
- `/daily` -- claim daily reward (gold, streak bonus, lootboxes)
- `/balance`, `/harvesters`, `/collect` -- passive income
- `/pull` -- gacha pull (costs Shards)
- `/lootboxes`, `/open <tier>` -- manage and open lootboxes

## Architecture notes

- **State is never held only in memory.** Every button/select interaction
  loads the player's state from the database, mutates it, and saves it back
  before responding. A mid-fight battle is fully serialized to
  `Expedition.combat_state` after every action, so it survives a bot
  restart or the player disappearing for a week.
- **Views are persistent and stateless.** `DungeonView`/`CombatView` are
  registered once at startup (`bot.add_view()` in `client.py`), not
  per-message. Callbacks always look up the interacting user's own
  expedition/battle by Discord ID rather than trusting anything embedded in
  the component itself.
- **Mutating commands lock during combat.** `/pull`, `/collect`, `/open`,
  `/equip`, `/unequip` all check `dungeon_service.is_in_combat()` first.

See inline docstrings throughout `bot/services/` and `bot/game/` for the
reasoning behind specific design choices (damage formula, rarity curves,
turn order, etc).

## Known gaps / next steps

- No shop yet (needs a curated, priced item catalog beyond the starter set).
- top.gg vote rewards not yet implemented (requires a public webhook
  endpoint -- a hosting/deployment concern as much as a code one).
- Artifacts (`ArtifactTemplate`/`PlayerArtifact`) exist in the data model
  but aren't yet wired into combat or acquirable through any command.
- Only ~15 item templates and 4 enemy templates exist -- functional, but
  thin. Expanding both is pure content work, no architecture changes needed.
