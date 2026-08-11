"""Conditional story unlocks (spec §9 M17). Pure Python — no pygame.

Side arcs that fire off story flags plus hero progress instead of taking a
slot in the sequential story.json chain — so an arc can sit dormant for
issues without stalling the HYDRA missions behind it. Content lives in
data/quests/unlocks.json.

An arc runs: requirements met -> a NIGHT SIGNAL fires at the sleep
boundary -> the team combs `search_groves` in the arc's zone -> the one
holding the item is found -> only `lift_requires` (who must be ON THE
TEAM) can pick it up -> the following morning the owner turns up at the
tower, joins, and sets the arc's flags.

Arc state lives in state["unlocks"][arc_id]:
    {"status": "searching" | "found" | "carried" | "done",
     "searched": [grove index, ...], "hidden": grove index, "day": abs day}

Cutscenes are queued onto state["pending_scenes"]; whatever scene is on
screen pops them (the hub does), so arcs never touch rendering.
"""

import zlib

from game import config
from game.core import clock, energy, inventory
from game.progression import attributes as attrs

ACTIVE = ("searching", "found")


def abs_day(state):
    return (state["issue"] - 1) * config.DAYS_PER_ISSUE + state["day"]


# ------------------------------------------------------------ scene queue

def queue_scene(state, scene):
    """Hand a cutscene to the hub. Queued scenes carry no id — they are
    one-shot story beats, not the bond scenes events.py tracks as seen."""
    if scene:
        state.setdefault("pending_scenes", []).append(dict(scene))


def pop_scene(state):
    queue = state.get("pending_scenes") or []
    return queue.pop(0) if queue else None


# ------------------------------------------------------------- arc state

def entry_of(state, arc):
    return state.get("unlocks", {}).get(arc["id"])


def status(state, arc):
    return (entry_of(state, arc) or {}).get("status")


def searched(state, arc):
    return (entry_of(state, arc) or {}).get("searched", [])


def is_active(state, arc):
    return status(state, arc) in ACTIVE


def active_arcs(content, state, location=None):
    """Arcs currently being worked, optionally filtered to one zone."""
    return [arc for arc in content["unlocks"]
            if is_active(state, arc)
            and (location is None or arc.get("location") == location)]


def requirements_met(content, state, arc):
    """Story flags plus a per-hero floor across ALL six attributes (Cap has
    to be a rounded-out level 2 before the sky opens up, not level 2 in one
    thing). A hero who isn't on the roster can never satisfy their clause."""
    requires = arc.get("requires", {})
    flags = state.get("story_flags", {})
    if not all(flags.get(flag) for flag in requires.get("flags", [])):
        return False
    for hero_id, min_rank in requires.get("hero_min_rank", {}).items():
        roster_entry = state.get("roster", {}).get(hero_id)
        if roster_entry is None:
            return False
        if any(attrs.rank(roster_entry, a) < min_rank
               for a in config.ATTRIBUTES):
            return False
    return True


def _hidden_grove(state, arc, day):
    """Which stand hides the item. A stable crc32 roll (M16 convention) so
    reloading the save never moves it."""
    key = f"{arc['id']}:{state['issue']}:{day}".encode()
    return zlib.crc32(key) % len(arc["search_groves"])


# ---------------------------------------------------------- night events

def process_night(content, state):
    """Run at the sleep boundary AFTER the calendar advances: fire any arc
    whose requirements have come true, and land the morning arrival of one
    that is already carried home. Returns log messages."""
    messages = []
    for arc in content["unlocks"]:
        entry = entry_of(state, arc)
        if entry is None:
            if requirements_met(content, state, arc):
                messages += _fire_signal(state, arc)
        elif entry.get("status") == "carried":
            messages += _arrive(content, state, arc)
    return messages


def _fire_signal(state, arc):
    today = abs_day(state)
    state.setdefault("unlocks", {})[arc["id"]] = {
        "status": "searching", "searched": [],
        "hidden": _hidden_grove(state, arc, today), "day": today}
    queue_scene(state, arc.get("signal_scene"))
    return [arc["signal_message"]]


