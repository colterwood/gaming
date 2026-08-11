"""M11 systems: board tiers + power-scaled dispatch pay, NPC requests,
tiered dialogue, gift reactions, unblocked mission engagement."""

import pytest

from game import config, data_loader
from game.core import energy, save
from game.hub import activities, dispatch
from game.social import bonds, dialogue


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


# --- team power & board tiers ---

def test_team_power_sums_top_four(content):
    state = state_with(["iron_man", "captain_america"], ["iron_man"])
    assert dispatch.hero_power(content, state, "iron_man") == 29
    assert dispatch.hero_power(content, state, "captain_america") == 18
    assert dispatch.team_power(content, state) == 47
    # trained ranks count toward power
    state["roster"]["captain_america"]["trained_ranks"] = {"strength": 2}
    assert dispatch.team_power(content, state) == 49


def test_roster_tier_thresholds(content):
    state = state_with(["iron_man", "captain_america"], ["iron_man"])
    assert dispatch.roster_tier(content, state) == 1            # power 47
    state["roster"]["ant_man"] = entry()                        # +20 -> 67
    assert dispatch.roster_tier(content, state) == 1
    state["roster"]["hulk"] = entry()                           # +28 -> 95
    assert dispatch.roster_tier(content, state) == 2
    for hid in state["roster"]:                                 # +4 each -> 111
        state["roster"][hid]["trained_ranks"] = {"speed": 2, "agility": 2}
    assert dispatch.roster_tier(content, state) == 3


def test_tasks_today_two_per_unlocked_tier(content):
    state = state_with(["iron_man"], ["iron_man"])
    tier1 = activities.assignment_tasks_today(state, content["assignments"], 1)
    assert len(tier1) == 2
    assert all(t["tier"] == 1 for t in tier1)
    tier3 = activities.assignment_tasks_today(state, content["assignments"], 3)
    assert len(tier3) == 6
    assert sorted({t["tier"] for t in tier3}) == [1, 2, 3]


# --- power-scaled dispatch pay ---

def test_dispatch_pay_scales_with_sent_hero(content):
    task = task_by_id(content, "sweep_hangar")                  # base 60 cr
    # Iron Man (power 29): 1 + 0.02*(29-24) = 1.10x
    state = state_with(["iron_man", "captain_america"],
                       ["iron_man", "captain_america"])
    assert dispatch.reward_mult(content, state, ["iron_man"]) == pytest.approx(1.10)
    dispatch.send(content, state, task, ["iron_man"])
    assert dispatch.active(state)[0]["credits"] == 66
    # Cap (power 18): 1 + 0.02*(18-24) = 0.88x
    state = state_with(["iron_man", "captain_america"],
                       ["iron_man", "captain_america"])
    dispatch.send(content, state, task, ["captain_america"])
    assert dispatch.active(state)[0]["credits"] == 53           # round(52.8)


def test_dispatch_pay_clamps(content):
    state = state_with(["iron_man", "captain_america"], ["iron_man"])
    # max out Cap: all six attributes to rank 7 -> power 42 -> raw 1.36x (in range)
    state["roster"]["captain_america"]["trained_ranks"] = {
        a: 7 for a in config.ATTRIBUTES}
    assert dispatch.reward_mult(content, state, ["captain_america"]) <= config.DISPATCH_MULT_MAX
    assert dispatch.reward_mult(content, state, ["captain_america"]) == pytest.approx(1.36)


# --- NPC requests ---

def test_npc_request_pays_bond_on_completion(content):
    state = state_with(["iron_man", "captain_america"],
                       ["iron_man", "captain_america"])
    task = task_by_id(content, "pepper_contracts")              # 1d, bond 35
    dispatch.send(content, state, task, ["iron_man"])
    assert dispatch.active(state)[0]["requested_by"] == "pepper_potts"
    messages = dispatch.process_day(content, state)
    assert any("grateful" in m and "+35 bond" in m for m in messages)
    assert state["bonds"]["pepper_potts"]["points"] == 35


def test_two_hero_dispatch_pays_once_and_banks_both(content):
    state = state_with(["iron_man", "captain_america", "ant_man"],
                       ["iron_man", "captain_america", "ant_man"])
    task = task_by_id(content, "escort_convoy")     # 2 heroes, 2 days, 280/80
    # Iron Man 29 + Ant-Man 20 -> avg 24.5 -> 1.01x
    assert dispatch.reward_mult(content, state,
                                ["iron_man", "ant_man"]) == pytest.approx(1.01)
    dispatch.send(content, state, task, ["iron_man", "ant_man"])
    assert dispatch.process_day(content, state) == []       # night 1: away
    dispatch.process_day(content, state)                    # night 2: home
    assert state["credits"] == 283                  # 280 x 1.01, paid ONCE
    assert state["roster"]["iron_man"]["unspent_xp"] == 81  # 80 x 1.01, EACH
    assert state["roster"]["ant_man"]["unspent_xp"] == 81


