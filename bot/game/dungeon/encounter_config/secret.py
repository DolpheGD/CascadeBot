"""
Secret-room encounters.

Secret rooms: hidden caches and places you weren't meant to find.

See bot/game/dungeon/encounter_config/__init__.py for the shape of an
encounter dict and how choices/outcomes are interpreted.
"""

from __future__ import annotations

SECRET_ENCOUNTERS: list[dict] = [
    # ------------------------------------------------------------------
    # thedoggyp -- abandoned shack, environmental looting rather than a
    # face-to-face NPC (matches the original event, which never actually
    # shows him on-screen either). Re-themed to SECRET -- a hidden,
    # easy-to-miss location is exactly what a Secret room represents.
    # ------------------------------------------------------------------
    {
        "id": "thedoggyp_shack",
        "name": "thedoggyp's Shack",
        "image_url": "https://cdn.discordapp.com/attachments/1135808718492139521/1280078811379011604/FrancisShack.png?ex=6a5a8d8b&is=6a593c0b&hm=e111dcfb378a14e1b3156c0ec1995c68d9a08d3b6c6871097d49adc77d077dbb&",
        "room_types": ["secret"],
        "intros": [
            "You stumble upon thedoggyp's abandoned shack. There's no life to be seen for miles.",
            "A faint, putrid odor comes from the shack. Looks like thedoggyp fell victim to gambling, same as everyone else around here.",
            "You swear you heard something moving inside the shack.",
        ],
        "choices": [
            {
                "id": "loot_house",
                "label": "🔍 Loot the house",
                "description": "Quick and quiet. Probably.",
                "action": "gamble",
                "style": "primary",
                "cost": {},
                "tiers": [
                    {"chance": 0.15, "text": "Turns out thedoggyp is still in there! He attacks you on the way out.", "outcome": {"loss": {"material_tier": 0, "amount": [3, 8]}, "hp_damage_percent": 8}},
                    {"chance": 0.85, "text": "You find a good stash of loot in the shack.", "outcome": {"gain": {"material_tier": 0, "amount": [16, 38]}, "bonus": {"chance": 0.08, "gain": {"shards": [1,3]}}}},
                ],
            },
            {
                "id": "deconstruct",
                "label": "🔨 Deconstruct the house",
                "description": "Slower, but far more thorough.",
                "action": "gamble",
                "style": "success",
                "cost": {},
                "tiers": [
                    {"chance": 0.3, "text": "thedoggyp WAS in there. He flees in terror, dropping loot.", "outcome": {"gain": {"material_tier": 0, "amount": [34, 61], "gold": [12, 25]}, "bonus": {"chance": 0.132, "gain": {"lootbox": "common"}}}},
                    {"chance": 0.7, "text": "You deconstruct the house and gather solid materials.", "outcome": {"gain": {"material_tier": 0, "amount": [27, 47]}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}}},
                ],
            },
            {
                "id": "forage",
                "label": "🌿 Forage outside instead",
                "description": "The safe, guaranteed option.",
                "action": "risk",
                "style": "secondary",
                "success_chance": 1.0,
                "success_text": "You find some supplies scattered around the house.",
                "on_success": {"gain": {"material_tier": 0, "amount": [14, 27]}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
                "fail_text": "",
                "on_fail": {},
            },
            {
                "id": "leave",
                "label": "🚪 Leave the shack untouched",
                "description": "",
                "action": "leave",
                "style": "secondary",
                "text": "You leave the shack untouched and continue your journey.",
            },
        ],
    },
    # ------------------------------------------------------------------
    # Flux -- brand new, the SECRET/"mystery" showcase encounter, built
    # directly around docs/WORLD_LORE.md's teased name: "a name (Rex,
    # Subject 29, Flux) that means nothing to the player yet and
    # everything to someone who survived it."
    # ------------------------------------------------------------------
    {
        "id": "flux_sighting",
        "name": "Flux",
        "image_url": "https://cdn.discordapp.com/attachments/1527164237560942726/1527176290963034253/image.png?ex=6a5b06c1&is=6a59b541&hm=08e60a69015078aa0ad06ed7b0c3309448a6bcbe3841db780184c90363572a66&",
        "room_types": ["secret"],
        "intros": [
            "You catch a flicker of movement -- gone before you can focus on it. Someone left behind a half-eaten meal and a name scratched into the dirt: FLUX.",
            "A shape you can't quite place watches you from just beyond the treeline, then isn't there anymore.",
            "Something about this place feels watched. A single word is carved into a nearby support beam: FLUX.",
        ],
        "choices": [
            {
                "id": "follow",
                "label": "👣 Follow the trail",
                "description": "Whoever they are, they're fast.",
                "action": "risk",
                "style": "primary",
                "success_chance": 0.4,
                "success_text": "You catch up just long enough for Flux to toss something back at you before vanishing again.",
                "on_success": {"gain": {"material_tier": 2, "amount": [5, 14], "gold": [38, 75]}, "bonus": {"chance": 0.15, "gain": {"shards": [1, 2]}}},
                "fail_text": "Whoever -- whatever -- Flux is, they're long gone by the time you catch up. You find nothing.",
                "on_fail": {},
            },
            {
                "id": "leave_offering",
                "label": "🎁 Leave an offering (10🔷) and wait",
                "description": "See if patience is rewarded.",
                "action": "trade",
                "style": "success",
                "cost": {"xendium": 10},
                "success_chance": 0.6,
                "success_text": "Whatever took the offering left something impressive in return.",
                "on_success": {"gain": {"material_tier": 2, "amount": [8, 19], "reroll_tokens": [2, 5]}, "bonus": {"chance": 0.13, "gain": {"lootbox": "rare"}}},
                "fail_text": "The offering just... disappears. Nothing comes of it.",
                "on_fail": {},
            },
            {
                "id": "leave",
                "label": "🚪 Leave it alone",
                "description": "",
                "action": "leave",
                "style": "secondary",
                "text": "Whatever Flux is, you decide it's not worth the risk today.",
            },
        ],
    },
    # ------------------------------------------------------------------
    # Slikrz -- new, drawn from Cascade_Classified_Files.txt (File
    # C-019). Dimension-seeing lobotomized cube; the SECRET/"mystery"
    # pool's third entry.
    # ------------------------------------------------------------------
    {
        "id": "slikrz_cube",
        "name": "Slikrz",
        "image_url": "https://cdn.discordapp.com/attachments/1527136925348135023/1527145961866924032/0VqQMAAAAGSURBVAMAxNJvo2z6dlsAAAAASUVORK5CYII.png?ex=6a5aea82&is=6a599902&hm=ae5496ec86fe696e051e839f24390edc53cc1eb44eeade4199c3e40f0558adf2&",
        "room_types": ["secret"],
        "intros": [
            "A cube-shaped figure sits perfectly still in the dark, humming an incantation under its breath. It doesn't seem to notice you -- or does it?",
            "\"I was less enlightened, once,\" the cube says, without turning to face you.",
            "Something about this cube-shaped figure makes your vision swim if you look at it too long.",
        ],
        "choices": [
            {
                "id": "listen",
                "label": "👂 Listen to the incantation",
                "description": "Probably fine.",
                "action": "risk",
                "style": "primary",
                "success_chance": 0.5,
                "success_text": "Whatever Slikrz is chanting, it leaves something behind when it's done -- real, physical, and valuable.",
                "on_success": {"gain": {"material_tier": 2, "amount": [7, 16], "gold": [25, 50]}, "bonus": {"chance": 0.144, "gain": {"shards": [1, 2]}}},
                "fail_text": "Your vision swims and you lose track of time -- and, apparently, a few of your supplies.",
                "on_fail": {"loss": {"material_tier": 0, "amount": [5, 12]}},
            },
            {
                "id": "offer_xendium",
                "label": "🔷 Offer 12 Xendium",
                "description": "See if it wants a trade.",
                "action": "trade",
                "style": "success",
                "cost": {"xendium": 12},
                "success_chance": 0.7,
                "success_text": "Slikrz accepts the offering and, in return, shows you something that definitely shouldn't exist.",
                "on_success": {"gain": {"material_tier": 2, "amount": [11, 22], "reroll_tokens": [4,10]}, "bonus": {"chance": 0.13, "gain": {"lootbox": "rare"}}},
                "fail_text": "Slikrz stares through you, unmoved. The offering vanishes anyway.",
                "on_fail": {},
            },
            {
                "id": "leave",
                "label": "🚪 Back away slowly",
                "description": "",
                "action": "leave",
                "style": "secondary",
                "text": "You decide some things are better left un-enlightened, and back away slowly.",
            },
        ],
    },
    # ------------------------------------------------------------------
    # The Ocellios Breach -- new, environmental, the Secret pool's first
    # genuinely dangerous entry (Slikrz/thedoggyp/Flux all lean tame).
    # ------------------------------------------------------------------
    {
        "id": "ocellios_breach",
        "name": "The Ocellios Breach",
        "image_url": "https://cdn.discordapp.com/attachments/1527136925348135023/1527153846130839632/image.png?ex=6a5af1da&is=6a59a05a&hm=303024a697de0cea720676ecbf40d25eeaad37924032b5b5eb7d57f8db9b1cf8&",
        "room_types": ["secret"],
        "intros": [
            "A containment breach hisses quietly in the dark -- old Ocellios tech, still venting something that glows faintly wrong.",
            "Whatever leaked out of this breach hasn't fully dissipated. You can feel it on your skin before you even get close.",
            "A warning placard, mostly melted, still reads: DO NOT APPRO--",
        ],
        "choices": [
            {
                "id": "seal_breach",
                "label": "🔧 Try to seal the breach",
                "description": "Valuable, if you don't get it wrong.",
                "action": "risk",
                "style": "danger",
                "success_chance": 0.4,
                "success_text": "You manage to seal it before it fully destabilizes, and salvage a genuinely valuable sample in the process.",
                "on_success": {"gain": {"material_tier": 2, "amount": [14, 27], "gold": [50, 88]}, "bonus": [{"chance": 0.15, "gain": {"shards": [1,3]}}, {"chance": 0.11, "gain": {"lootbox": "common"}}]},
                "fail_text": "You seal it wrong. The backlash is significant, and costs you more than you'd like to admit.",
                "on_fail": {"hp_damage_percent": 30, "loss": {"material_tier": 0, "amount": [15, 28], "gold": [10, 20]}},
            },
            {
                "id": "leave",
                "label": "🚪 Leave it be",
                "description": "",
                "action": "leave",
                "style": "secondary",
                "text": "Some breaches are better left sealed by people who actually know what they're doing. You leave it be.",
            },
        ],
    },
    # ------------------------------------------------------------------
    # Tbnr, Josh, and you -- new SECRET encounter. A pure whimsy detour:
    # the three of you stumble on an abandoned easel and decide to paint
    # a portrait of Hu Tao (Genshin Impact) together, purely for the
    # bit. Rewards/actions are original: painting quality gates the
    # payout (careful > rushed), and there's a "let Josh handle the
    # brush" gamble option in keeping with his character elsewhere in
    # this file.
    # ------------------------------------------------------------------
    {
        "id": "hu_tao_painting",
        "name": "Tbnr & Josh",
        "image_url": "https://cdn.discordapp.com/attachments/1527136925348135023/1527175107485765702/image.png?ex=6a5b05a7&is=6a59b427&hm=ade565a4e98db251fdd6d8260cbc97b2f8fc18c795871089397ed6ccc9ade912&",
        "room_types": ["secret"],
        "intros": [
            "You find Tbnr and Josh crouched over an abandoned easel and a half-empty paint set. \"We're painting Hu Tao,\" Tbnr says, like that explains everything.",
            "\"Perfect timing,\" Josh says, already mixing colors wrong. \"We need a third opinion. We're doing Hu Tao. Obviously.\"",
            "Tbnr has sketched an extremely rough outline. Josh is holding a paintbrush like a weapon. Somehow, this was already happening before you showed up.",
        ],
        "choices": [
            {
                "id": "paint_carefully",
                "label": "🎨 Take your time and paint it properly",
                "description": "Slow, but it might actually turn out good.",
                "action": "risk",
                "style": "success",
                "success_chance": 0.75,
                "success_text": "Between the three of you, the painting comes together beautifully. Tbnr insists on selling prints -- you get a cut.",
                "on_success": {"gain": {"gold": [31, 56], "material_tier": 0, "amount": [14, 27]}, "bonus": {"chance": 0.096, "gain": {"shards": [1,3]}}},
                "fail_text": "The proportions go horribly wrong somewhere around the death scythe. Josh insists it's \"abstract\" now.",
                "on_fail": {"gain": {"material_tier": 0, "amount": [7, 16]}},
            },
            {
                "id": "let_josh_paint",
                "label": "🎲 Let Josh take the brush",
                "description": "This can only go well.",
                "action": "gamble",
                "style": "primary",
                "cost": {},
                "tiers": [
                    {"chance": 0.1, "text": "Against all odds, Josh's chaotic technique actually works -- the finished piece is stunning. He immediately tries to sell it for way too much.", "outcome": {"gain": {"gold": [50, 88], "material_tier": 1, "amount": [8, 16]}, "bonus": {"chance": 0.12, "gain": {"lootbox": "uncommon"}}}},
                    {"chance": 0.45, "text": "It's... a painting. Technically. Tbnr looks personally offended, but a passing trader buys it out of pity.", "outcome": {"gain": {"gold": [12, 25]}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}}},
                    {"chance": 0.45, "text": "Josh knocks over the entire paint set. You spend the next twenty minutes cleaning it off everything, including yourself.", "outcome": {"loss": {"material_tier": 0, "amount": [2, 6]}}},
                ],
            },
            {
                "id": "leave",
                "label": "🚪 Leave them to it",
                "description": "",
                "action": "leave",
                "style": "secondary",
                "text": "You decide art isn't your calling today and leave Tbnr and Josh to their masterpiece.",
            },
        ],
    },
]
