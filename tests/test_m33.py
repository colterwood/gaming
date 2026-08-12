"""M33: the progression chart. Rank costs double every level, talent buys
combat value and nothing else, and above rank 10 sits Enlightenment — one
more doubling, open only to a hero who has maxed all six.
"""

import pygame
import pytest

from game import config, data_loader
from game.core import save
from game.hub import activities
from game.progression import attributes as attrs
from game.progression import mastery


@pytest.fixture(scope="module")
def content():
    pygame.init()
    return data_loader.load_all()


def entry(maxed=False):
    e = {"trained_ranks": {}, "attribute_xp": {}, "perks": [],
         "perk_choices": {}, "gear": {}, "ult_charge": 0, "energy": 100}
    if maxed:
        e["trained_ranks"] = {a: config.TRAINED_MAX for a in config.ATTRIBUTES}
    return e


# --- the published chart (1) ---------------------------------------------

def test_the_ladder_matches_the_chart():
    assert config.XP_TO_NEXT_RANK == {
        1: 100, 2: 200, 3: 400, 4: 800, 5: 1600,
        6: 3200, 7: 6400, 8: 12800, 9: 25600}
    assert config.ENLIGHTENMENT_XP == 51200          # one more doubling


def test_each_rung_costs_double_the_one_below():
    for level in range(1, config.TRAINED_MAX):
        assert attrs.xp_for_rank(level + 1) == attrs.xp_for_rank(level) * 2


def test_talent_is_not_a_discount(content):
    hulk = content["characters"]["hulk"]["boosts"]           # strength 7
    cap = content["characters"]["captain_america"]["boosts"]  # strength 2
    strong, weak = entry(), entry()
    cost = attrs.xp_for_rank(1)
    attrs.add_training_xp(hulk, strong, "strength", cost)
    attrs.add_training_xp(cap, weak, "strength", cost)
    assert attrs.rank(strong, "strength") == attrs.rank(weak, "strength") == 2
    # The boost still pays — in the combat value, which is its whole job.
    assert (attrs.effective_rank(hulk, strong, "strength")
            > attrs.effective_rank(cap, weak, "strength"))


# --- Enlightenment (2) ----------------------------------------------------

def test_it_is_shut_until_every_skill_is_at_ten(content):
    e = entry()
    assert not mastery.available(e)
    e["trained_ranks"] = {a: config.TRAINED_MAX for a in config.ATTRIBUTES}
    e["trained_ranks"]["speed"] = config.TRAINED_MAX - 1     # one short
    mastery.update_mastery(None, e)
    assert not mastery.available(e)
    e["trained_ranks"]["speed"] = config.TRAINED_MAX
    mastery.update_mastery(None, e)
    assert mastery.available(e)


def test_the_rack_refuses_it_early(content):
    state = save.new_game_state()
    state["roster"] = {"iron_man": entry(), "captain_america": entry()}
    state["party"] = ["iron_man", "captain_america"]
    result = activities.start_training(state, content, "iron_man",
                                       mastery.ATTRIBUTE)
    assert not result["ok"]
    assert "all six" in result["message"]


def test_the_rack_offers_it_once_the_six_are_full(content):
    state = save.new_game_state()
    state["roster"] = {"iron_man": entry(maxed=True), "captain_america": entry()}
    state["party"] = ["iron_man", "captain_america"]
    mastery.update_mastery(None, state["roster"]["iron_man"])

    result = activities.start_training(state, content, "iron_man",
                                       mastery.ATTRIBUTE)
    assert result["ok"]
    # It is trained like a tenth rank: the longest session in the game.
    assert result["minutes"] == config.TRAINING_MINUTES_BY_LEVEL[config.TRAINED_MAX]

    # A 2,400-minute session spans two days; the clock itself is M16's
    # business, so just run it out here.
    state["roster"]["iron_man"]["training"]["ends_abs"] = 0
    activities.finish_due_training(state, content)
    done, needed = mastery.progress(state["roster"]["iron_man"])
    assert 0 < done < needed


def test_it_completes_at_the_full_amount(content):
    e = entry(maxed=True)
    mastery.update_mastery(None, e)
    mastery.add_enlightenment_xp(e, config.ENLIGHTENMENT_XP - 1)
    assert not mastery.is_enlightened(e)
    mastery.add_enlightenment_xp(e, 1)
    assert mastery.is_enlightened(e)
    assert not mastery.available(e)              # nothing left to climb


def test_field_xp_pours_into_it_once_there_is_nowhere_else(content):
    boosts = content["characters"]["iron_man"]["boosts"]
    e = entry(maxed=True)
    # M21 drops maxed attributes from the split, so the six take nothing...
    assert attrs.award_battle_xp(boosts, e, 500)["per_attribute"] == {}
    # ...and this is where it lands instead, flagging the state on the way.
    mastery.log_mastery_xp(e, 500)
    assert mastery.progress(e)[0] == 500


def test_a_hero_short_of_the_cap_banks_nothing_toward_it(content):
    e = entry()
    mastery.log_mastery_xp(e, 500)
    assert mastery.progress(e)[0] == 0
