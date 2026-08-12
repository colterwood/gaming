"""M28: save slots and the title menu — New Game / Load Game / Continue,
three independent games, and no slot overwritten without being asked.

conftest redirects config.SAVE_DIR at a temp directory for the whole
suite, so everything here reads and writes throwaway slots.
"""

import os

import pygame
import pytest

from game import config, data_loader
from game.core import save
from game.core.state_machine import GameState
from game.ui import screens


@pytest.fixture(scope="module")
def content():
    pygame.init()
    return data_loader.load_all()


@pytest.fixture
def app(content, monkeypatch, tmp_path):
    """A real App writing into its own directory."""
    from game.__main__ import App

    monkeypatch.setattr(config, "SAVE_DIR", str(tmp_path))
    monkeypatch.setattr(data_loader, "load_all", lambda: content)
    return App()


def _game(day=1, credits=0, heroes=("iron_man",)):
    state = save.new_game_state()
    state["day"] = day
    state["credits"] = credits
    state["roster"] = {h: {"trained_ranks": {}, "attribute_xp": {}} for h in heroes}
    return state


# --- what a slot says about itself (1) -----------------------------------

def test_slot_summary_reads_the_headline_numbers(tmp_path):
    save.save_game(_game(day=9, credits=2392, heroes=("iron_man", "thor")), 1,
                   save_dir=str(tmp_path))
    summary = save.slot_summary(1, save_dir=str(tmp_path))
    assert summary["slot"] == 1
    assert (summary["issue"], summary["day"]) == (1, 9)
    assert summary["credits"] == 2392
    assert summary["heroes"] == 2


def test_an_empty_slot_summarises_as_nothing(tmp_path):
    assert save.slot_summary(2, save_dir=str(tmp_path)) is None


def test_a_corrupt_slot_does_not_hide_the_others(tmp_path):
    # A half-written file must not take the load menu down with it.
    save.save_game(_game(), 1, save_dir=str(tmp_path))
    (tmp_path / "slot_2.json").write_text("{ this is not json", encoding="utf-8")
    assert save.slot_summary(2, save_dir=str(tmp_path)) is None
    assert save.slot_summary(1, save_dir=str(tmp_path)) is not None
    assert len(save.list_slots(save_dir=str(tmp_path))) == config.SAVE_SLOTS


def test_latest_slot_is_the_one_last_written(tmp_path):
    assert save.latest_slot(save_dir=str(tmp_path)) is None
    save.save_game(_game(), 1, save_dir=str(tmp_path))
    save.save_game(_game(), 3, save_dir=str(tmp_path))
    # mtime resolution is coarse on Windows — stamp them apart explicitly.
    os.utime(tmp_path / "slot_1.json", (1_000, 1_000))
    os.utime(tmp_path / "slot_3.json", (2_000, 2_000))
    assert save.latest_slot(save_dir=str(tmp_path)) == 3


# --- the title menu (2) ---------------------------------------------------

def _labels(menu):
    return [row[0] for row in menu.rows()]


def _row(menu, text):
    return next(r for r in menu.rows() if r[0].startswith(text))


def test_a_first_run_offers_no_continue_and_no_load(app):
    menu = app.title_menu()
    assert not any(l.startswith("Continue") for l in _labels(menu))
    assert _row(menu, "Load Game")[1] is True       # disabled
    assert _row(menu, "New Game")[1] is False


def test_continue_appears_once_a_game_is_saved(app):
    app.new_game(slot=2)
    app.autosave()
    menu = app.title_menu()
    assert _labels(menu)[0].startswith("Continue  -  Slot 2")
    assert _row(menu, "Load Game")[1] is False


def test_continue_loads_that_slot_and_lands_in_the_hub(app):
    app.new_game(slot=2)
    app.game_state["credits"] = 777
    app.autosave()

    fresh = type(app)()
    fresh.machine.transition(GameState.TITLE)
    menu = fresh.title_menu()
    menu.handle_key(fresh, pygame.K_RETURN)         # Continue is row 0

    assert fresh.machine.state is GameState.HUB
    assert fresh.SAVE_SLOT == 2
    assert fresh.game_state["credits"] == 777


