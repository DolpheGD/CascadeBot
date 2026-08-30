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

THE DEFAULT TABLE IS GEARLESS, so those numbers are a floor and not a
forecast -- `run()` takes `gear=` and `gear_level=`, and the honest
reading of a region is at its own expected_squad_level and
expected_gear_rarity from region_config. The headline table was read as
a forecast for a long time and the endgame was tuned off it.

IT IS DETERMINISTIC, and was not. Three bugs, all fixed, all documented
where they were: boss rooms did not use get_boss_encounter, fight() let
Battle create its own unseeded rng, and the gear cache handed out shared
mutable items seeded from a per-process hash. Same seeds now give the
same answer in this process and in any other. Run it twice before
believing it -- that is how all three were found.
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

    DETERMINISTIC AND ISOLATED, and it was neither. Measuring Abyssnia
    twice with identical inputs returned 93% and then 83%, which makes
    every number this tool has ever produced a coin flip dressed as a
    measurement -- and the endgame was tuned off those numbers.

    Two separate causes, both fixed here:

      1. ORDER DEPENDENCE. `_GEN`'s rng is a module global that advances
         on every generate_item call, so the gear a region got depended
         on how many other regions had been measured first. Sweeping
         four candidate offsets for one region therefore compared four
         different sets of equipment. The generator is now re-seeded per
         cache key, so a given (rarity, level) always produces the same
         items no matter when it is asked for.

      2. SHARED MUTABLE ITEMS. The cache returned `list(...)` -- a new
         list around the SAME item objects -- and combat mutates what it
         is handed. Run two inherited run one's damaged gear. Now each
         caller gets a deep copy.

    Cheap either way: the copy is a handful of objects per run, against
    a full nine-floor simulation.
    """
    import copy

    key = (rarity, item_level, slots)
    if key not in _SLOT_CACHE:
        # Seeded from the key, so identical for a given kit regardless of
        # what else has been generated -- in this process OR any other.
        #
        # NOT `hash()`, which was the first attempt and is wrong in a way
        # that hides: Python randomises string hashing per process unless
        # PYTHONHASHSEED is fixed, so the gear was stable within one run
        # and different between runs. The determinism test passed (it
        # repeats inside one process) while a baseline and a sweep in two
        # processes disagreed by forty points on the same region.
        #
        # crc32 of the key is stable everywhere, forever.
        import zlib
        key_bytes = f"{rarity}|{item_level}|{slots}".encode()
        local = random.Random(zlib.crc32(key_bytes))
        gen = LootGenerator(rng=local)
        items = []
        for _ in range(slots):
            tpl = item_template_service.pick_random_template(db, rng=local, rarity=rarity)
            if tpl is None:
                continue
            items.append(gen.generate_item(tpl, player_id=1, item_level=item_level,
                                           rarity_override=rarity))
        _SLOT_CACHE[key] = items
    return [copy.deepcopy(item) for item in _SLOT_CACHE[key]]


avatar = db.query(CharacterTemplate).filter_by(is_player_avatar=True).first()
pool = db.query(CharacterTemplate).filter_by(is_player_avatar=False).all()
def pc(t,l):
    o=PlayerCharacter(player_id=1,template_id=t.id,level=l,dupe_count=0); o.template=t; o.current_hp=None; return o

def fight(party, enemies, rng):
    # THE BATTLE MUST USE THE RUN'S RNG.
    #
    # This constructed `Battle(party, enemies)` with no rng, and
    # Battle.__init__ falls back to `random.Random()` -- a fresh,
    # unseeded generator per fight. So every crit, every dodge, every
    # speed tie-break was drawn from system entropy, and the same seed
    # produced different runs: measured, seed 1 returned
    # [False, True, False, True, True] over five identical repeats.
    #
    # That makes every number this tool has ever printed a sample of one
    # from an unknown distribution, and the endgame difficulty was tuned
    # off those numbers. The game is right to default to a fresh Random;
    # a BENCHMARK is not.
    b = Battle(party, enemies, rng=rng)
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
        off = co if room == RoomType.COMBAT else eo
        level = floor//10 + 1 + off

        if room == RoomType.BOSS:
            # THE BOSS ROOM GOES THROUGH get_boss_encounter, LIKE THE GAME.
            #
            # This used to draw 1-3 templates at random from the boss pool,
            # the same way it builds a combat room. The game does not do
            # that -- dungeon_service.enter_node calls get_boss_encounter,
            # which returns ONE boss, or a curated BOSS_GROUP whose members
            # were designed to appear together.
            #
            # The difference was not cosmetic, it was the entire endgame
            # reading. Abyssnia's elite_squad_weights are {1:10, 2:35,
            # 3:55}, so this stacked THREE random bosses 55% of the time
            # and measured the region at 28% -- below Entrospire, the
            # region after it. The runs were being killed by "Dorve,
            # Rohan" and "Cascade Failure, The Process": pairs the game
            # will never generate.
            #
            # region_config's own notes conclude Abyssnia's problem is its
            # boss pool and that offsets do nothing for it. That
            # conclusion was drawn from this benchmark, so it inherits
            # this bug.
            chosen = cat.get_boss_encounter(rng, region=region,
                                            final=(floor == NUM_FLOORS - 1))
            if not chosen: continue
            enemies = [build_enemy_combatant(t, level) for t in chosen]
        else:
            tpl = cat.get_templates_by_role(role, region=region) or []
            if not tpl: continue
            sw = d["combat_squad_weights"] if room==RoomType.COMBAT else d["elite_squad_weights"]
            n = rng.choices(list(sw.keys()), weights=list(sw.values()), k=1)[0]
            enemies=[build_enemy_combatant(rng.choice(tpl), level) for _ in range(n)]
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
