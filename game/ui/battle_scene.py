"""Battle rendering + input (M1). All rules live in game.combat; this file
only draws engine state and translates keys into action dicts."""

import pygame

from game import config
from game.combat.engine import BattleEngine
from game.combat.entities import Combatant, make_enemy_group
from game.ui import widgets

ENEMY_TURN_DELAY = 0.55     # seconds before an enemy acts (readability)
POPUP_LIFETIME = 0.9


class BattleScene:
    def __init__(self, content, hero_ids=("iron_man", "captain_america"),
                 enemy_ids=("hydra_grunt", "hydra_grunt", "hydra_grunt"),
                 inventory=None, trained=None, rng=None,
                 perk_fx=None, synergy_crit=None):
        self.content = content
        heroes = [Combatant(content["characters"][h],
                            trained_ranks=(trained or {}).get(h),
                            perk_effects=(perk_fx or {}).get(h),
                            synergy_crit=(synergy_crit or {}).get(h, 0),
                            is_hero=True) for h in hero_ids]
        enemies = make_enemy_group([content["enemies"][e] for e in enemy_ids])
        self.engine = BattleEngine(
            heroes, enemies, rng=rng,
            inventory=inventory if inventory is not None else {"med_kit": 2, "energy_bar": 1},
            items_data=content["items"])
        self.phase = "turn_start"   # turn_start | menu | target | item | enemy_wait | result
        self.menu_index = 0
        self.target_index = 0
        self.item_index = 0
        self.pending_action = None
        self.popups = []            # {text, x, y, age, color}
        self.timer = 0.0

    # --- helpers ---

    def _actor(self):
        return self.engine.current()

    def _menu_options(self):
        actor = self._actor()
        opts = ["Basic", "Special", "Item", "Defend"]
        if actor.abilities_of_type("ultimate"):
            opts.append("Ultimate")
        return opts

    def _disabled_options(self):
        actor = self._actor()
        disabled = set()
        specials = actor.abilities_of_type("special")
        if not specials or not actor.can_afford(specials[0]):
            disabled.add("Special")
        if not self._battle_items():
            disabled.add("Item")
        if not actor.ult_ready():
            disabled.add("Ultimate")
        return disabled

    def _battle_items(self):
        return [(iid, n) for iid, n in self.engine.inventory.items()
                if n > 0 and self.content["items"].get(iid, {}).get("kind") == "consumable"]

    def _targets_for_pending(self):
        if self.pending_action and self.pending_action.get("type") == "item":
            return self.engine.living(self.engine.heroes)
        return self.engine.living(self.engine.enemies)

    def _emit(self, events):
        for ev in events:
            pos = self._position_of(ev.get("target") or ev.get("actor"))
            if ev["kind"] == "damage":
                label = f"{ev['amount']}" + (" CRIT!" if ev["crit"] else "")
                color = widgets.GOLD if ev["crit"] else widgets.CREAM
            elif ev["kind"] == "heal":
                label, color = f"+{ev['amount']}", widgets.GREEN
            elif ev["kind"] == "dodge":
                label, color = "DODGE", widgets.BLUE
            elif ev["kind"] == "burn":
                label, color = f"BURN {ev['amount']}", widgets.RED
            elif ev["kind"] == "stunned":
                label, color = "STUNNED", widgets.BLUE
            elif ev["kind"] == "status":
                label, color = ev["status"].upper() + "!", widgets.RED
            elif ev["kind"] == "defend":
                label, color = "DEFEND", widgets.BLUE
            elif ev["kind"] == "defeat":
                label, color = "DOWN", widgets.RED
            elif ev["kind"] == "energy":
                label, color = f"+{ev['amount']} EN", widgets.BLUE
            else:
                continue
            self.popups.append({"text": label, "x": pos[0], "y": pos[1],
                                "age": 0.0, "color": color})

    def _position_of(self, combatant_id):
        for i, h in enumerate(self.engine.heroes):
            if h.id == combatant_id:
                return (250, 240 + i * 150)
        for i, e in enumerate(self.engine.enemies):
            if e.id == combatant_id:
                return (config.WIDTH - 300, 200 + i * 130)
        return (config.WIDTH // 2, config.HEIGHT // 2)

    # --- update / input ---

    def update(self, dt):
        for p in self.popups:
            p["age"] += dt
            p["y"] -= 40 * dt
        self.popups = [p for p in self.popups if p["age"] < POPUP_LIFETIME]

        if self.engine.outcome:
            self.phase = "result"
            return

        actor = self._actor()
        if self.phase == "turn_start":
            turn_before = self.engine.turn_counter
            events = self.engine.begin_turn()
            self._emit(events)
            if self.engine.outcome:
                self.phase = "result"
            elif self.engine.turn_counter != turn_before:   # stun/burn consumed the turn
                self.phase = "turn_start"
            elif self._actor().is_hero:
                self.phase = "menu"
                self.menu_index = 0
            else:
                self.phase = "enemy_wait"
                self.timer = 0.0
        elif self.phase == "enemy_wait":
            self.timer += dt
            if self.timer >= ENEMY_TURN_DELAY:
                self._emit(self.engine.take_turn(self.engine.enemy_action()))
                self.phase = "result" if self.engine.outcome else "turn_start"

    def handle_key(self, app, key):
        if self.phase == "menu":
            self._menu_key(key)
        elif self.phase == "target":
            self._target_key(key)
        elif self.phase == "item":
            self._item_key(key)
        elif self.phase == "result" and key == pygame.K_RETURN:
            app.finish_battle(self.engine)

    def _menu_key(self, key):
        options = self._menu_options()
        if key in (pygame.K_UP, pygame.K_w):
            self.menu_index = (self.menu_index - 1) % len(options)
        elif key in (pygame.K_DOWN, pygame.K_s):
            self.menu_index = (self.menu_index + 1) % len(options)
        elif key == pygame.K_RETURN:
            choice = options[self.menu_index]
            if choice in self._disabled_options():
                return
            actor = self._actor()
            if choice == "Defend":
                self._emit(self.engine.take_turn({"type": "defend"}))
                self.phase = "turn_start"
            elif choice == "Item":
                self.pending_action = {"type": "item"}
                self.item_index = 0
                self.phase = "item"
            else:
                ability = actor.abilities_of_type(choice.lower())[0]
                self.pending_action = {"type": "ability", "ability_id": ability["id"],
                                       "ability": ability}
                if ability["target"] == "all":
                    self._commit_action(target_id=None)
                else:
                    self.target_index = 0
                    self.phase = "target"

    def _target_key(self, key):
        targets = self._targets_for_pending()
        if key in (pygame.K_LEFT, pygame.K_UP):
            self.target_index = (self.target_index - 1) % len(targets)
        elif key in (pygame.K_RIGHT, pygame.K_DOWN):
            self.target_index = (self.target_index + 1) % len(targets)
        elif key == pygame.K_ESCAPE:
            self.phase = "item" if self.pending_action.get("type") == "item" else "menu"
        elif key == pygame.K_RETURN:
            self._commit_action(target_id=targets[self.target_index % len(targets)].id)

    def _item_key(self, key):
        items = self._battle_items()
        if key in (pygame.K_UP, pygame.K_w):
            self.item_index = (self.item_index - 1) % len(items)
        elif key in (pygame.K_DOWN, pygame.K_s):
            self.item_index = (self.item_index + 1) % len(items)
        elif key == pygame.K_ESCAPE:
            self.phase = "menu"
        elif key == pygame.K_RETURN and items:
            iid, _ = items[self.item_index % len(items)]
            self.pending_action = {"type": "item", "item_id": iid}
            self.target_index = 0
            self.phase = "target"

    def _commit_action(self, target_id):
        action = {k: v for k, v in self.pending_action.items() if k != "ability"}
        action["target_id"] = target_id
        self._emit(self.engine.take_turn(action))
        self.pending_action = None
        self.phase = "result" if self.engine.outcome else "turn_start"

    # --- drawing ---

    def draw(self, surface):
        surface.fill(widgets.NAVY)
        self._draw_turn_strip(surface)
        for i, hero in enumerate(self.engine.heroes):
            self._draw_combatant(surface, hero, pygame.Rect(80, 200 + i * 150, 340, 120))
        for i, enemy in enumerate(self.engine.enemies):
            self._draw_combatant(surface, enemy,
                                 pygame.Rect(config.WIDTH - 460, 160 + i * 130, 340, 100))

        if self.phase == "menu":
            widgets.menu(surface, pygame.Rect(80, config.HEIGHT - 220, 300, 190),
                         self._menu_options(), self.menu_index,
                         disabled=self._disabled_options())
            widgets.text(surface, f"{self._actor().name}'s turn", 30, widgets.GOLD,
                         topleft=(80, config.HEIGHT - 252))
        elif self.phase == "target":
            targets = self._targets_for_pending()
            tgt = targets[self.target_index % len(targets)]
            pos = self._position_of(tgt.id)
            pygame.draw.polygon(surface, widgets.GOLD,
                                [(pos[0], pos[1] - 46), (pos[0] - 12, pos[1] - 66),
                                 (pos[0] + 12, pos[1] - 66)])
            widgets.text(surface, "Arrows: pick target   Enter: confirm   Esc: back",
                         26, widgets.CREAM, center=(config.WIDTH // 2, config.HEIGHT - 40))
        elif self.phase == "item":
            items = self._battle_items()
            labels = [f"{self.content['items'][iid]['name']} x{n}" for iid, n in items]
            widgets.menu(surface, pygame.Rect(80, config.HEIGHT - 220, 380, 190),
                         labels or ["(no items)"], self.item_index)
        elif self.phase == "result":
            verdict = "VICTORY!" if self.engine.outcome == "win" else "DEFEATED"
            widgets.text(surface, verdict, 84, widgets.GOLD if self.engine.outcome == "win"
                         else widgets.RED, center=(config.WIDTH // 2, config.HEIGHT // 2 - 40))
            if self.engine.outcome == "win":
                r = self.engine.rewards()
                widgets.text(surface, f"+{r['xp']} XP    +{r['credits']} credits", 36,
                             widgets.CREAM, center=(config.WIDTH // 2, config.HEIGHT // 2 + 20))
            widgets.text(surface, "Enter: return to Tower", 28, widgets.CREAM,
                         center=(config.WIDTH // 2, config.HEIGHT - 60))

        for p in self.popups:
            fade = max(0, 255 - int(255 * p["age"] / POPUP_LIFETIME))
            color = pygame.Color(p["color"].r, p["color"].g, p["color"].b, fade)
            widgets.text(surface, p["text"], 34, color, center=(int(p["x"]), int(p["y"])))

    def _draw_turn_strip(self, surface):
        widgets.text(surface, f"Round {self.engine.round_number}", 26, widgets.CREAM,
                     topleft=(80, 20))
        x = 80
        current = self._actor()
        for c in self.engine.round_order:
            w = widgets.font(24).size(c.name)[0] + 20
            rect = pygame.Rect(x, 48, w, 30)
            if not c.alive:
                bg, fg = widgets.INK, widgets.GREY
            elif c is current:
                bg, fg = widgets.RED, widgets.CREAM
            else:
                bg, fg = widgets.INK, widgets.CREAM
            pygame.draw.rect(surface, bg, rect, border_radius=6)
            widgets.text(surface, c.name, 24, fg, center=rect.center)
            x += w + 8

    def _draw_combatant(self, surface, c, rect):
        pygame.draw.rect(surface, widgets.INK, rect, border_radius=8)
        border = widgets.GOLD if c is self._actor() else (
            widgets.GREY if not c.alive else widgets.CREAM)
        pygame.draw.rect(surface, border, rect, width=2, border_radius=8)
        name = c.name + ("  [DOWN]" if not c.alive else "")
        status = "  ".join(s.upper() for s in c.statuses)
        if c.defending:
            status = ("DEFENDING  " + status).strip()
        widgets.text(surface, name, 28, widgets.CREAM, topleft=(rect.x + 12, rect.y + 8))
        if status:
            widgets.text(surface, status, 22, widgets.RED, topright=(rect.right - 10, rect.y + 10))
        widgets.bar(surface, pygame.Rect(rect.x + 12, rect.y + 40, rect.width - 24, 20),
                    c.hp_fraction(), widgets.GREEN, label=f"{c.hp}/{c.max_hp}")
        if c.is_hero:
            widgets.bar(surface, pygame.Rect(rect.x + 12, rect.y + 66, rect.width - 24, 14),
                        c.energy / c.max_energy if c.max_energy else 0, widgets.BLUE)
            widgets.bar(surface, pygame.Rect(rect.x + 12, rect.y + 86, rect.width - 24, 10),
                        c.ult_charge / config.ULT_CHARGE_MAX, widgets.GOLD)
