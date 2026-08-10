"""M3: bond math per §6.2 — talk, gifts, weekly limits, birthday multiplier,
levels, mission bonds, bond-event triggering."""

import pytest

from game import config, data_loader
from game.core import calendar as cal
from game.core import save
from game.social import bonds, events


@pytest.fixture(scope="module")
def content():
    return data_loader.load_all()


def fresh_state():
    return save.new_game_state()


def test_talk_gives_15_once_per_day():
    state = fresh_state()
    result = bonds.talk(state, "captain_america")
    assert result["ok"] and result["points"] == 15
    assert bonds.talk(state, "captain_america")["ok"] is False
    cal.sleep(state)
    assert bonds.talk(state, "captain_america")["ok"]
    assert state["bonds"]["captain_america"]["points"] == 30


def test_gift_categories_and_points(content):
    cap = content["characters"]["captain_america"]
    assert bonds.gift_category(cap, "forties_memorabilia") == "loved"
    assert bonds.gift_category(cap, "vintage_vinyl") == "liked"
    assert bonds.gift_category(cap, "modern_slang_guide") == "disliked"
    assert bonds.gift_category(cap, "hydra_propaganda") == "hated"
    assert bonds.gift_category(cap, "med_kit") == "neutral"

    state = fresh_state()
    state["inventory"] = {"forties_memorabilia": 1, "hydra_propaganda": 1}
    result = bonds.give_gift(state, cap, "forties_memorabilia")
    assert result["ok"] and result["points"] == config.GIFT_POINTS["loved"] == 80
    assert "forties_memorabilia" not in state["inventory"]          # consumed
    result = bonds.give_gift(state, cap, "hydra_propaganda")
    assert result["points"] == 80 - 40                               # hated: -40, floor 0 not hit


def test_negative_bond_floors_at_zero(content):
    cap = content["characters"]["captain_america"]
    state = fresh_state()
    state["inventory"] = {"hydra_propaganda": 1}
    result = bonds.give_gift(state, cap, "hydra_propaganda")
    assert result["points"] == 0                                     # not negative


def test_weekly_gift_limit_and_reset(content):
    cap = content["characters"]["captain_america"]
    state = fresh_state()
    state["day"] = 7
    state["inventory"] = {"sketchbook": 3}
    assert bonds.give_gift(state, cap, "sketchbook")["ok"]
    assert bonds.give_gift(state, cap, "sketchbook")["ok"]
    third = bonds.give_gift(state, cap, "sketchbook")
    assert third["ok"] is False                                      # max 2 per week
    assert state["inventory"]["sketchbook"] == 1                     # not consumed
    cal.sleep(state)                                                 # day 7 -> 8: new week row
    assert bonds.give_gift(state, cap, "sketchbook")["ok"]


def test_gift_requires_item(content):
    cap = content["characters"]["captain_america"]
    state = fresh_state()
    assert bonds.give_gift(state, cap, "sketchbook")["ok"] is False


def test_birthday_multiplier_x8(content):
    cap = content["characters"]["captain_america"]
    state = fresh_state()
    state["day"] = 20                                                # Cap's birthday
    state["inventory"] = {"forties_memorabilia": 1}
    result = bonds.give_gift(state, cap, "forties_memorabilia")
    assert result["points"] == 80 * 8 == 640
    assert result["level"] == 2                                      # 640 // 250
    assert result["level_up"]


def test_level_thresholds_and_lifetime_cap():
    state = fresh_state()
    assert bonds.add_points(state, "iron_man", 249)["level"] == 0
    assert bonds.add_points(state, "iron_man", 1)["level"] == 1
    result = bonds.add_points(state, "iron_man", 99999)
    assert result["points"] == config.BOND_LIFETIME_MAX == 2500
    assert result["level"] == config.BOND_LEVEL_MAX == 10


def test_mission_bond(content):
    state = fresh_state()
    bonds.mission_bond(state, ["iron_man", "captain_america"])
    assert state["bonds"]["iron_man"]["points"] == 10
    assert state["bonds"]["captain_america"]["points"] == 10


def test_cap_bond2_scene_triggers_once(content):
    state = fresh_state()
    assert events.pending_bond_events(state, content["bond_scenes"]) == []
    bonds.add_points(state, "captain_america", 500)
    pending = events.pending_bond_events(state, content["bond_scenes"])
    assert [s["id"] for s in pending] == ["cap_bond_2"]
    events.mark_seen(state, "cap_bond_2")
    assert events.pending_bond_events(state, content["bond_scenes"]) == []


def test_synergy_gate_at_level_6(content):
    cap = content["characters"]["captain_america"]
    synergy = cap["synergies"][0]
    state = fresh_state()
    bonds.add_points(state, "captain_america", 6 * 250 - 1)
    assert not bonds.synergy_active(state, cap, synergy)
    bonds.add_points(state, "captain_america", 1)
    assert bonds.synergy_active(state, cap, synergy)


# --- M3 acceptance: reach Cap Bond 2 through play across a week boundary ---

def test_reach_cap_bond_2_through_play(content):
    cap = content["characters"]["captain_america"]
    state = fresh_state()
    state["inventory"] = {"forties_memorabilia": 4}
    days_played = 0
    while bonds.bond_level(bonds.ensure_bond(state, "captain_america")["points"]) < 2:
        bonds.talk(state, "captain_america")                     # +15/day
        bonds.give_gift(state, cap, "forties_memorabilia")       # +80, 2/week max
        bonds.mission_bond(state, ["iron_man", "captain_america"])  # +10
        cal.sleep(state)
        days_played += 1
        assert days_played < 28, "should reach Bond 2 well within an issue"
    # 500 points needed; talks+missions+2 gifts/week -> ~11 days
    assert days_played <= 14
    gifts_given = 4 - state["inventory"].get("forties_memorabilia", 0)
    assert gifts_given >= 3                                      # crossed a week boundary
