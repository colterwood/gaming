"""M16 regression pins for behaviour the review proved was unprotected:
multi-day training lockouts across sleeps and issue boundaries, level-keyed
session costs, the KO half-XP rule, and pre-M16 save migration.
"""

from types import SimpleNamespace

import pytest

from game import config, data_loader
from game.core import calendar as cal
from game.core import clock, save
from game.core.state_machine import GameState
from game.hub import activities


@pytest.fixture(scope="module")
def content():
    return data_loader.load_all()


def entry(**levels):
    e = {"trained_ranks": {}, "attribute_xp": {}, "perks": [],
         "perk_choices": {}, "gear": {}, "ult_charge": 0,
         "energy": 100}
    for attribute, level in levels.items():
        e["trained_ranks"][attribute] = level - config.RANK_START
    return e


def two_hero_state(**cap_levels):
    state = save.new_game_state()
    state["path"] = "avengers"
    state["roster"]["iron_man"] = entry()
    state["roster"]["captain_america"] = entry(**cap_levels)
    state["party"] = ["iron_man", "captain_america"]
    state["credits"] = 100000      # M36: the rack bills at the door
    return state


# --- the waking-minutes clock ---

def test_absolute_minutes_counts_whole_issues():
    state = save.new_game_state()
    day = clock.DAY_MINUTES
    assert clock.absolute_minutes(state) == 0            # issue 1 day 1, 6 AM
    state["time_minutes"] = config.DAY_END_MINUTES
    assert clock.absolute_minutes(state) == day          # a full day of waking
    state["issue"], state["day"] = 1, 28
    state["time_minutes"] = config.DAY_START_MINUTES
    end_of_issue = clock.absolute_minutes(state)
    assert end_of_issue == 27 * day
    # rolling into issue 2 must keep counting UP, not restart
    state["issue"], state["day"] = 2, 1
    assert clock.absolute_minutes(state) == end_of_issue + day


def test_absolute_minutes_never_goes_backwards_across_a_month():
    state = save.new_game_state()
    seen = clock.absolute_minutes(state)
    for _ in range(40):                                  # past the issue roll
        cal.sleep(state)
        now = clock.absolute_minutes(state)
        assert now > seen, (state["issue"], state["day"])
        seen = now


# --- a long session really does span days ---

def test_level_eight_session_survives_a_sleep(content):
    # A level-8 session is longer than the 1200-minute day, so the hero
    # must still be on the mats the next morning. M36 doubles the table, so
    # it now runs 2800 minutes and spans THREE days rather than two.
    state = two_hero_state(strength=8)
    result = activities.start_training(state, content, "captain_america",
                                       "strength")
    session = (config.TRAINING_MINUTES_BY_LEVEL[8]
               * config.TRAINING_LOCKOUT_MULT)
    assert result["ok"] and result["minutes"] == session
    cap = state["roster"]["captain_america"]
    assert activities.training_remaining(state, cap["training"]) == session
    left = session
    while left > 0:
        cal.sleep(state)
        left = max(0, left - clock.DAY_MINUTES)
        assert activities.training_remaining(state, cap["training"]) == left
        if left:
            assert activities.finish_due_training(state, content) == []
            assert "training" in cap                    # still training
            assert "captain_america" not in state["party"]
    messages = activities.finish_due_training(state, content)
    assert len(messages) == 1
    assert "training" not in cap
    assert cap["attribute_xp"]["strength"] == config.TRAINING_XP_BY_LEVEL[8]


def test_session_spanning_the_issue_boundary(content):
    # The exact case the issue term in absolute_minutes exists for.
    state = two_hero_state(strength=8)
    state["issue"], state["day"] = 1, 28
    activities.start_training(state, content, "captain_america", "strength")
    lock = state["roster"]["captain_america"]["training"]
    assert activities.training_remaining(state, lock) == (
        config.TRAINING_MINUTES_BY_LEVEL[8] * config.TRAINING_LOCKOUT_MULT)
    cal.sleep(state)                                     # -> issue 2, day 1
    assert (state["issue"], state["day"]) == (2, 1)
    session = (config.TRAINING_MINUTES_BY_LEVEL[8]
               * config.TRAINING_LOCKOUT_MULT)
    left = activities.training_remaining(state, lock)
    assert left == session - clock.DAY_MINUTES,         "the issue rollover must not restart the counter"
    while activities.training_remaining(state, lock) > 0:
        cal.sleep(state)
    assert activities.finish_due_training(state, content)
    assert "training" not in state["roster"]["captain_america"]


