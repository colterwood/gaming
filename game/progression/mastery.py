"""Mastery stub (spec §6.3 / GDD): a hero Masters when every attribute
reaches RANK_MAX (M15: trained TRAINED_MAX). Detect it, log Mastery XP,
show the foil treatment. No perk shop in the POC. Pure Python — no pygame."""

from game import config


def is_mastered(boosts, roster_entry):
    trained = roster_entry.get("trained_ranks", {})
    return all(trained.get(attr, 0) >= config.TRAINED_MAX
               for attr in config.ATTRIBUTES)


def update_mastery(boosts, roster_entry):
    """Detect and flag mastery. Returns True the first time it's achieved."""
    if roster_entry.get("mastered"):
        return False
    if is_mastered(boosts, roster_entry):
        roster_entry["mastered"] = True
        roster_entry.setdefault("mastery_xp", 0)
        return True
    return False


def log_mastery_xp(roster_entry, amount):
    if roster_entry.get("mastered"):
        roster_entry["mastery_xp"] = roster_entry.get("mastery_xp", 0) + amount
