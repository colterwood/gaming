"""M20: squad caps by party size, board-read gating, card readability
fixes, and old saves surviving an update."""

import random

import pygame
import pytest

from game import config, data_loader
from game.core import save
from game.core.state_machine import GameState
from game.hub import activities, dispatch, field
from game.hub.tower import HubScene
from game.progression import attributes as attrs
from game.ui import sprites

from tests.test_tower_scene import FakeApp, put_player_at


@pytest.fixture(scope="module")
def content():
    pygame.init()
    return data_loader.load_all()


# --- squad caps (3) ---

@pytest.mark.parametrize("party_size,cap", [(1, 4), (2, 6), (3, 8), (4, 8)])
def test_squad_cap_by_party_size(party_size, cap):
    assert field.squad_cap(party_size) == cap


def test_no_squad_of_any_kind_exceeds_the_cap():
    rng = random.Random(3)
    for party_size in (1, 2, 3, 4):
        cap = field.squad_cap(party_size)
        for _ in range(500):
            assert len(field.trap_squad(3, party_size, rng)) <= cap
            assert field.ambush_size(party_size, rng) <= cap
            rolled = field.roll_ambush(3, party_size, rng)
            assert rolled is None or len(rolled) <= cap


def test_a_lone_hero_can_no_longer_open_a_crate_onto_eight(content):
    # The reported case: trap_squad ignored party size entirely.
    rng = random.Random(9)
    sizes = {len(field.trap_squad(3, 1, rng)) for _ in range(500)}
    assert max(sizes) == 4
    assert 8 not in sizes


def test_a_trap_in_the_field_uses_the_real_party_size(content):
    scene, app = HubScene(content), FakeApp(content)
    state = app.game_state
    state["party"] = ["iron_man"]                   # solo
    scene.area = "docks"
    scene.rng = random.Random(1)
    sprung = []
    app.start_battle = lambda enemy_ids=None, quest=None, ambush=False: (
        sprung.append(list(enemy_ids)))
    for x, y in ((3, 3), (3, 4), (4, 4), (17, 4), (17, 5), (5, 9), (5, 10)):
        scene.rng = random.Random(x * 31 + y)
        scene._search_crate(app, x, y)
    assert sprung, "no trap fired on these seeds"
    for squad in sprung:
        assert len(squad) <= field.squad_cap(1) == 4


# --- board must be read in person (6) ---

def test_the_board_is_unread_until_someone_walks_up_to_it(content):
    scene, app = HubScene(content), FakeApp(content)
    state = app.game_state
    assert not activities.board_checked_today(state)
    put_player_at(scene, 34, 12)                    # beside the board
    scene.handle_key(app, pygame.K_RETURN)
    assert activities.board_checked_today(state)


def test_reading_the_board_only_counts_for_today(content):
    state = FakeApp(content).game_state
    activities.check_board(state)
    assert activities.board_checked_today(state)
    state["day"] += 1
    assert not activities.board_checked_today(state)
    activities.check_board(state)
    state["issue"] += 1                             # and across an issue roll
    assert not activities.board_checked_today(state)


def test_the_board_title_no_longer_advertises_the_tier(content):
    scene, app = HubScene(content), FakeApp(content)
    put_player_at(scene, 34, 12)
    scene.handle_key(app, pygame.K_RETURN)
    assert scene.submenu["title"].startswith("Assignment Board")


# --- card readability (2, 4, 5, 7) ---

def _render_card(content, hero_id):
    """Draw one hero's card to a surface and return its raw pixels. Text is
    queued by pixelkit rather than blitted, so this is only what's painted."""
    from game.ui import pixelkit
    from game.ui.impel_card import ImpelCardScene

    state = save.new_game_state()
    for hid in ("iron_man", "captain_america"):
        state["roster"][hid] = {"trained_ranks": {}, "attribute_xp": {},
                                "perks": [], "perk_choices": {}, "gear": {},
                                "ult_charge": 0, "energy": 100,
                                "unspent_xp": 0}
    state["party"] = ["iron_man", "captain_america"]
    app = FakeApp(content)
    app.game_state = state
    app.SAVE_SLOT = 1
    card = ImpelCardScene(content)
    card.hero_index = card._hero_ids(state).index(hero_id)
    surface = pygame.Surface((config.WIDTH, config.HEIGHT))
    surface.fill((0, 0, 0))
    card.draw(surface, app)
    pixelkit.drop_queued_text()
    return pygame.image.tobytes(surface, "RGB")


def test_the_power_grid_no_longer_paints_the_boost(content, monkeypatch):
    # Iron Man is Strength/Speed boost 6 at rank 1, and the old grid
    # extended his bars with a gold band that read as "he IS that level".
    # Nothing drawn on the card may depend on the boost table any more, so
    # zeroing it out must not change a single pixel. (The +N marker is
    # text, which pixelkit defers rather than blits.)
    real = _render_card(content, "iron_man")
    monkeypatch.setitem(content["characters"]["iron_man"], "boosts",
                        {a: 0 for a in config.ATTRIBUTES})
    zeroed = _render_card(content, "iron_man")
    assert real == zeroed


