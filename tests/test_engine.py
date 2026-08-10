"""Turn engine, enemy AI, statuses, enrage, items (M1)."""

import pytest

from game import data_loader
from game.combat.engine import BattleEngine
from game.combat.entities import Combatant, make_enemy_group


class ScriptedRng:
    """uniform() -> no dodge/no crit by default; randint scripted per call."""

    def __init__(self, randints=None, uniforms=None):
        self.randints = list(randints or [])
        self.uniforms = list(uniforms or [])

    def randint(self, a, b):
        return self.randints.pop(0) if self.randints else a

    def uniform(self, a, b):
        return self.uniforms.pop(0) if self.uniforms else 99.0


@pytest.fixture(scope="module")
def content():
    return data_loader.load_all()


def make_heroes(content, *ids):
    return [Combatant(content["characters"][i], is_hero=True) for i in ids]


def std_battle(content, rng=None, enemy_ids=("hydra_grunt", "hydra_grunt", "hydra_grunt")):
    heroes = make_heroes(content, "iron_man", "captain_america")
    enemies = make_enemy_group([content["enemies"][e] for e in enemy_ids])
    return BattleEngine(heroes, enemies, rng=rng or ScriptedRng(),
                        items_data=content["items"])


def drive(engine, hero_action):
    """Step engine one full cycle: heroes use hero_action, enemies use AI."""
    actor = engine.current()
    events = engine.begin_turn()
    if engine.current() is not actor:      # turn consumed by stun/burn death
        return events
    if actor.is_hero:
        return events + engine.take_turn(hero_action(actor, engine))
    return events + engine.take_turn(engine.enemy_action())


def test_unique_enemy_instance_ids(content):
    engine = std_battle(content)
    ids = [e.id for e in engine.enemies]
    assert ids == ["hydra_grunt_1", "hydra_grunt_2", "hydra_grunt_3"]
    assert engine.enemies[1].name == "HYDRA Grunt 2"


def test_initiative_order_speed_times_ten_plus_roll(content):
    # Iron Man speed 6, Cap speed 2, grunts speed 2.
    # Rolls: IM 1 -> 61, Cap 6 -> 26, grunts 5,4,3 -> 25,24,23
    rng = ScriptedRng(randints=[1, 6, 5, 4, 3])
    engine = std_battle(content, rng=rng)
    assert [c.id for c in engine.round_order] == [
        "iron_man", "captain_america", "hydra_grunt_1", "hydra_grunt_2", "hydra_grunt_3"]


def test_full_battle_to_win(content):
    engine = std_battle(content)

    def basic_at_first_enemy(actor, eng):
        target = eng.living(eng.enemies)[0]
        basic = actor.abilities_of_type("basic")[0]
        return {"type": "ability", "ability_id": basic["id"], "target_id": target.id}

    for _ in range(200):
        if engine.outcome:
            break
        drive(engine, basic_at_first_enemy)
    assert engine.outcome == "win"
    assert engine.rewards() == {"xp": 60, "credits": 45}  # 3 grunts: 3*20 xp, 3*15 credits


def test_special_costs_battle_energy(content):
    engine = std_battle(content)
    iron_man = engine.heroes[0]
    while engine.current() is not iron_man:
        drive(engine, lambda a, e: {"type": "defend"})
    engine.begin_turn()
    start_energy = iron_man.energy          # 20 + 5*5 = 45
    assert start_energy == 45
    target = engine.living(engine.enemies)[0]
    events = engine.take_turn({"type": "ability", "ability_id": "unibeam",
                               "target_id": target.id})
    assert iron_man.energy == start_energy - 12
    # Unibeam vs grunt: 30 + 5*5 - 2*2 = 51
    assert any(e["kind"] == "damage" and e["amount"] == 51 for e in events)


def test_defend_halves_and_resets_next_turn(content):
    engine = std_battle(content, enemy_ids=("hydra_grunt",))
    cap = engine.heroes[1]
    cap.defending = True
    grunt = engine.enemies[0]
    # force it to be the grunt's turn
    engine.round_order = [grunt] + [c for c in engine.round_order if c is not grunt]
    engine._turn_index = 0
    engine.begin_turn()
    events = engine.take_turn({"type": "ability", "ability_id": "rifle_burst",
                               "target_id": cap.id})
    # Rifle burst vs Cap: 9 + 2*4 - 2*2 = 13 -> defended -> 6
    assert any(e["kind"] == "damage" and e["amount"] == 6 for e in events)
    # Cap's own turn start clears the defend flag
    while engine.current() is not cap:
        engine.begin_turn()
        engine.take_turn(engine.enemy_action() if not engine.current().is_hero
                         else {"type": "defend"})
    engine.begin_turn()
    assert cap.defending is False


def test_stun_skips_one_turn(content):
    engine = std_battle(content, enemy_ids=("hydra_grunt",))
    iron_man = engine.heroes[0]
    iron_man.statuses["stun"] = 1
    engine.round_order = [iron_man] + [c for c in engine.round_order if c is not iron_man]
    engine._turn_index = 0
    events = engine.begin_turn()
    assert any(e["kind"] == "stunned" for e in events)
    assert engine.current() is not iron_man
    assert "stun" not in iron_man.statuses
    assert iron_man.ult_charge == 0         # no per-turn charge while stunned


def test_burn_ticks_and_expires(content):
    engine = std_battle(content, enemy_ids=("hydra_grunt",))
    iron_man = engine.heroes[0]
    iron_man.statuses["burn"] = 3
    hp = iron_man.hp
    engine.round_order = [iron_man]
    engine._turn_index = 0
    events = engine.begin_turn()
    assert any(e["kind"] == "burn" and e["amount"] == 5 for e in events)
    assert iron_man.hp == hp - 5
    assert iron_man.statuses["burn"] == 2


