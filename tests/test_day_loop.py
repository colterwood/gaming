"""M2: clock, energy, calendar, activities, sleep, save/reload mid-run."""

import pytest

from game import config, data_loader
from game.core import calendar as cal
from game.core import clock, energy, save
from game.hub import activities


@pytest.fixture(scope="module")
def content():
    return data_loader.load_all()


def fresh_state():
    return save.new_game_state()


# --- clock (§6.1) ---

def test_day_starts_at_6am():
    state = fresh_state()
    assert state["time_minutes"] == 360
    assert clock.format_time(state["time_minutes"]) == "6:00 AM"


def test_clock_advance_and_day_end():
    state = fresh_state()
    assert clock.advance(state, 90) is False
    assert clock.format_time(state["time_minutes"]) == "7:30 AM"
    state["time_minutes"] = config.DAY_END_MINUTES - 10
    assert clock.advance(state, 10) is True          # hits 2 AM exactly
    assert clock.format_time(state["time_minutes"]) == "2:00 AM"


def test_clock_clamps_at_day_end():
    state = fresh_state()
    clock.advance(state, 10000)
    assert state["time_minutes"] == config.DAY_END_MINUTES


# --- energy (§6.1) ---

def test_energy_spend_and_block():
    state = fresh_state()
    assert energy.spend(state, 40) is True
    assert state["energy"] == 60
    assert energy.spend(state, 61) is False
    assert state["energy"] == 60                     # nothing spent on failure


# --- calendar (§6.2, §7) ---

def test_weeks_are_7_day_rows():
    assert cal.week_of_day(1) == 1
    assert cal.week_of_day(7) == 1
    assert cal.week_of_day(8) == 2
    assert cal.week_of_day(28) == 4
    assert [d for d in range(1, 29) if cal.is_gift_week_reset_day(d)] == [1, 8, 15, 22]


def test_sleep_advances_day_and_resets(content):
    state = fresh_state()
    state["energy"] = 5
    state["time_minutes"] = 1500
    state["bonds"] = {"captain_america": {"points": 100, "gifts_this_week": 2,
                                          "talked_today": True}}
    cal.sleep(state)
    assert state["day"] == 2
    assert state["energy"] == config.DAILY_ENERGY
    assert state["time_minutes"] == config.DAY_START_MINUTES
    assert state["bonds"]["captain_america"]["talked_today"] is False
    assert state["bonds"]["captain_america"]["gifts_this_week"] == 2   # day 2: no reset


def test_gift_counter_resets_on_week_boundary():
    state = fresh_state()
    state["day"] = 7
    state["bonds"] = {"iron_man": {"points": 0, "gifts_this_week": 2, "talked_today": True}}
    cal.sleep(state)                                  # day 7 -> 8, week boundary
    assert state["day"] == 8
    assert state["bonds"]["iron_man"]["gifts_this_week"] == 0


def test_issue_wraps_after_28_days():
    state = fresh_state()
    state["day"] = 28
    cal.sleep(state)
    assert (state["issue"], state["day"]) == (2, 1)


def test_pass_out_penalty():
    state = fresh_state()
    cal.sleep(state, passed_out=True)
    assert state["energy"] == config.PASS_OUT_NEXT_DAY_ENERGY


def test_caps_birthday_on_issue1_day20(content):
    state = fresh_state()
    state["day"] = 20
    assert cal.birthdays_today(state, content["characters"]) == ["captain_america"]


def test_supply_drop_event_active_days_12_13(content):
    state = fresh_state()
    for day, expected in [(11, 0), (12, 1), (13, 1), (14, 0)]:
        state["day"] = day
        assert len(cal.active_events(state, content["calendar"])) == expected


# --- activities (§6.1 costs) ---

def test_training_costs():
    state = fresh_state()
    result = activities.training_session(state)
    assert result["ok"]
    assert state["energy"] == config.DAILY_ENERGY - config.TRAINING_ENERGY
    assert state["time_minutes"] == 360 + config.TRAINING_MINUTES


def test_mission_costs_and_launches():
    state = fresh_state()
    result = activities.launch_mission(state)
    assert result["ok"] and result["launch_battle"]
    assert state["energy"] == config.DAILY_ENERGY - config.MISSION_ENERGY
    assert state["time_minutes"] == 360 + config.MISSION_MINUTES


def test_activity_blocked_without_energy():
    state = fresh_state()
    state["energy"] = 10
    result = activities.launch_mission(state)
    assert not result["ok"]
    assert state["energy"] == 10


def test_assignments_rotate_and_complete(content):
    state = fresh_state()
    today = activities.assignment_tasks_today(state, content["assignments"])
    assert len(today) == 2
    result = activities.do_assignment(state, today[0])
    assert result["ok"]
    assert state["credits"] == today[0]["credits"]
    assert activities.do_assignment(state, today[0])["ok"] is False   # once per day
    state2 = fresh_state()
    state2["day"] = 2
    tomorrow = activities.assignment_tasks_today(state2, content["assignments"])
    assert [t["id"] for t in tomorrow] != [t["id"] for t in today]


def test_pass_out_conditions():
    state = fresh_state()
    assert not activities.should_pass_out(state)
    state["energy"] = 0
    assert activities.should_pass_out(state)
    state["energy"] = 50
    state["time_minutes"] = config.DAY_END_MINUTES
    assert activities.should_pass_out(state)


# --- M2 acceptance: three consecutive days; save/reload restores mid-run ---

def test_three_consecutive_days(content):
    state = fresh_state()
    for expected_day in (1, 2, 3):
        assert state["day"] == expected_day
        while activities.training_session(state)["ok"]:
            pass
        assert state["energy"] < config.TRAINING_ENERGY   # energy limit enforced
        cal.sleep(state, passed_out=activities.should_pass_out(state))
    assert state["day"] == 4


def test_save_reload_restores_mid_run(tmp_path, content):
    state = fresh_state()
    activities.launch_mission(state)
    activities.training_session(state)
    today = activities.assignment_tasks_today(state, content["assignments"])
    activities.do_assignment(state, today[1])
    state["credits"] += 100
    save.save_game(state, 1, save_dir=str(tmp_path))
    assert save.load_game(1, save_dir=str(tmp_path)) == state
