"""M29: the tower starts wrecked. Repairs are posted on the board, accepted
there, and worked in person — find the parts, then fit them at the broken
thing itself. The elevator opens the tower, the Quinjet opens the missions,
and old saves keep the rooms they already had.
"""

import pygame
import pytest

from game import config, data_loader
from game.core import save
from game.hub import repairs, story
from game.hub.tower import FLOORS, HubScene

from tests.test_tower_scene import FakeApp, choose, put_player_at


@pytest.fixture(scope="module")
def content():
    pygame.init()
    return data_loader.load_all()


@pytest.fixture
def fresh(content):
    """A brand-new game: nothing repaired, nowhere to go but the common
    floor."""
    scene, app = HubScene(content), FakeApp(content)
    app.game_state["repairs"] = {}
    app.game_state["story_flags"] = {}
    return scene, app


def job(content, job_id):
    return repairs.job_by_id(content, job_id)


def work_every_part(state, content, job_id):
    for index in range(len(job(content, job_id)["parts"])):
        repairs.work_part(state, job(content, job_id), index)


# --- the tower starts broken (1) -----------------------------------------

def test_a_new_game_has_a_wrecked_tower(content):
    state = save.new_game_state()
    assert state["repairs"] == {}
    assert repairs.outstanding(content, state) == content["repairs"]
    assert not repairs.all_done(content, state)


def test_only_the_elevator_repair_is_posted_on_day_one(content):
    state = save.new_game_state()
    assert [j["id"] for j in repairs.posted(content, state)] == \
        ["repair_elevator"]


def test_the_dead_elevator_offers_the_work_instead_of_floors(fresh):
    scene, app = fresh
    put_player_at(scene, 17, 2)                     # beside the elevator
    scene.handle_key(app, pygame.K_RETURN)
    labels = [i[0] for i in scene.submenu["items"]]
    assert labels[0] == "Fix the Service Elevator"
    assert not any("Training Floor" in l for l in labels)


def test_no_floor_above_the_common_one_is_reachable(fresh):
    scene, app = fresh
    for floor in ("ops", "training", "med_bay", "tech_lab", "pym_lab"):
        locked, why = scene.floor_locked(app.game_state, floor)
        assert locked, floor
        assert why


# --- accept at the board, work it in person (2) --------------------------

def test_the_board_posts_the_repair_and_accepting_puts_it_in_hand(fresh):
    scene, app = fresh
    state = app.game_state
    put_player_at(scene, 34, 12)                    # the assignment board
    scene.handle_key(app, pygame.K_RETURN)
    choose(scene, app, "REPAIR - Fix the Service Elevator")
    assert repairs.is_active(state, job(app.content, "repair_elevator"))


def test_parts_only_appear_once_the_job_is_taken(fresh):
    scene, app = fresh
    state = app.game_state
    assert scene._repair_targets(state) == []
    repairs.accept(state, job(app.content, "repair_elevator"))
    assert len(scene._repair_targets(state)) == 3   # all three on this floor


def test_salvaging_a_part_costs_energy_and_time(fresh):
    scene, app = fresh
    state = app.game_state
    repairs.accept(state, job(app.content, "repair_elevator"))
    before_en = state["energy"]
    before_clock = state["time_minutes"]
    result = repairs.work_part(state, job(app.content, "repair_elevator"), 0)
    assert result["ok"]
    assert state["energy"] == before_en - config.REPAIR_PART_ENERGY
    assert state["time_minutes"] == before_clock + config.REPAIR_PART_MINUTES
    assert repairs.parts_left(state, job(app.content, "repair_elevator")) == 2


def test_the_same_part_cannot_be_salvaged_twice(fresh):
    _, app = fresh
    state = app.game_state
    elevator = job(app.content, "repair_elevator")
    repairs.accept(state, elevator)
    repairs.work_part(state, elevator, 0)
    again = repairs.work_part(state, elevator, 0)
    assert not again["ok"]
    assert repairs.parts_left(state, elevator) == 2


