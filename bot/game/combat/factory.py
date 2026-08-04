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

from bot.database.models.enums import ItemType
from bot.game.combat.combatant import STAT_KEYS, Combatant
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
    "combat": 1.15,
    "elite": 1.2,
    "boss": 1.15,
    "boss_group_member": 1.05,
}
ELITE_POWER_MULTIPLIER = {"attack": 1.4, "elemental": 1.4, "max_hp": 1.25}
NORMAL_POWER_MULTIPLIER = {"attack": 1.2, "elemental": 1.2, "max_hp": 1.3}
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


def base_character_stats(player_character) -> dict:
    """Template base stats + linear growth to the character's current
    level. Only HP/ATK/DEF/ELE/MP/SPD grow with level (per the leveling
    spec: 'marginally' -- crit rate/damage/recharge stay put and are gear's
    job to move)."""
    template = player_character.template
    levels = max(0, player_character.level - 1)
    return {
        "attack": template.base_attack + template.growth_attack * levels,
        "defense": template.base_defense + template.growth_defense * levels,
        "elemental": template.base_elemental + template.growth_elemental * levels,
        "speed": template.base_speed + template.growth_speed * levels,
        "max_hp": template.base_hp + template.growth_hp * levels,
        "max_mana": template.base_mana + template.growth_mana * levels,
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
    )


def build_party_combatants(squad: list, equipped_items_by_character: dict) -> list[Combatant]:
    """`squad` is an ordered list of PlayerCharacter (slot 0 = avatar).
    `equipped_items_by_character` maps PlayerCharacter.id -> list of that
    character's equipped InventoryItems."""
    return [
        build_character_combatant(pc, equipped_items_by_character.get(pc.id, []))
        for pc in squad
    ]


def build_enemy_combatant(template: dict, level: int = 1) -> Combatant:
    """`level` is typically the dungeon floor/expedition depth the enemy
    was encountered at -- higher floors produce tougher enemies from the
    same template via level_scale_percent."""
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
    base_stats["max_hp"] = max(1, base_stats["max_hp"])

    role = template.get("role", "combat")

    # Balance pass -- defense rework: see the DEFENSE_MULTIPLIER_BY_ROLE
    # comment above. Applied after level scaling so it compounds with
    # level_scale_percent the same way every other stat does.
    base_stats["defense"] = round(
        base_stats["defense"] * DEFENSE_MULTIPLIER_BY_ROLE.get(role, 1.35)
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
        ultimate.setdefault("cooldown", 0)

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
