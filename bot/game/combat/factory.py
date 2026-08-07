"""
Combatants are built once at battle start and thrown away when it ends --
nothing here is persisted (except the HP snapshot combat_service takes
back out afterward). This is the only place that needs to know how
PlayerCharacter + InventoryItem + kit registries map onto Combatant.

Combat Overhaul: every squad member (including the player's own avatar) is
built the same way via build_character_combatant() -- one Combatant per
PlayerCharacter. There is no more single "the player" Combatant; a full
battle now runs build_party_combatants() for up to 4 squad members against
1-3 (or more, for tougher encounters) enemy Combatants.

Stat resolution order (important for the "flat vs percent substats"
design): percent-based substats are always computed against the
CHARACTER'S pure base stat at their current level (before any gear), never
against another item's bonus -- so equipping several items that each roll
"+10% attack" all add the same absolute amount; they never compound with
each other.

Ability resolution per character:
  * character_skill (mana) + character_ultimate (energy, 100) -- always
    present, resolved from the kit registries (bot/game/combat/skills.py)
    by class (for the switchable avatar) or by the character's fixed
    skill_id/ultimate_id (for pulled characters).
  * weapon_skill -- from the equipped WEAPON's active_ability, if any.
  * artifact_skill -- from the equipped ARTIFACT's active_ability, if any.
  * passives -- from the equipped ARMOR/ACCESSORY's passive_ability, if any.
"""

from __future__ import annotations

import math

from bot.database.models.enums import ItemType
from bot.game.combat.combatant import STAT_KEYS, ULTIMATE_COOLDOWN, Combatant
from bot.game.combat.enemies import short_name_for
from bot.game.economy.resonance_config import bonus_total, resonance_for
from bot.game.combat.skills import (
    get_character_passive,
    get_character_skill,
    get_character_ultimate,
    get_class_kit,
)

# ---------------------------------------------------------------------
# Balance pass -- across-the-board enemy rework (see bot/game/combat/
# enemies.py's module docstring for the full picture). Applied uniformly
# here in build_enemy_combatant rather than hand-edited onto every one of
# the ~40 templates in enemies.py, so the whole roster moves together and
# stays easy to retune from one place. Three things happen per enemy, all
# keyed off the template's "role":
#
#   1. DEFENSE_MULTIPLIER -- enemies were too easy to punch through even
#      before the K-value change in formulas.py; every role gets more DEF
#      than its authored base_stats value, elites most of all so a hit
#      that shreds a normal enemy doesn't equally shred an elite.
#   2. ELITE_POWER_MULTIPLIER -- elites were weaker than a standalone boss
#      AND weaker than a small congregation of normal enemies, which is
#      backwards for a 1-per-fight "meaningfully tougher" encounter (see
#      enemies.py's role docstring). ATK/ELE/HP all get a real bump;
#      normal "combat"-role enemies get a smaller version of the same
#      bump so a pack of them stays a genuine threat too, without eclipsing
#      what an elite room now brings.
#   3. ATTACK_RAMP_PERCENT_PER_TURN_BY_ROLE -- replaces the old innate
#      per-turn HP regen (a permanent, battle-long HealOverTime every
#      enemy used to get for free). Regen let a sufficiently tanky enemy
#      out-sustain a party that couldn't quite burst through it, so a fight
#      could grind on forever with neither side able to close it out.
#      Instead, every enemy's own turns now feed a small, PERMANENT
#      (never expires, never resets) attack/elemental ramp -- see
#      Combatant.ramp_stacks / effective_stat in combatant.py. It's tuned
#      to be unnoticeable across a normal-length fight and only becomes a
#      real factor if a fight runs unusually long, at which point it
#      gradually forces a conclusion instead of letting either side
#      stalemate indefinitely. Bosses/elites ramp faster, both because
#      they're the templates most likely to be in a drawn-out fight and to
#      keep pace with their own now-higher DEF making them harder to
#      burst down cleanly.
# ---------------------------------------------------------------------
DEFENSE_MULTIPLIER_BY_ROLE = {
    "combat": 1.3,
    "elite": 1.4,
    "boss": 1.2,
    "boss_group_member": 1.05,
}
ELITE_POWER_MULTIPLIER = {"attack": 1.4, "elemental": 1.6, "max_hp": 1.2}
NORMAL_POWER_MULTIPLIER = {"attack": 1.5, "elemental": 1.7, "max_hp": 1.4}
ATTACK_RAMP_PERCENT_PER_TURN_BY_ROLE = {
    "combat": 1.0,
    "elite": 1.4,
    "boss": 1.2,
    "boss_group_member": 1.1,
}

