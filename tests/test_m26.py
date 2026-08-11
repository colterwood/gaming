"""M26: every board job is one-shot. The board is a finite list of work,
not an income tap, and a tier can be cleared out."""

import pygame
import pytest

from game import data_loader
from game.hub import activities, dispatch, requirements
from game.hub.tower import HubScene

from tests.test_tower_scene import FakeApp, put_player_at

ENTRY = {"trained_ranks": {}, "attribute_xp": {}, "perks": [],
         "perk_choices": {}, "gear": {}, "ult_charge": 0, "energy": 100}


@pytest.fixture(scope="module")
def content():
    pygame.init()
    return data_loader.load_all()


def task_by_id(content, task_id):
    return next(t for t in content["assignments"] if t["id"] == task_id)


def crewed_state(content):
    state = FakeApp(content).game_state
    for hero_id in ("ant_man", "hulk"):
        state["roster"][hero_id] = dict(ENTRY, trained_ranks={"agility": 2,
                                                              "strength": 2})
    state["party"] = ["iron_man", "captain_america", "ant_man", "hulk"]
    return state


# --- the rule ---

def test_no_job_carries_a_once_flag_any_more(content):
    for task in content["assignments"]:
        assert "once" not in task, task["id"]


def test_finishing_a_job_retires_it(content):
    state = crewed_state(content)
    task = task_by_id(content, "sweep_hangar")
    assert requirements.gate_open(state, task)
    dispatch.send(content, state, task, ["iron_man"])
    dispatch.process_day(content, state)                # 1-day job
    assert task["id"] in state["completed_tasks"]
    assert requirements.is_done(state, task)
    assert not requirements.gate_open(state, task)      # off the board
    ok, reason = dispatch.send(content, state, task, ["iron_man"])
    assert not ok and "already been handled" in reason


def test_a_retired_job_stops_being_posted(content):
    state = crewed_state(content)
    task = task_by_id(content, "sweep_hangar")
    seen = any(t["id"] == task["id"]
               for day in range(1, 15)
               for t in activities.assignment_tasks_today(
                   dict(state, day=day), content["assignments"], 1))
    assert seen, "the job should show up somewhere in a fortnight"
    state["completed_tasks"] = [task["id"]]
    still = any(t["id"] == task["id"]
                for day in range(1, 15)
                for t in activities.assignment_tasks_today(
                    dict(state, day=day), content["assignments"], 1))
    assert not still


def test_recalling_a_job_does_not_retire_it(content):
    # Abandoning pays nothing, so the work is still there to do.
    state = crewed_state(content)
    task = task_by_id(content, "sweep_hangar")
    dispatch.send(content, state, task, ["iron_man"])
    dispatch.recall(content, state, task["id"])
    assert state.get("completed_tasks", []) == []
    assert requirements.gate_open(state, task)


def test_the_board_runs_dry(content):
    state = crewed_state(content)
    tier1 = [t for t in content["assignments"] if t["tier"] == 1]
    state["completed_tasks"] = [t["id"] for t in tier1]
    assert activities.assignment_tasks_today(
        state, content["assignments"], 1) == []


# --- the footer reports it ---

def test_footer_names_a_cleared_tier(content):
    scene = HubScene(content)
    state = crewed_state(content)
    tier1 = [t for t in content["assignments"] if t["tier"] == 1]
    state["completed_tasks"] = [t["id"] for t in tier1]
    assert scene._tier_status(state, 2, 121) == (
        "Tier 2 jobs available, Tier 1 jobs complete. "
        "Tier 3 jobs unlocked at team power 160 (currently 121).")


def test_footer_when_everything_open_is_finished(content):
    scene = HubScene(content)
    state = crewed_state(content)
    state["completed_tasks"] = [t["id"] for t in content["assignments"]
                                if t["tier"] <= 2]
    assert scene._tier_status(state, 2, 121) == (
        "Tier 1 and Tier 2 jobs complete. "
        "Tier 3 jobs unlocked at team power 160 (currently 121).")


def test_footer_when_the_whole_board_is_done(content):
    scene = HubScene(content)
    state = crewed_state(content)
    state["completed_tasks"] = [t["id"] for t in content["assignments"]]
    assert scene._tier_status(state, 3, 210) == "Tier 1-3 jobs complete."


def test_the_board_says_when_nothing_is_posted(content):
    scene, app = HubScene(content), FakeApp(content)
    app.game_state["completed_tasks"] = [t["id"]
                                         for t in content["assignments"]]
    put_player_at(scene, 34, 12)
    scene.handle_key(app, pygame.K_RETURN)
    labels = [i[0] for i in scene.submenu["items"]]
    assert "Nothing posted today." in labels
    assert any("jobs complete" in l for l in labels)


# --- what the board is worth in total, now that it's finite ---

def test_the_whole_board_is_a_known_finite_purse(content):
    by_tier = {}
    for task in content["assignments"]:
        by_tier.setdefault(task["tier"], []).append(task)
    assert sum(len(v) for v in by_tier.values()) == 16
    total = sum(t["credits"] for t in content["assignments"])
    assert total == 3160        # base, before the M11 crew multiplier
    # and every tier is worth more than the one below it
    purse = {tier: sum(t["credits"] for t in jobs)
             for tier, jobs in by_tier.items()}
    assert purse[1] < purse[2] < purse[3]
