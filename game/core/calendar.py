"""Issues, days, weeks, birthdays, events, and the sleep sequence (spec §6.1,
§6.2, §7). Pure Python — no pygame.

An Issue is 28 days; weeks are the four 7-day rows (reset days 1/8/15/22).
"""

from game import config


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


def sleep(state, passed_out=False):
    """End the day (§7 sleep sequence, minus rendering): advance the calendar,
    reset energy and daily flags, reset weekly gift counters on week boundaries.
    Autosave is the caller's job (it owns the save slot)."""
    state["day"] += 1
    if state["day"] > config.DAYS_PER_ISSUE:
        state["day"] = 1
        state["issue"] += 1
    state["time_minutes"] = config.DAY_START_MINUTES
    state["energy"] = (config.PASS_OUT_NEXT_DAY_ENERGY if passed_out
                       else config.DAILY_ENERGY)
    state["assignments_done"] = []
    for bond in state.get("bonds", {}).values():
        bond["talked_today"] = False
        if is_gift_week_reset_day(state["day"]):
            bond["gifts_this_week"] = 0
    return state
