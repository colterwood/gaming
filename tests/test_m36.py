"""M36: the first-twelve-days playtest pass.

Forty-odd notes off a real playthrough, most of them small. The ones worth
pinning are the rules that changed underneath existing systems: carried HP,
what a collapse costs, when rooms are open, what a repair is worth, and the
two places the game was quietly lying to the player (the Unibeam's reach and
a searched spot that could never be searched again).
"""

import random

import pygame
import pytest

from game import config, data_loader
from game.combat.engine import BattleEngine
from game.combat.entities import Combatant, make_enemy_group
from game.core import calendar as cal
from game.core import health, save
from game.hub import activities, dispatch, field, repairs, story, tower

from tests.test_tower_scene import FakeApp, put_player_at


@pytest.fixture(scope="module")
def content():
    pygame.init()
    return data_loader.load_all()


def party_state(content, credits=5000):
    state = save.new_game_state()
    for cid, char in content["characters"].items():
        if char["recruit"]["method"] == "starter":
            state["roster"][cid] = {"trained_ranks": {}, "attribute_xp": {},
                                    "perks": [], "perk_choices": {}, "gear": {},
                                    "ult_charge": 0, "energy": 100}
    state["party"] = sorted(state["roster"], reverse=True)
    state["credits"] = credits
    story.init(state, content["story"])
    return state


# --- notes 1/4/7/9/10: a repair costs the hunt and nothing else ----------

def test_fitting_a_repair_costs_no_clock_no_energy_and_pays_nothing(content):
    state = party_state(content)
    state["story_flags"] = {}
    job = repairs.job_by_id(content, "repair_elevator")
    repairs.accept(content, state, job)
    for index, part in enumerate(job["parts"]):
        if part.get("from"):
            repairs.take_npc_part(state, job, index)
        else:
            repairs.work_part(state, job, index)
    before = (state["time_minutes"], state["energy"], state["credits"])

    repairs.repair(content, state, job)

    assert (state["time_minutes"], state["energy"], state["credits"]) == before
    assert state["story_flags"]["elevator_repaired"] is True


def test_no_repair_pays_credits_at_all(content):
    # The tower is the player's own building. 830 cr across six jobs was a
    # third of why the purse was full with nothing to spend it on.
    assert [j["credits"] for j in content["repairs"]] == [0] * 6


# --- notes 8/23: a spot you already searched reopens for a new job -------

@pytest.mark.parametrize("job_id", ["repair_training", "repair_tech_lab"])
def test_accepting_a_job_reopens_the_spots_it_hides_parts_in(content, job_id):
    state = party_state(content)
    state["story_flags"] = {"board_unlocked": True}
    state["quests"]["ch1_siege"] = {"name": "Siege", "status": "done"}
    job = repairs.job_by_id(content, job_id)
    hidden = [p for p in job["parts"] if repairs.part_kind(p) == "hidden"]
    assert hidden, f"{job_id} should hide something"
    for part in hidden:
        activities.mark_spot_searched(state, part["area"], part["x"], part["y"])

    repairs.accept(content, state, job)

    for part in hidden:
        assert not activities.spot_searched(state, part["area"],
                                            part["x"], part["y"]), part


# --- note 2/36: everything is searchable, almost everything is empty -----

def test_furniture_and_trees_are_searchable_with_no_job_in_hand(content):
    scene, app = tower.HubScene(content), FakeApp(content)
    app.game_state["repairs"] = {}
    assert scene._furniture_here(app.game_state)         # tower, nothing on
    scene.area = "midtown"
    assert scene._furniture_here(app.game_state)         # street trees too


def test_a_plant_and_a_couch_come_up_empty_in_different_words(content):
    scene = tower.HubScene(content)
    assert scene.EMPTY_SEARCH["plant"] != scene.EMPTY_SEARCH[None]
    assert "worm" in scene.EMPTY_SEARCH["plant"].lower()


# --- note 41: HP is carried between fights -------------------------------

def test_hp_is_a_fraction_of_max_so_it_survives_a_rank_up(content):
    state = party_state(content)
    health.set_hero_hp_fraction(state, "iron_man", 0.5)
    small = Combatant(content["characters"]["iron_man"], is_hero=True,
                      hp_frac=0.5)
    bigger = Combatant(content["characters"]["iron_man"], is_hero=True,
                       trained_ranks={"stamina": 5}, hp_frac=0.5)
    assert bigger.max_hp > small.max_hp
    assert bigger.hp > small.hp                     # half of a bigger body


def test_a_living_hero_never_starts_a_fight_dead(content):
    """A Combatant at 0 HP is dead and would end the battle on turn one."""
    nearly = Combatant(content["characters"]["iron_man"], is_hero=True,
                       hp_frac=0.0001)
    assert nearly.hp >= 1 and nearly.alive


def test_sleeping_heals_and_collapsing_leaves_you_at_eighty_percent(content):
    state = party_state(content)
    health.set_hero_hp_fraction(state, "iron_man", 0.2)
    cal.sleep(state)
    assert health.hero_hp_fraction(state, "iron_man") == config.SLEEP_HP_FRACTION

    health.set_hero_hp_fraction(state, "iron_man", 1.0)
    cal.sleep(state, passed_out=True)
    assert health.hero_hp_fraction(state, "iron_man") == config.PASS_OUT_HP_FRACTION


def test_the_chair_mends_hp_as_well_as_energy(content):
    state = party_state(content)
    for hero_id in state["party"]:
        health.set_hero_hp_fraction(state, hero_id, 0.5)
    ok, _ = activities.can_rest(state)
    assert ok, "a hurt but rested team should still be treatable"
    activities.rest_tick(state)
    assert health.team_hp_fraction(state) == pytest.approx(
        0.5 + config.MEDBAY_HP_PCT_PER_TICK)


