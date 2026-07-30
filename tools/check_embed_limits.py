#!/usr/bin/env python3
"""
Renders every embed the bot can produce with WORST-CASE data and checks it
against Discord's hard limits.

Why this exists: exceeding an embed limit isn't a soft failure. The API
rejects the entire message with a 400 and the command just looks broken to
the player -- there's no partial render, no truncation, no warning at build
time. `/help` shipped broken exactly this way after one paragraph too many
was added to a field, and the same sweep then found three more latent
crashes in relic listings that would only have triggered once a player
accumulated enough relics.

Anything whose length depends on game state (relics held, enemies alive,
items owned, log length) is the dangerous kind, because it renders fine in
testing and breaks later for whoever plays furthest.

    python tools/check_embed_limits.py

Exits non-zero if anything is over. Safe to run against a throwaway DB;
it creates its own.
"""

from __future__ import annotations

import ast
import os
import random
import sys
import tempfile

os.environ.setdefault("DISCORD_TOKEN", "x")
os.environ.setdefault("DEV_MODE", "False")
os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/embed_limits.db"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import discord  # noqa: E402

# https://discord.com/developers/docs/resources/message#embed-object-embed-limits
LIMITS = {
    "title": 256,
    "description": 4096,
    "field_name": 256,
    "field_value": 1024,
    "footer": 2048,
    "author": 256,
    "fields": 25,
    "total": 6000,
}

failures: list[str] = []


def check(label: str, embed: discord.Embed) -> None:
    data = embed.to_dict()
    problems = []

    if len(data.get("title", "")) > LIMITS["title"]:
        problems.append(f"title {len(data['title'])}")
    if len(data.get("description", "")) > LIMITS["description"]:
        problems.append(f"description {len(data['description'])}")
    if len(data.get("footer", {}).get("text", "")) > LIMITS["footer"]:
        problems.append("footer too long")
    if len(data.get("author", {}).get("name", "")) > LIMITS["author"]:
        problems.append("author too long")

    fields = data.get("fields", [])
    if len(fields) > LIMITS["fields"]:
        problems.append(f"{len(fields)} fields (max {LIMITS['fields']})")

    widest = 0
    for i, field in enumerate(fields):
        widest = max(widest, len(field["value"]))
        if len(field["value"]) > LIMITS["field_value"]:
            problems.append(f"field[{i}] {field['name'][:24]!r} value={len(field['value'])}")
        if len(field["name"]) > LIMITS["field_name"]:
            problems.append(f"field[{i}] name={len(field['name'])}")

    # Discord's 6000 total counts title+description+fields+footer+author.
    total = (
        len(data.get("title", ""))
        + len(data.get("description", ""))
        + len(data.get("footer", {}).get("text", ""))
        + len(data.get("author", {}).get("name", ""))
        + sum(len(f["name"]) + len(f["value"]) for f in fields)
    )
    if total > LIMITS["total"]:
        problems.append(f"total {total}")

    status = "FAIL" if problems else "ok  "
    print(f"  {status}  {label:44s} fields={len(fields):2d} widest={widest:4d} total={total:4d} "
          + ("; ".join(problems)))
    if problems:
        failures.append(label)


def help_embed() -> discord.Embed:
    """/help builds its embed inline in the cog and needs a live
    Interaction, so reconstruct it from the source's add_field calls."""
    tree = ast.parse(open("bot/cogs/help.py", encoding="utf-8").read())
    embed = discord.Embed(title="Welcome to CascadeBot", description="x" * 200)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "attr", "") == "add_field":
            kwargs = {k.arg: k.value for k in node.keywords}
            try:
                embed.add_field(
                    name=ast.literal_eval(kwargs["name"]),
                    value=ast.literal_eval(kwargs["value"]),
                    inline=False,
                )
            except Exception:  # a dynamically-built field; skip it
                pass
    return embed


