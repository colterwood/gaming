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
    state = save.new_game_state()
    for hid in ("iron_man", "captain_america"):
        state["roster"][hid] = {"trained_ranks": {}, "attribute_xp": {},
                                "perks": [], "perk_choices": {}, "gear": {},
                                "ult_charge": 0, "energy": 100, "unspent_xp": 0}
    state["party"] = ["iron_man", "captain_america"]
    return state


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
    assert state["energy"] == 60                     # every party member drained
    assert state["roster"]["iron_man"]["energy"] == 60
    assert energy.spend(state, 61) is False
    assert state["energy"] == 60                     # nothing spent on failure


def test_team_energy_is_minimum_of_party():
    state = fresh_state()
    state["roster"]["captain_america"]["energy"] = 35
    assert energy.team_energy(state) == 35           # M9: weakest member rules
    assert energy.spend(state, 40) is False          # cap can't afford it
    assert energy.spend_hero(state, "iron_man", 30)
    assert energy.team_energy(state) == 35           # iron man at 70, cap still min


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
    state["bonds"] = {"captain_america": {"points": 100, "talked_today": True,
                                          "gift_days": [1], "last_gift": None}}
    cal.sleep(state)
    assert state["day"] == 2
    assert state["energy"] == config.DAILY_ENERGY
    assert state["time_minutes"] == config.DAY_START_MINUTES
    assert state["bonds"]["captain_america"]["talked_today"] is False
    # M12: gift history is a rolling window (bonds.gift_allowed), untouched here
    assert state["bonds"]["captain_america"]["gift_days"] == [1]


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
    # legacy generic session: level-2 costs from the M16 tables (25 EN / 70 min)
    state = fresh_state()
    result = activities.training_session(state)
    assert result["ok"]
    en, minutes = activities.training_cost(2)
    assert state["energy"] == config.DAILY_ENERGY - en
    assert state["time_minutes"] == 360 + minutes


def test_mission_costs_and_launches():
    state = fresh_state()
    result = activities.launch_mission(state)
    assert result["ok"] and result["launch_battle"]
    assert state["energy"] == config.DAILY_ENERGY - config.MISSION_ENERGY
    assert state["time_minutes"] == 360 + config.MISSION_MINUTES


def test_mission_never_blocked_drains_to_zero():
    # M11: a tired team can always engage — energy floors at 0 and the
    # M9 initiative penalty is the price.
    state = fresh_state()
    state["roster"]["captain_america"]["energy"] = 10
    result = activities.launch_mission(state)
    assert result["ok"] and result["launch_battle"]
    assert state["roster"]["captain_america"]["energy"] == 0
    assert state["roster"]["iron_man"]["energy"] == 60


def test_training_still_blocked_without_energy():
    state = fresh_state()
    for entry in state["roster"].values():
        entry["energy"] = 5
    result = activities.training_session(state)
    assert not result["ok"]
    assert state["roster"]["iron_man"]["energy"] == 5    # nothing spent


def test_assignments_rotate_daily(content):
    state = fresh_state()
    today = activities.assignment_tasks_today(state, content["assignments"])
    assert len(today) == 2
    state2 = fresh_state()
    state2["day"] = 2
    tomorrow = activities.assignment_tasks_today(state2, content["assignments"])
    assert [t["id"] for t in tomorrow] != [t["id"] for t in today]


def test_pass_out_conditions():
    state = fresh_state()
    assert not activities.should_pass_out(state)
    for entry in state["roster"].values():
        entry["energy"] = 0
    assert activities.should_pass_out(state)
    for entry in state["roster"].values():
        entry["energy"] = 50
    state["time_minutes"] = config.DAY_END_MINUTES
    assert activities.should_pass_out(state)


# --- M2 acceptance: three consecutive days; save/reload restores mid-run ---

def test_three_consecutive_days(content):
    state = fresh_state()
    for expected_day in (1, 2, 3):
        assert state["day"] == expected_day
        while activities.training_session(state)["ok"]:
            pass
        assert state["energy"] < 25                       # energy limit enforced
        cal.sleep(state, passed_out=activities.should_pass_out(state))
        assert state["roster"]["iron_man"]["energy"] >= 80  # per-hero reset
    assert state["day"] == 4


def test_save_reload_restores_mid_run(tmp_path, content):
    from game.hub import dispatch
    state = fresh_state()
    activities.launch_mission(state)
    activities.training_session(state)
    today = activities.assignment_tasks_today(state, content["assignments"])
    one_hero_task = next(t for t in today if t["heroes"] == 1)
    ok, _ = dispatch.send(content, state, one_hero_task, ["iron_man"])
    assert ok
    state["credits"] += 100
    save.save_game(state, 1, save_dir=str(tmp_path))
    assert save.load_game(1, save_dir=str(tmp_path)) == state
