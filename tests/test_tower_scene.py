"""M8: walkable tower scene plumbing — interactions route to the right
logic, characters are placed per story state. Headless (no display)."""

import pygame
import pytest

from game import config, data_loader
from game.core import energy, save
from game.core.state_machine import GameState
from game.hub import activities, story
from game.hub.tower import FLOORS, HUD_H, TILE, HubScene


class FakeMachine:
    def __init__(self):
        self.transitions = []
        self.state = GameState.HUB

    def transition(self, to):
        self.transitions.append(to)
        self.state = to


class FakeApp:
    def __init__(self, content):
        self.content = content
        self.game_state = save.new_game_state()
        self.game_state["path"] = "avengers"
        for c in content["characters"].values():
            if c["recruit"]["method"] == "starter":
                self.game_state["roster"][c["id"]] = {
                    "trained_ranks": {}, "attribute_xp": {}, "perks": [],
                    "perk_choices": {}, "gear": {}, "ult_charge": 0,
                    "energy": 100, "unspent_xp": 0}
        self.game_state["party"] = sorted(self.game_state["roster"], reverse=True)
        story.init(self.game_state, content["story"])
        self.machine = FakeMachine()
        self.slept = []
        self.battles = []

    def go_to_sleep(self, passed_out=False):
        self.slept.append(passed_out)

    def start_battle(self, enemy_ids=None, quest=None, ambush=False):
        self.battles.append((tuple(enemy_ids), quest["id"] if quest else None))
        self.machine.transition(GameState.BATTLE)   # like the real App


@pytest.fixture(scope="module")
def content():
    pygame.init()
    return data_loader.load_all()


def scene_with_app(content):
    return HubScene(content), FakeApp(content)


def put_player_at(scene, tile_x, tile_y):
    scene.px = tile_x * TILE + TILE // 2
    scene.py = HUD_H + tile_y * TILE + TILE // 2


def choose(scene, app, label_prefix):
    items = scene.submenu["items"]
    for i, (label, disabled, cb) in enumerate(items):
        if label.startswith(label_prefix):
            scene.submenu["index"] = i
            scene._submenu_key(app, pygame.K_RETURN)
            return
    raise AssertionError(f"no submenu item starting with {label_prefix!r}: "
                         f"{[i[0] for i in items]}")


def test_talk_to_jarvis_gives_bond(content):
    scene, app = scene_with_app(content)
    put_player_at(scene, 4, 7)                  # next to Jarvis (4, 6)
    hit = scene._nearest_interaction(app.game_state)
    assert hit == ("char", "jarvis", "Edwin Jarvis")
    scene.handle_key(app, pygame.K_RETURN)
    assert scene.mode == "submenu"
    choose(scene, app, "Talk")
    assert app.game_state["bonds"]["jarvis"]["points"] == 15
    # M11: the talk line shows in a dialogue box (transient scene)
    assert scene.mode == "scene"
    assert scene.scene["lines"][0] in content["dialogue"]["jarvis"]["0"]
    scene.handle_key(app, pygame.K_RETURN)      # dismiss the line
    assert scene.mode == "normal"
    assert app.game_state.get("bond_scenes_seen", []) == []   # nothing marked


def test_gift_jarvis_loved(content):
    scene, app = scene_with_app(content)
    app.game_state["inventory"]["double_espresso"] = 1
    put_player_at(scene, 4, 7)
    scene.handle_key(app, pygame.K_RETURN)
    choose(scene, app, "Give Gift")
    assert scene.mode == "submenu"              # gift picker
    choose(scene, app, "Double Espresso")
    assert app.game_state["bonds"]["jarvis"]["points"] == 80
    assert "double_espresso" not in app.game_state["inventory"]


def test_benched_starter_chats_no_bonds(content):
    scene, app = scene_with_app(content)
    app.game_state["party"] = ["captain_america"]     # iron man benched, idle
    put_player_at(scene, 8, 14)                       # near the idle spot (8, 15)
    hit = scene._nearest_interaction(app.game_state)
    assert hit[1] == "iron_man"
    scene.handle_key(app, pygame.K_RETURN)
    assert scene.mode == "submenu"
    choose(scene, app, "Chat")
    assert scene.mode == "scene"                      # a flavor line, no points
    assert scene.scene["lines"][0] in content["dialogue"]["iron_man"]["0"]
    assert "iron_man" not in app.game_state.get("bonds", {})


