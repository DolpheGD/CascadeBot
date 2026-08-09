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
THE PLAYER SPEAKS -- IN THEIR OPTIONS, AND ONLY THERE
----------------------------------------------------------------------
This reversed a previous rule. The old constraint was that the avatar
never talks, on the grounds that any line written for a renameable,
class-switchable character is a line put in someone else's mouth.

The cost of that was a protagonist who was furniture: every scene was
other people talking AT a silent figure, which is fine for a corridor
and hopeless for an RPG where the point is that you're a person in a
room with other people.

So the player talks -- but only through `choice` options, never in
`dialogue` beats. An option's `label` IS the line they say, written in
quotes:

    {"id": "blunt", "label": "\\"So you were watching me.\\"", ...}

That keeps the character yours: the game never puts words in your mouth
unprompted, it offers you words and you pick. The `text` under each
option is the narration of what happens next, not more of your dialogue.

----------------------------------------------------------------------
TONE
----------------------------------------------------------------------
Mixed, deliberately, and the mix is the point. This is a game about
people doing a dangerous job badly-funded, so it should be funny far
more often than it is grim -- and the grim parts land because of the
contrast, not in spite of it.

  * FUNNY is the default register. Jofrog taking idioms literally,
    Blueflame saying something bleak far too cheerfully, Refender being
    insufferably correct.
  * SERIOUS is earned, not constant. Rex, the convoy, what Josh is
    actually doing. When it turns, it turns without a joke to cushion it.
  * EXCITING is structural: every mission should have a thing that
    happens, not just a conversation about a thing that happened.
  * SAD is rationed. Used well, once a chapter, it does more than five
    attempts at it.

The failure mode to avoid is uniform dryness -- everyone deadpan, every
scene the same temperature. Characters should disagree in register as
well as in opinion.
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
    "cards": "Character Cards",
    "abyss": "The Void Abyss",
}

# Features every player has from the moment they exist. Deliberately
# tiny: profile and help are how you find out what's going on, and story
# is the thing that unlocks everything else.
ALWAYS_AVAILABLE = frozenset({"profile", "help", "story", "characters"})


