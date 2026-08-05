"""
Quests embeds.

The /quests board: beginner quests plus active basic quests.
"""

from __future__ import annotations

import discord

from bot.game.economy.quest_config import BASIC_QUEST_POOL, BEGINNER_QUESTS, MAX_ACTIVE_BASIC_QUESTS
from bot.services.currency_service import format_currency


def quest_board_embed(beginner_quests: list, basic_quests: list, cooldown_remaining, player) -> discord.Embed:
    """`beginner_quests` is the full list of PlayerQuest rows (kind=
    "beginner") for this player, `basic_quests` is every currently-active
    (kind="basic") row -- up to MAX_ACTIVE_BASIC_QUESTS of them -- and
    `cooldown_remaining` is a datetime.timedelta (or None if a new/rerolled
    basic quest is available right now) -- see quest_service.
    get_beginner_quests / get_active_basic_quests /
    basic_quest_reroll_cooldown_remaining."""
    embed = discord.Embed(title="📋 Quests", color=discord.Color.teal())

    # BEGINNER QUESTS DISAPPEAR ONCE THEY'RE ALL DONE.
    #
    # They're one-time, and a finished set is a wall of struck-through
    # text sitting above the quests the player actually opened the board
    # to read. While any are still outstanding they're the most important
    # thing here -- they're the new-player tutorial -- so they stay at the
    # top; the moment the last one closes out, the section retires itself
    # and the board becomes purely about basic quests.
    #
    # Keyed off "are any incomplete" rather than off
    # beginner_quest_bonus_claimed, deliberately: the bonus is claimed by
    # a separate action, and hiding the list before the player has
    # collected it would hide the thing telling them to.
    unfinished = [q for q in beginner_quests if not q.is_completed]
    if unfinished:
        descriptions_by_id = {q["id"]: q["description"] for q in BEGINNER_QUESTS}
        beginner_lines = []
        completed_count = 0
        for quest in beginner_quests:
            desc = descriptions_by_id.get(quest.quest_id, quest.quest_id)
            if quest.is_completed:
                completed_count += 1
                beginner_lines.append(f"✅ ~~{desc}~~")
            else:
                beginner_lines.append(f"⬜ {desc} ({quest.progress}/{quest.goal_count})")
        embed.add_field(
            name=f"🌱 Beginner Quests ({completed_count}/{len(beginner_quests)})",
            value="\n".join(beginner_lines),
            inline=False,
        )
        if not player.beginner_quest_bonus_claimed:
            embed.add_field(
                name="🎁 Completion Bonus",
                value=f"Finish every beginner quest above for {format_currency('shards', 900)}!",
                inline=False,
            )

    if basic_quests:
        for quest in basic_quests:
            desc = next((q["description"] for q in BASIC_QUEST_POOL if q["id"] == quest.quest_id), quest.quest_id)
            reward = next((q["reward"] for q in BASIC_QUEST_POOL if q["id"] == quest.quest_id), {})
            reward_text = ", ".join(format_currency(c, a) for c, a in reward.items())
            status = "✅ Complete!" if quest.is_completed else f"{quest.progress}/{quest.goal_count}"
            embed.add_field(
                name=f"🎯 Basic Quest ({basic_quests.index(quest) + 1}/{MAX_ACTIVE_BASIC_QUESTS})",
                value=f"{desc}\nProgress: {status}\nReward: {reward_text}",
                inline=False,
            )
    else:
        embed.add_field(name=f"🎯 Basic Quests (0/{MAX_ACTIVE_BASIC_QUESTS})", value="*No quests active.*", inline=False)

    open_slots = MAX_ACTIVE_BASIC_QUESTS - len(basic_quests)
    if open_slots > 0:
        embed.set_footer(text=f"{open_slots} quest slot{'s' if open_slots != 1 else ''} open -- roll a new one anytime!")
    elif cooldown_remaining is None:
        embed.set_footer(text="All slots full, but your oldest quest is ready to reroll!")
    else:
        hours, remainder = divmod(int(cooldown_remaining.total_seconds()), 3600)
        minutes = remainder // 60
        embed.set_footer(text=f"All slots full. Oldest quest can be rerolled in {hours}h {minutes}m.")

    return embed
