"""
Launch character catalog for the Combat Overhaul.

Seeded the same upsert-on-startup way as item/harvester/lootbox templates
(see bot/services/character_template_service.py). Stat baselines are rough
first passes tuned by star rating -- 3★ characters are intentionally
serviceable-but-plain, 5★ are the power ceiling. Rebalance freely; nothing
else depends on the exact numbers.

skill_id / ultimate_id are placeholders for the Combat Overhaul's skill
registry (bot/game/combat/skills.py, phase 2) -- naming them now so kit
design and combat wiring can proceed independently.
"""

from __future__ import annotations

from bot.database.models.enums import CharacterClass

# ---------------------------------------------------------------------
# Baseline stat blocks per star rating. Individual characters nudge off
# these based on class (e.g. Sustain gets more HP/DEF, DPS gets more ATK).
# ---------------------------------------------------------------------
_BASELINE_BY_STAR = {
    3: dict(base_hp=950, base_attack=45, base_defense=38, base_mana=90,
            base_elemental=28, base_speed=95, growth_hp=22.0, growth_attack=1.2,
            growth_defense=1.0, growth_mana=1.3, growth_elemental=0.8, growth_speed=0.30),
    4: dict(base_hp=1050, base_attack=52, base_defense=42, base_mana=100,
            base_elemental=32, base_speed=100, growth_hp=26.0, growth_attack=1.45,
            growth_defense=1.15, growth_mana=1.5, growth_elemental=0.95, growth_speed=0.34),
    5: dict(base_hp=1150, base_attack=60, base_defense=46, base_mana=110,
            base_elemental=36, base_speed=105, growth_hp=30.0, growth_attack=1.7,
            growth_defense=1.3, growth_mana=1.7, growth_elemental=1.1, growth_speed=0.38),
}


def _char(name, star, cls, bio, skill_id, ultimate_id, **overrides):
    data = dict(name=name, star_rating=star, character_class=cls, bio=bio,
                skill_id=skill_id, ultimate_id=ultimate_id)
    data.update(_BASELINE_BY_STAR[star])
    data.update(overrides)
    return data


CHARACTER_TEMPLATES: list[dict] = [
    # -----------------------------------------------------------------
    # The player's own avatar -- freely switches class (see
    # bot.database.models.character_model.PlayerCharacter.current_class).
    # Every player owns exactly one copy of this, granted for free.
    # -----------------------------------------------------------------
    dict(
        name="You", star_rating=4, character_class=CharacterClass.DPS,
        is_player_avatar=True,
        bio="A wanderer making their way through the Cascade, still figuring out which role suits them best.",
        skill_id="avatar_class_skill", ultimate_id="avatar_class_ultimate",
        **_BASELINE_BY_STAR[4],
    ),

    # -----------------------------------------------------------------
    # 3-star
    # -----------------------------------------------------------------
    _char("Lily Lovelace", 3, CharacterClass.SUSTAIN,
          "A highly skilled cook who treats every meal like a small act of care -- and every battlefield like a kitchen that needs tidying up.",
          "lily_lovelace_skill", "lily_lovelace_ultimate",
          base_hp=1100, base_defense=48, growth_hp=28.0),
    _char("Nexus", 3, CharacterClass.AMPLIFIER,
          "Always on his phone, chasing the next viral moment. He's convinced that if he just amplifies the right signal, everyone will finally notice him.",
          "nexus_skill", "nexus_ultimate"),
    _char("FAX", 3, CharacterClass.SUPPORT_DPS,
          "A Cascade airship pilot with dreams bigger than his cargo hold -- he's saving every fare toward the business he swears he'll launch any day now.",
          "fax_skill", "fax_ultimate"),
    _char("Arkiver", 3, CharacterClass.DPS,
          "Loves fighting more than just about anything, channeling elemental energy through a pair of dual-wielded gauntlets he never takes off.",
          "arkiver_skill", "arkiver_ultimate",
          base_attack=52, growth_attack=1.35),

    # -----------------------------------------------------------------
    # 4-star
    # -----------------------------------------------------------------
    _char("Bee Jee", 4, CharacterClass.SUSTAIN,
          "A former bioweapons engineer who walked away from that life to support others instead, watching the field through a pair of high-tech goggles.",
          "bee_jee_skill", "bee_jee_ultimate",
          base_hp=1200, base_defense=50, growth_hp=30.0),
    _char("Sader Vorae", 4, CharacterClass.SUPPORT_DPS,
          "A pilot for Team Cascade and one of the few survivors of Glacier 15. She flies every mission looking for answers about what really happened that day.",
          "sader_vorae_skill", "sader_vorae_ultimate"),
    _char("Nebula", 4, CharacterClass.AMPLIFIER,
          "A survival specialist and excellent mountaineer who turns any terrain into a tactical advantage, reading the land the way others read a map.",
          "nebula_skill", "nebula_ultimate"),

    # -----------------------------------------------------------------
    # 5-star
    # -----------------------------------------------------------------
    _char("Josh", 5, CharacterClass.DPS,
          "Leader of the World Aligners and a survivor of Glacier 15, driven by a promise to avenge his friend Rex, who didn't make it out that day.",
          "josh_skill", "josh_ultimate",
          base_attack=66, growth_attack=1.85),
    _char("Refender", 5, CharacterClass.SUSTAIN,
          "Creator of the Refense philosophy -- a balance of offense and defense in all things. From the Hotlands, he travels the Cascade spreading his ideals.",
          "refender_skill", "refender_ultimate",
          base_hp=1300, base_defense=52, growth_hp=34.0),
]
