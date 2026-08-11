"""Hub activity definitions, costs, and effects (spec §6.1, §7).
Pure Python — no pygame.

perform() mutates the game state and returns a result dict:
    {"ok": bool, "message": str, ...}
Battles and sleep are not resolved here — the caller reacts to
{"launch_battle": ...} / {"sleep": True} markers in the result.
"""

from game import config
from game.core import calendar as cal
from game.core import clock, energy, inventory


def _spend(state, energy_cost, minutes):
    if not energy.can_afford(state, energy_cost):
        return {"ok": False, "message": "Too exhausted — sleep to recover."}
    energy.spend(state, energy_cost)
    hit_end = clock.advance(state, minutes)
    return {"ok": True, "hit_day_end": hit_end}


def training_cost(level):
    """EN and lockout minutes for one rack session (M9 energy scaling, M16
    minute table). `level` is the level being trained FROM, 1..TRAINED_MAX;
    a high-level session legitimately runs longer than a single day."""
    level = max(1, min(config.TRAINED_MAX, level))
    en = config.TRAINING_ENERGY_BASE + config.TRAINING_ENERGY_PER_RANK * level
    return en, config.TRAINING_MINUTES_BY_LEVEL[level]


def training_session(state):
    """Legacy generic session (M2 tests): rank-2 equivalent team costs.
    In-game training is the M12 lockout — start_training/finish_training."""
    result = _spend(state, *training_cost(2))
    if result["ok"]:
        result["message"] = "Training session complete."
    return result


def start_training(state, content, hero_id, attribute):
    """M12: training is a lockout, not a clock jump. The trainee pays the
    EN up front, leaves the party, and is unavailable until they have put
    in the session's hours (M16: measured in WAKING minutes, so a
    high-level session genuinely spans several days). The session's XP
    (facility-multiplied) is granted on completion. M21: there is no
    battle-XP top-up any more — field XP lands on attributes when it is
    earned, not the next time someone uses the rack."""
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
    level = attrs.rank(entry, attribute)
    en_cost, minutes = training_cost(level)
    # Strictly more EN than the cost: a session must not zero the trainee out
    # (they'd rejoin at 0 and instantly pass the team out).
    if energy.hero_energy(state, hero_id) <= en_cost:
        return {"ok": False, "message": f"{character['name']} is too exhausted."}
    energy.spend_hero(state, hero_id, en_cost)
    xp = attrs.session_xp(state, content["calendar"], level)
    if hero_id in party:
        party.remove(hero_id)
    entry.pop("assignment", None)
    entry["idle_days"] = 0
    # "ends_abs" (not the old within-day "ends") so a pre-M16 save's lock is
    # distinguishable and can be migrated — see migrate_training_locks.
    entry["training"] = {"attribute": attribute,
                         "ends_abs": clock.absolute_minutes(state) + minutes,
                         "xp": xp}
    energy.sync(state)
    return {"ok": True, "minutes": minutes,
            "message": (f"{character['name']} hits the mats: "
                        f"{attribute.title()}, "
                        f"{clock.format_duration(minutes)}.")}


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


def migrate_training_locks(state):
    """Save migration (M16): pre-M16 locks stored "ends" as a minute-of-day
    (360..1560); M16 stores "ends_abs" in campaign-wide waking minutes.
    Carry the remaining time over so an in-flight session isn't cancelled
    or stretched by decades."""
    for entry in state.get("roster", {}).values():
        lock = entry.get("training")
        if lock and "ends_abs" not in lock:
            owed = max(0, lock.pop("ends", 0) - state["time_minutes"])
            lock["ends_abs"] = clock.absolute_minutes(state) + owed


def training_remaining(state, lock):
    """Waking minutes still owed on a session (M16), never negative."""
    return max(0, lock["ends_abs"] - clock.absolute_minutes(state))


def finish_due_training(state, content, force=False, rejoin=True):
    """Complete every training lockout whose hours are served. M16: a
    session spans as many days as its length demands — sleeping banks the
    rest of that day's waking hours rather than short-circuiting it. Pass
    force=True to settle everything regardless, rejoin=False while the team
    is out in a zone. Returns messages."""
    messages = []
    for hero_id in sorted(state.get("roster", {})):
        lock = state["roster"][hero_id].get("training")
        if lock and (force or training_remaining(state, lock) <= 0):
            messages.append(finish_training(state, content, hero_id,
                                            rejoin=rejoin)["message"])
    return messages


