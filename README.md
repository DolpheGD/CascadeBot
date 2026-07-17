# CascadeBot

A Discord roguelite RPG: procedurally generated dungeons, ATB-based turn combat,
Diablo-style loot, and a full economy (gold/shards, harvesters, gacha, lootboxes) --
all played entirely through slash commands and buttons.

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
   character/item/harvester/lootbox catalogs automatically -- no manual
   migration step.

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
- `/daily` -- claim daily reward (gold, streak bonus, materials, lootboxes)
- `/harvesters` -- buy, upgrade, and collect passive income
- `/pull` -- gacha pull for characters and gear (costs Shards)
- `/lootboxes`, `/open <tier>` -- quick-glance and open lootboxes (also
  reachable from `/inventory`)
- `/admin_testgear` -- (Administrator only) grants a full Legendary kit
  (2 weapons, 4 armor pieces, 2 artifacts, 1 scroll, all with abilities)
  plus gold/shards/lootboxes, for quickly testing combat and the UI

### Combat at a glance

Turn order is speed-based (an ATB gauge), not a fixed rotation -- see the
🔀 Turn Order line on the battle message. Each turn is Attack (free, builds
Energy + Mana equal to your Recharge stat), a Skill from an equipped
weapon/artifact (costs Mana), or your Ultimate from your character's own
kit (usable once Energy reaches 100). There's no defending or fleeing, and
no dodge/miss chance -- every hit lands, mitigated only by Defense.
Switching which enemy you're targeting is a free action.

### Characters

Every character has a mechanical identity, not just a different portrait --
their skills, ultimate, and passive scale off different stats on purpose:

| Character | Class | Identity |
|---|---|---|
| FAX | Support DPS | Stacks damage and speed together (pilot fantasy) |
| Nexus | Amplifier | Buffs the whole team's Recharge |
| Sader Vorae | Support DPS | Stacks Crit Damage |
| Nebula | Amplifier | Team-wide Speed ultimate |
| Bee Jee | Sustain | Team heals that scale off her own Defense |
| Refender | Sustain | Team heals off Defense, embodying a "balance" philosophy |
| Lily Lovelace | Sustain | A cook who tends the battlefield like a kitchen |
| Arkiver | DPS | Straightforward elemental gauntlet damage |
| Josh | DPS | High-attack scaling, the World Aligners' leader |
| "You" | DPS (switchable) | The player's own free avatar; can freely change class |

Characters are rated 3★ to 5★ and pulled via `/pull` alongside gear.

### Loot and materials

Equipment rarity runs `Common → Uncommon → Rare → Epic → Legendary → Mythic
→ Divine`. Every material a piece of gear is crafted from has its own
rarity band -- crude materials like leather can only ever roll
Common-Uncommon gear, while exotic materials like void or entropy can roll
all the way up to Mythic-Divine. Rarity is rolled first, then the game picks
a template compatible with that rarity, so drop tables stay honest about
what a given material can actually produce.

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
- **Rarity and templates are decoupled.** Loot generation rolls a rarity
  first, then filters equipment templates down to ones compatible with that
  roll -- rather than picking a template and deriving its rarity -- so
  material tiers, gacha, lootboxes, and dungeon drops all share one
  consistent rule for "what can this rarity actually be."

See inline docstrings throughout `bot/services/` and `bot/game/` for the
reasoning behind specific design choices (damage formula, rarity curves,
turn order, character kits, etc).
