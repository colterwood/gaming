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


def search_loot(zone, rng):
    """Rummage one crate (M10): returns {"credits", "item", "trap"}. A trap
    forfeits the loot — the caller starts a battle with trap_squad(). Most
    crates are empty (M12 find_chance roll); loot tables live in zones.json;
    searched spots respawn daily."""
    if rng.random() < zone["danger"] * config.SEARCH_TRAP_CHANCE:
        return {"credits": 0, "item": None, "trap": True}
    loot = zone.get("loot", {})
    if rng.random() >= loot.get("find_chance", 1.0):
        return {"credits": 0, "item": None, "trap": False}      # empty crate
    lo, hi = loot.get("credits", [0, 0])
    item = None
    items = loot.get("items", [])
    if items and rng.random() < loot.get("item_chance", 0.0):
        item = items[rng.randrange(len(items))]
    return {"credits": rng.randint(lo, hi), "item": item, "trap": False}


def trap_squad(danger, rng):
    """The squad sprung by a booby-trapped crate — any size; no outnumber
    rule, you walked right into it."""
    pool = _POOLS.get(danger, _POOLS[1])
    size = rng.randint(2, config.AMBUSH_MAX_SIZE)
    return [pool[rng.randrange(len(pool))] for _ in range(size)]