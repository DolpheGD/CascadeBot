"""
Bulk roster expansion: forty-four enemies across every region.

WHAT THIS IS, AND WHAT THE PREVIOUS TWO BATCHES WERE NOT. The specialist
and conclave passes were each built around a mechanic nobody had used --
narrow, pointed, a dozen templates between them. This is the opposite
brief: VOLUME. The roster is what a player actually sees, and by the time
someone has walked forty-five rooms in a region they have met most of its
pool several times over. Repetition is a content problem that no amount
of clever mechanics fixes; sometimes a region just needs more bodies.

So these are mostly ordinary, on purpose. They use effect kinds the
engine already has and that enemies already use, in combinations and at
stat lines that vary. A drone that hits twice, a soldier that debuffs
defence, a beast that bleeds you -- the connective tissue a roster needs
between its set pieces.

HOW THEY WERE SIZED. Stat lines are anchored to the MEDIAN of each
region's existing pool, measured rather than guessed:

    region                combat atk/hp        elite atk/hp
    Glacier 15                 7 / 48              13 / 172
    The Wastelands            12 / 52              17 / 175
    The Hotlands              13 / 60              18 / 175
    Voidcrest Desert          13 / 58              20 / 192
    The Voidlands             15 / 74              21 / 175
    Abyssnia                  16 / 74              24 / 180
    Entrospire Deepworks      20 / 96              28 / 210

Each new template sits within roughly a quarter of its region's median,
so this adds variety without moving any region's difficulty. That is the
whole point of a volume pass -- if the numbers drift, it stops being more
content and becomes a balance change nobody asked for.

WHERE THEY WENT. Weighted at the thin pools, which after the previous
passes were Glacier 15 (23 combat / 12 elite), The Wastelands (29/13) and
Entrospire Deepworks (17/13). Glacier in particular is the region every
player spends their first hours in and had the smallest pool in the game.

THE HELPER. `_e()` builds the template dict. Forty-four hand-written
literals is forty-four chances to typo a key that no check would catch
because it would simply be ignored -- the helper makes the shape
impossible to get wrong and keeps each entry to the parts that differ.
"""

from __future__ import annotations

GLACIER = "Glacier 15"
WASTELANDS = "The Wastelands"
HOTLANDS = "The Hotlands"
VOIDCREST = "Voidcrest Desert"
VOIDLANDS = "The Voidlands"
ABYSSNIA = "Abyssnia"
DEEPWORKS = "Entrospire Deepworks"


def _e(name, role, regions, atk, dfn, ele, spd, hp, ability, *,
       crit=5, crit_dmg=150, recharge=16, passives=None):
    """One template. Every key the engine reads, none it does not."""
    template = {
        "name": name,
        "role": role,
        "regions": list(regions),
        "base_stats": {"attack": atk, "defense": dfn, "elemental": ele,
                       "speed": spd, "max_hp": hp, "max_mana": 999,
                       "crit_rate": crit, "crit_damage": crit_dmg,
                       "recharge": recharge},
        "level_scale_percent": 4,
        "active_abilities": [ability],
    }
    if passives:
        template["passive_abilities"] = passives
    return template


def _a(ability_id, name, description, effect, *, cost=22, cooldown=2,
       rarity="common"):
    return {
        "id": ability_id, "name": name, "min_rarity": rarity,
        "resource_cost": cost, "resource_type": "mana", "cooldown": cooldown,
        "description": description, "effect": effect,
    }


