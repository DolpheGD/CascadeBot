"""
Story mode embeds.

Deliberately quieter than the rest of the game's views. Story beats are
text the player is meant to READ, and the surrounding UI competing for
attention is the fastest way to make sure they don't. No stat blocks, no
progress bars, one speaker at a time.
"""

from __future__ import annotations

import discord

from bot.game.story import story_config as sc
from bot.utils.embedder._shared import fit_field

STORY_COLOR = discord.Color.from_rgb(88, 101, 242)

# Rarity/tier glyphs for the reward line. Kept here rather than imported
# from the loot layer because this is display shorthand for a one-line
# summary, not the authoritative rarity styling.
_TIER_ICON = {
    "common": "⚪", "uncommon": "🟢", "rare": "🔵",
    "epic": "🟣", "legendary": "🟠", "mythic": "🔴",
}


def _reward_summary(totals: dict) -> str:
    """One line: '💰 200 gold · 🟢 Uncommon gear · ⚪ 1 lootbox'.

    Empty string when a mission grants nothing, so the caller can leave
    the label off entirely rather than printing 'Rewards: none' -- plenty
    of story missions are pure narrative and shouldn't look like they're
    short-changing anyone.
    """
    from bot.services.currency_service import format_currency

    parts: list[str] = []
    for key, value in totals.items():
        if key == "item":
            for tier, count in value.items():
                icon = _TIER_ICON.get(tier, "🎁")
                parts.append(f"{icon} {count}× {tier.title()} gear"
                             if count > 1 else f"{icon} {tier.title()} gear")
        elif key == "lootbox":
            for tier, count in value.items():
                icon = _TIER_ICON.get(tier, "🎁")
                parts.append(f"{icon} {count}× {tier.title()} lootbox"
                             if count > 1 else f"{icon} {tier.title()} lootbox")
        elif key == "character":
            parts.extend(f"⭐ {name}" for name in value)
        else:
            parts.append(format_currency(key, value))
    return " · ".join(parts)


def default_chapter_page(story, next_mission: dict | None) -> int:
    """Which chapter the menu should open on.

    WHERE THE PLAYER IS, not the beginning. Opening on the prologue for
    somebody four chapters in would make the first thing they see the
    part they finished longest ago, and cost them two clicks every
    single time.

    Falls back to the last chapter when there is no next mission, because
    a player who has finished everything is at the END of the story, not
    the start of it.
    """
    target = (story.active_mission
              or (next_mission or {}).get("id"))
    if target:
        for index, chapter in enumerate(sc.CHAPTERS):
            if any(mission["id"] == target for mission in chapter["missions"]):
                return index
    return max(0, len(sc.CHAPTERS) - 1)


def chapter_page_count() -> int:
    return len(sc.CHAPTERS)


