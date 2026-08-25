"""
Variety encounters -- three deliberate bands of stakes.

WHY A THIRD BAND EXISTS AT ALL. The roster before this file was good but
narrow in one specific way: almost everything sat in the same middle
range of consequence. A choice cost a little, paid a little, and the
worst outcome was a scratch. Run after run, the encounter screen stopped
being a decision and became a button you press to continue.

So these are written to three explicit bands, and each band exists to do
something the others cannot:

  HIGH STAKES   real losses. Shards can go DOWN, HP damage runs 30-45%,
                and materials are taken whether or not the roll lands.
                These are the ones a player remembers losing. Every one
                has a plain walk-away, because a risk you cannot decline
                is not a risk, it is a tax.

  LOW STAKES    small, safe and quick. Not filler -- pacing. If every
                room is a decision with teeth, the teeth stop landing;
                these are the rooms that make the dangerous ones feel
                dangerous by contrast. Rewards are modest and the
                downside is usually nothing at all.

  TRADING       conversion, not acquisition. The economy has eight
                materials in four tiers and, before these, almost no way
                to move between them. A player sitting on 900 wood and
                short 40 crystal had no recourse but to go and grind the
                thing they were short of. These let a run's surplus
                become the thing that run actually needed.

THE SHARD RULE IS OBSERVED THROUGHOUT. Shards are never a flat guaranteed
`gain` behind a high success_chance -- they ride as a low-chance `bonus`,
or sit inside an already-rare gamble tier, or are bought explicitly. See
the module docstring in __init__.py; that rule is what keeps them rare
across a roster this size, and it only works if every new file follows
it.

TRADES ARE IN THE PLAYER'S FAVOUR, per the same docstring. A trade that
is a coin flip is a scam, and a scam gets clicked once. The conversion
rates below are deliberately generous in the direction of "use your
junk" and stingy in the direction of "manufacture the scarce thing" --
you can always go down a tier cheaply and only ever go up at a loss.
"""

from __future__ import annotations

