"""
Shrine-room encounters.

Shrine rooms: offerings, blessings, and the entities that grant them.

See bot/game/dungeon/encounter_config/__init__.py for the shape of an
encounter dict and how choices/outcomes are interpreted.
"""

from __future__ import annotations

SHRINE_ENCOUNTERS: list[dict] = [
    # ------------------------------------------------------------------
    # The Humming Shard -- brand new, giving SHRINE a dedicated
    # interactive option instead of just the flat ROOM_FLAVOR text.
    # ------------------------------------------------------------------
    {
        "id": "humming_shard",
        "name": "The Humming Shard",
        "image_url": "https://cdn.discordapp.com/attachments/1527136925348135023/1527142359094136883/image.png?ex=6a5ae727&is=6a5995a7&hm=953f2e3e88c7d8350fc33c62bf03df32453fb0c6588aa66414ec7fc651aa071d&",
        "room_types": ["shrine"],
        "intros": [
            "A stable shard of Void matter hums quietly in a hollow, casting faint light on the walls around it.",
            "The shard's hum rises in pitch as you get closer, like it's noticed you.",
            "Someone built a small stone ring around this shard, like an altar. Long before you got here.",
        ],
        "choices": [
            {
                "id": "draw_carefully",
                "label": "🕯️ Draw power carefully",
                "description": "A small, stable blessing.",
                "action": "risk",
                "style": "primary",
                "success_chance": 0.85,
                "success_text": "The shard offers a small, stable blessing.",
                "on_success": {"gain": {"gold": [25, 50], "material_tier": 1, "amount": [5, 14]}, "bonus": {"chance": 0.08, "gain": {"shards": [1,3]}}},
                "fail_text": "The shard flickers and gives up nothing this time.",
                "on_fail": {},
            },
            {
                "id": "draw_deeply",
                "label": "🔥 Draw deeply",
                "description": "Much more power, if you can handle it.",
                "action": "risk",
                "style": "danger",
                "success_chance": 0.5,
                "success_text": "The shard channels far more than expected -- you feel it in your bones.",
                "on_success": {"gain": {"material_tier": 2, "amount": [4, 11], "gold": [44, 81]}, "bonus": {"chance": 0.084, "gain": {"lootbox": "rare"}}},
                "fail_text": "The shard backlashes hard.",
                "on_fail": {"hp_damage_percent": 15},
            },
            {
                "id": "offer_materials",
                "label": "💎 Offer 15 Crystal to stabilize it",
                "description": "A generous offering, generously repaid.",
                "action": "trade",
                "style": "success",
                "cost": {"crystal": 15},
                "success_chance": 0.95,
                "success_text": "The shard steadies and rewards your offering generously.",
                "on_success": {"gain": {"material_tier": 2, "amount": [7, 14], "gold": [19, 38], "reroll_tokens": [1,2]}, "bonus": {"chance": 0.128, "gain": {"shards": [2,4]}}},
                "fail_text": "The shard rejects the offering, unchanged.",
                "on_fail": {},
            },
            {
                "id": "leave",
                "label": "🚪 Leave the shard undisturbed",
                "description": "",
                "action": "leave",
                "style": "secondary",
                "text": "You decide not to disturb it, and continue on.",
            },
        ],
    },
    # ------------------------------------------------------------------
    # Broskm -- new, drawn from Cascade_Classified_Files.txt (File H-002).
    # Eidolon void researcher; his old lab makes for a Shrine-flavored
    # encounter (mystical-but-dangerous, same as the Humming Shard).
    # ------------------------------------------------------------------
    {
        "id": "broskm_voidlab",
        "name": "Broskm's Voidlab",
        "image_url": "https://cdn.discordapp.com/attachments/1527136925348135023/1527143956654325800/download_2.png?ex=6a5ae8a4&is=6a599724&hm=9e804a29b73bce8957e404c1c1a76852f82016108689f57d0e1192be8e9431dd&",
        "room_types": ["shrine"],
        "intros": [
            "A makeshift lab is bolted into the rock here -- cables snake toward a humming void containment ring. A nameplate reads BROSKM, though the handwriting looks rushed.",
            "Broskm's old research notes are scattered everywhere, mid-experiment. Something in the containment ring is still active.",
            "You find a half-finished Voidwarp rig, abandoned in a hurry. Whatever Broskm was working on here, he didn't get to finish it.",
        ],
        "choices": [
            {
                "id": "study_notes",
                "label": "📓 Study the research notes",
                "description": "Dense, but might be useful.",
                "action": "risk",
                "style": "primary",
                "success_chance": 0.7,
                "success_text": "The notes are dense but useful -- you walk away with a working grasp of some of his methods.",
                "on_success": {"gain": {"material_tier": 1, "amount": [6, 20], "gold": [19, 38]}, "bonus": {"chance": 0.08, "gain": {"shards": 1}}},
                "fail_text": "The notes are written in a private shorthand you can't parse. You get nothing for your trouble.",
                "on_fail": {},
            },
            {
                "id": "tap_containment",
                "label": "⚡ Tap the containment ring",
                "description": "Void energy, right there for the taking.",
                "action": "risk",
                "style": "danger",
                "success_chance": 0.45,
                "success_text": "You draw a controlled trickle of void energy before the ring destabilizes -- more than worth the risk.",
                "on_success": {"gain": {"material_tier": 2, "amount": [5, 14], "gold": [25, 50]}, "bonus": {"chance": 0.098, "gain": {"lootbox": "rare"}}},
                "fail_text": "The ring destabilizes hard. Whatever Broskm was containing, it does not want to be touched.",
                "on_fail": {"hp_damage_percent": 18},
            },
            {
                "id": "offer_materials",
                "label": "💎 Feed the rig 20 Crystal to stabilize it",
                "description": "Give it what it wants and see what comes out.",
                "action": "trade",
                "style": "success",
                "cost": {"crystal": 20},
                "success_chance": 0.92,
                "success_text": "The rig stabilizes and spits out a refined sample.",
                "on_success": {"gain": {"material_tier": 2, "amount": [8, 16], "gold": [19, 31], "reroll_tokens": [1,2]}, "bonus": {"chance": 0.096, "gain": {"shards": 1}}},
                "fail_text": "The rig rejects the offering and shuts down cold.",
                "on_fail": {},
            },
            {
                "id": "leave",
                "label": "🚪 Leave the lab undisturbed",
                "description": "",
                "action": "leave",
                "style": "secondary",
                "text": "Whatever Broskm was doing here, you decide it's not worth finding out. You leave the lab undisturbed.",
            },
        ],
    },
    # ==================================================================
    # HIGH-REWARD encounters -- deliberately rare and/or high-stakes.
    # These sit at the top of their room type's reward curve: bigger
    # costs or much lower odds, in exchange for payouts well above that
    # pool's usual range (tier-3 materials, Epic/Legendary lootboxes,
    # much larger gold swings). Meant to feel like genuine standout
    # moments, not something to expect on a normal run.
    # ==================================================================
    {
        "id": "stubby_sighting",
        "name": "Stubby",
        "image_url": "https://cdn.discordapp.com/attachments/1527136925348135023/1527151252876693534/TydX9AkAdIAAAAASUVORK5CYII.png?ex=6a5aef6f&is=6a599def&hm=979e544cb2040d36274ed33f840086ffb9ac4877ac1a4dbf9c15456002cebd75&",
        "room_types": ["shrine"],
        "intros": [
            "A figure watches you from an impossible distance, features never quite resolving no matter how you look. You get the distinct feeling you are being studied, not seen.",
            "Something about this place is being observed. You don't see anyone. You still feel it.",
            "A voice you can't quite place says something about \"the vessel\" before the feeling passes, and you're alone again.",
        ],
        "choices": [
            {
                "id": "approach",
                "label": "🕯️ Approach, slowly",
                "description": "Almost certainly a bad idea.",
                "action": "risk",
                "style": "danger",
                "success_chance": 0.06,
                "success_text": "Whatever -- whoever -- that was, it leaves something behind before vanishing entirely. Something that shouldn't exist yet does.",
                "on_success": {"gain": {"material_tier": 3, "amount": [4, 11], "gold": [188, 350], "reroll_tokens": [10, 20]}, "bonus": {"chance": 0.07, "gain": {"lootbox": "legendary"}}},
                "fail_text": "Whatever it was loses interest, and so does whatever it left drifting near you.",
                "on_fail": {},
            },
            {
                "id": "leave",
                "label": "🚪 Leave, quickly",
                "description": "",
                "action": "leave",
                "style": "secondary",
                "text": "You decide you'd rather not find out what Stubby wants with \"the vessel,\" and leave quickly.",
            },
        ],
    },
]
