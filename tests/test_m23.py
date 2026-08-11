"""M23: defensive enemies stop turtling, board jobs advertise every reward,
the Ops console stops offering rides, and Stormbreaker wants a rank-3 Cap."""

import random
from types import SimpleNamespace

import pygame
import pytest

from game import config, data_loader
from game.combat import enemy_ai
from game.combat.engine import BattleEngine
from game.combat.entities import Combatant, make_enemy_group
from game.hub.tower import HubScene

from tests.test_tower_scene import FakeApp, put_player_at


@pytest.fixture(scope="module")
def content():
    pygame.init()
    return data_loader.load_all()


# --- defensive enemies fight back (1) ---

def wounded(fraction, defended_last_turn=False):
    return SimpleNamespace(hp_fraction=lambda: fraction,
                           defended_last_turn=defended_last_turn)


def test_a_healthy_defensive_enemy_never_guards():
    assert not enemy_ai.should_defend(wounded(1.0))
    assert not enemy_ai.should_defend(wounded(
        config.AI_DEFENSIVE_HP_THRESHOLD))


def test_it_guards_when_hurt_but_never_twice_running():
    hurt = (config.AI_DEFENSIVE_HP_THRESHOLD
            + config.AI_DEFENSIVE_LAST_STAND_HP) / 2
    assert enemy_ai.should_defend(wounded(hurt))
    assert not enemy_ai.should_defend(wounded(hurt, defended_last_turn=True))


def test_a_cornered_enemy_stops_guarding_entirely():
    assert not enemy_ai.should_defend(
        wounded(config.AI_DEFENSIVE_LAST_STAND_HP / 2))


def test_a_wounded_enforcer_cannot_stall_the_fight(content):
    # The reported behaviour: below the threshold it defended EVERY turn,
    # so the fight became a damage sponge that never hit back.
    hero = Combatant(content["characters"]["captain_america"],
                     trained_ranks={}, is_hero=True)
    enemy = make_enemy_group([content["enemies"]["hydra_enforcer"]])[0]
    enemy.hp = max(1, int(enemy.max_hp * 0.3))          # wounded, not cornered

    actions = []
    for _ in range(8):
        action = enemy_ai.choose_action(enemy, [enemy], [hero])
        actions.append(action["type"])
        enemy.defended_last_turn = action["type"] == "defend"
    assert "defend" in actions, "it should still guard sometimes"
    assert "ability" in actions, "but it must hit back too"
    # never two guards in a row
    assert not any(a == b == "defend" for a, b in zip(actions, actions[1:]))


def test_each_combatant_records_its_own_last_action(content):
    hero = Combatant(content["characters"]["iron_man"], trained_ranks={},
                     is_hero=True)
    enemy = make_enemy_group([content["enemies"]["hydra_enforcer"]])[0]
    engine = BattleEngine([hero], [enemy], rng=random.Random(1))

    first = engine.current()
    engine.take_turn({"type": "defend"})            # the turn passes on
    assert first.defended_last_turn is True

    second = engine.current()
    assert second is not first
    basic = second.abilities_of_type("basic")[0]
    engine.take_turn({"type": "ability", "ability_id": basic["id"],
                      "target_id": first.id})
    assert second.defended_last_turn is False
    assert first.defended_last_turn is True         # somebody else's turn



# --- the board advertises everything (2) ---

def test_the_board_spells_out_every_reward(content):
    scene, app = HubScene(content), FakeApp(content)
    app.game_state["day"] = 3                   # rotation shows an NPC request
    put_player_at(scene, 34, 12)
    scene.handle_key(app, pygame.K_RETURN)
    labels = [i[0] for i in scene.submenu["items"]]
    pays = [l for l in labels if l.strip().endswith(("cr",)) or " XP to " in l]
    assert pays, labels
    assert not any("pays " in l or "~" in l for l in labels)    # M25 wording
    assert any("XP to " in l for l in pays)
    assert any("bond with" in l for l in pays)


def test_a_reward_line_names_what_a_job_trains(content):
    scene = HubScene(content)
    sweep = next(t for t in content["assignments"] if t["id"] == "sweep_hangar")
    assert scene._reward_label(sweep) == "60 cr, 20 XP to Stamina"
    convoy = next(t for t in content["assignments"] if t["id"] == "escort_convoy")
    assert ("10 XP to Strength, Stamina, Agility and Durability"
            in scene._reward_label(convoy))


