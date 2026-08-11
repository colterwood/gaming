"""Attribute training XP, trained ranks, perk choices (spec §6.3).
Pure Python — no pygame.

Roster entry shape (in the save state):
    {"trained_ranks": {attr: n}, "attribute_xp": {attr: xp},
     "perks": ["haymaker", ...], ...}
"""

from game import config
from game.combat import formulas
from game.core import calendar as cal


def boost_weight(boost):
    """Cost multiplier for training an attribute you have `boost` talent in
    (M16b). Talent makes the climb cheaper; no talent makes it a slog."""
    return max(0.1, config.BOOST_XP_WEIGHT_BASE
               - config.BOOST_XP_WEIGHT_STEP * boost)


def xp_for_rank(n, boost=0):
    """XP to climb FROM level n to n+1 (§6.3, 1.5x growth since M16),
    scaled by the hero's innate talent for that attribute (M16b).
    `n` is the level being trained, 1..TRAINED_MAX."""
    base = config.XP_TO_NEXT_RANK[max(1, min(config.TRAINED_MAX, n))]
    return int(round(base * boost_weight(boost)))


def rank(roster_entry, attribute):
    """The plain trainable level, 1..RANK_MAX (M15) — what task
    requirements and the card's bar length talk about."""
    trained = min(config.TRAINED_MAX,
                  roster_entry.get("trained_ranks", {}).get(attribute, 0))
    return config.RANK_START + trained


def boost(boosts, attribute):
    return (boosts or {}).get(attribute, 0)


def effective_rank(boosts, roster_entry, attribute):
    """Combat rank (M15): trained rank lifted by the innate boost."""
    return formulas.effective_rank(rank(roster_entry, attribute),
                                   boost(boosts, attribute))


def can_train(boosts, roster_entry, attribute):
    """Trained ranks run 0..TRAINED_MAX (rank 1..RANK_MAX). They gate perks
    (trained 3/6) and Mastery (every attribute at RANK_MAX)."""
    return roster_entry.get("trained_ranks", {}).get(attribute, 0) < config.TRAINED_MAX


def facility_multiplier(state, calendar_data):
    """×1 basic / ×2 upgraded facility / ×3 during a training event (§6.3)."""
    for ev in cal.active_events(state, calendar_data):
        if "training_xp_bonus" in ev.get("effects", {}):
            return config.TRAINING_XP_MULT_EVENT
    if state.get("story_flags", {}).get("training_upgraded"):
        return config.TRAINING_XP_MULT_UPGRADED
    return config.TRAINING_XP_MULT_BASIC


def session_xp(state, calendar_data, level=1):
    """XP one rack session yields at the given level (M16 table), scaled by
    the facility multiplier."""
    level = max(1, min(config.TRAINED_MAX, level))
    return (config.TRAINING_XP_BY_LEVEL[level]
            * facility_multiplier(state, calendar_data))


def add_training_xp(boosts, roster_entry, attribute, xp):
    """Bank XP and consume it into trained ranks (0..TRAINED_MAX). Multiple
    rank-ups can occur; training past the cap is blocked by can_train."""
    xp_bank = roster_entry.setdefault("attribute_xp", {})
    ranks = roster_entry.setdefault("trained_ranks", {})
    xp_bank[attribute] = xp_bank.get(attribute, 0) + xp
    gained = []
    talent = boost(boosts, attribute)
    while ranks.get(attribute, 0) < config.TRAINED_MAX:
        next_rank = ranks.get(attribute, 0) + 1
        cost = xp_for_rank(next_rank, talent)
        if xp_bank[attribute] < cost:
            break
        xp_bank[attribute] -= cost
        ranks[attribute] = next_rank
        gained.append(next_rank)
    return {"ranks_gained": gained,
            "trained_rank": ranks.get(attribute, 0),
            "rank": rank(roster_entry, attribute),
            "effective_rank": effective_rank(boosts, roster_entry, attribute),
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


def sanitize_perk_choices(roster_entry, perks_data):
    """Drop perk ids that no longer exist in perks.json (content updates)."""
    valid = {p["id"] for attr in perks_data.values() for tier in attr.values() for p in tier}
    chosen = roster_entry.get("perk_choices", {})
    for key in [k for k, pid in chosen.items() if pid not in valid]:
        del chosen[key]


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
        perk = by_id.get(perk_id)
        if perk is None:            # stale id from an older save/content update
            continue
        for key, value in perk["effect"].items():
            total[key] = total.get(key, 0) + value
    return total
