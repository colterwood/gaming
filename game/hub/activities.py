"""Hub activity definitions, costs, and effects (spec §6.1, §7).
Pure Python — no pygame.

perform() mutates the game state and returns a result dict:
    {"ok": bool, "message": str, ...}
Battles and sleep are not resolved here — the caller reacts to
{"launch_battle": ...} / {"sleep": True} markers in the result.
"""

import math

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
    minute table, M36 lockout multiplier). `level` is the level being
    trained FROM, 1..TRAINED_MAX; a high-level session legitimately runs
    longer than a single day."""
    level = max(1, min(config.TRAINED_MAX, level))
    en = config.TRAINING_ENERGY_BASE + config.TRAINING_ENERGY_PER_RANK * level
    return en, (config.TRAINING_MINUTES_BY_LEVEL[level]
                * config.TRAINING_LOCKOUT_MULT)


def training_credits(level):
    """What one rack session costs at the door (M36) — a credit for every
    XP the BASIC facility pays, so the x2 upgraded rack is also half price
    per XP and a training event is a third.

    The credit price is the lever that actually bites early. Sessions per
    day are energy-bound below level 6, so the lockout multiplier does
    nothing at ranks 2-6; the door charge is paid every session at every
    level."""
    level = max(1, min(config.TRAINED_MAX, level))
    return config.TRAINING_CREDITS_BY_LEVEL[level]


def training_session(state):
    """Legacy generic session (M2 tests): rank-2 equivalent team costs.
    In-game training is the M12 lockout — start_training/finish_training."""
    result = _spend(state, *training_cost(2))
    if result["ok"]:
        result["message"] = "Training session complete."
    return result


def start_training(state, content, hero_id, attribute, solo_ok=False):
    """M12: training is a lockout, not a clock jump. The trainee pays the
    EN up front, leaves the party, and is unavailable until they have put
    in the session's hours (M16: measured in WAKING minutes, so a
    high-level session genuinely spans several days). The session's XP
    (facility-multiplied) is granted on completion. M21: there is no
    battle-XP top-up any more — field XP lands on attributes when it is
    earned, not the next time someone uses the rack."""
    from game.progression import attributes as attrs
    from game.progression import mastery

    character = content["characters"][hero_id]
    entry = state["roster"][hero_id]
    capstone = attribute == mastery.ATTRIBUTE       # the rung above rank 10
    if entry.get("training"):
        return {"ok": False, "message": f"{character['name']} is already training."}
    if entry.get("dispatch"):
        return {"ok": False, "message": f"{character['name']} is away on assignment."}
    if capstone:
        if not mastery.available(entry):
            return {"ok": False,
                    "message": (f"{character['name']} has to reach rank "
                                f"{config.RANK_MAX} in all six first.")}
    elif not attrs.can_train(character["boosts"], entry, attribute):
        return {"ok": False, "message": f"{attribute.title()} is already at max."}
    party = state.get("party", [])
    if hero_id not in party:                # M12: rack is party-only, even via
        return {"ok": False,                # the perk-chooser fall-through
                "message": f"{character['name']} isn't on the team."}
    # The capstone is trained like a tenth rank: the hardest session there
    # is, over and over, 51,200 XP deep.
    level = config.RANK_MAX if capstone else attrs.rank(entry, attribute)
    en_cost, minutes = training_cost(level)
    # EVERY reason this session simply cannot happen is checked BEFORE the
    # solo question below. Asking "this will leave nobody on the team, are
    # you sure?" and only then saying "you can't afford it anyway" wastes
    # the player's decision on a session that was never going to start.
    #
    # Strictly more EN than the cost: a session must not zero the trainee
    # out (they'd rejoin at 0 and instantly pass the team out).
    if energy.hero_energy(state, hero_id) <= en_cost:
        return {"ok": False, "message": f"{character['name']} is too exhausted."}
    # M36: the rack bills at the door, checked before anything is spent —
    # the same discipline as buy_item.
    price = training_credits(level)
    if state.get("credits", 0) < price:
        return {"ok": False,
                "message": (f"The rack wants {price} cr - you have "
                            f"{state.get('credits', 0)}.")}
    if len(party) <= 1 and not solo_ok:
        # Not a refusal — a question. The caller offers to promote a benched
        # hero, or to just stand and watch, then calls back with solo_ok.
        return {"ok": False, "needs_solo_confirm": True,
                "message": "That would leave nobody on the team."}
    state["credits"] = state.get("credits", 0) - price
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
    return {"ok": True, "minutes": minutes, "credits": price,
            "message": (f"{character['name']} hits the mats: "
                        f"{attribute.title()}, "
                        f"{clock.format_duration(minutes)}, {price} cr.")}


def finish_training(state, content, hero_id, rejoin=False):
    """Complete a training lockout and grant the XP.

    M36: the hero does NOT rejoin the party. They finish the session and
    stay standing at the mats, and the player walks up to the training
    floor and puts them back on the team in person — the same way a
    dispatched hero is recalled (M13) and a Pym bench upgrade is collected
    (M32). The rack used to teleport them onto the team from anywhere in
    the world, which made the training floor a vending machine.

    `rejoin` is kept for callers that genuinely want the old behaviour;
    nothing in the game passes it any more."""
    from game.progression import attributes as attrs
    from game.progression import mastery

    character = content["characters"][hero_id]
    entry = state["roster"][hero_id]
    lock = entry.pop("training", None)
    if not lock:
        return {"ok": False, "message": "They're not training."}
    entry["idle_days"] = 0
    if lock["attribute"] == mastery.ATTRIBUTE:
        result = mastery.add_enlightenment_xp(entry, lock["xp"])
        done, needed = mastery.progress(entry)
        gain = {"ranks_gained": [], "enlightenment": result}
        message = (f"{character['name']} sits with it: +{lock['xp']} toward "
                   f"Enlightenment ({done}/{needed})")
        if result["complete"]:
            message += "  ENLIGHTENED."
    else:
        gain = attrs.add_training_xp(character["boosts"], entry,
                                     lock["attribute"], lock["xp"])
        message = (f"{character['name']} finishes training "
                   f"{lock['attribute'].title()}: +{lock['xp']} XP")
        if gain["ranks_gained"]:
            message += (f" - rank up! ({gain['rank']}/{config.RANK_MAX}, "
                        f"combat {gain['effective_rank']:.1f})")
        if mastery.update_mastery(character["boosts"], entry):
            message += "  All six at ten - Enlightenment opens at the rack!"
    party = state.setdefault("party", [])
    # M36: "collect them in person" is a good rule when you HAVE a team. With
    # nobody left it is a cage — the player watched their last hero train,
    # the session ended, and there was no one to walk over and fetch them
    # with. An empty team always gets its hero straight back.
    alone = not party
    if (rejoin or alone) and hero_id not in party \
            and len(party) < config.PARTY_SIZE_MAX:
        party.append(hero_id)
        entry.pop("done_training", None)
        message += ("  Back on their feet - and back on the team." if alone
                    else "  Back on the team.")
    elif hero_id not in party:
        # They are standing on the training floor until fetched. The flag is
        # what puts "Put them back on the team" on the rack menu.
        entry["done_training"] = True
        message += "  Waiting at the mats."
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


def finish_due_training(state, content, force=False, rejoin=False):
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

    M18: but a team that COLLAPSES on the approach never makes contact. No
    battle, and the mission stays exactly as it was.

    M36: that rule is now about ENERGY only. Running past 2 AM on the way
    in used to cancel the fight and roll the day over, so a mission started
    at 11 PM simply evaporated. The clock no longer refuses anyone: engage
    at 1:55 AM, fight the fight, and pass out on the other side of it —
    the hub's own pass-out check picks the team up when the battle ends."""
    energy.drain(state, config.MISSION_ENERGY)
    hit_end = clock.advance(state, config.MISSION_MINUTES)
    if bool(energy.party(state)) and energy.is_exhausted(state):
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


