# CascadeBot

A Discord roguelite: procedurally generated dungeons, turn-based combat,
Diablo-style loot, an economy (gold/shards, harvesters, gacha, lootboxes),
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
- `/adventure` -- start or resume a dungeon expedition; every floor offers
  several room choices, and combat/movement happen entirely through
  buttons and dropdowns on the message
- `/profile` -- 3-page view: Overview (stats/currency), Equipment (every
  slot, empty or filled), and Abilities (weapon/artifact skills, ultimate,
  passives)
- `/inventory` -- browse a compact list of every item and lootbox you own,
  or open one in Detail mode to Equip/Level Up/Reroll/Open it; jump to a
  specific entry by number instead of paging through everything
- `/daily` -- claim daily reward (gold, streak bonus, lootboxes)
- `/harvesters` -- buy, upgrade, and collect passive income
- `/pull` -- gacha pull (costs Shards)
- `/lootboxes`, `/open <tier>` -- quick-glance and open lootboxes (also
  reachable from `/inventory`)
- `/admin_testgear` -- (Administrator only) grants a full Legendary kit
  (2 weapons, 4 armor pieces, 2 artifacts, 1 scroll, all with abilities)
  plus gold/shards/lootboxes, for quickly testing combat and the UI

### Combat at a glance

Turn order is speed-based (an ATB gauge), not a fixed rotation -- see the
🔀 Turn Order line on the battle message. Each turn is Attack (free, builds
Energy + Mana equal to your Recharge stat), a Skill from an equipped
weapon/artifact (costs Mana), or your Ultimate from an equipped Scroll
(usable once Energy reaches 100). There's no defending or fleeing, and no
dodge/miss chance -- every hit lands, mitigated only by Defense. Switching
which enemy you're targeting is a free action.

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
- **Mutating commands lock during combat.** `/pull`, `/harvesters`,
  `/open`, and equip/level-up/reroll/open-lootbox actions inside
  `/inventory` all check `dungeon_service.is_in_combat()` first.

See inline docstrings throughout `bot/services/` and `bot/game/` for the
reasoning behind specific design choices (damage formula, rarity curves,
turn order, etc).

## Known gaps / next steps

- No shop yet (needs a curated, priced item catalog beyond the starter set).
- top.gg vote rewards not yet implemented (requires a public webhook
  endpoint -- a hosting/deployment concern as much as a code one).
- `Expedition.current_hp` is tracked but not yet synced from/to actual
  battle HP -- every encounter currently starts at full HP regardless of
  prior damage taken earlier in the same expedition. Wiring that up (and
  deciding whether HP regenerates between rooms or only at campfires) is
  a natural next step.
- Only ~24 item templates and 6 enemy templates exist -- functional, but
  thin. Expanding both is pure content work, no architecture changes needed.
