"""Turn loop and action resolution (spec §6.4). Pure Python — no pygame.

The engine is stepwise so a UI can drive it: check `current()`, submit an
action dict via `take_turn`, read back a list of event dicts to display.

Action dicts:
    {"type": "ability", "ability_id": str, "target_id": str}
    {"type": "defend"}
    {"type": "item", "item_id": str, "target_id": str}

Ultimate charge rules (§6.4): +20 per turn taken, +10 per hit received,
fires at 100 then resets to 0 (no per-turn gain on the firing turn).
A stunned combatant skips the turn and gains no per-turn charge.
"""

import random

from game import config
from game.combat import enemy_ai, formulas


class BattleEngine:
    def __init__(self, heroes, enemies, rng=None, inventory=None, items_data=None):
        self.heroes = list(heroes)
        self.enemies = list(enemies)
        self.rng = rng or random.Random()
        self.inventory = inventory if inventory is not None else {}
        self.items_data = items_data or {}
        self.outcome = None                 # None | "win" | "lose"
        self.round_number = 0
        self.round_order = []
        self._turn_index = 0
        self.turn_counter = 0               # increments on every consumed turn
        self._start_round()

    # --- round / turn bookkeeping ---

    def living(self, side):
        return [c for c in side if c.alive]

    def _start_round(self):
        self.round_number += 1
        combatants = self.living(self.heroes) + self.living(self.enemies)
        rolls = {}
        for c in combatants:
            base = formulas.initiative(c.rank("speed"),
                                       self.rng.randint(*config.INITIATIVE_ROLL))
            tiers = formulas.energy_penalty_tiers(getattr(c, "energy_frac", 1.0))
            rolls[c.id] = base - tiers * config.EN_PENALTY_INITIATIVE
        self.round_order = sorted(combatants, key=lambda c: rolls[c.id], reverse=True)
        self._turn_index = 0

    def current(self):
        """The combatant whose turn it is, or None if the battle is over."""
        if self.outcome:
            return None
        while self._turn_index < len(self.round_order):
            c = self.round_order[self._turn_index]
            if c.alive:
                return c
            self._turn_index += 1
        self._start_round()
        return self.current()

    def _advance(self):
        self._turn_index += 1
        self.turn_counter += 1
        self._check_outcome()

    def _check_outcome(self):
        if not self.living(self.enemies):
            self.outcome = "win"
        elif not self.living(self.heroes):
            self.outcome = "lose"

    def rewards(self):
        """M16: XP per enemy defeated comes from the enemy's level tier."""
        if self.outcome != "win":
            return {"xp": 0, "credits": 0}
        return {"xp": sum(config.ENEMY_XP_BY_LEVEL[e.data["level"]]
                          for e in self.enemies),
                "credits": sum(e.data["credit_reward"] for e in self.enemies)}

    # --- turn resolution ---

    def begin_turn(self):
        """Apply turn-start effects for the current combatant. Returns events.
        If the combatant is stunned (or dies to burn), their turn is consumed."""
        actor = self.current()
        if actor is None:
            return []
        events = []
        actor.defending = False              # defend lasts until own next turn

        if "burn" in actor.statuses:
            actor.hp = max(0, actor.hp - config.BURN_DAMAGE_PER_TURN)
            actor.statuses["burn"] -= 1
            if actor.statuses["burn"] <= 0:
                del actor.statuses["burn"]
            events.append({"kind": "burn", "target": actor.id,
                           "amount": config.BURN_DAMAGE_PER_TURN})
            if not actor.alive:
                events.append({"kind": "defeat", "target": actor.id})
                self._advance()
                return events

        if "stun" in actor.statuses:
            actor.statuses["stun"] -= 1
            if actor.statuses["stun"] <= 0:
                del actor.statuses["stun"]
            events.append({"kind": "stunned", "target": actor.id})
            self._advance()
            return events

        return events

    def take_turn(self, action):
        """Resolve the current combatant's action. Returns events."""
        actor = self.current()
        if actor is None:
            return []
        events = []
        fired_ultimate = False

        actor.defended_last_turn = action["type"] == "defend"   # M23

        if action["type"] == "defend":
            actor.defending = True
            events.append({"kind": "defend", "actor": actor.id})

        elif action["type"] == "item":
            events += self._use_item(actor, action["item_id"], action["target_id"])

        elif action["type"] == "ability":
            ability = next(a for a in actor.data["abilities"]
                           if a["id"] == action["ability_id"])
            if ability["type"] == "ultimate":
                fired_ultimate = True
                actor.ult_charge = 0
            if ability["type"] == "special":
                actor.energy -= ability["cost"]
            events += self._resolve_ability(actor, ability, action.get("target_id"))

        if not fired_ultimate:
            actor.ult_charge = formulas.add_ult_charge(
                actor.ult_charge,
                config.ULT_CHARGE_PER_TURN + actor.perk_effects.get("ult_turn_charge_bonus", 0))

        self._advance()
        return events

    def enemy_action(self):
        """Ask the AI (§6.5) for the current enemy's action dict."""
        actor = self.current()
        allies, opponents = ((self.enemies, self.heroes) if actor in self.enemies
                             else (self.heroes, self.enemies))
        return enemy_ai.choose_action(actor, self.living(allies), self.living(opponents))

    # --- helpers ---

    def _side_of(self, combatant):
        return self.heroes if combatant in self.heroes else self.enemies

    def _opponents_of(self, combatant):
        return self.enemies if combatant in self.heroes else self.heroes

    def _find(self, combatant_id):
        for c in self.heroes + self.enemies:
            if c.id == combatant_id and c.alive:
                return c
        return None

    def _enrage_multiplier(self, actor):
        enrage = actor.data.get("enrage")
        if enrage and actor.hp_fraction() < enrage["hp_threshold"]:
            return enrage["damage_multiplier"]
        return 1.0

    def _spread_targets(self, actor, ability, primary):
        """M15 signature attacks: a single-target ability may splash onto
        extra opponents. `spread` in the ability JSON:
            "adjacent"  - the primary plus its immediate neighbours in the
                          enemy line (Iron Man's Unibeam)
            "random"    - the primary plus `extra_targets` others at random
                          (Ant-Man's Pym Particle Barrage)
            "random_range" - the primary plus extra_min..extra_max others,
                          the count decided by a coin flip (Cap's Shield
                          Throw ricochet)
        Every target is distinct; a spread never repeats or exceeds the
        living opponents available.
        """
        spread = ability.get("spread")
        if not spread:
            return [primary]
        if spread == "adjacent":
            # The line AS DRAWN, not the living one. Filtering the dead out
            # first closed the ranks, so a Unibeam at slot 1 with slot 2
            # already down splashed slot 3 — two panels away on screen, and
            # the more enemies the player had killed the further the beam
            # reached. A body in the way blocks the sweep now.
            line = self._opponents_of(actor)
            index = line.index(primary) if primary in line else 0
            return [primary] + [line[i] for i in (index - 1, index + 1)
                                if 0 <= i < len(line) and line[i].alive
                                and line[i] is not primary]
        line = self.living(self._opponents_of(actor))
        others = [c for c in line if c is not primary]
        if spread == "random_range":
            low = ability.get("extra_min", 1)
            high = ability.get("extra_max", low)
            wanted = low
            for _ in range(high - low):         # a coin flip per extra step
                if self.rng.randint(1, 2) == 1:
                    wanted += 1
        else:                                   # "random"
            wanted = ability.get("extra_targets", 1)
        wanted = min(wanted, len(others))
        picked = []
        pool = list(others)
        for _ in range(wanted):
            picked.append(pool.pop(self.rng.randint(0, len(pool) - 1)))
        return [primary] + picked

    def _resolve_ability(self, actor, ability, target_id):
        events = []
        if ability.get("effect") == "heal":
            target = self._find(target_id)
            if target:
                # int(): ranks are floats since M15 and HP must stay integral
                amount = int(ability["power"]
                             + actor.rank(ability["scales_with"])
                             * config.SPECIAL_SCALING_MULT)
                target.heal(amount)
                events.append({"kind": "heal", "actor": actor.id,
                               "target": target.id, "amount": amount})
            return events

        if ability["target"] == "all":
            targets = list(self.living(self._opponents_of(actor)))
        else:
            target = self._find(target_id)
            targets = self._spread_targets(actor, ability, target) if target else []

        damage_pct_key = ("basic_damage_pct" if ability["type"] == "basic"
                          else "special_damage_pct")
        for target in targets:
            base = formulas.ability_damage(
                ability["power"], actor.rank(ability["scales_with"]),
                target.rank("durability"), ability["type"])
            base = int(base * self._enrage_multiplier(actor))
            base = int(base * (1 + actor.perk_effects.get(damage_pct_key, 0) / 100))
            damage, dodged, crit = formulas.resolve_damage(
                base_damage=base,
                dodge_roll=self.rng.uniform(0, 100),
                defender_agility=target.rank("agility"),
                crit_roll=self.rng.uniform(0, 100),
                attacker_agility=actor.rank("agility"),
                defending=target.defending,
                crit_bonus=actor.crit_bonus,
                dodge_bonus=target.perk_effects.get("dodge_bonus", 0))
            if dodged:
                events.append({"kind": "dodge", "actor": actor.id, "target": target.id})
                continue
            target.take_damage(damage)
            events.append({"kind": "damage", "actor": actor.id, "target": target.id,
                           "amount": damage, "crit": crit})
            status = ability.get("applies_status")
            if status and target.alive:
                turns = config.BURN_TURNS if status == "burn" else config.STUN_TURNS
                target.statuses[status] = turns
                events.append({"kind": "status", "target": target.id, "status": status})
            if not target.alive:
                events.append({"kind": "defeat", "target": target.id})
        return events

    def _use_item(self, actor, item_id, target_id):
        events = []
        if self.inventory.get(item_id, 0) <= 0:
            return [{"kind": "no_item", "actor": actor.id, "item": item_id}]
        item = self.items_data.get(item_id, {})
        target = self._find(target_id)
        if target is None:
            return [{"kind": "no_target", "actor": actor.id}]
        self.inventory[item_id] -= 1
        if "heal" in item:
            target.heal(item["heal"])
            events.append({"kind": "heal", "actor": actor.id, "target": target.id,
                           "amount": item["heal"], "item": item_id})
        if "battle_energy" in item:
            target.energy = min(target.max_energy, target.energy + item["battle_energy"])
            events.append({"kind": "energy", "actor": actor.id, "target": target.id,
                           "amount": item["battle_energy"], "item": item_id})
        return events