def can_rest(state):
    """(ok, reason) for sitting down in the Med Bay (M30)."""
    from game.core import health
    members = energy.party(state)
    if not members:
        return False, "Nobody here to treat."
    if (all(energy.hero_energy(state, h) >= config.DAILY_ENERGY
            for h in members)
            and not health.party_needs_treatment(state)):
        return False, "The team is already at full strength."
    return True, ""


def rest_tick(state):
    """One tick of treatment: MEDBAY_TICK_MINUTES off the clock for
    MEDBAY_ENERGY_PER_TICK energy to every active party member (capped at
    the daily maximum, like a ration).

    The Med Bay is the one place the day's energy cap can be bought back,
    and it is bought with the only other thing there is — hours. Benched
    heroes aren't treated; they wake up full anyway."""
    from game.core import health
    hit_end = clock.advance(state, config.MEDBAY_TICK_MINUTES)
    for hero_id in energy.party(state):
        energy.set_hero_energy(
            state, hero_id,
            energy.hero_energy(state, hero_id) + config.MEDBAY_ENERGY_PER_TICK)
    # M36: it is a MED bay. Now that HP is carried between fights, the chair
    # is the only way to buy it back without losing the day — same price in
    # hours, same rate.
    health.heal_party(state, config.MEDBAY_HP_PCT_PER_TICK)
    team = energy.sync(state)
    mended = not health.party_needs_treatment(state)
    return {"hit_day_end": hit_end, "team_energy": team,
            "team_hp": health.team_hp_fraction(state),
            "full": team >= config.DAILY_ENERGY and mended}


