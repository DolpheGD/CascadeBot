"""
Puzzle-room encounters.

Puzzle rooms: riddles and tests of wit, re-themed as NPC encounters
after the standalone puzzle mini-game was retired.

See bot/game/dungeon/encounter_config/__init__.py for the shape of an
encounter dict and how choices/outcomes are interpreted.
"""

from __future__ import annotations

PUZZLE_ENCOUNTERS: list[dict] = [
    # ------------------------------------------------------------------
    # Subject 29 -- brand new. No source art (this encounter didn't
    # exist in explore.js), written to give PUZZLE a dedicated NPC-style
    # option and to pull on the "a name that means nothing to the player
    # yet" thread docs/WORLD_LORE.md explicitly flags as Story-room fuel.
    # ------------------------------------------------------------------
    {
        "id": "subject29_terminal",
        "name": "Subject 29",
        "image_url": "https://cdn.discordapp.com/attachments/1527136925348135023/1527141898588913945/8xiLC9AAAABklEQVQDAIIqAsBtunbaAAAAAElFTkSuQmCC.png?ex=6a5ae6b9&is=6a599539&hm=6c5a43c07c9ef5dac95c4333a5c7f81da21891bdbdab3e9fa0c6b714f098bf59&",
        "room_types": ["puzzle"],
        "intros": [
            "A cracked terminal hums back to life as you approach. A single line blinks: SUBJECT 29 -- STATUS: ACTIVE?",
            "The terminal's fan is still spinning after all this time. Someone -- or something -- called \"Subject 29\" left a login prompt half-finished.",
            "You find a terminal wired into the wall with cables that don't lead anywhere sane. It's waiting for input.",
        ],
        "choices": [
            {
                "id": "careful_decrypt",
                "label": "🔐 Attempt a careful decrypt",
                "description": "Slow and methodical.",
                "action": "risk",
                "style": "primary",
                "success_chance": 0.75,
                "success_text": "The terminal yields its cache without complaint.",
                "on_success": {"gain": {"material_tier": 0, "amount": [17, 37], "gold": [19, 38]}, "bonus": {"chance": 0.08, "gain": {"shards": [1,3]}}},
                "fail_text": "A failsafe locks you out, but not before a small cache dumps to a side buffer.",
                "on_fail": {"gain": {"material_tier": 0, "amount": [7, 16]}},
            },
            {
                "id": "brute_force",
                "label": "⚡ Brute-force the terminal",
                "description": "Fast, and a lot more dangerous.",
                "action": "risk",
                "style": "danger",
                "success_chance": 0.5,
                "success_text": "The lockout shatters -- Subject 29's entire research cache spills out.",
                "on_success": {"gain": {"material_tier": 1, "amount": [10, 47], "gold": [31, 62]}, "bonus": {"chance": 0.12, "gain": {"lootbox": "uncommon"}}},
                "fail_text": "The terminal fights back with a shock through the console.",
                "on_fail": {"loss": {"material_tier": 0, "amount": [3, 8]}, "hp_damage_percent": 10},
            },
            {
                "id": "feed_power",
                "label": "🔋 Feed it power (20⚙️ 10💎)",
                "description": "Give the terminal what it wants.",
                "action": "trade",
                "style": "success",
                "cost": {"metal": 20, "crystal": 10},
                "success_chance": 0.9,
                "success_text": "Power flows in, and the terminal obliges with a full data dump.",
                "on_success": {"gain": {"material_tier": 2, "amount": [4, 9], "gold": [25, 50], "reroll_tokens": [2, 5]}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
                "fail_text": "The terminal drains the power and gives nothing back.",
                "on_fail": {},
            },
            {
                "id": "leave",
                "label": "🚪 Leave the terminal dark",
                "description": "",
                "action": "leave",
                "style": "secondary",
                "text": "You decide some things are better left offline, and walk away.",
            },
        ],
    },
    # ------------------------------------------------------------------
    # Mr. R -- new, drawn from Cascade_Classified_Files.txt (File F-001,
    # first entry). Troll hacker with a grudge against Rex, and a
    # documented interest in the World Aligners; the Puzzle pool's
    # second entry alongside Subject 29's terminal.
    # ------------------------------------------------------------------
    {
        "id": "mr_r_terminal",
        "name": "Mr. R",
        "image_url": "https://cdn.discordapp.com/attachments/1527136925348135023/1527148271141785680/New_Piskel_1.png?ex=6a5aeca8&is=6a599b28&hm=5f2d4f1e987d4959192da66178de22fef2f23040678f82f02e86ce4e7e9f0bb1&",
        "room_types": ["puzzle"],
        "intros": [
            "A terminal blinks with a message that definitely wasn't there a second ago: \"hi. -Mr. R\"",
            "Every screen in the room flickers to the same feed at once: a kid's laughing face, pixelated on purpose.",
            "\"You're one of Josh's little friends, right?\" a voice crackles through a nearby speaker. \"Let's play a game.\"",
        ],
        "choices": [
            {
                "id": "play_along",
                "label": "🎮 Play along with his game",
                "description": "Beat him at his own thing.",
                "action": "risk",
                "style": "primary",
                "success_chance": 0.55,
                "success_text": "You beat Mr. R at his own game -- badly enough that he rage-quits and leaves a parting gift out of spite.",
                "on_success": {"gain": {"material_tier": 0, "amount": [22, 36], "gold": [25, 44]}, "bonus": {"chance": 0.132, "gain": {"lootbox": "common"}}},
                "fail_text": "Mr. R wins, obviously. He locks you out and drains something on the way.",
                "on_fail": {"loss": {"material_tier": 0, "amount": [5, 12]}},
            },
            {
                "id": "counter_hack",
                "label": "💻 Try to hack him back",
                "description": "Fight fire with fire.",
                "action": "risk",
                "style": "danger",
                "success_chance": 0.35,
                "success_text": "Against all odds, you out-troll the troll. He's furious enough to dump his whole stash just to end the conversation.",
                "on_success": {"gain": {"material_tier": 1, "amount": [12, 47], "gold": [38, 69], "reroll_tokens": [2, 4]}, "bonus": {"chance": 0.128, "gain": {"shards": 1}}},
                "fail_text": "Mr. R was, unsurprisingly, better at this than you.",
                "on_fail": {"loss": {"gold": [10, 20]}},
            },
            {
                "id": "unplug",
                "label": "🔌 Just unplug the terminal",
                "description": "The boring, reliable option.",
                "action": "risk",
                "style": "secondary",
                "success_chance": 0.9,
                "success_text": "Problem solved. Mr. R's laughter cuts off mid-sentence.",
                "on_success": {"gain": {"material_tier": 0, "amount": [11, 24]}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
                "fail_text": "The terminal reboots itself out of spite before you can fully disconnect it.",
                "on_fail": {},
            },
            {
                "id": "leave",
                "label": "🚪 Ignore him and walk away",
                "description": "",
                "action": "leave",
                "style": "secondary",
                "text": "You decide feeding a troll never ends well, and walk away.",
            },
        ],
    },
    # ==================================================================
    # MEDIUM / flavor encounters -- solidly in the middle of the reward
    # curve, added mostly to round out the World Aligners (Josh is
    # already in the roster elsewhere) and give Puzzle a lower-stakes
    # option to sit between XG-23 here and Subject 29 / Mr. R above.
    # ==================================================================
    {
        "id": "xg23_patrol",
        "name": "XG-23 Patrol Drone",
        "image_url": "https://cdn.discordapp.com/attachments/1527136925348135023/1527151859578572860/8DPgdLAAAABklEQVQDABtlzdiJOkHeAAAAAElFTkSuQmCC.png?ex=6a5af000&is=6a599e80&hm=ce354889b70e5f31025d0ac7aa18225305eacb81810074db73c824d2ca4fe24e&",
        "room_types": ["puzzle"],
        "intros": [
            "An XG-23 patrol drone hums past overhead, scanning in slow, methodical sweeps. Its optical sensor hasn't locked onto you. Yet.",
            "You find an XG-23 drone stalled out against a support pillar, its targeting system cycling through empty coordinates.",
            "The drone's rocket pods click as they reposition. You have maybe a few seconds before it finishes its scan.",
        ],
        "choices": [
            {
                "id": "hide_behind_cover",
                "label": "🧱 Duck behind cover",
                "description": "Let the scan pass you by.",
                "action": "risk",
                "style": "primary",
                "success_chance": 0.8,
                "success_text": "The drone's scan sweeps right over you. You slip past and grab what it was guarding.",
                "on_success": {"gain": {"material_tier": 0, "amount": [4, 15], "gold": [12, 25]}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
                "fail_text": "You're a half-second too slow. It clips you with a stray shot before losing track of you again.",
                "on_fail": {"hp_damage_percent": 10},
            },
            {
                "id": "disable_optics",
                "label": "🎯 Disable its optical sensor",
                "description": "Precise. Risky if you miss.",
                "action": "risk",
                "style": "danger",
                "success_chance": 0.45,
                "success_text": "One precise hit and the drone goes fully blind, dumping its cargo hold as a failsafe.",
                "on_success": {"gain": {"material_tier": 1, "amount": [4, 30], "gold": [19, 38]}, "bonus": {"chance": 0.11, "gain": {"lootbox": "common"}}},
                "fail_text": "You miss, and the drone very much notices you now.",
                "on_fail": {"hp_damage_percent": 16},
            },
            {
                "id": "leave",
                "label": "🚪 Wait for it to move on",
                "description": "",
                "action": "leave",
                "style": "secondary",
                "text": "You wait it out. The drone eventually loses interest and drifts away.",
            },
        ],
    },
    # ------------------------------------------------------------------
    # Gostley -- new, from Cascade_Classified_Files.txt (File C-003).
    # AI-visor calculator; the Puzzle pool's fourth entry.
    # ------------------------------------------------------------------
    {
        "id": "gostley_calculations",
        "name": "Gostley",
        "image_url": "https://cdn.discordapp.com/attachments/1527136925348135023/1527155714940731462/New_Piskel_2.png?ex=6a5af397&is=6a59a217&hm=cb999115397651478104b7b91fac74842f12251b12adc299575d700b2a9c1412&",
        "room_types": ["puzzle"],
        "intros": [
            "Gostley is staring at a wall of numbers only visible through his visor, muttering calculations to himself.",
            "\"The math doesn't lie,\" Gostley says, tapping the side of his visor. \"People do, constantly. Math's more restful.\"",
            "Gostley's visor throws faint calculation overlays across every surface in the room, including you.",
        ],
        "choices": [
            {
                "id": "help_calculate",
                "label": "🔢 Help him run the numbers",
                "description": "Two heads, one visor.",
                "action": "risk",
                "style": "primary",
                "success_chance": 0.7,
                "success_text": "Between the two of you, the math actually comes together. Gostley's grateful, and shares his findings.",
                "on_success": {"gain": {"gold": [25, 44], "xp": [17, 34]}, "bonus": {"chance": 0.11, "gain": {"lootbox": "common"}}},
                "fail_text": "You mostly just get in the way of his visor readouts.",
                "on_fail": {},
            },
            {
                "id": "ask_for_calc",
                "label": "❓ Ask him to calculate the safest route ahead",
                "description": "Let the visor do the work.",
                "action": "risk",
                "style": "secondary",
                "success_chance": 0.6,
                "success_text": "Gostley's numbers check out. You find supplies exactly where he said you would.",
                "on_success": {"gain": {"material_tier": 0, "amount": [14, 27]}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
                "fail_text": "\"Statistically improbable that I'm wrong,\" Gostley mutters, \"but here we are.\"",
                "on_fail": {},
            },
            {
                "id": "leave",
                "label": "🚪 Leave him to his calculations",
                "description": "",
                "action": "leave",
                "style": "secondary",
                "text": "You leave Gostley to his calculations and continue on your way.",
            },
        ],
    },
]
