"""
Starter item catalog. Without at least one ItemTemplate per slot, gacha,
lootboxes, and combat drops have nothing to roll -- this is what makes the
economy/loot systems actually produce items rather than erroring out with
"no item templates exist yet."

Combat Overhaul slots, per character: WEAPON (x1), ARTIFACT (x1), ARMOR
(x2), ACCESSORY (x2) -- see enums.SLOT_CAPACITY. The old HEAD/CHEST/
LEGGINGS/BOOTS split has been merged into a single ARMOR slot, and SCROLL
is gone entirely (ultimates now come from character kits -- see
bot/game/characters/character_seed_data.py).

The back half of this catalog is the item SET system: Wood, Iron, Sigma
Wolf, Crystal, Xendium, Permafrost, Hi-Tech, Error Code, Voidwalker,
Entropic, Refense, Aegis, and the ultra-rare "500 Billian Gem Giveaway".
Each set piece has a fixed `set_prefix` (so its display name is always just
"{prefix} {item name}" -- see bot/game/loot/naming.py) and a
`linked_ability_id` that's ALWAYS the ability it rolls (when it rolls one
at all -- still gated by RARITY_ABILITY_CHANCE), rather than a random pick
from its item_type's pool. Sets lean toward a particular class role
(Crystal/Xendium -> casters, Permafrost/Refense/Aegis -> tanks/Sustain,
Hi-Tech -> Support DPS, Sigma Wolf -> DPS) without being exclusive to it,
alongside Wood/Iron as simple, generic, flexible early options.

Seeded on startup the same way harvester/lootbox templates are (see
bot/services/item_template_service.py). Expanding this catalog with more
variety per slot/set is pure content work -- no code changes needed.
"""

from __future__ import annotations

from bot.database.models.enums import EquipmentSlot, ItemType, Rarity

