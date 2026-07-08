"""
Turns a generated item's mechanics into a Diablo-style display name, e.g.
"Savage Iron Sword of Chaos". Purely cosmetic -- naming never affects stats,
it just reflects them so a glance at the name hints at what the item does.
"""

from __future__ import annotations

import random

from bot.database.models.enums import Rarity

# Prefix chosen from the item's single strongest substat (by rarity-scaled
# value). Falls back to a rarity-flavored generic prefix if there are no
# substats to draw from.
PREFIX_BY_STAT: dict[str, list[str]] = {
    "attack": ["Savage", "Fierce", "Brutal", "Vicious"],
    "defense": ["Sturdy", "Guarded", "Reinforced", "Bulwark"],
    "elemental": ["Arcane", "Mystic", "Runic", "Eldritch"],
    "speed": ["Swift", "Fleet", "Nimble", "Hastened"],
    "max_hp": ["Vital", "Hearty", "Stalwart", "Undying"],
    "max_mana": ["Ethereal", "Luminous", "Wellspring", "Attuned"],
    "crit_rate": ["Deadly", "Lethal", "Precise", "Keen"],
    "crit_damage": ["Merciless", "Ruthless", "Devastating", "Savage"],
    "recharge": ["Galvanic", "Charged", "Kinetic", "Surging"],
}

GENERIC_PREFIX_BY_RARITY: dict[Rarity, list[str]] = {
    Rarity.COMMON: ["Worn", "Plain"],
    Rarity.UNCOMMON: ["Sturdy", "Reliable"],
    Rarity.RARE: ["Fine", "Notable"],
    Rarity.EPIC: ["Heroic", "Exalted"],
    Rarity.LEGENDARY: ["Legendary", "Storied"],
    Rarity.MYTHIC: ["Mythic", "Transcendent"],
    Rarity.ANCIENT: ["Ancient", "Primeval"],
    Rarity.DIVINE: ["Divine", "Celestial"],
}

# Suffix chosen from the item's ability (if any), otherwise from a rarity pool.
SUFFIX_BY_ABILITY_EFFECT_KIND: dict[str, list[str]] = {
    "damage_and_dot": ["of Flames", "of Cinders"],
    "damage_multiplier": ["of Ruin", "of Might"],
    "damage_and_debuff": ["of Frost", "of Winter"],
    "heal_percent_max_hp": ["of Life", "of Renewal"],
    "damage_and_stun": ["of Judgment", "of Force"],
    "self_buff_debuff": ["of Fury", "of Rage"],
    "damage_execute_heal": ["of the Phoenix", "of Rebirth"],
    "damage_and_heal_self": ["of the Leech", "of Hunger"],
    "heal_and_self_buff": ["of Resurgence", "of the Dawn"],
    "multi_hit": ["of the Tempest", "of Fury's Edge"],
    "lifesteal": ["of the Leech", "of Hunger"],
    "damage_reflect": ["of Thorns", "of Retribution"],
    "crit_damage_bonus": ["of Doom", "of Execution"],
    "stacking_buff": ["of Momentum", "of the Storm"],
    "prevent_death": ["of Defiance", "of the Phoenix"],
    "on_kill_restore": ["of the Reaper", "of Souls"],
    "damage_reduction": ["of Wardship", "of the Bastion"],
    "resource_regen": ["of the Archmage", "of Ether"],
}

GENERIC_SUFFIX_BY_RARITY: dict[Rarity, list[str]] = {
    Rarity.COMMON: ["of the Novice"],
    Rarity.UNCOMMON: ["of the Adept"],
    Rarity.RARE: ["of Fortune", "of Kings"],
    Rarity.EPIC: ["of Chaos", "of Glory"],
    Rarity.LEGENDARY: ["of Legends", "of the Ancients"],
    Rarity.MYTHIC: ["of the Void", "of Eternity"],
    Rarity.ANCIENT: ["of the First Age", "of the Old Gods"],
    Rarity.DIVINE: ["of Creation", "of the Heavens"],
}


def generate_display_name(
    base_name: str,
    rarity: Rarity,
    substats: list[dict],
    active_ability: dict | None,
    passive_ability: dict | None,
    rng: random.Random,
) -> str:
    # Prefix: strongest substat by value, else generic rarity flavor.
    if substats:
        top = max(substats, key=lambda s: s["value"])
        prefix_pool = PREFIX_BY_STAT.get(top["stat"], GENERIC_PREFIX_BY_RARITY[rarity])
    else:
        prefix_pool = GENERIC_PREFIX_BY_RARITY[rarity]
    prefix = rng.choice(prefix_pool)

    # Suffix: prefer the ability's flavor, active over passive, else generic.
    ability = active_ability or passive_ability
    if ability and ability["effect"]["kind"] in SUFFIX_BY_ABILITY_EFFECT_KIND:
        suffix_pool = SUFFIX_BY_ABILITY_EFFECT_KIND[ability["effect"]["kind"]]
    else:
        suffix_pool = GENERIC_SUFFIX_BY_RARITY[rarity]
    suffix = rng.choice(suffix_pool)

    # Common items with no ability and no substats stay plain -- not every
    # drop should sound epic.
    if rarity == Rarity.COMMON and not ability and len(substats) < 1:
        return base_name

    return f"{prefix} {base_name} {suffix}"
