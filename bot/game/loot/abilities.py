"""
Catalog of abilities gear can roll. Hand-authored (like the naming pools),
not player-specific -- the loot generator picks one at random (filtered by
the item's rolled rarity AND its item_type's pool) and stamps a copy onto
the InventoryItem's active_ability / passive_ability JSON column.

Four separate pools, matching the equipment design:
  * WEAPON_SKILLS   -- active, costs mana. Rolled onto WEAPON items only.
  * ARTIFACT_SKILLS -- active, costs mana. Rolled onto ARTIFACT items only.
  * ULTIMATE_ABILITIES -- kept as a reference catalog for character kit
    design (Combat Overhaul: ultimates now come from each character's kit,
    not gear -- see CharacterTemplate.ultimate_id in character_model.py).
    No longer rolled onto items.
  * ARMOR_PASSIVES  -- passive, always-on or conditional. Rolled onto
    ARMOR/ACCESSORY items only.

`effect` is a small, structured dict rather than free code -- combat reads
`effect["kind"]` and applies matching logic (see bot/game/combat/effects.py).
New effect kinds can be added there without changing the loot generator.

There is no dodge in this game, so no ability here keys off dodging or
grants dodge chance.

Content pass (shield kit + stat-scaled hits): adds a handful of new effect
kinds -- self_shield_percent_max_hp / team_shield_percent_max_hp / shield_regen
(a flat damage-absorbing pool, see Combatant.shield in combatant.py),
damage_bonus_if_debuffed (rewards follow-up damage on an already-debuffed
target), chance_double_hit (flat chance to swing twice), and
damage_reduction_scales_with_missing_hp (mitigation that grows the lower
the wearer's own HP is) -- plus several abilities that reuse the existing
damage_multiplier/damage_and_debuff kinds with a non-attack damage_stat
(speed, defense, recharge, crit_damage) for extra mechanical variety
without needing new combat code. Each new entry below is tagged "filler"
(cheap, simple, broadly reusable -- mostly existing kinds at new numbers)
or "unique" (a new effect kind, or an existing one used in a genuinely new
way) in its comment.
"""

from __future__ import annotations

from bot.database.models.enums import Rarity