def treatment_forecast(state):
    """When the chair will be finished with the team (M36).

    The price of the Med Bay is hours, so the one number the player is
    actually deciding on is what time they will get up — and now that the
    chair mends HP as well as energy, "when" depends on whichever of the two
    is further behind. Returns minutes-of-day for each and for both, plus
    whether that lands past the end of the day (2 AM), in which case the
    team passes out in the chair instead of finishing.

    Both figures track the WORST-OFF party member, because team energy and
    team HP are both the minimum across the party.
    """
    from game.core import health

    def ticks(short, per_tick):
        return 0 if short <= 0 else int(math.ceil(short / per_tick))

    energy_ticks = ticks(config.DAILY_ENERGY - energy.team_energy(state),
                         config.MEDBAY_ENERGY_PER_TICK)
    hp_ticks = ticks(health.FULL - health.team_hp_fraction(state),
                     config.MEDBAY_HP_PCT_PER_TICK)
    now = state.get("time_minutes", config.DAY_START_MINUTES)
    both = max(energy_ticks, hp_ticks)
    return {
        "energy_minutes": energy_ticks * config.MEDBAY_TICK_MINUTES,
        "hp_minutes": hp_ticks * config.MEDBAY_TICK_MINUTES,
        "minutes": both * config.MEDBAY_TICK_MINUTES,
        "energy_at": now + energy_ticks * config.MEDBAY_TICK_MINUTES,
        "hp_at": now + hp_ticks * config.MEDBAY_TICK_MINUTES,
        "done_at": now + both * config.MEDBAY_TICK_MINUTES,
        "past_day_end": now + both * config.MEDBAY_TICK_MINUTES
                        > config.DAY_END_MINUTES,
    }


