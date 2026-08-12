"""JSON content loading + schema validation (spec §5). Pure Python — no pygame.

Hand-rolled validation (no external schema dependency, per spec §2): every
error names the file and the offending field.
"""

import json
import os

from game import config

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


class DataError(Exception):
    pass


def _require(obj, key, kind, where):
    if key not in obj:
        raise DataError(f"{where}: missing required field '{key}'")
    value = obj[key]
    if kind is not None:
        # JSON true/false satisfies isinstance(x, int) in Python — reject it.
        if not isinstance(value, kind) or (kind is int and isinstance(value, bool)):
            raise DataError(f"{where}: field '{key}' must be {kind.__name__}, got {type(value).__name__}")
    return value


def _validate_grid(grid, where, field, low, high):
    for attr in config.ATTRIBUTES:
        if attr not in grid:
            raise DataError(f"{where}: {field} missing '{attr}'")
        rank = grid[attr]
        if not isinstance(rank, int) or isinstance(rank, bool) or not (low <= rank <= high):
            raise DataError(f"{where}: {field}.{attr} must be an int {low}..{high}, got {rank!r}")
    extra = set(grid) - set(config.ATTRIBUTES)
    if extra:
        raise DataError(f"{where}: {field} has unknown attributes {sorted(extra)}")


def _validate_power_grid(grid, where):
    """Enemies: a flat effective rank per attribute. Bosses are allowed
    above the hero ladder, up to ENEMY_RANK_MAX."""
    _validate_grid(grid, where, "power_grid", 1, config.ENEMY_RANK_MAX)


def _validate_boosts(grid, where):
    """Heroes (M15): innate talent 0..BOOST_MAX. Everyone starts at rank 1;
    the boost is what makes them feel like themselves. 0 is legal and means
    "no natural talent here" — the card-derived roster happens to have at
    least 1 everywhere, which is why 'any boost' gates never refuse them."""
    _validate_grid(grid, where, "boosts", 0, config.BOOST_MAX)


def _validate_abilities(abilities, where):
    if not abilities:
        raise DataError(f"{where}: needs at least one ability")
    for ab in abilities:
        if not isinstance(ab, dict):
            raise DataError(f"{where}: each ability must be an object, got {type(ab).__name__}")
        aw = f"{where} ability '{ab.get('id', '?')}'"
        _require(ab, "id", str, aw)
        _require(ab, "name", str, aw)
        ab_type = _require(ab, "type", str, aw)
        if ab_type not in ("basic", "special", "ultimate"):
            raise DataError(f"{aw}: type must be basic|special|ultimate, got '{ab_type}'")
        _require(ab, "power", int, aw)
        scales = _require(ab, "scales_with", str, aw)
        if scales not in config.ATTRIBUTES:
            raise DataError(f"{aw}: scales_with '{scales}' is not an attribute")
        target = _require(ab, "target", str, aw)
        if target not in ("single", "all"):
            raise DataError(f"{aw}: target must be single|all, got '{target}'")
        if ab_type == "special":
            _require(ab, "cost", int, aw)
        if ab_type == "ultimate":
            _require(ab, "charge_required", int, aw)
        spread = ab.get("spread")               # signature splash (M15)
        if spread is not None:
            if spread not in ("adjacent", "random", "random_range"):
                raise DataError(f"{aw}: spread must be adjacent|random|random_range, "
                                f"got '{spread}'")
            if target == "all":
                raise DataError(f"{aw}: spread is meaningless on an all-target ability")
            if spread == "random":
                if _require(ab, "extra_targets", int, aw) < 1:
                    raise DataError(f"{aw}: extra_targets must be >= 1")
            if spread == "random_range":
                low = _require(ab, "extra_min", int, aw)
                high = _require(ab, "extra_max", int, aw)
                if low < 1 or high < low:
                    raise DataError(f"{aw}: needs 1 <= extra_min <= extra_max")


RECRUIT_METHODS = ("starter", "story", "bond", "npc")