WEAPON_SKILLS: list[dict] = [
    {
        "id": "power_strike",
        "name": "Power Strike",
        "min_rarity": Rarity.COMMON,
        "resource_cost": 15,
        "resource_type": "mana",
        "cooldown": 1,
        "description": "Deal 175% ATK damage to the target.",
        "effect": {"kind": "damage_multiplier", "damage_percent": 175, "damage_stat": "attack"},
    },
    {
        "id": "shield_bash",
        "name": "Shield Bash",
        "min_rarity": Rarity.COMMON,
        "resource_cost": 10,
        "resource_type": "mana",
        "cooldown": 1,
        "description": "Deal 90% ATK damage and stun the target for 1 turn.",
        "effect": {"kind": "damage_and_stun", "damage_percent": 90, "damage_stat": "attack", "duration": 1},
    },
    {
        "id": "flame_strike",
        "name": "Flame Strike",
        "min_rarity": Rarity.UNCOMMON,
        "resource_cost": 20,
        "resource_type": "mana",
        "cooldown": 2,
        "description": "Deal 140% ELE damage and burn the target for 3 turns.",
        "effect": {"kind": "damage_and_dot", "damage_percent": 140, "damage_stat": "elemental",
                   "dot_stat": "elemental", "dot_percent": 10, "duration": 3},
    },
    {
        "id": "frost_lance",
        "name": "Frost Lance",
        "min_rarity": Rarity.RARE,
        "resource_cost": 25,
        "resource_type": "mana",
        "cooldown": 2,
        "description": "Deal 120% ELE damage and reduce the target's SPD by 20% for 2 turns.",
        "effect": {"kind": "damage_and_debuff", "damage_percent": 120, "damage_stat": "elemental",
                   "debuff_stat": "speed", "debuff_percent": -20, "duration": 2},
    },
    {
        "id": "berserker_rage",
        "name": "Berserker's Rage",
        "min_rarity": Rarity.RARE,
        "resource_cost": 30,
        "resource_type": "mana",
        "cooldown": 3,
        "description": "Gain 40% ATK for 3 turns, but lose 15% DEF.",
        "effect": {"kind": "self_buff_debuff", "buff_stat": "attack", "buff_percent": 40,
                   "debuff_stat": "defense", "debuff_percent": -15, "duration": 3},
    },
    {
        "id": "rending_cleave",
        "name": "Rending Cleave",
        "min_rarity": Rarity.EPIC,
        "resource_cost": 35,
        "resource_type": "mana",
        "cooldown": 3,
        "description": "Strike the target 3 times for 55% ATK damage each.",
        "effect": {"kind": "multi_hit", "hits": 3, "damage_percent_per_hit": 55, "damage_stat": "attack"},
    },
    {
        "id": "phoenix_dive",
        "name": "Phoenix Dive",
        "min_rarity": Rarity.LEGENDARY,
        "resource_cost": 40,
        "resource_type": "mana",
        "cooldown": 4,
        "description": "Deal 200% ATK damage; if this kills the target, restore 25% max HP.",
        "effect": {"kind": "damage_execute_heal", "damage_percent": 200, "damage_stat": "attack",
                   "heal_percent_on_kill": 25},
    },
    {
        "id": "sunder_strike",
        "name": "Sunder Strike",
        "min_rarity": Rarity.RARE,
        "resource_cost": 22,
        "resource_type": "mana",
        "cooldown": 2,
        "description": "Deal 130% ATK damage; if the target is below 30% HP, deal 220% ATK damage instead.",
        "effect": {"kind": "execute_below_threshold", "damage_percent": 130,
                   "execute_damage_percent": 220, "damage_stat": "attack",
                   "hp_threshold_percent": 30},
    },
    {
        # filler -- cheap, no-frills Common opener; a slightly stronger
        # variant of Power Strike's shape at a lower cooldown/cost for
        # more early-rarity variety.
        "id": "quickdraw_slash",
        "name": "Quickdraw Slash",
        "min_rarity": Rarity.COMMON,
        "resource_cost": 12,
        "resource_type": "mana",
        "cooldown": 1,
        "description": "Deal 150% ATK damage to the target.",
        "effect": {"kind": "damage_multiplier", "damage_percent": 150, "damage_stat": "attack"},
    },
    {
        # filler -- Sunder Strike's "cripple then hit" shape, reskinned
        # onto DEF instead of a HP-threshold check, at Uncommon.
        "id": "guard_splitter",
        "name": "Guard Splitter",
        "min_rarity": Rarity.UNCOMMON,
        "resource_cost": 18,
        "resource_type": "mana",
        "cooldown": 2,
        "description": "Deal 110% ATK damage and reduce the target's DEF by 15% for 2 turns.",
        "effect": {"kind": "damage_and_debuff", "damage_percent": 110, "damage_stat": "attack",
                   "debuff_stat": "defense", "debuff_percent": -15, "duration": 2},
    },
    {
        # unique -- reuses damage_multiplier but keys the hit off SPEED
        # instead of ATK, the first weapon skill to do so. A blade meant
        # for a fast, low-ATK build rather than a heavy hitter.
        "id": "tempest_edge",
        "name": "Tempest Edge",
        "min_rarity": Rarity.RARE,
        "resource_cost": 22,
        "resource_type": "mana",
        "cooldown": 2,
        "description": "Deal damage equal to 160% of your SPD stat to the target.",
        "effect": {"kind": "damage_multiplier", "damage_percent": 160, "damage_stat": "speed"},
    },
    {
        # unique -- new damage_bonus_if_debuffed kind: a finisher that
        # rewards going in AFTER a debuff (Frost Lance, Guard Splitter,
        # etc.) has already landed on the target.
        "id": "opportunist_strike",
        "name": "Opportunist Strike",
        "min_rarity": Rarity.RARE,
        "resource_cost": 24,
        "resource_type": "mana",
        "cooldown": 2,
        "description": "Deal 120% ATK damage, or 210% ATK damage if the target is already weakened by a debuff.",
        "effect": {"kind": "damage_bonus_if_debuffed", "damage_percent": 120,
                   "bonus_damage_percent": 90, "damage_stat": "attack"},
    },
    {
        # unique -- new aoe_damage kind (Support DPS role shift, see
        # bot/game/combat/effects.py): the first weapon skill to hit every
        # living enemy at once instead of a single target.
        "id": "sweeping_volley",
        "name": "Sweeping Volley",
        "min_rarity": Rarity.RARE,
        "resource_cost": 26,
        "resource_type": "mana",
        "cooldown": 2,
        "description": "Deal 90% ATK damage to all enemies.",
        "effect": {"kind": "aoe_damage", "damage_percent": 90, "damage_stat": "attack"},
    },
    {
        # unique -- new aoe_damage_chance_debuff kind: hits every enemy,
        # with each hit target independently rolling a chance to also be
        # debuffed -- the gear-side counterpart to the Support DPS kit
        # rework.
        "id": "crossfire_salvo",
        "name": "Crossfire Salvo",
        "min_rarity": Rarity.EPIC,
        "resource_cost": 32,
        "resource_type": "mana",
        "cooldown": 3,
        "description": "Deal 85% ATK damage to all enemies, with a 40% chance to reduce each hit target's DEF by 15% for 2 turns.",
        "effect": {"kind": "aoe_damage_chance_debuff", "damage_percent": 85, "damage_stat": "attack",
                   "debuff_chance_percent": 40, "debuff_stat": "defense", "debuff_percent": -15, "duration": 2},
    },
    {
        # unique -- new damage_and_double_debuff kind on the weapon side
        # (Axel's character kit introduced it; this is the first gear
        # item to carry it): one hit, two stat debuffs at once.
        "id": "twin_fracture_strike",
        "name": "Twin Fracture Strike",
        "min_rarity": Rarity.EPIC,
        "resource_cost": 28,
        "resource_type": "mana",
        "cooldown": 2,
        "description": "Deal 120% ATK damage and reduce the target's ATK and DEF by 15% each for 2 turns.",
        "effect": {"kind": "damage_and_double_debuff", "damage_percent": 120, "damage_stat": "attack",
                   "debuff_stat_1": "attack", "debuff_percent_1": -15,
                   "debuff_stat_2": "defense", "debuff_percent_2": -15, "duration": 2},
    },
    {
        # unique -- new chance_double_hit kind: every swing has a flat
        # chance to immediately swing again for the same damage.
        "id": "riftcutter",
        "name": "Riftcutter",
        "min_rarity": Rarity.EPIC,
        "resource_cost": 30,
        "resource_type": "mana",
        "cooldown": 3,
        "description": "Deal 130% ATK damage. 35% chance to strike again for another 130% ATK damage.",
        "effect": {"kind": "chance_double_hit", "damage_percent": 130,
                   "chance_percent": 35, "damage_stat": "attack"},
    },
    {
        # unique -- reuses aoe_damage (Support DPS role-shift kind, see
        # bot/game/combat/effects.py): the "light AoE weapon skill" a
        # couple of fast normal-tier enemies carry (bot/game/combat/
        # enemies.py's Scrap Buggy) instead of a second single-target hit.
        "id": "flurry_slash",
        "name": "Flurry Slash",
        "min_rarity": Rarity.RARE,
        "resource_cost": 20,
        "resource_type": "mana",
        "cooldown": 2,
        "description": "Deal 65% ATK damage to all enemies.",
        "effect": {"kind": "aoe_damage", "damage_percent": 65, "damage_stat": "attack"},
    },
    {
        # unique -- the heavier aoe_damage tier: the "slow, hard-hitting"
        # AoE weapon skill carried by tankier elites/bosses (bot/game/
        # combat/enemies.py's Xender Tank, Boss John's Driller Prototype).
        "id": "cleave_smash",
        "name": "Cleave Smash",
        "min_rarity": Rarity.EPIC,
        "resource_cost": 34,
        "resource_type": "mana",
        "cooldown": 3,
        "description": "Deal 120% ATK damage to all enemies.",
        "effect": {"kind": "aoe_damage", "damage_percent": 120, "damage_stat": "attack"},
    },
]

