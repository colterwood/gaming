"""Story quest progression (M6): sequential Ch. 1-2 quest chain, hub tasks,
recruitment, story flags. Pure Python — no pygame.

Quest state lives in state["quests"] as {quest_id: {"name", "status"}} with
status "active" | "done"; quests unlock strictly in story.json order.
"""

from game import config
from game.core import clock, energy


def abs_day(state):
    return (state["issue"] - 1) * config.DAYS_PER_ISSUE + state["day"]


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
                                   {"name": quest["name"], "status": "active",
                                    "activated_day": abs_day(state)})
    return quest


def quest_entry(state, quest):
    return state.setdefault("quests", {}).setdefault(
        quest["id"], {"name": quest["name"], "status": "active",
                      "activated_day": abs_day(state)})


def days_left(state, quest):
    """Days remaining before the mission deadline, or None if untimed."""
    deadline = quest.get("deadline_days")
    if not deadline:
        return None
    entry = quest_entry(state, quest)
    return entry.get("activated_day", abs_day(state)) + deadline - abs_day(state)


def is_locked(state, quest):
    """True while a failed mission is cooling down (M9)."""
    entry = state.get("quests", {}).get(quest["id"])
    return bool(entry and entry.get("status") == "failed"
                and abs_day(state) < entry.get("retry_day", 0))


def fail_mission(state, quest):
    """Deadline expired or battle lost: 2-day cooldown before retry (M9)."""
    entry = quest_entry(state, quest)
    entry["status"] = "failed"
    entry["retry_day"] = abs_day(state) + config.MISSION_FAIL_COOLDOWN_DAYS
    return (f"Mission failed: {quest['name']}. HYDRA goes to ground for "
            f"{config.MISSION_FAIL_COOLDOWN_DAYS} days.")


def check_deadlines(state, story_data):
    """Run at day start: expire overdue missions, reactivate cooled-down
    ones. Returns messages."""
    messages = []
    quest = current_quest(state, story_data)
    if quest is None or quest["kind"] != "battle":
        return messages
    entry = quest_entry(state, quest)
    today = abs_day(state)
    left = days_left(state, quest)
    if entry["status"] == "active" and left is not None and left < 0:
        messages.append(fail_mission(state, quest))
    elif entry["status"] == "failed" and today >= entry.get("retry_day", 0):
        entry["status"] = "active"
        entry["activated_day"] = today
        messages.append(f"New intel: {quest['name']} is back on the board.")
    return messages


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
                                       "gear": {}, "ult_charge": 0,
                                       "energy": config.DAILY_ENERGY,
                                       "unspent_xp": 0}
        name = content["characters"][recruit_id]["name"]
        messages.append(f"{name} joins the roster!")
    for flag, value in quest.get("flags", {}).items():
        state.setdefault("story_flags", {})[flag] = value
        if flag == "training_upgraded":
            messages.append("Training Floor upgraded! (+80 XP sessions)")
        if flag == "ch2_complete":
            messages.append("Chapters 1-2 complete. Kang is watching...")
    return messages
