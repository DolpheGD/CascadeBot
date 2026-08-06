"""
Combat embeds.

Battle message, battle log, battle info, and the end-of-run
expedition summary.
"""

from __future__ import annotations

import discord

from bot.game.combat import effects
from bot.utils import names
from bot.game.combat.battle import CYCLE_WARNING_THRESHOLD, MAX_BATTLE_CYCLES
from bot.game.combat.effects import BREAK_DAMAGE_BONUS_PERCENT
from bot.database.models.enums import CLASS_DISPLAY_NAME, CharacterClass
from bot.services.currency_service import format_currency
from bot.utils.embedder._shared import (
    ROOM_TYPE_EMOJI,
    STAT_EMOJI,
    STAT_LABEL,
    _bar,
    fit_field,
)

# Combatant.character_class is stored as the plain enum VALUE (a string),
# not the enum -- see the field's comment in combatant.py -- so the info
# page needs a value-keyed lookup rather than CLASS_DISPLAY_NAME directly.
CLASS_DISPLAY_NAME_BY_VALUE = {cls.value: name for cls, name in CLASS_DISPLAY_NAME.items()}

# How many poise pips to render at most, so a 14-poise boss doesn't blow
# out the embed field width.
MAX_POISE_PIPS = 10

# ----------------------------------------------------------------------
# Mobile layout budget.
#
# A Discord embed on a phone fits roughly 32-38 characters before it soft-
# wraps, and a wrapped combatant line is the specific thing that made the
# battle screen unreadable: with a 4-person squad plus 3-5 enemies, every
# line wrapping to two turned ~9 rows into ~18 and pushed the actual
# decision (what's incoming, whose turn it is) off-screen entirely.
#
# So every per-combatant line here is built to a budget: one line, under
# roughly 34 visible characters. That drives two choices below -- names
# are truncated (NAME_BUDGET) and big HP values are abbreviated
# (_short_num: "12.4k" not "12437").
#
# The budget loosened once the avatar THUMBNAIL was replaced by a small
# author icon. set_thumbnail renders a large image on the right that
# every field's text wraps around, so it was costing horizontal width on
# every single line of the most width-starved view in the game;
# set_author costs one short line and nothing horizontally. The HP bar
# (dropped in the first declutter pass) came back with that space.
#
# Anything still left out of this view is one tap away in the ℹ️ Info and
# 📜 Log ephemeral embeds, which have no layout budget to respect.
# ----------------------------------------------------------------------
# Raised from 14/9 after the avatar thumbnail was removed. set_thumbnail
# rendered a large image that every field wrapped around, costing roughly
# a third of the usable width on mobile; set_author costs one short line
# and nothing horizontally, so names can breathe again and fewer of them
# get clipped to an ambiguous "Corrupted Eri…".
# Both budgets live in bot/utils/names.py now, alongside the shortening
# rules and the authored short names that keep them from ever biting.
NAME_BUDGET = names.NAME_BUDGET
TURN_ORDER_NAME_BUDGET = names.TURN_ORDER_BUDGET


def _clip(name: str, budget: int = NAME_BUDGET) -> str:
    """Shorten a bare name STRING (not a Combatant) for the log tail.

    Delegates to names.shorten, which drops whole words rather than
    cutting mid-word -- the old version produced "Xendium Overc…" and, at
    the turn-order budget, rendered two different Wasteland enemies
    identically. Everywhere a Combatant is in hand, names.display_name is
    used instead so the AUTHORED short name wins; this exists only for
    log text, where all we have is the name already baked into a
    sentence."""
    return names.shorten(name, budget)


def _short_num(value: float) -> str:
    """Compact HP/shield rendering: values under 10,000 print in full
    (precision matters when you're deciding whether a hit kills), larger
    ones abbreviate to 1 decimal ("12.4k"). A late-game boss with 250,000
    HP shown in full is 13 characters per side of the slash -- on its own
    enough to wrap the line."""
    value = round(value)
    if value < 10_000:
        return str(int(value))
    if value < 1_000_000:
        return f"{value / 1000:.1f}k"
    return f"{value / 1_000_000:.1f}M"


# ----------------------------------------------------------------------
# Combat
# ----------------------------------------------------------------------

