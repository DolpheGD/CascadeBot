"""
Story mode content: chapters, missions and beats.

Pure data, like every other *_config module here. The interpreter lives
in bot/services/story_service.py and knows nothing about any specific
mission -- which is what lets `tools/check_story.py` validate the whole
script without running it.

----------------------------------------------------------------------
THE SHAPE
----------------------------------------------------------------------

    Chapter -> Mission -> Beat

A **beat** is the atom, and there are six kinds:

    dialogue   authored text from a speaker; one Continue button
    choice     2-4 authored options, each of which may set flags
    battle     a fixed, named enemy list at a fixed level
    encounter  an existing encounter by id, resolved by the normal
               encounter interpreter
    reward     grants currency/items
    unlock     turns a feature on (see FEATURES) and says so

Every beat may carry `requires` / `unless` (lists of flag names), so a
mission can include or skip a beat based on what the player did earlier.
A flag that has never been set reads as False, which is what makes flags
safe to add later -- see the "Flags must be additive" note in
docs/STORY_MODE.md.

----------------------------------------------------------------------
WHY THE PLAYER NEVER SPEAKS
----------------------------------------------------------------------
The avatar is renameable and class-switchable, so any line written for
them is a line put in the mouth of someone the player invented. Everyone
else talks; the player acts, through `choice` beats. That's a deliberate
constraint, not an omission -- see docs/STORY_MODE.md.

Tone is serious with dry humour: the cover-up and the disappearances play
straight, and the jokes come from characters rather than from undercutting
the premise. The comedy encounters in `/adventure` are texture there, not
the register here.
"""

from __future__ import annotations

# ----------------------------------------------------------------------
# FEATURES -- what story mode can switch on.
#
# A feature that isn't unlocked yet has its command refused with a
# pointer to the story, rather than being hidden: a player who typed
# `/raid` should be told when they'll get raids, not met with silence.
#
# The value is the human name used in that message.
# ----------------------------------------------------------------------
FEATURES: dict[str, str] = {
    "inventory": "Inventory",
    "pull": "Character pulls",
    "squad": "Squad management",
    "adventure": "Expeditions",
    "domains": "Domains",
    "base": "Cascade HQ",
    "raids": "Co-op raids",
    "forge": "The Forge",
    "lab": "The Research Lab",
    "exchange": "The Echo Exchange",
    "quests": "Quests",
    "gifting": "Gifting",
    "daily": "Daily rewards",
}

# Features every player has from the moment they exist. Deliberately
# tiny: profile and help are how you find out what's going on, and story
# is the thing that unlocks everything else.
ALWAYS_AVAILABLE = frozenset({"profile", "help", "story", "characters"})


