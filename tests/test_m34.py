"""M34: the opening is told to you by people, not a noticeboard.

Jarvis raises the elevator, Coulson turns out to be carrying a part of it,
Pepper raises the Quinjet on the Ops floor and unlocks the board when it
flies. One repair at a time, some parts are out in the city, and the
people doing the work say something about it.
"""

import pygame
import pytest

from game import config, data_loader
from game.core import save
from game.hub import repairs
from game.hub.tower import HubScene

from tests.test_tower_scene import FakeApp, choose, put_player_at


@pytest.fixture(scope="module")
def content():
    pygame.init()
    return data_loader.load_all()


@pytest.fixture
def day_one(content):
    """A brand-new game on the common floor: nothing fixed, nothing told."""
    scene, app = HubScene(content), FakeApp(content)
    app.game_state["repairs"] = {}
    app.game_state["story_flags"] = {}
    return scene, app


def job(content, job_id):
    return repairs.job_by_id(content, job_id)


def talk_to(scene, app, char_id):
    scene._interact_char(app, char_id)
    choose(scene, app, "Talk")


# --- the elevator arrives in conversation (1) ----------------------------

def test_jarvis_is_the_one_who_tells_you_about_the_elevator(day_one):
    scene, app = day_one
    state = app.game_state
    assert not repairs.is_active(state, job(app.content, "repair_elevator"))

    talk_to(scene, app, "jarvis")

    assert repairs.is_active(state, job(app.content, "repair_elevator"))
    assert scene.mode == "scene"
    assert scene.scene["character"] == "jarvis"


def test_coulson_says_his_usual_piece_before_jarvis_speaks(day_one):
    scene, app = day_one
    state = app.game_state
    talk_to(scene, app, "coulson")
    # No job in hand, so nothing has been handed over and no part is found.
    assert not repairs.is_active(state, job(app.content, "repair_elevator"))
    assert scene.scene["character"] == "coulson"


def test_coulson_hands_over_the_part_once_you_know_to_ask(day_one):
    scene, app = day_one
    state = app.game_state
    talk_to(scene, app, "jarvis")               # now you know
    scene.reset_modes()

    talk_to(scene, app, "coulson")

    elevator = job(app.content, "repair_elevator")
    index, _ = repairs.npc_part(state, elevator, "coulson")
    assert index is None                        # handed over
    assert repairs.parts_left(state, elevator) == 2
    assert scene.scene["character"] == "coulson"


def test_his_part_cannot_be_picked_up_off_the_floor(day_one):
    _, app = day_one
    state = app.game_state
    elevator = job(app.content, "repair_elevator")
    repairs.accept(app.content, state, elevator)
    held = next(i for i, p in enumerate(elevator["parts"]) if p.get("from"))
    result = repairs.work_part(state, elevator, held)
    assert not result["ok"]
    assert repairs.parts_left(state, elevator) == 3


def test_the_dead_elevator_looks_dead(day_one, content):
    """The tile changes, not just the message."""
    scene, app = day_one
    surface = pygame.Surface((config.WIDTH, config.HEIGHT))
    car = pygame.Rect(16 * 16, 20 + 1 * 16, 32, 16)     # both elevator tiles

    scene._draw_map(surface, app.game_state)
    broken = pygame.image.tobytes(surface.subsurface(car), "RGB")

    app.game_state["story_flags"]["elevator_repaired"] = True
    scene._draw_map(surface, app.game_state)
    fixed = pygame.image.tobytes(surface.subsurface(car), "RGB")
    assert fixed != broken


# --- Pepper, the jet, and the locked board (2) ---------------------------

def test_pepper_says_nothing_until_you_reach_her(day_one):
    _, app = day_one
    state = app.game_state
    # She is on the Ops floor, which is behind the elevator — and the jet
    # job cannot even be offered before the lift runs.
    assert repairs.triggered_by(app.content, state, "pepper_potts") is None
    state["story_flags"]["elevator_repaired"] = True
    assert repairs.triggered_by(app.content, state,
                                "pepper_potts")["id"] == "repair_quinjet"


def test_fixing_the_lift_plays_no_speech_of_its_own(day_one):
    _, app = day_one
    state = app.game_state
    elevator = job(app.content, "repair_elevator")
    repairs.accept(app.content, state, elevator)
    for index, part in enumerate(elevator["parts"]):
        if part.get("from"):
            repairs.take_npc_part(state, elevator, index)
        else:
            repairs.work_part(state, elevator, index)
    assert repairs.repair(app.content, state, elevator).get("scene") is None


def test_the_board_is_locked_and_the_keypad_never_opens_it(day_one):
    scene, app = day_one
    state = app.game_state
    put_player_at(scene, 34, 12)                    # the assignment board
    scene.handle_key(app, pygame.K_RETURN)
    assert scene.mode == "keypad"

    for code in ("0000", "1234", "9999"):
        for digit in code:
            scene.handle_key(app, getattr(pygame, f"K_{digit}"))
        assert scene.keypad == code
        scene.handle_key(app, pygame.K_RETURN)
        assert scene.keypad_message == "ACCESS DENIED"
        assert scene.keypad == ""
    assert not state.get("story_flags", {}).get("board_unlocked")
    scene.handle_key(app, pygame.K_ESCAPE)
    assert scene.mode == "normal"


