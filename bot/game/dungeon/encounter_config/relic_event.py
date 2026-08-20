"""
RELIC_EVENT room encounters: a relic offered for something other than gold.

WHY THESE ARE ENCOUNTERS AND NOT THEIR OWN SYSTEM
-------------------------------------------------
The first design for relic events was a separate config module, a
separate room handler in dungeon_service, and a separate view with its
own buttons -- roughly four hundred lines reimplementing choices, costs,
affordability checks, HP damage, walk-away and the run ledger. All of
which the encounter interpreter already does, and has done for eighty
encounters across seven room types.

So they are encounters, tagged `room_types: ["relic_event"]`. The only
thing the interpreter was actually missing was the ability to hand over a
RELIC, which is one branch in dungeon_service._apply_gain and a `rarity`
argument on relic_service.grant_random_relic. Everything else -- the
buttons, the "you can't afford that" path, the ledger, the embed -- came
free and is already tested.

WHAT MAKES THEM DIFFERENT FROM TREASURE
---------------------------------------
A Treasure room hands you a relic. A Merchant sells you one for gold. By
the late floors gold is the resource with nothing else to spend it on, so
a gold price is nearly free and the "choice" answers itself.

These charge HP -- the resource the boss fight is denominated in. That is
what makes "take the cursed relic at 40% health" a decision somebody will
remember losing. Every event also has a plain walk-away, because an event
you cannot decline is a tax, and a tax does not need a screen.
"""

from __future__ import annotations

