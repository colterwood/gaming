import copy
import json

import pytest

from game import data_loader
from game.data_loader import DataError

MINIMAL_CHAR = {
    "id": "test_hero",
    "name": "Test Hero",
    "path": "avengers",
    "rarity": "common",
    # M15: heroes carry innate boosts (1..BOOST_MAX), not a flat grid
    "boosts": {"strength": 1, "speed": 2, "agility": 3,
               "stamina": 4, "durability": 5, "intelligence": 6},
    "abilities": [
        {"id": "punch", "name": "Punch", "type": "basic",
         "power": 10, "scales_with": "strength", "target": "single"},
    ],
    "gifts": {"loved": [], "liked": [], "disliked": [], "hated": []},
    "birthday": {"issue": 1, "day": 1},
    "synergies": [],
    "recruit": {"chapter": 1, "method": "story"},
}

MINIMAL_ENEMY = {
    "id": "test_enemy",
    "name": "Test Enemy",
    "power_grid": {"strength": 1, "speed": 1, "agility": 1,
                   "stamina": 1, "durability": 1, "intelligence": 1},
    "abilities": [
        {"id": "swipe", "name": "Swipe", "type": "basic",
         "power": 8, "scales_with": "strength", "target": "single"},
    ],
    "ai": "aggressive",
    "xp_reward": 10,
    "credit_reward": 5,
}


def _write_data_dir(tmp_path, chars=(), enemies=(), items=()):
    (tmp_path / "characters").mkdir()
    (tmp_path / "enemies").mkdir()
    for c in chars:
        (tmp_path / "characters" / f"{c['id']}.json").write_text(json.dumps(c))
    for e in enemies:
        (tmp_path / "enemies" / f"{e['id']}.json").write_text(json.dumps(e))
    (tmp_path / "items.json").write_text(json.dumps(list(items)))
    return str(tmp_path)


# --- The shipped content must load clean ---

def test_real_data_loads():
    content = data_loader.load_all()
    assert {"iron_man", "captain_america", "ant_man"} <= set(content["characters"])
    assert {"hydra_grunt", "hydra_siege_captain", "crossbones"} <= set(content["enemies"])
    assert "double_espresso" in content["items"]


def test_real_iron_man_matches_card_grid():
    # M15: the card-authentic ratings transcribed from the 1991 Impel Series
    # II scan (assets/reference/iron_man_13_back.jpg) are now his innate
    # BOOST table — everyone starts at rank 1 and trains up from there.
    chars = data_loader.load_characters()
    im = chars["iron_man"]
    assert im["boosts"] == {"strength": 6, "speed": 6, "agility": 3,
                            "stamina": 4, "durability": 5, "intelligence": 5}
    assert {a["type"] for a in im["abilities"]} == {"basic", "special", "ultimate"}


# --- Validation failures ---

def test_missing_field_raises(tmp_path):
    bad = copy.deepcopy(MINIMAL_CHAR)
    del bad["boosts"]
    d = _write_data_dir(tmp_path, chars=[bad])
    with pytest.raises(DataError, match="boosts"):
        data_loader.load_characters(d)


@pytest.mark.parametrize("rank", [-1, 8, "5", 3.5])
def test_out_of_range_boost_raises(tmp_path, rank):
    bad = copy.deepcopy(MINIMAL_CHAR)
    bad["boosts"]["strength"] = rank
    d = _write_data_dir(tmp_path, chars=[bad])
    with pytest.raises(DataError, match="strength"):
        data_loader.load_characters(d)


def test_zero_boost_is_legal(tmp_path):
    # M15: 0 means "no natural talent here" — a valid authoring choice even
    # though the card-derived roster has at least 1 everywhere.
    ok = copy.deepcopy(MINIMAL_CHAR)
    ok["boosts"]["strength"] = 0
    d = _write_data_dir(tmp_path, chars=[ok])
    assert data_loader.load_characters(d)["test_hero"]["boosts"]["strength"] == 0


def test_bad_ability_type_raises(tmp_path):
    bad = copy.deepcopy(MINIMAL_CHAR)
    bad["abilities"][0]["type"] = "mega"
    d = _write_data_dir(tmp_path, chars=[bad])
    with pytest.raises(DataError, match="basic|special|ultimate"):
        data_loader.load_characters(d)


def test_special_requires_cost(tmp_path):
    bad = copy.deepcopy(MINIMAL_CHAR)
    bad["abilities"].append({"id": "beam", "name": "Beam", "type": "special",
                             "power": 20, "scales_with": "intelligence", "target": "single"})
    d = _write_data_dir(tmp_path, chars=[bad])
    with pytest.raises(DataError, match="cost"):
        data_loader.load_characters(d)


