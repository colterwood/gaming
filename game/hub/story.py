"""Story quest progression (M6): sequential Ch. 1-2 quest chain, field
scouting, recruitment, story flags. Pure Python — no pygame.

Quest state lives in state["quests"] as {quest_id: {"name", "status"}} with
status "offered" | "active" | "failed" | "done"; quests unlock strictly in
story.json order. M13: a quest is only visible in the field once ACCEPTED
at the Ops Console ("offered" -> "active"); the deadline starts at accept.
Scout quests (kind "scout") replace hub tasks: fly to the zone and work
every scout point.
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
                                   {"name": quest["name"], "status": "offered"})
    return quest


def quest_entry(state, quest):
    return state.setdefault("quests", {}).setdefault(
        quest["id"], {"name": quest["name"], "status": "offered"})


def is_accepted(state, quest):
    """M13: nothing shows in the field until the player takes the job."""
    return quest_entry(state, quest)["status"] == "active"


def accept(state, quest):
    """Take the job at the Ops Console; the deadline clock starts now."""
    entry = quest_entry(state, quest)
    if entry["status"] != "offered":
        return {"ok": False, "message": "Nothing to accept."}
    entry["status"] = "active"
    entry["activated_day"] = abs_day(state)
    return {"ok": True, "message": f"Mission accepted: {quest['name']}."}


def days_left(state, quest):
    """Days remaining before the mission deadline; None if untimed or not
    yet accepted (the clock starts at accept, M13)."""
    deadline = quest.get("deadline_days")
    entry = quest_entry(state, quest)
    if not deadline or "activated_day" not in entry:
        return None
    return entry["activated_day"] + deadline - abs_day(state)


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
    """Run at day start: expire overdue missions, re-offer cooled-down
    ones (they must be accepted again, M13). Returns messages."""
    messages = []
    quest = current_quest(state, story_data)
    if quest is None:
        return messages
    entry = quest_entry(state, quest)
    today = abs_day(state)
    left = days_left(state, quest)
    if entry["status"] == "active" and left is not None and left < 0:
        messages.append(fail_mission(state, quest))
    elif entry["status"] == "failed" and today >= entry.get("retry_day", 0):
        entry["status"] = "offered"
        entry.pop("activated_day", None)
        entry.pop("scouted", None)      # a re-offered scout restarts clean,
        messages.append(f"New intel: {quest['name']} is back on the board.")
    return messages                     # same as a failed battle quest


def story_complete(state, story_data):
    return current_quest(state, story_data) is None


# ----------------------------------------------------- scout quests (M13)

def scouted(state, quest):
    """Indices of this scout quest's points already worked."""
    return quest_entry(state, quest).setdefault("scouted", [])


def do_scout(state, quest, index, story_data=None):
    """Work one scout point in the field (SCOUT_ENERGY/SCOUT_MINUTES per
    point); the quest completes when every point is done."""
    if not is_accepted(state, quest):
        return {"ok": False, "message": "Accept the mission at Ops first."}
    done = scouted(state, quest)
    if index in done or not 0 <= index < len(quest["scout_points"]):
        return {"ok": False, "message": "Nothing left to do here."}
    if not energy.can_afford(state, config.SCOUT_ENERGY):
        return {"ok": False, "message": "Too exhausted — sleep to recover."}
    energy.spend(state, config.SCOUT_ENERGY)
    hit_end = clock.advance(state, config.SCOUT_MINUTES)
    if energy.is_exhausted(state) or clock.is_past_end(state):
        # M18: collapsing ON the job loses the job. The point isn't
        # credited and the night's work goes with it — previously the
        # last point still landed and could even COMPLETE the quest on
        # the way down.
        done.clear()
        return {"ok": True, "hit_day_end": True, "reset": True,
                "message": (f"The team drops where they stand. "
                            f"{quest['name']} will have to be worked again.")}
    done.append(index)
    remaining = len(quest["scout_points"]) - len(done)
    if remaining:
        return {"ok": True, "hit_day_end": hit_end,
                "message": f"{quest['name']}: {remaining} spot(s) left."}
    entry = quest_entry(state, quest)
    entry["status"] = "done"
    if story_data:
        _activate_next(state, story_data)
    return {"ok": True, "hit_day_end": hit_end, "complete": True,
            "message": f"{quest['name']} — complete!"}


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
                                       "energy": config.DAILY_ENERGY}
        name = content["characters"][recruit_id]["name"]
        messages.append(f"{name} joins the roster!")
    for flag, value in quest.get("flags", {}).items():
        state.setdefault("story_flags", {})[flag] = value
        if flag == "training_upgraded":
            messages.append("Training Floor upgraded! (+80 XP sessions)")
        if flag == "pym_lab_unlocked":
            messages.append("Scott hands over the Pym Lab access code.")
        if flag == "ch2_complete":
            messages.append("Chapters 1-2 complete. Kang is watching...")
    return messages
