"""Combat math (spec §6.4). Pure functions — no pygame, no randomness.

Random rolls are passed in as arguments so every function is deterministic
and unit-testable; the engine owns the RNG.
"""

from game import config


def effective_rank(rank, boost=0):
    """M15: what combat actually uses. `rank` is the trained level (1..10),
    `boost` the character's innate talent for that attribute (0..7).

    Each boost level is worth BOOST_RANK_VALUE flat rank — so talent shows
    at rank 1 — plus BOOST_PCT percent, which widens the gap as the rank
    climbs. Enemies pass boost 0 and get their raw rank back.
    """
    return (rank + boost * config.BOOST_RANK_VALUE) * (1 + boost * config.BOOST_PCT)


def max_hp(stamina, durability):
    return int(config.HP_BASE + stamina * config.HP_PER_STAMINA
               + durability * config.HP_PER_DURABILITY)


def battle_energy(intelligence):
    return int(config.BATTLE_ENERGY_BASE
               + intelligence * config.BATTLE_ENERGY_PER_INT)


def initiative(speed, roll):
    """roll is rand(1,6), recomputed each round by the engine."""
    return speed * config.INITIATIVE_SPEED_MULT + roll


def energy_penalty_tiers(energy_frac):
    """M9: tired heroes act slower. 0 tiers at >= 60% daily energy, then one
    tier per additional 10% below (capped)."""
    if energy_frac >= config.EN_PENALTY_THRESHOLD:
        return 0
    below = config.EN_PENALTY_THRESHOLD - energy_frac
    tiers = 1 + int(below / config.EN_PENALTY_STEP - 1e-9)
    return min(config.EN_PENALTY_MAX_TIERS, tiers)


def ability_damage(power, scaling_rank, target_durability, ability_type):
    """Base damage before dodge/crit/defend. Ultimates scale like specials."""
    mult = config.BASIC_SCALING_MULT if ability_type == "basic" else config.SPECIAL_SCALING_MULT
    dmg = power + scaling_rank * mult - target_durability * config.DURABILITY_REDUCTION_MULT
    return max(config.MIN_DAMAGE, int(dmg))


def crit_chance(agility):
    """Percent chance to crit."""
    return agility * config.CRIT_PCT_PER_AGILITY


def dodge_chance(agility):
    """Percent chance to dodge. Rolled after the hit, before crit."""
    return agility * config.DODGE_PCT_PER_AGILITY


def apply_crit(damage):
    return int(damage * config.CRIT_MULTIPLIER)


def apply_defend(damage):
    """Defend halves incoming damage until the defender's next turn."""
    return max(config.MIN_DAMAGE, int(damage * config.DEFEND_DAMAGE_MULT))


def resolve_damage(base_damage, dodge_roll, defender_agility, crit_roll,
                   attacker_agility, defending, crit_bonus=0, dodge_bonus=0):
    """Full §6.4 resolution pipeline. Rolls are percents in [0, 100).

    Order: dodge roll (after hit, before crit) -> crit -> defend.
    crit_bonus/dodge_bonus are flat percent additions from perks/synergies.
    Returns (damage, dodged, crit).
    """
    if dodge_roll < dodge_chance(defender_agility) + dodge_bonus:
        return 0, True, False
    damage = base_damage
    crit = crit_roll < crit_chance(attacker_agility) + crit_bonus
    if crit:
        damage = apply_crit(damage)
    if defending:
        damage = apply_defend(damage)
    return damage, False, crit


def add_ult_charge(current, amount):
    return min(config.ULT_CHARGE_MAX, current + amount)
