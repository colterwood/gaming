"""M32: materials and the Pym bench. ISO-8, vibranium and adamantium come
out of ore seams in the zones; the Pym Lab is Clint's forge — leave the
gear with the materials and the money and come back in a few days.
"""

import random

import pygame
import pytest

from game import config, data_loader
from game.core import save
from game.hub import activities, field
from game.hub.tower import HubScene
from game.progression import gear

from tests.test_tower_scene import FakeApp, choose, put_player_at


@pytest.fixture(scope="module")
def content():
    pygame.init()
    return data_loader.load_all()


@pytest.fixture
def lab(content):
    scene, app = HubScene(content), FakeApp(content)
    scene._switch_floor("pym_lab")
    app.game_state["credits"] = 5000
    return scene, app


class Rolls:
    """A scripted RNG: random() walks the given list."""

    def __init__(self, values):
        self.values = list(values)

    def random(self):
        return self.values.pop(0)

    def randint(self, lo, hi):
        return lo

    def randrange(self, n):
        return 0


# --- ore in the ground (1) ------------------------------------------------

def test_every_zone_yields_something_and_the_worst_yields_the_best(content):
    docks = content["zones"]["docks"]["mining"]
    hydra = content["zones"]["hydra_district"]["mining"]
    assert docks and hydra
    assert hydra.get("adamantium", 0) > docks.get("adamantium", 0)


def test_the_mining_table_is_rolled_cumulatively(content):
    zone = content["zones"]["hydra_district"]        # 0.20/0.35/0.30 sorted
    # sorted order is adamantium, iso8, vibranium
    assert field.mine_node(zone, Rolls([1.0, 0.10]))["item"] == "adamantium"
    assert field.mine_node(zone, Rolls([1.0, 0.40]))["item"] == "iso8"
    assert field.mine_node(zone, Rolls([1.0, 0.80]))["item"] == "vibranium"
    assert field.mine_node(zone, Rolls([1.0, 0.99]))["item"] is None


def test_a_watched_seam_springs_a_squad(content):
    zone = content["zones"]["hydra_district"]
    result = field.mine_node(zone, Rolls([0.0]))     # under the trap chance
    assert result["trap"] and result["item"] is None


def test_mining_costs_energy_and_time_and_the_seam_dries_up_for_the_day(content):
    scene, app = HubScene(content), FakeApp(content)
    state = app.game_state
    scene.area = "docks"
    scene.rng = Rolls([1.0, 0.0])                    # no trap, first material
    nodes = scene._ore_here(state)
    assert nodes, "the docks should have seams"
    tx, ty, _, _ = nodes[0]
    before_en, before_clock = state["energy"], state["time_minutes"]

    scene._mine_node(app, tx, ty)

    assert state["energy"] == before_en - config.MINE_ENERGY
    assert state["time_minutes"] == before_clock + config.MINE_MINUTES
    assert state["inventory"].get("iso8") == 1
    assert activities.spot_searched(state, "docks", tx, ty)
    assert (tx, ty) not in [(n[0], n[1]) for n in scene._ore_here(state)]


def test_seams_come_back_the_next_day(content):
    scene, app = HubScene(content), FakeApp(content)
    state = app.game_state
    scene.area = "docks"
    scene.rng = Rolls([1.0, 0.99])
    tx, ty, _, _ = scene._ore_here(state)[0]
    scene._mine_node(app, tx, ty)
    worked = len(scene._ore_here(state))
    activities.go_to_sleep(state)
    assert len(scene._ore_here(state)) == worked + 1


def test_a_tired_team_cannot_swing_at_rock(content):
    scene, app = HubScene(content), FakeApp(content)
    state = app.game_state
    scene.area = "docks"
    for hero_id in state["party"]:
        state["roster"][hero_id]["energy"] = 2
    state["energy"] = 2
    tx, ty, _, _ = scene._ore_here(state)[0]
    scene._mine_node(app, tx, ty)
    assert state["energy"] == 2
    assert not activities.spot_searched(state, "docks", tx, ty)


# --- leaving it at the bench (2) -----------------------------------------

def _stock(state, **materials):
    state["inventory"].update(materials)


def test_the_bench_takes_the_materials_and_the_money_up_front(lab):
    _, app = lab
    state = app.game_state
    _stock(state, iso8=3)
    gauntlets = app.content["items"]["combat_gauntlets"]

    result = gear.start_upgrade(state, gauntlets, app.content["items"])

    assert result["ok"]
    assert state["credits"] == 5000 - config.GEAR_UPGRADE_CREDITS[2]
    assert state["inventory"].get("iso8", 0) == 0
    assert gear.job_for(state, "combat_gauntlets")["days_left"] == \
        config.GEAR_UPGRADE_DAYS[2]


def test_it_refuses_without_the_materials(lab):
    _, app = lab
    state = app.game_state
    _stock(state, iso8=1)
    ok, reason, target = gear.can_upgrade(state, app.content["items"]["kevlar_weave"])
    assert not ok
    assert "Short" in reason and target == 2
    assert not gear.queue(state)


def test_it_refuses_without_the_credits(lab):
    _, app = lab
    state = app.game_state
    state["credits"] = 10
    _stock(state, iso8=3)
    ok, reason, _ = gear.can_upgrade(state, app.content["items"]["kevlar_weave"])
    assert not ok and "cr" in reason


