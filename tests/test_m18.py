"""M18: bag slots, team rations, collapsing on the job, and day-boundary
saving."""

import pygame
import pytest

from game import config, data_loader
from game.core import calendar as cal
from game.core import energy, inventory, save
from game.core.state_machine import GameState
from game.hub import activities, story
from game.hub.tower import HubScene

ENTRY = {"trained_ranks": {}, "attribute_xp": {}, "perks": [],
         "perk_choices": {}, "gear": {}, "ult_charge": 0, "energy": 100}


@pytest.fixture(scope="module")
def content():
    pygame.init()
    return data_loader.load_all()


def state_with(party_ids, roster_ids=None):
    state = save.new_game_state()
    state["path"] = "avengers"
    for hid in (roster_ids or party_ids):
        state["roster"][hid] = dict(ENTRY)
    state["party"] = list(party_ids)
    state["inventory"] = {}
    return state


# --- bag capacity (1) ---

def test_capacity_is_four_slots_per_active_hero():
    assert inventory.capacity(state_with(["iron_man"])) == 4
    assert inventory.capacity(state_with(["iron_man", "captain_america"])) == 8
    full = state_with(["iron_man", "captain_america", "ant_man", "hulk"])
    assert inventory.capacity(full) == config.INVENTORY_SLOTS_MAX == 16
    # a benched hero carries nothing for the team
    full["party"] = ["iron_man"]
    assert inventory.capacity(full) == 4


@pytest.mark.parametrize("count,slots", [(0, 0), (1, 1), (98, 1), (99, 1),
                                         (100, 2), (198, 2), (199, 3)])
def test_a_stack_spills_into_another_slot_past_99(count, slots):
    assert inventory.slots_for(count) == slots


def test_stacks_fill_before_new_slots_are_taken():
    state = state_with(["iron_man"])                    # 4 slots
    inventory.add(state, "coffee", 150)
    assert state["inventory"]["coffee"] == 150
    assert inventory.slots_used(state) == 2             # 99 + 51
    assert inventory.slots_free(state) == 2
    # 48 finish the open stack, then two full slots' worth
    assert inventory.room_for(state, "coffee") == 48 + 2 * 99


def test_sixteen_unique_items_fit_a_full_party(content):
    state = state_with(["iron_man", "captain_america", "ant_man", "hulk"])
    ids = sorted(content["items"])[:16]
    for item_id in ids:
        assert inventory.add(state, item_id, 1)["ok"], item_id
    assert inventory.slots_used(state) == 16
    assert inventory.is_full(state)
    # ...and the 17th does not
    extra = sorted(content["items"])[16]
    result = inventory.add(state, extra, 1)
    assert not result["ok"] and result["added"] == 0
    assert extra not in state["inventory"]
    # but stacking onto something already carried still works
    assert inventory.add(state, ids[0], 1)["ok"]
    assert state["inventory"][ids[0]] == 2


def test_add_fills_what_it_can_and_reports_the_rest():
    state = state_with(["iron_man"])                    # 4 slots = 396 max
    result = inventory.add(state, "coffee", 500)
    assert result["ok"] and result["added"] == 396 and result["dropped"] == 104
    assert "bags are full" in result["message"]


def test_removing_frees_the_slot():
    state = state_with(["iron_man"])
    inventory.add(state, "coffee", 1)
    assert inventory.slots_used(state) == 1
    assert inventory.remove(state, "coffee", 1)
    assert inventory.slots_used(state) == 0
    assert "coffee" not in state["inventory"]
    assert not inventory.remove(state, "coffee", 1)     # nothing left to take


def test_benching_a_hero_never_destroys_what_is_carried():
    state = state_with(["iron_man", "captain_america"])  # 8 slots
    for item_id in ("coffee", "shawarma", "med_kit", "tech_scrap", "magnets"):
        inventory.add(state, item_id, 1)
    state["party"] = ["iron_man"]                        # down to 4 slots
    assert inventory.slots_used(state) == 5              # everything still here
    assert inventory.capacity(state) == 4
    assert inventory.slots_free(state) == 0              # ...but over capacity
    assert not inventory.add(state, "paperwork", 1)["ok"]
    assert inventory.room_for(state, "coffee") == 98     # top-up still allowed