def _turn_order_line(battle, count: int = 5) -> str:
    """Compact turn order, rendered into the embed DESCRIPTION rather than
    its own field -- a field costs a bold header line of vertical space to
    show what is essentially one line of content.

    Five entries at a tight per-name budget. Six full-length names ran
    past 70 visible characters and wrapped even on the full-width
    description line; five clipped ones sit near 50. Five is also about
    as far ahead as the order stays actionable -- beyond that it's a
    projection (see preview_turn_order) that a single kill invalidates."""
    parts = []
    for c in battle.preview_turn_order(count):
        icon = "🧑" if c.is_player else "👹"
        parts.append(f"{icon}{names.display_name(c, TURN_ORDER_NAME_BUDGET)}")
    return " ▸ ".join(parts) if parts else "--"


def _recent_log_lines(battle, count: int = 5, char_limit: int = 900) -> str:
    """A short, in-battlefield tail of the log (see combat_embed) -- the
    last few lines only, further trimmed to fit comfortably inside one
    embed field. Deliberately much shorter than battle_log_embed's full
    history (and shorter than it used to be: 3 lines rather than 4, since
    log lines are full sentences and each one wraps to 2-3 rows on a
    phone); the complete record is one 📜 Log tap away.

    Two categories of pure bookkeeping are filtered out of this window
    (they remain in the full 📜 Log, which is a record rather than a
    summary):

      * Cycle/turn headers ("--- Cycle 2, Turn 7: Josh ---") -- scaffolding
        that says nothing the turn order doesn't, emitted every single
        turn.
      * Resource-gain lines ("Josh gains 6 energy and 0 SP.") -- emitted
        after every basic attack and every Guard, i.e. constantly, and
        already shown live as numbers on each combatant's own row.

    Between them these were routinely 2 of the 3 lines in this window,
    crowding out the one line that actually said what happened."""
    if not battle.log:
        return "*Nothing has happened yet.*"

    meaningful = [
        line for line in battle.log
        if not line.startswith("---")
        and not line.startswith("🔄 Cycle")
        and " gains " not in line
    ]
    lines = (meaningful or battle.log)[-count:]

    # Log lines are full prose sentences, so a 24-character enemy name
    # ("Xendium Overcharge Drone") appearing twice in one line is enough
    # to wrap it on its own. Rewrite long names to the SAME short name the
    # rows use -- the point is consistency: a player who reads "Eris
    # Sentry" on the enemy row should see that same token in the log, not
    # a second, differently-abbreviated version of it.
    # Longest-first so a name that's a prefix of another can't partially
    # rewrite it.
    replacements = sorted(
        ((c.name, names.display_name(c)) for c in battle.all_combatants()),
        key=lambda pair: len(pair[0]), reverse=True,
    )
    text = "\n".join(lines)
    for full, short in replacements:
        if short != full:
            text = text.replace(full, short)

    if len(text) > char_limit:
        text = "…" + text[-char_limit:]
    return text


def dungeon_map_graph_embed(expedition) -> discord.Embed:
    """The 🗺️ Map button's view: a floor-by-floor breakdown of every room
    between here and the NEXT boss (not the whole multi-boss run --
    anything past that boss hasn't been reached yet and would just be
    noise). Marks the current room and anything already cleared."""
    graph = expedition.graph
    current_node_id = expedition.current_node_id
    current_floor = graph["nodes"][current_node_id]["floor"]

    boss_nodes = graph.get("boss_nodes", [graph.get("boss_node")])
    boss_floors = sorted(graph["nodes"][b]["floor"] for b in boss_nodes if b in graph["nodes"])
    next_boss_floor = next((f for f in boss_floors if f >= current_floor), None)
    if next_boss_floor is None:
        next_boss_floor = max(n["floor"] for n in graph["nodes"].values())
    is_final_stretch = not boss_floors or next_boss_floor == boss_floors[-1]

    by_floor: dict[int, list[tuple[str, dict]]] = {}
    for node_id, node in graph["nodes"].items():
        if current_floor <= node["floor"] <= next_boss_floor:
            by_floor.setdefault(node["floor"], []).append((node_id, node))

    lines = []
    for floor in sorted(by_floor):
        room_strs = []
        for node_id, node in sorted(by_floor[floor]):
            emoji = ROOM_TYPE_EMOJI.get(node["room_type"], "❔")
            if node_id == current_node_id:
                room_strs.append(f"[{emoji}]")
            elif node.get("completed"):
                room_strs.append(f"~~{emoji}~~")
            else:
                room_strs.append(emoji)
        if floor == next_boss_floor:
            floor_label = "🐲 FINAL BOSS" if is_final_stretch else "🐲 Boss"
        else:
            floor_label = f"Floor {floor}"
        lines.append(f"**{floor_label}**  " + "  ".join(room_strs))

    embed = discord.Embed(
        title="🗺️ Map to the Next Boss",
        description="\n".join(lines) if lines else "*Nothing charted yet.*",
        color=discord.Color.blurple(),
    )
    embed.set_footer(text="[bracketed] = you are here. ~~struck-through~~ = already cleared.")
    return embed