def eat_food(state, content, item_id):
    """Break out a ration (M10; M18: the TEAM shares it). Every active
    party member gets the item's EN, capped at the daily max — team energy
    is the minimum across the party, so feeding one hero moved nothing.
    Costs a few minutes, no energy. Anywhere — tower or field."""
    from game.core import health
    item = content["items"].get(item_id, {})
    restore = item.get("energy", 0)
    # M36: a med kit mends the team out of combat too, now that HP is
    # carried. Its in-battle `heal` is absolute HP; out here the same number
    # is read as a percentage of each hero's maximum, because out of combat
    # there is no one body to measure it against.
    mend = item.get("heal", 0) / 100.0 if item.get("heal") else 0.0
    if not restore and not mend:
        return {"ok": False, "message": "That's not edible."}
    if state["inventory"].get(item_id, 0) <= 0:
        return {"ok": False, "message": f"No {item['name']} left."}
    members = energy.party(state)
    if not members:
        return {"ok": False, "message": "Nobody on the team to eat it."}
    tired = any(energy.hero_energy(state, h) < config.DAILY_ENERGY
                for h in members)
    hurt = health.party_needs_treatment(state)
    if not (restore and tired) and not (mend and hurt):
        return {"ok": False, "message": "The team is already at full strength."}
    inventory.remove(state, item_id, 1)
    before = energy.team_energy(state)
    for hero_id in members:
        energy.set_hero_energy(state, hero_id,
                               energy.hero_energy(state, hero_id) + restore)
    if mend:
        health.heal_party(state, mend)
    after = energy.sync(state)
    hit_end = clock.advance(state, config.EAT_MINUTES)
    told = []
    if restore:
        told.append(f"+{restore} EN each - team EN {before} to {after}")
    if mend:
        told.append(f"+{int(mend * 100)}% HP each")
    return {"ok": True, "hit_day_end": hit_end, "gained": after - before,
            "message": f"The team shares the {item['name']}: {'; '.join(told)}."}


def search_spot_key(zone_id, tx, ty):
    return f"{zone_id}:{tx},{ty}"


def spot_searched(state, zone_id, tx, ty):
    return search_spot_key(zone_id, tx, ty) in state.get("searched_today", [])


def mark_spot_searched(state, zone_id, tx, ty):
    state.setdefault("searched_today", []).append(search_spot_key(zone_id, tx, ty))


# --- how much of a fight one block has left in it today (M36) -------------
# Ambushes and sprung trap squads are the same fight: no energy, full XP to
# everyone who swings. Uncapped, walking laps of the HYDRA District with a
# single hero was the fastest XP in the game by a factor of five — a fight
# every seven seconds of walking, and a solo hero collects the whole purse
# instead of a quarter of it. Counted per zone, cleared at sleep.

def fights_today(state, zone_id):
    return state.get("fights_today", {}).get(zone_id, 0)


def zone_is_quiet(state, zone_id):
    """True once this block has thrown everything it has at the team today."""
    return fights_today(state, zone_id) >= config.AMBUSH_DAILY_CAP


def record_fight(state, zone_id):
    fights = state.setdefault("fights_today", {})
    fights[zone_id] = fights.get(zone_id, 0) + 1
    return fights[zone_id]


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
    """0 energy or 2 AM forces sleep with the §6.1 pass-out penalty.

    M36: an EMPTY team is not an exhausted one. `team_energy` is the minimum
    across the party and floors at 0 with nobody in it, so the frame a solo
    trainee walked onto the mats the hub read it as a collapse and put the
    player to bed — they never saw a minute of the session they had just
    been asked to confirm. The 2 AM branch is deliberately untouched:
    watching someone train all night still ends the same way."""
    return ((bool(energy.party(state)) and energy.is_exhausted(state))
            or clock.is_past_end(state))


def go_to_sleep(state, passed_out=False, sheltered=False):
    """End the day. `sheltered` (M36) means the team went down indoors, at
    the tower — no energy penalty in the morning, because they were already
    home. The purse and the bruises are charged either way."""
    lost = cal.passing_out_costs(state) if passed_out else 0
    cal.sleep(state, passed_out=passed_out, sheltered=sheltered)
    if not passed_out:
        return {"ok": True, "sleep": True, "message": "A new day begins."}
    where = ("Jarvis got everyone to a bed." if sheltered
             else "Waking up where you dropped is its own punishment.")
    cost = f" It cost you {lost} cr." if lost else ""
    return {"ok": True, "sleep": True, "lost_credits": lost,
            "message": f"You wake up groggy... {where}{cost}"}
