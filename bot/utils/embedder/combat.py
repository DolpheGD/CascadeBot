"""
Combat embeds.

Battle message, battle log, battle info, and the end-of-run
expedition summary.
"""

from __future__ import annotations

import discord

from bot.services.currency_service import format_currency
from bot.utils.embedder._shared import ROOM_TYPE_EMOJI, _bar


# ----------------------------------------------------------------------
# Combat
# ----------------------------------------------------------------------

def _turn_order_line(battle, count: int = 6) -> str:
    icons = []
    for c in battle.preview_turn_order(count):
        icon = "🧑" if c.is_player else "👹"
        icons.append(f"{icon} {c.name}")
    return " ➜ ".join(icons) if icons else "--"


def _recent_log_lines(battle, count: int = 4, char_limit: int = 900) -> str:
    """A short, in-battlefield tail of the log (see combat_embed) -- the
    last few lines only, further trimmed to fit comfortably inside one
    embed field. This is deliberately much shorter than battle_log_embed's
    full history; that's still one Log-button tap away for anyone who
    wants the complete record."""
    if not battle.log:
        return "*Nothing has happened yet.*"

    lines = battle.log[-count:]
    text = "\n".join(lines)
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


def _enemy_intent_lines(battle) -> str:
    """One line per enemy about to act before the next party turn (see
    Battle.peek_upcoming_enemy_intents) -- who they're targeting and
    whether it's a basic attack, an ability, or their ultimate. This
    LOCKS IN those enemies' decisions as a side effect of being called
    (see peek_upcoming_enemy_intents's docstring), so call this at most
    once per render."""
    upcoming = battle.peek_upcoming_enemy_intents()
    if not upcoming:
        return "*Nothing incoming right now.*"

    lines = []
    for enemy, intent in upcoming:
        if intent is None:
            lines.append(f"**{enemy.name}** -- 😵 Stunned, won't act")
            continue
        ability = intent["ability"]
        target = intent["target"]
        if ability is None:
            move = "⚔️ Attack"
        else:
            move = f"{'💥' if ability.get('is_ultimate') else '✨'} {ability['name']}"
        lines.append(f"**{enemy.name}** ➡️ 🎯 {target.name} -- {move}")
    return "\n".join(lines)


def combat_embed(battle, avatar_url: str | None = None) -> discord.Embed:
    """Renders the current battle state: HP/resource bars for everyone, the
    turn order preview, an enemy intent preview (see _enemy_intent_lines --
    who's about to act, on whom, with what), current target marker, and a
    short "Recent Actions" tail of the log, so a Discord message can be
    edited in place turn after turn. That tail is intentionally brief (see
    _recent_log_lines) -- the full history is still one 📜 Log tap away via
    battle_log_embed.

    Party and enemies are each ONE consolidated field (a line per member)
    rather than one Discord field per combatant -- with a full 4-person
    squad plus several enemies, one-field-each was wrapping into a bunched,
    hard-to-scan 3-per-row grid. A single readable block per side reads
    top-to-bottom instead."""
    color = discord.Color.red()
    if battle.result == "won":
        color = discord.Color.gold()
    elif battle.result == "lost":
        color = discord.Color.dark_gray()

    embed = discord.Embed(title="⚔️ Battle!", color=color)
    if avatar_url:
        embed.set_thumbnail(url=avatar_url)

    if not battle.is_over():
        embed.add_field(name="🔀 Turn Order", value=_turn_order_line(battle), inline=False)
        embed.add_field(name="😈 Enemy Intent", value=_enemy_intent_lines(battle), inline=False)

    party_lines = []
    for member in battle.party:
        acting_tag = " 🔸" if not battle.is_over() and member is battle.current_actor() else ""
        if not member.is_alive():
            party_lines.append(f"**{member.name}**{acting_tag} -- 💀 Down")
            continue
        ult_flag = " 💥" if member.ultimate_ready() else ""
        shield_tag = f" 🔷{round(member.shield)}" if member.shield > 0 else ""
        party_lines.append(
            f"**{member.name}**{acting_tag}{ult_flag}\n"
            f"┗ ❤️{member.current_hp}/{member.max_hp} {_bar(member.current_hp, member.max_hp, length=8)}{shield_tag}"
            f"  💧{member.mana}/{member.max_mana}  🔋{member.energy}/{member.max_energy}"
        )
    embed.add_field(name="🧑 Your Squad", value="\n".join(party_lines), inline=False)

    enemy_lines = []
    living_i = 0
    for enemy in battle.enemies:
        if not enemy.is_alive():
            enemy_lines.append(f"**{enemy.name}** -- 💀 Defeated")
            continue
        is_target = living_i == battle.target_index
        living_i += 1
        target_tag = " 🎯" if is_target else ""
        shield_tag = f" 🔷{round(enemy.shield)}" if enemy.shield > 0 else ""
        enemy_lines.append(
            f"**{enemy.name}**{target_tag}\n"
            f"┗ ❤️{enemy.current_hp}/{enemy.max_hp} {_bar(enemy.current_hp, enemy.max_hp, length=8)}{shield_tag}"
        )
    embed.add_field(name="👹 Enemies", value="\n".join(enemy_lines), inline=False)

    embed.add_field(name="📜 Recent Actions", value=_recent_log_lines(battle), inline=False)

    if battle.is_over():
        result_text = {"won": "🏆 Victory!", "lost": "💀 Defeat..."}[battle.result]
        embed.add_field(name="Result", value=result_text, inline=False)
    else:
        embed.set_footer(text="Tap ℹ️ Info for status effects/cooldowns, 📜 Log for the full battle log.")

    return embed