VARIETY_ENCOUNTERS: list[dict] = [

    # ==================================================================
    # HIGH STAKES
    # ==================================================================

    {
        # The clearest expression of the band: stake something that only
        # ever moves upward elsewhere in the game. Losing shards is rare
        # enough across the whole roster that it genuinely stings.
        "id": "var_overdraft_terminal",
        "name": "The Overdraft Terminal",
        "image_url": None,
        "room_types": ["story", "secret"],
        "intros": [
            "A terminal, still lit, still solvent. The balance on screen is not yours yet.",
            "\"ACCOUNT OPEN,\" the terminal says. It does not say whose.",
            "The screen offers you a line of credit against nothing you own.",
        ],
        "choices": [
            {
                "id": "draw_deep",
                "label": "💳 Draw against the account (3 shards)",
                "description": "Serious money if it clears. It may not clear.",
                "action": "trade",
                "style": "danger",
                "cost": {"shards": 3},
                "success_chance": 0.45,
                "success_text": "The transfer clears. Whoever owned this is past minding.",
                "on_success": {
                    "gain": {"gold": [2200, 4800], "material_tier": 2, "amount": [30, 70]},
                    "bonus": {"chance": 0.18, "gain": {"lootbox": "epic"}},
                },
                "fail_text": "The account is frozen mid-transfer. The fee is not.",
                "on_fail": {"loss": {"gold": [200, 700]}, "hp_damage_percent": 18},
                "cant_afford_text": "The terminal wants collateral you don't have.",
            },
            {
                "id": "draw_small",
                "label": "💳 Draw a modest amount (400🪙)",
                "description": "Lower ceiling, much safer.",
                "action": "trade",
                "style": "primary",
                "cost": {"gold": 400},
                "success_chance": 0.80,
                "success_text": "Small, clean, and nobody notices.",
                "on_success": {"gain": {"gold": [700, 1400], "material_tier": 1, "amount": [12, 30]}},
                "fail_text": "Declined. The fee stands.",
                "on_fail": {},
                "cant_afford_text": "You can't cover the minimum.",
            },
            {
                "id": "leave",
                "label": "🚪 Close the terminal",
                "description": "Debt is heavy to carry down a hole.",
                "action": "leave",
                "style": "secondary",
                "text": "You close the account without touching it. The screen thanks you.",
            },
        ],
    },

    {
        # HP as the stake, which is the resource the boss fight is
        # denominated in -- the same reasoning relic events use. Paying
        # 40% health three floors from a boss is a real decision.
        "id": "var_unstable_core",
        "name": "The Unstable Core",
        "image_url": None,
        "room_types": ["trap", "secret"],
        "intros": [
            "Something under the floor plate is still generating, and it is not happy about it.",
            "The core casing has one crack in it. The light coming out is the wrong colour.",
            "It hums at a pitch that makes your teeth ache. It is also, plainly, worth a fortune.",
        ],
        "choices": [
            {
                "id": "crack_it",
                "label": "☢️ Crack the casing open",
                "description": "Everything inside, or most of your health.",
                "action": "risk",
                "style": "danger",
                "success_chance": 0.40,
                "success_text": "It vents clean and goes quiet. What's left inside is extraordinary.",
                "on_success": {
                    "gain": {"material_tier": 3, "amount": [25, 55], "evolution_fragments": [18, 40]},
                    "bonus": [
                        {"chance": 0.22, "gain": {"lootbox": "legendary"}},
                        {"chance": 0.12, "gain": {"shards": [2, 4]}},
                    ],
                },
                "fail_text": "It vents through you instead.",
                "on_fail": {"hp_damage_percent": 42, "loss": {"material_tier": 1, "amount": [10, 25]}},
            },
            {
                "id": "tap_it",
                "label": "🔌 Tap it carefully",
                "description": "Less of everything, including the risk.",
                "action": "risk",
                "style": "primary",
                "success_chance": 0.75,
                "success_text": "You draw off what you can without touching the crack.",
                "on_success": {
                    "gain": {"material_tier": 2, "amount": [14, 30], "evolution_fragments": [4, 10]},
                    "bonus": {"chance": 0.08, "gain": {"lootbox": "rare"}},
                },
                "fail_text": "A short arcs up the line and finds you.",
                "on_fail": {"hp_damage_percent": 15},
            },
            {
                "id": "leave",
                "label": "🚪 Leave it running",
                "description": "It has been fine for nine years.",
                "action": "leave",
                "style": "secondary",
                "text": "You step around the plate. Behind you, it keeps humming.",
            },
        ],
    },

    {
        # A gamble with a genuinely thin jackpot. The 3% tier is the
        # whole point: an outcome rare enough to be worth talking about.
        "id": "var_long_odds",
        "name": "The Long Odds",
        "image_url": None,
        "room_types": ["treasure", "story"],
        "intros": [
            "Someone has set up a table down here. There is no one behind it.",
            "A hand-lettered sign reads THREE CUPS, ONE ANSWER. The cups are welded down.",
            "The table has been waiting for a player long enough that the dust has a shape.",
        ],
        "choices": [
            {
                "id": "play_high",
                "label": "🎲 Play the high table (2 shards)",
                "description": "Mostly you lose. Occasionally you don't.",
                "action": "gamble",
                "style": "danger",
                "cost": {"shards": 2},
                "tiers": [
                    {"chance": 0.03,
                     "text": "Every cup is the right cup. The table pays out like it has been waiting to.",
                     "outcome": {"gain": {"relic": "legendary", "gold": [3000, 6000],
                                          "shards": [4, 8]}}},
                    {"chance": 0.12,
                     "text": "You read it right. The table is unhappy about it.",
                     "outcome": {"gain": {"material_tier": 3, "amount": [18, 38],
                                          "evolution_fragments": [10, 22]},
                                 "bonus": {"chance": 0.20, "gain": {"lootbox": "epic"}}}},
                    {"chance": 0.30,
                     "text": "Close. The table allows you something for the effort.",
                     "outcome": {"gain": {"gold": [400, 1100], "material_tier": 1, "amount": [8, 20]}}},
                    {"chance": 0.55,
                     "text": "Wrong cup. The table does not gloat, which is somehow worse.",
                     "outcome": {"hp_damage_percent": 12}},
                ],
                "cant_afford_text": "The high table doesn't take gold.",
            },
            {
                "id": "play_low",
                "label": "🎲 Play the low table (250🪙)",
                "description": "Small stakes, small swings.",
                "action": "gamble",
                "style": "primary",
                "cost": {"gold": 250},
                "tiers": [
                    {"chance": 0.10, "text": "A clean read.",
                     "outcome": {"gain": {"gold": [900, 1500], "material_tier": 1, "amount": [10, 24]},
                                 "bonus": {"chance": 0.10, "gain": {"lootbox": "rare"}}}},
                    {"chance": 0.45, "text": "You break about even and enjoy yourself.",
                     "outcome": {"gain": {"gold": [220, 400]}}},
                    {"chance": 0.45, "text": "Wrong cup. It cost you a coffee.",
                     "outcome": {}},
                ],
                "cant_afford_text": "Even the low table has a minimum.",
            },
            {
                "id": "leave",
                "label": "🚪 Don't play",
                "description": "Nobody has ever regretted this one.",
                "action": "leave",
                "style": "secondary",
                "text": "You leave the cups where they are. The dust settles back into its shape.",
            },
        ],
    },

    {
        # The "everything you're carrying" option. Deliberately the
        # harshest failure in the file: material_tier 2 AND 3 losses,
        # plus heavy damage.
        "id": "var_deep_shaft",
        "name": "The Shaft Below the Shaft",
        "image_url": None,
        "room_types": ["secret", "trap"],
        "intros": [
            "The floor here isn't a floor. It's a lid, and it's ajar.",
            "There is a second hole under the hole. The survey maps stop at the first one.",
            "Cold air comes up out of it in a slow, regular rhythm, like breathing.",
        ],
        "choices": [
            {
                "id": "descend",
                "label": "🕳️ Go all the way down",
                "description": "Nobody has catalogued what's down there. That cuts both ways.",
                "action": "risk",
                "style": "danger",
                "success_chance": 0.35,
                "success_text": "The bottom is a storeroom nobody emptied. You take what you can carry.",
                "on_success": {
                    "gain": {"material_tier": 3, "amount": [30, 65], "gold": [1800, 4000],
                             "item": "natural"},
                    "bonus": [
                        {"chance": 0.25, "gain": {"relic": True}},
                        {"chance": 0.15, "gain": {"shards": [2, 5]}},
                    ],
                },
                "fail_text": "The rhythm was not breathing. You climb back out with less than you went in with.",
                "on_fail": {
                    "hp_damage_percent": 38,
                    "loss": {"material_tier": 2, "amount": [15, 35], "gold": [300, 900]},
                },
            },
            {
                "id": "rope_test",
                "label": "🪢 Sound it out first",
                "description": "Costs rope and time. Much better odds.",
                "action": "trade",
                "style": "primary",
                "cost": {"wood": 30, "metal": 15},
                "success_chance": 0.70,
                "success_text": "You go down as far as the rope allows and come back up loaded.",
                "on_success": {
                    "gain": {"material_tier": 2, "amount": [18, 40], "gold": [600, 1400]},
                    "bonus": {"chance": 0.12, "gain": {"lootbox": "epic"}},
                },
                "fail_text": "The rope holds. What it's tied to doesn't.",
                "on_fail": {"hp_damage_percent": 20},
                "cant_afford_text": "You'd need rope and anchors you don't have.",
            },
            {
                "id": "leave",
                "label": "🚪 Put the lid back",
                "description": "Some holes are load-bearing.",
                "action": "leave",
                "style": "secondary",
                "text": "You slide the plate back over it. The breathing stops, or you stop hearing it.",
            },
        ],
    },

    # ==================================================================
    # LOW STAKES
    # ==================================================================

    {
        "id": "var_scrap_pile",
        "name": "A Pile of Scrap",
        "image_url": None,
        "room_types": ["story", "treasure"],
        "intros": [
            "Somebody swept this corridor once and gave up halfway.",
            "A heap of offcuts, none of it sorted, all of it free.",
            "It is a pile of scrap. It is exactly and only that.",
        ],
        "choices": [
            {
                "id": "sort_it",
                "label": "🔧 Sort through it",
                "description": "Two minutes' work. No risk.",
                "action": "risk",
                "style": "success",
                "success_chance": 0.92,
                "success_text": "Half of it is junk. The other half isn't.",
                "on_success": {
                    "gain": {"material_tier": 1, "amount": [10, 24], "gold": [40, 120]},
                    "bonus": {"chance": 0.06, "gain": {"lootbox": "uncommon"}},
                },
                "fail_text": "It's all junk. You get a splinter for your trouble.",
                "on_fail": {"hp_damage_percent": 2},
            },
            {
                "id": "leave",
                "label": "🚪 Walk past",
                "description": "It's a pile of scrap.",
                "action": "leave",
                "style": "secondary",
                "text": "You walk past the pile of scrap.",
            },
        ],
    },

    {
        "id": "var_vending_machine",
        "name": "A Vending Machine, Still Powered",
        "image_url": None,
        "room_types": ["story", "campfire", "merchant"],
        "intros": [
            "Row F is sold out. Everything else is somehow still stocked.",
            "The machine lights up when you approach, delighted to have a customer.",
            "It takes coins. Nine years down here and it still takes coins.",
        ],
        "choices": [
            {
                "id": "buy_snack",
                "label": "🍫 Buy something from row C (35🪙)",
                "description": "It's food. It helps a little.",
                "action": "trade",
                "style": "success",
                "cost": {"gold": 35},
                "success_chance": 1.0,
                "success_text": "It is stale and it is exactly what everyone needed.",
                "on_success": {"heal": 15},
                "fail_text": "",
                "on_fail": {},
                "cant_afford_text": "You are short by less money than you would like to admit.",
            },
            {
                "id": "shake_it",
                "label": "🤝 Shake it",
                "description": "Everyone has done this. It rarely works.",
                "action": "risk",
                "style": "primary",
                "success_chance": 0.35,
                "success_text": "Two things fall out. One of them was not stocked by the machine.",
                "on_success": {
                    "gain": {"gold": [60, 180]},
                    "bonus": {"chance": 0.10, "gain": {"lootbox": "common"}},
                },
                "fail_text": "The machine holds its position. You've been told.",
                "on_fail": {"hp_damage_percent": 3},
            },
            {
                "id": "leave",
                "label": "🚪 Leave it alone",
                "description": "Let it have its dignity.",
                "action": "leave",
                "style": "secondary",
                "text": "You leave it humming to itself, fully stocked, waiting.",
            },
        ],
    },

    {
        "id": "var_dropped_toolkit",
        "name": "Someone's Dropped Toolkit",
        "image_url": None,
        "room_types": ["story", "secret"],
        "intros": [
            "A toolkit, open, tools laid out in order. Whoever set them out did not come back.",
            "The tools are good ones, kept well. The bag has a name inked out.",
            "Everything is where it should be, which is somehow the unsettling part.",
        ],
        "choices": [
            {
                "id": "take_tools",
                "label": "🧰 Take the toolkit",
                "description": "Good tools. No catch.",
                "action": "risk",
                "style": "success",
                "success_chance": 0.95,
                "success_text": "You pack it up. Whoever they were, they kept their edges sharp.",
                "on_success": {
                    "gain": {"material_tier": 1, "amount": [14, 28], "evolution_fragments": [2, 5]},
                    "bonus": {"chance": 0.07, "gain": {"lootbox": "rare"}},
                },
                "fail_text": "The bag's bottom has rotted through. Most of it is scattered and gone.",
                "on_fail": {"gain": {"material_tier": 0, "amount": [4, 10]}},
            },
            {
                "id": "leave",
                "label": "🚪 Leave it laid out",
                "description": "In case they do come back.",
                "action": "leave",
                "style": "secondary",
                "text": "You leave the tools in their order and step around them.",
            },
        ],
    },

    {
        "id": "var_notice_board",
        "name": "The Notice Board",
        "image_url": None,
        "room_types": ["story", "campfire"],
        "intros": [
            "Shift rotas, a safety poster, and one note that isn't either.",
            "Nine years of pinned paper, layered like sediment.",
            "SAFETY FIRST, says the poster, above a photograph of this exact corridor.",
        ],
        "choices": [
            {
                "id": "read_notes",
                "label": "📋 Read the layers",
                "description": "Costs nothing. You might learn where something is.",
                "action": "risk",
                "style": "success",
                "success_chance": 0.85,
                "success_text": "Under the rotas, someone has pencilled a store-room number and a route to it.",
                "on_success": {
                    "gain": {"gold": [80, 220], "material_tier": 1, "amount": [6, 16], "xp": [40, 120]},
                    "bonus": {"chance": 0.05, "gain": {"shards": 1}},
                },
                "fail_text": "It's rotas all the way down.",
                "on_fail": {"gain": {"xp": [10, 30]}},
            },
            {
                "id": "leave",
                "label": "🚪 Move on",
                "description": "You are not on the rota.",
                "action": "leave",
                "style": "secondary",
                "text": "You leave the board to its sediment.",
            },
        ],
    },

    # ==================================================================
    # RESOURCE TRADING
    # ==================================================================

    {
        # UPWARD conversion, at a deliberate loss. This is the one that
        # answers "I have 900 wood and need crystal", and it must stay
        # unattractive enough that running the region for the real thing
        # is still better -- a refinery that beats going and getting it
        # would replace three regions with a button.
        "id": "var_refinery_line",
        "name": "The Refinery Line",
        "image_url": None,
        "room_types": ["merchant", "story"],
        "intros": [
            "One line of the refinery is still running, processing nothing, very patiently.",
            "The hoppers are empty but the belt still moves. It would take input happily.",
            "A sign reads INPUT / OUTPUT with the ratio scratched out and rewritten four times.",
        ],
        "choices": [
            {
                "id": "refine_t0",
                "label": "⚙️ Refine 120 tier-1 → tier-2",
                "description": "Wood and stone in, metal and crystal out. Lossy.",
                "action": "trade",
                "style": "primary",
                "cost": {"wood": 60, "stone": 60},
                "success_chance": 1.0,
                "success_text": "The belt takes it and, some minutes later, gives back rather less.",
                "on_success": {"gain": {"material_tier": 1, "amount": [26, 34]}},
                "fail_text": "",
                "on_fail": {},
                "cant_afford_text": "The hopper needs 60 wood and 60 stone to start a cycle.",
            },
            {
                "id": "refine_t1",
                "label": "⚙️ Refine 100 tier-2 → tier-3",
                "description": "Metal and crystal in, xendium and permafrost out. Lossier.",
                "action": "trade",
                "style": "primary",
                "cost": {"metal": 50, "crystal": 50},
                "success_chance": 1.0,
                "success_text": "The line labours, complains, and produces a small, dense pile.",
                "on_success": {"gain": {"material_tier": 2, "amount": [18, 24]}},
                "fail_text": "",
                "on_fail": {},
                "cant_afford_text": "The line needs 50 metal and 50 crystal for a cycle.",
            },
            {
                "id": "refine_t2",
                "label": "⚙️ Refine 80 tier-3 → tier-4",
                "description": "The last stage. Least efficient, only real source down here.",
                "action": "trade",
                "style": "danger",
                "cost": {"xendium": 40, "permafrost_ore": 40},
                "success_chance": 1.0,
                "success_text": "Whatever comes off the end of the line is not warm and is not quite still.",
                "on_success": {"gain": {"material_tier": 3, "amount": [10, 15]}},
                "fail_text": "",
                "on_fail": {},
                "cant_afford_text": "The last stage needs 40 xendium and 40 permafrost ore.",
            },
            {
                "id": "leave",
                "label": "🚪 Shut the line down",
                "description": "Let it run. It's not hurting anyone.",
                "action": "leave",
                "style": "secondary",
                "text": "You leave the belt moving. It has been doing this a long time.",
            },
        ],
    },

    {
        # DOWNWARD conversion, generously. Breaking scarce things into
        # abundant ones should be easy -- it is the direction nobody can
        # exploit, because the output is the stuff you already have too
        # much of.
        "id": "var_downcycler",
        "name": "The Downcycler",
        "image_url": None,
        "room_types": ["merchant", "secret"],
        "intros": [
            "A hopper, a grinder, and a chute. The chute is the friendly end.",
            "\"BREAKS ANYTHING,\" says the stencil. Someone has added \"(yes, anything)\".",
            "It is a machine for turning something rare into a great deal of something common.",
        ],
        "choices": [
            {
                "id": "down_t3",
                "label": "🔨 Break 20 tier-4 → tier-3",
                "description": "Void and entropy down into xendium and permafrost.",
                "action": "trade",
                "style": "primary",
                "cost": {"void": 10, "entropy": 10},
                "success_chance": 1.0,
                "success_text": "The grinder makes a sound you feel in your sternum, then delivers.",
                "on_success": {"gain": {"material_tier": 2, "amount": [55, 75]}},
                "fail_text": "",
                "on_fail": {},
                "cant_afford_text": "It wants 10 void and 10 entropy to bother starting.",
            },
            {
                "id": "down_t2",
                "label": "🔨 Break 40 tier-3 → tier-2",
                "description": "Xendium and permafrost down into metal and crystal.",
                "action": "trade",
                "style": "primary",
                "cost": {"xendium": 20, "permafrost_ore": 20},
                "success_chance": 1.0,
                "success_text": "Out the chute it comes, considerably more of it than went in.",
                "on_success": {"gain": {"material_tier": 1, "amount": [95, 130]}},
                "fail_text": "",
                "on_fail": {},
                "cant_afford_text": "It wants 20 xendium and 20 permafrost ore.",
            },
            {
                "id": "down_gold",
                "label": "💰 Feed it tier-2 for gold",
                "description": "Metal and crystal in, coin out. Always a fair price.",
                "action": "trade",
                "style": "success",
                "cost": {"metal": 40, "crystal": 40},
                "success_chance": 1.0,
                "success_text": "The chute pays out in sorted, counted coin.",
                "on_success": {"gain": {"gold": [900, 1400]},
                               "bonus": {"chance": 0.06, "gain": {"shards": 1}}},
                "fail_text": "",
                "on_fail": {},
                "cant_afford_text": "It wants 40 metal and 40 crystal.",
            },
            {
                "id": "leave",
                "label": "🚪 Leave the hopper empty",
                "description": "Nothing here needs breaking.",
                "action": "leave",
                "style": "secondary",
                "text": "You leave it idling, hopper open, waiting to be fed.",
            },
        ],
    },

    {
        # Materials -> evolution fragments. Fragments have exactly one
        # passive source (the Evolution Cradle) and are needed by gear
        # breakthroughs, cards AND now character evolution, so a run
        # deserves a way to convert surplus into them.
        "id": "var_fragment_exchange",
        "name": "The Fragment Exchange",
        "image_url": None,
        "room_types": ["merchant", "shrine"],
        "intros": [
            "A counter, a set of brass scales, and a very tidy person who does not give a name.",
            "\"I take material,\" they say. \"I give fragments. That is the whole arrangement.\"",
            "The scales are calibrated to something that isn't weight.",
        ],
        "choices": [
            {
                "id": "exchange_small",
                "label": "💠 Trade 60 tier-2 for fragments",
                "description": "Metal and crystal across the counter.",
                "action": "trade",
                "style": "success",
                "cost": {"metal": 30, "crystal": 30},
                "success_chance": 1.0,
                "success_text": "They weigh it, nod once, and count fragments into your hand.",
                "on_success": {"gain": {"evolution_fragments": [14, 22]}},
                "fail_text": "",
                "on_fail": {},
                "cant_afford_text": "They want 30 metal and 30 crystal. They will not haggle.",
            },
            {
                "id": "exchange_large",
                "label": "💠 Trade 60 tier-3 for fragments",
                "description": "Better rate for the harder materials.",
                "action": "trade",
                "style": "success",
                "cost": {"xendium": 30, "permafrost_ore": 30},
                "success_chance": 1.0,
                "success_text": "The scales tip further than they should. They pay accordingly.",
                "on_success": {"gain": {"evolution_fragments": [40, 60]},
                               "bonus": {"chance": 0.08, "gain": {"shards": [1, 2]}}},
                "fail_text": "",
                "on_fail": {},
                "cant_afford_text": "They want 30 xendium and 30 permafrost ore.",
            },
            {
                "id": "exchange_gold",
                "label": "💠 Buy fragments with gold (1600🪙)",
                "description": "The expensive way. Available when you're short of everything else.",
                "action": "trade",
                "style": "primary",
                "cost": {"gold": 1600},
                "success_chance": 1.0,
                "success_text": "\"Coin works,\" they say, in the tone of someone who wishes it didn't.",
                "on_success": {"gain": {"evolution_fragments": [16, 24]}},
                "fail_text": "",
                "on_fail": {},
                "cant_afford_text": "1,600 gold, and they can see that you don't have it.",
            },
            {
                "id": "leave",
                "label": "🚪 Nothing today",
                "description": "Keep what you're carrying.",
                "action": "leave",
                "style": "secondary",
                "text": "\"Then nothing today,\" they agree, and go back to the scales.",
            },
        ],
    },

    {
        # Cores are the Character Card pull currency and have one
        # harvester. This is the run-side valve for them, and it charges
        # a real price in the tier-3 materials so it competes with the
        # forge rather than undercutting it.
        "id": "var_core_tap",
        "name": "The Core Tap",
        "image_url": None,
        "room_types": ["shrine", "secret"],
        "intros": [
            "A junction box the size of a door, and every cable in it still live.",
            "The tap is spliced into something much older than the splice.",
            "It reads full. It has read full for a very long time.",
        ],
        "choices": [
            {
                "id": "tap_cores",
                "label": "🔋 Draw cores (40 tier-3)",
                "description": "Xendium and permafrost for cores.",
                "action": "trade",
                "style": "success",
                "cost": {"xendium": 20, "permafrost_ore": 20},
                "success_chance": 1.0,
                "success_text": "It gives up its charge without complaint.",
                "on_success": {"gain": {"cores": [90, 150]}},
                "fail_text": "",
                "on_fail": {},
                "cant_afford_text": "The tap needs 20 xendium and 20 permafrost ore to prime.",
            },
            {
                "id": "overdraw",
                "label": "⚡ Overdraw it",
                "description": "Much more, or a shock and nothing.",
                "action": "risk",
                "style": "danger",
                "success_chance": 0.50,
                "success_text": "The junction holds and empties itself into your kit.",
                "on_success": {"gain": {"cores": [260, 480]},
                               "bonus": {"chance": 0.10, "gain": {"shards": [1, 3]}}},
                "fail_text": "The junction does not hold.",
                "on_fail": {"hp_damage_percent": 28},
            },
            {
                "id": "leave",
                "label": "🚪 Leave the tap",
                "description": "It's been full this long.",
                "action": "leave",
                "style": "secondary",
                "text": "You leave it reading full and walk on.",
            },
        ],
    },
]