def _validate_character(char, where):
    _require(char, "id", str, where)
    _require(char, "name", str, where)
    _require(char, "path", str, where)
    _require(char, "rarity", str, where)
    recruit = _require(char, "recruit", dict, where)
    _require(recruit, "chapter", int, f"{where} recruit")
    method = _require(recruit, "method", str, f"{where} recruit")
    if method not in RECRUIT_METHODS:
        raise DataError(f"{where}: recruit.method must be one of {RECRUIT_METHODS}")
    if method == "bond":
        _require(recruit, "bond_level", int, f"{where} recruit")
    if method != "npc":     # NPCs never fight: no boosts/abilities required
        _validate_boosts(_require(char, "boosts", dict, where), where)
        _validate_abilities(_require(char, "abilities", list, where), where)
    gifts = _require(char, "gifts", dict, where)
    for category in ("loved", "liked", "disliked", "hated"):
        for gift_id in _require(gifts, category, list, f"{where} gifts"):
            if not isinstance(gift_id, str):
                raise DataError(f"{where}: gifts.{category} entries must be strings, got {gift_id!r}")
    birthday = _require(char, "birthday", dict, where)
    _require(birthday, "issue", int, f"{where} birthday")
    _require(birthday, "day", int, f"{where} birthday")
    synergies = char.get("synergies", [])
    if not isinstance(synergies, list):
        raise DataError(f"{where}: synergies must be a list, got {type(synergies).__name__}")
    for syn in synergies:
        sw = f"{where} synergy"
        if not isinstance(syn, dict):
            raise DataError(f"{sw}: each synergy must be an object, got {type(syn).__name__}")
        _require(syn, "with", str, sw)
        _require(syn, "name", str, sw)
        _require(syn, "effect", dict, sw)
        _require(syn, "requires_bond_level", int, sw)
    unlocks = char.get("bond_unlocks", [])
    if not isinstance(unlocks, list):
        raise DataError(f"{where}: bond_unlocks must be a list")
    for unlock in unlocks:
        uw = f"{where} bond_unlock"
        if not isinstance(unlock, dict):
            raise DataError(f"{uw}: each unlock must be an object")
        _require(unlock, "level", int, uw)
        _require(unlock, "flag", str, uw)
        _require(unlock, "message", str, uw)


def _validate_enemy(enemy, where):
    _require(enemy, "id", str, where)
    _require(enemy, "name", str, where)
    _validate_power_grid(_require(enemy, "power_grid", dict, where), where)
    _validate_abilities(_require(enemy, "abilities", list, where), where)
    ai = _require(enemy, "ai", str, where)
    if ai not in ("aggressive", "defensive", "support"):
        raise DataError(f"{where}: ai must be aggressive|defensive|support, got '{ai}'")
    level = _require(enemy, "level", int, where)        # XP tier (M16)
    if level not in config.ENEMY_XP_BY_LEVEL:
        raise DataError(f"{where}: level must be "
                        f"1..{max(config.ENEMY_XP_BY_LEVEL)}, got {level}")
    _require(enemy, "credit_reward", int, where)


ITEM_KINDS = ("gift", "consumable", "weapon", "armor", "accessory", "artifact", "material")


def _validate_item(item, where):
    _require(item, "id", str, where)
    _require(item, "name", str, where)
    kind = _require(item, "kind", str, where)
    if kind not in ITEM_KINDS:
        raise DataError(f"{where}: kind must be one of {ITEM_KINDS}, got '{kind}'")
    _require(item, "price", int, where)
    _require(item, "sources", list, where)
    if kind in ("weapon", "armor", "accessory"):
        _require(item, "slot", str, where)
        _require(item, "effects", dict, where)
    if "energy" in item:            # edible ration (M10)
        value = item["energy"]
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            raise DataError(f"{where}: 'energy' must be a positive int, got {value!r}")


def _load_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise DataError(f"{os.path.basename(path)}: invalid JSON — {e}") from e


def _load_dir(subdir, validator, data_dir):
    folder = os.path.join(data_dir, subdir)
    result = {}
    for fname in sorted(os.listdir(folder)):
        if not fname.endswith(".json"):
            continue
        obj = _load_json(os.path.join(folder, fname))
        if not isinstance(obj, dict):
            raise DataError(f"{fname}: top-level JSON must be an object, got {type(obj).__name__}")
        validator(obj, fname)
        if obj["id"] in result:
            raise DataError(f"{fname}: duplicate id '{obj['id']}'")
        result[obj["id"]] = obj
    return result


def load_characters(data_dir=None):
    return _load_dir("characters", _validate_character, data_dir or DATA_DIR)


def load_enemies(data_dir=None):
    return _load_dir("enemies", _validate_enemy, data_dir or DATA_DIR)


def load_items(data_dir=None):
    path = os.path.join(data_dir or DATA_DIR, "items.json")
    items = _load_json(path)
    if not isinstance(items, list):
        raise DataError(f"items.json: top-level JSON must be a list, got {type(items).__name__}")
    result = {}
    for item in items:
        if not isinstance(item, dict):
            raise DataError(f"items.json: each item must be an object, got {type(item).__name__}")
        _validate_item(item, "items.json")
        if item["id"] in result:
            raise DataError(f"items.json: duplicate id '{item['id']}'")
        result[item["id"]] = item
    return result


