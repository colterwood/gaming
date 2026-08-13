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
    listing).

    A job with a `trigger` never appears here — somebody hands it to you in
    conversation instead. M34: the opening is a person telling you what is
    broken, not a noticeboard."""
    return [job for job in content["repairs"]
            if not job.get("trigger")
            and gate_open(state, job) and not is_done(state, job)
            and not is_active(state, job)]


def triggered_by(content, state, char_id):
    """The repair this character is waiting to tell you about, if any: gate
    open, not yet taken, not yet done, and nothing else in progress."""
    if any(is_active(state, job) for job in content["repairs"]):
        return None
    for job in content["repairs"]:
        if (job.get("trigger", {}).get("character") == char_id
                and gate_open(state, job) and not is_done(state, job)
                and not is_active(state, job)):
            return job
    return None


def active(content, state):
    return [job for job in content["repairs"] if is_active(state, job)]


def outstanding(content, state):
    """Everything not yet repaired, posted or not — what "the tower is
    still a building site" means."""
    return [job for job in content["repairs"] if not is_done(state, job)]


def all_done(content, state):
    """The tower is rebuilt. Half of the Ch. 3-4 gate."""
    return not outstanding(content, state)


def active_job(content, state):
    """The one repair in hand, if any."""
    return next((j for j in content["repairs"] if is_active(state, j)), None)


def accept(content, state, job):
    """Take a repair on. ONE AT A TIME (M34): a tower with four jobs open
    at once is a checklist, and the player ends up ferrying parts for
    things they have not been told about yet."""
    entry = state.setdefault("repairs", {}).get(job["id"])
    if entry and entry.get("status") in ("active", "done"):
        return {"ok": False, "message": "Already in hand."}
    busy = active_job(content, state)
    if busy is not None:
        return {"ok": False, "busy": busy,
                "message": (f"One thing at a time - finish {busy['name']} "
                            f"first.")}
    state["repairs"][job["id"]] = {"status": "active", "found": []}
    reopen_hidden_spots(state, job)
    return {"ok": True, "message": f"Repair accepted: {job['name']}."}


def hidden_spot_keys(job):
    """search-spot keys for every hidden piece this job stashes."""
    from game.hub import activities
    return [activities.search_spot_key(part["area"], part["x"], part["y"])
            for part in job.get("parts", [])
            if part_kind(part) == "hidden"
            and part.get("area") and "x" in part and "y" in part]


def reopen_hidden_spots(state, job):
    """Un-rummage the tiles this job hides pieces in.

    M36 bug fix. Furniture dims for the DAY once searched, and a hidden
    part is only findable while its job is in hand. Take the elevator job
    on Day 1, turn over the Ops planter looking for its parts, then accept
    the Training Floor job — whose part is in that same planter — and the
    planter is greyed out until tomorrow, with nothing to tell you why.
    The Pym Lab and Tech Lab hunts collide the same way over a Tech Lab
    table. Accepting a job therefore makes its own hiding places worth
    looking in again, whatever happened earlier today."""
    searched = state.get("searched_today")
    if not searched:
        return
    for key in hidden_spot_keys(job):
        while key in searched:
            searched.remove(key)


# ------------------------------------------------------------ the work

def part_kind(part):
    """How a piece is come by (M35):

      plain  — lying in the open; a marker shows where
      hidden — inside the furniture/crate/seam at that tile, no marker;
               you get it by searching the thing, like anything else there
      npc    — in someone's pocket, handed over when you speak to them
      battle — falls out of a fight you win
      mine   — comes out of ANY ore seam, on a roll per swing (M36)
    """
    if part.get("from"):
        return "npc"
    if part.get("battle"):
        return "battle"
    if part.get("mine"):
        return "mine"
    return "hidden" if part.get("hidden") else "plain"


