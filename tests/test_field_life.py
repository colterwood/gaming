"""M10 systems: rations (EN food), zone crate searching, and the dispatch
assignment board."""

import random

import pytest

from game import config, data_loader
from game.core import calendar as cal
from game.core import save
from game.hub import activities, dispatch, field, party, passive


@pytest.fixture(scope="module")
def content():
    return data_loader.load_all()


def entry():
    return {"trained_ranks": {}, "attribute_xp": {}, "perks": [],
            "perk_choices": {}, "energy": 100, "unspent_xp": 0}


def state_with(roster_ids, party_ids):
    state = save.new_game_state()
    state["path"] = "avengers"
    for hid in roster_ids:
        state["roster"][hid] = entry()
    state["party"] = list(party_ids)
    return state


def task_by_id(content, task_id):
    return next(t for t in content["assignments"] if t["id"] == task_id)


# --- rations (1) ---

def test_eat_restores_energy_and_consumes_item(content):
    state = state_with(["iron_man", "captain_america"],
                       ["iron_man", "captain_america"])
    state["roster"]["iron_man"]["energy"] = 40
    state["inventory"]["shawarma"] = 2
    result = activities.eat_food(state, content, "iron_man", "shawarma")
    assert result["ok"]
    assert state["roster"]["iron_man"]["energy"] == 65          # +25
    assert state["inventory"]["shawarma"] == 1
    assert state["time_minutes"] == 360 + config.EAT_MINUTES
    assert state["energy"] == 65                                 # team synced


def test_eat_caps_at_daily_max(content):
    state = state_with(["iron_man"], ["iron_man"])
    state["roster"]["iron_man"]["energy"] = 95
    state["inventory"]["power_smoothie"] = 1
    result = activities.eat_food(state, content, "iron_man", "power_smoothie")
    assert result["ok"]
    assert state["roster"]["iron_man"]["energy"] == config.DAILY_ENERGY
    assert "+5 EN" in result["message"]                          # only what fit


def test_eat_refuses_full_missing_and_inedible(content):
    state = state_with(["iron_man"], ["iron_man"])
    state["inventory"]["shawarma"] = 1
    assert not activities.eat_food(state, content, "iron_man", "shawarma")["ok"]
    state["roster"]["iron_man"]["energy"] = 50
    assert not activities.eat_food(state, content, "iron_man", "med_kit")["ok"]
    assert not activities.eat_food(state, content, "iron_man", "coffee")["ok"]
    # last one is removed from the bag entirely
    activities.eat_food(state, content, "iron_man", "shawarma")
    assert "shawarma" not in state["inventory"]


# --- zone searching (2) ---

def test_search_loot_within_zone_table(content):
    zone = content["zones"]["docks"]
    rng = random.Random(11)
    lo, hi = zone["loot"]["credits"]
    saw_item = False
    empties = finds = 0
    for _ in range(600):
        result = field.search_loot(zone, rng)
        if result["trap"]:
            assert result["credits"] == 0 and result["item"] is None
            continue
        if result["credits"] == 0 and result["item"] is None:
            empties += 1                # M12: most crates hold nothing
            continue
        finds += 1
        assert lo <= result["credits"] <= hi
        if result["item"]:
            assert result["item"] in zone["loot"]["items"]
            saw_item = True
    assert saw_item
    assert empties > finds              # find_chance 0.30 at the docks


def test_trap_rate_scales_with_danger(content):
    rng = random.Random(5)
    traps = {1: 0, 3: 0}
    for danger in traps:
        zone = dict(content["zones"]["docks"], danger=danger)
        traps[danger] = sum(field.search_loot(zone, rng)["trap"]
                            for _ in range(2000))
    assert traps[3] > traps[1] > 0


def test_trap_squad_any_size(content):
    rng = random.Random(9)
    for _ in range(200):
        squad = field.trap_squad(3, rng)
        assert 2 <= len(squad) <= config.AMBUSH_MAX_SIZE


def test_searched_spots_reset_at_sleep():
    state = state_with(["iron_man"], ["iron_man"])
    activities.mark_spot_searched(state, "docks", 3, 4)
    assert activities.spot_searched(state, "docks", 3, 4)
    assert not activities.spot_searched(state, "docks", 4, 4)
    cal.sleep(state)
    assert not activities.spot_searched(state, "docks", 3, 4)   # crates respawn


# --- dispatch board (3) ---