ARTIFACT_SKILLS: list[dict] = [
    {
        "id": "healing_light",
        "name": "Healing Light",
        "min_rarity": Rarity.UNCOMMON,
        "resource_cost": 20,
        "resource_type": "mana",
        "cooldown": 3,
        "description": "Restore 30% of max HP.",
        "effect": {"kind": "heal_percent_max_hp", "percent": 30},
    },
    {
        "id": "arcane_burst",
        "name": "Arcane Burst",
        "min_rarity": Rarity.COMMON,
        "resource_cost": 18,
        "resource_type": "mana",
        "cooldown": 1,
        "description": "Deal 150% ELE damage to the target.",
        "effect": {"kind": "damage_multiplier", "damage_percent": 150, "damage_stat": "elemental"},
    },
    {
        "id": "void_grasp",
        "name": "Void Grasp",
        "min_rarity": Rarity.RARE,
        "resource_cost": 26,
        "resource_type": "mana",
        "cooldown": 2,
        "description": "Deal 110% ELE damage and reduce the target's DEF by 25% for 2 turns.",
        "effect": {"kind": "damage_and_debuff", "damage_percent": 110, "damage_stat": "elemental",
                   "debuff_stat": "defense", "debuff_percent": -25, "duration": 2},
    },
    {
        "id": "empowering_ritual",
        "name": "Empowering Ritual",
        "min_rarity": Rarity.RARE,
        "resource_cost": 28,
        "resource_type": "mana",
        "cooldown": 3,
        "description": "Gain 35% ELE for 3 turns, but lose 10% DEF.",
        "effect": {"kind": "self_buff_debuff", "buff_stat": "elemental", "buff_percent": 35,
                   "debuff_stat": "defense", "debuff_percent": -10, "duration": 3},
    },
    {
        "id": "soul_siphon",
        "name": "Soul Siphon",
        "min_rarity": Rarity.EPIC,
        "resource_cost": 32,
        "resource_type": "mana",
        "cooldown": 3,
        "description": "Deal 130% ELE damage and heal for 40% of your ELE stat.",
        "effect": {"kind": "damage_and_heal_self", "damage_percent": 130, "damage_stat": "elemental",
                   "heal_stat": "elemental", "heal_percent": 40},
    },
    {
        "id": "starfall",
        "name": "Starfall",
        "min_rarity": Rarity.LEGENDARY,
        "resource_cost": 45,
        "resource_type": "mana",
        "cooldown": 4,
        "description": "Deal 260% ELE damage to the target.",
        "effect": {"kind": "damage_multiplier", "damage_percent": 260, "damage_stat": "elemental"},
    },
    {
        "id": "system_purge",
        "name": "System Purge",
        "min_rarity": Rarity.EPIC,
        "resource_cost": 30,
        "resource_type": "mana",
        "cooldown": 3,
        "description": "Deal true damage equal to 12% of the target's max HP, ignoring defense.",
        "effect": {"kind": "true_damage_percent_max_hp", "percent": 12},
    },
    {
        "id": "emp_burst",
        "name": "EMP Burst",
        "min_rarity": Rarity.RARE,
        "resource_cost": 24,
        "resource_type": "mana",
        "cooldown": 3,
        "description": "Deal 100% ELE damage and drain 20 energy and 15 mana from the target.",
        "effect": {"kind": "damage_and_resource_drain", "damage_percent": 100, "damage_stat": "elemental",
                   "energy_drain": 20, "mana_drain": 15},
    },
    {
        "id": "overclock_repair",
        "name": "Overclock Repair",
        "min_rarity": Rarity.EPIC,
        "resource_cost": 28,
        "resource_type": "mana",
        "cooldown": 4,
        "description": "Clear all of your own negative effects and restore 25% max HP.",
        "effect": {"kind": "cleanse_self_and_heal", "percent": 25},
    },
    {
        "id": "combat_medic",
        "name": "Combat Medic",
        "min_rarity": Rarity.UNCOMMON,
        "resource_cost": 22,
        "resource_type": "mana",
        "cooldown": 2,
        "description": "Heal whoever on your side (including you) is lowest on HP% for 30% of their max HP.",
        "effect": {"kind": "heal_lowest_ally_percent_max_hp", "percent": 30},
    },
    {
        "id": "rousing_signal",
        "name": "Rousing Signal",
        "min_rarity": Rarity.RARE,
        "resource_cost": 26,
        "resource_type": "mana",
        "cooldown": 3,
        "description": "Grant your whole side 25% ATK for 3 turns.",
        "effect": {"kind": "team_buff", "buff_stat": "attack", "buff_percent": 25, "duration": 3},
    },
    {
        "id": "static_field",
        "name": "Static Field",
        "min_rarity": Rarity.RARE,
        "resource_cost": 26,
        "resource_type": "mana",
        "cooldown": 3,
        "description": "Reduce the DEF of every enemy by 20% for 2 turns.",
        "effect": {"kind": "team_debuff", "debuff_stat": "defense", "debuff_percent": -20, "duration": 2},
    },
    {
        "id": "power_transfer",
        "name": "Power Transfer",
        "min_rarity": Rarity.EPIC,
        "resource_cost": 30,
        "resource_type": "mana",
        "cooldown": 4,
        "description": "Instantly restore 15 energy and 20 mana to your whole side.",
        "effect": {"kind": "team_resource_restore", "energy_amount": 15, "mana_amount": 20},
    },
    {
        "id": "regenerative_field",
        "name": "Regenerative Field",
        "min_rarity": Rarity.EPIC,
        "resource_cost": 32,
        "resource_type": "mana",
        "cooldown": 5,
        "description": "Your whole side regenerates 8% max HP at the start of each of their turns for 3 turns.",
        "effect": {"kind": "team_regen_over_time", "percent_max_hp_per_turn": 8, "duration": 3},
    },
    {
        # filler -- cheap Common-tier bolt, the artifact-side equivalent
        # of Quickdraw Slash for early ELE rolls.
        "id": "overcharged_bolt",
        "name": "Overcharged Bolt",
        "min_rarity": Rarity.COMMON,
        "resource_cost": 14,
        "resource_type": "mana",
        "cooldown": 1,
        "description": "Deal 130% ELE damage to the target.",
        "effect": {"kind": "damage_multiplier", "damage_percent": 130, "damage_stat": "elemental"},
    },
    {
        # unique -- reuses damage_multiplier keyed off RECHARGE instead of
        # ELE: literally channels stored energy into the hit, so it hits
        # hardest on a high-Recharge support/caster build.
        "id": "kinetic_feedback",
        "name": "Kinetic Feedback",
        "min_rarity": Rarity.RARE,
        "resource_cost": 24,
        "resource_type": "mana",
        "cooldown": 2,
        "description": "Discharge stored energy, dealing damage equal to 900% of your Recharge stat.",
        "effect": {"kind": "damage_multiplier", "damage_percent": 900, "damage_stat": "recharge"},
    },
    {
        # unique -- the artifact-side damage_bonus_if_debuffed, at ELE
        # instead of ATK, for caster builds that want the same
        # punish-a-weakened-target payoff as Opportunist Strike.
        "id": "weakpoint_scanner",
        "name": "Weakpoint Scanner",
        "min_rarity": Rarity.RARE,
        "resource_cost": 26,
        "resource_type": "mana",
        "cooldown": 2,
        "description": "Deal 110% ELE damage, or 195% ELE damage if the target is already weakened by a debuff.",
        "effect": {"kind": "damage_bonus_if_debuffed", "damage_percent": 110,
                   "bonus_damage_percent": 85, "damage_stat": "elemental"},
    },
    {
        # unique -- new self_shield_percent_max_hp kind: a burst of
        # absorb shield instead of a heal, for soaking the next few hits
        # rather than topping HP back up.
        "id": "ionic_ward",
        "name": "Ionic Ward",
        "min_rarity": Rarity.EPIC,
        "resource_cost": 28,
        "resource_type": "mana",
        "cooldown": 4,
        "description": "Raise a shield that absorbs damage equal to 35% of your max HP.",
        "effect": {"kind": "self_shield_percent_max_hp", "percent": 35},
    },
    {
        # unique -- team version of Ionic Ward; a Support/Amplifier-style
        # burst of shield across the whole side at once.
        "id": "aegis_broadcast",
        "name": "Aegis Broadcast",
        "min_rarity": Rarity.LEGENDARY,
        "resource_cost": 38,
        "resource_type": "mana",
        "cooldown": 5,
        "description": "Shield your whole side, each member absorbing damage equal to 25% of their own max HP.",
        "effect": {"kind": "team_shield_percent_max_hp", "percent": 25},
    },
    {
        # unique -- the artifact-side aoe_damage_chance_debuff (Support
        # DPS role shift), at ELE instead of ATK for caster builds.
        "id": "fracture_field",
        "name": "Fracture Field",
        "min_rarity": Rarity.EPIC,
        "resource_cost": 30,
        "resource_type": "mana",
        "cooldown": 3,
        "description": "Deal 80% ELE damage to all enemies, with a 40% chance to reduce each hit target's SPD by 18% for 2 turns.",
        "effect": {"kind": "aoe_damage_chance_debuff", "damage_percent": 80, "damage_stat": "elemental",
                   "debuff_chance_percent": 40, "debuff_stat": "speed", "debuff_percent": -18, "duration": 2},
    },
    {
        # unique -- new aoe_damage_chance_resource_drain kind: Nyrvite's
        # signal-jamming take on the AOE-plus-sometimes-more shape, now
        # available as a rollable artifact skill.
        "id": "jamming_array",
        "name": "Jamming Array",
        "min_rarity": Rarity.LEGENDARY,
        "resource_cost": 34,
        "resource_type": "mana",
        "cooldown": 4,
        "description": "Deal 75% ELE damage to all enemies, with a 45% chance to drain 12 energy and 12 SP from each hit target.",
        "effect": {"kind": "aoe_damage_chance_resource_drain", "damage_percent": 75, "damage_stat": "elemental",
                   "drain_chance_percent": 45, "energy_drain": 12, "mana_drain": 12},
    },
    {
        # unique -- new team_heal_percent_max_hp kind on gear (previously
        # only on Sustain character ultimates): a burst heal for the
        # whole side from an artifact skill instead of a 50-energy ult.
        "id": "wellspring_surge",
        "name": "Wellspring Surge",
        "min_rarity": Rarity.LEGENDARY,
        "resource_cost": 40,
        "resource_type": "mana",
        "cooldown": 5,
        "description": "Heal your whole side for 30% of each member's own max HP.",
        "effect": {"kind": "team_heal_percent_max_hp", "percent": 30},
    },
    {
        # unique -- new ally_buff kind on gear: buffs whichever ally needs
        # it most (never the caster), instead of the whole side at once
        # like Rousing Signal.
        "id": "focused_support_beam",
        "name": "Focused Support Beam",
        "min_rarity": Rarity.RARE,
        "resource_cost": 22,
        "resource_type": "mana",
        "cooldown": 2,
        "description": "Boost whichever ally needs it most ATK by 25% for 2 turns.",
        "effect": {"kind": "ally_buff", "buff_stat": "attack", "buff_percent": 25, "duration": 2},
    },
    {
        # unique -- new restore_resource_to_lowest_ally kind on gear: tops
        # off whichever ally is running lowest on energy/mana, instead of
        # the whole side at once like Power Transfer.
        "id": "emergency_relay",
        "name": "Emergency Relay",
        "min_rarity": Rarity.RARE,
        "resource_cost": 20,
        "resource_type": "mana",
        "cooldown": 2,
        "description": "Instantly restore 18 energy and 22 SP to whichever ally needs it most.",
        "effect": {"kind": "restore_resource_to_lowest_ally", "energy_amount": 18, "mana_amount": 22},
    },
    {
        # unique -- new cleanse_ally_and_heal kind on gear: the ally-
        # facing counterpart to Overclock Repair's self-cleanse-and-heal.
        "id": "purge_beacon",
        "name": "Purge Beacon",
        "min_rarity": Rarity.EPIC,
        "resource_cost": 26,
        "resource_type": "mana",
        "cooldown": 3,
        "description": "Cleanse all negative effects from whichever ally is lowest on HP% and heal them for 25% of their max HP.",
        "effect": {"kind": "cleanse_ally_and_heal", "heal_percent": 25},
    },
    {
        # unique -- new team_resource_drain kind on gear: the opposing-
        # side counterpart to Power Transfer, draining flat energy/mana
        # from every living enemy at once.
        "id": "null_field_projector",
        "name": "Null Field Projector",
        "min_rarity": Rarity.EPIC,
        "resource_cost": 28,
        "resource_type": "mana",
        "cooldown": 3,
        "description": "Drain 20 energy and 20 SP from every enemy at once.",
        "effect": {"kind": "team_resource_drain", "energy_amount": 20, "mana_amount": 20},
    },
    {
        # unique -- new sacrifice_hp_heal_lowest_ally_percent_max_hp kind
        # on gear (Blood-Sustain kit piece, previously only on Kotori's
        # character skill): pays with the caster's own HP instead of extra
        # mana to mend whichever ally needs it most.
        "id": "vitality_offering",
        "name": "Vitality Offering",
        "min_rarity": Rarity.RARE,
        "resource_cost": 20,
        "resource_type": "mana",
        "cooldown": 1,
        "description": "Sacrifice 10% of your own max HP to heal whichever ally needs it most for 25% of their max HP.",
        "effect": {"kind": "sacrifice_hp_heal_lowest_ally_percent_max_hp", "self_cost_percent": 10, "heal_percent": 25},
    },
    {
        # unique -- new sacrifice_hp_heal_team_percent_max_hp kind on gear
        # (previously only Kotori's ultimate): a repeatable, mana-gated
        # version of the same Blood-Sustain team heal at smaller numbers.
        "id": "sacrificial_aegis",
        "name": "Sacrificial Aegis",
        "min_rarity": Rarity.LEGENDARY,
        "resource_cost": 30,
        "resource_type": "mana",
        "cooldown": 4,
        "description": "Sacrifice 15% of your own max HP to heal your whole side for 20% of each member's max HP.",
        "effect": {"kind": "sacrifice_hp_heal_team_percent_max_hp", "self_cost_percent": 15, "heal_percent": 20},
    },
    {
        # unique -- reuses aoe_damage (Support DPS role-shift kind): the
        # "light AoE artifact skill" a fast normal-tier enemy carries
        # (bot/game/combat/enemies.py's Voidcrest Skitterer) instead of a
        # second single-target hit.
        "id": "arc_lightning",
        "name": "Arc Lightning",
        "min_rarity": Rarity.RARE,
        "resource_cost": 22,
        "resource_type": "mana",
        "cooldown": 2,
        "description": "Deal 65% ELE damage to all enemies.",
        "effect": {"kind": "aoe_damage", "damage_percent": 65, "damage_stat": "elemental"},
    },
    {
        # unique -- the heavier aoe_damage tier on the artifact side: the
        # "heavy AoE artifact skill" carried by endgame bosses (bot/game/
        # combat/enemies.py's Gatekeeper).
        "id": "meteor_shower",
        "name": "Meteor Shower",
        "min_rarity": Rarity.LEGENDARY,
        "resource_cost": 36,
        "resource_type": "mana",
        "cooldown": 4,
        "description": "Deal 110% ELE damage to all enemies.",
        "effect": {"kind": "aoe_damage", "damage_percent": 110, "damage_stat": "elemental"},
    },
]

