"""M30: the Med Bay. Sit in the chair and the clock runs while you mend —
10% of the daily maximum per 10 in-game minutes, paid in hours and nothing
else. This is the only place the day's energy cap can be bought back.
"""

import pygame
import pytest

from game import config, data_loader
from game.core import energy
from game.hub import activities
from game.hub.tower import HubScene

from tests.test_tower_scene import FakeApp, put_player_at


@pytest.fixture(scope="module")
def content():
    pygame.init()
    return data_loader.load_all()


@pytest.fixture
def med_bay(content):
    """In the chair, on a tired team."""
    scene, app = HubScene(content), FakeApp(content)
    scene._move = lambda dt, a: None                # headless: no key polling
    scene._switch_floor("med_bay")
    for hero_id in app.game_state["party"]:
        energy.set_hero_energy(app.game_state, hero_id, 40)
    energy.sync(app.game_state)
    return scene, app


def tick(scene, app, times=1):
    for _ in range(times):
        scene.update(config.MEDBAY_REST_SECONDS_PER_TICK, app)


# --- the exchange (1) -----------------------------------------------------

def test_ten_minutes_buys_ten_percent(content):
    _, app = HubScene(content), FakeApp(content)
    state = app.game_state
    for hero_id in state["party"]:
        energy.set_hero_energy(state, hero_id, 40)
    energy.sync(state)
    before = state["time_minutes"]

    result = activities.rest_tick(state)

    assert state["time_minutes"] == before + config.MEDBAY_TICK_MINUTES
    assert energy.team_energy(state) == 50
    assert result["team_energy"] == 50
    assert not result["full"]


def test_a_full_refill_costs_a_hundred_minutes(content):
    _, app = HubScene(content), FakeApp(content)
    state = app.game_state
    for hero_id in state["party"]:
        energy.set_hero_energy(state, hero_id, 0)
    energy.sync(state)
    before = state["time_minutes"]
    while energy.team_energy(state) < config.DAILY_ENERGY:
        activities.rest_tick(state)
    assert state["time_minutes"] - before == 100
    assert energy.team_energy(state) == config.DAILY_ENERGY


def test_treatment_costs_no_credits_and_no_energy(med_bay):
    scene, app = med_bay
    state = app.game_state
    credits = state["credits"]
    put_player_at(scene, 5, 3)                      # a treatment station
    scene.handle_key(app, pygame.K_RETURN)
    tick(scene, app, 3)
    assert state["credits"] == credits
    assert energy.team_energy(state) > 40           # only ever goes up


def test_every_active_member_is_treated_not_just_the_leader(med_bay):
    scene, app = med_bay
    state = app.game_state
    put_player_at(scene, 5, 3)
    scene.handle_key(app, pygame.K_RETURN)
    tick(scene, app, 2)
    for hero_id in state["party"]:
        assert energy.hero_energy(state, hero_id) == 60


# --- sitting there is the experience (2) ---------------------------------

def test_the_chair_puts_you_in_the_resting_mode(med_bay):
    scene, app = med_bay
    put_player_at(scene, 5, 3)
    scene.handle_key(app, pygame.K_RETURN)
    assert scene.mode == "resting"


def test_the_clock_runs_while_you_sit(med_bay):
    scene, app = med_bay
    state = app.game_state
    put_player_at(scene, 5, 3)
    scene.handle_key(app, pygame.K_RETURN)
    before = state["time_minutes"]
    tick(scene, app, 4)
    assert state["time_minutes"] == before + 4 * config.MEDBAY_TICK_MINUTES


def test_you_can_get_up_early(med_bay):
    scene, app = med_bay
    state = app.game_state
    put_player_at(scene, 5, 3)
    scene.handle_key(app, pygame.K_RETURN)
    tick(scene, app, 2)
    scene.handle_key(app, pygame.K_RETURN)          # stand up
    assert scene.mode == "normal"
    assert energy.team_energy(state) == 60          # keeps what it bought
    frozen = state["time_minutes"]
    scene.update(config.MEDBAY_REST_SECONDS_PER_TICK * 5, app)
    assert state["time_minutes"] == frozen          # and the clock stops


def test_the_treatment_stops_itself_when_the_team_is_full(med_bay):
    scene, app = med_bay
    state = app.game_state
    put_player_at(scene, 5, 3)
    scene.handle_key(app, pygame.K_RETURN)
    tick(scene, app, 20)                            # far more than needed
    assert scene.mode == "normal"
    assert energy.team_energy(state) == config.DAILY_ENERGY
    # 40 -> 100 is six ticks; the clock must not have run past that.
    assert state["time_minutes"] == config.DAY_START_MINUTES + 60


def test_a_full_team_is_turned_away(med_bay):
    scene, app = med_bay
    state = app.game_state
    for hero_id in state["party"]:
        energy.set_hero_energy(state, hero_id, config.DAILY_ENERGY)
    energy.sync(state)
    put_player_at(scene, 5, 3)
    scene.handle_key(app, pygame.K_RETURN)
    assert scene.mode == "normal"
    assert "full strength" in scene.messages[-1]


def test_sitting_past_two_am_ends_the_day(med_bay):
    scene, app = med_bay
    state = app.game_state
    state["time_minutes"] = config.DAY_END_MINUTES - 20
    put_player_at(scene, 5, 3)
    scene.handle_key(app, pygame.K_RETURN)
    tick(scene, app, 6)
    assert scene.mode != "resting"
    assert app.slept                                # passed out in the chair


# --- the room has to be repaired first (3) -------------------------------

def test_a_wrecked_med_bay_offers_the_repair_instead(content):
    scene, app = HubScene(content), FakeApp(content)
    state = app.game_state
    state["repairs"].pop("repair_med_bay")
    state["story_flags"]["med_bay_repaired"] = False
    scene._switch_floor("med_bay")
    put_player_at(scene, 5, 3)
    scene.handle_key(app, pygame.K_RETURN)
    assert scene.mode == "submenu"
    assert scene.submenu["items"][0][0] == "Open the Med Bay"
