"""Daily energy (spec §6.1, per-character since M9). Pure Python — no pygame.

Every roster member carries their own energy 0-100. The TEAM energy is the
minimum across the active party (spec M9); team actions drain every party
member. state["energy"] mirrors team energy for HUD/save compatibility.
"""

from game import config


def hero_energy(state, hero_id):
    entry = state["roster"].get(hero_id)
    if entry is None:
        return 0
    return entry.setdefault("energy", config.DAILY_ENERGY)


def set_hero_energy(state, hero_id, value):
    entry = state["roster"].get(hero_id)
    if entry is not None:
        entry["energy"] = max(0, min(config.DAILY_ENERGY, value))


def party(state):
    return [h for h in state.get("party", []) if h in state.get("roster", {})]


def team_energy(state):
    members = party(state)
    if not members:
        return 0
    return min(hero_energy(state, h) for h in members)


def sync(state):
    """Mirror team energy into state['energy'] (HUD, pass-out checks)."""
    state["energy"] = team_energy(state)
    return state["energy"]


def can_afford(state, amount):
    return team_energy(state) >= amount


def spend(state, amount):
    """Team action: drain every party member. False (nothing spent) if the
    weakest member can't afford it."""
    if not can_afford(state, amount):
        sync(state)
        return False
    for hero_id in party(state):
        set_hero_energy(state, hero_id, hero_energy(state, hero_id) - amount)
    sync(state)
    return True


def drain(state, amount):
    """Team action that can't be refused (M11: engaging a battle): drain
    every party member, flooring at 0. Fighting on fumes is allowed — the
    cost is the M9 initiative penalty, and passing out after."""
    for hero_id in party(state):
        set_hero_energy(state, hero_id, hero_energy(state, hero_id) - amount)
    return sync(state)


def spend_hero(state, hero_id, amount):
    """Individual drain (e.g. the trainee in a training session)."""
    if hero_energy(state, hero_id) < amount:
        return False
    set_hero_energy(state, hero_id, hero_energy(state, hero_id) - amount)
    sync(state)
    return True


def is_exhausted(state):
    return team_energy(state) <= 0