def load_calendar(data_dir=None):
    path = os.path.join(data_dir or DATA_DIR, "calendar.json")
    calendar = _load_json(path)
    if not isinstance(calendar, dict):
        raise DataError("calendar.json: top-level JSON must be an object")
    for issue in _require(calendar, "issues", list, "calendar.json"):
        _require(issue, "number", int, "calendar.json issue")
        _require(issue, "days", int, "calendar.json issue")
    for ev in _require(calendar, "events", list, "calendar.json"):
        ew = f"calendar.json event '{ev.get('id', '?')}'"
        _require(ev, "id", str, ew)
        _require(ev, "name", str, ew)
        _require(ev, "issue", int, ew)
        _require(ev, "start_day", int, ew)
        _require(ev, "end_day", int, ew)
        if ev["end_day"] < ev["start_day"]:
            raise DataError(f"{ew}: end_day before start_day")
    return calendar


def _validate_clause(clause, where):
    if not isinstance(clause, dict):
        raise DataError(f"{where}: each requirement clause must be an object")
    for attribute in clause.get("attributes", []):
        if attribute not in config.ATTRIBUTES:
            raise DataError(f"{where}: unknown attribute '{attribute}'")
    if not ({"min_rank", "min_boost"} & set(clause)):
        raise DataError(f"{where}: a clause needs min_rank and/or min_boost")
    rank_min = clause.get("min_rank", config.RANK_START)
    if not isinstance(rank_min, int) or not config.RANK_START <= rank_min <= config.RANK_MAX:
        raise DataError(f"{where}: min_rank must be "
                        f"{config.RANK_START}..{config.RANK_MAX}")
    boost_min = clause.get("min_boost", 0)
    if not isinstance(boost_min, int) or not 0 <= boost_min <= config.BOOST_MAX:
        raise DataError(f"{where}: min_boost must be 0..{config.BOOST_MAX}")


def _validate_task_requires(requires, where):
    """Hidden board-task gates (M15) — see game/hub/requirements.py."""
    if requires is None:
        return
    if not isinstance(requires, dict):
        raise DataError(f"{where}: requires must be an object")
    unknown = set(requires) - {"flag", "bond", "hero_any_of", "hero_all_attributes"}
    if unknown:
        raise DataError(f"{where}: unknown requires keys {sorted(unknown)}")
    if "flag" in requires and not isinstance(requires["flag"], str):
        raise DataError(f"{where}: requires.flag must be a string")
    bond_gate = requires.get("bond")
    if bond_gate is not None:
        _require(bond_gate, "character", str, f"{where} requires.bond")
        level = _require(bond_gate, "level", int, f"{where} requires.bond")
        if not 1 <= level <= config.BOND_LEVEL_MAX:
            raise DataError(f"{where}: requires.bond.level must be "
                            f"1..{config.BOND_LEVEL_MAX}")
    clauses = requires.get("hero_any_of")
    if clauses is not None:
        if not isinstance(clauses, list) or not clauses:
            raise DataError(f"{where}: hero_any_of must be a non-empty list")
        for clause in clauses:
            _validate_clause(clause, f"{where} hero_any_of")
    every = requires.get("hero_all_attributes")
    if every is not None:
        _validate_clause(every, f"{where} hero_all_attributes")


