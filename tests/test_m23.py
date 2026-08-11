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
    pays = [l for l in labels if l.strip().startswith("pays ")]
    assert pays, labels
    for line in pays:
        assert "cr" in line
    assert any("XP" in l and "/stat" in l for l in pays)
    assert any("bond with" in l for l in pays)


def test_a_reward_line_quotes_xp_per_stat(content):
    scene = HubScene(content)
    task = next(t for t in content["assignments"] if t["id"] == "spar_rookies")
    label = scene._reward_label(task)
    assert "~130 cr" in label
    assert f"~{task['xp']} XP (+20/stat)" in label


def test_jobs_without_a_reward_do_not_advertise_it(content):
    scene = HubScene(content)
    label = scene._reward_label({"credits": 50, "xp": 0})
    assert label == "~50 cr"


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
