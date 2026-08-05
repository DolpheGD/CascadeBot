"""
Every discord.Embed the bot renders lives in this package, kept separate from
the cogs so presentation never gets tangled with interaction/DB plumbing.

This was a single 1300-line bot/utils/embedder.py module. It is now split one
module per UI surface -- the same section boundaries the old file already had
as comment banners -- so a change to, say, the combat message doesn't mean
scrolling past the encyclopedia renderers to find it:

    _shared.py       constants + small formatting helpers used across sections
    profile.py       /profile
    dungeon.py       expedition floor map / room choices
    combat.py        battle message, log, info, end-of-run summary
    inventory.py     /inventory (detail + list) and /stash
    gacha.py         /pull results and /pull_rates
    encounters.py    interactive dungeon NPC encounters
    quests.py        /quests board
    domains.py       /domains
    vote.py          /vote (top.gg voting)
    relics.py        run-scoped relics + the campfire choice
    encyclopedia.py  /encyclopedia
    raid.py          co-op guild raids + server leaderboards

Everything is re-exported here, so existing `from bot.utils import embedder`
call sites keep working unchanged -- `embedder.combat_embed(...)` still
resolves exactly as before. Import from the specific submodule in new code if
you prefer; both are supported.
"""

from __future__ import annotations

from bot.utils.embedder._shared import (
    ROOM_TYPE_EMOJI,
    RARITY_COLORS,
    RARITY_EMOJI,
    STAT_EMOJI,
    STAT_LABEL,
    PERCENT_STATS,
    _fmt_stat,
    _fmt_stat_with_base,
    _bar,
)
from bot.utils.embedder.profile import (
    gift_collected_embed,
    gift_inbox_embed,
    gift_sent_embed,
    account_profile_embed,
    PROFILE_PAGE_COUNT,
    PROFILE_PAGE_TITLES,
    _profile_abilities_page,
    _profile_equipment_page,
    _profile_overview_page,
    profile_embed,
)
from bot.utils.embedder.dungeon import (
    dungeon_map_embed,
)
from bot.utils.embedder.story import (
    beat_embed as story_beat_embed,
    map_embed as story_map_embed,
    mission_complete_embed as story_mission_complete_embed,
    note_embed as story_note_embed,
    story_menu_embed,
)
from bot.utils.embedder.raid import (
    leaderboard_embed,
    raid_attack_result_embed,
    raid_claim_embed,
    raid_menu_embed,
    raid_status_embed,
    raid_tiers_help_embed,
)
from bot.utils.embedder.combat import (
    _intent_lines,
    _recent_log_lines,
    _turn_order_line,
    battle_info_embed,
    battle_log_embed,
    combat_embed,
    dungeon_map_graph_embed,
    expedition_summary_embed,
    info_page_count,
    info_page_targets,
)
from bot.utils.embedder.inventory import (
    ITEMS_PER_LIST_PAGE,
    entry_detail_embed,
    general_inventory_embed,
    inventory_list_embed,
    item_detail_embed,
    lootbox_detail_embed,
)
from bot.utils.embedder.gacha import (
    echo_exchange_embed,
    STAR_EMOJI,
    star_label,
    gacha_pull_embed,
    gacha_rates_embed,
    resonance_embed,
)
from bot.utils.embedder.encounters import (
    encounter_embed,
)
from bot.utils.embedder.quests import (
    quest_board_embed,
)
from bot.utils.embedder.domains import (
    _energy_bar_line,
    domain_menu_embed,
    domain_result_embed,
    domain_tier_embed,
)
from bot.utils.embedder.relics import (
    campfire_embed,
    relic_gained_embed,
    relic_lines,
)
from bot.utils.embedder.vote import (
    vote_claimed_embed,
    vote_prompt_embed,
    vote_unconfigured_embed,
)
from bot.utils.embedder.encyclopedia import (
    ENCYCLOPEDIA_ENTRIES_PER_PAGE,
    _encyclopedia_ability_embed,
    _encyclopedia_character_embed,
    _encyclopedia_class_embed,
    _encyclopedia_enemy_embed,
    _encyclopedia_item_embed,
    _encyclopedia_material_embed,
    encyclopedia_categories_embed,
    encyclopedia_detail_embed,
    encyclopedia_list_embed,
)

__all__ = [
    "ENCYCLOPEDIA_ENTRIES_PER_PAGE",
    "ITEMS_PER_LIST_PAGE",
    "PERCENT_STATS",
    "PROFILE_PAGE_COUNT",
    "PROFILE_PAGE_TITLES",
    "RARITY_COLORS",
    "RARITY_EMOJI",
    "ROOM_TYPE_EMOJI",
    "STAR_EMOJI",
    "star_label",
    "STAT_EMOJI",
    "STAT_LABEL",
    "_bar",
    "_encyclopedia_ability_embed",
    "_encyclopedia_character_embed",
    "_encyclopedia_class_embed",
    "_encyclopedia_enemy_embed",
    "_encyclopedia_item_embed",
    "_encyclopedia_material_embed",
    "_intent_lines",
    "_energy_bar_line",
    "_fmt_stat",
    "_fmt_stat_with_base",
    "_profile_abilities_page",
    "_profile_equipment_page",
    "_profile_overview_page",
    "_recent_log_lines",
    "_turn_order_line",
    "battle_info_embed",
    "battle_log_embed",
    "campfire_embed",
    "combat_embed",
    "domain_menu_embed",
    "domain_result_embed",
    "domain_tier_embed",
    "dungeon_map_embed",
    "dungeon_map_graph_embed",
    "encounter_embed",
    "encyclopedia_categories_embed",
    "encyclopedia_detail_embed",
    "encyclopedia_list_embed",
    "entry_detail_embed",
    "expedition_summary_embed",
    "echo_exchange_embed",
    "gacha_pull_embed",
    "gacha_rates_embed",
    "resonance_embed",
    "general_inventory_embed",
    "info_page_count",
    "info_page_targets",
    "inventory_list_embed",
    "item_detail_embed",
    "lootbox_detail_embed",
    "leaderboard_embed",
    "story_beat_embed",
    "story_map_embed",
    "story_menu_embed",
    "story_note_embed",
    "story_mission_complete_embed",
    "account_profile_embed",
    "gift_collected_embed",
    "gift_inbox_embed",
    "gift_sent_embed",
    "profile_embed",
    "raid_attack_result_embed",
    "raid_claim_embed",
    "raid_menu_embed",
    "raid_status_embed",
    "raid_tiers_help_embed",
    "quest_board_embed",
    "relic_gained_embed",
    "relic_lines",
    "vote_claimed_embed",
    "vote_prompt_embed",
    "vote_unconfigured_embed",
]