def _poise_tag(enemy) -> str:
    """Inline poise readout for an enemy's single status line (see the
    Poise/Break block in bot/game/combat/combatant.py).

    This used to be a SECOND line under the enemy's HP with a full run of
    up to 10 pip emoji -- roughly 20 visible characters of emoji on its
    own, which guaranteed a wrap on mobile for every breakable enemy on
    the field. The pips are gone; the number they encoded ("3 more hits")
    is stated directly instead, which is both shorter and more precise
    than counting squares. The full pip bar still lives in the ℹ️ Info
    view for anyone who wants it."""
    if not enemy.can_be_broken():
        return ""
    if enemy.is_broken():
        return f" 💫{enemy.break_turns}t"
    return f" 🛡️{enemy.poise}"


def _poise_pips(enemy) -> str:
    """The discrete pip rendering of a poise pool, used by the ℹ️ Info
    view. Pips rather than a proportional bar because poise is a small
    whole number of HITS -- pips let the player count "three more hits"
    at a glance, which a proportional bar actively obscures. Capped at
    MAX_POISE_PIPS so a 16-poise boss doesn't blow out the field."""
    if not enemy.can_be_broken():
        return ""
    if enemy.max_poise <= MAX_POISE_PIPS:
        return "🟦" * enemy.poise + "⬜" * (enemy.max_poise - enemy.poise)
    filled = round(MAX_POISE_PIPS * enemy.poise / enemy.max_poise)
    return "🟦" * filled + "⬜" * (MAX_POISE_PIPS - filled)


def _intent_lines(battle) -> str:
    """The enemy telegraph block: one row per enemy, showing what that
    enemy does NEXT.

    Rewritten from a per-cycle schedule. The old version listed every
    enemy action queued for the rest of the cycle and then projected into
    the following one, under "later this cycle" / "next cycle" headers --
    which was accurate and unreadable. A four-enemy fight produced eight
    or more rows, the same enemy appeared two or three times, and
    answering "what is about to hit me" meant reconstructing it from a
    schedule.

    Each enemy now gets exactly one row, and it advances when that enemy
    acts. Cycle boundaries aren't shown at all, because they were never
    the thing the player was deciding about.

    LOCKS IN each shown decision as a side effect (see
    Battle.peek_enemy_intent_schedule), so call this at most once per
    render."""
    schedule = battle.peek_enemy_intent_schedule()
    if not schedule:
        return "*Nothing incoming right now.*"

    lines = []
    for row in schedule:
        enemy, intent = row["enemy"], row["intent"]
        name = names.display_name(enemy)

        if enemy.is_broken():
            lines.append(f"**{name}** 💫 broken, won't act")
            continue
        if intent is None:
            lines.append(f"**{name}** 😵 stunned, won't act")
            continue

        ability = intent["ability"]
        if ability is None:
            move = "⚔️ Attack"
        elif ability.get("is_ultimate"):
            move = f"💥 **{ability['name']}**"
        else:
            move = f"✨ {ability['name']}"

        # WHO it hits, by the ability's actual scope rather than the
        # single target the engine happened to pick. An AOE used to be
        # telegraphed as "▸ Josh", which actively misled the player into
        # guarding Josh and thinking everyone else was safe. See
        # effects.ability_scope.
        scope = effects.ability_scope(ability)
        if scope == "aoe":
            target_label = "💥 ALL of you"
        elif scope == "team":
            target_label = "🛡️ its own side"
        elif scope == "self":
            target_label = "itself"
        else:
            target_label = names.display_name(intent["target"])

        # Back-to-back actions, called out because they all land before
        # you get to respond -- the one case where "this enemy acts
        # twice" changes what you should do about it.
        repeat = f" ×{row['extra_actions'] + 1}" if row["extra_actions"] else ""

        # Spell out the counterplay: how many more hits until this enemy
        # breaks and loses the move it's telegraphing.
        counter = f" · break in {enemy.poise}" if enemy.can_be_broken() else ""
        lines.append(f"**{name}**{repeat} ▸ {target_label}\n┗ {move}{counter}")

    hidden = battle.hidden_intent_count(schedule)
    if hidden:
        lines.append(f"*...and {hidden} more enemy(s).*")
    return "\n".join(lines)