def test_party_members_are_not_placed_in_world(content):
    scene, app = scene_with_app(content)
    ids = [cid for cid, _, _ in scene._characters_here(app.game_state)]
    assert "iron_man" not in ids and "captain_america" not in ids   # they follow you
    app.game_state["party"] = ["captain_america"]
    ids = [cid for cid, _, _ in scene._characters_here(app.game_state)]
    assert "iron_man" in ids                                        # benched now


def test_mission_flow_accept_fly_and_engage(content):
    scene, app = scene_with_app(content)
    state = app.game_state
    # M13: the docks are empty before the mission is accepted
    scene.area = "docks"
    assert scene._mission_target(state) is None
    scene.area = "tower"
    # Ops console OFFERS the mission; accept to start the clock
    scene.floor = "ops"
    put_player_at(scene, 8, 5)
    scene.handle_key(app, pygame.K_RETURN)
    labels = [i[0] for i in scene.submenu["items"]]
    assert any(l.startswith("NEW - ") for l in labels)
    assert any("once accepted" in l for l in labels)
    assert not any("Fly to" in l for l in labels)       # no flight offered yet
    choose(scene, app, "  ACCEPT MISSION")
    labels = [i[0] for i in scene.submenu["items"]]     # menu reopened
    assert any("Where: Hudson Docks" in l for l in labels)
    assert any("Deadline: 3 day(s) left" in l for l in labels)
    # cursor lands on an actionable row, not a disabled info line
    label, disabled, cb = scene.submenu["items"][scene.submenu["index"]]
    assert not disabled and cb is not None and "Fly to" in label
    choose(scene, app, "  Fly to Hudson Docks")
    assert scene.area == "docks"
    # walk to the target squad and engage
    zone = content["zones"]["docks"]
    put_player_at(scene, zone["target_spot"][0], zone["target_spot"][1] + 1)
    hit = scene._nearest_interaction(state)
    assert hit[0] == "target"
    scene.handle_key(app, pygame.K_RETURN)
    assert app.battles == [(("hydra_grunt", "hydra_grunt", "hydra_grunt"),
                            "ch1_shattered_shield")]
    assert state["energy"] == config.DAILY_ENERGY - config.MISSION_ENERGY


def test_locked_mission_shows_cooldown(content):
    scene, app = scene_with_app(content)
    state = app.game_state
    quest = story.current_quest(state, content["story"])
    story.fail_mission(state, quest)
    scene.floor = "ops"
    put_player_at(scene, 8, 5)
    scene.handle_key(app, pygame.K_RETURN)
    labels = [i[0] for i in scene.submenu["items"]]
    assert any("FAILED" in l and "retry in" in l for l in labels)
    # and the target squad is not standing in the zone
    scene.area = "docks"
    assert scene._mission_target(state) is None


def test_swap_menu_and_requirement_block(content):
    scene, app = scene_with_app(content)
    state = app.game_state
    from game.hub import passive
    # bench iron man on the support task (needs INT 4+; Cap has 3)
    state["party"] = ["captain_america"]
    ok, _ = passive.assign(content, state, "iron_man", "support")
    assert ok
    put_player_at(scene, 10, 5)                       # ops floor support spot
    scene.floor = "ops"
    hit = scene._nearest_interaction(state)
    assert hit[1] == "iron_man"
    scene.handle_key(app, pygame.K_RETURN)
    choose(scene, app, "Swap into team...")
    labels = [i[0] for i in scene.submenu["items"]]
    # open slot exists (party of 1) so adding is offered too
    assert any(l.startswith("Add Iron Man") for l in labels)
    # swapping out Cap is blocked: he can't cover the INT-4 support task
    blocked = [i for i in scene.submenu["items"]
               if i[0].startswith("Swap out Captain America")]
    assert blocked and blocked[0][1] is True


def test_elevator_switches_floor(content):
    scene, app = scene_with_app(content)
    put_player_at(scene, 17, 2)                 # spawn, below elevator
    scene.handle_key(app, pygame.K_RETURN)
    choose(scene, app, "Training Floor")
    assert scene.floor == "training"
    assert scene.mode == "normal"


def test_bed_sleeps(content):
    scene, app = scene_with_app(content)
    put_player_at(scene, 2, 14)                 # next to the bed (1-2, 15)
    hit = scene._nearest_interaction(app.game_state)
    assert hit == ("station", "bed", "Sleep")
    scene.handle_key(app, pygame.K_RETURN)
    assert app.slept == [False]


