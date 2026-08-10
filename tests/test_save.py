import os

from game.core import save


def test_empty_save_round_trip(tmp_path):
    state = save.new_game_state()
    save.save_game(state, 1, save_dir=str(tmp_path))
    assert save.slot_exists(1, save_dir=str(tmp_path))
    assert save.load_game(1, save_dir=str(tmp_path)) == state


def test_second_save_keeps_bak_of_previous(tmp_path):
    first = save.new_game_state()
    save.save_game(first, 1, save_dir=str(tmp_path))
    second = save.new_game_state()
    second["day"] = 2
    path = save.save_game(second, 1, save_dir=str(tmp_path))
    assert os.path.exists(path + ".bak")
    assert save.load_game(1, save_dir=str(tmp_path))["day"] == 2


def test_slots_are_independent(tmp_path):
    a = save.new_game_state()
    b = save.new_game_state()
    b["credits"] = 999
    save.save_game(a, 1, save_dir=str(tmp_path))
    save.save_game(b, 2, save_dir=str(tmp_path))
    assert save.load_game(1, save_dir=str(tmp_path))["credits"] == 0
    assert save.load_game(2, save_dir=str(tmp_path))["credits"] == 999


def test_missing_slot(tmp_path):
    assert not save.slot_exists(3, save_dir=str(tmp_path))