def test_send_pulls_from_party_and_locks_out(content):
    state = state_with(["iron_man", "captain_america", "ant_man"],
                       ["iron_man", "captain_america"])
    task = task_by_id(content, "sweep_hangar")                  # 1 hero, 1 day
    ok, message = dispatch.send(content, state, task, ["iron_man"])
    assert ok
    assert state["party"] == ["captain_america"]
    assert state["roster"]["iron_man"]["dispatch"] == "sweep_hangar"
    # locked out of everything until the job ends
    assert not party.add_to_party(content, state, "iron_man")[0]
    assert not party.can_swap_in(content, state, "iron_man", "captain_america")[0]
    assert not passive.assign(content, state, "iron_man", "train", "speed")[0]
    # and the same job can't be started twice
    assert not dispatch.send(content, state, task, ["ant_man"])[0]


def test_send_validates_count_and_party_floor(content):
    state = state_with(["iron_man", "captain_america"],
                       ["iron_man", "captain_america"])
    two_hero = task_by_id(content, "spar_rookies")              # 2 heroes
    ok, message = dispatch.send(content, state, two_hero, ["iron_man"])
    assert not ok and "needs 2" in message
    ok, message = dispatch.send(content, state, two_hero,
                                ["iron_man", "captain_america"])
    assert not ok and "stay on the team" in message             # party floor
    state["roster"]["ant_man"] = entry()
    ok, _ = dispatch.send(content, state, two_hero, ["iron_man", "ant_man"])
    assert ok
    assert state["party"] == ["captain_america"]


def test_dispatch_completes_at_sleep_with_rewards(content):
    state = state_with(["iron_man", "captain_america"],
                       ["iron_man", "captain_america"])
    task = task_by_id(content, "calibrate_sensors")             # 1 hero, 2 days
    mult = dispatch.reward_mult(content, state, ["iron_man"])
    ok, message = dispatch.send(content, state, task, ["iron_man"])
    assert ok, message
    assert dispatch.process_day(content, state) == []           # night 1: away
    assert dispatch.is_away(state, "iron_man")
    messages = dispatch.process_day(content, state)             # night 2: home
    assert any("Calibrate Tower Sensors done" in m for m in messages)
    # M11: pay scales with the sent hero's power (M15 rank scale)
    assert state["credits"] == round(task["credits"] * mult)
    assert state["roster"]["iron_man"]["unspent_xp"] == round(task["xp"] * mult)
    assert not dispatch.is_away(state, "iron_man")
    assert dispatch.active(state) == []
    # free to rejoin now
    assert party.add_to_party(content, state, "iron_man")[0]


def test_recall_frees_heroes_without_rewards(content):
    state = state_with(["iron_man", "captain_america"],
                       ["iron_man", "captain_america"])
    task = task_by_id(content, "calibrate_sensors")
    dispatch.send(content, state, task, ["iron_man"])
    ok, message = dispatch.recall(content, state, task["id"])
    assert ok and "empty-handed" in message
    assert state["credits"] == 0
    assert not dispatch.is_away(state, "iron_man")
    assert party.add_to_party(content, state, "iron_man")[0]


def test_dispatched_heroes_skip_idle_atrophy(content):
    state = state_with(["iron_man", "captain_america"], ["captain_america"])
    im = state["roster"]["iron_man"]
    im["attribute_xp"]["strength"] = 50
    task = task_by_id(content, "calibrate_sensors")
    dispatch.send(content, state, task, ["iron_man"])
    for _ in range(4):                                          # well past grace
        passive.process_day(content, state)
    assert im["attribute_xp"]["strength"] == 50                 # no decay away
    assert im["idle_days"] == 0


def test_backfill_spots_migrates_pre_m13_saves(content):
    # Jobs saved before work sites existed must still be findable/recallable.
    state = state_with(["iron_man"], ["iron_man"])
    state["dispatches"] = [
        {"task_id": "calibrate_sensors", "name": "Calibrate Tower Sensors",
         "heroes": ["iron_man"], "days_left": 2, "credits": 150, "xp": 50},
        {"task_id": "task_removed_from_pool", "name": "?", "heroes": [],
         "days_left": 1, "credits": 0, "xp": 0}]
    dispatch.backfill_spots(content, state)
    assert state["dispatches"][0]["spot"] == ["ops", 30, 4]     # from the task
    assert state["dispatches"][1]["spot"] == dispatch.FALLBACK_SPOT


def test_send_clears_passive_assignment(content):
    state = state_with(["iron_man", "captain_america"], ["captain_america"])
    passive.assign(content, state, "iron_man", "train", "agility")
    task = task_by_id(content, "sweep_hangar")
    dispatch.send(content, state, task, ["iron_man"])
    assert "assignment" not in state["roster"]["iron_man"]
