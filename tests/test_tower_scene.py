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
                    "perk_choices": {}, "gear": {}, "ult_charge": 0,
                    "energy": 100, "unspent_xp": 0}
        self.game_state["party"] = sorted(self.game_state["roster"], reverse=True)
        story.init(self.game_state, content["story"])
        self.machine = FakeMachine()
        self.slept = []
        self.battles = []

    def go_to_sleep(self, passed_out=False):
        self.slept.append(passed_out)

    def start_battle(self, enemy_ids=None, quest=None, ambush=False):
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


def test_benched_starter_chats_no_bonds(content):
    scene, app = scene_with_app(content)
    app.game_state["party"] = ["captain_america"]     # iron man benched, idle
    put_player_at(scene, 8, 14)                       # near the idle spot (8, 15)
    hit = scene._nearest_interaction(app.game_state)
    assert hit[1] == "iron_man"
    scene.handle_key(app, pygame.K_RETURN)
    assert scene.mode == "submenu"
    choose(scene, app, "Chat")
    assert scene.mode == "normal"                     # a flavor line, no points
    assert "iron_man" not in app.game_state.get("bonds", {})
    assert scene.messages


def test_party_members_are_not_placed_in_world(content):
    scene, app = scene_with_app(content)
    ids = [cid for cid, _, _ in scene._characters_here(app.game_state)]
    assert "iron_man" not in ids and "captain_america" not in ids   # they follow you
    app.game_state["party"] = ["captain_america"]
    ids = [cid for cid, _, _ in scene._characters_here(app.game_state)]
    assert "iron_man" in ids                                        # benched now


def test_mission_flow_fly_and_engage(content):
    scene, app = scene_with_app(content)
    state = app.game_state
    # Ops console shows the mission details and offers the flight
    scene.floor = "ops"
    put_player_at(scene, 8, 5)
    scene.handle_key(app, pygame.K_RETURN)
    labels = [i[0] for i in scene.submenu["items"]]
    assert any("Where: Hudson Docks" in l for l in labels)
    assert any("Deadline: 3 day(s) left" in l for l in labels)
    choose(scene, app, "  Fly to Hudson Docks")
    assert scene.area == "docks"
    # walk to the target squad and engage
    zone = content["zones"]["docks"]
    put_player_at(scene, zone["target_spot"][0], zone["target_spot"][1] + 1)
    hit = scene._nearest_interaction(state)
    assert hit[0] == "target"
    scene.handle_key(app, pygame.K_RETURN)
    assert app.battles == [(("hydra_grunt", "hydra_grunt", "hydra_grunt"),
                            "ch1_shattered_shield")]
    assert state["energy"] == config.DAILY_ENERGY - config.MISSION_ENERGY


def test_locked_mission_shows_cooldown(content):
    scene, app = scene_with_app(content)
    state = app.game_state
    quest = story.current_quest(state, content["story"])
    story.fail_mission(state, quest)
    scene.floor = "ops"
    put_player_at(scene, 8, 5)
    scene.handle_key(app, pygame.K_RETURN)
    labels = [i[0] for i in scene.submenu["items"]]
    assert any("FAILED" in l and "retry in" in l for l in labels)
    # and the target squad is not standing in the zone
    scene.area = "docks"
    assert scene._mission_target(state) is None


def test_swap_menu_and_requirement_block(content):
    scene, app = scene_with_app(content)
    state = app.game_state
    from game.hub import passive
    # bench iron man on the support task (needs INT 4+; Cap has 3)
    state["party"] = ["captain_america"]
    ok, _ = passive.assign(content, state, "iron_man", "support")
    assert ok
    put_player_at(scene, 10, 5)                       # ops floor support spot
    scene.floor = "ops"
    hit = scene._nearest_interaction(state)
    assert hit[1] == "iron_man"
    scene.handle_key(app, pygame.K_RETURN)
    choose(scene, app, "Swap into team...")
    labels = [i[0] for i in scene.submenu["items"]]
    # open slot exists (party of 1) so adding is offered too
    assert any(l.startswith("Add Iron Man") for l in labels)
    # swapping out Cap is blocked: he can't cover the INT-4 support task
    blocked = [i for i in scene.submenu["items"]
               if i[0].startswith("Swap out Captain America")]
    assert blocked and blocked[0][1] is True


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