def main() -> int:
    from bot.database.db_init import init_db
    from bot.database.models.character_model import CharacterTemplate
    from bot.database.session import SessionLocal
    from bot.game.combat.battle import Battle
    from bot.game.combat.combatant import STAT_KEYS, Combatant
    from bot.game.dungeon.relic_config import RELICS
    from bot.game.loot.abilities import ARMOR_PASSIVES
    from bot.services import (
        character_service,
        character_template_service,
        dungeon_service,
        item_template_service,
        lootbox_service,
        player_service,
        quest_service,
        relic_service,
        vote_service,
    )
    from bot.utils import embedder

    init_db()
    db = SessionLocal()
    item_template_service.ensure_item_templates_seeded(db)
    character_template_service.ensure_character_templates_seeded(db)
    lootbox_service.ensure_lootbox_templates_seeded(db)

    player = player_service.get_or_create_player(db, 1, "limitcheck")
    character_service.ensure_avatar_character(db, player)
    for i, klass in enumerate(("sustain", "amplifier", "support_dps"), start=1):
        template = [
            t for t in db.query(CharacterTemplate).filter_by(is_player_avatar=False).all()
            if t.character_class.value == klass
        ][0]
        pc, _, _ = character_service.grant_character(db, player, template)
        character_service.set_squad_slot(db, player, i, pc)
    db.commit()
    expedition = dungeon_service.start_expedition(db, player, region="cascade_wilds")

    print("\nStatic embeds")
    check("/help", help_embed())

    print("\nRelics -- worst case: entire catalog held")
    for relic in RELICS:
        relic_service.grant_relic(db, expedition, relic["id"])
    held = relic_service.held_relics(expedition)
    node = expedition.graph["nodes"][expedition.current_node_id]
    check(f"dungeon_map_embed ({len(held)} relics)", embedder.dungeon_map_embed(expedition, "msg"))
    check("campfire_embed", embedder.campfire_embed(node, relic_service.offer_relics(expedition), held, "msg"))
    check("relic_gained_embed", embedder.relic_gained_embed(RELICS[0], held))
    ledger = dungeon_service._ledger(expedition)
    ledger["relics"] = [r["id"] for r in RELICS]
    check("expedition_summary_embed", embedder.expedition_summary_embed(ledger, won=True))

    print("\nCombat -- worst case: 5 enemies, all broken, party guarding, max passives")

    def combatant(name, is_player, poise=0):
        stats = {k: 100 for k in STAT_KEYS}
        stats.update(max_hp=999999, max_mana=99999, recharge=20)
        return Combatant(
            name=name * 3, is_player=is_player, base_stats=dict(stats),
            current_hp=999999, max_hp=999999, mana=99999, max_mana=99999,
            energy=50, max_energy=50, max_poise=poise, poise=poise,
            passive_abilities=[dict(a) for a in ARMOR_PASSIVES[:6]],
        )

    party = [combatant(f"Party{i}", True) for i in range(4)]
    enemies = [combatant(f"Enemy{i}", False, poise=24) for i in range(5)]
    battle = Battle(party, enemies, rng=random.Random(1))
    for c in party:
        c.guarding = True
    for c in enemies:
        c.enter_break(2)
        c.poise = 0
    check("combat_embed (all broken)", embedder.combat_embed(battle))
    check("battle_info_embed", embedder.battle_info_embed(battle))
    for c in enemies:
        c.recover_from_break()
    battle.peek_upcoming_enemy_intents()
    check("combat_embed (all telegraphing)", embedder.combat_embed(battle))
    battle.log = [f"A fairly long battle log line, number {i}, with detail" for i in range(300)]
    check("battle_log_embed (300 lines)", embedder.battle_log_embed(battle))

    print("\nOther")
    player.vote_streak = 999
    player.total_votes = 9999
    db.commit()
    check("vote_prompt_embed", embedder.vote_prompt_embed(
        vote_service.peek_next_reward(player), "https://top.gg/bot/1/vote", player))
    check("vote_claimed_embed", embedder.vote_claimed_embed(
        {**vote_service.peek_next_reward(player), "total_votes": 9999, "is_weekend": True}, player))
    quest_service.ensure_beginner_quests_seeded(db, player)
    check("quest_board_embed", embedder.quest_board_embed(
        quest_service.get_beginner_quests(db, player),
        quest_service.get_active_basic_quests(db, player), None, player))
    check("general_inventory_embed", embedder.general_inventory_embed(
        player, lootbox_service.list_player_lootboxes(db, player.id)))
    check("gacha_rates_embed", embedder.gacha_rates_embed())
    check("encyclopedia_categories_embed", embedder.encyclopedia_categories_embed())

    db.close()

    print()
    if failures:
        print(f"*** {len(failures)} embed(s) OVER DISCORD'S LIMITS: {', '.join(failures)}")
        return 1
    print("All embeds within Discord's limits.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
