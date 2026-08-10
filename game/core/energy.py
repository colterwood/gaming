"""Daily energy budget (spec §6.1). Pure Python — no pygame."""


def can_afford(state, amount):
    return state["energy"] >= amount


def spend(state, amount):
    """Spend energy. Returns False (and spends nothing) if insufficient."""
    if not can_afford(state, amount):
        return False
    state["energy"] -= amount
    return True


def is_exhausted(state):
    return state["energy"] <= 0