def load_assignments(data_dir=None):
    path = os.path.join(data_dir or DATA_DIR, "quests", "assignments.json")
    tasks = _load_json(path)
    if not isinstance(tasks, list):
        raise DataError("assignments.json: top-level JSON must be a list")
    seen = set()
    for task in tasks:
        if not isinstance(task, dict):
            raise DataError("assignments.json: each task must be an object")
        tw = f"assignments.json task '{task.get('id', '?')}'"
        _require(task, "id", str, tw)
        _require(task, "name", str, tw)
        _require(task, "credits", int, tw)
        heroes = _require(task, "heroes", int, tw)      # dispatch jobs (M10)
        if heroes < 1:
            raise DataError(f"{tw}: heroes must be >= 1")
        days = _require(task, "days", int, tw)
        if days < 1:
            raise DataError(f"{tw}: days must be >= 1")
        _require(task, "xp", int, tw)       # M24: PER ATTRIBUTE, not a total
        trains = task.get("trains")         # which attributes; absent = all six
        if trains is not None:
            if not isinstance(trains, list) or not trains:
                raise DataError(f"{tw}: trains must be a non-empty list")
            unknown = [a for a in trains if a not in config.ATTRIBUTES]
            if unknown:
                raise DataError(f"{tw}: trains has unknown attributes {unknown}")
            if len(set(trains)) != len(trains):
                raise DataError(f"{tw}: trains repeats an attribute")
        tier = _require(task, "tier", int, tw)          # board tiers (M11)
        if not 1 <= tier <= 3:
            raise DataError(f"{tw}: tier must be 1..3")
        if "requested_by" in task:                      # NPC requests (M11)
            _require(task, "requested_by", str, tw)
            if not task["requested_by"]:
                raise DataError(f"{tw}: requested_by must be non-empty")
            bond = _require(task, "bond", int, tw)
            if bond < 1:
                raise DataError(f"{tw}: bond must be >= 1")
        spot = _require(task, "spot", list, tw)         # work site (M13)
        if (len(spot) != 3 or not isinstance(spot[0], str)
                or not all(isinstance(v, int) and not isinstance(v, bool)
                           for v in spot[1:])):
            raise DataError(f"{tw}: spot must be [area, x, y]")
        _validate_task_requires(task.get("requires"), tw)    # M15
        posting = task.get("posting")                        # M16
        if posting is not None:
            if not isinstance(posting, dict):
                raise DataError(f"{tw}: posting must be an object")
            _require(posting, "bond_character", str, f"{tw} posting")
            ladder = _require(posting, "chance_by_bond_level", list,
                              f"{tw} posting")
            if not ladder or not all(isinstance(c, (int, float))
                                     and not isinstance(c, bool)
                                     and 0.0 <= c <= 1.0 for c in ladder):
                raise DataError(f"{tw}: posting.chance_by_bond_level must be "
                                f"a non-empty list of 0..1 chances")
        if task["id"] in seen:
            raise DataError(f"{tw}: duplicate id")
        seen.add(task["id"])
    return tasks


def load_bond_scenes(data_dir=None):
    path = os.path.join(data_dir or DATA_DIR, "quests", "bond_scenes.json")
    scenes = _load_json(path)
    if not isinstance(scenes, list):
        raise DataError("bond_scenes.json: top-level JSON must be a list")
    seen = set()
    for scene in scenes:
        if not isinstance(scene, dict):
            raise DataError("bond_scenes.json: each scene must be an object")
        sw = f"bond_scenes.json scene '{scene.get('id', '?')}'"
        _require(scene, "id", str, sw)
        _require(scene, "character", str, sw)
        _require(scene, "level", int, sw)
        _require(scene, "title", str, sw)
        lines = _require(scene, "lines", list, sw)
        if not lines or not all(isinstance(l, str) for l in lines):
            raise DataError(f"{sw}: lines must be a non-empty list of strings")
        if scene["id"] in seen:
            raise DataError(f"{sw}: duplicate id")
        seen.add(scene["id"])
    return scenes


PERK_EFFECT_KEYS = ("basic_damage_pct", "special_damage_pct", "crit_bonus",
                    "dodge_bonus", "max_hp_pct", "battle_energy_flat",
                    "ult_turn_charge_bonus")


def load_perks(data_dir=None):
    path = os.path.join(data_dir or DATA_DIR, "perks.json")
    perks = _load_json(path)
    if not isinstance(perks, dict):
        raise DataError("perks.json: top-level JSON must be an object")
    seen = set()
    for attr in config.ATTRIBUTES:
        if attr not in perks:
            raise DataError(f"perks.json: missing attribute '{attr}'")
        for tier in config.PERK_CHOICE_RANKS:
            options = perks[attr].get(str(tier))
            if not isinstance(options, list) or len(options) != 2:
                raise DataError(f"perks.json: {attr} tier {tier} needs exactly 2 options")
            for perk in options:
                pw = f"perks.json {attr}:{tier} perk '{perk.get('id', '?')}'"
                _require(perk, "id", str, pw)
                _require(perk, "name", str, pw)
                effect = _require(perk, "effect", dict, pw)
                for key in effect:
                    if key not in PERK_EFFECT_KEYS:
                        raise DataError(f"{pw}: unknown effect '{key}'")
                if perk["id"] in seen:
                    raise DataError(f"{pw}: duplicate id")
                seen.add(perk["id"])
    return perks


def load_story(data_dir=None):
    path = os.path.join(data_dir or DATA_DIR, "quests", "story.json")
    story = _load_json(path)
    if not isinstance(story, list):
        raise DataError("story.json: top-level JSON must be a list")
    seen = set()
    for quest in story:
        if not isinstance(quest, dict):
            raise DataError("story.json: each quest must be an object")
        qw = f"story.json quest '{quest.get('id', '?')}'"
        _require(quest, "id", str, qw)
        _require(quest, "chapter", int, qw)
        _require(quest, "name", str, qw)
        _require(quest, "desc", str, qw)
        kind = _require(quest, "kind", str, qw)
        if kind == "battle":
            enemies = _require(quest, "enemies", list, qw)
            if not enemies or not all(isinstance(e, str) for e in enemies):
                raise DataError(f"{qw}: enemies must be a non-empty list of ids")
        elif kind == "scout":                           # field work (M13)
            _require(quest, "location", str, qw)
            points = _require(quest, "scout_points", list, qw)
            if not points or not all(
                    isinstance(p, list) and len(p) == 2
                    and all(isinstance(v, int) for v in p) for p in points):
                raise DataError(f"{qw}: scout_points must be a non-empty "
                                f"list of [x, y]")
        else:
            raise DataError(f"{qw}: kind must be battle|scout, got '{kind}'")
        if quest["id"] in seen:
            raise DataError(f"{qw}: duplicate id")
        seen.add(quest["id"])
    return story


