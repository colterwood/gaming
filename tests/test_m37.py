"""M37: levelling feels like levelling, and Stamina finally does something.

Five playtest notes. Four are feedback — a chime and a full restore on a
rank-up, and a teammate telling you in person when they are free again. The
fifth is the one with teeth: daily energy was a flat 100 for everybody, so
the attribute named Stamina bought HP and nothing that had to do with how
much you could get done in a day.
"""

import pygame
import pytest

from game import config, data_loader
from game.core import calendar as cal
from game.core import energy, health, save
from game.hub import activities, dispatch, tower
from game.progression import attributes as attrs
from game.ui import audio

from tests.test_tower_scene import FakeApp


@pytest.fixture(scope="module")
def content():
    pygame.init()
    return data_loader.load_all()


def entry(**trained):
    return {"trained_ranks": dict(trained), "attribute_xp": {}, "perks": [],
            "perk_choices": {}, "gear": {}, "ult_charge": 0,
            "energy": config.DAILY_ENERGY}


# --- note 3: Stamina raises the daily ceiling ----------------------------

def test_stamina_raises_the_daily_energy_ceiling():
    assert energy.max_for(entry()) == config.DAILY_ENERGY
    assert energy.max_for(entry(stamina=config.TRAINED_MAX)) == (
        config.DAILY_ENERGY
        + config.ENERGY_PER_STAMINA_RANK * config.TRAINED_MAX)
    # every rank is worth exactly the constant, no more and no less
    for trained in range(config.TRAINED_MAX):
        assert (energy.max_for(entry(stamina=trained + 1))
                - energy.max_for(entry(stamina=trained))
                == config.ENERGY_PER_STAMINA_RANK)


def test_energy_is_clamped_to_the_heros_own_ceiling():
    state = {"roster": {"tough": entry(stamina=9), "soft": entry()},
             "party": ["tough", "soft"]}
    energy.set_hero_energy(state, "tough", 999)
    energy.set_hero_energy(state, "soft", 999)
    assert energy.hero_energy(state, "tough") == 145
    assert energy.hero_energy(state, "soft") == 100


def test_everyone_wakes_at_their_own_ceiling():
    state = save.new_game_state()
    state["roster"] = {"tough": entry(stamina=9), "soft": entry()}
    state["party"] = ["tough", "soft"]
    for hero_id in state["party"]:
        energy.set_hero_energy(state, hero_id, 0)

    cal.sleep(state)

    assert state["roster"]["tough"]["energy"] == 145
    assert state["roster"]["soft"]["energy"] == 100
    assert state["energy"] == 100                # team = the weakest link


def test_the_collapse_penalty_scales_with_the_ceiling():
    """A flat 80 would punish a Stamina-10 hero less than a Stamina-1 one."""
    state = save.new_game_state()
    state["roster"] = {"tough": entry(stamina=9), "soft": entry()}
    state["party"] = ["tough", "soft"]

    cal.sleep(state, passed_out=True, sheltered=False)

    assert state["roster"]["soft"]["energy"] == config.PASS_OUT_NEXT_DAY_ENERGY
    assert state["roster"]["tough"]["energy"] == int(
        145 * config.PASS_OUT_ENERGY_FRACTION)


def test_the_chair_fills_a_bigger_tank_and_says_so(content):
    state = save.new_game_state()
    state["roster"] = {"tough": entry(stamina=9)}
    state["party"] = ["tough"]
    state["time_minutes"] = 12 * 60
    energy.set_hero_energy(state, "tough", 45)
    energy.sync(state)

    predicted = activities.treatment_forecast(state)["done_at"]
    for _ in range(60):
        if activities.rest_tick(state)["full"]:
            break
    assert state["roster"]["tough"]["energy"] == 145    # not 100
    assert state["time_minutes"] == predicted           # the quote was honest


def test_a_full_team_means_each_at_their_own_maximum():
    state = {"roster": {"tough": entry(stamina=9), "soft": entry()},
             "party": ["tough", "soft"]}
    energy.set_hero_energy(state, "soft", 100)
    energy.set_hero_energy(state, "tough", 100)         # full for soft, not tough
    assert not energy.team_is_full(state)
    energy.set_hero_energy(state, "tough", 145)
    assert energy.team_is_full(state)


# --- note 2: a rank-up restores the hero ---------------------------------

def test_a_rank_up_restores_energy_and_health():
    e = entry()
    e["energy"], e["hp_fraction"] = 12, 0.15

    attrs.add_training_xp({}, e, "strength", attrs.xp_for_rank(1))

    assert e["trained_ranks"]["strength"] == 1
    assert e["energy"] == energy.max_for(e)
    assert e["hp_fraction"] == 1.0


def test_xp_that_does_not_rank_you_up_restores_nothing():
    e = entry()
    e["energy"], e["hp_fraction"] = 12, 0.15
    attrs.add_training_xp({}, e, "strength", attrs.xp_for_rank(1) - 1)
    assert (e["energy"], e["hp_fraction"]) == (12, 0.15)
    assert not e.get("leveled_up")


