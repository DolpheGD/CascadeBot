"""
An identity emoji for every enemy in the game.

WHY A MAP AND NOT A TEMPLATE FIELD. The alternative was adding an
`"emoji"` key to 173 template literals, 148 of which live inside a single
3,500-line list in enemies.py -- the file scripted edits have destroyed
working code in twice in this project's history. ENEMY_SHORT_NAMES
already established the pattern of keying per-enemy display data by name
from outside that literal, and this is the same kind of data for the same
reason.

WHAT THE EMOJI IS FOR. A combat screen is a wall of similar-looking
lines, and the enemy name is the only thing distinguishing them. A glyph
in front of each one makes a five-enemy room scannable at a glance --
which of these is the drone, which is the medic, which is the big one --
before any of the words are read.

HOW THEY WERE CHOSEN, since "does not need to be unique" is not the same
as "does not matter":

  * MECHANIC FIRST where the enemy has a signature one. The medics are
    all 💉, the shielders all 🛡️, the artillery 📡. A player who learns
    "💉 means it heals" gets that for free on every medic in the game,
    which is worth more than a hundred and seventy-three distinct
    pictures.
  * FACTION SECOND. Xender's people trend 📡🚁🎥, Acatrya's ⚔️🎖️,
    Entrospire's Deepworks 🏭⚙️🔧 -- so a lineup reads as a group rather
    than as a list.
  * BOSSES GET SOMETHING WEIGHTIER than their minions on purpose: 👑💀🐉
    rather than another drone glyph, so the boss line is visibly the boss
    line.

DIVERSITY IS CHECKED, NOT ASSUMED. tools/check_enemy_emoji.py asserts
full coverage and a floor on how many distinct glyphs are in use, because
the failure mode here is not a missing emoji -- it is quietly ending up
with 🤖 on a hundred and forty of them.
"""

from __future__ import annotations

# Fallback by role, used only when a name is missing from the map below.
# tools/check_enemy_emoji.py fails on any template that needs one, so
# these should never actually render -- they exist so that a template
# added tomorrow degrades to a sensible glyph instead of a blank.
ROLE_FALLBACK: dict[str, str] = {
    "combat": "👾",
    "elite": "🔱",
    "boss": "👑",
    "boss_group_member": "🗡️",
}

