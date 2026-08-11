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
    state["day"] = 2                            # M12: one gift per day
    result = bonds.give_gift(state, cap, "hydra_propaganda")
    assert result["points"] == 80 - 40                               # hated: -40, floor 0 not hit


def test_negative_bond_floors_at_zero(content):
    cap = content["characters"]["captain_america"]
    state = fresh_state()
    state["inventory"] = {"hydra_propaganda": 1}
    result = bonds.give_gift(state, cap, "hydra_propaganda")
    assert result["points"] == 0                                     # not negative


def test_gift_limits_one_per_day_two_per_five(content):
    # M12: 1 gift per receiver per day, 2 per rolling 5 days
    cap = content["characters"]["captain_america"]
    state = fresh_state()
    state["inventory"] = {"sketchbook": 2, "vintage_vinyl": 2}
    assert bonds.give_gift(state, cap, "sketchbook")["ok"]
    second = bonds.give_gift(state, cap, "vintage_vinyl")
    assert second["ok"] is False                            # 1/day
    assert "today" in second["message"]
    assert state["inventory"]["vintage_vinyl"] == 2         # not consumed
    state["day"] = 2
    assert bonds.give_gift(state, cap, "vintage_vinyl")["ok"]
    state["day"] = 4                                        # 2 already in window
    third = bonds.give_gift(state, cap, "sketchbook")
    assert third["ok"] is False and "lately" in third["message"]
    state["day"] = 6                                        # day-1 gift ages out
    assert bonds.give_gift(state, cap, "sketchbook")["ok"]


def test_repeat_gift_next_day_costs_five(content):
    cap = content["characters"]["captain_america"]
    state = fresh_state()
    state["inventory"] = {"sketchbook": 3}
    assert bonds.give_gift(state, cap, "sketchbook")["points"] == 45    # liked
    state["day"] = 2
    result = bonds.give_gift(state, cap, "sketchbook")      # same, back-to-back
    assert result["repeated"] is True
    assert result["points"] == 45 + 45 - config.GIFT_REPEAT_PENALTY     # 85
    state["day"] = 6                                        # window clear, and a
    result = bonds.give_gift(state, cap, "sketchbook")      # DAY GAP: no penalty
    assert result["repeated"] is False


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


def test_coulson_bond2_scene_triggers_once(content):
    state = fresh_state()
    assert events.pending_bond_events(state, content["bond_scenes"]) == []
    bonds.add_points(state, "coulson", 500)
    pending = events.pending_bond_events(state, content["bond_scenes"])
    assert [s["id"] for s in pending] == ["coulson_bond_2"]
    events.mark_seen(state, "coulson_bond_2")
    assert events.pending_bond_events(state, content["bond_scenes"]) == []


def test_old_friends_synergy_is_innate(content):
    # Relationship redesign: starters don't bond; IM+Cap synergy is innate.
    cap = content["characters"]["captain_america"]
    synergy = cap["synergies"][0]
    state = fresh_state()
    assert bonds.synergy_active(state, cap, synergy)   # active at bond 0


def test_bondable_split(content):
    chars = content["characters"]
    assert not bonds.bondable(chars["iron_man"])       # starter
    assert not bonds.bondable(chars["ant_man"])        # story recruit
    assert bonds.bondable(chars["hulk"])               # bond recruit
    assert bonds.bondable(chars["coulson"])            # NPC
    assert bonds.bondable(chars["jarvis"])
    assert bonds.bondable(chars["pepper_potts"])


def test_hulk_joins_roster_at_bond_4(content):
    state = fresh_state()
    bonds.add_points(state, "hulk", 4 * 250 - 1)
    assert bonds.check_bond_progress(state, content) == []
    assert "hulk" not in state["roster"]
    bonds.add_points(state, "hulk", 1)
    messages = bonds.check_bond_progress(state, content)
    assert any("Hulk joins the roster" in m for m in messages)
    assert "hulk" in state["roster"]
    assert bonds.check_bond_progress(state, content) == []   # only fires once


def test_npc_unlocks_fire_at_level_4(content):
    from game import config
    from game.hub import activities
    state = fresh_state()
    for npc, flag in (("jarvis", "jarvis_service"),
                      ("pepper_potts", "pepper_requisitions"),
                      ("coulson", "coulson_intel")):
        bonds.add_points(state, npc, 1000)
    messages = bonds.check_bond_progress(state, content)
    assert len(messages) == 3
    flags = state["story_flags"]
    assert flags["jarvis_service"] and flags["pepper_requisitions"] and flags["coulson_intel"]
    # effects
    cal.sleep(state)
    assert state["energy"] == config.DAILY_ENERGY + config.JARVIS_ENERGY_BONUS
    assert activities.shop_discount(state, content["calendar"]) == config.PEPPER_SHOP_DISCOUNT
    assert activities.mission_credits(state, 100) == 150


def test_npc_data_loads_without_combat_fields(content):
    jarvis = content["characters"]["jarvis"]
    assert "power_grid" not in jarvis and "abilities" not in jarvis
    assert jarvis["recruit"]["method"] == "npc"
    hulk = content["characters"]["hulk"]
    # card-authentic grid from assets/reference/hulk_53_back.jpg
    assert hulk["power_grid"] == {"strength": 7, "speed": 2, "agility": 2,
                                  "stamina": 6, "durability": 6, "intelligence": 5}
    assert hulk["recruit"] == {"chapter": 2, "method": "bond", "bond_level": 4}


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
