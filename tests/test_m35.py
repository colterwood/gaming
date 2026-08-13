"""M35: the parts are actually hidden.

A piece is either lying in the open (marked), stashed in furniture / a
crate / an ore seam (no marker — you search things), in someone's pocket,
or in the wreckage of a fight. Every spot is fixed: the same playthrough
twice runs the same hunt. Only HEAVY pieces cost energy.
"""

import pygame
import pytest

from game import config, data_loader
from game.core import save
from game.hub import activities, repairs
from game.hub.tower import SEARCHABLE_FURNITURE, HubScene

from tests.test_tower_scene import FakeApp, put_player_at


@pytest.fixture(scope="module")
def content():
    pygame.init()
    return data_loader.load_all()


@pytest.fixture
def hunting(content):
    """The elevator job in hand, standing on the common floor."""
    scene, app = HubScene(content), FakeApp(content)
    app.game_state["repairs"] = {}
    app.game_state["story_flags"] = {}
    repairs.accept(content, app.game_state, job(content, "repair_elevator"))
    return scene, app


def job(content, job_id):
    return repairs.job_by_id(content, job_id)


class Always:
    def random(self):
        return 0.0

    def randint(self, a, b):
        return a

    def randrange(self, n):
        return 0


class Never:
    def random(self):
        return 0.99

    def randint(self, a, b):
        return a

    def randrange(self, n):
        return 0


# --- the shape of each hunt (1) ------------------------------------------

EXPECTED = {
    # id: (parts, plain, hidden, npc, battle, mine, heavy)
    "repair_elevator": (3, 1, 1, 1, 0, 0, 0),
    "repair_quinjet": (4, 2, 2, 0, 0, 0, 3),
    "repair_training": (3, 1, 2, 0, 0, 0, 1),
    "repair_med_bay": (4, 1, 3, 0, 0, 0, 0),
    "repair_tech_lab": (6, 1, 2, 1, 2, 0, 0),
    # M36: the regulator moved off its fixed docks seam onto a roll against
    # every seam in the world, so the hidden count drops by one.
    "repair_pym_lab": (4, 0, 1, 1, 1, 1, 0),
}


@pytest.mark.parametrize("job_id,expected", sorted(EXPECTED.items()))
def test_each_repair_has_the_hunt_it_was_designed_with(content, job_id,
                                                       expected):
    parts = job(content, job_id)["parts"]
    kinds = [repairs.part_kind(p) for p in parts]
    actual = (len(parts), kinds.count("plain"), kinds.count("hidden"),
              kinds.count("npc"), kinds.count("battle"), kinds.count("mine"),
              sum(1 for p in parts if p.get("heavy")))
    assert actual == expected


ENERGY_PRICE = {                    # 5 EN per heavy piece, and nothing else
    "repair_elevator": 0,
    "repair_quinjet": 15,
    "repair_training": 5,
    "repair_med_bay": 0,
    "repair_tech_lab": 0,
    "repair_pym_lab": 0,
}


@pytest.mark.parametrize("job_id,price", sorted(ENERGY_PRICE.items()))
def test_a_repair_costs_exactly_its_heavy_parts(content, job_id, price):
    """Nothing else in the system touches energy: searching is free,
    handing over is free, and FITTING the parts is free. Carrying is the
    only thing that tires anybody out."""
    state = FakeApp(content).game_state          # a real party to tire out
    state["repairs"] = {}
    state["story_flags"] = {"board_unlocked": True, "elevator_repaired": True,
                            "pym_lab_unlocked": True}
    state["quests"]["ch1_siege"] = {"name": "Siege", "status": "done"}
    spec = job(content, job_id)
    state["repairs"][job_id] = {"status": "active", "found": []}
    before = state["energy"]

    for index, part in enumerate(spec["parts"]):
        kind = repairs.part_kind(part)
        if kind == "npc":
            repairs.take_npc_part(state, spec, index)
        elif kind == "battle":
            state["repairs"][job_id]["found"].append(index)
        else:
            repairs.work_part(state, spec, index)
    repairs.repair(content, state, spec)

    assert before - state["energy"] == price


def test_the_spots_never_move(content):
    """No RNG anywhere in where a piece is: the same game twice is the same
    hunt, which is what makes learning the tower worth anything."""
    for job_spec in content["repairs"]:
        for part in job_spec["parts"]:
            if repairs.part_kind(part) in ("plain", "hidden"):
                assert isinstance(part["x"], int)
                assert isinstance(part["y"], int)