ENEMY_EMOJI: dict[str, str] = {
    # ==================================================================
    # COMBAT
    # ==================================================================
    # -- drifters, scavengers, people -------------------------------
    "Wandering Vagrant": "🧟",
    "Josh Imitator": "🎭",
    "Wasteland Rebel": "🔥",
    "Corrupted Wastelander": "🧟",
    "Undercity Scavenger": "🦝",
    "Josh Hater": "😡",
    "Romain's Body Pillow": "🛏️",
    "67": "🔢",
    "Training Dummy": "🎯",

    # -- Xender's outfit: surveillance and signals ------------------
    "Xender Henchmen": "🕶️",
    "Xender Enforcer": "🥊",
    "Xender Command Relay": "📡",
    "Xender Recon Scout": "🔭",
    "Xender Loyalist": "🎖️",
    "Xender Aerial Soldier": "🪂",
    "Xender Spy Camera": "🎥",
    "False Advertising Billboard": "📢",
    "Ad-Drone Swarm Unit": "📣",

    # -- Acatrya: soldiers and field support ------------------------
    "Acatrya Riot Trooper": "🛡️",
    "Acatrya Field Medic": "💉",
    "H-Nation Border Trooper": "🎖️",
    "Skyline Enforcer": "🏙️",
    "Corporate Security Mech": "🤖",
    "Tower Maintenance Bot": "🔧",
    "Bulwark Sentinel": "🛡️",
    "Wastes Fieldmedic": "💉",

    # -- machines and drones ----------------------------------------
    "Rogue Security Drone": "🚁",
    "Molten Turret": "🌋",
    "Scrap Buggy": "🛻",
    "Permafrost Automaton": "❄️",
    "Ocellios Failed Prototype": "🧪",
    "Sacrificial Construct": "🗿",
    "Concussion Drone": "💥",
    "Reclamation Swarm": "🐝",
    "Quality Assurance Drone": "📋",

    # -- void, entropy and the strange ------------------------------
    "Rohan's Bomb": "💣",
    "Thedoggyp's gem": "💎",
    "Dune Digger": "🏜️",
    "Glacial Piercer": "🧊",
    "Voidcrest Skitterer": "🕷️",
    "Xendium Lab Soldier": "🧫",
    "Entropy Executor": "⌛",
    "Entropy Aura Generator": "🌀",
    "Voidcell Amplifier": "🔆",
    "Choir of Ledgers": "📜",
    "Rustlung Crawler": "🦠",
    "Duneglass Stalker": "🏜️",
    "Hollow Auditor": "🧾",
    "Nullwrit Enforcer": "📕",
    "Cinderveil Acolyte": "🕯️",

    # -- Entrospire Deepworks: industry -----------------------------
    "Entrospire Soldier": "⚙️",
    "Deepworks Intake Arm": "🦾",
    "Sorting Frame": "📦",
    "Deepworks Welder": "🔥",
    "Line Supervisor Unit": "📋",
    "Reclaimed Surveyor": "📐",
    "Coolant Wraith": "💨",
    "Deepworks Hauler": "🚛",
    "Choir Conduit": "🔌",

    # -- The Voidlands ----------------------------------------------
    "Void Splinter": "🕳️",
    "Unmaking Wisp": "🌫️",
    "Rift Stalker": "🌑",
    "Null Warden": "🛡️",
    "Echo Of The Lost": "👻",
    "Collapse Herald": "📉",

    # -- specialists ------------------------------------------------
    "Slagjaw Breaker": "🔋",
    "Overpressure Cell": "🧨",
    "The Opportunist": "🗡️",
    "Shear Foreman": "🔨",
    "Ranging Officer": "📡",
    "Understudy Medic": "💉",

    # ==================================================================
    # ELITE
    # ==================================================================
    "Xender Tank": "🛡️",
    "Voidwarp Construct": "🌀",
    "Illusion of Rex": "🎭",
    "H-Nation Vanguard": "⚔️",
    "Ocellios Test Subject": "🧪",
    "Xendium Overcharge Drone": "⚡",
    "Glacial Exterminator": "❄️",
    "Permafrost Guardian": "🧊",
    "Wasteland Colosseum Champion": "🏆",
    "Sir Vengeance": "🗡️",
    "The Giveaway": "🎁",
    "Corrupted Eris Sentry": "👁️",
    "Acatrya Elite Guard": "⚔️",
    "Propaganda Broadcast Unit": "📢",
    "Skybridge Sentinel": "🌉",
    "Ashplate Warden": "🌋",
    "Abyssal Custodian": "🔱",
    "Blightspire Adept": "☣️",
    "Shatterjaw Reaver": "🦈",
    "MianotAI": "🧠",
    "Kiradmj": "🎧",
    "The Revengeance Block": "🧱",
    "Alan": "🙂",
    "Xender Convoy": "🚚",
    "Jynxzi": "🎮",
    "Xender Airship": "🛩️",
    "HHyper Airship": "✈️",
    "Refense Hater": "😤",
    "Frostblock": "🧊",
    "Rohan's Warden": "🗝️",
    "Hater Ringleader": "📣",
    "Rohan's Assessor": "🧮",
    "The Censor": "🚫",
    "Eris Sentinel": "👁️",
    "Stubby's Failsafe": "🔒",
    "Shift Foreman ANNEAL": "🔥",
    "Shift Foreman QUENCH": "💧",
    "The Night Shift": "🌙",
    "Retooling Gantry": "🏗️",
    "Inventory Reconciler": "🧾",
    "Dolpo's Old Rig": "🛠️",
    "Overpressure Ram": "🐏",
    "Field Chaplain Unit": "⛪",
    "The Gathering Absence": "🕳️",
    "Entropy Marshal": "⌛",
    "Archivist Of Unbeing": "📚",
    "The Full Measure": "⚖️",
    "Sanitation Unit 9": "🧼",
    "Choir Of Small Debts": "🩸",
    "Bulwark Shift": "🛡️",
    "Deepworks Regulator": "🎚️",

    # ==================================================================
    # BOSS -- weightier glyphs than their minions, on purpose
    # ==================================================================
    "XG-23 Heavy Drone": "🛸",   # not 🚁 -- its XG-23A/B escorts own that
    "Boss John's Driller Prototype": "🛢️",
    "SAJ II": "🤖",
    "Aerion Mk1": "🛩️",
    "Corrupted Bli": "☣️",
    "Thedoggyp": "🐕",
    "Triv": "🎲",
    "Void Hydra": "🐉",
    "NF": "🎤",
    "X-RR": "☄️",
    "Boss John": "🎩",
    "Rohan's Catastrophe Soldier": "💀",
    "Acatrya Prime Enforcer": "⚔️",
    "Xender": "👑",
    "Rohan's Negadom": "🌘",   # not 🌑 -- its Negadom Destroyer escorts own that
    "Samuel": "🗿",
    "Bt03": "🤖",
    "Rohan": "👑",
    "Rohan, At The Desk": "🪑",
    "Dorve": "🦂",
    "Rohan's Herald": "📯",
    "The Chairman": "🎩",
    "Floor Manager PRIME": "🏭",
    "The Process": "♾️",
    "The Hollow Choir": "🎼",
    "Nullstone Bastion": "🗿",
    "The Unmaking": "🕳️",
    "Cascade Failure": "⚡",
    "The Long Arrears": "🧾",

    # ==================================================================
    # BOSS GROUP MEMBERS -- escorts. Kept visually lighter than the boss
    # they arrive with, so the dangerous one still reads as dangerous.
    # ==================================================================
    "XG-23A": "🚁",
    "XG-23B": "🚁",
    "Dolpo": "🔧",
    "Xero": "❄️",
    "THE BILLIAN": "💰",
    "Loona": "🌙",
    "Ocellios Train": "🚂",
    "Broskm": "🥊",
    "Duko": "🎺",
    "Borehole": "🕳️",
    "Rupture": "💥",
    "Gatekeeper": "🚪",
    "Exiled Acid": "🧪",
    "Exiled APS": "🔌",
    "Exiled JP": "📎",
    "Negadom Destroyer": "🌑",
    "Josh Hater Ringleader": "📣",
    "Chant Leader": "🗣️",
    "Placard Bearer": "🪧",
    "Megaphone Guy": "📢",
    "The Quiet Hater": "🤐",
    "Mech Gunpod": "🔫",
}


# The Conclave's glyphs live with their templates and are merged in here,
# so a content module stays self-contained -- adding an enemy and adding
# its glyph are one edit in one file rather than two files that can drift.
from bot.game.combat.enemies_conclave import CONCLAVE_EMOJI  # noqa: E402

ENEMY_EMOJI.update(CONCLAVE_EMOJI)

from bot.game.combat.enemies_expansion import EXPANSION_EMOJI  # noqa: E402

ENEMY_EMOJI.update(EXPANSION_EMOJI)

from bot.game.combat.enemies_apex import APEX_EMOJI  # noqa: E402

ENEMY_EMOJI.update(APEX_EMOJI)

from bot.game.combat.enemies_ocellios import OCELLIOS_EMOJI  # noqa: E402

ENEMY_EMOJI.update(OCELLIOS_EMOJI)


def emoji_for(name: str, role: str = "combat") -> str:
    """The glyph for `name`, falling back by role.

    Never returns empty: a missing emoji would render as a stray space in
    front of the name, which looks like a bug rather than like an absence.
    """
    return ENEMY_EMOJI.get(name) or ROLE_FALLBACK.get(role, "👾")
