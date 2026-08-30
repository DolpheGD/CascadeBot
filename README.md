# CascadeBot

A Discord roguelite RPG: procedurally generated dungeons, cycle-based turn combat,
Diablo-style loot, and a full economy (gold/shards, harvesters, gacha, lootboxes) --
all played entirely through slash commands and buttons.

## Setup

**The short version:** get a bot token (step 2 below), then run
`./run.sh` on Linux/macOS or `run.bat` on Windows. It creates the virtual
environment, installs dependencies, migrates the database and starts the
bot, and it's safe to run every time -- it only does the work that's
actually needed. It'll copy `.env.example` to `.env` and stop to tell you
where to paste the token.

```bash
./run.sh              # set up if needed, then start
./run.sh --check      # run the tools/check_*.py suite instead of starting
./run.sh --update     # force-reinstall requirements.txt
./run.sh --no-migrate # skip the schema migration step
```

The rest of this section is what those scripts do, for when you want to
do it by hand or something goes wrong.

1. **Install dependencies**

   ```bash
   python3 -m venv .venv
   .venv/bin/python -m pip install -r requirements.txt   # Windows: .venv\Scripts\python.exe
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
   - `DEV_MODE` + `SERVER_ID` -- **set both or neither**; the bot refuses
     to start with one without the other. `DEV_MODE=True` plus your test
     server's ID makes slash commands sync instantly to that one server
     instead of waiting up to an hour for global propagation, which is
     strongly recommended while testing. The template ships with
     `DEV_MODE=False` so a fresh copy boots as-is.
   - `BOT_OWNER_IDS` -- comma-separated Discord user IDs that may run
     `/grant`, which hands any user any amount of any resource. **Leave it
     empty unless you want that.** An empty list refuses everybody.

     This is the bot's only permission gate, and it is deliberately a
     list of user IDs rather than a Discord permission. "Administrator in
     the server the command was typed in" is not a gate: anyone can
     create a server, invite the bot, and be its administrator inside a
     minute.

4. **Enable top.gg voting** *(optional)*

   Powers `/vote`. Skip this and everything else still works -- `/vote`
   just tells players voting isn't set up.

   - List your bot on [top.gg](https://top.gg) and wait for the listing to
     be approved. Players can't vote for an unlisted bot, and the API
     returns 404 for one.
   - On your bot's listing page, open **Integrations & API** (older
     listings label this tab **Webhooks**) and copy the API token.
   - Put it in `.env` as `TOPGG_TOKEN=...`. Treat it like `DISCORD_TOKEN`
     and keep it out of source control.
   - `TOPGG_BOT_ID` is optional; leave it unset and the bot uses its own
     application ID, which is correct for a normal listing.

   No webhook URL, public hosting, or port forwarding is needed. The bot
   asks top.gg "has this user voted in the last 12h?" when a player runs
   `/vote`, rather than receiving pushed vote notifications. The trade-off
   is that claiming takes a second `/vote` after voting in the browser --
   top.gg's push webhooks would make it instant, but they require a
   publicly reachable HTTPS endpoint.

5. **Run**

   ```bash
   .venv/bin/python start_bot.py
   ```

   On first run this creates all database tables and seeds the starter
   character/item/harvester/lootbox catalogs automatically -- no manual
   migration step.

   When *upgrading* an existing database rather than creating one, run
   `python -m tools.migrate_db` first (`--dry-run` to see what it would do
   without touching anything). It backs up before it starts. `run.sh` /
   `run.bat` do this for you on every launch.

## Playing

`/help` is the in-game version of this list. It is authored rather than
generated -- it says what is worth doing and in what order, which a
generated list cannot -- so `tools/check_help_coverage.py` asserts that it
and this README between them mention every real command, and mention no
command that does not exist.

**Getting started**

- `/start` -- create your profile (grants starting gold/shards and your own
  class-switchable avatar character)
- `/story` -- the main mode: an authored campaign across a walkable
  overworld, with missions, NPCs, side quests, puzzles and commissions
- `/help` -- a paged guide to everything below

**Running content**

- `/adventure` -- start or resume a dungeon expedition. The map is a
  planned route, Slay-the-Spire style: paths fork, and taking one locks
  you out of others, so the whole run is chosen before it is fought
- **Adventure regions**, in order: Glacier 15, The Wastelands, The
  Hotlands, Voidcrest Desert, The Voidlands, Abyssnia, Entrospire
  Deepworks, and **Ocellios Labs**. Each unlocks by clearing the one
  before it. Ocellios is optional endgame -- it gates nothing and its
  loot ceiling is the same Divine as Entrospire, so it exists purely as
  the hardest content in the game, at the biggest reward multipliers.
- `/domains` -- energy-gated single battles for direct rewards, without
  committing to a full expedition
- `/abyss` -- a separate endless-floor gauntlet, run outside the region ladder
- `/raid`, `/raid_claim` -- this server's co-op boss, and your share of it
- `/challenge` -- fight another player's squad offline. Wins bank points
  toward weekly milestones you claim when the cycle resets

**Your squad**

- `/squad`, `/presets` -- manage your team of 4, and save named lineups to
  swap between them
- `/characters` -- everyone you own: stats, equipment and abilities
- `/class`, `/rename` -- switch your avatar's role, or give it your own name
- `/talents` -- spend talent points on a character (one per 5 levels, free respec)
- `/evolve` -- raise a 3★ or 4★ up the star ladder. A native 5★ stays stronger
- `/cards`, `/cardpull` -- Character Cards, pulled with Cores
- `/resonance` -- what duplicate copies have unlocked for a character

**Gear and money**

- `/inventory` -- every item and lootbox you own; open one in Detail mode
  to Equip/Level Up/Reroll/Open it, or jump straight to an entry by number
- `/base forge` -- craft gear in the slot and rarity you choose, salvage
  what you won't use, re-roll an ability, or move one between items
- `/sell_rarity` -- bulk-sell every unequipped item of a given rarity
- `/stash` -- gold, shards, reroll tokens, materials, and lootboxes
- `/open <tier>` -- open all lootboxes of a tier (also reachable from `/stash`)
- `/pull` -- gacha pull for characters (costs Shards); odds and pity are on
  the banner itself, and you can nominate a target 5★
- `/exchange` -- spend Echoes from duplicate pulls on a character you choose

**The base**

- `/base dojo` -- the Dojo: build your own fights from the enemy roster,
  publish them, and play what other people have built. Share codes work
  across servers. Clearing someone's challenge pays a little XP, capped
  daily and scaled to what the fight actually fields -- it is not a
  place to grind
- `/base hq`, `/base harvesters`, `/base shrines`, `/base shop`,
  `/base lab` -- passive income, account-wide research, and the shop.
- `/base dispatch` -- the Dispatch Board. Send characters you aren't
  fielding on timed contracts for materials, gold and XP. Assigned
  characters **cannot be used in your squad until they return**, so the
  board rewards a wide roster rather than a strong one. Opens at HQ
  level 3; slots scale to four by HQ 8.
  These live under the `/base` group, so Discord will show them as you
  type `/base`

**Every day**

- `/daily` -- claim daily reward (gold, streak bonus, materials, lootboxes)
- `/quests` -- one-time beginner quests plus a rerollable repeating quest
- `/vote` -- vote on top.gg every 12h for the game's largest Shard payout,
  plus gold, materials and lootboxes scaling on your vote streak
  (requires `TOPGG_TOKEN`, see Setup step 4)

**Everything else**

- `/profile` -- account level, roster completion, power and currencies
- `/achievements` -- 29 achievements across 7 categories, a collection
  screen, and 14 earnable titles you can wear beside your name on your
  profile and the leaderboard
- `/notifications` -- opt in to reminder DMs. **Off by default**; at most
  one a day, only when something is actually going to waste, and it
  stops trying if your DMs are closed
- `/encyclopedia` -- reference for characters, classes, enemies, abilities,
  equipment, and materials
- `/leaderboard` -- how you rank against everyone else in this server
- `/gift`, `/gifts` -- send another player materials or gold, and collect
  what you have been sent
- `/reset` -- wipe your account and start over, cleanly or with prestige rewards

**Admin**

- `/grant` -- (bot owner only, see `BOT_OWNER_IDS`) give any user any
  amount of any resource
- `/takedown` -- (bot owner only) unpublish a dojo challenge by its share
  code. The character allowlist blocks formatting and mention abuse in
  player-written names; this is for anything a filter can't judge

### Combat at a glance

Turn order is cycle-based: every living combatant acts exactly once per
cycle, and Speed only decides the ORDER within a cycle (fastest first),
never whether a slower combatant gets a turn at all -- see the 🔀 Turn Order
line on the battle message. Some elites and bosses act more than once per
cycle. Each turn is Attack (free, builds Energy + Mana equal to your
Recharge stat), Guard, your Character Skill, a Skill from an equipped
weapon/artifact (all costing Mana), or your Ultimate from your character's
own kit (usable once Energy reaches 50). There's no fleeing, and no
dodge/miss chance -- every hit lands, mitigated only by Defense. Switching
which enemy you're targeting is a free action.

**Intent and counterplay.** Enemies decide their next move before it
happens, and the battle message shows it: who is about to act, on whom,
with what. You get two answers to that information.

- **Guard** halves incoming damage until that character's next turn and
  banks bonus Energy if a hit does land -- so reading a telegraph
  correctly moves you closer to your Ultimate rather than merely costing
  you less.
- **Breaking** empties an enemy's Poise pool (shown under its HP bar).
  Every landed hit chips it: 1 for an Attack, 2 for a Skill, 3 for an
  Ultimate, and once per *hit* for multi-hit skills or per *target* for
  AOE -- which is what makes those the dedicated breaking tools. At zero
  the enemy is **Broken**: its telegraphed move is cancelled outright, it
  loses its next 2 turns, and it takes +50% damage throughout. Poise
  refills on recovery, so chip damage between breaks is wasted and timing
  the commit is the actual decision.

Trash mobs have small poise pools and break incidentally; elites and
bosses have deep ones, so a break there is a window you work toward and
spend. A break can never be consumed without you getting a turn to
capitalise on it, regardless of what the turn order does.

### Campfires and relics

HP persists across every fight in a run and is only restored at a
campfire, which appears before each boss and offers exactly one of:

- **Rest** -- recover 50% of max HP across the squad. Not a full heal;
  the point is that damage taken earlier in a run still costs you
  something later.
- **Attune** -- take one of three offered **relics** instead, and go into
  the boss on whatever HP you have.

Relics are run-scoped party-wide power that vanishes when the expedition
ends: percent stat boosts, granted passives (lifesteal, thornmail, cheat
death), bonus Poise damage for faster breaking, or a gold multiplier.
They also drop from non-final bosses and sometimes from elites. Because
the offer is a choice from a random three, two runs with the same squad
and the same gear end up shaped differently -- which is the point.
Relics never stack with themselves, and an offer never includes one you
already carry.

### Characters

Every character has a mechanical identity, not just a different portrait --
their skills, ultimate, and passive scale off different stats on purpose.
The full roster (25 characters) lives in
`bot/game/characters/character_seed_data.py`; a sample:

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

Characters are rated 3★ to 5★ and pulled via `/pull`. The gacha grants
characters only -- gear comes from dungeon drops, lootboxes, and the shop.
Pulling a duplicate converts into gold + reroll tokens instead of a wasted
second copy.

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
- **Mutating commands lock during combat.** `/pull`, `/base harvesters`,
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