# --- hidden means hidden (2) ---------------------------------------------

def test_a_hidden_part_gets_no_marker(hunting):
    scene, app = hunting
    state = app.game_state
    hidden = [p for p in job(app.content, "repair_elevator")["parts"]
              if p.get("hidden")]
    assert hidden
    marked = {(x, y) for _, x, y in
              repairs.parts_on(state, job(app.content, "repair_elevator"),
                               "common")}
    for part in hidden:
        assert (part["x"], part["y"]) not in marked


def test_furniture_is_searchable_whether_or_not_a_hunt_is_on(content):
    """M35 made furniture live only during a repair hunt, which taught the
    player that a couch is scenery and then expected them to start turning
    couches over. M36: always searchable, almost always empty."""
    scene, app = HubScene(content), FakeApp(content)
    state = app.game_state
    state["repairs"] = {}
    idle = scene._furniture_here(state)
    assert len(idle) > 3                            # couches, tables, plants
    repairs.accept(content, state, job(content, "repair_elevator"))
    assert scene._furniture_here(state) == idle     # the same things, always


def test_a_searched_thing_can_be_searched_again_for_a_new_job(content):
    """M36 bug fix (notes 8 and 23). Furniture dims for the day once
    searched, and a hidden part is only findable while its own job is in
    hand — so turning over the Ops planter during the elevator hunt made
    the Training Floor part inside it unreachable until tomorrow, silently."""
    scene, app = HubScene(content), FakeApp(content)
    state = app.game_state
    state["repairs"] = {}
    state["story_flags"] = {"board_unlocked": True}
    training = job(content, "repair_training")
    planter = next(p for p in training["parts"]
                   if repairs.part_kind(p) == "hidden" and p["area"] == "ops")

    # rummage it today, for no reason, before the job exists
    activities.mark_spot_searched(state, "ops", planter["x"], planter["y"])
    assert activities.spot_searched(state, "ops", planter["x"], planter["y"])

    repairs.accept(content, state, training)

    assert not activities.spot_searched(state, "ops",
                                        planter["x"], planter["y"])
    scene.floor = "ops"
    assert any((tx, ty) == (planter["x"], planter["y"])
               for tx, ty, *_ in scene._furniture_here(state))


def test_searching_the_wrong_thing_costs_minutes_and_finds_nothing(hunting):
    scene, app = hunting
    state = app.game_state
    before_en, before_clock = state["energy"], state["time_minutes"]
    empty = next((tx, ty) for tx, ty, _n, _x, _y in scene._furniture_here(state)
                 if repairs.hidden_at(app.content, state, "common",
                                      tx, ty)[0] is None)

    scene._search_furniture(app, *empty)

    assert state["energy"] == before_en             # attention, not attrition
    assert state["time_minutes"] == before_clock + config.FURNITURE_SEARCH_MINUTES
    assert repairs.parts_left(state, job(app.content, "repair_elevator")) == 3
    assert activities.spot_searched(state, "common", *empty)


def test_searching_the_right_thing_turns_up_the_part(hunting):
    scene, app = hunting
    state = app.game_state
    elevator = job(app.content, "repair_elevator")
    spot = next(p for p in elevator["parts"] if p.get("hidden"))

    scene._search_furniture(app, spot["x"], spot["y"])

    assert repairs.parts_left(state, elevator) == 2


def test_a_searched_spot_stays_searched_for_the_day(hunting):
    scene, app = hunting
    state = app.game_state
    tx, ty = scene._furniture_here(state)[0][:2]
    scene._search_furniture(app, tx, ty)
    assert (tx, ty) not in [(f[0], f[1]) for f in scene._furniture_here(state)]


def test_the_mats_are_rolled_back_in_one_go(content):
    """The training floor is ~140 mat tiles; searching them one at a time
    would be a punishment, not a hunt."""
    scene, app = HubScene(content), FakeApp(content)
    state = app.game_state
    state["repairs"] = {}
    state["story_flags"] = {"board_unlocked": True}
    repairs.accept(content, state, job(content, "repair_training"))
    scene._switch_floor("training")
    mats = [(tx, ty) for tx, ty, name, _x, _y in scene._furniture_here(state)
            if name == "mats"]
    assert len(mats) > 50                           # a whole field of them

    scene._search_furniture(app, *mats[0])          # one search does it

    assert repairs.parts_left(state, job(content, "repair_training")) == 2
    assert not [f for f in scene._furniture_here(state) if f[2] == "mats"]


