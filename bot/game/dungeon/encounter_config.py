"""
Story-room (and, now, Treasure/Trap/Shrine/Puzzle/Secret-room) "Encounters":
interactive, choice-driven run-ins with recurring Cascade-world characters,
adapted from the original JS bot's explore.js (the old /explore command's
`events` array). That system had one bespoke JS function per button; this
one is pure data, like TRAP_CHOICES/PUZZLES in interactive_config.py,
resolved generically by a small interpreter in dungeon_service.py (see
resolve_encounter_choice / _apply_outcome).

Each encounter has:
  - id / name / image_url: identity + flavor art. Encounters ported from
    explore.js keep its original `imageUrl`; brand new encounters (added
    to cover themes the old cast didn't reach) leave image_url as None --
    there's no source art for a character that never existed before.
  - room_types: which RoomType value(s) (see bot/database/models/enums.py)
    this encounter is eligible to be rolled for. dungeon_service picks
    from whichever pool matches the node the player is actually standing
    on -- a "shrine"-tagged encounter only ever shows up in a Shrine room,
    etc. Most of the original cast stayed STORY-flavored (they're
    character run-ins, not environmental set-pieces); a few were
    re-themed to rooms they fit better (Duko's loot-crate gambling ->
    Treasure, Triv's ambush -> Trap, thedoggyp's looted shack -> Secret),
    and a handful of brand new encounters were written to give
    Shrine/Puzzle/Secret a dedicated NPC-flavored option too.

    "merchant" is a special case: Merchant rooms no longer have their own
    bespoke shop UI at all (see dungeon_service.py's ROOM_ENCOUNTER_CHANCE
    -- Merchant rolls an encounter 100% of the time, with a defensive
    "trading post is closed" fallback message if that pool were ever
    empty). A merchant-tagged encounter's choices are almost always plain
    "trade" actions with success_chance 1.0 and a flat (non-range) `gain`
    amount -- a real shop sells you exactly what the price tag says, no
    scam roll, unlike Xender's lottery or a "sell materials" trade
    elsewhere that still carries a little risk. Tbnr's shop covers cheap
    tier-0/tier-1 bulk goods; Boss John's covers the expensive end
    (tier-2/tier-3 materials, pricier lootboxes, and the one deliberately
    steep way to buy Shards outright with gold instead of hoping for a
    rare bonus roll).
  - intros: a few randomized opening lines (old code picked one of these
    with Math.random() per visit; same idea here via rng.choice).
  - choices: 1-5 buttons. Every choice has an "action":
      - "leave"  -- no cost, no roll, just flavor text.
      - "risk"   -- no upfront cost; success_chance rolls between
                    on_success/on_fail outcomes.
      - "trade"  -- pay `cost` upfront (skipped entirely if unaffordable),
                    then success_chance rolls between on_success/on_fail.
                    Trades that amount to "sell materials for a reward"
                    are intentionally generous and near-guaranteed --
                    per a balance pass, a trade should clearly be in the
                    player's favor, not a coin flip.
      - "gamble" -- pay `cost` (can be empty), then pick one of `tiers`
                    (weighted by "chance") for its outcome. Good for
                    lottery/lootcrate-style choices with more than two
                    possible results, including rare high-tier ones.

An "outcome" (on_success / on_fail / a gamble tier's "outcome") is a dict
with any of:
  - "gain": currency/material amounts to add (see _apply_gain) --
    supports plain currency keys ("gold", "shards", "wood", ...), a
    random pick from a material tier via {"material_tier": int,
    "amount": n_or_[lo, hi]}, {"lootbox": tier_str}, or {"item": True}
    for a guaranteed random Common item, or {"item": "natural"} for a
    naturally-rolled item (any rarity up to the region's cap -- rare,
    but how a lucky forge/terminal/shrine choice can occasionally hand
    out something much better than Common).
  - "loss": currency/material amounts to subtract, clamped to what the
    player actually has (see _apply_loss). Same material_tier shorthand
    as gain.
  - "hp_damage_percent": knocks a random squad member for that % of
    their max HP, same mechanic TRAP_CHOICES' fail_damage_percent uses.
  - "bonus": {"chance": p, "gain": {...}} -- an independent, usually-low
    chance of an EXTRA reward on top of whatever else the outcome gave.
    This is how Shards and rare Lootboxes are sprinkled across a wide
    variety of encounters while staying rare at any single one of them:
    a plain "gain" of shards is only ever used inside an already-rare
    gamble tier (<=10% chance); everywhere else, a shard reward rides
    along as a small "bonus" (~4-10% chance for 1-2) on top of a
    reward that's guaranteed or near-guaranteed on its own. NEVER give
    shards as a flat guaranteed "gain" behind a high success_chance --
    that's how they'd stop being rare. (Boss John's merchant shop is the
    one deliberate exception: a guaranteed, expensive, explicit "buy a
    Shard" purchase -- see that encounter's comment.)
  - "heal": "full" or an int percent (a sibling of "gain"/"loss"/
    "hp_damage_percent"/"bonus", not something that goes inside "gain")
    -- restores the WHOLE squad's HP, either fully (same current_hp =
    None sentinel a Campfire room uses) or by that percent of each
    member's own max HP. Unlike damage, which always lands on one
    random squad member, healing applies to everyone -- it reads better
    as a reward, and there's no per-member damage mechanic to mirror.

A "gain" dict can also include "xp": n_or_[lo, hi], which splits that
much XP across the WHOLE squad via combat_service.apply_character_xp
(the same function combat victories use), including any resulting
level-ups.

Amount values can be a flat int or an inclusive [min, max] range.

Some encounters/choices are also written with deliberately harsher
failure states than the rest of the roster on purpose -- bigger
hp_damage_percent (30%+), and even a "loss" of Shards on failure
(normally shards only ever move in the *gain* direction) -- as the
high-stakes end of the risk/reward curve. These are flagged in their
own comments; they're not oversights.

Original character/story content and image links are preserved from
explore.js; the resource types and numbers have been re-tuned to this
project's current economy (gold/shards/reroll_tokens + 8 tiered
materials instead of the old wood/stone/rope/ruby/etc. inventory), and
rewards across the board were bumped up in a balance pass so Encounters
read as clearly worthwhile next to a plain Treasure/Secret room instead
of just a novelty detour.

SECOND BALANCE PASS (post-Encounter-only migration): with Trap/Puzzle
now folded into this same Encounter system (see dungeon_service.py --
TRAP_CHOICES/PUZZLES and interactive_config.py are gone, every
non-combat/campfire/start room resolves through here now), rewards were
scaled up again across the board: material gain amounts (both the
material_tier/amount pattern and any directly-named material key) are
roughly +35%, gold gains roughly +25%, XP gains roughly +15%. Every
existing "bonus" chance (shards or lootbox) was also increased --
common-lootbox bonus chances especially, since the goal of this pass
was specifically to make Common lootboxes a frequent, expected drop
rather than a rare one -- and most success outcomes that previously
carried no bonus at all now carry a small (8%) chance of a bonus Common
Lootbox on top of their normal reward. Choices whose payout is
deliberately tied to their cost by a fixed ratio (Josh's betting table:
literal double-or-nothing) were deliberately left alone so that
mechanic stays honest -- don't blanket-rescale those without also
rescaling the cost they're a multiple of.
"""