def _validate_scene(scene, where):
    """A queued cutscene (M17): title + lines, optional portrait and sound."""
    if scene is None:
        return
    if not isinstance(scene, dict):
        raise DataError(f"{where}: must be an object")
    _require(scene, "title", str, where)
    lines = _require(scene, "lines", list, where)
    if not lines or not all(isinstance(l, str) and l for l in lines):
        raise DataError(f"{where}: lines must be a non-empty list of strings")
    for key in ("character", "sound"):
        if key in scene and not isinstance(scene[key], str):
            raise DataError(f"{where}: {key} must be a string")


def _validate_template(text, where, **sample):
    """Catch a typo'd {placeholder} at load time, not mid-playthrough."""
    try:
        text.format(**sample)
    except (KeyError, IndexError, ValueError) as e:
        raise DataError(f"{where}: bad message template — {e}") from e


UNLOCK_SCENES = ("signal_scene", "found_scene", "lift_scene", "arrival_scene")


def load_unlocks(data_dir=None):
    """Conditional side arcs (M17) — see game/hub/unlocks.py."""
    path = os.path.join(data_dir or DATA_DIR, "quests", "unlocks.json")
    arcs = _load_json(path)
    if not isinstance(arcs, list):
        raise DataError("unlocks.json: top-level JSON must be a list")
    seen = set()
    for arc in arcs:
        if not isinstance(arc, dict):
            raise DataError("unlocks.json: each arc must be an object")
        aw = f"unlocks.json arc '{arc.get('id', '?')}'"
        _require(arc, "id", str, aw)
        _require(arc, "name", str, aw)
        _require(arc, "desc", str, aw)
        _require(arc, "location", str, aw)
        _require(arc, "signal_message", str, aw)
        _require(arc, "arrival_message", str, aw)
        _validate_template(_require(arc, "empty_message", str, aw),
                           f"{aw} empty_message", grove="a grove")
        requires = arc.get("requires", {})
        if not isinstance(requires, dict):
            raise DataError(f"{aw}: requires must be an object")
        for flag in requires.get("flags", []):
            if not isinstance(flag, str):
                raise DataError(f"{aw}: requires.flags entries must be strings")
        for hero_id, min_rank in requires.get("hero_min_rank", {}).items():
            if (not isinstance(min_rank, int) or isinstance(min_rank, bool)
                    or not config.RANK_START <= min_rank <= config.RANK_MAX):
                raise DataError(f"{aw}: requires.hero_min_rank['{hero_id}'] must "
                                f"be {config.RANK_START}..{config.RANK_MAX}")
        groves = _require(arc, "search_groves", list, aw)
        if not groves:
            raise DataError(f"{aw}: search_groves must be non-empty")
        for grove in groves:
            gw = f"{aw} grove '{(grove or {}).get('name', '?') if isinstance(grove, dict) else '?'}'"
            if not isinstance(grove, dict):
                raise DataError(f"{gw}: each grove must be an object")
            _require(grove, "name", str, gw)
            tiles = _require(grove, "tiles", list, gw)
            if not tiles or not all(
                    isinstance(t, list) and len(t) == 2
                    and all(isinstance(v, int) and not isinstance(v, bool)
                            for v in t) for t in tiles):
                raise DataError(f"{gw}: tiles must be a non-empty list of [x, y]")
        if "lift_requires" in arc:
            _require(arc, "lift_requires", str, aw)
            _require(arc, "lift_refusal", str, aw)
        _validate_template(_require(arc, "lift_message", str, aw),
                           f"{aw} lift_message", hero="Someone")
        if "item" in arc:
            _require(arc, "item", str, aw)
        if "recruit" in arc:
            _require(arc, "recruit", str, aw)
        flags = arc.get("flags", {})
        if not isinstance(flags, dict):
            raise DataError(f"{aw}: flags must be an object")
        for key in UNLOCK_SCENES:
            _validate_scene(arc.get(key), f"{aw} {key}")
        if arc["id"] in seen:
            raise DataError(f"{aw}: duplicate id")
        seen.add(arc["id"])
    return arcs


