"""Assignment-board dispatches (M10): board jobs are no longer done on the
spot — you send 1+ roster heroes away for 1+ days. Sent heroes leave the
party and can't rejoin until the job completes at sleep (rewards paid) or
you recall them (nothing paid). Pure Python — no pygame.

M11 additions: board tiers unlock as the roster's top-4 power grows;
rewards scale with the power of the heroes you send; NPC-requested jobs
pay bond points with the requester on completion.

A hero away on a job carries roster_entry["dispatch"] = task_id; the job
itself lives in state["dispatches"] with its rewards snapshotted.
"""

from game import config
from game.hub import requirements
from game.progression import attributes as attrs
from game.progression import mastery
from game.social import bonds


def hero_power(content, state, hero_id):
    """A hero's effective power-grid total (6..42): base + trained ranks."""
    char = content["characters"][hero_id]
    entry = state["roster"][hero_id]
    return sum(attrs.effective_rank(char["boosts"], entry, attribute)
               for attribute in config.ATTRIBUTES)


def team_power(content, state):
    """Sum of the top-4 roster heroes' power totals — the board's measure
    of how advanced the team is (M11)."""
    totals = sorted((hero_power(content, state, hid)
                     for hid in state.get("roster", {})), reverse=True)
    return sum(totals[:config.PARTY_SIZE_MAX])


def roster_tier(content, state):
    """Highest board tier this roster has unlocked (1..3)."""
    power = team_power(content, state)
    tier = 1
    for level, threshold in sorted(config.BOARD_TIER_POWER.items()):
        if power >= threshold:
            tier = level
    return tier


def reward_mult(content, state, hero_ids):
    """Stronger heroes negotiate better: pay scales with the average power
    of who you send, clamped to [MULT_MIN, MULT_MAX]."""
    avg = sum(hero_power(content, state, h) for h in hero_ids) / len(hero_ids)
    mult = 1.0 + config.DISPATCH_POWER_BONUS * (avg - config.DISPATCH_POWER_BASELINE)
    return max(config.DISPATCH_MULT_MIN, min(config.DISPATCH_MULT_MAX, mult))


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


def job_of(state, hero_id):
    """The active job a hero is away on, or None."""
    for job in active(state):
        if hero_id in job["heroes"]:
            return job
    return None


# Where a job with no recorded work site lands after a save migration:
# the common floor, by the bunks — always findable, always recallable.
FALLBACK_SPOT = ["common", 8, 15]


def backfill_spots(content, state):
    """Save migration (M13): jobs saved before work sites existed get their
    task's spot — or the fallback — so in-person recall always works."""
    tasks = {t["id"]: t for t in content["assignments"]}
    for job in state.get("dispatches", []):
        if not job.get("spot"):
            task = tasks.get(job["task_id"])
            job["spot"] = list(task["spot"]) if task and task.get("spot") \
                else list(FALLBACK_SPOT)


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
        if roster[hero_id].get("training"):
            name = content["characters"][hero_id]["name"]
            return False, f"{name} is mid-training."
    party = state.get("party", [])
    if party and not [p for p in party if p not in hero_ids]:
        return False, "Someone has to stay on the team."
    ok, reason = requirements.check(content, state, task, hero_ids)
    if not ok:                          # M15: Coulson explains the refusal
        return False, requirements.coulson_says(reason)
    mult = reward_mult(content, state, hero_ids)        # before they leave
    for hero_id in hero_ids:
        if hero_id in party:
            party.remove(hero_id)
        roster[hero_id].pop("assignment", None)
        roster[hero_id]["idle_days"] = 0
        roster[hero_id]["dispatch"] = task["id"]
    days = task.get("days", 1)
    job = {"task_id": task["id"], "name": task["name"], "heroes": hero_ids,
           "days_left": days, "credits": int(round(task["credits"] * mult)),
           "xp": int(round(task.get("xp", 0) * mult))}
    if task.get("requested_by"):                        # NPC request (M11)
        job["requested_by"] = task["requested_by"]
        job["bond"] = task.get("bond", 0)
    if task.get("spot"):                                # work site (M13):
        job["spot"] = list(task["spot"])                # they're findable there
    if task.get("once"):                                # one-shot job (M15)
        job["once"] = True
    active(state).append(job)
    names = " and ".join(content["characters"][h]["name"] for h in hero_ids)
    return True, (f"{names} head(s) out: {task['name']} "
                  f"({days} day(s), ~{job['credits']} cr).")


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
        if job.get("once"):
            state.setdefault("completed_tasks", []).append(job["task_id"])
        for hero_id in job["heroes"]:
            entry = state.get("roster", {}).get(hero_id)
            if entry and job["xp"]:
                # M21: away work trains them the same way field work does —
                # straight onto the attributes, not into a bank.
                attrs.award_battle_xp(
                    content["characters"][hero_id].get("boosts", {}),
                    entry, job["xp"])
                mastery.log_mastery_xp(entry, job["xp"])
        _release(state, job)
        active(state).remove(job)
        names = " and ".join(content["characters"][h]["name"] for h in job["heroes"])
        reward = f"+{job['credits']} cr"
        if job["xp"]:
            reward += f", +{job['xp']} XP each"
        messages.append(f"{job['name']} done - {names} return(s). {reward}.")
        requester = job.get("requested_by")             # NPC request (M11)
        if requester and job.get("bond"):
            bonds.add_points(state, requester, job["bond"])
            requester_name = content["characters"][requester]["name"]
            messages.append(f"{requester_name} is grateful (+{job['bond']} bond).")
            messages.extend(bonds.check_bond_progress(state, content))
    return messages
