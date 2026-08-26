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
                        "grant": {"xp": 20, "item": "uncommon", "gold": 200, "lootbox": "common"},
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
                        "grant": {"xp": 30, "item": ("uncommon", "weapon")},
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
                                "sets": {"asked_about_class": True},
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
                                "sets": {"suspicious_of_jofrog": True},
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
                            "paragraph about the numbers being rude.\n\n"
                            "The banner has four buttons and you should press all of "
                            "them at least once: **×1** and **×10** roll, **📜 History** "
                            "shows your last hundred results, and **📊 Rates** shows the "
                            "actual odds and how close you are to a guarantee.\n\n"
                            "That last part matters. A 5★ is **guaranteed by pull 50**, "
                            "and from pull 30 the odds climb every roll — so a dry "
                            "streak is a countdown, not bad luck."
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
                        "grant": {"xp": 40, "shards": 120},
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
                        "grant": {"xp": 50, "item": "rare", "gold": 400, "wood": 40, "stone": 40,
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
                                "sets": {"pro_asked_card": True},
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
                                "sets": {"pro_card_handwriting": True},
                            },
                        ],
                    },
                    {
                        "kind": "unlock",
                        "feature": "cards",
                        "text": (
                            "**`/cards` and `/cardpull` are open.**\n\n"
                            "Cards run on **Cores**, not Shards — a separate pull with "
                            "its own count. One card per character, three big stats, and "
                            "an ability strong enough that gear no longer rolls anything "
                            "like it.\n\n"
                            "The banner is **the same screen** as `/pull`: ×1, ×10, "
                            "History, Rates, and the same guarantees — 5★ by pull 50, "
                            "climbing odds from pull 30, 4★ by pull 10. Learn one and "
                            "you have learned both.\n\n"
                            "The counts are separate, though. Pulling here never moves "
                            "your character pity, and pulling there never moves this "
                            "one.\n\n"
                            "You do not need a Card. You will want one."
                        ),
                    },
                    {
                        "kind": "reward",
                        "text": (
                            "\"Starter allocation,\" she says, in the voice of someone "
                            "reading a policy she wrote herself. \"Spend it badly if you "
                            "like. Everyone does the first time.\""
                        ),
                        # FIVE card pulls, matching the five character
                        # pulls the prologue pays out across its other
                        # grants. The two banners should leave the
                        # tutorial with the same number of rolls behind
                        # them -- a player who ends the prologue able to
                        # ten-pull one banner and single-pull the other
                        # has been taught that one of them matters more.
                        "grant": {"xp": 60, "cores": 600},
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
                        "grant": {"xp": 60, "gold": 900, "metal": 30, "lootbox": "uncommon", "shards": 120},
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
                        "grant": {"xp": 70, "item": "rare", "gold": 700, "crystal": 20, "lootbox": ("rare", 2),
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
                                "sets": {"pro_asked_rex": True},
                            },
                            {
                                "id": "yard_work",
                                "label": "\"North side. On it.\"",
                                "text": (
                                    "\"...Right.\" He sounds faintly thrown, like he had "
                                    "an argument prepared and you have declined to have "
                                    "it.\n\n\"Good. Fine. North side.\""
                                ),
                                "sets": {"pro_easy_with_josh": True},
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
                        "grant": {"xp": 80, "gold": 500, "metal": 25, "lootbox": ("uncommon", 2)},
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
                                "sets": {"pro_asked_rohan_name": True},
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
                                "sets": {"pro_showed_rohan": True},
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
                                "sets": {"pro_pushed_rohan": True},
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
                        # The prologue's fifth and last Shard grant.
                        #
                        # This was briefly shard-free, to hold the total
                        # at the 480 (four pulls) originally specified.
                        # The target is now FIVE character pulls and FIVE
                        # card pulls, so the boss pays like the rest of
                        # the chapter -- and the richest fight in the
                        # prologue no longer looks like the one reward
                        # that forgot something.
                        "grant": {"xp": 90, "item": "rare", "gold": 1400, "crystal": 45,
                                  "metal": 60, "lootbox": ("rare", 3), "shards": 120},
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
                # THE MISSION THAT ENDS THE PROLOGUE.
                #
                # `completes_prologue` was read by story_service in two
                # places and set by NO mission, so PlayerStory.
                # prologue_complete was False for every player who ever
                # lived. It did not bite today only because all 15
                # features happen to have their own unlock beat -- but
                # feature_unlocked() falls back to this flag for any
                # feature that does NOT, which means the next feature
                # added without an unlock beat would have been locked
                # forever, for everybody, with nothing to explain why.
                "completes_prologue": True,
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
                        "grant": {"xp": 100, "gold": 1200, "lootbox": ("rare", 3), "shards": 120},
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

    # ======================================================================
    # CHAPTER ONE — THE WORLD ALIGNERS
    # ======================================================================
    #
    # WHAT THIS CHAPTER IS ABOUT, in one line: four people leave a good
    # organisation because it is too big to check things quickly, and the
    # thing they want to check turns out to be real.
    #
    # ----------------------------------------------------------------------
    # THE RULE THIS CHAPTER IS WRITTEN UNDER: SAY THE THING
    # ----------------------------------------------------------------------
    # The prologue could afford to be oblique because it was a mystery
    # about the player. This one is a mystery about a MAN, and a mystery
    # about a man only works if the audience can follow the case. So the
    # main line states things plainly:
    #
    #   * Why the Aligners left Cascade -- a specific report, a specific
    #     eleven weeks, a specific conclusion nobody believes.
    #   * What Josh actually has on Rohan -- nineteen survey teams, by
    #     number, with dates. Not "something is wrong out there".
    #   * What Ashfield proves -- Cascade's traffic is being read. Which
    #     is a much better reason to distrust an ally than a feeling.
    #
    # EVERYTHING UNRESOLVED IS OPTIONAL AND ON THE MAP. Dolphin's amnesia,
    # his brother Dolpo, the H-Nation connection, the workbench nobody
    # sits at: all of it lives in NPC lines and notes in map_config, where
    # a player who wants the mystery can go and dig, and a player who
    # wants the plot is never confused by it.
    #
    # ----------------------------------------------------------------------
    # CAST NOTES
    # ----------------------------------------------------------------------
    # JOSH        Leader. Two years of being told he was grieving rather
    #             than right. Does not perform grief; performs competence,
    #             which is worse to watch.
    # REFENDER    The reason the faction functions. Blunt, precise, and
    #             the only one who says the quiet thing about Josh out
    #             loud -- to you, once, and never to him.
    # JOFROG      Warmth. Takes things literally. The chapter's floor: if
    #             Jofrog is worried, it is bad.
    # BLUEFLAME   Says the bleak thing cheerfully. The only one who finds
    #             any of this funny, which is how you know when he stops.
    # DOLPHIN     Comic register, and the chapter's one piece of real
    #             sadness, rationed to a single beat. He impersonates
    #             Dolphe openly and badly; everybody knows; that is the
    #             joke. He is NOT a twist.
    # ======================================================================
    {
        "id": "chapter1",
        "name": "Chapter One: Sixteen Freight",
        "blurb": "Four people left a good organisation. They would like to explain why.",
        "unlocks_region": None,
        "missions": [
            {
                "id": "c1m1_sixteen_freight",
                "name": "Sixteen Freight",
                "summary": "Josh has a building now, and an argument he'd like you to hear.",
                "beats": [
                    {
                        "kind": "dialogue",
                        "speaker": "Josh",
                        "text": (
                            "The address Josh gave you is a freight depot on the wrong "
                            "side of the ring road, and the number on the shutter is 16.\n\n"
                            "He is waiting under it with his hands in his pockets, and he "
                            "does not do the thing where somebody pretends they have not "
                            "been waiting.\n\n"
                            "\"You came,\" he says. \"Good. I'll do this badly if I put it "
                            "off, so I'm going to do it badly now.\"\n\n"
                            "He ducks under the shutter. It only opens halfway. Nobody has "
                            "fixed it and you get the strong sense nobody is going to."
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Josh",
                        "text": (
                            "Inside: concrete, four camp beds, and a kettle that is clearly "
                            "the most valued object in the building.\n\n"
                            "\"We're not Cascade any more. Four of us. Refender, Jofrog, "
                            "Blueflame, me.\" He counts them off like a man who has "
                            "practised making it sound like enough. \"World Aligners. "
                            "Blueflame picked the name and we've all decided to live "
                            "with it.\"\n\n"
                            "\"Before you ask: nobody threw us out and nobody stormed off. "
                            "Dolphe knows exactly where we are. He helped with the lease.\"\n\n"
                            "\"That's the part people find confusing, so I'll say it "
                            "straight. We didn't leave because Cascade is bad. We left "
                            "because Cascade is *big*.\""
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Refender",
                        "text": (
                            "\"He is going to be vague about this, so I will not be.\"\n\n"
                            "Refender does not look up from the four sets of gear she is "
                            "laying out in four identical rows.\n\n"
                            "\"In the spring we lost a convoy on the south road. Six "
                            "people. Cascade opened an inquiry, which was correct. The "
                            "inquiry took **eleven weeks**, which was not, and it concluded "
                            "that it was nobody's fault.\"\n\n"
                            "She squares the fourth row.\n\n"
                            "\"I have read every page of it. It is a good report. It is "
                            "careful, and it is fair, and it is eleven weeks long, and at "
                            "the end of it nobody had gone and *looked at the road*.\"\n\n"
                            "\"I went and looked at the road. It took a morning.\""
                        ),
                    },
                    {
                        "kind": "choice",
                        "prompt": (
                            "Josh is watching you take this in. He has clearly rehearsed "
                            "the next part and is clearly about to abandon it."
                        ),
                        "options": [
                            {
                                "id": "c1_ask_why_me",
                                "label": "\"Why tell me? I've been here nine days.\"",
                                "text": (
                                    "\"Because you've been here nine days,\" Josh says. "
                                    "\"Everyone else has had two years to get used to how "
                                    "things are done. You haven't got a used-to yet.\"\n\n"
                                    "\"And because the thing in the yard came for *you*, "
                                    "and I would like to be standing next to whoever that "
                                    "turns out to matter to.\""
                                ),
                                "sets": {"c1_asked_why_me": True},
                            },
                            {
                                "id": "c1_ask_dolphe",
                                "label": "\"What does Dolphe think about all this?\"",
                                "text": (
                                    "\"He thinks we're right and he thinks we're going to "
                                    "get hurt, and he's decided he can hold both of those "
                                    "without picking.\" Josh almost smiles. \"That's the "
                                    "most Dolphe sentence I've ever said out loud.\"\n\n"
                                    "\"He gave us the lease. He didn't give us the "
                                    "*people*. That's his whole position and it's a fair "
                                    "one.\""
                                ),
                                "sets": {"c1_asked_dolphe": True},
                            },
                            {
                                "id": "c1_ask_bad",
                                "label": "\"You're describing paperwork. What's the real reason?\"",
                                "text": (
                                    "Refender's hands stop moving.\n\n"
                                    "\"The paperwork *is* the real reason,\" she says. \"I "
                                    "understand it is an unsatisfying one. Six people are "
                                    "dead and the process that was supposed to find out why "
                                    "worked exactly as designed and found out nothing.\"\n\n"
                                    "\"I would rather be four people who are sometimes "
                                    "wrong quickly than four hundred who are eventually "
                                    "correct.\""
                                ),
                                "sets": {"c1_pushed_back": True},
                            },
                        ],
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Dolphin",
                        "text": (
                            "Somebody clears his throat from the doorway in a way that is "
                            "unmistakably Dolphe's throat-clear.\n\n"
                            "It is not Dolphe. It is a man in a coat that is very nearly "
                            "Dolphe's coat, standing the way Dolphe stands, and getting "
                            "about seventy percent of it.\n\n"
                            "\"Team,\" he says, in Dolphe's voice. \"I've reviewed the "
                            "situation and I—\"\n\n"
                            "\"Dolphin.\"\n\n"
                            "\"—and I'm going to stop doing that,\" he finishes, in his own."
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Blueflame",
                        "text": (
                            "\"That's Dolphin,\" Blueflame says, from the table he is "
                            "sitting on rather than at. \"He does an impression of Dolphe "
                            "so that people who are expecting Dolphe get nodded at by "
                            "someone.\"\n\n"
                            "\"It works about half the time, which is a *staggering* rate "
                            "for something that shouldn't work at all.\"\n\n"
                            "\"He knows we know. We know he knows we know. It's the most "
                            "honest arrangement in the building.\"\n\n"
                            "Dolphin gives a small bow. It is also seventy percent "
                            "Dolphe's."
                        ),
                    },
                    {
                        # THE THING THAT HAPPENS. Every mission needs one
                        # (see the TONE block at the top of this module),
                        # and it lands better here than a fifth speech:
                        # the pitch is interrupted by evidence FOR the
                        # pitch, so the player is convinced by the plot
                        # rather than by an argument.
                        # 13% of a level-6 party of four -- MEASURED, not
                        # picked. A Recon Scout at any level costs 0%: the
                        # early drones are region-one trash and cannot be
                        # made threatening by levelling them. Combining
                        # enemies is also violently non-linear here (two
                        # 13% enemies together measured 74%), so the
                        # chapter climbs by adding bodies one at a time.
                        "kind": "battle",
                        "enemies": ["Rohan's Warden"],
                        "level": 12,
                        "intro": (
                            "Jofrog comes through the side door faster than a man that "
                            "size should move.\n\n"
                            "\"There's something in the lot,\" he says. \"It's been there "
                            "since before you arrived. I thought it was a *generator*.\"\n\n"
                            "It is not a generator. It stands up — unhurried, on four "
                            "legs it had folded under itself — turns its housing toward "
                            "the open shutter, and holds there.\n\n"
                            "Not aiming. *Reading.*"
                        ),
                        "on_win": (
                            "It fights back hard and it never once tries to leave, which "
                            "are two facts that do not go together.\n\n"
                            "Refender is on it before it has finished settling.\n\n"
                            "\"Same as the yard,\" she says. \"No weapons log. Camera log, "
                            "half full, and the timestamps start nine days ago.\"\n\n"
                            "Josh says nothing at all, which from him is a shout."
                        ),
                        "on_lose": (
                            "It leaves before it finishes you, which is somehow the "
                            "insulting part.\n\n"
                            "Jofrog sits you down by the kettle and does not say anything "
                            "encouraging, because he is not a liar."
                        ),
                    },
                    {
                        "kind": "reward",
                        "text": (
                            "Josh pulls the camera core and turns it over the way you turn "
                            "over a thing you have seen before.\n\n"
                            "\"Nine days,\" he says. \"It started watching this building "
                            "nine days ago. We signed the lease eleven days ago.\"\n\n"
                            "He hands it to you rather than to Refender, which everyone in "
                            "the room notices.\n\n"
                            "\"Come and look at the table.\""
                        ),
                        "grant": {"xp": 80, "gold": 900, "item": "rare", "evolution_fragments": 40,
                                  "lootbox": ("rare", 2)},
                    },
                ],
            },

            {
                "id": "c1m2_the_pitch",
                "name": "What Josh Has",
                "summary": "Two years of work, laid out on a table, in order.",
                "beats": [
                    {
                        "kind": "dialogue",
                        "speaker": "Josh",
                        "text": (
                            "The table is the length of the room and there are four chairs "
                            "at one end of it. Everything on it is paper.\n\n"
                            "\"I'm going to show you all of it in order,\" Josh says, \"and "
                            "you're going to tell me at the end whether I'm mad. People "
                            "keep deciding that halfway and then not listening to the "
                            "rest.\"\n\n"
                            "He puts down the first sheet.\n\n"
                            "\"Nineteen Xender survey teams. Numbered, dated. Over "
                            "fourteen months, all nineteen went into the same stretch of "
                            "country north of Ashfield.\"\n\n"
                            "He puts down the second sheet.\n\n"
                            "\"None of them filed anything on the way out. Not a report, "
                            "not a fuel claim, not a resignation. Nineteen.\""
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Josh",
                        "text": (
                            "\"Here's the part that took me a year to believe.\"\n\n"
                            "\"Xender didn't cover it up. There's no cover-up. The filings "
                            "are *public* — they're dull, they're numbered, and they're "
                            "sitting in an archive anyone can walk into.\"\n\n"
                            "He taps the bottom of the sheet, where somebody has written in "
                            "small letters: *they are not hiding it. nobody is looking.*\n\n"
                            "\"Nineteen teams is a rounding error to a company that size. "
                            "It only looks like a pattern if one person reads fourteen "
                            "months of filings in a row.\"\n\n"
                            "\"I did that. It took a winter. That's the whole trick.\""
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Refender",
                        "text": (
                            "\"Tell them the rest of it, Josh.\"\n\n"
                            "He doesn't, so she does.\n\n"
                            "\"Josh took this to Cascade fourteen times. I have the dates; "
                            "I keep them because he won't.\" Her voice is exactly as level "
                            "as it always is, which is how you can tell.\n\n"
                            "\"Each time it was received politely and referred to an "
                            "appropriate desk. Twice it came back with a note suggesting he "
                            "speak to someone about how he was doing.\"\n\n"
                            "\"He was not doing well. That was true. It was also **not the "
                            "point**, and being right about the first thing let everybody "
                            "off the second.\""
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Jofrog",
                        "text": (
                            "\"Can I do the last bit?\" Jofrog says. \"I've been practising "
                            "the last bit.\"\n\n"
                            "He lays down a photograph, taken from very far away, of a "
                            "drilling machine the size of a house lying in two pieces.\n\n"
                            "\"That's a Xender deep-driller. It cost more than this "
                            "building. It's cut in half.\"\n\n"
                            "He puts his finger next to the cut, which is perfectly "
                            "straight.\n\n"
                            "\"One pass. Whatever did that did it *once* and then went "
                            "away and left it there. Josh says a person who can afford to "
                            "leave that lying in a field is telling you something about "
                            "themselves.\"\n\n"
                            "He looks pleased with the delivery and then, a second later, "
                            "considerably less pleased with the content."
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Blueflame",
                        "text": (
                            "\"And there's a letter on it,\" Blueflame says.\n\n"
                            "He turns the photograph a quarter-turn so you can see the "
                            "plating near the cut, where something has been scratched into "
                            "the metal by hand.\n\n"
                            "One character. **R**.\n\n"
                            "\"Everyone who's ever seen one calls him Mr. R, because "
                            "that's all anyone's got.\" He says it as lightly as he says "
                            "everything. \"Fourteen months and one letter. He's not "
                            "shy — he's *tidy*.\""
                        ),
                    },
                    {
                        "kind": "choice",
                        "prompt": (
                            "Four people are looking at you. Josh has asked you a direct "
                            "question and is visibly bracing for the answer he usually "
                            "gets."
                        ),
                        "options": [
                            {
                                "id": "c1_believe",
                                "label": "\"You're not mad. Nineteen is nineteen.\"",
                                "text": (
                                    "Josh lets a breath out that he has clearly been "
                                    "holding for about fourteen months.\n\n"
                                    "\"Right,\" he says. \"Right. Good.\" He starts "
                                    "squaring the sheets and gives up on it immediately, "
                                    "which Refender notices and does not mention.\n\n"
                                    "\"Then I'll tell you what I want to do about it.\""
                                ),
                                "sets": {"c1_believed_josh": True},
                            },
                            {
                                "id": "c1_hole",
                                "label": "\"There's a hole in it. Why hasn't he touched Cascade?\"",
                                "text": (
                                    "\"*Thank* you,\" says Refender, with feeling.\n\n"
                                    "\"It is the correct question and Josh hates it. "
                                    "Nineteen Xender teams and not one Cascade convoy — "
                                    "until the spring, when we lost six people on a road "
                                    "he has no reason to care about.\"\n\n"
                                    "\"Either those are unrelated, or he has started, and I "
                                    "would like to know which before we find out the "
                                    "expensive way.\""
                                ),
                                "sets": {"c1_found_the_hole": True},
                            },
                            {
                                "id": "c1_cascade_first",
                                "label": "\"Take it to Dolphe. Properly, one more time.\"",
                                "text": (
                                    "\"I would,\" Josh says, and he means it. \"I've got no "
                                    "pride left about this, I'd take it to him on my "
                                    "knees.\"\n\n"
                                    "\"But he'd have to put it through the same desks, "
                                    "because he's the head of an organisation and that's "
                                    "what heads of organisations do. Eleven weeks. And "
                                    "there's a thing sitting in our lot that has been "
                                    "watching us for nine days.\"\n\n"
                                    "\"I haven't got eleven weeks. That's all. That's the "
                                    "entire disagreement.\""
                                ),
                                "sets": {"c1_argued_for_cascade": True},
                            },
                        ],
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Josh",
                        "text": (
                            "\"So here's what I want to do, and it's small, and that's "
                            "deliberate.\"\n\n"
                            "He puts his hand flat on a map at the edge of the table — "
                            "an ordinary regional map, the kind that comes free with a "
                            "fuel card.\n\n"
                            "\"There's a signal relay at Ashfield. It's ours — Cascade's — "
                            "it's been there nine years and it does nothing but pass "
                            "traffic along the northern line.\"\n\n"
                            "\"Every one of those nineteen teams went past it. And three "
                            "weeks ago its output stopped matching its input, by about a "
                            "second and a half.\"\n\n"
                            "\"That's it. That's the whole lead. A second and a half.\""
                        ),
                    },
                    {
                        # ESCALATION: two bodies, not one. The chapter's
                        # fights climb 1 -> 2 -> 3 enemies, which is the
                        # shape check_story measures for (a chapter must
                        # end on its hardest fight, and three bodies act
                        # three times a cycle where one acts once).
                        # 25% -- up from 13%, by adding a second body
                        # rather than by raising a level.
                        "kind": "battle",
                        "enemies": ["Rohan's Warden", "Xender Recon Scout"],
                        "level": 17,
                        "intro": (
                            "The lights go out in the order they are wired, which is "
                            "north wall first.\n\n"
                            "\"That's not the grid,\" Refender says, already moving. "
                            "\"The grid fails all at once. That was *done*.\"\n\n"
                            "Two of them come in under the half-open shutter, and these "
                            "ones are not carrying cameras."
                        ),
                        "on_win": (
                            "Blueflame gets the lights back with a fusebox and an "
                            "attitude.\n\n"
                            "In the middle of the floor, the table is exactly as it was. "
                            "Nothing has been taken. Nothing has been burned.\n\n"
                            "\"They came in, they didn't touch the wall, and they left "
                            "when we pushed,\" Josh says slowly. \"That's not a raid. "
                            "That's someone finding out how hard we push.\""
                        ),
                        "on_lose": (
                            "You come round on one of the four camp beds with Jofrog "
                            "sitting on the floor beside it, entirely still, watching the "
                            "shutter.\n\n"
                            "\"They went,\" he says. \"They didn't take anything. I've "
                            "checked twice. I keep checking.\""
                        ),
                    },
                    {
                        "kind": "reward",
                        "text": (
                            "Refender hands you a kit bag that has been packed by someone "
                            "who has thought about it for a long time.\n\n"
                            "\"You are going to Ashfield in the morning,\" she says. \"Not "
                            "because Josh asked. Because I have run out of ways to be "
                            "careful about this from a chair.\"\n\n"
                            "\"Take the good radio. Bring it back.\""
                        ),
                        "grant": {"xp": 130, "gold": 1400, "item": "rare", "evolution_fragments": 60,
                                  "shards": 120, "cores": 120},
                    },
                ],
            },

            {
                "id": "c1m3_ashfield",
                "name": "A Second And A Half",
                "summary": "The relay is fine. That is the problem with it.",
                "beats": [
                    {
                        "kind": "dialogue",
                        "speaker": "Jofrog",
                        "text": (
                            "Ashfield is a hill, a fence, and a mast, and the drive up "
                            "takes two hours in a van that Jofrog has strong opinions "
                            "about.\n\n"
                            "\"I like this bit,\" he announces, somewhere around the "
                            "ninety-minute mark. \"The going-somewhere bit. Nobody's "
                            "worried yet.\"\n\n"
                            "In the back, Dolphin has fallen asleep in the coat and is "
                            "listing gently against the window.\n\n"
                            "\"He came because nobody told him not to,\" Jofrog says "
                            "fondly. \"That's how he ends up most places.\""
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Refender",
                        "text": (
                            "The relay is a nine-year-old mast in a wire cage, and there "
                            "is nothing wrong with it.\n\n"
                            "\"No damage. No tampering. The seals are the original seals — "
                            "I can see the batch stamp from here.\" Refender walks the "
                            "fence line twice anyway. \"It is in better condition than the "
                            "one at Central.\"\n\n"
                            "\"Which is the problem, because it is also lying.\"\n\n"
                            "She holds up the good radio.\n\n"
                            "\"Everything Cascade sends up the northern line arrives a "
                            "second and a half late and *perfectly intact*. Nothing is "
                            "missing. Nothing is altered.\"\n\n"
                            "\"A second and a half is how long it takes to copy "
                            "something.\""
                        ),
                    },
                    {
                        "kind": "choice",
                        "prompt": (
                            "It takes a moment to land, and then it lands all at once."
                        ),
                        "options": [
                            {
                                "id": "c1_reading",
                                "label": "\"He's not attacking Cascade. He's reading it.\"",
                                "text": (
                                    "\"Yes,\" Refender says. \"For at least three weeks, "
                                    "and possibly for nine years — I can only prove three.\"\n\n"
                                    "\"Every route filing. Every convoy schedule. Every "
                                    "one of Josh's fourteen reports, incidentally, since "
                                    "he filed them all through this line.\"\n\n"
                                    "A pause.\n\n"
                                    "\"He has read Josh's case against him. He has been "
                                    "reading it as it was written.\""
                                ),
                                "sets": {"c1_understood_relay": True},
                            },
                            {
                                "id": "c1_who_installed",
                                "label": "\"Who's had access to this mast?\"",
                                "text": (
                                    "\"Cascade maintenance, on a nine-year rota. Eleven "
                                    "names.\" She has clearly had this answer ready since "
                                    "the van. \"I have all eleven and I do not think any of "
                                    "them did it.\"\n\n"
                                    "\"You do not need a person inside if you have a mast "
                                    "outside. That is the entire elegance of it, and I "
                                    "resent how much I admire it.\""
                                ),
                                "sets": {"c1_asked_access": True},
                            },
                            {
                                "id": "c1_tell_dolphe",
                                "label": "\"Cascade needs to know today. Not in eleven weeks.\"",
                                "text": (
                                    "\"Agreed,\" Refender says, without hesitating, and "
                                    "something in your chest unclenches slightly.\n\n"
                                    "\"We are not keeping this. We were never going to keep "
                                    "this. Josh will grumble and Josh will also be the one "
                                    "who drives it down.\"\n\n"
                                    "\"We left so that we could check things quickly. We "
                                    "did not leave so that we could sit on them.\""
                                ),
                                "sets": {"c1_told_cascade": True},
                            },
                        ],
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Dolphin",
                        "text": (
                            "Dolphin has wandered to the far side of the cage and gone "
                            "very quiet, which is not a thing he does.\n\n"
                            "He is looking at the maintenance plate bolted to the mast "
                            "foot. Nine years of signatures, two a year, in eleven "
                            "different hands.\n\n"
                            "\"I know this handwriting,\" he says.\n\n"
                            "He says it in his own voice, and he sounds frightened by it.\n\n"
                            "\"I don't know how I know it. I don't know *any* handwriting. "
                            "I've got two years of knowing things and this isn't in them.\"\n\n"
                            "He steps back from the plate like it has moved.\n\n"
                            "\"Can we — is it alright if I wait in the van?\""
                        ),
                    },
                    {
                        # THE CHAPTER'S HARDEST FIGHT SO FAR, and it must
                        # be: check_story asserts a chapter ends on its
                        # hardest encounter, and this is currently the
                        # last one written. Three bodies against the two
                        # and one before it.
                        # 43%: harder than anything in the prologue,
                        # whose climax measured 33%, and comfortably the
                        # hardest fight in this chapter -- which
                        # check_story asserts, because both previously
                        # written chapters ended on their EASIEST fight
                        # and nothing but measurement would have shown it.
                        "kind": "battle",
                        "enemies": ["Rohan's Warden", "Xender Recon Scout", "Concussion Drone"],
                        "level": 16,
                        "intro": (
                            "The mast stops transmitting.\n\n"
                            "Not breaks. *Stops* — cleanly, mid-packet, the way a thing "
                            "stops when somebody decides it should.\n\n"
                            "\"Right,\" says Blueflame, with enormous cheer. \"So he's "
                            "listening to us listening to him.\"\n\n"
                            "Three shapes come up the hill from the north side, unhurried, "
                            "in a formation that has been used before."
                        ),
                        "on_win": (
                            "The last of them goes down on the fence line and the mast "
                            "comes back on by itself four seconds later, as though nothing "
                            "had interrupted it.\n\n"
                            "Refender pulls the Warden's core and reads it standing up in "
                            "the wind.\n\n"
                            "\"Camera log,\" she says. \"Again. And a routing table.\"\n\n"
                            "She turns the screen so you can see the top line of it.\n\n"
                            "\"It was not sending to Xender. It was sending **north**, to "
                            "somewhere with no name on any map I own — and it has been "
                            "doing it since the spring.\""
                        ),
                        "on_lose": (
                            "You come round in the van with the heater on and Ashfield "
                            "already an hour behind you.\n\n"
                            "Nobody says the obvious thing, which is that they did not "
                            "follow."
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Josh",
                        "text": (
                            "Josh reads the routing table three times in the depot with "
                            "his coat still on.\n\n"
                            "\"Fourteen reports,\" he says. \"I filed fourteen reports "
                            "about this man up a line he was standing on.\"\n\n"
                            "He puts the screen down carefully, which is worse than if he "
                            "had thrown it.\n\n"
                            "\"Everyone who told me I was grieving was reading a copy he'd "
                            "already had.\"\n\n"
                            "Then, quieter, and to you rather than the room:\n\n"
                            "\"His name is Rohan. I've had it for a year. I stopped saying "
                            "it out loud because of what people's faces did.\"\n\n"
                            "\"You can say it. I'd like somebody else to be able to say "
                            "it.\""
                        ),
                    },
                    {
                        "kind": "reward",
                        "text": (
                            "Refender writes the whole of it up in a single evening — the "
                            "mast, the delay, the routing table, the nineteen teams — and "
                            "sends it to Cascade Central before anyone can argue about "
                            "whether to.\n\n"
                            "The reply comes back in **forty minutes**, which is not "
                            "eleven weeks.\n\n"
                            "It says: *Understood. Northern line is dark as of now. Don't "
                            "go back to Ashfield. — D*\n\n"
                            "Jofrog reads it twice and puts the kettle on, which is what "
                            "Jofrog does with news of any temperature."
                        ),
                        "grant": {"xp": 180, "gold": 2200, "item": "epic", "evolution_fragments": 90,
                                  "shards": 200, "cores": 200, "lootbox": ("epic", 2)},
                    },
                ],
            },

            {
                # THE QUIET MISSION. No fight, on purpose.
                #
                # A chapter that is all escalation has no shape. This one
                # is a room, four objects and a man who cannot come in,
                # and it carries the chapter's whole emotional load --
                # which is why the objects are on the MAP as notes rather
                # than in beats. The player finds Rex by walking around
                # his workshop, not by being told about him.
                #
                # It also does the plot work the reveal needs: Rex found
                # the Ashfield delay two years before Refender did, told
                # Josh, and was told he needed a holiday. Josh has been
                # carrying that since.
                "id": "c1m4_still_switched_on",
                "name": "What He Left Switched On",
                "summary": "The south building has been locked for two years. It has not been off.",
                "beats": [
                    {
                        "kind": "dialogue",
                        "speaker": "Josh",
                        "text": (
                            "Josh walks you to the south building and stops about four "
                            "metres short of the door, at what is very obviously a "
                            "practised distance.\n\n"
                            "\"Key's taped under the bench in Records. It's been there "
                            "since we moved in. I put it there so I'd know where it was "
                            "and then I never went and got it.\"\n\n"
                            "He looks at the door rather than at you.\n\n"
                            "\"It's Rex's. It's exactly how he left it, because I pay the "
                            "power bill on it and I don't go in. I'm aware of how that "
                            "sounds. I've had two years to find a better way to say it "
                            "and this is the best one I've got.\""
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Refender",
                        "text": (
                            "\"I have been in twice,\" Refender says, quietly, once he has "
                            "gone back inside. \"Once to check the wiring was safe, and "
                            "once because I did not believe the first time.\"\n\n"
                            "\"There is a receiver in there. Hand-built. It has been "
                            "recording the northern line continuously for two years, and "
                            "it was switched on **before** he died.\"\n\n"
                            "She hands you the key.\n\n"
                            "\"I did not tell Josh, because at the time it was a machine "
                            "in a room and it meant nothing. As of Ashfield it means "
                            "something and I am now the person who sat on it for eleven "
                            "months.\"\n\n"
                            "\"Go in. Read the notebook. I will tell him myself, tonight, "
                            "and I would rather you did not do it for me.\""
                        ),
                    },
                    {
                        "kind": "choice",
                        "prompt": (
                            "The door opens easily. The light above the bench is on, and "
                            "warm, which means it has been on for two years."
                        ),
                        "options": [
                            {
                                "id": "c1_read_notebook",
                                "label": "*Read the notebook first.*",
                                "text": (
                                    "The last written page is dated the 12th.\n\n"
                                    "*second and a half. every time. it is not the "
                                    "equipment.*\n\n"
                                    "*somebody is copying the line. told J. J thinks I "
                                    "need a holiday. going to go and look at the mast "
                                    "myself on the 14th.*\n\n"
                                    "There is no entry for the 14th. There is no entry for "
                                    "any day after it.\n\n"
                                    "Rex found it two years before Refender did. He told "
                                    "one person. That person now runs a faction out of a "
                                    "freight depot because nobody would listen to him "
                                    "either."
                                ),
                                "sets": {"c1_read_rex_notebook": True},
                            },
                            {
                                "id": "c1_look_around",
                                "label": "*Don't touch anything. Just look.*",
                                "text": (
                                    "Tools laid out in the order you would use them. A mug "
                                    "two thirds full, washed on the outside and put back "
                                    "in its own ring. A receiver running off the mains "
                                    "with a full tape and a counter in the tens of "
                                    "thousands.\n\n"
                                    "Nothing in this room has been tidied and nothing in "
                                    "it has been disturbed. Somebody has been keeping it "
                                    "at exactly the temperature of an afternoon that "
                                    "hasn't ended.\n\n"
                                    "You are almost certain Josh has never once come in "
                                    "here. You are equally certain he knows where every "
                                    "object in it is."
                                ),
                                "sets": {"c1_looked_around_workshop": True},
                            },
                            {
                                "id": "c1_switch_off",
                                "label": "*Reach for the light switch.*",
                                "text": (
                                    "Your hand is on it before you have finished deciding, "
                                    "and then you stop.\n\n"
                                    "It is not your light to turn off. It is not Refender's "
                                    "either, and she has been in here twice and left it "
                                    "burning both times.\n\n"
                                    "You take your hand back. The bulb goes on being warm, "
                                    "the way it has been for two years, over a bench where "
                                    "somebody meant to come back."
                                ),
                                "sets": {"c1_left_the_light_on": True},
                            },
                        ],
                    },
                    {
                        "kind": "reward",
                        "text": (
                            "There is a toolroll under the bench with a name on it in "
                            "marker, and a second name underneath in different "
                            "handwriting: *if you're reading this you're using them, so "
                            "they're yours now, don't be weird about it.*\n\n"
                            "The screwdriver is behind the thing somebody once insisted "
                            "was not a shelf."
                        ),
                        "grant": {"xp": 220, "gold": 1600, "item": ("epic", "artifact"),
                                  "evolution_fragments": 80, "cores": 120},
                    },
                ],
            },

            {
                "id": "c1m5_the_herald",
                "name": "The Herald",
                "summary": "Something is coming up the access road, and it is not in a hurry.",
                "beats": [
                    {
                        "kind": "dialogue",
                        "speaker": "Blueflame",
                        "text": (
                            "Blueflame puts his head round the workshop door, which "
                            "nobody has done in two years, and does not appear to notice "
                            "that he has.\n\n"
                            "\"So there's a thing on the access road,\" he says. \"It's "
                            "walking. It's been walking for about a mile and it hasn't "
                            "sped up once.\"\n\n"
                            "\"Refender says it's putting out a carrier signal. Not "
                            "sending anything. Just — being on.\"\n\n"
                            "He considers the door frame for a second.\n\n"
                            "\"It's coming to *this* building. Not the depot. This one.\""
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Josh",
                        "text": (
                            "Josh is already outside, and he has gone very calm, which is "
                            "the worst version of him.\n\n"
                            "\"Forty minutes,\" he says. \"Refender sent Cascade the "
                            "routing table forty minutes before that thing stepped onto "
                            "the road.\"\n\n"
                            "\"He wasn't watching the depot. He was watching the "
                            "*line* — and the second we said his name on it, he sent "
                            "something to the one building that could prove Rex was right "
                            "first.\"\n\n"
                            "He checks his weapon without looking at it.\n\n"
                            "\"It's here for the receiver. It is not getting the "
                            "receiver.\""
                        ),
                    },
                    {
                        "kind": "choice",
                        "prompt": (
                            "It is four hundred metres out and holding a walking pace. "
                            "There is time to do exactly one sensible thing."
                        ),
                        "options": [
                            {
                                "id": "c1_save_tape",
                                "label": "\"Get the tape out. The building doesn't matter.\"",
                                "text": (
                                    "Refender has the reel out of the housing in under a "
                                    "minute and into a case that was clearly built for "
                                    "something else.\n\n"
                                    "\"Two years of the northern line,\" she says. \"If we "
                                    "lose the room we still have the evidence. Thank you "
                                    "for saying it out loud — Josh was not going to.\"\n\n"
                                    "Josh does not argue, which is how you know she's "
                                    "right."
                                ),
                                "sets": {"c1_saved_the_tape": True},
                            },
                            {
                                "id": "c1_hold_the_door",
                                "label": "\"Then we hold the building. All of it.\"",
                                "text": (
                                    "\"Yes,\" Josh says, immediately and with something "
                                    "close to gratitude, which from him is alarming.\n\n"
                                    "Refender's jaw sets. \"Noted, and I will say for the "
                                    "record that a room is not worth a person.\"\n\n"
                                    "She takes up a position covering the door anyway.\n\n"
                                    "\"The record is now made. Let us hold the building.\""
                                ),
                                "sets": {"c1_held_the_workshop": True},
                            },
                            {
                                "id": "c1_get_dolphin_out",
                                "label": "\"Where's Dolphin?\"",
                                "text": (
                                    "There is a short, bad silence.\n\n"
                                    "Then Jofrog says, \"Van,\" with enormous relief, and "
                                    "goes to make sure.\n\n"
                                    "He comes back with Dolphin, who is white, and who "
                                    "says, before anyone asks him anything: \"It stopped. "
                                    "When it got level with the van. It *stopped* and then "
                                    "it started again.\"\n\n"
                                    "Nobody has an answer for that, and there is no longer "
                                    "time to look for one."
                                ),
                                "sets": {"c1_asked_about_dolphin": True},
                            },
                        ],
                    },
                    {
                        # THE CHAPTER CLIMAX. Rohan's Herald at 14 measures
                        # ~54% of a level-11 party -- against 33% for the
                        # prologue's hardest, and comfortably the biggest
                        # number in this chapter, which check_story
                        # asserts. The Herald is also the template the
                        # prologue tried to use for its own boss and had
                        # to abandon as unwinnable at that point; using it
                        # here is the payoff for having grown into it.
                        "kind": "battle",
                        "enemies": ["Rohan's Herald"],
                        "level": 14,
                        "intro": (
                            "It comes up the last of the road at the same walking pace it "
                            "has held for a mile, and stops at the workshop door.\n\n"
                            "It is tall, and it is *finished* — no field welds, no "
                            "scavenged plate, nothing about it improvised. Somebody built "
                            "this in a place with proper tools and enough time.\n\n"
                            "It looks at the four of you. Then it looks past you, at the "
                            "bench, and the light still burning over it.\n\n"
                            "Then it comes in."
                        ),
                        "on_win": (
                            "It takes all four of you and most of what you have, and when "
                            "it finally goes down it goes down facing the bench.\n\n"
                            "Josh gets to it first and pulls the housing off with his "
                            "hands.\n\n"
                            "Inside, where a manufacturer's plate would go, one character "
                            "is scratched into the metal by hand. **R**.\n\n"
                            "Underneath it, in the same hand, much smaller, a second "
                            "line — and this one is not a letter. It is a date.\n\n"
                            "It is the 14th."
                        ),
                        "on_lose": (
                            "You come round on the workshop floor with the light still on "
                            "above you and Jofrog's coat under your head.\n\n"
                            "The building is standing. The bench is untouched. The "
                            "receiver is gone, housing and all, cut out cleanly in one "
                            "pass.\n\n"
                            "Refender is sitting against the wall with the tape reel in "
                            "both hands, and she does not say a single word about having "
                            "taken it out first."
                        ),
                    },
                    {
                        "kind": "reward",
                        "text": (
                            "Nobody clears up. Everybody sits down more or less where "
                            "they were standing.\n\n"
                            "After a while Jofrog goes and puts the kettle on in the other "
                            "building and carries four mugs back across the yard in the "
                            "rain, which takes him a long time, and which nobody comments "
                            "on because it is the only useful thing any of them can think "
                            "of to do."
                        ),
                        "grant": {"xp": 270, "gold": 3600, "item": "epic", "evolution_fragments": 140,
                                  "shards": 300, "cores": 300, "lootbox": ("epic", 3)},
                    },
                ],
            },

            {
                # THE CHAPTER CLOSE. No fight -- the last BATTLE in the
                # chapter is the Herald, which is what the climax rule
                # measures, so this is free to be a conversation.
                #
                # Ending state, deliberately unresolved in one specific
                # way: Josh trusts YOU and still does not trust Cascade,
                # and both are reasonable. The player has to hold two
                # true things that point in opposite directions, which is
                # the whole argument the faction exists to have.
                "id": "c1m6_stay_out_of_it",
                "name": "Stay Out Of It",
                "summary": "He has a date now. He would like you to not come.",
                "beats": [
                    {
                        "kind": "dialogue",
                        "speaker": "Josh",
                        "text": (
                            "Josh is at the long table with his coat still on, which means "
                            "he has not sat down properly, which means he is leaving.\n\n"
                            "\"The date on that thing is the day Rex went to the mast,\" "
                            "he says. \"He didn't stamp it as a build date. He stamped it "
                            "because it's a *label*. That machine was made to mark an "
                            "anniversary.\"\n\n"
                            "\"I've spent two years being told I was seeing patterns "
                            "because I couldn't accept an accident.\" He turns the housing "
                            "plate over once. \"He's been signing his work the whole time. "
                            "Nobody looks at the bottom of things.\""
                        ),
                    },
                    {
                        # Only if you actually went in and read it. Josh
                        # cannot bring himself to, so somebody having done
                        # it on his behalf is a specific kindness he is
                        # specifically bad at receiving.
                        "requires": ["c1_read_rex_notebook"],
                        "kind": "dialogue",
                        "speaker": "Josh",
                        "text": (
                            "\"You read it,\" Josh says, out of nowhere. \"The "
                            "notebook. Refender said.\"\n\n"
                            "He does not look up from the housing plate.\n\n"
                            "\"I've had the key to that building for two years. Two "
                            "years, and a man I've never met walks in and reads the last "
                            "thing he wrote inside a morning.\"\n\n"
                            "\"I'm not having a go. I want to be clear that I'm not "
                            "having a go.\" A pause. \"What did the writing look like? "
                            "Was it — was he in a hurry?\"\n\n"
                            "\"No,\" you tell him, because it is true. It was the "
                            "neatest page in the book.\n\n"
                            "He nods for a while without saying anything."
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Refender",
                        "text": (
                            "\"Cascade have replied again,\" Refender says, putting a "
                            "printout on the table. \"Twice in one day, which for them is "
                            "a sprint.\"\n\n"
                            "\"The northern line is dark. Every relay on it is being "
                            "physically inspected — not audited, *inspected*, by people "
                            "standing next to it. Dolphe has moved four teams onto it and "
                            "he has done it in under a week.\"\n\n"
                            "She lets that sit for exactly as long as it deserves.\n\n"
                            "\"I would like it minuted that when we finally handed them "
                            "something they could act on, they acted on it in forty "
                            "minutes. Our disagreement with Cascade was never that they do "
                            "not care.\"\n\n"
                            "\"It is that Rex told Josh, and Josh told them, and it took "
                            "two years and a dead man's notebook to get from one to the "
                            "other.\""
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Josh",
                        "text": (
                            "\"Right,\" Josh says. \"So here's the part you're not going "
                            "to like.\"\n\n"
                            "\"I'm going north. On the 14th. Alone.\"\n\n"
                            "He says it flatly and quickly, the way you get a thing said "
                            "before anyone can start negotiating.\n\n"
                            "\"It's not heroics and it's not a death wish, whatever "
                            "Refender's face is currently doing. He built a machine to "
                            "mark a date. He wants somebody there on it. If somebody's "
                            "going to be there, it's going to be the person he's actually "
                            "been talking to for two years, and that's me.\"\n\n"
                            "\"You've got a squad and a base and a job. Do that. Stay out "
                            "of this one.\""
                        ),
                    },
                    {
                        "kind": "choice",
                        "prompt": (
                            "Four people are waiting to see what you say. Blueflame has "
                            "stopped eating, which you have learned to read."
                        ),
                        "options": [
                            {
                                "id": "c1_agree_stay",
                                "label": "\"Alright. It's yours.\"",
                                "text": (
                                    "Josh blinks. He had a whole argument ready and you "
                                    "have taken it off him.\n\n"
                                    "\"...Right,\" he says. \"Good. Thank you.\"\n\n"
                                    "At the door he stops, without turning round.\n\n"
                                    "\"For what it's worth. Nine days ago I'd have said "
                                    "you were a Cascade asset with an interesting medical "
                                    "history.\" A pause. \"I'd have been wrong, and I "
                                    "wouldn't have checked. So — that's mine to fix, and "
                                    "I'm fixing it.\""
                                ),
                                "sets": {"c1_let_josh_go": True},
                            },
                            {
                                "id": "c1_refuse",
                                "label": "\"No. He's expecting you alone. That's the whole point.\"",
                                "text": (
                                    "\"*Thank* you,\" says Refender, to the ceiling.\n\n"
                                    "Josh is quiet for a long moment.\n\n"
                                    "\"...Yeah,\" he says eventually. \"Yeah, that's the "
                                    "bit I've been walking around.\"\n\n"
                                    "\"I'm still going. But I'll tell you when, and I'll "
                                    "tell you where, and if I stop answering the radio you "
                                    "can come and be insufferable about having been "
                                    "right.\"\n\n"
                                    "It is, by his standards, an enormous concession, and "
                                    "everyone in the room registers it as one."
                                ),
                                "sets": {"c1_pushed_back_on_josh": True},
                            },
                            {
                                "id": "c1_ask_rex",
                                "label": "\"What was he like? Rex.\"",
                                "text": (
                                    "It is the first time anyone has asked him that "
                                    "instead of asking about the accident.\n\n"
                                    "\"Annoying,\" Josh says. \"Genuinely. He'd take a "
                                    "thing apart to see how it worked and then leave it "
                                    "apart for a *fortnight* while he thought about it. "
                                    "The kettle. He did it to the kettle.\"\n\n"
                                    "Something in his face gives way about a millimetre.\n\n"
                                    "\"He was right about the mast and I told him he "
                                    "needed a holiday. That's — yeah. That's the one I've "
                                    "got.\"\n\n"
                                    "He picks his coat up off the back of a chair he never "
                                    "sat in."
                                ),
                                "sets": {"c1_asked_about_rex": True},
                            },
                        ],
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Dolphin",
                        "text": (
                            "Dolphin catches you on the way out, in the doorway, in the "
                            "coat.\n\n"
                            "\"That thing stopped when it got level with the van,\" he "
                            "says. \"I keep going over it. It stopped, and it *looked*, "
                            "and then it carried on to the building.\"\n\n"
                            "\"I've got two years of memories and a brother who flies for "
                            "the H-Nation and a face people mistake for someone "
                            "important's.\" He tries the light version of it and it does "
                            "not come out light. \"One of those is a reason for a machine "
                            "to look at me and I don't know which and I would very much "
                            "like it to be the face.\"\n\n"
                            "He straightens the coat.\n\n"
                            "\"Anyway. If you're going anywhere and you need someone who "
                            "gets nodded at — I'm about.\""
                        ),
                    },
                    {
                        "kind": "reward",
                        "text": (
                            "The depot is quiet by the time you leave. Refender has the "
                            "tape in a case by the door, labelled twice.\n\n"
                            "Jofrog has written a fifth name on the roster board in the "
                            "hallway, in very careful handwriting, under the four that "
                            "were already there.\n\n"
                            "Nobody asked him to. Nobody says anything about it either, "
                            "which — from this lot — is the loudest possible way of "
                            "agreeing."
                        ),
                        "grant": {"xp": 320, "gold": 4000, "item": "epic", "evolution_fragments": 160,
                                  "shards": 400, "cores": 400, "lootbox": ("epic", 3)},
                    },
                ],
            },

            # ------------------------------------------------------------------
            # SIDE MISSION -- optional, and marked so.
            #
            # `optional: True` is load-bearing, not documentation.
            # check_story reads a chapter's LAST fight as its climax, and
            # side missions are appended after the finale, so without the
            # flag every chapter's climax would become whatever side
            # content happened to be added last. Optional missions are
            # measured separately instead.
            # ------------------------------------------------------------------
            {
                "id": "s1_higher_than_the_argument",
                "name": "Higher Than The Argument",
                "optional": True,
                "summary": "Dolphin is on the roof again. He has been on the roof a lot.",
                "beats": [
                    {
                        "kind": "dialogue",
                        "speaker": "Dolphin",
                        "text": ("He hears the door and does not turn round.\n\n"
                                 "\"Don't tell Josh I'm up here. He'll think I'm "
                                 "sulking.\" A pause. \"I'm not sulking. I'm doing "
                                 "the thing where I try to remember something and "
                                 "it slides off, and I'd rather do that where "
                                 "nobody's watching me do it.\""),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Dolphin",
                        "text": ("The roof is flat and gritty and looks out over "
                                 "the car park, the road, and about forty miles of "
                                 "nothing after that.\n\n"
                                 "\"I know four things,\" he says. \"I know my "
                                 "brother's name. I know I've got a scar on my arm "
                                 "I didn't get in a fight. I know the word "
                                 "*Ocellios* makes my jaw go tight before I've "
                                 "finished thinking it. And I know I'm not Dolphe, "
                                 "which everybody thinks is the joke, and it's the "
                                 "only one of the four I'm certain about.\""),
                    },
                    {
                        "kind": "choice",
                        "prompt": "He is waiting for you to say something.",
                        "options": [
                            {
                                "id": "ask_scar",
                                "label": "Ask about the scar.",
                                "text": ("He pushes his sleeve up without being "
                                         "asked twice. It is a clean line, "
                                         "surgical, four years healed.\n\n"
                                         "\"Dolpo says I've always had it. Dolpo "
                                         "is a bad liar and a good brother, and "
                                         "he's been doing both at me since I "
                                         "turned up.\""),
                                "sets": {"s1_saw_the_scar": True},
                            },
                            {
                                "id": "ask_why_dolphe",
                                "label": "Ask why he wanted to be Dolphe.",
                                "text": ("\"Because he's *good at it*,\" Dolphin "
                                         "says, immediately, like he's had the "
                                         "answer ready for a while. \"People look "
                                         "at him and they know what he's for.\"\n\n"
                                         "Then, quieter: \"And because when I "
                                         "woke up, his was the first name I could "
                                         "remember, and I didn't have one of my "
                                         "own to put next to it.\""),
                                "sets": {"s1_asked_why_dolphe": True},
                            },
                            {
                                "id": "just_sit",
                                "label": "Sit down next to him and say nothing.",
                                "text": ("You sit. The second chair has the grit "
                                         "worn off it, which means somebody does "
                                         "this regularly.\n\n"
                                         "After a while he says, \"Thanks,\" and "
                                         "does not explain what for."),
                                "sets": {"s1_sat_with_him": True},
                            },
                        ],
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Dolphin",
                        "text": ("\"Here's the bit I haven't said downstairs,\" he "
                                 "says. \"When Refender read out that list of "
                                 "nineteen teams — I knew the numbers were wrong "
                                 "before he finished. Not guessed. *Knew.* Like "
                                 "somebody had read them to me before.\"\n\n"
                                 "\"I don't know what that means. I'd like it to "
                                 "mean I'm clever. I don't think it does.\""),
                    },
                    {
                        "kind": "reward",
                        "text": ("He stays up there when you go. Later, somebody "
                                 "carries a cooler up four flights and leaves it "
                                 "by the parapet without mentioning it to anyone, "
                                 "and it is restocked every week after that."),
                        "grant": {"xp": 240, "gold": 3400, "evolution_fragments": 200,
                                  "cores": 260, "item": "epic"},
                    },
                ],
            },
        ],
    },

    # ======================================================================
    # CHAPTER TWO — THE FORTY MILES
    # ======================================================================
    #
    # WHAT THIS CHAPTER IS ABOUT: the answer to the nineteen teams, and
    # the discovery that the answer is worse for being reasonable.
    #
    # ----------------------------------------------------------------------
    # ROHAN IS PRESENT AND IS NOT FOUGHT
    # ----------------------------------------------------------------------
    # Measured, not chosen. `Rohan` as an enemy template costs 100% of a
    # level-appropriate party at level 18, 20, 22 AND 24 -- he is the
    # Abyssnia endgame boss and no amount of re-levelling makes him a
    # chapter-two fight. That is the same trap the prologue hit with
    # Rohan's Herald, and the same fix applies: pick a different enemy.
    #
    # Which turns out to be the better story anyway. You fight what he
    # brought; he stands there and lets you; and the reason you cannot
    # reach him is the point of the scene rather than an excuse for it.
    # The chapter ends with him alive, unhurried, and having answered
    # every question he was asked.
    #
    # ----------------------------------------------------------------------
    # THE H-NATION ARE NOT VILLAINS
    # ----------------------------------------------------------------------
    # They have a border post fourteen months old on a road to nowhere,
    # and a fuel log proving nobody has ever driven north from it. They
    # are not guarding the forty miles from you. They are guarding
    # themselves from the forty miles, and they lost people finding out
    # they needed to.
    #
    # That is what Dolpo is for, and why the brothers' scene has no
    # fight in it: the chapter's midpoint is two people failing to have
    # a conversation while a war goes on around them.
    # ======================================================================
    {
        "id": "chapter2",
        "name": "Chapter Two: The Forty Miles",
        "blurb": "Nineteen teams went north. The equipment is all still running.",
        "unlocks_region": None,
        "missions": [
            {
                "id": "c2m1_the_fourteenth",
                "name": "The Fourteenth",
                "summary": "He left before it got light, and he left the radio.",
                "beats": [
                    {
                        "kind": "dialogue",
                        "speaker": "Refender",
                        "text": (
                            "Refender is standing in the middle of the floor at six in "
                            "the morning holding the good radio, which is the wrong "
                            "object for her to be holding, because Josh took the good "
                            "radio.\n\n"
                            "\"He left it,\" she says. \"On the table. Charged.\"\n\n"
                            "\"He said he would tell us when and where. He has told us "
                            "neither, and he has removed the one item by which we could "
                            "have asked.\"\n\n"
                            "She sets it down very precisely, which is how she puts "
                            "things down when she would rather throw them."
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Jofrog",
                        "text": (
                            "Jofrog has the note. He has read it several times and is "
                            "holding it as though it might be needed as evidence.\n\n"
                            "\"It's four lines,\" he says. \"I'll do them all.\"\n\n"
                            "*Gone north. Don't follow — I mean it, and I know that's not "
                            "worth much from me.*\n\n"
                            "*Refender: the tape goes to Cascade whatever happens. All of "
                            "it, not the useful bits.*\n\n"
                            "*Jofrog: you've been putting a fifth name on that board for "
                            "a week. Put mine under it when I'm back, not before.*\n\n"
                            "*Blueflame: don't.*\n\n"
                            "Jofrog looks up. \"That last one's the whole line. I checked "
                            "twice.\""
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Blueflame",
                        "text": (
                            "\"'Don't,'\" Blueflame repeats. \"Rude. Accurate, but "
                            "rude.\"\n\n"
                            "He is already dressed for outside, which he was not five "
                            "minutes ago.\n\n"
                            "\"For the record — and I'd like this minuted too, Refender, "
                            "since we're doing minutes — I have never once talked anyone "
                            "out of anything.\"\n\n"
                            "\"He's had two years of people managing him. What he hasn't "
                            "had is anyone turn up.\""
                        ),
                    },
                    {
                        "kind": "choice",
                        "prompt": (
                            "Three of them are looking at you. It is your call, which "
                            "everyone in the room has silently decided without discussing "
                            "it."
                        ),
                        "options": [
                            {
                                "id": "c2_go_now",
                                "label": "\"We go now. He's got four hours on us at most.\"",
                                "text": (
                                    "\"Three and a half,\" says Refender, who has "
                                    "obviously been calculating it since she found the "
                                    "radio and waiting for somebody to ask.\n\n"
                                    "\"The van is fuelled. I fuelled it at four this "
                                    "morning, when I worked out what he had done, and "
                                    "before I decided whether I approved of it.\""
                                ),
                                "sets": {"c2_went_immediately": True},
                            },
                            {
                                "id": "c2_tell_cascade",
                                "label": "\"Send the tape to Cascade first. All of it, like he said.\"",
                                "text": (
                                    "\"Already gone,\" Refender says. \"Six o'clock. "
                                    "Every reel, uncut, with the routing table and my "
                                    "working.\"\n\n"
                                    "\"He asked for the one thing he could be certain I "
                                    "would do whether he came back or not. That is either "
                                    "very considerate or very final and I have not decided "
                                    "which.\"\n\n"
                                    "A pause.\n\n\"Now the van.\""
                                ),
                                "sets": {"c2_sent_tape_first": True},
                            },
                            {
                                "id": "c2_respect_it",
                                "label": "\"He asked us not to. That should count for something.\"",
                                "text": (
                                    "Nobody answers straight away, because it is a fair "
                                    "point and everybody knows it.\n\n"
                                    "\"It counts,\" Refender says eventually. \"It counts, "
                                    "and I am overruling it, and I would like you to hold "
                                    "me to that later when we are all calmer.\"\n\n"
                                    "\"Rex asked him for one thing as well. He asked to be "
                                    "believed, and Josh has spent two years unable to "
                                    "forgive himself for the four hours he took to do "
                                    "it.\"\n\n"
                                    "\"I am not giving him four hours.\""
                                ),
                                "sets": {"c2_argued_to_respect_it": True},
                            },
                        ],
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Dolphin",
                        "text": (
                            "Dolphin is in the van when you get to it. He has been in it "
                            "for some time. He has brought a flask.\n\n"
                            "\"Right, so, before anyone says it,\" he says. \"I know. I "
                            "know I'm not — I'm aware of what I am on a trip like this. "
                            "I'm a coat.\"\n\n"
                            "He turns the flask over a couple of times.\n\n"
                            "\"But that thing stopped when it got level with me. And "
                            "everything north of here belongs to a man who apparently "
                            "*knows things about me*, and I have got two years of my own "
                            "life and a brother I don't speak to, and I am extremely "
                            "tired of finding out about myself secondhand.\"\n\n"
                            "\"So I'd like to come. I'll stay in the van. I'm very good "
                            "at staying in the van.\""
                        ),
                    },
                    {
                        "kind": "reward",
                        "text": (
                            "Refender hands out the northern kit without ceremony: cold "
                            "gear, spare cells, and a printed copy of Rex's notebook page "
                            "for each of you, which nobody asked her for.\n\n"
                            "\"Read it in the van,\" she says. \"He wrote down what he was "
                            "going to do and then he went and did it, and everyone who "
                            "read it afterwards understood it perfectly.\"\n\n"
                            "\"I would like us to be legible in the same way, and rather "
                            "earlier.\""
                        ),
                        "grant": {"xp": 120, "gold": 2600, "item": "epic", "evolution_fragments": 120,
                                  "cores": 200, "lootbox": ("epic", 2)},
                    },
                ],
            },

            {
                "id": "c2m2_the_border",
                "name": "The Border Post",
                "summary": "Somebody has put a fence across a road that goes nowhere.",
                "beats": [
                    {
                        "kind": "dialogue",
                        "speaker": "Refender",
                        "text": (
                            "Thirty-one miles up the access road there is a gate.\n\n"
                            "It is a proper one: poured footings, a hut with a stove "
                            "chimney, a generator on a concrete pad. Somebody built this "
                            "to last and then staffed it, on a road that leads to forty "
                            "miles of nothing and then stops.\n\n"
                            "\"H-Nation,\" Refender says. \"Which is interesting, because "
                            "this is nine hundred kilometres from anything the H-Nation "
                            "has ever claimed.\"\n\n"
                            "She reads the notice wired to the gate twice.\n\n"
                            "\"'Road closed. **Not a border.** Do not report this post.' "
                            "That third line was added later, by somebody senior enough to "
                            "add lines to a notice.\""
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Blueflame",
                        "text": (
                            "\"Van tracks,\" Blueflame says, from a crouch about ten "
                            "metres up the verge. He sounds delighted, which he always "
                            "does, and this time it does not fit.\n\n"
                            "\"Ours. Well — Josh's. Same tread, four hours cold, and they "
                            "go *round* the post through the ditch and back onto the road "
                            "past it.\"\n\n"
                            "He straightens up.\n\n"
                            "\"He didn't stop and argue with these people. He knew the "
                            "post was here and he knew to go round it, which means he's "
                            "been up this road before and not told anyone.\""
                        ),
                    },
                    {
                        "kind": "choice",
                        "prompt": (
                            "There are four troopers on the gate and they have seen you. "
                            "The ditch is still there."
                        ),
                        "options": [
                            {
                                "id": "c2_talk_first",
                                "label": "\"Walk up. Hands visible. Let's find out who they are.\"",
                                "text": (
                                    "They do not raise anything as you approach, which is "
                                    "the first surprise.\n\n"
                                    "The second is what the sergeant says, before you have "
                                    "opened your mouth:\n\n"
                                    "\"Are you going north or are you coming back from "
                                    "it?\"\n\n"
                                    "It is not a challenge. It is the tone of a man who "
                                    "asks it a lot and has stopped liking either answer."
                                ),
                                "sets": {"c2_talked_to_the_post": True},
                            },
                            {
                                "id": "c2_take_the_ditch",
                                "label": "\"Take the ditch. Same as Josh did.\"",
                                "text": (
                                    "The van gets about sixty metres before the ground "
                                    "gives and a floodlight finds you, and by then it is a "
                                    "conversation anyway — just a worse one, conducted "
                                    "loudly, at an angle.\n\n"
                                    "\"YOU ARE THE THIRD SET THIS MONTH,\" somebody "
                                    "shouts, with what is unmistakably exhaustion rather "
                                    "than anger."
                                ),
                                "sets": {"c2_took_the_ditch": True},
                            },
                            {
                                "id": "c2_show_the_page",
                                "label": "*Hold up Rex's notebook page where they can see it.*",
                                "text": (
                                    "The nearest trooper looks at it for slightly too "
                                    "long, then calls something back to the hut in a "
                                    "language you do not have.\n\n"
                                    "Whatever it was, four people stop what they are doing "
                                    "at once.\n\n"
                                    "\"Where did you get a page with a date on it,\" the "
                                    "sergeant says, and it is not a question about "
                                    "paper."
                                ),
                                "sets": {"c2_showed_the_page": True},
                            },
                        ],
                    },
                    {
                        # 14% -- the chapter's floor. The H-Nation are not
                        # the enemy and this fight is not meant to feel
                        # like a victory; it is a misunderstanding that
                        # gets as far as weapons because both sides are
                        # frightened of the same thing.
                        "kind": "battle",
                        "enemies": ["H-Nation Vanguard", "H-Nation Border Trooper"],
                        "level": 19,
                        "intro": (
                            "It goes wrong in the ordinary way these things go wrong: "
                            "somebody moves toward a vehicle, somebody else reads it as "
                            "reaching for something, and after that nobody is deciding "
                            "anything.\n\n"
                            "\"NOT AT THE VAN,\" Refender is shouting. \"THERE IS A "
                            "CIVILIAN IN THE—\"\n\n"
                            "The Vanguard puts itself between the hut and all of you, "
                            "which even at the time reads less like an attack and more "
                            "like somebody standing in a doorway."
                        ),
                        "on_win": (
                            "It ends the way it started: quickly, and with everybody "
                            "immediately embarrassed.\n\n"
                            "The Vanguard goes down on one knee and stays there, upright, "
                            "not pursuing. Nobody on the gate advances. Somebody in the "
                            "hut is already shouting for a medic in two languages.\n\n"
                            "\"They're not chasing,\" Blueflame says, and for once there "
                            "is nothing cheerful in it. \"We just had a fight with people "
                            "who don't want the road either.\""
                        ),
                        "on_lose": (
                            "You come to sitting against the van with a field dressing on "
                            "and an H-Nation trooper crouched in front of you holding up "
                            "two fingers and asking you, in careful, heavily-accented "
                            "words, how many you can see.\n\n"
                            "Nobody has taken anything. Nobody has restrained anyone. "
                            "Somebody has put a blanket over Dolphin."
                        ),
                    },
                    {
                        "kind": "reward",
                        "text": (
                            "The sergeant calls it off himself, walks out past his own "
                            "gate unarmed, and stands in front of Refender with the air of "
                            "a man completing a form he has completed many times.\n\n"
                            "\"You are the third this month,\" he says. \"The other two "
                            "went north. Do you want to know how many came back?\"\n\n"
                            "He does not wait, because they all know the number.\n\n"
                            "\"Come inside. The officer will want to see you, and I would "
                            "like to stop having this conversation on a road.\""
                        ),
                        "grant": {"xp": 190, "gold": 2800, "item": "epic", "evolution_fragments": 130,
                                  "shards": 200},
                    },
                ],
            },

            {
                # NO FIGHT. The chapter's midpoint is two brothers not
                # managing to talk to each other, and putting a battle in
                # it would let everyone off.
                "id": "c2m3_dolpo",
                "name": "Dolpo",
                "summary": "The officer in the hut has been expecting somebody for fourteen months. Not you.",
                "beats": [
                    {
                        "kind": "dialogue",
                        "speaker": "Dolpo",
                        "text": (
                            "The officer does not stand up when you come in, and does not "
                            "look at any of you.\n\n"
                            "He is looking past your shoulder at the van, and at the "
                            "figure that has just got out of it and is standing in the "
                            "doorway in a coat that is very nearly somebody else's.\n\n"
                            "\"...You are joking,\" he says.\n\n"
                            "\"Hello, Dolpo,\" says Dolphin.\n\n"
                            "\"You are **joking**.\""
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Dolpo",
                        "text": (
                            "It is not a reunion. It is two people who have practised "
                            "this and find that neither prepared version works.\n\n"
                            "\"I put you south,\" Dolpo says. \"I put you nine hundred "
                            "kilometres south and I paid a man to keep you in work and "
                            "you have driven *here*. To the one place—\"\n\n"
                            "He stops himself, visibly, and starts again lower.\n\n"
                            "\"Fourteen months I have sat on this gate. Do you know what "
                            "the job is? The job is: nobody goes north. That is the whole "
                            "job. I requested it. I requested the worst posting in the "
                            "service and I have held it for fourteen months so that the "
                            "road would have somebody on it who would not be curious.\""
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Refender",
                        "text": (
                            "\"Nineteen Xender survey teams,\" Refender says, into the "
                            "gap. \"Fourteen months. Your post is fourteen months old. "
                            "Those are the same fourteen months.\"\n\n"
                            "Dolpo looks at her properly for the first time.\n\n"
                            "\"Twenty-two,\" he says. \"Nineteen of theirs. Three of "
                            "ours.\"\n\n"
                            "\"We sent three teams north before command understood what "
                            "was happening, and then we stopped sending teams and started "
                            "sending *a gate*. We are not guarding this road from you. We "
                            "are guarding it from what is at the end of it, and we are "
                            "doing it by making sure nobody has a reason to look.\"\n\n"
                            "\"Your friend went past us four hours ago. We let him. That "
                            "is also the job now, and I like it less every time.\""
                        ),
                    },
                    {
                        "kind": "choice",
                        "prompt": (
                            "Dolphin has not moved from the doorway. Dolpo has not looked "
                            "at him since he started talking."
                        ),
                        "options": [
                            {
                                "id": "c2_ask_about_dolphin",
                                "label": "\"He doesn't remember anything before two years ago. Do you know why?\"",
                                "text": (
                                    "The room goes very quiet.\n\n"
                                    "\"Yes,\" Dolpo says.\n\n"
                                    "Then, after a long moment, and to his brother rather "
                                    "than to you:\n\n"
                                    "\"I found you on this road. Two years ago, walking "
                                    "south, eleven kilometres from the end of it, with no "
                                    "kit and no vehicle and no idea what your own name "
                                    "was.\"\n\n"
                                    "\"You are not my brother. I have never had a brother. "
                                    "I told you that you were because you were nineteen "
                                    "years old and terrified and it was the fastest way to "
                                    "make you stop asking, and then it was a year later "
                                    "and there was no version of telling you that was not "
                                    "cruel.\"\n\n"
                                    "Dolphin says nothing at all."
                                ),
                                "sets": {"c2_learned_dolphin_origin": True},
                            },
                            {
                                "id": "c2_ask_what_is_north",
                                "label": "\"What is at the end of the road?\"",
                                "text": (
                                    "\"A man, and a cut in the rock, and machinery,\" "
                                    "Dolpo says. \"That is all any of my three teams got "
                                    "back, and only one of them got back at all.\"\n\n"
                                    "\"He does not chase. He does not raid. He has never "
                                    "once come south of this post, and I have stopped "
                                    "believing that is because he cannot.\"\n\n"
                                    "\"He takes what walks in. Then, mostly, he sends it "
                                    "out again — which is the part command could not "
                                    "process, and the part that made me request this "
                                    "gate.\""
                                ),
                                "sets": {"c2_asked_what_is_north": True},
                            },
                            {
                                "id": "c2_ask_for_help",
                                "label": "\"Come with us. You've had fourteen months of watching.\"",
                                "text": (
                                    "\"No,\" Dolpo says, immediately, and then sits with "
                                    "it, and it clearly costs him.\n\n"
                                    "\"If I take this gate off the road, the road is open. "
                                    "I have four people and a fence and it is the only "
                                    "thing standing between forty miles of that and "
                                    "everybody who has not yet thought to be curious.\"\n\n"
                                    "\"I will hold the gate. You will go north. That is "
                                    "the arrangement whether either of us likes it, and "
                                    "for what it is worth I have wanted somebody to go "
                                    "north for fourteen months.\""
                                ),
                                "sets": {"c2_asked_dolpo_along": True},
                            },
                        ],
                    },
                    {
                        # The version where you asked, and he heard the
                        # answer. Deliberately NOT more dramatic than the
                        # default -- just smaller, which is worse.
                        "requires": ["c2_learned_dolphin_origin"],
                        "kind": "dialogue",
                        "speaker": "Dolphin",
                        "text": (
                            "Dolphin comes out to the van a while later and gets in "
                            "without saying anything.\n\n"
                            "About a mile up the road:\n\n"
                            "\"Nineteen,\" he says. \"He said I was nineteen. That's "
                            "the bit I keep getting stuck on. Not the — not the rest of "
                            "it. Just that somebody knew how old I was and I "
                            "didn't.\"\n\n"
                            "He turns the flask over a few times.\n\n"
                            "\"I'm keeping the coat, by the way. Before anyone starts. I "
                            "know exactly what it is and I picked it, which is one more "
                            "thing than I had this morning.\"\n\n"
                            "After a moment Jofrog reaches back and pats him on the "
                            "shoulder twice, in the manner of a man operating machinery "
                            "he has not been trained on."
                        ),
                    },
                    {
                        "unless": ["c2_learned_dolphin_origin"],
                        "kind": "dialogue",
                        "speaker": "Dolphin",
                        "text": (
                            "Dolphin comes out to the van a while later and gets in "
                            "without saying anything, which from him is unprecedented.\n\n"
                            "Then, about a mile up the road:\n\n"
                            "\"I'm keeping the coat.\"\n\n"
                            "Nobody says anything.\n\n"
                            "\"I know what it is. I know it's a stupid coat and I know I "
                            "do a stupid voice and I know exactly why I started.\" He is "
                            "looking out of the window. \"But I picked it. Whoever I was "
                            "before, he didn't pick anything, and I've got precisely one "
                            "thing that's mine on purpose and it's a coat.\"\n\n"
                            "After a moment Jofrog reaches back and pats him on the "
                            "shoulder twice, in the manner of a man operating machinery "
                            "he has not been trained on."
                        ),
                    },
                    {
                        "kind": "reward",
                        "text": (
                            "Dolpo walks out to the gate to open it himself, which the "
                            "sergeant clearly considers beneath him and does not say so.\n\n"
                            "He hands Refender a folder: three teams, their routes, and "
                            "the debrief of the one man who came back, which runs to a "
                            "page and a half and stops mid-sentence.\n\n"
                            "\"Fourteen months I have not given this to anybody,\" he "
                            "says. \"Bring it back or do not, but do not let it end up in "
                            "an archive.\""
                        ),
                        "grant": {"xp": 260, "gold": 3000, "item": "epic", "evolution_fragments": 140,
                                  "cores": 250, "lootbox": ("epic", 2)},
                    },
                ],
            },

            {
                "id": "c2m4_survey_point_nine",
                "name": "Survey Point 9",
                "summary": "Nineteen camps, all still standing, all zipped shut from the outside.",
                "beats": [
                    {
                        "kind": "dialogue",
                        "speaker": "Refender",
                        "text": (
                            "The site is a shallow bowl of ground with a bore head in the "
                            "middle of it and nineteen camps pitched in a rough ring "
                            "around the edge.\n\n"
                            "Everything is standing. Everything is powered. The comms mast "
                            "is transmitting an all-clear from Survey Team 4, on a loop, "
                            "and has been for fourteen months.\n\n"
                            "\"Team 4 arrived eleven months ago,\" Refender says. \"So "
                            "that loop was recorded before they got here, using their "
                            "call sign, by somebody who knew they were coming.\"\n\n"
                            "She looks at the ring of tents.\n\n"
                            "\"Every one of those is zipped from the outside. You cannot "
                            "do that to your own tent.\""
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Blueflame",
                        "text": (
                            "\"Right,\" Blueflame says. \"I'm going to say the thing "
                            "nobody's saying, because somebody has to and it may as well "
                            "be the one who enjoys it.\"\n\n"
                            "\"There's no bodies. There's no blood, there's no burning, "
                            "there's no — anything. Nineteen teams of eight, and the worst "
                            "thing that has happened at this site is that the washing up "
                            "got done.\"\n\n"
                            "He toes a guy line, and it is taut, and properly pegged.\n\n"
                            "\"Somebody tidied nineteen camps. That's not a massacre. I "
                            "don't know what it is and I would genuinely rather it were a "
                            "massacre.\""
                        ),
                    },
                    {
                        "kind": "choice",
                        "prompt": (
                            "Josh's van is parked at the north edge of the site, empty, "
                            "with the keys in it."
                        ),
                        "options": [
                            {
                                "id": "c2_check_the_van",
                                "label": "*Check the van first.*",
                                "text": (
                                    "Cold. Four hours at least. His kit is gone and the "
                                    "printed page from Rex's notebook is folded on the "
                                    "dash, weighted down with the housing plate off the "
                                    "Herald.\n\n"
                                    "He left them where somebody following would look. He "
                                    "expected to be followed and he came anyway, which is "
                                    "either an apology or a message and is probably "
                                    "both."
                                ),
                                "sets": {"c2_checked_joshs_van": True},
                            },
                            {
                                "id": "c2_check_the_tents",
                                "label": "*Open one of the tents.*",
                                "text": (
                                    "Bedroll made. Kit stowed. A paperback face-down on "
                                    "the pillow, open at page one hundred and nine.\n\n"
                                    "There is a mug on the groundsheet with a ring in the "
                                    "bottom of it, washed on the outside, and you have "
                                    "seen this exact thing before in a workshop nine "
                                    "hundred kilometres south, and it means the same thing "
                                    "here that it meant there.\n\n"
                                    "Somebody has been *looking after* this."
                                ),
                                "sets": {"c2_opened_a_tent": True},
                            },
                            {
                                "id": "c2_check_the_mast",
                                "label": "*Go to the mast and stop the loop.*",
                                "text": (
                                    "Refender gets the panel off and then does not touch "
                                    "anything for a long moment.\n\n"
                                    "\"It is not a recording,\" she says. \"It is a *live "
                                    "feed* from a set somewhere else, relayed through "
                                    "here, and the all-clear is being spoken.\"\n\n"
                                    "\"Somebody has been reading a routine all-clear into "
                                    "a microphone, in Team 4's call sign, twice a day, for "
                                    "fourteen months.\"\n\n"
                                    "She puts the panel back on very carefully.\n\n"
                                    "\"I would like to not have stopped it.\""
                                ),
                                "sets": {"c2_touched_the_mast": True},
                            },
                        ],
                    },
                    {
                        # 21% -- second rung. The Assessor is a watcher
                        # rather than a guard, which is the note the whole
                        # site is playing.
                        "kind": "battle",
                        "enemies": ["Rohan's Assessor"],
                        "level": 22,
                        "intro": (
                            "It has been standing between two of the tents the entire "
                            "time you have been on the site.\n\n"
                            "You are fairly sure of this. Nobody can say when they first "
                            "saw it, and everybody assumed somebody else had.\n\n"
                            "It does not approach. It waits until all four of you are "
                            "looking at it, the way a person waits to be sure they have "
                            "the room, and then it starts across the bowl."
                        ),
                        "on_win": (
                            "It goes down between two tents and does not damage either of "
                            "them, which by now you have stopped finding surprising and "
                            "started finding much worse.\n\n"
                            "Refender pulls the core. She has stopped announcing what she "
                            "expects to find.\n\n"
                            "\"Camera log,\" she says anyway. \"And an *inventory*. It has "
                            "been counting the tents. Twice a day, for fourteen "
                            "months.\"\n\n"
                            "\"Nineteen. Every time. It is a stock check.\""
                        ),
                        "on_lose": (
                            "You wake up where you fell, and nothing is missing, and "
                            "somebody has put your pack where you can reach it.\n\n"
                            "Jofrog will not talk about the hour you were out. Whatever he "
                            "saw, he has decided you do not need it."
                        ),
                    },
                    {
                        "kind": "reward",
                        "text": (
                            "Team 11's supply pallet has been opened at some point and "
                            "repacked by somebody who was not the person who packed it.\n\n"
                            "Whoever repacked it took the food and left the tools, and "
                            "squared the corners.\n\n"
                            "Blueflame looks at it for a while and then says, with no "
                            "cheer whatsoever: \"He's been *shopping*.\""
                        ),
                        "grant": {"xp": 340, "gold": 3400, "item": "epic", "evolution_fragments": 150,
                                  "shards": 250, "cores": 250},
                    },
                ],
            },

            {
                "id": "c2m5_nineteen",
                "name": "Nineteen",
                "summary": "The bore head, the crates, and the tally on the last one.",
                "beats": [
                    {
                        "kind": "dialogue",
                        "speaker": "Refender",
                        "text": (
                            "The bore head is not a bore head. It is the top of a cut: a "
                            "trench in the rock two metres across, machined smooth, going "
                            "down past where the light stops.\n\n"
                            "The tool marks run in one continuous direction from the lip "
                            "to as far as anybody can see.\n\n"
                            "\"One pass,\" Refender says. \"Same as the driller. He does "
                            "not do second passes. I have started to think that is not "
                            "capability, it is *manner*.\"\n\n"
                            "Stacked against the wall of the cut, out of the weather, in "
                            "numbered order: nineteen crates."
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Jofrog",
                        "text": (
                            "Jofrog opens crate 11 because it is nearest and because "
                            "somebody has to.\n\n"
                            "\"Instruments,\" he says. \"Logs. Somebody's glasses, in a "
                            "case. There's a — there's a birthday card in here.\"\n\n"
                            "He is being extremely careful with all of it.\n\n"
                            "\"It's all labelled. Team number, name, date. Every crate's "
                            "the same. Somebody packed up eight people's things "
                            "*properly*, and then carried the crate down here, and put it "
                            "in the right order.\"\n\n"
                            "He closes the lid and stands there with his hand on it."
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Refender",
                        "text": (
                            "There is a clipboard on the last crate. Refender reads it "
                            "twice before she reads it out.\n\n"
                            "\"Nineteen entries. Team number, date, one word.\"\n\n"
                            "\"Eighteen of them say **RETURNED**.\"\n\n"
                            "She turns the board round so you can see the last line, and "
                            "her hand is not quite steady, which you have never seen.\n\n"
                            "\"The nineteenth says **KEPT**. And the date on it is the "
                            "fourteenth.\"\n\n"
                            "\"Two years ago. The day Rex drove to the mast.\""
                        ),
                    },
                    {
                        "kind": "choice",
                        "prompt": (
                            "Eighteen teams went home and nobody has ever heard from them. "
                            "That needs saying out loud before anyone goes down the cut."
                        ),
                        "options": [
                            {
                                "id": "c2_returned_means_home",
                                "label": "\"Returned means he sent them home.\"",
                                "text": (
                                    "\"Then a hundred and forty-four people went home "
                                    "fourteen months ago and not one of them has filed a "
                                    "report, claimed a wage, or told anybody where they "
                                    "had been,\" Refender says.\n\n"
                                    "\"Which is possible. It requires every one of them to "
                                    "have decided the same thing.\"\n\n"
                                    "A long pause.\n\n"
                                    "\"I would like that to be what it means. I am writing "
                                    "down that I would like it, so that later I can check "
                                    "whether I believed it.\""
                                ),
                                "sets": {"c2_hoped_returned": True},
                            },
                            {
                                "id": "c2_returned_means_worse",
                                "label": "\"Returned means he was finished with them.\"",
                                "text": (
                                    "Nobody argues.\n\n"
                                    "\"That reads better against the evidence,\" Refender "
                                    "says quietly. \"A man who tidies nineteen camps and "
                                    "keeps a stock check is not a man who loses interest "
                                    "in people. He is a man who *concludes* about them.\"\n\n"
                                    "Blueflame, unusually, says nothing at all."
                                ),
                                "sets": {"c2_feared_returned": True},
                            },
                            {
                                "id": "c2_kept_is_the_word",
                                "label": "\"Forget the eighteen. One of them says KEPT.\"",
                                "text": (
                                    "\"Yes,\" Refender says. \"Yes, that is the word that "
                                    "matters and I have been avoiding it for four "
                                    "minutes.\"\n\n"
                                    "\"Eighteen teams were a process. One of them was a "
                                    "*decision*, and it was made on the day Rex went to "
                                    "the mast, and Rex was not on a survey team.\"\n\n"
                                    "She looks down the cut.\n\n"
                                    "\"Josh has been down there for five hours.\""
                                ),
                                "sets": {"c2_focused_on_kept": True},
                            },
                        ],
                    },
                    {
                        # 46% -- the step before the climax, and a real
                        # one: two elites at once, where the site's other
                        # fight was a single watcher.
                        "kind": "battle",
                        "enemies": ["Rohan's Assessor", "Rohan's Warden"],
                        "level": 21,
                        "intro": (
                            "Two of them come up out of the cut, unhurried, in the "
                            "formation you last saw on a hill at Ashfield.\n\n"
                            "They are not defending the crates. They walk past the "
                            "crates.\n\n"
                            "They are standing between you and the way down, which is a "
                            "thing you only notice once you have already decided to go "
                            "down it."
                        ),
                        "on_win": (
                            "The way down is clear, and neither of them was ever going to "
                            "stop being in it until somebody moved them.\n\n"
                            "Refender does not pull the cores. She has run out of interest "
                            "in what they were recording.\n\n"
                            "\"He is not keeping us out,\" she says. \"He has never once "
                            "kept anybody out. He is making us *decide* to come in, and I "
                            "find I resent that more than the fighting.\""
                        ),
                        "on_lose": (
                            "You come round at the lip of the cut with the crates still "
                            "stacked in order beside you and nothing taken.\n\n"
                            "Somewhere below, a long way down, something is running, and "
                            "it has been running the whole time."
                        ),
                    },
                    {
                        "kind": "reward",
                        "text": (
                            "Before you go down, Jofrog takes the birthday card out of "
                            "crate 11, writes the team number on the back of it in his "
                            "very careful handwriting, and puts it in his inside "
                            "pocket.\n\n"
                            "\"I'm not leaving all of it,\" he says, to nobody. \"I can "
                            "carry one.\""
                        ),
                        "grant": {"xp": 410, "gold": 4000, "item": "epic", "evolution_fragments": 170,
                                  "shards": 300, "cores": 300, "lootbox": ("epic", 3)},
                    },
                ],
            },

            {
                "id": "c2m6_mr_r",
                "name": "Mr. R",
                "summary": "There is a man at the bottom of it, and he has been expecting company for two years.",
                "beats": [
                    {
                        "kind": "dialogue",
                        "speaker": "Rohan",
                        "text": (
                            "The cut opens out at the bottom into a working floor: "
                            "lighting on stands, cable runs pinned to the rock, machinery "
                            "under covers.\n\n"
                            "It is a *tidy site*. Somebody sweeps down here.\n\n"
                            "Josh is sitting against the far wall with his hands loose in "
                            "his lap. He is not restrained. He is not hurt. He looks up "
                            "when you come in and the look on his face is the worst thing "
                            "in the room.\n\n"
                            "\"He's been answering my questions,\" Josh says. \"All of "
                            "them. For five hours. I asked him to stop.\""
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Rohan",
                        "text": (
                            "Rohan is dressed for an office that does not exist out here, "
                            "and he is holding a clipboard, and he does not put it "
                            "down.\n\n"
                            "\"You are the one from Ocellios,\" he says to you. \"Good. "
                            "You are the only entry on this site I have not been able to "
                            "close.\"\n\n"
                            "\"I will save us the part where you ask what happened to "
                            "nineteen survey teams, because your colleague has already "
                            "asked and the answer does not improve with repetition.\"\n\n"
                            "\"They came to look at my work. I let them. Then I took an "
                            "inventory of what each of them was, and eighteen times the "
                            "inventory came out the same way, and I returned them.\""
                        ),
                    },
                    {
                        "kind": "choice",
                        "prompt": (
                            "He is waiting. He has answered everything he has been asked "
                            "so far, promptly and completely, and that is beginning to "
                            "feel like the trap."
                        ),
                        "options": [
                            {
                                "id": "c2_ask_returned",
                                "label": "\"Returned where?\"",
                                "text": (
                                    "\"To circulation,\" he says, and makes a small mark "
                                    "on the clipboard.\n\n"
                                    "\"I am not a murderer, which everybody finds "
                                    "disappointing and then, shortly afterwards, worse. "
                                    "One hundred and forty-four people walked south from "
                                    "this site and are alive today.\"\n\n"
                                    "\"None of them recall being here. That is not "
                                    "cruelty, it is *hygiene* — a person who cannot report "
                                    "on a site does not need to be prevented from "
                                    "reporting on it.\"\n\n"
                                    "Beside you, very quietly, Dolphin says: \"...Eleven "
                                    "kilometres from the end of the road.\""
                                ),
                                "sets": {"c2_asked_returned_where": True},
                            },
                            {
                                "id": "c2_ask_kept",
                                "label": "\"One entry says KEPT. That was Rex.\"",
                                "text": (
                                    "For the first time, he stops writing.\n\n"
                                    "\"Yes,\" he says. \"Your friend's friend was the only "
                                    "person who arrived here having worked it out "
                                    "*beforehand*. He was not surveying. He came because he "
                                    "had followed a second and a half across nine "
                                    "hundred kilometres, alone, on his own time, and been "
                                    "told he needed a holiday.\"\n\n"
                                    "\"An inventory is a record of what a thing is. I could "
                                    "not return that to circulation without returning what "
                                    "he knew. So I kept it.\"\n\n"
                                    "Josh has not moved and is not breathing very "
                                    "regularly."
                                ),
                                "sets": {"c2_asked_about_kept": True},
                            },
                            {
                                "id": "c2_ask_why_watch_me",
                                "label": "\"Then why have you been watching me since Ocellios?\"",
                                "text": (
                                    "\"Because you are not on the inventory,\" Rohan says, "
                                    "with something that on a warmer man would be "
                                    "enthusiasm.\n\n"
                                    "\"Nine days before you walked out of that building "
                                    "there was nothing in it worth the electricity. I have "
                                    "a complete record of everything in this region that "
                                    "can be accounted for, and you are a line I cannot "
                                    "fill in.\"\n\n"
                                    "\"I have sent four machines to look at you and each "
                                    "of them came back with the same nothing. Do you "
                                    "understand how rare it is that I have to come and see "
                                    "for myself?\""
                                ),
                                "sets": {"c2_asked_why_watched": True},
                            },
                        ],
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Josh",
                        "text": (
                            "Josh gets up. It takes him a while, and nobody helps him, "
                            "because he would not have it.\n\n"
                            "\"Two years,\" he says. \"Two years of telling people there "
                            "was a man, and being handled, and filing reports up a line he "
                            "was standing on.\"\n\n"
                            "\"And I get down here and he's — \" his voice goes, and he "
                            "takes it back — \"he's *polite*. He's got a clipboard. He's "
                            "been answering me like I'm a supplier.\"\n\n"
                            "He looks at Rohan.\n\n"
                            "\"Say his name. You've said everything else. Say the name of "
                            "the one you kept.\"\n\n"
                            "Rohan checks the clipboard, which he does not need to do, and "
                            "which is the single cruellest thing he does all day.\n\n"
                            "\"Rex,\" he says."
                        ),
                    },
                    {
                        # THE CHAPTER CLIMAX -- 64%, against 46% for the
                        # rung below it, and the biggest number in the
                        # story so far.
                        #
                        # NOT ROHAN. He is measured at 100% of a
                        # level-appropriate party at 18, 20, 22 and 24 --
                        # the Abyssnia endgame template, unwinnable at
                        # every level, exactly like the Herald was for the
                        # prologue. So he stands there, and you fight what
                        # he brought, and the fact that you cannot reach
                        # him is the scene rather than an excuse.
                        "kind": "battle",
                        "enemies": ["Rohan's Negadom"],
                        "level": 24,
                        "intro": (
                            "Rohan puts the clipboard down on a crate, squares it to the "
                            "edge, and steps back out of the way.\n\n"
                            "\"I would rather you did not,\" he says, without any "
                            "particular urgency. \"You will not reach me, and I will have "
                            "to open a new line for each of you, and I have found the "
                            "paperwork on your friend genuinely tiring.\"\n\n"
                            "The covers come off the machinery at the back of the floor "
                            "by themselves.\n\n"
                            "It is not a guard. It is the thing that made the cut."
                        ),
                        "on_win": (
                            "It takes everything, and when it finally stops it stops "
                            "*folded* — settling down onto its own footprint, the way a "
                            "thing does when somebody switches it off rather than when "
                            "somebody kills it.\n\n"
                            "The floor is very quiet.\n\n"
                            "Rohan has not moved from where he stepped back to. He has "
                            "picked the clipboard up again.\n\n"
                            "\"Noted,\" he says, and writes something down, and you would "
                            "give a great deal to see what.\n\n"
                            "Then he walks to the lift at the back of the floor, and gets "
                            "into it, and goes down."
                        ),
                        "on_lose": (
                            "You come round on the working floor with the lights still on "
                            "and the machine standing over you, not finishing it.\n\n"
                            "Josh is sitting against the wall again. Somebody has put "
                            "everyone's packs in a neat row.\n\n"
                            "The clipboard is gone."
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Refender",
                        "text": (
                            "There is a lift shaft at the back of the floor and it goes "
                            "down, and the counter above it does not have numbers on it. "
                            "It has **letters**.\n\n"
                            "Refender stands in front of it for a long moment.\n\n"
                            "\"This site is not the end of the road,\" she says. \"This "
                            "site is the *reception*.\"\n\n"
                            "She turns round.\n\n"
                            "\"We are going home. All of us, today, with everything we "
                            "can carry and every word of this written down while it is "
                            "still accurate.\"\n\n"
                            "\"And then we are going to Dolphe, and we are going to tell "
                            "him that four people and a fence is not enough, and this "
                            "time we will have the crates.\""
                        ),
                    },
                    {
                        "kind": "reward",
                        "text": (
                            "They bring up what they can. Nineteen crates is more than a "
                            "van, so it takes three trips and most of a day, and Dolpo "
                            "sends two of his four people down to help without being "
                            "asked and without filing it anywhere.\n\n"
                            "Josh works the whole time and does not say anything to "
                            "anyone.\n\n"
                            "At the top, on the last trip, he stops by crate 19 — which is "
                            "lighter than the others, because one man's effects do not "
                            "fill a crate — and he stands there with his hand on the lid "
                            "the way Jofrog did, and then he picks it up himself and "
                            "carries it to the van."
                        ),
                        "grant": {"xp": 480, "gold": 6000, "item": "mythic", "evolution_fragments": 240,
                                  "shards": 500, "cores": 500, "lootbox": ("legendary", 2)},
                    },
                ],
            },

            # ------------------------------------------------------------------
            # SIDE MISSION -- see the note on s1 for why `optional` matters.
            # ------------------------------------------------------------------
            {
                "id": "s2_the_long_walk",
                "name": "The Long Walk",
                "optional": True,
                "summary": "One set of bootprints, going away from everything.",
                "beats": [
                    {
                        "kind": "dialogue",
                        "speaker": "Refender",
                        "text": ("The prints come up out of the cut and turn "
                                 "north-west, and Refender follows them for about "
                                 "two hundred metres before he stops and waits for "
                                 "you to catch up.\n\n"
                                 "\"Unhurried,\" he says. \"That's the part I keep "
                                 "getting stuck on. Whoever this was, they weren't "
                                 "running.\""),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Refender",
                        "text": ("The trail goes another kilometre before the wind "
                                 "takes it. At the end there is a spot where "
                                 "somebody sat down in the snow for a while, and a "
                                 "ration wrapper folded into a neat square and "
                                 "pushed into a crack in the rock so it would not "
                                 "blow away.\n\n"
                                 "Somebody who was walking out into forty miles of "
                                 "nothing, and who still would not litter."),
                    },
                    {
                        "kind": "choice",
                        "prompt": "Refender turns the wrapper over in his glove.",
                        "options": [
                            {
                                "id": "read_the_date",
                                "label": "Check the date on the wrapper.",
                                "text": ("Eleven months old. Team 19's window "
                                         "exactly.\n\n"
                                         "\"So one of them walked out,\" Refender "
                                         "says. \"Nineteen teams go quiet, and one "
                                         "person out of all of them puts their "
                                         "boots on and walks north-west, alone, "
                                         "into that.\" He looks at the horizon. "
                                         "\"That's not a person fleeing. That's a "
                                         "person who was told where to go.\""),
                                "sets": {"s2_read_the_date": True},
                            },
                            {
                                "id": "look_north_west",
                                "label": "Look at what they were walking towards.",
                                "text": ("Nothing. Snow, rock, more snow, and the "
                                         "curve of the world.\n\n"
                                         "Except — and you have to be standing in "
                                         "exactly this spot to catch it — there is "
                                         "a straight line out there where the snow "
                                         "sits differently. Something under it, "
                                         "buried, running dead straight for as far "
                                         "as you can see.\n\n"
                                         "A cable. Or a rail. Or something that "
                                         "wanted to be neither and got laid like "
                                         "both."),
                                "sets": {"s2_saw_the_line": True},
                            },
                        ],
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Refender",
                        "text": ("On the walk back he says, without preamble: "
                                 "\"Don't put this in the report to Cascade.\"\n\n"
                                 "And then, before you can answer: \"I'm not "
                                 "asking you to lie. I'm asking you to let me be "
                                 "the one who tells them, when I know what it is. "
                                 "There's a difference and I'd like to keep "
                                 "standing on the right side of it.\""),
                    },
                    {
                        "kind": "reward",
                        "text": ("He folds the wrapper back into its square and "
                                 "puts it in his inside pocket, where he keeps "
                                 "things he intends to look at again."),
                        "grant": {"xp": 380, "gold": 7200, "evolution_fragments": 380,
                                  "cores": 520, "item": "legendary",
                                  "permafrost_ore": 40},
                    },
                ],
            },
        ],
    },

    # ======================================================================
    # CHAPTER THREE — BELOW THE CUT
    # ======================================================================
    #
    # WHAT THIS CHAPTER IS ABOUT: the answer to KEPT, and the discovery
    # that Rohan's operation is not a lair but a WORKPLACE with a rota
    # and a kettle.
    #
    # ----------------------------------------------------------------------
    # THE REVEAL, AND WHY IT IS NOT A TWIST
    # ----------------------------------------------------------------------
    # Rex is alive, two levels down, reading a routine all-clear into a
    # microphone twice a day. He has been doing it for fourteen months.
    # He does not know Josh.
    #
    # This is set up in plain sight and on purpose: Chapter Two's survey
    # mast is explicitly a LIVE FEED being SPOKEN, not a recording, and
    # Refender says so out loud while standing in front of it. A player
    # who was paying attention should arrive at Level A already afraid of
    # what the voice is going to turn out to be. That is a much better
    # feeling than surprise, and it is the difference between a story
    # that respects the reader and one that ambushes them.
    #
    # KEPT does not mean killed and never did. It means Rohan could not
    # return what Rex knew, so he kept the man and returned nothing.
    #
    # ----------------------------------------------------------------------
    # THE ONE SAD BEAT, SPENT HERE
    # ----------------------------------------------------------------------
    # Per this module's TONE block, sadness is rationed to roughly once a
    # chapter and does more for being rare. Chapter Three spends its
    # entire allowance in a single scene -- c3m3 -- and everything
    # afterwards is anger, competence and a bad joke from Blueflame,
    # because that is what people actually do afterwards.
    #
    # ----------------------------------------------------------------------
    # THE LAST LOCKED FEATURE
    # ----------------------------------------------------------------------
    # The Void Abyss is the only one of the fifteen features the story had
    # never opened. It opens here, at the bottom of a shaft whose floors
    # are lettered rather than numbered, which is the one place in the
    # game where "there is further down than this" is the actual subject.
    # ======================================================================
    {
        "id": "chapter3",
        "name": "Chapter Three: Below The Cut",
        "blurb": "Nineteen crates on a table, and a lift with letters instead of numbers.",
        "unlocks_region": None,
        "missions": [
            {
                "id": "c3m1_the_long_room",
                "name": "The Long Room",
                "summary": "Three factions, one table, nineteen crates.",
                "beats": [
                    {
                        "kind": "dialogue",
                        "speaker": "Dolphe",
                        "text": (
                            "Cascade's Ops Deck has a long table that is used for "
                            "planning and has never once had nineteen crates on it.\n\n"
                            "Dolphe walks the length of it twice without saying anything. "
                            "He stops at crate 19, which is the light one.\n\n"
                            "\"Eleven weeks,\" he says, eventually. \"That's the number "
                            "you're all too polite to say, so I'll say it.\"\n\n"
                            "\"Josh brought me this fourteen times. I read it every time. "
                            "I referred it to a desk every time, because that is what the "
                            "head of an organisation does, and the desks did their job "
                            "properly and the job was wrong.\"\n\n"
                            "He puts a hand flat on the crate.\n\n"
                            "\"I'm not going to apologise in a room this size. I'll do it "
                            "properly later and privately, and he can tell me where to "
                            "put it.\""
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Dolpo",
                        "text": (
                            "Dolpo has come south for this, in uniform, without telling "
                            "his command — which he mentions in passing, the way you would "
                            "mention the weather.\n\n"
                            "\"Twenty-two teams,\" he says. \"Nineteen of Xender's, three "
                            "of ours. My nation has been holding a gate on that road for "
                            "fourteen months and calling it a training posting.\"\n\n"
                            "\"I am here to say the following out loud in front of "
                            "witnesses, because I intend to be quoted.\"\n\n"
                            "\"The H-Nation has known. Not the whole of it — six people, "
                            "of whom I am the most junior. We knew, and we chose a fence, "
                            "and the fence has held and it has also meant that nobody "
                            "went and looked for two years.\""
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Refender",
                        "text": (
                            "\"Then we are all in the same position,\" Refender says, "
                            "\"which is a relief, because I had prepared something "
                            "cutting and I would rather not use it.\"\n\n"
                            "She sets the clipboard down where everyone can see it.\n\n"
                            "\"Eighteen **RETURNED**. One **KEPT**, dated the fourteenth "
                            "of two years ago.\"\n\n"
                            "\"I want to be precise about what that word does and does "
                            "not tell us. It does not say died. Every other entry on this "
                            "board describes a *disposition*, and this man keeps records "
                            "the way other people breathe.\"\n\n"
                            "She looks at Josh, who has not spoken since he came in.\n\n"
                            "\"I am not offering you hope. I am telling you that the "
                            "evidence does not close, and I will not pretend it does to "
                            "spare anybody an afternoon.\""
                        ),
                    },
                    {
                        "kind": "choice",
                        "prompt": (
                            "Everyone in the room is now waiting on the same question, "
                            "and nobody senior wants to be the one to put it."
                        ),
                        "options": [
                            {
                                "id": "c3_go_back_together",
                                "label": "\"We go back down. All three of us — Cascade, Aligners, H-Nation.\"",
                                "text": (
                                    "\"Agreed,\" Dolphe says, before anyone can start "
                                    "structuring it. \"And to be clear about the shape: "
                                    "Cascade supplies, the Aligners lead, and the "
                                    "H-Nation holds the road. I am not putting a Cascade "
                                    "officer over Josh on this.\"\n\n"
                                    "\"He has been right for two years while we were "
                                    "orderly. He can be right for a fortnight while we "
                                    "carry things.\""
                                ),
                                "sets": {"c3_joint_operation": True},
                            },
                            {
                                "id": "c3_ask_josh",
                                "label": "\"Josh. It's your call and everyone here knows it.\"",
                                "text": (
                                    "He looks up for the first time.\n\n"
                                    "\"Two years I've wanted a room like this,\" he says. "
                                    "\"Everyone listening. Everyone agreeing. I used to "
                                    "run it in my head to get to sleep.\"\n\n"
                                    "\"And now I'm in it and all I can think is that we "
                                    "could have had this meeting the first week and Rex "
                                    "would have been at it.\"\n\n"
                                    "He stands.\n\n"
                                    "\"We go down. Today, if the vans are loaded. I'm not "
                                    "doing another night of this.\""
                                ),
                                "sets": {"c3_josh_decided": True},
                            },
                            {
                                "id": "c3_press_on_kept",
                                "label": "\"Say the thing nobody's saying. KEPT might mean alive.\"",
                                "text": (
                                    "The room does not react well, and Refender lets it "
                                    "not react for a moment before she steps in.\n\n"
                                    "\"It might,\" she says. \"It is the least likely "
                                    "reading and it is not an unreasonable one, and I "
                                    "would rather it was said here, by us, than discovered "
                                    "by one of us alone down a hole.\"\n\n"
                                    "Josh has gone completely still.\n\n"
                                    "\"Then we had better go and find out,\" he says, "
                                    "\"before I have time to build anything on it.\""
                                ),
                                "sets": {"c3_named_the_possibility": True},
                            },
                        ],
                    },
                    {
                        # Only if the player was the one who said it in
                        # the room. Refender does not forget who put
                        # something on a record.
                        "requires": ["c3_named_the_possibility"],
                        "kind": "dialogue",
                        "speaker": "Refender",
                        "text": (
                            "Refender catches you before the vans.\n\n"
                            "\"You said it first,\" she says. \"In there. That KEPT "
                            "might mean alive.\"\n\n"
                            "\"I had written it down four days ago and not said it, "
                            "because I could not work out how to say it to him without "
                            "handing him a thing I might have to take back.\"\n\n"
                            "She adjusts something on her pack that does not need "
                            "adjusting.\n\n"
                            "\"That was cowardice dressed as rigour. I would like you to "
                            "know that I know the difference, and that I noticed you did "
                            "not.\""
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Blueflame",
                        "text": (
                            "In the corridor afterwards, Blueflame falls into step beside "
                            "you with a mug he has taken from a room he was not invited "
                            "into.\n\n"
                            "\"Nice meeting,\" he says. \"Everyone agreed. Everyone "
                            "shook hands. Genuinely lovely.\"\n\n"
                            "He drinks some of somebody else's tea.\n\n"
                            "\"He's had two years of being the only person who believed "
                            "it. That's a horrible way to live and it's also the entire "
                            "shape of him now. If we go down there and find out he was "
                            "right about *everything*—\"\n\n"
                            "He doesn't finish it, which from Blueflame is the loudest "
                            "punctuation available."
                        ),
                    },
                    {
                        "kind": "reward",
                        "text": (
                            "Cascade loads three vans in four hours, which Refender "
                            "times, writes down, and shows to Dolphe without comment.\n\n"
                            "He reads it, and says: \"Yes. I know.\"\n\n"
                            "Jofrog is given a list of everything going north and checks "
                            "it twice against the vans themselves, on the grounds that "
                            "lists have been wrong before."
                        ),
                        "grant": {"xp": 160, "gold": 5000, "item": "mythic", "evolution_fragments": 520,
                                  "shards": 400, "cores": 400, "lootbox": ("legendary", 2)},
                    },
                ],
            },

            {
                "id": "c3m2_level_a",
                "name": "Level A",
                "summary": "The lift goes down a long way, and what is at the bottom has a rota.",
                "beats": [
                    {
                        "kind": "dialogue",
                        "speaker": "Refender",
                        "text": (
                            "The lift takes ninety seconds and nobody talks for any of "
                            "them.\n\n"
                            "The doors open on swept concrete, good lighting, and warm "
                            "air.\n\n"
                            "There is a duty rota laminated to the wall by the doors. Six "
                            "names, a fortnight of shifts, and a note about who is "
                            "covering the kettle run.\n\n"
                            "Refender reads it for a long moment.\n\n"
                            "\"Four of these names are on crates upstairs,\" she says.\n\n"
                            "\"They were *rostered*. They had shifts and breaks and a "
                            "kettle run and then they were packed into numbered boxes and "
                            "stacked in the correct order.\""
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Jofrog",
                        "text": (
                            "Jofrog has found the shelving, which runs floor to ceiling "
                            "and is labelled in the same neat hand as everything else.\n\n"
                            "\"*Spares, track. Spares, optical. Returns, processed. "
                            "Returns, pending.*\"\n\n"
                            "He stops at the pending shelf, which has three boxes on it, "
                            "and they are not the shape of equipment.\n\n"
                            "\"I don't like this floor,\" he says, in a small voice for a "
                            "man his size. \"Nothing here's wrong. It's all — it's all "
                            "*tidy*. I keep waiting for the bit that's wrong and it's just "
                            "shelves.\""
                        ),
                    },
                    {
                        # 15% -- the chapter's floor, and deliberately a
                        # thing that was working rather than guarding.
                        "kind": "battle",
                        "enemies": ["Rohan's Catastrophe Soldier"],
                        "level": 45,
                        "intro": (
                            "It is at the far end of the level, moving crates, and it has "
                            "been doing that since before you arrived.\n\n"
                            "It sets the one it is holding down properly, square to the "
                            "others, before it turns round.\n\n"
                            "\"It finished the job first,\" Blueflame says. \"Did anyone "
                            "else see that? It finished the *job* first.\""
                        ),
                        "on_win": (
                            "It goes down beside the stack it was building and does not "
                            "knock any of it over.\n\n"
                            "There is no alarm. Nothing else on the level reacts. Two "
                            "rooms away, at exactly the top of the hour, a voice begins "
                            "reading a routine all-clear into a microphone.\n\n"
                            "Josh stops dead in the middle of the floor.\n\n"
                            "\"That's a *person*,\" he says."
                        ),
                        "on_lose": (
                            "You come round on Level A with your kit stacked beside you, "
                            "squared to the wall.\n\n"
                            "Somewhere off the floor, at the top of the hour, somebody "
                            "starts reading an all-clear."
                        ),
                    },
                    {
                        "kind": "reward",
                        "text": (
                            "The optical spares shelf is better catalogued than Cascade's "
                            "own store, which Refender says out loud and then looks "
                            "unhappy about having said.\n\n"
                            "\"He is not mad,\" she says. \"I would like him to be mad. It "
                            "would be so much easier to plan against.\""
                        ),
                        "grant": {"xp": 260, "gold": 5500, "item": "mythic", "evolution_fragments": 560,
                                  "cores": 400},
                    },
                ],
            },

            {
                # THE CHAPTER'S ONE SAD SCENE. No fight, no choice that
                # changes the outcome, and it is short -- the worst thing
                # you can do to a moment like this is give it eleven
                # beats and a boss.
                "id": "c3m3_the_voice",
                "name": "The Voice On The Loop",
                "summary": "Two rooms away, at the top of every hour, somebody reads an all-clear.",
                "beats": [
                    {
                        "kind": "dialogue",
                        "speaker": "Refender",
                        "text": (
                            "The room is small and warm and has a chair in it, a desk, a "
                            "microphone on a stand, and a card taped to the desk with the "
                            "words of a routine all-clear printed on it.\n\n"
                            "There is a man sitting at it. He is about fifty. He has a mug "
                            "at his elbow, two thirds full, with a ring in the bottom.\n\n"
                            "He finishes the line he is on — Survey Team 4, all clear, "
                            "nothing to report — and switches off the microphone properly, "
                            "and only then looks up.\n\n"
                            "\"Oh,\" he says. \"Hello. Are you the new intake?\""
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Josh",
                        "text": (
                            "Josh does not say anything for four seconds, which is a very "
                            "long time in a small room.\n\n"
                            "\"Rex,\" he says.\n\n"
                            "The man's face does the thing a face does when it is being "
                            "polite about a word it does not have.\n\n"
                            "\"That's me,\" he says, pleasantly. \"It's on the tin.\" He "
                            "taps a name badge, printed, laminated, clipped on straight. "
                            "\"Sorry — have we met? I'm terrible. I've been on the desk a "
                            "while.\"\n\n"
                            "\"Fourteen months,\" says Refender, very quietly.\n\n"
                            "\"Is it? Feels about right.\""
                        ),
                    },
                    {
                        "kind": "choice",
                        "prompt": (
                            "Josh has not moved. Somebody has to say the next thing and "
                            "it is not going to be him."
                        ),
                        "options": [
                            {
                                "id": "c3_tell_him",
                                "label": "\"Your name is Rex. You built a receiver. This man took two years off you.\"",
                                "text": (
                                    "He listens to all of it, politely, the way you listen "
                                    "to somebody describing a film you have not seen.\n\n"
                                    "\"That's a lot,\" he says, when you finish. \"I'm not "
                                    "saying you're wrong. I'm saying I've got a desk and a "
                                    "card and a mug, and you've got a story, and from in "
                                    "here they're not the same size.\"\n\n"
                                    "He looks at Josh.\n\n"
                                    "\"You do keep looking at me like I owe you money.\"\n\n"
                                    "\"You don't,\" Josh says. \"You really, really "
                                    "don't.\""
                                ),
                                "sets": {"c3_told_rex_everything": True},
                            },
                            {
                                "id": "c3_ask_him_to_come",
                                "label": "\"Would you come upstairs with us? Just up. Nothing else.\"",
                                "text": (
                                    "He considers it seriously, which is the worst part.\n\n"
                                    "\"I'd have to get someone to cover the hour,\" he "
                                    "says. \"You can't just leave the hour.\"\n\n"
                                    "Then, after a moment, with a small frown, as though "
                                    "something has snagged:\n\n"
                                    "\"...Who would I get? There's nobody on the rota "
                                    "after Tuesday.\"\n\n"
                                    "He sits with that. Nobody helps him with it.\n\n"
                                    "\"I'll get my coat,\" he says."
                                ),
                                "sets": {"c3_asked_rex_upstairs": True},
                            },
                            {
                                "id": "c3_say_nothing",
                                "label": "*Say nothing. Let Josh do this.*",
                                "text": (
                                    "Josh crosses the room, and does not embrace him, and "
                                    "does not shout.\n\n"
                                    "He picks up the mug, looks at the ring in the bottom "
                                    "of it, and washes it out in the little sink in the "
                                    "corner — outside first, then in — and puts it back "
                                    "exactly where it was.\n\n"
                                    "\"You always did that,\" he says. \"You washed the "
                                    "outside. Drove me mad.\"\n\n"
                                    "\"Did I?\" says Rex, delighted. \"That's a good one. "
                                    "Nobody's told me a thing about myself in "
                                    "*ages*.\"\n\n"
                                    "Josh has to leave the room for a minute after that."
                                ),
                                "sets": {"c3_let_josh_do_it": True},
                            },
                        ],
                    },
                    {
                        # The two-chapter callback. If the player looked
                        # around Rex's workshop rather than reading the
                        # notebook, they are the only person in the room
                        # who has seen this mug before.
                        "requires": ["c1_looked_around_workshop"],
                        "kind": "dialogue",
                        "speaker": "Refender",
                        "text": (
                            "You have seen that mug before.\n\n"
                            "Not this one. The other one, nine hundred kilometres south, "
                            "on a bench under a light that has been on for two years — "
                            "washed on the outside, put back in its own ring.\n\n"
                            "Whoever has been keeping that workshop has been doing to a "
                            "room what this man does to a mug, and neither of them knows "
                            "about the other.\n\n"
                            "Refender follows your eyes to it, and works it out about a "
                            "second behind you, and has to go and stand in the corridor."
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Blueflame",
                        "text": (
                            "Outside, in the corridor, Blueflame is standing with his back "
                            "against the wall and his eyes shut.\n\n"
                            "\"Right,\" he says. \"So I've been doing the joke for two "
                            "years. The one about how he's fine, he's off somewhere, he'll "
                            "turn up. Everyone hated it. I kept doing it.\"\n\n"
                            "He opens his eyes.\n\n"
                            "\"Turns out I was *right*, which I would like on the record "
                            "as the single worst thing that has ever happened to me.\"\n\n"
                            "It is not funny, and he knows it is not funny, and he says it "
                            "anyway because the alternative is the other thing."
                        ),
                    },
                    {
                        "kind": "reward",
                        "text": (
                            "Refender takes the card off the desk — the printed all-clear, "
                            "the one he has read twice a day for fourteen months — and "
                            "folds it into her jacket.\n\n"
                            "\"Evidence,\" she says, and nobody believes her, and nobody "
                            "says so."
                        ),
                        "grant": {"xp": 350, "gold": 6000, "item": "mythic", "evolution_fragments": 600,
                                  "shards": 400, "cores": 400},
                    },
                ],
            },

            {
                "id": "c3m4_what_he_was_building",
                "name": "What He Was Building",
                "summary": "Level R. An assembly line, running, unattended, with a counter above it.",
                "beats": [
                    {
                        "kind": "dialogue",
                        "speaker": "Refender",
                        "text": (
                            "Level R is a factory floor, and it is running.\n\n"
                            "Raw plate at one end. At the other, finished and racked in "
                            "threes: Wardens. The same machine that stood in a freight "
                            "depot's car park for nine days and watched.\n\n"
                            "There is a counter above the line. It reads three hundred and "
                            "twelve.\n\n"
                            "\"That is not a defence,\" Refender says. \"Nobody needs "
                            "three hundred of anything to hold a hole in the ground.\"\n\n"
                            "\"That is a *deployment*, and it is nearly finished, and we "
                            "are standing in it.\""
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Jofrog",
                        "text": (
                            "Jofrog has found the filing.\n\n"
                            "Floor to ceiling, alphabetical, and not machines. One folder "
                            "per *person*, and the tabs run from before the survey teams "
                            "to well after them.\n\n"
                            "Refender finds Cascade's spring convoy in under a minute, "
                            "because it is exactly where it should be.\n\n"
                            "\"Six people,\" she says. \"Photographs. Route. Times. A note "
                            "in the margin.\"\n\n"
                            "She reads the note twice before she reads it aloud.\n\n"
                            "\"*Sample. Response time of southern organisation: eleven "
                            "weeks. Adequate.*\""
                        ),
                    },
                    {
                        "kind": "choice",
                        "prompt": (
                            "That is the convoy the Aligners left Cascade over. It is in a "
                            "folder, in a filing system, marked as a test."
                        ),
                        "options": [
                            {
                                "id": "c3_it_was_a_test",
                                "label": "\"He killed six people to time how long Cascade takes.\"",
                                "text": (
                                    "\"Yes,\" Refender says. Her voice does not change at "
                                    "all, which is how you know.\n\n"
                                    "\"And we passed. Eleven weeks was *adequate* — "
                                    "adequate for his purposes, meaning slow enough that "
                                    "he could proceed.\"\n\n"
                                    "\"I have spent two years being angry at a report. I "
                                    "would like to redirect that now, please, and I would "
                                    "like to do it accurately.\""
                                ),
                                "sets": {"c3_understood_the_convoy": True},
                            },
                            {
                                "id": "c3_check_our_folders",
                                "label": "\"Find ours. We're in here somewhere.\"",
                                "text": (
                                    "You are.\n\n"
                                    "All of you, one folder each, tabbed and current. "
                                    "Josh's is the thickest by a wide margin and goes back "
                                    "two years.\n\n"
                                    "Yours is the thinnest. It contains four photographs "
                                    "taken from a distance, a single line of text — "
                                    "*origin unestablished* — and nothing else at all.\n\n"
                                    "Dolphin's has one sheet in it. He does not open it, "
                                    "and nobody makes him."
                                ),
                                "sets": {"c3_found_own_folder": True},
                            },
                            {
                                "id": "c3_burn_it",
                                "label": "\"We take all of it. Every folder, upstairs, today.\"",
                                "text": (
                                    "\"Every folder is a person,\" Jofrog says "
                                    "immediately. \"That's — there's families in here who "
                                    "don't know. We can't leave them in a *basement*.\"\n\n"
                                    "\"We cannot carry it either,\" Refender says. \"Not "
                                    "today, not in three vans.\"\n\n"
                                    "She is already photographing tab rows in sequence, "
                                    "methodically, ten to a frame.\n\n"
                                    "\"So we take the index and we come back with a "
                                    "convoy. And this time nobody is going to have to "
                                    "argue for eleven weeks about whether to.\""
                                ),
                                "sets": {"c3_took_the_index": True},
                            },
                        ],
                    },
                    {
                        # 38%. The line's own product, in numbers.
                        "kind": "battle",
                        "enemies": ["Rohan's Negadom"],
                        "level": 39,
                        "intro": (
                            "The line stops.\n\n"
                            "Not breaks — stops, cleanly, mid-cycle, the way things stop "
                            "down here when somebody decides they should.\n\n"
                            "The thing that comes off the end of it is not a Warden. It is "
                            "what the Wardens are being built *by*, and it has been at the "
                            "far end of this floor doing that job for fourteen months."
                        ),
                        "on_win": (
                            "It comes apart across the width of the floor and the line "
                            "does not restart.\n\n"
                            "The counter above it stays at three hundred and twelve, which "
                            "somehow reads worse than if it had kept climbing.\n\n"
                            "\"Three hundred and twelve of those,\" Blueflame says. \"And "
                            "we've now met four. Anyone want to do the sum out loud or "
                            "shall we all just carry it privately?\""
                        ),
                        "on_lose": (
                            "You come round with the line running again and the counter "
                            "one higher than it was.\n\n"
                            "Nobody has been moved. Nobody has been taken. The work simply "
                            "resumed around you, which is the most frightening thing that "
                            "has happened all day."
                        ),
                    },
                    {
                        "kind": "reward",
                        "text": (
                            "The returns bench is at the back: personal effects, sorted, "
                            "bagged, labelled, waiting to go up.\n\n"
                            "Jofrog checks every bag against the crate numbers he "
                            "memorised upstairs. He does not find the one he is looking "
                            "for, and he does not say who it was for, and after a while he "
                            "puts the birthday card from crate 11 back in his inside "
                            "pocket and gets on with it."
                        ),
                        "grant": {"xp": 450, "gold": 7000, "item": "mythic", "evolution_fragments": 660,
                                  "shards": 500, "cores": 500, "lootbox": ("legendary", 3)},
                    },
                ],
            },

            {
                "id": "c3m5_inventory",
                "name": "Inventory",
                "summary": "There is a desk down here with a ledger on it, and the ledger is the whole thing.",
                "beats": [
                    {
                        "kind": "dialogue",
                        "speaker": "Refender",
                        "text": (
                            "The desk is at the centre of Level R and it is the only "
                            "untidy thing on it — because it is in use.\n\n"
                            "A ledger, open, handwritten, in the hand you have now seen on "
                            "a driller, a housing plate and a clipboard.\n\n"
                            "It is not a diary. It is an *inventory of the region*: "
                            "settlements, organisations, capabilities, response times. "
                            "Cascade has eleven pages. The H-Nation has nine. The Aligners "
                            "have two, and one of those is new.\n\n"
                            "\"He is not planning an attack,\" Refender says slowly. \"He "
                            "is planning an **audit**. He intends to go through this "
                            "region the way he went through those teams — establish what "
                            "each thing is, and dispose of it accordingly.\""
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Dolphin",
                        "text": (
                            "Dolphin, who has been quiet since Level A, is standing at the "
                            "end of the desk with a page held flat under both hands.\n\n"
                            "\"There's a section on me,\" he says.\n\n"
                            "\"It's — it's not long. It says where I was found. It says "
                            "what was removed and it says why.\" His voice is very "
                            "level, which it never is. \"It says *returned to circulation, "
                            "monitored*, and there's a column of dates going all the way "
                            "to last month.\"\n\n"
                            "He looks up.\n\n"
                            "\"He's been checking on me for two years. Somebody's been "
                            "checking on me my whole life and it was *him*.\""
                        ),
                    },
                    {
                        "kind": "choice",
                        "prompt": (
                            "There is a chair at the desk, pushed in. There is a second "
                            "mug on the tray by the kettle, put out ready."
                        ),
                        "options": [
                            {
                                "id": "c3_take_the_ledger",
                                "label": "\"Take the ledger. It's the whole case.\"",
                                "text": (
                                    "\"It is the whole case,\" Refender agrees, \"and it "
                                    "is also the only copy, and he has left it open on a "
                                    "desk in a room he knew we would reach.\"\n\n"
                                    "She takes it anyway.\n\n"
                                    "\"I am aware I am doing the thing he expects. I have "
                                    "weighed being predictable against leaving a "
                                    "ledger of every settlement in the region on his "
                                    "desk, and I find I can live with being "
                                    "predictable.\""
                                ),
                                "sets": {"c3_took_the_ledger": True},
                            },
                            {
                                "id": "c3_read_the_last_page",
                                "label": "*Turn to the last written page.*",
                                "text": (
                                    "It is dated today.\n\n"
                                    "*Southern organisation has arrived in force. "
                                    "Response time from disclosure: six days. Revised "
                                    "from adequate.*\n\n"
                                    "Below that, a second line, added in the same hand:\n\n"
                                    "*Reassessment required. Nineteen entries reopened.*\n\n"
                                    "He has been down here today. He has watched you come "
                                    "down, and gone back to his desk, and updated his "
                                    "figures."
                                ),
                                "sets": {"c3_read_the_last_page": True},
                            },
                            {
                                "id": "c3_the_second_mug",
                                "label": "*Look at the second mug.*",
                                "text": (
                                    "Clean, dry, set out ready on the tray beside the "
                                    "kettle. There is a spoon next to it.\n\n"
                                    "There has been exactly one person on this level for "
                                    "fourteen months, and he has been putting out two "
                                    "mugs.\n\n"
                                    "\"He's been expecting company,\" Blueflame says. "
                                    "\"For over a year. Nobody put a second mug out for me "
                                    "in my entire life and I've had *friends*.\""
                                ),
                                "sets": {"c3_saw_the_second_mug": True},
                            },
                        ],
                    },
                    {
                        # 59% -- the step before the climax.
                        "kind": "battle",
                        "enemies": ["Rohan's Catastrophe Soldier", "Rohan's Warden"],
                        "level": 42,
                        "intro": (
                            "They come in through the door you came in by, which means "
                            "they came down the lift, which means somebody sent them "
                            "after you rather than leaving them here.\n\n"
                            "\"He's not defending the desk,\" Josh says. \"He's *tidying "
                            "up behind us.*\"\n\n"
                            "They do not stop at the filing. They walk straight past three "
                            "hundred folders and come for the people in the room."
                        ),
                        "on_win": (
                            "It is the hardest thing any of you have done and it takes all "
                            "four, and at the end of it the floor is a mess for the first "
                            "time since you arrived.\n\n"
                            "Refender looks at the wreckage, and then at the filing wall "
                            "behind it, entirely undamaged.\n\n"
                            "\"They were careful of the folders,\" she says. \"In the "
                            "middle of that. They were *careful of the folders*.\""
                        ),
                        "on_lose": (
                            "You come round with the ledger gone from the desk and "
                            "everything else exactly as it was.\n\n"
                            "The second mug is still out. Somebody has, at some point, "
                            "filled the kettle."
                        ),
                    },
                    {
                        "kind": "reward",
                        "text": (
                            "Refender photographs the ledger cover to cover before "
                            "anybody argues about carrying it, working through it page by "
                            "page with the steadiness of somebody who has decided not to "
                            "feel anything until later.\n\n"
                            "It takes forty minutes. Nobody hurries her, and Josh stands "
                            "at the end of the desk the entire time without being asked "
                            "to."
                        ),
                        "grant": {"xp": 540, "gold": 8000, "item": "mythic", "evolution_fragments": 900,
                                  "shards": 600, "cores": 600, "lootbox": ("legendary", 3)},
                    },
                ],
            },

            {
                "id": "c3m6_the_bottom",
                "name": "The Bottom Of The Letters",
                "summary": "He is waiting by the last door, and he would like to finish the conversation.",
                "beats": [
                    {
                        "kind": "dialogue",
                        "speaker": "Rohan",
                        "text": (
                            "There is one more door on Level R and he is standing beside "
                            "it, holding two mugs.\n\n"
                            "He offers one. Nobody takes it. He sets it down on a crate "
                            "without any apparent disappointment, square to the edge.\n\n"
                            "\"Six days,\" he says. \"From your disclosure to three "
                            "vans on my road. I had eleven weeks in the ledger and I have "
                            "corrected it.\"\n\n"
                            "\"I want to be clear that this is not a complaint. I have "
                            "been trying to establish what the southern organisation "
                            "actually is for two years, and you have told me in six days, "
                            "which is the most useful thing anybody has done for me since "
                            "I got here.\""
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Josh",
                        "text": (
                            "\"He doesn't know who I am,\" Josh says.\n\n"
                            "It is not a question and Rohan treats it as one anyway.\n\n"
                            "\"No. That was the disposition. I could not return what he "
                            "knew, and what he knew was not separable from who he had "
                            "been, and I am not in the business of half measures.\"\n\n"
                            "\"He has been content. I want to be accurate about that "
                            "rather than kind: he has been *content*, for fourteen months, "
                            "with a desk and an hour and a mug. That is more than most "
                            "people manage.\"\n\n"
                            "\"He built a receiver in a shed and followed a second and a "
                            "half nine hundred kilometres,\" Josh says. \"He was the best "
                            "person I ever met and you gave him a *card to read*.\""
                        ),
                    },
                    {
                        "kind": "choice",
                        "prompt": (
                            "He is listening properly. He has listened properly to every "
                            "word anyone has said to him, which is the thing about him "
                            "that is hardest to hold."
                        ),
                        "options": [
                            {
                                "id": "c3_what_are_you",
                                "label": "\"What are you actually doing here?\"",
                                "text": (
                                    "\"Establishing what is here,\" he says, \"so that it "
                                    "can be dealt with correctly. There is a great deal in "
                                    "this region that nobody has ever counted.\"\n\n"
                                    "\"You are going to ask on whose authority. The honest "
                                    "answer is that I arrived, and found no inventory, and "
                                    "no one keeping one, and I have never in my life been "
                                    "able to leave that alone.\"\n\n"
                                    "\"You may find that insufficient. I would, in your "
                                    "position.\""
                                ),
                                "sets": {"c3_asked_what_he_is_doing": True},
                            },
                            {
                                "id": "c3_give_him_back",
                                "label": "\"Give him back. Whatever you took, put it back.\"",
                                "text": (
                                    "For the first time since you met him, he takes a "
                                    "moment before answering.\n\n"
                                    "\"I cannot,\" he says. \"Not as a refusal. As a "
                                    "statement of capability. What is removed is not "
                                    "stored.\"\n\n"
                                    "\"I understand that this is the answer that makes me "
                                    "unforgivable rather than merely opposed. I have had "
                                    "two years to find a better one and there isn't "
                                    "one.\"\n\n"
                                    "Josh does not say anything at all."
                                ),
                                "sets": {"c3_demanded_rex_back": True},
                            },
                            {
                                "id": "c3_dolphin_asks",
                                "label": "*Step aside. Dolphin has walked to the front.*",
                                "text": (
                                    "\"You've got a column of dates on me,\" Dolphin says. "
                                    "\"Going up to last month.\"\n\n"
                                    "\"I have.\"\n\n"
                                    "\"Why check? You took it. It's gone. What's there to "
                                    "check?\"\n\n"
                                    "And Rohan pauses — actually pauses, for the first "
                                    "time in three chapters.\n\n"
                                    "\"Because in your case,\" he says, \"the inventory "
                                    "did not come out the same way twice.\"\n\n"
                                    "He picks up the untouched mug and looks at it.\n\n"
                                    "\"You are the only entry I have ever had to check.\""
                                ),
                                "sets": {"c3_dolphin_asked_rohan": True},
                            },
                        ],
                    },
                    {
                        # THE CLIMAX -- 78%, the hardest fight in the
                        # story so far. Still not Rohan himself, and the
                        # scene says why out loud: he does not fight, he
                        # DELEGATES, and the one time he is asked a
                        # question he cannot answer he leaves rather than
                        # engage.
                        "kind": "battle",
                        "enemies": ["Rohan's Negadom", "Rohan's Warden"],
                        "level": 31,
                        "intro": (
                            "He opens the last door and goes through it, and does not "
                            "hurry, and does not look back.\n\n"
                            "What comes out of it is the thing that cut the driller in one "
                            "pass, and it has one of the three hundred and twelve with "
                            "it.\n\n"
                            "\"Every time,\" Blueflame says, getting up. \"Every single "
                            "time. He never once does it himself.\""
                        ),
                        "on_win": (
                            "When it is over, the door he went through is open, and there "
                            "is a lift behind it, and the lift has gone down.\n\n"
                            "The counter above it has letters on it. There are eleven of "
                            "them and you have seen two.\n\n"
                            "On the crate by the door, the second mug is still standing "
                            "where he put it, untouched, square to the edge."
                        ),
                        "on_lose": (
                            "You come round on Level R with the lights on and the line "
                            "restarted and the folders untouched.\n\n"
                            "The mug is gone. Somebody has washed it, outside first, and "
                            "put it back on the tray."
                        ),
                    },
                    {
                        "kind": "unlock",
                        "feature": "abyss",
                        "text": (
                            "**The Void Abyss is open.**\n\n"
                            "Eleven letters on a counter, and you have seen two of them. "
                            "The shaft below Level R goes down further than anybody has "
                            "surveyed, and the things coming up it do not belong to "
                            "Rohan.\n\n"
                            "Twelve floors, twelve teams, and one rule: **no character may "
                            "appear in more than one chamber of the same floor.** This is "
                            "the mode that asks how deep your roster actually goes.\n\n"
                            "It is the last thing the story had left to open."
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Josh",
                        # UNGATED. This is the chapter's closing image and
                        # every player gets it; only the Dolpo half below
                        # is conditional. Gating the whole beat -- which is
                        # what I did first -- would have deleted the Rex
                        # scene for anyone who picked a different line two
                        # chapters ago, which is not a consequence, it is a
                        # punishment for not guessing.
                        "text": (
                            "They bring Rex up in the second van, sitting in the front "
                            "with a blanket he did not ask for and a mug he would not "
                            "leave behind.\n\n"
                            "He is interested in everything. He asks Jofrog three "
                            "questions about the van's suspension and gets four answers.\n\n"
                            "Josh drives the third van, alone, and nobody suggests "
                            "otherwise."
                        ),
                    },
                    {
                        "requires": ["c2_asked_dolpo_along"],
                        "kind": "dialogue",
                        "speaker": "Dolpo",
                        "text": (
                            "At the gate, Dolpo waves all three vans through without "
                            "checking any of them, and then stands in the road watching "
                            "until they are out of sight, which is not in any procedure "
                            "he has ever been issued.\n\n"
                            "You asked him to come north, months ago, and he said no and "
                            "meant it and it cost him.\n\n"
                            "As the last van passes he steps forward and puts a hand flat "
                            "on the side of it — once, briefly, the way you would touch a "
                            "wall you were leaving.\n\n"
                            "\"Tell him,\" he says, through the window, to nobody in "
                            "particular. \"Tell my brother I said the coat suits him.\""
                        ),
                    },
                    {
                        "unless": ["c2_asked_dolpo_along"],
                        "kind": "dialogue",
                        "speaker": "Dolpo",
                        "text": (
                            "At the gate, Dolpo waves all three vans through without "
                            "checking any of them, and then stands in the road watching "
                            "until they are out of sight, which is not in any procedure "
                            "he has ever been issued."
                        ),
                    },
                    {
                        "kind": "reward",
                        "text": (
                            "Refender's report goes to Cascade, the H-Nation and — at "
                            "Dolpo's insistence and over some objection — Xender, who lost "
                            "nineteen teams and have not been told why.\n\n"
                            "It is forty pages. It is finished in a night. Nobody refers "
                            "it to a desk.\n\n"
                            "At the bottom of the last page, under her signature, she has "
                            "written one line that is not evidence:\n\n"
                            "*He puts out two mugs. Whatever else is true, plan for the "
                            "fact that he wants someone to talk to.*"
                        ),
                        "grant": {"xp": 640, "gold": 12000, "item": "mythic", "evolution_fragments": 1100,
                                  "shards": 800, "cores": 800, "lootbox": ("mythic", 2)},
                    },
                ],
            },

            # ------------------------------------------------------------------
            # SIDE MISSION -- see the note on s1 for why `optional` matters.
            # ------------------------------------------------------------------
            {
                "id": "s3_the_fourth_name",
                "name": "The Fourth Name",
                "optional": True,
                "summary": "Four rows in the intake ledger have nothing in the RETURNED column.",
                "beats": [
                    {
                        "kind": "dialogue",
                        "speaker": "Rex",
                        "text": ("Rex gets to the ledger before you do and does "
                                 "not turn the page when you arrive, which is how "
                                 "you know he has already read it twice.\n\n"
                                 "\"Four,\" he says. \"Four people came in here "
                                 "and the column that says whether they went home "
                                 "again is empty. Three of those four have a line "
                                 "through them.\""),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Rex",
                        "text": ("\"A line through a name in a ledger like this "
                                 "means the file was closed,\" Rex says. \"It "
                                 "doesn't mean *died*. It means somebody decided "
                                 "there was nothing further to record.\"\n\n"
                                 "He puts one finger on the fourth row. The paper "
                                 "there has gone soft and translucent from being "
                                 "written over and over.\n\n"
                                 "\"This one they never closed. They just kept "
                                 "changing what it said.\""),
                    },
                    {
                        "kind": "choice",
                        "prompt": "The fourth name is short and starts with a D.",
                        "options": [
                            {
                                "id": "hold_it_to_the_light",
                                "label": "Hold the page up to the light.",
                                "text": ("Eleven versions, stacked. The earliest "
                                         "is the shortest. The latest has been "
                                         "written by somebody pressing very hard.\n\n"
                                         "You can read two of the eleven. One says "
                                         "a name you have heard somebody introduce "
                                         "himself with on a roof. The other says "
                                         "*SUBJECT DECLINED DESIGNATION*."),
                                "sets": {"s3_read_the_page": True},
                            },
                            {
                                "id": "close_the_book",
                                "label": "Close it. This isn't yours to read first.",
                                "text": ("You put your hand flat on the page and "
                                         "shut the ledger, and Rex lets you.\n\n"
                                         "\"Right,\" he says, after a moment. "
                                         "\"Yes. Right.\" He sounds like somebody "
                                         "who wanted to be stopped and could not "
                                         "have stopped himself."),
                                "sets": {"s3_closed_the_book": True},
                            },
                        ],
                    },
                    {
                        "kind": "puzzle",
                        "puzzle_kind": "code",
                        "optional": True,
                        "emoji": "🔢",
                        "name": "The fourth row's intake number",
                        "text": ("Every row in the ledger has an intake number. "
                                 "The fourth row's has been scratched out — but "
                                 "the numbering is sequential and the rows either "
                                 "side of it are intact.\n\n"
                                 "Optional. Rex will read it out eventually "
                                 "either way; working it out yourself just gets "
                                 "you to the drawer first."),
                        "clues": [
                            "The third row's intake number is 0114.",
                            "The fifth row's intake number is 0116.",
                            "They were logged in order, one per row, no gaps.",
                        ],
                        "answers": ["0115", "115"],
                        "derivation": ("Sequential between the intact rows 0114 "
                                       "and 0116."),
                        "on_solve": ("0115. You find the drawer before Rex does, "
                                     "and what is in it is a single index card "
                                     "with two words on it in a hand you have "
                                     "started to recognise: *keep him*."),
                        "on_fail": "That number belongs to a row that is right there in front of you.",
                        "on_skip": ("You leave it. Rex will get there, and there "
                                    "is something in his face that says he would "
                                    "rather be the one who does."),
                        "grant": {"xp": 180, "gold": 7000, "evolution_fragments": 300,
                                  "cores": 420, "item": "mythic"},
                        "sets": {"s3_found_the_card": True},
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Rex",
                        "text": ("\"I want to say something and I want you to "
                                 "hear the whole thing before you react,\" Rex "
                                 "says.\n\n"
                                 "\"I have been in this building before. Not on "
                                 "the plan, not in the log, not in anybody's "
                                 "record — but my hands knew the stairwell was "
                                 "behind the racking, and I did not tell them "
                                 "to.\"\n\n"
                                 "\"So either I am also in this ledger somewhere, "
                                 "or I am the person who wrote it. And I do not "
                                 "know which of those I would rather be true.\""),
                    },
                    {
                        "kind": "reward",
                        "text": ("He takes the ledger with him. Nobody objects, "
                                 "and nobody asks him to hand it over later "
                                 "either, which is its own kind of answer."),
                        "grant": {"xp": 520, "gold": 19000, "evolution_fragments": 820,
                                  "cores": 1100, "item": "mythic",
                                  "lootbox": ("mythic", 2)},
                    },
                ],
            },
        ],
    },

    # ======================================================================
    # CHAPTER FOUR — THE AUDIT
    # ======================================================================
    #
    # WHAT THIS CHAPTER IS ABOUT: he stops waiting for people to come to
    # him. Three hundred and twelve Wardens, and a region that has never
    # been counted.
    #
    # ----------------------------------------------------------------------
    # THE STRUCTURAL INVERSION
    # ----------------------------------------------------------------------
    # Chapters One to Three were all APPROACH -- a depot, a road, a site,
    # a shaft, each one further from home. This chapter turns that round:
    # the first half is a defence of the shabbiest location in the game,
    # and it only goes back underground once the player has had to hold
    # the freight depot with sandbags and three factions' vans in the car
    # park.
    #
    # That is the only way a base earns anything. Sixteen Freight has
    # been "four camp beds and a kettle" for three chapters precisely so
    # that defending it costs something.
    #
    # ----------------------------------------------------------------------
    # DOLPHIN PAYS OFF, WITHOUT RESOLVING
    # ----------------------------------------------------------------------
    # Rohan's own file on him now reads, in three lines added at three
    # different times: *inventory does not resolve. second attempt: does
    # not resolve. why.* That is on the map, in a note, optional.
    #
    # The chapter USES it -- Dolphin is the one person the audit will not
    # categorise, and therefore the one person it does not immediately
    # act on -- without explaining it. What he is remains open. What he
    # is FOR, in this story, is now answered: he is the reason the audit
    # can be interrupted.
    # ======================================================================
    {
        "id": "chapter4",
        "name": "Chapter Four: The Audit",
        "blurb": "Three hundred and twelve of them, and a region nobody has ever counted.",
        "unlocks_region": None,
        "missions": [
            {
                "id": "c4m1_the_audit_begins",
                "name": "The Audit Begins",
                "summary": "Every radio in the building goes off at once, and none of it is an attack.",
                "beats": [
                    {
                        "kind": "dialogue",
                        "speaker": "Refender",
                        "text": (
                            "It starts at eleven in the morning, on a Tuesday, and the "
                            "first sign is that every radio in the building goes off "
                            "within ninety seconds of the others.\n\n"
                            "Refender takes them in order.\n\n"
                            "\"Ashfield. Two of them, standing at the fence, not "
                            "approaching. Kettleford — four, in the square, counting "
                            "*doors*. The H-Nation post reports six on the road, walking "
                            "past the gate without stopping.\"\n\n"
                            "She puts the last handset down.\n\n"
                            "\"Nobody is under attack. Nineteen settlements are being "
                            "**visited**, simultaneously, by machines that arrived on "
                            "foot and are writing things down.\""
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Josh",
                        "text": (
                            "\"He's doing the region,\" Josh says. \"He told us he "
                            "would. He said it out loud in a room and we all heard "
                            "it.\"\n\n"
                            "He is at the map with a marker and he is not shaking, which "
                            "is somehow worse than if he were.\n\n"
                            "\"Establish what is here so it can be dealt with correctly. "
                            "That's an audit. This is the audit. It started six days "
                            "after we told him how fast we can move.\"\n\n"
                            "He caps the marker.\n\n"
                            "\"Three hundred and twelve. We counted them ourselves and "
                            "then we came home and slept.\""
                        ),
                    },
                    {
                        "kind": "choice",
                        "prompt": (
                            "Nineteen settlements. Three factions. One van each is not a "
                            "plan and everybody in the room knows it."
                        ),
                        "options": [
                            {
                                "id": "c4_defend_here",
                                "label": "\"We can't cover nineteen. We hold this one and make him come.\"",
                                "text": (
                                    "\"Agreed, and I hate it,\" Refender says. \"We hold "
                                    "Sixteen Freight, we hold it loudly, and we make "
                                    "ourselves the most expensive line on his sheet.\"\n\n"
                                    "\"It is a real cost. Kettleford has ninety people in "
                                    "it and we are choosing not to be there.\"\n\n"
                                    "\"Cascade is going to Kettleford,\" says Josh. "
                                    "\"Dolphe moved four teams before we finished the "
                                    "call. That's the difference this time.\""
                                ),
                                "sets": {"c4_chose_to_hold": True},
                            },
                            {
                                "id": "c4_split_up",
                                "label": "\"Split. Everyone takes a settlement.\"",
                                "text": (
                                    "\"No,\" says Jofrog, before anyone else can, which "
                                    "nobody has ever heard him do.\n\n"
                                    "\"Sorry. Sorry. But no. We're four people and we're "
                                    "only any good as four people, and if we split up "
                                    "we're four people who are each on their own.\"\n\n"
                                    "He goes slightly red and does not take it back.\n\n"
                                    "\"...He's right,\" Refender says. \"Note the "
                                    "date.\""
                                ),
                                "sets": {"c4_jofrog_objected": True},
                            },
                            {
                                "id": "c4_ask_what_he_counts",
                                "label": "\"What is he actually counting? That tells us what he does next.\"",
                                "text": (
                                    "Refender stops halfway through folding the map.\n\n"
                                    "\"Doors,\" she says. \"Kettleford said doors. Not "
                                    "people, not weapons — *doors*.\"\n\n"
                                    "\"He is establishing capacity. How much of a thing "
                                    "each place is.\" She sits down, which she does not "
                                    "do. \"He counted nineteen survey teams and returned "
                                    "eighteen of them because they came out the same way "
                                    "twice.\"\n\n"
                                    "\"We are about to find out what he does with a "
                                    "settlement that comes out the same way twice.\""
                                ),
                                "sets": {"c4_worked_out_the_counting": True},
                            },
                        ],
                    },
                    {
                        "requires": ["c3_took_the_ledger"],
                        "kind": "dialogue",
                        "speaker": "Refender",
                        "text": (
                            "\"We have his ledger,\" Refender says, and pulls it out of "
                            "the case she has not let out of her sight since Level R.\n\n"
                            "\"Every settlement in the region, with his own figures "
                            "against them. I have been reading it for six days and I was "
                            "reading it as *evidence*.\"\n\n"
                            "She opens it flat on the table.\n\n"
                            "\"It is not evidence. It is a **schedule**. And because we "
                            "took it off his desk, we now know the order he intends to do "
                            "them in — which he has presumably also worked out, and has "
                            "not changed.\"\n\n"
                            "\"Sixteen Freight is fourth.\""
                        ),
                    },
                    {
                        "kind": "reward",
                        "text": (
                            "Cascade sends everything it can spare in under four hours, "
                            "which is now simply how Cascade behaves and which nobody has "
                            "commented on since.\n\n"
                            "The H-Nation flatbed arrives at dusk with its plates taken "
                            "off, driven by a sergeant who says he is on leave and does "
                            "not appear to be."
                        ),
                        "grant": {"xp": 190, "gold": 9000, "item": "mythic", "evolution_fragments": 340,
                                  "shards": 600, "cores": 600, "lootbox": ("legendary", 3)},
                    },
                ],
            },

            {
                "id": "c4m2_the_yard",
                "name": "The Yard",
                "summary": "Sandbags, a washing line nobody has taken in, and two of them at the fence.",
                "beats": [
                    {
                        "kind": "dialogue",
                        "speaker": "Blueflame",
                        "text": (
                            "They arrive the way everything of his arrives: on foot, "
                            "unhurried, in daylight.\n\n"
                            "Two of them stop at the fence line and stand there, and one "
                            "of them begins working along it, counting.\n\n"
                            "\"It's doing the fence posts,\" Blueflame says. He has "
                            "stopped eating, which is the signal everyone now watches "
                            "for. \"It has counted forty-one fence posts. There are "
                            "forty-one fence posts.\"\n\n"
                            "\"That's the bit I can't get past. It's *right*. It's been "
                            "right about everything since the day we met it.\""
                        ),
                    },
                    {
                        "kind": "choice",
                        "prompt": (
                            "It has finished the fence. It has started on the vehicles. "
                            "Nobody has fired and it has not come through the wire."
                        ),
                        "options": [
                            {
                                "id": "c4_let_it_count",
                                "label": "*Let it finish. See what it does when it runs out of things.*",
                                "text": (
                                    "It counts the vans. It counts the sandbag "
                                    "emplacements. It counts the washing on the line, "
                                    "which takes it four seconds and which nobody in the "
                                    "yard will ever quite recover from.\n\n"
                                    "Then it turns to face the building, and stops, and "
                                    "does not move for two full minutes.\n\n"
                                    "\"It's stuck,\" Refender breathes. \"Something in "
                                    "here doesn't count.\""
                                ),
                                "sets": {"c4_let_it_count": True},
                            },
                            {
                                "id": "c4_open_first",
                                "label": "\"Don't let it finish the sheet. Open now.\"",
                                "text": (
                                    "The first shot takes the nearer one off its feet, "
                                    "and the second one does not react at all — it "
                                    "carries on down the fence line, counting, for "
                                    "another eleven posts before it turns.\n\n"
                                    "\"It finished the section,\" Josh says. \"We shot "
                                    "its partner and it *finished the section*.\""
                                ),
                                "sets": {"c4_opened_first": True},
                            },
                            {
                                "id": "c4_put_dolphin_out",
                                "label": "\"Dolphin. Walk out where it can see you.\"",
                                "text": (
                                    "It is a terrible idea and Dolphin does it before "
                                    "anybody can construct the argument against it.\n\n"
                                    "He walks to the middle of the yard in the coat and "
                                    "stands there with his hands out from his sides.\n\n"
                                    "The nearer machine stops counting. It looks at him "
                                    "for eleven seconds — everybody counts them "
                                    "afterwards and everybody agrees on eleven — and then "
                                    "it goes back to the fence and starts the section "
                                    "again from the beginning.\n\n"
                                    "\"It recounted,\" Refender says. \"It saw him and it "
                                    "went back and *recounted*.\""
                                ),
                                "sets": {"c4_used_dolphin_early": True},
                            },
                        ],
                    },
                    {
                        # 36% -- the chapter's floor, and the first time
                        # the player is defending rather than arriving.
                        "kind": "battle",
                        "enemies": ["Rohan's Warden", "Rohan's Warden"],
                        "level": 45,
                        "intro": (
                            "Whatever the sheet said, it is finished now.\n\n"
                            "They come through the wire together, and for the first time "
                            "in four chapters there is something behind you that you "
                            "cannot afford to lose — a shabby building with four camp "
                            "beds in it and a kettle that everybody has strong opinions "
                            "about."
                        ),
                        "on_win": (
                            "The yard holds. The fence does not, in two places, and the "
                            "washing line comes down in the second minute and nobody has "
                            "time to be sentimental about it until afterwards.\n\n"
                            "Jofrog picks the coat up out of the mud, and looks at it, "
                            "and hangs it back on the wire.\n\n"
                            "Nobody says anything, and everybody sees him do it."
                        ),
                        "on_lose": (
                            "They do not take the building.\n\n"
                            "They finish the count, and they leave, and the sheet goes "
                            "with them — which is the entire problem, because a sheet "
                            "that leaves is a sheet that gets acted on."
                        ),
                    },
                    {
                        "requires": ["c4_used_dolphin_early"],
                        "kind": "dialogue",
                        "speaker": "Refender",
                        "text": (
                            "Afterwards, Refender goes through the second machine's core "
                            "in the yard, in the rain, because she will not wait.\n\n"
                            "\"It recounted this site four times,\" she says. \"Four. "
                            "Every one of them after the moment he walked out.\"\n\n"
                            "She looks up.\n\n"
                            "\"It could not close the entry. It is not permitted to leave "
                            "an entry open, so it stayed, and kept counting, and did not "
                            "act — and while it did that we killed it.\"\n\n"
                            "A pause.\n\n"
                            "\"He is a *stall*. I am going to have to say that to his "
                            "face at some point and I am not looking forward to it.\""
                        ),
                    },
                    {
                        "kind": "reward",
                        "text": (
                            "Cascade's third van is still half-loaded because nobody has "
                            "had four consecutive minutes to finish unpacking it.\n\n"
                            "The manifest is taped inside the door in Refender's "
                            "handwriting, ticked to about a third, with a line at the "
                            "bottom in somebody else's:\n\n"
                            "*stopped ticking, sorry, we needed it.*"
                        ),
                        "grant": {"xp": 300, "gold": 10000, "item": "mythic", "evolution_fragments": 380,
                                  "shards": 700, "cores": 700, "lootbox": ("legendary", 3)},
                    },
                ],
            },

            {
                # NO FIGHT. The chapter's breath, and its second-best
                # scene. Rex has no memory and a great deal of muscle.
                "id": "c4m3_what_his_hands_remember",
                "name": "What His Hands Remember",
                "summary": "Nobody asked him to. He found the parts and started.",
                "beats": [
                    {
                        "kind": "dialogue",
                        "speaker": "Jofrog",
                        "text": (
                            "Jofrog finds him at four in the morning in the corner of the "
                            "Floor, with a bench light on and about nine hundred "
                            "components laid out in front of him.\n\n"
                            "They are laid out in the order you would use them.\n\n"
                            "\"He's been at it since two,\" Jofrog says, in the doorway, "
                            "not going in. \"He didn't ask anyone for anything. He went "
                            "and found the box of spares we took off Level A and he "
                            "started.\"\n\n"
                            "\"I asked him what it was. He said he didn't know yet.\""
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Rex",
                        "text": (
                            "\"It's going to be a receiver,\" Rex says, without looking "
                            "up, when you have been standing there a while.\n\n"
                            "\"I don't know how I know that. I know where the next bit "
                            "goes and I know it before I've thought about it, which is a "
                            "very strange way to spend an evening.\"\n\n"
                            "He seats a component, and it is exactly right, and his hands "
                            "do not hesitate once.\n\n"
                            "\"Somebody told me I built one before. The tall one who "
                            "keeps not looking at me.\" A pause. \"He's very careful "
                            "around me. Everybody is. It's like being a *vase*.\""
                        ),
                    },
                    {
                        "kind": "choice",
                        "prompt": (
                            "He has done in six hours what Refender estimated would take "
                            "a workshop three days."
                        ),
                        "options": [
                            {
                                "id": "c4_tell_him_who",
                                "label": "\"The tall one is Josh. You were friends for eleven years.\"",
                                "text": (
                                    "\"Eleven years,\" Rex repeats, and turns the number "
                                    "over the way he turns components over. \"That's a "
                                    "long time to be friends with somebody.\"\n\n"
                                    "\"I'm not going to remember him. I want to say that "
                                    "now, while I can say it kindly, because everyone "
                                    "here is waiting for me to and I can feel it.\"\n\n"
                                    "He goes back to the board.\n\n"
                                    "\"But he can come and sit down. I don't need to "
                                    "remember someone to want the company.\""
                                ),
                                "sets": {"c4_told_rex_about_josh": True},
                            },
                            {
                                "id": "c4_just_help",
                                "label": "*Sit down and hold the light steady for him.*",
                                "text": (
                                    "You hold the light. He works.\n\n"
                                    "Twice he says \"thanks\" without looking up, and "
                                    "once he says \"no, the other one — no, that one, "
                                    "yes\" before you have moved, because he saw where "
                                    "your hand was going.\n\n"
                                    "At about six he says, to the board rather than to "
                                    "you: \"This is the most like myself I've felt since "
                                    "I woke up in that chair.\"\n\n"
                                    "He does not elaborate and you do not ask him to."
                                ),
                                "sets": {"c4_held_the_light": True},
                            },
                            {
                                "id": "c4_ask_about_the_chair",
                                "label": "\"What do you remember? Honestly. Anything at all.\"",
                                "text": (
                                    "\"A desk,\" he says. \"A card. The top of the hour — "
                                    "I still feel the top of the hour, it's like a "
                                    "*tide*.\"\n\n"
                                    "He sets the iron down.\n\n"
                                    "\"And a second cup. Somebody put a second cup out "
                                    "and we didn't talk. Fourteen months and I don't "
                                    "think we ever talked. He'd just come and sit "
                                    "sometimes.\"\n\n"
                                    "He picks the iron back up.\n\n"
                                    "\"I don't know if that's a nice thing or the worst "
                                    "thing anybody's ever told you. From in here it's "
                                    "just Tuesday.\""
                                ),
                                "sets": {"c4_asked_rex_what_he_remembers": True},
                            },
                        ],
                    },
                    {
                        "requires": ["c1_looked_around_workshop"],
                        "kind": "dialogue",
                        "speaker": "Josh",
                        "text": (
                            "Josh comes in at seven, sees the bench, and stops in the "
                            "doorway exactly the way he stopped four metres short of the "
                            "south building a lifetime ago.\n\n"
                            "The tools are laid out in the order you would use them.\n\n"
                            "You have stood in a room laid out like this before, nine "
                            "hundred kilometres south, under a light that has been on for "
                            "two years — and so, you realise, has he, every day, without "
                            "ever going in.\n\n"
                            "\"That's how he does it,\" Josh says. \"That's exactly how "
                            "he does it.\"\n\n"
                            "He comes in and sits down."
                        ),
                    },
                    {
                        "kind": "reward",
                        "text": (
                            "By eight in the morning there is a working receiver on the "
                            "bench, and it is better than the one Cascade issued.\n\n"
                            "Refender examines it for a long time and then says, "
                            "carefully: \"This is not a copy of his old one. This is the "
                            "*next* one.\"\n\n"
                            "\"He has improved on a design he does not remember "
                            "producing.\""
                        ),
                        "grant": {"xp": 410, "gold": 11000, "item": "mythic", "evolution_fragments": 400,
                                  "cores": 700},
                    },
                ],
            },

            {
                "id": "c4m4_the_other_end",
                "name": "The Other End",
                "summary": "Rex's receiver finds where the audit reports to, and it is not Level R.",
                "beats": [
                    {
                        "kind": "dialogue",
                        "speaker": "Rex",
                        "text": (
                            "It takes the new receiver a day and a half to find them, "
                            "because there are three hundred and twelve of them and they "
                            "are extremely quiet.\n\n"
                            "\"They're not talking to each other,\" Rex says. \"That's "
                            "what took so long — I kept looking for a network. There "
                            "isn't one. They each report to the same place, one at a "
                            "time, in a rota.\"\n\n"
                            "He is enjoying himself, which nobody has the heart to "
                            "interrupt.\n\n"
                            "\"And it's not the place your lot came from. It's under it. "
                            "The signal's going *past* Level R and carrying on down.\""
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Refender",
                        "text": (
                            "\"Level C,\" Refender says. \"He labels downward, so C is "
                            "below R. That is not an alphabet, it is a *depth*.\"\n\n"
                            "She has the ledger open and is going through it fast.\n\n"
                            "\"Everything we have seen so far — the cut, the crates, the "
                            "line, three hundred Wardens — was on levels he had "
                            "**finished**. Swept. Squared. Rota on the wall.\"\n\n"
                            "\"I would like to see one he has not finished. I think it is "
                            "the only way any of us will ever learn anything about him "
                            "that he has not chosen to say.\""
                        ),
                    },
                    {
                        # 59%.
                        "kind": "battle",
                        "enemies": ["Rohan's Negadom"],
                        "level": 40,
                        "intro": (
                            "The audit notices.\n\n"
                            "Not the machines in the yard — the thing at the other end of "
                            "them. Eleven minutes after Rex locks onto the signal, "
                            "something comes up the access road that has not been "
                            "counting anything.\n\n"
                            "\"That's a response,\" Josh says, almost admiringly. "
                            "\"That's the first thing he's ever done in a hurry.\""
                        ),
                        "on_win": (
                            "It comes apart in the yard it was sent to, and the fence is "
                            "past saving, and the building is standing.\n\n"
                            "Rex, who has spent the entire fight in the doorway holding "
                            "his own receiver like a cat, says: \"It's still "
                            "transmitting. Down. It's telling him it lost.\"\n\n"
                            "\"Good,\" says Josh."
                        ),
                        "on_lose": (
                            "You wake to the sound of Rex's receiver still running, "
                            "because he carried it into cover and would not put it down.\n\n"
                            "\"I've still got the bearing,\" he says, before anybody asks. "
                            "\"I'm not clever, I just didn't let go.\""
                        ),
                    },
                    {
                        "kind": "reward",
                        "text": (
                            "They go north in six vehicles, in daylight, along a road "
                            "that has a fence-post count and a name.\n\n"
                            "Dolpo's people wave them through the gate without stopping "
                            "them, and then — for the first time in fifteen months — two "
                            "of the four fall in behind and come along."
                        ),
                        "grant": {"xp": 520, "gold": 12000, "item": "mythic", "evolution_fragments": 420,
                                  "shards": 700, "cores": 700, "lootbox": ("mythic", 2)},
                    },
                ],
            },

            {
                "id": "c4m5_the_open_entry",
                "name": "The Open Entry",
                "summary": "Level C is the first room down here that isn't finished.",
                "beats": [
                    {
                        "kind": "dialogue",
                        "speaker": "Refender",
                        "text": (
                            "Level C is untidy.\n\n"
                            "After three chapters of squared edges and swept concrete "
                            "that single fact does more work than any amount of "
                            "menace: there is a tally sheet abandoned mid-line, and a pen "
                            "on the floor where it was dropped rather than put down.\n\n"
                            "\"He has been interrupted,\" Refender says. \"Repeatedly. "
                            "For some time.\"\n\n"
                            "On the wall, a regional map more accurate than anything "
                            "Cascade owns. Every settlement counted, with a number.\n\n"
                            "Four are not. Beside one of them, a freight depot on the "
                            "wrong side of a ring road: *anomalous. recount.*"
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Dolphin",
                        "text": (
                            "Dolphin has found his own folder open on a stool, and he is "
                            "not touching it.\n\n"
                            "\"Three lines,\" he says. \"Added at three different times. "
                            "You can tell, the pen's different.\"\n\n"
                            "He reads them out flatly.\n\n"
                            "\"*Inventory does not resolve.*\"\n\n"
                            "\"*Second attempt: does not resolve.*\"\n\n"
                            "\"*Why.*\"\n\n"
                            "He looks up, and for once the coat and the voice and the "
                            "whole apparatus are simply not there.\n\n"
                            "\"That's the only time he's ever asked a question. In any of "
                            "it. Pages and pages and he *tells* you things — and the one "
                            "question in the whole lot is me.\""
                        ),
                    },
                    {
                        "kind": "choice",
                        "prompt": (
                            "It is the first advantage anybody has found in four chapters "
                            "and it is standing in front of you in a borrowed coat."
                        ),
                        "options": [
                            {
                                "id": "c4_dolphin_leads",
                                "label": "\"Then you go first. He can't close you, so he can't ignore you.\"",
                                "text": (
                                    "\"Right,\" says Dolphin. \"Yes. Great. Love it.\"\n\n"
                                    "He does not move for a second.\n\n"
                                    "\"I want to be clear I'm terrified, and I'm doing it "
                                    "anyway, and I would like at least one person to "
                                    "notice that those are two separate things.\"\n\n"
                                    "\"Noticed,\" says Refender, immediately."
                                ),
                                "sets": {"c4_dolphin_leads": True},
                            },
                            {
                                "id": "c4_refuse_to_use_him",
                                "label": "\"No. We're not using him as a key.\"",
                                "text": (
                                    "\"I'd like a say in that, actually,\" Dolphin says, "
                                    "and everybody stops.\n\n"
                                    "\"Everyone's been very kind about me the whole way "
                                    "up this road. Kind and — sort of *around* me. I've "
                                    "been in the van a lot.\"\n\n"
                                    "\"This is the one thing in the entire world that "
                                    "only I can do. You don't get to take that off me to "
                                    "be nice.\"\n\n"
                                    "Josh, of all people, is the first to nod."
                                ),
                                "sets": {"c4_tried_to_protect_dolphin": True},
                            },
                            {
                                "id": "c4_ask_dolphin",
                                "label": "\"Dolphin. What do you want to do?\"",
                                "text": (
                                    "Nobody has asked him that in four chapters and it "
                                    "visibly lands.\n\n"
                                    "\"I want to know what I am,\" he says. \"That's it. "
                                    "That's the whole thing. Everyone keeps trying to "
                                    "give me a nice answer and I don't want a nice one, I "
                                    "want the *right* one.\"\n\n"
                                    "He straightens the coat, which by now is a gesture "
                                    "everybody in the party can read.\n\n"
                                    "\"He's got the right one. So I'd like to go and ask "
                                    "him, please, and I would like all of you to come "
                                    "with me, because I'm not brave, I'm just out of "
                                    "patience.\""
                                ),
                                "sets": {"c4_asked_dolphin_what_he_wants": True},
                            },
                        ],
                    },
                    {
                        # 85% -- the step before the climax and a brutal
                        # one. Level C is the room he did not finish, and
                        # what is in it was not left as a guard: it was
                        # left mid-assembly.
                        "kind": "battle",
                        "enemies": ["Rohan's Catastrophe Soldier", "Rohan's Warden"],
                        "level": 43,
                        "intro": (
                            "The thing at the far end of Level C has been standing in a "
                            "half-built state on a cradle, and it comes off the cradle "
                            "before it is finished.\n\n"
                            "Panels are missing. You can see the works.\n\n"
                            "\"He's spending an unfinished one,\" Refender says. \"He has "
                            "never once spent anything unfinished.\""
                        ),
                        "on_win": (
                            "The half-built one goes down across its own cradle and takes "
                            "the tally sheet with it, and nobody picks the sheet up.\n\n"
                            "The last door on Level C is at the far end, and it is "
                            "open.\n\n"
                            "That is new. Every other door in this place has been shut, "
                            "and squared, and waiting."
                        ),
                        "on_lose": (
                            "You come round on Level C with the pen still on the floor "
                            "where it was dropped.\n\n"
                            "Nobody has tidied. Nobody has counted you. The room is "
                            "exactly as untidy as it was, which after four chapters is "
                            "the single most alarming thing it could be."
                        ),
                    },
                    {
                        "kind": "reward",
                        "text": (
                            "There is a bench on Level C with tools laid out in the order "
                            "you would use them.\n\n"
                            "Rex looks at it for a long time when he comes down. He does "
                            "not say anything about it, and nobody asks him to, and after "
                            "a while he squares one of the tools a quarter-inch and then "
                            "looks faintly embarrassed."
                        ),
                        "grant": {"xp": 630, "gold": 14000, "item": "mythic", "evolution_fragments": 460,
                                  "shards": 800, "cores": 800, "lootbox": ("mythic", 2)},
                    },
                ],
            },

            {
                "id": "c4m6_audit_paused",
                "name": "Audit Paused",
                "summary": "He has left the door open, which he has never done, and he would like to ask a question.",
                "beats": [
                    {
                        "kind": "dialogue",
                        "speaker": "Rohan",
                        "text": (
                            "He is not holding a clipboard.\n\n"
                            "That is the first thing anybody notices, and it takes a "
                            "moment to work out why it is unsettling: in four chapters "
                            "nobody has seen his hands empty.\n\n"
                            "\"You brought him,\" he says. To you, about Dolphin, without "
                            "any preamble at all.\n\n"
                            "\"I have run four hundred and six entries through this "
                            "region in nine days. Every one of them closed. He walks into "
                            "a yard and my unit recounts a fence four times and then "
                            "stands in a field until somebody destroys it.\"\n\n"
                            "\"I would like to know what he is. I am asking. I want it "
                            "noted that I am asking rather than establishing.\""
                        ),
                    },
                    {
                        "requires": ["c4_used_dolphin_early"],
                        "kind": "dialogue",
                        "speaker": "Refender",
                        "text": (
                            "\"You already know what happened in that yard,\" Refender "
                            "says. \"We used him. Deliberately. Once we understood.\"\n\n"
                            "\"Your machine could not close the entry, and it is not "
                            "permitted to leave one open, so it stood in a field and "
                            "recounted a fence while we killed it.\"\n\n"
                            "She lets that sit.\n\n"
                            "\"That is your whole method, and we found the end of it in "
                            "an afternoon, and it was standing in a coat.\""
                        ),
                    },
                    {
                        "kind": "choice",
                        "prompt": (
                            "He is waiting for an answer to a question he asked honestly, "
                            "which is the most dangerous thing he has ever done."
                        ),
                        "options": [
                            {
                                "id": "c4_he_is_a_person",
                                "label": "\"He's a person. That's the whole answer and it's why it doesn't resolve.\"",
                                "text": (
                                    "\"That is not sufficient,\" Rohan says. \"Four "
                                    "hundred and six people resolved.\"\n\n"
                                    "\"Then your inventory is wrong,\" you tell him, "
                                    "\"and it has been wrong four hundred and six "
                                    "times.\"\n\n"
                                    "For the first time since the prologue's south yard, "
                                    "he does not have an answer ready. He does not "
                                    "concede. He simply — stops, for about four seconds, "
                                    "in a way that no machine of his has ever managed."
                                ),
                                "sets": {"c4_told_him_person": True},
                            },
                            {
                                "id": "c4_you_returned_him",
                                "label": "\"You returned him. Whatever he is now, you made it.\"",
                                "text": (
                                    "\"Yes,\" he says, without hesitation. \"Two years "
                                    "ago, eleven kilometres from the end of this road. It "
                                    "was a standard disposition and it was performed "
                                    "correctly.\"\n\n"
                                    "\"Then it did not take, and I do not have a category "
                                    "for a disposition that does not take. I have "
                                    "attempted the inventory twice since. Both attempts "
                                    "produced a different result, which is not possible, "
                                    "and which I have now written down three times.\"\n\n"
                                    "\"You are describing something breaking,\" says "
                                    "Refender.\n\n"
                                    "\"I am describing something I do not understand. I "
                                    "accept that from your position those are the same "
                                    "sentence.\""
                                ),
                                "sets": {"c4_pressed_on_the_return": True},
                            },
                            {
                                "id": "c4_dolphin_answers",
                                "label": "*Step back. Let Dolphin answer him.*",
                                "text": (
                                    "\"I don't know what I am,\" Dolphin says. \"I came "
                                    "all this way to ask you and you've asked me first, "
                                    "which is honestly typical.\"\n\n"
                                    "\"But I'll tell you what I've got, since we're both "
                                    "short.\"\n\n"
                                    "He counts it off, and his voice does not shake, "
                                    "which is the bravest thing that happens in this "
                                    "chapter.\n\n"
                                    "\"Two years. A brother who isn't. A coat I picked. "
                                    "Four people who came up a road with me when they "
                                    "didn't have to.\"\n\n"
                                    "\"That's the inventory. That's all of it. If it "
                                    "doesn't resolve then your form's the wrong shape, "
                                    "mate, because I know exactly what I've got.\""
                                ),
                                "sets": {"c4_dolphin_answered_him": True},
                            },
                        ],
                    },
                    {
                        # THE CLIMAX -- 90%, the hardest fight in the
                        # story. Still not Rohan; the chapter's own text
                        # now makes that a characterisation rather than a
                        # limitation, because the one time he engages
                        # directly is the moment he stops being able to.
                        "kind": "battle",
                        "enemies": ["Rohan's Herald"],
                        "level": 43,
                        "intro": (
                            "\"I am going to have to stop this conversation,\" Rohan "
                            "says, and for the first time he sounds like somebody making "
                            "a decision rather than reading one out.\n\n"
                            "\"Not because of what you have said. Because of how long I "
                            "have been standing here having it.\"\n\n"
                            "He steps back through the open door.\n\n"
                            "What comes forward is the largest thing he has ever sent, "
                            "and it is not new — it is scarred, and repaired, and it has "
                            "been used."
                        ),
                        "on_win": (
                            "When it finally goes down, Level C is quiet, and the audit "
                            "is not.\n\n"
                            "Rex, in the doorway with his receiver, says: \"They've "
                            "stopped. All of them. Three hundred and twelve, at "
                            "once.\"\n\n"
                            "He listens for a while longer.\n\n"
                            "\"They're not withdrawing. They're just — standing there. "
                            "Every one of them has stopped counting and none of them has "
                            "been told what to do next.\"\n\n"
                            "The audit is not over. The audit is **paused**, which is a "
                            "thing that happens when the person running it has to go and "
                            "think."
                        ),
                        "on_lose": (
                            "You come round on Level C, and the pen is back on the desk, "
                            "and the tally sheet has been squared to the edge and "
                            "continued in the same hand.\n\n"
                            "The line it resumes on is not the one it stopped on. He went "
                            "back and started the column again."
                        ),
                    },
                    {
                        "requires": ["c4_dolphin_answered_him"],
                        "kind": "dialogue",
                        "speaker": "Dolphin",
                        "text": (
                            "On the lift back up, Dolphin is very quiet, and then says:\n\n"
                            "\"He wrote it down.\"\n\n"
                            "He has the folder. He took it off the stool on the way past "
                            "and nobody stopped him.\n\n"
                            "\"After I said all that. He went to the desk and he wrote it "
                            "down, and I watched him do it, and he wasn't — he wasn't "
                            "filing me. He was *taking a note*.\"\n\n"
                            "He closes the folder.\n\n"
                            "\"I've been an entry for two years. I think I've just been "
                            "an argument, and I'd quite like to sit down.\""
                        ),
                    },
                    {
                        "kind": "reward",
                        "text": (
                            "Three hundred and twelve machines stand still in nineteen "
                            "settlements for eleven days.\n\n"
                            "Cascade evacuates four villages in that window. The H-Nation "
                            "opens the northern road officially, which requires an act of "
                            "parliament and gets one in a week. Xender, who lost nineteen "
                            "teams and were never told why, send a single unmarked "
                            "aircraft that lands at Sixteen Freight, unloads without a "
                            "word, and leaves.\n\n"
                            "On the eleventh day, Rex's receiver picks up one "
                            "transmission going out to all three hundred and twelve at "
                            "once.\n\n"
                            "It is four words long: **resume. revised. begin again.**"
                        ),
                        "grant": {"xp": 750, "gold": 20000, "item": "mythic", "evolution_fragments": 600,
                                  "shards": 1200, "cores": 1200, "lootbox": ("mythic", 3)},
                    },
                ],
            },

            # ------------------------------------------------------------------
            # SIDE MISSION -- see the note on s1 for why `optional` matters.
            # ------------------------------------------------------------------
            {
                "id": "s4_the_photograph",
                "name": "The Photograph",
                "optional": True,
                "summary": "Six people outside a building that is not this one.",
                "beats": [
                    {
                        "kind": "dialogue",
                        "speaker": "Jofrog",
                        "text": ("Jofrog is standing in the bunks looking at the "
                                 "photograph on the bulkhead, and does not stop "
                                 "when you come in.\n\n"
                                 "\"Nine years,\" he says. \"Six of us. He's "
                                 "laughing in it. I've worked with that man for "
                                 "four years and I have never once seen him do "
                                 "that.\""),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Jofrog",
                        "text": ("\"Two of the six aren't here any more,\" he "
                                 "says. \"And before you ask — no, they didn't "
                                 "die. That's the bit nobody says out loud.\"\n\n"
                                 "\"They took work with Entrospire. Good work. "
                                 "Sensible work, with a pension. And then about a "
                                 "year later they stopped answering, and about a "
                                 "year after *that* the nineteen teams went "
                                 "quiet.\""),
                    },
                    {
                        "kind": "choice",
                        "prompt": "He has clearly been waiting to say this to somebody.",
                        "options": [
                            {
                                "id": "ask_if_josh_knows",
                                "label": "Ask whether Josh has made that connection.",
                                "text": ("\"Josh made it before I did,\" Jofrog "
                                         "says. \"Josh made it four years ago and "
                                         "has been carrying it around on his own "
                                         "ever since, because the alternative was "
                                         "telling the rest of us that two of our "
                                         "friends might be on the other side of "
                                         "this.\"\n\n"
                                         "\"That's why he founded the Aligners. "
                                         "Not because Cascade can't be trusted. "
                                         "Because he couldn't stand to be wrong "
                                         "about it in front of them.\""),
                                "sets": {"s4_josh_knew": True},
                            },
                            {
                                "id": "ask_their_names",
                                "label": "Ask what their names were.",
                                "text": ("He tells you. They are ordinary names, "
                                         "and he says both of them carefully, the "
                                         "way you say a word you have practised "
                                         "not stumbling over.\n\n"
                                         "\"I check the audit lists,\" he admits. "
                                         "\"Every one Rohan's people file. I've "
                                         "checked every list for four years and "
                                         "neither name has ever been on one, and I "
                                         "cannot decide whether that's good.\""),
                                "sets": {"s4_learned_the_names": True},
                            },
                            {
                                "id": "say_nothing_useful",
                                "label": "Admit you don't know what to say.",
                                "text": ("\"No,\" Jofrog agrees. \"There isn't "
                                         "anything. I've been looking for it for "
                                         "four years.\"\n\n"
                                         "He straightens the photograph on its "
                                         "hook, which does not need straightening, "
                                         "and goes back to work."),
                                "sets": {"s4_said_nothing": True},
                            },
                        ],
                    },
                    {
                        "kind": "reward",
                        "text": ("The photograph stays where it is. Somebody has "
                                 "been careful, over nine years, never to cut the "
                                 "other two out of it — and now you know that was "
                                 "a decision somebody made, and kept making."),
                        "grant": {"xp": 620, "gold": 34000, "evolution_fragments": 1200,
                                  "cores": 1700, "item": "mythic",
                                  "lootbox": ("mythic", 2)},
                    },
                ],
            },
        ],
    },

    # ======================================================================
    # CHAPTER FIVE — UNRESOLVABLE
    # ======================================================================
    #
    # WHAT THIS CHAPTER IS ABOUT: the revised audit stops counting and
    # starts disposing, and the counter-move is to attack the METHOD
    # rather than the machines -- because Dolphin has already proved the
    # method can fail.
    #
    # ----------------------------------------------------------------------
    # THE ANSWER AT THE BOTTOM, AND WHY IT IS SMALL
    # ----------------------------------------------------------------------
    # Rohan is not the origin of anything. He is an auditor who was sent,
    # four years ago, with a four-line instruction: *establish what is
    # there, report, await further.* He established. He has reported
    # every morning for four years into an outgoing tray with nothing to
    # send it with, and nothing has ever come back.
    #
    # He is not waiting for orders because he is loyal. He is doing the
    # only thing he was ever told to do, because the alternative is
    # deciding, and he has never once been asked to.
    #
    # That is deliberately NOT a cosmic reveal. Every room on the way
    # down got larger and better organised; the bottom is a box with a
    # desk in it. The two mugs, the clipboard, the tidiness, the returned
    # survey teams -- all of it resolves to a man doing a job nobody has
    # checked on in four years, and the horror is the scale of what that
    # job turned out to include.
    #
    # ----------------------------------------------------------------------
    # HE IS STILL NOT FOUGHT, AND NOW IT IS THE POINT
    # ----------------------------------------------------------------------
    # `Rohan` as a template measures 100% of a level-appropriate party at
    # EVERY level -- 20 against a level-42 squad included -- because he
    # carries 9,999 flat HP and four actions per cycle (see
    # tools/check_story.py's note on the auto-attack model). He is the
    # Abyssnia final boss and belongs there.
    #
    # Five chapters of not fighting him have made that a character fact
    # rather than a limitation, and this chapter closes it properly: the
    # thing that stops him is not damage. It is being handed something he
    # cannot file.
    # ======================================================================
    {
        "id": "chapter5",
        "name": "Chapter Five: Unresolvable",
        "blurb": "Resume. Revised. Begin again.",
        "unlocks_region": None,
        "missions": [
            {
                "id": "c5m1_revised",
                "name": "Revised",
                "summary": "The audit starts again, and it is not counting any more.",
                "beats": [
                    {
                        "kind": "dialogue",
                        "speaker": "Rex",
                        "text": (
                            "Rex has not left the receiver for eleven days. He has a "
                            "chair now, and a blanket, and a rota of people who bring him "
                            "things, and none of it has persuaded him to sleep more than "
                            "four hours at a stretch.\n\n"
                            "\"They've started,\" he says, at twenty past six in the "
                            "morning. \"All three hundred and twelve. Same second.\"\n\n"
                            "He listens.\n\n"
                            "\"It's different. Before, they each reported a number and "
                            "waited. This time they're not reporting anything.\"\n\n"
                            "He takes the headset off, which he never does.\n\n"
                            "\"They've already got the numbers. They're not counting. "
                            "They're *acting on it*.\""
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Refender",
                        "text": (
                            "The reports come in over four hours and Refender writes them "
                            "on the wall as they arrive, because there is no longer time "
                            "to file anything.\n\n"
                            "\"Two settlements evacuated ahead of contact — those are "
                            "ours, that is Cascade doing its job in under a day and I "
                            "will be grateful for it later.\"\n\n"
                            "\"Four have been *entered*. No casualties reported. People "
                            "walking out south in ones and twos with no memory of the "
                            "morning.\"\n\n"
                            "She caps the marker.\n\n"
                            "\"He is returning them. At scale. He has stopped assessing "
                            "the region and started **clearing** it, and he is doing it "
                            "the polite way, which is somehow the thing I find hardest to "
                            "hold.\""
                        ),
                    },
                    {
                        "requires": ["c4_dolphin_answered_him"],
                        "kind": "dialogue",
                        "speaker": "Dolphin",
                        "text": (
                            "Dolphin has the folder open on his knees. He has been "
                            "reading his own file for eleven days, on and off, the way "
                            "you worry at a tooth.\n\n"
                            "\"He wrote down what I said,\" he says. \"I watched him do "
                            "it. And now he's revised the whole thing eleven days "
                            "later.\"\n\n"
                            "He looks up, and he looks frightened, and he says it "
                            "anyway.\n\n"
                            "\"I think I did this. I think I told him his form was the "
                            "wrong shape and he went away and got a *better form*.\""
                        ),
                    },
                    {
                        "kind": "choice",
                        "prompt": (
                            "Four settlements entered before lunch. Whatever the answer "
                            "is, it is not going to be reached by driving somewhere."
                        ),
                        "options": [
                            {
                                "id": "c5_not_your_fault",
                                "label": "\"You didn't cause this. You showed us the crack in it.\"",
                                "text": (
                                    "\"That is the correct reading and I want to reinforce "
                                    "it,\" Refender says immediately, before Dolphin can "
                                    "get anywhere.\n\n"
                                    "\"He revised because his method failed. His method "
                                    "failed because it *is* fallible. You did not make it "
                                    "fallible, you made it visible, and those are not the "
                                    "same and I will not have them treated as such in this "
                                    "building.\""
                                ),
                                "sets": {"c5_reassured_dolphin": True},
                            },
                            {
                                "id": "c5_use_the_crack",
                                "label": "\"Then we widen it. If one unresolvable person stops a machine, make more.\"",
                                "text": (
                                    "There is a silence of a very particular kind — the "
                                    "one where four people have all had the same thought "
                                    "and are waiting to see who is mad enough to say "
                                    "it.\n\n"
                                    "\"...Go on,\" says Refender, slowly.\n\n"
                                    "\"We cannot make people forget who they are. That is "
                                    "his trick and I would rather lose.\"\n\n"
                                    "\"But an inventory is a *form*. And a form does not "
                                    "care whether an answer is true. It only cares whether "
                                    "it fits in the box.\""
                                ),
                                "sets": {"c5_proposed_the_jam": True},
                            },
                            {
                                "id": "c5_kettleford",
                                "label": "\"Kettleford. It's ninety people and it's next on his list.\"",
                                "text": (
                                    "Josh has the ledger open before you finish the "
                                    "sentence.\n\n"
                                    "\"Fourth,\" he says. \"It was fourth on his schedule "
                                    "and we have had eleven days to think about that and "
                                    "we thought about *us*.\"\n\n"
                                    "He is already moving.\n\n"
                                    "\"We can be there in ninety minutes. Cascade can't. "
                                    "That's the whole argument for existing that we've "
                                    "ever had — let's go and be right about it.\""
                                ),
                                "sets": {"c5_chose_kettleford": True},
                            },
                        ],
                    },
                    {
                        "kind": "reward",
                        "text": (
                            "The yard empties in six minutes. Jofrog counts everyone into "
                            "the vehicles by name, twice, and then a third time, and "
                            "nobody tells him to stop."
                        ),
                        "grant": {"xp": 210, "gold": 16000, "item": "mythic", "evolution_fragments": 500,
                                  "shards": 900, "cores": 900, "lootbox": ("mythic", 2)},
                    },
                ],
            },

            {
                "id": "c5m2_kettleford",
                "name": "Kettleford",
                "summary": "Ninety people, one square, and something already halfway through the job.",
                "beats": [
                    {
                        "kind": "dialogue",
                        "speaker": "Josh",
                        "text": (
                            "Kettleford is a square, a chapel, a shop and about thirty "
                            "houses, and there is a queue in the middle of it.\n\n"
                            "That is the thing nobody is able to process for the first "
                            "several seconds. Not a panic. A **queue** — ninety people, "
                            "in a line, waiting their turn, because the machine at the "
                            "front of it has been polite and clear and has told them "
                            "this will not hurt.\n\n"
                            "\"It's asked them to form up,\" Josh says. \"It's asked "
                            "them, and they've *done* it, because it's the first thing in "
                            "two years that's turned up and explained itself.\""
                        ),
                    },
                    {
                        "kind": "choice",
                        "prompt": (
                            "Forty of the ninety have already been through. They are "
                            "sitting on the chapel steps, calm, pleasant, and unable to "
                            "say what village this is."
                        ),
                        "options": [
                            {
                                "id": "c5_break_the_queue",
                                "label": "\"Break the queue. Get between it and the rest of them.\"",
                                "text": (
                                    "It is not heroic and it does not look like anything: "
                                    "four people walking into the middle of a line and "
                                    "standing there.\n\n"
                                    "The queue does not disperse. Somebody near the front "
                                    "asks, politely, whether you are jumping in, and it is "
                                    "the single worst sentence anybody hears all "
                                    "chapter."
                                ),
                                "sets": {"c5_broke_the_queue": True},
                            },
                            {
                                "id": "c5_talk_to_them",
                                "label": "\"Talk to them. Tell them what's happening to them.\"",
                                "text": (
                                    "It half works, which is worse than not working.\n\n"
                                    "About twenty leave the line. About forty do not, "
                                    "because a stranger in a muddy coat shouting about "
                                    "memory is a less convincing thing than a calm machine "
                                    "that has answered every question it was asked.\n\n"
                                    "\"They're not stupid,\" Refender says, tightly. "
                                    "\"They are being reasonable with the information "
                                    "available and the information available is *him*.\""
                                ),
                                "sets": {"c5_talked_to_the_queue": True},
                            },
                            {
                                "id": "c5_get_the_processed",
                                "label": "\"Leave the queue. Get the forty on the steps out first.\"",
                                "text": (
                                    "It is the colder call and it is probably the right "
                                    "one: the forty on the steps cannot make decisions for "
                                    "themselves any more and the ninety in the line still "
                                    "can.\n\n"
                                    "Jofrog does it. He walks up to the chapel steps and "
                                    "says, to forty people who do not know where they "
                                    "are, \"Right — everyone follow me, we're going to go "
                                    "and have a sit down,\" and forty people get up and "
                                    "follow him, because somebody finally told them what "
                                    "to do next."
                                ),
                                "sets": {"c5_saved_the_processed": True},
                            },
                        ],
                    },
                    {
                        # 42% -- the chapter's floor, in a village square.
                        "kind": "battle",
                        "enemies": ["Rohan's Catastrophe Soldier"],
                        "level": 54,
                        "intro": (
                            "The thing at the head of the queue stops what it is doing, "
                            "and turns, and — this is the part that stays with everyone — "
                            "it asks the next person in line to wait a moment.\n\n"
                            "Then it comes across the square.\n\n"
                            "\"It said *excuse me*,\" Blueflame says, with no cheer at "
                            "all. \"It said excuse me to a farmer.\""
                        ),
                        "on_win": (
                            "It goes down in the middle of a village square with ninety "
                            "people watching, and the square is completely silent, and "
                            "then somebody starts crying and then a great many people do.\n\n"
                            "Forty of them will not be told why they are upset. They are "
                            "upset anyway, which Refender notes down, in the van, "
                            "afterwards, with her jaw set.\n\n"
                            "\"Something is left,\" she says. \"He does not get all of "
                            "it.\""
                        ),
                        "on_lose": (
                            "It finishes the queue.\n\n"
                            "It is unhurried and it is courteous and at the end of it "
                            "ninety people walk south in ones and twos, and Kettleford is "
                            "still standing, and there is nobody in it who can tell you "
                            "what it was called."
                        ),
                    },
                    {
                        "kind": "reward",
                        "text": (
                            "Cascade arrives forty minutes later with four vehicles and "
                            "an entire mobile clinic, and Dolphe is in the second van, "
                            "which is not where the head of an organisation is supposed to "
                            "be.\n\n"
                            "He does not ask anybody for a report. He starts carrying "
                            "boxes."
                        ),
                        "grant": {"xp": 340, "gold": 18000, "item": "mythic", "evolution_fragments": 540,
                                  "shards": 1000, "cores": 1000, "lootbox": ("mythic", 2)},
                    },
                ],
            },

            {
                # NO FIGHT. Two clever people and a whiteboard, and it is
                # the hinge of the entire chapter.
                "id": "c5m3_the_shape_of_the_form",
                "name": "The Shape Of The Form",
                "summary": "Refender and Rex have been arguing about a form for nine hours.",
                "beats": [
                    {
                        "kind": "dialogue",
                        "speaker": "Refender",
                        "text": (
                            "They have been at it since Kettleford and the wall of the "
                            "Floor is now entirely covered.\n\n"
                            "\"His method is an inventory,\" Refender says. \"Establish "
                            "what a thing is, and dispose accordingly. Everything he has "
                            "ever done follows from that sentence.\"\n\n"
                            "\"An inventory needs an answer that CLOSES. Eighteen teams "
                            "closed. One did not, because Rex knew something that could "
                            "not be separated from him.\"\n\n"
                            "She taps the third column.\n\n"
                            "\"And one man in a borrowed coat did not close, twice, and "
                            "his machine stood in a field recounting a fence until we "
                            "killed it.\""
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Rex",
                        "text": (
                            "\"So don't fight the machines,\" Rex says. \"Fight the "
                            "*form*.\"\n\n"
                            "He has been drawing the same diagram for an hour and it has "
                            "got simpler each time, which Refender says is how you can "
                            "tell he is right.\n\n"
                            "\"Every unit reports what it establishes. The report has to "
                            "close. If it can't close, the unit can't act — it stands "
                            "there and recounts, we've watched it happen.\"\n\n"
                            "He underlines something.\n\n"
                            "\"His receiver's mine. I mean — it's the same design, I've "
                            "seen the boards, whoever built his was working off the same "
                            "idea I was.\" A pause; he does not chase it. \"Point is I "
                            "know exactly what shape it wants. And I can send it "
                            "something that fits in the box and doesn't resolve.\""
                        ),
                    },
                    {
                        "kind": "choice",
                        "prompt": (
                            "It is a jamming signal made of paperwork. Nobody in the room "
                            "can decide whether that is brilliant or humiliating."
                        ),
                        "options": [
                            {
                                "id": "c5_ask_if_it_hurts",
                                "label": "\"Does it hurt anyone? Ours or his?\"",
                                "text": (
                                    "\"No,\" says Rex. \"That's why I like it.\"\n\n"
                                    "\"It doesn't break anything. It doesn't take anything "
                                    "off anybody. It just puts an entry in front of every "
                                    "unit in the region that they can't finish, and they "
                                    "*stop*, because stopping is what they do when they "
                                    "can't finish.\"\n\n"
                                    "\"It's not a weapon. It's an unanswerable "
                                    "question.\""
                                ),
                                "sets": {"c5_asked_if_it_hurts": True},
                            },
                            {
                                "id": "c5_whats_the_catch",
                                "label": "\"What's the catch? There's always a catch with him.\"",
                                "text": (
                                    "\"It works once,\" Refender says. \"He revised his "
                                    "whole method in eleven days after one man confused "
                                    "one unit. This will buy us hours, not a "
                                    "settlement.\"\n\n"
                                    "\"And it tells him precisely where the transmitter "
                                    "is, which will be a room with all of us in it.\"\n\n"
                                    "\"Then it wants to be somewhere we're going anyway,\" "
                                    "says Josh."
                                ),
                                "sets": {"c5_asked_the_catch": True},
                            },
                            {
                                "id": "c5_dolphin_content",
                                "label": "\"What do we actually put in the box?\"",
                                "text": (
                                    "Everybody looks at Dolphin, who has been sitting on "
                                    "the table pretending not to listen for nine "
                                    "hours.\n\n"
                                    "\"Oh,\" he says. \"Right. Yeah. Me.\"\n\n"
                                    "\"It's my file. Word for word, the bit he wrote down "
                                    "after I talked at him — the coat, the brother who "
                                    "isn't, the four people who came up a road with me.\" "
                                    "He shrugs, and it very nearly works. \"He couldn't "
                                    "file it the first time. I've been carrying the only "
                                    "thing in the world he can't put in a box, and it's a "
                                    "list of what I've got.\""
                                ),
                                "sets": {"c5_dolphin_is_the_payload": True},
                            },
                        ],
                    },
                    {
                        "requires": ["c4_asked_rex_what_he_remembers"],
                        "kind": "dialogue",
                        "speaker": "Rex",
                        "text": (
                            "Late on, when it is mostly finished, Rex says — to the "
                            "board, not to anyone:\n\n"
                            "\"You asked me once what I remembered. I said a desk, a "
                            "card, the top of the hour and a second cup.\"\n\n"
                            "He sets the pen down.\n\n"
                            "\"I've been thinking about the second cup for a fortnight. "
                            "He never talked to me. Fourteen months and he never once "
                            "talked to me, he just came and sat.\"\n\n"
                            "\"I don't think he was guarding me. I think I was the only "
                            "entry down there he could stand to be in a room with.\""
                        ),
                    },
                    {
                        "kind": "reward",
                        "text": (
                            "It takes a day and a half to build, and it fits in a case "
                            "the size of a toolbox, and Rex will not let anybody else "
                            "carry it.\n\n"
                            "Refender writes the operating instructions out by hand, in "
                            "duplicate, and gives one copy to Dolphe and keeps one, "
                            "because she has never in her life trusted a single copy of "
                            "anything."
                        ),
                        "grant": {"xp": 470, "gold": 20000, "item": "mythic", "evolution_fragments": 600,
                                  "cores": 1000},
                    },
                ],
            },

            {
                "id": "c5m4_unresolvable",
                "name": "Unresolvable",
                "summary": "Level C, a transmitter, and one entry nobody can close.",
                "beats": [
                    {
                        "kind": "dialogue",
                        "speaker": "Rex",
                        "text": (
                            "They set it up on Level C, in the untidy room, because it is "
                            "the only place in the region with a clear line to every unit "
                            "at once.\n\n"
                            "The tally sheet is still on the floor where the half-built "
                            "one fell on it. Nobody has picked it up. Nobody ever "
                            "will.\n\n"
                            "\"Right,\" says Rex, with his hands on the case. \"When I "
                            "send this, three hundred and twelve units in nineteen "
                            "settlements are going to be handed an entry they can't "
                            "close.\"\n\n"
                            "\"And every one of them is going to stop, and stand there, "
                            "and recount.\"\n\n"
                            "He looks up.\n\n"
                            "\"And then he's going to come and find out why.\""
                        ),
                    },
                    {
                        "requires": ["c5_dolphin_is_the_payload"],
                        "kind": "dialogue",
                        "speaker": "Dolphin",
                        "text": (
                            "Dolphin reads it out himself, into the microphone, because "
                            "Rex says the transmitter wants a voice and everybody else in "
                            "the room says nothing at all.\n\n"
                            "It takes ninety seconds. It is his own file, in his own "
                            "words, said out loud to three hundred and twelve machines "
                            "and one man.\n\n"
                            "When he gets to *four people who came up a road with me when "
                            "they didn't have to*, his voice does not go, which everybody "
                            "notices and nobody mentions until much later, when they will "
                            "not shut up about it."
                        ),
                    },
                    {
                        # 68%.
                        "kind": "battle",
                        "enemies": ["Rohan's Negadom"],
                        "level": 46,
                        "intro": (
                            "The response takes four minutes, which is the fastest he has "
                            "ever done anything.\n\n"
                            "It does not come down the lift. It comes through the wall of "
                            "Level C — the unfinished wall, the one he never got round to "
                            "— because that was always the shortest route and he has "
                            "never once taken a longer one."
                        ),
                        "on_win": (
                            "The transmitter survives, which was the entire point, and "
                            "Rex is lying on top of it when the room stops moving.\n\n"
                            "\"Still sending,\" he says, muffled. \"Still sending, still "
                            "sending — somebody help me up, I've done my back.\"\n\n"
                            "Across nineteen settlements, three hundred and twelve "
                            "machines have stopped in the middle of what they were doing, "
                            "and are recounting."
                        ),
                        "on_lose": (
                            "The transmitter survives. Rex saw to that before anything "
                            "else, including himself.\n\n"
                            "You come round to the sound of it still running, and to "
                            "Jofrog saying, very steadily, to somebody who is not "
                            "answering: \"That's it. That's it. You're alright.\""
                        ),
                    },
                    {
                        "kind": "reward",
                        "text": (
                            "The lift at the back of Level C has been standing open since "
                            "the wall came in.\n\n"
                            "The counter above it starts at C and runs down through nine "
                            "more letters, and the last one is not in any alphabet "
                            "Refender has seen — and she has, as she points out, seen "
                            "several.\n\n"
                            "\"He came up through a wall rather than use it,\" she says. "
                            "\"I would like everybody to hold on to that when we get to "
                            "the bottom.\""
                        ),
                        "grant": {"xp": 600, "gold": 22000, "item": "mythic", "evolution_fragments": 640,
                                  "shards": 1100, "cores": 1100, "lootbox": ("mythic", 3)},
                    },
                ],
            },

            {
                "id": "c5m5_the_last_letter",
                "name": "The Last Letter",
                "summary": "Eleven floors down there is a small room with a desk in it.",
                "beats": [
                    {
                        "kind": "dialogue",
                        "speaker": "Refender",
                        "text": (
                            "The lift takes eleven minutes.\n\n"
                            "Every level it passes is finished: swept, lit, racked, "
                            "rota'd. Level after level of a job done properly by somebody "
                            "with nobody to show it to.\n\n"
                            "The bottom is a small room.\n\n"
                            "That is all it is. After four chapters of descending through "
                            "rooms that got bigger and better organised, the last letter "
                            "is a box about the size of the Mess at Cascade Central, with "
                            "a desk in it, and nothing else running."
                        ),
                    },
                    {
                        "kind": "dialogue",
                        "speaker": "Josh",
                        "text": (
                            "There is an outgoing tray on the desk and it is full.\n\n"
                            "Reports, in order, sealed and addressed and stacked. The "
                            "oldest is dated four years ago. The newest is from this "
                            "morning.\n\n"
                            "None of them have been sent, because there is nothing down "
                            "here to send them with.\n\n"
                            "Josh works through the stack without touching the seals, and "
                            "when he gets to the bottom he sits down on the floor, which "
                            "is not a thing he does.\n\n"
                            "\"He's been writing to somebody for four years,\" he says. "
                            "\"Every morning. And putting it in a tray.\""
                        ),
                    },
                    {
                        "kind": "choice",
                        "prompt": (
                            "There is an incoming tray on the other side of the desk. It "
                            "is empty. It has been dusted."
                        ),
                        "options": [
                            {
                                "id": "c5_read_the_instruction",
                                "label": "*Read the sheet under the glass.*",
                                "text": (
                                    "It is the only object down here anybody has bothered "
                                    "to protect.\n\n"
                                    "It is four years old, it is four lines long, and it "
                                    "is in a hand that is not his:\n\n"
                                    "*Establish what is there. Report. Await further.*\n\n"
                                    "There is no further.\n\n"
                                    "There has never, in four years, been any further."
                                ),
                                "sets": {"c5_read_the_instruction": True},
                            },
                            {
                                "id": "c5_open_a_report",
                                "label": "*Open one of the sealed reports.*",
                                "text": (
                                    "Refender takes one from the middle of the stack and "
                                    "opens it, and reads it standing up, and her face does "
                                    "something nobody in the party has seen before.\n\n"
                                    "\"It is a **survey**,\" she says. \"Rainfall. Crop "
                                    "yields. Population figures for nineteen settlements, "
                                    "with a note about the state of the roads.\"\n\n"
                                    "\"It is *thorough*. It is the most competent piece of "
                                    "regional administration I have ever held.\"\n\n"
                                    "She puts it back in the tray, squared to the edge, "
                                    "which she does not appear to notice doing."
                                ),
                                "sets": {"c5_opened_a_report": True},
                            },
                            {
                                "id": "c5_look_at_the_room",
                                "label": "*Just look at the room.*",
                                "text": (
                                    "A desk. Two trays. A chair. A kettle, and a tray "
                                    "beside it with two mugs on it, one used and one put "
                                    "out ready.\n\n"
                                    "No screens. No maps. Nothing on the walls at all.\n\n"
                                    "Eleven floors of the most organised operation any of "
                                    "you has ever seen, and the man running it works at a "
                                    "desk in an empty room and has done for four years."
                                ),
                                "sets": {"c5_looked_at_the_room": True},
                            },
                        ],
                    },
                    {
                        # 73%.
                        "kind": "battle",
                        "enemies": ["Rohan's Herald"],
                        "level": 46,
                        "intro": (
                            "He is not in the room. The Herald is.\n\n"
                            "It is standing beside the desk in the manner of a thing that "
                            "has been left on guard by somebody who did not expect to need "
                            "one, and it moves the moment anybody touches the outgoing "
                            "tray.\n\n"
                            "\"It's not defending him,\" Josh says. \"It's defending the "
                            "**post**.\""
                        ),
                        "on_win": (
                            "It falls across the desk and takes the outgoing tray with "
                            "it, and four years of unsent reports go across the floor of a "
                            "small room at the bottom of eleven letters.\n\n"
                            "Nobody picks them up either.\n\n"
                            "Behind the desk there is one more door, and it is standing "
                            "open, and there is light on the other side of it."
                        ),
                        "on_lose": (
                            "You come round on the floor of a small room with the reports "
                            "back in the tray, in order, and the tray squared to the edge "
                            "of the desk.\n\n"
                            "The mug that was out ready has been washed. Outside first."
                        ),
                    },
                    {
                        "kind": "reward",
                        "text": (
                            "Dolphin picks one report up off the floor, and looks at the "
                            "address on it for a long time, and does not read it out.\n\n"
                            "Later, in the van, he will say only that it was addressed to "
                            "a place, not a person, and that he had never heard of the "
                            "place."
                        ),
                        "grant": {"xp": 730, "gold": 24000, "item": "mythic", "evolution_fragments": 700,
                                  "shards": 1200, "cores": 1200, "lootbox": ("mythic", 3)},
                    },
                ],
            },

            {
                "id": "c5m6_nothing_to_file",
                "name": "Nothing To File",
                "summary": "He has stopped writing, which he has not done in four years.",
                "beats": [
                    {
                        "kind": "dialogue",
                        "speaker": "Rohan",
                        "text": (
                            "The room behind the door is the same size as the first one "
                            "and has nothing in it but a chair.\n\n"
                            "He is sitting in it, and he is not holding anything, and he "
                            "has stopped writing.\n\n"
                            "\"Three hundred and twelve units are recounting a single "
                            "entry,\" he says. \"They have been recounting it for nine "
                            "hours. They will recount it until I tell them to stop and I "
                            "have not been able to construct the instruction.\"\n\n"
                            "He looks up.\n\n"
                            "\"It is a list of what a man has. I have read it four hundred "
                            "times. There is nothing in it I can dispute and nothing in "
                            "it I can file.\""
                        ),
                    },
                    {
                        "requires": ["c5_read_the_instruction"],
                        "kind": "dialogue",
                        "speaker": "Refender",
                        "text": (
                            "\"*Establish what is there. Report. Await further.*\"\n\n"
                            "Refender says it flatly, from memory, and it lands like "
                            "something dropped.\n\n"
                            "\"Four years. Four years of the best regional administration "
                            "I have ever seen, into a tray, with nothing to send it "
                            "with.\"\n\n"
                            "\"Nobody is coming. You know that. You have known it for at "
                            "least three of those years and you have carried on writing "
                            "every morning, because the alternative was to decide "
                            "something yourself and you have never once been asked "
                            "to.\"\n\n"
                            "He does not deny it. He does not do anything at all for "
                            "several seconds, which from him is an admission."
                        ),
                    },
                    {
                        "kind": "choice",
                        "prompt": (
                            "He is waiting. For the first time in five chapters, nobody "
                            "in the room is certain he knows what happens next."
                        ),
                        "options": [
                            {
                                "id": "c5_offer_the_answer",
                                "label": "\"Then decide something. Start with the ninety people in Kettleford.\"",
                                "text": (
                                    "\"I do not have the authority to—\"\n\n"
                                    "\"You have three hundred and twelve machines and "
                                    "eleven floors and *nobody has written to you in four "
                                    "years*,\" you tell him. \"There is nobody left to "
                                    "have the authority. There is only you, and what you "
                                    "do next.\"\n\n"
                                    "He is quiet for a very long time.\n\n"
                                    "\"That is not an instruction,\" he says, at last, and "
                                    "it is almost a complaint.\n\n"
                                    "\"No,\" says Josh. \"It's the other thing. Took me "
                                    "two years as well.\""
                                ),
                                "sets": {"c5_told_him_to_decide": True},
                            },
                            {
                                "id": "c5_demand_the_returns",
                                "label": "\"Give back what you can. Start there and we'll talk about the rest.\"",
                                "text": (
                                    "\"What is removed is not stored,\" he says, and it is "
                                    "the same sentence he used two chapters ago, and it "
                                    "costs him something to repeat it.\n\n"
                                    "\"But the *files* exist. Four hundred and six of "
                                    "them, complete, with photographs and origins and "
                                    "next of kin.\"\n\n"
                                    "A pause.\n\n"
                                    "\"I cannot give a man back his memory. I can tell "
                                    "ninety people in Kettleford what their village is "
                                    "called and who they came home to. That is not "
                                    "restitution. It is a filing exercise.\"\n\n"
                                    "\"It's a start,\" says Jofrog. \"Do that one.\""
                                ),
                                "sets": {"c5_demanded_the_files": True},
                            },
                            {
                                "id": "c5_dolphin_last_word",
                                "label": "*Step back one last time.*",
                                "text": (
                                    "\"You've read my list four hundred times,\" Dolphin "
                                    "says.\n\n"
                                    "\"Yes.\"\n\n"
                                    "\"Do you want to know the bit that would've closed "
                                    "it?\"\n\n"
                                    "Rohan actually leans forward, which is the most "
                                    "undignified thing he has done in five chapters.\n\n"
                                    "\"You'd have had to ask me,\" Dolphin says. \"Not "
                                    "assess me. *Ask* me. It's a different form and you've "
                                    "never once had it in stock.\"\n\n"
                                    "And Rohan says, quietly: \"...No. I have not.\""
                                ),
                                "sets": {"c5_dolphin_had_the_last_word": True},
                            },
                        ],
                    },
                    {
                        # ============================================
                        # THE FIGHT THE WHOLE STORY IS FOR.
                        # ============================================
                        # Five chapters of not fighting him, and this is
                        # where that ends -- against "Rohan, At The
                        # Desk", a template written for exactly this
                        # scene (see bot/game/combat/enemies.py).
                        #
                        # The Abyssnia `Rohan` cannot be used here and it
                        # is not a matter of tuning: measured against a
                        # fully-kitted, geared level-45 party he has
                        # 46,556 HP against ~92 damage a hit, which is a
                        # hundred and twenty-six cycles to kill something
                        # that kills you in two. Sixty times too strong,
                        # not sixty percent.
                        #
                        # This one is measured to be a real fight at the
                        # level the story ITSELF now delivers. The story
                        # grants 12,000 XP across five chapters, which
                        # lands a story-only player at character level 40
                        # exactly, and at level 40 this fight costs 73%
                        # of the party's health with an 88% win rate.
                        # Under-levelled players genuinely lose; the
                        # curve is in the enemies.py comment.
                        "kind": "battle",
                        "enemies": ["Rohan, At The Desk"],
                        "level": 30,
                        "intro": (
                            "The door at the back of the room opens, and he does not look "
                            "round at it.\n\n"
                            "\"I did not send for that,\" he says.\n\n"
                            "\"Then stop it,\" says Refender.\n\n"
                            "\"It has a standing instruction. It has had it for four "
                            "years. I have never revoked one.\"\n\n"
                            "And then, quietly, as the thing comes through:\n\n"
                            "\"...No. That is not good enough, is it.\"\n\n"
                            "He puts the pen down. He squares it to the edge of the desk. "
                            "He stands up, and he steps between you and the door, and for "
                            "the first time in four years Rohan does something himself.\n\n"
                            "\"I will deal with my own equipment. You will not enjoy it "
                            "and neither will I.\""
                        ),
                        "on_win": (
                            "He goes down once and gets up, because of course he does — "
                            "and the second time he stays down, sitting rather than "
                            "falling, with his back against his own desk.\n\n"
                            "Everybody in the party is still standing. After five "
                            "chapters and eleven floors it is the only ending anybody "
                            "would have accepted.\n\n"
                            "He looks at the wreckage of the last thing he had running, "
                            "and then at his hands, which are shaking, and which he "
                            "observes with what appears to be professional "
                            "curiosity.\n\n"
                            "Then he reaches up to the desk, finds the pen without "
                            "looking, and writes one line — and it is not a report, "
                            "because he addresses it to nobody, and it is four words "
                            "long.\n\n"
                            "**All units: stand down.**"
                        ),
                        "on_lose": (
                            "You come round in the outer room with the reports back in "
                            "the tray and somebody's coat over you.\n\n"
                            "Nothing has been taken. Nothing has been counted.\n\n"
                            "Through the door, a pen is moving. It has not stopped.\n\n"
                            "You will have to come back stronger, and everybody in the "
                            "party knows it, and Jofrog is already working out what you "
                            "need."
                        ),
                    },
                    {
                        "requires": ["c5_dolphin_had_the_last_word"],
                        "kind": "dialogue",
                        "speaker": "Rohan",
                        "text": (
                            "As you leave he says, to Dolphin, without getting up:\n\n"
                            "\"What is your name.\"\n\n"
                            "Not *what are you*. Four years of establishing what things "
                            "are, eleven floors of it, four hundred and six closed "
                            "entries — and the first question he has ever asked a person "
                            "is that one.\n\n"
                            "\"Dolphin,\" says Dolphin. \"It's not the one I was born "
                            "with. I picked it.\"\n\n"
                            "\"...Yes,\" says Rohan. \"I see.\"\n\n"
                            "He does not write it down."
                        ),
                    },
                    {
                        "kind": "reward",
                        "text": (
                            "Three hundred and twelve machines stand down inside four "
                            "minutes, and stay down.\n\n"
                            "The files come out over six weeks — four hundred and six of "
                            "them, carried up eleven floors by hand, sorted by Cascade, "
                            "cross-checked by the H-Nation and delivered by whoever could "
                            "be spared. Ninety people in Kettleford are told what their "
                            "village is called.\n\n"
                            "Nobody gets their memory back. Refender is careful to write "
                            "that down first, before anything else, so that no report of "
                            "this ever reads like a happy ending.\n\n"
                            "Rohan is still down there. He has not been arrested, because "
                            "nobody can work out who would have the authority, and he has "
                            "not left, and every morning he writes something and puts it "
                            "in a tray.\n\n"
                            "The difference is that Refender goes down once a month now, "
                            "and takes it away with her, and reads it.\n\n"
                            "There are two mugs on the tray. Somebody uses the second "
                            "one."
                        ),
                        "grant": {"xp": 850, "gold": 40000, "item": "mythic", "evolution_fragments": 1000,
                                  "shards": 2000, "cores": 2000, "lootbox": ("mythic", 4)},
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
