"""M19: message-log scrollback — keep LOG_HISTORY_MAX lines and page back
through them so a message that scrolled by is still readable."""

import pygame
import pytest

from game import config, data_loader
from game.hub.tower import HubScene

from tests.test_tower_scene import FakeApp


@pytest.fixture(scope="module")
def content():
    pygame.init()
    return data_loader.load_all()


def scene_with_lines(content, count):
    scene = HubScene(content)
    for i in range(count):
        scene.log(f"message {i}")
    return scene


def test_history_keeps_the_last_twelve(content):
    scene = scene_with_lines(content, 20)
    assert len(scene.messages) == config.LOG_HISTORY_MAX == 12
    assert scene.messages[0] == "message 8"     # oldest survivor
    assert scene.messages[-1] == "message 19"


def test_window_shows_the_newest_three(content):
    scene = scene_with_lines(content, 12)
    lines, older, newer = scene.visible_log()
    assert lines == ["message 9", "message 10", "message 11"]
    assert (older, newer) == (9, 0)


def test_paging_back_walks_the_history(content):
    scene = scene_with_lines(content, 12)
    scene.scroll_log(1)
    assert scene.visible_log()[0] == ["message 6", "message 7", "message 8"]
    scene.scroll_log(1)
    assert scene.visible_log()[0] == ["message 3", "message 4", "message 5"]
    scene.scroll_log(1)
    lines, older, newer = scene.visible_log()
    assert lines == ["message 0", "message 1", "message 2"]
    assert (older, newer) == (0, 9)             # top of the history
    scene.scroll_log(1)                         # clamped, no wrap
    assert scene.visible_log()[0] == ["message 0", "message 1", "message 2"]


def test_paging_forward_returns_to_the_newest(content):
    scene = scene_with_lines(content, 12)
    scene.scroll_log(3)
    scene.scroll_log(-1)
    assert scene.visible_log()[0] == ["message 3", "message 4", "message 5"]
    scene.scroll_log(-5)                        # clamped at the bottom
    assert scene.log_scroll == 0
    assert scene.visible_log() == (["message 9", "message 10", "message 11"],
                                   9, 0)


def test_a_short_log_has_nothing_to_scroll(content):
    scene = scene_with_lines(content, 2)
    assert scene.scroll_log(1) == 0
    lines, older, newer = scene.visible_log()
    assert lines == ["message 0", "message 1"]
    assert (older, newer) == (0, 0)


def test_an_empty_log_is_harmless(content):
    scene = HubScene(content)
    assert scene.visible_log() == ([], 0, 0)
    assert scene.scroll_log(1) == 0


def test_a_new_message_snaps_back_to_the_newest(content):
    scene = scene_with_lines(content, 12)
    scene.scroll_log(2)
    assert scene.log_scroll == 6
    scene.log("something just happened")
    assert scene.log_scroll == 0
    assert scene.visible_log()[0][-1] == "something just happened"


def test_page_keys_scroll_in_the_walkable_world(content):
    scene, app = scene_with_lines(content, 12), FakeApp(content)
    scene.handle_key(app, pygame.K_PAGEUP)
    assert scene.log_scroll == config.LOG_VISIBLE_LINES
    scene.handle_key(app, pygame.K_PAGEDOWN)
    assert scene.log_scroll == 0


def test_page_keys_are_inert_inside_a_menu(content):
    # Up/Down already drive submenus; PgUp/PgDn must not scroll the log
    # out from under an open menu.
    scene, app = scene_with_lines(content, 12), FakeApp(content)
    scene._open_submenu("Test", [("a", False, None), ("b", False, None)])
    scene.handle_key(app, pygame.K_PAGEUP)
    assert scene.log_scroll == 0
    assert scene.mode == "submenu"


def test_the_collapse_message_survives_a_busy_night(content):
    # The reason this milestone exists: a 3-line log dropped the "why"
    # behind a pass-out under the wake-up messages.
    scene = HubScene(content)
    scene.log("The team drops where they stand. Case the Safehouse will "
              "have to be worked again.")
    for msg in ("You wake up groggy...", "Iron Man finishes training Speed",
                "Ant-Man returns from Sweep the Rail Yard: +120 cr",
                "New intel: Cell Hunt is back on the board."):
        scene.log(msg)
    assert any("drops where they stand" in m for m in scene.messages)
    scene.scroll_log(1)
    assert any("drops where they stand" in m for m in scene.visible_log()[0])
