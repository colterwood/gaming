"""In-game time (spec §6.1). Pure Python — no pygame.

Time is minutes since midnight on state["time_minutes"]; the day runs
6:00 (360) to 26:00 (1560, i.e. 2 AM). Activities advance the clock in
fixed jumps; the cosmetic tick advances it 10 minutes per 7 real seconds.
"""

from game import config


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
