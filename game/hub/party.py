"""Active-party management and swap rules (spec M9). Pure Python — no pygame.

The party (max PARTY_SIZE_MAX) is who roams and fights. Swapping is done in
person: the benched character joins, the outgoing teammate takes over any
passive task the incoming one held — so the outgoing member must meet that
task's requirement.
"""

from game import config
from game.progression import attributes as attrs


def get_party(state):
    return [h for h in state.get("party", []) if h in state.get("roster", {})]


def in_party(state, hero_id):
    return hero_id in get_party(state)


def meets_requirement(content, state, hero_id, requirement):
    if not requirement:
        return True
    char = content["characters"][hero_id]
    entry = state["roster"][hero_id]
    rank = attrs.effective_rank(char["power_grid"], entry, requirement["attribute"])
    return rank >= requirement["min"]


def task_requirement(content, entry):
    assignment = entry.get("assignment")
    if not assignment:
        return None
    return content["passive"][assignment["kind"]].get("requires")


def can_swap_in(content, state, incoming_id, outgoing_id):
    """Returns (ok, reason). The outgoing teammate inherits the incoming
    character's passive task, so they must meet its requirement."""
    party = get_party(state)
    if incoming_id in party:
        return False, "Already on the team."
    if outgoing_id not in party:
        return False, "They're not on the team."
    if incoming_id not in state["roster"]:
        return False, "Not on the roster."
    requirement = task_requirement(content, state["roster"][incoming_id])
    if requirement and not meets_requirement(content, state, outgoing_id, requirement):
        name = content["characters"][outgoing_id]["name"]
        return False, (f"{name} can't cover that task "
                       f"({requirement['attribute']} {requirement['min']}+ needed).")
    return True, ""


def swap(content, state, incoming_id, outgoing_id):
    """Perform the swap; the outgoing member takes over the incoming one's
    passive task (fresh day count). Returns (ok, message)."""
    ok, reason = can_swap_in(content, state, incoming_id, outgoing_id)
    if not ok:
        return False, reason
    roster = state["roster"]
    assignment = roster[incoming_id].pop("assignment", None)
    roster[incoming_id]["idle_days"] = 0
    if assignment:
        assignment["days"] = 0
        roster[outgoing_id]["assignment"] = assignment
    party = state["party"]
    party[party.index(outgoing_id)] = incoming_id
    incoming = content["characters"][incoming_id]["name"]
    outgoing = content["characters"][outgoing_id]["name"]
    message = f"{incoming} joins the team; {outgoing} steps out"
    if assignment:
        message += " and takes over their task"
    return True, message + "."


def add_to_party(content, state, hero_id):
    """Join an open slot (no swap needed). Returns (ok, message)."""
    party = get_party(state)
    if hero_id in party:
        return False, "Already on the team."
    if len(party) >= config.PARTY_SIZE_MAX:
        return False, "The team is full - swap someone out."
    state["roster"][hero_id].pop("assignment", None)
    state["roster"][hero_id]["idle_days"] = 0
    state["party"].append(hero_id)
    return True, f"{content['characters'][hero_id]['name']} joins the team."