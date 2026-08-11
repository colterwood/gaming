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


def _validate_power_grid(grid, where):
    for attr in config.ATTRIBUTES:
        if attr not in grid:
            raise DataError(f"{where}: power_grid missing '{attr}'")
        rank = grid[attr]
        if not isinstance(rank, int) or isinstance(rank, bool) or not (1 <= rank <= config.RANK_MAX):
            raise DataError(f"{where}: power_grid.{attr} must be an int 1..{config.RANK_MAX}, got {rank!r}")
    extra = set(grid) - set(config.ATTRIBUTES)
    if extra:
        raise DataError(f"{where}: power_grid has unknown attributes {sorted(extra)}")


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
    if method != "npc":     # NPCs never fight: no grid/abilities required
        _validate_power_grid(_require(char, "power_grid", dict, where), where)
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
    _require(enemy, "xp_reward", int, where)
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
        raise DataError(f"calendar.json: top-level JSON must be an object")
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
        _require(task, "energy", int, tw)
        _require(task, "credits", int, tw)
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
        elif kind == "hub_task":
            _require(quest, "energy", int, qw)
        else:
            raise DataError(f"{qw}: kind must be battle|hub_task, got '{kind}'")
        if quest["id"] in seen:
            raise DataError(f"{qw}: duplicate id")
        seen.add(quest["id"])
    return story


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
        if zone["id"] in seen:
            raise DataError(f"{zw}: duplicate id")
        seen.add(zone["id"])
    return {z["id"]: z for z in zones}


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
    story = load_story(data_dir)
    zones = load_zones(data_dir)
    for quest in story:
        for enemy_id in quest.get("enemies", []):
            if enemy_id not in enemies:
                raise DataError(f"story.json '{quest['id']}': enemy '{enemy_id}' not found")
        if quest.get("recruit") and quest["recruit"] not in characters:
            raise DataError(f"story.json '{quest['id']}': recruit '{quest['recruit']}' not found")
        if quest["kind"] == "battle":
            if quest.get("location") and quest["location"] not in zones:
                raise DataError(f"story.json '{quest['id']}': zone '{quest['location']}' not found")
            if quest.get("deadline_days") is not None and (
                    not isinstance(quest["deadline_days"], int) or quest["deadline_days"] < 1):
                raise DataError(f"story.json '{quest['id']}': deadline_days must be a positive int")
    return {"characters": characters, "enemies": enemies, "items": items,
            "calendar": load_calendar(data_dir), "assignments": load_assignments(data_dir),
            "bond_scenes": bond_scenes, "perks": load_perks(data_dir), "story": story,
            "zones": zones, "passive": load_passive(data_dir)}
