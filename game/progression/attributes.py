"""Attribute training XP, trained ranks, perk choices (spec §6.3).
Pure Python — no pygame.

Roster entry shape (in the save state):
    {"trained_ranks": {attr: n}, "attribute_xp": {attr: xp},
     "perks": ["haymaker", ...], ...}
"""

from game import config
from game.core import calendar as cal


def xp_for_rank(n):
    """XP required to gain trained rank N: 100 × N (§6.3)."""
    return config.ATTRIBUTE_XP_PER_RANK * n


def effective_rank(base_grid, roster_entry, attribute):
    trained = roster_entry.get("trained_ranks", {}).get(attribute, 0)
    return min(config.RANK_MAX, base_grid[attribute] + trained)


def can_train(base_grid, roster_entry, attribute):
    return effective_rank(base_grid, roster_entry, attribute) < config.RANK_MAX


def session_xp(state, calendar_data):
    """40 basic / 80 upgraded facility / 120 during a training event (§6.3)."""
    for ev in cal.active_events(state, calendar_data):
        if "training_xp_bonus" in ev.get("effects", {}):
            return config.TRAINING_XP_EVENT
    if state.get("story_flags", {}).get("training_upgraded"):
        return config.TRAINING_XP_UPGRADED
    return config.TRAINING_XP_BASIC


def add_training_xp(base_grid, roster_entry, attribute, xp):
    """Bank XP and consume it into trained ranks. Multiple rank-ups can occur.
    Training past effective rank 7 is blocked by the caller via can_train."""
    xp_bank = roster_entry.setdefault("attribute_xp", {})
    ranks = roster_entry.setdefault("trained_ranks", {})
    xp_bank[attribute] = xp_bank.get(attribute, 0) + xp
    gained = []
    while effective_rank(base_grid, roster_entry, attribute) < config.RANK_MAX:
        next_rank = ranks.get(attribute, 0) + 1
        cost = xp_for_rank(next_rank)
        if xp_bank[attribute] < cost:
            break
        xp_bank[attribute] -= cost
        ranks[attribute] = next_rank
        gained.append(next_rank)
    return {"ranks_gained": gained,
            "trained_rank": ranks.get(attribute, 0),
            "effective_rank": effective_rank(base_grid, roster_entry, attribute),
            "xp_banked": xp_bank[attribute],
            "perk_pending": pending_perk_tier(roster_entry, attribute)}


def pending_perk_tier(roster_entry, attribute):
    """The lowest §6.3 perk tier (trained rank 3 or 6) reached but not yet
    chosen for this attribute, or None."""
    trained = roster_entry.get("trained_ranks", {}).get(attribute, 0)
    chosen = roster_entry.setdefault("perk_choices", {})
    for tier in config.PERK_CHOICE_RANKS:
        if trained >= tier and f"{attribute}:{tier}" not in chosen:
            return tier
    return None


def choose_perk(roster_entry, attribute, tier, perk_id, perks_data):
    options = perk_options(attribute, tier, perks_data)
    if perk_id not in [p["id"] for p in options]:
        return {"ok": False, "message": f"'{perk_id}' is not an option for {attribute} {tier}"}
    key = f"{attribute}:{tier}"
    chosen = roster_entry.setdefault("perk_choices", {})
    if key in chosen:
        return {"ok": False, "message": "Perk already chosen for this tier."}
    chosen[key] = perk_id
    return {"ok": True, "message": f"Perk chosen: {perk_id}"}


def perk_options(attribute, tier, perks_data):
    return perks_data[attribute][str(tier)]


def perk_effects(roster_entry, perks_data):
    """Sum the flat effects of every chosen perk into one dict."""
    total = {}
    by_id = {p["id"]: p for attr in perks_data.values()
             for tier in attr.values() for p in tier}
    for perk_id in roster_entry.get("perk_choices", {}).values():
        for key, value in by_id[perk_id]["effect"].items():
            total[key] = total.get(key, 0) + value
    return total