def test_jobs_without_a_reward_do_not_advertise_it(content):
    scene = HubScene(content)
    label = scene._reward_label({"credits": 50, "xp": 0})
    assert label == "50 cr"


# --- Stormbreaker's gate (4) ---

def test_stormbreaker_wants_a_rank_three_cap(content):
    arc = next(a for a in content["unlocks"] if a["id"] == "thor_stormbreaker")
    assert arc["requires"]["hero_min_rank"] == {"captain_america": 3}


def test_the_ops_console_never_offers_a_ride(content):
    # Both a mission briefing and a live side-arc signal (3).
    from game.hub import story, unlocks

    scene, app = HubScene(content), FakeApp(content)
    state = app.game_state
    story.accept(state, story.current_quest(state, content["story"]))
    arc = next(a for a in content["unlocks"] if a["id"] == "thor_stormbreaker")
    state["unlocks"] = {arc["id"]: {"status": "searching", "searched": [],
                                    "hidden": 0, "day": 1}}
    assert unlocks.is_active(state, arc)
    scene.floor = "ops"
    put_player_at(scene, 8, 5)
    scene.handle_key(app, pygame.K_RETURN)
    labels = [i[0] for i in scene.submenu["items"]]
    assert any(l.startswith("SIGNAL - ") for l in labels)     # still briefed
    assert not any("Fly to" in l for l in labels)
    for label, disabled, callback in scene.submenu["items"]:
        assert disabled or label == "Close", label


# --- targeted assignment XP (M24) ---

def test_a_job_trains_only_what_it_names(content):
    from game.hub import dispatch

    state = FakeApp(content).game_state
    task = next(t for t in content["assignments"] if t["id"] == "sweep_hangar")
    assert task["trains"] == ["stamina"]
    dispatch.send(content, state, task, ["iron_man"])
    dispatch.process_day(content, state)
    gains = state["roster"]["iron_man"]["attribute_xp"]
    assert set(gains) == {"stamina"}                # nothing else moved
    assert gains["stamina"] >= task["xp"] * config.DISPATCH_MULT_MIN


def test_award_targets_each_named_attribute_in_full(content):
    from game.progression import attributes as attrs
    boosts = content["characters"]["captain_america"]["boosts"]
    entry = {"trained_ranks": {}, "attribute_xp": {}, "perks": [],
             "perk_choices": {}, "gear": {}, "ult_charge": 0, "energy": 100}
    gain = attrs.award_attribute_xp(boosts, entry, 40, ["speed", "agility"])
    assert gain["per_attribute"] == {"speed": 40, "agility": 40}   # each, not split
    assert entry["attribute_xp"] == {"speed": 40, "agility": 40}
    # None means all six
    fresh = dict(entry, attribute_xp={}, trained_ranks={})
    attrs.award_attribute_xp(boosts, fresh, 10, None)
    assert set(fresh["attribute_xp"]) == set(config.ATTRIBUTES)


def test_a_maxed_attribute_is_skipped_not_wasted(content):
    from game.progression import attributes as attrs
    boosts = content["characters"]["captain_america"]["boosts"]
    entry = {"trained_ranks": {"speed": config.TRAINED_MAX},
             "attribute_xp": {}, "perks": [], "perk_choices": {}, "gear": {},
             "ult_charge": 0, "energy": 100}
    gain = attrs.award_attribute_xp(boosts, entry, 40, ["speed", "agility"])
    assert gain["per_attribute"] == {"agility": 40}


def test_trains_label_reads_naturally():
    from game.hub import dispatch
    assert dispatch.trains_label(None) == "all skills"
    assert dispatch.trains_label(list(config.ATTRIBUTES)) == "all skills"
    assert dispatch.trains_label(["stamina"]) == "Stamina"
    assert dispatch.trains_label(["speed", "agility"]) == "Speed and Agility"
    assert (dispatch.trains_label(["strength", "stamina", "agility"])
            == "Strength, Stamina and Agility")


def test_every_shipped_job_names_a_real_attribute(content):
    for task in content["assignments"]:
        for attribute in task.get("trains") or []:
            assert attribute in config.ATTRIBUTES, task["id"]