def test_a_med_kit_works_outside_a_fight_too(content):
    state = party_state(content)
    state["inventory"]["med_kit"] = 1
    for hero_id in state["party"]:
        health.set_hero_hp_fraction(state, hero_id, 0.4)
    result = activities.eat_food(state, content, "med_kit")
    assert result["ok"]
    assert health.team_hp_fraction(state) > 0.4
    assert state["inventory"].get("med_kit", 0) == 0


# --- notes 5/18: what a collapse costs -----------------------------------

def test_collapsing_indoors_costs_no_morning_but_still_costs_money(content):
    state = party_state(content, credits=1000)
    activities.go_to_sleep(state, passed_out=True, sheltered=True)
    assert state["energy"] == config.DAILY_ENERGY       # you were already home
    assert state["credits"] == 900                      # somebody still bills


def test_collapsing_in_the_field_costs_the_morning(content):
    state = party_state(content, credits=1000)
    activities.go_to_sleep(state, passed_out=True, sheltered=False)
    assert state["energy"] == config.PASS_OUT_NEXT_DAY_ENERGY


@pytest.mark.parametrize("purse,lost", [(0, 0), (900, 90), (40000, 4000),
                                        (200000, config.PASS_OUT_CREDIT_MAX)])
def test_a_collapse_costs_a_tenth_of_the_purse_capped(purse, lost):
    assert cal.passing_out_costs({"credits": purse}) == lost


# --- note 17: the clock never cancels a fight ----------------------------

def test_a_mission_engaged_at_two_in_the_morning_still_happens(content):
    """The clock never cancels a fight. M37c went further and made engaging
    cost no clock at all, so even a mission taken with the day already spent
    goes ahead — the reckoning is afterwards, in the hub."""
    state = party_state(content)
    state["time_minutes"] = config.DAY_END_MINUTES - 5
    result = activities.launch_mission(state)
    assert result["launch_battle"] and not result.get("passed_out")
    assert state["time_minutes"] == config.DAY_END_MINUTES - 5   # untouched

    state["time_minutes"] = config.DAY_END_MINUTES
    assert activities.should_pass_out(state)
    result = activities.launch_mission(state)
    assert result["launch_battle"], "the clock must never refuse the fight"


# --- note 39: the Unibeam reaches exactly one panel either way -----------

def test_a_corpse_blocks_the_unibeam_instead_of_conducting_it(content):
    """`living()` closed the ranks, so the more enemies the player had
    already killed the further the beam reached."""
    heroes = [Combatant(content["characters"]["iron_man"], is_hero=True)]
    enemies = make_enemy_group([content["enemies"]["hydra_grunt"]] * 4)
    engine = BattleEngine(heroes, enemies, rng=random.Random(1))
    unibeam = next(a for a in content["characters"]["iron_man"]["abilities"]
                   if a["id"] == "unibeam")

    assert len(engine._spread_targets(heroes[0], unibeam, enemies[1])) == 3
    enemies[1].hp = 0
    assert engine._spread_targets(heroes[0], unibeam, enemies[0]) == [enemies[0]]


# --- note 16: per-encounter enemy levels ---------------------------------

def test_an_encounter_can_ask_for_an_enemy_at_another_level(content):
    green = content["enemies"]["hydra_grunt@1"]
    veteran = content["enemies"]["hydra_grunt"]
    assert green["level"] == 1 and veteran["level"] == 2
    # the variant keeps the base id, so it shares a sprite and numbers as
    # "HYDRA Grunt 1 / 2" rather than reading as a different enemy
    assert green["id"] == veteran["id"] == "hydra_grunt"
    assert green["power_grid"]["strength"] < veteran["power_grid"]["strength"]


def test_the_lang_breakout_fields_the_squad_it_was_written_for(content):
    quest = next(q for q in content["story"] if q["id"] == "ch1_break_out_lang")
    levels = sorted((content["enemies"][e]["id"], content["enemies"][e]["level"])
                    for e in quest["enemies"])
    assert levels == [("hydra_enforcer", 1), ("hydra_enforcer", 2),
                      ("hydra_grunt", 1), ("hydra_grunt", 2),
                      ("hydra_medic", 1), ("hydra_medic", 1)]


# --- note 40: ambush frequency and the daily cap -------------------------

def test_midtown_is_the_safest_block_and_hydra_the_worst(content):
    rates = {z: field.ambush_rate(content["zones"][z])
             for z in ("midtown", "docks", "hydra_district")}
    assert rates["midtown"] < rates["docks"] < rates["hydra_district"]
    # ...and the ratio the design asks for: docks 2x midtown, HYDRA 2x docks
    assert rates["docks"] == pytest.approx(rates["midtown"] * 2)
    assert rates["hydra_district"] == pytest.approx(rates["docks"] * 2)


def test_ambush_rate_is_a_separate_knob_from_danger(content):
    """They are free to disagree — `danger` drives the badge, the trap risk
    and the enemy pool, `ambush_rate` drives how often you get jumped — and
    a zone written without a rate falls back to its danger.

    M37b: the shipped three now AGREE (see below), because having the map
    badge say the opposite of the ambush rate confused a real player. The
    mechanism stays: it is what lets them disagree deliberately later."""
    assert field.ambush_rate({"danger": 3}) == 3
    assert field.ambush_rate({"danger": 3, "ambush_rate": 0.25}) == 0.25


