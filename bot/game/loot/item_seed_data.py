"""
Starter item catalog. Without at least one ItemTemplate per slot, gacha,
lootboxes, and combat drops have nothing to roll -- this is what makes the
economy/loot systems actually produce items rather than erroring out with
"no item templates exist yet."

Combat Overhaul slots (one item each, per character): WEAPON, ARTIFACT,
ARMOR, ACCESSORY. The old HEAD/CHEST/LEGGINGS/BOOTS split has been merged
into a single ARMOR slot, and SCROLL is gone entirely (ultimates now come
from character kits -- see bot/game/characters/character_seed_data.py).

The back half of this catalog is the item SET system: Wood, Iron, Sigma
Wolf, Crystal, Xendium, Permafrost, Hi-Tech, Error Code, Voidwalker,
Entropic, Refense, and the ultra-rare "500 Billian Gem Giveaway". Each set
piece has a fixed `set_prefix` (so its display name is always just
"{prefix} {item name}" -- see bot/game/loot/naming.py) and a
`linked_ability_id` that's ALWAYS the ability it rolls (when it rolls one
at all -- still gated by RARITY_ABILITY_CHANCE), rather than a random pick
from its item_type's pool. Sets lean toward a particular class role
(Crystal/Xendium -> casters, Permafrost/Refense -> tanks/Sustain, Hi-Tech ->
Support DPS, Sigma Wolf -> DPS) without being exclusive to it, alongside
Wood/Iron as simple, generic, flexible early options.

Seeded on startup the same way harvester/lootbox templates are (see
bot/services/item_template_service.py). Expanding this catalog with more
variety per slot/set is pure content work -- no code changes needed.
"""

from __future__ import annotations

from bot.database.models.enums import EquipmentSlot, ItemType