def test_a_part_in_a_dock_box_comes_out_of_the_box(content):
    scene, app = HubScene(content), FakeApp(content)
    state = app.game_state
    state["repairs"] = {}
    state["story_flags"] = {"board_unlocked": True}
    repairs.accept(content, state, job(content, "repair_med_bay"))
    scene.area = "docks"
    scene.rng = Never()                             # no trap, no loot
    part = next(p for p in job(content, "repair_med_bay")["parts"]
                if p.get("area") == "docks")

    scene._search_crate(app, part["x"], part["y"])

    assert repairs.parts_left(state, job(content, "repair_med_bay")) == 3


def test_a_part_in_a_seam_comes_out_of_any_seam(content):
    """M36: the Pym regulator is no longer pinned to one named tile in the
    docks — it rolls out of whatever seam the player happens to crack."""
    pym = job(content, "repair_pym_lab")
    state = save.new_game_state()
    state["story_flags"] = {"board_unlocked": True, "pym_lab_unlocked": True}
    repairs.accept(content, state, pym)

    assert repairs.mine_drop(content, state, Never()) == []     # unlucky swing
    assert repairs.parts_left(state, pym) == 4

    messages = repairs.mine_drop(content, state, Always())
    assert len(messages) == 1
    assert repairs.parts_left(state, pym) == 3
    # ...and it only comes out of the rock once, however much you mine.
    assert repairs.mine_drop(content, state, Always()) == []


# --- pieces that come out of a fight (3) ---------------------------------

def test_the_tech_lab_pieces_drop_from_won_fights(content):
    state = save.new_game_state()
    state["story_flags"] = {"board_unlocked": True}
    state["quests"]["ch1_siege"] = {"name": "Siege", "status": "done"}
    tech = job(content, "repair_tech_lab")
    repairs.accept(content, state, tech)

    first = repairs.battle_drop(content, state, ["iron_man"], Always())
    assert len(first) == 1                      # one piece per fight, at most
    second = repairs.battle_drop(content, state, ["iron_man"], Always())
    assert len(second) == 1
    # Both battle parts are in; a third win yields nothing more.
    assert repairs.battle_drop(content, state, ["iron_man"], Always()) == []


def test_an_unlucky_fight_drops_nothing(content):
    state = save.new_game_state()
    state["story_flags"] = {"board_unlocked": True}
    state["quests"]["ch1_siege"] = {"name": "Siege", "status": "done"}
    repairs.accept(content, state, job(content, "repair_tech_lab"))
    assert repairs.battle_drop(content, state, ["iron_man"], Never()) == []


def test_nothing_drops_before_the_job_is_taken(content):
    state = save.new_game_state()
    state["story_flags"] = {"board_unlocked": True}
    state["quests"]["ch1_siege"] = {"name": "Siege", "status": "done"}
    assert repairs.battle_drop(content, state, ["iron_man"], Always()) == []


def test_the_pym_coupling_needs_scott_in_the_party(content):
    state = save.new_game_state()
    state["story_flags"] = {"board_unlocked": True, "pym_lab_unlocked": True}
    pym = job(content, "repair_pym_lab")
    repairs.accept(content, state, pym)

    # A certainty with him, and it never rolls without him.
    assert repairs.battle_drop(content, state, ["iron_man"], Always()) == []
    assert repairs.battle_drop(content, state,
                               ["iron_man", "ant_man"], Never())
    assert repairs.parts_left(state, pym) == 3


# --- the last piece is held back (4) -------------------------------------

def test_jarvis_keeps_the_sixth_until_five_are_in(content):
    state = save.new_game_state()
    state["story_flags"] = {"board_unlocked": True}
    state["quests"]["ch1_siege"] = {"name": "Siege", "status": "done"}
    tech = job(content, "repair_tech_lab")
    repairs.accept(content, state, tech)

    assert repairs.npc_part(state, tech, "jarvis") == (None, None)
    for index, part in enumerate(tech["parts"]):        # everything else
        if repairs.part_kind(part) != "npc":
            state["repairs"][tech["id"]]["found"].append(index)
    index, _ = repairs.npc_part(state, tech, "jarvis")
    assert index is not None
    assert repairs.take_npc_part(state, tech, index)["ok"]
    assert repairs.can_repair(state, tech)
