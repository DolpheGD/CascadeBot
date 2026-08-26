"""
Variety, second pass -- written to fill the THIN POOLS specifically.

WHY THESE ROOMS AND NOT MORE OF THE POPULAR ONES. Encounters are rolled
from the pool matching the room the player is standing in, so a pool's
size is exactly how repetitive that room type feels. Measured before this
file:

    story 41   secret 17   trap 14   treasure 13   merchant 12
    puzzle 9   shrine 8    relic_event 6   campfire 3

Three campfires meant a player saw the same rest-stop text every second
or third campfire of a run, in the one room type they visit deliberately
and often. Relic events at six had the same problem with much higher
stakes attached. Adding another Story encounter would have been easier
and would have improved nothing anybody notices.

WHAT A CAMPFIRE IS FOR, and why these are not just small treasure rooms.
A Campfire is the room you choose on the map when you are hurt, so its
encounters are about the DECISION TO REST rather than about loot: heal
now or push on for something better, spend the stop preparing instead of
recovering, trade safety for supplies. Every one of them has a plain
"just rest" option that behaves the way the room already behaves, so
picking a campfire never becomes a gamble the player did not want.

RELIC EVENTS CHARGE HP, following the pattern relic_event.py established:
gold is nearly free by the late floors, and HP is the resource the boss
fight is actually denominated in. See that module for the full reasoning.

The shard rule from __init__.py is observed throughout -- shards ride as
low-chance bonuses, never as a flat guaranteed gain.
"""

from __future__ import annotations