CHAPTERS: list[dict] = [
    {
        "id": "prologue",
        "name": "Prologue: Somebody Has To",
        "blurb": (
            "You wake up somewhere you don't remember agreeing to, and by the end of "
            "the week you have a job, a squad, and a locker with nothing in it."
        ),
        "unlocks_region": None,
        "missions": [
            # ==========================================================
            # ACT ONE -- before the hub. Three missions, linear, and the
            # only part of the prologue that is a corridor. It teaches
            # combat and gets you recruited; everything after it happens
            # at Cascade Central and can be done in any order.
            # ==========================================================
            {
                "id": "pr1_wake_up",
                "name": "Wake Up",
                "summary": "Ocellios Lab is coming down. You are inside it.",
                "beats": [
                    {
                        "kind": "dialogue",
                        "speaker": "Ocellios Lab",
                        "text": (
                            "**CONTAINMENT FAULT — SECTOR 9 — EVACUATE**\n\n"
                            "You come to on a floor that is at eleven degrees and getting "
                            "worse. There's a restraint frame beside you with the cuffs "
                            "already open.\n\n"
                            "You don't remember lying down in it. You don't remember "
                            "much, which is a problem for later, because the ceiling is "
                            "a problem for now."
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Ocellios Lab",
                        "text": (
                            "Something's gone through the lab's mech control and left it "
                            "wrong. A D-class unit turns towards you and doesn't run its "
                            "greeting routine.\n\n"
                            "Your hands are producing light.\n\n"
                            "That's new information. There is no time to have feelings "
                            "about it."
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
                        "prompt": (
                            "There's a door east and the ceiling isn't going to hold. The "
                            "restraint frame is right there."
                        ),
                        "options": [
                            {
                                "id": "run",
                                "label": "\"Not my problem. Moving.\"",
                                "text": (
                                    "You don't look back at the frame.\n\n"
                                    "Later you'll wonder whether that was instinct or "
                                    "training, and which would be worse."
                                ),
                                "sets": {"pro_ran": True},
                            },
                            {
                                "id": "look",
                                "label": "\"Ten seconds. I want to know whose this was.\"",
                                "text": (
                                    "Your own weight is logged on the chart. Eleven months "
                                    "of readings, in three different hands, and the "
                                    "earliest entry is older than anything you can "
                                    "remember.\n\n"
                                    "Then the ceiling comes down and takes the question "
                                    "with it."
                                ),
                                "sets": {"pro_looked": True},
                            },
                        ],
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Sector 9",
                        "text": (
                            "The east door is buckled in its frame. It opens anyway, "
                            "because you are still producing light and the light turns "
                            "out to have opinions about doors.\n\n"
                            "Behind you, the room you woke up in stops existing."
                        ),
                    },
                ],
            },
            {
                "id": "pr2_long_way_out",
                "name": "The Long Way Out",
                "summary": "Both ends of the corridor are on fire. One of them less so.",
                "beats": [
                    {
                        "kind": "dialogue",
                        "speaker": "Sector 9 — East Corridor",
                        "text": (
                            "Both ends are burning. The east end is burning less, which "
                            "is the closest thing to good news available.\n\n"
                            "Something else is moving out there, and it isn't running "
                            "its greeting routine either."
                        ),
                    },
                    {
                        # ONE enemy, not two. You are alone and level 2 here:
                        # two bodies act twice a cycle against your one and
                        # the fight is lost to arithmetic before skill gets
                        # a say. Measured at a 0% win rate over 60 runs --
                        # see tools/check_story.py's solo-prologue check,
                        # which now models the roster you ACTUALLY have
                        # rather than a fabricated party of four.
                        "kind": "battle",
                        "enemies": ["Concussion Drone"],
                        "level": 2,
                        "intro": "It comes down the corridor at a walk, which is somehow worse.",
                        "on_win": (
                            "It goes down hard and takes a long moment about it.\n\n"
                            "In the quiet afterwards you can hear the building settling — "
                            "a sound like a very large animal getting comfortable."
                        ),
                        "on_lose": "You come to further down the corridor. Something dragged you.",
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "???",
                        "text": (
                            "A voice, close, and far too calm for the circumstances:\n\n"
                            "\"Left. **Left.** Other left — there we go.\"\n\n"
                            "A hand takes your elbow and steers you through a gap that "
                            "wasn't there a second ago."
                        ),
                    },
                ],
            },
            {
                "id": "pr3_pickup",
                "name": "Pickup",
                "summary": "Someone was already outside, waiting, with a spare seat.",
                "beats": [
                    {
                        "kind": "dialogue",
                        "speaker": "Dolphe",
                        "text": (
                            "Outside, the cold is a physical event. There's a transport "
                            "idling with its door open and a man in the doorway who does "
                            "not look surprised to see you.\n\n"
                            "\"You're the one from Sector Nine.\" He steps back to make "
                            "room. \"Get in, don't get in — the offer's the same either "
                            "way and the building isn't.\""
                        ),
                    },
                    {
                        "kind": "choice",
                        "prompt": "He waits. He seems prepared to wait a while.",
                        "options": [
                            {
                                "id": "who",
                                "label": "\"Who are you, and how did you know I was in there?\"",
                                "text": (
                                    "\"Dolphe. Team Cascade.\" He says it like both facts "
                                    "are mildly embarrassing.\n\n"
                                    "\"And I didn't. We came for the building. You were an "
                                    "extra.\"\n\n"
                                    "A beat.\n\n"
                                    "\"That's not an insult. Most good things are extras.\""
                                ),
                                "sets": {"pro_asked_who": True},
                            },
                            {
                                "id": "hands",
                                "label": "\"My hands were doing something. Do you know what?\"",
                                "text": (
                                    "He looks at them. Properly, for two full seconds.\n\n"
                                    "\"No,\" he says. \"And I'd rather find out with you "
                                    "than about you. There's a difference and it matters.\""
                                ),
                                "sets": {"pro_asked_hands": True},
                            },
                            {
                                "id": "silent",
                                "label": "*Get in without saying anything.*",
                                "text": (
                                    "You get in.\n\n"
                                    "He doesn't push it. He does, at some point in the "
                                    "next hour, put a blanket over you without making it "
                                    "a thing."
                                ),
                                "sets": {"pro_silent": True},
                            },
                        ],
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Dolphe",
                        "text": (
                            "The transport turns south and the lab goes out of the window "
                            "behind you, one storey at a time.\n\n"
                            "\"We clean up what the Cascade left behind,\" he says, to the "
                            "windscreen. \"It's dangerous, it doesn't pay, and about a "
                            "third of what we do is paperwork.\"\n\n"
                            "\"I'm telling you the boring part first. Everyone else leads "
                            "with the heroics and then people are annoyed later.\""
                        ),
                    },
                    {
                        "kind": "reward",
                        "text": (
                            "Somebody has left a kit bag on the seat beside you with a "
                            "sticky note on it reading FOR THE NEW ONE."
                        ),
                        "grant": {"item": "uncommon", "gold": 200, "lootbox": "common"},
                    },
                    {
                        "kind": "unlock",
                        "feature": "inventory",
                        "text": (
                            "**`/inventory` is open.**\n\n"
                            "Equip what's in the bag — unequipped gear does nothing at "
                            "all, which is the single most common way to be needlessly "
                            "bad at this."
                        ),
                    },
                ],
            },

            # ==========================================================
            # ACT TWO -- the hub. Five missions, one per room, and they
            # can be done in any order because the hub is a place rather
            # than a queue. Each one hands over the system that room owns
            # and the person who explains it.
            # ==========================================================
            {
                "id": "pr4_the_atrium",
                "name": "The Atrium",
                "summary": "Dolphe explains the job. Most of it is true.",
                "beats": [
                    {
                        "kind": "dialogue",
                        "speaker": "Dolphe",
                        "text": (
                            "Cascade Central is a converted freight depot with a crooked "
                            "banner in it. Dolphe is under the banner, reading something, "
                            "and doesn't look up.\n\n"
                            "\"Right. The board.\" He taps it without turning round. "
                            "\"Things that need doing, in the order somebody decided they "
                            "needed doing. That somebody is usually me and I'm usually "
                            "about seventy percent right.\""
                        ),
                    },
                    {
                        "kind": "choice",
                        "prompt": "\"Questions. Go on, everyone has one.\"",
                        "options": [
                            {
                                "id": "pay",
                                "label": "\"You said it doesn't pay. Was that a joke?\"",
                                "text": (
                                    "\"Half of one.\" He finally looks up. \"It pays. It "
                                    "pays badly, late, and in materials more often than "
                                    "money.\"\n\n"
                                    "\"Nobody here is doing it for that, which is either "
                                    "very reassuring or the single biggest red flag in "
                                    "the building. I've never decided.\""
                                ),
                                "sets": {"pro_asked_pay": True},
                            },
                            {
                                "id": "why_me",
                                "label": "\"Why me? You said I was an extra.\"",
                                "text": (
                                    "\"You were.\" He puts the paper down.\n\n"
                                    "\"Then you walked out of a Sector Nine collapse under "
                                    "your own power, which nobody has done, and you did it "
                                    "without asking anyone for permission.\"\n\n"
                                    "\"I've got four people who'd have waited for orders. "
                                    "I've got nobody who'd have walked.\""
                                ),
                                "sets": {"pro_asked_why": True},
                            },
                        ],
                    },
                    {
                        "kind": "unlock",
                        "feature": "quests",
                        "text": (
                            "**`/quests` is open.**\n\n"
                            "Standing objectives that pay out as you go. You don't stop "
                            "and *do* quests — you play, and they notice.\n\n"
                            "The starter set is the one to actually finish. Clearing "
                            "all of it pays a lump of Shards big enough to matter, and "
                            "the last few ask for real work — a base upgrade, a deep "
                            "run — so it doubles as a list of what you should be "
                            "learning to do next."
                        ),
                    },
                    {
                        # /rename, introduced. It has always existed and
                        # the story has never mentioned it, so the one
                        # thing every player wants in the first five
                        # minutes -- to not be called "You" -- was
                        # undiscoverable. Put on the ID badge because
                        # that is the object it is about.
                        "kind": "dialogue",
                        "speaker": "Refender",
                        "text": (
                            "She hands you a laminated badge. The name field reads "
                            "**YOU** in the flat grey of a default nobody chose.\n\n"
                            "\"Printer does that. It'll keep doing that until you tell "
                            "it otherwise — `/rename`, whatever you want on it.\"\n\n"
                            "She's already walking. \"Mine said BEE for a year. I let "
                            "it. Different situation.\""
                        ),
                    },
                ],
            },
            {
                "id": "pr5_ops_deck",
                "name": "The Ops Deck",
                "summary": "Jofrog teaches you squads by losing on purpose.",
                "beats": [
                    {
                        "kind": "dialogue",
                        "speaker": "Jofrog",
                        "text": (
                            "The Ops Deck has six screens. Four show the same thing, one "
                            "shows a card game, and one is off.\n\n"
                            "A large robot is standing at parade rest facing a wall.\n\n"
                            "\"You are the new one. I have been looking forward to this "
                            "for eleven hours.\" He turns round. \"I have prepared a "
                            "demonstration.\""
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Jofrog",
                        "text": (
                            "\"Four of you go out. That is the rule. Not three.\"\n\n"
                            "He produces a chart. It is hand-drawn and meticulous.\n\n"
                            "\"I have run the numbers on three. The numbers are rude. I "
                            "will not read them aloud because there is a policy about "
                            "morale, and I am the policy.\""
                        ),
                    },
                    {
                        # A WEAPON, BEFORE THE DUMMY. Guaranteed slot, not
                        # a random roll -- see story_service's "item"
                        # grant and item_template_service.pick_random_template.
                        #
                        # Reported: the dummy fight could stall out. A
                        # level-1 avatar with no weapon does chip damage
                        # into a sack designed to absorb it, and the
                        # lesson the player takes from a fight that goes
                        # nowhere is that combat is slow, not that gear
                        # matters. Handing over a weapon immediately
                        # before the first real swing teaches the
                        # opposite, and teaches it in the one place the
                        # difference is impossible to miss.
                        "kind": "reward",
                        "text": (
                            "Jofrog opens a locker with the air of a man performing a "
                            "ceremony he invented himself this morning.\n\n"
                            "\"Standard issue. It is not good. It is yours, which the "
                            "policy says makes it good.\""
                        ),
                        "grant": {"item": ("uncommon", "weapon")},
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Jofrog",
                        "text": (
                            "\"Equip it. `/inventory`.\"\n\nHe waits. He is very good at "
                            "waiting.\n\n"
                            "\"I will know if you have not. The dummy will also know, "
                            "and the dummy gossips.\""
                        ),
                    },
                    {
                        "kind": "battle",
                        "enemies": ["Training Dummy"],
                        "level": 3,
                        "intro": (
                            "\"Hit it. I will tell you what you did wrong afterwards, and "
                            "then I will tell you what you did right, because that order "
                            "is better for you.\""
                        ),
                        "on_win": (
                            "\"Good.\" He sounds delighted, and slightly surprised at "
                            "being delighted.\n\n"
                            "\"You did nothing wrong. This is inconvenient — I had "
                            "prepared notes.\""
                        ),
                        "on_lose": (
                            "\"That is fine. That is what it is for.\" He rights the dummy "
                            "with one hand. \"Again, when you would like.\""
                        ),
                    },
                    {
                        "kind": "unlock",
                        "feature": "squad",
                        "text": (
                            "**`/squad` is open.**\n\n"
                            "Four slots, any character in any slot. Bring one of each "
                            "role if you can — DPS, Support DPS, Amplifier, Sustain. "
                            "Jofrog has a chart about this and would love to be asked."
                        ),
                    },
                    {
                        # CLASS CHANGE, introduced where it means
                        # something. /class has existed the whole time
                        # and the story never mentioned it, so the one
                        # character a player keeps forever -- their own --
                        # was the one they never learned they could
                        # rebuild. Taught here, immediately after the
                        # four roles are named, because that is the only
                        # moment the words "Amplifier" and "Sustain"
                        # mean anything to them yet.
                        "kind": "choice",
                        "speaker": "Jofrog",
                        "prompt": (
                            "\"One more thing, and it is the important one.\"\n\n"
                            "He points at you with the chart.\n\n"
                            "\"You are not fixed. Everyone else out there is what they "
                            "are. You can be any of the four, whenever you like, with "
                            "`/class`. Between runs. As often as you want.\"\n\n"
                            "\"It costs nothing. People do not believe me about this "
                            "part.\""
                        ),
                        "options": [
                            {
                                "id": "class_hit",
                                "label": "\"What should I be right now?\"",
                                "text": (
                                    "\"Right now? Whatever is missing.\" He shrugs, which "
                                    "on him is a structural event.\n\n"
                                    "\"You are one person and there are four jobs. Look "
                                    "at who you have got, find the hole, be the hole. "
                                    "That is the entire strategy. I have a longer version "
                                    "with diagrams.\""
                                ),
                                "flag": "asked_about_class",
                            },
                            {
                                "id": "class_free",
                                "label": "\"Nothing is free here.\"",
                                "text": (
                                    "\"This is.\" A pause. \"Almost nothing else is. You "
                                    "are correct to be suspicious and wrong about this "
                                    "specific case, which is the best kind of wrong.\"\n\n"
                                    "He makes a note. You suspect it is about you."
                                ),
                                "flag": "suspicious_of_jofrog",
                            },
                        ],
                    },
                    {
                        "kind": "unlock",
                        "feature": "pull",
                        "text": (
                            "**`/pull` is open.**\n\n"
                            "Shards bring people in. You'll need more than one body "
                            "before Dolphe sends you anywhere real — see the previous "
                            "paragraph about the numbers being rude."
                        ),
                    },
                    {
                        # EXACTLY ONE PULL. The prologue is balanced around
                        # the roster it has actually handed over, and at
                        # this point that is the avatar plus whoever this
                        # buys -- see tools/check_story.py, which measures
                        # every prologue fight against that party rather
                        # than a hypothetical four.
                        "kind": "reward",
                        "text": (
                            "Jofrog produces a shard case with the air of a man who has "
                            "been holding it for eleven hours.\n\n"
                            "\"This is one pull. I have checked. I checked twice, and "
                            "then I checked that I had checked.\""
                        ),
                        "grant": {"shards": 120},
                    },
                ],
            },
            {
                "id": "pr6_armory",
                "name": "The Armory",
                "summary": "Refender has opinions about balance. All of them.",
                "beats": [
                    {
                        "kind": "dialogue",
                        "speaker": "Refender",
                        "text": (
                            "Everything in the Armory is labelled, in handwriting that "
                            "takes itself extremely seriously.\n\n"
                            "\"Offense and defense are the same decision made twice,\" "
                            "says the man doing the labelling, by way of hello.\n\n"
                            "\"Most people gear for damage and then die. Most people are "
                            "also very fast about it, so at least it's efficient.\""
                        ),
                    },
                    {
                        "kind": "choice",
                        "prompt": "He hands you a whetstone you did not ask for.",
                        "options": [
                            {
                                "id": "agree",
                                "label": "\"So — never gear for damage. Got it.\"",
                                "text": (
                                    "\"No.\" He takes the whetstone back. \"That is the "
                                    "same mistake facing the other way.\"\n\n"
                                    "\"Balance is not the middle. Balance is knowing which "
                                    "way you are about to fall.\"\n\n"
                                    "He gives you the whetstone again."
                                ),
                                "sets": {"pro_refense_wrong": True},
                            },
                            {
                                "id": "push",
                                "label": "\"That sounds like something you'd put on a poster.\"",
                                "text": (
                                    "There is a silence of exactly the wrong length.\n\n"
                                    "\"There is a poster,\" he admits. \"Blueflame made "
                                    "it. It is in the Mess and I have asked him to take "
                                    "it down four times.\"\n\n"
                                    "\"He has laminated it.\""
                                ),
                                "sets": {"pro_refense_poster": True},
                            },
                        ],
                    },
                    {
                        "kind": "reward",
                        "text": (
                            "He fills a crate without appearing to choose anything, which "
                            "is somehow more impressive than if he had."
                        ),
                        "grant": {"item": "rare", "gold": 400, "wood": 40, "stone": 40,
                                  "lootbox": ("uncommon", 2)},
                    },
                    {
                        "kind": "unlock",
                        "feature": "forge",
                        "text": (
                            "**`/forge` is open.**\n\n"
                            "Move an ability off a piece you've outgrown and onto one you "
                            "haven't. Refender considers throwing away a good ability a "
                            "minor moral failing."
                        ),
                    },
                    {
                        # CHARACTER CARDS, taught in the Armory, because
                        # the whole lesson is a comparison against the
                        # gear the player was handed four beats ago. A
                        # Card explained anywhere else is just a second
                        # inventory; explained here it is "this is the
                        # one that isn't like the others".
                        "kind": "dialogue",
                        "speaker": "Refender",
                        "text": (
                            "She pulls a flat case out from under the bench and does not "
                            "open it straight away.\n\n"
                            "\"Everything in that crate, you'll replace. Month, maybe "
                            "two. That's fine — that's what it's for.\"\n\n"
                            "\"This isn't that.\""
                        ),
                    },
                    {
                        "kind": "choice",
                        "prompt": (
                            "Inside is a card. Not a component, not a chip — a card, "
                            "printed and worn at the corners, with something written on "
                            "it in a hand that isn't hers."
                        ),
                        "options": [
                            {
                                "id": "card_what",
                                "label": "\"What is it?\"",
                                "text": (
                                    "\"Nobody's sure. They come out of the Cascade like "
                                    "this — already old, already about something.\"\n\n"
                                    "She turns it over. \"One per person. Big numbers, and "
                                    "one thing it does that nothing else does. You don't "
                                    "find them. They find their way to you.\""
                                ),
                                "flag": "pro_asked_card",
                            },
                            {
                                "id": "card_whose",
                                "label": "\"Whose handwriting is that?\"",
                                "text": (
                                    "She looks at it for a second longer than the question "
                                    "needs.\n\n"
                                    "\"Somebody who isn't using it any more.\" The case "
                                    "shuts. \"Go and get your own.\""
                                ),
                                "flag": "pro_card_handwriting",
                            },
                        ],
                    },
                    {
                        "kind": "unlock",
                        "feature": "cards",
                        "text": (
                            "**`/cards` and `/cardpull` are open.**\n\n"
                            "Cards run on **Cores**, not Shards — a separate pull, a "
                            "separate count. One card per character, three big stats, and "
                            "an ability strong enough that gear no longer rolls anything "
                            "like it.\n\n"
                            "You do not need one. You will want one."
                        ),
                    },
                    {
                        "kind": "reward",
                        "text": (
                            "\"Starter allocation,\" she says, in the voice of someone "
                            "reading a policy she wrote herself. \"Spend it badly if you "
                            "like. Everyone does the first time.\""
                        ),
                        # Exactly one 10-pull (CARD_PULL_COST 10 x 10), so
                        # the tutorial ends on the multi rather than on a
                        # single roll -- same reasoning as the beginner
                        # quests' 1,200 shards.
                        "grant": {"cores": 100},
                    },
                ],
            },
            {
                "id": "pr7_the_mess",
                "name": "The Mess",
                "summary": "The only room anyone decorated on purpose.",
                "beats": [
                    {
                        "kind": "dialogue",
                        "speaker": "Blueflame",
                        "text": (
                            "The Mess is warm and loud and smells like something that has "
                            "been going since morning.\n\n"
                            "A man is eating alone at a table built for eight and looks "
                            "completely content about it.\n\n"
                            "\"You're the lab one.\" He gestures at the bench opposite "
                            "with a fork. \"Everything burns eventually. I just prefer to "
                            "be early.\"\n\nHe goes back to eating. \"That's a joke. "
                            "Mostly.\""
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Blueflame",
                        "text": (
                            "\"I'm not Cascade, before somebody tells you badly. World "
                            "Aligners. Different outfit, same problems, worse funding.\"\n\n"
                            "\"I'm here because the food's better and Dolphe doesn't ask "
                            "me things.\"\n\nA beat.\n\n"
                            "\"He asks me things constantly. Politely, though, so it "
                            "doesn't count.\""
                        ),
                    },
                    {
                        "kind": "choice",
                        "prompt": "\"Go on. You've got the face of someone with a question.\"",
                        "options": [
                            {
                                "id": "aligners",
                                "label": "\"What do the World Aligners actually do?\"",
                                "text": (
                                    "\"Same as you lot. We just do it angrier.\"\n\n"
                                    "He thinks about it while chewing.\n\n"
                                    "\"Cascade puts things back. We go and find out who "
                                    "knocked them over. It's the same job with a worse "
                                    "temper and no paperwork.\""
                                ),
                                "sets": {"pro_asked_aligners": True},
                            },
                            {
                                "id": "josh",
                                "label": "\"Who's Josh? Your lot keep saying the name.\"",
                                "text": (
                                    "The cheerfulness doesn't move. Something underneath "
                                    "it does.\n\n"
                                    "\"He runs us. He's better at this than anyone I've "
                                    "met and he's currently doing something extremely "
                                    "stupid about it.\"\n\n"
                                    "\"You'll meet him. Don't take it personally when he "
                                    "doesn't like you — it isn't about you.\""
                                ),
                                "sets": {"pro_asked_josh": True},
                            },
                        ],
                    },
                    {
                        "kind": "unlock",
                        "feature": "exchange",
                        "text": (
                            "**`/exchange` is open.**\n\n"
                            "You've pulled by now, which means you've had the other "
                            "thing happen: the same face twice.\n\n"
                            "A duplicate isn't a wasted pull. It pays **Echoes**, and "
                            "Echoes buy a specific character outright — no rolling, no "
                            "luck. It's slow on purpose. It is also the only way in "
                            "this building to get exactly what you wanted."
                        ),
                    },
                    {
                        "kind": "unlock",
                        "feature": "daily",
                        "text": (
                            "**`/daily` is open.**\n\n"
                            "\"Come and eat,\" Blueflame says, not looking up. \"Every "
                            "day. That's the whole system. I've explained it worse than "
                            "the manual and I stand by it.\""
                        ),
                    },
                ],
            },
            {
                "id": "pr8_the_base",
                "name": "Somebody Has To Run It",
                "summary": "The depot is falling apart. Apparently that's your problem now.",
                "beats": [
                    {
                        "kind": "dialogue",
                        "speaker": "Dolphe",
                        "text": (
                            "\"Right — you're settled, so you get the other half.\"\n\n"
                            "He hands you a clipboard with a genuine expression of "
                            "apology.\n\n"
                            "\"Half of this outfit is going out and hitting things. The "
                            "other half is the roof, the harvesters, the shrines, and the "
                            "fact that our Research Lab is a shed with ambitions.\"\n\n"
                            "\"Nobody sings songs about the second half. The second half "
                            "is why the first half comes home.\""
                        ),
                    },
                    {
                        "kind": "unlock",
                        "feature": "base",
                        "text": (
                            "**`/base`, `/harvesters` and `/shrines` are open.**\n\n"
                            "Harvesters produce while you're away. Shrines make the whole "
                            "party better at everything, permanently, and they grow with "
                            "your squad."
                        ),
                    },
                    {
                        "kind": "unlock",
                        "feature": "lab",
                        "text": (
                            "**`/lab` is open.**\n\n"
                            "\"It's a shed,\" Dolphe says. \"It's a shed that has doubled "
                            "our loot rates twice. I've stopped calling it a shed to its "
                            "face.\""
                        ),
                    },
                    {
                        "kind": "reward",
                        "text": "The clipboard comes with a starting float. It is not generous.",
                        "grant": {"gold": 900, "metal": 30, "lootbox": "uncommon", "shards": 120},
                    },
                ],
            },

            # ==========================================================
            # ACT THREE -- out the gate. The first real work, the first
            # thing that isn't funny, and the door to everything else.
            # ==========================================================
            {
                "id": "pr9_first_contract",
                "name": "First Contract",
                "summary": "Small, clean, and successful. Enjoy it.",
                "beats": [
                    {
                        "kind": "dialogue",
                        "speaker": "Dolphe",
                        "text": (
                            "\"Northern relay. It's been fine for six years, which means "
                            "nobody's looked at it for six years.\"\n\n"
                            "\"Go and look at it. Take whoever you like. Be back for "
                            "dinner or Blueflame eats yours and makes a speech about "
                            "waste.\""
                        ),
                    },
                    {
                        "kind": "battle",
                        "enemies": ["Xender Henchmen", "Xender Recon Scout"],
                        "level": 5,
                        "intro": (
                            "The relay is fine. The two people stripping it for parts are "
                            "the problem, and they see you at the same moment you see them."
                        ),
                        "on_win": (
                            "They run. You let them — Dolphe was specific about that, and "
                            "annoyingly right about why.\n\n"
                            "The relay comes back up while you're still standing there. "
                            "Six more years, probably."
                        ),
                        "on_lose": (
                            "You come off worse and the relay stays down. It'll keep. "
                            "Most things do."
                        ),
                    },
                    {
                        "kind": "reward",
                        "text": "The relay's service cache pops open at your feet, unprompted, like a tip.",
                        "grant": {"item": "rare", "gold": 700, "crystal": 20, "lootbox": ("rare", 2),
                                  "shards": 120},
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Jofrog",
                        "text": (
                            "Jofrog is waiting at the gate when you get back. He has been "
                            "waiting some time.\n\n"
                            "\"You are within the expected window,\" he says, with enormous "
                            "satisfaction. \"I did not tell anyone I was worried. I am "
                            "telling you now, because it is over.\""
                        ),
                    },
                ],
            },
            {
                "id": "pr10_the_convoy",
                "name": "What's Left By The Road",
                "summary": "You pass something on the way back that nobody wants to discuss.",
                "beats": [
                    {
                        "kind": "dialogue",
                        "speaker": "The road south",
                        "text": (
                            "Four hours out, there's a burned-out convoy pulled onto the "
                            "verge. Three vehicles, Cascade markings, arranged in the shape "
                            "of people who tried to make a wall out of them.\n\n"
                            "The transport doesn't slow down. Nobody in it says anything "
                            "for a while."
                        ),
                    },
                    {
                        "kind": "choice",
                        "prompt": "Dolphe is looking out of the other window.",
                        "options": [
                            {
                                "id": "ask",
                                "label": "\"Was that ours?\"",
                                "text": (
                                    "\"Yes.\"\n\n"
                                    "He doesn't turn round.\n\n"
                                    "\"Eight months ago. Two of them are on the board by "
                                    "the door and I haven't taken them off, and I've "
                                    "stopped pretending that's an administrative "
                                    "oversight.\"\n\n"
                                    "That's all he says about it. It's more than anyone "
                                    "else has got."
                                ),
                                "sets": {"pro_asked_convoy": True},
                            },
                            {
                                "id": "quiet",
                                "label": "*Say nothing. Watch it go past.*",
                                "text": (
                                    "You watch it until the road bends.\n\n"
                                    "Dolphe doesn't turn round, but at some point his "
                                    "reflection is looking at yours, and neither of you "
                                    "makes anything of it."
                                ),
                                "sets": {"pro_quiet_convoy": True},
                            },
                        ],
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Dolphe",
                        "text": (
                            "Later, at the gate, he stops you with a hand that doesn't "
                            "quite make contact.\n\n"
                            "\"The thing I said about it not paying.\" A pause. \"That was "
                            "the boring part first again. This is the rest of it.\"\n\n"
                            "\"I'd rather you had it from me on a Tuesday than from a road "
                            "in eight months.\""
                        ),
                    },
                ],
            },
            # ==========================================================
            # ACT THREE -- the turn.
            #
            # The prologue used to end four beats after the convoy: one
            # contract, one uneasy sight on the road home, and then a
            # goodbye at the door. That gave the player a job and a hub
            # but never a REASON -- nothing had happened TO them, so
            # "everything else is out there, off you go" was an
            # invitation rather than a call to action, and an invitation
            # is easy to decline.
            #
            # These three missions are the turn. You work a couple of
            # real jobs alongside people you now know, which makes the
            # crew feel like a crew rather than a tutorial rota; then
            # somebody stands in a yard and looks at you specifically;
            # then he sends something to find out what you are. You
            # arrive at the gate having been noticed, which is a very
            # different thing to walk out of a door with.
            #
            # NOTE ON IDS: these are numbered above pr11_the_gate but
            # ordered before it. Renaming pr11_the_gate to keep the
            # numbers tidy would strip its completion from every player
            # currently mid-prologue -- completed_missions stores the id
            # string. Cosmetic disorder beats wiping saves.
            # ==========================================================
            {
                "id": "pr12_quiet_yard",
                "name": "The Quiet Yard",
                "summary": "A routine sweep with Josh, who does not do routine.",
                "beats": [
                    {
                        "kind": "dialogue",
                        "speaker": "Josh",
                        "text": (
                            "\"Dolphe says sweep the yard. So we sweep the yard.\"\n\n"
                            "He is checking corners that do not need checking, in an "
                            "order he clearly worked out in advance.\n\n"
                            "\"I want to be very clear that I still don't like you. This "
                            "is professional courtesy. It runs out.\""
                        ),
                    },
                    {
                        "kind": "choice",
                        "prompt": (
                            "The yard is four crates, a dead floodlight and about an acre "
                            "of nothing. Josh has not stopped moving since you got here."
                        ),
                        "options": [
                            {
                                "id": "yard_ask_rex",
                                "label": "\"Who's Rex?\"",
                                "text": (
                                    "He stops moving.\n\n"
                                    "That's the whole answer, and it lasts about four "
                                    "seconds, and then he starts moving again.\n\n"
                                    "\"Not today. Check the north side.\""
                                ),
                                "flag": "pro_asked_rex",
                            },
                            {
                                "id": "yard_work",
                                "label": "\"North side. On it.\"",
                                "text": (
                                    "\"...Right.\" He sounds faintly thrown, like he had "
                                    "an argument prepared and you have declined to have "
                                    "it.\n\n\"Good. Fine. North side.\""
                                ),
                                "flag": "pro_easy_with_josh",
                            },
                        ],
                    },
                    {
                        "kind": "battle",
                        "enemies": ["Josh Hater", "Refense Hater"],
                        "level": 6,
                        "intro": (
                            "They come out from behind the crates with the specific "
                            "confidence of people who have rehearsed this.\n\n"
                            "\"JOSH!\" one of them shouts, delightedly, as though "
                            "arriving at a party."
                        ),
                        "on_win": (
                            "Josh stands over the quieter of the two for a moment "
                            "longer than the situation requires.\n\n"
                            "\"They knew I'd be here,\" he says. \"Dolphe assigned this "
                            "an hour ago.\"\n\n"
                            "He doesn't say the rest of it. He doesn't have to."
                        ),
                        "on_lose": (
                            "Josh gets you behind a crate, which is not where either of "
                            "you wanted to end up.\n\n\"Again. Properly this time.\""
                        ),
                    },
                    {
                        "kind": "reward",
                        "text": (
                            "He hands you half of what was in their bag without counting "
                            "it, which from Josh is practically a hug."
                        ),
                        "grant": {"gold": 500, "metal": 25, "lootbox": ("uncommon", 2)},
                    },
                ],
            },
            {
                "id": "pr13_the_figure",
                "name": "The Man In The Yard",
                "summary": "Somebody has been waiting for you to be worth talking to.",
                "beats": [
                    {
                        "kind": "dialogue",
                        "speaker": "Blueflame",
                        "text": (
                            "\"Third job this week where they knew we were coming,\" "
                            "Blueflame says, cheerfully, eating something she has not "
                            "identified. \"Statistically that's a leak. Emotionally "
                            "it's a bit rude.\"\n\n"
                            "\"Anyway. There's a man standing in the south yard. He's "
                            "been there forty minutes. He's not doing anything.\""
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Rohan",
                        "text": (
                            "He is dressed for an office that does not exist out here. "
                            "He does not look at Blueflame at all.\n\n"
                            "\"You came out of Ocellios,\" he says. To you. Only to "
                            "you.\n\n"
                            "\"Nine days ago there was nothing in that building worth "
                            "the electricity. Then there was you. I would like to know "
                            "which of those facts caused the other.\""
                        ),
                    },
                    {
                        "kind": "choice",
                        "prompt": (
                            "Blueflame has stopped eating. That, more than anything he "
                            "has said, is the part that worries you."
                        ),
                        "options": [
                            {
                                "id": "rohan_who",
                                "label": "\"Who are you?\"",
                                "text": (
                                    "\"Rohan.\" As though that settles it. As though you "
                                    "should have known.\n\n"
                                    "\"I keep an inventory. You are not on it. That is "
                                    "the entire problem and I would like it solved.\""
                                ),
                                "flag": "pro_asked_rohan_name",
                            },
                            {
                                "id": "rohan_hands",
                                "label": "*Look at your hands. Say nothing.*",
                                "text": (
                                    "He follows your eyes down, and something in his "
                                    "face resolves — not surprise. Confirmation.\n\n"
                                    "\"Thank you,\" he says. \"That was the answer.\"\n\n"
                                    "You did not say anything. That appears not to have "
                                    "mattered."
                                ),
                                "flag": "pro_showed_rohan",
                            },
                            {
                                "id": "rohan_leave",
                                "label": "\"You're standing in our yard.\"",
                                "text": (
                                    "\"I am.\" He does not move. \"It is a good yard. "
                                    "You have kept it better than the last people to "
                                    "hold it.\"\n\n"
                                    "The past tense sits there for a while after he "
                                    "stops speaking."
                                ),
                                "flag": "pro_pushed_rohan",
                            },
                        ],
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Rohan",
                        "text": (
                            "\"I am not going to fight you,\" he says, and turns to "
                            "go.\n\n"
                            "\"I don't know what you are yet. It would be poor practice "
                            "to spend myself finding out.\"\n\n"
                            "At the gate he pauses, without turning round.\n\n"
                            "\"I have sent something that will tell me. Try to survive "
                            "it — the data is worthless otherwise.\""
                        ),
                    },
                ],
            },
            {
                "id": "pr14_what_he_sent",
                "name": "What He Sent",
                "summary": "The prologue's last fight, and it is not a formality.",
                "beats": [
                    {
                        "kind": "dialogue",
                        "speaker": "Refender",
                        "text": (
                            "\"It came in over the ridge and it is not squawking any "
                            "transponder I have on file,\" Refender says, already moving. "
                            "\"Which means somebody built it to not be on file, which is "
                            "an expensive thing to want.\"\n\n"
                            "She hands you the good radio. She does not usually hand "
                            "anyone the good radio."
                        ),
                    },
                    {
                        # THE PROLOGUE BOSS, and the numbers here were
                        # measured rather than chosen.
                        #
                        # It was written as "Rohan's Herald" at level 8,
                        # which check_story rejected outright: 100% of a
                        # 4-character level-3 party, i.e. everything they
                        # have. Dropping the level did nothing -- 99% at
                        # 4, 100% at 6 -- because the template itself is
                        # endgame-statted, not because the level was
                        # wrong. Worth remembering: for a fight this far
                        # outside a party's weight class, picking a
                        # different enemy is the fix, and re-levelling is
                        # a way to spend an afternoon not fixing it.
                        #
                        # Rohan's Warden at 9 costs 33%, against The
                        # Quiet Yard's 10% earlier in the chapter -- a
                        # climax that is clearly the hardest thing in the
                        # prologue while still leaving a party that
                        # played well two thirds of its health. It is
                        # also one of HIS, which the fiction requires:
                        # he says he sent something, so the thing that
                        # arrives should have his name on it.
                        "kind": "battle",
                        "enemies": ["Rohan's Warden"],
                        "level": 9,
                        "intro": (
                            "It sets down in the yard without hurrying and takes a "
                            "moment to look at each of you in turn.\n\n"
                            "It spends noticeably longer on you."
                        ),
                        "on_win": (
                            "It goes down in one piece, which somehow reads worse than "
                            "coming apart would have.\n\n"
                            "Refender crouches by the housing and goes very still.\n\n"
                            "\"There's no weapons log,\" she says. \"There's a *camera* "
                            "log. It wasn't sent here to win.\""
                        ),
                        "on_lose": (
                            "You wake up in the Mess with Blueflame's coat over you and "
                            "Jofrog standing in the doorway like a very large closed "
                            "door.\n\n"
                            "It left. Nobody can tell you why it left."
                        ),
                    },
                    {
                        "kind": "reward",
                        "text": (
                            "Josh pulls the core out and turns it over twice before he "
                            "hands it to you.\n\n"
                            "\"He watched you,\" he says. \"That's what he came for. "
                            "That's what he *always* comes for.\"\n\n"
                            "It is the first time he has looked at you like you are on "
                            "the same side of something."
                        ),
                        # NO SHARDS HERE, deliberately, and it is the one
                        # reward in the prologue that looks like it is
                        # missing something.
                        #
                        # The spec was 120 Shards when pulls unlock and
                        # roughly 360 more across the rest -- 480 total,
                        # four pulls. Act Three added a fourth grant
                        # point and quietly pushed that to 600. Paying
                        # the boss in gear and materials instead keeps
                        # the pull budget exactly where it was set while
                        # still making it the richest fight in the
                        # chapter. Easy to flip if the prologue should
                        # end on five pulls rather than four.
                        "grant": {"item": "rare", "gold": 1400, "crystal": 45,
                                  "metal": 60, "lootbox": ("rare", 3)},
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Dolphe",
                        "text": (
                            "Dolphe reads the camera log twice, then puts it face-down "
                            "on the table, which he has never once done with anything.\n\n"
                            "\"Right,\" he says. \"So he knows.\"\n\n"
                            "\"Then we stop waiting to be found and we go and be "
                            "somewhere first. Everyone in the Gatehouse. Now, please.\""
                        ),
                    },
                ],
            },
            {
                "id": "pr11_the_gate",
                "name": "Good Luck, In Marker",
                "summary": "He knows your name now. Go and be somewhere first.",
                "beats": [
                    {
                        "kind": "dialogue",
                        "speaker": "Dolphe",
                        "text": (
                            "The Gatehouse is the last warm room before the cold one. "
                            "Somebody has written GOOD LUCK on the inside of the door in "
                            "marker, and somebody else has added a comma and a name that "
                            "has been rubbed almost out.\n\n"
                            "\"That's you done,\" Dolphe says. \"You know where everything "
                            "is and you know what it costs.\"\n\n"
                            "He taps the camera core, still sitting on the table where "
                            "he put it face-down.\n\n"
                            "\"And a man who keeps an inventory has put you on it. So "
                            "we're not settling in any more. The rest is out there, and "
                            "I'd rather we got to it first.\""
                        ),
                    },
                    {
                        "kind": "choice",
                        "prompt": "\"Anything before you go?\"",
                        "options": [
                            {
                                "id": "ready",
                                "label": "\"No. I'm good.\"",
                                "text": (
                                    "\"Good.\" He steps aside.\n\n"
                                    "\"For what it's worth — and I've been doing this long "
                                    "enough that it's worth something — you're going to be "
                                    "fine at this. Which is not the same as safe. I want to "
                                    "be accurate.\""
                                ),
                                "sets": {"pro_confident": True},
                            },
                            {
                                "id": "name",
                                "label": "\"Whose name is that on the door?\"",
                                "text": (
                                    "He looks at it for a while.\n\n"
                                    "\"Someone who wrote GOOD LUCK for the person after "
                                    "them,\" he says. \"Which is the whole job, really, if "
                                    "you strip the rest out.\"\n\n"
                                    "\"Go on. There's a marker in the drawer for when it's "
                                    "your turn.\""
                                ),
                                "sets": {"pro_asked_name": True},
                            },
                        ],
                    },
                    {
                        "kind": "unlock",
                        "feature": "domains",
                        "text": (
                            "**`/domains` is open.**\n\n"
                            "Short, self-contained fights that cost energy instead of a "
                            "whole afternoon. The place to test a squad before you commit "
                            "it to something longer."
                        ),
                    },
                    {
                        "kind": "unlock",
                        "feature": "raids",
                        "text": (
                            "**`/raid` is open.**\n\n"
                            "Everyone in the server hits the same boss. Bring your own "
                            "summon once a day; join anyone else's whenever."
                        ),
                    },
                    {
                        "kind": "unlock",
                        "feature": "gifting",
                        "text": (
                            "**`/gift` is open.**\n\n"
                            "\"Give people things,\" Jofrog says, from directly behind you. "
                            "\"I have read about this. I am told it is not weird if the "
                            "thing is useful.\""
                        ),
                    },
                    {
                        "kind": "reward",
                        "text": (
                            "Jofrog has left a bag by the door with a label on it in "
                            "very careful handwriting: **FOR THE FIRST ONE**.\n\n"
                            "There is a second label underneath, crossed out, reading "
                            "*FOR LUCK* — apparently reconsidered."
                        ),
                        "grant": {"gold": 1200, "lootbox": ("rare", 3), "shards": 120},
                    },
                    {
                        "kind": "unlock",
                        "feature": "adventure",
                        "text": (
                            "**`/adventure` is open.**\n\n"
                            "Expeditions. Multiple floors, HP that carries between fights, "
                            "and a campfire before the boss where you choose between "
                            "healing and a relic.\n\n"
                            "This is the game. Everything up to here was the building."
                        ),
                    },
                ],
            },
        ],
    },
]


# ----------------------------------------------------------------------
# Lookups. Missions are addressed by a globally unique id, so nothing
# needs to know which chapter it's in to run it.
# ----------------------------------------------------------------------

def mission_rewards(mission: dict) -> dict:
    """Everything a mission pays, summed across its `reward` beats.

    DERIVED from the beats rather than authored as a separate field on
    the mission, on purpose. A hand-written summary is a second source of
    truth that nobody updates: edit a grant, forget the summary, and the
    screen now advertises a payout the mission doesn't give. Reading the
    beats means the advertised reward is the reward, always.

    Returns a plain {key: total} -- currencies sum, and "item"/"lootbox"
    accumulate as {tier: count} since those are rarities, not amounts.
    """
    totals: dict = {}
    for beat in mission.get("beats", []):
        if beat.get("kind") != "reward":
            continue
        for key, value in (beat.get("grant") or {}).items():
            if key in ("item", "lootbox"):
                # Both keys accept a bare tier ("epic") or a 2-tuple, but
                # the SECOND element means different things:
                #
                #     "lootbox": ("epic", 3)        -> 3 of them
                #     "item":    ("epic", "weapon") -> one, in that slot
                #
                # Reading the item form as a count produced
                # `0 + "weapon"` and a TypeError the first time the
                # prologue's rewards were totalled. Splitting on the key
                # rather than on the shape is what keeps that honest --
                # the two forms are the same shape and always will be.
                tier, second = (value if isinstance(value, (list, tuple)) else (value, None))
                count = second if (key == "lootbox" and second is not None) else 1
                bucket = totals.setdefault(key, {})
                bucket[tier] = bucket.get(tier, 0) + count
            elif key == "character":
                totals.setdefault("character", []).append(value)
            else:
                totals[key] = totals.get(key, 0) + value
    return totals


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