RELIC_EVENT_ENCOUNTERS: list[dict] = [
    {
        "id": "the_scavengers_table",
        "name": "The Scavenger's Table",
        "image_url": None,
        "room_types": ["relic_event"],
        "intros": [
            "Somebody has laid four objects out on a folding table and gone away. "
            "There is a card, weighed down with a stone: *take one, leave what "
            "it's worth.* It does not say who decides what it's worth.",
            "A folding table, four objects, and a handwritten card. The handwriting "
            "is steady. Whoever set this up expected to be gone a while.",
        ],
        "choices": [
            {
                "id": "pay_blood",
                "label": "🩸 Take one — pay in blood",
                "description": "The table decides what it's worth. It costs the squad.",
                "action": "risk",
                "style": "danger",
                "success_chance": 1.0,
                "success_text": (
                    "You take one. The stone is warm. Everyone in the squad feels "
                    "it, and nobody says anything about it."
                ),
                "on_success": {
                    "gain": {"relic": "rare"},
                    "hp_damage_percent": 22,
                },
            },
            {
                "id": "pay_gold",
                "label": "🪙 Take one — leave everything you're carrying",
                "description": "Empty your pockets onto the table instead.",
                "action": "trade",
                "style": "primary",
                "success_chance": 1.0,
                "cost": {"gold": 4000},
                "cant_afford_text": "The table is unimpressed by what you have.",
                "success_text": (
                    "You empty your pockets onto the table. It seems to be enough. "
                    "It seems to be *exactly* enough, which is worse."
                ),
                "on_success": {"gain": {"relic": "rare"}},
            },
            {
                "id": "leave",
                "label": "◀ Leave it",
                "description": "Walk on.",
                "action": "leave",
                "style": "secondary",
                "text": "You leave it where it is. The stone is still warm.",
            },
        ],
    },
    {
        "id": "the_thing_in_the_case",
        "name": "The Thing In The Case",
        "image_url": None,
        "room_types": ["relic_event"],
        "intros": [
            "A shipping case, cracked along one edge, and something inside that has "
            "clearly been in there a very long time and has clearly not been dormant "
            "the whole while. It will come out either way.",
            "The case moves when you are not looking at it. The seals have been "
            "opened and re-closed from the inside, more than once.",
        ],
        "choices": [
            {
                "id": "reach_in",
                "label": "🫳 Reach in without opening it",
                "description": "Faster. Considerably worse.",
                "action": "risk",
                "style": "danger",
                "success_chance": 0.7,
                "success_text": (
                    "You get your arm in up to the elbow and something gets its "
                    "opinion across. You come away with the relic, and a good deal "
                    "less blood."
                ),
                "on_success": {
                    "gain": {"relic": "legendary"},
                    "hp_damage_percent": 30,
                },
                "fail_text": (
                    "It gets hold of you first. You get the arm back. You do not get "
                    "anything else."
                ),
                "on_fail": {"hp_damage_percent": 35},
            },
            {
                "id": "lever_it",
                "label": "🔧 Open it properly, carefully",
                "description": "Slower, safer, and it costs supplies.",
                "action": "trade",
                "style": "primary",
                "success_chance": 1.0,
                "cost": {"gold": 2600},
                "cant_afford_text": "You do not have the tools or the tape for this.",
                "success_text": (
                    "You take the time. The case opens the way cases are supposed "
                    "to. What is inside is calmer than you expected, and heavier."
                ),
                "on_success": {"gain": {"relic": "rare"}},
            },
            {
                "id": "leave",
                "label": "◀ Leave it sealed",
                "description": "Somebody else's problem.",
                "action": "leave",
                "style": "secondary",
                "text": "You walk away. Behind you, the case settles.",
            },
        ],
    },
    {
        "id": "the_blood_price",
        "name": "The Blood Price",
        "image_url": None,
        "room_types": ["relic_event"],
        "intros": [
            "A shrine, of a sort — a bowl, a blade kept clean, and instructions in a "
            "hand that has written them many times. It offers a great deal, and it "
            "is extremely clear about what it wants.",
            "The bowl is empty and the blade is clean. The instructions are short, "
            "and the last line has been underlined by somebody who meant it.",
        ],
        "choices": [
            {
                "id": "pay_deeply",
                "label": "🩸 Pay what it asks",
                "description": "All of it. It is very specific.",
                "action": "risk",
                "style": "danger",
                "success_chance": 1.0,
                "success_text": (
                    "The bowl fills. Everyone is standing, which the instructions "
                    "did say would be the case, and which you believed slightly "
                    "less than you do now."
                ),
                "on_success": {
                    "gain": {"relic": "legendary"},
                    "hp_damage_percent": 42,
                },
            },
            {
                "id": "pay_shallow",
                "label": "🤏 Pay the smaller price",
                "description": "It will accept less. It will give less.",
                "action": "risk",
                "style": "primary",
                "success_chance": 1.0,
                "success_text": "The bowl accepts it, without enthusiasm.",
                "on_success": {
                    "gain": {"relic": "common"},
                    "hp_damage_percent": 14,
                },
            },
            {
                "id": "leave",
                "label": "◀ Don't",
                "description": "Leave the bowl empty.",
                "action": "leave",
                "style": "secondary",
                "text": "You leave the bowl empty. It does not seem surprised.",
            },
        ],
    },
    {
        "id": "the_offer_you_regret",
        "name": "The Offer You Will Regret",
        "image_url": None,
        "room_types": ["relic_event"],
        "intros": [
            "It is not hiding what it is, which is the unsettling part — every other "
            "cursed thing down here at least tried. \"I'll be a problem,\" it says, "
            "agreeably. \"I'll also be the reason you get through the next one.\"",
            "\"Before you ask: yes. Yes to all of it. I'm still the best offer "
            "you'll get on this floor.\"",
        ],
        "choices": [
            {
                "id": "take_the_curse",
                "label": "🕳️ Take it anyway",
                "description": "It was honest, at least.",
                "action": "risk",
                "style": "danger",
                "success_chance": 1.0,
                "success_text": (
                    "It settles in somewhere behind your ribs and gets comfortable. "
                    "It was telling the truth about both parts."
                ),
                "on_success": {"gain": {"relic": "cursed"}},
            },
            {
                "id": "take_and_heal",
                "label": "🩹 Take it, and let it patch you up first",
                "description": "\"Oh, gladly.\"",
                "action": "risk",
                "style": "primary",
                "success_chance": 1.0,
                "success_text": (
                    "Everyone feels better. Nobody feels reassured."
                ),
                "on_success": {"gain": {"relic": "cursed"}, "heal": 30},
            },
            {
                "id": "leave",
                "label": "◀ Decline",
                "description": "Politely.",
                "action": "leave",
                "style": "secondary",
                "text": "\"Suit yourself. I'll be on the next floor as well.\"",
            },
        ],
    },
    {
        "id": "the_quartermasters_apology",
        "name": "The Quartermaster's Apology",
        "image_url": None,
        "room_types": ["relic_event"],
        "intros": [
            "A supply drop that came down hard, split, and scattered. Most of it is "
            "ruined. Most of it — there is one case that landed on soft ground, and "
            "getting to it means going through the wreckage of everything that "
            "didn't.",
            "The drop chute is still tangled in what is left of the crates. One case "
            "at the bottom of it is intact.",
        ],
        "choices": [
            {
                "id": "dig",
                "label": "⛏️ Dig it out",
                "description": "An hour of work and some skin.",
                "action": "risk",
                "style": "danger",
                "success_chance": 0.85,
                "success_text": (
                    "It takes an hour and costs some skin. The case is intact and "
                    "the seals are good."
                ),
                "on_success": {
                    "gain": {"relic": "rare", "gold": [1800, 2600]},
                    "hp_damage_percent": 16,
                },
                "fail_text": (
                    "The stack shifts while you are inside it. You get out. The case "
                    "does not."
                ),
                "on_fail": {"hp_damage_percent": 20},
            },
            {
                "id": "salvage",
                "label": "📦 Take what's already loose",
                "description": "No digging. No case.",
                "action": "risk",
                "style": "primary",
                "success_chance": 1.0,
                "success_text": "You fill your pack from what split open on impact.",
                "on_success": {"gain": {"gold": [900, 1400], "lootbox": "rare"}},
            },
            {
                "id": "leave",
                "label": "◀ Leave it",
                "description": "It is a lot of wreckage.",
                "action": "leave",
                "style": "secondary",
                "text": "You leave the drop where it fell.",
            },
        ],
    },
    {
        "id": "an_exchange_politely_proposed",
        "name": "An Exchange, Politely Proposed",
        "image_url": None,
        "room_types": ["relic_event"],
        "intros": [
            "A figure at a folding chair, with a ledger, who does not look up. "
            "\"You have something. I have something. I'm not going to pretend mine "
            "is better — I'm going to point out that you already know what yours "
            "does.\"",
            "\"Sit down. Or don't. The offer is the same either way, and so is the "
            "chair.\"",
        ],
        "choices": [
            {
                "id": "buy_outright",
                "label": "🪙 Just buy it",
                "description": "\"Sensible. Boring. Sensible.\"",
                "action": "trade",
                "style": "primary",
                "success_chance": 1.0,
                "cost": {"gold": 5200},
                "cant_afford_text": "They look at your gold, then at you, and say nothing.",
                "success_text": "They take the gold and slide it across without counting it.",
                "on_success": {"gain": {"relic": "rare"}},
            },
            {
                "id": "the_hard_way",
                "label": "🩸 Offer what you're actually carrying",
                "description": "They aren't asking for gold, and you both know it.",
                "action": "risk",
                "style": "danger",
                "success_chance": 1.0,
                "success_text": (
                    "They look at you for slightly too long, then write something in "
                    "the ledger and hand over something heavier than it should be."
                ),
                "on_success": {
                    "gain": {"relic": "legendary"},
                    "hp_damage_percent": 34,
                },
            },
            {
                "id": "leave",
                "label": "◀ Walk on",
                "description": "Nothing changes hands.",
                "action": "leave",
                "style": "secondary",
                "text": "They go back to the ledger. They were never really waiting.",
            },
        ],
    },
]