def battle_log_embed(battle) -> discord.Embed:
    """The full battle log, shown via the 📜 Log button -- unlike the main
    battle message's brief "Recent Actions" tail (see combat_embed /
    _recent_log_lines, just the last handful of lines), this shows
    everything that's happened so far, trimmed from the oldest end only
    if it would overflow an embed description (4096 chars)."""
    embed = discord.Embed(title="📜 Battle Log", color=discord.Color.dark_grey())
    if not battle.log:
        embed.description = "*Nothing has happened yet.*"
        return embed

    lines = list(battle.log)
    text = "\n".join(lines)
    if len(text) > 4000:
        while lines and len("\n".join(lines)) > 3900:
            lines.pop(0)
        text = "*(earlier entries truncated)*\n" + "\n".join(lines)
    embed.description = text
    return embed


def battle_info_embed(battle) -> discord.Embed:
    """The ephemeral 'ℹ️ Info' view -- everything combat_embed leaves out
    to stay uncluttered: every combatant's active status effects
    (buffs/debuffs/DoTs/stun) and ability cooldowns."""
    embed = discord.Embed(title="ℹ️ Battlefield Info", color=discord.Color.blurple())

    def _status_lines(c) -> str:
        lines = []
        for p in c.passive_abilities:
            lines.append(f"🧬 **{p['name']}**: {p['description']}")
        for m in c.modifiers:
            sign = "+" if m.percent >= 0 else ""
            lines.append(f"{sign}{m.percent:g}% {m.stat} ({m.duration}t) -- {m.source}")
        for d in c.dots:
            lines.append(f"🔥 {d.flat_amount:g} dmg/turn ({d.duration}t) -- {d.source}")
        for h in c.heals:
            duration_label = "passive" if h.duration >= 999 else f"{h.duration}t"
            lines.append(f"🌿 {h.percent_max_hp:g}% max HP/turn ({duration_label}) -- {h.source}")
        if getattr(c, "ramp_percent_per_turn", 0) and c.ramp_stacks:
            bonus = round(c.ramp_percent_per_turn * c.ramp_stacks, 1)
            lines.append(f"😤 +{bonus:g}% ATK/ELE (prolonged fight, permanent)")
        if c.stunned_turns > 0:
            lines.append(f"😵 Stunned ({c.stunned_turns}t)")
        for ability_id, remaining in c.cooldowns.items():
            if remaining > 0:
                ability = next(
                    (a for a in c.active_abilities if a["id"] == ability_id),
                    {"name": ability_id},
                )
                lines.append(f"⏳ {ability['name']} ready in {remaining}t")
        return "\n".join(lines) if lines else "*No active effects.*"

    for member in battle.party:
        if not member.is_alive():
            continue
        embed.add_field(name=f"🧑 **{member.name}**", value=_status_lines(member), inline=True)

    for enemy in battle.living_enemies():
        embed.add_field(name=f"👹 **{enemy.name}**", value=_status_lines(enemy), inline=True)

    embed.add_field(name="Turn", value=str(battle.turn_count), inline=False)
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