from __future__ import annotations

ENCOUNTERS: list[dict] = [
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
                "on_success": {"gain": {"gold": [31, 56]}, "bonus": {"chance": 0.08, "gain": {"shards": 1}}},
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
                "on_success": {"gain": {"wood": [30, 51]}, "bonus": {"chance": 0.064, "gain": {"shards": 1}}},
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
                "on_success": {"gain": {"stone": [30, 51]}, "bonus": {"chance": 0.064, "gain": {"shards": 1}}},
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
                "on_success": {"gain": {"metal": [16, 27]}, "bonus": {"chance": 0.08, "gain": {"shards": 1}}},
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
                    {"chance": 0.03, "text": "No way. NO WAY. You actually won the top-tier prize.", "outcome": {"gain": {"lootbox": "rare", "reroll_tokens": 1}}},
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
                "on_success": {"gain": {"material_tier": 1, "amount": [16, 30]}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
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
                "on_success": {"gain": {"material_tier": 1, "amount": [16, 30]}, "bonus": {"chance": 0.11, "gain": {"lootbox": "common"}}},
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
                "on_success": {"gain": {"gold": [28, 50]}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
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
                "action": "trade",
                "style": "success",
                "cost": {"stone": 60, "metal": 40, "gold": 15},
                "success_chance": 0.96,
                "success_text": "NF89 delivers a piece of gear, fresh off the forge.",
                "on_success": {"gain": {"item": "natural"}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
                "fail_text": "The forge misfires. NF89 refunds some materials, embarrassed.",
                "on_fail": {"gain": {"material_tier": 1, "amount": [16, 27]}},
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
                "on_success": {"gain": {"gold": [69, 119]}, "bonus": {"chance": 0.11, "gain": {"lootbox": "common"}}},
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
                    {"chance": 0.1, "text": "NF89 hands you a rare batch, muttering about Ultra M again.", "outcome": {"gain": {"material_tier": 2, "amount": [7, 14]}, "bonus": {"chance": 0.128, "gain": {"shards": 1}}}},
                    {"chance": 0.9, "text": "A standard batch of parts, nothing special.", "outcome": {"gain": {"material_tier": 1, "amount": [20, 34]}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}}},
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
                "on_success": {"gain": {"material_tier": 2, "amount": [8, 19]}, "bonus": {"chance": 0.096, "gain": {"shards": 1}}},
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
                "on_success": {"gain": {"gold": [250, 438], "lootbox": "legendary"}},
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
                "on_success": {"gain": {"gold": [44, 75]}, "bonus": {"chance": 0.08, "gain": {"shards": 1}}},
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
                "on_success": {"gain": {"gold": [25, 50]}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
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
                "on_success": {"gain": {"gold": [31, 56]}, "bonus": {"chance": 0.11, "gain": {"lootbox": "common"}}},
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
                "on_success": {"gain": {"gold": [56, 94]}, "bonus": {"chance": 0.112, "gain": {"shards": 1}}},
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
                "on_success": {"gain": {"gold": [31, 56], "material_tier": 0, "amount": [16, 30]}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
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
                    {"chance": 0.01, "text": "LEGENDARY -- the rock splits open to reveal something incredible.", "outcome": {"gain": {"lootbox": "rare"}}},
                    {"chance": 0.09, "text": "A genuinely good haul.", "outcome": {"gain": {"material_tier": 1, "amount": [11, 20]}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}}},
                    {"chance": 0.40, "text": "A modest find.", "outcome": {"gain": {"gold": [12, 31]}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}}},
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
                    {"chance": 0.04, "text": "Multiple legendary cracks in one go -- Duko looks personally wounded.", "outcome": {"gain": {"lootbox": "uncommon"}}},
                    {"chance": 0.30, "text": "A solid batch, all around.", "outcome": {"gain": {"material_tier": 1, "amount": [27, 47]}, "bonus": {"chance": 0.08, "gain": {"shards": 1}}}},
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
                    {"chance": 0.08, "text": "An entire crate's worth of the good stuff -- Duko mutters something about early retirement.", "outcome": {"gain": {"lootbox": "epic"}}},
                    {"chance": 0.50, "text": "A genuinely excellent haul.", "outcome": {"gain": {"material_tier": 1, "amount": [20, 40], "gold": [12, 25]}, "bonus": {"chance": 0.096, "gain": {"shards": 1}}}},
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
                "on_success": {"gain": {"material_tier": 1, "amount": [20, 38], "gold": [31, 56]}, "bonus": {"chance": 0.132, "gain": {"lootbox": "common"}}},
                "fail_text": "Even fighting seriously, Triv gets the better of you.",
                "on_fail": {"loss": {"material_tier": 0, "amount": [5, 12]}, "hp_damage_percent": 20},
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
                    {"chance": 0.15, "text": "An excellent day -- Daffysamlake finds something shiny and hands it right over.", "outcome": {"gain": {"material_tier": 1, "amount": [11, 22]}, "bonus": {"chance": 0.08, "gain": {"shards": 1}}}},
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
                    {"chance": 0.08, "text": "Jackpot -- a vein nobody's touched in decades.", "outcome": {"gain": {"material_tier": 1, "amount": [27, 47], "gold": [31, 56]}, "bonus": {"chance": 0.12, "gain": {"lootbox": "uncommon"}}}},
                    {"chance": 0.77, "text": "A solid, multi-resource haul, all to yourself.", "outcome": {"gain": {"material_tier": 0, "amount": [27, 54], "gold": [12, 25]}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}}},
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
                    {"chance": 0.85, "text": "You find a good stash of loot in the shack.", "outcome": {"gain": {"material_tier": 0, "amount": [16, 38]}, "bonus": {"chance": 0.08, "gain": {"shards": 1}}}},
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
                "on_success": {"gain": {"material_tier": 1, "amount": [14, 27], "gold": [19, 38]}, "bonus": {"chance": 0.08, "gain": {"shards": 1}}},
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
                "on_success": {"gain": {"material_tier": 1, "amount": [27, 47], "gold": [31, 62]}, "bonus": {"chance": 0.12, "gain": {"lootbox": "uncommon"}}},
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
                "on_success": {"gain": {"material_tier": 2, "amount": [4, 9], "gold": [25, 50]}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
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
                "on_success": {"gain": {"gold": [25, 50], "material_tier": 1, "amount": [5, 14]}, "bonus": {"chance": 0.08, "gain": {"shards": 1}}},
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
                "on_success": {"gain": {"material_tier": 2, "amount": [7, 14], "gold": [19, 38]}, "bonus": {"chance": 0.128, "gain": {"shards": 1}}},
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
                "on_success": {"gain": {"material_tier": 2, "amount": [8, 19]}, "bonus": {"chance": 0.13, "gain": {"lootbox": "rare"}}},
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
                "on_success": {"gain": {"wood": 54, "stone": 54}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
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
                "on_success": {"gain": {"metal": 34}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
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
                "on_success": {"gain": {"crystal": 34}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
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
                "on_success": {"gain": {"xendium": 8}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
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
                "on_success": {"gain": {"permafrost_ore": 8}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
                "fail_text": "",
                "on_fail": {},
            },
            {
                "id": "buy_void",
                "label": "🕳️ \"Acquire\" 2 Void (120🪙)",
                "description": "Very expensive. Don't ask where it's from.",
                "action": "trade",
                "style": "primary",
                "cost": {"gold": 120},
                "success_chance": 1.0,
                "success_text": "Boss John lowers his voice, just this once. \"Don't tell Xender.\"",
                "on_success": {"gain": {"void": 3}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
                "fail_text": "",
                "on_fail": {},
            },
            {
                "id": "buy_rare_lootbox",
                "label": "🎁 Buy a Rare Lootbox (140🪙)",
                "description": "Steep, but guaranteed.",
                "action": "trade",
                "style": "primary",
                "cost": {"gold": 140},
                "success_chance": 1.0,
                "success_text": "\"You will NOT regret this!\" Boss John says, probably lying.",
                "on_success": {"gain": {"lootbox": "rare"}},
                "fail_text": "",
                "on_fail": {},
            },
            {
                "id": "buy_shard",
                "label": "✨ Buy 1 Shard (180🪙)",
                "description": "The single most expensive line item in his store.",
                "action": "trade",
                "style": "danger",
                "cost": {"gold": 180},
                "success_chance": 1.0,
                "success_text": "Boss John produces it from somewhere you'd rather not think about. \"A RARE treasure, for a RARE customer.\"",
                "on_success": {"gain": {"shards": 1}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
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
                "on_success": {"gain": {"material_tier": 1, "amount": [16, 30], "gold": [19, 38]}, "bonus": {"chance": 0.08, "gain": {"shards": 1}}},
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
                "on_success": {"gain": {"material_tier": 2, "amount": [8, 16], "gold": [19, 31]}, "bonus": {"chance": 0.096, "gain": {"shards": 1}}},
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
                "on_success": {"gain": {"material_tier": 1, "amount": [20, 38], "gold": [25, 44]}, "bonus": {"chance": 0.132, "gain": {"lootbox": "common"}}},
                "fail_text": "Caliper's aim is exactly as good as his reputation says.",
                "on_fail": {"loss": {"gold": [5, 15]}, "hp_damage_percent": 18},
            },
            {
                "id": "outshoot",
                "label": "🎯 Challenge him to a real shootout",
                "description": "Bold. Possibly stupid.",
                "action": "risk",
                "style": "danger",
                "success_chance": 0.3,
                "success_text": "Somehow, you out-shoot one of the best marksmen in the Wastelands. He hands over his gear out of pure respect.",
                "on_success": {"gain": {"material_tier": 1, "amount": [27, 47], "gold": [38, 69]}, "bonus": {"chance": 0.12, "gain": {"lootbox": "uncommon"}}},
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
                "on_success": {"gain": {"material_tier": 1, "amount": [20, 38], "gold": [19, 38]}, "bonus": {"chance": 0.112, "gain": {"shards": 1}}},
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
                "on_success": {"gain": {"material_tier": 2, "amount": [11, 22]}, "bonus": {"chance": 0.13, "gain": {"lootbox": "rare"}}},
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
                "on_success": {"gain": {"material_tier": 1, "amount": [19, 34], "gold": [25, 44]}, "bonus": {"chance": 0.132, "gain": {"lootbox": "common"}}},
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
                "on_success": {"gain": {"material_tier": 1, "amount": [27, 47], "gold": [38, 69]}, "bonus": {"chance": 0.128, "gain": {"shards": 1}}},
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
                "on_success": {"gain": {"gold": [25, 50], "material_tier": 0, "amount": [14, 27]}, "bonus": {"chance": 0.11, "gain": {"lootbox": "common"}}},
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
                "on_success": {"gain": {"material_tier": 2, "amount": [8, 16], "gold": [12, 25]}, "bonus": {"chance": 0.11, "gain": {"lootbox": "common"}}},
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
                "on_success": {"gain": {"material_tier": 1, "amount": [20, 38], "gold": [25, 44]}, "bonus": {"chance": 0.132, "gain": {"lootbox": "common"}}},
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
                "on_success": {"gain": {"material_tier": 3, "amount": [4, 11], "gold": [188, 350]}, "bonus": {"chance": 0.07, "gain": {"lootbox": "legendary"}}},
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
                "on_success": {"gain": {"material_tier": 2, "amount": [14, 27], "gold": [75, 138]}, "bonus": {"chance": 0.1, "gain": {"lootbox": "epic"}}},
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
                "on_success": {"gain": {"material_tier": 3, "amount": [4, 9], "gold": [50, 88]}, "bonus": {"chance": 0.128, "gain": {"shards": [1, 2]}}},
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
                "on_success": {"gain": {"material_tier": 0, "amount": [11, 24], "gold": [12, 25]}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
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
                "on_success": {"gain": {"material_tier": 1, "amount": [16, 30], "gold": [19, 38]}, "bonus": {"chance": 0.11, "gain": {"lootbox": "common"}}},
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
                "on_success": {"gain": {"gold": [31, 56], "material_tier": 1, "amount": [8, 19]}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
                "fail_text": "Something you say sets him off. The flame flares hot enough to singe your supplies.",
                "on_fail": {"loss": {"material_tier": 0, "amount": [5, 12]}},
            },
            {
                "id": "harvest_flame",
                "label": "🔥 Try to harvest a sample of the flame",
                "description": "Valuable, if he doesn't mind.",
                "action": "risk",
                "style": "danger",
                "success_chance": 0.4,
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
    # "Refense" riddle already in PUZZLES (interactive_config.py).
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
                "on_success": {"gain": {"material_tier": 1, "amount": [14, 27], "gold": [12, 25]}, "bonus": {"chance": 0.11, "gain": {"lootbox": "common"}}},
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
                "on_success": {"gain": {"material_tier": 1, "amount": [27, 47], "gold": [31, 56]}, "bonus": {"chance": 0.09, "gain": {"lootbox": "uncommon"}}},
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
                "on_success": {"gain": {"material_tier": 2, "amount": [14, 27], "gold": [50, 88]}, "bonus": [{"chance": 0.15, "gain": {"shards": 1}}, {"chance": 0.11, "gain": {"lootbox": "common"}}]},
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
                "on_success": {"gain": {"gold": [62, 106]}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
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
                "on_success": {"gain": {"material_tier": 1, "amount": [14, 27]}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
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
                "action": "trade",
                "style": "success",
                "cost": {"metal": 70, "gold": 30},
                "success_chance": 0.95,
                "success_text": "Bee Jee's work is precise, as always.",
                "on_success": {"gain": {"item": "natural"}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
                "fail_text": "\"Wrong caliber for what I've got,\" she admits, refunding you.",
                "on_fail": {"gain": {"gold": 38}},
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
                "on_success": {"gain": {"crystal": 40}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
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
                "on_success": {"gain": {"material_tier": 1, "amount": [20, 38], "gold": [19, 38]}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
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
                "label": "🎲 Buy a guaranteed Uncommon item (150🪙)",
                "description": "The entry price for doing business here.",
                "action": "trade",
                "style": "success",
                "cost": {"gold": 150},
                "success_chance": 1.0,
                "success_text": "The Bookie doesn't even blink. \"Pleasure doing business.\"",
                "on_success": {"gain": {"item": "uncommon"}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
                "fail_text": "",
                "on_fail": {},
            },
            {
                "id": "buy_rare",
                "label": "💎 Buy a guaranteed Rare item (350🪙)",
                "description": "No chance involved. You pay, you get.",
                "action": "trade",
                "style": "success",
                "cost": {"gold": 350},
                "success_chance": 1.0,
                "success_text": "\"Good taste,\" the Bookie says, sliding the case over.",
                "on_success": {"gain": {"item": "rare"}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
                "fail_text": "",
                "on_fail": {},
            },
            {
                "id": "buy_epic",
                "label": "🔥 Buy a guaranteed Epic item (800🪙)",
                "description": "Now we're talking real money.",
                "action": "trade",
                "style": "primary",
                "cost": {"gold": 800},
                "success_chance": 1.0,
                "success_text": "The Bookie actually smiles. \"Now THAT'S a customer.\"",
                "on_success": {"gain": {"item": "epic"}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
                "fail_text": "",
                "on_fail": {},
            },
            {
                "id": "buy_legendary",
                "label": "👑 Buy a guaranteed Legendary item (1800🪙)",
                "description": "The kind of purchase that gets remembered.",
                "action": "trade",
                "style": "primary",
                "cost": {"gold": 1800},
                "success_chance": 1.0,
                "success_text": "Even the bodyguards look impressed. \"Don't spend it all in one place,\" the Bookie says, handing it over anyway.",
                "on_success": {"gain": {"item": "legendary"}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
                "fail_text": "",
                "on_fail": {},
            },
            {
                "id": "buy_mythic",
                "label": "🌌 Buy a guaranteed Mythic item (3500🪙)",
                "description": "Absurd. Also, available.",
                "action": "trade",
                "style": "danger",
                "cost": {"gold": 3500},
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
                "on_success": {"gain": {"material_tier": 0, "amount": [20, 40], "gold": [12, 25]}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
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
                "on_success": {"gain": {"material_tier": 1, "amount": [16, 30], "gold": [25, 50]}, "bonus": {"chance": 0.096, "gain": {"shards": 1}}},
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
                "on_success": {"gain": {"gold": [31, 56], "material_tier": 0, "amount": [14, 27]}, "bonus": {"chance": 0.096, "gain": {"shards": 1}}},
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
                "on_success": {"gain": {"material_tier": 1, "amount": [14, 24], "gold": [19, 31]}, "bonus": {"chance": 0.08, "gain": {"lootbox": "common"}}},
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
                "on_success": {"gain": {"material_tier": 2, "amount": [8, 19], "gold": [38, 69]}, "bonus": {"chance": 0.128, "gain": {"shards": 1}}},
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


def get_encounter_by_id(encounter_id: str) -> dict | None:
    return next((e for e in ENCOUNTERS if e["id"] == encounter_id), None)


def get_encounters_for_room_type(room_type_value: str) -> list[dict]:
    return [e for e in ENCOUNTERS if room_type_value in e.get("room_types", ())]