def test_ult_charges_and_fires(content):
    engine = std_battle(content)
    iron_man = engine.heroes[0]
    # +20 per turn taken
    engine.round_order = [iron_man]
    engine._turn_index = 0
    engine.begin_turn()
    engine.take_turn({"type": "defend"})
    assert iron_man.ult_charge == 20
    # +10 per hit received
    iron_man.take_damage(5)
    assert iron_man.ult_charge == 30
    # fire at 100: resets to 0, hits all enemies
    iron_man.ult_charge = 100
    assert iron_man.ult_ready()
    engine.round_order = [iron_man]
    engine._turn_index = 0
    engine.begin_turn()
    events = engine.take_turn({"type": "ability", "ability_id": "house_party",
                               "target_id": None})
    # House Party vs grunts: 55 + 5*5 - 4 = 76 each, all three hit
    damage_events = [e for e in events if e["kind"] == "damage"]
    assert len(damage_events) == 3
    assert all(e["amount"] == 76 for e in damage_events)
    assert iron_man.ult_charge == 0


def test_aggressive_ai_picks_highest_damage_at_lowest_hp(content):
    engine = std_battle(content, enemy_ids=("hydra_grunt",))
    grunt = engine.enemies[0]
    cap = engine.heroes[1]
    cap.hp = 10                             # lowest HP target
    engine.round_order = [grunt]
    engine._turn_index = 0
    action = engine.enemy_action()
    # Frag grenade (special, 13 + 2*5 = 23 base) beats rifle burst (9 + 8 = 17)
    assert action == {"type": "ability", "ability_id": "frag_grenade", "target_id": cap.id}
    grunt.energy = 0                        # can't afford the special anymore
    action = engine.enemy_action()
    assert action["ability_id"] == "rifle_burst"


def test_defensive_ai_defends_when_hurt(content):
    engine = std_battle(content, enemy_ids=("hydra_enforcer",))
    enforcer = engine.enemies[0]
    engine.round_order = [enforcer]
    engine._turn_index = 0
    assert engine.enemy_action()["type"] == "ability"   # healthy: basic attack
    enforcer.hp = int(enforcer.max_hp * 0.3)
    assert engine.enemy_action() == {"type": "defend"}


def test_support_ai_heals_hurt_ally(content):
    engine = std_battle(content, enemy_ids=("hydra_medic", "hydra_grunt"))
    medic, grunt = engine.enemies
    engine.round_order = [medic]
    engine._turn_index = 0
    assert engine.enemy_action()["type"] == "ability"   # nobody hurt: attack
    grunt.hp = int(grunt.max_hp * 0.4)
    action = engine.enemy_action()
    assert action == {"type": "ability", "ability_id": "field_stim", "target_id": grunt.id}


def test_crossbones_enrage_below_30pct(content):
    engine = std_battle(content, enemy_ids=("crossbones",))
    crossbones = engine.enemies[0]
    iron_man = engine.heroes[0]
    engine.round_order = [crossbones]
    engine._turn_index = 0
    engine.begin_turn()
    events = engine.take_turn({"type": "ability", "ability_id": "gauntlet_smash",
                               "target_id": iron_man.id})
    # 15 + 5*4 - 5*2 = 25 base, not enraged
    assert any(e["kind"] == "damage" and e["amount"] == 25 for e in events)
    crossbones.hp = int(crossbones.max_hp * 0.2)        # under 30% -> enrage
    engine.round_order = [crossbones]
    engine._turn_index = 0
    engine.begin_turn()
    events = engine.take_turn({"type": "ability", "ability_id": "gauntlet_smash",
                               "target_id": iron_man.id})
    assert any(e["kind"] == "damage" and e["amount"] == int(25 * 1.5) for e in events)


def test_status_applies_on_hit(content):
    engine = std_battle(content, enemy_ids=("hydra_siege_captain",))
    captain = engine.enemies[0]
    iron_man = engine.heroes[0]
    engine.round_order = [captain]
    engine._turn_index = 0
    engine.begin_turn()
    events = engine.take_turn({"type": "ability", "ability_id": "incendiary_rounds",
                               "target_id": iron_man.id})
    assert any(e["kind"] == "status" and e["status"] == "burn" for e in events)
    assert iron_man.statuses.get("burn") == 3


def test_item_heals_and_consumes(content):
    engine = std_battle(content)
    engine.inventory["med_kit"] = 1
    iron_man = engine.heroes[0]
    iron_man.hp = 100
    engine.round_order = [iron_man]
    engine._turn_index = 0
    engine.begin_turn()
    events = engine.take_turn({"type": "item", "item_id": "med_kit",
                               "target_id": iron_man.id})
    assert any(e["kind"] == "heal" and e["amount"] == 40 for e in events)
    assert iron_man.hp == 140
    assert engine.inventory["med_kit"] == 0


def test_dodge_produces_no_damage(content):
    # Cap agility 5 -> 15% dodge; scripted uniform 5.0 < 15 dodges
    rng = ScriptedRng(uniforms=[5.0])
    engine = std_battle(content, rng=rng, enemy_ids=("hydra_grunt",))
    cap = engine.heroes[1]
    grunt = engine.enemies[0]
    engine.round_order = [grunt]
    engine._turn_index = 0
    engine.begin_turn()
    events = engine.take_turn({"type": "ability", "ability_id": "rifle_burst",
                               "target_id": cap.id})
    assert any(e["kind"] == "dodge" for e in events)
    assert cap.hp == cap.max_hp
