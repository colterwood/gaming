"""Mastery stub (spec §6.3 / GDD): a hero Masters when they reach TRAINED
rank 7 in all six attributes. Detect it, log Mastery XP, show the foil
treatment. No perk shop in the POC. Pure Python — no pygame."""

from game import config


def is_mastered(base_grid, roster_entry):
    trained = roster_entry.get("trained_ranks", {})
    return all(trained.get(attr, 0) >= config.RANK_MAX for attr in config.ATTRIBUTES)


def update_mastery(base_grid, roster_entry):
    """Detect and flag mastery. Returns True the first time it's achieved."""
    if roster_entry.get("mastered"):
        return False
    if is_mastered(base_grid, roster_entry):
        roster_entry["mastered"] = True
        roster_entry.setdefault("mastery_xp", 0)
        return True
    return False


def log_mastery_xp(roster_entry, amount):
    if roster_entry.get("mastered"):
        roster_entry["mastery_xp"] = roster_entry.get("mastery_xp", 0) + amount