def test_the_badge_the_traps_and_the_ambushes_all_agree(content):
    """M37b: the docks read [!] while being jumped twice as often as
    Midtown's [!!]. A player who reads the map should not be misled."""
    order = ["midtown", "docks", "hydra_district"]
    zones = [content["zones"][z] for z in order]
    dangers = [z["danger"] for z in zones]
    rates = [field.ambush_rate(z) for z in zones]
    assert dangers == sorted(dangers) == [1, 2, 3], dangers
    assert rates == sorted(rates), rates          # same ranking as the badge


def test_a_zone_runs_out_of_patrols_for_the_day(content):
    state = party_state(content)
    for _ in range(config.AMBUSH_DAILY_CAP):
        assert not activities.zone_is_quiet(state, "docks")
        activities.record_fight(state, "docks")
    assert activities.zone_is_quiet(state, "docks")
    assert not activities.zone_is_quiet(state, "hydra_district")   # per zone
    cal.sleep(state)
    assert not activities.zone_is_quiet(state, "docks")            # re-arms


def test_a_quiet_zone_throws_no_more_ambushes(content):
    scene, app = tower.HubScene(content), FakeApp(content)
    scene.area = "docks"
    scene.rng = random.Random(0)
    for _ in range(config.AMBUSH_DAILY_CAP):
        activities.record_fight(app.game_state, "docks")
    for _ in range(500):
        scene._maybe_ambush(1.0, app)
    assert app.battles == []


# --- note 3: the person with the problem raises it as you walk in --------

def test_pepper_raises_the_quinjet_the_moment_you_reach_the_ops_floor(content):
    scene, app = tower.HubScene(content), FakeApp(content)
    state = app.game_state
    state["repairs"] = {}
    state["story_flags"] = {}
    elevator = repairs.job_by_id(content, "repair_elevator")
    state["repairs"]["repair_elevator"] = {
        "status": "done", "found": list(range(len(elevator["parts"])))}
    state["story_flags"]["elevator_repaired"] = True

    scene.floor = "common"
    scene._open_elevator(app)
    labels = [i[0] for i in scene.submenu["items"]]
    scene.submenu["index"] = next(i for i, l in enumerate(labels)
                                  if l.startswith("Ops Floor"))
    scene._submenu_key(app, pygame.K_RETURN)

    assert scene.floor == "ops"
    assert scene.mode == "scene"                    # she is already talking
    assert scene.scene["title"] == "Pepper Potts"
    assert repairs.is_active(state, repairs.job_by_id(content, "repair_quinjet"))


def test_arriving_somewhere_with_nothing_to_say_is_silent(content):
    scene, app = tower.HubScene(content), FakeApp(content)   # tower rebuilt
    scene._switch_floor("ops", app)
    assert scene.mode == "normal"


# --- notes 27/28/29: rooms keep hours ------------------------------------

@pytest.mark.parametrize("floor", sorted(config.ROOM_HOURS))
def test_every_room_is_open_inside_its_hours_and_shut_outside(floor):
    opens, closes = config.ROOM_HOURS[floor]
    assert tower.room_open({"time_minutes": opens}, floor)
    assert tower.room_open({"time_minutes": closes - 1}, floor)
    assert not tower.room_open({"time_minutes": closes}, floor)


def test_only_the_training_floor_actually_locks_its_door(content):
    """The labs and the ward stay walkable when shut — you find a dark
    bench, which is information. The mats roll up and the floor closes."""
    assert config.CLOSED_FLOORS_LOCK_OUT == ("training",)
    scene, app = tower.HubScene(content), FakeApp(content)
    state = app.game_state
    state["story_flags"]["pym_lab_unlocked"] = True     # Lang's door code
    state["time_minutes"] = 23 * 60 + 30                # after the mats close
    locked, why = scene.floor_locked(state, "training")
    assert locked and "closed" in why
    for floor in ("med_bay", "tech_lab", "pym_lab"):
        assert not scene.floor_locked(state, floor)[0], floor
        assert not tower.room_open(state, floor), floor  # shut, but reachable


def test_a_shut_bench_says_so_and_does_not_open(content):
    scene, app = tower.HubScene(content), FakeApp(content)
    app.game_state["time_minutes"] = 20 * 60            # labs shut at 6 PM
    scene._switch_floor("tech_lab")
    put_player_at(scene, 6, 4)
    scene.handle_key(app, pygame.K_RETURN)
    assert scene.submenu is None
    assert any("cold" in m or "Back at" in m for m in scene.messages), scene.messages


# --- notes 26/27/34: the rack ---------------------------------------------

def test_the_rack_charges_at_the_door(content):
    state = party_state(content, credits=0)
    refused = activities.start_training(state, content, "captain_america",
                                        "strength")
    assert not refused["ok"] and "cr" in refused["message"]
    assert "training" not in state["roster"]["captain_america"]

    state["credits"] = 500
    ok = activities.start_training(state, content, "captain_america", "strength")
    assert ok["ok"]
    assert state["credits"] == 500 - config.TRAINING_CREDITS_BY_LEVEL[1]


def test_the_credit_price_is_a_credit_per_xp_the_basic_rack_pays():
    assert (config.TRAINING_CREDITS_BY_LEVEL
            == config.TRAINING_XP_BY_LEVEL), \
        "the price keys off the BASE yield, so the x2 facility is half price"


def test_a_finished_trainee_waits_to_be_collected(content):
    state = party_state(content)
    activities.start_training(state, content, "captain_america", "strength")
    state["time_minutes"] += 50 * config.TRAINING_LOCKOUT_MULT
    messages = activities.finish_due_training(state, content)

    assert "captain_america" not in state["party"]
    assert state["roster"]["captain_america"]["done_training"] is True
    assert any("mats" in m for m in messages)


