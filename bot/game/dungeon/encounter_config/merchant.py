"""
Merchant-room encounters.

Merchant rooms: the shop layer. Choices here are almost always plain
"trade" actions with success_chance 1.0 and flat (non-range) gains -- a
real shop sells you exactly what the price tag says, no scam roll.

See bot/game/dungeon/encounter_config/__init__.py for the shape of an
encounter dict and how choices/outcomes are interpreted.
"""

from __future__ import annotations

MERCHANT_ENCOUNTERS: list[dict] = [
    # ------------------------------------------------------------------
    # Tbnr -- old event was a straightforward shopkeeper (buy materials
    # for rubies). This is the Merchant room's everyday, cheap-goods shop:
    # tier-0/tier-1 bulk materials at low, predictable prices (all trades
    # are success_chance 1.0 -- a real shop doesn't scam you, that's
    # Xender's job). His "Special Stock" line is the one pricier item.
    # ------------------------------------------------------------------
    {
        "id": "tbnr_shop",
        "name": "Tbnr",
        "image_url": "https://cdn.discordapp.com/attachments/704530416475832342/1275726750420303904/TBNRSHOP.png?ex=6a5a8a5f&is=6a5938df&hm=70b39e7c1de745b68664b7bcb9a0a46634183355c628b4a4490a931a00285e88&",
        "room_types": ["merchant"],
        "intros": [
            "Tbnr, a struggling shopkeeper, looks you over. \"Buying, or just looking?\"",
            "Tbnr turns around to check his \"Special Stock\" the moment you walk in.",
            "\"Yes,\" Tbnr says, before you've even asked anything.",
        ],
        "choices": [
            {
                "id": "buy_bulk_basics",
                "label": "🪵 Buy 40 Wood + 40 Stone (15🪙)",
                "description": "Cheap bulk basics, no haggling.",
                "action": "trade",
                "style": "success",
                "cost": {"gold": 15},
                "success_chance": 1.0,
                "success_text": "Tbnr counts out your order without looking up.",
                "on_success": {"gain": {"wood": 40, "stone": 40}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
                "fail_text": "",
                "on_fail": {},
            },
            {
                "id": "buy_metal",
                "label": "⚙️ Buy 25 Metal (20🪙)",
                "description": "Standard stock, standard price.",
                "action": "trade",
                "style": "success",
                "cost": {"gold": 20},
                "success_chance": 1.0,
                "success_text": "\"Good choice,\" Tbnr says, not meaning it.",
                "on_success": {"gain": {"metal": 25}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
                "fail_text": "",
                "on_fail": {},
            },
            {
                "id": "buy_crystal",
                "label": "💎 Buy 25 Crystal (20🪙)",
                "description": "Standard stock, standard price.",
                "action": "trade",
                "style": "success",
                "cost": {"gold": 20},
                "success_chance": 1.0,
                "success_text": "Tbnr slides the crate over without a word.",
                "on_success": {"gain": {"crystal": 25}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
                "fail_text": "",
                "on_fail": {},
            },
            {
                "id": "special_stock",
                "label": "🎁 Browse the \"Special Stock\" (90🪙)",
                "description": "Pricier. Tbnr's cagey about what's actually in it.",
                "action": "trade",
                "style": "primary",
                "cost": {"gold": 90},
                "success_chance": 1.0,
                "success_text": "Tbnr hands it over with a wink you did not ask for.",
                "on_success": {"gain": {"lootbox": "uncommon"}},
                "fail_text": "",
                "on_fail": {},
            },
            {
                "id": "leave",
                "label": "🚪 Leave the shop",
                "description": "",
                "action": "leave",
                "style": "secondary",
                "text": "You decide to leave the shopkeeper and continue your journey.",
            },
        ],
    },
    # ------------------------------------------------------------------
    # Boss John -- old event was a shop selling gear for rubies. Per
    # docs/WORLD_LORE.md (File X-002), Boss John is Xender's elite
    # assistant who literally "oversees the economy" -- so his shop is
    # the Merchant room's premium counterpart to Tbnr's: tier-2/tier-3
    # materials, rarer lootboxes, and the single most reliable (if
    # expensive) way to convert plain gold into Shards on purpose,
    # rather than hoping for a rare bonus roll elsewhere.
    # ------------------------------------------------------------------
    {
        "id": "boss_john_shop",
        "name": "Boss John",
        "image_url": "https://cdn.discordapp.com/attachments/1135808718492139521/1286202437346000896/BOSSJOHN.png?ex=6a5b13dd&is=6a59c25d&hm=ac8866a4757828278066d7a574154f6a430e762d27f552058bbde19131fa5e52&",
        "room_types": ["merchant"],
        "intros": [
            "Boss John gives you a big smile. \"No matter who COME to my STORE, I make SURE do everything I can to HELP.\"",
            "\"If you need SUPPLIES, I GOT YOU!\" Boss John announces, to no one in particular.",
            "\"Have you SEE Ultra M?\" Boss John asks. \"I have not see him... AM WORRY...\" He shakes it off and gets back to business.",
        ],
        "choices": [
            {
                "id": "buy_xendium",
                "label": "🔷 Buy 6 Xendium (50🪙)",
                "description": "Premium stock, premium price.",
                "action": "trade",
                "style": "success",
                "cost": {"gold": 50},
                "success_chance": 1.0,
                "success_text": "Boss John counts it out personally. \"ONLY the BEST for you!\"",
                "on_success": {"gain": {"xendium": 6}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
                "fail_text": "",
                "on_fail": {},
            },
            {
                "id": "buy_permafrost",
                "label": "🧊 Buy 6 Permafrost Ore (50🪙)",
                "description": "Premium stock, premium price.",
                "action": "trade",
                "style": "success",
                "cost": {"gold": 50},
                "success_chance": 1.0,
                "success_text": "\"GENUINE Glacier 15 stock!\" Boss John insists.",
                "on_success": {"gain": {"permafrost_ore": 6}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
                "fail_text": "",
                "on_fail": {},
            },
            {
                "id": "buy_void",
                "label": "🕳️ \"Acquire\" 3 Void (250🪙)",
                "description": "Very expensive. Don't ask where it's from.",
                "action": "trade",
                "style": "primary",
                "cost": {"gold": 250},
                "success_chance": 1.0,
                "success_text": "Boss John lowers his voice, just this once. \"Don't tell Xender.\"",
                "on_success": {"gain": {"void": 3}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
                "fail_text": "",
                "on_fail": {},
            },
            {
                "id": "buy_rare_lootbox",
                "label": "🎁 Buy a Rare Lootbox (200🪙)",
                "description": "Steep, but guaranteed.",
                "action": "trade",
                "style": "primary",
                "cost": {"gold": 200},
                "success_chance": 1.0,
                "success_text": "\"You will NOT regret this!\" Boss John says, probably lying.",
                "on_success": {"gain": {"lootbox": "rare"}},
                "fail_text": "",
                "on_fail": {},
            },
            {
                "id": "buy_shard",
                "label": "✨ Buy 10 Shards (1500🪙)",
                "description": "The single most expensive line item in his store.",
                "action": "trade",
                "style": "danger",
                "cost": {"gold": 1500},
                "success_chance": 1.0,
                "success_text": "Boss John produces it from somewhere you'd rather not think about. \"A RARE treasure, for a RARE customer.\"",
                "on_success": {"gain": {"shards": 10}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
                "fail_text": "",
                "on_fail": {},
            },
            {
                "id": "leave",
                "label": "🚪 Leave the shop",
                "description": "",
                "action": "leave",
                "style": "secondary",
                "text": "You decide to leave Boss John's shop and continue on your journey.",
            },
        ],
    },
    # ------------------------------------------------------------------
    # Bee Jee -- new, from Cascade_Classified_Files.txt (File C-011).
    # Ex-Ocellios weapons crafter; a third Merchant option.
    # ------------------------------------------------------------------
    {
        "id": "bee_jee_shop",
        "name": "Bee Jee",
        "image_url": "https://cdn.discordapp.com/attachments/1527136925348135023/1527156995898081370/avsvsvs_1.png?ex=6a5af4c9&is=6a59a349&hm=1d24a7f40f70f947f1ad099fcf1adb62d67d988f54b19bd331e06aeeacddba9f&",
        "room_types": ["merchant"],
        "intros": [
            "Bee Jee has her goggles flipped down, examining a rifle scope with more attention than the rifle probably deserves. \"Oh -- customer. What do you need?\"",
            "\"I don't do combat,\" Bee Jee says, \"but I make sure the people who do, do it better.\"",
            "Bee Jee is running numbers on a betting slip from the Waste Colosseum when you walk up. She pockets it fast.",
        ],
        "choices": [
            {
                "id": "buy_augment",
                "label": "🔫 Commission a weapon augment (70⚙️ 30🪙)",
                "description": "Quality's the workshop's call.",
                "action": "gamble",
                "style": "success",
                "cost": {"metal": 70, "gold": 30},
                # A COMMISSION HAS A FLOOR.
                #
                # This used to grant {"item": "natural"} -- a fresh
                # weighted roll, which lands Common about 42% of the time
                # (see rarity_config.RARITY_WEIGHTS). Paying a smith 70
                # Metal and 30 gold and walking away with a Common is not
                # a bad roll, it's a bad trade, and it happened more often
                # than any other outcome.
                #
                # A gamble with an explicit rarity per tier gives the
                # thing a commission should have: a guaranteed floor you
                # can plan around, plus real upside. Same mechanism the
                # High Roller shop uses to sell certainty.
                "tiers": [
                    {"chance": 0.12, "text": "She outdoes herself. What she hands back is genuinely exceptional.",
                     "outcome": {"gain": {"item": "legendary", "reroll_tokens": [5, 10]}}},
                    {"chance": 0.33, "text": "Precise, over-engineered, and well worth the metal.",
                     "outcome": {"gain": {"item": "epic", "reroll_tokens": [5, 10]}}},
                    {"chance": 0.55, "text": "Solid work, delivered on time. Exactly what you paid for.",
                     "outcome": {"gain": {"item": "rare", "reroll_tokens": [5, 10]}}},
                ],
            },
            {
                "id": "buy_crystal",
                "label": "💎 Buy 30 Crystal (25🪙)",
                "description": "Standard stock, standard price.",
                "action": "trade",
                "style": "success",
                "cost": {"gold": 25},
                "success_chance": 1.0,
                "success_text": "\"Good stock today,\" she says, counting it out.",
                "on_success": {"gain": {"crystal": 30}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
                "fail_text": "",
                "on_fail": {},
            },
            {
                "id": "leave",
                "label": "🚪 Leave her to her work",
                "description": "",
                "action": "leave",
                "style": "secondary",
                "text": "You decide to leave Bee Jee to her work and continue your journey.",
            },
        ],
    },
    # ------------------------------------------------------------------
    # The Colosseum Bookie -- new. The "High Roller" shop: unlike every
    # other merchant (Tbnr/Boss John/Bee Jee), which sell fixed goods at
    # fixed prices, this one sells GUARANTEED item rarity, at steep
    # gold prices that scale hard with the rarity. rarity_override in
    # LootGenerator.generate_item always wins over a region's
    # max_item_rarity cap (see _apply_gain's "item" handling), so this
    # is a genuine way to buy your way to better gear with plain gold --
    # a real gold sink for players sitting on a large stockpile, not a
    # chance at anything. Named after the Waste Colosseum betting scene
    # Bee Jee's file also references.
    # ------------------------------------------------------------------
    {
        "id": "high_roller_shop",
        "name": "The Colosseum Bookie",
        "image_url": "https://cdn.discordapp.com/attachments/1527136925348135023/1527157780522205294/image.png?ex=6a5af584&is=6a59a404&hm=f57993b443aba0573e1bfb6035edd41e39ad5ea08850d1cddaf9bb9a2cf30b87&",
        "room_types": ["merchant"],
        "intros": [
            "A figure in an expensive coat has set up shop here, flanked by two very large, very quiet men. \"Word is you've got coin to burn,\" they say. \"I deal in the good stuff. For the right price.\"",
            "\"Everyone's got a price where they stop asking questions,\" the Bookie says, gesturing at a case of gear that definitely wasn't acquired legally. \"What's yours?\"",
            "The Colosseum Bookie doesn't do small talk, and doesn't do small purchases either. \"You're either here to spend real money, or you're wasting my time.\"",
        ],
        "choices": [
            {
                "id": "buy_uncommon",
                "label": "🎲 Buy a guaranteed Uncommon item (99🪙)",
                "description": "The entry price for doing business here.",
                "action": "trade",
                "style": "success",
                "cost": {"gold": 99},
                "success_chance": 1.0,
                "success_text": "The Bookie doesn't even blink. \"Pleasure doing business.\"",
                "on_success": {"gain": {"item": "uncommon"}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
                "fail_text": "",
                "on_fail": {},
            },
            {
                "id": "buy_rare",
                "label": "💎 Buy a guaranteed Rare item (249🪙)",
                "description": "No chance involved. You pay, you get.",
                "action": "trade",
                "style": "success",
                "cost": {"gold": 249},
                "success_chance": 1.0,
                "success_text": "\"Good taste,\" the Bookie says, sliding the case over.",
                "on_success": {"gain": {"item": "rare"}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
                "fail_text": "",
                "on_fail": {},
            },
            {
                "id": "buy_epic",
                "label": "🔥 Buy a guaranteed Epic item (599🪙)",
                "description": "Now we're talking real money.",
                "action": "trade",
                "style": "primary",
                "cost": {"gold": 599},
                "success_chance": 1.0,
                "success_text": "The Bookie actually smiles. \"Now THAT'S a customer.\"",
                "on_success": {"gain": {"item": "epic"}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
                "fail_text": "",
                "on_fail": {},
            },
            {
                "id": "buy_legendary",
                "label": "👑 Buy a guaranteed Legendary item (1499🪙)",
                "description": "The kind of purchase that gets remembered.",
                "action": "trade",
                "style": "primary",
                "cost": {"gold": 1499},
                "success_chance": 1.0,
                "success_text": "Even the bodyguards look impressed. \"Don't spend it all in one place,\" the Bookie says, handing it over anyway.",
                "on_success": {"gain": {"item": "legendary"}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
                "fail_text": "",
                "on_fail": {},
            },
            {
                "id": "buy_mythic",
                "label": "🌌 Buy a guaranteed Mythic item (2999🪙)",
                "description": "Absurd. Also, available.",
                "action": "trade",
                "style": "danger",
                "cost": {"gold": 2999},
                "success_chance": 1.0,
                "success_text": "The Bookie goes quiet for a moment. \"...Alright. Didn't think anyone actually had this much.\"",
                "on_success": {"gain": {"item": "mythic"}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
                "fail_text": "",
                "on_fail": {},
            },
            {
                "id": "leave",
                "label": "🚪 Leave; you're not that rich",
                "description": "",
                "action": "leave",
                "style": "secondary",
                "text": "You decide you're not quite that rich yet, and leave.",
            },
        ],
    },
    # ------------------------------------------------------------------
    # Josh's Betting Table -- new MERCHANT encounter. Straight
    # double-or-nothing: pay a stake, 50% chance to walk away with
    # double, 50% chance it's just gone. The data schema here is choice
    # buttons, not a free-text amount prompt, so "varying amounts" is
    # expressed as several fixed stake tiers (small/medium/large/
    # everything) rather than a single arbitrary-amount bet -- if a
    # true numeric bet input gets added to the interpreter later, this
    # is the encounter to wire it into. All four options use identical
    # 50/50 odds; only the stake and payout scale.
    # ------------------------------------------------------------------
    {
        "id": "josh_betting_table",
        "name": "Josh",
        "image_url": "https://cdn.discordapp.com/attachments/1527136925348135023/1527175408674406471/image.png?ex=6a5b05ee&is=6a59b46e&hm=d673ddaae779700882211f08b1082c33d769663d96e0ed536bb031c8f4e3fdc7&",
        "room_types": ["merchant"],
        "intros": [
            "Josh has set up a rickety table with a hand-painted sign: \"DOUBLE OR NOTHING, 50/50, TOTALLY FAIR.\"",
            "\"Coin flip,\" Josh says, already flipping one. \"Heads you double it, tails I keep it. Simple.\"",
            "Josh grins at you from behind his betting table. \"I've only lost track of the count a *few* times today.\"",
        ],
        "choices": [
            {
                "id": "bet_small",
                "label": "🪙 Bet 25 gold",
                "description": "Low stakes, 50/50 odds to double it.",
                "action": "trade",
                "style": "primary",
                "cost": {"gold": 25},
                "success_chance": 0.5,
                "success_text": "The coin lands your way. Josh grumbles and doubles you up.",
                "on_success": {"gain": {"gold": 50}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
                "fail_text": "Tails. Josh pockets your gold with a completely straight face.",
                "on_fail": {},
            },
            {
                "id": "bet_medium",
                "label": "🪙🪙 Bet 75 gold",
                "description": "Medium stakes, same 50/50 odds.",
                "action": "trade",
                "style": "primary",
                "cost": {"gold": 75},
                "success_chance": 0.5,
                "success_text": "Your call lands. Josh hands over double, visibly pained about it.",
                "on_success": {"gain": {"gold": 150}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
                "fail_text": "Josh flips it, catches it, and doesn't even show you before sweeping your gold away.",
                "on_fail": {},
            },
            {
                "id": "bet_large",
                "label": "🪙🪙🪙 Bet 200 gold",
                "description": "High stakes, same 50/50 odds.",
                "action": "trade",
                "style": "danger",
                "cost": {"gold": 200},
                "success_chance": 0.5,
                "success_text": "\"...Fine. FINE.\" Josh doubles you up, looking personally betrayed by the coin.",
                "on_success": {"gain": {"gold": 400}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
                "fail_text": "Josh lets out a whoop of victory that is deeply unprofessional for a man running a betting table.",
                "on_fail": {},
            },
            {
                "id": "bet_all_in",
                "label": "🎰 Go all in (500 gold)",
                "description": "Josh's max stake. Same 50/50 odds, biggest swing.",
                "action": "trade",
                "style": "danger",
                "cost": {"gold": 500},
                "success_chance": 0.5,
                "success_text": "Josh stares at the coin like it personally wronged him and slides a thousand gold across the table.",
                "on_success": {"gain": {"gold": 1000}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
                "fail_text": "\"Better luck next time,\" Josh says, already counting your gold into his own pocket.",
                "on_fail": {},
            },
            {
                "id": "leave",
                "label": "🚪 Walk away from the table",
                "description": "",
                "action": "leave",
                "style": "secondary",
                "text": "You decide you know better than to bet against Josh and walk away from the table.",
            },
        ],
    },
]
