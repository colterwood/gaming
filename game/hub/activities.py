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


def training_session(state, content=None, hero_id=None, attribute=None):
    """A supervised training session: drains the TRAINEE's energy (scaled by
    the rank being trained, M9), advances the clock, grants §6.3 facility XP
    plus any banked battle XP the hero has."""
    from game.progression import attributes as attrs
    from game.progression import mastery

    if not (content and hero_id and attribute):
        # legacy generic session (rank-2 equivalent costs)
        result = _spend(state, *training_cost(2))
        if result["ok"]:
            result["message"] = "Training session complete."
        return result

    character = content["characters"][hero_id]
    entry = state["roster"][hero_id]
    if not attrs.can_train(character["power_grid"], entry, attribute):
        return {"ok": False, "message": f"{attribute.title()} is already at max."}
    next_rank = entry.get("trained_ranks", {}).get(attribute, 0) + 1
    en_cost, minutes = training_cost(next_rank)
    if not energy.spend_hero(state, hero_id, en_cost):
        return {"ok": False, "message": f"{character['name']} is too exhausted."}
    hit_end = clock.advance(state, minutes)

    xp = attrs.session_xp(state, content["calendar"])
    banked = min(entry.get("unspent_xp", 0), xp)        # battle XP double-dips
    if banked:
        entry["unspent_xp"] = entry.get("unspent_xp", 0) - banked
    gain = attrs.add_training_xp(character["power_grid"], entry, attribute,
                                 xp + banked)
    message = f"{character['name']} trains {attribute.title()}: +{xp} XP"
    if banked:
        message += f" (+{banked} banked)"
    if gain["ranks_gained"]:
        message += f" - rank up! ({gain['effective_rank']}/{config.RANK_MAX})"
    if mastery.update_mastery(character["power_grid"], entry):
        message += "  MASTERED - the card goes foil!"
    return {"ok": True, "hit_day_end": hit_end, "message": message, **gain}


def craft(state):
    result = _spend(state, config.CRAFT_ENERGY, config.CRAFT_MINUTES)
    if result["ok"]:
        result["message"] = "Crafting session complete."
    return result


def launch_mission(state, mission_id="hydra_patrol"):
    result = _spend(state, config.MISSION_ENERGY, config.MISSION_MINUTES)
    if result["ok"]:
        result["launch_battle"] = mission_id
        result["message"] = "Mission launched."
    return result


def assignment_tasks_today(state, assignments):
    """Two rotating tasks per day from the assignment pool (§7)."""
    pool = sorted(assignments, key=lambda a: a["id"])
    if not pool:
        return []
    base = ((state["issue"] - 1) * config.DAYS_PER_ISSUE + state["day"] - 1) * 2
    return [pool[base % len(pool)], pool[(base + 1) % len(pool)]]


def do_assignment(state, task):
    if task["id"] in state.get("assignments_done", []):
        return {"ok": False, "message": "Already done today."}
    result = _spend(state, task["energy"], task.get("minutes", 60))
    if result["ok"]:
        state.setdefault("assignments_done", []).append(task["id"])
        state["credits"] += task["credits"]
        result["message"] = f"{task['name']} done: +{task['credits']} credits."
    return result


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
