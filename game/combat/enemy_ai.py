"""Enemy AI (spec §6.5). Pure Python — no pygame.

- aggressive: highest-damage available action at lowest-HP target
- defensive:  Defend below 40% HP, else basic attack
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


def choose_action(enemy, allies, opponents):
    ai = enemy.data["ai"]
    target = _lowest_hp(opponents)

    if ai == "defensive" and enemy.hp_fraction() < config.AI_DEFENSIVE_HP_THRESHOLD:
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

    # defensive above threshold falls through to a basic attack
    basic = enemy.abilities_of_type("basic")[0]
    return {"type": "ability", "ability_id": basic["id"], "target_id": target.id}