CHAPTERS: list[dict] = [
    {
        "id": "prologue",
        "name": "Prologue: Signal Discipline",
        "blurb": (
            "Somebody at The Daily Dolphe has been trying to reach you for a week. "
            "You finally answer."
        ),
        # The prologue unlocks no region -- it unlocks the GAME.
        "unlocks_region": None,
        "missions": [
            # ==========================================================
            # P1 -- combat. One fight, against something that cannot
            # realistically kill a starting squad. The job of this
            # mission is to make the four buttons mean something.
            # ==========================================================
            {
                "id": "p1_answer_the_call",
                "name": "Answer the Call",
                "summary": "Dolphe has been calling for a week.",
                "beats": [
                    {
                        "kind": "dialogue",
                        "speaker": "Dolphe",
                        "text": (
                            "You're a hard person to reach. I've left six messages.\n\n"
                            "I'm not going to waste the seventh. My name is Dolphe. I used to "
                            "run a newspaper. Now I run something that used to be a newspaper."
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Dolphe",
                        "text": (
                            "Here's the short version. Ninety years of peace, one lab nobody "
                            "was allowed to audit, and a city that stopped existing overnight. "
                            "Officially: an unknown incident. Officially, nobody went missing.\n\n"
                            "I have four hundred names that say otherwise."
                        ),
                    },
                    {
                        "kind": "choice",
                        "prompt": "Dolphe waits.",
                        "options": [
                            {
                                "id": "in",
                                "label": "🗞️ \"What do you need?\"",
                                "text": (
                                    "\"Someone who can walk into places Acatrya has written off "
                                    "and walk back out. That's the entire job description.\""
                                ),
                                "sets": {"prologue_eager": True},
                            },
                            {
                                "id": "wary",
                                "label": "🤨 \"Why me?\"",
                                "text": (
                                    "\"Because you answered. That's genuinely most of it.\" "
                                    "She doesn't smile. \"The rest is that you're not on anyone's payroll.\""
                                ),
                                "sets": {"prologue_wary": True},
                            },
                            {
                                "id": "paid",
                                "label": "💰 \"What does it pay?\"",
                                "text": (
                                    "\"Badly, at first.\" A pause. \"Honestly, badly for a while. "
                                    "But nobody else is hiring for this, and you already know why.\""
                                ),
                                "sets": {"prologue_mercenary": True},
                            },
                        ],
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Dolphe",
                        "text": (
                            "There's a drone on the approach road that never got a shutdown "
                            "order. It's been shooting at scavengers for eleven years.\n\n"
                            "Deal with it and we'll talk properly."
                        ),
                    },
                    {
                        "kind": "battle",
                        "enemies": ["Rogue Security Drone"],
                        "level": 2,
                        "intro": (
                            "**⚔️ Attack** builds Energy and SP. **🌀 Skill** spends SP. "
                            "**💥 Ultimate** costs 50 Energy and has a cooldown.\n"
                            "The **😈 Incoming** panel shows what the drone will do *before* it "
                            "does it. It never lies."
                        ),
                        "on_win": "The drone goes quiet for the first time in eleven years.",
                        # A prologue fight you cannot fail out of. Losing
                        # the tutorial and being kicked back to a menu is
                        # the worst possible first impression, so a loss
                        # here retries rather than ending the mission.
                        "retry_on_loss": True,
                        "on_lose": "It puts you down. Dolphe waits while you get back up.",
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Dolphe",
                        "text": (
                            "Good. You can fight, which I was about to have to find out the "
                            "expensive way.\n\n"
                            "Take what's left of it. You'll want the parts."
                        ),
                    },
                ],
                "rewards": {"gold": 200},
            },

            # ==========================================================
            # P2 -- gear. Unlocks the inventory, which is the first
            # system the player owns rather than watches.
            # ==========================================================
            {
                "id": "p2_field_kit",
                "name": "Field Kit",
                "summary": "Salvage from the drone. Something to hold.",
                "beats": [
                    {
                        "kind": "dialogue",
                        "speaker": "Bee Jee",
                        "text": (
                            "Dolphe said you'd be filthy. She undersold it.\n\n"
                            "I don't fight. I make sure the people who do, do it better. "
                            "Give me the drone parts."
                        ),
                    },
                    {
                        "kind": "reward",
                        "text": (
                            "Bee Jee works for about four minutes and hands you something "
                            "that is technically a weapon."
                        ),
                        "grant": {"item": "uncommon"},
                    },
                    {
                        "kind": "unlock",
                        "feature": "inventory",
                        "text": (
                            "**`/inventory` is open.** Equip what she gave you.\n\n"
                            "Every character wears a Weapon, an Artifact, two Armor and two "
                            "Accessories. Weapons and Artifacts grant active skills; Armor and "
                            "Accessories grant passives. Gear you never equip does nothing at all."
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Bee Jee",
                        "text": (
                            "It'll hold. Come back when it doesn't and I'll pretend to be "
                            "surprised."
                        ),
                    },
                ],
                "rewards": {"gold": 150, "wood": 40, "stone": 40},
            },

            # ==========================================================
            # P2B -- quests, and the prologue's first joke.
            #
            # Tonally this is the release valve. P1 is a cover-up and
            # four hundred missing names, P2 is a medic telling you that
            # you'll be hurt; if the whole prologue plays at that pitch
            # the serious parts stop landing, because nothing contrasts
            # with them. Nexus is genuinely useful (he wrote the quest
            # board) and genuinely ridiculous (he wrote it for the
            # engagement), and the joke never costs the premise anything.
            # ==========================================================
            {
                "id": "p2b_the_corkboard",
                "name": "Content Strategy",
                "summary": "Nexus has a corkboard and a plan. Mostly a corkboard.",
                "beats": [
                    {
                        "kind": "dialogue",
                        "speaker": "Nexus",
                        "text": (
                            "Hey — hey. You're the new one. Don't move, the light's good.\n\n"
                            "*He photographs you before you can answer.*"
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Nexus",
                        "text": (
                            "So Dolphe won't let me post about any of this, which, "
                            "creatively? Devastating. Four hundred people vanish and I'm "
                            "sitting on the biggest story of the decade with the engagement "
                            "of a soup recipe.\n\n"
                            "But she *did* say I could organise the board. So I organised "
                            "the board."
                        ),
                    },
                    {
                        "kind": "choice",
                        "prompt": "The corkboard is enormous. Some of it is colour-coded.",
                        "options": [
                            {
                                "id": "impressed",
                                "label": "📌 Tell him it's actually well organised",
                                "text": (
                                    "\"THANK you.\" He gestures at a column of index cards. "
                                    "\"Nobody says that. Bee Jee called it a crime scene.\""
                                ),
                                "sets": {"humoured_nexus": True},
                            },
                            {
                                "id": "concerned",
                                "label": "🧶 Ask why there's so much string",
                                "text": (
                                    "\"The string is *load-bearing*.\" He says this with "
                                    "total confidence. \"Also it films well.\""
                                ),
                                "sets": {"questioned_nexus": True},
                            },
                            {
                                "id": "business",
                                "label": "📋 Ask what's actually on it",
                                "text": (
                                    "He straightens up, and for a second the performance "
                                    "drops. \"Everything we still need someone to do. "
                                    "It's longer than it should be.\""
                                ),
                                "sets": {"all_business": True},
                            },
                        ],
                    },
                    {
                        "kind": "unlock",
                        "feature": "quests",
                        "text": (
                            "**`/quests` is open.**\n\n"
                            "Standing objectives that pay out as you play — some are one-off, "
                            "some reset. You don't go *do* quests; you do the game, and the "
                            "quests notice.\n\n"
                            "Check it when you've been away a while. Things accumulate."
                        ),
                    },
                    {
                        "kind": "reward",
                        "text": "He shoves a battered lootbox at you off the bottom shelf.",
                        "grant": {"gold": 120, "reroll_tokens": 3},
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Nexus",
                        "text": (
                            "Look — I know what I sound like. I do it on purpose, it's easier "
                            "than the alternative.\n\n"
                            "My sister's on that board. Third column, second row. So when I "
                            "say I want this to reach people, I'm not joking about that part."
                        ),
                    },
                ],
                "rewards": {"gold": 100},
            },

            # ==========================================================
            # P3 -- the roster. A guided pull, then a squad. This is the
            # mission that turns "a character" into "your team".
            # ==========================================================
            {
                "id": "p3_who_else",
                "name": "Who Else Is Coming",
                "summary": "Cascade is a network, not an army.",
                "beats": [
                    {
                        "kind": "dialogue",
                        "speaker": "Dolphe",
                        "text": (
                            "You are not doing this alone. I want to be extremely clear about "
                            "that, because the last three people who tried are three of my "
                            "four hundred names.\n\n"
                            "Cascade is a network. Let's find out who answers."
                        ),
                    },
                    {
                        # 480 Shards = FOUR pulls at 120 each.
                        #
                        # The number is a softlock guard, not generosity.
                        # The prologue's last fight is unwinnable with a
                        # solo level-1 avatar (measured 0%), so the player
                        # MUST come out of this mission with a second
                        # character. The avatar template is excluded from
                        # the gacha pool, which means a player who owns
                        # only their avatar cannot roll a duplicate --
                        # their first pull is guaranteed to be somebody
                        # new. Four pulls is therefore three more than the
                        # guarantee needs, which is the margin for a
                        # player who spends some of it before reading
                        # what it was for.
                        "kind": "reward",
                        "text": "She routes you a recruitment budget.",
                        "grant": {"shards": 480},
                    },
                    {
                        "kind": "unlock",
                        "feature": "pull",
                        "text": (
                            "**`/pull` is open.** 120 Shards a pull; the 10x costs exactly ten "
                            "times that, so there's no penalty for going one at a time.\n\n"
                            "A duplicate is never a wasted pull — the first five copies of "
                            "anyone permanently upgrade them, and every copy pays **Echoes**."
                        ),
                    },
                    {
                        "kind": "unlock",
                        "feature": "squad",
                        "text": (
                            "**`/squad` is open.** Four slots, and any character can go in any "
                            "of them.\n\n"
                            "The strongest shape is at least one **Amplifier** and one "
                            "**Sustain** — a good Amplifier is worth more than a fourth attacker. "
                            "`/characters` shows anyone's full stats and kit."
                        ),
                    },
                    {
                        # NOBODY IS GIFTED HERE.
                        #
                        # An earlier version handed the player Josh
                        # outright, which removed the softlock but also
                        # removed the tutorial: the first pull is one of
                        # the systems the prologue exists to teach, and
                        # being given the reward for a mechanic is a
                        # reliable way never to learn the mechanic.
                        #
                        # The softlock is instead handled by the LANE
                        # DOOR, which won't open until the player actually
                        # has a second squad member (see the
                        # `requires_characters` lock in map_config). That
                        # keeps the guard rail without skipping the
                        # lesson, and it means whoever walks north is
                        # somebody the player chose.
                        "kind": "dialogue",
                        "speaker": "Dolphe",
                        "text": (
                            "Put the word out with `/pull` and see who answers. Then put them "
                            "in your `/squad` — nobody walks into Glacier 15 alone.\n\n"
                            "I'll be here. Josh is already outside, pretending he isn't waiting."
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Josh",
                        "text": (
                            "So you're the new one.\n\n"
                            "I was at Glacier 15. I got out. A lot of people didn't, and the "
                            "official position is that there was nobody there to not get out.\n\n"
                            "Dolphe says you're going to help me prove otherwise."
                        ),
                    },
                    {
                        "kind": "choice",
                        "prompt": "Josh is looking at you like he's already been disappointed twice today.",
                        "options": [
                            {
                                "id": "promise",
                                "label": "🤝 Tell him you'll help",
                                "text": (
                                    "\"People say that.\" He nods anyway. \"Say it again when "
                                    "you've seen the place.\""
                                ),
                                "sets": {"promised_josh": True},
                            },
                            {
                                "id": "honest",
                                "label": "🧊 Tell him you don't make promises",
                                "text": (
                                    "Something in his face relaxes very slightly. \"Good. "
                                    "The last one made promises.\""
                                ),
                                "sets": {"honest_with_josh": True},
                            },
                            {
                                "id": "ask",
                                "label": "❓ Ask what happened at Glacier 15",
                                "text": (
                                    "\"One night. That's what happened. I'll show you the rest "
                                    "when we're standing in it.\""
                                ),
                                "sets": {"asked_about_glacier": True},
                            },
                        ],
                    },
                    # A mission must not END on a choice: the player picks
                    # an option and the completion screen replaces the
                    # reply before they can read it. tools/check_story.py
                    # enforces this -- it caught exactly that here.
                    {
                        "kind": "dialogue",
                        "speaker": "Josh",
                        "text": (
                            "Get your team in order. Whoever answered, whoever you trust "
                            "with this.\n\n"
                            "I'm not opening that door until there's more than one of you. "
                            "Then we go north."
                        ),
                    },
                ],
                "rewards": {"gold": 300},
            },

            # ==========================================================
            # P4 -- the real fight, and the door to the rest of the game.
            # ==========================================================
            {
                "id": "p4_the_approach",
                "name": "The Approach",
                "summary": "Glacier 15 is four hours out and guarded.",
                "beats": [
                    {
                        "kind": "dialogue",
                        "speaker": "Josh",
                        "text": (
                            "There's a checkpoint on the last road in. It isn't Acatrya's. "
                            "It isn't anyone's, officially.\n\n"
                            "Which is how you know it's worth something."
                        ),
                    },
                    {
                        # LEVEL 3, NOT 4.
                        #
                        # This fight used to be balanced around the
                        # prologue handing you Josh, a 5-star, which made
                        # level 4 a formality. Now you bring whoever you
                        # pulled, so it was re-simulated against all 29
                        # possible partners at level 1: at level 4 the
                        # worst partner won 70% and four fell below 90%;
                        # at level 3 the mean is 98% and the worst is
                        # 80%. Losing retries rather than ending the run,
                        # so 80% is a fight you might lose once -- which
                        # is the right feeling for the last tutorial
                        # beat, where a coin flip is not.
                        "kind": "battle",
                        "enemies": ["Xender Henchmen", "Xender Henchmen"],
                        "level": 3,
                        "intro": (
                            "Two of them. **🎯 Switch target** is a free action — it doesn't "
                            "cost your turn, so pick who dies first.\n"
                            "**🛡️ Guard** halves incoming damage. Read the Incoming panel and "
                            "guard whoever's being aimed at."
                        ),
                        "on_win": "The road is clear. Nobody comes to find out why.",
                        "retry_on_loss": True,
                        "on_lose": "You pull back bloodied. Josh doesn't say anything about it.",
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Josh",
                        "text": (
                            "That's the last checkpoint. Everything past this is frozen and "
                            "empty and full of things that don't know the war ended.\n\n"
                            "You should get properly equipped before we go in. I'll wait. "
                            "I've waited eleven years."
                        ),
                    },
                    {
                        "kind": "unlock",
                        "feature": "adventure",
                        "text": (
                            "**`/adventure` is open.**\n\n"
                            "Expeditions are how you get strong enough for what's next — gear, "
                            "levels, materials. Regions unlock as the story reaches them.\n\n"
                            "Come back to `/story` when you're ready. Glacier 15 isn't going "
                            "anywhere."
                        ),
                    },
                ],
                "rewards": {"gold": 500, "reroll_tokens": 10},
            },

            # ==========================================================
            # P5 -- the base. Virtual is the game's engineer, so the HQ
            # and the daily loop arrive in her voice rather than in a
            # tooltip's.
            # ==========================================================
            {
                "id": "p5_the_signal_room",
                "name": "The Signal Room",
                "summary": "Virtual has been running Cascade off a car battery.",
                "beats": [
                    {
                        "kind": "dialogue",
                        "speaker": "Virtual",
                        "text": (
                            "Mind the cable. Mind *that* cable. That one's fine, it's "
                            "decorative.\n\n"
                            "You're the one from the lane. Josh said you didn't run. He says "
                            "that about maybe four people, so try not to let it go to your "
                            "head."
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Virtual",
                        "text": (
                            "This is what's left of Team Cascade's infrastructure: one "
                            "basement, one antenna, and whatever I can build out of what you "
                            "bring back.\n\n"
                            "It is not much. It is, however, *ours*, which is more than the "
                            "last three places we tried this."
                        ),
                    },
                    {
                        "kind": "unlock",
                        "feature": "base",
                        "text": (
                            "**`/hq` is open**, along with `/shrines`, `/harvesters` and "
                            "`/shop`.\n\n"
                            "Your HQ levels up and unlocks the rest. Harvesters generate "
                            "materials while you're offline, shrines give permanent stat "
                            "bonuses, and the shop trades in materials rather than gear.\n\n"
                            "None of it needs babysitting. Set it up, go do something else, "
                            "come back richer."
                        ),
                    },
                    {
                        "kind": "unlock",
                        "feature": "daily",
                        "text": (
                            "**`/daily` is open.**\n\n"
                            "One claim a day. Streaks pay better, so the cheapest way to get "
                            "stronger in this game is to show up."
                        ),
                    },
                    {
                        "kind": "choice",
                        "prompt": "Virtual watches you take in the room.",
                        "options": [
                            {
                                "id": "offer_help",
                                "label": "🔧 Offer to help build",
                                "text": (
                                    "\"Noted. I'll hold you to it — I hold everyone to it, "
                                    "it's why the antenna works.\""
                                ),
                                "sets": {"offered_virtual_help": True},
                            },
                            {
                                "id": "ask_cost",
                                "label": "💭 Ask what it cost to build",
                                "text": (
                                    "She doesn't look up. \"Two years and a friend. Next "
                                    "question.\""
                                ),
                                "sets": {"asked_virtual_cost": True},
                            },
                        ],
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Virtual",
                        "text": (
                            "Sader's at the map table and she's been waiting on you for an "
                            "hour, which for her is roughly a geological era.\n\n"
                            "Go. I have a car battery to lie to."
                        ),
                    },
                ],
                "rewards": {"gold": 250, "wood": 60, "stone": 60},
            },

            # ==========================================================
            # P6 -- domains. Sader Vorae flew at Glacier 15 and got out,
            # same as Josh, and she is the counterweight to him: he wants
            # to go back, she wants you to be ready first. That
            # disagreement is the prologue's actual argument.
            # ==========================================================
            {
                "id": "p6_the_map_table",
                "name": "The Map Table",
                "summary": "Sader Vorae would like a word about preparation.",
                "beats": [
                    {
                        "kind": "dialogue",
                        "speaker": "Sader Vorae",
                        "text": (
                            "You're the one Josh is planning around. Sit.\n\n"
                            "I flew the evac at Glacier 15. I got eleven people out and I "
                            "have counted them every night since, which is a thing I'm "
                            "telling you so you understand I'm not being dramatic when I say: "
                            "he wants to go back too early."
                        ),
                    },
                    {
                        "kind": "choice",
                        "prompt": "She turns the map around so it's facing you.",
                        "options": [
                            {
                                "id": "trust_josh",
                                "label": "🤝 Say Josh knows what he's doing",
                                "text": (
                                    "\"He does. That's the problem — he knows exactly what "
                                    "he's doing and he's going to do it anyway.\""
                                ),
                                "sets": {"sided_with_josh": True},
                            },
                            {
                                "id": "agree",
                                "label": "🧭 Agree that you're not ready",
                                "text": (
                                    "\"Good.\" Something unclenches in her shoulders. "
                                    "\"Then we have somewhere to start.\""
                                ),
                                "sets": {"sided_with_sader": True},
                            },
                            {
                                "id": "ask_glacier",
                                "label": "❄️ Ask what she saw up there",
                                "text": (
                                    "A long pause. \"Lights under the ice that shouldn't "
                                    "have been on. I'll tell you the rest when telling you "
                                    "helps.\""
                                ),
                                "sets": {"asked_sader_glacier": True},
                            },
                        ],
                    },
                    {
                        "kind": "unlock",
                        "feature": "domains",
                        "text": (
                            "**`/domains` is open.**\n\n"
                            "Single fights against a known enemy for direct rewards — no run "
                            "to commit to, no route to survive. They cost Energy, which "
                            "refills over time, so this is where a spare five minutes goes.\n\n"
                            "Tiers unlock as you clear regions and as your roster levels."
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Sader Vorae",
                        "text": (
                            "Run them until the numbers stop scaring you. Then run them "
                            "again.\n\n"
                            "I am not trying to slow you down. I am trying to make sure that "
                            "when you *do* go north, I only have to count you once."
                        ),
                    },
                ],
                "rewards": {"gold": 300, "reroll_tokens": 5},
            },

            # ==========================================================
            # P7 -- the close. No new mechanic, on purpose: the prologue
            # has handed over eight systems and the last thing it should
            # do is hand over a ninth. This one only does the story job
            # -- names the enemy, sets the destination, and lets the
            # player answer for themselves one more time.
            #
            # THIS is what completes the prologue.
            # ==========================================================
            {
                "id": "p7_what_we_do_now",
                "name": "What We Do Now",
                "summary": "Everyone in the room has already decided. They're waiting on you.",
                "beats": [
                    {
                        "kind": "dialogue",
                        "speaker": "Dolphe",
                        "text": (
                            "Sit down. All of you.\n\n"
                            "The two in the lane weren't muscle for hire. They were on a "
                            "payroll, and the payroll has a name on it: **Xender**. Which "
                            "would be a small story, except Xender is the company that "
                            "certified Glacier 15 as empty."
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Dolphe",
                        "text": (
                            "They signed a piece of paper that said nobody was there. Then "
                            "they sent people to make sure nobody went and looked.\n\n"
                            "That's not a cover-up any more. That's a schedule."
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Josh",
                        "text": (
                            "I've been saying this for two years to a room that kept telling "
                            "me I was grieving.\n\n"
                            "*He looks at you, not at her.* You're the first person who came "
                            "to the lane instead of the funeral."
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Bee Jee",
                        "text": (
                            "And you came back off it standing, which I'd like on the record "
                            "as partly my doing.\n\n"
                            "*She's smiling. She's also already restocking your kit.*"
                        ),
                    },
                    {
                        "kind": "choice",
                        "prompt": "Dolphe puts a hand flat on the table. \"So. What do we do now?\"",
                        "options": [
                            {
                                "id": "north",
                                "label": "❄️ \"We go to Glacier 15.\"",
                                "text": (
                                    "Josh exhales like he's been holding it since the lane. "
                                    "Sader says nothing, which from Sader is a vote.\n\n"
                                    "\"Then we go north,\" Dolphe says. \"Properly. "
                                    "Not tonight.\""
                                ),
                                "sets": {"chose_north": True},
                            },
                            {
                                "id": "proof",
                                "label": "📰 \"We prove it first.\"",
                                "text": (
                                    "\"Spoken like someone who's worked for me for a day,\" "
                                    "Dolphe says, and it's almost warm.\n\n"
                                    "Josh doesn't argue. He also doesn't agree."
                                ),
                                "sets": {"chose_proof": True},
                            },
                            {
                                "id": "people",
                                "label": "🫂 \"We find who's still alive.\"",
                                "text": (
                                    "The room goes quiet in a way the other answers wouldn't "
                                    "have caused.\n\n"
                                    "\"Four hundred and six,\" Dolphe says softly. \"I've "
                                    "never let myself say *still*.\""
                                ),
                                "sets": {"chose_survivors": True},
                            },
                        ],
                    },
                    {
                        "kind": "reward",
                        "text": "Dolphe slides a field advance across the table. It's most of what's left.",
                        "grant": {"gold": 600, "shards": 120, "reroll_tokens": 8},
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Dolphe",
                        "text": (
                            "Then that's what we do.\n\n"
                            "Go get strong enough to survive being right. `/adventure` for "
                            "runs, `/domains` when you've got five minutes, `/hq` to build "
                            "something that lasts. Come back to `/story` when you're ready "
                            "for the north.\n\n"
                            "**Welcome to Cascade.**"
                        ),
                    },
                ],
                "rewards": {"gold": 400},
                # THIS finishes the prologue -- moved off P4 when the
                # safehouse missions were added. A feature with no unlock
                # beat of its own opens here (see story_service), so
                # moving this marker also moves the Forge, the Lab, raids,
                # gifting and the Echo Exchange.
                "completes_prologue": True,
            },
        ],
    },
]


# ----------------------------------------------------------------------
# Lookups. Missions are addressed by a globally unique id, so nothing
# needs to know which chapter it's in to run it.
# ----------------------------------------------------------------------

def all_missions() -> list[dict]:
    return [m for chapter in CHAPTERS for m in chapter["missions"]]


def get_mission(mission_id: str) -> dict | None:
    return next((m for m in all_missions() if m["id"] == mission_id), None)


def get_chapter(chapter_id: str) -> dict | None:
    return next((c for c in CHAPTERS if c["id"] == chapter_id), None)


def chapter_of(mission_id: str) -> dict | None:
    for chapter in CHAPTERS:
        if any(m["id"] == mission_id for m in chapter["missions"]):
            return chapter
    return None


def mission_ids_in(chapter_id: str) -> list[str]:
    chapter = get_chapter(chapter_id)
    return [m["id"] for m in chapter["missions"]] if chapter else []


def prologue_mission_ids() -> list[str]:
    return mission_ids_in("prologue")


def feature_unlocked_by(feature: str) -> str | None:
    """Which mission turns `feature` on -- used to tell a player exactly
    what they need to do rather than "not available yet"."""
    for mission in all_missions():
        for beat in mission["beats"]:
            if beat.get("kind") == "unlock" and beat.get("feature") == feature:
                return mission["id"]
    return None
