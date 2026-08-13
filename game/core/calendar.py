"""Issues, days, weeks, birthdays, events, and the sleep sequence (spec §6.1,
§6.2, §7). Pure Python — no pygame.

An Issue is 28 days; weeks are the four 7-day rows. (Gift limits are the
M12 rolling window in bonds.gift_allowed — nothing resets weekly anymore.)
"""

from game import config
from game.core import energy


def week_of_day(day):
    return (day - 1) // config.DAYS_PER_WEEK + 1


def is_gift_week_reset_day(day):
    return (day - 1) % config.DAYS_PER_WEEK == 0


def birthdays_today(state, characters):
    return [c["id"] for c in characters.values()
            if c["birthday"]["issue"] == state["issue"]
            and c["birthday"]["day"] == state["day"]]


def active_events(state, calendar_data):
    return [e for e in calendar_data.get("events", [])
            if e["issue"] == state["issue"]
            and e["start_day"] <= state["day"] <= e["end_day"]]


def passing_out_costs(state):
    """What a collapse takes out of the purse (M36): a tenth of it, capped.

    A percentage so it stays a real cost as the team gets rich, and a cap so
    it never becomes the only thing that matters once they are. Cheap at the
    bottom, which is correct — collapsing on Day 2 with 40 credits should
    sting, not end the run."""
    purse = max(0, state.get("credits", 0))
    return min(int(purse * config.PASS_OUT_CREDIT_PCT),
               config.PASS_OUT_CREDIT_MAX)


def sleep(state, passed_out=False, sheltered=False):
    """End the day (§7 sleep sequence, minus rendering): advance the calendar,
    reset energy, HP and daily flags. Gift limits are enforced by the rolling
    window in bonds.gift_allowed (M12) — nothing weekly happens here.
    Autosave is the caller's job (it owns the save slot).

    M36: `sheltered` says the team went down INSIDE THE TOWER. Collapsing on
    your own common floor is being carried to a bed by Jarvis; collapsing in
    the HYDRA District is a night in the HYDRA District. Only the second one
    costs a morning. The credit loss is charged either way — somebody always
    goes through your pockets, and the bill for the ward is the same.
    """
    from game.core import health

    state["day"] += 1
    if state["day"] > config.DAYS_PER_ISSUE:
        state["day"] = 1
        state["issue"] += 1
    state["time_minutes"] = config.DAY_START_MINUTES
    rough = passed_out and not sheltered
    bonus = (config.JARVIS_ENERGY_BONUS
             if not rough and state.get("story_flags", {}).get("jarvis_service")
             else 0)                                        # NPC bond unlock
    # M37: everybody wakes at their OWN ceiling, which Stamina raises. The
    # collapse penalty is a fraction of that rather than a flat 80, or a
    # Stamina-10 hero would be punished less than a Stamina-1 one.
    for entry in state.get("roster", {}).values():          # per-hero (M9)
        top = energy.max_for(entry)
        entry["energy"] = (int(top * config.PASS_OUT_ENERGY_FRACTION) if rough
                           else top + bonus)
    # state["energy"] mirrors the team for the HUD and the save. With nobody
    # ON the team there is no team figure, so mirror what a hero woke up
    # with — the best-rested one, or the notional rank-1 figure if the
    # roster is empty. Waking up is not being exhausted.
    default = (int(config.DAILY_ENERGY * config.PASS_OUT_ENERGY_FRACTION)
               if rough else config.DAILY_ENERGY + bonus)
    state["energy"] = (energy.team_energy(state) if state.get("party")
                       else max((e.get("energy", default)
                                 for e in state.get("roster", {}).values()),
                                default=default))
    health.restore_all(state, config.PASS_OUT_HP_FRACTION if passed_out
                       else config.SLEEP_HP_FRACTION)
    if passed_out:
        state["credits"] = state.get("credits", 0) - passing_out_costs(state)
    state["searched_today"] = []                            # crates respawn (M10)
    state["fights_today"] = {}                              # zones re-arm (M36)
    for bond in state.get("bonds", {}).values():
        bond["talked_today"] = False
        # Gift limits are a rolling window since M12 (bonds.gift_allowed);
        # nothing weekly to reset.
    return state