# Every floor of the tower (M29 added the last three). Kept here so both
# assignment work-sites and repair parts are bounds-checked at load.
TOWER_FLOORS = ("common", "training", "ops", "med_bay", "tech_lab", "pym_lab")
# Station kinds a repair can be finished at — the same names tower.py maps
# its tiles to (tests/test_m29.py pins the two lists together).
REPAIR_STATIONS = ("elevator", "quinjet", "training", "medbay", "techlab",
                   "pymlab")


def load_repairs(data_dir=None):
    """Tower repair jobs (M29) — see game/hub/repairs.py."""
    path = os.path.join(data_dir or DATA_DIR, "quests", "repairs.json")
    jobs = _load_json(path)
    if not isinstance(jobs, list):
        raise DataError("repairs.json: top-level JSON must be a list")
    seen = set()
    for job in jobs:
        if not isinstance(job, dict):
            raise DataError("repairs.json: each job must be an object")
        jw = f"repairs.json job '{job.get('id', '?')}'"
        for key in ("id", "name", "desc", "flag", "done_message",
                    "part_label", "repair_label"):
            _require(job, key, str, jw)
        station = _require(job, "station", str, jw)
        if station not in REPAIR_STATIONS:
            raise DataError(f"{jw}: station must be one of {REPAIR_STATIONS}")
        floor = _require(job, "floor", str, jw)
        if floor not in TOWER_FLOORS:
            raise DataError(f"{jw}: floor '{floor}' is not a tower floor")
        parts = _require(job, "parts", list, jw)
        if not parts:
            raise DataError(f"{jw}: parts must be non-empty — a repair with "
                            f"nothing to find is just a button")
        for part in parts:
            if (not isinstance(part, list) or len(part) != 3
                    or not isinstance(part[0], str)
                    or not all(isinstance(v, int) and not isinstance(v, bool)
                               for v in part[1:])):
                raise DataError(f"{jw}: each part must be [floor, x, y]")
            if part[0] not in TOWER_FLOORS:
                raise DataError(f"{jw}: part floor '{part[0]}' is not a tower floor")
            if not (0 <= part[1] < config.MAP_TILES_W
                    and 0 <= part[2] < config.MAP_TILES_H):
                raise DataError(f"{jw}: part [{part[1]}, {part[2]}] is off the map")
        for key in ("credits", "xp"):
            if _require(job, key, int, jw) < 0:
                raise DataError(f"{jw}: {key} must be >= 0")
        requires = job.get("requires", {})
        if not isinstance(requires, dict):
            raise DataError(f"{jw}: requires must be an object")
        unknown = set(requires) - {"flags", "quests"}
        if unknown:
            raise DataError(f"{jw}: unknown requires keys {sorted(unknown)}")
        for key in ("flags", "quests"):
            values = requires.get(key, [])
            if not isinstance(values, list) or not all(
                    isinstance(v, str) for v in values):
                raise DataError(f"{jw}: requires.{key} must be a list of strings")
        _validate_scene(job.get("done_scene"), f"{jw} done_scene")
        if job["id"] in seen:
            raise DataError(f"{jw}: duplicate id")
        seen.add(job["id"])
    return jobs


def load_zones(data_dir=None):
    path = os.path.join(data_dir or DATA_DIR, "zones.json")
    zones = _load_json(path)
    if not isinstance(zones, list):
        raise DataError("zones.json: top-level JSON must be a list")
    seen = set()
    for zone in zones:
        if not isinstance(zone, dict):
            raise DataError("zones.json: each zone must be an object")
        zw = f"zones.json zone '{zone.get('id', '?')}'"
        _require(zone, "id", str, zw)
        _require(zone, "name", str, zw)
        danger = _require(zone, "danger", int, zw)
        if not 1 <= danger <= 3:
            raise DataError(f"{zw}: danger must be 1..3")
        zone_map = _require(zone, "map", list, zw)
        if not zone_map or not all(isinstance(r, str) for r in zone_map):
            raise DataError(f"{zw}: map must be a non-empty list of strings")
        for key in ("spawn", "target_spot"):
            point = _require(zone, key, list, zw)
            if len(point) != 2 or not all(isinstance(v, int) for v in point):
                raise DataError(f"{zw}: {key} must be [x, y]")
        loot = zone.get("loot")                         # search spots (M10)
        if loot is not None:
            if not isinstance(loot, dict):
                raise DataError(f"{zw}: loot must be an object")
            lo_hi = _require(loot, "credits", list, f"{zw} loot")
            if (len(lo_hi) != 2 or not all(isinstance(v, int) for v in lo_hi)
                    or lo_hi[0] > lo_hi[1] or lo_hi[0] < 0):
                raise DataError(f"{zw}: loot.credits must be [lo, hi] with 0 <= lo <= hi")
            for item_id in loot.get("items", []):
                if not isinstance(item_id, str):
                    raise DataError(f"{zw}: loot.items entries must be strings")
            for key in ("item_chance", "find_chance"):
                chance = loot.get(key, 0.0)
                if not isinstance(chance, (int, float)) or isinstance(chance, bool) \
                        or not 0.0 <= chance <= 1.0:
                    raise DataError(f"{zw}: loot.{key} must be 0..1")
        if zone["id"] in seen:
            raise DataError(f"{zw}: duplicate id")
        seen.add(zone["id"])
    return {z["id"]: z for z in zones}