def test_hulk_placement_follows_story(content):
    scene, app = scene_with_app(content)
    scene.floor = "training"
    state = app.game_state
    ids = [cid for cid, _, _ in scene._characters_here(state)]
    assert "hulk" not in ids                    # not arrived yet
    state["story_flags"]["hulk_arrived"] = True
    ids = [cid for cid, _, _ in scene._characters_here(state)]
    assert "hulk" in ids                        # brooding on the training floor
    state["roster"]["hulk"] = {"trained_ranks": {}, "attribute_xp": {},
                               "perks": [], "perk_choices": {}, "gear": {},
                               "ult_charge": 0}
    ids = [cid for cid, _, _ in scene._characters_here(state)]
    assert "hulk" not in ids                    # recruited: moved to common
    scene.floor = "common"
    ids = [cid for cid, _, _ in scene._characters_here(state)]
    assert "hulk" in ids


def test_maps_are_wellformed(content):
    for floor in FLOORS.values():
        assert len(floor["map"]) == 21
        for row in floor["map"]:
            assert len(row) == 40, f"bad row width in {floor['name']}: {len(row)}"
        sx, sy = floor["spawn"]
        assert floor["map"][sy][sx] == "."      # spawn tile walkable


# --- M10: rations, dispatch board, zone searching, street cart ---

def test_rations_menu_feeds_party_member(content):
    scene, app = scene_with_app(content)
    state = app.game_state
    state["roster"]["iron_man"]["energy"] = 50
    scene.handle_key(app, pygame.K_i)
    assert scene.mode == "submenu" and scene.submenu["title"] == "Rations"
    choose(scene, app, "Shawarma Wrap")         # starter ration
    choose(scene, app, "Iron Man")
    assert state["roster"]["iron_man"]["energy"] == 75
    assert "shawarma" not in state["inventory"]
    assert any("+25 EN" in m for m in scene.messages)


def test_board_dispatch_and_recall_in_person(content):
    scene, app = scene_with_app(content)
    state = app.game_state
    put_player_at(scene, 34, 12)                # next to the board (35, 12)
    scene.handle_key(app, pygame.K_RETURN)
    assert scene.submenu["title"] == "Assignment Board - Tier 1"
    labels = [i[0] for i in scene.submenu["items"]]
    assert any("1 Hero / 2 Days" in l for l in labels)  # M13: full words
    choose(scene, app, "Calibrate Tower Sensors")     # 1 hero, 2 days, ops spot
    choose(scene, app, "Send Iron Man")
    assert state["roster"]["iron_man"]["dispatch"] == "calibrate_sensors"
    assert state["party"] == ["captain_america"]
    # not on the common floor — he's at the job site on the ops floor
    ids = [cid for cid, _, _ in scene._characters_here(state)]
    assert "iron_man" not in ids
    # the board shows the job under way and WHERE the crew is — no recall row
    scene.handle_key(app, pygame.K_RETURN)
    labels = [i[0] for i in scene.submenu["items"]]
    assert any("[under way]" in l for l in labels)
    assert any("Away: Iron Man - Ops Floor" in l for l in labels)
    assert not any("Recall" in l for l in labels)
    scene.reset_modes()
    # M13: find him at the work site (ops 30, 4) and recall face to face
    scene.floor = "ops"
    ids = [cid for cid, _, _ in scene._characters_here(state)]
    assert "iron_man" in ids
    put_player_at(scene, 30, 5)
    hit = scene._nearest_interaction(state)
    assert hit[:2] == ("char", "iron_man")
    scene.handle_key(app, pygame.K_RETURN)
    assert "on assignment" in scene.submenu["title"]
    choose(scene, app, "Recall")
    assert "dispatch" not in state["roster"]["iron_man"]
    assert state["dispatches"] == []


def test_dispatch_cannot_empty_the_party(content):
    scene, app = scene_with_app(content)
    app.game_state["party"] = ["captain_america"]
    put_player_at(scene, 34, 12)
    scene.handle_key(app, pygame.K_RETURN)
    choose(scene, app, "Calibrate Tower Sensors")
    blocked = [i for i in scene.submenu["items"]
               if i[0].startswith("Send Captain America")]
    assert blocked and blocked[0][1] is True    # disabled: last team member


