"""
Prestige: starting over, on purpose, and getting something for it.

Two ways to wipe an account, both from the player-facing `/reset`:

  * CLEAN     -- the account is deleted and rebuilt empty. The prologue
                 from the beginning, nothing carried, nothing granted.
  * PRESTIGE  -- the same wipe, but the new account starts with a bundle
                 of gold, shards, lootboxes and materials scaled to what
                 the old one had achieved, and a permanent badge counting
                 how many times you've done it.

----------------------------------------------------------------------
WHY A PRESTIGE PAYS LESS THAN IT COSTS
----------------------------------------------------------------------
The obvious failure mode is a shard farm: if resetting returns more
value than the run produced, the optimal way to play is to rush the
cheapest milestone and reset in a loop forever, and every number in the
economy is then wrong.

So the payout is deliberately a FRACTION of the progress it consumes
(PAYOUT_FRACTION). Prestiging is never a net gain in resources -- it
buys a fresh start with a head start, which is a different thing and the
only thing it should be. A player who wants shards is always better off
playing the account they have.

The second guard is the gate: prestige is unavailable until the account
has actually got somewhere (MIN_LEVEL / MIN_SCORE). Below that, only a
clean reset is offered, because there is nothing to be proud of yet and
nothing worth paying out for.

----------------------------------------------------------------------
WHAT "PROGRESS" MEANS
----------------------------------------------------------------------
One number, `progress_score`, computed from the things a player would
name if you asked them how far they'd got: account level, the characters
they've raised, the gear they've built, the story they've cleared and
the currency they're sitting on. It is deliberately NOT just net worth
-- an account that hoarded gold and never fought should not out-prestige
one that spent everything getting to Abyssnia.

The score feeds two things: whether the gate opens, and how big the
bundle is. Keeping it to a single function means "how far have I got"
has one answer, and tuning the feature is tuning one curve.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from bot.database.models.character_model import PlayerCharacter
from bot.database.models.equipment_model import InventoryItem
from bot.database.models.enums import MaterialType
from bot.database.models.player_model import Player

# ----------------------------------------------------------------------
# THE GATE
# ----------------------------------------------------------------------
# Both conditions must hold. Level alone is gameable by grinding the
# easiest content; score alone can be reached by hoarding. Requiring both
# means the player has actually played a game.
MIN_LEVEL = 15
MIN_SCORE = 2_000

# ----------------------------------------------------------------------
# THE PAYOUT
# ----------------------------------------------------------------------
# How much of the run's measured progress comes back as resources. Set
# well below 1.0 on purpose -- see the block at the top. At 0.18 a player
# who reaches the gate exactly gets a meaningful head start (a few
# thousand gold, a pull's worth of shards) and a player who prestiges
# from a deep account gets several times that, while both are handing
# over strictly more than they receive.
PAYOUT_FRACTION = 0.18

# Diminishing returns on REPEAT prestiges, so the second and third are
# worth doing for the badge rather than for the bundle. Multiplies the
# bundle by this to the power of prestiges already done: 100%, 70%, 49%.
REPEAT_PAYOUT_FALLOFF = 0.7

# How the bundle splits. Shards are the scarce currency (120 per pull),
# so their share is small in absolute terms and is what makes the bundle
# feel valuable; gold is the bulk.
GOLD_PER_SCORE = 1.4
SHARDS_PER_SCORE = 0.05

# Materials are priced against what they're FOR, which is gear upgrades:
# one level-up costs 2 units rising to about 9 at level 30, split across
# three types (see item_upgrade_service). A first pass at this paid out
# 3,240 units of every material to a deep account -- enough to level
# every item anyone will ever own, several times over, which would have
# made the entire harvester and material economy pointless for anyone
# who had prestiged once.
MATERIAL_PER_SCORE = 0.015

# ...and rarer materials are rarer. The same first pass handed out
# exactly as much Xendium as Wood, which is wrong by the whole design of
# the material tiers: MaterialType.tier exists precisely because these
# are not interchangeable. Divides the payout by tier, so the deep
# materials stay something you go and earn.
MATERIAL_TIER_DIVISOR = {0: 1, 1: 3, 2: 9, 3: 27}

# Lootbox tiers unlocked by score, best-first. A player prestiging from
# the endgame should get boxes that reflect where they were, not a pile
# of Commons.
LOOTBOX_LADDER: list[tuple[int, str, int]] = [
    # (score needed, tier, how many)
    (40_000, "mythic", 3),
    (20_000, "legendary", 4),
    (10_000, "epic", 4),
    (5_000, "rare", 5),
    (2_000, "uncommon", 5),
    (0, "common", 3),
]

# Materials paid out, cheapest-first. A deep account gets the deeper
# tiers too, which is the part a returning player actually can't
# shortcut -- gold is farmable in an afternoon, Xendium is not.
MATERIAL_LADDER: list[tuple[int, str]] = [
    (0, "wood"),
    (0, "stone"),
    (5_000, "metal"),
    (12_000, "crystal"),
    (25_000, "xendium"),
]


@dataclass
class PrestigeReward:
    """What a prestige would hand back. Built by preview_rewards, and the
    exact object granted by perform -- so the preview cannot drift from
    the payout, which for an irreversible action matters more than
    usual."""

    score: int = 0
    gold: int = 0
    shards: int = 0
    materials: dict[str, int] = field(default_factory=dict)
    lootboxes: dict[str, int] = field(default_factory=dict)

    def is_empty(self) -> bool:
        return not (self.gold or self.shards or self.materials or self.lootboxes)


def progress_score(db, player: Player) -> int:
    """One number for "how far did this account get".

    Weighted so that things you can only get by PLAYING count for more
    than things you can get by saving: a levelled character is worth more
    than the gold it took to level, and clearing a region is worth more
    than either.
    """
    score = 0

    # Account level -- superlinear, because levels get harder.
    score += int((player.level or 1) ** 1.6) * 6

    characters = db.query(PlayerCharacter).filter_by(player_id=player.id).all()
    for character in characters:
        template = character.template
        stars = getattr(template, "star_rating", 3) if template else 3
        # A 5-star at level 60 is the headline achievement of an account.
        score += 40 * stars
        score += int((character.level or 1) ** 1.4) * stars
        # Duplicates are pulls that already happened.
        score += 60 * max(0, getattr(character, "dupe_count", 0) or 0)

    items = db.query(InventoryItem).filter_by(player_id=player.id).all()
    for item in items:
        rarity = getattr(item, "rarity", None)
        sort_order = getattr(rarity, "sort_order", 0) or 0
        score += 8 * (sort_order + 1)
        score += 3 * max(0, (getattr(item, "item_level", 1) or 1) - 1)

    # Liquid wealth counts, but weakly -- it is the most easily hoarded
    # and the least indicative of progress.
    score += int((player.gold or 0) * 0.05)
    score += int((player.shards or 0) * 0.4)
    score += int((player.echoes or 0) * 0.3)

    return max(0, int(score))


def eligible(db, player: Player) -> tuple[bool, str]:
    """(can prestige, why not). The reason is shown to the player, so it
    always names the number they need rather than just refusing."""
    if (player.level or 1) < MIN_LEVEL:
        return False, (
            f"Prestige unlocks at account level {MIN_LEVEL} — you're level "
            f"{player.level or 1}. A clean reset is still available."
        )
    score = progress_score(db, player)
    if score < MIN_SCORE:
        return False, (
            f"Prestige needs a bit more progress ({score:,} / {MIN_SCORE:,}). "
            f"Raise some characters or push a region further. A clean reset "
            f"is still available."
        )
    return True, ""


def preview_rewards(db, player: Player) -> PrestigeReward:
    """The exact bundle a prestige would grant, right now."""
    score = progress_score(db, player)
    reward = PrestigeReward(score=score)

    already = max(0, player.prestige_count or 0)
    scale = PAYOUT_FRACTION * (REPEAT_PAYOUT_FALLOFF ** already)
    paid = score * scale

    reward.gold = int(paid * GOLD_PER_SCORE)
    reward.shards = int(paid * SHARDS_PER_SCORE)

    material_budget = paid * MATERIAL_PER_SCORE
    for needed, material in MATERIAL_LADDER:
        if score < needed:
            continue
        tier = MaterialType(material).tier
        amount = int(material_budget / MATERIAL_TIER_DIVISOR.get(tier, 1))
        if amount > 0:
            reward.materials[material] = amount

    for needed, tier, count in LOOTBOX_LADDER:
        if score >= needed:
            reward.lootboxes[tier] = count
            break

    return reward


def perform(db, player_id: int, prestige: bool) -> tuple[dict[str, int], PrestigeReward]:
    """Wipe the account and rebuild it. Returns (rows deleted, rewards).

    The account is RECREATED here rather than leaving the player to run
    /start themselves. `/reset` is a player-facing command now, and one
    that leaves you with no account until you remember a second command
    is a trap -- especially since the failure looks identical to the
    reset having broken.
    """
    from bot.services import (
        character_service,
        currency_service,
        lootbox_service,
        player_reset_service,
        story_service,
    )
    from bot.services.player_service import get_or_create_player, get_player

    player = get_player(db, player_id)
    if player is None:
        return {}, PrestigeReward()

    username = player.username
    # Read everything that has to outlive the row BEFORE it is deleted.
    reward = preview_rewards(db, player) if prestige else PrestigeReward()
    carried_count = (player.prestige_count or 0) + (1 if prestige else 0)
    carried_best = max(player.prestige_best_level or 0, player.level or 1)

    deleted = player_reset_service.reset(db, player_id)

    get_or_create_player(db, player_id, username)
    fresh = get_player(db, player_id)
    fresh.prestige_count = carried_count
    fresh.prestige_best_level = carried_best
    character_service.ensure_avatar_character(db, fresh)
    story_service.get_or_create(db, fresh)
    db.commit()

    if prestige and not reward.is_empty():
        if reward.gold:
            currency_service.add_currency(db, fresh, "gold", reward.gold)
        if reward.shards:
            currency_service.add_currency(db, fresh, "shards", reward.shards)
        for material, amount in reward.materials.items():
            currency_service.add_currency(db, fresh, material, amount)
        for tier, count in reward.lootboxes.items():
            lootbox_service.grant_lootbox(db, fresh, tier, count)
        db.commit()

    return deleted, reward


# ----------------------------------------------------------------------
# BADGES
# ----------------------------------------------------------------------
# The whole of what a prestige is worth permanently: proof you did it.
#
# Deliberately NOT a stat bonus. A reset that makes you stronger forever
# is a treadmill every serious player is then obliged to ride, and it
# quietly re-tunes the entire difficulty curve around people who have
# ridden it. A badge costs nothing to balance and says the same thing.
PRESTIGE_BADGE = "🔆"
MAX_BADGES_SHOWN = 5


def badge_text(player: Player) -> str:
    """The badge string for a profile, or "" for a first-life account."""
    count = max(0, player.prestige_count or 0)
    if not count:
        return ""
    if count <= MAX_BADGES_SHOWN:
        return PRESTIGE_BADGE * count
    return f"{PRESTIGE_BADGE}×{count}"