def load_dialogue(data_dir=None):
    """Bond/story-tiered talk lines (M11): {char_id: {"0": [...], "2": [...]}}.
    Tier keys are the minimum bond level (or story stage for non-bonding
    teammates) at which the pool unlocks."""
    path = os.path.join(data_dir or DATA_DIR, "dialogue.json")
    dialogue = _load_json(path)
    if not isinstance(dialogue, dict):
        raise DataError("dialogue.json: top-level JSON must be an object")
    for char_id, pools in dialogue.items():
        dw = f"dialogue.json '{char_id}'"
        if not isinstance(pools, dict) or not pools:
            raise DataError(f"{dw}: must be a non-empty object of tier pools")
        for tier, lines in pools.items():
            # Canonical ASCII integers only: "04" would silently shadow "4"
            # and Unicode digits pass isdigit() but break int() at talk time.
            if not (tier.isascii() and tier.isdigit() and str(int(tier)) == tier):
                raise DataError(f"{dw}: tier keys must be canonical non-negative "
                                f"integers, got '{tier}'")
            if (not isinstance(lines, list) or not lines
                    or not all(isinstance(l, str) and l for l in lines)):
                raise DataError(f"{dw} tier {tier}: must be a non-empty list of strings")
        if "0" not in pools:
            raise DataError(f"{dw}: needs a tier '0' pool (the default lines)")
    return dialogue


def load_passive(data_dir=None):
    path = os.path.join(data_dir or DATA_DIR, "passive.json")
    passive = _load_json(path)
    if not isinstance(passive, dict):
        raise DataError("passive.json: top-level JSON must be an object")
    for kind, spec in passive.items():
        pw = f"passive.json '{kind}'"
        if not isinstance(spec, dict):
            raise DataError(f"{pw}: must be an object")
        _require(spec, "label", str, pw)
        requirement = spec.get("requires")
        if requirement is not None:
            _require(requirement, "attribute", str, pw)
            if requirement["attribute"] not in config.ATTRIBUTES:
                raise DataError(f"{pw}: unknown attribute in requires")
            _require(requirement, "min", int, pw)
    return passive


