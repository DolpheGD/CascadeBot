"""
Launch character catalog for the Combat Overhaul.

Seeded the same upsert-on-startup way as item/harvester/lootbox templates
(see bot/services/character_template_service.py). Stat baselines are rough
first passes tuned by star rating -- 3★ characters are intentionally
serviceable-but-plain, 5★ are the power ceiling. Rebalance freely; nothing
else depends on the exact numbers.

Balancing pass: these were originally set roughly 10x higher than the
pre-Combat-Overhaul game's stats (and than enemy stats in
bot/game/combat/enemies.py, which were never touched and stayed at the
original ~40-100 HP / ~7-12 ATK scale) -- badly overpowering both enemies
and gear. Rescaled back down to be in the same ballpark as enemies, with a
slower per-level growth curve (~3.5-4x from level 1 to 100, not ~4.5-5x).

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
    3: dict(base_hp=85, base_attack=8, base_defense=7, base_mana=42,
            base_elemental=6, base_speed=9, base_crit_rate=5, base_crit_damage=145, base_recharge=10,
            growth_hp=2.3, growth_attack=0.21, growth_defense=0.14,
            growth_mana=0.80, growth_elemental=0.12, growth_speed=0.09),
    4: dict(base_hp=95, base_attack=9, base_defense=8, base_mana=47,
            base_elemental=7, base_speed=10, base_crit_rate=5, base_crit_damage=150, base_recharge=10,
            growth_hp=2.6, growth_attack=0.25, growth_defense=0.16,
            growth_mana=0.90, growth_elemental=0.14, growth_speed=0.11),
    5: dict(base_hp=105, base_attack=10, base_defense=9, base_mana=52,
            base_elemental=8, base_speed=11, base_crit_rate=6, base_crit_damage=155, base_recharge=10,
            growth_hp=2.9, growth_attack=0.29, growth_defense=0.18,
            growth_mana=1.00, growth_elemental=0.16, growth_speed=0.12),
}


def _char(name, star, cls, bio, skill_id, ultimate_id, **overrides):
    slug = name.lower().replace(" ", "_")
    data = dict(name=name, star_rating=star, character_class=cls, bio=bio,
                skill_id=skill_id, ultimate_id=ultimate_id, passive_id=f"{slug}_passive")
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
        name="You", star_rating=5, character_class=CharacterClass.DPS,
        is_player_avatar=True,
        bio="A wanderer making their way through the Cascade, still figuring out which role suits them best.",
        skill_id="avatar_class_skill", ultimate_id="avatar_class_ultimate",
        **_BASELINE_BY_STAR[5],
    ),

    # -----------------------------------------------------------------
    # 3-star
    # -----------------------------------------------------------------
    _char("Lily Lovelace", 3, CharacterClass.SUSTAIN,
          "A highly skilled cook who treats every meal like a small act of care -- and every battlefield like a kitchen that needs tidying up.",
          "lily_lovelace_skill", "lily_lovelace_ultimate",
          base_hp=100, base_defense=9, growth_hp=2.7),
    _char("Nexus", 3, CharacterClass.AMPLIFIER,
          "Always on his phone, chasing the next viral moment. He's convinced that if he just amplifies the right signal, everyone will finally notice him.",
          "nexus_skill", "nexus_ultimate"),
    _char("FAX", 3, CharacterClass.SUPPORT_DPS,
          "A Cascade airship pilot with dreams bigger than his cargo hold -- he's saving every fare toward the business he swears he'll launch any day now.",
          "fax_skill", "fax_ultimate"),
    _char("Arkiver", 3, CharacterClass.DPS,
          "Loves fighting more than just about anything, channeling elemental energy through a pair of dual-wielded gauntlets he never takes off.",
          "arkiver_skill", "arkiver_ultimate",
          base_attack=9, growth_attack=0.24),

    # -----------------------------------------------------------------
    # 4-star
    # -----------------------------------------------------------------
    _char("Bee Jee", 4, CharacterClass.SUSTAIN,
          "A former bioweapons engineer who walked away from that life to support others instead, watching the field through a pair of high-tech goggles.",
          "bee_jee_skill", "bee_jee_ultimate",
          base_hp=110, base_defense=10, growth_hp=3.0),
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
          base_attack=12, growth_attack=0.34),
    _char("Refender", 5, CharacterClass.SUSTAIN,
          "Creator of the Refense philosophy -- a balance of offense and defense in all things. From the Hotlands, he travels the Cascade spreading his ideals.",
          "refender_skill", "refender_ultimate",
          base_hp=120, base_defense=11, growth_hp=3.3),
]
