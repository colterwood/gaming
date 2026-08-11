"""M14: pause-card Social/Tasks lists shrink to fit and scroll instead of
overflowing the panel; Up/Down is repurposed to scroll on those tabs."""

import pygame
import pytest

from game import data_loader
from game.core import save
from game.ui import pixelkit
from game.ui.impel_card import TABS, ImpelCardScene


@pytest.fixture(scope="module")
def content():
    pygame.init()
    return data_loader.load_all()


def fresh_app(content):
    state = save.new_game_state()
    state["path"] = "avengers"
    for cid, c in content["characters"].items():
        if c["recruit"]["method"] == "starter":
            state["roster"][cid] = {"trained_ranks": {}, "attribute_xp": {},
                                    "perks": [], "perk_choices": {}, "gear": {},
                                    "ult_charge": 0, "energy": 100}
    state["party"] = sorted(state["roster"])

    class FakeApp:
        SAVE_SLOT = 1
        game_state = state

    return FakeApp()


def draw_all_tabs(scene, app):
    surface = pygame.Surface((640, 360))
    for i in range(len(TABS)):
        scene.tab_index = i
        pixelkit.drop_queued_text()
        scene.draw(surface, app)


def test_all_bondable_npcs_gift_no_overflow(content):
    # M14 regression: 4 bondable characters (Jarvis, Pepper, Coulson, Hulk)
    # must never overflow the panel — this is the bug from the screenshot.
    scene = ImpelCardScene(content)
    app = fresh_app(content)
    app.game_state["roster"]["hulk"] = {"trained_ranks": {}, "attribute_xp": {},
                                        "perks": [], "perk_choices": {},
                                        "gear": {}, "ult_charge": 0,
                                        "energy": 100}
    scene.tab_index = TABS.index("Social")
    draw_all_tabs(scene, app)   # must not raise
    assert scene.scroll["Social"] == 0   # all 4 fit — no scroll needed


def test_social_scrolls_with_up_down_and_clamps(content):
    # Force an overflow (more rows than the panel can show) directly against
    # _scroll_window, independent of exact pixel geometry.
    scene = ImpelCardScene(content)
    app = fresh_app(content)
    scene.tab_index = TABS.index("Social")
    for _ in range(10):
        scene.handle_key(app, pygame.K_DOWN)
    assert scene.scroll["Social"] == 10          # intent tracked pre-clamp
    first, more_above, more_below = scene._scroll_window("Social", total=20, visible=4)
    assert scene.scroll["Social"] == 10          # 10 is a valid offset here
    assert first == 10 and more_above and more_below
    # an offset past the end DOES clamp
    scene.scroll["Social"] = 999
    first, more_above, more_below = scene._scroll_window("Social", total=20, visible=4)
    assert first == 16 and scene.scroll["Social"] == 16
    assert more_above and not more_below
    scene.handle_key(app, pygame.K_UP)
    assert scene.scroll["Social"] == 15


def test_up_down_on_social_does_not_switch_hero(content):
    scene = ImpelCardScene(content)
    app = fresh_app(content)
    scene.tab_index = TABS.index("Social")
    before = scene.hero_index
    scene.handle_key(app, pygame.K_DOWN)
    assert scene.hero_index == before        # scrolled the list, not the hero


def test_up_down_on_attributes_still_switches_hero(content):
    scene = ImpelCardScene(content)
    app = fresh_app(content)
    scene.tab_index = TABS.index("Attributes")
    before = scene.hero_index
    scene.handle_key(app, pygame.K_DOWN)
    assert scene.hero_index != before


def test_tasks_board_scrolls_at_tier_3(content):
    # Tier 3 offers up to 6 tasks/day plus any active jobs — enough to
    # overflow the short lower panel without scrolling.
    scene = ImpelCardScene(content)
    app = fresh_app(content)
    for hid in ("ant_man", "hulk"):
        app.game_state["roster"][hid] = {"trained_ranks": {a: 7 for a in
                                          ("strength", "speed", "agility",
                                           "stamina", "durability", "intelligence")},
                                         "attribute_xp": {}, "perks": [],
                                         "perk_choices": {}, "gear": {},
                                         "ult_charge": 0, "energy": 100}
    scene.tab_index = TABS.index("Tasks")
    draw_all_tabs(scene, app)   # must not raise even with a long board
    for _ in range(10):
        scene.handle_key(app, pygame.K_DOWN)
    draw_all_tabs(scene, app)
    assert scene.scroll["Tasks"] >= 0        # clamped, drew without error


def test_fit_truncates_with_ellipsis():
    long_text = "A" * 200
    fitted = ImpelCardScene._fit(long_text, 60, size=11)
    assert fitted.endswith("...")
    assert pixelkit.font(11).size(fitted)[0] <= 60


def test_fit_leaves_short_text_untouched():
    assert ImpelCardScene._fit("short", 200, size=11) == "short"