def load_all(data_dir=None):
    """Load and cross-validate all game content."""
    characters = load_characters(data_dir)
    enemies = load_enemies(data_dir)
    items = load_items(data_dir)
    # Cross-check: every gift id a character references must exist in items.json
    for char in characters.values():
        for category in ("loved", "liked", "disliked", "hated"):
            for gift_id in char["gifts"][category]:
                if gift_id not in items:
                    raise DataError(
                        f"{char['id']}: gift '{gift_id}' ({category}) not found in items.json")
    # Cross-check: synergy partners must exist
    for char in characters.values():
        for syn in char.get("synergies", []):
            if syn["with"] not in characters:
                raise DataError(f"{char['id']}: synergy partner '{syn['with']}' not found")
    bond_scenes = load_bond_scenes(data_dir)
    for scene in bond_scenes:
        if scene["character"] not in characters:
            raise DataError(f"bond_scenes.json: character '{scene['character']}' not found")
    assignments = load_assignments(data_dir)
    for task in assignments:
        requester = task.get("requested_by")
        if requester is None:
            continue
        if requester not in characters:
            raise DataError(
                f"assignments.json '{task['id']}': requested_by '{requester}' not found")
        if characters[requester]["recruit"]["method"] not in ("bond", "npc"):
            raise DataError(
                f"assignments.json '{task['id']}': requested_by '{requester}' "
                f"is not a bondable NPC — the bond reward would be invisible")
    for task in assignments:
        gate = (task.get("requires") or {}).get("bond")
        if gate and gate["character"] not in characters:
            raise DataError(f"assignments.json '{task['id']}': requires.bond "
                            f"character '{gate['character']}' not found")
        posting = task.get("posting")
        if posting and posting["bond_character"] not in characters:
            raise DataError(f"assignments.json '{task['id']}': posting "
                            f"character '{posting['bond_character']}' not found")
    dialogue = load_dialogue(data_dir)
    for char_id in dialogue:
        if char_id not in characters:
            raise DataError(f"dialogue.json: character '{char_id}' not found")
    story = load_story(data_dir)
    zones = load_zones(data_dir)
    for zone in zones.values():
        for item_id in zone.get("loot", {}).get("items", []):
            if item_id not in items:
                raise DataError(
                    f"zones.json '{zone['id']}': loot item '{item_id}' not found in items.json")
    for task in assignments:
        area, sx, sy = task["spot"]
        if area in TOWER_FLOORS:
            in_bounds = (0 <= sx < config.MAP_TILES_W
                         and 0 <= sy < config.MAP_TILES_H)
        elif area in zones:
            zone_map = zones[area]["map"]
            in_bounds = 0 <= sy < len(zone_map) and 0 <= sx < len(zone_map[sy])
        else:
            raise DataError(
                f"assignments.json '{task['id']}': spot area '{area}' is neither "
                f"a tower floor nor a zone")
        if not in_bounds:
            # An unreachable spot would make the hero unrecallable now that
            # recall is in-person only (M13).
            raise DataError(
                f"assignments.json '{task['id']}': spot [{sx}, {sy}] is outside "
                f"the '{area}' map")
    for quest in story:
        for enemy_id in quest.get("enemies", []):
            if enemy_id not in enemies:
                raise DataError(f"story.json '{quest['id']}': enemy '{enemy_id}' not found")
        if quest.get("recruit") and quest["recruit"] not in characters:
            raise DataError(f"story.json '{quest['id']}': recruit '{quest['recruit']}' not found")
        if quest["kind"] in ("battle", "scout"):
            if quest.get("location") and quest["location"] not in zones:
                raise DataError(f"story.json '{quest['id']}': zone '{quest['location']}' not found")
            if quest.get("deadline_days") is not None and (
                    not isinstance(quest["deadline_days"], int) or quest["deadline_days"] < 1):
                raise DataError(f"story.json '{quest['id']}': deadline_days must be a positive int")
        if quest["kind"] == "scout":
            zone_map = zones[quest["location"]]["map"]
            for x, y in quest["scout_points"]:
                if not (0 <= y < len(zone_map) and 0 <= x < len(zone_map[y])):
                    raise DataError(f"story.json '{quest['id']}': scout point "
                                    f"[{x}, {y}] is outside the zone map")
    repairs = load_repairs(data_dir)
    story_ids = {q["id"] for q in story}
    for job in repairs:
        jw = f"repairs.json '{job['id']}'"
        for quest_id in job.get("requires", {}).get("quests", []):
            # A repair gated on a quest that doesn't exist would never post,
            # and the tower could never finish being rebuilt.
            if quest_id not in story_ids:
                raise DataError(f"{jw}: requires.quests '{quest_id}' is not a "
                                f"story quest")
        scene_char = (job.get("done_scene") or {}).get("character")
        if scene_char and scene_char not in characters:
            raise DataError(f"{jw}: done_scene character '{scene_char}' not found")
    unlocks = load_unlocks(data_dir)
    for arc in unlocks:
        aw = f"unlocks.json '{arc['id']}'"
        if arc["location"] not in zones:
            raise DataError(f"{aw}: zone '{arc['location']}' not found")
        zone_map = zones[arc["location"]]["map"]
        for grove in arc["search_groves"]:
            for x, y in grove["tiles"]:
                # An off-map stand would be unreachable and the arc would
                # dead-end with the item un-findable.
                if not (0 <= y < len(zone_map) and 0 <= x < len(zone_map[y])):
                    raise DataError(f"{aw}: grove tile [{x}, {y}] is outside "
                                    f"the '{arc['location']}' map")
        if arc.get("item") and arc["item"] not in items:
            raise DataError(f"{aw}: item '{arc['item']}' not found in items.json")
        referenced = [arc.get("lift_requires"), arc.get("recruit")]
        referenced += list(arc.get("requires", {}).get("hero_min_rank", {}))
        referenced += [(arc.get(key) or {}).get("character")
                       for key in UNLOCK_SCENES]
        for char_id in referenced:
            if char_id and char_id not in characters:
                raise DataError(f"{aw}: character '{char_id}' not found")
    return {"characters": characters, "enemies": enemies, "items": items,
            "calendar": load_calendar(data_dir), "assignments": assignments,
            "bond_scenes": bond_scenes, "perks": load_perks(data_dir), "story": story,
            "zones": zones, "passive": load_passive(data_dir), "dialogue": dialogue,
            "unlocks": unlocks, "repairs": repairs}