def test_training_the_last_hero_asks_and_then_allows(content):
    state = party_state(content)
    state["party"] = ["captain_america"]

    asked = activities.start_training(state, content, "captain_america",
                                      "strength")
    assert not asked["ok"] and asked["needs_solo_confirm"]

    allowed = activities.start_training(state, content, "captain_america",
                                        "strength", solo_ok=True)
    assert allowed["ok"] and state["party"] == []
    # ...and the empty team must not read as a collapse the very next frame
    assert not activities.should_pass_out(state)


def test_an_empty_team_is_not_a_collapse_and_is_not_a_cage(content):
    """The first cut froze movement with nobody on the team. Watching your
    last hero train then became a trap: the session ended, there was no one
    left to walk over and collect them with, and 2 AM arrived. You can always
    walk — off a floor that is closing, to the lift, to bed."""
    import collections
    import unittest.mock as mock

    scene, app = tower.HubScene(content), FakeApp(content)
    app.game_state["party"] = []
    assert not activities.should_pass_out(app.game_state)

    keys = collections.defaultdict(bool)
    keys[pygame.K_RIGHT] = True
    before = (scene.px, scene.py)
    with mock.patch.object(pygame.key, "get_pressed", lambda: keys):
        scene._move(0.5, app)
    assert (scene.px, scene.py) != before, "the player must still be able to walk"


def test_the_last_hero_comes_off_the_mats_by_themselves(content):
    """With a team you collect a finished trainee in person. With NO team
    there is nobody to collect them with, so they come back on their own —
    otherwise the player never gets control of anything again."""
    state = party_state(content)
    state["party"] = ["captain_america"]
    assert activities.start_training(state, content, "captain_america",
                                     "strength", solo_ok=True)["ok"]
    assert state["party"] == []

    state["time_minutes"] += 50 * config.TRAINING_LOCKOUT_MULT
    messages = activities.finish_due_training(state, content)

    assert state["party"] == ["captain_america"]
    assert "done_training" not in state["roster"]["captain_america"]
    assert any("back on the team" in m.lower() for m in messages), messages


def test_a_closing_floor_never_traps_the_hero_on_it(content):
    """The training floor locks at 11 PM. A session that ends after that
    must still hand the player back their hero, and the player must be able
    to walk off the floor they are standing on."""
    import collections
    import unittest.mock as mock

    scene, app = tower.HubScene(content), FakeApp(content)
    state = app.game_state
    state["credits"] = 5000
    state["party"] = ["iron_man"]
    scene.floor = "training"
    state["time_minutes"] = 22 * 60 + 30
    activities.start_training(state, content, "iron_man", "strength",
                              solo_ok=True)

    state["time_minutes"] = 23 * 60 + 30            # the mats close
    assert not tower.room_open(state, "training")
    assert scene.floor_locked(state, "training")[0]  # can't come back IN...
    keys = collections.defaultdict(bool)
    keys[pygame.K_RIGHT] = True
    before = (scene.px, scene.py)
    with mock.patch.object(pygame.key, "get_pressed", lambda: keys):
        scene._move(0.5, app)
    assert (scene.px, scene.py) != before            # ...but can walk OUT

    scene._move = lambda dt, a: None
    for _ in range(40):                              # watch it out
        state["time_minutes"] += 10
        if state["time_minutes"] >= config.DAY_END_MINUTES:
            break
        scene.update(0.0, app)
        if state["party"]:
            break
    assert state["party"] == ["iron_man"], "control never came back"


# --- note 14: perk tiers are the rank on the card ------------------------

def test_perk_tiers_are_card_ranks_not_trained_ranks(content):
    assert config.PERK_CHOICE_RANKS == (5, config.RANK_MAX)
    assert sorted(content["perks"]["strength"]) == ["10", "5"]


# --- notes 35/37/38/43: the Thor arc stops holding your hand -------------

def test_the_thunder_does_not_tell_you_where_to_look(content):
    arc = content["unlocks"][0]
    lines = " ".join(arc["signal_scene"]["lines"]).lower()
    assert "trees" not in lines


def test_finding_it_does_not_name_it_or_mark_it(content):
    arc = content["unlocks"][0]
    assert arc["lift_label"] == arc["search_label"]
    assert "Stormbreaker" not in arc["lift_label"]
    assert "mighty enough to lift" in arc["lift_refusal"]


def test_the_searched_trees_are_not_greyed_out(content):
    scene = tower.HubScene(content)
    scene.area = "midtown"
    assert scene._worked_grove_tiles({}) == set()


def test_thors_arrival_narrates_before_he_speaks(content):
    scene = tower.HubScene(content)
    scene.scene = content["unlocks"][0]["arrival_scene"]
    assert scene._scene_speaker(0) == (None, "The Common Floor")
    assert scene._scene_speaker(1) == ("thor", "Thor Odinson")


def test_a_scene_without_speakers_behaves_exactly_as_before(content):
    scene = tower.HubScene(content)
    scene.scene = {"character": "coulson", "title": "Agent Coulson",
                   "lines": ["a", "b"]}
    assert scene._scene_speaker(0) == ("coulson", "Agent Coulson")
    assert scene._scene_speaker(1) == ("coulson", "Agent Coulson")


# --- notes 30/31/32/44: the rooms have people in them --------------------

@pytest.mark.parametrize("floor,who", [("tech_lab", "jarvis"),
                                       ("pym_lab", "hank_pym"),
                                       ("med_bay", "medbay_unit")])