def test_nothing_changes_until_you_collect_it(lab):
    _, app = lab
    state = app.game_state
    _stock(state, iso8=3)
    weave = app.content["items"]["kevlar_weave"]
    gear.start_upgrade(state, weave, app.content["items"])

    for _ in range(config.GEAR_UPGRADE_DAYS[2]):
        assert gear.level(state, "kevlar_weave") == 1
        gear.process_day(state, app.content["items"])

    assert gear.ready_jobs(state)                    # sitting on the bench
    assert gear.level(state, "kevlar_weave") == 1    # still not applied
    result = gear.collect(state, gear.ready_jobs(state)[0], app.content["items"])
    assert result["ok"]
    assert gear.level(state, "kevlar_weave") == 2


def test_collecting_early_is_refused(lab):
    _, app = lab
    state = app.game_state
    _stock(state, iso8=3)
    weave = app.content["items"]["kevlar_weave"]
    gear.start_upgrade(state, weave, app.content["items"])
    result = gear.collect(state, gear.queue(state)[0], app.content["items"])
    assert not result["ok"]
    assert gear.level(state, "kevlar_weave") == 1


def test_the_same_design_cannot_be_queued_twice(lab):
    _, app = lab
    state = app.game_state
    _stock(state, iso8=6)
    weave = app.content["items"]["kevlar_weave"]
    gear.start_upgrade(state, weave, app.content["items"])
    second = gear.start_upgrade(state, weave, app.content["items"])
    assert not second["ok"]
    assert len(gear.queue(state)) == 1


def test_a_maxed_design_has_nothing_left_to_give(lab):
    _, app = lab
    state = app.game_state
    state["gear_levels"]["kevlar_weave"] = config.GEAR_LEVEL_MAX
    ok, reason, target = gear.can_upgrade(state, app.content["items"]["kevlar_weave"])
    assert not ok and target is None
    assert "as good as it gets" in reason


def test_the_upgrade_reaches_gear_already_being_worn(lab):
    _, app = lab
    state = app.game_state
    state["inventory"]["kevlar_weave"] = 1
    gear.equip(state, "iron_man", "kevlar_weave", app.content["items"])
    _stock(state, iso8=3)
    gear.start_upgrade(state, app.content["items"]["kevlar_weave"],
                       app.content["items"])
    for _ in range(config.GEAR_UPGRADE_DAYS[2]):
        gear.process_day(state, app.content["items"])
    gear.collect(state, gear.ready_jobs(state)[0], app.content["items"])
    # The schematic improved, so the piece on Iron Man's back improved.
    effects = gear.total_effects(state, state["roster"]["iron_man"],
                                 app.content["items"])
    assert effects["durability"] == 3               # 2 x 1.5


# --- through the bench, and the night (3) --------------------------------

def test_the_bench_menu_hands_it_over_and_takes_it_back(lab):
    scene, app = lab
    state = app.game_state
    _stock(state, iso8=3)
    put_player_at(scene, 8, 5)                       # the Pym bench
    scene.handle_key(app, pygame.K_RETURN)
    choose(scene, app, "Combat Gauntlets ->")
    assert gear.job_for(state, "combat_gauntlets")

    for _ in range(config.GEAR_UPGRADE_DAYS[2]):
        gear.process_day(state, app.content["items"])
    scene.reset_modes()
    put_player_at(scene, 8, 5)
    scene.handle_key(app, pygame.K_RETURN)
    choose(scene, app, "COLLECT")
    assert gear.level(state, "combat_gauntlets") == 2


def test_a_night_at_the_tower_advances_the_bench(content, monkeypatch, tmp_path):
    from game.__main__ import App
    from game.core.state_machine import GameState

    monkeypatch.setattr(config, "SAVE_DIR", str(tmp_path))
    monkeypatch.setattr(data_loader, "load_all", lambda: content)
    app = App()
    app.new_game(slot=1)
    for to in (GameState.TITLE, GameState.PATH_SELECT, GameState.HUB):
        app.machine.transition(to)
    state = app.game_state
    state["credits"] = 5000
    state["inventory"]["iso8"] = 3
    gear.start_upgrade(state, content["items"]["kevlar_weave"], content["items"])

    app.go_to_sleep()

    assert gear.job_for(state, "kevlar_weave")["days_left"] == \
        config.GEAR_UPGRADE_DAYS[2] - 1


def test_an_unpowered_pym_lab_offers_the_repair_instead(content):
    scene, app = HubScene(content), FakeApp(content)
    state = app.game_state
    state["repairs"].pop("repair_pym_lab")
    state["story_flags"]["pym_lab_repaired"] = False
    scene._switch_floor("pym_lab")
    put_player_at(scene, 8, 5)
    scene.handle_key(app, pygame.K_RETURN)
    assert scene.submenu["items"][0][0] == "Get Into the Pym Lab"


# --- the recipes are reachable (4) ---------------------------------------

def test_every_recipe_material_can_actually_be_mined(content):
    mineable = {m for z in content["zones"].values()
                for m in z.get("mining", {})}
    for materials in config.GEAR_UPGRADE_MATERIALS.values():
        assert set(materials) <= mineable


def test_there_is_a_recipe_for_every_level_above_the_first(content):
    for level in range(2, config.GEAR_LEVEL_MAX + 1):
        assert gear.upgrade_recipe(level) is not None
    assert gear.upgrade_recipe(config.GEAR_LEVEL_MAX + 1) is None
