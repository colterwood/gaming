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
            "perk_choices": {}, "energy": 100}


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
    # M15: everyone starts at rank 1; power is rank lifted by innate boosts
    state = state_with(["iron_man", "captain_america"], ["iron_man"])
    assert dispatch.hero_power(content, state, "iron_man") == pytest.approx(21.53, abs=0.01)
    assert dispatch.hero_power(content, state, "captain_america") == pytest.approx(15.49, abs=0.01)
    assert dispatch.team_power(content, state) == pytest.approx(37.02, abs=0.01)
    before = dispatch.team_power(content, state)
    state["roster"]["captain_america"]["trained_ranks"] = {"strength": 2}
    assert dispatch.team_power(content, state) > before      # training adds power


def test_roster_tier_thresholds(content):
    # M15 scale: 2 starters at rank 1 = 37, a full roster at rank 1 = 75,
    # everyone at rank 10 = 299. Tiers unlock at 90 and 160.
    state = state_with(["iron_man", "captain_america"], ["iron_man"])
    assert dispatch.roster_tier(content, state) == 1            # power 37
    state["roster"]["ant_man"] = entry()
    state["roster"]["hulk"] = entry()
    assert dispatch.roster_tier(content, state) == 1            # power 75
    for hid in state["roster"]:                                 # rank 2 -> 100
        state["roster"][hid]["trained_ranks"] = {a: 1 for a in config.ATTRIBUTES}
    assert dispatch.roster_tier(content, state) == 2
    for hid in state["roster"]:                                 # rank 5 -> 187
        state["roster"][hid]["trained_ranks"] = {a: 4 for a in config.ATTRIBUTES}
    assert dispatch.roster_tier(content, state) == 3


def test_tasks_today_two_per_unlocked_tier(content):
    state = state_with(["iron_man"], ["iron_man"])
    tier1 = activities.assignment_tasks_today(state, content["assignments"], 1)
    assert len(tier1) == 2
    assert all(t["tier"] == 1 for t in tier1)
    # M15: bond-gated jobs are not posted until the relationship exists, so
    # a fresh roster sees fewer than the full 2-per-tier at the top end.
    tier3 = activities.assignment_tasks_today(state, content["assignments"], 3)
    assert 4 <= len(tier3) <= 6
    assert sorted({t["tier"] for t in tier3})[0] == 1


# --- power-scaled dispatch pay ---

def test_dispatch_pay_scales_with_sent_hero(content):
    task = task_by_id(content, "sweep_hangar")                  # base 60 cr
    # M15: Iron Man (power 21.5) out-earns Cap (15.5) on the same job
    state = state_with(["iron_man", "captain_america"],
                       ["iron_man", "captain_america"])
    im_mult = dispatch.reward_mult(content, state, ["iron_man"])
    cap_mult = dispatch.reward_mult(content, state, ["captain_america"])
    assert im_mult > cap_mult
    dispatch.send(content, state, task, ["iron_man"])
    assert dispatch.active(state)[0]["credits"] == round(60 * im_mult)
    state = state_with(["iron_man", "captain_america"],
                       ["iron_man", "captain_america"])
    dispatch.send(content, state, task, ["captain_america"])
    assert dispatch.active(state)[0]["credits"] == round(60 * cap_mult)


def test_dispatch_pay_clamps(content):
    state = state_with(["iron_man", "captain_america"], ["iron_man"])
    # max out Cap: every attribute at rank 10 -> power ~71 -> ~1.49x
    state["roster"]["captain_america"]["trained_ranks"] = {
        a: config.TRAINED_MAX for a in config.ATTRIBUTES}
    mult = dispatch.reward_mult(content, state, ["captain_america"])
    assert config.DISPATCH_MULT_MIN <= mult <= config.DISPATCH_MULT_MAX
    assert mult == pytest.approx(1.49, abs=0.01)


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
    task = task_by_id(content, "escort_convoy")     # 2 heroes, 2 days
    mult = dispatch.reward_mult(content, state, ["iron_man", "ant_man"])
    dispatch.send(content, state, task, ["iron_man", "ant_man"])
    assert dispatch.process_day(content, state) == []       # night 1: away
    dispatch.process_day(content, state)                    # night 2: home
    assert state["credits"] == round(task["credits"] * mult)    # paid ONCE
    # M21 applies it to attributes; M24 aims it at the ones the job trains
    each = round(task["xp"] * mult)
    for hero_id in ("iron_man", "ant_man"):
        gains = state["roster"][hero_id]["attribute_xp"]
        assert set(gains) == set(task["trains"]), hero_id
        assert all(v == each for v in gains.values()), gains


def test_two_hero_request_pays_bond_once_per_job(content):
    state = state_with(["iron_man", "captain_america", "ant_man"],
                       ["iron_man", "captain_america", "ant_man"])
    task = task_by_id(content, "escort_delegation")         # coulson, bond 60
    # M15: this job is gated behind Coulson bond 2 — earn it first
    bonds.add_points(state, "coulson", 2 * config.BOND_POINTS_PER_LEVEL)
    ok, message = dispatch.send(content, state, task, ["iron_man", "ant_man"])
    assert ok, message
    dispatch.process_day(content, state)
    assert state["bonds"]["coulson"]["points"] == 500 + 60  # once, not per hero


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