ITEM_TEMPLATES: list[dict] = [
    # ---------------------------------------------------------------
    # Weapons -- main stat is attack or elemental. May roll a weapon skill.
    # ---------------------------------------------------------------
    {"name": "Iron Sword", "item_type": ItemType.WEAPON, "slot": EquipmentSlot.WEAPON,
     "main_stat": "attack", "base_main_stat_value": 12,
     "flavor_text": "A well-balanced blade, standard issue for Cascade wanderers."},
    {"name": "Oakwood Bow", "item_type": ItemType.WEAPON, "slot": EquipmentSlot.WEAPON,
     "main_stat": "attack", "base_main_stat_value": 10,
     "flavor_text": "Carved from ancient oak, still humming faintly with old magic."},
    {"name": "Twin Daggers", "item_type": ItemType.WEAPON, "slot": EquipmentSlot.WEAPON,
     "main_stat": "attack", "base_main_stat_value": 9,
     "flavor_text": "Fast, light, and favored by scouts who strike before being seen."},
    {"name": "Arcane Staff", "item_type": ItemType.WEAPON, "slot": EquipmentSlot.WEAPON,
     "main_stat": "elemental", "base_main_stat_value": 14,
     "flavor_text": "Channels raw Cascade energy into devastating spells."},
    {"name": "Voidglass Wand", "item_type": ItemType.WEAPON, "slot": EquipmentSlot.WEAPON,
     "main_stat": "elemental", "base_main_stat_value": 13,
     "flavor_text": "Forged from crystallized Void matter -- cold to hold, colder to face."},

    # ---------------------------------------------------------------
    # Armor -- single slot now. Main stat: defense, health, speed, energy
    # (recharge), or mana. May roll a passive.
    # ---------------------------------------------------------------
    {"name": "Iron Chestplate", "item_type": ItemType.ARMOR, "slot": EquipmentSlot.ARMOR,
     "main_stat": "defense", "base_main_stat_value": 14,
     "flavor_text": "Forged to withstand the Cascade's deepest horrors."},
    {"name": "Leather Vest", "item_type": ItemType.ARMOR, "slot": EquipmentSlot.ARMOR,
     "main_stat": "speed", "base_main_stat_value": 8,
     "flavor_text": "Favored by scouts who value speed over protection."},
    {"name": "Runic Robe", "item_type": ItemType.ARMOR, "slot": EquipmentSlot.ARMOR,
     "main_stat": "max_mana", "base_main_stat_value": 24,
     "flavor_text": "Threaded with sigils that hum when spells are near."},
    {"name": "Pendant of Vigor", "item_type": ItemType.ARMOR, "slot": EquipmentSlot.ARMOR,
     "main_stat": "max_hp", "base_main_stat_value": 40,
     "flavor_text": "Warm to the touch, even in the coldest depths."},
    {"name": "Charged Plating", "item_type": ItemType.ARMOR, "slot": EquipmentSlot.ARMOR,
     "main_stat": "recharge", "base_main_stat_value": 4,
     "flavor_text": "Faintly crackles with stored Cascade energy."},

    # ---------------------------------------------------------------
    # Accessories -- secondary defensive/utility slot. Main stat: defense,
    # health, speed, energy (recharge), mana, crit rate, or crit damage.
    # May roll a passive.
    # ---------------------------------------------------------------
    {"name": "Amulet of Insight", "item_type": ItemType.ARMOR, "slot": EquipmentSlot.ACCESSORY,
     "main_stat": "max_mana", "base_main_stat_value": 18,
     "flavor_text": "Whispers old Cascade secrets to those who listen."},
    {"name": "Swift Boots", "item_type": ItemType.ARMOR, "slot": EquipmentSlot.ACCESSORY,
     "main_stat": "speed", "base_main_stat_value": 9,
     "flavor_text": "Feels lighter than air."},
    {"name": "Iron Greaves", "item_type": ItemType.ARMOR, "slot": EquipmentSlot.ACCESSORY,
     "main_stat": "defense", "base_main_stat_value": 8,
     "flavor_text": "Sturdy plating for the long descent."},
    {"name": "Battery-Lined Bracer", "item_type": ItemType.ARMOR, "slot": EquipmentSlot.ACCESSORY,
     "main_stat": "recharge", "base_main_stat_value": 4,
     "flavor_text": "Scavenged tech, repurposed for the fight ahead."},
    {"name": "Ring of Precision", "item_type": ItemType.ARMOR, "slot": EquipmentSlot.ACCESSORY,
     "main_stat": "crit_damage", "base_main_stat_value": 15,
     "flavor_text": "Sharpens the wearer's focus in the heat of battle."},
    {"name": "Wanderer's Treads", "item_type": ItemType.ARMOR, "slot": EquipmentSlot.ACCESSORY,
     "main_stat": "max_hp", "base_main_stat_value": 25,
     "flavor_text": "Thousands of miles, and still holding together."},

    # ---------------------------------------------------------------
    # Artifacts -- main stat: speed, energy (recharge), attack, elemental,
    # crit damage, crit rate, HP, or DEF. May roll an artifact skill.
    # ---------------------------------------------------------------
    {"name": "Band of Fortune", "item_type": ItemType.ARTIFACT, "slot": EquipmentSlot.ARTIFACT,
     "main_stat": "crit_rate", "base_main_stat_value": 6,
     "flavor_text": "Said to guide its wearer toward better fortune."},
    {"name": "Cascade Core Shard", "item_type": ItemType.ARTIFACT, "slot": EquipmentSlot.ARTIFACT,
     "main_stat": "elemental", "base_main_stat_value": 10,
     "flavor_text": "A fragment of the Cascade itself, still faintly pulsing."},
    {"name": "Kinetic Battery", "item_type": ItemType.ARTIFACT, "slot": EquipmentSlot.ARTIFACT,
     "main_stat": "recharge", "base_main_stat_value": 4,
     "flavor_text": "Stores momentum and releases it as raw energy."},
    {"name": "Wanderer's Compass", "item_type": ItemType.ARTIFACT, "slot": EquipmentSlot.ARTIFACT,
     "main_stat": "speed", "base_main_stat_value": 7,
     "flavor_text": "Always points toward the fastest way forward."},
    {"name": "Bloodfang Talisman", "item_type": ItemType.ARTIFACT, "slot": EquipmentSlot.ARTIFACT,
     "main_stat": "attack", "base_main_stat_value": 11,
     "flavor_text": "Carved from a predator's tooth, still hungry."},
    {"name": "Bulwark Idol", "item_type": ItemType.ARTIFACT, "slot": EquipmentSlot.ARTIFACT,
     "main_stat": "defense", "base_main_stat_value": 12,
     "flavor_text": "An old ward-stone, radiating quiet stubbornness."},
    {"name": "Heartroot Talisman", "item_type": ItemType.ARTIFACT, "slot": EquipmentSlot.ARTIFACT,
     "main_stat": "max_hp", "base_main_stat_value": 35,
     "flavor_text": "Grown, not forged -- it beats faintly, like something alive."},

    # ---------------------------------------------------------------
    # Item sets. Each set has a fixed prefix (the whole display name is
    # just "{prefix} {item name}" now -- see bot/game/loot/naming.py) and
    # a linked_ability_id so that piece always carries the same identity
    # ability instead of a random roll. Main stat is fixed per template
    # (same as every other item -- substats are still random), and each
    # set leans toward a particular role without being exclusive to it.
    #
    # Each set now has TWO pieces -- one from the "active" slots
    # (weapon/artifact, using WEAPON_SKILLS/ARTIFACT_SKILLS) and one from
    # the "passive" slots (armor/accessory, using ARMOR_PASSIVES) -- so a
    # set actually covers two of a character's four gear slots instead of
    # just one, and several now carry abilities from the newer status-
    # effect content pass (retaliation_plating, system_purge, emp_burst,
    # combat_medic, regen_field_generator, support_matrix).
    # ---------------------------------------------------------------

    # Wood -- earliest material tier, generic/defensive, simple starter set.
    {"name": "Vest", "item_type": ItemType.ARMOR, "slot": EquipmentSlot.ARMOR,
     "main_stat": "defense", "base_main_stat_value": 7,
     "set_name": "Wood Set", "set_prefix": "Wood", "linked_ability_id": "iron_skin",
     "flavor_text": "Cheap, plentiful, and better than nothing. Most Cascade wanderers start here."},
    {"name": "Club", "item_type": ItemType.WEAPON, "slot": EquipmentSlot.WEAPON,
     "main_stat": "attack", "base_main_stat_value": 8,
     "set_name": "Wood Set", "set_prefix": "Wood", "linked_ability_id": "shield_bash",
     "flavor_text": "Splintery, heavy, and effective. Nobody asks where the wood came from."},

    # Iron -- generic/flexible, the reliable step up from Wood.
    {"name": "Longsword", "item_type": ItemType.WEAPON, "slot": EquipmentSlot.WEAPON,
     "main_stat": "attack", "base_main_stat_value": 9,
     "set_name": "Iron Set", "set_prefix": "Iron", "linked_ability_id": "power_strike",
     "flavor_text": "No frills. It cuts, and it doesn't break."},
    {"name": "Cuirass", "item_type": ItemType.ARMOR, "slot": EquipmentSlot.ARMOR,
     "main_stat": "defense", "base_main_stat_value": 9,
     "set_name": "Iron Set", "set_prefix": "Iron", "linked_ability_id": "retaliation_plating",
     "flavor_text": "Dented in a dozen places. Still standing in all of them."},

    # Sigma Wolf -- feral, aggressive, DPS-leaning.
    {"name": "Fang", "item_type": ItemType.WEAPON, "slot": EquipmentSlot.WEAPON,
     "main_stat": "attack", "base_main_stat_value": 10,
     "set_name": "Sigma Wolf Set", "set_prefix": "Sigma Wolf", "linked_ability_id": "berserker_rage",
     "flavor_text": "Runs with a pack of one. Answers to nobody."},
    {"name": "Fangguard", "item_type": ItemType.ARMOR, "slot": EquipmentSlot.ACCESSORY,
     "main_stat": "crit_damage", "base_main_stat_value": 12,
     "set_name": "Sigma Wolf Set", "set_prefix": "Sigma Wolf", "linked_ability_id": "vampiric_edge",
     "flavor_text": "Every kill feeds the next one."},

    # Crystal -- mana/elemental, caster/Amplifier-leaning.
    {"name": "Prism", "item_type": ItemType.ARTIFACT, "slot": EquipmentSlot.ARTIFACT,
     "main_stat": "elemental", "base_main_stat_value": 9,
     "set_name": "Crystal Set", "set_prefix": "Crystal", "linked_ability_id": "arcane_burst",
     "flavor_text": "Refracts more than just light."},
    {"name": "Focus Lens", "item_type": ItemType.ARMOR, "slot": EquipmentSlot.ACCESSORY,
     "main_stat": "max_mana", "base_main_stat_value": 20,
     "set_name": "Crystal Set", "set_prefix": "Crystal", "linked_ability_id": "arcane_battery",
     "flavor_text": "Hums faintly, always drawing in a little more than it gives off."},

    # Xendium -- lava/fire, aggressive elemental weapon.
    {"name": "Cinderblade", "item_type": ItemType.WEAPON, "slot": EquipmentSlot.WEAPON,
     "main_stat": "elemental", "base_main_stat_value": 10,
     "set_name": "Xendium Set", "set_prefix": "Xendium", "linked_ability_id": "flame_strike",
     "flavor_text": "Forged in Hotlands magma. Never quite cools down."},
    {"name": "Slagplate", "item_type": ItemType.ARMOR, "slot": EquipmentSlot.ARMOR,
     "main_stat": "defense", "base_main_stat_value": 8,
     "set_name": "Xendium Set", "set_prefix": "Xendium", "linked_ability_id": "iron_skin",
     "flavor_text": "Cooled just enough to wear. Just barely."},

    # Permafrost -- ice/defense, tank/Sustain-leaning.
    {"name": "Plate", "item_type": ItemType.ARMOR, "slot": EquipmentSlot.ARMOR,
     "main_stat": "defense", "base_main_stat_value": 8,
     "set_name": "Permafrost Set", "set_prefix": "Permafrost", "linked_ability_id": "thornmail",
     "flavor_text": "Frozen solid centuries ago. Still holds an edge -- and a grudge."},
    {"name": "Frostbrand", "item_type": ItemType.WEAPON, "slot": EquipmentSlot.WEAPON,
     "main_stat": "elemental", "base_main_stat_value": 9,
     "set_name": "Permafrost Set", "set_prefix": "Permafrost", "linked_ability_id": "frost_lance",
     "flavor_text": "Draws the warmth out of anything it touches."},

    # Hi-Tech -- crit/precision, Support DPS-leaning.
    {"name": "Visor", "item_type": ItemType.ARMOR, "slot": EquipmentSlot.ACCESSORY,
     "main_stat": "crit_rate", "base_main_stat_value": 5,
     "set_name": "Hi-Tech Set", "set_prefix": "Hi-Tech", "linked_ability_id": "support_matrix",
     "flavor_text": "Scavenged, patched, and somehow still calibrating -- for the whole squad, not just its wearer."},
    {"name": "Diagnostic Core", "item_type": ItemType.ARTIFACT, "slot": EquipmentSlot.ARTIFACT,
     "main_stat": "elemental", "base_main_stat_value": 9,
     "set_name": "Hi-Tech Set", "set_prefix": "Hi-Tech", "linked_ability_id": "system_purge",
     "flavor_text": "Finds every gap in an enemy's armor and reports back instantly."},

    # Error Code -- glitchy, chaotic/flexible, recharge-leaning.
    {"name": "Fragment", "item_type": ItemType.ARMOR, "slot": EquipmentSlot.ACCESSORY,
     "main_stat": "recharge", "base_main_stat_value": 4,
     "set_name": "Error Code Set", "set_prefix": "Error Code", "linked_ability_id": "arcane_battery",
     "flavor_text": "It shouldn't work. It works anyway."},
    {"name": "Corrupted Drive", "item_type": ItemType.ARTIFACT, "slot": EquipmentSlot.ARTIFACT,
     "main_stat": "elemental", "base_main_stat_value": 9,
     "set_name": "Error Code Set", "set_prefix": "Error Code", "linked_ability_id": "emp_burst",
     "flavor_text": "Whatever it corrupts on the way in, it corrupts twice as hard on the way out."},

    # Voidwalker -- high-end elemental artifact.
    {"name": "Rift Shard", "item_type": ItemType.ARTIFACT, "slot": EquipmentSlot.ARTIFACT,
     "main_stat": "elemental", "base_main_stat_value": 11,
     "set_name": "Voidwalker Set", "set_prefix": "Voidwalker", "linked_ability_id": "void_grasp",
     "flavor_text": "Colder than Permafrost. Emptier than anything."},
    {"name": "Abyssal Plate", "item_type": ItemType.ARMOR, "slot": EquipmentSlot.ARMOR,
     "main_stat": "defense", "base_main_stat_value": 10,
     "set_name": "Voidwalker Set", "set_prefix": "Voidwalker", "linked_ability_id": "undying_will",
     "flavor_text": "The void doesn't let go easily -- apparently that cuts both ways."},

    # Entropic -- high-end, crit damage / chaos-leaning.
    {"name": "Husk", "item_type": ItemType.ARTIFACT, "slot": EquipmentSlot.ARTIFACT,
     "main_stat": "crit_damage", "base_main_stat_value": 14,
     "set_name": "Entropic Set", "set_prefix": "Entropic", "linked_ability_id": "soul_siphon",
     "flavor_text": "Falls apart a little more every time it's used. Somehow that's the point."},
    {"name": "Decay Band", "item_type": ItemType.ARMOR, "slot": EquipmentSlot.ACCESSORY,
     "main_stat": "crit_rate", "base_main_stat_value": 5,
     "set_name": "Entropic Set", "set_prefix": "Entropic", "linked_ability_id": "executioner",
     "flavor_text": "Finds the weak point in everything, including itself."},

    # Refense -- Refender's philosophy, balance of offense/defense, Sustain-leaning.
    {"name": "Bulwark", "item_type": ItemType.ARMOR, "slot": EquipmentSlot.ARMOR,
     "main_stat": "defense", "base_main_stat_value": 9,
     "set_name": "Refense Set", "set_prefix": "Refense", "linked_ability_id": "second_wind",
     "flavor_text": "Neither sword nor shield alone. Refender would approve."},
    {"name": "Refense Core", "item_type": ItemType.ARTIFACT, "slot": EquipmentSlot.ARTIFACT,
     "main_stat": "max_hp", "base_main_stat_value": 30,
     "set_name": "Refense Set", "set_prefix": "Refense", "linked_ability_id": "combat_medic",
     "flavor_text": "Balance isn't just personal -- Refender's teachings hold the whole line together."},

    # "500 Billian Gem Giveaway" -- ultra rare joke set. The misspelling of
    # "Billion" is intentional; the creator, a silly man named Thedoggyp,
    # would not have it any other way.
    {"name": "Gem", "item_type": ItemType.ARTIFACT, "slot": EquipmentSlot.ARTIFACT,
     "main_stat": "crit_rate", "base_main_stat_value": 13,
     "set_name": "500 Billian Gem Giveaway", "set_prefix": "Billian",
     "linked_ability_id": "starfall", "is_ultra_rare": True,
     "flavor_text": "Certificate of authenticity signed 'Thedoggyp' in crayon. Somehow still worth it."},
    {"name": "Coin", "item_type": ItemType.ARMOR, "slot": EquipmentSlot.ACCESSORY,
     "main_stat": "crit_damage", "base_main_stat_value": 12,
     "set_name": "500 Billian Gem Giveaway", "set_prefix": "Billian",
     "linked_ability_id": "regen_field_generator", "is_ultra_rare": True,
     "flavor_text": "Novelty currency from a giveaway nobody remembers entering. Heals the whole team anyway."},
]
