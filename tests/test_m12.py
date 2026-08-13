"""M12 systems: battle time standard + defeat rework (App.finish_battle),
crate find_chance, and the training-lockout day flow."""

from types import SimpleNamespace

import pytest

from game import config
from game.__main__ import App
from game.core.state_machine import GameState
from game.hub import activities


@pytest.fixture()
def app():
    a = App()
    a.game_state = {"day": 1, "issue": 1,
                    "time_minutes": config.DAY_START_MINUTES,
                    "energy": 100, "roster": {}, "party": [], "bonds": {},
                    "inventory": {}, "credits": 0, "story_flags": {},
                    "quests": {}, "dispatches": [], "searched_today": []}
    for hid in ("iron_man", "captain_america"):
        a.game_state["roster"][hid] = {
            "trained_ranks": {}, "attribute_xp": {}, "perks": [],
            "perk_choices": {}, "gear": {}, "ult_charge": 0,
            "energy": 70}
    a.game_state["party"] = ["iron_man", "captain_america"]
    a.game_state["credits"] = 10000     # M36: the rack bills at the door
    for to in (GameState.TITLE, GameState.PATH_SELECT, GameState.HUB,
               GameState.BATTLE):
        a.machine.transition(to)
    return a


def lost_engine():
    return SimpleNamespace(outcome="lose", heroes=[])


def won_engine():
    hero = SimpleNamespace(id="iron_man", alive=True, data={"id": "iron_man"},
                           ult_charge=40, hp=90, max_hp=100)   # M36
    return SimpleNamespace(outcome="win", heroes=[hero],
                           rewards=lambda: {"credits": 10, "xp": 5})


def test_defeat_costs_three_hours_and_leaves_ten_en(app):
    state = app.game_state
    app.battle_quest = None
    app.battle_ambush = True
    app.finish_battle(lost_engine())
    assert state["time_minutes"] == \
        config.DAY_START_MINUTES + config.DEFEAT_RECOVERY_MINUTES
    for hid in state["party"]:
        assert state["roster"][hid]["energy"] == config.DEFEAT_ENERGY
    assert state["energy"] == config.DEFEAT_ENERGY
    assert app.machine.state is GameState.HUB
    assert state["day"] == 1                        # the day did NOT end


def test_defeat_caps_energy_never_raises(app):
    # Losing on fumes must not beat winning on fumes: 10 EN is a CAP.
    state = app.game_state
    state["roster"]["captain_america"]["energy"] = 3
    app.battle_quest = None
    app.battle_ambush = True
    app.finish_battle(lost_engine())
    assert state["roster"]["captain_america"]["energy"] == 3    # not raised
    assert state["roster"]["iron_man"]["energy"] == config.DEFEAT_ENERGY


def test_ambush_win_costs_an_hour(app):
    state = app.game_state
    app.battle_quest = None
    app.battle_ambush = True
    app.finish_battle(won_engine())
    assert state["time_minutes"] == \
        config.DAY_START_MINUTES + config.BATTLE_MINUTES
    assert state["credits"] == 10010            # the fixture's purse + 10
    assert app.machine.state is GameState.HUB


def test_quest_win_costs_no_extra_time(app):
    # mission time was already paid at engage (MISSION_MINUTES)
    state = app.game_state
    app.battle_quest = None                         # (quest bookkeeping aside)
    app.battle_ambush = False
    app.finish_battle(won_engine())
    assert state["time_minutes"] == config.DAY_START_MINUTES


def test_training_completes_at_sleep(app):
    state = app.game_state
    result = activities.start_training(state, app.content,
                                       "captain_america", "strength")
    assert result["ok"]
    app.machine.transition(GameState.HUB)
    app.autosave = lambda: None                     # keep real saves/ untouched
    app.go_to_sleep()                               # session runs into the night
    cap = state["roster"]["captain_america"]
    assert "training" not in cap
    assert cap["attribute_xp"]["strength"] == config.TRAINING_XP_BY_LEVEL[1]
    # M36: no auto-rejoin. The session finished overnight and Cap is
    # standing on the mats waiting to be collected in person.
    assert "captain_america" not in state["party"]
