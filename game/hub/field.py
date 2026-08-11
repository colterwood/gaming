"""Field operations (spec M9): zone ambush rolls and squad composition.
Pure Python — no pygame; the caller owns the RNG."""

from game import config

# Ambush squad composition pool by zone danger level
_POOLS = {
    1: ["hydra_grunt"],
    2: ["hydra_grunt", "hydra_grunt", "hydra_enforcer", "hydra_medic"],
    3: ["hydra_grunt", "hydra_enforcer", "hydra_enforcer", "hydra_medic"],
}


def ambush_chance(danger, party_size):
    """Per walk-tick probability. Scales with danger, and up as the party
    shrinks below PARTY_SIZE_MAX."""
    missing = max(0, config.PARTY_SIZE_MAX - party_size)
    return danger * (config.AMBUSH_BASE_CHANCE
                     + config.AMBUSH_PARTY_BONUS * missing)


def roll_ambush(danger, party_size, rng):
    """Returns a list of enemy ids, or None. An ambush only happens if the
    rolled squad outnumbers the party (squad size 2..AMBUSH_MAX_SIZE)."""
    if party_size <= 0:
        return None
    if rng.random() >= ambush_chance(danger, party_size):
        return None
    size = rng.randint(2, config.AMBUSH_MAX_SIZE)
    if size <= party_size:
        return None
    pool = _POOLS.get(danger, _POOLS[1])
    return [pool[rng.randrange(len(pool))] for _ in range(size)]