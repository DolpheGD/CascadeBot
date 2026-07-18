"""
Read-only aggregator for /encyclopedia. Every source here is already plain,
hand-authored in-memory data (enemy/character/item templates, ability
pools, class kits) -- none of it is player state, so this module never
touches the database. It just normalizes everything into a common
EncyclopediaEntry shape the cog/embedder can render generically.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from bot.database.models.enums import (
    CLASS_DISPLAY_NAME,
    MATERIAL_DISPLAY_NAME,
    SLOT_DISPLAY_NAME,
    CharacterClass,
    MaterialType,
)
from bot.game.characters.character_seed_data import CHARACTER_TEMPLATES
from bot.game.combat.enemies import BOSS_GROUP_REGION_ROLES, BOSS_GROUPS, ENEMY_TEMPLATES
from bot.game.combat.skills import (
    CLASS_KIT_MAP,
    get_character_passive,
    get_character_skill,
    get_character_ultimate,
)
from bot.game.loot.abilities import ARMOR_PASSIVES, ARTIFACT_SKILLS, WEAPON_SKILLS, get_ability_by_id
from bot.game.loot.item_seed_data import ITEM_TEMPLATES


@dataclass
class EncyclopediaEntry:
    category: str
    key: str
    name: str
    summary: str  # one-liner shown in the list view
    data: dict = field(default_factory=dict)


# (category key, display label, blurb shown on the category picker)
CATEGORIES: list[tuple[str, str, str]] = [
    ("characters", "🧑 Characters", "Playable characters you can pull or unlock."),
    ("classes", "🧬 Classes", "The four roles your own avatar can freely switch between."),
    ("enemies", "👹 Enemies", "Creatures and foes encountered on expeditions."),
    ("abilities", "✨ Abilities", "Skills and passives found on weapons, artifacts, and armor."),
    ("items", "🗡️ Equipment", "Weapons, artifacts, armor, and accessories -- including full sets."),
    ("materials", "🧱 Materials", "Crafting materials used to upgrade gear."),
]

CATEGORY_LABELS: dict[str, str] = {key: label for key, label, _ in CATEGORIES}

ROLE_LABELS = {
    "combat": "Regular Enemy",
    "elite": "Elite",
    "boss": "Boss",
    "boss_group_member": "Boss (Group Encounter)",
}

MATERIAL_BLURB: dict[MaterialType, str] = {
    MaterialType.WOOD: "Common scrap timber -- the first thing any wanderer learns to scavenge.",
    MaterialType.STONE: "Plain quarried rock, plentiful across every region.",
    MaterialType.METAL: "Scavenged plating and scrap alloy, a step up from raw stone.",
    MaterialType.CRYSTAL: "Naturally-formed Cascade crystal, faintly charged with latent energy.",
    MaterialType.XENDIUM: "A refined alloy tied to Acatrya's Xendium supercomputer labs.",
    MaterialType.PERMAFROST_ORE: "Ore chipped from Glacier 15's frozen ruins, cold to the touch.",
    MaterialType.VOID: "Matter drawn from the Voidcrest Desert's original Void-matter discovery site.",
    MaterialType.ENTROPY: "Unstable, half-corrupted matter -- the rarest and most volatile material known.",
}

CLASS_BLURB: dict[CharacterClass, str] = {
    CharacterClass.DPS: "Snowballs its own Attack the longer a fight runs -- a self-contained damage engine.",
    CharacterClass.SUPPORT_DPS: "Sweeps the whole enemy line at once, sometimes shredding a stat on whoever it hits.",
    CharacterClass.AMPLIFIER: "Keeps the whole team's resources flowing, trickling Energy and SP to every ally each turn.",
    CharacterClass.SUSTAIN: "Keeps the whole team alive, regenerating HP for every ally each turn on top of direct heals.",
}

# Character/enemy template stat keys -> the stat keys STAT_EMOJI/STAT_LABEL
# in bot.utils.embedder actually key off of.
CHARACTER_BASE_STAT_KEYS: list[tuple[str, str]] = [
    ("base_hp", "max_hp"), ("base_attack", "attack"), ("base_defense", "defense"),
    ("base_mana", "max_mana"), ("base_elemental", "elemental"), ("base_speed", "speed"),
    ("base_crit_rate", "crit_rate"), ("base_crit_damage", "crit_damage"), ("base_recharge", "recharge"),
]

ENEMY_STAT_KEYS = ["max_hp", "attack", "defense", "elemental", "speed", "crit_rate", "crit_damage", "recharge"]


def _slug(name: str) -> str:
    return name.lower().replace(" ", "_").replace("'", "").replace(".", "").replace("-", "_")


def _character_kit(template: dict) -> dict:
    return {
        "skill": get_character_skill(template["skill_id"]),
        "ultimate": get_character_ultimate(template["ultimate_id"]),
        "passive": get_character_passive(template["passive_id"]),
    }


def list_characters() -> list[EncyclopediaEntry]:
    """Every pullable character -- excludes the player's own class-switchable
    avatar template, whose kit depends on current_class and is covered by
    the separate Classes category instead."""
    entries = []
    for t in CHARACTER_TEMPLATES:
        if t.get("is_player_avatar"):
            continue
        entries.append(EncyclopediaEntry(
            category="characters", key=_slug(t["name"]), name=t["name"],
            summary=f"{'⭐' * t['star_rating']} {CLASS_DISPLAY_NAME[t['character_class']]}",
            data={"template": t, "kit": _character_kit(t)},
        ))
    entries.sort(key=lambda e: (-e.data["template"]["star_rating"], e.name))
    return entries


def list_classes() -> list[EncyclopediaEntry]:
    entries = []
    for cls in CharacterClass:
        entries.append(EncyclopediaEntry(
            category="classes", key=cls.value, name=CLASS_DISPLAY_NAME[cls],
            summary=CLASS_BLURB[cls],
            data={"character_class": cls, "kit": CLASS_KIT_MAP[cls]},
        ))
    return entries


_GROUP_ID_BY_MEMBER_NAME = {
    member: group_id for group_id, members in BOSS_GROUPS.items() for member in members
}


def enemy_region_text(t: dict) -> str:
    """Enemy templates spell out where they show up three different ways
    depending on role: "regions" (combat/elite -- flat list), "region_roles"
    (solo boss -- region -> "regular"/"final") or, for boss_group_member
    templates (which have neither field themselves), the region_roles of
    the BOSS_GROUPS entry they belong to."""
    if "regions" in t:
        return ", ".join(t["regions"]) or "Unknown"
    if "region_roles" in t:
        return ", ".join(f"{region} ({role})" for region, role in t["region_roles"].items())
    group_id = _GROUP_ID_BY_MEMBER_NAME.get(t["name"])
    region_roles = BOSS_GROUP_REGION_ROLES.get(group_id, {}) if group_id else {}
    if region_roles:
        group_members = ", ".join(BOSS_GROUPS[group_id])
        return ", ".join(f"{region} ({role})" for region, role in region_roles.items()) + f" -- fought alongside {group_members}"
    return "Unknown"


def list_enemies() -> list[EncyclopediaEntry]:
    entries = []
    for t in ENEMY_TEMPLATES:
        entries.append(EncyclopediaEntry(
            category="enemies", key=_slug(t["name"]), name=t["name"],
            summary=f"{ROLE_LABELS.get(t['role'], t['role'].title())} -- {enemy_region_text(t)}",
            data={"template": t},
        ))
    entries.sort(key=lambda e: e.name)
    return entries


_ABILITY_POOLS: list[tuple[list[dict], str, str]] = [
    (WEAPON_SKILLS, "Weapon Skill", "⚔️"),
    (ARTIFACT_SKILLS, "Artifact Skill", "🔮"),
    (ARMOR_PASSIVES, "Armor Passive", "🛡️"),
]


def list_abilities() -> list[EncyclopediaEntry]:
    """The rollable gear-ability catalog (bot/game/loot/abilities.py) --
    NOT character skills/ultimates/passives, which are fixed per character
    and shown on that character's own Characters/Classes entry instead."""
    entries = []
    seen_keys: set[str] = set()
    for pool, label, emoji in _ABILITY_POOLS:
        for a in pool:
            key = a["id"] if a["id"] not in seen_keys else f"{a['id']}_{label}"
            seen_keys.add(key)
            entries.append(EncyclopediaEntry(
                category="abilities", key=key, name=a["name"],
                summary=f"{emoji} {label} -- min rarity {a['min_rarity'].value.title()}",
                data={"ability": a, "pool_label": label, "pool_emoji": emoji},
            ))
    entries.sort(key=lambda e: e.name)
    return entries


