"""Hub activity definitions, costs, and effects (spec §6.1, §7).
Pure Python — no pygame.

perform() mutates the game state and returns a result dict:
    {"ok": bool, "message": str, ...}
Battles and sleep are not resolved here — the caller reacts to
{"launch_battle": ...} / {"sleep": True} markers in the result.
"""

from game import config
from game.core import calendar as cal
from game.core import clock, energy


def _spend(state, energy_cost, minutes):
    if not energy.can_afford(state, energy_cost):
        return {"ok": False, "message": "Too exhausted — sleep to recover."}
    energy.spend(state, energy_cost)
    hit_end = clock.advance(state, minutes)
    return {"ok": True, "hit_day_end": hit_end}


def training_cost(next_rank):
    """M9: EN and time scale with the rank being trained toward."""
    en = config.TRAINING_ENERGY_BASE + config.TRAINING_ENERGY_PER_RANK * next_rank
    minutes = config.TRAINING_MINUTES_BASE + config.TRAINING_MINUTES_PER_RANK * next_rank
    return en, minutes


def training_session(state):
    """Legacy generic session (M2 tests): rank-2 equivalent team costs.
    In-game training is the M12 lockout — start_training/finish_training."""
    result = _spend(state, *training_cost(2))
    if result["ok"]:
        result["message"] = "Training session complete."
    return result


def start_training(state, content, hero_id, attribute):
    """M12: training is a lockout, not a clock jump. The trainee pays the
    EN up front, leaves the party, and is unavailable until the in-game
    clock passes the session length (rank 1 = 1 h, +30 min per rank). XP
    (facility + banked battle XP double-dip) is granted on completion."""
    from game.progression import attributes as attrs

    character = content["characters"][hero_id]
    entry = state["roster"][hero_id]
    if entry.get("training"):
        return {"ok": False, "message": f"{character['name']} is already training."}
    if entry.get("dispatch"):
        return {"ok": False, "message": f"{character['name']} is away on assignment."}
    if not attrs.can_train(character["boosts"], entry, attribute):
        return {"ok": False, "message": f"{attribute.title()} is already at max."}
    party = state.get("party", [])
    if hero_id not in party:                # M12: rack is party-only, even via
        return {"ok": False,                # the perk-chooser fall-through
                "message": f"{character['name']} isn't on the team."}
    if len(party) <= 1:
        return {"ok": False, "message": "Someone has to stay on the team."}
    next_rank = entry.get("trained_ranks", {}).get(attribute, 0) + 1
    en_cost, minutes = training_cost(next_rank)
    # Strictly more EN than the cost: a session must not zero the trainee out
    # (they'd rejoin at 0 and instantly pass the team out).
    if energy.hero_energy(state, hero_id) <= en_cost:
        return {"ok": False, "message": f"{character['name']} is too exhausted."}
    energy.spend_hero(state, hero_id, en_cost)
    xp = attrs.session_xp(state, content["calendar"])
    banked = min(entry.get("unspent_xp", 0), xp)        # battle XP double-dips
    if banked:
        entry["unspent_xp"] = entry.get("unspent_xp", 0) - banked
    if hero_id in party:
        party.remove(hero_id)
    entry.pop("assignment", None)
    entry["idle_days"] = 0
    entry["training"] = {"attribute": attribute,
                         "ends": state["time_minutes"] + minutes,
                         "xp": xp + banked, "banked": banked}
    energy.sync(state)
    return {"ok": True, "minutes": minutes,
            "message": (f"{character['name']} hits the mats: "
                        f"{attribute.title()}, {minutes} min.")}


def finish_training(state, content, hero_id, rejoin=True):
    """Complete a training lockout: grant the XP, rejoin the party if there
    is room. rejoin=False when the team is away in a zone — the hero waits
    benched at the tower instead of teleporting into the field. Returns the
    result dict (with perk_pending when a choice waits)."""
    from game.progression import attributes as attrs
    from game.progression import mastery

    character = content["characters"][hero_id]
    entry = state["roster"][hero_id]
    lock = entry.pop("training", None)
    if not lock:
        return {"ok": False, "message": "They're not training."}
    gain = attrs.add_training_xp(character["boosts"], entry,
                                 lock["attribute"], lock["xp"])
    entry["idle_days"] = 0
    message = (f"{character['name']} finishes training "
               f"{lock['attribute'].title()}: +{lock['xp']} XP")
    if lock.get("banked"):
        message += f" ({lock['banked']} banked)"
    if gain["ranks_gained"]:
        message += (f" - rank up! ({gain['rank']}/{config.RANK_MAX}, "
                    f"combat {gain['effective_rank']:.1f})")
    if mastery.update_mastery(character["boosts"], entry):
        message += "  MASTERED - the card goes foil!"
    party = state.setdefault("party", [])
    if rejoin and hero_id not in party and len(party) < config.PARTY_SIZE_MAX:
        party.append(hero_id)
        message += "  Back on the team."
    elif not rejoin:
        message += "  Waiting at the tower."
    energy.sync(state)
    return {"ok": True, "message": message, **gain}