def _party_line(battle, member) -> str:
    """One combatant, one line, inside the mobile budget (see the layout
    block at the top of this module).

    The HP BAR is kept (at 6 segments rather than the original 8): the
    declutter pass dropped it as redundant with the numbers beside it,
    but a bar is read at a glance where a number has to be read and
    compared, and "who is low" is the single most frequent question this
    view answers. Six segments plus abbreviated numbers still fits the
    one-line budget.

    Still dropped versus the original two-line form: the "/max" on mana
    and energy (a player knows their own pools; the current value is the
    decision-relevant half). Flags collapse to bare emoji with no
    spacing."""
    acting = "🔸" if not battle.is_over() and member is battle.current_actor() else ""
    name = names.display_name(member)
    if not member.is_alive():
        return f"{acting}💀 ~~{name}~~"

    flags = ""
    # Marks the explicitly chosen recipient of a single-ally support
    # ability (see Battle.ally_target_index). Without this the pick is
    # only visible inside a collapsed dropdown, which is exactly where a
    # player won't look before committing their turn.
    if not battle.is_over() and battle.ally_target_index is not None \
            and member is battle.party[battle.ally_target_index]:
        flags += "💚"
    if member.is_taunting():
        flags += f"🎯{member.taunt_turns}"
    if member.ultimate_ready():
        flags += "💥"
    if member.guarding:
        flags += "🛡️"
    if member.shield > 0:
        flags += f"🔷{_short_num(member.shield)}"

    # Energy shown as current/max: with ultimates now genuinely castable
    # (see effects.py's PLAYER ENERGY ECONOMY block), "how close am I"
    # is a real per-turn question, and a bare number can't answer it
    # without the player remembering the cap.
    return (
        f"{acting}**{name}** {flags}\n"
        f"❤️{_short_num(member.current_hp)}/{_short_num(member.max_hp)}"
        f" {_bar(member.current_hp, member.max_hp, length=7)}"
        f" 💧{member.mana} 🔋{member.energy}/{member.max_energy}"
    )


def _enemy_line(battle, enemy, is_target: bool) -> str:
    """One enemy, one line. Same budget rules as _party_line; enemies keep
    a short HP bar because their max HP is not something the player has
    memorised the way they have their own squad's, so the proportion
    carries real information here that it doesn't there."""
    name = names.display_name(enemy)
    if not enemy.is_alive():
        return f"💀 ~~{name}~~"

    target_tag = "🎯" if is_target else ""
    shield_tag = f" 🔷{_short_num(enemy.shield)}" if enemy.shield > 0 else ""
    # A taunting enemy is forcing the player's attacks onto itself, which
    # the player needs to see on the enemy row itself -- not just infer
    # from a disabled dropdown.
    taunt_tag = f" 🛑{enemy.taunt_turns}" if enemy.is_taunting() else ""
    return (
        f"{target_tag}**{name}**{taunt_tag}{_poise_tag(enemy)}\n"
        f"❤️{_short_num(enemy.current_hp)}/{_short_num(enemy.max_hp)}"
        f" {_bar(enemy.current_hp, enemy.max_hp, length=6)}{shield_tag}"
    )


