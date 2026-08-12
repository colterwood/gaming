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

ADVANCED = ("vibranium", "adamantium")


def test_chapters_one_and_two_hand_out_basic_stock_only(content):
    # The material ladder (what tier drops where, what each metal DOES to a
    # piece) is an open design question. Until it exists, nothing advanced
    # is reachable — the early game must not be handing out adamantium.
    for zone in content["zones"].values():
        assert set(zone.get("mining", {})) == {"iso8"}, zone["id"]


def test_the_worse_the_district_the_better_the_odds(content):
    chance = {z["id"]: sum(z.get("mining", {}).values())
              for z in content["zones"].values()}
    assert chance["docks"] < chance["midtown"] < chance["hydra_district"]


def test_no_recipe_asks_for_a_metal_the_world_cannot_give(content):
    mineable = {m for z in content["zones"].values()
                for m in z.get("mining", {})}
    for materials in config.GEAR_UPGRADE_MATERIALS.values():
        assert set(materials) <= mineable
        assert not set(materials) & set(ADVANCED)


def test_the_mining_table_is_rolled_cumulatively(content):
    zone = content["zones"]["hydra_district"]        # iso8 at 0.75
    assert field.mine_node(zone, Rolls([1.0, 0.10]))["item"] == "iso8"
    assert field.mine_node(zone, Rolls([1.0, 0.74]))["item"] == "iso8"
    assert field.mine_node(zone, Rolls([1.0, 0.80]))["item"] is None


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


def test_the_bench_takes_the_materials_the_money_and_the_gear(lab):
    _, app = lab
    state = app.game_state
    _stock(state, iso8=3, combat_gauntlets=1)
    gauntlets = app.content["items"]["combat_gauntlets"]

    result = gear.start_upgrade(state, gauntlets, app.content["items"])

    assert result["ok"]
    assert state["credits"] == 5000 - config.GEAR_UPGRADE_CREDITS[2]
    assert state["inventory"].get("iso8", 0) == 0
    assert state["inventory"].get("combat_gauntlets", 0) == 0   # handed over
    assert gear.job_for(state, "combat_gauntlets")["days_left"] == \
        config.GEAR_UPGRADE_DAYS[2]


def test_you_cannot_upgrade_a_design_you_do_not_own(lab):
    _, app = lab
    state = app.game_state
    _stock(state, iso8=3)
    ok, reason, target = gear.can_upgrade(
        state, app.content["items"]["combat_gauntlets"])
    assert not ok
    assert "own one first" in reason and target == 2
    assert not gear.queue(state)


def test_it_refuses_without_the_materials(lab):
    _, app = lab
    state = app.game_state
    _stock(state, iso8=1, kevlar_weave=1)
    ok, reason, target = gear.can_upgrade(state, app.content["items"]["kevlar_weave"])
    assert not ok
    assert "Short" in reason and target == 2
    assert not gear.queue(state)


def test_it_refuses_without_the_credits(lab):
    _, app = lab
    state = app.game_state
    state["credits"] = 10
    _stock(state, iso8=3, kevlar_weave=1)
    ok, reason, _ = gear.can_upgrade(state, app.content["items"]["kevlar_weave"])
    assert not ok and "cr" in reason


def test_nothing_changes_until_you_collect_it(lab):
    _, app = lab
    state = app.game_state
    _stock(state, iso8=3, kevlar_weave=1)
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
    _stock(state, iso8=3, kevlar_weave=1)
    weave = app.content["items"]["kevlar_weave"]
    gear.start_upgrade(state, weave, app.content["items"])
    result = gear.collect(state, gear.queue(state)[0], app.content["items"])
    assert not result["ok"]
    assert gear.level(state, "kevlar_weave") == 1
    assert state["inventory"].get("kevlar_weave", 0) == 0   # still on the bench


def test_the_same_design_cannot_be_queued_twice(lab):
    _, app = lab
    state = app.game_state
    _stock(state, iso8=6, kevlar_weave=2)
    weave = app.content["items"]["kevlar_weave"]
    gear.start_upgrade(state, weave, app.content["items"])
    second = gear.start_upgrade(state, weave, app.content["items"])
    assert not second["ok"]
    assert len(gear.queue(state)) == 1
    assert state["inventory"]["kevlar_weave"] == 1          # the spare stays


