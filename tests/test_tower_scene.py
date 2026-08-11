"""M8: walkable tower scene plumbing — interactions route to the right
logic, characters are placed per story state. Headless (no display)."""

import pygame
import pytest

from game import config, data_loader
from game.core import save
from game.hub import story
from game.hub.tower import FLOORS, HUD_H, TILE, HubScene


class FakeMachine:
    def __init__(self):
        self.transitions = []

    def transition(self, to):
        self.transitions.append(to)


class FakeApp:
    def __init__(self, content):
        self.content = content
        self.game_state = save.new_game_state()
        self.game_state["path"] = "avengers"
        for c in content["characters"].values():
            if c["recruit"]["method"] == "starter":
                self.game_state["roster"][c["id"]] = {
                    "trained_ranks": {}, "attribute_xp": {}, "perks": [],
                    "perk_choices": {}, "gear": {}, "ult_charge": 0}
        story.init(self.game_state, content["story"])
        self.machine = FakeMachine()
        self.slept = []
        self.battles = []

    def go_to_sleep(self, passed_out=False):
        self.slept.append(passed_out)

    def start_battle(self, enemy_ids=None, quest=None):
        self.battles.append((tuple(enemy_ids), quest["id"] if quest else None))


@pytest.fixture(scope="module")
def content():
    pygame.init()
    return data_loader.load_all()


def scene_with_app(content):
    return HubScene(content), FakeApp(content)


def put_player_at(scene, tile_x, tile_y):
    scene.px = tile_x * TILE + TILE // 2
    scene.py = HUD_H + tile_y * TILE + TILE // 2


def choose(scene, app, label_prefix):
    items = scene.submenu["items"]
    for i, (label, disabled, cb) in enumerate(items):
        if label.startswith(label_prefix):
            scene.submenu["index"] = i
            scene._submenu_key(app, pygame.K_RETURN)
            return
    raise AssertionError(f"no submenu item starting with {label_prefix!r}: "
                         f"{[i[0] for i in items]}")


def test_talk_to_jarvis_gives_bond(content):
    scene, app = scene_with_app(content)
    put_player_at(scene, 4, 7)                  # next to Jarvis (4, 6)
    hit = scene._nearest_interaction(app.game_state)
    assert hit == ("char", "jarvis", "Edwin Jarvis")
    scene.handle_key(app, pygame.K_RETURN)
    assert scene.mode == "submenu"
    choose(scene, app, "Talk")
    assert app.game_state["bonds"]["jarvis"]["points"] == 15
    assert scene.mode == "normal"


def test_gift_jarvis_loved(content):
    scene, app = scene_with_app(content)
    app.game_state["inventory"]["double_espresso"] = 1
    put_player_at(scene, 4, 7)
    scene.handle_key(app, pygame.K_RETURN)
    choose(scene, app, "Give Gift")
    assert scene.mode == "submenu"              # gift picker
    choose(scene, app, "Double Espresso")
    assert app.game_state["bonds"]["jarvis"]["points"] == 80
    assert "double_espresso" not in app.game_state["inventory"]


def test_starters_give_flavor_not_bonds(content):
    scene, app = scene_with_app(content)
    put_player_at(scene, 10, 4)                 # below Iron Man (10, 3)
    hit = scene._nearest_interaction(app.game_state)
    assert hit[1] == "iron_man"
    scene.handle_key(app, pygame.K_RETURN)
    assert scene.mode == "normal"               # no menu, just a flavor line
    assert "iron_man" not in app.game_state.get("bonds", {})
    assert scene.messages                        # something was said


def test_ops_console_launches_story_battle(content):
    scene, app = scene_with_app(content)
    scene.floor = "ops"
    put_player_at(scene, 8, 5)                  # below the console row
    scene.handle_key(app, pygame.K_RETURN)
    assert scene.mode == "submenu"
    choose(scene, app, "Mission - Shattered Shield")
    assert app.battles == [(("hydra_grunt", "hydra_grunt", "hydra_grunt"),
                            "ch1_shattered_shield")]
    assert app.game_state["energy"] == config.DAILY_ENERGY - config.MISSION_ENERGY


def test_elevator_switches_floor(content):
    scene, app = scene_with_app(content)
    put_player_at(scene, 17, 2)                 # spawn, below elevator
    scene.handle_key(app, pygame.K_RETURN)
    choose(scene, app, "Training Floor")
    assert scene.floor == "training"
    assert scene.mode == "normal"


def test_bed_sleeps(content):
    scene, app = scene_with_app(content)
    put_player_at(scene, 2, 14)                 # next to the bed (1-2, 15)
    hit = scene._nearest_interaction(app.game_state)
    assert hit == ("station", "bed", "Sleep")
    scene.handle_key(app, pygame.K_RETURN)
    assert app.slept == [False]


def test_hulk_placement_follows_story(content):
    scene, app = scene_with_app(content)
    scene.floor = "training"
    state = app.game_state
    ids = [cid for cid, _, _ in scene._characters_here(state)]
    assert "hulk" not in ids                    # not arrived yet
    state["story_flags"]["hulk_arrived"] = True
    ids = [cid for cid, _, _ in scene._characters_here(state)]
    assert "hulk" in ids                        # brooding on the training floor
    state["roster"]["hulk"] = {"trained_ranks": {}, "attribute_xp": {},
                               "perks": [], "perk_choices": {}, "gear": {},
                               "ult_charge": 0}
    ids = [cid for cid, _, _ in scene._characters_here(state)]
    assert "hulk" not in ids                    # recruited: moved to common
    scene.floor = "common"
    ids = [cid for cid, _, _ in scene._characters_here(state)]
    assert "hulk" in ids


def test_maps_are_wellformed(content):
    for floor in FLOORS.values():
        assert len(floor["map"]) == 21
        for row in floor["map"]:
            assert len(row) == 40, f"bad row width in {floor['name']}: {len(row)}"
        sx, sy = floor["spawn"]
        assert floor["map"][sy][sx] == "."      # spawn tile walkable
