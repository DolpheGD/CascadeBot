from bot.database.db import engine
from bot.database.models.base_model import Base

# Import every model module so each table registers on Base.metadata before
# create_all runs.
from bot.database.models import (  # noqa: F401
    abyss_model,
    achievement_model,
    base_building_model,
    card_model,
    character_model,
    dojo_model,
    economy_model,
    equipment_model,
    expedition_model,
    gift_model,
    hq_model,
    player_model,
    presence_model,
    pull_model,
    quest_model,
    story_model,
    raid_model,
)


# create_all only creates tables that don't exist yet -- it never adds a
# newly-defined column to a table that was already created by an earlier
# version of a model (no Alembic in this project). Any column added to an
# existing model after its table may already be live in deployed DBs needs
# a defensive ALTER TABLE like this one, run once at every startup; it's a
# no-op once the column is actually there.
def _ensure_columns(conn):
    from sqlalchemy import inspect, text

    inspector = inspect(conn)
    tables = set(inspector.get_table_names())

    def add_column(table: str, column: str, ddl_type: str) -> None:
        if table not in tables:
            return  # create_all will build it fresh, with the column already on it
        if column in {col["name"] for col in inspector.get_columns(table)}:
            return
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}"))

    # custom_name -- lets a player rename their avatar (was hardcoded to
    # the "You" template name everywhere) via
    # character_service.rename_avatar / the /rename command.
    add_column("player_characters", "custom_name", "VARCHAR(32)")

    # Character evolution stage. 0 for every existing character, which is
    # the only honest backfill: nobody has paid for an evolution yet, and
    # granting one retroactively would hand out stat bonuses that the
    # difficulty ladder was not tuned against.
    add_column("player_characters", "evolution_stage", "INTEGER DEFAULT 0")

    # Talent nodes bought, as a JSON list of ids. NULL/absent reads as
    # "nothing bought", which is correct for every existing character --
    # their points are all unspent and waiting, rather than auto-assigned
    # to a build nobody chose.
    add_column("player_characters", "talents", "JSON")

    # Top.gg vote tracking -- see bot/services/vote_service.py. Defaults
    # are spelled out in the DDL as well as on the model so existing rows
    # come back as 0/NULL rather than NULL-where-an-int-is-expected.
    add_column("players", "last_vote_claimed_at", "DATETIME")
    add_column("players", "vote_streak", "INTEGER DEFAULT 0")
    add_column("players", "total_votes", "INTEGER DEFAULT 0")

    # Character gacha pity counters -- see
    # bot/game/economy/character_gacha_config.py. Existing players start
    # at 0, i.e. a fresh pity cycle, which is the generous read of an
    # ambiguous situation (we have no pull history to reconstruct from).
    add_column("players", "pity_since_five_star", "INTEGER DEFAULT 0")

    # Commission claim state -- see quest_model.PlayerQuest. Existing
    # rows are all beginner/basic quests, which never claim, so 0/NULL is
    # the correct backfill for every one of them.
    add_column("player_quests", "is_claimed", "BOOLEAN DEFAULT 0")
    add_column("player_quests", "claimed_at", "DATETIME")
    add_column("players", "pity_since_four_star", "INTEGER DEFAULT 0")

    # Echoes -- the duplicate currency (bot/game/economy/resonance_config.py).
    # Existing players start at 0 rather than being paid retroactively for
    # duplicates they already pulled; their RESONANCE, though, is derived
    # from dupe_count and so applies immediately with no backfill at all
    # (see resonance_config.resonance_for).
    add_column("players", "echoes", "INTEGER DEFAULT 0")

    # Hardest raid difficulty a participant fought at -- drives the
    # absolute reward bonus. NULL on existing rows reads as the default
    # difficulty, i.e. a 1.0x bonus, so nobody's in-flight raid changes.
    add_column("raid_participants", "best_difficulty", "VARCHAR(16)")

    # Story overworld position. NULL `area` is meaningful, not missing:
    # it's how map_service tells "never stepped onto the map" apart from
    # "standing at (0, 0)", which is a wall in every authored area. Any
    # player whose story row predates the overworld reads as NULL and is
    # spawned properly on their first move.
    add_column("player_stories", "area", "VARCHAR(64)")
    add_column("player_stories", "pos_x", "INTEGER DEFAULT 0")
    add_column("player_stories", "pos_y", "INTEGER DEFAULT 0")
    add_column("player_stories", "visited", "JSON")
    add_column("player_stories", "read_tiles", "JSON")
    add_column("player_stories", "pending_hunt", "JSON")
    # An open puzzle, stored as a REFERENCE (area+char, or the active
    # mission's beat). NULL for everyone who has not opened one, which is
    # every existing row. Table is "player_stories" -- the first version
    # of this line said "player_story", which silently did nothing at all
    # because add_column returns early for a table it cannot find.
    add_column("player_stories", "pending_puzzle", "JSON")
    add_column("player_stories", "grandfathered", "BOOLEAN DEFAULT 0")

    # Void Abyss. The table is created fresh by create_all for anyone who
    # doesn't have it, so these ALTERs only matter for a database that saw
    # an earlier version of the model.
    add_column("player_abyss", "run_flawless", "INTEGER DEFAULT 1")
    add_column("player_abyss", "run_fast", "INTEGER DEFAULT 1")

    # Prestige -- see the block on Player. Existing players read as 0
    # prestiges and a best level of 0; the first thing prestige_service
    # does on a reset is raise best_level to the level being left behind,
    # so nobody's history needs backfilling.
    add_column("players", "prestige_count", "INTEGER DEFAULT 0")
    add_column("players", "prestige_best_level", "INTEGER DEFAULT 0")

    # Per-player raid summoning (raid_config.PLAYER_SUMMON_COOLDOWN).
    # NULL means "never summoned", which reads as off cooldown -- the
    # generous default, and correct for everyone who played before this.
    add_column("players", "last_raid_summon_at", "DATETIME")
    add_column("guild_raids", "summoned_by", "BIGINT")

    # Cores -- the Character Card pull currency. Existing players start
    # at 0 rather than being backfilled: Cards are new content and the
    # sources that pay Cores are the ones they'll play next, so a
    # retroactive grant would hand out a banner's worth of pulls for
    # things done before the banner existed.
    add_column("players", "cores", "INTEGER DEFAULT 0")

    # Character Card pity, mirroring the character gacha's counters.
    add_column("players", "card_pity_since_five_star", "INTEGER DEFAULT 0")
    add_column("players", "card_pity_since_four_star", "INTEGER DEFAULT 0")

    # Targeted 5-star nominations. NULL means "no target", which is the
    # correct state for every existing player -- backfilling a target
    # would start silently steering pulls somebody never asked to steer.
    add_column("players", "target_character", "VARCHAR(64)")
    add_column("players", "target_character_guaranteed", "BOOLEAN DEFAULT 0")
    add_column("players", "target_card", "VARCHAR(64)")
    add_column("players", "target_card_guaranteed", "BOOLEAN DEFAULT 0")

    # Async squad challenges. Everyone starts unrated with no history,
    # which is exactly right -- a rating backfilled from gear would seed
    # matchmaking with numbers nobody earned.
    add_column("players", "challenge_power", "INTEGER DEFAULT 0")
    add_column("players", "challenge_wins", "INTEGER DEFAULT 0")
    add_column("players", "challenge_losses", "INTEGER DEFAULT 0")
    add_column("players", "last_challenge_at", "DATETIME")
    add_column("players", "challenges_today", "INTEGER DEFAULT 0")

    # Equipped title. NULL means "no title", which is right for every
    # existing player -- a title is earned, and nobody has earned one yet.
    add_column("players", "active_title", "VARCHAR(64)")

    # Dojo clear tracking. Existing players read as never having cleared
    # anything, which is correct -- the feature did not exist.
    add_column("players", "dojo_clears_today", "INTEGER DEFAULT 0")
    add_column("players", "last_dojo_clear_at", "DATETIME")

    # Presence and reminders. Existing players read as never-seen (NULL),
    # which the away summary treats as "no absence to report" rather than
    # "away forever" -- the first command after this deploys sets it, and
    # nobody gets a spurious welcome-back for time that predates the
    # feature.
    #
    # reminders_enabled defaults to 0: opt-in, for everyone, including
    # players who already existed. Enabling it for the existing player
    # base would be sending unsolicited DMs to every single one of them
    # on the first night.
    add_column("players", "last_seen_at", "DATETIME")
    add_column("players", "reminders_enabled", "BOOLEAN DEFAULT 0")
    add_column("players", "last_reminder_at", "DATETIME")
    add_column("players", "reminder_failures", "INTEGER DEFAULT 0")

    # Challenge cycles. Existing players start in the CURRENT cycle with
    # zero points and nothing banked, which is the only defensible
    # backfill: there is no record of which week their past challenge
    # wins happened in, so any retroactive points would be invented.
    #
    # challenge_claimed_cycle defaults to -1 rather than 0 because 0 is a
    # real cycle index. Defaulting to 0 would tell the game that every
    # existing player had already claimed cycle 0 -- harmless today, and
    # exactly the kind of off-by-one that only shows up when somebody
    # resets the epoch and cycle 0 comes round again.
    add_column("players", "challenge_cycle", "INTEGER DEFAULT 0")
    add_column("players", "challenge_points", "INTEGER DEFAULT 0")
    add_column("players", "challenge_banked_points", "INTEGER DEFAULT 0")
    add_column("players", "challenge_claimed_cycle", "INTEGER DEFAULT -1")

    # booster_kit_claimed was removed with /admin_boosterkit. The column
    # is deliberately NOT dropped from databases that already have it:
    # SQLite drops are rewrites, the column is three bytes, and nothing
    # reads it. A live database should not be restructured to tidy up.

    # Evolution Fragments -- the breakthrough material
    # (bot/game/economy/evolution_config.py). Existing players start at 0,
    # which is deliberately NOT a free pass: gear they have already
    # levelled past a breakthrough keeps that level (nothing is taken
    # away, and no item is rolled back), but the NEXT breakthrough is
    # gated like everyone else's. Backfilling instead would hand a
    # long-standing account a stack of the one resource the system exists
    # to make them go and earn.
    add_column("players", "evolution_fragments", "INTEGER DEFAULT 0")


def init_db():
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        _ensure_columns(conn)


if __name__ == "__main__":
    init_db()
