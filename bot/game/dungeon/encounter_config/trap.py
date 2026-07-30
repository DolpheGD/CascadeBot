"""
Trap-room encounters.

Trap rooms: ambushes and hazards. These deliberately tend to have no
clean "walk away" option -- the room already sprung on you.

See bot/game/dungeon/encounter_config/__init__.py for the shape of an
encounter dict and how choices/outcomes are interpreted.
"""

from __future__ import annotations

TRAP_ENCOUNTERS: list[dict] = [
    # ------------------------------------------------------------------
    # Triv -- feared assassin, straight combat-flavored risk encounter.
    # Re-themed to TRAP: no leave/avoid option, same as TRAP_CHOICES
    # itself never offers a truly free bail-out from an ambush. No
    # gear/tool-durability gating like the old JS version either -- risk
    # and reward come purely from success_chance and hp_damage_percent.
    # ------------------------------------------------------------------
    {
        "id": "triv_assassin",
        "name": "Triv",
        "image_url": "https://cdn.discordapp.com/attachments/704530416475832342/1274674180419489822/1v1Triv.png?ex=6a5aaa96&is=6a595916&hm=32e65fa2e436e72dcf0c741cf0f94eecd48b9d5b5b11b1191cb37e43772399d8&",
        "room_types": ["trap"],
        "intros": [
            "Triv the feared assassin steps out of the shadows. \"You and I will fight to the death... for LOONA!!\"",
            "\"I am always two steps ahead,\" Triv says. \"People like you must be eliminated...\"",
            "Triv has been sent by Xender to eliminate you. He seems almost apologetic about it.",
        ],
        "choices": [
            {
                "id": "flee",
                "label": "🏃 Flee",
                "description": "Live to explore another floor.",
                "action": "risk",
                "style": "secondary",
                "success_chance": 0.7,
                "success_text": "You get away clean, snatching a dropped supply pouch on the way.",
                "on_success": {"gain": {"gold": [6, 15]}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
                "fail_text": "You drop some supplies scrambling to get away.",
                "on_fail": {"loss": {"material_tier": 0, "amount": [2, 6]}},
            },
            {
                "id": "fight_fists",
                "label": "🥊 Fight with your fists",
                "description": "Quick and risky.",
                "action": "risk",
                "style": "danger",
                "success_chance": 0.45,
                "success_text": "You disarm Triv and he flees, dropping loot in his hurry.",
                "on_success": {"gain": {"gold": [31, 56], "material_tier": 0, "amount": [14, 27]}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
                "fail_text": "Triv wipes the floor with you.",
                "on_fail": {"loss": {"gold": [5, 15]}, "hp_damage_percent": 15},
            },
            {
                "id": "fight_hard",
                "label": "⚔️ Fight seriously",
                "description": "Commit fully -- bigger reward, bigger risk.",
                "action": "risk",
                "style": "danger",
                "success_chance": 0.5,
                "success_text": "You thoroughly defeat Triv in battle. A wealth of resources scatters everywhere.",
                "on_success": {"gain": {"material_tier": 1, "amount": [10, 38], "gold": [31, 56], "reroll_tokens": [1,2]}, "bonus": {"chance": 0.132, "gain": {"lootbox": "common"}}},
                "fail_text": "Even fighting seriously, Triv gets the better of you.",
                "on_fail": {"loss": {"material_tier": 0, "amount": [5, 12]}, "hp_damage_percent": 20},
            },
        ],
    },
    # ------------------------------------------------------------------
    # Caliper -- new, drawn from Cascade_Classified_Files.txt (File
    # C-006). Firearms engineer/marksman; a second Trap-flavored
    # encounter alongside Triv, diversifying that pool.
    # ------------------------------------------------------------------
    {
        "id": "caliper_range",
        "name": "Caliper",
        "image_url": "https://cdn.discordapp.com/attachments/1527136925348135023/1527144237332697220/ii7xLgAAAAZJREFUAwAp0ICWxD4Q0AAAAABJRU5ErkJggg.png?ex=6a5ae8e7&is=6a599767&hm=7b8fdee6b9391ccaffd228b6eaf7ada3695c54522788f758d0d99bdc7ed54073&",
        "room_types": ["trap"],
        "intros": [
            "A trip-wire snaps taut behind you -- and Caliper steps out from cover, rifle already raised. \"Didn't expect company. Let's see what you've got.\"",
            "Caliper has turned this stretch of corridor into a firing range, and you just became the target.",
            "\"Nobody sneaks up on me,\" Caliper says, not even looking up from stripping down a blaster. \"Guess we're doing this.\"",
        ],
        "choices": [
            {
                "id": "dodge",
                "label": "🌀 Try to dodge past",
                "description": "Live to explore another floor.",
                "action": "risk",
                "style": "secondary",
                "success_chance": 0.6,
                "success_text": "You weave past him before he can line up a real shot.",
                "on_success": {"gain": {"gold": [19, 38]}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
                "fail_text": "Caliper doesn't miss. You take a graze and drop something on your way past.",
                "on_fail": {"loss": {"material_tier": 0, "amount": [3, 8]}, "hp_damage_percent": 8},
            },
            {
                "id": "rush_him",
                "label": "🏃 Rush him before he can aim",
                "description": "Close the distance fast.",
                "action": "risk",
                "style": "danger",
                "success_chance": 0.4,
                "success_text": "You close the distance fast enough to matter -- Caliper concedes the round and tosses you his spare parts.",
                "on_success": {"gain": {"material_tier": 0, "amount": [4, 30], "gold": [25, 44]}, "bonus": {"chance": 0.132, "gain": {"lootbox": "common"}}},
                "fail_text": "Caliper's aim is exactly as good as his reputation says.",
                "on_fail": {"loss": {"gold": [5, 15]}, "hp_damage_percent": 18},
            },
            {
                "id": "outshoot",
                "label": "🎯 Challenge him to a real shootout",
                "description": "Bold. Possibly stupid.",
                "action": "risk",
                "style": "danger",
                "success_chance": 0.2,
                "success_text": "Somehow, you out-shoot one of the best marksmen in the Wastelands. He hands over his gear out of pure respect.",
                "on_success": {"gain": {"material_tier": 1, "amount": [10, 30], "gold": [38, 69], "reroll_tokens": [1,2]}, "bonus": {"chance": 0.12, "gain": {"lootbox": "uncommon"}}},
                "fail_text": "You did not, in fact, out-shoot Caliper.",
                "on_fail": {"loss": {"material_tier": 0, "amount": [8, 15]}, "hp_damage_percent": 22},
            },
        ],
    },
    # ------------------------------------------------------------------
    # Xero -- new, drawn from Cascade_Classified_Files.txt (File H-009).
    # H-Army explosives specialist; a third Trap-flavored encounter.
    # ------------------------------------------------------------------
    {
        "id": "xero_minefield",
        "name": "Xero",
        "image_url": "https://cdn.discordapp.com/attachments/1527136925348135023/1527145720015098017/3yoEloAAAAGSURBVAMAdWp6JqgeYbcAAAAASUVORK5CYII.png?ex=6a5aea48&is=6a5998c8&hm=8b494edb67f068806a03e4b9b9909e2951a41a008c9b45d6cd666a27513e6229&",
        "room_types": ["trap"],
        "intros": [
            "The ground ahead is studded with half-buried charges. Xero crouches nearby, utterly unbothered. \"Wrong path,\" he says flatly.",
            "Xero doesn't say much. He just gestures at the minefield between you and where you need to go.",
            "You smell scorched earth before you see him -- Xero, surrounded by more explosives than any one person should carry.",
        ],
        "choices": [
            {
                "id": "pick_path",
                "label": "🧭 Pick your way through carefully",
                "description": "Slow and careful.",
                "action": "risk",
                "style": "primary",
                "success_chance": 0.65,
                "success_text": "You thread the charges without incident. Xero almost looks impressed.",
                "on_success": {"gain": {"gold": [22, 44], "material_tier": 0, "amount": [11, 22]}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
                "fail_text": "One charge goes off closer than you'd like.",
                "on_fail": {"hp_damage_percent": 14, "loss": {"material_tier": 0, "amount": [4, 10]}},
            },
            {
                "id": "sprint_through",
                "label": "⚡ Sprint straight through",
                "description": "Reckless. Fast, if it works.",
                "action": "risk",
                "style": "danger",
                "success_chance": 0.4,
                "success_text": "Reckless, but it works -- you clear the field and grab a stash of his spare charges on the way.",
                "on_success": {"gain": {"material_tier": 1, "amount": [4, 27], "gold": [19, 38], "reroll_tokens": [1,2]}, "bonus": {"chance": 0.112, "gain": {"shards": 1}}},
                "fail_text": "You did not, in fact, clear the field.",
                "on_fail": {"hp_damage_percent": 25, "loss": {"material_tier": 0, "amount": [10, 20]}},
            },
            {
                "id": "talk_him_down",
                "label": "🗣️ Try to talk him down",
                "description": "He's reclusive, not deaf.",
                "action": "risk",
                "style": "secondary",
                "success_chance": 0.55,
                "success_text": "Xero, of all people, decides you're not worth the charges. He clears a path and even tosses you supplies.",
                "on_success": {"gain": {"gold": [31, 56]}, "bonus": {"chance": 0.075, "gain": {"lootbox": "uncommon"}}},
                "fail_text": "Xero doesn't respond well to conversation. He detonates a charge just to make a point.",
                "on_fail": {"hp_damage_percent": 16},
            },
        ],
    },
    # ------------------------------------------------------------------
    # H-Henchmen -- new, from Cascade_Classified_Files.txt (File H-007 /
    # BE-008, Class D-09, the weakest class in the entire enemy roster).
    # The low-reward Trap encounter, contrasted against Corrupted Bli
    # (Class S-05, the single highest-risk/highest-reward Trap here).
    # ------------------------------------------------------------------
    {
        "id": "h_henchmen_patrol",
        "name": "H-Henchmen",
        "image_url": "https://cdn.discordapp.com/attachments/1527136925348135023/1527151081203830925/lrpAAAABklEQVQDADdKIxQC4AB8AAAAAElFTkSuQmCC.png?ex=6a5aef46&is=6a599dc6&hm=dff119e44543e5903ad395dcf2751e71dcb0945cacba8f91f31aa79f12733a67&",
        "room_types": ["trap"],
        "intros": [
            "A pair of H-Henchmen are arguing about whose turn it is to patrol. Neither one has noticed you yet.",
            "An H-Henchman fumbles his pistol, drops it, picks it up, and only then notices you standing there.",
            "H-Henchmen patrol here in a loose formation that generously could be called \"a formation.\"",
        ],
        "choices": [
            {
                "id": "fight",
                "label": "🥊 Fight them off",
                "description": "Barely worth calling a fight.",
                "action": "risk",
                "style": "primary",
                "success_chance": 0.85,
                "success_text": "Barely a fight. You take their gear before they even finish reacting.",
                "on_success": {"gain": {"gold": [12, 25], "material_tier": 0, "amount": [7, 16]}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
                "fail_text": "Somehow, you still manage to trip over your own feet.",
                "on_fail": {"hp_damage_percent": 5},
            },
            {
                "id": "sneak_past",
                "label": "🐾 Sneak past instead",
                "description": "They're not exactly alert.",
                "action": "risk",
                "style": "secondary",
                "success_chance": 0.75,
                "success_text": "They're too busy arguing to notice you at all.",
                "on_success": {"gain": {"gold": [6, 15]}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
                "fail_text": "You knock something over. Fortunately, H-Henchmen aren't known for reflexes.",
                "on_fail": {"hp_damage_percent": 5},
            },
        ],
    },
    # ------------------------------------------------------------------
    # Corrupted Bli -- new, from Cascade_Classified_Files.txt (File
    # H-005 / BE-011, Class S-05). The high-reward Trap encounter.
    # ------------------------------------------------------------------
    {
        "id": "corrupted_bli",
        "name": "Corrupted Bli",
        "image_url": "https://cdn.discordapp.com/attachments/1527136925348135023/1527151489405947986/AAAAAZJREFUAwDGeSgtpuZ7tAAAAABJRU5ErkJggg.png?ex=6a5aefa8&is=6a599e28&hm=c2d6cc2fba9d6e1a1bca206bc1e2a511a802c8f797a437649256bc0364d26ddc&",
        "room_types": ["trap"],
        "intros": [
            "The temperature drops sharply. Something with too many mismatched parts is standing perfectly still at the end of the corridor -- until it isn't.",
            "Corrupted Bli doesn't speak. It doesn't need to. It's already locked onto you.",
            "Ice crystals form on every surface Bli has touched. It hasn't touched you yet.",
        ],
        "choices": [
            {
                "id": "hold_ground",
                "label": "🛡️ Hold your ground and parry",
                "description": "Extremely dangerous. Extremely rewarding.",
                "action": "risk",
                "style": "danger",
                "success_chance": 0.25,
                "success_text": "Against everything you know about Bli, you weather it and come away with salvage no one else has gotten close enough to take.",
                "on_success": {"gain": {"material_tier": 2, "amount": [14, 27], "gold": [75, 138], "reroll_tokens": [7, 15]}, "bonus": {"chance": 0.1, "gain": {"lootbox": "epic"}}},
                "fail_text": "Bli does not miss twice.",
                "on_fail": {"hp_damage_percent": 30, "loss": {"material_tier": 0, "amount": [10, 20]}},
            },
            {
                "id": "flee",
                "label": "🏃 Run. Immediately.",
                "description": "The sensible option.",
                "action": "risk",
                "style": "secondary",
                "success_chance": 0.6,
                "success_text": "You get clear before it fully locks on. Not glamorous, but you're alive.",
                "on_success": {"gain": {"gold": [12, 25]}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
                "fail_text": "It's faster than you. It's faster than everything.",
                "on_fail": {"hp_damage_percent": 20},
            },
        ],
    },
    # ==================================================================
    # HIGH-CONSEQUENCE encounters -- the sharpest end of the risk curve.
    # Big hp_damage_percent on failure (30%+), and -- new for this
    # batch -- an actual Shard *loss* on the worst outcomes. Shards
    # otherwise only ever move in the gain direction (see the docstring
    # above); losing one you already earned is meant to genuinely sting.
    # ==================================================================
    {
        "id": "void_hydra_echo",
        "name": "Void Hydra",
        "image_url": "https://cdn.discordapp.com/attachments/1527136925348135023/1527153478130991144/image.png?ex=6a5af182&is=6a59a002&hm=4440ce7e8d5ac1fcef431a39032584914398732f48cee93c2cf09ffaf9fedeb0&",
        "room_types": ["trap"],
        "intros": [
            "The ground splits. Something enormous and half-buried stirs beneath the ice -- the Void Hydra, or what's left of it, waking up because you got too close.",
            "You feel it before you see it: a presence too large and too wrong to be entirely physical. The Void Hydra doesn't need to move to be terrifying.",
            "Retractable turrets emerge from the snow around you. The Void Hydra was never fully dormant. It was just waiting.",
        ],
        "choices": [
            {
                "id": "exploit_instability",
                "label": "⚡ Exploit its unstable void core",
                "description": "The single riskiest option in the whole roster.",
                "action": "risk",
                "style": "danger",
                "success_chance": 0.2,
                "success_text": "You find the one weak point in its unstable core and it works even better than you hoped. The Hydra collapses back into the ice.",
                "on_success": {"gain": {"material_tier": 3, "amount": [8, 19], "gold": [125, 225], "xp": [46, 80]}, "bonus": {"chance": 0.07, "gain": {"lootbox": "legendary"}}},
                "fail_text": "You hit the core wrong. It retaliates with everything it has -- turrets, drones, all of it. This goes about as badly as it sounds.",
                "on_fail": {"hp_damage_percent": 35, "loss": {"material_tier": 0, "amount": [20, 40], "gold": [15, 30]}},
            },
            {
                "id": "flee",
                "label": "🏃 Run. Now.",
                "description": "The sane option.",
                "action": "risk",
                "style": "secondary",
                "success_chance": 0.55,
                "success_text": "You get clear before it fully surfaces.",
                "on_success": {"gain": {"gold": [12, 25]}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
                "fail_text": "It's faster than something that size has any right to be.",
                "on_fail": {"hp_damage_percent": 20, "loss": {"material_tier": 0, "amount": [8, 15]}},
            },
        ],
    },
    # ------------------------------------------------------------------
    # The Ravaged Convoy -- new, environmental (no single named NPC), a
    # second high-consequence Trap encounter.
    # ------------------------------------------------------------------
    {
        "id": "ravaged_convoy",
        "name": "The Ravaged Convoy",
        "image_url": "https://cdn.discordapp.com/attachments/1527136925348135023/1527153654061203586/image.png?ex=6a5af1ac&is=6a59a02c&hm=74f0c14eebeb0ed28b70e67487f1dd3e888f9039baca9ae64d23c83f0101105d&",
        "room_types": ["trap"],
        "intros": [
            "A supply convoy lies overturned and burning. Whatever hit it might still be nearby.",
            "You find scorched crates and no bodies. Something took whoever was here, and left the cargo behind as bait.",
            "The convoy's alarm is still blaring, faint and dying, powered by a battery that's almost spent.",
        ],
        "choices": [
            {
                "id": "grab_cargo",
                "label": "📦 Grab the cargo and run",
                "description": "Whatever hit this might come back.",
                "action": "risk",
                "style": "danger",
                "success_chance": 0.45,
                "success_text": "You grab everything you can carry and get clear before whatever did this comes back.",
                "on_success": {"gain": {"material_tier": 0, "amount": [12, 47], "gold": [31, 56], "reroll_tokens": [2,4]}, "bonus": {"chance": 0.09, "gain": {"lootbox": "uncommon"}}},
                "fail_text": "Whatever hit this convoy is still here, and it is not happy to see you looting its kill.",
                "on_fail": {"hp_damage_percent": 32, "loss": {"gold": [15, 30], "material_tier": 0, "amount": [10, 20]}},
            },
            {
                "id": "search_carefully",
                "label": "🔍 Search carefully for survivors",
                "description": "Slower, safer, less to gain.",
                "action": "risk",
                "style": "secondary",
                "success_chance": 0.7,
                "success_text": "No survivors, but you do find a supply cache that wasn't touched.",
                "on_success": {"gain": {"material_tier": 0, "amount": [20, 38], "gold": [19, 31]}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
                "fail_text": "You find what's left of a guard. It's not a pleasant discovery, and it costs you time and composure.",
                "on_fail": {"hp_damage_percent": 10},
            },
        ],
    },
]
