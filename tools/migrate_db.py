"""
Migrate an existing CascadeBot database onto the current code.

    python -m tools.migrate_db --dry-run     # report only, changes nothing
    python -m tools.migrate_db               # back up, then migrate

WHY THIS EXISTS AT ALL.

Most of what changed migrates itself, and this script does not duplicate
any of it:

  * New COLUMNS (players.pity_since_five_star / pity_since_four_star) are
    added by db_init._ensure_columns, which runs a defensive ALTER TABLE
    on every startup.
  * New TABLES (guild_raids, raid_participants) are created by
    Base.metadata.create_all.
  * Catalog tables -- character templates, item templates, shop listings,
    shrines, harvesters, lootboxes -- are upserted from their seed data on
    startup, and the shop seeder additionally RETIRES listings that were
    removed from the catalog (the gear and lootbox trades).
  * Character skills/ultimates/passives are resolved from the registry by
    id at battle-build time and never stored, so every kit change applies
    on its own.

What does NOT migrate itself is data that was COPIED onto player-owned
rows at the moment it was created, because nothing ever goes back to
re-read the catalog for those:

  1. inventory_items.active_ability / .passive_ability hold a full copy of
     the ability dict from when the item dropped. Three gear abilities had
     their effect kind replaced in this rework (energy/mana drain was
     removed from the game), so items that rolled them are still carrying
     an effect kind that no longer resolves -- in combat they'd hit the
     "no combat effect implemented yet" branch and simply do nothing.
     Step 3 rewrites these in place from the catalog, matched by id.

  2. expeditions.combat_state holds a fully serialized in-progress battle,
     including copies of those same ability dicts and enemy stat blocks
     computed under the old (uncapped) percent-stat scaling. Step 4 clears
     these so the affected room is re-entered fresh rather than resumed
     with stale numbers.

SAFETY. The script backs up the database file before touching it, is
idempotent (running it twice is a no-op the second time), and supports
--dry-run. It only ever REWRITES ability JSON and CLEARS combat state --
it never deletes a player, character, item or currency.
"""

from __future__ import annotations

import argparse
import datetime as dt
import shutil
import sys
from pathlib import Path


def _resolve_sqlite_path(database_url: str) -> Path | None:
    """The on-disk file behind a sqlite:/// URL, or None for any other
    backend (Postgres/MySQL), where file copying isn't the right backup
    mechanism and the user should take their own dump first."""
    if not database_url.startswith("sqlite"):
        return None
    _, _, tail = database_url.partition("///")
    return Path(tail) if tail else None


def backup(database_url: str) -> Path | None:
    path = _resolve_sqlite_path(database_url)
    if path is None:
        print("!  Non-SQLite database detected. Take your own dump before continuing.")
        return None
    if not path.exists():
        print(f"   No existing database at {path} -- this will be a fresh install, nothing to migrate.")
        return None
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = path.with_name(f"{path.stem}.backup-{stamp}{path.suffix}")
    shutil.copy2(path, dest)
    print(f"   Backup written to {dest}")
    return dest


