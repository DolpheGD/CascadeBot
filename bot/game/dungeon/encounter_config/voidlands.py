"""
Void-flavoured encounters, written for the Voidlands and shared everywhere.

WHY THEY ARE NOT REGION-LOCKED. Encounters carry no `regions` key -- the
whole pool is global, and every room in every region draws from it. That
is not a limitation to work around here, it is the reason these read the
way they do: the Void is already a world-wide force in this game (the
Void Hydra guards Glacier 15, Voidcrest Desert is named for it, `void` is
a material you can hold), so a Void encounter is at home in the first
region and the last one.

What that buys is exactly what the Voidlands needed. A brand-new region
whose rooms all draw from a pool written for somewhere else feels
borrowed; adding to the shared pool means the Voidlands gets rooms that
match it AND every other region gets rooms it did not have, from one
piece of work.

WHAT THIS BATCH IS FOR, by room type. Counted before writing rather than
guessed at -- the pool stood at 109 encounters, and the thin ones were
campfire (7), relic_event (9) and puzzle (10) against story's 42. Those
three are also the rooms a player CHOOSES to walk into rather than the
ones they land on, so seeing the same text twice in a run is most likely
and most noticeable there. This batch is weighted accordingly.

THE DESIGN LINE THESE FOLLOW. relic_event.py established that a relic is
priced in HP rather than gold, because by the late floors gold is the
resource with nothing else to spend it on and a gold price answers
itself. Every relic offer below charges health, and every encounter has a
plain walk-away -- an event you cannot decline is a tax, and a tax does
not need a screen.
"""

from __future__ import annotations

