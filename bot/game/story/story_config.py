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
    "abyss": "The Void Abyss",
}

# Features every player has from the moment they exist. Deliberately
# tiny: profile and help are how you find out what's going on, and story
# is the thing that unlocks everything else.
ALWAYS_AVAILABLE = frozenset({"profile", "help", "story", "characters"})


CHAPTERS: list[dict] = [
    {
        "id": "prologue",
        "name": "Prologue: Destruction Eruption",
        "blurb": (
            "You wake up in a lab that is coming apart around you, and you do not "
            "remember arriving."
        ),
        "unlocks_region": None,
        "missions": [
            # ==========================================================
            # PR1 -- the wake-up. Canon opening: the Player comes to
            # inside Ocellios Lab mid-collapse with Stubby's mechs hacked
            # and hostile, and neutralises them with electricity.
            #
            # The combat tutorial is therefore diegetic: the first fight
            # is the first thing that happens to you, and the four
            # buttons are the only thing between you and a mech.
            # ==========================================================
            {
                "id": "pr1_destruction_eruption",
                "name": "Destruction Eruption",
                "summary": "Ocellios Lab is coming down. You are inside it.",
                "beats": [
                    {
                        "kind": "dialogue",
                        "speaker": "Ocellios Lab",
                        "text": (
                            "**CONTAINMENT FAULT — SECTOR 9 — EVACUATE**\n\n"
                            "You come to on a floor that is at eleven degrees and getting "
                            "worse. There is a restraint frame beside you with the cuffs "
                            "already open.\n\n"
                            "You do not remember lying down in it."
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Ocellios Lab",
                        "text": (
                            "Something has gone through the lab's mech control and left it "
                            "wrong. A D-class unit turns towards you and does not run its "
                            "greeting routine.\n\n"
                            "Your hands are producing light. That is new information, and "
                            "there is no time to have feelings about it."
                        ),
                    },
                    {
                        "kind": "battle",
                        "enemies": ["Rogue Security Drone"],
                        "level": 2,
                        "intro": "It has decided you are debris that moved.",
                        "on_win": (
                            "The arc goes through it and out the far wall. The mech drops.\n\n"
                            "You look at your hands for slightly too long."
                        ),
                        "on_lose": "The floor tilts and takes you with it. You wake up again.",
                    },
                    {
                        "kind": "choice",
                        "prompt": "There is a door east and the ceiling is not going to hold.",
                        "options": [
                            {
                                "id": "run",
                                "label": "🏃 Get out. Now.",
                                "text": (
                                    "You do not look back at the restraint frame. Later you "
                                    "will wonder whether that was instinct or training."
                                ),
                                "sets": {"pro_ran": True},
                            },
                            {
                                "id": "look",
                                "label": "🔎 Look at the frame first",
                                "text": (
                                    "Your own weight is logged on the chart. Eleven months of "
                                    "readings, and the earliest entry is older than anything "
                                    "you can remember.\n\n"
                                    "Then the ceiling comes down and the question goes with it."
                                ),
                                "sets": {"pro_looked": True},
                            },
                        ],
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Ocellios Lab",
                        "text": (
                            "You come out into weather.\n\n"
                            "East, past the fence line, the ground goes white and stays "
                            "white. There is a city out there under the ice, and everything "
                            "you have on you is what you woke up wearing."
                        ),
                    },
                ],
                "rewards": {"gold": 120},
            },

            # ==========================================================
            # PR2 -- gear, from a locker rather than a mentor. Nobody has
            # met you yet; the tutorial has to be the world for a while
            # longer.
            # ==========================================================
            {
                "id": "pr2_field_salvage",
                "name": "Field Salvage",
                "summary": "A supply locker that survived better than the building did.",
                "beats": [
                    {
                        "kind": "dialogue",
                        "speaker": "Ocellios Lab",
                        "text": (
                            "A staging locker, buckled but shut. Ocellios kitted its field "
                            "teams properly — whatever else the place was, it was funded.\n\n"
                            "The lock is electronic. You are, apparently, electricity."
                        ),
                    },
                    {
                        "kind": "reward",
                        "text": "It opens with a noise like a struck bell.",
                        "grant": {"item": "uncommon", "gold": 180, "wood": 30, "stone": 30},
                    },
                    {
                        "kind": "unlock",
                        "feature": "inventory",
                        "text": (
                            "**`/inventory` is open.**\n\n"
                            "Equip it — unequipped gear does nothing at all. Items level up "
                            "with gold and materials, and every piece has substats you can "
                            "reroll later.\n\n"
                            "`/stash` holds your currencies and materials. `/sell_rarity` "
                            "clears out a whole tier at once when you outgrow it."
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Ocellios Lab",
                        "text": (
                            "There's a jacket in there too, three sizes wrong, and a ration "
                            "bar with eight months on the clock.\n\n"
                            "You eat it walking. East is the only direction that isn't on "
                            "fire."
                        ),
                    },
                ],
                "rewards": {"gold": 150},
            },

            # ==========================================================
            # PR3 -- the crossing, and quests.
            #
            # Canon: the Player survives Glacier 15 by powering heat
            # beacons. A chain of standing objectives that pay out as you
            # reach them IS the quest system, so /quests arrives as the
            # literal mechanic keeping you alive rather than as a menu.
            # ==========================================================
            {
                "id": "pr3_heat_beacons",
                "name": "Heat Beacons",
                "summary": "The cold is not a mood. It is a timer.",
                "beats": [
                    {
                        "kind": "dialogue",
                        "speaker": "Glacier 15",
                        "text": (
                            "Two hours out from the lab the shivering stops, which you are "
                            "fairly sure is the bad version.\n\n"
                            "Then: a post. Waist-high, iced over, with a dead lamp on top "
                            "and a socket at the base shaped like nothing in particular."
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Glacier 15",
                        "text": (
                            "You put your hand on it because you have no better ideas.\n\n"
                            "The lamp comes up amber. Heat rolls off the post hard enough to "
                            "hurt, and forty metres east another one answers it.\n\n"
                            "Somebody built a road out of these. Somebody expected to be "
                            "walking home in the dark."
                        ),
                    },
                    {
                        "kind": "unlock",
                        "feature": "quests",
                        "text": (
                            "**`/quests` is open.**\n\n"
                            "Standing objectives that pay out as you go — some one-off, some "
                            "resetting. You don't stop and *do* quests; you play, and the "
                            "quests notice.\n\n"
                            "The beacon line works the same way. Reach the next one and it "
                            "pays you in not freezing to death."
                        ),
                    },
                    {
                        "kind": "reward",
                        "text": "The beacon's service cache pops open at your feet.",
                        "grant": {"gold": 200, "permafrost_ore": 25},
                    },
                ],
                "rewards": {"gold": 150},
            },

            # ==========================================================
            # PR4 -- first contact. Nebula and Gostley, sent out by Dolphe
            # to investigate the anomaly on Cascade's radar.
            #
            # The anomaly is you.
            #
            # This is where /pull and /squad arrive: the beacon network
            # can raise Cascade, and Cascade answers with people.
            # ==========================================================
            {
                "id": "pr4_the_anomaly",
                "name": "The Anomaly",
                "summary": "Team Cascade sent two people to find out what you are.",
                "beats": [
                    {
                        "kind": "dialogue",
                        "speaker": "Nebula",
                        "text": (
                            "Stop there. Hands where the light is.\n\n"
                            "*A woman on the ridge with climbing irons on her boots and a "
                            "rifle she has not pointed at you.* You lit four beacons in a row "
                            "on a network that has been dead for two years. You're the "
                            "anomaly we came out for."
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Gostley",
                        "text": (
                            "*The second one has been standing behind you for some time.*\n\n"
                            "\"It came from the lab.\"\n\n"
                            "He does not say it unkindly. He says it the way you'd read a "
                            "label."
                        ),
                    },
                    {
                        "kind": "choice",
                        "prompt": "Nebula lowers the light. \"Alright. What are you?\"",
                        "options": [
                            {
                                "id": "dont_know",
                                "label": "🌀 \"I don't know.\"",
                                "text": (
                                    "\"...Right,\" she says, and something in her recalculates. "
                                    "\"Gostley, that's an honest answer. Nobody rehearses "
                                    "*that* one.\""
                                ),
                                "sets": {"pro_honest": True},
                            },
                            {
                                "id": "lab",
                                "label": "⚡ Tell them about the lab",
                                "text": (
                                    "Nebula's jaw sets. \"Ocellios went up two hours ago. "
                                    "You walked out of it. On foot. In this.\"\n\n"
                                    "Gostley, quietly: \"That's not the impressive part.\""
                                ),
                                "sets": {"pro_told_lab": True},
                            },
                            {
                                "id": "silent",
                                "label": "🐱 Say nothing",
                                "text": (
                                    "The silence goes on long enough that Gostley makes a "
                                    "sound that might be approval.\n\n"
                                    "\"Fine,\" says Nebula. \"Be like that. Be like that "
                                    "*indoors*, you're grey.\""
                                ),
                                "sets": {"pro_silent": True},
                            },
                        ],
                    },
                    {
                        "kind": "reward",
                        "text": "Nebula puts a Cascade relay tag in your hand and closes your fingers on it.",
                        "grant": {"shards": 480, "item": "uncommon"},
                    },
                    {
                        "kind": "unlock",
                        "feature": "pull",
                        "text": (
                            "**`/pull` is open.** 120 <:shard:1534383382924890192> a pull; "
                            "the 10x is exactly ten times that, so there's no penalty for "
                            "going one at a time.\n\n"
                            "Cascade is a decentralised network of cells. The tag broadcasts; "
                            "whoever is close enough and willing comes to you.\n\n"
                            "A duplicate is never wasted — the first five copies of anyone "
                            "permanently upgrade them, and every copy pays **Echoes**."
                        ),
                    },
                    {
                        "kind": "unlock",
                        "feature": "squad",
                        "text": (
                            "**`/squad` is open.** Four slots, any character in any slot.\n\n"
                            "The strongest shape is at least one **Amplifier** and one "
                            "**Sustain** — a good Amplifier is worth more than a fourth "
                            "attacker. `/characters` shows anyone's full stats and kit."
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Nebula",
                        "text": (
                            "Base is east and we are not walking it as three.\n\n"
                            "Call somebody. I mean it — the last stretch runs along the "
                            "drift line, and things have been coming up through the drift "
                            "line all week."
                        ),
                    },
                ],
                "rewards": {"gold": 250},
            },

            # ==========================================================
            # PR5 -- the worm. Canon, and the prologue's real fight.
            #
            # In the timeline it is escaped rather than killed, so the
            # beat is written as driving it back under: the win condition
            # is surviving contact, and the text says so. The engine
            # needs a winner; the fiction doesn't have to pretend that's
            # the same as a kill.
            # ==========================================================
            {
                "id": "pr5_through_the_drift",
                "name": "Through the Drift",
                "summary": "Something has been following the beacon line from underneath.",
                "beats": [
                    {
                        "kind": "dialogue",
                        "speaker": "Gostley",
                        "text": (
                            "Stop walking.\n\n"
                            "*He has his hand flat on the ice.*\n\n"
                            "\"It's been under us since the third beacon. It's been waiting "
                            "for the ground to get thin.\""
                        ),
                    },
                    {
                        # THE WORM IS NOT THE FIGHT. It is the hazard.
                        #
                        # Canon says the Player *narrowly escapes* it, and
                        # the engine agrees: the Driller Prototype is a
                        # boss-tier template and measured 0% winnable at
                        # every level from 1 to 5 against the two-character
                        # party this beat is gated to. Elite and boss
                        # templates carry 200-520 base HP against the
                        # 40-58 of a combat-tier enemy, so no amount of
                        # level tuning reaches them this early.
                        #
                        # So the fight is its escort -- combat-tier, and
                        # measured winnable -- and the worm stays exactly
                        # what the timeline says it is: a thing you get
                        # away from. It comes back as a boss later, when
                        # a squad can actually meet it.
                        "kind": "battle",
                        "enemies": ["Concussion Drone", "Xender Recon Scout"],
                        "level": 3,
                        "intro": (
                            "The drift opens. What comes out of it is machined, sectioned, "
                            "and far too long to see the end of — and it has *minders*, two "
                            "of them, riding the segment plates.\n\n"
                            "*You are not going to kill that thing. You are going to get out "
                            "from under it, and its escort is in the way.*"
                        ),
                        "on_win": (
                            "The last minder goes down and the worm, uninterested now that "
                            "nothing is signalling, folds and slides back through its own "
                            "entry hole.\n\n"
                            "The ice keeps shaking for a long time after it's gone."
                        ),
                        "on_lose": (
                            "Nebula gets a hand under your arm and hauls. You lose ground, "
                            "and you go again."
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Nebula",
                        "text": (
                            "That's Xender plant. Prototype frame, Boss John's fingerprints "
                            "all over the drive assembly.\n\n"
                            "Which is *fascinating*, because Xender's official position is "
                            "that there is nothing at Glacier 15 worth drilling for."
                        ),
                    },
                    {
                        "kind": "unlock",
                        "feature": "adventure",
                        "text": (
                            "**`/adventure` is open.**\n\n"
                            "Full expedition runs — gear, levels, materials. Regions unlock "
                            "in order and harder ones pay more.\n\n"
                            "This is where you get strong enough for the next thing the "
                            "story asks of you. It will keep asking."
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Gostley",
                        "text": (
                            "*He is looking at the hole, not at you.*\n\n"
                            "\"It didn't surface for us. We walked this line yesterday.\"\n\n"
                            "\"It surfaced for the thing that lights beacons.\""
                        ),
                    },
                ],
                "rewards": {"gold": 500, "reroll_tokens": 10},
            },

            # ==========================================================
            # PR6 -- the base, Virtual, and the systems that run while
            # you're gone.
            # ==========================================================
            {
                "id": "pr6_forward_base",
                "name": "Forward Base",
                "summary": "Team Cascade has been living in a dead city for two years.",
                "beats": [
                    {
                        "kind": "dialogue",
                        "speaker": "Virtual",
                        "text": (
                            "Mind the cable. Mind *that* cable. That one's decorative.\n\n"
                            "So you're the anomaly. You're shorter than the radar made you "
                            "look."
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Virtual",
                        "text": (
                            "This is everything Cascade has this far north: one heated shell, "
                            "one relay, and whatever I can build out of what people drag "
                            "home.\n\n"
                            "It is not much. It is, however, *ours*, which is more than the "
                            "last three places we tried this."
                        ),
                    },
                    {
                        "kind": "unlock",
                        "feature": "base",
                        "text": (
                            "**`/hq` is open**, with `/shrines`, `/harvesters` and `/shop`.\n\n"
                            "Your HQ levels up and unlocks the rest. Harvesters generate "
                            "materials while you're offline, shrines give permanent stat "
                            "bonuses, and the shop trades materials rather than gear.\n\n"
                            "None of it needs babysitting. Set it going and come back richer."
                        ),
                    },
                    {
                        "kind": "unlock",
                        "feature": "daily",
                        "text": (
                            "**`/daily` is open.**\n\n"
                            "One claim a day, and streaks pay better. The cheapest way to get "
                            "stronger in this game is to show up."
                        ),
                    },
                    {
                        "kind": "choice",
                        "prompt": "Virtual watches you take in the room.",
                        "options": [
                            {
                                "id": "help",
                                "label": "🔧 Offer to help build",
                                "text": (
                                    "\"Noted. I'll hold you to it — I hold everyone to it, "
                                    "it's why the relay works.\""
                                ),
                                "sets": {"pro_offered_help": True},
                            },
                            {
                                "id": "cost",
                                "label": "💭 Ask what it cost to build",
                                "text": (
                                    "She doesn't look up. \"Two years and a friend. Next "
                                    "question.\""
                                ),
                                "sets": {"pro_asked_cost": True},
                            },
                        ],
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Virtual",
                        "text": (
                            "Dolphe's at the map table and he's been told three separate "
                            "versions of what you are.\n\n"
                            "Go and be the fourth."
                        ),
                    },
                ],
                "rewards": {"gold": 300, "wood": 60, "stone": 60, "item": "rare"},
            },

            # ==========================================================
            # PR7 -- Dolphe. HE, not she: File C-000 is unambiguous, and
            # an earlier draft of this prologue had it wrong throughout.
            # ==========================================================
            {
                "id": "pr7_the_map_table",
                "name": "The Map Table",
                "summary": "The leader of Team Cascade would like to know what he has picked up.",
                "beats": [
                    {
                        "kind": "dialogue",
                        "speaker": "Dolphe",
                        "text": (
                            "I ran a newspaper for seventeen years. Then Glacier 15 happened, "
                            "four hundred and six people stopped existing on paper, and I "
                            "found out what my press was actually worth.\n\n"
                            "So now I run this. Sit down."
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Dolphe",
                        "text": (
                            "Nebula says you don't know what you are. Gostley says you came "
                            "out of Ocellios. Virtual says your resonance signature doesn't "
                            "match anything in the library.\n\n"
                            "*He turns the map to face you.*\n\n"
                            "I'm choosing to find that interesting rather than alarming. "
                            "People tell me that's my worst habit."
                        ),
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
                        "kind": "choice",
                        "prompt": "\"One question, and answer it however you like.\"",
                        "options": [
                            {
                                "id": "stay",
                                "label": "🤝 \"I'd like to stay.\"",
                                "text": (
                                    "\"Then you're staying.\" No paperwork, no vote. You "
                                    "will learn that this is exactly how Dolphe does "
                                    "everything, and exactly how it goes wrong."
                                ),
                                "sets": {"pro_joined_willing": True},
                            },
                            {
                                "id": "useful",
                                "label": "⚡ \"I'd like to be useful.\"",
                                "text": (
                                    "\"Careful. People who lead with *useful* tend to have "
                                    "been treated as equipment.\"\n\n"
                                    "He lets that sit exactly one second too long."
                                ),
                                "sets": {"pro_joined_useful": True},
                            },
                            {
                                "id": "answers",
                                "label": "🔎 \"I want to know what was done to me.\"",
                                "text": (
                                    "\"Good. That's a motive I can plan around.\"\n\n"
                                    "\"And it's the same file as mine, which should worry "
                                    "us both.\""
                                ),
                                "sets": {"pro_joined_answers": True},
                            },
                        ],
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Dolphe",
                        "text": (
                            "Welcome to Team Cascade. Nobody will explain the coffee rota and "
                            "you will be expected to know it.\n\n"
                            "Get some sleep. There's a man coming in off the shelf tomorrow "
                            "and I'd rather you met him rested."
                        ),
                    },
                ],
                "rewards": {"gold": 400, "reroll_tokens": 6, "item": "rare"},
            },

            # ==========================================================
            # PR8 -- the close, and the first thread of the real story.
            #
            # No new mechanic on purpose: the prologue has handed over
            # eight systems and the last thing it should do is hand over
            # a ninth. What it does instead is plant R -- unnamed, one
            # letter, mentioned by nobody who understands it yet.
            # ==========================================================
            {
                "id": "pr8_someone_got_here_first",
                "name": "Someone Got Here First",
                "summary": "Gostley found something in the drift and nobody likes it.",
                "beats": [
                    {
                        "kind": "dialogue",
                        "speaker": "Gostley",
                        "text": (
                            "I went back to the hole.\n\n"
                            "*He puts a plate of sectioned metal on the table. It is cut, not "
                            "broken — one pass, clean, through a driller frame that ate a "
                            "reinforced beacon post without slowing down.*"
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Virtual",
                        "text": (
                            "That's not us. That's not Xender either — nobody at Xender is "
                            "issuing cutting gear that does *that*, I'd know, I've stolen "
                            "their catalogue.\n\n"
                            "Somebody put this thing down after we walked away. Somebody who "
                            "was already out there."
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Nebula",
                        "text": (
                            "There's a mark on the underside. One letter, scored in after the "
                            "cut.\n\n"
                            "**R.**\n\n"
                            "*Nobody in the room has anything to add. Dolphe writes it on the "
                            "map anyway, because that is what he does with things he doesn't "
                            "understand yet.*"
                        ),
                    },
                    {
                        "kind": "choice",
                        "prompt": "Dolphe looks up. \"Opinions. Anyone.\"",
                        "options": [
                            {
                                "id": "helped",
                                "label": "🙂 \"Whoever it was, they helped us.\"",
                                "text": (
                                    "\"They killed something that was hunting us,\" Dolphe "
                                    "agrees. \"That isn't the same as helping. It's the same "
                                    "as *arriving first*.\""
                                ),
                                "sets": {"pro_r_friendly": True},
                            },
                            {
                                "id": "signature",
                                "label": "🔻 \"People who sign their work want it found.\"",
                                "text": (
                                    "The room goes quiet.\n\n"
                                    "\"Yes,\" says Gostley, to nobody. \"They do.\""
                                ),
                                "sets": {"pro_r_signature": True},
                            },
                            {
                                "id": "worry",
                                "label": "🗡️ \"I want to know what cuts like that.\"",
                                "text": (
                                    "Virtual turns the plate over twice. \"So do I. And I "
                                    "build the things that cut.\""
                                ),
                                "sets": {"pro_r_weapon": True},
                            },
                        ],
                    },
                    {
                        "kind": "reward",
                        "text": "Dolphe advances you a field allowance out of a fund that is mostly optimism.",
                        "grant": {"gold": 600, "shards": 120, "reroll_tokens": 8, "item": "rare"},
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Dolphe",
                        "text": (
                            "Sleep. Build something. Go and get strong.\n\n"
                            "`/adventure` for runs, `/domains` for five spare minutes, `/hq` "
                            "for the long game. Come back to `/story` when you're ready.\n\n"
                            "**Welcome to Cascade.** The man off the shelf gets here at dawn "
                            "and his name is Josh."
                        ),
                    },
                ],
                "rewards": {"gold": 400},
                "completes_prologue": True,
            },
        ],
    },

    {
        "id": "ch1",
        "name": "Chapter 1: What Josh Owes",
        "blurb": (
            "A survivor with a debt, a letter carved into wreckage, and somebody who "
            "keeps getting there first."
        ),
        "unlocks_region": "Glacier 15",
        "missions": [
            # ==========================================================
            # C1M1 -- Josh.
            #
            # HIS VOICE IS BROKEN ENGLISH, and that is canon, not
            # characterisation I invented: "Im just try to live, but
            # people say it bad." An earlier draft wrote him fluent and
            # clipped, which quietly turned the roster's most distinctive
            # character into a generic soldier.
            #
            # Two unlocks, both about reaching other people, because
            # that's what Josh has come to ask for.
            # ==========================================================
            {
                "id": "c1m1_the_man_off_the_shelf",
                "name": "The Man Off the Shelf",
                "summary": "He walked here. From the shelf. In that.",
                "beats": [
                    {
                        "kind": "dialogue",
                        "speaker": "Josh",
                        "text": (
                            "Im hear you got the beacons on.\n\n"
                            "*He is yellow, underfed, and has walked in from a direction "
                            "with nothing in it.* Two year them lights is off. Two year Im "
                            "ask people to turn them on. Then you come and just — do it."
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Josh",
                        "text": (
                            "Im from here. Glacier 15. Before.\n\n"
                            "Everyone say Glacier 15 people not exist no more. Im standing "
                            "here, so that a lie, but Im the only one Im can prove."
                        ),
                    },
                    {
                        "kind": "choice",
                        "prompt": "He hasn't sat down. He doesn't seem to think he's allowed to.",
                        "options": [
                            {
                                "id": "sit",
                                "label": "🪑 Push a chair towards him",
                                "text": (
                                    "He looks at it like it might be a trick. Then he sits, "
                                    "very carefully, on the front third of it.\n\n"
                                    "\"...Thanks,\" he says. It is the only word he says "
                                    "properly."
                                ),
                                "sets": {"c1_kind_to_josh": True},
                            },
                            {
                                "id": "ask_who",
                                "label": "❓ Ask who you'd be proving it for",
                                "text": (
                                    "Everything in his face shuts at once.\n\n"
                                    "\"...Rex,\" he says. \"Him name Rex.\" And then "
                                    "nothing else, for a while."
                                ),
                                "sets": {"c1_asked_rex": True},
                            },
                            {
                                "id": "blunt",
                                "label": "🧊 Ask what he wants from Cascade",
                                "text": (
                                    "\"Good. Straight. Im like straight.\"\n\n"
                                    "\"Im want people. Im can't do it alone no more, Im try "
                                    "two year.\""
                                ),
                                "sets": {"c1_blunt_with_josh": True},
                            },
                        ],
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Dolphe",
                        "text": (
                            "Then you'll have people. That's the entire point of us.\n\n"
                            "*To you:* Cascade runs on cells passing things to each other — "
                            "supplies, names, favours. If you're going to work with him "
                            "you'd better know how that works."
                        ),
                    },
                    {
                        "kind": "unlock",
                        "feature": "gifting",
                        "text": (
                            "**`/gift` and `/gifts` are open.**\n\n"
                            "Send materials and currency to other players and collect what "
                            "they send you. There's a cap per window, so nobody can be farmed "
                            "as a mule — it's for helping somebody over a wall, not for "
                            "running an economy through a friend."
                        ),
                    },
                    {
                        "kind": "unlock",
                        "feature": "exchange",
                        "text": (
                            "**`/exchange` is open.**\n\n"
                            "Every duplicate you have ever pulled paid **Echoes**. Spend them "
                            "on *exactly* the character you want — no rates, no pity, no "
                            "luck.\n\n"
                            "Buying somebody you already own raises their **Resonance** "
                            "instead, which is the deterministic way to push a favourite."
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Josh",
                        "text": (
                            "One thing. Before you say yes.\n\n"
                            "Someone else out there. Been out there long time, before you, "
                            "before Cascade come back. Him don't want the city found.\n\n"
                            "Im not say him name in this room."
                        ),
                    },
                ],
                "rewards": {"gold": 500, "echoes": 40},
            },

            # ==========================================================
            # C1M2 -- the first fight of the chapter, and the first time
            # R is ahead of the party rather than behind them.
            # ==========================================================
            {
                "id": "c1m2_the_cut_line",
                "name": "The Cut Line",
                "summary": "Xender is digging where Xender says there is nothing.",
                "beats": [
                    {
                        "kind": "dialogue",
                        "speaker": "Nebula",
                        "text": (
                            "Survey camp, four hours old, and it's been abandoned in a "
                            "hurry.\n\n"
                            "Xender kit, Xender rations, Xender everything. On a site their "
                            "own inspection slips certify as empty. Somebody is lying and "
                            "they're not even being careful about it."
                        ),
                    },
                    {
                        "kind": "battle",
                        "enemies": ["Xender Tank", "Xender Henchmen", "Xender Henchmen"],
                        "level": 4,
                        "intro": "The rear guard came back for the equipment. You're standing in it.",
                        "on_win": (
                            "The last one goes down still trying to raise a channel that "
                            "nobody is answering."
                        ),
                        "on_lose": "Too many, too fast. Josh gets a shoulder under you and runs.",
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Josh",
                        "text": (
                            "Look the tents. Look them.\n\n"
                            "*Six tents. Four are cut open, one pass each, from outside.*\n\n"
                            "Them not run from us. Them already run from someone."
                        ),
                    },
                    {
                        "kind": "reward",
                        "text": "The camp's stores are intact. Whoever came through wasn't here for supplies.",
                        "grant": {"gold": 350, "permafrost_ore": 30, "metal": 40, "item": "rare"},
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Gostley",
                        "text": (
                            "*He is crouched at the fourth tent, looking at the cut.*\n\n"
                            "\"Same edge as the driller.\"\n\n"
                            "\"He's not following Xender. He's following whoever gets close "
                            "to the city.\""
                        ),
                    },
                ],
                "rewards": {"gold": 400, "reroll_tokens": 6},
            },

            # ==========================================================
            # C1M3 -- the Forge, at the far end of a supply line that
            # doesn't exist.
            # ==========================================================
            {
                "id": "c1m3_no_supply_line",
                "name": "No Supply Line",
                "summary": "Virtual has found a shed and is extremely happy about it.",
                "beats": [
                    {
                        "kind": "dialogue",
                        "speaker": "Virtual",
                        "text": (
                            "Bench. Vice. Power. *Roof.* I could cry.\n\n"
                            "We are four hundred kilometres from a shop and nothing is "
                            "getting resupplied out here. From now on, if you want it, we "
                            "make it."
                        ),
                    },
                    {
                        "kind": "unlock",
                        "feature": "forge",
                        "text": (
                            "**`/forge` is open.**\n\n"
                            "Craft gear in the **slot and rarity you choose** — no rolling "
                            "for the piece you actually need. You can also reforge substats, "
                            "transfer an upgrade level between items, and salvage what you "
                            "don't want back into materials.\n\n"
                            "Crafting starts at **Rare**. Below that the drops are already "
                            "better than the recipe."
                        ),
                    },
                    {
                        "kind": "choice",
                        "prompt": "She's already sorting your salvage into piles.",
                        "options": [
                            {
                                "id": "learn",
                                "label": "🔨 Ask her to show you properly",
                                "text": (
                                    "\"Finally.\" She clears the bench with her forearm. "
                                    "\"Sit. This takes an hour and saves you a month.\""
                                ),
                                "sets": {"c1_learned_forge": True},
                            },
                            {
                                "id": "rush",
                                "label": "⏱️ Tell her there isn't time",
                                "text": (
                                    "\"There's never time. That's how people end up on a "
                                    "shelf in gear that was fine for a corridor.\"\n\n"
                                    "She hands you the schematic anyway."
                                ),
                                "sets": {"c1_rushed_forge": True},
                            },
                        ],
                    },
                    {
                        "kind": "reward",
                        "text": "She empties the shed into your pack on principle.",
                        "grant": {"metal": 80, "crystal": 40, "permafrost_ore": 50, "gold": 300, "item": "epic"},
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Josh",
                        "text": (
                            "*He has been standing in the doorway the whole time, not coming "
                            "in.*\n\n"
                            "\"Rex do this. Fix thing. Him fix my boot four time.\"\n\n"
                            "\"Him not good at it.\" A pause. \"Him keep doing it anyway.\""
                        ),
                    },
                ],
                "rewards": {"gold": 350},
            },

            # ==========================================================
            # C1M4 -- the Lab, and the name.
            #
            # R stops being a letter here. He does not appear; he is
            # simply demonstrated to have been present, repeatedly, for
            # longer than anyone has been looking.
            # ==========================================================
            {
                "id": "c1m4_the_letter",
                "name": "The Letter",
                "summary": "Two years of logs, and somebody is in all of them.",
                "beats": [
                    {
                        "kind": "dialogue",
                        "speaker": "Virtual",
                        "text": (
                            "I pulled the survey camp's recorder. It's not one camp's worth "
                            "of data — they've been feeding a chain since the incident.\n\n"
                            "Two years of it. It's going to take real work to get anything "
                            "usable out."
                        ),
                    },
                    {
                        "kind": "unlock",
                        "feature": "lab",
                        "text": (
                            "**`/lab` is open.**\n\n"
                            "The Research Lab turns time and materials into **permanent, "
                            "account-wide upgrades** — loot rarity, gacha pity, expedition "
                            "yield. Projects run in the background whether you're playing or "
                            "not.\n\n"
                            "Nothing in it is a consumable. Everything you finish, you keep."
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Virtual",
                        "text": (
                            "Here's the first thing out of the decrypt, and I want somebody "
                            "else to say it so it isn't only me.\n\n"
                            "Xender has lost **nineteen** survey teams at Glacier 15 in two "
                            "years. Nineteen. They keep sending them and they keep not coming "
                            "back, and they have never once filed it as hostile action."
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Nebula",
                        "text": (
                            "Because filing it means admitting there's somebody up here.\n\n"
                            "And every one of the nineteen has the same field note attached "
                            "before it stops. Not a report. A *name they were told*."
                        ),
                    },
                    {
                        "kind": "choice",
                        "prompt": "Josh has gone very still. \"Say it,\" he says. \"Im already know.\"",
                        "options": [
                            {
                                "id": "read",
                                "label": "📄 Read it out",
                                "text": (
                                    "\"**Mr. R sends his regards.**\"\n\n"
                                    "Josh puts both hands on the table. \"Rohan,\" he says. "
                                    "\"Him name Rohan. Him were there when Rex die.\""
                                ),
                                "sets": {"c1_read_the_name": True},
                            },
                            {
                                "id": "let_josh",
                                "label": "🤝 Let Josh say it",
                                "text": (
                                    "\"Rohan,\" Josh says, to the table. \"Him call himself "
                                    "Mr. R now. Like it a joke.\"\n\n"
                                    "\"Him were there when Rex die. Im the only one who see "
                                    "him, so Im the only one who lying.\""
                                ),
                                "sets": {"c1_josh_said_it": True},
                            },
                        ],
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Dolphe",
                        "text": (
                            "Two years ago a man told me the same thing in my own newsroom "
                            "and I printed a correction about it.\n\n"
                            "*He is not looking at Josh.*\n\n"
                            "I owe you a retraction. You'll get it in print, with my name on "
                            "it. After."
                        ),
                    },
                ],
                "rewards": {"gold": 600, "reroll_tokens": 8, "crystal": 60, "item": "rare"},
            },

            # ==========================================================
            # C1M5 -- the chapter boss, and raids.
            #
            # Rohan does not fight you here and is not seen. What you
            # fight is the thing he left switched on, which is the honest
            # shape of a first chapter: the antagonist is established by
            # the size of what he can afford to abandon.
            #
            # Raids unlock here because this is the first thing in the
            # story a squad demonstrably cannot finish.
            # ==========================================================
            {
                "id": "c1m5_what_he_left_on",
                "name": "What He Left Switched On",
                "summary": "Nineteen teams did not come back. This is what stopped them.",
                "beats": [
                    {
                        "kind": "dialogue",
                        "speaker": "Virtual",
                        "text": (
                            "Power draw just went somewhere and it all went *down*.\n\n"
                            "Ninety-one percent of this site's load for two years has gone "
                            "to one unlabelled circuit. It just woke up."
                        ),
                    },
                    {
                        "kind": "battle",
                        "enemies": ["Permafrost Guardian"],
                        "level": 11,
                        "intro": (
                            "It doesn't come through the door. It comes through the wall "
                            "beside the door, which was, on reflection, always an option.\n\n"
                            "*It is alone. It does not appear to think it needs help.*"
                        ),
                        "on_win": (
                            "It goes down on one knee and stops. It does not power off. It "
                            "is simply waiting, which is worse."
                        ),
                        "on_lose": "You get out. Not with everything you went in with.",
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Gostley",
                        "text": (
                            "*He has found the maker's plate and is holding it out.*\n\n"
                            "\"It's Eris frame. Pre-collapse. Somebody woke it up and pointed "
                            "it at the stairs.\"\n\n"
                            "\"He didn't build this. He *found* it. That's worse.\""
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Josh",
                        "text": (
                            "Him always find thing. Him say him got divine power, everyone "
                            "laugh.\n\n"
                            "Nobody laugh at nineteen team."
                        ),
                    },
                    {
                        "kind": "unlock",
                        "feature": "raids",
                        "text": (
                            "**`/raid` is open.**\n\n"
                            "A server-wide boss that everyone in your Discord fights "
                            "*together*, across several difficulties. Damage is tracked and "
                            "rewarded by contribution, and `/raid_claim` collects your share "
                            "once it ends. **`/leaderboard`** opens with it.\n\n"
                            "This is the first thing in this story a squad of four cannot "
                            "finish. It will not be the last."
                        ),
                    },
                    {
                        "kind": "choice",
                        "prompt": "Dolphe, on the relay: \"I need a headline and I need it true.\"",
                        "options": [
                            {
                                "id": "nineteen",
                                "label": "📰 \"Xender has lost nineteen teams and filed none of them.\"",
                                "text": (
                                    "\"That one they'll sue over.\" A pause you could park "
                                    "an airship in. \"Good. Let them explain the other "
                                    "eighteen under oath.\""
                                ),
                                "sets": {"c1_headline_nineteen": True},
                            },
                            {
                                "id": "name",
                                "label": "🔻 \"Print the name. Mr. R.\"",
                                "text": (
                                    "\"If I print that and I'm wrong, I finish Josh a second "
                                    "time.\"\n\n"
                                    "*Long silence.* \"...Set it. I'll decide at the press.\""
                                ),
                                "sets": {"c1_headline_name": True},
                            },
                            {
                                "id": "hold",
                                "label": "🤐 \"Don't print anything yet.\"",
                                "text": (
                                    "\"You're the third person to tell me that this month "
                                    "and the first one I've believed.\""
                                ),
                                "sets": {"c1_headline_hold": True},
                            },
                        ],
                    },
                    {
                        "kind": "reward",
                        "text": "The Guardian's core comes out intact. Virtual takes it like it's a bird.",
                        "grant": {"gold": 900, "shards": 240, "crystal": 80, "permafrost_ore": 100, "item": "epic"},
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Josh",
                        "text": (
                            "Im not ask you to help me kill him.\n\n"
                            "*He is looking at the thing on one knee.*\n\n"
                            "Im ask you help me make people know him real. Killing him easy "
                            "part. Im been ready for that two year.\n\n"
                            "*Chapter 2 isn't written yet — but `/raid`, `/lab` and the Forge "
                            "are, and you're going to need all three.*"
                        ),
                    },
                ],
                "rewards": {"gold": 800, "reroll_tokens": 12},
            },
        ],
    },
    {
        "id": "ch2",
        "name": "Chapter 2: Two Hundred Crates",
        "blurb": (
            "The freight leaves Glacier 15 heading north with no contents listed. "
            "Somebody has been shipping something for two years."
        ),
        "unlocks_region": "The Wastelands",
        "missions": [
            # ==========================================================
            # C2M1 -- the road, and the first time the party disagrees
            # about what they're actually doing.
            #
            # No feature unlocks left: everything is open by now, which
            # frees Chapter 2 to be about people rather than menus. That
            # is a feature of the pacing, not a gap in it.
            # ==========================================================
            {
                "id": "c2m1_the_freight_line",
                "name": "The Freight Line",
                "summary": "Two hundred crates left the site while you were in it.",
                "beats": [
                    {
                        "kind": "dialogue",
                        "speaker": "Virtual",
                        "text": (
                            "The crates are gone. All two hundred, out on the freight line, "
                            "and they moved them while we were four floors down fighting "
                            "their doorman.\n\n"
                            "Which means somebody watched us go in and decided that was the "
                            "window."
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Josh",
                        "text": (
                            "Him not run from us. Him *use* us.\n\n"
                            "Two year Im try get someone to look at Glacier 15. First time "
                            "anyone look — same day the crates move. That not luck."
                        ),
                    },
                    {
                        "kind": "choice",
                        "prompt": "Dolphe has the map out and a decision to make.",
                        "options": [
                            {
                                "id": "chase",
                                "label": "🚂 \"Follow the freight.\"",
                                "text": (
                                    "\"Then we follow it.\" He is already folding the map. "
                                    "\"Every road out of here is a road he chose. That's "
                                    "worth knowing on its own.\""
                                ),
                                "sets": {"c2_chose_chase": True},
                            },
                            {
                                "id": "stay",
                                "label": "🏚️ \"Finish searching the site.\"",
                                "text": (
                                    "\"The site isn't going anywhere and the freight is.\" "
                                    "Sader says it flatly. \"But you're right that we're "
                                    "being walked. Let's at least know where to.\""
                                ),
                                "sets": {"c2_chose_stay": True},
                            },
                        ],
                    },
                    {
                        "kind": "reward",
                        "text": "Virtual strips the site's relay for parts before you leave.",
                        "grant": {"gold": 700, "crystal": 60, "metal": 100, "item": "rare"},
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Nebula",
                        "text": (
                            "Line runs south-west through the Wastelands before it turns "
                            "north. It has to — the Divide is impassable for anything on "
                            "rails.\n\n"
                            "So we can beat it to the bend. It's four days of walking and "
                            "we have two."
                        ),
                    },
                ],
                "rewards": {"gold": 600, "reroll_tokens": 8},
            },

            # ==========================================================
            # C2M2 -- the Wastelands, and the strike.
            #
            # Canon has Cascade protecting strikers and rioters in the
            # Wastelands while Boss John sends mechs at them. That happens
            # HERE, but as something the party walks into rather than an
            # assignment -- Rohan's freight is the reason they're on this
            # road at all.
            # ==========================================================
            {
                "id": "c2m2_the_picket",
                "name": "The Picket",
                "summary": "Four hundred people are sitting on the rails.",
                "beats": [
                    {
                        "kind": "dialogue",
                        "speaker": "Nebula",
                        "text": (
                            "That's not a checkpoint. That's a *picket*.\n\n"
                            "Rail workers, four hundred of them, sitting on the line with "
                            "banners. They've stopped the freight for us and they don't "
                            "know it."
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Josh",
                        "text": (
                            "Four hundred.\n\n"
                            "*He does not say the other four hundred and six. Nobody makes "
                            "him.*"
                        ),
                    },
                    {
                        "kind": "battle",
                        "enemies": ["Xender Tank", "Xender Enforcer", "Xender Enforcer"],
                        "level": 14,
                        "intro": (
                            "Company security comes down the embankment at a walk, which is "
                            "worse than a run. They have done this before."
                        ),
                        "on_win": (
                            "The line holds. Somebody in the crowd starts clapping and then "
                            "stops, embarrassed, and then four hundred people join in."
                        ),
                        "on_lose": "You're driven off the embankment. The picket scatters.",
                    },
                    {
                        "kind": "choice",
                        "prompt": "The organiser wants to know who you are.",
                        "options": [
                            {
                                "id": "cascade",
                                "label": "📰 \"Team Cascade.\"",
                                "text": (
                                    "\"...The newspaper?\" She looks at Dolphe properly for "
                                    "the first time. \"You printed my brother's name. In "
                                    "'07. Nobody else did.\""
                                ),
                                "sets": {"c2_named_cascade": True},
                            },
                            {
                                "id": "nobody",
                                "label": "🤐 \"Nobody. We were passing.\"",
                                "text": (
                                    "\"Right.\" She doesn't believe it and doesn't push. "
                                    "\"Then nobody just kept four hundred people off a "
                                    "casualty list.\""
                                ),
                                "sets": {"c2_stayed_anonymous": True},
                            },
                        ],
                    },
                    {
                        "kind": "reward",
                        "text": "The rail workers empty their strike fund into your hands. You try to refuse.",
                        "grant": {"gold": 900, "metal": 120, "xendium": 30, "item": "rare"},
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Dolphe",
                        "text": (
                            "Ask her about the freight.\n\n"
                            "*The organiser's face changes.* \"The sealed one? It doesn't "
                            "stop. It doesn't crew. It runs at night and the yard bosses "
                            "won't sign for it.\"\n\n"
                            "\"We've been striking about pay. They think we're striking "
                            "about *that*.\""
                        ),
                    },
                ],
                "rewards": {"gold": 800, "reroll_tokens": 10},
            },

            # ==========================================================
            # C2M3 -- Entrospire, and somebody who knew Rohan before.
            #
            # Chary is a card sharp who reads a room the way she reads a
            # table, which makes her the right person to have already
            # worked out what everyone else is still arguing about.
            # ==========================================================
            {
                "id": "c2m3_the_underside",
                "name": "The Underside",
                "summary": "Entrospire City, below the rail deck. Chary has been expecting you.",
                "beats": [
                    {
                        "kind": "dialogue",
                        "speaker": "Chary",
                        "text": (
                            "Sit. You're blocking my light and you're about to ask me "
                            "something you think is subtle.\n\n"
                            "*She deals two cards face down and does not look at them.* "
                            "It's about the night freight, it's about who signs for it, and "
                            "you already know the answer or you wouldn't have walked down "
                            "here to hear it out loud."
                        ),
                    },
                    {
                        "kind": "choice",
                        "prompt": "She turns one card over. It means nothing. She knows it means nothing.",
                        "options": [
                            {
                                "id": "ask_rohan",
                                "label": "🔻 Ask about Mr. R directly",
                                "text": (
                                    "The card stops halfway.\n\n"
                                    "\"Nobody says that down here. Not because they're "
                                    "scared of him. Because the ones who said it aren't "
                                    "down here any more.\""
                                ),
                                "sets": {"c2_asked_chary_direct": True},
                            },
                            {
                                "id": "ask_freight",
                                "label": "🚂 Ask about the freight instead",
                                "text": (
                                    "\"Cleverer. Fine.\" She deals a third card. \"It "
                                    "signs out of a yard that closed in '06. The signature "
                                    "is a letter. You've seen it.\""
                                ),
                                "sets": {"c2_asked_chary_oblique": True},
                            },
                            {
                                "id": "say_nothing",
                                "label": "🐱 Put Josh's badge on the table",
                                "text": (
                                    "She looks at **J. — SITE ENGINEERING — GLACIER 15** "
                                    "for a long moment.\n\n"
                                    "\"...Oh,\" she says quietly, and sweeps the cards "
                                    "away. \"You're not asking. You're telling me. Sit "
                                    "down properly, then.\""
                                ),
                                "sets": {"c2_showed_badge": True},
                            },
                        ],
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Chary",
                        "text": (
                            "I dealt to him. Years ago, before he was anything.\n\n"
                            "Worst player I ever sat across from. Not because he was bad at "
                            "cards — because he genuinely could not accept that the deck "
                            "didn't owe him. Lost, and lost, and kept explaining why it "
                            "shouldn't have happened.\n\n"
                            "Men like that don't stop. They just find a bigger table."
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Josh",
                        "text": (
                            "Him say him got divine power. Everyone laugh at that.\n\n"
                            "Rex laugh at that.\n\n"
                            "*He stops. Nobody fills the gap.*"
                        ),
                    },
                    {
                        "kind": "reward",
                        "text": "Chary slides a yard key across the table and takes nothing for it.",
                        "grant": {"gold": 800, "shards": 120, "item": "epic"},
                    },
                ],
                "rewards": {"gold": 700, "reroll_tokens": 10},
            },

            # ==========================================================
            # C2M4 -- the crates. The chapter's real turn.
            # ==========================================================
            {
                "id": "c2m4_what_is_in_them",
                "name": "What Is In Them",
                "summary": "The yard that closed in '06, and two hundred crates that didn't.",
                "beats": [
                    {
                        "kind": "battle",
                        "enemies": ["Xender Convoy", "Xender Loyalist", "Xender Loyalist"],
                        "level": 16,
                        "intro": (
                            "The yard has a night crew after all. They are not railway "
                            "people and they do not ask who you are."
                        ),
                        "on_win": "The yard goes quiet. Two hundred crates sit under the lamps.",
                        "on_lose": "You're pushed back through the gate. The lamps go out behind you.",
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Virtual",
                        "text": (
                            "Manifest says weight only. Every crate within four kilos.\n\n"
                            "*She gets the first one open.*\n\n"
                            "...It's rock. It's *rock*. Two hundred crates of ballast."
                        ),
                    },
                    {
                        "kind": "choice",
                        "prompt": "Nobody in the yard says anything for several seconds.",
                        "options": [
                            {
                                "id": "decoy",
                                "label": "🎭 \"It's a decoy. Always was.\"",
                                "text": (
                                    "\"For two years?\" Nebula says. \"Who runs a decoy "
                                    "for two years?\"\n\n"
                                    "\"Somebody who knew somebody would eventually come "
                                    "and look,\" says Dolphe."
                                ),
                                "sets": {"c2_read_decoy": True},
                            },
                            {
                                "id": "moved",
                                "label": "📦 \"Then where did the real ones go?\"",
                                "text": (
                                    "Virtual is already on the yard ledger. \"Same weight, "
                                    "same route, twice a month, north.\"\n\n"
                                    "\"North of the map,\" she says. \"There is no north "
                                    "of the map.\""
                                ),
                                "sets": {"c2_asked_where": True},
                            },
                        ],
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Dolphe",
                        "text": (
                            "It was never about hiding the cargo.\n\n"
                            "Two hundred crates leaving Glacier 15 in daylight is a *story*. "
                            "It's the story I'd have printed. It's the story anyone would "
                            "chase.\n\n"
                            "He built us a headline and pointed it away from wherever the "
                            "people went."
                        ),
                    },
                    {
                        "kind": "reward",
                        "text": "The yard ledger comes off the wall with the bolts still in it.",
                        "grant": {"gold": 1_100, "crystal": 90, "xendium": 45, "item": "rare"},
                    },
                ],
                "rewards": {"gold": 900, "reroll_tokens": 12},
            },

            # ==========================================================
            # C2M5 -- Rohan, in person, for ninety seconds.
            #
            # He does NOT fight you. He is not withheld out of coyness --
            # the point of the scene is that he does not consider this an
            # engagement. You fight what he leaves running, again, and
            # this time he stays to watch you do it.
            # ==========================================================
            {
                "id": "c2m5_the_man_himself",
                "name": "Mr. R",
                "summary": "He was always going to be standing at the end of it.",
                "beats": [
                    {
                        "kind": "dialogue",
                        "speaker": "Rohan",
                        "text": (
                            "*There is a man sitting on a crate at the end of the yard, and "
                            "he has been there the whole time.*\n\n"
                            "Two years. Two years of that fence, that gate, that inspection "
                            "slip signed every ninety days in my own handwriting, and not "
                            "one person came.\n\n"
                            "Then *you* lit a beacon."
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Rohan",
                        "text": (
                            "You have no idea what you are. That's the part I enjoy.\n\n"
                            "*He looks at Josh without hurrying.* Hello, Josh. You've told "
                            "them about me. I can tell, because they're standing like people "
                            "who've been told."
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Josh",
                        "text": (
                            "You were there.\n\n"
                            "*It is not a question and his voice does not shake.*\n\n"
                            "Rex. You were *there*."
                        ),
                    },
                    {
                        "kind": "choice",
                        "prompt": "Rohan does not stand up.",
                        "options": [
                            {
                                "id": "swing",
                                "label": "⚡ Go for him",
                                "text": (
                                    "You cross half the yard before the floor opens.\n\n"
                                    "\"No,\" he says, mildly, the way you'd correct a "
                                    "child's grammar. \"Not yet. You're not finished being "
                                    "useful.\""
                                ),
                                "sets": {"c2_went_for_him": True},
                            },
                            {
                                "id": "listen",
                                "label": "🐱 Let him talk",
                                "text": (
                                    "\"...Huh.\" For the first time something in his face "
                                    "moves. \"You're patient. That's not what the file "
                                    "said.\"\n\n"
                                    "*He notices he has said 'the file' out loud, and is "
                                    "briefly, visibly annoyed with himself.*"
                                ),
                                "sets": {"c2_let_him_talk": True},
                            },
                            {
                                "id": "protect",
                                "label": "🛡️ Put yourself between him and Josh",
                                "text": (
                                    "Rohan's eyebrows go up.\n\n"
                                    "\"That's new. Nobody's ever done that for him.\" A "
                                    "pause. \"Rex did, once. Look how that went.\""
                                ),
                                "sets": {"c2_shielded_josh": True},
                            },
                        ],
                    },
                    {
                        # THE LECTOR FIGHTS ALONE, at level 12.
                        #
                        # It shipped with a Xender Convoy escort at level
                        # 18 and measured 0% at every squad level tested.
                        # Exactly the lesson the Permafrost Guardian
                        # taught in Chapter 1: an elite or boss template
                        # is already a harder fight than most three-enemy
                        # groups, so an escort on top is not difficulty,
                        # it's unwinnability.
                        #
                        # It reads better alone too. Rohan gestures at ONE
                        # thing and sits back down.
                        "kind": "battle",
                        "enemies": ["The Lector of Ledgers"],
                        "level": 12,
                        "intro": (
                            "He doesn't get up. He gestures, and the thing that has been "
                            "standing in the dark behind him stops being scenery.\n\n"
                            "*He watches. He does not draw a weapon at any point.*"
                        ),
                        "on_win": (
                            "It comes apart. Rohan applauds — three slow claps, entirely "
                            "sincere, which is somehow the worst part."
                        ),
                        "on_lose": (
                            "You go down in the lamplight. When you come round the yard is "
                            "empty and nobody has taken anything from you."
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Rohan",
                        "text": (
                            "*He is already walking, unhurried, towards the north gate.*\n\n"
                            "That was worth the trip. Genuinely — I've been curious since "
                            "Ocellios put you in the frame, and now I've seen it.\n\n"
                            "Keep going north, by all means. I'd like the company."
                        ),
                    },
                    {
                        "kind": "unlock",
                        "feature": "abyss",
                        "text": (
                            "**`/abyss` is open.**\n\n"
                            "Past the north gate the ground stops being ground. Twelve "
                            "floors down, and every floor is several chambers that must be "
                            "cleared by **different teams** — nobody fights twice.\n\n"
                            "The early floors are doable now. The bottom four rotate every "
                            "two weeks and are the hardest content in the game. It is not "
                            "your gear that decides how far you get; it is how many "
                            "characters you actually built."
                        ),
                    },
                    {
                        "kind": "reward",
                        "text": "He leaves the yard key on the crate. It fits the north gate.",
                        "grant": {"gold": 1_600, "shards": 300, "crystal": 120, "item": "epic"},
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Dolphe",
                        "text": (
                            "He said *Ocellios put you in the frame*.\n\n"
                            "*He is looking at you, and for once he is not being generous "
                            "about it.*\n\n"
                            "He knows what you are and we don't. That is now the second "
                            "most dangerous thing about him.\n\n"
                            "*Chapter 3 isn't written yet. Go north when it is.*"
                        ),
                    },
                ],
                "rewards": {"gold": 1_400, "reroll_tokens": 15},
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
