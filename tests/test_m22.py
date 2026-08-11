"""M22: sparring pays a flat +20 to every stat, and the Ops console briefs
you without driving you to the target."""

import pygame
import pytest

from game import config, data_loader
from game.hub import dispatch, story
from game.hub.tower import HubScene

from tests.test_tower_scene import FakeApp, choose, put_player_at


@pytest.fixture(scope="module")
def content():
    pygame.init()
    return data_loader.load_all()


def task_by_id(content, task_id):
    return next(t for t in content["assignments"] if t["id"] == task_id)


# --- sparring (1) ---

def test_sparring_is_worth_twenty_to_every_stat(content):
    task = task_by_id(content, "spar_rookies")
    assert task["xp"] == 20 * len(config.ATTRIBUTES) == 120


def test_a_spar_pays_out_across_the_board(content):
    state = FakeApp(content).game_state
    state["roster"]["ant_man"] = {"trained_ranks": {"agility": 1},
                                  "attribute_xp": {}, "perks": [],
                                  "perk_choices": {}, "gear": {},
                                  "ult_charge": 0, "energy": 100}
    state["party"] = ["iron_man", "captain_america", "ant_man"]
    task = task_by_id(content, "spar_rookies")
    crew = ["iron_man", "ant_man"]
    mult = dispatch.reward_mult(content, state, crew)
    ok, message = dispatch.send(content, state, task, crew)
    assert ok, message
    dispatch.process_day(content, state)               # 1-day job: home
    for hero_id in crew:
        gains = state["roster"][hero_id]["attribute_xp"]
        assert set(gains) == set(config.ATTRIBUTES), hero_id
        assert sum(gains.values()) == round(task["xp"] * mult)
        # baseline crew -> the flat +20 the job advertises
        assert all(abs(v - 20 * mult) <= 1 for v in gains.values()), gains


# --- no taxi from the Ops console (2) ---

def test_accepting_a_mission_does_not_offer_a_ride(content):
    scene, app = HubScene(content), FakeApp(content)
    state = app.game_state
    scene.floor = "ops"
    put_player_at(scene, 8, 5)
    scene.handle_key(app, pygame.K_RETURN)
    choose(scene, app, "  ACCEPT MISSION")
    labels = [i[0] for i in scene.submenu["items"]]
    assert story.is_accepted(state, story.current_quest(state, content["story"]))
    assert any("Where: Hudson Docks" in l for l in labels)   # still briefed
    assert not any("Fly to" in l for l in labels)            # but not driven
    assert scene.area == "tower"
    # and nothing on the reopened menu will move you either
    for label, disabled, callback in scene.submenu["items"]:
        assert disabled or label == "Close", label


def test_the_cursor_rests_on_the_briefing(content):
    scene, app = HubScene(content), FakeApp(content)
    scene.floor = "ops"
    put_player_at(scene, 8, 5)
    scene.handle_key(app, pygame.K_RETURN)
    choose(scene, app, "  ACCEPT MISSION")
    assert scene.submenu["index"] == 0
    # pressing Enter on it does nothing rather than launching a trip
    scene._submenu_key(app, pygame.K_RETURN)
    assert scene.mode == "submenu" and scene.area == "tower"


def test_the_player_still_gets_there_under_their_own_steam(content):
    scene, app = HubScene(content), FakeApp(content)
    state = app.game_state
    story.accept(state, story.current_quest(state, content["story"]))
    put_player_at(scene, 17, 2)                     # the elevator
    scene.handle_key(app, pygame.K_RETURN)
    choose(scene, app, "Quinjet: Hudson Docks")
    assert scene.area == "docks"
    assert state["time_minutes"] == (config.DAY_START_MINUTES
                                     + config.TRAVEL_MINUTES)
