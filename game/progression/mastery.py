"""The capstone above rank 10 (spec §6.3). Pure Python — no pygame.

A hero is MAXED when every attribute reaches RANK_MAX. That used to be the
end of the ladder ("Mastery" — a flag, a foil card, and a dead XP counter).
M33 makes it a rung instead: once all six are at 10, **Enlightenment**
opens as a single 51,200 XP climb — the next doubling after 9 -> 10, and
the only place XP can still go once the six are full.

    roster entry: {"mastered": True,          # all six at RANK_MAX
                   "enlightenment_xp": n,     # progress toward the capstone
                   "enlightened": True}       # the climb is finished

`mastered` keeps its name because the card and the binder read it for the
foil treatment, and old saves already carry it.
"""

from game import config

ATTRIBUTE = "enlightenment"     # what the rack calls this row


def is_mastered(boosts, roster_entry):
    """Every attribute at the trained cap — the gate on the capstone."""
    trained = roster_entry.get("trained_ranks", {})
    return all(trained.get(attr, 0) >= config.TRAINED_MAX
               for attr in config.ATTRIBUTES)


def update_mastery(boosts, roster_entry):
    """Detect and flag the all-six-at-ten state. True the first time."""
    if roster_entry.get("mastered"):
        return False
    if is_mastered(boosts, roster_entry):
        roster_entry["mastered"] = True
        roster_entry.setdefault("mastery_xp", 0)
        return True
    return False


def available(roster_entry):
    """Can this hero work on Enlightenment? Only with all six at rank 10,
    and only until it's done."""
    return bool(roster_entry.get("mastered")) and not is_enlightened(roster_entry)


def is_enlightened(roster_entry):
    return bool(roster_entry.get("enlightened"))


def progress(roster_entry):
    """(xp so far, xp needed)."""
    return (roster_entry.get("enlightenment_xp", 0), config.ENLIGHTENMENT_XP)


def add_enlightenment_xp(roster_entry, amount):
    """Pour XP into the capstone. Anything past the requirement is kept on
    the counter rather than dropped, so nothing earned disappears."""
    amount = max(0, int(amount))
    if not available(roster_entry) or not amount:
        return {"gained": 0, "xp": roster_entry.get("enlightenment_xp", 0),
                "complete": False}
    total = roster_entry.get("enlightenment_xp", 0) + amount
    roster_entry["enlightenment_xp"] = total
    complete = total >= config.ENLIGHTENMENT_XP
    if complete:
        roster_entry["enlightened"] = True
    return {"gained": amount, "xp": total, "complete": complete}


def log_mastery_xp(roster_entry, amount):
    """Field XP earned by a hero with nothing left to train (M21 drops
    maxed attributes from the split, so this is where it lands).

    Flags the all-six-at-ten state first: the last rank may well have come
    from a battle rather than the rack, and XP earned after that must not
    fall on the floor waiting for someone to visit the mats."""
    update_mastery(None, roster_entry)
    if roster_entry.get("mastered"):
        roster_entry["mastery_xp"] = roster_entry.get("mastery_xp", 0) + amount
        add_enlightenment_xp(roster_entry, amount)