def combat_embed(battle, avatar_url: str | None = None) -> discord.Embed:
    """The live battle screen, edited in place turn after turn.

    DECLUTTER PASS. This view was five stacked fields of two-line-per-
    combatant blocks, and on a phone almost every one of those lines
    wrapped -- a 4-person squad against 4 enemies rendered as ~30 rows,
    which pushed the two things a player actually decides from (what's
    incoming, whose turn it is) below the fold. The rewrite keeps all the
    same information but re-budgets it:

      * Turn order moved into the embed DESCRIPTION. It was one line of
        content paying for a bold field header, and it now sits directly
        under the title where the eye already is.
      * Every combatant is one line (see _party_line / _enemy_line),
        with names clipped and big numbers abbreviated so nothing wraps.
      * Poise moved inline onto the enemy's own line instead of a third
        line of pip emoji beneath it (_poise_tag).
      * The log tail is 3 lines instead of 4 and drops the
        "--- Cycle N, Turn N ---" scaffolding, which was routinely half
        of that window.

    Nothing was actually removed from the game -- the full poise pips,
    every status effect, cooldowns and the complete log all still live in
    the ℹ️ Info and 📜 Log ephemeral views, which have no layout budget
    to respect.

    Party and enemies remain ONE consolidated field each rather than one
    field per combatant: with a full squad, field-per-combatant wraps into
    a bunched 3-per-row grid that reads far worse than a single block."""
    color = discord.Color.red()
    if battle.result == "won":
        color = discord.Color.gold()
    elif battle.result == "lost":
        color = discord.Color.dark_gray()

    # Author line rather than a thumbnail. set_thumbnail renders a large
    # image on the right of the embed and, on mobile, every field's text
    # wraps around it -- so the avatar was costing horizontal width on
    # EVERY line of the battle screen, which is the most width-starved
    # view in the game. set_author puts the same picture in as a small
    # inline icon that costs one short line and squeezes nothing.
    embed = discord.Embed(title="⚔️ Battle", color=color)
    if avatar_url:
        embed.set_author(name="Battle", icon_url=avatar_url)
        embed.title = None  # the author line already carries the label

    if not battle.is_over():
        # Past the warning threshold the cycle counter turns into a
        # countdown. A battle ends in a withdrawal at MAX_BATTLE_CYCLES
        # (see the CYCLE LIMIT block in battle.py) and that has to be
        # visible well before it lands -- a fight that simply stops is
        # the same unexplained-mechanic problem this rework removed
        # everywhere else.
        if battle.cycle_number >= CYCLE_WARNING_THRESHOLD:
            cycle_line = (
                f"⏳ Cycle {battle.cycle_number}/{MAX_BATTLE_CYCLES} "
                "— your squad withdraws if neither side breaks"
            )
        else:
            cycle_line = f"🔄 Cycle {battle.cycle_number}"
        embed.description = f"{cycle_line}\n{_turn_order_line(battle)}"
        # Forced targeting is called out above everything else: it changes
        # what the player's buttons will actually do, so burying it would
        # make Attack look broken rather than redirected.
        forced = battle.taunting_enemy()
        if forced is not None:
            embed.description += f"\n🛑 **{names.display_name(forced)}** is taunting -- your attacks are forced onto it."
        drawing = battle.taunting_ally()
        if drawing is not None:
            embed.description += f"\n🎯 **{names.display_name(drawing)}** is drawing all enemy attacks."
        embed.add_field(name="😈 Incoming", value=_intent_lines(battle), inline=False)

    party_lines = [_party_line(battle, m) for m in battle.party]
    embed.add_field(name="🧑 Squad", value="\n".join(party_lines), inline=False)

    enemy_lines = []
    living_i = 0
    for enemy in battle.enemies:
        is_target = False
        if enemy.is_alive():
            is_target = living_i == battle.target_index
            living_i += 1
        enemy_lines.append(_enemy_line(battle, enemy, is_target))
    embed.add_field(name="👹 Enemies", value="\n".join(enemy_lines), inline=False)

    embed.add_field(name="📜 Recent", value=_recent_log_lines(battle), inline=False)

    if battle.is_over():
        result_text = {"won": "🏆 Victory!", "lost": "💀 Defeat..."}[battle.result]
        embed.add_field(name="Result", value=result_text, inline=False)
    else:
        embed.set_footer(text="ℹ️ Info for effects & cooldowns · 📜 Log for full history")

    return embed


# Characters of log per page. Under Discord's 4096-char description
# ceiling with room for the header line.
LOG_PAGE_CHARS = 3600


def log_pages(battle) -> list[list[str]]:
    """The battle log split into pages, oldest first.

    Pages are built by CHARACTER COUNT rather than a fixed number of
    lines, because log lines vary from "Guard." to a four-clause
    ultimate resolution, and a fixed line count produces pages that are
    either half-empty or over the limit.
    """
    pages: list[list[str]] = []
    current: list[str] = []
    size = 0
    for line in battle.log:
        # +1 for the newline it will be joined with.
        if current and size + len(line) + 1 > LOG_PAGE_CHARS:
            pages.append(current)
            current, size = [], 0
        current.append(line)
        size += len(line) + 1
    if current:
        pages.append(current)
    return pages or [[]]


