"""Enemy AI (spec §6.5). Pure Python — no pygame.

- aggressive: highest-damage available action at lowest-HP target
- defensive:  guards when hurt, but never twice running, and fights flat
              out once cornered (M23) — see should_defend
- support:    heal/buff ally if one is below 50% HP, else basic attack
"""

from game import config
from game.combat import formulas


def _lowest_hp(combatants):
    return min((c for c in combatants if c.alive), key=lambda c: c.hp)


def _damage_abilities(enemy):
    usable = []
    for ab in enemy.data["abilities"]:
        if ab.get("effect") == "heal":
            continue
        if ab["type"] == "ultimate" and not enemy.ult_ready():
            continue
        if ab["type"] == "special" and not enemy.can_afford(ab):
            continue
        usable.append(ab)
    return usable


def should_defend(enemy):
    """M23: a defensive enemy used to guard EVERY turn once it dropped below
    the threshold, which turned a wounded enforcer into a damage sponge that
    never fought back — and would only get worse on a high-level enemy with
    a big HP pool. Now it guards at most every other turn, and stops
    entirely once it's cornered: below AI_DEFENSIVE_LAST_STAND_HP it swings
    with everything it has left."""
    hurt = enemy.hp_fraction()
    if hurt >= config.AI_DEFENSIVE_HP_THRESHOLD:
        return False                        # not hurt enough to bother
    if hurt < config.AI_DEFENSIVE_LAST_STAND_HP:
        return False                        # cornered: go down swinging
    return not enemy.defended_last_turn     # never two guards running


def choose_action(enemy, allies, opponents):
    ai = enemy.data["ai"]
    target = _lowest_hp(opponents)

    if ai == "defensive" and should_defend(enemy):
        return {"type": "defend"}

    if ai == "support":
        hurt = [a for a in allies if a.alive and a.hp_fraction() < config.AI_SUPPORT_HP_THRESHOLD]
        if hurt:
            heals = [ab for ab in enemy.data["abilities"]
                     if ab.get("effect") == "heal" and enemy.can_afford(ab)]
            if heals:
                patient = _lowest_hp(hurt)
                return {"type": "ability", "ability_id": heals[0]["id"], "target_id": patient.id}
        basic = enemy.abilities_of_type("basic")[0]
        return {"type": "ability", "ability_id": basic["id"], "target_id": target.id}

    if ai == "aggressive":
        best = max(_damage_abilities(enemy),
                   key=lambda ab: formulas.ability_damage(
                       ab["power"], enemy.rank(ab["scales_with"]),
                       target.rank("durability"), ab["type"]))
        return {"type": "ability", "ability_id": best["id"], "target_id": target.id}

    # A defensive enemy that isn't guarding this turn still hits back, and
    # hits with the best thing it has rather than a token jab (M23).
    best = max(_damage_abilities(enemy) or enemy.abilities_of_type("basic"),
               key=lambda ab: formulas.ability_damage(
                   ab["power"], enemy.rank(ab["scales_with"]),
                   target.rank("durability"), ab["type"]))
    return {"type": "ability", "ability_id": best["id"], "target_id": target.id}