def test_the_repair_is_refused_until_every_part_is_in_hand(fresh):
    _, app = fresh
    state = app.game_state
    elevator = job(app.content, "repair_elevator")
    repairs.accept(state, elevator)
    repairs.work_part(state, elevator, 0)
    result = repairs.repair(app.content, state, elevator)
    assert not result["ok"]
    assert "short" in result["message"]
    assert not state["story_flags"].get("elevator_repaired")


def test_fixing_the_elevator_opens_the_tower_and_pays(fresh):
    _, app = fresh
    state = app.game_state
    elevator = job(app.content, "repair_elevator")
    repairs.accept(state, elevator)
    work_every_part(state, app.content, "repair_elevator")
    credits_before = state["credits"]
    result = repairs.repair(app.content, state, elevator)

    assert result["ok"]
    assert state["story_flags"]["elevator_repaired"] is True
    assert state["credits"] == credits_before + elevator["credits"]
    assert repairs.is_done(state, elevator)
    # ...and Pepper is waiting on the Ops floor with the next problem.
    assert result["scene"]["character"] == "pepper_potts"


def test_a_finished_repair_never_posts_again(fresh):
    _, app = fresh
    state = app.game_state
    elevator = job(app.content, "repair_elevator")
    repairs.accept(state, elevator)
    work_every_part(state, app.content, "repair_elevator")
    repairs.repair(app.content, state, elevator)
    posted = [j["id"] for j in repairs.posted(app.content, state)]
    assert "repair_elevator" not in posted
    assert "repair_quinjet" in posted       # ...but the next one does


# --- the chain, in the order the player meets it (3) ---------------------

def test_repairs_unlock_in_order(fresh):
    _, app = fresh
    state = app.game_state
    seen = []
    for _ in range(3):
        posted = repairs.posted(app.content, state)
        assert posted, "the chain stalled"
        head = posted[0]
        seen.append(head["id"])
        repairs.accept(state, head)
        work_every_part(state, app.content, head["id"])
        repairs.repair(app.content, state, head)
    assert seen == ["repair_elevator", "repair_quinjet", "repair_training"]


def test_the_ops_console_offers_nothing_while_the_jet_is_grounded(fresh):
    scene, app = fresh
    state = app.game_state
    state["story_flags"]["elevator_repaired"] = True
    scene._switch_floor("ops")
    put_player_at(scene, 8, 4)                      # the ops console
    scene.handle_key(app, pygame.K_RETURN)
    labels = [i[0] for i in scene.submenu["items"]]
    assert labels[0] == "The Quinjet is grounded."
    assert not any("ACCEPT MISSION" in l for l in labels)
    # The first mission must NOT be accepted — its deadline would be
    # running on a team with no way to reach the docks.
    quest = story.current_quest(state, app.content["story"])
    assert not story.is_accepted(state, quest)


def test_missions_come_back_once_the_jet_flies(fresh):
    scene, app = fresh
    state = app.game_state
    state["story_flags"]["elevator_repaired"] = True
    state["story_flags"]["quinjet_repaired"] = True
    scene._switch_floor("ops")
    put_player_at(scene, 8, 4)
    scene.handle_key(app, pygame.K_RETURN)
    labels = [i[0] for i in scene.submenu["items"]]
    assert any("ACCEPT MISSION" in l for l in labels)


def test_the_elevator_will_not_fly_a_grounded_quinjet(fresh):
    scene, app = fresh
    app.game_state["story_flags"]["elevator_repaired"] = True
    put_player_at(scene, 17, 2)
    scene.handle_key(app, pygame.K_RETURN)
    rows = scene.submenu["items"]
    grounded = [r for r in rows if r[0] == "Quinjet: grounded"]
    assert grounded and grounded[0][1] is True      # disabled
    assert not any(r[0].startswith("Quinjet: The Docks") for r in rows)


