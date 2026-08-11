"""M25: the clock stops for menus, board XP is budgeted per tier, and the
board reads plainly."""

import pygame
import pytest

from game import config, data_loader
from game.core.state_machine import GameState
from game.hub.tower import HubScene

from tests.test_tower_scene import FakeApp, put_player_at


@pytest.fixture(scope="module")
def content():
    pygame.init()
    return data_loader.load_all()


# --- the clock only runs while you're on your feet (1) ---

def test_the_clock_runs_while_walking(content):
    scene, app = HubScene(content), FakeApp(content)
    scene._move = lambda dt, a: None                # headless: no key polling
    before = app.game_state["time_minutes"]
    for _ in range(200):                            # well past one tick
        scene.update(config.TICK_REAL_SECONDS / 10, app)
    assert app.game_state["time_minutes"] > before


@pytest.mark.parametrize("open_menu", [
    lambda scene, app: scene._open_submenu("Test", [("a", False, None)]),
    lambda scene, app: put_player_at(scene, 34, 12) or scene.handle_key(
        app, pygame.K_RETURN),                       # the assignment board
])
def test_the_clock_stops_for_a_menu(content, open_menu):
    scene, app = HubScene(content), FakeApp(content)
    scene._move = lambda dt, a: None
    open_menu(scene, app)
    assert scene.mode == "submenu"
    before = app.game_state["time_minutes"]
    for _ in range(200):
        scene.update(config.TICK_REAL_SECONDS / 10, app)
    assert app.game_state["time_minutes"] == before


def test_the_clock_stops_for_a_cutscene(content):
    scene, app = HubScene(content), FakeApp(content)
    scene._play_scene({"title": "T", "lines": ["a line"]})
    before = app.game_state["time_minutes"]
    for _ in range(200):
        scene.update(config.TICK_REAL_SECONDS / 10, app)
    assert app.game_state["time_minutes"] == before


def test_the_pause_screen_never_reaches_the_hub_clock(content):
    # App.update only ticks the hub in the HUB state - this pins that, since
    # it is what keeps the Impel card from burning daylight.
    from game.__main__ import App

    app = App()
    app.new_game()
    for to in (GameState.TITLE, GameState.PATH_SELECT, GameState.HUB,
               GameState.PAUSE):
        app.machine.transition(to)
    app.hub._move = lambda dt, a: None
    before = app.game_state["time_minutes"]
    for _ in range(200):
        app.update(config.TICK_REAL_SECONDS / 10)
    assert app.game_state["time_minutes"] == before


# --- board XP sits inside its tier's budget (2) ---

def test_every_job_respects_its_tier_xp_budget(content):
    for task in content["assignments"]:
        trains = task.get("trains") or list(config.ATTRIBUTES)
        total = task["xp"] * len(trains)
        budget = config.board_tier_xp_per_day(task["tier"]) * task["days"]
        assert total <= budget + len(trains), (
            f"{task['id']}: {total} XP over {task['days']}d exceeds the "
            f"tier-{task['tier']} budget of {budget}")
        assert total >= budget - len(trains), (
            f"{task['id']}: {total} XP is well under its budget {budget}")


def test_the_tier_budgets_are_multiples_of_the_passive_rate():
    assert config.PASSIVE_TRAIN_XP_PER_DAY == 40
    assert config.board_tier_xp_per_day(1) == 20     # 0.5x
    assert config.board_tier_xp_per_day(2) == 40     # 1.0x
    assert config.board_tier_xp_per_day(3) == 60     # 1.5x


def test_board_work_never_beats_sitting_on_the_mats_by_much(content):
    """The whole point: a dispatched hero is off the team exactly like one
    on the passive train assignment, so board XP must stay the lesser route."""
    for task in content["assignments"]:
        trains = task.get("trains") or list(config.ATTRIBUTES)
        per_day = task["xp"] * len(trains) / task["days"]
        assert per_day <= 1.5 * config.PASSIVE_TRAIN_XP_PER_DAY + 1, task["id"]


# --- the board reads plainly (3) ---

def test_the_title_is_just_the_board(content):
    scene, app = HubScene(content), FakeApp(content)
    put_player_at(scene, 34, 12)
    scene.handle_key(app, pygame.K_RETURN)
    assert scene.submenu["title"] == "Assignment Board"


def test_payouts_drop_the_pays_prefix_and_the_tilde(content):
    scene = HubScene(content)
    sweep = next(t for t in content["assignments"] if t["id"] == "sweep_hangar")
    assert scene._reward_label(sweep) == "60 cr, 20 XP to Stamina"
    assert "~" not in scene._reward_label(sweep)


@pytest.mark.parametrize("tier,power,expected", [
    (1, 37, "Tier 1 jobs available. Tier 2 jobs unlocked at team power "
            "90 (currently 37)."),
    (2, 121, "Tier 1 and Tier 2 jobs available. Tier 3 jobs unlocked at "
             "team power 160 (currently 121)."),
    (3, 210, "Tier 1-3 jobs available."),
])
def test_the_footer_says_what_is_open_and_what_is_next(tier, power, expected):
    assert HubScene._tier_status(tier, power) == expected


def test_the_footer_is_the_last_line_before_close(content):
    scene, app = HubScene(content), FakeApp(content)
    put_player_at(scene, 34, 12)
    scene.handle_key(app, pygame.K_RETURN)
    labels = [i[0] for i in scene.submenu["items"]]
    assert labels[-1] == "Close"
    assert labels[-2].startswith("Tier 1 jobs available.")
