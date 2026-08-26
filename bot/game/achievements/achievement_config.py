"""
Achievements and the titles they grant.

WHY THIS IS A LENS, NOT A SYSTEM. Every achievement below is computed
from state the game ALREADY stores -- completed missions, finished
expeditions, Abyss stars, roster size, resonance, evolutions, challenge
wins, dojo clears, prestige count, streaks. Nothing here adds a counter,
a hook, or a write to any existing code path.

That constraint is doing real work. The obvious way to build achievements
is to sprinkle `record_progress("killed_a_boss")` calls through combat,
and it is how achievement systems become a maintenance tax: seven battle
entry points, each one a place to forget, and a counter that silently
stops incrementing is invisible until a player asks why their progress
stalled. Deriving instead means an achievement cannot drift from the
thing it describes, because it IS the thing it describes.

The cost of that choice is honest and worth stating: anything the game
does not already record cannot be an achievement. There is no "defeat 100
Coolant Wraiths", because nothing counts enemies killed by type, and
adding that would mean writing to the database on every kill.

TITLES ARE THE REWARD, and deliberately the only one.

No achievement grants currency, materials or XP. The moment they do, they
stop being a record of what you did and become a checklist to farm --
and several of these would then be gameable (dojo clears, challenge
wins). A title costs nothing, inflates nothing, and is worth exactly as
much as the thing it says you did.

TIERS exist so a category has a shape: bronze is "you have started",
gold is "you have finished". A player should be able to look at one
category and know roughly how far through it they are.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Achievement:
    id: str
    name: str
    description: str
    category: str
    # The metric key from achievement_service.metrics(), and the value
    # that metric must reach.
    metric: str
    threshold: int
    tier: str = "bronze"
    # A title this unlocks, or None. Titles are the only reward.
    title: str | None = None


# Categories, in the order they are shown.
CATEGORIES = ("Story", "Expeditions", "The Abyss", "Roster",
              "Mastery", "Competition", "Dedication")

TIER_EMOJI = {"bronze": "🥉", "silver": "🥈", "gold": "🥇", "legend": "🏆"}


ACHIEVEMENTS: list[Achievement] = [
    # ---- Story ------------------------------------------------------
    Achievement("story_first", "Signed On", "Complete your first mission.",
                "Story", "missions_completed", 1, "bronze"),
    Achievement("story_ten", "On The Books", "Complete 10 missions.",
                "Story", "missions_completed", 10, "silver"),
    Achievement("story_prologue", "Out Of The Lab",
                "Finish the prologue.", "Story", "prologue_complete", 1,
                "bronze", title="Cascade Recruit"),
    Achievement("story_all", "Nothing Left To File",
                "Complete every mission in the game.",
                "Story", "missions_completed", 48, "legend",
                title="The One Who Read It All"),

    # ---- Expeditions -------------------------------------------------
    Achievement("exp_first", "First Descent", "Finish an expedition.",
                "Expeditions", "expeditions_completed", 1, "bronze"),
    Achievement("exp_twentyfive", "Seasoned", "Finish 25 expeditions.",
                "Expeditions", "expeditions_completed", 25, "silver"),
    Achievement("exp_hundred", "Career Depth", "Finish 100 expeditions.",
                "Expeditions", "expeditions_completed", 100, "gold",
                title="Deepworker"),
    Achievement("exp_regions", "Every Road", "Clear every region at least once.",
                "Expeditions", "regions_cleared", 6, "gold",
                title="Cartographer"),

    # ---- The Abyss ---------------------------------------------------
    Achievement("abyss_first", "Down The Threshold", "Earn your first Abyss star.",
                "The Abyss", "abyss_stars", 1, "bronze"),
    Achievement("abyss_twelve", "Descending", "Earn 12 Abyss stars.",
                "The Abyss", "abyss_stars", 12, "silver"),
    Achievement("abyss_all", "The Bottom", "Earn all 36 Abyss stars.",
                "The Abyss", "abyss_stars", 36, "legend",
                title="Abyssal"),

    # ---- Roster ------------------------------------------------------
    Achievement("roster_five", "A Team", "Own 5 characters.",
                "Roster", "characters_owned", 5, "bronze"),
    Achievement("roster_twenty", "Full Bench", "Own 20 characters.",
                "Roster", "characters_owned", 20, "silver"),
    Achievement("roster_all", "Everyone", "Own every character.",
                "Roster", "characters_owned", 35, "legend",
                title="Talent Scout"),
    Achievement("cards_ten", "Collector", "Own 10 Character Cards.",
                "Roster", "cards_owned", 10, "bronze"),
    Achievement("cards_all", "The Whole Deck", "Own every Character Card.",
                "Roster", "cards_owned", 38, "legend",
                title="Archivist"),

    # ---- Mastery -----------------------------------------------------
    Achievement("level_hundred", "Ceiling", "Take a character to level 100.",
                "Mastery", "highest_character_level", 100, "gold",
                title="Perfectionist"),
    Achievement("evolve_first", "Ascension", "Evolve a character.",
                "Mastery", "evolutions_done", 1, "bronze"),
    Achievement("evolve_five", "Star Maker", "Perform 5 evolutions.",
                "Mastery", "evolutions_done", 5, "silver"),
    Achievement("resonance_max", "In Tune",
                "Take a character to maximum resonance.",
                "Mastery", "max_resonance_characters", 1, "gold",
                title="Resonant"),
    Achievement("divine_item", "Divine Right", "Own a Divine item.",
                "Mastery", "divine_items", 1, "silver"),

    # ---- Competition -------------------------------------------------
    Achievement("challenge_first", "Sparring", "Win a squad challenge.",
                "Competition", "challenge_wins", 1, "bronze"),
    Achievement("challenge_fifty", "Contender", "Win 50 squad challenges.",
                "Competition", "challenge_wins", 50, "gold",
                title="Undefeated"),
    Achievement("dojo_built", "Instructor", "Publish a dojo challenge.",
                "Competition", "dojo_published", 1, "bronze",
                title="Instructor"),
    Achievement("dojo_cleared", "Student", "Clear 10 dojo challenges.",
                "Competition", "dojo_clears", 10, "silver"),

    # ---- Dedication --------------------------------------------------
    Achievement("daily_seven", "Regular", "Reach a 7-day daily streak.",
                "Dedication", "daily_streak", 7, "bronze"),
    Achievement("daily_thirty", "Fixture", "Reach a 30-day daily streak.",
                "Dedication", "daily_streak", 30, "gold",
                title="Reliable"),
    Achievement("prestige_first", "Again, From The Top", "Prestige once.",
                "Dedication", "prestige_count", 1, "gold",
                title="Reborn"),
    Achievement("prestige_three", "And Again", "Prestige three times.",
                "Dedication", "prestige_count", 3, "legend",
                title="Eternal"),
]


BY_ID = {a.id: a for a in ACHIEVEMENTS}

# Every title in the game, and what earns it. Derived rather than listed
# separately so a title cannot exist with no way to get it.
TITLES = {a.title: a for a in ACHIEVEMENTS if a.title}


def by_category() -> dict[str, list[Achievement]]:
    out: dict[str, list[Achievement]] = {c: [] for c in CATEGORIES}
    for achievement in ACHIEVEMENTS:
        out.setdefault(achievement.category, []).append(achievement)
    return out