# ---------------------------------------------------------------------
# Poise pools by role (see the Poise/Break block in combatant.py and the
# tuning constants in effects.py). Derived from role here rather than
# authored per-template so the whole existing ~90-template roster gets the
# mechanic without a 1,600-line edit; any individual template can still
# override it with an explicit "max_poise" key.
#
# Values are in HITS, not damage, since poise damage counts actions (1 per
# basic attack, 2 per skill, 3 per ultimate, and once per hit/target for
# multi-hit/AOE).
#
# TUNED AGAINST SIMULATION -- specifically against BREAK FREQUENCY, which
# 400-fight batches measure reliably, and NOT against win rate, which they
# don't: win rate turned out to be extremely sensitive to how the sim's
# stand-in for gear was calibrated (a "50% baseline" over 60 seeds became
# 100% over 400), so any win-rate number from it is noise dressed as data.
# Frequency is also the design-legible target: how often a break is
# available is what decides whether the mechanic is a recurring decision
# or a once-a-fight novelty.
#
# At these values a full 4-person squad sees roughly one break every 5-6
# cycles on an elite or boss -- 1-2 per fight -- and the sim's AI is
# deliberately unsophisticated about poise (it fires whatever ability is
# off cooldown rather than favouring the multi-hit and AOE kinds that chip
# hardest), so a player who understands the system will break meaningfully
# faster than these numbers suggest. That gap is intentional headroom:
# it's the skill expression the mechanic exists to create.
#
# What this does to actual difficulty still wants real playtesting -- the
# sim can say "a break happens about this often", not "fights are now this
# much easier".
#
# Trash mobs (role "combat") sit low on purpose: breaking them should be
# incidental, something that just happens while you clear, not a decision.
# The decision lives on elites and bosses, where a break actually denies a
# telegraphed heavy hit worth denying.
# ---------------------------------------------------------------------
POISE_BY_ROLE = {
    "combat": 6,
    "elite": 12,
    "boss": 16,
    "boss_group_member": 12,
}
DEFAULT_POISE = 8

# ---------------------------------------------------------------------
# Percent-stat scaling for enemies.
#
# crit_rate / crit_damage / recharge are PERCENTAGES, and running them
# through the full level curve produced nonsense: a template with 18%
# crit reached 81% by level 45 and 153% -- every hit, always -- by 95,
# with crit damage compounding to 1789%. Players are explicitly excluded
# from scaling these (see base_character_stats: "gear's job to move"),
# so a level-95 player fought at ~6% crit against an enemy at 153%.
#
# They aren't cut to zero growth either, though, and that's deliberate:
# enemies have no gear, so this scaling is their ONLY substitute for the
# crit/recharge a player accumulates from equipment over 100 levels.
# Removing it entirely made every test composition win 100%.
#
# So: scale at a fraction of the normal curve, then hard-cap. The caps
# are what actually matter -- they keep a late-game enemy meaningfully
# more dangerous than an early one while guaranteeing it can never
# out-crit a geared player or exceed "crits about half the time".
#
# Surfaced by the new paged ℹ️ Info view, which shows every combatant's
# real stats for the first time. The numbers were always this wrong;
# there was simply nowhere in the game to see them.
# ---------------------------------------------------------------------
PERCENT_STAT_SCALE_FACTOR = 0.25
PERCENT_STAT_CAPS = {"crit_rate": 50, "crit_damage": 300, "recharge": 60}


# ----------------------------------------------------------------------
# LEVELS GET BIGGER AS YOU CLIMB, INSTEAD OF SMALLER
# ----------------------------------------------------------------------
# Character growth was purely linear: every level added the same flat
# amount forever. Linear growth against a base that starts small has a
# specific, bad feel, and it is exactly the reported one -- "HP gains a
# lot at the start but then plateaus". Level 2 adds ~7% of a 5-star's
# health bar; level 90 adds under 1% of it. Nothing about the numbers
# changes, but the player's sense of progress falls away to nothing
# precisely when the content gets hardest.
#
# It also left levels as the weakest of the three power sources. Gear
# multiplies, resonance multiplies, and levelling added a constant --
# so "should I level this character or farm one more item" had the same
# answer every time, and the answer wasn't levelling.
#
# Both of those are the same fix: a multiplier that grows WITH the level,
# applied on top of the authored linear growth. Late levels are then
# worth more than early ones in absolute terms, which is what makes the
# climb feel like a climb, and it gives max HP a curve that can keep pace
# with the enemy attack curve instead of falling behind it by a factor of
# five.
#
# ANCHORED AT LEVEL 1, so it can only ever add. At the levels Glacier 15
# is played at this is worth a few percent (level 8 -> 1.06x) and the
# region the balance is judged against does not meaningfully move; by
# level 100 it is 1.79x on top of linear, which is the point.
#
# Deliberately applied to the whole stat block rather than to max HP
# alone. HP-only would fix the plateau and leave levelling still not
# worth doing -- a character who only gets tankier as they level is not a
# character who is getting stronger.
LEVEL_POWER_PER_LEVEL = 0.008


def level_power_multiplier(level: int) -> float:
    """Compounding-ish bonus for character level. Exactly 1.0 at level 1."""
    return 1 + LEVEL_POWER_PER_LEVEL * max(0, int(level or 1) - 1)


def base_character_stats(player_character) -> dict:
    """Template base stats + growth to the character's current level.

    Only HP/ATK/DEF/ELE/MP/SPD grow with level (per the leveling spec:
    crit rate/damage/recharge stay put and are gear's job to move). The
    authored growth is linear; level_power_multiplier then scales the
    result so higher levels are worth progressively more -- see the block
    above for why."""
    template = player_character.template
    levels = max(0, player_character.level - 1)
    power = level_power_multiplier(player_character.level)
    return {
        "attack": (template.base_attack + template.growth_attack * levels) * power,
        "defense": (template.base_defense + template.growth_defense * levels) * power,
        "elemental": (template.base_elemental + template.growth_elemental * levels) * power,
        "speed": (template.base_speed + template.growth_speed * levels) * power,
        "max_hp": (template.base_hp + template.growth_hp * levels) * power,
        "max_mana": (template.base_mana + template.growth_mana * levels) * power,
        "crit_rate": template.base_crit_rate,
        "crit_damage": template.base_crit_damage,
        "recharge": template.base_recharge,
    }