def finish_due_training(state, content, force=False, rejoin=True):
    """Complete every training lockout whose time has passed (or all of
    them with force=True, used at sleep). Pass rejoin=False while the team
    is out in a zone. Returns messages."""
    messages = []
    for hero_id in sorted(state.get("roster", {})):
        lock = state["roster"][hero_id].get("training")
        if lock and (force or state["time_minutes"] >= lock["ends"]):
            messages.append(finish_training(state, content, hero_id,
                                            rejoin=rejoin)["message"])
    return messages


def craft(state):
    result = _spend(state, config.CRAFT_ENERGY, config.CRAFT_MINUTES)
    if result["ok"]:
        result["message"] = "Crafting session complete."
    return result


def launch_mission(state, mission_id="hydra_patrol"):
    """M11: engaging is never blocked by low EN. The team drains toward 0
    and fights with the M9 initiative penalty instead of being refused."""
    energy.drain(state, config.MISSION_ENERGY)
    hit_end = clock.advance(state, config.MISSION_MINUTES)
    return {"ok": True, "hit_day_end": hit_end, "launch_battle": mission_id,
            "message": "Mission launched."}


def assignment_tasks_today(state, assignments, tier=1):
    """Two rotating tasks per day from each unlocked tier's pool (§7; M10
    dispatches, M11 tiers). Pass tier = dispatch.roster_tier(...).

    M15: jobs whose story-flag / relationship / once-only gate is shut are
    not posted at all. Hidden SKILL requirements don't hide a job — those
    surface as a Coulson refusal when you try to send the wrong hero.
    """
    from game.hub import requirements
    base = ((state["issue"] - 1) * config.DAYS_PER_ISSUE + state["day"] - 1) * 2
    today = []
    for level in range(1, tier + 1):
        pool = sorted((a for a in assignments if a.get("tier", 1) == level
                       and requirements.gate_open(state, a)),
                      key=lambda a: a["id"])
        if not pool:
            continue
        today.append(pool[base % len(pool)])
        if len(pool) > 1:
            today.append(pool[(base + 1) % len(pool)])
    return today


def eat_food(state, content, hero_id, item_id):
    """Eat a ration (M10): restores the item's EN to one hero, costs a few
    minutes, no energy. Anywhere — tower or field."""
    item = content["items"].get(item_id, {})
    restore = item.get("energy", 0)
    if not restore:
        return {"ok": False, "message": "That's not edible."}
    if state["inventory"].get(item_id, 0) <= 0:
        return {"ok": False, "message": f"No {item['name']} left."}
    if state["roster"].get(hero_id) is None:
        return {"ok": False, "message": "They're not on the roster."}
    before = energy.hero_energy(state, hero_id)
    if before >= config.DAILY_ENERGY:
        name = content["characters"][hero_id]["name"]
        return {"ok": False, "message": f"{name} is already at full energy."}
    state["inventory"][item_id] -= 1
    if state["inventory"][item_id] <= 0:
        del state["inventory"][item_id]
    energy.set_hero_energy(state, hero_id, before + restore)
    gained = energy.hero_energy(state, hero_id) - before
    energy.sync(state)
    hit_end = clock.advance(state, config.EAT_MINUTES)
    name = content["characters"][hero_id]["name"]
    return {"ok": True, "hit_day_end": hit_end,
            "message": f"{name} eats the {item['name']}: +{gained} EN."}


def search_spot_key(zone_id, tx, ty):
    return f"{zone_id}:{tx},{ty}"


def spot_searched(state, zone_id, tx, ty):
    return search_spot_key(zone_id, tx, ty) in state.get("searched_today", [])


def mark_spot_searched(state, zone_id, tx, ty):
    state.setdefault("searched_today", []).append(search_spot_key(zone_id, tx, ty))


def shop_discount(state, calendar_data):
    """Multiplier applied to shop prices; events and Pepper's requisitions
    (NPC bond unlock) may discount (§7)."""
    discount = 1.0
    for ev in cal.active_events(state, calendar_data):
        discount = min(discount, ev.get("effects", {}).get("shop_discount", 1.0))
    if state.get("story_flags", {}).get("pepper_requisitions"):
        discount = min(discount, config.PEPPER_SHOP_DISCOUNT)
    return discount


def mission_credits(state, base):
    """Coulson's intel network (NPC bond unlock) boosts mission credits."""
    if state.get("story_flags", {}).get("coulson_intel"):
        return int(base * config.COULSON_CREDIT_MULT)
    return base


def buy_item(state, item, discount=1.0):
    price = int(item["price"] * discount)
    if state["credits"] < price:
        return {"ok": False, "message": "Not enough credits."}
    state["credits"] -= price
    state["inventory"][item["id"]] = state["inventory"].get(item["id"], 0) + 1
    return {"ok": True, "message": f"Bought {item['name']} for {price} cr."}


def should_pass_out(state):
    """0 energy or 2 AM forces sleep with the §6.1 pass-out penalty."""
    return energy.is_exhausted(state) or clock.is_past_end(state)


def go_to_sleep(state, passed_out=False):
    cal.sleep(state, passed_out=passed_out)
    return {"ok": True, "sleep": True,
            "message": "You wake up groggy..." if passed_out else "A new day begins."}