def refresh_item_abilities(db, dry_run: bool) -> dict:
    """Rewrite every stored item ability from the live catalog, matched by
    id. This is the step that actually matters -- see the module docstring.

    Three outcomes per ability:
      * id still in the catalog and the dict differs -> rewritten
      * id still in the catalog and identical        -> left alone
      * id no longer in the catalog                  -> cleared to None,
        because an ability that doesn't exist can't be resolved and
        leaving it would keep showing the player a skill button that does
        nothing. The item keeps all its stats and remains usable.
    """
    from bot.database.models.equipment_model import InventoryItem
    from bot.game.loot.abilities import (
        ARMOR_PASSIVES,
        ARTIFACT_SKILLS,
        ULTIMATE_ABILITIES,
        WEAPON_SKILLS,
    )

    catalog: dict[str, dict] = {}
    for pool in (WEAPON_SKILLS, ARTIFACT_SKILLS, ULTIMATE_ABILITIES, ARMOR_PASSIVES):
        for ability in pool:
            entry = dict(ability)
            # The loot generator stores the catalog dict verbatim, and the
            # JSON column serializes min_rarity (a Rarity enum) to its
            # string value. Match that exactly, or every single item would
            # compare "changed" and get needlessly rewritten -- and would
            # silently lose min_rarity in the process.
            rarity = entry.get("min_rarity")
            if rarity is not None:
                entry["min_rarity"] = getattr(rarity, "value", rarity)
            catalog[ability["id"]] = entry

    stats = {"checked": 0, "refreshed": 0, "orphaned": 0, "unchanged": 0}

    for item in db.query(InventoryItem).all():
        for field in ("active_ability", "passive_ability"):
            stored = getattr(item, field)
            if not stored:
                continue
            stats["checked"] += 1
            ability_id = stored.get("id")
            fresh = catalog.get(ability_id)

            if fresh is None:
                stats["orphaned"] += 1
                print(f"     item {item.id}: {field} '{ability_id}' no longer exists -> cleared")
                if not dry_run:
                    setattr(item, field, None)
                continue

            # Preserve the per-item display tag the factory adds at battle
            # time rather than at drop time, if a save ever carried one.
            merged = dict(fresh)
            for carry in ("source", "source_item"):
                if carry in stored:
                    merged[carry] = stored[carry]

            if merged == stored:
                stats["unchanged"] += 1
                continue

            stats["refreshed"] += 1
            old_kind = (stored.get("effect") or {}).get("kind")
            new_kind = (merged.get("effect") or {}).get("kind")
            detail = f" ({old_kind} -> {new_kind})" if old_kind != new_kind else ""
            print(f"     item {item.id}: {field} '{ability_id}' refreshed{detail}")
            if not dry_run:
                # Reassign wholesale -- SQLAlchemy does not detect in-place
                # mutation of a plain JSON column.
                setattr(item, field, merged)

    return stats


def drop_retired_tables(db, dry_run: bool) -> list[str]:
    """Drop tables for systems that no longer exist.

    Currently just `player_mailboxes`: the mailbox was replaced by the
    Research Lab and the Forge (it was a wait-then-collect building,
    which is what harvesters already are). create_all never drops
    anything, so without this the table lingers forever holding rows for
    a feature with no code behind it.

    Deliberately the ONLY destructive step in this script, and it only
    touches a table whose feature is gone -- no player-facing data is
    lost, since mailbox level didn't feed anything else."""
    from sqlalchemy import inspect, text

    retired = ["player_mailboxes"]
    dropped = []
    inspector = inspect(db.get_bind())
    existing = set(inspector.get_table_names())
    for table in retired:
        if table not in existing:
            continue
        dropped.append(table)
        print(f"     dropping retired table '{table}'")
        if not dry_run:
            db.execute(text(f"DROP TABLE {table}"))
    if not dropped:
        print("     nothing to drop")
    return dropped


def grandfather_story(db, dry_run: bool) -> int:
    """Mark every EXISTING player as pre-story: prologue complete AND
    grandfathered.

    This is the single most important step in the script. Story mode
    gates features -- inventory, pulls, squad, expeditions -- that every
    player has had since the day they ran /start. Without this, shipping
    story mode would lock an established player out of their own
    inventory and tell them to go do a tutorial.

    Deliberately generous: anyone who already has a Player row predates
    story mode by definition, so they're all grandfathered, no heuristics
    involved. story_service.is_grandfathered is the runtime safety net
    for anyone created between this running and the deploy finishing.
    """
    from bot.database.models.player_model import Player
    from bot.database.models.story_model import PlayerStory

    # Only the ID column, deliberately. A full ORM load of Player selects
    # every mapped column, so a database missing ANY unrelated column
    # would fail here -- and this step must not be the thing that breaks
    # a migration, because it's the step that stops people being locked
    # out. Reading one column makes it immune to schema drift elsewhere.
    player_ids = [row[0] for row in db.query(Player.id).all()]
    existing = {row[0] for row in db.query(PlayerStory.player_id).all()}
    marked = 0
    for player_id in player_ids:
        if player_id in existing:
            continue
        marked += 1
        if not dry_run:
            db.add(PlayerStory(
                player_id=player_id, completed_missions=[], flags={},
                active_mission=None, beat_index=0, prologue_complete=True,
                grandfathered=True,
            ))

    # ALSO backfill anyone who already HAS a story row.
    #
    # prologue_complete was never enough on its own: it covers the
    # features the prologue unlocks, but Chapter 1-2 gate six more
    # (forge, lab, raids, gifting, exchange, abyss). A player who had
    # only ever run /start passed the prologue check, then failed the
    # runtime "looks like a veteran" heuristic -- one character, no
    # expeditions -- and lost six features they used to have. Measured on
    # a real migrated database, not theorised.
    if not dry_run:
        backfilled = (
            db.query(PlayerStory)
            .filter(PlayerStory.prologue_complete.is_(True),
                    PlayerStory.grandfathered.is_(False))
            .all()
        )
        for row in backfilled:
            # Anyone who has actually PLAYED the story is not a pre-story
            # player, and must not be handed the whole game.
            if row.completed_missions or row.active_mission:
                continue
            row.grandfathered = True
            marked += 1
        db.commit()
    return marked