def battle_log_embed(battle, page: int | None = None) -> discord.Embed:
    """The battle log, PAGED, shown via the 📜 Log button.

    It used to render the whole log into one embed and, when that
    overflowed, delete lines from the oldest end -- so the longer and
    more interesting the fight, the more of its opening was silently
    thrown away. A boss fight that turned on something that happened in
    cycle two would lose exactly that.

    `page` defaults to the LAST page: the newest lines are what a player
    hitting the log button mid-fight almost always wants, and paging
    back from there is the deliberate act. Passing an explicit page is
    what the prev/next buttons do.
    """
    pages = log_pages(battle)
    if page is None:
        page = len(pages) - 1
    page = max(0, min(page, len(pages) - 1))

    embed = discord.Embed(title="📜 Battle Log", color=discord.Color.dark_grey())
    if not battle.log:
        embed.description = "*Nothing has happened yet.*"
        return embed

    embed.description = "\n".join(pages[page])
    if len(pages) > 1:
        embed.set_footer(text=f"Page {page + 1} of {len(pages)} · oldest first")
    return embed


# ----------------------------------------------------------------------
# The ℹ️ Info view.
#
# This used to be a single embed with one cramped INLINE field per living
# combatant, which meant Discord packed up to 9 combatants into a
# 3-per-row grid of truncated columns. It also showed only status
# effects: it never listed a character's abilities, never showed their
# ability descriptions or costs, and -- worst of the three -- showed no
# stats at all, so there was nowhere in the entire game to answer "what
# is my ATK actually at right now, with these buffs up?" A player running
# an Amplifier could not see what the Amplifier was doing.
#
# It's now paginated: one page per combatant, party first then enemies,
# each page giving that combatant a full screen for stats (base ->
# effective, with the delta called out), their whole kit, and every
# active effect on them. Enemies get exactly the same page, because
# reading what a boss is buffed by is at least as important as reading
# your own squad.
# ----------------------------------------------------------------------

def info_page_count(battle) -> int:
    """One page per combatant -- dead ones included, so page indices stay
    stable for the whole fight. A view that renumbers its own pages when
    something dies will send the player somewhere they didn't ask for."""
    return len(battle.party) + len(battle.enemies)


def info_page_targets(battle) -> list:
    """The combatants, in page order: party first, then enemies."""
    return list(battle.party) + list(battle.enemies)


def _effective_stat_line(c, stat: str) -> str:
    """`base -> effective (+N%)` for one stat, showing what buffs,
    debuffs, stacking passives and the enemy attack-ramp actually add up
    to. This is the number that decides fights and it was previously not
    displayed anywhere in combat."""
    base = c.base_stats.get(stat, 0)
    effective = c.effective_stat(stat)
    label = STAT_LABEL.get(stat, stat)
    emoji = STAT_EMOJI.get(stat, "")
    if round(base, 2) == round(effective, 2):
        return f"{emoji} {label} {effective:g}"
    pct = (effective / base - 1) * 100 if base else 0
    arrow = "🔺" if effective > base else "🔻"
    return f"{emoji} {label} {base:g} → **{effective:g}** {arrow}{abs(pct):.0f}%"


def _ability_lines(c) -> list[str]:
    """Every ability this combatant can use, with cost, cooldown state
    and description. Players could previously only see an ability's
    description by opening the dropdown, and could not see their
    ULTIMATE's description anywhere at all."""
    lines = []
    for ability in c.active_abilities:
        unit = "SP" if ability["resource_type"] == "mana" else "EN"
        cd = c.cooldowns.get(ability["id"], 0)
        if cd > 0:
            state = f"⏳ {cd}t"
        elif c.ability_ready(ability):
            state = "✅"
        else:
            state = "🚫"
        source = {"character": "🌀", "weapon": "⚔️", "artifact": "🔮"}.get(ability.get("source"), "✨")
        lines.append(f"{state} {source} **{ability['name']}** ({ability['resource_cost']} {unit})")
        lines.append(f"　{ability['description']}")

    if c.ultimate_ability:
        u = c.ultimate_ability
        # Cooldown first, energy second -- a fully charged ultimate that
        # still isn't usable has to say why, or "50/50 EN" next to a dead
        # button reads as a bug rather than as a cooldown.
        ultimate_cd = c.cooldowns.get(u["id"], 0)
        if c.ultimate_ready():
            state = "✅ READY"
        elif ultimate_cd > 0:
            state = f"⏳ {ultimate_cd}t"
        else:
            state = f"{c.energy}/{u['resource_cost']} EN"
        lines.append(f"💥 **{u['name']}** ({state})")
        lines.append(f"　{u['description']}")
    return lines or ["*No active abilities.*"]