def story_menu_embed(story, next_mission: dict | None, player,
                     page: int | None = None) -> discord.Embed:
    """The `/story` landing screen: where you are and what's next.

    ONE CHAPTER PER PAGE. Every chapter used to be listed at once -- six
    fields and forty-eight mission names on a single screen, which is a
    wall to read and grows with every chapter written. At six chapters it
    was 972 characters and merely hard to scan; it has a hard ceiling at
    25 fields and 6000 characters, and the failure at that point is an
    embed Discord refuses to send at all.

    Paging fixes the readability now and removes the ceiling entirely, so
    adding chapter six or sixteen changes nothing about this screen.
    """
    embed = discord.Embed(title="📖 Story", color=STORY_COLOR)

    completed = set(story.completed_missions or [])
    if next_mission is None:
        embed.description = (
            "You're up to date with everything written so far.\n"
            "*More chapters are coming.*"
        )
    else:
        chapter = sc.chapter_of(next_mission["id"])
        embed.description = (
            f"**{chapter['name']}**\n{chapter['blurb']}" if chapter else ""
        )
        # WHAT IT PAYS, on the same field as what it is.
        #
        # The menu named the next mission and described it, and said
        # nothing at all about the reward -- so the only way to find out
        # what a mission was worth was to finish it. Every other
        # content screen in the game (quests, raids, the shop) leads with
        # its payout; story was the one place you were asked to commit
        # blind.
        #
        # The line is built from story_config.mission_rewards, which reads
        # the mission's own reward beats, so it cannot advertise something
        # the mission doesn't actually grant.
        reward_line = _reward_summary(sc.mission_rewards(next_mission))
        embed.add_field(
            name=f"▶ Next: {next_mission['name']}",
            value=(next_mission.get("summary", "​")
                   + (f"\n\n**Rewards:** {reward_line}" if reward_line else "")),
            inline=False,
        )

    # ---- one chapter, and a progress line for the rest --------------
    if page is None:
        page = default_chapter_page(story, next_mission)
    page = max(0, min(page, len(sc.CHAPTERS) - 1))
    chapter = sc.CHAPTERS[page]

    marks = []
    for mission in chapter["missions"]:
        done = mission["id"] in completed
        active = story.active_mission == mission["id"]
        marks.append(f"{'✅' if done else '▶️' if active else '⬜'} {mission['name']}")
    done_here = sum(1 for m in chapter["missions"] if m["id"] in completed)
    embed.add_field(
        name=f"{chapter['name']} — {done_here}/{len(chapter['missions'])}",
        value="\n".join(marks)[:1024],
        inline=False)

    # A one-line map of the whole story, so paging away from a chapter
    # does not mean losing sight of where it sits. Cheap to render and it
    # is what the removed all-chapters view was really providing.
    overview = []
    for index, other in enumerate(sc.CHAPTERS):
        cleared = sum(1 for m in other["missions"] if m["id"] in completed)
        total = len(other["missions"])
        marker = "✅" if cleared == total else ("▶️" if cleared else "⬜")
        overview.append(f"**{marker} {index + 1}**" if index == page
                        else f"{marker} {index + 1}")
    embed.add_field(name="Chapters",
                    value="  ".join(overview) + f"   ·  {len(completed)}/"
                          f"{sum(len(c['missions']) for c in sc.CHAPTERS)} missions",
                    inline=False)

    footer = f"Chapter {page + 1} of {len(sc.CHAPTERS)}"
    if story.active_mission:
        footer += "  ·  You have a mission in progress."
    embed.set_footer(text=footer)
    return embed


def map_embed(area: dict, grid: str, legend: list[str], standing_on: str | None,
              locked: bool = False, readout: dict | None = None,
              exits: list[str] | None = None) -> discord.Embed:
    """The overworld screen: the grid, then what's on it, then what's
    under your feet.

    That order is deliberate. An emoji grid on its own is a puzzle about
    emoji -- the labelled list underneath is what turns it into a place,
    and the "you are standing on" line is what makes the d-pad feel
    connected to anything. Dropping either one was tried and the map
    immediately reads as decoration.
    """
    # THE ROOM NAME IS THE HEADLINE, and the region sits above it.
    #
    # A grid of emoji with no label is a puzzle; the same grid titled
    # "Sector 9 — Containment" inside "OCELLIOS LAB" is a place you can
    # navigate by memory. Every room names itself and its region, so a
    # player always knows both where they are and where that is.
    region = area.get("region")
    embed = discord.Embed(
        title=f"🗺️ {area['name']}",
        description=(f"*{region}*\n\n" if region else "") + area.get("blurb", ""),
        color=STORY_COLOR,
    )
    embed.add_field(name="​", value=grid, inline=False)

    if legend:
        # 1024-char field ceiling. Areas are small enough that this has
        # never been close, but a truncated legend would silently hide
        # the one tile the player is looking for.
        embed.add_field(name="Here", value="\n".join(legend)[:1024], inline=False)

    # WAYS OUT -- its own field, below what's in the room.
    #
    # "Here" answers what is in this place; this answers how you leave it
    # and where each door goes. They were one list, and the doors lost:
    # in a room with a mission, two NPCs and four exits, the exits are
    # the entries a player scans for when they are done and want to move
    # on, and they were scattered through everything else without ever
    # naming a destination.
    #
    # Placed AFTER "Here" deliberately -- you decide what to do in a room
    # before you decide to leave it, and the field order should match
    # that order.
    if exits:
        embed.add_field(name="Ways out", value="\n".join(exits)[:1024], inline=False)

    # Keep the field structure stable between ordinary and interactive tiles.
    # Zero-width content reserves the field without displaying a placeholder.
    embed.add_field(
        name="You're standing on" if standing_on else "\u200b",
        value=(("🔒 " if locked else "") + standing_on
               if standing_on else "\u200b"),
        inline=False,
    )

    if standing_on:
        embed.set_footer(text="Press ✋ to interact.")
    else:
        embed.set_footer(text="Move with the arrows.")

    # THE READOUT: what you just interacted with, shown ON the map.
    #
    # Reading a note used to REPLACE this whole screen with a note embed
    # and a "back to map" button, so inspecting three things in a room
    # was six screen changes and you lost your place every time. In an
    # RPG hub -- where the intended loop is walk, talk, read, talk again
    # -- that friction is most of the experience.
    #
    # Rendered last so the map, the legend and your position stay put
    # above it and only the bottom of the embed changes as you poke at
    # things.
    if readout:
        title = f"{readout.get('emoji', '')} {readout.get('name', '')}".strip() or "​"
        embed.add_field(name=title[:256], value=(readout.get("text") or "​")[:1024],
                        inline=False)
    return embed


