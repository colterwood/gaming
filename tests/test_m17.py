"""M17: the Thor / Stormbreaker unlock — a conditional side arc that fires
off story flags plus hero progress, is worked on foot in Midtown, and only
yields to a hero who is actually present."""

import pygame
import pytest

from game import config, data_loader
from game.core import calendar as cal
from game.core import save
from game.hub import story, unlocks
from game.hub.tower import HUD_H, TILE, HubScene
from game.progression import attributes as attrs

ARC_ID = "thor_stormbreaker"


@pytest.fixture(scope="module")
def content():
    pygame.init()
    return data_loader.load_all()


@pytest.fixture
def arc(content):
    return next(a for a in content["unlocks"] if a["id"] == ARC_ID)


def fresh_run(content):
    state = save.new_game_state()
    state["path"] = "avengers"
    for c in content["characters"].values():
        if c["recruit"]["method"] == "starter":
            state["roster"][c["id"]] = {"trained_ranks": {}, "attribute_xp": {},
                                        "perks": [], "perk_choices": {},
                                        "gear": {}, "ult_charge": 0,
                                        "energy": 100}
    state["party"] = sorted(state["roster"], reverse=True)
    story.init(state, content["story"])
    return state


def train_cap_to(state, content, rank):
    entry = state["roster"]["captain_america"]
    boosts = content["characters"]["captain_america"]["boosts"]
    for attribute in config.ATTRIBUTES:
        while attrs.rank(entry, attribute) < rank:
            attrs.add_training_xp(boosts, entry, attribute,
                                  attrs.xp_for_rank(attrs.rank(entry, attribute),
                                                    boosts[attribute]))


def ready_state(content, party=("iron_man", "captain_america")):
    """A save one night away from the signal: Crossbones down, Cap at 2."""
    state = fresh_run(content)
    state["story_flags"]["ch2_complete"] = True
    train_cap_to(state, content, 2)
    state["party"] = list(party)
    return state


def night(content, state):
    cal.sleep(state)
    return unlocks.process_night(content, state)


# --- the gate ---

def test_signal_needs_crossbones_and_a_rounded_cap(content, arc):
    state = fresh_run(content)
    assert not unlocks.requirements_met(content, state, arc)

    state["story_flags"]["ch2_complete"] = True         # boss down, Cap at 1
    assert not unlocks.requirements_met(content, state, arc)

    train_cap_to(state, content, 2)                     # ...but only in one
    entry = state["roster"]["captain_america"]          # attribute is no good
    entry["trained_ranks"]["agility"] = 0
    assert attrs.rank(entry, "agility") == 1
    assert not unlocks.requirements_met(content, state, arc)

    entry["trained_ranks"]["agility"] = 1
    assert unlocks.requirements_met(content, state, arc)


def test_cap_at_rank_2_without_the_boss_stays_quiet(content, arc):
    state = fresh_run(content)
    train_cap_to(state, content, 2)
    assert night(content, state) == []
    assert unlocks.status(state, arc) is None


# --- the night signal ---

def test_night_signal_fires_once_with_thunder(content, arc):
    state = ready_state(content)
    messages = night(content, state)
    assert "Something strange happened in Midtown..." in messages
    assert unlocks.status(state, arc) == "searching"
    scene = unlocks.pop_scene(state)
    assert scene["sound"] == "thunder"
    assert scene["lines"][0] == "Something strange happened in Midtown..."
    assert unlocks.pop_scene(state) is None             # queue drained
    hidden = state["unlocks"][ARC_ID]["hidden"]

    assert night(content, state) == []                  # never re-fires
    assert state["unlocks"][ARC_ID]["hidden"] == hidden  # and never moves


def test_hidden_stand_is_stable_across_a_save_round_trip(content, arc, tmp_path):
    state = ready_state(content)
    night(content, state)
    save.save_game(state, 1, save_dir=str(tmp_path))
    reloaded = save.load_game(1, save_dir=str(tmp_path))
    assert reloaded["unlocks"][ARC_ID]["hidden"] == state["unlocks"][ARC_ID]["hidden"]


# --- searching the trees ---

