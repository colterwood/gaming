"""Assignment-board dispatches (M10): board jobs are no longer done on the
spot — you send 1+ roster heroes away for 1+ days. Sent heroes leave the
party and can't rejoin until the job completes at sleep (rewards paid) or
you recall them (nothing paid). Pure Python — no pygame.

A hero away on a job carries roster_entry["dispatch"] = task_id; the job
itself lives in state["dispatches"] with its rewards snapshotted.
"""

from game.progression import mastery


def active(state):
    return state.setdefault("dispatches", [])


def find(state, task_id):
    for job in active(state):
        if job["task_id"] == task_id:
            return job
    return None


def is_away(state, hero_id):
    entry = state.get("roster", {}).get(hero_id)
    return bool(entry and entry.get("dispatch"))


def send(content, state, task, hero_ids):
    """Dispatch hero_ids on a board task. Returns (ok, message)."""
    hero_ids = list(hero_ids)
    need = task.get("heroes", 1)
    if len(hero_ids) != len(set(hero_ids)) or len(hero_ids) != need:
        return False, f"That job needs {need} hero(es)."
    if find(state, task["id"]):
        return False, "That job is already under way."
    roster = state["roster"]
    for hero_id in hero_ids:
        if hero_id not in roster:
            return False, "They're not on the roster."
        if roster[hero_id].get("dispatch"):
            name = content["characters"][hero_id]["name"]
            return False, f"{name} is already away on assignment."
    party = state.get("party", [])
    if party and not [p for p in party if p not in hero_ids]:
        return False, "Someone has to stay on the team."
    for hero_id in hero_ids:
        if hero_id in party:
            party.remove(hero_id)
        roster[hero_id].pop("assignment", None)
        roster[hero_id]["idle_days"] = 0
        roster[hero_id]["dispatch"] = task["id"]
    days = task.get("days", 1)
    active(state).append({"task_id": task["id"], "name": task["name"],
                          "heroes": hero_ids, "days_left": days,
                          "credits": task["credits"], "xp": task.get("xp", 0)})
    names = " and ".join(content["characters"][h]["name"] for h in hero_ids)
    return True, f"{names} head(s) out: {task['name']} ({days} day(s))."


def recall(content, state, task_id):
    """Abandon a job under way; the heroes come home empty-handed."""
    job = find(state, task_id)
    if not job:
        return False, "No such job under way."
    _release(state, job)
    active(state).remove(job)
    names = " and ".join(content["characters"][h]["name"] for h in job["heroes"])
    return True, f"{job['name']} abandoned - {names} return(s) empty-handed."


def _release(state, job):
    for hero_id in job["heroes"]:
        entry = state.get("roster", {}).get(hero_id)
        if entry and entry.get("dispatch") == job["task_id"]:
            entry.pop("dispatch", None)
            entry["idle_days"] = 0


def process_day(content, state):
    """Advance every job one night; completed jobs pay credits and bank XP
    (spent as bonus progress at training, like battle XP). Called at sleep.
    Returns morning messages."""
    messages = []
    for job in list(active(state)):
        job["days_left"] -= 1
        if job["days_left"] > 0:
            continue
        state["credits"] += job["credits"]
        for hero_id in job["heroes"]:
            entry = state.get("roster", {}).get(hero_id)
            if entry and job["xp"]:
                entry["unspent_xp"] = entry.get("unspent_xp", 0) + job["xp"]
                mastery.log_mastery_xp(entry, job["xp"])
        _release(state, job)
        active(state).remove(job)
        names = " and ".join(content["characters"][h]["name"] for h in job["heroes"])
        reward = f"+{job['credits']} cr"
        if job["xp"]:
            reward += f", +{job['xp']} XP banked each"
        messages.append(f"{job['name']} done - {names} return(s). {reward}.")
    return messages