VOIDLANDS_ENCOUNTERS: list[dict] = [
    # ------------------------------------------------------------------
    # RELIC EVENTS -- priced in HP
    # ------------------------------------------------------------------
    {
        "id": "the_thing_that_stayed",
        "name": "The Thing That Stayed",
        "image_url": None,
        "room_types": ["relic_event"],
        "intros": [
            "There is an object here that the Void has been working on for a "
            "long time and has not finished. Most of it is gone. The part that "
            "is left is very much still here, and it is warm.",
            "Everything in this room has been thinned out except one object, "
            "which is sitting in the middle of the floor being extremely "
            "present about it.",
        ],
        "choices": [
            {
                "id": "take_it",
                "label": "🕳️ Take it",
                "description": "Whatever kept it here will want something.",
                "action": "risk",
                "style": "danger",
                "success_chance": 1.0,
                "success_text": (
                    "You pick it up. For a moment everyone in the squad is "
                    "briefly less certain they are standing there. It passes. "
                    "Mostly."
                ),
                "on_success": {"gain": {"relic": "rare"}, "hp_damage_percent": 24},
            },
            {
                "id": "pry_it_open",
                "label": "⚒️ Pry it open first",
                "description": "Find out what is keeping it real. Riskier, better.",
                "action": "risk",
                "style": "danger",
                "success_chance": 0.55,
                "success_text": (
                    "It comes apart along a seam that was not there a second "
                    "ago. What is inside is worth the walk."
                ),
                "on_success": {"gain": {"relic": "legendary"}, "hp_damage_percent": 30},
                "fail_text": (
                    "It comes apart. So, briefly, does the room. When it "
                    "reassembles the object is gone and the squad is not "
                    "entirely sure it was ever there."
                ),
                "on_fail": {"hp_damage_percent": 34},
            },
            {
                "id": "leave_it",
                "label": "🚪 Leave it where it is",
                "description": "It has been here longer than you have.",
                "action": "leave",
                "style": "secondary",
                "text": "You leave it. It is still warm. You walk faster.",
            },
        ],
    },
    {
        "id": "the_unmade_cache",
        "name": "The Unmade Cache",
        "image_url": None,
        "room_types": ["relic_event"],
        "intros": [
            "A supply cache, half-erased. The crates on the left are crates. "
            "The crates on the right are a very confident suggestion of crates.",
            "Somebody stocked this place properly, and then the Void got about "
            "forty percent of the way through disagreeing.",
        ],
        "choices": [
            {
                "id": "reach_into_the_gone_half",
                "label": "🫳 Reach into the half that isn't there",
                "description": "Something in it is still solid enough to hold.",
                "action": "risk",
                "style": "danger",
                "success_chance": 0.7,
                "success_text": (
                    "Your hand closes on something that decides, on balance, to "
                    "exist. You do not look at it until you are outside."
                ),
                "on_success": {"gain": {"relic": "rare"}, "hp_damage_percent": 18},
                "fail_text": (
                    "Your hand closes on nothing, and the nothing closes back."
                ),
                "on_fail": {"hp_damage_percent": 26},
            },
            {
                "id": "loot_the_real_half",
                "label": "📦 Loot the half that's still crates",
                "description": "Boring. Reliable. Free.",
                "action": "risk",
                "style": "primary",
                "success_chance": 1.0,
                "success_text": "Rations, wire, and a startling amount of small change.",
                "on_success": {"gain": {"gold": [1400, 2600],
                                        "material_tier": 1, "amount": [30, 60]}},
            },
            {
                "id": "leave_cache",
                "label": "🚪 Move on",
                "description": "Neither half is worth the time.",
                "action": "leave",
                "style": "secondary",
                "text": "You leave the cache to finish whatever it is doing.",
            },
        ],
    },

    # ------------------------------------------------------------------
    # CAMPFIRE -- the thinnest pool at seven
    # ------------------------------------------------------------------
    {
        "id": "fire_that_wont_catch",
        "name": "The Fire That Won't Catch",
        "image_url": None,
        "room_types": ["campfire"],
        "intros": [
            "Good wood, dry tinder, no wind, and the fire will not take. It "
            "lights, considers the situation, and goes out. Six times now.",
            "The kindling is perfect. The Void is simply not in the mood for "
            "combustion tonight.",
        ],
        "choices": [
            {
                "id": "burn_something_that_matters",
                "label": "🔥 Burn something that matters",
                "description": "Give it a reason to stay lit. It costs supplies.",
                "action": "trade",
                "style": "primary",
                "success_chance": 1.0,
                "cost": {"metal": 45},
                "cant_afford_text": "You have nothing here worth burning.",
                "success_text": (
                    "It catches instantly and burns far too well. Everyone "
                    "sleeps. Nobody sleeps easily."
                ),
                "on_success": {"heal": 60},
            },
            {
                "id": "sit_in_the_cold",
                "label": "🥶 Sit in the cold",
                "description": "Rest badly, for free.",
                "action": "risk",
                "style": "secondary",
                "success_chance": 1.0,
                "success_text": (
                    "You sit in the dark with your backs together. It is not "
                    "rest, exactly, but it is not nothing."
                ),
                "on_success": {"heal": 22},
            },
            {
                "id": "walk_on_cold",
                "label": "🚪 Don't stop at all",
                "description": "Keep the distance you've made.",
                "action": "leave",
                "style": "secondary",
                "text": "You walk past the woodpile without slowing down.",
            },
        ],
    },
    {
        "id": "the_last_warm_room",
        "name": "The Last Warm Room",
        "image_url": None,
        "room_types": ["campfire"],
        "intros": [
            "Somebody has been maintaining this room. Swept floor, banked "
            "coals, four cups set out. There is nobody here and the coals are "
            "hot.",
            "A room kept ready for a squad of four by somebody who is not in "
            "it. The cups are clean. The kettle is full.",
        ],
        "choices": [
            {
                "id": "accept_hospitality",
                "label": "☕ Accept it",
                "description": "Rest properly. Somebody meant this for you.",
                "action": "risk",
                "style": "success",
                "success_chance": 1.0,
                "success_text": (
                    "You sit down in a warm room and drink something hot, and "
                    "for twenty minutes nothing is trying to unmake anybody."
                ),
                "on_success": {"heal": 58},
            },
            {
                "id": "search_the_room",
                "label": "🔍 Search it instead of resting",
                "description": "Whoever keeps this room keeps supplies.",
                "action": "risk",
                "style": "primary",
                "success_chance": 0.75,
                "success_text": (
                    "Under the third floorboard: a strongbox, and a note that "
                    "says *for whoever needs it more*."
                ),
                "on_success": {"gain": {"gold": [2200, 4200],
                                        "evolution_fragments": [18, 34]},
                               "heal": 18},
                "fail_text": (
                    "You take the room apart and find nothing, and now it is "
                    "not a nice room any more."
                ),
                "on_fail": {"heal": 10},
            },
            {
                "id": "leave_warm_room",
                "label": "🚪 Leave it as you found it",
                "description": "Somebody else may need it more.",
                "action": "leave",
                "style": "secondary",
                "text": (
                    "You bank the coals back up, rinse the cups, and go. It "
                    "costs you nothing and it is the right thing to do."
                ),
            },
        ],
    },

    # ------------------------------------------------------------------
    # PUZZLE
    # ------------------------------------------------------------------
    {
        "id": "the_door_that_forgets",
        "name": "The Door That Forgets",
        "image_url": None,
        "room_types": ["puzzle"],
        "intros": [
            "A door with a combination lock. Beside it, scratched into the "
            "wall, the combination. Every time you look away, the number on "
            "the wall changes. The lock does not.",
            "The lock wants four digits. The wall helpfully provides four "
            "digits. They are not always the same four digits.",
        ],
        "choices": [
            {
                "id": "trust_the_wall",
                "label": "🔢 Trust the wall",
                "description": "Read it once, don't look away, punch it in.",
                "action": "risk",
                "style": "primary",
                "success_chance": 0.6,
                "success_text": (
                    "You keep your eyes on it the whole way down and the lock "
                    "opens. Behind it, somebody's entire kit."
                ),
                "on_success": {"gain": {"gold": [3000, 5200],
                                        "material_tier": 2, "amount": [22, 40]}},
                "fail_text": (
                    "It changes between your eye and your hand. The lock "
                    "objects, loudly, and something in the wall objects back."
                ),
                "on_fail": {"hp_damage_percent": 20},
            },
            {
                "id": "break_the_lock",
                "label": "⚒️ Ignore the wall entirely",
                "description": "The lock is only a lock.",
                "action": "risk",
                "style": "danger",
                "success_chance": 0.85,
                "success_text": (
                    "Three minutes with a pry bar. The wall keeps offering "
                    "numbers the whole time, increasingly insistently."
                ),
                "on_success": {"gain": {"gold": [1800, 3200]},
                               "hp_damage_percent": 12},
                "fail_text": "The pry bar goes through the door. So does the noise.",
                "on_fail": {"hp_damage_percent": 24},
            },
            {
                "id": "leave_door",
                "label": "🚪 Use the corridor instead",
                "description": "There is always another way round.",
                "action": "leave",
                "style": "secondary",
                "text": "You take the long way. The wall offers one last number.",
            },
        ],
    },

    # ------------------------------------------------------------------
    # TRAP
    # ------------------------------------------------------------------
    {
        "id": "the_thin_floor",
        "name": "The Thin Floor",
        "image_url": None,
        "room_types": ["trap"],
        "intros": [
            "The floor here is thinner than floor should be. Not damaged — "
            "*thinner*, the way a story gets thinner each time it is retold.",
            "Halfway across the room the floor stops being especially committed "
            "to the idea of being a floor.",
        ],
        "choices": [
            {
                "id": "cross_fast",
                "label": "🏃 Cross it fast",
                "description": "Be somewhere else before it decides.",
                "action": "risk",
                "style": "danger",
                "success_chance": 0.65,
                "success_text": "You are across before it finishes making up its mind.",
                "on_success": {"gain": {"gold": [900, 1700]}},
                "fail_text": (
                    "Halfway across, the floor concludes its argument. The drop "
                    "is not far. The landing is not the problem."
                ),
                "on_fail": {"hp_damage_percent": 26},
            },
            {
                "id": "bridge_it",
                "label": "🪵 Bridge it with something real",
                "description": "Spend materials on something solid to walk on.",
                "action": "trade",
                "style": "primary",
                "success_chance": 1.0,
                "cost": {"wood": 80},
                "cant_afford_text": "You have nothing solid enough to trust.",
                "success_text": (
                    "You lay a path of things that are definitely things and "
                    "walk across on them. It works perfectly and feels awful."
                ),
                "on_success": {"gain": {"gold": [900, 1700]}},
            },
            {
                "id": "go_around_floor",
                "label": "🚪 Go around",
                "description": "Longer. Duller. Floored.",
                "action": "leave",
                "style": "secondary",
                "text": "You take the corridor with a floor in it.",
            },
        ],
    },

    # ------------------------------------------------------------------
    # SECRET
    # ------------------------------------------------------------------
    {
        "id": "the_room_that_isnt_on_the_map",
        "name": "The Room That Isn't On The Map",
        "image_url": None,
        "room_types": ["secret"],
        "intros": [
            "Your map shows solid rock. You are standing in a room. Both of "
            "these continue to be true for as long as you are willing to put "
            "up with it.",
            "There is no door behind you now, which is fine, because there was "
            "no room in front of you a minute ago.",
        ],
        "choices": [
            {
                "id": "strip_it",
                "label": "🔦 Strip it before it notices",
                "description": "Take everything. Quickly.",
                "action": "risk",
                "style": "danger",
                "success_chance": 0.72,
                "success_text": (
                    "You get everything portable out through a door that is "
                    "there again. The room is not."
                ),
                "on_success": {"gain": {"gold": [3400, 6000],
                                        "evolution_fragments": [22, 44],
                                        "reroll_tokens": [1, 2]}},
                "fail_text": (
                    "It notices. You get out with your hands empty and a strong "
                    "sense of having been counted."
                ),
                "on_fail": {"hp_damage_percent": 22},
            },
            {
                "id": "take_one_thing",
                "label": "🤏 Take exactly one thing",
                "description": "Modest. Safe. Out.",
                "action": "risk",
                "style": "primary",
                "success_chance": 1.0,
                "success_text": (
                    "You take one thing and leave. The door stays a door the "
                    "whole way, which you decide to find reassuring."
                ),
                "on_success": {"gain": {"gold": [1200, 2200]}},
            },
            {
                "id": "leave_unmapped",
                "label": "🚪 Leave immediately",
                "description": "Rooms that aren't there rarely improve.",
                "action": "leave",
                "style": "secondary",
                "text": "You leave. Behind you the map is right again.",
            },
        ],
    },

    # ------------------------------------------------------------------
    # MERCHANT
    # ------------------------------------------------------------------
    {
        "id": "the_inventory_clerk",
        "name": "The Inventory Clerk",
        "image_url": None,
        "room_types": ["merchant"],
        "intros": [
            "A man with a clipboard is standing in the middle of nowhere "
            "counting things that are not there. He looks up. 'Oh good. "
            "Are you real? I can do a lot with real.'",
            "'Don't touch the left column,' says the clerk, without "
            "explaining what the left column is. 'The right column I can "
            "sell you.'",
        ],
        "choices": [
            {
                "id": "buy_solid_goods",
                "label": "🪙 Buy from the right column",
                "description": "Trade gold for materials that definitely exist.",
                "action": "trade",
                "style": "primary",
                "success_chance": 1.0,
                "cost": {"gold": 3200},
                "cant_afford_text": "'Come back when you're carrying something.'",
                "success_text": (
                    "He ticks four boxes, hands over a crate, and goes back to "
                    "counting. The crate is heavier than he is."
                ),
                "on_success": {"gain": {"material_tier": 2, "amount": [34, 62]}},
            },
            {
                "id": "ask_about_left_column",
                "label": "📋 Ask about the left column",
                "description": "He said not to. He didn't say you couldn't ask.",
                "action": "risk",
                "style": "danger",
                "success_chance": 0.5,
                "success_text": (
                    "He goes very quiet, then gives you something off the left "
                    "column anyway. 'Don't tell the audit.'"
                ),
                "on_success": {"gain": {"relic": "rare"}, "hp_damage_percent": 16},
                "fail_text": (
                    "He looks at you for a long moment and puts a line through "
                    "something. You feel briefly and specifically diminished."
                ),
                "on_fail": {"hp_damage_percent": 20},
            },
            {
                "id": "leave_clerk",
                "label": "🚪 Let him count",
                "description": "He seems busy.",
                "action": "leave",
                "style": "secondary",
                "text": "'Right you are,' he says, already counting again.",
            },
        ],
    },

    # ------------------------------------------------------------------
    # TREASURE
    # ------------------------------------------------------------------
    {
        "id": "the_payroll_that_never_arrived",
        "name": "The Payroll That Never Arrived",
        "image_url": None,
        "room_types": ["treasure"],
        "intros": [
            "A strongbox on a handcart, three regions from anywhere it was "
            "supposed to be, with the seal still on it.",
            "Somebody was moving a lot of money somewhere and stopped moving "
            "it here. The handcart is fine. The somebody is a question.",
        ],
        "choices": [
            {
                "id": "crack_the_box",
                "label": "⚒️ Crack the seal",
                "description": "It's been unclaimed a long time.",
                "action": "risk",
                "style": "primary",
                "success_chance": 0.9,
                "success_text": (
                    "Wages for two hundred people who are not coming to collect "
                    "them. You take it. Somebody should."
                ),
                "on_success": {"gain": {"gold": [4200, 7800],
                                        "reroll_tokens": [1, 3]}},
                "fail_text": (
                    "The seal was doing more than sealing. The lid comes off "
                    "harder than expected and takes some skin with it."
                ),
                "on_fail": {"gain": {"gold": [1200, 2000]}, "hp_damage_percent": 16},
            },
            {
                "id": "leave_payroll",
                "label": "🚪 Leave it sealed",
                "description": "It was somebody's. It might still be.",
                "action": "leave",
                "style": "secondary",
                "text": "You leave the seal intact and the handcart where it is.",
            },
        ],
    },

    # ------------------------------------------------------------------
    # STORY
    # ------------------------------------------------------------------
    {
        "id": "the_survey_marker",
        "name": "The Survey Marker",
        "image_url": None,
        "room_types": ["story"],
        "intros": [
            "A survey marker, driven into rock, with a brass plate: "
            "*EDGE OF AFFECTED ZONE — 4.2 km*. The arrow points back the way "
            "you came. Somebody drove it in a long time ago, and the zone has "
            "not respected it.",
            "The marker says the Void stops 4.2 kilometres behind you. The "
            "Void does not appear to have read the marker.",
        ],
        "choices": [
            {
                "id": "record_the_drift",
                "label": "📐 Measure how far it's moved",
                "description": "Somebody should be keeping track of this.",
                "action": "risk",
                "style": "primary",
                "success_chance": 1.0,
                "success_text": (
                    "You pace it out and write it down. The number is worse "
                    "than anybody at home is expecting, which is exactly why "
                    "it is worth carrying back."
                ),
                "on_success": {"gain": {"xp": [400, 900], "gold": [800, 1600]}},
            },
            {
                "id": "pull_the_marker",
                "label": "🪓 Pull it out and take the plate",
                "description": "Brass is brass.",
                "action": "risk",
                "style": "danger",
                "success_chance": 0.8,
                "success_text": (
                    "The plate comes off clean. It is worth something, and you "
                    "feel worse about it than the money accounts for."
                ),
                "on_success": {"gain": {"gold": [1600, 2800]}},
                "fail_text": (
                    "The marker has been holding something down. Briefly, "
                    "loudly, it stops."
                ),
                "on_fail": {"hp_damage_percent": 18},
            },
            {
                "id": "leave_marker",
                "label": "🚪 Leave it standing",
                "description": "It is the only honest thing out here.",
                "action": "leave",
                "style": "secondary",
                "text": (
                    "You leave it where it is. It is wrong, and it is still "
                    "the only sign anybody ever put up."
                ),
            },
        ],
    },
]