def mine_drop(content, state, rng):
    """A piece prised out of whatever seam the player happened to crack
    (M36). Returns log messages.

    This is the one place the M35 rule "every spot is fixed" is deliberately
    broken. Pinning the Pym regulator to one named seam in the docks meant
    the hunt was a walk to a known tile; as a roll against every seam it is
    a reason to keep mining, and mining is the system that wants the
    traffic. One piece per swing, however lucky."""
    messages = []
    for job in content["repairs"]:
        if not is_active(state, job):
            continue
        done = found(state, job)
        for index, part in enumerate(job["parts"]):
            spec = part.get("mine")
            if not spec or index in done:
                continue
            if rng.random() >= spec.get("chance", 1.0):
                continue
            entry_of(state, job)["found"].append(index)
            left = parts_left(state, job)
            messages.append(
                f"{spec.get('message', 'Salvage in the rock')} - "
                f"{job['name']}: "
                + (f"{left} piece(s) still missing." if left
                   else "that's the last piece."))
            return messages
    return messages


def parts_on(state, job, area):
    """[(index, x, y)] for unfound parts lying IN THE OPEN in one place — a
    tower floor or a zone. Hidden parts deliberately aren't here: a marker
    on one would turn the search into an instruction."""
    if not is_active(state, job):
        return []
    done = found(state, job)
    return [(i, part["x"], part["y"])
            for i, part in enumerate(job["parts"])
            if part.get("area") == area and i not in done
            and part_kind(part) == "plain"]


def hidden_at(content, state, area, x, y):
    """(job, index) for a hidden piece stashed at this tile, or (None, None).
    Whatever is there — a couch, a crate, an ore seam — gives it up when
    searched in the ordinary way."""
    for job in content["repairs"]:
        if not is_active(state, job):
            continue
        done = found(state, job)
        for index, part in enumerate(job["parts"]):
            if (index not in done and part_kind(part) == "hidden"
                    and part.get("area") == area
                    and part.get("x") == x and part.get("y") == y):
                return job, index
    return None, None


def searching_for_parts(content, state):
    """True while a job with hidden pieces is in hand — which is when the
    tower's furniture is worth turning over at all."""
    for job in content["repairs"]:
        if not is_active(state, job):
            continue
        done = found(state, job)
        if any(part_kind(p) == "hidden" and i not in done
               for i, p in enumerate(job["parts"])):
            return True
    return False


def npc_part(state, job, char_id):
    """(index, part) for a piece this character is holding and willing to
    hand over, or (None, None). `after_found` keeps one back until the
    hunt is nearly done — Jarvis produces the last Tech Lab component only
    once everything else is in."""
    if not is_active(state, job):
        return None, None
    done = found(state, job)
    for index, part in enumerate(job["parts"]):
        if part.get("from") != char_id or index in done:
            continue
        if len(done) < part.get("after_found", 0):
            continue
        return index, part
    return None, None


def battle_drop(content, state, hero_ids, rng):
    """Pieces that fall out of a won fight (M35). A `chance` part rolls for
    it; a `with` part is certain the first time that hero is in the party.
    Returns log messages."""
    messages = []
    for job in content["repairs"]:
        if not is_active(state, job):
            continue
        done = found(state, job)
        for index, part in enumerate(job["parts"]):
            spec = part.get("battle")
            if not spec or index in done:
                continue
            wanted = spec.get("with")
            if wanted and wanted not in hero_ids:
                continue
            if not wanted and rng.random() >= spec.get("chance", 1.0):
                continue
            entry_of(state, job)["found"].append(index)
            left = parts_left(state, job)
            messages.append(
                f"{spec.get('message', 'Salvage in the wreckage')} - "
                f"{job['name']}: "
                + (f"{left} piece(s) still missing." if left
                   else "that's the last piece."))
            break               # one piece per fight, however lucky you are
    return messages


def take_npc_part(state, job, index):
    """Accept a part out of somebody's pocket. No energy, no clock — they
    are handing it to you, not making you lift it out of a wall."""
    entry = entry_of(state, job)
    if entry is None or entry["status"] != "active" or index in entry["found"]:
        return {"ok": False, "message": "Nothing to hand over."}
    entry["found"].append(index)
    left = parts_left(state, job)
    tail = (f"{left} piece(s) still missing." if left
            else "That's all of it - go and fit it.")
    return {"ok": True, "left": left, "message": tail}


def parts_left(state, job):
    return len(job["parts"]) - len(found(state, job))


