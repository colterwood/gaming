"""Passive assignments for benched roster members (spec M9): daily gains at
sleep, and skill atrophy after too long in the same spot. Pure Python.
"""

from game import config
from game.progression import attributes as attrs
from game.progression import mastery
from game.social import bonds


def assign(content, state, hero_id, kind, attribute=None):
    """Give a benched hero a passive task. Returns (ok, message)."""
    entry = state["roster"][hero_id]
    spec = content["passive"].get(kind)
    if spec is None:
        return False, "Unknown task."
    if entry.get("dispatch"):
        return False, "They're away on assignment."
    if entry.get("training"):
        return False, "They're mid-training."
    requirement = spec.get("requires")
    if requirement:
        char = content["characters"][hero_id]
        rank = attrs.effective_rank(char["boosts"], entry, requirement["attribute"])
        if rank < requirement["min"]:
            return False, (f"{char['name']} needs {requirement['attribute']} "
                           f"{requirement['min']}+ for that.")
    entry["assignment"] = {"kind": kind, "days": 0}
    if kind == "train":
        entry["assignment"]["attribute"] = attribute or "strength"
    entry["idle_days"] = 0
    name = content["characters"][hero_id]["name"]
    label = content["passive"][kind]["label"]
    return True, f"{name} assigned: {label}."


def clear(state, hero_id):
    state["roster"][hero_id].pop("assignment", None)
    state["roster"][hero_id]["idle_days"] = 0


def _atrophy(entry, base_grid, exclude=None):
    """Drain XP from unworked attributes; drop a trained rank when the bank
    runs dry (§M9: 'slowly start to decrease')."""
    xp_bank = entry.setdefault("attribute_xp", {})
    ranks = entry.setdefault("trained_ranks", {})
    decayed = False
    for attribute in config.ATTRIBUTES:
        if attribute == exclude:
            continue
        bank = xp_bank.get(attribute, 0) - config.ATROPHY_XP_PER_DAY
        if bank < 0:
            rank = ranks.get(attribute, 0)
            if rank > 0:
                ranks[attribute] = rank - 1
                bank += attrs.xp_for_rank(rank)
                decayed = True
            else:
                bank = 0
        xp_bank[attribute] = bank
    return decayed


def process_day(content, state):
    """Apply one day of passive work + atrophy. Called at sleep. Returns
    messages to show in the morning."""
    messages = []
    party = set(state.get("party", []))
    for hero_id, entry in state.get("roster", {}).items():
        char = content["characters"][hero_id]
        if hero_id in party:
            entry["idle_days"] = 0
            continue
        if entry.get("dispatch") or entry.get("training"):
            entry["idle_days"] = 0      # busy, not idling: no atrophy (M10/M12)
            continue
        assignment = entry.get("assignment")
        if not assignment:
            entry["idle_days"] = entry.get("idle_days", 0) + 1
            if entry["idle_days"] > config.ATROPHY_GRACE_DAYS:
                if _atrophy(entry, char.get("boosts", {})):
                    messages.append(f"{char['name']} is getting rusty idling around.")
            continue
        assignment["days"] = assignment.get("days", 0) + 1
        kind = assignment["kind"]
        spec = content["passive"][kind]
        if kind == "train":
            attribute = assignment.get("attribute", "strength")
            gain = attrs.add_training_xp(char["boosts"], entry, attribute,
                                         spec["xp_per_day"])
            if gain["ranks_gained"]:
                messages.append(f"{char['name']}'s {attribute.title()} reached "
                                f"trained rank {gain['trained_rank']}!")
            if mastery.update_mastery(char["boosts"], entry):
                messages.append(f"{char['name']} MASTERED - the card goes foil!")
        elif kind == "support":
            credits = spec["credits_per_day"]
            state["credits"] += credits
            messages.append(f"{char['name']}'s ops support earned {credits} cr.")
        elif kind == "socialize":
            npcs = [c for c in content["characters"].values()
                    if c["recruit"]["method"] == "npc"]
            if npcs:
                lowest = min(npcs, key=lambda c: bonds.ensure_bond(state, c["id"])["points"])
                bonds.add_points(state, lowest["id"], spec["bond_per_day"])
                messages.append(f"{char['name']} spent the day with {lowest['name']}.")
                messages.extend(bonds.check_bond_progress(state, content))
        if assignment["days"] > config.ATROPHY_GRACE_DAYS:
            exclude = assignment.get("attribute") if kind == "train" else None
            if _atrophy(entry, char.get("boosts", {}), exclude=exclude):
                messages.append(f"{char['name']}'s unworked skills are slipping.")
    return messages