def _resolve_gear_stats(base_stats: dict, equipped_items: list) -> dict:
    """Combines pure character base stats with every equipped item's flat
    and percent contributions. Percent substats are computed once against
    `base_stats` (the pre-gear values), then added as a flat amount -- they
    never compound with other items' bonuses."""
    final_stats = dict(base_stats)

    for item in equipped_items:
        for stat in STAT_KEYS:
            final_stats[stat] += item.total_stat_bonus_flat(stat)

    for item in equipped_items:
        for stat in STAT_KEYS:
            percent = item.percent_substats_for(stat)
            if percent:
                final_stats[stat] += base_stats.get(stat, 0) * percent / 100

    return final_stats


def _gear_abilities(equipped_items: list) -> tuple[dict | None, dict | None, list]:
    """Returns (weapon_skill, artifact_skill, passive_abilities) from
    whatever's equipped. WEAPON/ARTIFACT hold at most one item each, so at
    most one weapon_skill/artifact_skill wins (last one iterated, though in
    practice there's only ever one). ARMOR/ACCESSORY hold up to two items
    each (see enums.SLOT_CAPACITY), and every one of them contributes its
    passive_ability -- so a character can have up to 4 passives from gear."""
    weapon_skill = None
    artifact_skill = None
    passive_abilities: list = []

    for item in equipped_items:
        if item.item_type == ItemType.WEAPON and item.active_ability:
            weapon_skill = dict(item.active_ability)
            weapon_skill["source"] = "weapon"
            weapon_skill["source_item"] = item.display_name
        elif item.item_type == ItemType.ARTIFACT and item.active_ability:
            artifact_skill = dict(item.active_ability)
            artifact_skill["source"] = "artifact"
            artifact_skill["source_item"] = item.display_name
        elif item.item_type == ItemType.ARMOR and item.passive_ability:
            passive = dict(item.passive_ability)
            passive["source_item"] = item.display_name
            passive_abilities.append(passive)

    return weapon_skill, artifact_skill, passive_abilities


def build_character_combatant(player_character, equipped_items: list) -> Combatant:
    """`equipped_items` should be that character's InventoryItems where
    is_equipped is True (fetch and filter by character_id before calling)."""
    template = player_character.template
    base_stats = base_character_stats(player_character)
    final_stats = _resolve_gear_stats(base_stats, equipped_items)

    effective_class = player_character.effective_class()
    if template.is_player_avatar:
        kit = get_class_kit(effective_class)
        character_skill, character_ultimate = kit["skill"], kit["ultimate"]
        character_passive = kit.get("passive")
    else:
        character_skill = get_character_skill(template.skill_id)
        character_ultimate = get_character_ultimate(template.ultimate_id)
        character_passive = get_character_passive(template.passive_id)

    weapon_skill, artifact_skill, passive_abilities = _gear_abilities(equipped_items)
    if character_passive:
        passive = dict(character_passive)
        passive["source"] = "character"
        passive_abilities.append(passive)

    active_abilities = []
    if character_skill:
        ability = dict(character_skill)
        ability["source"] = "character"
        active_abilities.append(ability)
    if weapon_skill:
        active_abilities.append(weapon_skill)
    if artifact_skill:
        active_abilities.append(artifact_skill)

    ultimate_ability = None
    if character_ultimate:
        ultimate_ability = dict(character_ultimate)
        ultimate_ability["source"] = "character"
        ultimate_ability["is_ultimate"] = True

    # RESONANCE -- what duplicate copies of this character bought (see
    # bot/game/economy/resonance_config.py). Applied HERE, after gear and
    # before the Combatant is built, so every one of its effects lands on
    # the final numbers and nothing downstream needs to know it exists.
    resonance = resonance_for(getattr(player_character, "dupe_count", 1))
    if resonance > 0:
        _apply_resonance(resonance, final_stats, active_abilities, ultimate_ability)

    max_hp = round(final_stats["max_hp"])
    max_mana = round(final_stats["max_mana"])

    # If the character has HP persisted from a previous battle (see
    # PlayerCharacter.current_hp / the HP-persistence display change),
    # start there instead of full -- clamped down in case max_hp SHRANK
    # (a cursed relic, regearing) since it was last saved.
    #
    # The lower bound is 0, not 1. It used to be max(1, ...), which had
    # two visible consequences, both wrong:
    #
    #   1. A character who died was stored at 0 (sync_party_hp_to_characters
    #      writes the real value) but rebuilt at 1, so every view that
    #      builds a Combatant -- the profile page, the dungeon map's squad
    #      HP lines -- reported a dead character as being on 1 HP.
    #   2. Worse, it was a free revival. Expedition HP persists BETWEEN
    #      fights in a run, so a character who died in one room came back
    #      at 1 HP for the next room's fight, every time, at no cost.
    #      Death inside a run was effectively "you're at 1 HP now".
    #
    # Nothing needs the clamp: every entry point that starts a fresh
    # fight resets the squad to full first (start_expedition, and now
    # domain_service/raid_service too), and a party wiped mid-expedition
    # ends the run rather than continuing with 0-HP members.
    starting_hp = getattr(player_character, "current_hp", None)
    starting_hp = max_hp if starting_hp is None else max(0, min(starting_hp, max_hp))

    return Combatant(
        name=player_character.display_name,
        is_player=True,
        base_stats=final_stats,
        current_hp=starting_hp,
        max_hp=max_hp,
        character_id=player_character.id,
        character_class=effective_class.value,
        mana=max_mana,
        max_mana=max_mana,
        energy=0,
        max_energy=50,
        active_abilities=active_abilities,
        ultimate_ability=ultimate_ability,
        passive_abilities=passive_abilities,
        level=getattr(player_character, "level", 1) or 1,
    )