EXPANSION_ENEMIES: list[dict] = [
    # ==================================================================
    # GLACIER 15 -- the smallest pool in the game, and the one every
    # player spends their first hours in
    # ==================================================================
    _e("Frostbitten Drifter", "combat", [GLACIER], 7, 5, 3, 7, 46,
       _a("cold_hands", "Cold Hands",
          "Deal 105% ATK damage and slow the target by 18% for 2 turns.",
          {"kind": "damage_and_debuff", "damage_percent": 105,
           "damage_stat": "attack", "debuff_stat": "speed",
           "debuff_percent": -18, "duration": 2})),
    _e("Ice Shelf Crawler", "combat", [GLACIER, WASTELANDS], 8, 6, 3, 9, 44,
       _a("underfoot", "Underfoot",
          "Strike twice for 55% ATK damage each.",
          {"kind": "multi_hit", "hits": 2, "damage_percent_per_hit": 55,
           "damage_stat": "attack"})),
    _e("Snowline Poacher", "combat", [GLACIER], 9, 4, 3, 11, 42,
       _a("set_the_snare", "Set The Snare",
          "Deal 100% ATK damage with a 40% chance to stun for 1 turn.",
          {"kind": "damage_and_stun", "damage_percent": 100,
           "damage_stat": "attack", "chance_percent": 40, "duration": 1}),
       crit=8, crit_dmg=160),
    _e("Rime Lantern", "combat", [GLACIER], 6, 6, 8, 8, 50,
       _a("cold_light", "Cold Light",
          "Deal 90% ELE damage to every enemy.",
          {"kind": "aoe_damage", "damage_percent": 90, "damage_stat": "elemental"},
          cost=24, cooldown=3)),
    _e("Relay Station Guard", "combat", [GLACIER, WASTELANDS], 8, 8, 3, 7, 58,
       _a("dig_in", "Dig In",
          "Deal 95% ATK damage and draw attacks for 2 turns.",
          {"kind": "damage_and_self_taunt", "damage_percent": 95,
           "damage_stat": "attack", "duration": 2})),
    _e("Meltwater Thing", "combat", [GLACIER], 7, 5, 6, 9, 52,
       _a("seep", "Seep",
          "Deal 110% ELE damage and inflict 10% ELE a turn for 3 turns.",
          {"kind": "damage_and_dot", "damage_percent": 110,
           "damage_stat": "elemental", "dot_stat": "elemental",
           "dot_percent": 10, "duration": 3})),
    _e("Avalanche Warden", "elite", [GLACIER], 14, 11, 9, 10, 168,
       _a("bring_it_down", "Bring It Down",
          "Deal 85% ELE damage to every enemy, with a 45% chance to chip 3 "
          "extra poise.",
          {"kind": "aoe_damage_chance_poise_strike", "damage_percent": 85,
           "damage_stat": "elemental", "poise_chance_percent": 45,
           "bonus_poise": 3}, cost=28, cooldown=3, rarity="epic")),
    _e("The Long Winter", "elite", [GLACIER, WASTELANDS], 13, 12, 10, 9, 180,
       _a("settle_in", "Settle In",
          "Lower the squad's attack by 26% for 2 turns.",
          {"kind": "team_debuff", "debuff_stat": "attack",
           "debuff_percent": -26, "duration": 2}, cost=26, cooldown=3,
          rarity="epic")),

    # ==================================================================
    # THE WASTELANDS
    # ==================================================================
    _e("Rust Convoy Outrider", "combat", [WASTELANDS], 13, 6, 4, 13, 50,
       _a("run_them_down", "Run Them Down",
          "Deal 125% ATK damage, with a 35% chance to hit twice.",
          {"kind": "chance_double_hit", "damage_percent": 125,
           "chance_percent": 35, "damage_stat": "attack"}, cooldown=3),
       crit=8, crit_dmg=165),
    _e("Salvage Rig Crew", "combat", [WASTELANDS, HOTLANDS], 12, 8, 4, 9, 60,
       _a("strip_it_down", "Strip It Down",
          "Deal 115% ATK damage and lower the target's defense by 22% for "
          "2 turns.",
          {"kind": "damage_and_debuff", "damage_percent": 115,
           "damage_stat": "attack", "debuff_stat": "defense",
           "debuff_percent": -22, "duration": 2})),
    _e("Fuel Thief", "combat", [WASTELANDS], 14, 5, 5, 15, 46,
       _a("siphon", "Siphon",
          "Deal 120% ELE damage and heal itself for 40% of its Elemental.",
          {"kind": "damage_and_heal_self", "damage_percent": 120,
           "damage_stat": "elemental", "heal_stat": "elemental",
           "heal_percent": 40})),
    _e("Roadside Preacher", "combat", [WASTELANDS], 10, 7, 9, 10, 56,
       _a("the_good_word", "The Good Word",
          "Raise the crew's attack by 22% for 3 turns.",
          {"kind": "team_buff", "buff_stat": "attack", "buff_percent": 22,
           "duration": 3}, cost=24, cooldown=3)),
    _e("Scrapyard Dog Pack", "combat", [WASTELANDS, HOTLANDS], 13, 5, 3, 14, 48,
       _a("worry_the_leg", "Worry The Leg",
          "Strike three times for 45% ATK damage each.",
          {"kind": "multi_hit", "hits": 3, "damage_percent_per_hit": 45,
           "damage_stat": "attack"}, cooldown=3), crit=9),
    _e("Bottle Bomber", "combat", [WASTELANDS], 12, 5, 8, 11, 50,
       _a("lob_it", "Lob It",
          "Deal 80% ELE damage to every enemy.",
          {"kind": "aoe_damage", "damage_percent": 80,
           "damage_stat": "elemental"}, cost=24, cooldown=3)),
    _e("Colosseum Hopeful", "elite", [WASTELANDS], 18, 10, 8, 13, 170,
       _a("play_to_the_crowd", "Play To The Crowd",
          "Raise its own attack by 38% and lower its defense by 24% for "
          "3 turns.",
          {"kind": "self_buff_debuff", "buff_stat": "attack",
           "buff_percent": 38, "debuff_stat": "defense",
           "debuff_percent": -24, "duration": 3}, cost=26, cooldown=3,
          rarity="epic"), crit=10, crit_dmg=170),
    _e("Convoy Quartermaster", "elite", [WASTELANDS, HOTLANDS], 15, 13, 10, 10, 185,
       _a("open_the_stores", "Open The Stores",
          "Shield the whole crew for 26% of their max HP.",
          {"kind": "team_shield_percent_max_hp", "percent": 26},
          cost=28, cooldown=3, rarity="epic")),

    # ==================================================================
    # THE HOTLANDS
    # ==================================================================
    _e("Ashfall Skirmisher", "combat", [HOTLANDS], 14, 7, 6, 13, 58,
       _a("cinders", "Cinders",
          "Deal 115% ELE damage and inflict 12% ELE a turn for 3 turns.",
          {"kind": "damage_and_dot", "damage_percent": 115,
           "damage_stat": "elemental", "dot_stat": "elemental",
           "dot_percent": 12, "duration": 3})),
    _e("Slag Pourer", "combat", [HOTLANDS], 15, 9, 8, 9, 68,
       _a("pour", "Pour",
          "Deal 85% ELE damage to every enemy, with a 40% chance to chip 3 "
          "extra poise.",
          {"kind": "aoe_damage_chance_poise_strike", "damage_percent": 85,
           "damage_stat": "elemental", "poise_chance_percent": 40,
           "bonus_poise": 3}, cost=26, cooldown=3)),
    _e("Thermal Vent Stalker", "combat", [HOTLANDS, VOIDCREST], 16, 6, 5, 15, 54,
       _a("out_of_the_heat", "Out Of The Heat",
          "Deal 130% ATK damage, with a 35% chance to hit twice.",
          {"kind": "chance_double_hit", "damage_percent": 130,
           "chance_percent": 35, "damage_stat": "attack"}, cooldown=3),
       crit=11, crit_dmg=170),
    _e("Kiln Attendant", "combat", [HOTLANDS], 12, 10, 9, 10, 70,
       _a("bank_the_heat", "Bank The Heat",
          "Regenerate 2% of the crew's max HP a turn for 3 turns.",
          {"kind": "team_regen_over_time", "percent_max_hp_per_turn": 2,
           "duration": 3}, cost=24, cooldown=4)),
    _e("Firebreak Crew", "combat", [HOTLANDS], 14, 11, 6, 8, 74,
       _a("hold_the_line_here", "Hold The Line",
          "Deal 100% ATK damage and draw attacks for 2 turns.",
          {"kind": "damage_and_self_taunt", "damage_percent": 100,
           "damage_stat": "attack", "duration": 2})),
    _e("Emberglass Weaver", "elite", [HOTLANDS], 19, 10, 15, 12, 172,
       _a("spin_the_glass", "Spin The Glass",
          "Deal 130% ELE damage and inflict 16% ELE a turn for 4 turns.",
          {"kind": "damage_and_dot", "damage_percent": 130,
           "damage_stat": "elemental", "dot_stat": "elemental",
           "dot_percent": 16, "duration": 4}, cost=28, cooldown=3,
          rarity="epic")),
    _e("The Furnace Steward", "elite", [HOTLANDS, VOIDCREST], 17, 14, 11, 10, 195,
       _a("stoke_them", "Stoke Them",
          "Raise the crew's attack by 28% for 3 turns.",
          {"kind": "team_buff", "buff_stat": "attack", "buff_percent": 28,
           "duration": 3}, cost=28, cooldown=3, rarity="epic")),

    # ==================================================================
    # VOIDCREST DESERT
    # ==================================================================
    _e("Glasswind Rider", "combat", [VOIDCREST], 15, 6, 6, 16, 54,
       _a("cut_across", "Cut Across",
          "Strike three times for 48% ATK damage each.",
          {"kind": "multi_hit", "hits": 3, "damage_percent_per_hit": 48,
           "damage_stat": "attack"}, cooldown=3), crit=10, crit_dmg=168),
    _e("Sandglass Sentry", "combat", [VOIDCREST], 12, 11, 8, 9, 70,
       _a("stand_watch", "Stand Watch",
          "Shield the whole crew for 20% of their max HP.",
          {"kind": "team_shield_percent_max_hp", "percent": 20},
          cost=26, cooldown=3)),
    _e("Dust Reader", "combat", [VOIDCREST, VOIDLANDS], 13, 7, 12, 12, 60,
       _a("read_the_dust", "Read The Dust",
          "Lower the squad's defense by 24% for 2 turns.",
          {"kind": "team_debuff", "debuff_stat": "defense",
           "debuff_percent": -24, "duration": 2}, cost=26, cooldown=3)),
    _e("Crestfall Marauder", "combat", [VOIDCREST], 16, 8, 5, 12, 62,
       _a("pick_the_wounded", "Pick The Wounded",
          "Deal 130% ATK damage, increased by up to 130% more the lower the "
          "target's HP is.",
          {"kind": "damage_scales_with_missing_hp", "base_damage_percent": 130,
           "bonus_damage_percent_at_zero_hp": 130, "damage_stat": "attack"},
          cooldown=3)),
    _e("Buried Signal", "combat", [VOIDCREST], 11, 9, 14, 11, 64,
       _a("carrier_wave", "Carrier Wave",
          "Deal 95% ELE damage to every enemy.",
          {"kind": "aoe_damage", "damage_percent": 95,
           "damage_stat": "elemental"}, cost=26, cooldown=3)),
    _e("The Cartographer", "elite", [VOIDCREST], 20, 12, 14, 14, 188,
       _a("mark_the_route", "Mark The Route",
          "Deal 125% ELE damage and slow the target by 26% for 3 turns.",
          {"kind": "damage_and_debuff", "damage_percent": 125,
           "damage_stat": "elemental", "debuff_stat": "speed",
           "debuff_percent": -26, "duration": 3}, cost=28, cooldown=3,
          rarity="epic")),
    _e("Duneglass Colossus", "elite", [VOIDCREST, VOIDLANDS], 22, 16, 9, 8, 215,
       _a("bear_down", "Bear Down",
          "Deal 120% ATK damage and chip 3 extra poise.",
          {"kind": "damage_and_poise_strike", "damage_percent": 120,
           "damage_stat": "attack", "bonus_poise": 3}, cost=28, cooldown=3,
          rarity="epic")),

    # ==================================================================
    # THE VOIDLANDS
    # ==================================================================
    _e("Thinning Drifter", "combat", [VOIDLANDS], 16, 9, 8, 12, 72,
       _a("less_of_you", "Less Of You",
          "Deal 120% ELE damage and inflict 14% ELE a turn for 3 turns.",
          {"kind": "damage_and_dot", "damage_percent": 120,
           "damage_stat": "elemental", "dot_stat": "elemental",
           "dot_percent": 14, "duration": 3})),
    _e("Absence Surveyor", "combat", [VOIDLANDS], 14, 10, 13, 13, 70,
       _a("measure_the_gap", "Measure The Gap",
          "Lower the squad's defense by 26% for 2 turns.",
          {"kind": "team_debuff", "debuff_stat": "defense",
           "debuff_percent": -26, "duration": 2}, cost=26, cooldown=3)),
    _e("Hollowed Marcher", "combat", [VOIDLANDS, ABYSSNIA], 17, 11, 7, 10, 82,
       _a("keep_walking", "Keep Walking",
          "Deal 135% ATK damage, increased by up to 120% more the lower the "
          "target's HP is.",
          {"kind": "damage_scales_with_missing_hp", "base_damage_percent": 135,
           "bonus_damage_percent_at_zero_hp": 120, "damage_stat": "attack"},
          cooldown=3)),
    _e("Static Choir", "combat", [VOIDLANDS], 13, 9, 16, 11, 74,
       _a("all_at_once_now", "All At Once",
          "Deal 100% ELE damage to every enemy.",
          {"kind": "aoe_damage", "damage_percent": 100,
           "damage_stat": "elemental"}, cost=26, cooldown=3)),
    _e("Remnant Warden", "combat", [VOIDLANDS], 15, 13, 8, 9, 88,
       _a("what_is_left", "What Is Left",
          "Deal 110% ATK damage and draw attacks for 2 turns.",
          {"kind": "damage_and_self_taunt", "damage_percent": 110,
           "damage_stat": "attack", "duration": 2})),
    _e("The Quiet Arithmetic", "elite", [VOIDLANDS], 21, 14, 17, 13, 178,
       _a("subtract", "Subtract",
          "Deal 130% ELE damage and heal itself for 45% of its Elemental.",
          {"kind": "damage_and_heal_self", "damage_percent": 130,
           "damage_stat": "elemental", "heal_stat": "elemental",
           "heal_percent": 45}, cost=28, cooldown=3, rarity="epic")),
    _e("Erasure Vanguard", "elite", [VOIDLANDS, ABYSSNIA], 24, 15, 11, 14, 182,
       _a("first_to_go", "First To Go",
          "Strike four times for 52% ATK damage each.",
          {"kind": "multi_hit", "hits": 4, "damage_percent_per_hit": 52,
           "damage_stat": "attack"}, cost=30, cooldown=3, rarity="epic"),
       crit=10, crit_dmg=172),

    # ==================================================================
    # ABYSSNIA
    # ==================================================================
    _e("Capital Cordon Trooper", "combat", [ABYSSNIA], 17, 12, 8, 11, 76,
       _a("cordon", "Cordon",
          "Deal 115% ATK damage and draw attacks for 2 turns.",
          {"kind": "damage_and_self_taunt", "damage_percent": 115,
           "damage_stat": "attack", "duration": 2})),
    _e("Gilt Tower Sniper", "combat", [ABYSSNIA], 20, 8, 7, 15, 66,
       _a("one_shot", "One Shot",
          "Deal 145% ATK damage, with a 30% chance to hit twice.",
          {"kind": "chance_double_hit", "damage_percent": 145,
           "chance_percent": 30, "damage_stat": "attack"}, cooldown=3),
       crit=13, crit_dmg=180),
    _e("Ledger Enforcer", "combat", [ABYSSNIA], 16, 13, 9, 10, 84,
       _a("call_it_in", "Call It In",
          "Deal 110% ATK damage and lower the target's defense by 26% for "
          "2 turns.",
          {"kind": "damage_and_debuff", "damage_percent": 110,
           "damage_stat": "attack", "debuff_stat": "defense",
           "debuff_percent": -26, "duration": 2})),
    _e("Palace Reliquary", "combat", [ABYSSNIA], 14, 15, 13, 9, 92,
       _a("consecrate", "Consecrate",
          "Regenerate 3% of the crew's max HP a turn for 3 turns.",
          {"kind": "team_regen_over_time", "percent_max_hp_per_turn": 3,
           "duration": 3}, cost=26, cooldown=4)),
    _e("The Standing Order", "elite", [ABYSSNIA], 25, 18, 13, 12, 190,
       _a("as_instructed", "As Instructed",
          "Raise the crew's defense by 32% for 3 turns.",
          {"kind": "team_buff", "buff_stat": "defense", "buff_percent": 32,
           "duration": 3}, cost=30, cooldown=3, rarity="epic")),
    _e("Crown Assessor", "elite", [ABYSSNIA, DEEPWORKS], 26, 16, 16, 14, 186,
       _a("valuation", "Valuation",
          "Deal 140% ELE damage and inflict 18% ELE a turn for 4 turns.",
          {"kind": "damage_and_dot", "damage_percent": 140,
           "damage_stat": "elemental", "dot_stat": "elemental",
           "dot_percent": 18, "duration": 4}, cost=30, cooldown=3,
          rarity="epic")),

    # ==================================================================
    # ENTROSPIRE DEEPWORKS -- still the thinnest pool
    # ==================================================================
    _e("Nightshift Fitter", "combat", [DEEPWORKS], 20, 12, 9, 12, 94,
       _a("torque_it", "Torque It",
          "Deal 125% ATK damage and chip 3 extra poise.",
          {"kind": "damage_and_poise_strike", "damage_percent": 125,
           "damage_stat": "attack", "bonus_poise": 3})),
    _e("Slurry Pump", "combat", [DEEPWORKS], 18, 14, 12, 8, 108,
       _a("flood_the_floor", "Flood The Floor",
          "Deal 95% ELE damage to every enemy.",
          {"kind": "aoe_damage", "damage_percent": 95,
           "damage_stat": "elemental"}, cost=26, cooldown=3)),
    _e("Tally Clerk", "combat", [DEEPWORKS], 17, 13, 14, 11, 96,
       _a("reconcile", "Reconcile",
          "Lower the squad's attack by 24% for 2 turns.",
          {"kind": "team_debuff", "debuff_stat": "attack",
           "debuff_percent": -24, "duration": 2}, cost=26, cooldown=3)),
    _e("Cutting Floor Crew", "combat", [DEEPWORKS], 22, 11, 8, 13, 90,
       _a("piecework", "Piecework",
          "Strike three times for 58% ATK damage each.",
          {"kind": "multi_hit", "hits": 3, "damage_percent_per_hit": 58,
           "damage_stat": "attack"}, cooldown=3), crit=9, crit_dmg=165),
    _e("Recovery Bay Unit", "combat", [DEEPWORKS], 15, 16, 13, 10, 112,
       _a("patch_and_return", "Patch And Return",
          "Regenerate 3% of the crew's max HP a turn for 3 turns.",
          {"kind": "team_regen_over_time", "percent_max_hp_per_turn": 3,
           "duration": 3}, cost=26, cooldown=4)),
    _e("Foreman's Second", "elite", [DEEPWORKS], 29, 20, 15, 13, 205,
       _a("do_it_again", "Do It Again",
          "Deal 140% ATK damage, with a 35% chance to hit twice.",
          {"kind": "chance_double_hit", "damage_percent": 140,
           "chance_percent": 35, "damage_stat": "attack"}, cost=30,
          cooldown=3, rarity="epic"), crit=11, crit_dmg=172),
    _e("The Annual Review", "elite", [DEEPWORKS], 27, 22, 18, 12, 220,
       _a("performance_notes", "Performance Notes",
          "Lower the squad's defense by 34% for 2 turns.",
          {"kind": "team_debuff", "debuff_stat": "defense",
           "debuff_percent": -34, "duration": 2}, cost=30, cooldown=3,
          rarity="epic")),
    _e("Containment Sled", "elite", [DEEPWORKS, VOIDLANDS], 26, 24, 12, 9, 235,
       _a("seal_it_in", "Seal It In",
          "Shield the whole crew for 30% of their max HP.",
          {"kind": "team_shield_percent_max_hp", "percent": 30},
          cost=30, cooldown=3, rarity="epic")),
]