def test_searching_costs_energy_and_time_until_the_axe_turns_up(content, arc):
    state = ready_state(content)
    night(content, state)
    hidden = state["unlocks"][ARC_ID]["hidden"]
    empty = [i for i in range(len(arc["search_groves"])) if i != hidden]

    result = unlocks.search(content, state, arc, empty[0])
    assert result["ok"] and not result.get("found")
    assert state["energy"] == config.DAILY_ENERGY - config.UNLOCK_SEARCH_ENERGY
    assert state["time_minutes"] == (config.DAY_START_MINUTES
                                     + config.UNLOCK_SEARCH_MINUTES)
    assert "stand(s) left" in result["message"]
    assert not unlocks.search(content, state, arc, empty[0])["ok"]   # once each
    assert unlocks.searched(state, arc) == [empty[0]]

    result = unlocks.search(content, state, arc, hidden)
    assert result["found"] and result["lifted"]
    assert unlocks.status(state, arc) == "carried"
    assert state["inventory"]["stormbreaker"] == 1


def test_only_the_worthy_can_pick_it_up(content, arc):
    state = ready_state(content, party=("iron_man",))    # Cap benched at home
    night(content, state)
    unlocks.pop_scene(state)                            # the 2:41 AM alert
    hidden = state["unlocks"][ARC_ID]["hidden"]

    result = unlocks.search(content, state, arc, hidden)
    assert result["found"] and result["lifted"] is False
    assert result["message"] == ("None of your heroes are mighty enough to "
                                 "get this found item.")
    assert "stormbreaker" not in state["inventory"]
    assert unlocks.status(state, arc) == "found"
    # the refusal closes the discovery cutscene, not just the message log
    scene = unlocks.pop_scene(state)
    assert scene["title"] == arc["found_scene"]["title"]
    assert scene["lines"][-1] == arc["lift_refusal"]
    assert arc["found_scene"]["lines"][-1] != arc["lift_refusal"]   # not stuck
    assert unlocks.pop_scene(state) is None      # nothing lifted, nothing else
    # the stand stays the only thing worth walking to, and retrying is free
    assert unlocks.searchable(state, arc) == [hidden]
    before = state["energy"]
    assert not unlocks.search(content, state, arc, hidden)["ok"]
    assert state["energy"] == before

    state["party"] = ["iron_man", "captain_america"]     # come back with Cap
    result = unlocks.search(content, state, arc, hidden)
    assert result["lifted"]
    assert "Captain America pulls Stormbreaker free" in result["message"]
    assert state["inventory"]["stormbreaker"] == 1
    assert unlocks.status(state, arc) == "carried"
    assert unlocks.pop_scene(state)["character"] == "captain_america"


def test_searching_blocked_without_energy(content, arc):
    state = ready_state(content)
    night(content, state)
    for entry in state["roster"].values():
        entry["energy"] = 2
    assert not unlocks.search(content, state, arc, 0)["ok"]
    assert unlocks.searched(state, arc) == []


# --- the morning after ---

def test_thor_arrives_the_next_morning_and_takes_it_back(content, arc):
    state = ready_state(content)
    night(content, state)
    unlocks.pop_scene(state)
    hidden = state["unlocks"][ARC_ID]["hidden"]
    unlocks.search(content, state, arc, hidden)
    unlocks.pop_scene(state)                            # the found scene
    unlocks.pop_scene(state)                            # Cap lifting it
    assert "thor" not in state["roster"]

    messages = night(content, state)
    assert any("Thor" in m for m in messages)
    assert unlocks.status(state, arc) == "done"
    assert "thor" in state["roster"]
    assert "thor" in state["party"]                     # room on a team of 2
    assert state["story_flags"]["thor_joined"] is True
    assert "stormbreaker" not in state["inventory"]     # he takes it back
    scene = unlocks.pop_scene(state)
    assert scene["character"] == "thor"
    assert any("Worthy" in line for line in scene["lines"])

    assert night(content, state) == []                  # and only the once