def list_materials() -> list[EncyclopediaEntry]:
    entries = []
    for m in MaterialType:
        entries.append(EncyclopediaEntry(
            category="materials", key=m.value, name=MATERIAL_DISPLAY_NAME[m],
            summary=f"Tier {m.tier} -- {MATERIAL_BLURB[m]}",
            data={"material": m, "blurb": MATERIAL_BLURB[m]},
        ))
    entries.sort(key=lambda e: e.data["material"].tier)
    return entries


def _linked_ability_for(template: dict) -> dict | None:
    ability_id = template.get("linked_ability_id")
    if not ability_id:
        return None
    from bot.database.models.enums import EquipmentSlot
    pool = {
        EquipmentSlot.WEAPON: WEAPON_SKILLS,
        EquipmentSlot.ARTIFACT: ARTIFACT_SKILLS,
        EquipmentSlot.ARMOR: ARMOR_PASSIVES,
        EquipmentSlot.ACCESSORY: ARMOR_PASSIVES,
    }[template["slot"]]
    try:
        return get_ability_by_id(pool, ability_id)
    except KeyError:
        return None


def list_items() -> list[EncyclopediaEntry]:
    entries = []
    for idx, t in enumerate(ITEM_TEMPLATES):
        display_name = f"{t['set_prefix']} {t['name']}" if t.get("set_prefix") else t["name"]
        set_tag = f" ({t['set_name']})" if t.get("set_name") else ""
        entries.append(EncyclopediaEntry(
            category="items", key=str(idx), name=display_name,
            summary=f"{SLOT_DISPLAY_NAME[t['slot']]}{set_tag} -- {t['min_rarity'].value.title()}-{t['max_rarity'].value.title()}",
            data={"template": t, "linked_ability": _linked_ability_for(t)},
        ))
    entries.sort(key=lambda e: (e.data["template"].get("set_name") or "", e.name))
    return entries


_LIST_FUNCS = {
    "characters": list_characters,
    "classes": list_classes,
    "enemies": list_enemies,
    "abilities": list_abilities,
    "items": list_items,
    "materials": list_materials,
}


def list_entries(category: str) -> list[EncyclopediaEntry]:
    return _LIST_FUNCS[category]()


def get_entry(category: str, key: str) -> EncyclopediaEntry | None:
    return next((e for e in list_entries(category) if e.key == key), None)


def entry_index_and_total(category: str, key: str) -> tuple[int, int]:
    entries = list_entries(category)
    for i, e in enumerate(entries):
        if e.key == key:
            return i, len(entries)
    return 0, len(entries)