# Effect keys carrying a MAGNITUDE that Resonance 4 scales.
#
# An explicit allowlist rather than "scale every number in the dict", and
# the exclusions are the interesting part -- three kinds of key look like
# magnitudes and must not be touched:
#
#   * COUNTS and DURATIONS (duration, hits, max_stacks). Scaling a
#     3-turn buff to 3.54 turns is not the upgrade the level advertises,
#     and `hits` decides how many times a multi-hit ability resolves.
#   * CHANCES (debuff_chance_percent, dot_chance_percent,
#     poise_chance_percent). Reliability is a different axis from power,
#     and these can pass 100.
#   * SELF-COSTS (self_cost_percent, hp_threshold_percent). Scaling these
#     UP would make Resonance 4 a straight DOWNGRADE -- Bee Jee's
#     sacrifice_hp_team_buff would cost her 17.7% of her HP instead of
#     15% for the same buff.
#
# The allowlist was built by enumerating every numeric key actually used
# across all 24 character kits, not by guessing: the first version of it
# missed base_damage_percent and bonus_damage_percent_at_zero_hp, which
# silently made R4 do NOTHING AT ALL for Josh -- a dead level on the
# roster's flagship DPS, invisible unless someone diffed his skill
# numbers before and after. tools/check_resonance.py now asserts every
# character's R4 changes something.
_KIT_MAGNITUDE_KEYS = (
    # damage
    "damage_percent", "damage_percent_per_hit", "base_damage_percent",
    "bonus_damage_percent", "bonus_damage_percent_at_zero_hp",
    "execute_damage_percent", "dot_percent",
    # healing, shielding, and generic percent-of-max-HP effects
    "percent", "heal_percent", "shield_percent", "percent_max_hp_per_turn",
    # buffs and debuffs (debuffs are negative, so scaling deepens them)
    "buff_percent", "buff_percent_1", "buff_percent_2",
    "debuff_percent", "debuff_percent_1", "debuff_percent_2",
    "percent_per_stack",
    # resources handed to the team
    "energy_amount", "mana_amount",
)

# Poise magnitudes, scaled by Resonance 4 like everything else but ROUNDED
# UP rather than to two decimals.
#
# Poise is counted in whole hits, and these values are small -- Nyrvite's
# ultimate chips 5. An 18% increase is 5.9, which as a fractional poise
# chip is worth nothing the player can see. Ceiling makes it 6, an
# actually-different number of hits.
#
# Nyrvite is the reason this exists at all: her ultimate deals NO damage,
# healing, shielding or buffing -- it is pure poise -- so before this she
# was the one character on the roster whose Resonance 4 had nothing to
# scale, and the break specialist getting no benefit from "hits harder"
# is exactly backwards.
_KIT_POISE_KEYS = ("poise_damage", "bonus_poise")


def _resonance_damage_stat(abilities: list[dict], ultimate: dict | None) -> str:
    """Which stat Resonance 1 should boost: whichever one this character's
    own kit actually scales from.

    Reads the kit rather than the class because the two genuinely
    disagree -- Arkiver, Axel, Blueflame and Nyrvite are ELE-scaled, and
    Sader Vorae is deliberately split across both. Handing every DPS +12%
    ATK would be a dead level for exactly the characters the elemental
    pass was built for."""
    for ability in list(abilities) + ([ultimate] if ultimate else []):
        if (ability.get("effect") or {}).get("damage_stat") == "elemental":
            return "elemental"
    return "attack"


def _scale_ability(ability: dict, percent: float) -> dict:
    """A copy of `ability` with its magnitude numbers raised by `percent`.

    Copied, never mutated: these dicts come straight out of the module-
    level kit registries, so editing one in place would permanently buff
    that ability for every character in the process."""
    scaled = dict(ability)
    effect = dict(scaled.get("effect") or {})
    for key in _KIT_MAGNITUDE_KEYS:
        value = effect.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            effect[key] = round(value * (1 + percent / 100), 2)
    for key in _KIT_POISE_KEYS:
        value = effect.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            effect[key] = math.ceil(value * (1 + percent / 100))
    scaled["effect"] = effect
    return scaled