def test_bad_enemy_ai_raises(tmp_path):
    bad = copy.deepcopy(MINIMAL_ENEMY)
    bad["ai"] = "berserk"
    d = _write_data_dir(tmp_path, enemies=[bad])
    with pytest.raises(DataError, match="ai"):
        data_loader.load_enemies(d)


def test_unknown_gift_id_fails_cross_check(tmp_path):
    bad = copy.deepcopy(MINIMAL_CHAR)
    bad["gifts"]["loved"] = ["nonexistent_thing"]
    d = _write_data_dir(tmp_path, chars=[bad], enemies=[MINIMAL_ENEMY])
    with pytest.raises(DataError, match="nonexistent_thing"):
        data_loader.load_all(d)


def test_unknown_synergy_partner_fails_cross_check(tmp_path):
    bad = copy.deepcopy(MINIMAL_CHAR)
    bad["synergies"] = [{"with": "ghost_rider", "name": "X",
                         "effect": {"crit_bonus": 1}, "requires_bond_level": 6}]
    d = _write_data_dir(tmp_path, chars=[bad], enemies=[MINIMAL_ENEMY])
    with pytest.raises(DataError, match="ghost_rider"):
        data_loader.load_all(d)


def test_invalid_json_raises(tmp_path):
    (tmp_path / "characters").mkdir()
    (tmp_path / "characters" / "broken.json").write_text("{not json")
    with pytest.raises(DataError, match="invalid JSON"):
        data_loader.load_characters(str(tmp_path))


def test_bool_rank_rejected(tmp_path):
    bad = copy.deepcopy(MINIMAL_CHAR)
    bad["boosts"]["strength"] = True       # bools satisfy isinstance(x, int)
    d = _write_data_dir(tmp_path, chars=[bad])
    with pytest.raises(DataError, match="strength"):
        data_loader.load_characters(d)


def test_non_dict_top_level_raises(tmp_path):
    (tmp_path / "characters").mkdir()
    (tmp_path / "characters" / "weird.json").write_text("42")
    with pytest.raises(DataError, match="top-level"):
        data_loader.load_characters(str(tmp_path))


def test_non_list_items_top_level_raises(tmp_path):
    (tmp_path / "items.json").write_text('{"id": "x"}')
    with pytest.raises(DataError, match="top-level"):
        data_loader.load_items(str(tmp_path))


def test_string_ability_entry_raises(tmp_path):
    bad = copy.deepcopy(MINIMAL_CHAR)
    bad["abilities"] = ["punch"]
    d = _write_data_dir(tmp_path, chars=[bad])
    with pytest.raises(DataError, match="ability"):
        data_loader.load_characters(d)


def test_non_string_gift_entry_raises(tmp_path):
    bad = copy.deepcopy(MINIMAL_CHAR)
    bad["gifts"]["loved"] = [["oops"]]
    d = _write_data_dir(tmp_path, chars=[bad])
    with pytest.raises(DataError, match="loved"):
        data_loader.load_characters(d)


def test_bad_item_kind_raises(tmp_path):
    d = _write_data_dir(tmp_path, items=[{"id": "x", "name": "X", "kind": "potion",
                                          "price": 1, "sources": []}])
    with pytest.raises(DataError, match="kind"):
        data_loader.load_items(d)


def test_dialogue_noncanonical_tier_key_raises(tmp_path):
    # "04" would pass isdigit() but line_for indexes pools[str(int(k))] -> "4"
    (tmp_path / "dialogue.json").write_text(
        json.dumps({"someone": {"0": ["hi"], "04": ["later"]}}))
    with pytest.raises(DataError, match="canonical"):
        data_loader.load_dialogue(str(tmp_path))


def test_dialogue_unicode_digit_tier_key_raises(tmp_path):
    # "²" passes isdigit() but int() raises at talk time
    (tmp_path / "dialogue.json").write_text(
        json.dumps({"someone": {"0": ["hi"], "²": ["boom"]}}))
    with pytest.raises(DataError, match="canonical"):
        data_loader.load_dialogue(str(tmp_path))


def test_assignment_empty_requester_raises(tmp_path):
    (tmp_path / "quests").mkdir()
    task = {"id": "t", "name": "T", "credits": 10, "heroes": 1, "days": 1,
            "xp": 5, "tier": 1, "requested_by": "", "bond": 10}
    (tmp_path / "quests" / "assignments.json").write_text(json.dumps([task]))
    with pytest.raises(DataError, match="non-empty"):
        data_loader.load_assignments(str(tmp_path))