def test_xp_line_shows_progress_over_the_next_rank(content):
    entry = {"trained_ranks": {}, "attribute_xp": {"strength": 40},
             "perks": [], "perk_choices": {}, "gear": {}, "ult_charge": 0,
             "energy": 100, "unspent_xp": 0}
    boosts = content["characters"]["captain_america"]["boosts"]
    need = attrs.xp_for_rank(attrs.rank(entry, "strength"))
    assert need > 0
    # what the card composes: got/need, not a bare running total
    assert f"STR {entry['attribute_xp']['strength']}/{need}" == f"STR 40/{need}"


def test_avengers_pips_are_lit_and_dark(content):
    lit = sprites.avengers_pip(True)
    dark = sprites.avengers_pip(False)
    assert lit.get_size() == dark.get_size()
    blue = pygame.Color(config.PIXEL_PALETTE["blue"])[:3]
    grey = pygame.Color(config.PIXEL_PALETTE["grey_dark"])[:3]
    lit_px = [lit.get_at((x, y))[:3] for x in range(lit.get_width())
              for y in range(lit.get_height()) if lit.get_at((x, y)).a]
    dark_px = [dark.get_at((x, y))[:3] for x in range(dark.get_width())
               for y in range(dark.get_height()) if dark.get_at((x, y)).a]
    assert blue in lit_px and grey not in lit_px
    assert dark_px and set(dark_px) == {grey}
    assert len(lit_px) == len(dark_px)      # same shape, different colour


def test_ten_pips_fit_the_social_row(content):
    pip = sprites.avengers_pip(True)
    assert config.BOND_LEVEL_MAX == 10
    assert (pip.get_width() + 1) * config.BOND_LEVEL_MAX < 130


# --- old saves keep working (the update question) ---

LEGACY_SAVE = {          # the M16-era shape, before unlocks/inventory slots
    "day": 14, "issue": 1, "time_minutes": 600, "energy": 70,
    "path": "avengers",
    "roster": {
        "iron_man": {"trained_ranks": {"strength": 2}, "attribute_xp": {},
                     "perks": [], "perk_choices": {}, "gear": {},
                     "ult_charge": 40, "energy": 70, "unspent_xp": 130},
        "captain_america": {"trained_ranks": {}, "attribute_xp": {},
                            "perks": [], "perk_choices": {}, "gear": {},
                            "ult_charge": 0, "energy": 90, "unspent_xp": 0},
        "ant_man": {"trained_ranks": {}, "attribute_xp": {}, "perks": [],
                    "perk_choices": {}, "gear": {}, "ult_charge": 0,
                    "energy": 100, "unspent_xp": 0},
    },
    "party": ["iron_man", "captain_america", "ant_man"],
    "bonds": {"coulson": {"points": 300, "talked_today": False,
                          "gift_days": [], "last_gift": None}},
    "inventory": {"med_kit": 2, "shawarma": 1},
    "credits": 640,
    "story_flags": {"training_upgraded": True, "hulk_arrived": True},
    "quests": {"ch1_shattered_shield": {"name": "Shattered Shield",
                                        "status": "done"},
               "ch2_cell_hunt": {"name": "Cell Hunt", "status": "active"}},
    "dispatches": [], "completed_tasks": [], "searched_today": [],
    "unspent_xp": 0,
}


def test_a_pre_update_save_still_loads_and_plays(content, monkeypatch, tmp_path):
    """No key added since M16 may be REQUIRED to load an older save."""
    from game.__main__ import App
    from game.core import inventory

    monkeypatch.setattr(config, "SAVE_DIR", str(tmp_path))
    save.save_game(dict(LEGACY_SAVE), 1, save_dir=str(tmp_path))

    app = App()
    assert app.load_game() is True
    state = app.game_state
    # nothing lost
    assert state["day"] == 14 and state["credits"] == 640
    assert sorted(state["roster"]) == ["ant_man", "captain_america", "iron_man"]
    assert state["roster"]["iron_man"]["trained_ranks"]["strength"] == 2
    assert state["bonds"]["coulson"]["points"] == 300
    # ...and every system added since M16 copes with the keys being absent
    assert activities.board_checked_today(state) is False
    assert inventory.capacity(state) == 12
    assert inventory.slots_used(state) == 2
    assert state.get("unlocks", {}) == {}
    assert dispatch.roster_tier(content, state) >= 1
    for to in (GameState.TITLE, GameState.PATH_SELECT, GameState.HUB):
        app.machine.transition(to)
    app.hub._move = lambda dt, a: None
    app.hub.update(0.016, app)                  # a frame of real play
    app.go_to_sleep()                           # and a night
    assert state["day"] == 15
    reloaded = save.load_game(1, save_dir=str(tmp_path))
    assert reloaded["day"] == 15