def _apply_resonance(resonance: int, stats: dict, abilities: list[dict],
                     ultimate: dict | None) -> None:
    """Applies every unlocked resonance level. Mutates `stats` and
    `abilities` in place (both are already per-build copies)."""
    damage_stat = _resonance_damage_stat(abilities, ultimate)

    for stat, key in (
        (damage_stat, "damage_stat_percent"),
        ("max_hp", "max_hp_percent"),
        ("defense", "defense_percent"),
        ("crit_damage", "crit_damage_percent"),
    ):
        percent = bonus_total(resonance, key)
        if percent:
            stats[stat] = stats.get(stat, 0) * (1 + percent / 100)

    # R2: the character SKILL specifically -- not weapon or artifact
    # skills, which aren't part of who this character is.
    cost_percent = bonus_total(resonance, "skill_cost_percent")
    if cost_percent:
        for i, ability in enumerate(abilities):
            if ability.get("source") == "character":
                cheaper = dict(ability)
                cheaper["resource_cost"] = max(
                    1, round(ability["resource_cost"] * (1 + cost_percent / 100))
                )
                abilities[i] = cheaper

    # R4: skill and ultimate magnitudes.
    magnitude = bonus_total(resonance, "kit_magnitude_percent")
    if magnitude:
        for i, ability in enumerate(abilities):
            if ability.get("source") == "character":
                abilities[i] = _scale_ability(ability, magnitude)
        if ultimate is not None:
            ultimate.update(_scale_ability(ultimate, magnitude))

    # R5: a shorter ultimate cooldown. Floors at 0 rather than going
    # negative, which ability_ready would read as permanently ready.
    reduction = bonus_total(resonance, "ultimate_cooldown_reduction")
    if reduction and ultimate is not None:
        ultimate["cooldown"] = max(0, ultimate.get("cooldown", ULTIMATE_COOLDOWN) - int(reduction))


def build_party_combatants(squad: list, equipped_items_by_character: dict,
                           starting_energy: int = 0) -> list[Combatant]:
    """`squad` is an ordered list of PlayerCharacter.
    `equipped_items_by_character` maps PlayerCharacter.id -> list of that
    character's equipped InventoryItems.

    `starting_energy` is the Research Lab's Fieldwork perk -- the squad
    begins each battle with energy already banked, so a researched
    account reaches its first ultimate sooner."""
    party = [
        build_character_combatant(pc, equipped_items_by_character.get(pc.id, []))
        for pc in squad
    ]
    if starting_energy:
        for combatant in party:
            combatant.energy = min(combatant.max_energy, int(starting_energy))
    return party


# How much harder every enemy hits. See the block inside
# build_enemy_combatant for the measurement behind this number.
#
# This is the multiplier AT GLACIER DEPTH. Past that it climbs -- see
# enemy_attack_multiplier().
ENEMY_ATTACK_MULTIPLIER = 1.5

# ----------------------------------------------------------------------
# THE LATE GAME WAS THE EASIEST PART OF THE GAME
# ----------------------------------------------------------------------
# Reported from play: Abyssnia enemies doing ~20 damage to a 500 HP
# character, while Glacier 15 felt right. Reproduced exactly in
# simulation before touching anything, which is the only reason the
# numbers below are trustworthy.
#
# Two compounding causes, and BOTH had to move:
#
#   1. Defence outscaled content. Fixed in formulas.mitigate -- see the
#      block there. That alone took Abyssnia from ~20 to ~45.
#
#   2. Enemy ATTACK grows slower than player HP does. Template attack
#      climbs on level_scale_percent (4-5%/level, and only a QUARTER of
#      that for percent stats), while a player's HP climbs on level AND
#      on gear that roughly doubles it again. Over a 48-level span the
#      player wins that race comfortably.
#
# So the multiplier itself now grows with depth, anchored at Glacier:
# a level-17 enemy is multiplied by exactly the old 1.5, and the curve
# only bites past the region the player says is already correct.
#
# Deliberately applied to the MULTIPLIER rather than to template attack
# values: retuning 100+ templates by hand would drift, and every one of
# them is also used by the Abyss and by raids at levels the region
# ladder never reaches. One curve keeps all three consistent.
# RE-CUT AGAIN, because the curve was still losing the race.
#
# The first version of this fixed the direction but not the magnitude.
# Enemy LEVELS are set by region (see region_config's level_offset), and
# they run 3 at Glacier to 51 at Abyssnia -- so across the whole game an
# enemy's attack multiplier moved 1.50 -> 2.57, about 1.7x. Over the same
# span the squad goes level 8 -> 70 with Rare -> Divine gear, which is
# closer to a 9x gain in effective HP. Enemies were still falling behind
# by a factor of five; the earlier pass just made them fall behind more
# slowly.
#
# That gap is what made the healer optional. If an enemy hit costs 4% of
# a character's HP, no one needs a Sustain -- passive regen off a single
# armour piece covers it, which is precisely the substitution players
# found. A Sustain only earns its slot when a hit hurts enough that
# spending a turn to undo it is worth the turn.
#
# At 0.046/level the multiplier reaches 2.88 at Voidcrest depth and 3.84
# at Abyssnia depth: incoming damage as a share of party HP now stays
# roughly flat from Glacier onward instead of falling away, which is all
# this was ever supposed to do. The slope is set by where VOIDCREST
# needs to land rather than where Abyssnia does -- a gentler slope put
# the whole difficulty ramp in the last region and left the one before
# it still soft enough that a support slot was optional there.
#
# GLACIER IS UNTOUCHED, BY CONSTRUCTION. Everything below the anchor
# level returns exactly 1.5, and Glacier's enemies are level 2-3, so the
# region the balance is judged against does not move by so much as a
# point. The Wastelands (level 10-14) doesn't move either.
ATTACK_SCALE_ANCHOR_LEVEL = 17
ATTACK_SCALE_PER_LEVEL = 0.046
ATTACK_SCALE_CAP = 3.6


