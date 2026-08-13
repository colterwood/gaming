"""M21: field XP lands on the attributes when it's earned, split across the
six, with the innate boost buying exactly what it buys on the rack."""

import pytest

from game import config, data_loader
from game.core import save
from game.progression import attributes as attrs

ATTRS = config.ATTRIBUTES


@pytest.fixture(scope="module")
def content():
    return data_loader.load_all()


def entry():
    return {"trained_ranks": {}, "attribute_xp": {}, "perks": [],
            "perk_choices": {}, "gear": {}, "ult_charge": 0, "energy": 100}


# --- the split ---

def test_xp_is_split_evenly_across_the_six(content):
    e = entry()
    boosts = content["characters"]["captain_america"]["boosts"]
    gain = attrs.award_battle_xp(boosts, e, 270)        # a Crossbones win
    assert gain["per_attribute"] == {a: 45 for a in ATTRS}
    assert sum(e["attribute_xp"].values()) == 270


def test_a_remainder_is_spread_not_dropped(content):
    e = entry()
    boosts = content["characters"]["captain_america"]["boosts"]
    gain = attrs.award_battle_xp(boosts, e, 100)        # 16 r4
    assert sum(gain["per_attribute"].values()) == 100
    assert sorted(gain["per_attribute"].values()) == [16, 16, 17, 17, 17, 17]


def test_zero_and_negative_are_no_ops(content):
    boosts = content["characters"]["captain_america"]["boosts"]
    for xp in (0, -50):
        e = entry()
        assert attrs.award_battle_xp(boosts, e, xp)["per_attribute"] == {}
        assert e["attribute_xp"] == {}


def test_a_maxed_attribute_drops_out_instead_of_eating_its_share(content):
    e = entry()
    boosts = content["characters"]["captain_america"]["boosts"]
    e["trained_ranks"]["agility"] = config.TRAINED_MAX      # rank 10
    gain = attrs.award_battle_xp(boosts, e, 100)
    assert "agility" not in gain["per_attribute"]
    assert len(gain["per_attribute"]) == 5
    assert sum(gain["per_attribute"].values()) == 100       # nothing lost


def test_a_fully_mastered_hero_loses_nothing_it_could_have_used(content):
    e = entry()
    boosts = content["characters"]["captain_america"]["boosts"]
    for a in ATTRS:
        e["trained_ranks"][a] = config.TRAINED_MAX
    gain = attrs.award_battle_xp(boosts, e, 500)
    assert gain["per_attribute"] == {}       # nowhere left to put it


# --- the boost buys the same thing it buys on the rack ---

def test_field_xp_goes_exactly_as_far_for_everyone(content):
    # M33: talent no longer discounts the ladder, so the same 600 XP buys
    # Iron Man (Strength boost 6) and Cap (boost 2) the same rank. What the
    # boost is worth shows up in the combat value, not in the climb.
    iron, cap = entry(), entry()
    iron_boosts = content["characters"]["iron_man"]["boosts"]
    cap_boosts = content["characters"]["captain_america"]["boosts"]
    attrs.award_battle_xp(iron_boosts, iron, 600)
    attrs.award_battle_xp(cap_boosts, cap, 600)

    assert attrs.rank(iron, "strength") == attrs.rank(cap, "strength")
    assert (attrs.effective_rank(iron_boosts, iron, "strength")
            > attrs.effective_rank(cap_boosts, cap, "strength"))


def test_the_award_itself_is_boost_blind(content):
    # Same 300 XP to a boost-7 and a boost-2 attribute: the XP put in is
    # the same number, per the rack's model.
    hulk = content["characters"]["hulk"]["boosts"]        # strength 7
    cap = content["characters"]["captain_america"]["boosts"]   # strength 2
    a, b = entry(), entry()
    assert (attrs.award_battle_xp(hulk, a, 300)["per_attribute"]["strength"]
            == attrs.award_battle_xp(cap, b, 300)["per_attribute"]["strength"]
            == 50)


def test_ranks_gained_in_the_field_are_reported(content):
    e = entry()
    boosts = content["characters"]["captain_america"]["boosts"]
    # 130 XP per attribute clears Cap's rank 1 -> 2 in every one of them
    gain = attrs.award_battle_xp(boosts, e, 130 * len(ATTRS))
    assert {a for a, _ in gain["ranks_gained"]} == set(ATTRS)
    assert all(attrs.rank(e, a) == 2 for a in ATTRS)


# --- the bank is gone, and nothing already earned was lost ---

def test_the_training_rack_no_longer_double_dips(content):
    from game.hub import activities
    state = save.new_game_state()
    state["roster"] = {"iron_man": entry(), "captain_america": entry()}
    state["party"] = ["iron_man", "captain_america"]
    state["credits"] = 10000                                 # M36: the rack bills
    state["roster"]["captain_america"]["unspent_xp"] = 500   # a legacy bank
    activities.start_training(state, content, "captain_america", "strength")
    lock = state["roster"]["captain_america"]["training"]
    assert lock["xp"] == config.TRAINING_XP_BY_LEVEL[1]      # no top-up
    assert "banked" not in lock


def test_loading_a_save_spends_any_leftover_bank(content, monkeypatch, tmp_path):
    """A save from before this change still has XP sitting in the bank. It
    was earned - spend it onto the attributes rather than dropping it."""
    from game.__main__ import App

    monkeypatch.setattr(config, "SAVE_DIR", str(tmp_path))
    legacy = save.new_game_state()
    legacy["path"] = "avengers"
    legacy["roster"] = {"iron_man": entry(), "captain_america": entry()}
    legacy["roster"]["iron_man"]["unspent_xp"] = 600
    legacy["party"] = ["iron_man", "captain_america"]
    legacy["unspent_xp"] = 999                      # dead top-level copy
    save.save_game(legacy, 1, save_dir=str(tmp_path))

    app = App()
    assert app.load_game() is True
    iron = app.game_state["roster"]["iron_man"]
    assert "unspent_xp" not in iron                 # bank retired...
    banked_now = sum(iron["attribute_xp"].values())
    ranks = sum(iron["trained_ranks"].values())
    assert banked_now or ranks                      # ...into real progress
    spent_on_ranks = sum(
        attrs.xp_for_rank(config.RANK_START + i)
        for a in ATTRS
        for i in range(iron["trained_ranks"].get(a, 0)))
    assert banked_now + spent_on_ranks == 600       # every point accounted for
    assert "unspent_xp" not in app.game_state       # and the dead copy is gone