def test_shop_refuses_a_full_bag_without_charging(content):
    state = state_with(["iron_man"])
    state["credits"] = 1000
    for item_id in ("coffee", "shawarma", "med_kit", "tech_scrap"):
        inventory.add(state, item_id, 1)
    assert inventory.is_full(state)
    vinyl = content["items"]["vintage_vinyl"]
    result = activities.buy_item(state, vinyl)
    assert not result["ok"] and "No room" in result["message"]
    assert state["credits"] == 1000                      # money untouched
    assert "vintage_vinyl" not in state["inventory"]


def test_story_artifacts_ignore_the_cap(content):
    # A quest item that bounced off a full bag would dead-end the arc.
    from game.hub import unlocks
    arc = next(a for a in content["unlocks"] if a["id"] == "thor_stormbreaker")
    state = state_with(["iron_man", "captain_america"])
    for item_id in sorted(content["items"])[:8]:
        inventory.add(state, item_id, 1)
    assert inventory.is_full(state)
    state["unlocks"] = {arc["id"]: {"status": "found", "searched": [0],
                                    "hidden": 0, "day": 1}}
    result = unlocks.search(content, state, arc, 0)
    assert result["lifted"]
    assert state["inventory"]["stormbreaker"] == 1


def test_crate_loot_is_left_behind_when_the_bag_is_full(content):
    import random
    scene, state = HubScene(content), state_with(["iron_man"])

    class FakeApp:
        pass

    app = FakeApp()
    app.game_state = state
    app.start_battle = lambda **kw: None
    app.go_to_sleep = lambda **kw: None
    scene.area = "docks"
    scene.rng = random.Random(4)            # this seed finds an item
    for item_id in ("coffee", "shawarma", "med_kit", "tech_scrap"):
        inventory.add(state, item_id, 1)
    before = dict(state["inventory"])
    scene._search_crate(app, 3, 3)
    assert state["inventory"] == before or "No room" in " ".join(scene.messages)
    assert inventory.slots_used(state) <= inventory.capacity(state)


# --- collapsing on the job (2) ---

def scout_run(content, ready=2):
    """A state parked on Case the Safehouse with `ready` points worked."""
    state = state_with(["iron_man", "captain_america"])
    story.init(state, content["story"])
    first = content["story"][0]
    state["quests"][first["id"]] = {"name": first["name"], "status": "done"}
    story.init(state, content["story"])
    quest = story.current_quest(state, content["story"])
    story.accept(state, quest)
    for i in range(ready):
        story.do_scout(state, quest, i, content["story"])
    return state, quest


def test_passing_out_on_a_scout_point_resets_the_whole_quest(content):
    # The bug this milestone exists for: the last point used to land - and
    # COMPLETE the quest - on the way down.
    state, quest = scout_run(content)
    assert story.scouted(state, quest) == [0, 1]
    for entry in state["roster"].values():
        entry["energy"] = config.SCOUT_ENERGY       # exactly enough, then out
    energy.sync(state)
    result = story.do_scout(state, quest, 2, content["story"])
    assert result["ok"] and result["reset"]
    assert "worked again" in result["message"]
    assert story.scouted(state, quest) == []                    # wiped
    assert state["quests"][quest["id"]]["status"] == "active"   # NOT done
    assert activities.should_pass_out(state)


def test_running_the_clock_out_on_a_scout_point_resets_it_too(content):
    state, quest = scout_run(content)
    state["time_minutes"] = config.DAY_END_MINUTES - config.SCOUT_MINUTES
    result = story.do_scout(state, quest, 2, content["story"])
    assert result["ok"] and result["reset"]
    assert story.scouted(state, quest) == []
    assert state["quests"][quest["id"]]["status"] == "active"