# ----------------------------------------------------------------------
# ENEMY DEFENCE HAS TO SCALE TOO, OR THE DEBUFF ECONOMY IS FICTION
# ----------------------------------------------------------------------
# Mitigation is DEF / (DEF + K), and K scales with the ATTACKER'S level
# (see formulas.mitigation_k) so that player defence can't outrun the
# content. That fix has a mirror-image consequence nobody costed at the
# time: the same rising K also erases ENEMY defence, because enemy DEF
# does NOT rise anything like as fast as the party's level does.
#
# Measured at Abyssnia depth: a normal enemy has 31 DEF against a
# level-70 party, whose K is 185. That is 14% mitigation. Stripping SIXTY
# PERCENT of it -- the single biggest DEF shred in the game, Caliper's
# ultimate -- moves the party's damage by about 9%.
#
# That number is the whole Support DPS class. Their kits are AOE hits
# that shred DEF; if shredding DEF is worth 9% then the class is worth a
# rounding error, which is exactly what the role benchmark kept saying:
# a squad that swapped its Support DPS for a duplicate Amplifier cleared
# the region more often even after the Amplifier stacking tax.
#
# So enemy DEF now climbs with depth on the same shape as enemy attack,
# anchored at the same level so the early game is untouched by
# construction. At Abyssnia depth a normal enemy carries roughly 4x the
# defence it used to, which puts it back in the same league as the
# attacker's K -- and puts DEF shred back to being worth a turn.
#
# The knock-on is intended, not incidental: enemies being genuinely
# tanky is also what makes fights long enough for a Sustain to matter.
# The two problems in the report -- "enemies don't hit as hard" and
# "healers are obsolete" -- share this cause.
DEFENSE_SCALE_ANCHOR_LEVEL = ATTACK_SCALE_ANCHOR_LEVEL
DEFENSE_SCALE_PER_LEVEL = 0.065
DEFENSE_SCALE_CAP = 4.5


# ----------------------------------------------------------------------
# ENEMIES THAT DIE IN ONE HIT ARE NOT A FIGHT
# ----------------------------------------------------------------------
# The third leg of the same problem the attack and defence curves fix,
# and the one doing the most damage to how the game plays.
#
# Measured with a geared squad at each region's own level, against that
# region's own normal enemies:
#
#     region            party ATK    enemy HP    hits to kill one
#     Glacier 15               19          76                 3.7
#     The Wastelands           73         106                 1.1
#     The Hotlands             50         137                 2.2
#     Voidcrest Desert        139         157                 0.9
#     Abyssnia                 99         273                 2.9
#
# Enemy HP grows 3.6x across the entire game while player damage grows
# six-fold or more, so from The Wastelands onward a normal enemy is a
# one-shot. That is not merely "too easy" -- it changes what the game IS.
# A fight that resolves in one round has no room for a debuff to pay off,
# no room for a heal to matter, and no reason to bring anyone but
# attackers. Every complaint about support roles being pointless has a
# component of this underneath it: they were being asked to contribute to
# fights that were over before their contribution existed.
#
# It also makes the difficulty swingy in the worst way. Enemies now hit
# hard (see the attack curve above), so a fight where both sides delete
# each other in a round is decided by turn order rather than by anything
# the player chose.
#
# So HP scales with depth like everything else, anchored at the same
# level so Glacier and The Wastelands are untouched by construction.
# BOSSES GET LESS OF IT: their pools are already large and hand-tuned,
# and the region capstone ladder (tools/check_progression.py) is measured
# off them, so they take a fraction of the curve rather than the whole
# thing.
# ANCHORED LOWER THAN THE ATTACK CURVE, at 12 rather than 17, and
# steeper. Two measured reasons:
#
#   * The one-shot problem starts EARLIER than the damage problem. The
#     Wastelands (enemy level 10-14) already kills a normal enemy in
#     about one hit, and the attack curve's anchor was set to protect
#     Glacier 15 -- whose enemies are level 2-3 and stay untouched at
#     either anchor.
#   * Support DPS value tracks FIGHT LENGTH almost exactly. Measured over
#     full runs, that class was worth its slot at Abyssnia (enemies take
#     ~4 hits to kill) and a wasted slot at Voidcrest (~1.3 hits), where
#     a squad that dropped it for a second attacker cleared 85% against
#     67%. A debuff cannot pay for the turn that applied it if the target
#     dies before anyone benefits -- so the fix for "Support DPS is
#     undervalued" is here, in fight length, not in their kit.
HP_SCALE_ANCHOR_LEVEL = 12
# Steepened from 0.045 once the cap below was in place, which is what
# made it safe: the cap pins Abyssnia, so the slope now sets the MIDDLE
# of the game without touching the end of it. Two things wanted this:
#
#   * The Hotlands had no difficulty at all -- every squad composition
#     cleared it 100% of the time, so the region asked the player no
#     question. It now takes 1.66x rather than 1.50x.
#   * Voidcrest fights were still short enough that both support classes
#     were losing their slot to a second attacker, for the same
#     fight-length reason described above.
HP_SCALE_PER_LEVEL = 0.06
# The cap is doing real work here rather than being a safety rail. All
# three depth curves -- attack, defence and HP -- are linear in level, so
# they compound hardest exactly where the level is highest, and Abyssnia
# (enemy level 51) got the full product of all three: a one-of-each squad
# went from a 62% clear at Voidcrest to 16% there, against the region's
# own design target of roughly a third. 2.3 is the value that leaves
# Voidcrest (2.13x, under the cap) untouched while pulling Abyssnia back
# from 2.76x.
HP_SCALE_CAP = 2.3

