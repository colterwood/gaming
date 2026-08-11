"""Assignment-board eligibility (M15). Pure Python — no pygame.

Board tasks carry a hidden `requires` block. Nothing is advertised on the
board: the player picks a crew and Coulson tells them why it won't fly.

Schema (all keys optional):
    "requires": {
      "flag": "hulk_arrived",                       # story flag gate
      "bond": {"character": "coulson", "level": 1}, # relationship gate
      "hero_any_of": [                              # each clause: ANY of the
        {"attributes": ["intelligence"], "min_rank": 2},
        {"attributes": ["intelligence"], "min_boost": 3, "min_rank": 2}
      ],                                            # listed attributes must
                                                    # satisfy EVERY key in
                                                    # that clause, on the
                                                    # SAME attribute
      "hero_all_attributes": {"min_rank": 2}        # every attribute
    }

Rank means the plain trainable level 1..RANK_MAX; boost means innate
talent 0..BOOST_MAX. Every hero being sent must qualify.
"""

import zlib

from game import config
from game.progression import attributes as attrs
from game.social import bonds

ATTRIBUTE_LABEL = {
    "strength": "Strength", "speed": "Speed", "agility": "Agility",
    "stamina": "Stamina", "durability": "Durability",
    "intelligence": "Intelligence",
}


def _clause_met(char, entry, clause):
    """True if ANY listed attribute satisfies every condition in the clause."""
    boosts = char.get("boosts", {})
    for attribute in clause.get("attributes", config.ATTRIBUTES):
        if attrs.rank(entry, attribute) < clause.get("min_rank", 0):
            continue
        if boosts.get(attribute, 0) < clause.get("min_boost", 0):
            continue
        return True
    return False


def hero_qualifies(content, state, task, hero_id):
    """(ok, reason) for one hero against a task's hero-side requirements."""
    requires = task.get("requires") or {}
    char = content["characters"][hero_id]
    entry = state["roster"][hero_id]
    name = char["name"]

    every = requires.get("hero_all_attributes")
    if every:
        short = [a for a in config.ATTRIBUTES
                 if attrs.rank(entry, a) < every.get("min_rank", 0)]
        if short:
            return False, (f"{name} isn't rounded out enough - this one needs "
                           f"level {every['min_rank']} across the board, and "
                           f"{ATTRIBUTE_LABEL[short[0]]} is still "
                           f"{attrs.rank(entry, short[0])}.")

    clauses = requires.get("hero_any_of")
    if clauses and not any(_clause_met(char, entry, c) for c in clauses):
        wanted = sorted({ATTRIBUTE_LABEL[a] for c in clauses
                         for a in c.get("attributes", config.ATTRIBUTES)})
        return False, (f"{name} isn't cleared for this one - it wants more "
                       f"{' or '.join(wanted)} than they've got, trained or "
                       f"natural.")
    return True, ""


def daily_roll(state, task_id):
    """A stable [0, 1) roll for this task on this date (M16). Deterministic
    so the board doesn't reshuffle every time the player opens it."""
    key = f"{task_id}:{state['issue']}:{state['day']}".encode()
    return (zlib.crc32(key) % 10000) / 10000.0


def posting_chance(state, task):
    """Probability this job is on today's board. Tasks with a `posting`
    block get warmer as the requester's bond grows (M16); everything else
    is always posted once its gates are open."""
    posting = task.get("posting")
    if not posting:
        return 1.0
    ladder = posting["chance_by_bond_level"]
    level = bonds.bond_level(
        bonds.ensure_bond(state, posting["bond_character"])["points"])
    return ladder[min(level, len(ladder) - 1)]


def is_done(state, task):
    """M26: EVERY board job is one-shot. Finishing one retires it for good,
    so the board is a finite list of work rather than an income tap."""
    return task["id"] in state.get("completed_tasks", [])


def gate_open(state, task):
    """Story-flag / relationship / already-done / posting-chance gates.
    These decide whether the job is even POSTED — unlike the hidden skill
    requirements, a job whose gate is shut simply isn't on the board."""
    requires = task.get("requires") or {}
    flag = requires.get("flag")
    if flag and not state.get("story_flags", {}).get(flag):
        return False
    if is_done(state, task):
        return False
    bond_gate = requires.get("bond")
    if bond_gate:
        level = bonds.bond_level(
            bonds.ensure_bond(state, bond_gate["character"])["points"])
        if level < bond_gate["level"]:
            return False
    if daily_roll(state, task["id"]) >= posting_chance(state, task):
        return False
    return True


def task_available(content, state, task):
    """(ok, reason) for the non-hero gates: story flags and relationships."""
    requires = task.get("requires") or {}
    flag = requires.get("flag")
    if flag and not state.get("story_flags", {}).get(flag):
        return False, "That request isn't on my desk yet."
    if is_done(state, task):
        return False, "That one's already been handled."
    bond_gate = requires.get("bond")
    if bond_gate:
        char_id = bond_gate["character"]
        level = bonds.bond_level(bonds.ensure_bond(state, char_id)["points"])
        if level < bond_gate["level"]:
            who = content["characters"][char_id]["name"]
            if char_id == "coulson":
                return False, ("I'd need to know you better before I put your "
                               "name on this one.")
            return False, (f"{who} doesn't know your team well enough to hand "
                           f"that over yet.")
    return True, ""


def check(content, state, task, hero_ids):
    """Full gate for a dispatch attempt. Returns (ok, coulson_line)."""
    ok, reason = task_available(content, state, task)
    if not ok:
        return False, reason
    for hero_id in hero_ids:
        ok, reason = hero_qualifies(content, state, task, hero_id)
        if not ok:
            return False, reason
    return True, ""


def coulson_says(line):
    return f"COULSON: {line}"
