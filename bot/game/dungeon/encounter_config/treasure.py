"""
Treasure-room encounters.

Treasure rooms: hoards, caches, and gambling on what's inside them.

See bot/game/dungeon/encounter_config/__init__.py for the shape of an
encounter dict and how choices/outcomes are interpreted.
"""

from __future__ import annotations

TREASURE_ENCOUNTERS: list[dict] = [
    # ------------------------------------------------------------------
    # Duko -- "illegal rock dealer" lootbox-style gambler in the old
    # event. Re-themed to TREASURE: cracking open a crate of loot rocks
    # is basically a treasure-room mechanic already.
    # ------------------------------------------------------------------
    {
        "id": "duko_dealer",
        "name": "Duko",
        "image_url": "https://cdn.discordapp.com/attachments/704530416475832342/1274616296985723056/DUKOEVENTROCKSD.png?ex=6a5a74ae&is=6a59232e&hm=3c96fa4497fa2c09a719bee3a2674943af9af36738a493e7c11986941495a6a5&",
        "room_types": ["treasure"],
        "intros": [
            "Duko, self-proclaimed \"illegal rock dealer,\" waves you over. \"One loot rock, cheap. Don't ask questions.\"",
            "\"Don't tell anyone about this,\" Duko whispers, gesturing at a crate of suspicious rocks.",
            "Duko is busy modeling something on an ancient computer. He barely looks up as he names his price.",
        ],
        "choices": [
            {
                "id": "buy_1",
                "label": "💰 Buy 1 Loot Rock (6🪵 3🪨)",
                "description": "Crack one open and see what's inside.",
                "action": "gamble",
                "style": "primary",
                "cost": {"wood": 6, "stone": 3},
                "tiers": [
                    {"chance": 0.01, "text": "LEGENDARY -- the rock splits open to reveal something incredible.", "outcome": {"gain": {"lootbox": "epic"}}},
                    {"chance": 0.09, "text": "A genuinely good haul.", "outcome": {"gain": {"material_tier": 1, "amount": [6, 20]}, "bonus": {"chance": 0.08, "gain": {"lootbox": "rare"}}}},
                    {"chance": 0.40, "text": "A modest find.", "outcome": {"gain": {"gold": [12, 31]}, "bonus": {"chance": 0.08, "gain": {"lootbox": "uncommon"}}}},
                    {"chance": 0.50, "text": "Just a rock. It was, in fact, just a rock.", "outcome": {"gain": {"material_tier": 0, "amount": [5, 14]}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}}},
                ],
            },
            {
                "id": "buy_5",
                "label": "💰💰 Buy 5 Loot Rocks (30🪵 15🪨)",
                "description": "Buy in bulk. Better odds at something good.",
                "action": "gamble",
                "style": "primary",
                "cost": {"wood": 30, "stone": 15},
                "tiers": [
                    {"chance": 0.04, "text": "Multiple legendary cracks in one go -- Duko looks personally wounded.", "outcome": {"gain": {"lootbox": "epic", "reroll_tokens": [2,5], "shards": [1,3]}}},
                    {"chance": 0.30, "text": "A solid batch, all around.", "outcome": {"gain": {"material_tier": 1, "amount": [10, 47]}, "bonus": {"chance": 0.08, "gain": {"shards": 1}}}},
                    {"chance": 0.66, "text": "Mostly rocks, some gold dust mixed in.", "outcome": {"gain": {"gold": [31, 56], "material_tier": 0, "amount": [14, 27]}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}}},
                ],
            },
            {
                "id": "buy_10",
                "label": "💰💰💰 Buy 10 Loot Rocks (60🪵 30🪨)",
                "description": "Go all in. Best odds Duko's got.",
                "action": "gamble",
                "style": "primary",
                "cost": {"wood": 60, "stone": 30},
                "tiers": [
                    {"chance": 0.08, "text": "An entire crate's worth of the good stuff -- Duko mutters something about early retirement.", "outcome": {"gain": {"lootbox": "epic", "reroll_tokens": [5,10], "shards": 5}}},
                    {"chance": 0.50, "text": "A genuinely excellent haul.", "outcome": {"gain": {"material_tier": 1, "amount": [15, 40], "gold": [12, 25], "reroll_tokens": [2,5]}, "bonus": {"chance": 0.096, "gain": {"shards": 1}}}},
                    {"chance": 0.42, "text": "A decent pile of common goods, at least.", "outcome": {"gain": {"material_tier": 0, "amount": [20, 40], "gold": [19, 38]}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}}},
                ],
            },
            {
                "id": "leave",
                "label": "🚪 Leave Duko to his business",
                "description": "",
                "action": "leave",
                "style": "secondary",
                "text": "You decide to leave Duko to his business and continue your exploration.",
            },
        ],
    },
    # ------------------------------------------------------------------
    # Daffysamlake -- cave-diving companion. Re-themed to TREASURE (it's
    # a literal cave-exploring-for-loot event already); the old "group
    # vs. solo" choice (guaranteed-but-modest vs. bigger variance) is
    # kept almost exactly, just re-costed and bumped up.
    # ------------------------------------------------------------------
    {
        "id": "daffysamlake_cave",
        "name": "Daffysamlake",
        "image_url": "https://cdn.discordapp.com/attachments/1135808718492139521/1280078811680997448/Daffysamlake.png?ex=6a5a8d8b&is=6a593c0b&hm=dc56d6a15a5155ffd647ccc4a6f340c84bdefa2d4b6ccddac7bac3c57e1a65f1&",
        "room_types": ["treasure"],
        "intros": [
            "Daffysamlake spots a cave in the distance. \"Let's go explore together! Better odds surviving that way...\"",
            "\"STARMASTER TO THE RESCUE!\" Daffysamlake yells, and sprints off into a nearby cave without waiting for you.",
            "Daffysamlake eyes his near-broken pickaxe and grins at the cave mouth ahead.",
        ],
        "choices": [
            {
                "id": "explore_together",
                "label": "🤝 Explore the cave with Daffysamlake",
                "description": "Safer, steadier odds.",
                "action": "gamble",
                "style": "success",
                "cost": {},
                "tiers": [
                    {"chance": 0.5, "text": "You explore together and gather a solid haul.", "outcome": {"gain": {"material_tier": 0, "amount": [20, 38]}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}}},
                    {"chance": 0.35, "text": "A good haul, and Daffysamlake insists on splitting evenly.", "outcome": {"gain": {"material_tier": 0, "amount": [27, 47], "gold": [12, 25]}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}}},
                    {"chance": 0.15, "text": "An excellent day -- Daffysamlake finds something shiny and hands it right over.", "outcome": {"gain": {"material_tier": 1, "amount": [6, 22]}, "bonus": {"chance": 0.08, "gain": {"shards": 1}}}},
                ],
            },
            {
                "id": "explore_alone",
                "label": "⛏️ Explore the cave alone",
                "description": "Higher variance, all the loot to yourself.",
                "action": "gamble",
                "style": "primary",
                "cost": {},
                "tiers": [
                    {"chance": 0.08, "text": "Jackpot -- a vein nobody's touched in decades.", "outcome": {"gain": {"material_tier": 1, "amount": [10, 30], "gold": [31, 56]}, "bonus": {"chance": 0.12, "gain": {"lootbox": "uncommon"}}}},
                    {"chance": 0.77, "text": "A solid, multi-resource haul, all to yourself.", "outcome": {"gain": {"material_tier": 0, "amount": [10, 54], "gold": [12, 25]}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}}},
                    {"chance": 0.15, "text": "Daffysamlake beat you to the good stuff. You scrounge up scraps.", "outcome": {"gain": {"material_tier": 0, "amount": [7, 16]}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}}},
                ],
            },
            {
                "id": "leave",
                "label": "🚪 Skip the cave",
                "description": "",
                "action": "leave",
                "style": "secondary",
                "text": "You decide to skip the cave and continue on your way.",
            },
        ],
    },
    # ------------------------------------------------------------------
    # Eris Relic Fragment -- new, from Cascade_Classified_Files.txt
    # (File GE-010, Eris). The high-reward Treasure encounter.
    # ------------------------------------------------------------------
    {
        "id": "eris_relic",
        "name": "Eris Relic Fragment",
        "image_url": "https://cdn.discordapp.com/attachments/1527136925348135023/1527151657241280583/image.png?ex=6a5aefd0&is=6a599e50&hm=097d3edee45099af57053af299f5d22d7f0d623a9002de50b38676976c957a66&",
        "room_types": ["treasure"],
        "intros": [
            "A fragment of something ancient juts out of the rock -- crystalline, faintly warm, humming at a frequency that makes your teeth ache. Eris tech, unmistakably.",
            "Every drone you've ever seen would break down within a few meters of this thing. You're not a drone.",
            "Whatever this fragment is, it predates every nation you've ever heard of.",
        ],
        "choices": [
            {
                "id": "extract_carefully",
                "label": "🔬 Extract it carefully",
                "description": "Priceless, if it survives extraction.",
                "action": "risk",
                "style": "primary",
                "success_chance": 0.35,
                "success_text": "It comes free intact -- a genuine, uncorrupted piece of Eris technology. This is worth a great deal to the right people.",
                "on_success": {"gain": {"material_tier": 3, "amount": [5, 14], "gold": [88, 162]}, "bonus": {"chance": 0.1, "gain": {"lootbox": "epic"}}},
                "fail_text": "It shatters the moment you apply pressure. Whatever it was, it's scrap now.",
                "on_fail": {"gain": {"material_tier": 1, "amount": [11, 20]}},
            },
            {
                "id": "offer_power",
                "label": "🔋 Feed it 30 Xendium and see what happens",
                "description": "It's humming like it's waiting for something.",
                "action": "trade",
                "style": "success",
                "cost": {"xendium": 30},
                "success_chance": 0.8,
                "success_text": "The fragment resonates, then releases something in return -- like it was waiting to be asked properly.",
                "on_success": {"gain": {"material_tier": 3, "amount": [4, 9], "gold": [50, 88], "reroll_tokens": [7, 15]}, "bonus": {"chance": 0.128, "gain": {"shards": [1, 3]}}},
                "fail_text": "The fragment stays dark. Whatever it wanted, that wasn't it.",
                "on_fail": {},
            },
            {
                "id": "leave",
                "label": "🚪 Leave it buried",
                "description": "",
                "action": "leave",
                "style": "secondary",
                "text": "Some things are better left buried. You leave the fragment where it is.",
            },
        ],
    },
    # ------------------------------------------------------------------
    # Nexus -- new, from Cascade_Classified_Files.txt (File C-021). A
    # low-ranking Cascade member who games the XP-leveling system --
    # a fitting fourth Treasure encounter, XP-focused this time.
    # ------------------------------------------------------------------
    {
        "id": "nexus_grind",
        "name": "Nexus",
        "image_url": "https://cdn.discordapp.com/attachments/1527136925348135023/1527157222193369088/81QmKcAAAAGSURBVAMAIPr6UVw8WgMAAAAASUVORK5CYII.png?ex=6a5af4fe&is=6a59a37e&hm=3d59c6b69758fdf2f7031d9b3064575c0ac34843fd448f9466db5c18a67dd3f3&",
        "room_types": ["treasure"],
        "intros": [
            "Nexus is standing in the exact same spot doing the exact same low-effort task he was doing the last time anyone saw him. \"Building experience,\" he explains, unconvincingly.",
            "\"You just gotta grind the right activities,\" Nexus says, not looking up from... whatever this is. \"Numbers go up eventually.\"",
            "Nexus has apparently been standing here accepting minor commissions for hours, purely to pad his stats.",
        ],
        "choices": [
            {
                "id": "join_grind",
                "label": "📈 Join his grinding session",
                "description": "Unglamorous. Apparently effective.",
                "action": "risk",
                "style": "success",
                "success_chance": 0.85,
                "success_text": "Turns out his methods, however unglamorous, genuinely work. You come away with real experience for it.",
                "on_success": {"gain": {"xp": [34, 57], "gold": [12, 25]}, "bonus": {"chance": 0.075, "gain": {"lootbox": "uncommon"}}},
                "fail_text": "You mostly just watch him do the same task forty more times.",
                "on_fail": {},
            },
            {
                "id": "take_his_stash",
                "label": "🎒 \"Borrow\" his commission stash",
                "description": "He seems distracted.",
                "action": "risk",
                "style": "danger",
                "success_chance": 0.35,
                "success_text": "He's too focused on his numbers to notice you taking half his stockpile.",
                "on_success": {"gain": {"material_tier": 0, "amount": [20, 38], "gold": [19, 38]}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
                "fail_text": "He notices immediately. Turns out obsessive grinding builds real reflexes, apparently.",
                "on_fail": {"hp_damage_percent": 10, "loss": {"material_tier": 0, "amount": [5, 12]}},
            },
            {
                "id": "leave",
                "label": "🚪 Leave him to his grind",
                "description": "",
                "action": "leave",
                "style": "secondary",
                "text": "You leave Nexus to his grind and continue on your way.",
            },
        ],
    },
    # ------------------------------------------------------------------
    # Jungle Treasure Chest -- new. Plain, unnamed TREASURE find: no NPC,
    # no risk/fail branch, just a guaranteed common-tier haul. This is
    # the "you found a chest" baseline the rest of the treasure roster
    # (Duko, Daffysamlake, etc.) escalates from -- success_chance 1.0 via
    # "risk" (no cost) is how a truly guaranteed opener is expressed in
    # this schema, same trick a "trade" with cost {} and 1.0 would do.
    # ------------------------------------------------------------------
    {
        "id": "jungle_treasure_chest",
        "name": "Jungle Treasure Chest",
        "image_url": "https://cdn.discordapp.com/attachments/1527136925348135023/1527175021695598682/image.png?ex=6a5b0592&is=6a59b412&hm=dbc007ea6ec0053d7741efddf19c96667ef392881f314bad9ad579fce26ba04a&",
        "room_types": ["treasure"],
        "intros": [
            "Half-buried in vines and jungle rot, a wooden chest sits wedged between two roots.",
            "Sunlight filters through the canopy onto a weathered chest, its lock long since rusted through.",
            "You nearly trip over it: a jungle chest, moss-covered but clearly still intact.",
        ],
        "choices": [
            {
                "id": "open_chest",
                "label": "📦 Open the chest",
                "description": "Guaranteed loot inside.",
                "action": "risk",
                "style": "success",
                "success_chance": 1.0,
                "success_text": "The lid creaks open, revealing a straightforward but solid haul of common materials and a handful of gold.",
                "on_success": {"gain": {"material_tier": 0, "amount": [20, 40], "gold": [12, 25]}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common", "reroll_tokens": [1,2]}}},
                "fail_text": "",
                "on_fail": {},
            },
            {
                "id": "leave",
                "label": "🚪 Leave it be",
                "description": "",
                "action": "leave",
                "style": "secondary",
                "text": "You decide to leave the chest where it lies and continue on your way.",
            },
        ],
    },
    # ------------------------------------------------------------------
    # Voidlands Plains Chest -- new. Same "guaranteed find" shape as the
    # jungle chest above, but re-tuned to the Voidlands' rougher, more
    # dangerous flavor (see Void matter / Voidwarp / Void Hydra
    # elsewhere in this file) -- a medium (tier-1/uncommon) guaranteed
    # haul instead of tier-0, with a small bonus-shard chance riding
    # along like other mid-tier guaranteed finds do.
    # ------------------------------------------------------------------
    {
        "id": "voidlands_plains_chest",
        "name": "Voidlands Plains Chest",
        "image_url": "https://cdn.discordapp.com/attachments/1527136925348135023/1527175045808394320/image.png?ex=6a5b0598&is=6a59b418&hm=eb86c4958a7e5cbea8c6edd5cca5285eb43c1025ea5ff903ad1bffa8b1a21ff9&",
        "room_types": ["treasure"],
        "intros": [
            "A reinforced chest sits alone on the cracked, glassy plains, humming faintly with residual Void energy.",
            "Out here in the open Voidlands plains, a lone chest is the last thing you expected to find intact.",
            "The chest's metal casing is scorched and pitted, but whatever's inside survived the plains just fine.",
        ],
        "choices": [
            {
                "id": "open_chest",
                "label": "📦 Open the chest",
                "description": "Guaranteed medium-tier loot inside.",
                "action": "risk",
                "style": "success",
                "success_chance": 1.0,
                "success_text": "The chest pops open to reveal a solid stash of uncommon materials, along with a decent amount of gold.",
                "on_success": {"gain": {"material_tier": 1, "amount": [7, 15], "gold": [25, 50], "reroll_tokens": [1,2]}, "bonus": {"chance": 0.096, "gain": {"shards": [1,3]}}},
                "fail_text": "",
                "on_fail": {},
            },
            {
                "id": "leave",
                "label": "🚪 Leave it be",
                "description": "",
                "action": "leave",
                "style": "secondary",
                "text": "You decide to leave the chest where it lies and continue across the plains.",
            },
        ],
    },
]