def test_full_team_gets_thor_on_the_roster_not_the_field(content, arc):
    state = ready_state(content)
    for hero_id in ("ant_man", "hulk"):
        state["roster"][hero_id] = {"trained_ranks": {}, "attribute_xp": {},
                                    "perks": [], "perk_choices": {}, "gear": {},
                                    "ult_charge": 0, "energy": 100}
    state["party"] = ["iron_man", "captain_america", "ant_man", "hulk"]
    night(content, state)
    unlocks.search(content, state, arc, state["unlocks"][ARC_ID]["hidden"])
    messages = night(content, state)
    assert "thor" in state["roster"]
    assert "thor" not in state["party"]
    assert any("swap him in" in m for m in messages)


# --- content ---

def test_thor_content_is_wired(content):
    thor = content["characters"]["thor"]
    assert thor["recruit"]["method"] == "story"     # story recruit: no bonding
    assert {a["type"] for a in thor["abilities"]} == {"basic", "special",
                                                      "ultimate"}
    assert content["items"]["stormbreaker"]["kind"] == "artifact"
    assert "thor" in content["dialogue"]


def test_stormbreaker_is_not_shop_or_gift_fodder(content):
    stormbreaker = content["items"]["stormbreaker"]
    # the shop and gift pickers both filter on kind gift|consumable
    assert stormbreaker["kind"] not in ("gift", "consumable")


def test_every_stand_of_trees_is_actually_trees(content, arc):
    zone_map = content["zones"][arc["location"]]["map"]
    for grove in arc["search_groves"]:
        for x, y in grove["tiles"]:
            assert zone_map[y][x] == "p", f"{grove['name']} tile {(x, y)}"


# --- scene plumbing in the walkable world ---

def put_player_at(scene, tile_x, tile_y):
    scene.px = tile_x * TILE + TILE // 2
    scene.py = HUD_H + tile_y * TILE + TILE // 2


def test_trees_are_searchable_on_foot(content, arc):
    from tests.test_tower_scene import FakeApp

    hub, app = HubScene(content), FakeApp(content)
    app.game_state = ready_state(content)
    state = app.game_state
    hub.area = arc["location"]
    assert hub._grove_targets(state) == []          # nothing before the signal

    night(content, state)
    unlocks.pop_scene(state)                        # the 2:41 AM alert, seen
    hidden = state["unlocks"][ARC_ID]["hidden"]
    assert len(hub._grove_targets(state)) == len(arc["search_groves"])

    # stand beside a tree of the stand that hides it and take it
    tx, ty = arc["search_groves"][hidden]["tiles"][0]
    put_player_at(hub, tx + 1, ty)
    hit = hub._nearest_interaction(state)
    assert hit[0] == "grove" and hit[1] == (ARC_ID, hidden)
    assert hit[2] == arc["search_label"]
    hub.handle_key(app, pygame.K_RETURN)
    assert state["inventory"]["stormbreaker"] == 1
    assert hub._grove_targets(state) == []          # hunt over

    # the queued scenes play out in the hub, in order
    hub._move = lambda dt, a: None                  # headless: no key polling
    hub.update(0.016, app)
    assert hub.mode == "scene"
    assert hub.scene["title"] == arc["found_scene"]["title"]
    for _ in arc["found_scene"]["lines"]:
        hub.handle_key(app, pygame.K_RETURN)
    assert hub.mode == "normal"
    hub.update(0.016, app)
    assert hub.scene["title"] == arc["lift_scene"]["title"]
    assert app.game_state.get("bond_scenes_seen", []) == []   # nothing marked


def test_ops_console_lists_the_signal(content, arc):
    from tests.test_tower_scene import FakeApp

    hub, app = HubScene(content), FakeApp(content)
    app.game_state = ready_state(content)
    night(content, app.game_state)
    hub.floor = "ops"
    put_player_at(hub, 8, 5)
    hub.handle_key(app, pygame.K_RETURN)
    labels = [i[0] for i in hub.submenu["items"]]
    assert any(l.startswith("SIGNAL - ") for l in labels)
    assert any("0/5 stands of trees" in l for l in labels)
    assert any(l.strip() == "Fly to Midtown now" for l in labels)
