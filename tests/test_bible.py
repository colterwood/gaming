"""docs/BIBLE.md is generated — this is what stops it drifting.

A reference document for a game this numeric is worse than useless once it
is stale, because it is confidently wrong. The generator reads config.py and
data/*.json, so the only way the file can lie is if somebody retunes a
constant and forgets to rebuild. This test is that reminder.

    python tools/build_bible.py
"""

import os
import runpy
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIBLE = os.path.join(ROOT, "docs", "BIBLE.md")
BUILDER = os.path.join(ROOT, "tools", "build_bible.py")


def test_the_bible_is_up_to_date(tmp_path):
    """Rebuild it into a scratch file and compare. If this fails, run
    `python tools/build_bible.py` and commit the result — the diff is a
    readable summary of what your balance change actually did."""
    assert os.path.exists(BIBLE), "docs/BIBLE.md is missing — run the builder"
    before = open(BIBLE, encoding="utf-8").read()

    result = subprocess.run([sys.executable, BUILDER], cwd=ROOT,
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    after = open(BIBLE, encoding="utf-8").read()

    if before != after:
        open(BIBLE, "w", encoding="utf-8").write(before)   # leave it as found
        pytest.fail("docs/BIBLE.md is out of date. Run "
                    "`python tools/build_bible.py` and commit the result.")


def test_the_bible_covers_every_tuned_constant():
    """Every number in config.py should be reachable from the document —
    either printed, or deliberately listed here as internal."""
    from game import config

    text = open(BIBLE, encoding="utf-8").read()
    # Rendering, palettes and layout are not game rules; the save dir and
    # slot count are covered in prose rather than by name.
    internal = {
        "WIDTH", "HEIGHT", "WINDOW_SCALE", "FPS", "TITLE", "PIXEL_PALETTE",
        "PALETTE", "CARD_PALETTE", "CARD_MARGIN", "CARD_HEADER_HEIGHT",
        "CARD_PORTRAIT_SIZE", "CARD_GRID_ROW_HEIGHT", "SAVE_DIR",
        "MAP_TILES_W", "MAP_TILES_H", "LOG_VISIBLE_LINES", "LOG_HISTORY_MAX",
        "ATTRIBUTES", "RANK_START", "TRAINED_MAX", "DAYS_PER_WEEK",
        "MEDBAY_REST_SECONDS_PER_TICK", "PASS_OUT_NEXT_DAY_ENERGY",
        "CLOSED_FLOORS_LOCK_OUT", "ROOM_HOURS", "ENERGY_BY_STAMINA_RANK",
        "GIFT_POINTS", "XP_TO_NEXT_RANK", "TRAINING_XP_BY_LEVEL",
        "TRAINING_MINUTES_BY_LEVEL", "TRAINING_CREDITS_BY_LEVEL",
        "ENEMY_XP_BY_LEVEL", "AMBUSH_SIZE_TABLE", "AMBUSH_MAX_BY_PARTY",
        "BOARD_TIER_POWER", "BOARD_TIER_XP_MULT", "GEAR_UPGRADE_CREDITS",
        "GEAR_UPGRADE_DAYS", "GEAR_UPGRADE_MATERIALS", "PERK_CHOICE_RANKS",
        "TRAINING_ENERGY_BASE", "TRAINING_ENERGY_PER_RANK",
        "SAVE_SLOTS", "ENEMY_RANK_MAX", "CRAFT_ENERGY", "CRAFT_MINUTES",
        "SEARCH_MINUTES", "SCOUT_MINUTES", "UNLOCK_SEARCH_MINUTES",
        "MINE_MINUTES", "FURNITURE_SEARCH_MINUTES", "REPAIR_PART_MINUTES",
        "TALK_GIFT_MINUTES", "EAT_MINUTES", "MISSION_MINUTES",
        "FURNITURE_SEARCH_CREDIT_CHANCE", "FURNITURE_SEARCH_CREDITS",
        "FURNITURE_SEARCH_ITEM_CHANCE", "INITIATIVE_ROLL",
        "TRAINING_XP_MULT_BASIC", "TRAINING_XP_MULT_UPGRADED",
        "TRAINING_XP_MULT_EVENT", "TICK_GAME_MINUTES", "TICK_REAL_SECONDS",
        "DAY_START_MINUTES", "DAY_END_MINUTES", "AMBUSH_TICK_SECONDS",
        "AMBUSH_BASE_CHANCE", "AMBUSH_PARTY_BONUS", "AMBUSH_MAX_SIZE",
        "SEARCH_TRAP_CHANCE", "PASS_OUT_ENERGY_FRACTION",
        "PASS_OUT_CREDIT_PCT", "PASS_OUT_CREDIT_MAX", "SLEEP_HP_FRACTION",
        "PASS_OUT_HP_FRACTION", "DEFEAT_HP_FRACTION", "MEDBAY_HP_PCT_PER_TICK",
        "KO_REVIVE_HP_FRACTION", "MEDBAY_ENERGY_PER_TICK", "GEAR_UPGRADE_STEP",
        "EN_PENALTY_THRESHOLD", "EN_PENALTY_STEP", "EN_PENALTY_INITIATIVE",
        "EN_PENALTY_MAX_TIERS", "KO_XP_MULT", "MISSION_FAIL_COOLDOWN_DAYS",
        "DISPATCH_POWER_BASELINE", "DISPATCH_POWER_BONUS",
        "DISPATCH_MULT_MIN", "DISPATCH_MULT_MAX", "PASSIVE_TRAIN_XP_PER_DAY",
        "BOND_GATE_SCENE", "BOND_GATE_RECRUIT", "BOND_GATE_SYNERGY",
        "BOND_GATE_GEAR", "BOND_GATE_SIGNATURE", "BOND_PERSONAL_QUEST_MIN",
        "BOND_PERSONAL_QUEST_MAX", "BOND_TALK_POINTS", "BOND_MISSION_POINTS",
        "BOND_POINTS_PER_LEVEL", "BOND_LEVEL_MAX", "BOND_LIFETIME_MAX",
        "BIRTHDAY_GIFT_MULTIPLIER", "GIFT_WINDOW_DAYS", "GIFTS_PER_WINDOW",
        "GIFT_REPEAT_PENALTY", "JARVIS_ENERGY_BONUS", "PEPPER_SHOP_DISCOUNT",
        "COULSON_CREDIT_MULT", "ATROPHY_GRACE_DAYS", "ATROPHY_XP_PER_DAY",
        "INVENTORY_SLOTS_PER_HERO", "INVENTORY_SLOTS_MAX",
        "INVENTORY_STACK_MAX", "MINE_ENERGY", "SCOUT_ENERGY",
        "UNLOCK_SEARCH_ENERGY", "REPAIR_PART_ENERGY", "MISSION_ENERGY",
        "TRAVEL_MINUTES", "MEDBAY_TICK_MINUTES", "BATTLE_MINUTES",
        "DEFEAT_RECOVERY_MINUTES", "DEFEAT_ENERGY", "DAILY_ENERGY",
        "ENERGY_PER_STAMINA_RANK", "ENLIGHTENMENT_ENERGY_BONUS",
        "ENLIGHTENMENT_XP", "AMBUSH_DAILY_CAP", "DAYS_PER_ISSUE",
        "RANK_MAX", "BOOST_MAX", "BOOST_RANK_VALUE", "BOOST_PCT",
        "PARTY_SIZE_MAX", "HP_BASE", "HP_PER_STAMINA", "HP_PER_DURABILITY",
        "BATTLE_ENERGY_BASE", "BATTLE_ENERGY_PER_INT",
        "INITIATIVE_SPEED_MULT", "BASIC_SCALING_MULT", "SPECIAL_SCALING_MULT",
        "DURABILITY_REDUCTION_MULT", "MIN_DAMAGE", "CRIT_PCT_PER_AGILITY",
        "CRIT_MULTIPLIER", "DODGE_PCT_PER_AGILITY", "ULT_CHARGE_PER_TURN",
        "ULT_CHARGE_PER_HIT", "ULT_CHARGE_MAX", "DEFEND_DAMAGE_MULT",
        "BURN_DAMAGE_PER_TURN", "BURN_TURNS", "STUN_TURNS",
        "AI_DEFENSIVE_HP_THRESHOLD", "AI_DEFENSIVE_LAST_STAND_HP",
        "AI_SUPPORT_HP_THRESHOLD", "GEAR_LEVEL_MAX", "TRAINING_LOCKOUT_MULT",
    }
    names = {n for n in dir(config) if n.isupper()}
    missing = sorted(names - internal)
    assert not missing, (
        f"new config constants not accounted for in the bible: {missing}. "
        f"Add them to a section of tools/build_bible.py, or to this test's "
        f"`internal` set if they are not game rules.")


@pytest.mark.parametrize("heading", [
    "## 1. The day", "## 2. Energy & health", "## 3. Progression",
    "## 4. Combat", "## 5. Heroes", "## 6. NPCs", "## 7. Enemies",
    "## 8. Items", "## 9. Gear", "## 10. The tower",
    "## 11. Tower repairs", "## 12. Zones & the field", "## 13. Story",
    "## 14. Side arcs", "## 15. The assignment board", "## 16. Bonds",
    "## 17. Calendar", "## 18. The save file",
])
def test_every_section_is_present(heading):
    assert heading in open(BIBLE, encoding="utf-8").read()


def test_every_hero_enemy_zone_and_item_is_named():
    from game import data_loader

    content = data_loader.load_all()
    text = open(BIBLE, encoding="utf-8").read()
    for group in ("characters", "enemies", "items", "zones"):
        for thing in content[group].values():
            assert thing["name"] in text, f"{group}: {thing['name']} missing"
    for job in content["repairs"]:
        assert job["name"] in text
    for quest in content["story"]:
        assert quest["name"] in text
    for task in content["assignments"]:
        assert task["name"] in text