EXPANSION_SHORT_NAMES: dict[str, str] = {
    "Frostbitten Drifter": "Drifter",
    "Ice Shelf Crawler": "Crawler",
    "Snowline Poacher": "Poacher",
    "Rime Lantern": "Lantern",
    "Relay Station Guard": "Relay Guard",
    "Meltwater Thing": "Meltwater",
    "Avalanche Warden": "Avalanche",
    "The Long Winter": "Winter",
    "Rust Convoy Outrider": "Outrider",
    "Salvage Rig Crew": "Rig Crew",
    "Fuel Thief": "Thief",
    "Roadside Preacher": "Preacher",
    "Scrapyard Dog Pack": "Dog Pack",
    "Bottle Bomber": "Bomber",
    "Colosseum Hopeful": "Hopeful",
    "Convoy Quartermaster": "Quartermaster",
    "Ashfall Skirmisher": "Skirmisher",
    "Slag Pourer": "Pourer",
    "Thermal Vent Stalker": "Vent Stalker",
    "Kiln Attendant": "Attendant",
    "Firebreak Crew": "Firebreak",
    "Emberglass Weaver": "Weaver",
    "The Furnace Steward": "Steward",
    "Glasswind Rider": "Rider",
    "Sandglass Sentry": "Sentry",
    "Dust Reader": "Reader",
    "Crestfall Marauder": "Marauder",
    "Buried Signal": "Signal",
    "The Cartographer": "Cartographer",
    "Duneglass Colossus": "Colossus",
    "Thinning Drifter": "Thinning",
    "Absence Surveyor": "Surveyor",
    "Hollowed Marcher": "Marcher",
    "Static Choir": "Static",
    "Remnant Warden": "Remnant",
    "The Quiet Arithmetic": "Arithmetic",
    "Erasure Vanguard": "Erasure",
    "Capital Cordon Trooper": "Cordon",
    "Gilt Tower Sniper": "Sniper",
    "Ledger Enforcer": "Ledger",
    "Palace Reliquary": "Reliquary",
    "The Standing Order": "Order",
    "Crown Assessor": "Assessor",
    "Nightshift Fitter": "Fitter",
    "Slurry Pump": "Pump",
    "Tally Clerk": "Tally",
    "Cutting Floor Crew": "Cutters",
    "Recovery Bay Unit": "Recovery",
    "Foreman's Second": "Second",
    "The Annual Review": "Review",
    "Containment Sled": "Sled",
}

