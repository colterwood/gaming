"""Combatants built from character/enemy JSON + trained ranks (spec §5, §6.3).
Pure Python — no pygame."""

from game import config
from game.combat import formulas


class Combatant:
    def __init__(self, data, trained_ranks=None, is_hero=False, instance_id=None,
                 name=None, perk_effects=None, synergy_crit=0):
        self.id = instance_id or data["id"]
        self.name = name or data["name"]
        self.data = data
        self.is_hero = is_hero
        self.trained_ranks = dict(trained_ranks or {})
        self.perk_effects = dict(perk_effects or {})
        hp_mult = 1 + self.perk_effects.get("max_hp_pct", 0) / 100
        self.max_hp = int(formulas.max_hp(self.rank("stamina"), self.rank("durability")) * hp_mult)
        self.hp = self.max_hp
        self.max_energy = (formulas.battle_energy(self.rank("intelligence"))
                           + self.perk_effects.get("battle_energy_flat", 0))
        self.energy = self.max_energy
        self.ult_charge = 0
        self.defending = False
        self.statuses = {}          # e.g. {"burn": 3, "stun": 1} -> turns remaining
        self.crit_bonus = self.perk_effects.get("crit_bonus", 0) + synergy_crit

    def rank(self, attribute):
        """effective_rank = base grid rank + trained ranks, capped at RANK_MAX (§6.3)."""
        base = self.data["power_grid"][attribute]
        trained = self.trained_ranks.get(attribute, 0)
        return min(config.RANK_MAX, base + trained)

    @property
    def alive(self):
        return self.hp > 0

    def abilities_of_type(self, ability_type):
        return [a for a in self.data["abilities"] if a["type"] == ability_type]

    def can_afford(self, ability):
        return ability.get("cost", 0) <= self.energy

    def ult_ready(self):
        ults = self.abilities_of_type("ultimate")
        return bool(ults) and self.ult_charge >= ults[0]["charge_required"]

    def take_damage(self, amount):
        self.hp = max(0, self.hp - amount)
        if amount > 0 and self.alive:
            self.ult_charge = formulas.add_ult_charge(
                self.ult_charge, config.ULT_CHARGE_PER_HIT)

    def heal(self, amount):
        self.hp = min(self.max_hp, self.hp + amount)

    def hp_fraction(self):
        return self.hp / self.max_hp


def make_enemy_group(enemy_datas):
    """Build Combatants with unique instance ids ("hydra_grunt_1", ...) and
    numbered display names when the same enemy appears more than once."""
    total = {}
    for d in enemy_datas:
        total[d["id"]] = total.get(d["id"], 0) + 1
    seen = {}
    group = []
    for d in enemy_datas:
        seen[d["id"]] = seen.get(d["id"], 0) + 1
        n = seen[d["id"]]
        name = f"{d['name']} {n}" if total[d["id"]] > 1 else d["name"]
        group.append(Combatant(d, instance_id=f"{d['id']}_{n}", name=name))
    return group

