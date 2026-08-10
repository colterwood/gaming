"""Bond points, levels, talk/gift/mission gains, weekly limits (spec §6.2).
Pure Python — no pygame."""

from game import config


def ensure_bond(state, char_id):
    return state.setdefault("bonds", {}).setdefault(
        char_id, {"points": 0, "gifts_this_week": 0, "talked_today": False})


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


def is_birthday(state, character):
    return (character["birthday"]["issue"] == state["issue"]
            and character["birthday"]["day"] == state["day"])


def give_gift(state, character, item_id):
    """Give one inventory item as a gift (§6.2): category points, ×8 on the
    character's birthday, max 2 gifts per character per calendar week."""
    char_id = character["id"]
    bond = ensure_bond(state, char_id)
    if state["inventory"].get(item_id, 0) <= 0:
        return {"ok": False, "message": "You don't have that."}
    if bond["gifts_this_week"] >= config.GIFTS_PER_WEEK_MAX:
        return {"ok": False, "message": f"{character['name']} has had enough gifts this week."}
    state["inventory"][item_id] -= 1
    if state["inventory"][item_id] <= 0:
        del state["inventory"][item_id]
    bond["gifts_this_week"] += 1
    points = config.GIFT_POINTS[gift_category(character, item_id)]
    if is_birthday(state, character):
        points *= config.BIRTHDAY_GIFT_MULTIPLIER
    result = add_points(state, char_id, points)
    result.update(ok=True, message=f"{points:+d} bond"
                  + (" (birthday!)" if is_birthday(state, character) else ""))
    return result


def mission_bond(state, char_ids):
    """Same-party mission: +10 for every hero in the party (§6.2)."""
    return {cid: add_points(state, cid, config.BOND_MISSION_POINTS)
            for cid in char_ids}


def synergy_active(state, character, synergy):
    return bond_level(ensure_bond(state, character["id"])["points"]) >= synergy["requires_bond_level"]