def can_repair(state, job):
    return is_active(state, job) and parts_left(state, job) == 0


def work_part(state, job, index):
    """Salvage one part. Every piece costs the minutes; only a HEAVY one
    (M35 `"heavy": true`) costs energy as well — a capacitor goes in your
    pocket, a nacelle strut does not."""
    if not is_active(state, job):
        return {"ok": False, "message": "Take the job at the board first."}
    entry = state["repairs"][job["id"]]
    if index in entry["found"] or not 0 <= index < len(job["parts"]):
        return {"ok": False, "message": "Nothing here."}
    part = job["parts"][index]
    if part.get("from") or part.get("battle") or part.get("mine"):
        # In somebody's pocket, or still out there in a fight or a rock face.
        return {"ok": False, "message": "That one isn't lying around."}
    heavy = bool(part.get("heavy"))
    if heavy and not energy.can_afford(state, config.REPAIR_PART_ENERGY):
        return {"ok": False, "message": "Too exhausted to shift that."}
    if heavy:
        energy.spend(state, config.REPAIR_PART_ENERGY)
    hit_end = clock.advance(state, config.REPAIR_PART_MINUTES)
    from game.hub import activities         # M36: one definition of collapse,
    if activities.should_pass_out(state):   # so an empty team isn't one
        # M18's rule: collapsing ON the job loses the work. Parts already
        # carried home stay carried — only this trip is lost.
        return {"ok": True, "hit_day_end": True,
                "message": "The team drops where they stand. The part stays "
                           "where it is."}
    entry["found"].append(index)
    left = parts_left(state, job)
    message = job.get("part_message", "One more piece.")
    if left:
        return {"ok": True, "hit_day_end": hit_end, "heavy": heavy,
                "message": f"{message} {left} piece(s) still missing."}
    return {"ok": True, "hit_day_end": hit_end, "complete": True,
            "heavy": heavy,
            "message": f"{message} That's all of it — go and fit it."}


def repair(content, state, job):
    """Fit the parts and bring the thing back to life. Sets the job's
    story flag, which is what actually opens the room.

    M36: fitting costs NOTHING — no energy, no clock. The price of a repair
    is the hunt that got you here; being charged another hour while standing
    in front of the finished thing read as a toll booth. A job's whole cost
    is REPAIR_PART_ENERGY x its heavy pieces, so the elevator and the three
    rooms are free outright.

    It also pays NO CREDITS. The tower is the player's own building — the
    six jobs were handing over 830 cr for work nobody commissioned, on top
    of a board that pays 3,160, which is most of why the purse was full
    with nothing to spend it on. The XP stays: the team really did learn
    something."""
    if not is_active(state, job):
        return {"ok": False, "message": "Take the job at the board first."}
    if not can_repair(state, job):
        left = parts_left(state, job)
        return {"ok": False,
                "message": f"Still {left} piece(s) short."}
    state["repairs"][job["id"]] = {"status": "done",
                                   "found": list(range(len(job["parts"])))}
    state.setdefault("story_flags", {})[job["flag"]] = True
    for flag, value in job.get("flags", {}).items():
        state["story_flags"][flag] = value      # e.g. the board coming back
    hit_end = False
    messages = [job["done_message"]]
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
    work. A game started under M29 has the key already and is left alone.

    Then, for EVERY finished repair, set the flags it should have granted.
    M34 hung `board_unlocked` on the Quinjet — a job every live save had
    already done — and without this their assignment board would be locked
    behind a keypad that nothing opens."""
    if "repairs" not in state:
        state["repairs"] = {}
        for job_id in LEGACY_JOBS:
            job = job_by_id(content, job_id)
            if job is None:
                continue
            state["repairs"][job_id] = {
                "status": "done", "found": list(range(len(job["parts"])))}
            state.setdefault("story_flags", {})[job["flag"]] = True
    flags = state.setdefault("story_flags", {})
    for job in content["repairs"]:
        if not (is_done(state, job) or flags.get(job["flag"])):
            continue
        flags[job["flag"]] = True
        for flag, value in job.get("flags", {}).items():
            flags.setdefault(flag, value)