ITEM_TEMPLATES: list[dict] = [
    # ---------------------------------------------------------------
    # Weapons -- main stat is attack or elemental. May roll a weapon skill.
    # ---------------------------------------------------------------
    {"name": "Iron Sword", "item_type": ItemType.WEAPON, "slot": EquipmentSlot.WEAPON,
     "main_stat": "attack", "base_main_stat_value": 12,
     "flavor_text": "A well-balanced blade, standard issue for Cascade wanderers.",
     "min_rarity": Rarity.COMMON, "max_rarity": Rarity.UNCOMMON},
    {"name": "Oakwood Bow", "item_type": ItemType.WEAPON, "slot": EquipmentSlot.WEAPON,
     "main_stat": "attack", "base_main_stat_value": 10,
     "flavor_text": "Carved from ancient oak, still humming faintly with old magic.",
     "min_rarity": Rarity.COMMON, "max_rarity": Rarity.UNCOMMON},
    {"name": "Twin Daggers", "item_type": ItemType.WEAPON, "slot": EquipmentSlot.WEAPON,
     "main_stat": "attack", "base_main_stat_value": 9,
     "flavor_text": "Fast, light, and favored by scouts who strike before being seen.",
     "min_rarity": Rarity.COMMON, "max_rarity": Rarity.UNCOMMON},
    {"name": "Arcane Staff", "item_type": ItemType.WEAPON, "slot": EquipmentSlot.WEAPON,
     "main_stat": "elemental", "base_main_stat_value": 14,
     "flavor_text": "Channels raw Cascade energy into devastating spells.",
     "min_rarity": Rarity.UNCOMMON, "max_rarity": Rarity.RARE},
    {"name": "Voidglass Wand", "item_type": ItemType.WEAPON, "slot": EquipmentSlot.WEAPON,
     "main_stat": "elemental", "base_main_stat_value": 13,
     "flavor_text": "Forged from crystallized Void matter -- cold to hold, colder to face.",
     "min_rarity": Rarity.UNCOMMON, "max_rarity": Rarity.RARE},
    {"name": "Windrunner Rapier", "item_type": ItemType.WEAPON, "slot": EquipmentSlot.WEAPON,
     "main_stat": "speed", "base_main_stat_value": 11,
     "flavor_text": "Barely touches the target before it's already somewhere else.",
     "min_rarity": Rarity.RARE, "max_rarity": Rarity.EPIC},
    {"name": "Serrated Kris", "item_type": ItemType.WEAPON, "slot": EquipmentSlot.WEAPON,
     "main_stat": "attack", "base_main_stat_value": 11,
     "flavor_text": "Every notch along the blade catches on the way out, not the way in.",
     "min_rarity": Rarity.RARE, "max_rarity": Rarity.EPIC},

    # ---------------------------------------------------------------
    # Armor -- single slot now. Main stat: defense, health, speed, energy
    # (recharge), or mana. May roll a passive.
    # ---------------------------------------------------------------
    {"name": "Iron Chestplate", "item_type": ItemType.ARMOR, "slot": EquipmentSlot.ARMOR,
     "main_stat": "defense", "base_main_stat_value": 14,
     "flavor_text": "Forged to withstand the Cascade's deepest horrors.",
     "min_rarity": Rarity.COMMON, "max_rarity": Rarity.UNCOMMON},
    {"name": "Leather Vest", "item_type": ItemType.ARMOR, "slot": EquipmentSlot.ARMOR,
     "main_stat": "speed", "base_main_stat_value": 8,
     "flavor_text": "Favored by scouts who value speed over protection.",
     "min_rarity": Rarity.COMMON, "max_rarity": Rarity.UNCOMMON},
    {"name": "Runic Robe", "item_type": ItemType.ARMOR, "slot": EquipmentSlot.ARMOR,
     "main_stat": "max_mana", "base_main_stat_value": 24,
     "flavor_text": "Threaded with sigils that hum when spells are near.",
     "min_rarity": Rarity.UNCOMMON, "max_rarity": Rarity.RARE},
    {"name": "Pendant of Vigor", "item_type": ItemType.ARMOR, "slot": EquipmentSlot.ARMOR,
     "main_stat": "max_hp", "base_main_stat_value": 40,
     "flavor_text": "Warm to the touch, even in the coldest depths.",
     "min_rarity": Rarity.COMMON, "max_rarity": Rarity.UNCOMMON},
    {"name": "Charged Plating", "item_type": ItemType.ARMOR, "slot": EquipmentSlot.ARMOR,
     "main_stat": "recharge", "base_main_stat_value": 4,
     "flavor_text": "Faintly crackles with stored Cascade energy.",
     "min_rarity": Rarity.UNCOMMON, "max_rarity": Rarity.RARE},

    # ---------------------------------------------------------------
    # Accessories -- secondary defensive/utility slot. Main stat: defense,
    # health, speed, energy (recharge), mana, crit rate, or crit damage.
    # May roll a passive.
    # ---------------------------------------------------------------
    {"name": "Amulet of Insight", "item_type": ItemType.ARMOR, "slot": EquipmentSlot.ACCESSORY,
     "main_stat": "max_mana", "base_main_stat_value": 18,
     "flavor_text": "Whispers old Cascade secrets to those who listen.",
     "min_rarity": Rarity.UNCOMMON, "max_rarity": Rarity.RARE},
    {"name": "Swift Boots", "item_type": ItemType.ARMOR, "slot": EquipmentSlot.ACCESSORY,
     "main_stat": "speed", "base_main_stat_value": 9,
     "flavor_text": "Feels lighter than air.",
     "min_rarity": Rarity.COMMON, "max_rarity": Rarity.UNCOMMON},
    {"name": "Iron Greaves", "item_type": ItemType.ARMOR, "slot": EquipmentSlot.ACCESSORY,
     "main_stat": "defense", "base_main_stat_value": 8,
     "flavor_text": "Sturdy plating for the long descent.",
     "min_rarity": Rarity.COMMON, "max_rarity": Rarity.UNCOMMON},
    {"name": "Battery-Lined Bracer", "item_type": ItemType.ARMOR, "slot": EquipmentSlot.ACCESSORY,
     "main_stat": "recharge", "base_main_stat_value": 4,
     "flavor_text": "Scavenged tech, repurposed for the fight ahead.",
     "min_rarity": Rarity.UNCOMMON, "max_rarity": Rarity.RARE},
    {"name": "Ring of Precision", "item_type": ItemType.ARMOR, "slot": EquipmentSlot.ACCESSORY,
     "main_stat": "crit_damage", "base_main_stat_value": 15,
     "flavor_text": "Sharpens the wearer's focus in the heat of battle.",
     "min_rarity": Rarity.RARE, "max_rarity": Rarity.EPIC},
    {"name": "Wanderer's Treads", "item_type": ItemType.ARMOR, "slot": EquipmentSlot.ACCESSORY,
     "main_stat": "max_hp", "base_main_stat_value": 25,
     "flavor_text": "Thousands of miles, and still holding together.",
     "min_rarity": Rarity.COMMON, "max_rarity": Rarity.UNCOMMON},

    # ---------------------------------------------------------------
    # Artifacts -- main stat: speed, energy (recharge), attack, elemental,
    # crit damage, crit rate, HP, or DEF. May roll an artifact skill.
    # ---------------------------------------------------------------
    {"name": "Band of Fortune", "item_type": ItemType.ARTIFACT, "slot": EquipmentSlot.ARTIFACT,
     "main_stat": "crit_rate", "base_main_stat_value": 6,
     "flavor_text": "Said to guide its wearer toward better fortune.",
     "min_rarity": Rarity.RARE, "max_rarity": Rarity.EPIC},
    {"name": "Cascade Core Shard", "item_type": ItemType.ARTIFACT, "slot": EquipmentSlot.ARTIFACT,
     "main_stat": "elemental", "base_main_stat_value": 10,
     "flavor_text": "A fragment of the Cascade itself, still faintly pulsing.",
     "min_rarity": Rarity.RARE, "max_rarity": Rarity.EPIC},
    {"name": "Kinetic Battery", "item_type": ItemType.ARTIFACT, "slot": EquipmentSlot.ARTIFACT,
     "main_stat": "recharge", "base_main_stat_value": 4,
     "flavor_text": "Stores momentum and releases it as raw energy.",
     "min_rarity": Rarity.UNCOMMON, "max_rarity": Rarity.RARE},
    {"name": "Wanderer's Compass", "item_type": ItemType.ARTIFACT, "slot": EquipmentSlot.ARTIFACT,
     "main_stat": "speed", "base_main_stat_value": 7,
     "flavor_text": "Always points toward the fastest way forward.",
     "min_rarity": Rarity.UNCOMMON, "max_rarity": Rarity.RARE},
    {"name": "Bloodfang Talisman", "item_type": ItemType.ARTIFACT, "slot": EquipmentSlot.ARTIFACT,
     "main_stat": "attack", "base_main_stat_value": 11,
     "flavor_text": "Carved from a predator's tooth, still hungry.",
     "min_rarity": Rarity.RARE, "max_rarity": Rarity.EPIC},
    {"name": "Bulwark Idol", "item_type": ItemType.ARTIFACT, "slot": EquipmentSlot.ARTIFACT,
     "main_stat": "defense", "base_main_stat_value": 12,
     "flavor_text": "An old ward-stone, radiating quiet stubbornness.",
     "min_rarity": Rarity.RARE, "max_rarity": Rarity.EPIC},
    {"name": "Heartroot Talisman", "item_type": ItemType.ARTIFACT, "slot": EquipmentSlot.ARTIFACT,
     "main_stat": "max_hp", "base_main_stat_value": 35,
     "flavor_text": "Grown, not forged -- it beats faintly, like something alive.",
     "min_rarity": Rarity.UNCOMMON, "max_rarity": Rarity.RARE},
    {"name": "Static Coil", "item_type": ItemType.ARTIFACT, "slot": EquipmentSlot.ARTIFACT,
     "main_stat": "recharge", "base_main_stat_value": 5,
     "flavor_text": "Winds itself tighter with every basic attack, waiting to let go all at once.",
     "min_rarity": Rarity.RARE, "max_rarity": Rarity.EPIC},
    {"name": "Warden's Lantern", "item_type": ItemType.ARTIFACT, "slot": EquipmentSlot.ARTIFACT,
     "main_stat": "max_hp", "base_main_stat_value": 38,
     "flavor_text": "Casts a faint barrier of light around whoever carries it.",
     "min_rarity": Rarity.RARE, "max_rarity": Rarity.EPIC},

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
     "flavor_text": "Cheap, plentiful, and better than nothing. Most Cascade wanderers start here.",
     "min_rarity": Rarity.COMMON, "max_rarity": Rarity.UNCOMMON},
    {"name": "Club", "item_type": ItemType.WEAPON, "slot": EquipmentSlot.WEAPON,
     "main_stat": "attack", "base_main_stat_value": 8,
     "set_name": "Wood Set", "set_prefix": "Wood", "linked_ability_id": "shield_bash",
     "flavor_text": "Splintery, heavy, and effective. Nobody asks where the wood came from.",
     "min_rarity": Rarity.COMMON, "max_rarity": Rarity.UNCOMMON},

    # Iron -- generic/flexible, the reliable step up from Wood.
    {"name": "Longsword", "item_type": ItemType.WEAPON, "slot": EquipmentSlot.WEAPON,
     "main_stat": "attack", "base_main_stat_value": 9,
     "set_name": "Iron Set", "set_prefix": "Iron", "linked_ability_id": "power_strike",
     "flavor_text": "No frills. It cuts, and it doesn't break.",
     "min_rarity": Rarity.UNCOMMON, "max_rarity": Rarity.RARE},
    {"name": "Cuirass", "item_type": ItemType.ARMOR, "slot": EquipmentSlot.ARMOR,
     "main_stat": "defense", "base_main_stat_value": 9,
     "set_name": "Iron Set", "set_prefix": "Iron", "linked_ability_id": "retaliation_plating",
     "flavor_text": "Dented in a dozen places. Still standing in all of them.",
     "min_rarity": Rarity.UNCOMMON, "max_rarity": Rarity.RARE},

    # Sigma Wolf -- feral, aggressive, DPS-leaning.
    {"name": "Fang", "item_type": ItemType.WEAPON, "slot": EquipmentSlot.WEAPON,
     "main_stat": "attack", "base_main_stat_value": 10,
     "set_name": "Sigma Wolf Set", "set_prefix": "Sigma Wolf", "linked_ability_id": "berserker_rage",
     "flavor_text": "Runs with a pack of one. Answers to nobody.",
     "min_rarity": Rarity.RARE, "max_rarity": Rarity.EPIC},
    {"name": "Fangguard", "item_type": ItemType.ARMOR, "slot": EquipmentSlot.ACCESSORY,
     "main_stat": "crit_damage", "base_main_stat_value": 12,
     "set_name": "Sigma Wolf Set", "set_prefix": "Sigma Wolf", "linked_ability_id": "vampiric_edge",
     "flavor_text": "Every kill feeds the next one.",
     "min_rarity": Rarity.RARE, "max_rarity": Rarity.EPIC},

    # Crystal -- mana/elemental, caster/Amplifier-leaning.
    {"name": "Prism", "item_type": ItemType.ARTIFACT, "slot": EquipmentSlot.ARTIFACT,
     "main_stat": "elemental", "base_main_stat_value": 9,
     "set_name": "Crystal Set", "set_prefix": "Crystal", "linked_ability_id": "arcane_burst",
     "flavor_text": "Refracts more than just light.",
     "min_rarity": Rarity.RARE, "max_rarity": Rarity.EPIC},
    {"name": "Focus Lens", "item_type": ItemType.ARMOR, "slot": EquipmentSlot.ACCESSORY,
     "main_stat": "max_mana", "base_main_stat_value": 20,
     "set_name": "Crystal Set", "set_prefix": "Crystal", "linked_ability_id": "arcane_battery",
     "flavor_text": "Hums faintly, always drawing in a little more than it gives off.",
     "min_rarity": Rarity.RARE, "max_rarity": Rarity.EPIC},

    # Xendium -- lava/fire, aggressive elemental weapon.
    {"name": "Cinderblade", "item_type": ItemType.WEAPON, "slot": EquipmentSlot.WEAPON,
     "main_stat": "elemental", "base_main_stat_value": 10,
     "set_name": "Xendium Set", "set_prefix": "Xendium", "linked_ability_id": "flame_strike",
     "flavor_text": "Forged in Hotlands magma. Never quite cools down.",
     "min_rarity": Rarity.EPIC, "max_rarity": Rarity.LEGENDARY},
    {"name": "Slagplate", "item_type": ItemType.ARMOR, "slot": EquipmentSlot.ARMOR,
     "main_stat": "defense", "base_main_stat_value": 8,
     "set_name": "Xendium Set", "set_prefix": "Xendium", "linked_ability_id": "iron_skin",
     "flavor_text": "Cooled just enough to wear. Just barely.",
     "min_rarity": Rarity.EPIC, "max_rarity": Rarity.LEGENDARY},

    # Permafrost -- ice/defense, tank/Sustain-leaning.
    {"name": "Plate", "item_type": ItemType.ARMOR, "slot": EquipmentSlot.ARMOR,
     "main_stat": "defense", "base_main_stat_value": 8,
     "set_name": "Permafrost Set", "set_prefix": "Permafrost", "linked_ability_id": "thornmail",
     "flavor_text": "Frozen solid centuries ago. Still holds an edge -- and a grudge.",
     "min_rarity": Rarity.EPIC, "max_rarity": Rarity.LEGENDARY},
    {"name": "Frostbrand", "item_type": ItemType.WEAPON, "slot": EquipmentSlot.WEAPON,
     "main_stat": "elemental", "base_main_stat_value": 9,
     "set_name": "Permafrost Set", "set_prefix": "Permafrost", "linked_ability_id": "frost_lance",
     "flavor_text": "Draws the warmth out of anything it touches.",
     "min_rarity": Rarity.EPIC, "max_rarity": Rarity.LEGENDARY},

    # Hi-Tech -- crit/precision, Support DPS-leaning.
    {"name": "Visor", "item_type": ItemType.ARMOR, "slot": EquipmentSlot.ACCESSORY,
     "main_stat": "crit_rate", "base_main_stat_value": 5,
     "set_name": "Hi-Tech Set", "set_prefix": "Hi-Tech", "linked_ability_id": "support_matrix",
     "flavor_text": "Scavenged, patched, and somehow still calibrating -- for the whole squad, not just its wearer.",
     "min_rarity": Rarity.LEGENDARY, "max_rarity": Rarity.MYTHIC},
    {"name": "Diagnostic Core", "item_type": ItemType.ARTIFACT, "slot": EquipmentSlot.ARTIFACT,
     "main_stat": "elemental", "base_main_stat_value": 9,
     "set_name": "Hi-Tech Set", "set_prefix": "Hi-Tech", "linked_ability_id": "system_purge",
     "flavor_text": "Finds every gap in an enemy's armor and reports back instantly.",
     "min_rarity": Rarity.LEGENDARY, "max_rarity": Rarity.MYTHIC},

    # Error Code -- glitchy, chaotic/flexible, recharge-leaning.
    {"name": "Fragment", "item_type": ItemType.ARMOR, "slot": EquipmentSlot.ACCESSORY,
     "main_stat": "recharge", "base_main_stat_value": 4,
     "set_name": "Error Code Set", "set_prefix": "Error Code", "linked_ability_id": "arcane_battery",
     "flavor_text": "It shouldn't work. It works anyway.",
     "min_rarity": Rarity.LEGENDARY, "max_rarity": Rarity.MYTHIC},
    {"name": "Corrupted Drive", "item_type": ItemType.ARTIFACT, "slot": EquipmentSlot.ARTIFACT,
     "main_stat": "elemental", "base_main_stat_value": 9,
     "set_name": "Error Code Set", "set_prefix": "Error Code", "linked_ability_id": "emp_burst",
     "flavor_text": "Whatever it corrupts on the way in, it corrupts twice as hard on the way out.",
     "min_rarity": Rarity.LEGENDARY, "max_rarity": Rarity.MYTHIC},

    # Voidwalker -- high-end elemental artifact.
    {"name": "Rift Shard", "item_type": ItemType.ARTIFACT, "slot": EquipmentSlot.ARTIFACT,
     "main_stat": "elemental", "base_main_stat_value": 11,
     "set_name": "Voidwalker Set", "set_prefix": "Voidwalker", "linked_ability_id": "void_grasp",
     "flavor_text": "Colder than Permafrost. Emptier than anything.",
     "min_rarity": Rarity.MYTHIC, "max_rarity": Rarity.DIVINE},
    {"name": "Abyssal Plate", "item_type": ItemType.ARMOR, "slot": EquipmentSlot.ARMOR,
     "main_stat": "defense", "base_main_stat_value": 10,
     "set_name": "Voidwalker Set", "set_prefix": "Voidwalker", "linked_ability_id": "undying_will",
     "flavor_text": "The void doesn't let go easily -- apparently that cuts both ways.",
     "min_rarity": Rarity.MYTHIC, "max_rarity": Rarity.DIVINE},

    # Entropic -- high-end, crit damage / chaos-leaning.
    {"name": "Husk", "item_type": ItemType.ARTIFACT, "slot": EquipmentSlot.ARTIFACT,
     "main_stat": "crit_damage", "base_main_stat_value": 14,
     "set_name": "Entropic Set", "set_prefix": "Entropic", "linked_ability_id": "soul_siphon",
     "flavor_text": "Falls apart a little more every time it's used. Somehow that's the point.",
     "min_rarity": Rarity.MYTHIC, "max_rarity": Rarity.DIVINE},
    {"name": "Decay Band", "item_type": ItemType.ARMOR, "slot": EquipmentSlot.ACCESSORY,
     "main_stat": "crit_rate", "base_main_stat_value": 5,
     "set_name": "Entropic Set", "set_prefix": "Entropic", "linked_ability_id": "executioner",
     "flavor_text": "Finds the weak point in everything, including itself.",
     "min_rarity": Rarity.MYTHIC, "max_rarity": Rarity.DIVINE},

    # Refense -- Refender's philosophy, balance of offense/defense, Sustain-leaning.
    {"name": "Bulwark", "item_type": ItemType.ARMOR, "slot": EquipmentSlot.ARMOR,
     "main_stat": "defense", "base_main_stat_value": 9,
     "set_name": "Refense Set", "set_prefix": "Refense", "linked_ability_id": "second_wind",
     "flavor_text": "Neither sword nor shield alone. Refender would approve.",
     "min_rarity": Rarity.MYTHIC, "max_rarity": Rarity.DIVINE},
    {"name": "Refense Core", "item_type": ItemType.ARTIFACT, "slot": EquipmentSlot.ARTIFACT,
     "main_stat": "max_hp", "base_main_stat_value": 30,
     "set_name": "Refense Set", "set_prefix": "Refense", "linked_ability_id": "combat_medic",
     "flavor_text": "Balance isn't just personal -- Refender's teachings hold the whole line together.",
     "min_rarity": Rarity.MYTHIC, "max_rarity": Rarity.DIVINE},

    # Aegis -- shield-kit showcase set, tanky/Sustain-leaning. Both pieces
    # are new-content additions built around Combatant.shield (see
    # bot/game/combat/combatant.py and bot/game/combat/effects.py) rather
    # than heals or flat mitigation.
    {"name": "Barrier Blade", "item_type": ItemType.WEAPON, "slot": EquipmentSlot.WEAPON,
     "main_stat": "defense", "base_main_stat_value": 10,
     "set_name": "Aegis Set", "set_prefix": "Aegis", "linked_ability_id": "guard_splitter",
     "flavor_text": "Less a sword than a promise: whatever gets past this doesn't get far.",
     "min_rarity": Rarity.EPIC, "max_rarity": Rarity.LEGENDARY},
    {"name": "Shellcasing", "item_type": ItemType.ARMOR, "slot": EquipmentSlot.ARMOR,
     "main_stat": "defense", "base_main_stat_value": 9,
     "set_name": "Aegis Set", "set_prefix": "Aegis", "linked_ability_id": "capacitor_shell",
     "flavor_text": "Hums faintly between hits, rebuilding whatever it just lost.",
     "min_rarity": Rarity.EPIC, "max_rarity": Rarity.LEGENDARY},

    # Vantage -- Support DPS role-shift showcase set: both pieces use the
    # new AOE-plus-sometimes-a-debuff kit pieces (see
    # bot/game/combat/effects.py's aoe_damage_chance_debuff /
    # aoe_damage_chance_resource_drain) introduced when the class moved
    # away from single-target burst.
    {"name": "Longrifle", "item_type": ItemType.WEAPON, "slot": EquipmentSlot.WEAPON,
     "main_stat": "attack", "base_main_stat_value": 10,
     "set_name": "Vantage Set", "set_prefix": "Vantage", "linked_ability_id": "crossfire_salvo",
     "flavor_text": "Built for one shooter to hold a whole line under fire at once.",
     "min_rarity": Rarity.EPIC, "max_rarity": Rarity.LEGENDARY},
    {"name": "Scatterlink Core", "item_type": ItemType.ARTIFACT, "slot": EquipmentSlot.ARTIFACT,
     "main_stat": "elemental", "base_main_stat_value": 9,
     "set_name": "Vantage Set", "set_prefix": "Vantage", "linked_ability_id": "jamming_array",
     "flavor_text": "Splits its signal across every hostile frequency it can find.",
     "min_rarity": Rarity.EPIC, "max_rarity": Rarity.LEGENDARY},

    # Fieldwork -- ally-support showcase set: both pieces cover kit pieces
    # that used to exist only on character ultimates/passives (Sustain's
    # team_heal_percent_max_hp, Kotori's aura_team_regen_self_sacrifice),
    # now obtainable as gear.
    {"name": "Reservoir Core", "item_type": ItemType.ARTIFACT, "slot": EquipmentSlot.ARTIFACT,
     "main_stat": "max_hp", "base_main_stat_value": 32,
     "set_name": "Fieldwork Set", "set_prefix": "Fieldwork", "linked_ability_id": "wellspring_surge",
     "flavor_text": "Holds more than it needs, just in case someone else runs dry first.",
     "min_rarity": Rarity.LEGENDARY, "max_rarity": Rarity.MYTHIC},
    {"name": "Tourniquet Charm", "item_type": ItemType.ARMOR, "slot": EquipmentSlot.ACCESSORY,
     "main_stat": "max_hp", "base_main_stat_value": 28,
     "set_name": "Fieldwork Set", "set_prefix": "Fieldwork", "linked_ability_id": "bloodwell_charm",
     "flavor_text": "Every turn it takes a little, so someone else can keep a little more.",
     "min_rarity": Rarity.LEGENDARY, "max_rarity": Rarity.MYTHIC},

    # "500 Billian Gem Giveaway" -- ultra rare joke set. The misspelling of
    # "Billion" is intentional; the creator, a silly man named Thedoggyp,
    # would not have it any other way.
    {"name": "Gem", "item_type": ItemType.ARTIFACT, "slot": EquipmentSlot.ARTIFACT,
     "main_stat": "crit_rate", "base_main_stat_value": 13,
     "set_name": "500 Billian Gem Giveaway", "set_prefix": "Billian",
     "linked_ability_id": "starfall", "is_ultra_rare": True,
     "flavor_text": "Certificate of authenticity signed 'Thedoggyp' in crayon. Somehow still worth it.",
     "min_rarity": Rarity.DIVINE, "max_rarity": Rarity.DIVINE},
    {"name": "Coin", "item_type": ItemType.ARMOR, "slot": EquipmentSlot.ACCESSORY,
     "main_stat": "crit_damage", "base_main_stat_value": 12,
     "set_name": "500 Billian Gem Giveaway", "set_prefix": "Billian",
     "linked_ability_id": "regen_field_generator", "is_ultra_rare": True,
     "flavor_text": "Novelty currency from a giveaway nobody remembers entering. Heals the whole team anyway.",
     "min_rarity": Rarity.DIVINE, "max_rarity": Rarity.DIVINE},
]