def test_a_rebuilt_room_has_somebody_running_it(content, floor, who):
    scene, app = tower.HubScene(content), FakeApp(content)
    scene.floor = floor
    here = [c for c, _, _ in scene._characters_here(app.game_state)]
    assert who in here


def test_an_unrepaired_room_is_empty(content):
    scene, app = tower.HubScene(content), FakeApp(content)
    app.game_state["story_flags"] = {}
    scene.floor = "pym_lab"
    assert "hank_pym" not in [c for c, _, _ in
                              scene._characters_here(app.game_state)]


def test_the_autodocs_are_staff_not_cast(content):
    """They talk. There is nothing there to have a relationship with."""
    from game.social import bonds
    assert not bonds.bondable(content["characters"]["medbay_unit"])
    assert bonds.bondable(content["characters"]["hank_pym"])


def test_hulk_has_something_to_say_when_he_joins(content):
    scene = next(s for s in content["bond_scenes"] if s["id"] == "hulk_bond_4")
    assert scene["character"] == "hulk"
    assert scene["level"] == config.BOND_GATE_RECRUIT
    assert len(scene["lines"]) > 1


# --- note 33: a failed fight re-arms itself ------------------------------

def test_a_failed_fight_mission_comes_back_without_a_trip_to_ops(content):
    state = party_state(content)
    quest = story.current_quest(state, content["story"])
    assert quest["kind"] == "battle"
    story.accept(state, quest)
    state["day"] += quest["deadline_days"] + 1
    story.check_deadlines(state, content["story"])
    assert story.is_locked(state, quest)

    state["day"] += config.MISSION_FAIL_COOLDOWN_DAYS
    messages = story.check_deadlines(state, content["story"])

    assert story.is_accepted(state, quest)              # already live again
    assert story.days_left(state, quest) == quest["deadline_days"]
    assert any("back" in m for m in messages)


def test_a_scout_quest_still_has_to_be_re_accepted(content):
    scout = next(q for q in content["story"] if q["kind"] == "scout")
    assert not story.reactivates_itself(scout)
    assert story.reactivates_itself({"kind": "battle"})
    assert not story.reactivates_itself({"kind": "battle", "reaccept": True})


# --- caught by review: things the first cut of M36 got wrong -------------

def test_the_repair_menu_opens_when_the_job_is_ready_to_fit(content):
    """Deleting config.REPAIR_MINUTES left the menu row still reading it, so
    standing at a finished repair raised AttributeError. No test opened the
    menu in the ready-to-fit state, so the suite stayed green."""
    scene, app = tower.HubScene(content), FakeApp(content)
    state = app.game_state
    state["repairs"], state["story_flags"] = {}, {}
    job = repairs.job_by_id(content, "repair_elevator")
    repairs.accept(content, state, job)
    for index, part in enumerate(job["parts"]):
        if part.get("from"):
            repairs.take_npc_part(state, job, index)
        else:
            repairs.work_part(state, job, index)
    assert repairs.can_repair(state, job)

    scene._open_repair_menu(app, job)               # used to raise

    labels = [i[0] for i in scene.submenu["items"]]
    assert job["repair_label"] in labels
    assert not any("h 00m" in l for l in labels)    # no cost to quote


def test_a_finished_trainee_is_standing_at_the_mats_to_be_collected(content):
    """The hub asked for rejoin=(area == "tower"), which is True exactly when
    the trainee is standing in the tower — so they teleported back onto the
    team and the collect-in-person rule never fired in normal play."""
    scene, app = tower.HubScene(content), FakeApp(content)
    state = app.game_state
    activities.start_training(state, content, "captain_america", "strength")
    state["time_minutes"] += 50 * config.TRAINING_LOCKOUT_MULT
    scene._move = lambda dt, a: None
    scene.update(0.016, app)

    assert "captain_america" not in state["party"]
    assert state["roster"]["captain_america"]["done_training"] is True
    scene.floor = "training"
    assert "captain_america" in [c for c, _, _ in
                                 scene._characters_here(state)]


def test_a_quiet_zone_does_not_spring_crate_traps_either(content):
    """The cap gated the ambush ROLL but _spring_squad only counted, so a
    booby-trapped crate could still fire on a block that had gone quiet —
    and traps are the same free, full-XP fight."""
    scene, app = tower.HubScene(content), FakeApp(content)
    zone = content["zones"]["docks"]
    for _ in range(config.AMBUSH_DAILY_CAP):
        activities.record_fight(app.game_state, "docks")

    fired = scene._spring_squad(app, zone, ["hydra_grunt", "hydra_grunt"], "!")

    assert fired is False
    assert app.battles == []


def test_reloading_does_not_drag_a_locked_hero_back_onto_the_team(content):
    """load_game refills an empty party from the roster. That was dead code
    until solo training made an empty party reachable; it then handed the
    player a free skip of the longest lockout in the game, and put heroes who
    are supposed to be unavailable into battles."""
    from game import __main__ as main_mod

    state = party_state(content)
    activities.start_training(state, content, "iron_man", "strength")
    activities.start_training(state, content, "captain_america", "strength",
                              solo_ok=True)
    assert state["party"] == []

    app = main_mod.App.__new__(main_mod.App)        # no window needed
    app.game_state = state
    if not app.game_state.get("party"):
        free = [h for h, e in sorted(app.game_state["roster"].items())
                if not e.get("training") and not e.get("dispatch")]
        app.game_state["party"] = sorted(free, reverse=True)[:config.PARTY_SIZE_MAX]

    assert state["party"] == []                     # everyone is locked
    for entry in state["roster"].values():
        assert entry.get("training")                # ...and stays locked


