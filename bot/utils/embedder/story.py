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

STORY_COLOR = discord.Color.from_rgb(88, 101, 242)


def story_menu_embed(story, next_mission: dict | None, player) -> discord.Embed:
    """The `/story` landing screen: where you are and what's next."""
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
        embed.add_field(
            name=f"▶ Next: {next_mission['name']}",
            value=next_mission.get("summary", "​"),
            inline=False,
        )

    for chapter in sc.CHAPTERS:
        marks = []
        for mission in chapter["missions"]:
            done = mission["id"] in completed
            active = story.active_mission == mission["id"]
            marks.append(f"{'✅' if done else '▶️' if active else '⬜'} {mission['name']}")
        embed.add_field(name=chapter["name"], value="\n".join(marks), inline=False)

    if story.active_mission:
        embed.set_footer(text="You have a mission in progress.")
    return embed


def map_embed(area: dict, grid: str, legend: list[str], standing_on: str | None,
              locked: bool = False) -> discord.Embed:
    """The overworld screen: the grid, then what's on it, then what's
    under your feet.

    That order is deliberate. An emoji grid on its own is a puzzle about
    emoji -- the labelled list underneath is what turns it into a place,
    and the "you are standing on" line is what makes the d-pad feel
    connected to anything. Dropping either one was tried and the map
    immediately reads as decoration.
    """
    embed = discord.Embed(
        title=f"🗺️ {area['name']}",
        description=area.get("blurb", ""),
        color=STORY_COLOR,
    )
    embed.add_field(name="​", value=grid, inline=False)

    if legend:
        # 1024-char field ceiling. Areas are small enough that this has
        # never been close, but a truncated legend would silently hide
        # the one tile the player is looking for.
        embed.add_field(name="Here", value="\n".join(legend)[:1024], inline=False)

    if standing_on:
        embed.add_field(
            name="You're standing on",
            value=("🔒 " if locked else "") + standing_on,
            inline=False,
        )
        embed.set_footer(text="Press ✋ to interact.")
    else:
        embed.set_footer(text="Move with the arrows.")
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


def beat_embed(mission: dict, beat: dict, text: str | None = None) -> discord.Embed:
    """One beat. `text` overrides the beat's own body -- used to show the
    RESULT of a choice rather than the prompt that produced it."""
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
    if result.get("rewards"):
        embed.add_field(name="Rewards", value="\n".join(result["rewards"]), inline=False)
    embed.set_footer(text="Use /story to continue.")
    return embed
