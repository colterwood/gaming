"""Carried HP (M36). Pure Python — no pygame.

Before this, every battle built its Combatants at full HP, so a fight cost
nothing that survived it: a team could walk out of an ambush on 3 HP and
walk into the next one whole. Attrition was entirely an energy story, and
the energy story is about the clock, not about danger.

HP is stored per hero as a FRACTION of maximum, not an absolute:

  * max HP is derived (stamina/durability ranks, perks, gear) and changes
    under the player as heroes train and equip. An absolute pool would
    silently cap a hero who just ranked up Stamina, or hand them free HP.
  * a fraction survives any of that: 40% of a bigger body is more HP, which
    is what "you got tougher" ought to mean.

Everything that mends is expressed as a fraction too, in config:
sleeping is a full heal, collapsing leaves PASS_OUT_HP_FRACTION, a wipe
FLOORS the team at DEFEAT_HP_FRACTION (never a raise — losing on fumes must
not beat winning on fumes, the M12 rule for energy applied to HP).
"""

from game import config

FULL = 1.0


def hero_hp_fraction(state, hero_id):
    entry = state.get("roster", {}).get(hero_id)
    if entry is None:
        return 0.0
    return entry.setdefault("hp_fraction", FULL)


# Fractions are rounded to this many places on the way in. Healing adds a
# tenth at a time, and 0.3 + 0.1 x 7 is 0.9999999999999999 in binary — which
# reads as "still hurt", so the Med Bay chair silently wanted one more tick
# than it had quoted, and saves filled up with 0.30000000000000004.
_PLACES = 4


def set_hero_hp_fraction(state, hero_id, value):
    entry = state.get("roster", {}).get(hero_id)
    if entry is not None:
        entry["hp_fraction"] = round(max(0.0, min(FULL, float(value))), _PLACES)


def party_fractions(state):
    """{hero_id: fraction} for the active party — what a battle needs to
    start everyone where they left off."""
    from game.core import energy
    return {h: hero_hp_fraction(state, h) for h in energy.party(state)}


def heal_party(state, amount):
    """Add `amount` (a fraction of max) to every ACTIVE party member, like
    a ration. Returns the number of heroes who actually gained."""
    from game.core import energy
    healed = 0
    for hero_id in energy.party(state):
        before = hero_hp_fraction(state, hero_id)
        if before >= FULL:
            continue
        set_hero_hp_fraction(state, hero_id, before + amount)
        healed += 1
    return healed


def party_needs_treatment(state):
    from game.core import energy
    return any(hero_hp_fraction(state, h) < FULL for h in energy.party(state))


def restore_all(state, fraction):
    """Set EVERY roster member to this fraction — the morning after."""
    for hero_id in list(state.get("roster", {})):
        set_hero_hp_fraction(state, hero_id, fraction)


def floor_party(state, fraction):
    """Lift the active party TO `fraction` only if they are below it. A
    floor, never a raise: a team that wins a fight on 5% must not be better
    off for losing the next one."""
    from game.core import energy
    for hero_id in energy.party(state):
        if hero_hp_fraction(state, hero_id) < fraction:
            set_hero_hp_fraction(state, hero_id, fraction)


def team_hp_fraction(state):
    """The worst-off active member, mirroring how team energy works."""
    from game.core import energy
    members = energy.party(state)
    if not members:
        return 0.0
    return min(hero_hp_fraction(state, h) for h in members)
