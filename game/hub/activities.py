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


def training_session(state, hero_id=None, attribute=None):
    """M2: costs only. M4 wires attribute XP onto this."""
    result = _spend(state, config.TRAINING_ENERGY, config.TRAINING_MINUTES)
    if result["ok"]:
        result["message"] = "Training session complete."
    return result


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
    """Multiplier applied to shop prices; events may discount (§7)."""
    discount = 1.0
    for ev in cal.active_events(state, calendar_data):
        discount = min(discount, ev.get("effects", {}).get("shop_discount", 1.0))
    return discount


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