def _effect_lines(c) -> list[str]:
    """Buffs, debuffs, DoTs, regens, marks and control states."""
    lines = []
    for m in c.modifiers:
        sign = "+" if m.percent >= 0 else ""
        icon = "📈" if m.percent >= 0 else "📉"
        lines.append(f"{icon} {sign}{m.percent:g}% {STAT_LABEL.get(m.stat, m.stat)} ({m.duration}t) — {m.source}")
    for d in c.dots:
        lines.append(f"🔥 {d.flat_amount:g} dmg/turn ({d.duration}t) — {d.source}")
    for h in c.heals:
        duration_label = "passive" if h.duration >= 999 else f"{h.duration}t"
        lines.append(f"🌿 {h.percent_max_hp:g}% max HP/turn ({duration_label}) — {h.source}")
    for v in c.vulnerabilities:
        stat_label = "damage-over-time" if v.damage_stat == "dot" else STAT_LABEL.get(v.damage_stat, v.damage_stat)
        lines.append(f"☣️ +{v.percent_per_stack * v.stacks:g}% {stat_label} taken ({v.stacks}/{v.max_stacks}) — {v.source}")
    # EXPOSED is derived from the debuffs listed just above rather than
    # stored anywhere, so it has to be rendered explicitly or the player
    # sees the debuffs and never learns what they bought. It is the
    # Support DPS's whole contribution -- leaving it implicit is how that
    # class ended up looking like "an AOE attack that sometimes does
    # something" in the first place.
    exposed = effects.exposed_bonus_percent(c)
    if exposed:
        lines.append(f"🎯 Exposed +{exposed:g}% damage taken — from every attacker, while debuffed")
    if c.shield > 0:
        lines.append(f"🔷 Shield absorbing {round(c.shield)} damage")
    if c.is_taunting():
        lines.append(f"🎯 Taunting ({c.taunt_turns}t) — forcing the other side to attack it")
    if getattr(c, "ramp_percent_per_turn", 0) and c.ramp_stacks:
        lines.append(f"😤 +{round(c.ramp_percent_per_turn * c.ramp_stacks, 1):g}% ATK/ELE (prolonged fight, permanent)")
    if c.stunned_turns > 0:
        lines.append(f"😵 Stunned ({c.stunned_turns}t)")
    if c.guarding:
        lines.append("🛡️ Guarding — incoming damage halved until their next turn")
    if c.is_broken():
        lines.append(f"💫 Broken ({c.break_turns}t) — takes extra damage, turns skipped")
    elif c.can_be_broken():
        lines.append(f"🛡️ Poise {c.poise}/{c.max_poise} {_poise_pips(c)} — breaks in {c.poise} hit(s)")
    return lines or ["*Nothing active.*"]


def battle_info_embed(battle, page: int = 0) -> discord.Embed:
    """One combatant's full readout -- stats (base → buffed), complete
    kit, and every active effect. Page order is party then enemies; see
    the block above for why this replaced the old one-field-per-combatant
    single embed."""
    targets = info_page_targets(battle)
    if not targets:
        return discord.Embed(title="ℹ️ Battlefield Info", description="*Nothing to show.*")
    page = max(0, min(page, len(targets) - 1))
    c = targets[page]
    is_party = c in battle.party

    dead = not c.is_alive()
    embed = discord.Embed(
        title=f"{'🧑' if is_party else '👹'} {c.name}{' 💀' if dead else ''}",
        description=(
            f"Page {page + 1}/{len(targets)} · {'Your squad' if is_party else 'Enemy'}"
            + (f" · {CLASS_DISPLAY_NAME_BY_VALUE.get(c.character_class, '')}" if c.character_class else "")
        ),
        color=discord.Color.blurple() if is_party else discord.Color.dark_red(),
    )

    resources = [f"❤️ {c.current_hp}/{c.max_hp}"]
    if c.max_mana and is_party:
        resources.append(f"💧 {c.mana}/{c.max_mana}")
    resources.append(f"🔋 {c.energy}/{c.max_energy}")
    if c.shield > 0:
        resources.append(f"🔷 {round(c.shield)}")
    embed.add_field(name="Resources", value="  ".join(resources), inline=False)

    stat_order = ["attack", "elemental", "defense", "speed", "crit_rate", "crit_damage", "recharge"]
    embed.add_field(
        name="📊 Stats (base → with buffs)",
        value=fit_field([_effective_stat_line(c, s) for s in stat_order]),
        inline=False,
    )

    embed.add_field(name="🎯 Abilities", value=fit_field(_ability_lines(c)), inline=False)

    if c.passive_abilities:
        embed.add_field(
            name="🧬 Passives",
            value=fit_field([f"**{p['name']}** — {p['description']}" for p in c.passive_abilities]),
            inline=False,
        )

    embed.add_field(name="✨ Active Effects", value=fit_field(_effect_lines(c)), inline=False)
    embed.set_footer(text=f"Cycle {battle.cycle_number} · Turn {battle.turn_count} · Use the buttons to page through everyone.")
    return embed


