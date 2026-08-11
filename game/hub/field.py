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


def squad_cap(party_size):
    """The most bodies that can come at a party this size (M20). Applies to
    ambushes AND booby-trap squads: 4 against a lone hero, 6 against a
    pair, the full AMBUSH_MAX_SIZE against three or four."""
    if party_size <= 0:
        return 0
    return min(config.AMBUSH_MAX_SIZE,
               config.AMBUSH_MAX_BY_PARTY.get(party_size,
                                              config.AMBUSH_MAX_SIZE))


def ambush_size(party_size, rng):
    """M15: an ambush always outnumbers the party — by 1 half the time, by
    2 a third of the time, rarely by 3 or 4 — up to the M20 squad cap."""
    roll = rng.random()
    extra = config.AMBUSH_SIZE_TABLE[-1][1]
    for cumulative, value in config.AMBUSH_SIZE_TABLE:
        if roll < cumulative:
            extra = value
            break
    return min(party_size + extra, squad_cap(party_size))


def roll_ambush(danger, party_size, rng):
    """Returns a list of enemy ids, or None if no ambush triggers."""
    if party_size <= 0:
        return None
    if rng.random() >= ambush_chance(danger, party_size):
        return None
    size = ambush_size(party_size, rng)
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


def trap_squad(danger, party_size, rng):
    """The squad sprung by a booby-trapped crate. You walked right into it,
    so there's no outnumber GUARANTEE the way an ambush has one — but M20
    holds it to the same squad_cap. It used to roll 2..AMBUSH_MAX_SIZE
    regardless of who was standing there."""
    cap = squad_cap(party_size)
    if cap <= 0:
        return []
    pool = _POOLS.get(danger, _POOLS[1])
    size = rng.randint(min(2, cap), cap)
    return [pool[rng.randrange(len(pool))] for _ in range(size)]