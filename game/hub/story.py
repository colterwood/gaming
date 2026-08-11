"""Story quest progression (M6): sequential Ch. 1-2 quest chain, hub tasks,
recruitment, story flags. Pure Python — no pygame.

Quest state lives in state["quests"] as {quest_id: {"name", "status"}} with
status "active" | "done"; quests unlock strictly in story.json order.
"""

from game import config
from game.core import clock, energy


def init(state, story_data):
    state.setdefault("quests", {})
    _activate_next(state, story_data)


def current_quest(state, story_data):
    """The first quest in story order that isn't done, or None."""
    for quest in story_data:
        entry = state.get("quests", {}).get(quest["id"])
        if not entry or entry["status"] != "done":
            return quest
    return None


def _activate_next(state, story_data):
    quest = current_quest(state, story_data)
    if quest:
        state["quests"].setdefault(quest["id"],
                                   {"name": quest["name"], "status": "active"})
    return quest


def story_complete(state, story_data):
    return current_quest(state, story_data) is None


def do_hub_task(state, quest, story_data=None):
    """Perform a hub_task quest step (§6.1 small-task costs from quest data)."""
    if not energy.can_afford(state, quest["energy"]):
        return {"ok": False, "message": "Too exhausted — sleep to recover."}
    energy.spend(state, quest["energy"])
    clock.advance(state, quest.get("minutes", 60))
    state["quests"][quest["id"]] = {"name": quest["name"], "status": "done"}
    if story_data:
        _activate_next(state, story_data)
    return {"ok": True, "message": f"{quest['name']} — done."}


def complete_battle_quest(state, quest, content):
    """Mark a battle quest won and apply recruit/flags. Returns messages."""
    messages = [f"{quest['name']} — complete!"]
    state["quests"][quest["id"]] = {"name": quest["name"], "status": "done"}
    _activate_next(state, content["story"])
    recruit_id = quest.get("recruit")
    if recruit_id and recruit_id not in state["roster"]:
        state["roster"][recruit_id] = {"trained_ranks": {}, "attribute_xp": {},
                                       "perks": [], "perk_choices": {},
                                       "gear": {}, "ult_charge": 0}
        name = content["characters"][recruit_id]["name"]
        messages.append(f"{name} joins the roster!")
    for flag, value in quest.get("flags", {}).items():
        state.setdefault("story_flags", {})[flag] = value
        if flag == "training_upgraded":
            messages.append("Training Floor upgraded! (+80 XP sessions)")
        if flag == "ch2_complete":
            messages.append("Chapters 1-2 complete. Kang is watching...")
    return messages
