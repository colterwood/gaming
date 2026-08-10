"""Mastery stub (spec §6.3): detect all-six-at-7, log Mastery XP, show the
foil treatment. No perk shop in the POC. Pure Python — no pygame."""

from game import config
from game.progression import attributes


def is_mastered(base_grid, roster_entry):
    return all(attributes.effective_rank(base_grid, roster_entry, attr) == config.RANK_MAX
               for attr in config.ATTRIBUTES)


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