ULTIMATE_ABILITIES: list[dict] = [
    {
        "id": "meteor_ultimate",
        "name": "Meteor",
        "min_rarity": Rarity.UNCOMMON,
        "resource_cost": 50,
        "resource_type": "energy",
        "cooldown": 0,
        "description": "Unleash a meteor for 320% ELE damage.",
        "effect": {"kind": "damage_multiplier", "damage_percent": 320, "damage_stat": "elemental"},
    },
    {
        "id": "executioners_reckoning",
        "name": "Executioner's Reckoning",
        "min_rarity": Rarity.RARE,
        "resource_cost": 50,
        "resource_type": "energy",
        "cooldown": 0,
        "description": "Deal 280% ATK damage; if this kills the target, restore 30% max HP.",
        "effect": {"kind": "damage_execute_heal", "damage_percent": 280, "damage_stat": "attack",
                   "heal_percent_on_kill": 30},
    },
    {
        "id": "phoenix_rebirth",
        "name": "Phoenix Rebirth",
        "min_rarity": Rarity.RARE,
        "resource_cost": 50,
        "resource_type": "energy",
        "cooldown": 0,
        "description": "Restore 50% max HP and gain 30% ATK for 3 turns.",
        "effect": {"kind": "heal_and_self_buff", "heal_percent": 50, "buff_stat": "attack",
                   "buff_percent": 30, "duration": 3},
    },
    {
        "id": "cascade_barrage",
        "name": "Cascade Barrage",
        "min_rarity": Rarity.EPIC,
        "resource_cost": 50,
        "resource_type": "energy",
        "cooldown": 0,
        "description": "Strike the target 4 times for 70% ATK damage each.",
        "effect": {"kind": "multi_hit", "hits": 4, "damage_percent_per_hit": 70, "damage_stat": "attack"},
    },
    {
        "id": "voidstorm",
        "name": "Voidstorm",
        "min_rarity": Rarity.LEGENDARY,
        "resource_cost": 50,
        "resource_type": "energy",
        "cooldown": 0,
        "description": "Deal 420% ELE damage and reduce the target's DEF by 30% for 2 turns.",
        "effect": {"kind": "damage_and_debuff", "damage_percent": 420, "damage_stat": "elemental",
                   "debuff_stat": "defense", "debuff_percent": -30, "duration": 2},
    },
    {
        "id": "ascension",
        "name": "Ascension",
        "min_rarity": Rarity.MYTHIC,
        "resource_cost": 50,
        "resource_type": "energy",
        "cooldown": 0,
        "description": "Deal 500% ATK damage to the target.",
        "effect": {"kind": "damage_multiplier", "damage_percent": 500, "damage_stat": "attack"},
    },
    {
        "id": "cataclysm",
        "name": "Cataclysm",
        "min_rarity": Rarity.EPIC,
        "resource_cost": 50,
        "resource_type": "energy",
        "cooldown": 0,
        "description": "Deal 150% ELE damage, increased by up to 150% more the lower the target's HP is.",
        "effect": {"kind": "damage_scales_with_missing_hp", "base_damage_percent": 150,
                   "bonus_damage_percent_at_zero_hp": 150, "damage_stat": "elemental"},
    },
    {
        # filler -- Phoenix Rebirth's shape at a lower rarity gate and
        # slightly smaller numbers, for more Uncommon/Rare-tier ultimate
        # variety on enemies that shouldn't have the full 50%/30% version.
        "id": "last_stand",
        "name": "Last Stand",
        "min_rarity": Rarity.UNCOMMON,
        "resource_cost": 50,
        "resource_type": "energy",
        "cooldown": 0,
        "description": "Restore 35% max HP and gain 20% ATK for 3 turns.",
        "effect": {"kind": "heal_and_self_buff", "heal_percent": 35, "buff_stat": "attack",
                   "buff_percent": 20, "duration": 3},
    },
    {
        # unique -- reuses damage_multiplier keyed off SPEED at ultimate
        # scale, the signature-move counterpart to Tempest Edge; a huge
        # payoff for a build that's stacked Speed instead of ATK/ELE.
        "id": "gale_ascendant",
        "name": "Gale Ascendant",
        "min_rarity": Rarity.RARE,
        "resource_cost": 50,
        "resource_type": "energy",
        "cooldown": 0,
        "description": "Deal damage equal to 700% of your SPD stat to the target.",
        "effect": {"kind": "damage_multiplier", "damage_percent": 700, "damage_stat": "speed"},
    },
    {
        # unique -- ultimate-scale damage_bonus_if_debuffed: a true
        # finishing move meant to come down AFTER a debuff (from a
        # teammate, an earlier skill, anything) has already landed.
        "id": "null_strike",
        "name": "Null Strike",
        "min_rarity": Rarity.EPIC,
        "resource_cost": 50,
        "resource_type": "energy",
        "cooldown": 0,
        "description": "Deal 240% ATK damage, or 440% ATK damage if the target is already weakened by a debuff.",
        "effect": {"kind": "damage_bonus_if_debuffed", "damage_percent": 240,
                   "bonus_damage_percent": 200, "damage_stat": "attack"},
    },
    {
        # unique -- ultimate-scale team_shield_percent_max_hp: a
        # Sustain/tank signature move that soaks incoming damage across
        # the whole side rather than healing it back afterward.
        "id": "aegis_protocol",
        "name": "Aegis Protocol",
        "min_rarity": Rarity.LEGENDARY,
        "resource_cost": 50,
        "resource_type": "energy",
        "cooldown": 0,
        "description": "Shield your whole side, each member absorbing damage equal to 45% of their own max HP.",
        "effect": {"kind": "team_shield_percent_max_hp", "percent": 45},
    },
    {
        # unique -- ultimate-scale aoe_damage: the "lighter AoE ultimate"
        # paired with a fast, multi-action boss (bot/game/combat/
        # enemies.py's XG-23 Heavy Drone) -- hits everyone, but for less
        # than World Ender below, matching "fast = frequent + lighter."
        "id": "storm_of_blades",
        "name": "Storm of Blades",
        "min_rarity": Rarity.RARE,
        "resource_cost": 50,
        "resource_type": "energy",
        "cooldown": 0,
        "description": "Deal 220% ATK damage to all enemies.",
        "effect": {"kind": "aoe_damage", "damage_percent": 220, "damage_stat": "attack"},
    },
    {
        # unique -- the roster's signature hard-hitting AoE ultimate,
        # reserved for final bosses (bot/game/combat/enemies.py's Void
        # Hydra) -- an "everyone's in danger" capstone hit.
        "id": "world_ender",
        "name": "World Ender",
        "min_rarity": Rarity.MYTHIC,
        "resource_cost": 50,
        "resource_type": "energy",
        "cooldown": 0,
        "description": "Deal 300% ELE damage to all enemies.",
        "effect": {"kind": "aoe_damage", "damage_percent": 300, "damage_stat": "elemental"},
    },
]