def test_crate_search_marks_spot_and_pays(content):
    import random
    scene, app = scene_with_app(content)
    state = app.game_state
    scene.area = "docks"
    scene.rng = random.Random(4)                # no trap, and the find succeeds
    put_player_at(scene, 2, 3)                  # beside the crate at (3, 3)
    hit = scene._nearest_interaction(state)
    assert hit[0] == "crate" and hit[1] == (3, 3)
    scene.handle_key(app, pygame.K_RETURN)
    assert 8 <= state["credits"] <= 20          # docks loot table
    assert state["time_minutes"] == 360 + config.SEARCH_MINUTES
    # (3,3) is spent for the day; the prompt moves on to the next crate
    hit = scene._nearest_interaction(state)
    assert hit[0] == "crate" and hit[1] != (3, 3)
    assert app.battles == []                    # no trap on this seed


def test_zone_helipad_flies_anywhere(content):
    scene, app = scene_with_app(content)
    scene.area = "docks"
    zone = content["zones"]["docks"]
    put_player_at(scene, 2, 15)                 # beside the helipad (1-2, 16)
    hit = scene._nearest_interaction(app.game_state)
    assert hit == ("station", "helipad", "Quinjet")
    scene.handle_key(app, pygame.K_RETURN)
    labels = [i[0] for i in scene.submenu["items"]]
    assert any(l.startswith("Avengers Tower") for l in labels)
    assert any(l.startswith("Midtown") for l in labels)
    assert any(l.startswith("HYDRA District") for l in labels)
    assert any(l.startswith("Stay here") for l in labels)
    assert not any(l.startswith("Hudson Docks") for l in labels)   # already here
    choose(scene, app, "Midtown")
    assert scene.area == "midtown"              # zone-to-zone, no tower stop
    # exactly one Quinjet hop on the clock (spec M11: TRAVEL_MINUTES per hop)
    assert app.game_state["time_minutes"] == 360 + config.TRAVEL_MINUTES


def test_board_shows_tier_teaser_and_request_label(content):
    scene, app = scene_with_app(content)
    app.game_state["day"] = 3                   # rotation shows the request tasks
    put_player_at(scene, 34, 12)
    scene.handle_key(app, pygame.K_RETURN)
    assert scene.submenu["title"] == "Assignment Board - Tier 1"
    labels = [i[0] for i in scene.submenu["items"]]
    assert any("Tier 2 jobs at team power 90 (now 37)" in l for l in labels)
    # NPC request shows who wants it and the bond payout (M13 wording)
    assert any(l.strip().startswith("requested by ") and "bond" in l
               for l in labels)


def test_street_cart_stocks_field_food(content):
    scene, app = scene_with_app(content)
    scene.area = "midtown"
    put_player_at(scene, 18, 11)                # below the cart at (18, 10)
    hit = scene._nearest_interaction(app.game_state)
    assert hit == ("station", "shop", "Street Cart")
    scene.handle_key(app, pygame.K_RETURN)
    labels = [i[0] for i in scene.submenu["items"]]
    assert any(l.startswith("Cup of Coffee") for l in labels)
    assert any(l.startswith("Shawarma Wrap") for l in labels)
    assert any(l.startswith("Med Kit") for l in labels)
    assert not any("Vintage Vinyl" in l for l in labels)   # tower-only stock


def test_ambush_frame_never_stacks_pass_out(content):
    # M11 regression pin: an ambush and a pass-out on the same update frame
    # must not fire together (BATTLE -> SLEEP is an illegal transition).
    scene, app = scene_with_app(content)
    scene.area = "docks"
    for entry in app.game_state["roster"].values():
        entry["energy"] = 0
    energy.sync(app.game_state)
    scene._move = lambda dt, a: a.start_battle(     # walking springs an ambush
        enemy_ids=["hydra_grunt"] * 5, ambush=True)
    scene.update(0.016, app)
    assert app.battles                              # the ambush fired
    assert app.slept == []                          # and pass-out did not stack


def test_engage_at_low_energy_fights_first_sleeps_after(content):
    scene, app = scene_with_app(content)
    state = app.game_state
    story.accept(state, story.current_quest(state, content["story"]))
    state["roster"]["captain_america"]["energy"] = 10
    energy.sync(state)
    scene.area = "docks"
    zone = content["zones"]["docks"]
    put_player_at(scene, zone["target_spot"][0], zone["target_spot"][1] + 1)
    scene.handle_key(app, pygame.K_RETURN)          # engage the mission squad
    assert app.battles and app.slept == []          # fight first, no sleep yet
    assert state["roster"]["captain_america"]["energy"] == 0
    app.machine.state = GameState.HUB               # battle resolved
    scene._move = lambda dt, a: None                # (headless: no key polling)
    scene.update(0.016, app)
    assert app.slept == [True]                      # the collapse comes after