def test_app_sleep_does_not_force_complete_a_long_session(content):
    # Pins the M16 go_to_sleep ordering: settling training must happen AFTER
    # the calendar advances, and must NOT force. Reverting either one lets a
    # two-day session finish in a single night.
    from game.__main__ import App
    app = App()
    app.game_state = two_hero_state(strength=8)
    app.autosave = lambda: None
    for to in (GameState.TITLE, GameState.PATH_SELECT, GameState.HUB):
        app.machine.transition(to)
    activities.start_training(app.game_state, app.content,
                              "captain_america", "strength")
    cap = app.game_state["roster"]["captain_america"]
    app.go_to_sleep()
    assert "training" in cap, "a level-8 session must outlast one night"
    assert "captain_america" not in app.game_state["party"]
    for _ in range(config.TRAINING_LOCKOUT_MULT):
        app.machine.transition(GameState.HUB)
        app.go_to_sleep()
    assert "training" not in cap                         # settles a night later
    assert cap["attribute_xp"]["strength"] == config.TRAINING_XP_BY_LEVEL[8]


# --- level-keyed costs use the LEVEL, not the trained count ---

def test_session_cost_and_yield_follow_the_level(content):
    state = two_hero_state(strength=5)
    result = activities.start_training(state, content, "captain_america",
                                       "strength")
    en, minutes = activities.training_cost(5)
    assert result["minutes"] == minutes == (
        config.TRAINING_MINUTES_BY_LEVEL[5] * config.TRAINING_LOCKOUT_MULT)
    assert state["roster"]["captain_america"]["energy"] == 100 - en
    activities.finish_due_training(state, content, force=True)
    # the yield is the LEVEL-5 figure, not the level-1 one
    assert (state["roster"]["captain_america"]["attribute_xp"]["strength"]
            == config.TRAINING_XP_BY_LEVEL[5])
    assert config.TRAINING_XP_BY_LEVEL[5] != config.TRAINING_XP_BY_LEVEL[1]


# --- battle XP: participants bank it, the fallen bank half ---

def test_ko_participants_earn_half_xp(content):
    from game.__main__ import App
    app = App()
    app.game_state = two_hero_state()
    app.autosave = lambda: None
    for to in (GameState.TITLE, GameState.PATH_SELECT, GameState.HUB,
               GameState.BATTLE):
        app.machine.transition(to)
    app.battle_quest = None
    app.battle_ambush = True
    standing = SimpleNamespace(id="iron_man", alive=True, ult_charge=0,
                               hp=70, max_hp=100,                # M36
                               data={"id": "iron_man"})
    fallen = SimpleNamespace(id="captain_america", alive=False, ult_charge=0,
                             hp=0, max_hp=100,
                             data={"id": "captain_america"})
    engine = SimpleNamespace(outcome="win", heroes=[standing, fallen],
                             rewards=lambda: {"credits": 10, "xp": 100})
    app.finish_battle(engine)
    roster = app.game_state["roster"]
    # M21: it lands on the attributes now instead of banking. A KO'd
    # participant still earns KO_XP_MULT of the standing hero's share.
    assert sum(roster["iron_man"]["attribute_xp"].values()) == 100
    assert (sum(roster["captain_america"]["attribute_xp"].values())
            == int(100 * config.KO_XP_MULT))
    assert roster["iron_man"].get("unspent_xp", 0) == 0   # nothing banked


def test_enemy_levels_drive_battle_xp(content):
    for enemy in content["enemies"].values():
        assert enemy["level"] in config.ENEMY_XP_BY_LEVEL
        assert "xp_reward" not in enemy               # replaced by level (M16)
    assert config.ENEMY_XP_BY_LEVEL[content["enemies"]["hydra_grunt"]["level"]] == 24


# --- pre-M16 saves ---

def test_pre_m16_training_lock_is_migrated(content):
    # M15 stored a minute-of-day; M16 stores campaign-wide waking minutes.
    # Without migration the old value reads as a lock that expired decades
    # ago (or one that never ends).
    state = two_hero_state(strength=8)
    state["issue"], state["day"] = 2, 5
    state["time_minutes"] = 600                          # 10:00 AM
    state["roster"]["captain_america"]["training"] = {
        "attribute": "strength", "ends": 900,            # old shape: 3h left
        "xp": 700, "banked": 0}
    activities.migrate_training_locks(state)
    lock = state["roster"]["captain_america"]["training"]
    assert "ends" not in lock and "ends_abs" in lock
    assert activities.training_remaining(state, lock) == 300     # 3 hours
    clock.advance(state, 300)
    assert activities.finish_due_training(state, content)


def test_migration_is_idempotent(content):
    state = two_hero_state(strength=8)
    activities.start_training(state, content, "captain_america", "strength")
    before = dict(state["roster"]["captain_america"]["training"])
    activities.migrate_training_locks(state)
    assert state["roster"]["captain_america"]["training"] == before