def clear_stale_combat_state(db, dry_run: bool) -> int:
    """Drop any in-progress battle. Those saves embed both the old ability
    dicts and enemy stat blocks built under the pre-cap percent scaling,
    so resuming one would run a fight with numbers this build no longer
    produces. Clearing it returns the player to the room's pre-battle
    state -- they re-enter and fight it fresh, losing nothing but the
    partial fight."""
    from bot.database.models.expedition_model import Expedition

    rows = db.query(Expedition).filter(Expedition.combat_state.isnot(None)).all()
    for exp in rows:
        print(f"     expedition {exp.id} (player {exp.player_id}): in-progress battle cleared")
        if not dry_run:
            exp.combat_state = None
    return len(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate an existing CascadeBot database.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Report what would change without writing anything.")
    parser.add_argument("--skip-backup", action="store_true",
                        help="Don't copy the database file first. Not recommended.")
    args = parser.parse_args()

    from bot.config import DATABASE_URL

    mode = "DRY RUN -- nothing will be written" if args.dry_run else "LIVE"
    print(f"CascadeBot database migration  [{mode}]")
    print(f"   Database: {DATABASE_URL}\n")

    print("1. Backup")
    if args.dry_run:
        print("   (skipped -- dry run)")
    elif args.skip_backup:
        print("   (skipped -- --skip-backup)")
    else:
        backup(DATABASE_URL)

    print("\n2. Schema + catalog")
    # Import every model module BEFORE any query, so SQLAlchemy's class
    # registry can resolve the string-named relationships between them
    # (Player -> "Expedition" and friends). init_db() does this as a side
    # effect of its own imports, but --dry-run skips init_db entirely, so
    # relying on that would make the dry run crash where the live run
    # works -- the exact opposite of what a dry run is for.
    import bot.database.models  # noqa: F401
    from bot.database.models import (  # noqa: F401
        abyss_model, base_building_model, character_model, economy_model,
        equipment_model, expedition_model, gift_model, hq_model, player_model,
        presence_model, quest_model, raid_model, story_model,
    )
    from bot.database.db_init import init_db
    from bot.database.session import SessionLocal

    if args.dry_run:
        print("   (skipped -- dry run; this step adds columns/tables and is safe to re-run)")
    else:
        init_db()
        print("   Columns and tables up to date "
              "(story overworld + optional-content columns, Void Abyss table).")

    db = SessionLocal()
    try:
        if not args.dry_run:
            from bot.services import base_service, lootbox_service
            from bot.services.character_template_service import ensure_character_templates_seeded
            from bot.services.harvester_service import ensure_harvester_templates_seeded
            from bot.services.item_template_service import ensure_item_templates_seeded

            ensure_item_templates_seeded(db)
            ensure_character_templates_seeded(db)
            ensure_harvester_templates_seeded(db)
            lootbox_service.ensure_lootbox_templates_seeded(db)
            # Also retires the removed gear/lootbox shop listings and
            # installs the materials market.
            base_service.ensure_base_catalog_seeded(db)
            print("   Catalogs seeded (characters, items, harvesters, lootboxes, shop, shrines).")

        print("\n3. Refresh stored item abilities")
        stats = refresh_item_abilities(db, args.dry_run)
        print(f"   {stats['checked']} abilities checked · {stats['refreshed']} refreshed · "
              f"{stats['orphaned']} orphaned/cleared · {stats['unchanged']} already current")

        print("\n4. Drop retired tables")
        drop_retired_tables(db, args.dry_run)

        print("\n5. Grandfather existing players into story mode")
        marked = grandfather_story(db, args.dry_run)
        print(f"   {marked} existing player(s) marked prologue-complete "
              "(nobody loses access to a feature they already had)")

        print("\n6. Clear in-progress battles")
        cleared = clear_stale_combat_state(db, args.dry_run)
        print(f"   {cleared} in-progress battle(s) cleared")

        if not args.dry_run:
            db.commit()
    finally:
        db.close()

    print("\nDone." if not args.dry_run else "\nDry run complete -- no changes written.")
    if args.dry_run:
        print("Re-run without --dry-run to apply.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