def craft(state):
    result = _spend(state, config.CRAFT_ENERGY, config.CRAFT_MINUTES)
    if result["ok"]:
        result["message"] = "Crafting session complete."
    return result


def launch_mission(state, mission_id="hydra_patrol"):
    """M11: engaging is never blocked by low EN — the team drains toward 0
    and fights with the M9 initiative penalty rather than being refused.

    M18: but a team that COLLAPSES on the approach (drained to 0, or the
    three hours run past 2 AM) never makes contact. No battle, and the
    mission stays exactly as it was — it has to be run again after a
    night's sleep."""
    energy.drain(state, config.MISSION_ENERGY)
    hit_end = clock.advance(state, config.MISSION_MINUTES)
    if should_pass_out(state):
        return {"ok": True, "hit_day_end": hit_end, "passed_out": True,
                "message": ("The team never reaches the target - they're "
                            "spent. The mission will have to keep.")}
    return {"ok": True, "hit_day_end": hit_end, "launch_battle": mission_id,
            "message": "Mission launched."}


def _abs_day(state):
    return (state["issue"] - 1) * config.DAYS_PER_ISSUE + state["day"]


def board_checked_today(state):
    """Has anyone actually walked up to the assignment board today (M20)?
    Until they have, the pause card can't list what's posted."""
    return state.get("board_checked_day") == _abs_day(state)


def check_board(state):
    """Called when the player opens the board in person."""
    state["board_checked_day"] = _abs_day(state)


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
        open_here = [a for a in assignments if a.get("tier", 1) == level
                     and requirements.gate_open(state, a)]
        # M16: a job with its own posting chance already won a dice roll to
        # be here — it doesn't also have to win the rotation lottery.
        today.extend(sorted((a for a in open_here if a.get("posting")),
                            key=lambda a: a["id"]))
        pool = sorted((a for a in open_here if not a.get("posting")),
                      key=lambda a: a["id"])
        if not pool:
            continue
        today.append(pool[base % len(pool)])
        if len(pool) > 1:
            today.append(pool[(base + 1) % len(pool)])
    return today


def eat_food(state, content, item_id):
    """Break out a ration (M10; M18: the TEAM shares it). Every active
    party member gets the item's EN, capped at the daily max — team energy
    is the minimum across the party, so feeding one hero moved nothing.
    Costs a few minutes, no energy. Anywhere — tower or field."""
    item = content["items"].get(item_id, {})
    restore = item.get("energy", 0)
    if not restore:
        return {"ok": False, "message": "That's not edible."}
    if state["inventory"].get(item_id, 0) <= 0:
        return {"ok": False, "message": f"No {item['name']} left."}
    members = energy.party(state)
    if not members:
        return {"ok": False, "message": "Nobody on the team to eat it."}
    if all(energy.hero_energy(state, h) >= config.DAILY_ENERGY for h in members):
        return {"ok": False, "message": "The team is already at full energy."}
    inventory.remove(state, item_id, 1)
    before = energy.team_energy(state)
    for hero_id in members:
        energy.set_hero_energy(state, hero_id,
                               energy.hero_energy(state, hero_id) + restore)
    after = energy.sync(state)
    hit_end = clock.advance(state, config.EAT_MINUTES)
    return {"ok": True, "hit_day_end": hit_end, "gained": after - before,
            "message": (f"The team shares the {item['name']}: +{restore} EN "
                        f"each - team EN {before} to {after}.")}


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
    if inventory.room_for(state, item["id"]) <= 0:      # M18: check BEFORE
        return {"ok": False,                            # taking their money
                "message": f"No room for it - {inventory.label(state)}."}
    state["credits"] -= price
    inventory.add(state, item["id"], 1)
    return {"ok": True, "message": f"Bought {item['name']} for {price} cr."}


def should_pass_out(state):
    """0 energy or 2 AM forces sleep with the §6.1 pass-out penalty."""
    return energy.is_exhausted(state) or clock.is_past_end(state)


def go_to_sleep(state, passed_out=False):
    cal.sleep(state, passed_out=passed_out)
    return {"ok": True, "sleep": True,
            "message": "You wake up groggy..." if passed_out else "A new day begins."}