def _arrive(content, state, arc):
    """The morning after the item comes home: its owner is in the tower."""
    entry = state["unlocks"][arc["id"]]
    entry["status"] = "done"
    queue_scene(state, arc.get("arrival_scene"))
    messages = [arc["arrival_message"]]
    item_id = arc.get("item")
    if item_id and state.get("inventory", {}).get(item_id):     # he takes it
        state["inventory"][item_id] -= 1                        # back
        if state["inventory"][item_id] <= 0:
            del state["inventory"][item_id]
    recruit_id = arc.get("recruit")
    if recruit_id and recruit_id not in state["roster"]:
        state["roster"][recruit_id] = {
            "trained_ranks": {}, "attribute_xp": {}, "perks": [],
            "perk_choices": {}, "gear": {}, "ult_charge": 0,
            "energy": config.DAILY_ENERGY}
        name = content["characters"][recruit_id]["name"]
        party = state.setdefault("party", [])
        if len(party) < config.PARTY_SIZE_MAX:
            party.append(recruit_id)
            messages.append(f"{name} joins the team!")
        else:
            messages.append(f"{name} joins the roster - swap him in when "
                            f"there's room.")
    for flag, value in arc.get("flags", {}).items():
        state.setdefault("story_flags", {})[flag] = value
    return messages


# --------------------------------------------------------- field searching

def grove_name(arc, index):
    return arc["search_groves"][index]["name"]


def searchable(state, arc):
    """Grove indices still worth walking up to: everything unsearched while
    hunting, and only the one holding the item once it has been found."""
    entry = entry_of(state, arc) or {}
    if entry.get("status") == "found":
        return [entry["hidden"]]
    if entry.get("status") != "searching":
        return []
    return [i for i in range(len(arc["search_groves"]))
            if i not in entry.get("searched", [])]


def action_label(state, arc, index):
    entry = entry_of(state, arc) or {}
    if entry.get("status") == "found" and index == entry.get("hidden"):
        return arc.get("lift_label", "Take it")
    return arc.get("search_label", "Search")


def search(content, state, arc, index):
    """Work one stand of trees. Costs UNLOCK_SEARCH_ENERGY/MINUTES like a
    scout point; the stand hiding the item ends the hunt and rolls straight
    into the pickup attempt."""
    entry = entry_of(state, arc)
    if entry is None or entry["status"] not in ACTIVE:
        return {"ok": False, "message": "There's nothing to find here."}
    if entry["status"] == "found":
        if index != entry["hidden"]:
            return {"ok": False, "message": "Nothing else out here matters."}
        return _lift(content, state, arc)           # a second attempt is free
    if not 0 <= index < len(arc["search_groves"]):
        return {"ok": False, "message": "There's nothing to find here."}
    if index in entry["searched"]:
        return {"ok": False, "message": "Already searched."}
    if not energy.can_afford(state, config.UNLOCK_SEARCH_ENERGY):
        return {"ok": False, "message": "Too exhausted — sleep to recover."}
    energy.spend(state, config.UNLOCK_SEARCH_ENERGY)
    hit_end = clock.advance(state, config.UNLOCK_SEARCH_MINUTES)
    entry["searched"].append(index)
    if index != entry["hidden"]:
        left = len(arc["search_groves"]) - len(entry["searched"])
        message = arc["empty_message"].format(grove=grove_name(arc, index))
        return {"ok": True, "hit_day_end": hit_end,
                "message": f"{message} {left} stand(s) left."}
    entry["status"] = "found"
    mark = len(state.get("pending_scenes") or [])
    result = _lift(content, state, arc)
    scene = arc.get("found_scene")
    if scene:
        scene = dict(scene, lines=list(scene["lines"]))
        if not result["lifted"]:
            # Say why nobody could take it in the cutscene itself, where it
            # can't be missed, not only in the message log.
            scene["lines"].append(arc["lift_refusal"])
        # The discovery beat plays ahead of whatever the pickup queued.
        state.setdefault("pending_scenes", []).insert(mark, scene)
    result.update(ok=True, hit_day_end=hit_end, found=True)
    return result


def _lift(content, state, arc):
    """Pick the thing up — if anyone present is up to it. The named hero
    must be on the ACTIVE TEAM, not merely on the roster."""
    hero_id = arc.get("lift_requires")
    if hero_id and hero_id not in state.get("party", []):
        return {"ok": False, "lifted": False, "message": arc["lift_refusal"]}
    entry = state["unlocks"][arc["id"]]
    entry["status"] = "carried"
    item_id = arc.get("item")
    if item_id:
        # force: a story artifact must never bounce off a full bag (M18) —
        # an arc you can't pick up is an arc that dead-ends.
        inventory.add(state, item_id, 1, force=True)
    queue_scene(state, arc.get("lift_scene"))
    name = content["characters"][hero_id]["name"] if hero_id else "The team"
    return {"ok": True, "lifted": True,
            "message": arc["lift_message"].format(hero=name)}