EXPANSION_EMOJI: dict[str, str] = {
    "Frostbitten Drifter": "🥶",
    "Ice Shelf Crawler": "🦎",
    "Snowline Poacher": "🪤",
    "Rime Lantern": "🏮",
    "Relay Station Guard": "📻",
    "Meltwater Thing": "💧",
    "Avalanche Warden": "🏔️",
    "The Long Winter": "🌨️",
    "Rust Convoy Outrider": "🏍️",
    "Salvage Rig Crew": "🔩",
    "Fuel Thief": "⛽",
    "Roadside Preacher": "📖",
    "Scrapyard Dog Pack": "🐺",
    "Bottle Bomber": "🍾",
    "Colosseum Hopeful": "🤼",
    "Convoy Quartermaster": "📦",
    "Ashfall Skirmisher": "🌪️",
    "Slag Pourer": "🫗",
    "Thermal Vent Stalker": "♨️",
    "Kiln Attendant": "🧱",
    "Firebreak Crew": "🧯",
    "Emberglass Weaver": "🕸️",
    "The Furnace Steward": "🔥",
    "Glasswind Rider": "🏇",
    "Sandglass Sentry": "⏳",
    "Dust Reader": "🔮",
    "Crestfall Marauder": "🪫",
    "Buried Signal": "📶",
    "The Cartographer": "🗺️",
    "Duneglass Colossus": "🗿",
    "Thinning Drifter": "🌬️",
    "Absence Surveyor": "📏",
    "Hollowed Marcher": "🚶",
    "Static Choir": "📻",
    "Remnant Warden": "🧱",
    "The Quiet Arithmetic": "➖",
    "Erasure Vanguard": "✏️",
    "Capital Cordon Trooper": "🚧",
    "Gilt Tower Sniper": "🔭",
    "Ledger Enforcer": "📒",
    "Palace Reliquary": "⛩️",
    "The Standing Order": "📜",
    "Crown Assessor": "👑",
    "Nightshift Fitter": "🔧",
    "Slurry Pump": "🛢️",
    "Tally Clerk": "🧮",
    "Cutting Floor Crew": "✂️",
    "Recovery Bay Unit": "🏥",
    "Foreman's Second": "🥈",
    "The Annual Review": "📊",
    "Containment Sled": "🛷",
}
