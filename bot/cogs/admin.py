"""
Admin/dev tooling. Currently just one command: /admin_testgear, which
outfits the caller with a full set of high-rarity, guaranteed-ability gear
(2 weapons, 4 armor pieces, 2 artifacts, 1 scroll) plus a pile of currency
and lootboxes, so a developer can immediately test combat, profile display,
and inventory management without grinding for drops first.
"""

from __future__ import annotations

import discord

from discord.ext import commands
from discord import app_commands

from bot.config import ADMIN_USER_IDS
from bot.database.models.enums import EquipmentSlot, ItemType, Rarity
from bot.database.models.equipment_model import ItemTemplate
from bot.database.session import SessionLocal
from bot.game.loot.generator import LootGenerator
from bot.services import inventory_service, lootbox_service
from bot.services.currency_service import add_currency
from bot.services.player_service import get_or_create_player
from bot.utils.guild_decorator import guild_decorator

TEST_GOLD = 100_000
TEST_SHARDS = 10_000
TEST_LOOTBOXES_PER_TIER = 10
TEST_RARITY = Rarity.LEGENDARY
TEST_ITEM_LEVEL = 25


def _is_admin(interaction: discord.Interaction) -> bool:
    if interaction.user.id in ADMIN_USER_IDS:
        return True
    member = interaction.user
    return isinstance(member, discord.Member) and member.guild_permissions.administrator


def _templates_for_slot(db, slot: EquipmentSlot) -> list[ItemTemplate]:
    return db.query(ItemTemplate).filter_by(slot=slot).all()


@guild_decorator
class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # COMMAND: /admin_testgear
    # Grants the caller a large pile of gold/shards/lootboxes and a full,
    # already-equipped kit of Legendary gear (2 weapons, helmet/necklace,
    # chest, leggings, boots, 2 artifacts, 1 scroll) each guaranteed to
    # carry an ability, so combat/profile/inventory can all be tested
    # immediately. Restricted to server Administrators or IDs listed in
    # the ADMIN_USER_IDS env var.
    @app_commands.command(
        name="admin_testgear",
        description="[Admin] Give yourself test gold, shards, lootboxes, and a full kit of gear.",
    )
    async def admin_testgear(self, ctx: discord.Interaction):
        if not _is_admin(ctx):
            await ctx.response.send_message(
                "You need Administrator permission (or be a configured bot admin) to use this.",
                ephemeral=True,
            )
            return

        await ctx.response.defer(ephemeral=True)

        db = SessionLocal()
        try:
            player = get_or_create_player(db, ctx.user.id, ctx.user.display_name)

            add_currency(db, player, "gold", TEST_GOLD)
            add_currency(db, player, "shards", TEST_SHARDS)

            for tier in ("common", "rare", "epic", "legendary"):
                lootbox_service.grant_lootbox(db, player, tier, TEST_LOOTBOXES_PER_TIER)

            generator = LootGenerator()
            granted_names: list[str] = []

            slot_counts = {
                EquipmentSlot.WEAPON: 2,
                EquipmentSlot.HEAD: 1,
                EquipmentSlot.CHEST: 1,
                EquipmentSlot.LEGGINGS: 1,
                EquipmentSlot.BOOTS: 1,
                EquipmentSlot.ARTIFACT: 2,
                EquipmentSlot.SCROLL: 1,
            }

            for slot, count in slot_counts.items():
                templates = _templates_for_slot(db, slot)
                if not templates:
                    continue
                chosen = (templates * count)[:count] if len(templates) < count else generator.rng.sample(templates, count)

                for template in chosen:
                    item = generator.generate_item(
                        template,
                        player_id=player.id,
                        item_level=TEST_ITEM_LEVEL,
                        rarity_override=TEST_RARITY,
                        force_ability=True,
                    )
                    db.add(item)
                    db.commit()
                    db.refresh(item)

                    ok, message = inventory_service.equip_item(db, player, item)
                    granted_names.append(f"{'✅' if ok else '⚠️'} {item.display_name}")

            db.commit()
        finally:
            db.close()

        summary = (
            f"🛠️ **Test kit granted!**\n"
            f"🪙 +{TEST_GOLD:,} gold | 💎 +{TEST_SHARDS:,} shards | "
            f"📦 +{TEST_LOOTBOXES_PER_TIER} of every lootbox tier\n\n"
            f"**Equipped:**\n" + "\n".join(granted_names) +
            "\n\nRun `/profile` to see your new stats and abilities."
        )
        await ctx.followup.send(summary, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Admin(bot))
