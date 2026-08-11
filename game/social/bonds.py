"""Bond points, levels, talk/gift/mission gains, weekly limits (spec §6.2).
Pure Python — no pygame."""

from game import config


def ensure_bond(state, char_id):
    return state.setdefault("bonds", {}).setdefault(
        char_id, {"points": 0, "talked_today": False,
                  "gift_days": [], "last_gift": None})


def _abs_day(state):
    return (state["issue"] - 1) * config.DAYS_PER_ISSUE + state["day"]


def gift_allowed(state, char_id):
    """M12 limits: 1 gift per receiver per day, GIFTS_PER_WINDOW per rolling
    GIFT_WINDOW_DAYS. Returns (ok, reason); also trims the day log."""
    bond = ensure_bond(state, char_id)
    today = _abs_day(state)
    days = [d for d in bond.setdefault("gift_days", [])
            if today - d < config.GIFT_WINDOW_DAYS]
    bond["gift_days"] = days
    if today in days:
        return False, "already got a gift today"
    if len(days) >= config.GIFTS_PER_WINDOW:
        return False, "has had plenty of gifts lately"
    return True, ""


def bond_level(points):
    return min(points // config.BOND_POINTS_PER_LEVEL, config.BOND_LEVEL_MAX)


def add_points(state, char_id, amount):
    """Apply a bond change, clamped to [0, lifetime max]. Returns a result with
    level_up set when a new level was reached."""
    bond = ensure_bond(state, char_id)
    before_level = bond_level(bond["points"])
    bond["points"] = max(0, min(config.BOND_LIFETIME_MAX, bond["points"] + amount))
    after_level = bond_level(bond["points"])
    return {"points": bond["points"], "level": after_level,
            "gained": amount, "level_up": after_level > before_level}


def talk(state, char_id):
    """Daily talk: +15, once per day per character (§6.2)."""
    bond = ensure_bond(state, char_id)
    if bond["talked_today"]:
        return {"ok": False, "message": "Already talked today."}
    bond["talked_today"] = True
    result = add_points(state, char_id, config.BOND_TALK_POINTS)
    result.update(ok=True, message=f"+{config.BOND_TALK_POINTS} bond")
    return result


def gift_category(character, item_id):
    for category in ("loved", "liked", "disliked", "hated"):
        if item_id in character["gifts"][category]:
            return category
    return "neutral"


# Reaction flavor so gift relevance is visible in play (M11)
GIFT_REACTIONS = {
    "loved": "loves it!",
    "liked": "likes it.",
    "neutral": "accepts it politely.",
    "disliked": "frowns at it.",
    "hated": "hates it!",
}


def is_birthday(state, character):
    return (character["birthday"]["issue"] == state["issue"]
            and character["birthday"]["day"] == state["day"])


def give_gift(state, character, item_id):
    """Give one inventory item as a gift: category points, ×8 on the
    character's birthday. M12 limits: 1/day per receiver, GIFTS_PER_WINDOW
    per rolling GIFT_WINDOW_DAYS, and repeating yesterday's gift costs
    GIFT_REPEAT_PENALTY points."""
    char_id = character["id"]
    bond = ensure_bond(state, char_id)
    if state["inventory"].get(item_id, 0) <= 0:
        return {"ok": False, "message": "You don't have that."}
    ok, reason = gift_allowed(state, char_id)
    if not ok:
        return {"ok": False, "message": f"{character['name']} {reason}."}
    state["inventory"][item_id] -= 1
    if state["inventory"][item_id] <= 0:
        del state["inventory"][item_id]
    today = _abs_day(state)
    bond["gift_days"].append(today)
    category = gift_category(character, item_id)
    points = config.GIFT_POINTS[category]
    if is_birthday(state, character):
        points *= config.BIRTHDAY_GIFT_MULTIPLIER
    last = bond.get("last_gift")
    repeated = bool(last and last["item"] == item_id
                    and last["day"] == today - 1)
    if repeated:
        points -= config.GIFT_REPEAT_PENALTY
    bond["last_gift"] = {"item": item_id, "day": today}
    result = add_points(state, char_id, points)
    message = f"{GIFT_REACTIONS[category]} {points:+d} bond"
    if repeated:
        message += " (the same again?)"
    if is_birthday(state, character):
        message += " (birthday!)"
    result.update(ok=True, category=category, repeated=repeated,
                  message=message)
    return result


def mission_bond(state, char_ids):
    """Same-party mission: +10 for every hero in the party (§6.2)."""
    return {cid: add_points(state, cid, config.BOND_MISSION_POINTS)
            for cid in char_ids}


def synergy_active(state, character, synergy):
    if synergy.get("innate"):       # e.g. Old Friends: IM + Cap need no bonding
        return True
    return bond_level(ensure_bond(state, character["id"])["points"]) >= synergy["requires_bond_level"]


def bondable(character):
    """Relationship redesign: only bond-recruits (Hulk) and NPCs build bonds.
    Starters and story recruits get flavor talk, no points."""
    return character["recruit"]["method"] in ("bond", "npc")


def check_bond_progress(state, content):
    """Apply bond-gated effects: bond-recruits joining the roster and NPC
    unlock flags. Returns messages for whatever newly triggered."""
    messages = []
    for char in content["characters"].values():
        level = bond_level(ensure_bond(state, char["id"])["points"])
        recruit = char["recruit"]
        if (recruit["method"] == "bond" and char["id"] not in state["roster"]
                and level >= recruit["bond_level"]):
            state["roster"][char["id"]] = {"trained_ranks": {}, "attribute_xp": {},
                                           "perks": [], "perk_choices": {},
                                           "gear": {}, "ult_charge": 0,
                                           "energy": config.DAILY_ENERGY,
                                           "unspent_xp": 0}
            messages.append(f"{char['name']} joins the roster!")
        for unlock in char.get("bond_unlocks", []):
            flags = state.setdefault("story_flags", {})
            if level >= unlock["level"] and not flags.get(unlock["flag"]):
                flags[unlock["flag"]] = True
                messages.append(unlock["message"])
    return messages