# How much of the curve each role takes. Normal enemies were the worst
# affected and get all of it; bosses are already the longest fights in
# the game and get a third.
HP_SCALE_SHARE_BY_ROLE = {
    "combat": 1.0,
    "elite": 0.85,
    "boss": 0.35,
    "boss_group_member": 0.35,
}


def enemy_hp_multiplier(level: int, role: str = "combat") -> float:
    """HP multiplier for an enemy of this level and role. Exactly 1.0 at
    and below the anchor level."""
    above = max(0, int(level or 1) - HP_SCALE_ANCHOR_LEVEL)
    share = HP_SCALE_SHARE_BY_ROLE.get(role, 1.0)
    grown = 1 + HP_SCALE_PER_LEVEL * share * above
    return min(grown, 1 + (HP_SCALE_CAP - 1) * share)


def enemy_defense_multiplier(level: int) -> float:
    """Defence multiplier for an enemy of this level. Exactly 1.0 at and
    below the anchor -- Glacier and The Wastelands do not move -- rising
    to about 3.9x at Abyssnia depth and capped so the Abyss's level-95
    chambers don't turn into damage sponges."""
    above = max(0, int(level or 1) - DEFENSE_SCALE_ANCHOR_LEVEL)
    return min(1 + DEFENSE_SCALE_PER_LEVEL * above, DEFENSE_SCALE_CAP)


# ----------------------------------------------------------------------
# EARLY-GAME GRACE -- the first hours hit slightly softer
# ----------------------------------------------------------------------
# Reported from play: Glacier 15 and the opening story fights were a
# little too hard. Both live in the same narrow band -- Glacier's enemies
# are level 2-3 and the prologue's scripted fights are levels 2-4 -- so
# one curve covers both rather than hand-editing a region and a script
# separately and having them drift.
#
# The 1.5x attack multiplier was measured against a GEARED squad partway
# through the game (see the block above); it was never sized for a squad
# that has just been handed its first two Uncommons. Below the anchor it
# was applied flat, so the least-equipped players in the game took the
# full adult rate.
#
# Grace ramps out rather than switching off, so there is no step where
# the game suddenly gets harder: about 18% softer at the very start,
# gone entirely by level 12, which is where The Wastelands begins. It
# scales the multiplier and not the templates, so it reaches every mode
# at once -- adventure, story, domains -- and cannot be forgotten for one
# of them.
EARLY_GRACE_UNTIL_LEVEL = 12
EARLY_GRACE_FLOOR = 0.82


def early_game_grace(level: int) -> float:
    """How much of the attack multiplier applies at this level: 0.82 at
    level 1, rising linearly to 1.0 at EARLY_GRACE_UNTIL_LEVEL."""
    level = max(1, int(level or 1))
    if level >= EARLY_GRACE_UNTIL_LEVEL:
        return 1.0
    progress = (level - 1) / (EARLY_GRACE_UNTIL_LEVEL - 1)
    return EARLY_GRACE_FLOOR + (1 - EARLY_GRACE_FLOOR) * progress


def enemy_attack_multiplier(level: int) -> float:
    """Attack multiplier for an enemy of this level. About 1.23x at the
    very start, 1.5x from The Wastelands on, rising to roughly 3.8x by
    the deepest Abyssnia floors, capped so the Abyss's level-95 chambers
    don't run away with it."""
    above = max(0, int(level or 1) - ATTACK_SCALE_ANCHOR_LEVEL)
    grown = ENEMY_ATTACK_MULTIPLIER * (1 + ATTACK_SCALE_PER_LEVEL * above)
    return min(grown, ENEMY_ATTACK_MULTIPLIER * ATTACK_SCALE_CAP) * early_game_grace(level)


