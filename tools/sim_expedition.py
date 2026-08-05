"""
Simulate whole expedition runs, not single fights.

    python -m tools.sim_expedition

Single-fight win rates are actively misleading in this game, because
HP CARRIES BETWEEN FIGHTS inside a run. Glacier 15 measured 98-100%
per combat room and 32% per RUN: you win every fight and still die of
accumulated attrition. Any tuning done off per-fight numbers will be
wrong in the same direction.

So this models the real thing: 9 floors, room types drawn from
ROOM_WEIGHTS_BY_STAGE, the forced pre-boss campfire and its 50% heal,
the revive-to-1-HP rule between fights, and get_boss_encounter for the
capstone (which can return a GROUP, not a single boss -- worth knowing,
since a "final boss" can total well over 2,000 HP across four bodies).

NO GEAR is modelled, so every number here is a floor, not a forecast.
Real players at level 30+ are considerably stronger than this says.
Use it for comparing regions to each other, which is what it is good
at, rather than for absolute difficulty.
"""

import sys, tempfile, os, random; sys.path.insert(0,'.')
os.environ["DATABASE_URL"]="sqlite:///"+tempfile.mktemp(suffix=".db")
import bot.config as cfg; cfg.DATABASE_URL=os.environ["DATABASE_URL"]
from bot.database.db import engine
from bot.database.db_init import init_db
from sqlalchemy.orm import sessionmaker
init_db(); db=sessionmaker(bind=engine)()
from bot.services import character_template_service
from bot.database.models.character_model import CharacterTemplate, PlayerCharacter
from bot.database.models.enums import RoomType
character_template_service.ensure_character_templates_seeded(db); db.commit()
from bot.game.combat.battle import Battle
from bot.game.combat.factory import build_enemy_combatant, build_party_combatants
from bot.game.dungeon.region_config import REGION_DIFFICULTY, ordered_regions
from bot.game.dungeon.room_config import ROOM_WEIGHTS_BY_STAGE
from bot.game.dungeon.relic_config import CAMPFIRE_REST_PERCENT
from bot.game.combat import enemies as cat

# --------------------------------------------------------------- gear
# Gear is the single biggest multiplier in the game and leaving it out of
# the model made every deep-region number meaningless. A "no gear" squad
# is a floor nobody actually plays at.
from bot.database.models.enums import Rarity
from bot.game.loot.generator import LootGenerator
from bot.services import item_template_service
item_template_service.ensure_item_templates_seeded(db)

_GEN = LootGenerator(rng=random.Random(99))
_SLOT_CACHE: dict = {}


def kit(character_id: int, rarity: Rarity, item_level: int, slots: int = 5) -> list:
    """`slots` items of `rarity` at `item_level`, one per equipment slot.

    Generated once per (rarity, level, slots) and reused, so a sweep
    compares squads that differ only in the axis being swept."""
    key = (rarity, item_level, slots)
    if key not in _SLOT_CACHE:
        items = []
        for _ in range(slots):
            tpl = item_template_service.pick_random_template(db, rng=_GEN.rng, rarity=rarity)
            if tpl is None:
                continue
            items.append(_GEN.generate_item(tpl, player_id=1, item_level=item_level,
                                            rarity_override=rarity))
        _SLOT_CACHE[key] = items
    return list(_SLOT_CACHE[key])


avatar = db.query(CharacterTemplate).filter_by(is_player_avatar=True).first()
pool = db.query(CharacterTemplate).filter_by(is_player_avatar=False).all()
def pc(t,l):
    o=PlayerCharacter(player_id=1,template_id=t.id,level=l,dupe_count=0); o.template=t; o.current_hp=None; return o

def fight(party, enemies, rng):
    b = Battle(party, enemies)
    for _ in range(600):
        if b.is_over(): break
        a=b.current_actor()
        if a is None: break
        if a in b.enemies: b.take_enemy_turn()
        elif a.ultimate_ready(): b.take_party_action("ultimate")
        else:
            r=[x for x in a.active_abilities if a.ability_ready(x)]
            if r and rng.random()<0.7: b.take_party_action("ability",ability_id=rng.choice(r)["id"])
            else: b.take_party_action("attack")
    return b.result=="won"

NUM_FLOORS = 9
def stage_of(f):
    return "early" if f < NUM_FLOORS/3 else ("mid" if f < 2*NUM_FLOORS/3 else "late")

def run(region, squad_level, seed, co=None, eo=None, gear=None, gear_level=None):
    """`gear` is a Rarity (or None for naked). `gear_level` defaults to
    the squad level, capped by what that rarity can be upgraded to."""
    rng = random.Random(seed)
    d = REGION_DIFFICULTY[region]
    co = d["combat_level_offset"] if co is None else co
    eo = d["level_offset"] if eo is None else eo
    members = [pc(avatar,squad_level)] + [pc(t,squad_level) for t in rng.sample(pool,3)]
    for i, m in enumerate(members):
        m.id = i + 1
    equipped = {}
    if gear is not None:
        from bot.game.loot.rarity_config import upgrade_level_cap
        lvl = min(gear_level if gear_level is not None else squad_level,
                  upgrade_level_cap(gear))
        equipped = {m.id: kit(m.id, gear, max(1, lvl)) for m in members}
    party = build_party_combatants(members, equipped)
    for floor in range(NUM_FLOORS):
        if floor == NUM_FLOORS - 2:          # forced pre-boss campfire
            for m in party:
                m.current_hp = min(m.max_hp, m.current_hp + max(1, round(m.max_hp*CAMPFIRE_REST_PERCENT/100)))
            continue
        if floor == NUM_FLOORS - 1:
            room = RoomType.BOSS
        else:
            w = ROOM_WEIGHTS_BY_STAGE[stage_of(floor)]
            room = rng.choices(list(w.keys()), weights=list(w.values()), k=1)[0]
        if room not in (RoomType.COMBAT, RoomType.ELITE, RoomType.BOSS):
            continue
        role = {RoomType.COMBAT:"combat", RoomType.ELITE:"elite", RoomType.BOSS:"boss"}[room]
        tpl = cat.get_templates_by_role(role, region=region) or []
        if not tpl: continue
        off = co if room == RoomType.COMBAT else eo
        sw = d["combat_squad_weights"] if room==RoomType.COMBAT else d["elite_squad_weights"]
        n = rng.choices(list(sw.keys()), weights=list(sw.values()), k=1)[0]
        enemies=[build_enemy_combatant(rng.choice(tpl), floor//10 + 1 + off) for _ in range(n)]
        if not fight(party, enemies, rng):
            return False
        for m in party:
            if m.current_hp <= 0: m.current_hp = 1
    return True

if __name__ == "__main__":
    print("FULL 9-FLOOR RUN clear rate (4 chars, no gear, campfire modelled)\n")
    print(f"{'region':<18} " + "  ".join(f"sq{l:<3}" for l in (1,5,10,20,40,60)))
    for region in ordered_regions():
        row=[sum(run(region,L,k) for k in range(50))/50 for L in (1,5,10,20,40,60)]
        print(f"{region:<18} " + "  ".join(f"{r:>4.0%} " for r in row))