def test_a_stamina_rank_up_restores_to_the_NEW_ceiling():
    """The rank that raised the tank is the one that fills it."""
    e = entry()
    e["energy"] = 12
    attrs.add_training_xp({}, e, "stamina", attrs.xp_for_rank(1))
    assert e["energy"] == config.DAILY_ENERGY + config.ENERGY_PER_STAMINA_RANK


def test_a_rank_up_from_the_field_restores_too(content):
    """Not just the rack — award_battle_xp goes through the same door."""
    e = entry()
    e["energy"], e["hp_fraction"] = 5, 0.05
    attrs.award_battle_xp({}, e, attrs.xp_for_rank(1) * 6)
    assert e.get("leveled_up") and e["hp_fraction"] == 1.0


# --- note 1: the chime ----------------------------------------------------

def test_a_level_up_chimes_once_however_many_ranks_landed(content, monkeypatch):
    scene, app = tower.HubScene(content), FakeApp(content)
    state = app.game_state
    played = []
    monkeypatch.setattr(audio, "play", played.append)

    attrs.add_training_xp({}, state["roster"]["iron_man"], "strength",
                          attrs.xp_for_rank(1))
    attrs.add_training_xp({}, state["roster"]["captain_america"], "speed",
                          attrs.xp_for_rank(1))
    scene._announce_level_ups(state)

    assert played == ["level_up"]                       # one chime, not two
    assert sum("levels up" in m for m in scene.messages) == 2
    scene._announce_level_ups(state)
    assert played == ["level_up"]                       # and never again


def test_nothing_chimes_when_nothing_happened(content, monkeypatch):
    scene, app = tower.HubScene(content), FakeApp(content)
    played = []
    monkeypatch.setattr(audio, "play", played.append)
    scene._announce_level_ups(app.game_state)
    assert played == []


# --- notes 4/5: they come and tell you ------------------------------------

def test_finishing_training_puts_the_hero_on_screen(content):
    state = save.new_game_state()
    for hero_id in ("iron_man", "captain_america"):
        state["roster"][hero_id] = entry()
    state["party"] = ["iron_man", "captain_america"]
    state["credits"] = 5000
    activities.start_training(state, content, "captain_america", "strength")
    state["time_minutes"] += 50 * config.TRAINING_LOCKOUT_MULT

    activities.finish_due_training(state, content)

    scene = (state.get("pending_scenes") or [None])[0]
    assert scene is not None, "no dialogue box queued"
    assert scene["character"] == "captain_america"
    assert scene["sound"] == "training_done"
    assert scene["lines"] and scene["lines"][0]


def test_finishing_an_assignment_puts_the_hero_on_screen(content):
    state = save.new_game_state()
    for hero_id in ("iron_man", "captain_america", "thor"):
        state["roster"][hero_id] = entry()
    state["party"] = ["iron_man", "captain_america", "thor"]
    task = next(t for t in content["assignments"] if t["id"] == "sweep_hangar")
    ok, message = dispatch.send(content, state, task, ["thor"])
    assert ok, message

    for _ in range(task["days"]):
        dispatch.process_day(content, state)

    scene = (state.get("pending_scenes") or [None])[0]
    assert scene is not None, "no dialogue box queued"
    assert scene["character"] == "thor"
    assert scene["sound"] == "assignment_done"


def test_every_hero_has_something_to_say_when_they_are_done(content):
    """A new recruit must never report in silently."""
    for pool in ("training_done", "assignment_done"):
        lines = content["flavor"][pool]
        assert lines.get("default"), pool
        for hero_id in ("iron_man", "captain_america", "ant_man", "thor",
                        "hulk"):
            assert lines.get(hero_id), f"{pool}/{hero_id}"


def test_report_in_is_silent_for_a_pool_that_does_not_exist(content):
    state = save.new_game_state()
    state["roster"]["iron_man"] = entry()
    activities.report_in(state, content, "iron_man", "no_such_pool", "x")
    assert not state.get("pending_scenes")


# --- the sounds themselves -----------------------------------------------

@pytest.mark.parametrize("name", ["level_up", "training_done",
                                  "assignment_done", "thunder"])
def test_every_sound_renders_to_real_samples(name):
    raw = audio.GENERATORS[name](22050, 2)
    assert len(raw) > 1000
    assert len(raw) % 4 == 0            # 16-bit, 2 channels


def test_the_level_up_chime_is_not_a_sharp_one():
    """It fires constantly, so it eases in rather than clicking. A hard
    transient that is pleasant once is a hazard by the fiftieth time."""
    import array

    raw = audio.GENERATORS["level_up"](22050, 1)
    samples = array.array("h")
    samples.frombytes(raw)
    assert abs(samples[0]) < 200, "the attack must not start at full swing"
    peak = max(abs(s) for s in samples)
    ramp = max(abs(s) for s in samples[:120])
    assert ramp < peak * 0.6, "too abrupt an onset"


def test_a_dead_mixer_never_breaks_anything(monkeypatch):
    """Sound is entirely optional — the M17 rule."""
    monkeypatch.setattr(audio, "_mixer", lambda: None)
    for name in ("level_up", "training_done", "assignment_done", None, "nope"):
        audio.play(name)                # must not raise