def build_enemy_combatant(template: dict, level: int = 1, hp_multiplier: float = 1.0) -> Combatant:
    """`level` is typically the dungeon floor/expedition depth the enemy
    was encountered at -- higher floors produce tougher enemies from the
    same template via level_scale_percent.

    `hp_multiplier` inflates ONLY the HP pool, leaving offence, defence
    and speed exactly where the template put them. Raids are the reason it
    exists (see raid_config.boss_hp_multiplier): a raid attack contributes
    "damage dealt to the boss", which is silently ceilinged by the boss's
    own max HP -- so against a normal template every attack caps out at
    one kill's worth of damage no matter how strong the squad is, and a
    raid pool sized above that is literally unclearable. A fatter HP bar
    (rather than a fatter everything) also gives the raid fight room to
    last long enough for a squad's kit to matter, without making the boss
    hit harder than the tier intends."""
    # Magnitude stats take the full level curve; percent stats take a
    # fraction of it and are then capped -- see PERCENT_STAT_CAPS above
    # for why they can neither scale fully nor be frozen entirely.
    scale = 1 + (level - 1) * template.get("level_scale_percent", 8) / 100
    percent_scale = 1 + (scale - 1) * PERCENT_STAT_SCALE_FACTOR

    base_stats = {}
    for stat in STAT_KEYS:
        raw = template["base_stats"].get(stat, 0)
        if stat in PERCENT_STAT_CAPS:
            base_stats[stat] = round(min(raw * percent_scale, PERCENT_STAT_CAPS[stat]))
        else:
            base_stats[stat] = round(raw * scale)
    # Applied to base_stats, not just the Combatant fields, so that every
    # percent-of-max-HP effect (self-heals, shields, execute thresholds)
    # reads the inflated pool too rather than quietly working off the
    # template's original number.
    role = template.get("role", "combat")

    # Depth scaling first, then the caller's own multiplier (raids). Both
    # land on base_stats rather than only on the Combatant fields so that
    # every percent-of-max-HP effect -- self-heals, shields, execute
    # thresholds -- reads the real pool.
    base_stats["max_hp"] = max(1, round(
        base_stats["max_hp"]
        * enemy_hp_multiplier(level, role)
        * max(0.01, hp_multiplier)
    ))

    # Balance pass -- defense rework: see the DEFENSE_MULTIPLIER_BY_ROLE
    # comment above. Applied after level scaling so it compounds with
    # level_scale_percent the same way every other stat does.
    # ENEMIES HIT 1.5x HARDER THAN THEY USED TO.
    #
    # Measured, not guessed. Players were dropping dedicated Sustains for
    # healing GEAR, and the benchmark showed why: with the old numbers a
    # squad with NO Sustain still won 46% of fights, so the class was
    # optional and gear was a fine substitute. At 1.5x attack the same
    # no-Sustain squad wins **0%** while a squad with a healer or
    # shielder still wins ~54% -- which is the intended shape. Bringing
    # one is no longer a preference.
    #
    # Applied here, to base_stats, so it lands on every enemy in every
    # mode at once and can't be forgotten for one of them. See
    # tools/bench_healers.py for the sweep this came from.
    attack_multiplier = enemy_attack_multiplier(level)
    base_stats["attack"] = round(base_stats["attack"] * attack_multiplier)
    base_stats["elemental"] = round(base_stats["elemental"] * attack_multiplier)

    base_stats["defense"] = round(
        base_stats["defense"]
        * DEFENSE_MULTIPLIER_BY_ROLE.get(role, 1.35)
        * enemy_defense_multiplier(level)
    )

    # Balance pass -- elites (and, to a lesser degree, normal enemies)
    # were weaker than they should be relative to standalone bosses and
    # to a group of normal enemies. Boss/boss_group_member templates are
    # left at their authored numbers -- that roster already went through
    # its own tuning pass (see enemies.py's module docstring).
    power_multiplier = (
        ELITE_POWER_MULTIPLIER if role == "elite"
        else NORMAL_POWER_MULTIPLIER if role == "combat"
        else None
    )
    if power_multiplier:
        for stat, mult in power_multiplier.items():
            base_stats[stat] = round(base_stats[stat] * mult)

    ultimate = template.get("ultimate_ability")
    if ultimate:
        ultimate = dict(ultimate)
        ultimate["is_ultimate"] = True
        ultimate.setdefault("resource_type", "energy")
        ultimate.setdefault("resource_cost", 50)
        # Enemies are held to the same ultimate cadence as the party --
        # see ULTIMATE_COOLDOWN in combatant.py. setdefault, so a template
        # that deliberately specifies its own cooldown still wins.
        ultimate.setdefault("cooldown", ULTIMATE_COOLDOWN)

    # Balance pass -- attack ramp-up (replaces innate regen): a small,
    # PERMANENT per-turn attack/elemental bonus that accumulates every one
    # of this enemy's own turns (see battle.py's _begin_turn and
    # Combatant.effective_stat). Unlike the old regen, this is an offense
    # buff, not sustain -- it stacks fine alongside anything a template's
    # own passives additionally grant (regen_field_generator, etc.), which
    # are deliberate per-character kit pieces left untouched by this pass.
    ramp_percent_per_turn = ATTACK_RAMP_PERCENT_PER_TURN_BY_ROLE.get(role, 0.4)

    # Poise pool -- role-derived, per-template overridable. Deliberately
    # NOT scaled by `level`: poise counts actions rather than damage, so a
    # floor-40 elite takes the same number of hits to break as a floor-1
    # one. Breaking stays a tactical decision at every depth instead of
    # decaying into "you out-gear it so it never breaks" or "you out-gear
    # it so it's permanently broken".
    max_poise = template.get("max_poise", POISE_BY_ROLE.get(role, DEFAULT_POISE))

    return Combatant(
        name=template["name"],
        short_name=short_name_for(template["name"]),
        is_player=False,
        base_stats=base_stats,
        current_hp=base_stats["max_hp"],
        max_hp=base_stats["max_hp"],
        # Enemies aren't resource-constrained the way players are for mana
        # -- their "budget" is which abilities they're given, not a scarce
        # pool. Energy is still capped at 50 so an enemy ultimate feels
        # earned rather than spammed turn one.
        mana=9999,
        max_mana=9999,
        energy=0,
        max_energy=50,
        active_abilities=[dict(a, source="enemy") for a in template.get("active_abilities", [])],
        level=level,
        ultimate_ability=ultimate,
        passive_abilities=list(template.get("passive_abilities", [])),
        ramp_percent_per_turn=ramp_percent_per_turn,
        # Cycle turn order (see battle.py): defaults to 1 action/cycle like
        # everyone else. Set "actions_per_cycle": 2 (or higher) on an enemy
        # template to make it act that many times every cycle -- e.g. for
        # an elite or boss meant to feel meaningfully faster/more dangerous
        # than a normal enemy without breaking the "everyone still gets a
        # turn" guarantee the cycle system is built around.
        base_actions_per_cycle=template.get("actions_per_cycle", 1),
        max_poise=max_poise,
        poise=max_poise,
    )