VARIETY2_ENCOUNTERS: list[dict] = [

    # ==================================================================
    # CAMPFIRE -- the decision to rest
    # ==================================================================

    {
        "id": "v2_burnt_out_signal_fire",
        "name": "A Burnt-Out Signal Fire",
        "image_url": None,
        "room_types": ["campfire"],
        "intros": [
            "Someone built a fire here to be seen from a long way off. It went out a long time ago.",
            "The stack is still laid, still dry, still waiting for a match it never got.",
            "A signal fire, unlit. Whoever built it either left or didn't.",
        ],
        "choices": [
            {
                "id": "light_it",
                "label": "🔥 Light it and rest properly",
                "description": "A real fire. Everyone recovers.",
                "action": "risk",
                "style": "success",
                "success_chance": 0.95,
                "success_text": "It goes up first time. The squad sleeps in the warm for once.",
                "on_success": {"heal": "full"},
                "fail_text": "The stack is damper than it looks. You get warmth out of it, not much.",
                "on_fail": {"heal": 25},
            },
            {
                "id": "strip_it",
                "label": "🪵 Strip it for materials instead",
                "description": "No rest, but you leave carrying something.",
                "action": "risk",
                "style": "primary",
                "success_chance": 0.9,
                "success_text": "Seasoned, cut, stacked. Somebody did the hard part years ago.",
                "on_success": {
                    "gain": {"material_tier": 0, "amount": [40, 90], "gold": [60, 160]},
                    "bonus": {"chance": 0.07, "gain": {"lootbox": "uncommon"}},
                },
                "fail_text": "Most of it crumbles when you lift it.",
                "on_fail": {"gain": {"material_tier": 0, "amount": [10, 25]}},
            },
            {
                "id": "leave",
                "label": "🚪 Leave it laid",
                "description": "In case whoever built it is still coming back.",
                "action": "leave",
                "style": "secondary",
                "text": "You leave the stack where it is, ready for a match.",
            },
        ],
    },

    {
        "id": "v2_field_kitchen",
        "name": "The Field Kitchen",
        "image_url": None,
        "room_types": ["campfire"],
        "intros": [
            "A folding table, two burners, and a tin of something that outlived its label.",
            "Somebody cooked for a crew here. The pans are stacked clean.",
            "It still smells faintly of food, which after this long is a slightly alarming fact.",
        ],
        "choices": [
            {
                "id": "cook_properly",
                "label": "🍲 Cook a real meal (30🪵 20🪨)",
                "description": "Costs fuel. Worth it.",
                "action": "trade",
                "style": "success",
                "cost": {"wood": 30, "stone": 20},
                "success_chance": 1.0,
                "success_text": "It is the first hot meal in days and it does more than the numbers say.",
                "on_success": {"heal": "full", "gain": {"xp": [120, 300]}},
                "fail_text": "",
                "on_fail": {},
                "cant_afford_text": "No fuel, no fire, no meal.",
            },
            {
                "id": "eat_cold",
                "label": "🥫 Eat what's here, cold",
                "description": "Free. Less of everything.",
                "action": "risk",
                "style": "primary",
                "success_chance": 0.88,
                "success_text": "It is exactly as good as it sounds, and everyone feels better anyway.",
                "on_success": {"heal": 35},
                "fail_text": "The tin had turned. You find out the hard way.",
                "on_fail": {"hp_damage_percent": 8},
            },
            {
                "id": "take_supplies",
                "label": "🎒 Pack the kitchen up and take it",
                "description": "No meal, but the kit is worth something.",
                "action": "risk",
                "style": "primary",
                "success_chance": 0.93,
                "success_text": "Burners, pans, a sealed crate under the table. Somebody was well supplied.",
                "on_success": {
                    "gain": {"material_tier": 1, "amount": [16, 34], "gold": [150, 380]},
                    "bonus": {"chance": 0.06, "gain": {"shards": 1}},
                },
                "fail_text": "It comes apart in your hands. Nine years of damp.",
                "on_fail": {},
            },
        ],
    },

    {
        "id": "v2_someone_elses_camp",
        "name": "Someone Else's Camp",
        "image_url": None,
        "room_types": ["campfire"],
        "intros": [
            "Two bedrolls, a banked fire, and nobody in either of them.",
            "The fire has been kept going. Recently. That is the whole problem.",
            "Someone is using this camp. They are not using it right now.",
        ],
        "choices": [
            {
                "id": "rest_anyway",
                "label": "😴 Use it anyway",
                "description": "Rest here and hope they're slow coming back.",
                "action": "risk",
                "style": "primary",
                "success_chance": 0.7,
                "success_text": "Nobody comes back. You leave the fire banked the way you found it.",
                "on_success": {"heal": "full"},
                "fail_text": "They come back. It is brief, and it is not friendly.",
                "on_fail": {"hp_damage_percent": 25, "heal": 15},
            },
            {
                "id": "leave_payment",
                "label": "🪙 Rest, and leave payment (500🪙)",
                "description": "Costs gold. Nobody minds a paying guest.",
                "action": "trade",
                "style": "success",
                "cost": {"gold": 500},
                "success_chance": 1.0,
                "success_text": "You leave coin on the bedroll. Whoever finds it will understand.",
                "on_success": {"heal": "full", "bonus": {"chance": 0.10, "gain": {"lootbox": "rare"}}},
                "fail_text": "",
                "on_fail": {},
                "cant_afford_text": "You've nothing worth leaving.",
            },
            {
                "id": "rob_it",
                "label": "🥷 Take everything and go",
                "description": "No rest. Everything they had.",
                "action": "risk",
                "style": "danger",
                "success_chance": 0.55,
                "success_text": "You are gone before they are back. It is not something to be proud of.",
                "on_success": {
                    "gain": {"material_tier": 2, "amount": [20, 45], "gold": [800, 1800]},
                    "bonus": {"chance": 0.12, "gain": {"lootbox": "epic"}},
                },
                "fail_text": "They are closer than you thought, and they are not slow.",
                "on_fail": {"hp_damage_percent": 32, "loss": {"gold": [200, 600]}},
            },
            {
                "id": "leave",
                "label": "🚪 Move on",
                "description": "Not your camp.",
                "action": "leave",
                "style": "secondary",
                "text": "You leave it exactly as you found it and keep walking.",
            },
        ],
    },

    {
        "id": "v2_the_long_watch",
        "name": "The Long Watch",
        "image_url": None,
        "room_types": ["campfire"],
        "intros": [
            "There is a good sightline here, and enough cover to sleep in shifts.",
            "A defensible corner. The kind you take when you intend to be tired later.",
            "Nothing here but a good position and a decision about how to spend it.",
        ],
        "choices": [
            {
                "id": "sleep_deep",
                "label": "😴 Everyone sleeps",
                "description": "Full recovery, no watch. Slight risk.",
                "action": "risk",
                "style": "success",
                "success_chance": 0.85,
                "success_text": "Nothing finds you. Everyone wakes up whole.",
                "on_success": {"heal": "full"},
                "fail_text": "Something finds you halfway through. You see it off, but not for free.",
                "on_fail": {"heal": 45, "hp_damage_percent": 12},
            },
            {
                "id": "shifts",
                "label": "🛡️ Sleep in shifts",
                "description": "Less rest, and nothing gets close.",
                "action": "risk",
                "style": "primary",
                "success_chance": 1.0,
                "success_text": "Broken sleep, but nobody is surprised by anything.",
                "on_success": {"heal": 55},
                "fail_text": "",
                "on_fail": {},
            },
            {
                "id": "work_through",
                "label": "🔧 Don't sleep — service the gear",
                "description": "No healing at all. Everything gets maintained.",
                "action": "risk",
                "style": "primary",
                "success_chance": 0.95,
                "success_text": "Edges sharpened, straps replaced, everything oiled. It shows.",
                "on_success": {
                    "gain": {"evolution_fragments": [8, 18], "material_tier": 1,
                             "amount": [10, 22], "xp": [150, 400]},
                },
                "fail_text": "You spend the night on it and mostly succeed in staying awake.",
                "on_fail": {"gain": {"xp": [40, 90]}},
            },
        ],
    },

    # ==================================================================
    # RELIC EVENTS -- priced in HP
    # ==================================================================

    {
        "id": "v2_the_inheritance",
        "name": "The Inheritance",
        "image_url": None,
        "room_types": ["relic_event"],
        "intros": [
            "A locker, name-taped, still padlocked. The tape reads a name none of you know.",
            "Somebody's whole kit, kept together, waiting for a person who is not coming.",
            "The padlock is cheap. That is somehow the saddest part of it.",
        ],
        "choices": [
            {
                "id": "force_it",
                "label": "🔨 Force the lock",
                "description": "Costs the squad. You get what's inside.",
                "action": "risk",
                "style": "danger",
                "success_chance": 1.0,
                "success_text": "Whatever they were keeping, they were keeping it carefully.",
                "on_success": {"gain": {"relic": True}, "hp_damage_percent": 18},
            },
            {
                "id": "do_it_properly",
                "label": "🕯️ Open it properly — take the time",
                "description": "Slower and gentler. Costs less, gives less.",
                "action": "trade",
                "style": "primary",
                "cost": {"gold": 2500},
                "success_chance": 1.0,
                "success_text": "You do it the long way, and pack the rest of it back up afterwards.",
                "on_success": {"gain": {"relic": "common", "material_tier": 2,
                                        "amount": [10, 24]}},
                "fail_text": "",
                "on_fail": {},
                "cant_afford_text": "Doing it properly takes supplies you don't have.",
            },
            {
                "id": "leave",
                "label": "◀ Leave the locker shut",
                "description": "It isn't yours.",
                "action": "leave",
                "style": "secondary",
                "text": "You leave the name-tape where it is and walk on.",
            },
        ],
    },

    {
        "id": "v2_the_offer",
        "name": "The Offer",
        "image_url": None,
        "room_types": ["relic_event"],
        "intros": [
            "There is something in the alcove that wants to be picked up. You can feel it deciding about you.",
            "It is not a voice. It is close enough to one that arguing about it feels unwise.",
            "The alcove holds one object and a great deal of attention.",
        ],
        "choices": [
            {
                "id": "accept_fully",
                "label": "🖤 Take it on its terms",
                "description": "The strongest thing on offer. It takes a great deal.",
                "action": "risk",
                "style": "danger",
                "success_chance": 1.0,
                "success_text": "It comes away easily. Everyone is very tired afterwards, and nobody can say why.",
                "on_success": {"gain": {"relic": "legendary"}, "hp_damage_percent": 45},
            },
            {
                "id": "haggle",
                "label": "🤝 Take it on yours",
                "description": "Less of it, and less of you.",
                "action": "risk",
                "style": "primary",
                "success_chance": 0.7,
                "success_text": "You take it without agreeing to anything. It seems to accept the terms.",
                "on_success": {"gain": {"relic": "rare"}, "hp_damage_percent": 15},
                "fail_text": "It does not accept the terms. You leave with nothing and a headache.",
                "on_fail": {"hp_damage_percent": 22},
            },
            {
                "id": "leave",
                "label": "◀ Decline",
                "description": "Nothing that wants to be picked up should be.",
                "action": "leave",
                "style": "secondary",
                "text": "You step back out of the alcove. The attention follows you for a while.",
            },
        ],
    },

    {
        "id": "v2_quartermasters_ledger",
        "name": "The Quartermaster's Ledger",
        "image_url": None,
        "room_types": ["relic_event"],
        "intros": [
            "A ledger, open, and a shelf of numbered boxes behind it. Every box is signed for.",
            "\"SIGN BEFORE REMOVAL,\" says the ledger, in the tone of somebody who meant it.",
            "The last signature is nine years old. The pen is still on the string.",
        ],
        "choices": [
            {
                "id": "sign_for_it",
                "label": "✍️ Sign for one",
                "description": "Costs materials. Take a box, properly.",
                "action": "trade",
                "style": "success",
                "cost": {"xendium": 25, "permafrost_ore": 25},
                "success_chance": 1.0,
                "success_text": "You sign, take the box, and put the pen back on its string.",
                "on_success": {"gain": {"relic": "rare"}},
                "fail_text": "",
                "on_fail": {},
                "cant_afford_text": "The ledger wants 25 xendium and 25 permafrost ore signed against it.",
            },
            {
                "id": "take_two",
                "label": "📦 Sign for one, take two",
                "description": "Nobody is checking. Something might be.",
                "action": "risk",
                "style": "danger",
                "success_chance": 0.5,
                "success_text": "Nothing happens. Nothing continues to happen, which you notice all the way out.",
                "on_success": {"gain": {"relic": "rare", "material_tier": 3, "amount": [12, 28]}},
                "fail_text": "Something is checking.",
                "on_fail": {"hp_damage_percent": 35, "loss": {"material_tier": 2, "amount": [10, 25]}},
            },
            {
                "id": "leave",
                "label": "◀ Close the ledger",
                "description": "Leave the shelves alone.",
                "action": "leave",
                "style": "secondary",
                "text": "You close the ledger and leave the boxes signed for by somebody else.",
            },
        ],
    },

    # ==================================================================
    # PUZZLE / TREASURE spread
    # ==================================================================

    {
        "id": "v2_sorting_problem",
        "name": "The Sorting Problem",
        "image_url": None,
        "room_types": ["puzzle"],
        "intros": [
            "Three chutes, one crate, and a diagram that assumes you already understand it.",
            "The machine wants the crate in the right chute. It will not say which.",
            "A sorting station, still powered, still waiting for the correct answer.",
        ],
        "choices": [
            {
                "id": "work_it_out",
                "label": "🧠 Work the diagram out",
                "description": "Slow, and mostly right.",
                "action": "risk",
                "style": "primary",
                "success_chance": 0.72,
                "success_text": "Third chute. The machine accepts it and pays out whatever it was holding.",
                "on_success": {
                    "gain": {"material_tier": 2, "amount": [18, 40], "evolution_fragments": [6, 14]},
                    "bonus": {"chance": 0.10, "gain": {"lootbox": "rare"}},
                },
                "fail_text": "Wrong chute. The machine returns the crate, emptier than it went in.",
                "on_fail": {},
            },
            {
                "id": "brute_force",
                "label": "🔨 Try all three at once",
                "description": "Fast, and the machine objects.",
                "action": "risk",
                "style": "danger",
                "success_chance": 0.9,
                "success_text": "Two chutes jam. The third pays out anyway.",
                "on_success": {"gain": {"material_tier": 1, "amount": [14, 30], "gold": [200, 500]}},
                "fail_text": "All three jam, loudly, and something in the housing lets go.",
                "on_fail": {"hp_damage_percent": 16},
            },
            {
                "id": "leave",
                "label": "🚪 Leave the crate",
                "description": "Let the machine keep waiting.",
                "action": "leave",
                "style": "secondary",
                "text": "You leave the crate on the belt. The machine waits.",
            },
        ],
    },

    # ==================================================================
    # SHRINE -- offerings, and what answers
    # ==================================================================

    {
        "id": "v2_the_maintenance_altar",
        "name": "The Maintenance Altar",
        "image_url": None,
        "room_types": ["shrine"],
        "intros": [
            "A service bay, swept clean, with tools laid out like offerings and nothing being serviced.",
            "Somebody kept this bay in working order long after there was anything to work on.",
            "Every tool is in its outline. The outlines were painted by hand.",
        ],
        "choices": [
            {
                "id": "make_offering",
                "label": "🔧 Leave materials on the bench",
                "description": "Give something. See what the bay gives back.",
                "action": "trade",
                "style": "success",
                "cost": {"metal": 35, "crystal": 35},
                "success_chance": 1.0,
                "success_text": "You leave them in the outlines. The bay hums, briefly, and your gear is better for it.",
                "on_success": {
                    "gain": {"evolution_fragments": [20, 38]},
                    "heal": 30,
                    "bonus": {"chance": 0.10, "gain": {"lootbox": "epic"}},
                },
                "fail_text": "",
                "on_fail": {},
                "cant_afford_text": "The outlines are for 35 metal and 35 crystal, and they are specific about it.",
            },
            {
                "id": "take_the_tools",
                "label": "🥷 Take the tools instead",
                "description": "They're good tools. The bay may disagree.",
                "action": "risk",
                "style": "danger",
                "success_chance": 0.55,
                "success_text": "You lift them out of their outlines. Nothing objects. Nothing at all objects.",
                "on_success": {
                    "gain": {"material_tier": 2, "amount": [30, 60], "item": "natural"},
                },
                "fail_text": "Something in the bay objects, and it objects through the nearest person.",
                "on_fail": {"hp_damage_percent": 30},
            },
            {
                "id": "leave",
                "label": "🚪 Leave the bay as it is",
                "description": "Somebody kept this tidy for a reason.",
                "action": "leave",
                "style": "secondary",
                "text": "You put nothing down and take nothing away. The outlines stay full.",
            },
        ],
    },

    {
        "id": "v2_wall_of_shift_photos",
        "name": "The Wall of Shift Photographs",
        "image_url": None,
        "room_types": ["shrine", "story"],
        "intros": [
            "Every shift, photographed, pinned in rows. The rows stop partway along the wall.",
            "Hundreds of faces, all of them mid-laugh, none of them here.",
            "Somebody pinned these up one shift at a time and then stopped pinning.",
        ],
        "choices": [
            {
                "id": "read_the_wall",
                "label": "🖼️ Read every row",
                "description": "Costs nothing but time.",
                "action": "risk",
                "style": "success",
                "success_chance": 1.0,
                "success_text": (
                    "You find the last row, and the gap after it, and a name you "
                    "recognise from somewhere you would rather you didn't."
                ),
                "on_success": {
                    "gain": {"xp": [200, 500], "gold": [150, 400]},
                    "bonus": {"chance": 0.08, "gain": {"shards": [1, 2]}},
                },
                "fail_text": "",
                "on_fail": {},
            },
            {
                "id": "take_one",
                "label": "📷 Take one photograph",
                "description": "For whoever might want it back.",
                "action": "risk",
                "style": "primary",
                "success_chance": 0.9,
                "success_text": "You unpin one and put it somewhere safe. It weighs nothing and it is not nothing.",
                "on_success": {
                    "gain": {"relic": "common"},
                },
                "fail_text": "The pin has rusted through the paper. It comes apart in your hand.",
                "on_fail": {},
            },
            {
                "id": "leave",
                "label": "🚪 Leave the wall",
                "description": "Let the rows stand.",
                "action": "leave",
                "style": "secondary",
                "text": "You leave every row where it is and go on down the corridor.",
            },
        ],
    },

    {
        "id": "v2_pallet_of_unopened",
        "name": "A Pallet of Unopened Stock",
        "image_url": None,
        "room_types": ["treasure", "secret"],
        "intros": [
            "Shrink-wrapped, stacked, and never signed for. Nine years of nobody's problem.",
            "The wrap is intact. Whatever is under it has been under it the whole time.",
            "A full pallet, untouched, in a facility where nothing else is.",
        ],
        "choices": [
            {
                "id": "open_all",
                "label": "📦 Cut it all open",
                "description": "Everything on the pallet, whatever it is.",
                "action": "risk",
                "style": "primary",
                "success_chance": 0.8,
                "success_text": "Most of it is stock. Some of it is much better than stock.",
                "on_success": {
                    "gain": {"material_tier": 2, "amount": [25, 55], "item": "natural"},
                    "bonus": [
                        {"chance": 0.14, "gain": {"lootbox": "epic"}},
                        {"chance": 0.06, "gain": {"shards": [1, 3]}},
                    ],
                },
                "fail_text": "It's all coolant. Every box. You smell of it for the rest of the run.",
                "on_fail": {"gain": {"material_tier": 0, "amount": [20, 40]}},
            },
            {
                "id": "take_one",
                "label": "🎁 Take one box off the top",
                "description": "Quick, quiet, and you keep moving.",
                "action": "risk",
                "style": "success",
                "success_chance": 0.95,
                "success_text": "One box, cleanly lifted, nothing disturbed.",
                "on_success": {"gain": {"lootbox": "rare", "gold": [120, 300]}},
                "fail_text": "The box is empty. Somebody got here first, once, a long time ago.",
                "on_fail": {},
            },
            {
                "id": "leave",
                "label": "🚪 Leave the pallet",
                "description": "It's been fine this long.",
                "action": "leave",
                "style": "secondary",
                "text": "You leave the wrap intact and the pallet where it stands.",
            },
        ],
    },
]