ARMOR_PASSIVES: list[dict] = [
    {
        "id": "iron_skin",
        "name": "Iron Skin",
        "min_rarity": Rarity.COMMON,
        "trigger": "always",
        "description": "Reduce all incoming damage by 5%.",
        "effect": {"kind": "damage_reduction", "percent": 5},
    },
    {
        "id": "thornmail",
        "name": "Thornmail",
        "min_rarity": Rarity.UNCOMMON,
        "trigger": "always",
        "description": "Reflect 20% of damage taken back to the attacker.",
        "effect": {"kind": "damage_reflect", "percent": 20},
    },
    {
        "id": "vampiric_edge",
        "name": "Vampiric Edge",
        "min_rarity": Rarity.RARE,
        "trigger": "always",
        "description": "Heal for 10% of damage dealt on every hit.",
        "effect": {"kind": "lifesteal", "percent": 10},
    },
    {
        "id": "executioner",
        "name": "Executioner",
        "min_rarity": Rarity.RARE,
        "trigger": "on_crit",
        "description": "Critical hits deal an additional 15% damage.",
        "effect": {"kind": "crit_damage_bonus", "percent": 15},
    },
    {
        "id": "momentum",
        "name": "Momentum",
        "min_rarity": Rarity.UNCOMMON,
        "trigger": "on_turn_start",
        "description": "Gain 5% ATK, stacking up to 3 times per fight.",
        "effect": {"kind": "stacking_buff", "buff_stat": "attack", "percent_per_stack": 5,
                   "max_stacks": 3},
    },
    {
        "id": "second_wind",
        "name": "Second Wind",
        "min_rarity": Rarity.EPIC,
        "trigger": "on_low_hp",
        "description": "The first time HP drops below 25% in a fight, heal 20% of max HP.",
        "effect": {"kind": "heal_percent_max_hp", "percent": 20, "charges_per_combat": 1},
    },
    {
        "id": "soul_harvest",
        "name": "Soul Harvest",
        "min_rarity": Rarity.EPIC,
        "trigger": "on_kill",
        "description": "Restore 15% max HP and 20 mana when you defeat an enemy.",
        "effect": {"kind": "on_kill_restore", "hp_percent": 15, "mana": 20},
    },
    {
        "id": "arcane_battery",
        "name": "Arcane Battery",
        "min_rarity": Rarity.MYTHIC,
        "trigger": "on_turn_start",
        "description": "Restore 10 mana at the start of every turn.",
        "effect": {"kind": "resource_regen", "resource_type": "mana", "amount": 10},
    },
    {
        "id": "undying_will",
        "name": "Undying Will",
        "min_rarity": Rarity.DIVINE,
        "trigger": "on_low_hp",
        "description": "The first fatal hit in a fight instead leaves you at 1 HP.",
        "effect": {"kind": "prevent_death", "charges_per_combat": 1},
    },
    {
        "id": "retaliation_plating",
        "name": "Retaliation Plating",
        "min_rarity": Rarity.RARE,
        "trigger": "always",
        "description": "20% chance to stun an attacker for 1 turn whenever you take a hit.",
        "effect": {"kind": "chance_stun_attacker", "percent": 20, "duration": 1},
    },
    {
        "id": "support_matrix",
        "name": "Support Matrix",
        "min_rarity": Rarity.EPIC,
        "trigger": "on_turn_start",
        "description": "At the start of every turn, restore 5 energy and 8 mana to your whole side.",
        "effect": {"kind": "aura_team_resource_regen", "energy_amount": 5, "mana_amount": 8},
    },
    {
        "id": "regen_field_generator",
        "name": "Regen Field Generator",
        "min_rarity": Rarity.MYTHIC,
        "trigger": "on_turn_start",
        "description": "At the start of every turn, heal your whole side for 4% of their own max HP.",
        "effect": {"kind": "aura_team_regen", "percent": 4},
    },
    {
        # filler -- a cheaper, Common-tier Iron Skin variant so early-game
        # armor has more than one flat-mitigation option to roll.
        "id": "scrap_armor",
        "name": "Scrap Armor",
        "min_rarity": Rarity.COMMON,
        "trigger": "always",
        "description": "Reduce all incoming damage by 3%.",
        "effect": {"kind": "damage_reduction", "percent": 3},
    },
    {
        # filler -- Retaliation Plating's shape at a lower rarity gate and
        # a shorter stun, for more Uncommon-tier reactive-defense variety.
        "id": "static_discharge",
        "name": "Static Discharge",
        "min_rarity": Rarity.UNCOMMON,
        "trigger": "always",
        "description": "15% chance to stun an attacker for 1 turn whenever you take a hit.",
        "effect": {"kind": "chance_stun_attacker", "percent": 15, "duration": 1},
    },
    {
        # filler -- Executioner's shape at a lower rarity gate and a
        # smaller bonus, for more Uncommon-tier crit-damage variety.
        "id": "focused_lens",
        "name": "Focused Lens",
        "min_rarity": Rarity.UNCOMMON,
        "trigger": "on_crit",
        "description": "Critical hits deal an additional 8% damage.",
        "effect": {"kind": "crit_damage_bonus", "percent": 8},
    },
    {
        # unique -- new shield_regen kind: trickles a small self-shield
        # every turn instead of Iron Skin's flat percent mitigation --
        # absorbs a chunk of a hit outright rather than shaving a little
        # off every hit forever.
        "id": "capacitor_shell",
        "name": "Capacitor Shell",
        "min_rarity": Rarity.RARE,
        "trigger": "on_turn_start",
        "description": "At the start of every turn, gain a shield equal to 6% of your max HP (capped at 30%).",
        "effect": {"kind": "shield_regen", "percent": 6, "cap_percent": 30},
    },
    {
        # unique -- new damage_reduction_scales_with_missing_hp kind: a
        # "gets sturdier while hurt" passive, the mitigation counterpart
        # to Second Wind's one-time heal-at-25% -- this scales smoothly
        # instead of triggering once.
        "id": "adaptive_plating",
        "name": "Adaptive Plating",
        "min_rarity": Rarity.EPIC,
        "trigger": "always",
        "description": "Reduce incoming damage by 5%, plus up to 20% more the lower your own HP is.",
        "effect": {"kind": "damage_reduction_scales_with_missing_hp", "base_percent": 5,
                   "bonus_percent_at_zero_hp": 20},
    },
    {
        # unique -- Cycle turn order rework: new bonus_actions_per_cycle
        # kind. Grants an extra action every combat cycle (see
        # bot/game/combat/battle.py) on top of the wearer's normal one --
        # generic and reusable the same way enemy templates configure
        # "actions_per_cycle" for an elite/boss that should act more than
        # once per cycle. Gated to DIVINE: acting twice as often as
        # everything else is one of the strongest things a passive can do.
        "id": "temporal_capacitor",
        "name": "Temporal Capacitor",
        "min_rarity": Rarity.DIVINE,
        "trigger": "always",
        "description": "Act one additional time every combat cycle.",
        "effect": {"kind": "bonus_actions_per_cycle", "count": 1},
    },
    {
        # unique -- new aura_team_regen_self_sacrifice kind on gear
        # (previously only Kotori's character passive): every turn, pays
        # for the team-wide regen with a slice of the wearer's own max HP
        # instead of it being free like Regen Field Generator.
        "id": "bloodwell_charm",
        "name": "Bloodwell Charm",
        "min_rarity": Rarity.LEGENDARY,
        "trigger": "on_turn_start",
        "description": "At the start of every turn, sacrifices 2% of your own max HP to heal the rest of your side for 3% of their own max HP each.",
        "effect": {"kind": "aura_team_regen_self_sacrifice", "self_cost_percent": 2, "percent": 3},
    },
]


def abilities_for_rarity(pool: list[dict], rarity: Rarity) -> list[dict]:
    """Every ability in `pool` unlocked at `rarity` or below."""
    return [a for a in pool if a["min_rarity"].sort_order <= rarity.sort_order]


def get_ability_by_id(pool: list[dict], ability_id: str) -> dict:
    """Look up a single ability by id, e.g. for assigning enemy movesets."""
    for ability in pool:
        if ability["id"] == ability_id:
            return ability
    raise KeyError(f"No ability with id {ability_id!r}")