def test_load_game_lists_every_slot_and_greys_out_the_empty_ones(app):
    app.new_game(slot=1)
    app.autosave()
    menu = app.title_menu()
    menu.activate(app, ("load", None))
    rows = menu.rows()
    assert len(rows) == config.SAVE_SLOTS + 1       # + Back
    assert rows[0][1] is False                      # slot 1 holds a game
    assert rows[1][1] is True                       # slot 2 is empty
    assert rows[0][0].startswith("Slot 1  -  Issue 1, Day 1")
    assert rows[1][0] == "Slot 2  -  empty"


# --- three games at once, and no silent overwrite (3) --------------------

def test_slots_do_not_bleed_into_each_other(app):
    app.new_game(slot=1)
    app.game_state["credits"] = 100
    app.autosave()

    app.new_game(slot=2)                            # a second, separate game
    app.game_state["credits"] = 999
    app.autosave()

    assert save.load_game(1)["credits"] == 100
    assert save.load_game(2)["credits"] == 999


def test_starting_a_new_game_in_an_occupied_slot_asks_first(app):
    app.new_game(slot=1)
    app.game_state["credits"] = 4242
    app.autosave()

    app.machine.transition(GameState.TITLE)
    menu = app.title_menu()
    menu.activate(app, ("new", None))
    menu.activate(app, ("pick", 1))

    assert menu.mode == "confirm"
    assert app.machine.state is GameState.TITLE     # went nowhere yet
    assert save.load_game(1)["credits"] == 4242     # and wrote nothing

    # The cursor starts on the harmless answer, not on the overwrite.
    assert menu.rows()[menu.index][0] == "No, go back"
    menu.handle_key(app, pygame.K_RETURN)
    assert menu.mode == "root"
    assert save.load_game(1)["credits"] == 4242


def test_confirming_the_overwrite_starts_a_new_game_in_that_slot(app):
    app.new_game(slot=1)
    app.autosave()
    app.machine.transition(GameState.TITLE)
    menu = app.title_menu()
    menu.activate(app, ("new", None))
    menu.activate(app, ("pick", 1))
    menu.activate(app, ("start", 1))

    assert app.pending_slot == 1
    assert app.machine.state is GameState.PATH_SELECT
    screens.handle_key(app, pygame.K_RETURN)        # choose the path
    assert app.machine.state is GameState.HUB
    assert app.SAVE_SLOT == 1
    assert app.game_state["day"] == 1


def test_an_empty_slot_needs_no_confirmation(app):
    app.machine.transition(GameState.TITLE)
    menu = app.title_menu()
    menu.activate(app, ("new", None))
    menu.activate(app, ("pick", 3))
    assert menu.mode == "root"
    assert app.pending_slot == 3
    assert app.machine.state is GameState.PATH_SELECT


def test_the_autosave_follows_the_slot_you_started_in(app):
    app.new_game(slot=3)
    app.game_state["credits"] = 55
    app.autosave()
    assert save.slot_exists(3) and not save.slot_exists(1)
    assert save.load_game(3)["credits"] == 55


# --- navigation (4) -------------------------------------------------------

def test_the_cursor_skips_rows_that_cannot_be_chosen(app):
    menu = app.title_menu()                         # no saves: Load disabled
    labels = _labels(menu)
    assert labels[menu.index] == "New Game"
    menu.handle_key(app, pygame.K_DOWN)             # Load Game is disabled...
    assert labels[menu.index] == "New Game"         # ...so we stay put


def test_escape_backs_out_of_the_slot_picker(app):
    menu = app.title_menu()
    menu.activate(app, ("new", None))
    assert menu.mode == "new"
    menu.handle_key(app, pygame.K_ESCAPE)
    assert menu.mode == "root"