def note_embed(name: str, emoji: str, text: str) -> discord.Embed:
    """A flavour tile. Same visual weight as a dialogue beat on purpose --
    optional content that looks cheaper than required content teaches the
    player not to read it."""
    return discord.Embed(
        title=f"{emoji} {name}".strip(),
        description=text,
        color=STORY_COLOR,
    )


def beat_embed(mission: dict, beat: dict, text: str | None = None,
               rewards: list[str] | None = None) -> discord.Embed:
    """One beat. `text` overrides the beat's own body -- used to show the
    RESULT of a choice rather than the prompt that produced it.

    `rewards` is what the PREVIOUS beat granted. It exists for one
    reason: story_service computed those lines and every caller threw
    them away, so the player read some flavour text about a kit bag and
    their Shard balance silently went up somewhere off-screen. For the
    prologue's Core grants that meant a currency they had never seen
    before arriving with no announcement at all.
    """
    kind = beat.get("kind")
    embed = discord.Embed(color=STORY_COLOR)

    if kind == "dialogue":
        embed.title = beat.get("speaker") or mission["name"]
        embed.description = text or beat.get("text")
    elif kind == "choice":
        embed.title = mission["name"]
        embed.description = text or beat.get("prompt")
    elif kind == "battle":
        embed.title = f"⚔️ {mission['name']}"
        embed.description = beat.get("intro")
    elif kind == "reward":
        embed.title = f"🎁 {mission['name']}"
        embed.description = text or beat.get("text")
    elif kind == "unlock":
        feature = sc.FEATURES.get(beat.get("feature", ""), "Something new")
        embed.title = f"🔓 {feature} unlocked"
        embed.description = text or beat.get("text")
    else:
        embed.title = mission["name"]
        embed.description = text

    # WHAT YOU ACTUALLY GOT, on the beat that gave it to you.
    #
    # Rendered for any beat that granted something, not just `reward`
    # beats -- an unlock or a choice can carry a grant too, and a reward
    # that appears for some beat kinds and not others is worse than one
    # that never appears, because it teaches the player to stop looking.
    if rewards:
        embed.add_field(name="Received", value=fit_field(rewards), inline=False)

    embed.set_author(name=mission["name"])
    return embed


def mission_complete_embed(mission: dict, result: dict) -> discord.Embed:
    embed = discord.Embed(
        title=f"✅ {mission['name']}",
        description=(
            "*Replayed — reduced rewards.*" if result.get("replay")
            else "Mission complete."
        ),
        color=discord.Color.gold(),
    )
    # The mission's WHOLE payout, re-derived from its beats.
    #
    # result["rewards"] only ever holds what the LAST beat granted, so a
    # mission that paid out in three places showed a third of itself
    # here. Deriving from sc.mission_rewards gives the total, and is the
    # same source the /story menu advertises it with -- so the summary
    # you saw before the mission and the one you see after it cannot
    # disagree.
    total = _reward_summary(sc.mission_rewards(mission))
    if total:
        embed.add_field(name="Rewards", value=total[:1024], inline=False)
    elif result.get("rewards"):
        embed.add_field(name="Rewards", value=fit_field(result["rewards"]), inline=False)
    embed.set_footer(text="Use /story to continue.")
    return embed
