"""
Story-room encounters.

Character run-ins: the bulk of the original explore.js cast, and the
default flavor for a Story room.

See bot/game/dungeon/encounter_config/__init__.py for the shape of an
encounter dict and how choices/outcomes are interpreted.
"""

from __future__ import annotations

STORY_ENCOUNTERS: list[dict] = [
    # ------------------------------------------------------------------
    # Josh -- the Cascade-verse's resident degenerate gambler. Old event
    # had an ambush + two barter-for-wood options; kept the same shape.
    # ------------------------------------------------------------------
    {
        "id": "josh_campfire",
        "name": "Josh",
        "image_url": "https://cdn.discordapp.com/attachments/704530416475832342/1275352717501665332/JOSHCAMPFIRE_1.png?ex=6a5a7f86&is=6a592e06&hm=2bf23a4a77ceaf8db4edcf5f8c2805c8b84478b401cce0c4848cdc31ac9c01ae&",
        "room_types": ["story"],
        "intros": [
            "You find Josh hunched by a dying campfire, counting a stack of chips that clearly aren't his. He hasn't noticed you.",
            "Josh is sniffling by the fire, muttering something about \"one more hand\" and \"it'll turn around.\"",
            "Josh looks up with the calm, too-calm smile of a man who just lost everything and doesn't know it yet.",
        ],
        "choices": [
            {
                "id": "ambush",
                "label": "🗡️ Ambush Josh",
                "description": "Jump him before he notices you.",
                "action": "risk",
                "style": "danger",
                "success_chance": 0.55,
                "success_text": "You catch Josh completely off guard -- he bolts, dropping a fat stack of gold on his way out.",
                "on_success": {"gain": {"gold": [31, 56]}, "bonus": {"chance": 0.08, "gain": {"shards": [1,3]}}},
                "fail_text": "Josh recovers fast and shoves you into the ash. He grabs your supplies and runs.",
                "on_fail": {"loss": {"material_tier": 0, "amount": [3, 8]}},
            },
            {
                "id": "barter_gold",
                "label": "🪙 Pay 12 gold for \"a sure thing\"",
                "description": "Josh swears this tip on a supply shipment is worth every coin.",
                "action": "trade",
                "style": "primary",
                "cost": {"gold": 12},
                "success_chance": 0.55,
                "success_text": "Somehow, the tip was real. You cash in before word gets around.",
                "on_success": {"gain": {"gold": [62, 112]}, "bonus": {"chance": 0.11, "gain": {"lootbox": "common"}}},
                "fail_text": "The tip was garbage, obviously. Josh shrugs: \"worth a shot, right?\"",
                "on_fail": {},
            },
            {
                "id": "stake_materials",
                "label": "🪨 Stake 10 Stone on a hand of cards",
                "description": "Josh is always up for a game, even one paid in materials.",
                "action": "trade",
                "style": "primary",
                "cost": {"stone": 10},
                "success_chance": 0.45,
                "success_text": "You actually win. Josh grumbles and pays out from his own stash.",
                "on_success": {"gain": {"material_tier": 0, "amount": [40, 74]}, "bonus": {"chance": 0.084, "gain": {"material_tier": 1, "amount": [3, 5]}}},
                "fail_text": "You lose. This is Josh we're talking about.",
                "on_fail": {},
            },
            {
                "id": "leave",
                "label": "🚪 Leave him to it",
                "description": "Josh's problems are Josh's problems.",
                "action": "leave",
                "style": "secondary",
                "text": "You decide Josh's problems are Josh's problems, and keep moving.",
            },
        ],
    },
    # ------------------------------------------------------------------
    # Dolphe -- old event was a homeless-beggar donation gauntlet. Kept
    # that shape but nodded lightly at his actual in-lore identity (Team
    # Cascade's founder) without hard-contradicting it.
    # ------------------------------------------------------------------
    {
        "id": "dolphe_drifter",
        "name": "Dolphe",
        "image_url": "https://cdn.discordapp.com/attachments/704530416475832342/1275348918305161216/HOMELESSDOLPHE.png?ex=6a5a7bfc&is=6a592a7c&hm=b81599e7af4fae9fa48c93d54c0e9cf8f0cca3ccdb975616828884cf70fb3b6b&",
        "room_types": ["story"],
        "intros": [
            "A gaunt man huddled against a collapsed wall calls himself Dolphe -- though he insists he's not THAT Dolphe. He's shivering.",
            "This \"Dolphe\" looks like he hasn't eaten in days. He eyes your pack hopefully.",
            "The man calling himself Dolphe mutters about a paper he used to run, before laughing bitterly at himself.",
        ],
        "choices": [
            {
                "id": "donate_wood",
                "label": "🪵 Donate 6 Wood",
                "description": "Give up some wood -- he looks like he needs it.",
                "action": "trade",
                "style": "success",
                "cost": {"wood": 6},
                "success_chance": 0.9,
                "success_text": "Dolphe's grip is stronger than it looks -- turns out he had a stash of his own, and shares it back generously.",
                "on_success": {"gain": {"wood": [30, 51]}, "bonus": {"chance": 0.064, "gain": {"shards": [1,3]}}},
                "fail_text": "Dolphe thanks you quietly. He needed it more than you did.",
                "on_fail": {},
            },
            {
                "id": "donate_stone",
                "label": "🪨 Donate 6 Stone",
                "description": "Give up some stone -- he looks like he needs it.",
                "action": "trade",
                "style": "success",
                "cost": {"stone": 6},
                "success_chance": 0.9,
                "success_text": "Dolphe's grip is stronger than it looks -- turns out he had a stash of his own, and shares it back generously.",
                "on_success": {"gain": {"stone": [30, 51]}, "bonus": {"chance": 0.064, "gain": {"shards": [1,3]}}},
                "fail_text": "Dolphe thanks you quietly. He needed it more than you did.",
                "on_fail": {},
            },
            {
                "id": "donate_metal",
                "label": "⚙️ Donate 3 Metal",
                "description": "A rarer donation -- he seems almost embarrassed to take it.",
                "action": "trade",
                "style": "success",
                "cost": {"metal": 3},
                "success_chance": 0.88,
                "success_text": "Dolphe insists on paying you back, and then some.",
                "on_success": {"gain": {"metal": [16, 27]}, "bonus": {"chance": 0.08, "gain": {"shards": [1,3]}}},
                "fail_text": "Dolphe thanks you quietly. He needed it more than you did.",
                "on_fail": {},
            },
            {
                "id": "ignore_him",
                "label": "🙅 Harden your heart and walk past",
                "description": "Not everyone gets helped today.",
                "action": "risk",
                "style": "danger",
                "success_chance": 0.5,
                "success_text": "Dolphe just watches you go, saying nothing -- though you do spot a dropped coin on your way past.",
                "on_success": {"gain": {"gold": [6, 15]}, "bonus": {"chance": 0.088, "gain": {"lootbox": "common"}}},
                "fail_text": "Desperation makes people fast. Dolphe grabs what he can from your pack before you shake him off.",
                "on_fail": {"loss": {"material_tier": 0, "amount": [1, 3]}},
            },
        ],
    },
    # ------------------------------------------------------------------
    # Xender -- shady lottery-runner in the old event, and per
    # docs/WORLD_LORE.md, literally the head of Acatrya in-canon. The
    # scam-artist energy tracks disturbingly well either way.
    # ------------------------------------------------------------------
    {
        "id": "xender_lottery",
        "name": "Xender",
        "image_url": "https://cdn.discordapp.com/attachments/704530416475832342/1275340818382721024/XENDERCRACKPIPE_1.png?ex=6a5a7471&is=6a5922f1&hm=f68bb9cae12b4dd1c7ff4f45e191765b7603259ddfeb294d145b108565f5469a&",
        "room_types": ["story"],
        "intros": [
            "Xender has set up a rickety folding table draped in gold cloth: \"STEP RIGHT UP -- COME BIG, WIN BIG!\" A prize pool glitters in front of him.",
            "\"I need FUNDING,\" Xender hisses, \"for very official Acatrya business. Definitely not a scam.\"",
            "Xender's sign reads \"THIS IS NOT A SCAM\" in every color he owns. You believe him approximately zero percent.",
        ],
        "choices": [
            {
                "id": "honest_lottery",
                "label": "🎟️ Enter the \"NOT A SCAM\" Lottery (10🪙)",
                "description": "Xender promises this one is real.",
                "action": "gamble",
                "style": "primary",
                "cost": {"gold": 10},
                "tiers": [
                    {"chance": 0.05, "text": "IMPOSSIBLE -- you actually won the grand prize!", "outcome": {"gain": {"shards": [1, 2]}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}}},
                    {"chance": 0.25, "text": "A solid prize, at least. Xender looks personally offended.", "outcome": {"gain": {"gold": [38, 69]}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}}},
                    {"chance": 0.70, "text": "You got scammed. You knew this. You did it anyway.", "outcome": {}},
                ],
            },
            {
                "id": "super_lottery",
                "label": "🎟️ Enter the \"SUPER Not A Scam\" Lottery (30🪙)",
                "description": "The SUPER version. Somehow less trustworthy.",
                "action": "gamble",
                "style": "primary",
                "cost": {"gold": 30},
                "tiers": [
                    {"chance": 0.03, "text": "No way. NO WAY. You actually won the top-tier prize.", "outcome": {"gain": {"lootbox": "rare", "reroll_tokens": [1,2]}}},
                    {"chance": 0.22, "text": "A decent haul, surprisingly.", "outcome": {"gain": {"gold": [88, 162]}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}}},
                    {"chance": 0.75, "text": "SUPER scammed. Somehow worse than the regular scam.", "outcome": {}},
                ],
            },
            {
                "id": "fund_him",
                "label": "💰 \"Fund\" his totally official operation (25🪙)",
                "description": "Xender promises a cut of the returns.",
                "action": "trade",
                "style": "danger",
                "cost": {"gold": 25},
                "success_chance": 0.2,
                "success_text": "Against all odds, Xender actually delivers -- a supply crate shows up later that shift.",
                "on_success": {"gain": {"material_tier": 1, "amount": [6, 30]}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
                "fail_text": "You never hear from him again. Shocking.",
                "on_fail": {},
            },
            {
                "id": "leave",
                "label": "🚪 Keep your gold and walk away",
                "description": "The only winning move.",
                "action": "leave",
                "style": "secondary",
                "text": "You keep your gold and walk away, ignoring Xender's protests.",
            },
        ],
    },
    # ------------------------------------------------------------------
    # Rex -- crafter/shopkeeper in the old event, out in the middle of
    # nowhere for reasons nobody explains.
    # ------------------------------------------------------------------
    {
        "id": "rex_workshop",
        "name": "Rex",
        "image_url": "https://cdn.discordapp.com/attachments/704530416475832342/1274572311445635173/REXEVENT.png?ex=6a5af477&is=6a59a2f7&hm=ecbf164219a00fa7f020d2899c9c70bc4eaf76f52c162b048d7e13f62e4bdfe1&",
        "room_types": ["story"],
        "intros": [
            "You find Rex's workshop deep in the woods -- one random shop, no neighbors, no explanation. He offers to craft something from your materials.",
            "Rex looks a bit beaten up. He doesn't say why, and you don't ask.",
            "Nobody's in Rex's shop today except Rex. He waves you in anyway.",
        ],
        "choices": [
            {
                "id": "commission",
                "label": "🔨 Commission a supply run (20🪨 15🪵 10🪙)",
                "description": "Pay upfront; Rex delivers whatever he can scrounge.",
                "action": "trade",
                "style": "success",
                "cost": {"stone": 20, "wood": 15, "gold": 10},
                "success_chance": 0.95,
                "success_text": "Rex delivers exactly what he promised, plus a lot extra for the trouble.",
                "on_success": {"gain": {"material_tier": 1, "amount": [14, 30]}, "bonus": {"chance": 0.11, "gain": {"lootbox": "common"}}},
                "fail_text": "Rex apologizes -- the shipment fell through. He refunds what he can.",
                "on_fail": {"gain": {"gold": [12, 22]}},
            },
            {
                "id": "ambush_rex",
                "label": "🗡️ Ambush Rex",
                "description": "He's an old man. What's the worst that could happen.",
                "action": "risk",
                "style": "danger",
                "success_chance": 0.35,
                "success_text": "You catch him off guard for once and make off with a good chunk of his stock.",
                "on_success": {"gain": {"gold": [28, 50], "reroll_tokens": [1,2]}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
                "fail_text": "Rex is stronger than he looks. You end up scuffling and losing supplies in the chaos.",
                "on_fail": {"loss": {"material_tier": 0, "amount": [4, 10]}, "hp_damage_percent": 5},
            },
            {
                "id": "sell_scrap",
                "label": "📦 Sell him 15 Metal",
                "description": "Rex always needs raw materials.",
                "action": "trade",
                "style": "success",
                "cost": {"metal": 15},
                "success_chance": 0.98,
                "success_text": "Rex pays fair price, no haggling.",
                "on_success": {"gain": {"gold": [56, 100]}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
                "fail_text": "Rex says he's overstocked this week. Awkward.",
                "on_fail": {},
            },
            {
                "id": "leave",
                "label": "🚪 Leave Rex to his work",
                "description": "",
                "action": "leave",
                "style": "secondary",
                "text": "You decide to leave Rex to his work and continue exploring.",
            },
        ],
    },
    # ------------------------------------------------------------------
    # NF89 -- blacksmith. The old event's gear-crafting choices map onto
    # this project's actual item system (a rolled item) instead of the
    # old bespoke axe/pickaxe/dagger objects. His main commission is now
    # the encounter system's showcase for the rare-natural-rarity roll --
    # usually Common, occasionally something much better.
    # ------------------------------------------------------------------
    {
        "id": "nf89_blacksmith",
        "name": "NF89",
        "image_url": "https://cdn.discordapp.com/attachments/704530416475832342/1274977215314133023/NFTHEBLACKSMITH.png?ex=6a5a7350&is=6a5921d0&hm=72e2c1f0edc5159b0cc4c9d1d9939828518572c8153797205700b0ebb5179f91&",
        "room_types": ["story"],
        "intros": [
            "NF89 the blacksmith looks up from his forge. \"If you need anything forged, I'll get it done.\"",
            "\"Have you seen Ultra M anywhere?\" NF89 asks. \"Ever since the highlands disaster, he's been missing...\"",
            "NF89 is mid-forge, sparks flying. He waves you over without looking up.",
        ],
        "choices": [
            {
                "id": "commission_gear",
                "label": "⚒️ Commission gear (60🪨 40⚙️ 15🪙)",
                "description": "Have NF89 forge you something to equip -- quality's the forge's call.",
                "action": "gamble",
                "style": "success",
                "cost": {"stone": 60, "metal": 40, "gold": 15},
                # Same fix as Bee Jee's augment (see merchant.py): a paid
                # commission granting {"item": "natural"} returned a
                # Common about 42% of the time, which made the whole
                # trade a loss more often than not. NF89's bill is
                # lighter than hers, so his floor sits one tier lower and
                # his ceiling stops at Epic.
                "tiers": [
                    {"chance": 0.08, "text": "He surprises himself. It's the best thing he's made all month.",
                     "outcome": {"gain": {"item": "epic"}}},
                    {"chance": 0.37, "text": "Clean, honest work -- better than the price suggested.",
                     "outcome": {"gain": {"item": "rare"}}},
                    {"chance": 0.55, "text": "Serviceable, sturdy, and exactly to spec.",
                     "outcome": {"gain": {"item": "uncommon", "material_tier": 1, "amount": [4, 10]}}},
                ],
            },
            {
                "id": "sell_metal",
                "label": "📦 Sell him 30 Metal",
                "description": "NF89 always needs raw stock.",
                "action": "trade",
                "style": "success",
                "cost": {"metal": 30},
                "success_chance": 0.98,
                "success_text": "Fair trade, no complaints.",
                "on_success": {"gain": {"gold": [69, 119], "reroll_tokens": [1,2]}, "bonus": {"chance": 0.11, "gain": {"lootbox": "common"}}},
                "fail_text": "\"Overstocked,\" he says, waving you off.",
                "on_fail": {},
            },
            {
                "id": "forge_parts",
                "label": "⚙️ Pay for scrap parts (20🪙)",
                "description": "A grab-bag of leftover forge material.",
                "action": "gamble",
                "style": "primary",
                "cost": {"gold": 20},
                "tiers": [
                    {"chance": 0.1, "text": "NF89 hands you a rare batch, muttering about Ultra M again.", "outcome": {"gain": {"material_tier": 2, "amount": [7, 14]}, "bonus": {"chance": 0.128, "gain": {"shards": [1,3]}}}},
                    {"chance": 0.9, "text": "A standard batch of parts, nothing special.", "outcome": {"gain": {"material_tier": 1, "amount": [10, 34]}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}}},
                ],
            },
            {
                "id": "leave",
                "label": "🚪 Leave NF89 to his forge",
                "description": "",
                "action": "leave",
                "style": "secondary",
                "text": "You decide to leave NF89's workshop and continue on your journey.",
            },
        ],
    },
    # ------------------------------------------------------------------
    # HHyper -- the old event's kaiju-scale rampage, hilariously on-brand
    # given WORLD_LORE.md's HHyper is literally the H-Nation's leader.
    # Ambushing him is (correctly) a terrible idea 97% of the time -- but
    # the 3% is the single biggest jackpot in the whole encounter pool.
    # ------------------------------------------------------------------
    {
        "id": "hhyper_dragon",
        "name": "HHyper",
        "image_url": "https://cdn.discordapp.com/attachments/704530416475832342/1275748057174118400/HHYPER_1.png?ex=6a5a9e37&is=6a594cb7&hm=f22df69441ad9f3464dcdfc747fb940307e2d860b21c8cdb758b8164187ea42b&",
        "room_types": ["story"],
        "intros": [
            "HHyper, an extra-large presence, looms over the wreckage of a nearby structure. The ground shakes with every step.",
            "You can hear distant cries as HHyper passes through. Something about him doesn't feel entirely real.",
            "HHyper stops on a ridge, causing a small earthquake. He seems to be looking directly at you.",
        ],
        "choices": [
            {
                "id": "sell_materials",
                "label": "📦 Sell 80 Stone for rare materials",
                "description": "Risk approaching him with a trade offer.",
                "action": "trade",
                "style": "success",
                "cost": {"stone": 80},
                "success_chance": 0.97,
                "success_text": "Somehow, this works out. You walk away with something valuable.",
                "on_success": {"gain": {"material_tier": 2, "amount": [8, 19], "reroll_tokens": [1,2]}, "bonus": {"chance": 0.096, "gain": {"shards": [1,3]}}},
                "fail_text": "HHyper isn't interested. You keep your stone, at least.",
                "on_fail": {},
            },
            {
                "id": "ambush",
                "label": "⚔️ Try to fight HHyper",
                "description": "This is, statistically, a very bad idea.",
                "action": "risk",
                "style": "danger",
                "success_chance": 0.03,
                "success_text": "Against every possible odd, you win. Nobody believes you when you tell this story.",
                "on_success": {"gain": {"gold": [250, 438], "reroll_tokens": [10,20], "lootbox": "legendary"}},
                "fail_text": "HHyper is, unsurprisingly, too big for you. You get obliterated and lose supplies in the blast.",
                "on_fail": {"loss": {"material_tier": 0, "amount": [15, 30]}, "hp_damage_percent": 25},
            },
            {
                "id": "leave",
                "label": "🚪 Leave HHyper well alone",
                "description": "The wise choice.",
                "action": "leave",
                "style": "secondary",
                "text": "You decide to leave HHyper alone and walk away.",
            },
        ],
    },
    # ------------------------------------------------------------------
    # Rohan -- fruit vendor with a grudge and a gossip habit.
    # ------------------------------------------------------------------
    {
        "id": "rohan_vendor",
        "name": "Rohan",
        "image_url": "hhttps://cdn.discordapp.com/attachments/935416283976048680/1277522580164575284/ROHANfruitvendor.png?ex=6a5a7b5e&is=6a5929de&hm=461bd159390e277d43755ac09e2f01d95978bf766834f90f74957d5578697d9e&",
        "room_types": ["story"],
        "intros": [
            "Rohan the fruit vendor mutters, \"If you ever see Josh around, don't talk to him. He can't be trusted...\"",
            "\"Everyone is oblivious to my divine powers,\" Rohan says, arranging his stand with unusual intensity.",
            "\"I can't stand that Rex guy,\" Rohan grumbles. \"Always so supportive of Josh...\"",
        ],
        "choices": [
            {
                "id": "sell_produce",
                "label": "🪵 Sell him 20 Wood \"for the stand\"",
                "description": "He's oddly specific about needing wood.",
                "action": "trade",
                "style": "success",
                "cost": {"wood": 20},
                "success_chance": 0.97,
                "success_text": "Rohan pays up without complaint.",
                "on_success": {"gain": {"gold": [44, 75]}, "bonus": {"chance": 0.08, "gain": {"shards": [1,3]}}},
                "fail_text": "\"Not today,\" Rohan says, oddly defensive.",
                "on_fail": {},
            },
            {
                "id": "ambush_rohan",
                "label": "🗡️ Try to ambush Rohan",
                "description": "His \"divine powers\" are probably a bluff. Probably.",
                "action": "risk",
                "style": "danger",
                "success_chance": 0.3,
                "success_text": "You manage it -- barely -- and he flees, dropping a fair bit of gold.",
                "on_success": {"gain": {"gold": [25, 50], "reroll_tokens": [1,2]}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
                "fail_text": "Rohan's \"divine powers\" turn out to be a very solid right hook.",
                "on_fail": {"loss": {"material_tier": 0, "amount": [5, 12]}, "hp_damage_percent": 10},
            },
            {
                "id": "ask_about_josh",
                "label": "❓ Ask about Josh",
                "description": "He clearly has opinions.",
                "action": "risk",
                "style": "secondary",
                "success_chance": 0.6,
                "success_text": "Rohan actually has useful gossip -- and a solid tip to go with it.",
                "on_success": {"gain": {"gold": [31, 56], "reroll_tokens": 1}, "bonus": {"chance": 0.11, "gain": {"lootbox": "common"}}},
                "fail_text": "Rohan just glares at you for bringing Josh up at all.",
                "on_fail": {},
            },
            {
                "id": "leave",
                "label": "🚪 Leave Rohan to his stand",
                "description": "",
                "action": "leave",
                "style": "secondary",
                "text": "You decide to leave Rohan and continue exploring.",
            },
        ],
    },
    # ------------------------------------------------------------------
    # Frost -- ex-Xender-Corp janitor turned scrap vendor.
    # ------------------------------------------------------------------
    {
        "id": "frost_vendor",
        "name": "Frost",
        "image_url": "https://cdn.discordapp.com/attachments/704530416475832342/1282278127363559547/jani_1.png?ex=6a5aa4d1&is=6a595351&hm=23f8e7aa18f39a9e6900f6db26007b9952519d436768452eed0b286deeb6b034&",
        "room_types": ["story"],
        "intros": [
            "Frost, once a janitor at Xender Corp, now runs a scrap stand in the frozen wastes. \"Fired last week,\" he mutters.",
            "\"The economy's destroying everything,\" Frost says, not looking up from his scavenged goods.",
            "Frost nervously glances over his shoulder. Something -- or someone -- has him spooked.",
        ],
        "choices": [
            {
                "id": "sell_wood",
                "label": "📦 Sell 40 Wood for gold",
                "description": "Straightforward trade.",
                "action": "trade",
                "style": "success",
                "cost": {"wood": 40},
                "success_chance": 0.98,
                "success_text": "Frost pays fair, no games.",
                "on_success": {"gain": {"gold": [44, 75]}, "bonus": {"chance": 0.11, "gain": {"lootbox": "common"}}},
                "fail_text": "Frost is out of gold today, apparently.",
                "on_fail": {},
            },
            {
                "id": "sell_ore",
                "label": "🧊 Sell 15 Permafrost Ore",
                "description": "Frost seems to know its actual worth.",
                "action": "trade",
                "style": "success",
                "cost": {"permafrost_ore": 15},
                "success_chance": 0.96,
                "success_text": "Frost trades up -- this stuff is rarer than he's letting on.",
                "on_success": {"gain": {"gold": [56, 94]}, "bonus": {"chance": 0.112, "gain": {"shards": [1,3]}}},
                "fail_text": "\"Not enough,\" Frost says, shaking his head.",
                "on_fail": {},
            },
            {
                "id": "ambush_frost",
                "label": "🗡️ Ambush Frost",
                "description": "He's just a janitor. Right?",
                "action": "risk",
                "style": "danger",
                "success_chance": 0.35,
                "success_text": "You catch Frost off guard and make off with his stock.",
                "on_success": {"gain": {"gold": [31, 56], "material_tier": 0, "amount": [16, 30], "reroll_tokens": [1,2]}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
                "fail_text": "Frost the ex-janitor throws a surprisingly mean punch.",
                "on_fail": {"loss": {"material_tier": 0, "amount": [8, 15]}, "hp_damage_percent": 12},
            },
            {
                "id": "leave",
                "label": "🚪 Leave Frost's stand",
                "description": "",
                "action": "leave",
                "style": "secondary",
                "text": "You leave Frost's stand and continue on your way.",
            },
        ],
    },
    # ------------------------------------------------------------------
    # Nyrvite -- new, drawn from Cascade_Classified_Files.txt (File
    # C-005). Cascade "ninja"; a Story-flavored character encounter.
    # ------------------------------------------------------------------
    {
        "id": "nyrvite_duel",
        "name": "Nyrvite",
        "image_url": "https://cdn.discordapp.com/attachments/1527136925348135023/1527148474720583870/2wpUVcAAAAGSURBVAMAl9UFHHTB7aIAAAAASUVORK5CYII.png?ex=6a5aecd9&is=6a599b59&hm=e06432cfa7ccd9e059e7ee364407c0ee3cb1239d81987f9e4ffe34b2ca6b1c61&",
        "room_types": ["story"],
        "intros": [
            "Nyrvite drops down from somewhere above, twin energy machetes already drawn. \"You're either backup or a problem. Let's find out which.\"",
            "\"Don't worry,\" Nyrvite says, spinning a blade idly, \"I only cut people who deserve it. Probably.\"",
            "Nyrvite is testing the edge of her machetes on a support beam when she notices you. \"Oh good, a volunteer.\"",
        ],
        "choices": [
            {
                "id": "spar",
                "label": "⚔️ Take her up on a friendly spar",
                "description": "\"Friendly\" is doing some work in that sentence.",
                "action": "risk",
                "style": "danger",
                "success_chance": 0.5,
                "success_text": "You hold your own well enough that Nyrvite calls it a draw and shares some supplies out of respect.",
                "on_success": {"gain": {"gold": [25, 50], "material_tier": 0, "amount": [14, 27], "reroll_tokens": [1,2]}, "bonus": {"chance": 0.11, "gain": {"lootbox": "common"}}},
                "fail_text": "\"Friendly\" turns out to be relative. Nyrvite is very, very fast.",
                "on_fail": {"hp_damage_percent": 12},
            },
            {
                "id": "trade_intel",
                "label": "🗣️ Trade for intel on Josh's whereabouts (10🪙)",
                "description": "She gets around. She might know something.",
                "action": "trade",
                "style": "success",
                "cost": {"gold": 10},
                "success_chance": 0.75,
                "success_text": "Nyrvite actually has useful intel, and throws in a little extra for the conversation.",
                "on_success": {"gain": {"gold": [31, 56]}, "bonus": {"chance": 0.08, "gain": {"shards": 1}}},
                "fail_text": "\"Never heard of him,\" Nyrvite says, pocketing your gold anyway.",
                "on_fail": {},
            },
            {
                "id": "leave",
                "label": "🚪 Leave before she decides you're a problem",
                "description": "",
                "action": "leave",
                "style": "secondary",
                "text": "You decide not to test which one you are, and leave before Nyrvite makes up her mind.",
            },
        ],
    },
    # ------------------------------------------------------------------
    # Anti-Void Allegiance -- new, drawn from Cascade_Classified_Files.txt
    # (File F-001, second entry). Eco-terrorist anti-void faction; a
    # Story-flavored ideological encounter.
    # ------------------------------------------------------------------
    {
        "id": "antivoid_recruiter",
        "name": "The Anti-Void Recruiter",
        "image_url": "https://cdn.discordapp.com/attachments/1527136925348135023/1527148702932668496/image.png?ex=6a5aed0f&is=6a599b8f&hm=4d4ed43d90ebb0d0fda7be057cd711175c1e55f948891e39d2fbbec2d5109f76&",
        "room_types": ["story"],
        "intros": [
            "A masked figure presses a pamphlet into your hands before you can object. \"VOID IS A CORRUPTION -- JOIN THE ALLEGIANCE.\"",
            "\"You're carrying void-tainted materials,\" the recruiter says, eyeing your pack with open suspicion. \"That stuff isn't as safe as they tell you.\"",
            "The recruiter doesn't ask for your name. Just: \"Does it feel wrong yet? The void, I mean. It will.\"",
        ],
        "choices": [
            {
                "id": "donate_cause",
                "label": "🕊️ Donate 10 Xendium to \"the cause\"",
                "description": "Support the Allegiance, see what happens.",
                "action": "trade",
                "style": "success",
                "cost": {"xendium": 10},
                "success_chance": 0.8,
                "success_text": "The recruiter accepts the donation and, oddly, hands you something useful in return -- entropy-adjacent tech, they call it.",
                "on_success": {"gain": {"material_tier": 2, "amount": [8, 16], "gold": [12, 25], "reroll_tokens": [3, 6]}, "bonus": {"chance": 0.11, "gain": {"lootbox": "common"}}},
                "fail_text": "\"We don't need YOUR kind of help,\" the recruiter snaps, keeping the materials anyway.",
                "on_fail": {},
            },
            {
                "id": "argue",
                "label": "🗣️ Argue that void tech isn't the problem",
                "description": "Debate a true believer.",
                "action": "risk",
                "style": "secondary",
                "success_chance": 0.55,
                "success_text": "You actually win the argument. The recruiter, grudgingly, respects it -- and slips you something on the way out.",
                "on_success": {"gain": {"gold": [31, 56]}, "bonus": {"chance": 0.08, "gain": {"shards": 1}}},
                "fail_text": "The recruiter is not interested in your opinion, and makes that clear.",
                "on_fail": {"loss": {"material_tier": 0, "amount": [3, 8]}},
            },
            {
                "id": "leave",
                "label": "🚪 Take the pamphlet and go",
                "description": "",
                "action": "leave",
                "style": "secondary",
                "text": "You take the pamphlet, mostly to be polite, and go on your way.",
            },
        ],
    },
    # ------------------------------------------------------------------
    # Dolpo -- new, drawn from Cascade_Classified_Files.txt (File H-008).
    # Radicalized ex-Acatrya sniper; a tragic Story-flavored standoff.
    # ------------------------------------------------------------------
    {
        "id": "dolpo_standoff",
        "name": "Dolpo",
        "image_url": "https://cdn.discordapp.com/attachments/1527136925348135023/1527148818842517646/image.png?ex=6a5aed2b&is=6a599bab&hm=4ca50b39e829f15841520af725ce49170e2437242cc759a8514ca2583e500cfb&",
        "room_types": ["story"],
        "intros": [
            "A lone gunner watches you from atop a collapsed wall, rifle already tracking your movement. \"Cascade,\" he mutters, like the word itself is an insult.",
            "\"My brother trusted people like you,\" Dolpo says, not lowering his rifle. \"Look where that got him.\"",
            "Dolpo hasn't missed a shot in years, according to the rumors. You'd rather not test that today.",
        ],
        "choices": [
            {
                "id": "stand_down",
                "label": "🕊️ Try to talk him down",
                "description": "He's radicalized, not unreachable.",
                "action": "risk",
                "style": "primary",
                "success_chance": 0.5,
                "success_text": "For a moment, something in Dolpo's expression cracks. He lowers the rifle and walks off without a word, leaving supplies behind.",
                "on_success": {"gain": {"gold": [25, 50], "material_tier": 0, "amount": [11, 22]}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
                "fail_text": "Dolpo isn't interested in talking. He wasn't really interested in missing, either.",
                "on_fail": {"hp_damage_percent": 15},
            },
            {
                "id": "draw_first",
                "label": "⚡ Draw first",
                "description": "He's already aiming. Might as well move first.",
                "action": "risk",
                "style": "danger",
                "success_chance": 0.35,
                "success_text": "You catch him off guard, just barely. Dolpo retreats, dropping his supply pack in the process.",
                "on_success": {"gain": {"material_tier": 1, "amount": [12, 30], "gold": [25, 44], "reroll_tokens": [1,2]}, "bonus": {"chance": 0.132, "gain": {"lootbox": "common"}}},
                "fail_text": "Dolpo trained for this exact scenario, apparently. His aim is exactly as good as advertised.",
                "on_fail": {"loss": {"gold": [10, 20]}, "hp_damage_percent": 22},
            },
            {
                "id": "leave",
                "label": "🚪 Back away slowly",
                "description": "",
                "action": "leave",
                "style": "secondary",
                "text": "You decide this isn't a fight worth having, and back away slowly.",
            },
        ],
    },
    # ==================================================================
    # LOW-REWARD encounters -- deliberately minor. Not every stop needs
    # to be a jackpot; these are quick, low-risk breathers that mostly
    # exist for flavor and pacing variety, with correspondingly small
    # numbers. Contrast these against the HIGH-REWARD block further
    # down within the *same* room-type pools (e.g. H-Henchmen here vs.
    # Corrupted Bli below, both tagged "trap").
    # ==================================================================
    {
        "id": "xg_scamera",
        "name": "XG-SCamera",
        "image_url": "https://cdn.discordapp.com/attachments/1527136925348135023/1527148979249348648/PCpy8gAAAAZJREFUAwDeVBEL31fZMAAAAABJRU5ErkJggg.png?ex=6a5aed51&is=6a599bd1&hm=04bc79abf340856d6dbfba4d2fef4eab1c42f6de4767c0e44f78f73f97fba7c9&",
        "room_types": ["story"],
        "intros": [
            "A surveillance camera watches from a rusted mount overhead, its red light blinking steadily. Xender's network never really stopped watching.",
            "You spot one of Xender's surveillance cameras, half-buried in rubble but still faintly powered.",
            "A camera's lens tracks your movement for a second before going still again. Somewhere, a report is probably being filed.",
        ],
        "choices": [
            {
                "id": "salvage_chip",
                "label": "🔧 Salvage its chip",
                "description": "Quick and quiet.",
                "action": "risk",
                "style": "secondary",
                "success_chance": 0.85,
                "success_text": "A quick, quiet job. The chip's worth a little to the right buyer.",
                "on_success": {"gain": {"gold": [10, 20]}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
                "fail_text": "The housing is more stubborn than it looks. You give up before wasting more time.",
                "on_fail": {},
            },
            {
                "id": "disable_it",
                "label": "🔌 Disable it, just in case",
                "description": "One less pair of eyes on you.",
                "action": "risk",
                "style": "secondary",
                "success_chance": 0.8,
                "success_text": "One less pair of eyes on you. Small comfort, but comfort all the same.",
                "on_success": {"gain": {"gold": [6, 12]}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
                "fail_text": "You fumble the wiring, but manage to shut it off anyway.",
                "on_fail": {},
            },
            {
                "id": "leave",
                "label": "🚪 Ignore it and move on",
                "description": "",
                "action": "leave",
                "style": "secondary",
                "text": "It's just a camera. You keep moving.",
            },
        ],
    },
    # ------------------------------------------------------------------
    # Dorve -- new, from Cascade_Classified_Files.txt (File X-001).
    # Deliberately the sparsest encounter in the whole roster: per his
    # own file, "Team Cascade has not encountered Dorve in combat" --
    # so there isn't much of an encounter to have here, on purpose.
    # ------------------------------------------------------------------
    {
        "id": "dorve_sighting",
        "name": "Dorve",
        "image_url": "https://cdn.discordapp.com/attachments/1527136925348135023/1527150632904167535/image.png?ex=6a5aeedb&is=6a599d5b&hm=6e4b8599eba3aec51ac0425097c525623b6fd2422c5cf5583efc0757dd23d35e&",
        "room_types": ["story"],
        "intros": [
            "You catch a glimpse of Dorve, Xender's elite assistant, reviewing something on a tablet from a passing convoy. He doesn't so much as glance your way.",
            "Dorve is too far away to approach safely, flanked by more guards than you'd like to count.",
            "Word is Dorve has never been seen in actual combat. You're not about to be the first test case.",
        ],
        "choices": [
            {
                "id": "observe",
                "label": "👀 Watch and take notes",
                "description": "Might be worth something to someone.",
                "action": "risk",
                "style": "secondary",
                "success_chance": 0.9,
                "success_text": "Nothing dramatic, but you note enough troop movement to be worth a little gold from the right buyer.",
                "on_success": {"gain": {"gold": [12, 25]}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
                "fail_text": "You don't see anything worth remembering.",
                "on_fail": {},
            },
            {
                "id": "leave",
                "label": "🚪 Keep your distance",
                "description": "",
                "action": "leave",
                "style": "secondary",
                "text": "You decide Dorve's guard detail is not worth testing, and keep your distance.",
            },
        ],
    },
    # ------------------------------------------------------------------
    # Jofrog -- new, from Cascade_Classified_Files.txt (File F-000, The
    # World Aligners). A gentler, medium-reward Story encounter.
    # ------------------------------------------------------------------
    {
        "id": "jofrog_meeting",
        "name": "Jofrog",
        "image_url": "https://cdn.discordapp.com/attachments/1527136925348135023/1527152048192098325/hSioQAAAAZJREFUAwB0bhXeRqijSAAAAABJRU5ErkJggg.png?ex=6a5af02d&is=6a599ead&hm=6efb58adaadbaf8cce73ae77c61ac1977953ffee3794ec71b9eddd0a82d71f26&",
        "room_types": ["story"],
        "intros": [
            "A boxy robot with a hand-painted smile waves at you. \"Oh! A traveler! I'm Jofrog. I used to be somebody's bodyguard. Now I'm just... me, I guess.\"",
            "\"Do you think a robot can be happy?\" Jofrog asks, apropos of nothing.",
            "Jofrog is humming to himself, badly, and doesn't seem to mind that you can hear it.",
        ],
        "choices": [
            {
                "id": "help_him",
                "label": "🔧 Help him with a small repair",
                "description": "He seems nice enough.",
                "action": "risk",
                "style": "success",
                "success_chance": 0.8,
                "success_text": "Jofrog is delighted, and insists on paying you back even though you told him not to bother.",
                "on_success": {"gain": {"gold": [25, 44], "material_tier": 0, "amount": [11, 22]}, "bonus": {"chance": 0.11, "gain": {"lootbox": "common"}}},
                "fail_text": "You make it slightly worse, honestly. Jofrog is very gracious about it anyway.",
                "on_fail": {},
            },
            {
                "id": "ask_about_aligners",
                "label": "❓ Ask about the World Aligners",
                "description": "He clearly wants to talk about it.",
                "action": "risk",
                "style": "secondary",
                "success_chance": 0.6,
                "success_text": "Jofrog talks your ear off, but some of it is actually useful, and he hands you something as thanks for listening.",
                "on_success": {"gain": {"gold": [19, 38]}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
                "fail_text": "Jofrog gets distracted mid-explanation and wanders off entirely.",
                "on_fail": {},
            },
            {
                "id": "leave",
                "label": "🚪 Wish him well and move on",
                "description": "",
                "action": "leave",
                "style": "secondary",
                "text": "You wish him well and continue on your way.",
            },
        ],
    },
    # ------------------------------------------------------------------
    # Blueflame -- new, from Cascade_Classified_Files.txt (File F-000).
    # A medium-high reward Story encounter with a genuinely risky option.
    # ------------------------------------------------------------------
    {
        "id": "blueflame_encounter",
        "name": "Blueflame",
        "image_url": "https://cdn.discordapp.com/attachments/1527136925348135023/1527152594256924672/image.png?ex=6a5af0af&is=6a599f2f&hm=b29961c26b878024f12dddf5736844f86aa0ca946f96be874a7e462a919fcdcb&",
        "room_types": ["story"],
        "intros": [
            "A figure wreathed in flickering blue flame sits alone, staring at nothing. The flame gutters low, then flares, tracking something you can't see.",
            "\"They made me into an experiment,\" Blueflame says, without turning around. \"Now I get to decide what I am.\"",
            "The air around Blueflame shimmers with heat that somehow doesn't burn anything nearby. His mood, apparently, runs hot.",
        ],
        "choices": [
            {
                "id": "talk_freedom",
                "label": "🗣️ Talk with him about freedom",
                "description": "He seems like he wants to talk.",
                "action": "risk",
                "style": "primary",
                "success_chance": 0.65,
                "success_text": "Blueflame's aura settles to a calm blue. He shares a little of what he's scavenged, grateful for the company.",
                "on_success": {"gain": {"gold": [31, 56], "material_tier": 0, "amount": [4, 10]}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
                "fail_text": "Something you say sets him off. The flame flares hot enough to singe your supplies.",
                "on_fail": {"loss": {"material_tier": 0, "amount": [5, 12]}},
            },
            {
                "id": "harvest_flame",
                "label": "🔥 Try to harvest a sample of the flame",
                "description": "Valuable, if he doesn't mind.",
                "action": "risk",
                "style": "danger",
                "success_chance": 0.3,
                "success_text": "You manage to bottle a stable sample. It's worth a great deal to the right buyer -- and Blueflame doesn't even seem to mind.",
                "on_success": {"gain": {"material_tier": 2, "amount": [7, 16], "gold": [38, 69]}, "bonus": {"chance": 0.098, "gain": {"lootbox": "rare"}}},
                "fail_text": "Blueflame very much minds. The flame flares defensively.",
                "on_fail": {"hp_damage_percent": 14},
            },
            {
                "id": "leave",
                "label": "🚪 Leave him be",
                "description": "",
                "action": "leave",
                "style": "secondary",
                "text": "You decide Blueflame deserves to be left alone, and you leave him be.",
            },
        ],
    },
    # ------------------------------------------------------------------
    # Refender -- new, from Cascade_Classified_Files.txt (File F-000).
    # A medium-reward Story encounter, and a nice callback to the
    # "Refense" riddle from the old Puzzle-room mini-game.
    # ------------------------------------------------------------------
    {
        "id": "refender_speech",
        "name": "Refender",
        "image_url": "https://cdn.discordapp.com/attachments/1527136925348135023/1527152707675230319/download.png?ex=6a5af0ca&is=6a599f4a&hm=f0c587a69be793d68dd26aac3167701259943139561e8640c118723a5d0b5b49&",
        "room_types": ["story"],
        "intros": [
            "A weathered man stands on a crate, mid-speech, to an audience of exactly no one. \"REFENSE!\" he shouts. \"The balance of offense and defense!\"",
            "\"You look like someone who understands balance,\" Refender says, eyeing your gear approvingly.",
            "Refender is handing out hand-written pamphlets about \"Refense\" to absolutely nobody in this abandoned corridor.",
        ],
        "choices": [
            {
                "id": "listen_to_speech",
                "label": "👂 Listen to his speech",
                "description": "It's the least you can do.",
                "action": "risk",
                "style": "secondary",
                "success_chance": 0.75,
                "success_text": "It's actually kind of compelling. Refender's thrilled to have an audience and rewards you for your patience.",
                "on_success": {"gain": {"gold": [19, 38]}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
                "fail_text": "You zone out about halfway through. Refender notices, and it stings his pride more than you.",
                "on_fail": {},
            },
            {
                "id": "demonstrate_balance",
                "label": "⚖️ Demonstrate \"balance\" with a fair trade (15🪵 15🪨)",
                "description": "Show, don't tell.",
                "action": "trade",
                "style": "success",
                "cost": {"stone": 15, "wood": 15},
                "success_chance": 0.85,
                "success_text": "Refender is delighted by the symmetry of the trade and rewards you generously, on principle.",
                "on_success": {"gain": {"material_tier": 1, "amount": [14, 27], "gold": [12, 25], "reroll_tokens": [1,2]}, "bonus": {"chance": 0.11, "gain": {"lootbox": "common"}}},
                "fail_text": "Refender decides your trade wasn't balanced enough, and keeps the materials on principle.",
                "on_fail": {},
            },
            {
                "id": "leave",
                "label": "🚪 Leave him to his speech",
                "description": "",
                "action": "leave",
                "style": "secondary",
                "text": "You leave Refender to his speech and continue on your way.",
            },
        ],
    },
    # ==================================================================
    # HEAL / XP encounters -- the roster's first rewards that restore
    # squad HP or grant XP directly, instead of only currency/materials/
    # lootboxes. Written around characters whose lore already leans
    # support/caretaker (a cook, a doctor, an engineer, a grinder).
    # ==================================================================
    {
        "id": "lily_kitchen",
        "name": "Lily Lovelace",
        "image_url": "https://cdn.discordapp.com/attachments/1527136925348135023/1527152932091330560/7PEccAAAAGSURBVAMAdpCHdVGIpEAAAAASUVORK5CYII.png?ex=6a5af100&is=6a599f80&hm=83524efd382f8985cdaae2ca7cfeb4d28401a69849afdfe954c67f574ec715e8&",
        "room_types": ["story"],
        "intros": [
            "Lily Lovelace has set up a small travelling kitchen here, humming to herself as something simmers. \"Oh! A new face. Sit, sit -- you look like you need a good meal.\"",
            "The smell hits you before you see her: Lily, mid-recipe, somehow cooking a full meal out of what looks like scraps.",
            "\"I remember every face that visits me,\" Lily says warmly. \"You're new. Let's fix that.\"",
        ],
        "choices": [
            {
                "id": "eat_meal",
                "label": "🍲 Share a meal with her",
                "description": "Free, and exactly what you needed.",
                "action": "risk",
                "style": "success",
                "success_chance": 0.9,
                "success_text": "It's exactly what your squad needed. Everyone feels steadier.",
                "on_success": {"heal": 25},
                "fail_text": "You're stuffed, but it doesn't do much beyond that.",
                "on_fail": {},
            },
            {
                "id": "trade_ingredients",
                "label": "🥘 Trade 15 Wood for a proper feast",
                "description": "Bring your own ingredients, get the full spread.",
                "action": "trade",
                "style": "success",
                "cost": {"wood": 15},
                "success_chance": 0.95,
                "success_text": "Lily goes all out. Your squad eats like royalty and rests easier for it.",
                "on_success": {"heal": "full", "gain": {"gold": [12, 25]}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
                "fail_text": "She's out of the good stuff today, but insists on refunding you.",
                "on_fail": {"gain": {"wood": 20}},
            },
            {
                "id": "ask_advice",
                "label": "❓ Ask for combat advice over dinner",
                "description": "She's seen more battles secondhand than most people see firsthand.",
                "action": "risk",
                "style": "primary",
                "success_chance": 0.7,
                "success_text": "Turns out Lily's picked up more from soldiers passing through than most soldiers ever learn firsthand. Her tips are genuinely useful.",
                "on_success": {"gain": {"xp": [23, 40]}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
                "fail_text": "She mostly just tells you to eat your vegetables.",
                "on_fail": {},
            },
            {
                "id": "leave",
                "label": "🚪 Thank her and move on",
                "description": "",
                "action": "leave",
                "style": "secondary",
                "text": "You thank her for the hospitality and continue on your way.",
            },
        ],
    },
    # ------------------------------------------------------------------
    # Evz -- new, from Cascade_Classified_Files.txt (File C-015). Ex-
    # doctor turned mechanic/pilot; the roster's most direct "medic"
    # flavored heal encounter.
    # ------------------------------------------------------------------
    {
        "id": "evz_checkup",
        "name": "Evz",
        "image_url": "https://cdn.discordapp.com/attachments/1527136925348135023/1527153166028898395/6xhfqAAAAAGSURBVAMA8cJi1MzmR2oAAAAASUVORK5CYII.png?ex=6a5af137&is=6a599fb7&hm=e1ba652ba86ccc4855d4b298124695dbc983ac19d6e8ebf206e3e410f6bc4001&",
        "room_types": ["story"],
        "intros": [
            "Evz has set up a field aid station here, more out of habit than necessity. \"Old doctor instincts,\" he explains, waving you over.",
            "\"I don't get to practice medicine much anymore,\" Evz says, \"but I keep the kit anyway. Let me take a look at you.\"",
            "Evz is halfway through repairing an airship engine when he spots your squad's condition and immediately switches modes: doctor, not mechanic.",
        ],
        "choices": [
            {
                "id": "checkup",
                "label": "🩺 Let him look you over",
                "description": "Free, quick, and thorough.",
                "action": "risk",
                "style": "success",
                "success_chance": 0.9,
                "success_text": "Evz's old training hasn't faded a bit. Your squad walks away steadier.",
                "on_success": {"heal": 30},
                "fail_text": "He's more mechanic than doctor these days, honestly. Not much comes of it.",
                "on_fail": {},
            },
            {
                "id": "full_treatment",
                "label": "💉 Ask for the full treatment (20🪙)",
                "description": "Pay for the real thing.",
                "action": "trade",
                "style": "success",
                "cost": {"gold": 20},
                "success_chance": 0.95,
                "success_text": "Evz doesn't hold back. Your squad is patched up completely.",
                "on_success": {"heal": "full"},
                "fail_text": "He's out of proper supplies, and refunds you on principle.",
                "on_fail": {"gain": {"gold": 25}},
            },
            {
                "id": "leave",
                "label": "🚪 Thank him and move on",
                "description": "",
                "action": "leave",
                "style": "secondary",
                "text": "You thank Evz for the offer and continue on your way.",
            },
        ],
    },
    # ------------------------------------------------------------------
    # Vegetable Tam -- new, from Cascade_Classified_Files.txt (File
    # C-016). Ex-air-force-turned-farmer; lighthearted heal + XP mix.
    # ------------------------------------------------------------------
    {
        "id": "vegtam_carrots",
        "name": "Vegetable Tam",
        "image_url": "https://cdn.discordapp.com/attachments/1527136925348135023/1527153345234473070/2gAAAAZJREFUAwB3TUpsdlpnJAAAAABJRU5ErkJggg.png?ex=6a5af162&is=6a599fe2&hm=91487bf51b659471f17568b53f645c2c17af5066dfc34853cf38d1d55919c3ae&",
        "room_types": ["story"],
        "intros": [
            "Vegetable Tam is tending a small patch of carrots that absolutely should not be growing here. \"They like the attention,\" he explains, unprompted.",
            "\"Used to fly for Xender's air force,\" Tam says, elbow-deep in dirt. \"Carrots are more honest work.\"",
            "Tam offers you a carrot before you've said a single word.",
        ],
        "choices": [
            {
                "id": "share_carrots",
                "label": "🥕 Share a meal of fresh carrots",
                "description": "Surprisingly good, apparently.",
                "action": "risk",
                "style": "success",
                "success_chance": 0.9,
                "success_text": "Surprisingly good. Your squad feels genuinely refreshed.",
                "on_success": {"heal": 15, "gain": {"gold": [6, 12]}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
                "fail_text": "Good carrots, but that's about it.",
                "on_fail": {},
            },
            {
                "id": "flying_tips",
                "label": "✈️ Ask about his time in the air force",
                "description": "Old stories, maybe useful ones.",
                "action": "risk",
                "style": "primary",
                "success_chance": 0.65,
                "success_text": "Tam's old flying stories turn out to have some genuinely useful tactical nuggets buried in them.",
                "on_success": {"gain": {"xp": [17, 32]}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
                "fail_text": "It's mostly just stories about carrots, if you're honest.",
                "on_fail": {},
            },
            {
                "id": "leave",
                "label": "🚪 Wish him well and move on",
                "description": "",
                "action": "leave",
                "style": "secondary",
                "text": "You wish him well and continue on your way.",
            },
        ],
    },
    # ==================================================================
    # More world flavor -- rounding out the roster further.
    # ==================================================================
    {
        "id": "andy_engine",
        "name": "Andy",
        "image_url": "https://cdn.discordapp.com/attachments/1527136925348135023/1527154496956793003/ZgjwaAAAAAZJREFUAwCyMLBQqtz3owAAAABJRU5ErkJggg.png?ex=6a5af275&is=6a59a0f5&hm=fa2d59992423aad68a0ba7a5e7a3f2ee336e6510078553d267c04e269757f1c5&",
        "room_types": ["story"],
        "intros": [
            "Andy is elbow-deep in an airship engine, muttering calculations under his breath. \"Almost -- there. Oh! Didn't see you there.\"",
            "\"You ever flown a Voidwarp-capable ship?\" Andy asks, not looking up from his tools. \"Terrifying, first time. Gets better.\"",
            "Andy has schematics spread out everywhere, half of them your basic aircraft, half of them... considerably less basic.",
        ],
        "choices": [
            {
                "id": "help_repairs",
                "label": "🔧 Help with repairs",
                "description": "An extra pair of hands, and a free lesson.",
                "action": "risk",
                "style": "primary",
                "success_chance": 0.8,
                "success_text": "You're not an engineer, but you're a decent extra pair of hands. Andy teaches you a thing or two while you work.",
                "on_success": {"gain": {"gold": [19, 35], "xp": [17, 29]}, "bonus": {"chance": 0.11, "gain": {"lootbox": "common"}}},
                "fail_text": "You mostly get in the way. Andy's patient about it, at least.",
                "on_fail": {},
            },
            {
                "id": "sell_parts",
                "label": "📦 Sell him 25 Metal",
                "description": "Good parts are hard to come by out here.",
                "action": "trade",
                "style": "success",
                "cost": {"metal": 25},
                "success_chance": 0.97,
                "success_text": "Andy pays well -- good parts are hard to come by out here.",
                "on_success": {"gain": {"gold": [62, 106], "reroll_tokens": [3, 7]}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
                "fail_text": "\"Wrong gauge, sorry,\" Andy says, apologetic.",
                "on_fail": {},
            },
            {
                "id": "leave",
                "label": "🚪 Leave him to his work",
                "description": "",
                "action": "leave",
                "style": "secondary",
                "text": "You leave Andy to his repairs and continue on your way.",
            },
        ],
    },
    # ------------------------------------------------------------------
    # Void Reactor Remnants -- new STORY encounter. Environmental
    # set-piece (no NPC), matching the "no character, just a place"
    # pattern the two new treasure chests above use. Explosion +
    # poisoning is represented as hp_damage_percent (this project's only
    # per-member damage mechanic -- see file docstring) rather than a
    # bespoke status effect, since there isn't one to hook into here.
    # The careless option risks real harm for real reward; the cautious
    # option is a smaller, safer guaranteed salvage; walking away is
    # always free.
    # ------------------------------------------------------------------
    {
        "id": "void_reactor_remnants",
        "name": "Void Reactor Remnants",
        "image_url": "https://cdn.discordapp.com/attachments/1527136925348135023/1527175504287760384/image.png?ex=6a5b0605&is=6a59b485&hm=36886d4e46469b84a9cb714152924dcf88bfb4ce07794080df062042e05be2ef&",
        "room_types": ["story"],
        "intros": [
            "The crater is unmistakable: a Void reactor went critical here, and recently. A sickly haze still clings to the wreckage.",
            "Twisted, half-melted machinery juts out of scorched earth. Whatever this reactor was containing, it clearly didn't stay contained.",
            "The air here tastes wrong. At the center of the blast site, the reactor core sits cracked open, still leaking something faintly luminous.",
        ],
        "choices": [
            {
                "id": "salvage_carefully",
                "label": "🧤 Salvage from a safe distance",
                "description": "Stick to the outer wreckage. Smaller, safer haul.",
                "action": "risk",
                "style": "success",
                "success_chance": 0.9,
                "success_text": "You keep well clear of the core and strip usable parts from the outer wreckage without incident.",
                "on_success": {"gain": {"material_tier": 0, "amount": [14, 24], "gold": [19, 31]}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
                "fail_text": "A stray gust carries the haze your way and you catch a lungful before backing off.",
                "on_fail": {"hp_damage_percent": 8},
            },
            {
                "id": "push_to_core",
                "label": "☢️ Push through the poisoned zone to the core",
                "description": "The real materials are at the center. High risk.",
                "action": "risk",
                "style": "danger",
                "success_chance": 0.45,
                "success_text": "You reach the cracked core and pull out a dense cluster of rare, still-warm Void-touched materials before the haze forces you back.",
                "on_success": {"gain": {"material_tier": 2, "amount": [8, 19], "gold": [38, 69], "reroll_tokens": [1,2]}, "bonus": {"chance": 0.128, "gain": {"shards": [1,3]}}},
                "fail_text": "The haze thickens fast. By the time you stumble back out, the poison has already done its damage.",
                "on_fail": {"hp_damage_percent": 28, "loss": {"material_tier": 0, "amount": [8, 15]}},
            },
            {
                "id": "leave",
                "label": "🚪 Steer clear entirely",
                "description": "",
                "action": "leave",
                "style": "secondary",
                "text": "You decide the void-tainted wreckage isn't worth the risk and give the crater a wide berth.",
            },
        ],
    },
]