def test_a_maxed_design_has_nothing_left_to_give(lab):
    _, app = lab
    state = app.game_state
    state["gear_levels"]["kevlar_weave"] = config.GEAR_LEVEL_MAX
    ok, reason, target = gear.can_upgrade(state, app.content["items"]["kevlar_weave"])
    assert not ok and target is None
    assert "as good as it gets" in reason


def test_upgrading_worn_gear_takes_it_off_the_hero(lab):
    """You give the piece up and fight without it — that waiting IS the
    cost of the upgrade."""
    _, app = lab
    state = app.game_state
    state["inventory"]["kevlar_weave"] = 1
    gear.equip(state, "iron_man", "kevlar_weave", app.content["items"])
    _stock(state, iso8=3)

    result = gear.start_upgrade(state, app.content["items"]["kevlar_weave"],
                                app.content["items"])

    assert result["stripped"] == "iron_man"
    assert gear.equipped(state["roster"]["iron_man"]) == {}
    assert state["inventory"].get("kevlar_weave", 0) == 0
    # No armour bonus at all while it sits on the bench.
    assert gear.total_effects(state, state["roster"]["iron_man"],
                              app.content["items"]) == {}


def test_collecting_puts_it_straight_back_on_the_hero_it_came_off(lab):
    _, app = lab
    state = app.game_state
    state["inventory"]["kevlar_weave"] = 1
    gear.equip(state, "iron_man", "kevlar_weave", app.content["items"])
    _stock(state, iso8=3)
    gear.start_upgrade(state, app.content["items"]["kevlar_weave"],
                       app.content["items"])
    for _ in range(config.GEAR_UPGRADE_DAYS[2]):
        gear.process_day(state, app.content["items"])

    result = gear.collect(state, gear.ready_jobs(state)[0], app.content["items"])

    assert result["refitted"] == "iron_man"
    effects = gear.total_effects(state, state["roster"]["iron_man"],
                                 app.content["items"])
    assert effects["durability"] == 3               # 2 x 1.5


def test_a_slot_filled_while_it_was_away_gets_the_piece_back_in_the_bag(lab):
    _, app = lab
    state = app.game_state
    state["inventory"]["kevlar_weave"] = 1
    gear.equip(state, "iron_man", "kevlar_weave", app.content["items"])
    _stock(state, iso8=3, stark_underlay=1)
    gear.start_upgrade(state, app.content["items"]["kevlar_weave"],
                       app.content["items"])
    gear.equip(state, "iron_man", "stark_underlay", app.content["items"])
    for _ in range(config.GEAR_UPGRADE_DAYS[2]):
        gear.process_day(state, app.content["items"])

    result = gear.collect(state, gear.ready_jobs(state)[0], app.content["items"])

    assert result["refitted"] is None
    assert gear.equipped(state["roster"]["iron_man"])["armor"] == "stark_underlay"
    assert state["inventory"]["kevlar_weave"] == 1


def test_a_spare_in_the_bag_is_handed_over_before_the_worn_one(lab):
    _, app = lab
    state = app.game_state
    state["inventory"]["kevlar_weave"] = 2
    gear.equip(state, "iron_man", "kevlar_weave", app.content["items"])
    _stock(state, iso8=3)
    result = gear.start_upgrade(state, app.content["items"]["kevlar_weave"],
                                app.content["items"])
    assert result["stripped"] is None
    assert gear.equipped(state["roster"]["iron_man"])["armor"] == "kevlar_weave"
    assert state["inventory"].get("kevlar_weave", 0) == 0


# --- through the bench, and the night (3) --------------------------------

def test_the_bench_menu_hands_it_over_and_takes_it_back(lab):
    scene, app = lab
    state = app.game_state
    _stock(state, iso8=3, combat_gauntlets=1)
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
    state["inventory"]["kevlar_weave"] = 1
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
