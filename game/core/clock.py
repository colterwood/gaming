"""In-game time (spec §6.1). Pure Python — no pygame.

Time is minutes since midnight on state["time_minutes"]; the day runs
6:00 (360) to 26:00 (1560, i.e. 2 AM). Activities advance the clock in
fixed jumps; the cosmetic tick advances it 10 minutes per 7 real seconds.
"""

from game import config


DAY_MINUTES = config.DAY_END_MINUTES - config.DAY_START_MINUTES


def absolute_minutes(state):
    """Waking minutes elapsed since the campaign began (M16). Nights are
    not counted — a multi-day training lockout is measured in the hours the
    hero is actually awake to work, so sleeping banks the rest of the day."""
    day_index = ((state["issue"] - 1) * config.DAYS_PER_ISSUE
                 + state["day"] - 1)
    into_today = min(DAY_MINUTES,
                     max(0, state["time_minutes"] - config.DAY_START_MINUTES))
    return day_index * DAY_MINUTES + into_today


def format_duration(minutes):
    """'2400' -> '2d 0h', '150' -> '2h 30m'."""
    minutes = max(0, int(minutes))
    days, rest = divmod(minutes, DAY_MINUTES)
    hours, mins = divmod(rest, 60)
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {mins:02d}m"
    return f"{mins}m"


def advance(state, minutes):
    """Advance the clock. Returns True if the day-end boundary (2 AM) was hit."""
    state["time_minutes"] = min(config.DAY_END_MINUTES, state["time_minutes"] + minutes)
    return state["time_minutes"] >= config.DAY_END_MINUTES


def is_past_end(state):
    return state["time_minutes"] >= config.DAY_END_MINUTES


def format_time(minutes):
    """1560 -> '2:00 AM' (next day); 390 -> '6:30 AM'."""
    m = minutes % (24 * 60)
    hour = m // 60
    minute = m % 60
    suffix = "AM" if hour < 12 else "PM"
    display_hour = hour % 12
    if display_hour == 0:
        display_hour = 12
    return f"{display_hour}:{minute:02d} {suffix}"
