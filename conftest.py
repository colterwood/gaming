# Root conftest so pytest puts the repo root on sys.path (makes `game` importable).

import pytest

from game import config


@pytest.fixture(autouse=True)
def _never_touch_the_real_save(tmp_path_factory, monkeypatch):
    """saves/slot_N.json is the player's game — no test may write it.

    App.autosave() and App.go_to_sleep() save the live slot, so any test
    that drives a real App would otherwise overwrite a real playthrough.
    Redirect the whole suite at a throwaway directory instead of relying
    on each test to remember (see also config.SAVE_DIR / GAME_SAVE_DIR,
    which does the same job for headless driver scripts).
    """
    monkeypatch.setattr(config, "SAVE_DIR",
                        str(tmp_path_factory.mktemp("saves")))
