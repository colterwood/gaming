"""Tower repairs (spec §9 M29). Pure Python — no pygame.

The tower starts wrecked: the elevator is dead, the Quinjet won't fly, the
training floor is a pile of torn mats, and three rooms have never been
opened. Each repair is posted on the assignment board, but unlike a
dispatch job (M10) it is not sent away with a hero — it is ACCEPTED at the
board and then WORKED in person, which is what makes the opening playable
instead of a two-day wait:

    posted -> accept at the board -> walk the tower salvaging `parts`
           -> stand at the broken thing itself and repair it -> flag set

Repair state lives in state["repairs"][job_id]:
    {"status": "active" | "done", "found": [part index, ...]}

Content is data/quests/repairs.json. A job's `station` names the station
KIND the repair is finished at (the elevator, the jet, the rack...), and
its `parts` are [floor, x, y] triples, so "find the pieces around the
tower" genuinely means walking more than one floor.

Repairs sit on the critical path — the Ch. 3-4 gate is every mission done
AND the tower repaired — so they never carry a posting-chance roll or a
bond gate the way board jobs may. A dice roll that stalls the campaign is
a softlock.
"""

from game import config
from game.core import clock, energy
from game.progression import attributes as attrs

# Rooms that existed before M29. A save from an older build has been
# playing in them for days, so loading one counts them as already
# repaired — only the new rooms post as fresh work (the M20 rule).
LEGACY_JOBS = ("repair_elevator", "repair_quinjet", "repair_training")


def job_by_id(content, job_id):
    return next((j for j in content["repairs"] if j["id"] == job_id), None)


def entry_of(state, job):
    return state.get("repairs", {}).get(job["id"])


def status(state, job):
    return (entry_of(state, job) or {}).get("status")


def is_done(state, job):
    return status(state, job) == "done"


def is_active(state, job):
    return status(state, job) == "active"


def flag_set(state, job):
    return bool(state.get("story_flags", {}).get(job["flag"]))


def found(state, job):
    return (entry_of(state, job) or {}).get("found", [])


# ------------------------------------------------------------- posting

def gate_open(state, job):
    """Whether the board is willing to post this repair yet: the story
    flags it waits on, plus any quests that must already be done."""
    flags = state.get("story_flags", {})
    if not all(flags.get(f) for f in job.get("requires", {}).get("flags", [])):
        return False
    quests = state.get("quests", {})
    for quest_id in job.get("requires", {}).get("quests", []):
        if (quests.get(quest_id) or {}).get("status") != "done":
            return False
    return True


def posted(content, state):
    """Repairs the board is showing today: gate open, not finished, and
    not already accepted (an accepted one is work in the world, not a
    listing)."""
    return [job for job in content["repairs"]
            if gate_open(state, job) and not is_done(state, job)
            and not is_active(state, job)]


def active(content, state):
    return [job for job in content["repairs"] if is_active(state, job)]


def outstanding(content, state):
    """Everything not yet repaired, posted or not — what "the tower is
    still a building site" means."""
    return [job for job in content["repairs"] if not is_done(state, job)]


def all_done(content, state):
    """The tower is rebuilt. Half of the Ch. 3-4 gate."""
    return not outstanding(content, state)


def accept(state, job):
    entry = state.setdefault("repairs", {}).get(job["id"])
    if entry and entry.get("status") in ("active", "done"):
        return {"ok": False, "message": "Already in hand."}
    state["repairs"][job["id"]] = {"status": "active", "found": []}
    return {"ok": True, "message": f"Repair accepted: {job['name']}."}


# ------------------------------------------------------------ the work

def parts_on(state, job, floor):
    """[(index, x, y)] for this job's unfound parts on one tower floor."""
    if not is_active(state, job):
        return []
    done = found(state, job)
    return [(i, part[1], part[2])
            for i, part in enumerate(job["parts"])
            if part[0] == floor and i not in done]


def parts_left(state, job):
    return len(job["parts"]) - len(found(state, job))


def can_repair(state, job):
    return is_active(state, job) and parts_left(state, job) == 0


def work_part(state, job, index):
    """Salvage one part. Costs the same as a scout point — this is field
    work that happens to be indoors."""
    if not is_active(state, job):
        return {"ok": False, "message": "Take the job at the board first."}
    entry = state["repairs"][job["id"]]
    if index in entry["found"] or not 0 <= index < len(job["parts"]):
        return {"ok": False, "message": "Nothing here."}
    if not energy.can_afford(state, config.REPAIR_PART_ENERGY):
        return {"ok": False, "message": "Too exhausted — sleep to recover."}
    energy.spend(state, config.REPAIR_PART_ENERGY)
    hit_end = clock.advance(state, config.REPAIR_PART_MINUTES)
    if energy.is_exhausted(state) or clock.is_past_end(state):
        # M18's rule: collapsing ON the job loses the work. Parts already
        # carried home stay carried — only this trip is lost.
        return {"ok": True, "hit_day_end": True,
                "message": "The team drops where they stand. The part stays "
                           "where it is."}
    entry["found"].append(index)
    left = parts_left(state, job)
    message = job.get("part_message", "One more piece.")
    if left:
        return {"ok": True, "hit_day_end": hit_end,
                "message": f"{message} {left} piece(s) still missing."}
    return {"ok": True, "hit_day_end": hit_end, "complete": True,
            "message": f"{message} That's all of it — go and fit it."}


def repair(content, state, job):
    """Fit the parts and bring the thing back to life. Sets the job's
    story flag, which is what actually opens the room."""
    if not is_active(state, job):
        return {"ok": False, "message": "Take the job at the board first."}
    if not can_repair(state, job):
        left = parts_left(state, job)
        return {"ok": False,
                "message": f"Still {left} piece(s) short."}
    if not energy.can_afford(state, config.REPAIR_ENERGY):
        return {"ok": False, "message": "Too exhausted — sleep to recover."}
    energy.spend(state, config.REPAIR_ENERGY)
    hit_end = clock.advance(state, config.REPAIR_MINUTES)
    state["repairs"][job["id"]] = {"status": "done",
                                   "found": list(range(len(job["parts"])))}
    state.setdefault("story_flags", {})[job["flag"]] = True
    state["credits"] = state.get("credits", 0) + job.get("credits", 0)
    messages = [job["done_message"]]
    if job.get("credits"):
        messages.append(f"+{job['credits']} cr for the work.")
    xp = job.get("xp", 0)
    if xp:
        # Paid like battle XP: split across the six, to everyone who was
        # actually holding a wrench (M21).
        for hero_id in state.get("party", []):
            entry = state["roster"].get(hero_id)
            if entry is None:
                continue
            boosts = content["characters"][hero_id].get("boosts", {})
            attrs.award_battle_xp(boosts, entry, xp)
        share = xp // len(config.ATTRIBUTES)
        messages.append(f"+{xp} XP each (+{share} to every skill).")
    return {"ok": True, "hit_day_end": hit_end, "messages": messages,
            "scene": job.get("done_scene"), "message": messages[0]}


# ------------------------------------------------------------ migration

def migrate(content, state):
    """A save from before M29 has been using the elevator, the jet and the
    mats for days — it must not wake up in a building site. Anything the
    old build shipped counts as repaired; the new rooms post as fresh
    work. A game started under M29 has the key already and is left alone."""
    if "repairs" in state:
        return
    state["repairs"] = {}
    for job_id in LEGACY_JOBS:
        job = job_by_id(content, job_id)
        if job is None:
            continue
        state["repairs"][job_id] = {
            "status": "done", "found": list(range(len(job["parts"])))}
        state.setdefault("story_flags", {})[job["flag"]] = True