def expedition_summary_embed(ledger: dict, won: bool, forfeited: bool = False) -> discord.Embed:
    """The whole-run tally shown once when an expedition ends -- win,
    lose, or forfeit -- on top of that final battle's own reward message
    (or the forfeit confirmation message). Everything here accumulated
    across every room of the run (combat rewards, treasure/secret/story/
    shrine rooms, trap/puzzle outcomes, encounter trades/gambles --
    including merchant purchases, which are now just "trade"-action
    encounter choices), not just the last fight; see the `_ledger_*`
    helpers in bot/services/dungeon_service.py. Nothing is actually taken
    away on a loss or forfeit -- gains from earlier in the run are kept --
    so "lost"/"spent" here means gold spent on encounter trades, not gold
    clawed back on defeat or forfeit."""
    if forfeited:
        title = "🏳️ Expedition Forfeited -- Summary"
    elif won:
        title = "🏆 Expedition Complete -- Summary"
    else:
        title = "💀 Expedition Ended -- Summary"
    embed = discord.Embed(
        title=title,
        color=discord.Color.gold() if won else discord.Color.dark_gray(),
    )

    # Relics led with, before the loot tally: they're what made this run
    # play differently from the last one, which is the part worth
    # remembering once the numbers have been banked.
    relic_ids = ledger.get("relics") or []
    if relic_ids:
        from bot.game.dungeon.relic_config import get_relic

        relics = [r for r in (get_relic(rid) for rid in relic_ids) if r]
        if relics:
            embed.add_field(
                name=f"✨ Relics carried ({len(relics)})",
                value="\n".join(f"{r['emoji']} **{r['name']}**" for r in relics),
                inline=False,
            )

    gained_lines = []
    if ledger["gold_gained"]:
        gained_lines.append(f"{format_currency('gold', ledger['gold_gained'])}")
    if ledger["shards_gained"]:
        gained_lines.append(f"{format_currency('shards', ledger['shards_gained'])}")
    if ledger["reroll_tokens_gained"]:
        gained_lines.append(f"{format_currency('reroll_tokens', ledger['reroll_tokens_gained'])}")
    if ledger["xp_gained"]:
        gained_lines.append(f"✨ {ledger['xp_gained']} XP")
    for material, qty in ledger["materials"].items():
        gained_lines.append(format_currency(material, qty))
    embed.add_field(
        name="📈 Gained",
        value="\n".join(gained_lines) if gained_lines else "*Nothing.*",
        inline=True,
    )

    spent_lines = []
    if ledger["gold_spent"]:
        spent_lines.append(f"{format_currency('gold', ledger['gold_spent'])} on trades")
    if ledger["reroll_tokens_spent"]:
        spent_lines.append(f"{format_currency('reroll_tokens', ledger['reroll_tokens_spent'])} on trades")
    embed.add_field(
        name="📉 Spent",
        value="\n".join(spent_lines) if spent_lines else "*Nothing.*",
        inline=True,
    )

    loot_lines = []
    for entry in ledger["items_found"]:
        loot_lines.append(f"{entry['name']} ({entry['rarity'].title()})")
    for entry in ledger["items_bought"]:
        loot_lines.append(f"{entry['name']} ({entry['rarity'].title()}, bought)")
    for tier, qty in ledger["lootboxes_found"].items():
        loot_lines.append(f"{qty}x {tier.title()} Lootbox")
    for tier, qty in ledger["lootboxes_bought"].items():
        loot_lines.append(f"{qty}x {tier.title()} Lootbox (bought)")
    if loot_lines:
        embed.add_field(name="🎒 Items & Lootboxes", value="\n".join(loot_lines), inline=False)

    if ledger["level_ups"]:
        level_lines = [
            f"{name} Lv.{lu['from']} → Lv.{lu['to']}" for name, lu in ledger["level_ups"].items()
        ]
        embed.add_field(name="📈 Level Ups", value="\n".join(level_lines), inline=False)

    return embed