def test_the_hud_says_no_team_rather_than_showing_two_empty_bars(content):
    """Both bars floor at 0 with nobody on the team, which reads as "you are
    about to collapse" — the opposite of the truth while you stand watching
    your last hero train."""
    from game.ui import pixelkit

    scene, app = tower.HubScene(content), FakeApp(content)
    app.game_state["party"] = []
    surface = pygame.Surface((config.WIDTH, config.HEIGHT))
    drawn, original = [], pixelkit.text

    def spy(surf, text, size, colour, **kw):
        drawn.append(text)
        return original(surf, text, size, colour, **kw)

    pixelkit.text = spy
    try:
        scene._draw_hud(surface, app.game_state)
    finally:
        pixelkit.text = original

    assert any("no team" in t for t in drawn), drawn


def test_the_lockout_multiplier_does_what_the_comment_says():
    """config.py claims it changes nothing through level 5 and first bites at
    level 6. Sessions/day is min(energy-allowed, clock-allowed), and the
    energy figure is not a plain division — the rack refuses a session that
    would zero the trainee."""
    def by_energy(level):
        cost = config.TRAINING_ENERGY_BASE + config.TRAINING_ENERGY_PER_RANK * level
        left, n = config.DAILY_ENERGY, 0
        while left > cost:
            left -= cost
            n += 1
        return n

    day = config.DAY_END_MINUTES - config.DAY_START_MINUTES
    for level in range(1, 6):
        base = config.TRAINING_MINUTES_BY_LEVEL[level]
        assert min(by_energy(level), day // base) == \
               min(by_energy(level), day // (base * config.TRAINING_LOCKOUT_MULT)), \
            f"level {level} should be unaffected"
    base6 = config.TRAINING_MINUTES_BY_LEVEL[6]
    assert (min(by_energy(6), day // base6)
            > min(by_energy(6), day // (base6 * config.TRAINING_LOCKOUT_MULT)))


# --- playtest round 2: the Tasks tab and the training prompt -------------

def test_the_tasks_tab_shows_progress_without_reading_the_board(content):
    """The tab early-returned when today's board was unread, so every
    progress line sat behind a trip to a corkboard downstairs. The M20 rule
    is about POSTINGS; how long Cap has left on the mats is your own."""
    from game.ui.impel_card import ImpelCardScene

    state = party_state(content)
    state["story_flags"]["board_unlocked"] = True
    state["repairs"] = {}
    repairs.accept(content, state, repairs.job_by_id(content, "repair_med_bay"))
    activities.start_training(state, content, "captain_america", "strength")
    state["upgrades"] = [{"item": "kevlar_weave", "level": 2, "days_left": 2}]

    assert not activities.board_checked_today(state)
    rows = [r[0] for r in ImpelCardScene(content)._progress_rows(state)]

    assert any("Open the Med Bay" in r and "parts" in r for r in rows)
    assert any("training Strength" in r and "to go" in r for r in rows)
    assert any("Pym bench" in r and "left" in r for r in rows)


def test_the_tasks_tab_shows_time_left_on_an_assignment(content):
    from game.ui.impel_card import ImpelCardScene

    state = party_state(content)
    for hero_id in ("ant_man", "thor"):
        state["roster"][hero_id] = {"trained_ranks": {}, "attribute_xp": {},
                                    "perks": [], "perk_choices": {}, "gear": {},
                                    "ult_charge": 0, "energy": 100}
    state["party"] = ["iron_man", "captain_america", "thor"]
    task = next(t for t in content["assignments"] if t["id"] == "sweep_hangar")
    ok, message = dispatch.send(content, state, task, ["ant_man"])
    assert ok, message

    rows = [r[0] for r in ImpelCardScene(content)._progress_rows(state)]
    away = [r for r in rows if "Ant-Man" in r]
    assert away and ("back in" in away[0] or "back tonight" in away[0]), rows


def test_a_menu_opens_on_something_you_can_actually_choose(content):
    """Menus here often lead with a disabled label — a job name, a question.
    The cursor started on it, so the first Enter did nothing at all."""
    scene = tower.HubScene(content)
    scene._open_submenu("t", [("a heading", True, None),
                              ("do the thing", False, lambda a: None),
                              ("never mind", False, None)])
    assert scene.submenu["index"] == 1

    # ...and arrowing around never parks on the heading again
    for _ in range(6):
        scene._submenu_key(None, pygame.K_UP)
        assert not scene.submenu["items"][scene.submenu["index"]][1]
        scene._submenu_key(None, pygame.K_DOWN)
        assert not scene.submenu["items"][scene.submenu["index"]][1]


def test_a_menu_of_pure_labels_does_not_hang_looking_for_a_row(content):
    scene = tower.HubScene(content)
    scene._open_submenu("t", [("just a label", True, None)])
    assert scene.submenu["index"] == 0


def test_being_broke_is_said_before_the_team_question(content):
    """You were asked whether to empty the team, and only then told you
    could not afford the session anyway."""
    state = party_state(content, credits=0)
    state["party"] = ["captain_america"]

    result = activities.start_training(state, content, "captain_america",
                                       "strength")

    assert not result["ok"]
    assert not result.get("needs_solo_confirm")
    assert "cr" in result["message"]


def test_too_exhausted_is_also_said_before_the_team_question(content):
    state = party_state(content)
    state["party"] = ["captain_america"]
    state["roster"]["captain_america"]["energy"] = 1

    result = activities.start_training(state, content, "captain_america",
                                       "strength")

    assert not result["ok"] and not result.get("needs_solo_confirm")
    assert "exhausted" in result["message"]


def test_confirming_the_solo_question_starts_the_session_it_asked_about(content):
    """The confirm used to drop the player back on the attribute list to
    re-pick the attribute they had already picked."""
    scene, app = tower.HubScene(content), FakeApp(content)
    state = app.game_state
    state["credits"] = 5000
    state["party"] = ["iron_man"]
    scene.floor = "training"
    put_player_at(scene, 35, 7)

    scene.handle_key(app, pygame.K_RETURN)          # 1: the rack
    scene.handle_key(app, pygame.K_RETURN)          # 2: Train Iron Man
    scene.handle_key(app, pygame.K_RETURN)          # 3: Strength
    assert scene.mode == "submenu"
    assert scene.submenu["title"] == "Training"
    labels = [i[0] for i in scene.submenu["items"]]
    assert labels[0].startswith("Iron Man is the only one left on the team")
    assert "Ya - I'll just watch" in labels and "No!" in labels

    scene.submenu["index"] = labels.index("Ya - I'll just watch")
    scene.handle_key(app, pygame.K_RETURN)          # 4: and it STARTS

    assert state["roster"]["iron_man"]["training"]["attribute"] == "strength"
    assert scene.mode == "normal"
    assert any("Creepy" in m for m in scene.messages)


def test_saying_no_to_the_solo_question_leaves_everything_alone(content):
    scene, app = tower.HubScene(content), FakeApp(content)
    state = app.game_state
    state["credits"] = 5000
    state["party"] = ["iron_man"]
    scene.floor = "training"
    put_player_at(scene, 35, 7)
    for _ in range(3):
        scene.handle_key(app, pygame.K_RETURN)
    labels = [i[0] for i in scene.submenu["items"]]
    scene.submenu["index"] = labels.index("No!")
    scene.handle_key(app, pygame.K_RETURN)

    assert "training" not in state["roster"]["iron_man"]
    assert state["credits"] == 5000                 # nothing charged
    assert state["party"] == ["iron_man"]
    assert scene.mode == "normal"


def _waiting_at_the_mats(content, extra=("thor",)):
    """A finished trainee, benched, flagged for collection."""
    from game.hub import party as party_mod

    state = party_state(content)
    for hero_id in extra:
        state["roster"][hero_id] = {"trained_ranks": {}, "attribute_xp": {},
                                    "perks": [], "perk_choices": {}, "gear": {},
                                    "ult_charge": 0, "energy": 100}
        state["party"].append(hero_id)
    activities.start_training(state, content, "captain_america", "strength")
    state["time_minutes"] += 50 * config.TRAINING_LOCKOUT_MULT
    activities.finish_due_training(state, content)
    assert state["roster"]["captain_america"]["done_training"] is True
    return state, party_mod


@pytest.mark.parametrize("how", ["open slot", "swap"])
def test_collecting_a_trainee_anywhere_stops_the_card_asking(content, how):
    """"Waiting at the mats" stops being true the moment they are on the
    team, HOWEVER they got there. The flag was cleared by the rack menu
    only, so collecting them by walking up to them in the world left it set
    and the Tasks tab went on telling the player to fetch a hero already
    following them around."""
    from game.ui.impel_card import ImpelCardScene

    state, party_mod = _waiting_at_the_mats(content)
    if how == "open slot":
        state["party"].remove("thor")               # make room
        ok, message = party_mod.add_to_party(content, state, "captain_america")
    else:
        ok, message = party_mod.swap(content, state, "captain_america", "thor")
    assert ok, message

    assert "captain_america" in state["party"]
    assert "done_training" not in state["roster"]["captain_america"]
    rows = [r[0] for r in ImpelCardScene(content)._progress_rows(state)]
    assert not [r for r in rows if "collect them" in r], rows


def test_the_card_never_asks_you_to_collect_someone_on_the_team(content):
    """Belt and braces: even with the flag somehow set, a hero who is on the
    team is not waiting anywhere."""
    from game.ui.impel_card import ImpelCardScene

    state = party_state(content)
    state["roster"]["captain_america"]["done_training"] = True
    assert "captain_america" in state["party"]
    rows = [r[0] for r in ImpelCardScene(content)._progress_rows(state)]
    assert not [r for r in rows if "collect them" in r], rows


# --- the Med Bay chair tells you what the hours buy ----------------------

def _in_the_chair(content, en, hp, when=12 * 60 + 30):
    from game.core import energy as energy_mod

    state = party_state(content)
    state["time_minutes"] = when
    for hero_id in state["party"]:
        energy_mod.set_hero_energy(state, hero_id, en)
        health.set_hero_hp_fraction(state, hero_id, hp)
    energy_mod.sync(state)
    return state


def test_the_forecast_counts_whichever_is_further_behind(content):
    """The chair mends both at MEDBAY_*_PER_TICK a tick, so "when do I get
    up" is decided by the worse of the two."""
    state = _in_the_chair(content, en=40, hp=0.30)
    f = activities.treatment_forecast(state)

    # 60 EN short at 10/tick = 6 ticks; 70% HP short at 10%/tick = 7 ticks
    assert f["energy_minutes"] == 6 * config.MEDBAY_TICK_MINUTES
    assert f["hp_minutes"] == 7 * config.MEDBAY_TICK_MINUTES
    assert f["minutes"] == f["hp_minutes"]
    assert f["done_at"] == state["time_minutes"] + f["hp_minutes"]
    assert not f["past_day_end"]


def test_the_forecast_is_zero_when_there_is_nothing_to_mend(content):
    f = activities.treatment_forecast(_in_the_chair(content, en=100, hp=1.0))
    assert f["minutes"] == 0 and not f["past_day_end"]


def test_the_forecast_says_when_it_will_not_finish_before_two_am(content):
    state = _in_the_chair(content, en=20, hp=0.10, when=25 * 60)
    assert activities.treatment_forecast(state)["past_day_end"]


def test_the_forecast_matches_what_the_chair_actually_does(content):
    """The estimate has to agree with rest_tick, or it is a lie."""
    state = _in_the_chair(content, en=40, hp=0.30)
    predicted = activities.treatment_forecast(state)["done_at"]
    for _ in range(50):
        if activities.rest_tick(state)["full"]:
            break
    assert state["time_minutes"] == predicted


@pytest.mark.parametrize("en,hp,expect", [
    (40, 0.30, "both by"),          # different, so name the earlier one
    (40, 1.00, "Full by"),          # only energy
    (100, 0.30, "Full by"),         # only HP
    (100, 1.00, "Nothing left"),
])
def test_the_chair_line_reads_correctly(content, en, hp, expect):
    scene = tower.HubScene(content)
    assert expect in scene._treatment_line(_in_the_chair(content, en, hp))


def test_the_chair_shows_both_bars(content):
    from game.ui import pixelkit

    scene, app = tower.HubScene(content), FakeApp(content)
    app.game_state = _in_the_chair(content, en=40, hp=0.30)
    scene.mode = "resting"
    drawn, original = [], pixelkit.text

    def spy(surface, text, size, colour, **kw):
        drawn.append(text)
        return original(surface, text, size, colour, **kw)

    pixelkit.text = spy
    try:
        scene._draw_rest(pygame.Surface((config.WIDTH, config.HEIGHT)),
                         app.game_state)
    finally:
        pixelkit.text = original

    assert "EN" in drawn and "HP" in drawn
    assert any("40 / 100" in t for t in drawn)
    assert any(t == "30%" for t in drawn)
    assert any("both by" in t for t in drawn)


# --- the board explains itself -------------------------------------------

def test_a_gated_repair_says_what_it_is_waiting_for(content):
    """A room that is still broken but not yet offered used to be simply
    absent from the board, which is indistinguishable from a bug."""
    scene, app = tower.HubScene(content), FakeApp(content)
    state = app.game_state
    state["repairs"], state["story_flags"] = {}, {}
    for job_id in ("repair_elevator", "repair_quinjet", "repair_training"):
        job = repairs.job_by_id(content, job_id)
        state["repairs"][job_id] = {"status": "done",
                                    "found": list(range(len(job["parts"])))}
        state["story_flags"][job["flag"]] = True
        for flag, value in job.get("flags", {}).items():
            state["story_flags"][flag] = value

    ids = [j["id"] for j in repairs.blocked(content, state)]
    assert "repair_tech_lab" in ids and "repair_pym_lab" in ids
    assert repairs.why_blocked(
        content, state, repairs.job_by_id(content, "repair_tech_lab")
    ) == "Siege of the Tower"

    scene._open_board(app)
    labels = [i[0] for i in scene.submenu["items"]]
    assert any("LOCKED - Restart the Tech Lab" in l
               and "Siege of the Tower" in l for l in labels), labels


def test_the_tech_lab_opens_once_the_chapter_one_boss_is_down(content):
    state = party_state(content)
    state["repairs"], state["story_flags"] = {}, {"board_unlocked": True}
    tech = repairs.job_by_id(content, "repair_tech_lab")
    assert tech in repairs.blocked(content, state)

    state["quests"]["ch1_siege"] = {"name": "Siege", "status": "done"}

    assert repairs.why_blocked(content, state, tech) is None
    assert tech in repairs.posted(content, state)


def test_a_posted_repair_greys_out_while_another_is_in_hand(content):
    """One repair at a time. The row used to look pickable and only refuse
    once you chose it."""
    scene, app = tower.HubScene(content), FakeApp(content)
    state = app.game_state
    state["repairs"], state["story_flags"] = {}, {"board_unlocked": True}
    repairs.accept(content, state, repairs.job_by_id(content, "repair_training"))

    scene._open_board(app)
    rows = [(l, d) for l, d in
            [(i[0], i[1]) for i in scene.submenu["items"]]
            if l.startswith("REPAIR - ")]
    assert rows, [i[0] for i in scene.submenu["items"]]
    for label, disabled in rows:
        assert disabled and "finish Restore the Training Floor first" in label


# --- note 42: the HUD packs itself and cannot collide --------------------

def test_the_event_banner_never_runs_through_the_floor_name(content):
    from game.ui import pixelkit

    scene, app = tower.HubScene(content), FakeApp(content)
    state = app.game_state
    state["day"] = 12                       # S.H.I.E.L.D. Supply Drop, days 12-13
    state["credits"] = 123456               # and a fat purse to crowd it
    surface = pygame.Surface((config.WIDTH, config.HEIGHT))

    spans, original = [], pixelkit.text

    def spy(surf, text, size, colour, **kw):
        anchor = kw.get("topleft") or kw.get("topright")
        if anchor and anchor[1] == 5:
            width = pixelkit.font(size).size(text)[0]
            left = anchor[0] if "topleft" in kw else anchor[0] - width
            spans.append((left, left + width, text))
        return original(surf, text, size, colour, **kw)

    pixelkit.text = spy
    try:
        scene._draw_hud(surface, state)
    finally:
        pixelkit.text = original

    assert any("Supply Drop" in t for _, _, t in spans)
    assert any("Common Floor" in t for _, _, t in spans)
    spans.sort()
    for (_, end, left_text), (start, _, right_text) in zip(spans, spans[1:]):
        assert end <= start, f"{left_text!r} runs into {right_text!r}"