def test_rack_is_party_only_and_locks_the_trainee(content):
    scene, app = scene_with_app(content)
    state = app.game_state
    state["roster"]["ant_man"] = {"trained_ranks": {}, "attribute_xp": {},
                                  "perks": [], "perk_choices": {}, "gear": {},
                                  "ult_charge": 0, "energy": 100, "unspent_xp": 0}
    scene.floor = "training"
    put_player_at(scene, 35, 7)                 # beside the rack (36-37, 6-7)
    scene.handle_key(app, pygame.K_RETURN)
    labels = [i[0] for i in scene.submenu["items"]]
    assert not any("Ant-Man" in l for l in labels)      # benched: not trainable
    choose(scene, app, "Train Captain America")
    assert scene.mode == "train_attr"
    scene.handle_key(app, pygame.K_RETURN)              # strength
    cap = state["roster"]["captain_america"]
    assert cap["training"]["attribute"] == "strength"
    assert state["party"] == ["iron_man"]               # pulled off the team
    assert scene.mode == "normal"
    scene.handle_key(app, pygame.K_RETURN)              # rack again
    labels = [i[0] for i in scene.submenu["items"]]
    assert not any(l.startswith("Train Captain America") for l in labels)
    assert any("Captain America - Strength, done" in l for l in labels)
    # while they're on the mats the dispatch picker refuses them too
    scene.reset_modes()
    scene.floor = "common"
    put_player_at(scene, 34, 12)
    scene.handle_key(app, pygame.K_RETURN)              # board
    choose(scene, app, "Calibrate Tower Sensors")
    rows = [i for i in scene.submenu["items"] if "Captain America" in i[0]]
    assert rows and rows[0][1] is True and "[training]" in rows[0][0]
    # the clock passing the session end brings them back mid-play
    state["time_minutes"] += 60
    scene.reset_modes()
    scene._move = lambda dt, a: None                    # headless: no key poll
    scene.update(0.016, app)
    assert "training" not in cap
    assert state["party"] == ["iron_man", "captain_america"]
    # but a session ending in the FIELD leaves them benched at the tower
    result = activities.start_training(state, content, "captain_america",
                                       "strength")
    assert result["ok"]
    scene.area = "docks"
    state["time_minutes"] += 200
    scene.update(0.016, app)
    assert state["party"] == ["iron_man"]               # no field teleport


def test_scout_quest_worked_on_foot(content):
    scene, app = scene_with_app(content)
    state = app.game_state
    first = content["story"][0]
    state["quests"][first["id"]] = {"name": first["name"], "status": "done"}
    story.init(state, content["story"])
    quest = story.current_quest(state, content["story"])
    assert quest["kind"] == "scout" and quest["location"] == "midtown"
    scene.area = "midtown"
    assert scene._scout_targets(state) == []            # not accepted yet
    story.accept(state, quest)
    assert len(scene._scout_targets(state)) == 3        # markers appear
    for i, (tx, ty) in enumerate(quest["scout_points"]):
        put_player_at(scene, tx, ty)
        hit = scene._nearest_interaction(state)
        assert hit[0] == "scout" and hit[2] == "Scout"
        scene.handle_key(app, pygame.K_RETURN)
    assert state["quests"][quest["id"]]["status"] == "done"
    assert scene._scout_targets(state) == []            # all worked
    assert any("complete" in m for m in scene.messages)


def test_gift_menu_lists_consumables(content):
    scene, app = scene_with_app(content)
    app.game_state["inventory"]["energy_bar"] = 1       # Hulk's true love
    put_player_at(scene, 4, 7)                          # Jarvis
    scene.handle_key(app, pygame.K_RETURN)
    choose(scene, app, "Give Gift")
    labels = [i[0] for i in scene.submenu["items"]]
    assert any(l.startswith("Energy Bar") for l in labels)      # M13
    assert any(l.startswith("Med Kit") for l in labels)         # starter kit
    assert any(l.startswith("Shawarma Wrap") for l in labels)


def test_talk_at_2am_sleeps_without_dialogue_box(content):
    scene, app = scene_with_app(content)
    state = app.game_state
    state["time_minutes"] = config.DAY_END_MINUTES - 15     # 1:45 AM
    put_player_at(scene, 4, 7)                              # Jarvis
    scene.handle_key(app, pygame.K_RETURN)
    choose(scene, app, "Talk")
    assert app.slept == [True]                              # pass-out won
    assert scene.mode != "scene"                            # no orphaned box
    assert state["bonds"]["jarvis"]["points"] == 15         # talk still counted