def test_two_hero_request_pays_bond_once_per_job(content):
    state = state_with(["iron_man", "captain_america", "ant_man"],
                       ["iron_man", "captain_america", "ant_man"])
    task = task_by_id(content, "escort_delegation")         # coulson, bond 60
    dispatch.send(content, state, task, ["iron_man", "ant_man"])
    dispatch.process_day(content, state)
    assert state["bonds"]["coulson"]["points"] == 60        # once, not per hero


def test_recalled_request_pays_no_bond(content):
    state = state_with(["iron_man", "captain_america"],
                       ["iron_man", "captain_america"])
    task = task_by_id(content, "pepper_contracts")
    dispatch.send(content, state, task, ["iron_man"])
    dispatch.recall(content, state, task["id"])
    assert state.get("bonds", {}).get("pepper_potts", {}).get("points", 0) == 0


# --- unblocked mission engagement ---

def test_energy_drain_floors_at_zero():
    state = state_with(["iron_man", "captain_america"],
                       ["iron_man", "captain_america"])
    state["roster"]["captain_america"]["energy"] = 15
    energy.drain(state, config.MISSION_ENERGY)
    assert state["roster"]["captain_america"]["energy"] == 0
    assert state["roster"]["iron_man"]["energy"] == 60
    assert state["energy"] == 0                                 # team = min


# --- tiered dialogue ---

def test_dialogue_tier_follows_bond_level(content):
    state = state_with([], [])
    jarvis = content["characters"]["jarvis"]
    low = dialogue.line_for(state, jarvis, content["dialogue"])
    assert low in content["dialogue"]["jarvis"]["0"]
    bonds.add_points(state, "jarvis", 6 * config.BOND_POINTS_PER_LEVEL)
    high = dialogue.line_for(state, jarvis, content["dialogue"])
    assert high in content["dialogue"]["jarvis"]["6"]


def test_dialogue_starters_follow_story(content):
    state = state_with([], [])
    cap = content["characters"]["captain_america"]
    assert dialogue.tier_level(state, cap) == 0
    state["story_flags"]["training_upgraded"] = True
    assert dialogue.tier_level(state, cap) == 2
    state["story_flags"]["ch2_complete"] = True
    assert dialogue.tier_level(state, cap) == 4
    line = dialogue.line_for(state, cap, content["dialogue"])
    assert line in content["dialogue"]["captain_america"]["4"]


def test_dialogue_between_and_above_pool_keys(content):
    # Pools are keyed 0/2/4/6 but bond levels run 0-10: in-between levels
    # floor to the richest unlocked pool, and 7+ falls back to pool "6".
    state = state_with([], [])
    jarvis = content["characters"]["jarvis"]
    bonds.add_points(state, "jarvis", 1 * config.BOND_POINTS_PER_LEVEL)
    assert dialogue.line_for(state, jarvis, content["dialogue"]) \
        in content["dialogue"]["jarvis"]["0"]               # level 1 -> pool 0
    bonds.add_points(state, "jarvis", 6 * config.BOND_POINTS_PER_LEVEL)
    assert dialogue.line_for(state, jarvis, content["dialogue"]) \
        in content["dialogue"]["jarvis"]["6"]               # level 7 -> pool 6
    bonds.add_points(state, "jarvis", 3 * config.BOND_POINTS_PER_LEVEL)
    assert dialogue.line_for(state, jarvis, content["dialogue"]) \
        in content["dialogue"]["jarvis"]["6"]               # level 10 -> pool 6


def test_dialogue_rotates_daily(content):
    state = state_with([], [])
    jarvis = content["characters"]["jarvis"]
    lines = set()
    for day in (1, 2, 3):
        state["day"] = day
        lines.add(dialogue.line_for(state, jarvis, content["dialogue"]))
    assert len(lines) == 3                                      # 3-line pool


def test_every_character_has_dialogue(content):
    for char_id in content["characters"]:
        assert char_id in content["dialogue"], f"{char_id} has no dialogue"


# --- gift reactions ---

def test_gift_reactions_show_relevance(content):
    cap = content["characters"]["captain_america"]
    state = state_with([], [])
    state["inventory"] = {"forties_memorabilia": 1, "hydra_propaganda": 1,
                          "med_kit": 1}
    assert "loves it!" in bonds.give_gift(state, cap, "forties_memorabilia")["message"]
    state["day"] = 2                    # M12: one gift per receiver per day
    assert "hates it!" in bonds.give_gift(state, cap, "hydra_propaganda")["message"]
    state["day"] = 7                    # both earlier gifts age out of the window
    result = bonds.give_gift(state, cap, "med_kit")
    assert "accepts it politely" in result["message"]
    assert result["category"] == "neutral"