def test_the_rack_offers_repairs_not_training_while_it_is_wrecked(fresh):
    scene, app = fresh
    state = app.game_state
    state["story_flags"]["elevator_repaired"] = True
    scene._switch_floor("training")
    put_player_at(scene, 36, 6)                     # the rack
    scene.handle_key(app, pygame.K_RETURN)
    assert scene.submenu["title"] == "Repair"
    assert scene.submenu["items"][0][0] == "Restore the Training Floor"


def test_the_pym_lab_stays_sealed_until_lang_hands_over_the_code(fresh):
    scene, app = fresh
    state = app.game_state
    state["story_flags"]["elevator_repaired"] = True
    locked, why = scene.floor_locked(state, "pym_lab")
    assert locked and "code" in why
    state["story_flags"]["pym_lab_unlocked"] = True
    assert scene.floor_locked(state, "pym_lab")[0] is False


def test_breaking_lang_out_is_what_hands_over_the_code(content):
    quest = next(q for q in content["story"] if q["id"] == "ch1_break_out_lang")
    assert quest["flags"]["pym_lab_unlocked"] is True


# --- old saves keep the rooms they had (4) -------------------------------

def test_a_pre_m29_save_wakes_up_in_a_working_tower(content):
    old = save.new_game_state()
    old.pop("repairs")                              # as an older build wrote it
    old["day"] = 10
    repairs.migrate(content, old)
    flags = old["story_flags"]
    assert flags["elevator_repaired"] and flags["quinjet_repaired"]
    assert flags["training_repaired"]
    # ...but the rooms that build never had are still work to do.
    assert [j["id"] for j in repairs.outstanding(content, old)] == \
        ["repair_med_bay", "repair_tech_lab", "repair_pym_lab"]


def test_migration_leaves_a_game_started_under_m29_alone(content):
    fresh_state = save.new_game_state()
    repairs.migrate(content, fresh_state)
    assert fresh_state["repairs"] == {}
    assert not fresh_state["story_flags"]


def test_the_tower_is_only_repaired_when_every_room_is(content):
    state = save.new_game_state()
    for job_id in ("repair_elevator", "repair_quinjet", "repair_training",
                   "repair_med_bay", "repair_tech_lab"):
        state["repairs"][job_id] = {"status": "done", "found": []}
    assert not repairs.all_done(content, state)
    state["repairs"]["repair_pym_lab"] = {"status": "done", "found": []}
    assert repairs.all_done(content, state)


# --- content sanity (5) ---------------------------------------------------

def test_every_repair_station_exists_on_its_floor(content):
    from game.hub.tower import STATION_KINDS

    for job in content["repairs"]:
        rows = FLOORS[job["floor"]]["map"]
        kinds = {STATION_KINDS.get(ch) for row in rows for ch in row}
        assert job["station"] in kinds, (
            f"{job['id']} is fitted at a '{job['station']}' station, and "
            f"there isn't one on the {job['floor']} floor")


def test_every_part_lies_on_a_tile_you_can_stand_next_to(content):
    from game.hub.tower import WALKABLE

    for job in content["repairs"]:
        for floor, x, y in job["parts"]:
            rows = FLOORS[floor]["map"]
            neighbours = [rows[y][x]] + [
                rows[y + dy][x + dx] for dx, dy in
                ((1, 0), (-1, 0), (0, 1), (0, -1))
                if 0 <= y + dy < len(rows) and 0 <= x + dx < len(rows[0])]
            assert any(ch in WALKABLE for ch in neighbours), (
                f"{job['id']}: the part at {floor} [{x}, {y}] is walled in")


def test_no_repair_is_gated_on_a_dice_roll_or_a_bond(content):
    # Repairs are the critical path to Ch. 3-4 — a posting chance or a
    # relationship gate could stall the campaign outright.
    for job in content["repairs"]:
        assert "posting" not in job
        assert set(job.get("requires", {})) <= {"flags", "quests"}


def test_the_loader_knows_every_station_the_hub_draws(content):
    from game.hub.tower import STATION_KINDS

    assert set(data_loader.REPAIR_STATIONS) <= set(STATION_KINDS.values())