def test_the_jet_flying_is_what_opens_the_board(day_one):
    scene, app = day_one
    state = app.game_state
    state["story_flags"]["elevator_repaired"] = True
    quinjet = job(app.content, "repair_quinjet")
    repairs.accept(app.content, state, quinjet)
    for index in range(len(quinjet["parts"])):
        repairs.work_part(state, quinjet, index)
    result = repairs.repair(app.content, state, quinjet)

    assert state["story_flags"]["board_unlocked"] is True
    assert result["scene"]["character"] == "pepper_potts"
    put_player_at(scene, 34, 12)
    scene.handle_key(app, pygame.K_RETURN)
    assert scene.mode == "submenu"                  # the board opens now


def test_both_room_repairs_go_up_together_but_only_one_can_be_taken(content):
    state = save.new_game_state()
    state["story_flags"]["board_unlocked"] = True
    posted = {j["id"] for j in repairs.posted(content, state)}
    assert posted == {"repair_training", "repair_med_bay"}

    repairs.accept(content, state, job(content, "repair_med_bay"))
    refused = repairs.accept(content, state, job(content, "repair_training"))
    assert not refused["ok"] and "One thing at a time" in refused["message"]


# --- parts out in the city (3) -------------------------------------------

def test_the_room_repairs_each_need_a_trip_out_of_the_tower(content):
    zones = set(content["zones"])
    for job_id, expected in (("repair_med_bay", "docks"),
                             ("repair_training", "midtown")):
        areas = {p.get("area") for p in job(content, job_id)["parts"]}
        assert expected in areas
        assert areas & zones == {expected}


def test_a_part_in_a_zone_shows_up_there_and_not_in_the_tower(content):
    scene, app = HubScene(content), FakeApp(content)
    state = app.game_state
    state["repairs"] = {}
    state["story_flags"] = {"board_unlocked": True}
    repairs.accept(content, state, job(content, "repair_training"))

    # The Midtown piece is in the open; the two tower pieces are hidden and
    # therefore unmarked, so the only marker in the game is out in the city.
    scene._switch_floor("training")
    assert scene._repair_targets(state) == []
    scene.area = "midtown"
    assert len(scene._repair_targets(state)) == 1
    scene.area = "docks"
    assert scene._repair_targets(state) == []


# --- the team says something (4) -----------------------------------------

def test_hauling_a_HEAVY_part_gets_a_line_from_the_leader(day_one):
    scene, app = day_one
    state = app.game_state
    state["story_flags"]["elevator_repaired"] = True
    quinjet = job(app.content, "repair_quinjet")
    repairs.accept(app.content, state, quinjet)
    heavy = next(i for i, p in enumerate(quinjet["parts"])
                 if p.get("heavy") and p.get("area") == "ops")
    scene._switch_floor("ops")

    scene._salvage_part(app, quinjet["id"], heavy)

    assert scene.mode == "scene"
    assert scene.scene["character"] == state["party"][0]


def test_a_pocket_sized_part_passes_without_comment(day_one):
    scene, app = day_one
    state = app.game_state
    elevator = job(app.content, "repair_elevator")
    repairs.accept(app.content, state, elevator)
    index = repairs.parts_on(state, elevator, "common")[0][0]

    scene._salvage_part(app, elevator["id"], index)

    assert scene.mode == "normal"               # no speech for a capacitor


def test_mining_reads_in_the_leaders_voice(content):
    scene, app = HubScene(content), FakeApp(content)
    state = app.game_state
    scene.area = "docks"

    class Rolls:
        def __init__(self):
            self.values = [1.0, 0.0]        # no trap, first material

        def random(self):
            return self.values.pop(0)

    scene.rng = Rolls()
    tx, ty, _, _ = scene._ore_here(state)[0]
    scene._mine_node(app, tx, ty)

    leader_name = content["characters"][state["party"][0]]["name"]
    line = scene.messages[-1]
    assert leader_name.split()[0] in line or line.startswith('"')
    assert "ISO-8" in line


def test_every_hero_has_their_own_lines(content):
    for pool in ("part_lift", "mining"):
        lines = content["flavor"][pool]
        assert "default" in lines
        for char in content["characters"].values():
            if char["recruit"]["method"] == "npc":
                continue
            assert char["id"] in lines, f"{char['id']} has no {pool} line"


# --- old saves keep their board (5) --------------------------------------

def test_a_save_that_already_fixed_the_jet_keeps_an_open_board(content):
    # board_unlocked was hung on a job every live save had finished; without
    # the backfill their board is locked behind a keypad nothing opens.
    old = save.new_game_state()
    old.pop("repairs")
    old["day"] = 10
    repairs.migrate(content, old)
    assert old["story_flags"]["quinjet_repaired"] is True
    assert old["story_flags"]["board_unlocked"] is True


def test_a_new_game_does_not_get_the_board_for_free(content):
    fresh_state = save.new_game_state()
    repairs.migrate(content, fresh_state)
    assert not fresh_state["story_flags"].get("board_unlocked")


# --- talking is never refused (6) ----------------------------------------

def test_talk_stays_available_after_the_days_points_are_spent(content):
    scene, app = HubScene(content), FakeApp(content)
    state = app.game_state
    from game.social import bonds
    bonds.talk(state, "jarvis")                     # today's points, spent

    scene._interact_char(app, "jarvis")
    talk_row = next(i for i in scene.submenu["items"] if i[0] == "Talk")
    assert talk_row[1] is False                     # not greyed out

    choose(scene, app, "Talk")
    assert scene.mode == "scene"                    # they still say something
