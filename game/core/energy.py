"""Daily energy (spec §6.1, per-character since M9). Pure Python — no pygame.

Every roster member carries their own energy 0-100. The TEAM energy is the
minimum across the active party (spec M9); team actions drain every party
member. state["energy"] mirrors team energy for HUD/save compatibility.
"""

from game import config


def max_for(entry):
    """This hero's daily ceiling (M37).

    Stamina is the "how much can you get done in a day" attribute and it did
    nothing for the day — it bought HP and a little battle bulk and stopped
    there, while the thing it is named after was a flat 100 for everybody.

    The bonus accelerates (`ENERGY_BY_STAMINA_RANK`, cumulative and keyed by
    the CARD rank): 100 at rank 1, 120 at 5, 230 at 10, and 730 once the
    hero is Enlightened. Rank costs double every step, so the late ranks
    have to be worth more than the early ones.

    Reads the trained rank straight off the entry rather than going through
    progression.attributes, so game.core stays free of an upward import."""
    if not entry:
        return config.DAILY_ENERGY
    trained = min(config.TRAINED_MAX,
                  entry.get("trained_ranks", {}).get("stamina", 0))
    rank = config.RANK_START + trained
    top = config.DAILY_ENERGY + config.ENERGY_BY_STAMINA_RANK.get(rank, 0)
    if entry.get("enlightened"):
        top += config.ENLIGHTENMENT_ENERGY_BONUS
    return top


def hero_max(state, hero_id):
    return max_for(state.get("roster", {}).get(hero_id))


def hero_energy(state, hero_id):
    entry = state["roster"].get(hero_id)
    if entry is None:
        return 0
    return entry.setdefault("energy", max_for(entry))


def set_hero_energy(state, hero_id, value):
    entry = state["roster"].get(hero_id)
    if entry is not None:
        entry["energy"] = max(0, min(max_for(entry), value))


def team_max(state):
    """The ceiling the HUD bar measures against — the lowest in the party,
    matching team_energy being the lowest current."""
    members = party(state)
    if not members:
        return config.DAILY_ENERGY
    return min(hero_max(state, h) for h in members)


def team_is_full(state):
    """Every active member at their OWN maximum."""
    members = party(state)
    return bool(members) and all(
        hero_energy(state, h) >= hero_max(state, h) for h in members)


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