def test_a_point_worked_with_energy_to_spare_still_counts(content):
    state, quest = scout_run(content, ready=0)
    result = story.do_scout(state, quest, 0, content["story"])
    assert result["ok"] and not result.get("reset")
    assert story.scouted(state, quest) == [0]
    assert state["energy"] == config.DAILY_ENERGY - config.SCOUT_ENERGY


def test_the_quest_can_be_worked_again_after_sleeping(content):
    state, quest = scout_run(content)
    for entry in state["roster"].values():
        entry["energy"] = config.SCOUT_ENERGY
    energy.sync(state)
    story.do_scout(state, quest, 2, content["story"])
    cal.sleep(state, passed_out=True)
    energy.sync(state)
    for i in range(len(quest["scout_points"])):
        assert story.do_scout(state, quest, i, content["story"])["ok"]
    assert state["quests"][quest["id"]]["status"] == "done"     # done properly


def test_collapsing_on_a_marker_in_the_field_tells_the_player(content):
    # The reported bug, end to end: work the last marker of Case the
    # Safehouse on fumes and the quest must NOT tick over to complete.
    from tests.test_tower_scene import FakeApp, put_player_at

    scene, app = HubScene(content), FakeApp(content)
    state = app.game_state
    first = content["story"][0]
    state["quests"][first["id"]] = {"name": first["name"], "status": "done"}
    story.init(state, content["story"])
    quest = story.current_quest(state, content["story"])
    story.accept(state, quest)
    scene.area = quest["location"]
    points = quest["scout_points"]
    for i, (tx, ty) in enumerate(points):
        if i == len(points) - 1:
            for entry in state["roster"].values():
                entry["energy"] = config.SCOUT_ENERGY
            energy.sync(state)
        put_player_at(scene, tx, ty)
        scene.handle_key(app, pygame.K_RETURN)
    assert state["quests"][quest["id"]]["status"] == "active"    # not "done"
    assert story.scouted(state, quest) == []
    assert app.slept == [True]
    assert any("drops where they stand" in m for m in scene.messages)
    # every marker is standing in the zone again, including the two that
    # were worked before the collapse
    assert len(scene._scout_targets(state)) == len(points)


# --- saving is a day boundary (3) ---

def test_the_pause_card_no_longer_writes_a_save(content, monkeypatch):
    from game.core import save as save_module
    from game.ui.impel_card import TABS, ImpelCardScene

    writes = []
    monkeypatch.setattr(save_module, "save_game",
                        lambda *a, **kw: writes.append(a))

    class FakeMachine:
        state = GameState.PAUSE

        def transition(self, to):
            self.state = to

    class FakeApp:
        SAVE_SLOT = 1

    app = FakeApp()
    app.game_state = state_with(["iron_man"])
    app.machine = FakeMachine()
    card = ImpelCardScene(content)
    card.tab_index = TABS.index("Options")
    card.handle_key(app, pygame.K_RETURN)
    assert writes == []
    assert "lights-out" in card.message


def test_autosave_lands_on_the_morning_after(content, monkeypatch, tmp_path):
    from game.__main__ import App

    monkeypatch.setattr(config, "SAVE_DIR", str(tmp_path))
    app = App()
    app.new_game()
    for to in (GameState.TITLE, GameState.PATH_SELECT, GameState.HUB):
        app.machine.transition(to)
    app.game_state["time_minutes"] = 20 * 60        # a full day gets played
    app.game_state["credits"] = 250
    app.go_to_sleep()

    written = save.load_game(1, save_dir=str(tmp_path))
    assert written["day"] == 2                       # the NEXT day...
    assert written["time_minutes"] == config.DAY_START_MINUTES   # ...at 6 AM
    assert written["energy"] == config.DAILY_ENERGY  # rested
    assert written["credits"] == 250                 # the day's gains kept
