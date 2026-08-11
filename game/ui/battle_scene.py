"""Battle rendering + input, 16-bit style (§9 M1/M7). All rules live in
game.combat; this file only draws engine state and translates keys into
action dicts."""

import pygame

from game import config
from game.combat.engine import BattleEngine
from game.combat.entities import Combatant, make_enemy_group
from game.ui import pixelkit, sprites, widgets

ENEMY_TURN_DELAY = 0.55     # seconds before an enemy acts (readability)
POPUP_LIFETIME = 0.9


class BattleScene:
    def __init__(self, content, hero_ids=("iron_man", "captain_america"),
                 enemy_ids=("hydra_grunt", "hydra_grunt", "hydra_grunt"),
                 inventory=None, trained=None, rng=None,
                 perk_fx=None, synergy_crit=None, energy_frac=None,
                 ult_charge=None):
        self.content = content
        heroes = [Combatant(content["characters"][h],
                            trained_ranks=(trained or {}).get(h),
                            perk_effects=(perk_fx or {}).get(h),
                            synergy_crit=(synergy_crit or {}).get(h, 0),
                            energy_frac=(energy_frac or {}).get(h, 1.0),
                            ult_charge=(ult_charge or {}).get(h, 0),
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

    # Special/Ultimate rows are tinted to match their resource bars (M15).
    KIND_COLORS = {"special": "sky", "ultimate": "gold"}

    def _menu_entries(self):
        """(label, kind) rows — labels are the actor's OWN ability names
        (M13). Order (M15): Basic, Special, Ultimate, Defend, Item."""
        actor = self._actor()
        entries = []
        basics = actor.abilities_of_type("basic")
        if basics:
            entries.append((basics[0]["name"], "basic"))
        specials = actor.abilities_of_type("special")
        if specials:
            entries.append((specials[0]["name"], "special"))
        ults = actor.abilities_of_type("ultimate")
        if ults:
            entries.append((ults[0]["name"], "ultimate"))
        entries.append(("Defend", "defend"))
        entries.append(("Item", "item"))
        return entries

    def _menu_options(self):
        return [label for label, _ in self._menu_entries()]

    def _menu_colors(self):
        return {label: self.KIND_COLORS[kind]
                for label, kind in self._menu_entries() if kind in self.KIND_COLORS}

    def _disabled_options(self):
        actor = self._actor()
        disabled = set()
        specials = actor.abilities_of_type("special")
        items = self._battle_items()
        ult_ok = actor.ult_ready()
        for label, kind in self._menu_entries():
            if kind == "special" and (not specials or not actor.can_afford(specials[0])):
                disabled.add(label)
            elif kind == "item" and not items:
                disabled.add(label)
            elif kind == "ultimate" and not ult_ok:
                disabled.add(label)
        return disabled

    def _battle_items(self):
        # Only consumables with a battle effect — rations (M10 "energy"
        # items) are eaten outside combat and would waste the turn here.
        return [(iid, n) for iid, n in self.engine.inventory.items()
                if n > 0 and self.content["items"].get(iid, {}).get("kind") == "consumable"
                and any(k in self.content["items"][iid] for k in ("heal", "battle_energy"))]

    def _targets_for_pending(self):
        if self.pending_action and self.pending_action.get("type") == "item":
            return self.engine.living(self.engine.heroes)
        return self.engine.living(self.engine.enemies)

    def _emit(self, events):
        for ev in events:
            pos = self._position_of(ev.get("target") or ev.get("actor"))
            if ev["kind"] == "damage":
                label = f"{ev['amount']}" + ("!" if ev["crit"] else "")
                color = widgets.GOLD if ev["crit"] else widgets.WHITE
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

    def _enemy_rect(self, i):
        """Up to 4 enemies: one column. Ambushes up to 8: two columns (M9)."""
        if len(self.engine.enemies) <= 4:
            return pygame.Rect(config.WIDTH - 218, 74 + i * 60, 188, 52)
        col, row = divmod(i, 4)
        return pygame.Rect(config.WIDTH - 348 + col * 174, 60 + row * 58, 166, 50)

    def _position_of(self, combatant_id):
        for i, h in enumerate(self.engine.heroes):
            if h.id == combatant_id:
                return (150, 118 + i * 56)
        for i, e in enumerate(self.engine.enemies):
            if e.id == combatant_id:
                rect = self._enemy_rect(i)
                return (rect.centerx, rect.y + 18)
        return (config.WIDTH // 2, config.HEIGHT // 2)

    # --- update / input (logic identical to M1) ---

    def update(self, dt):
        for p in self.popups:
            p["age"] += dt
            p["y"] -= 20 * dt
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
        entries = self._menu_entries()
        if key in (pygame.K_UP, pygame.K_w):
            self.menu_index = (self.menu_index - 1) % len(entries)
        elif key in (pygame.K_DOWN, pygame.K_s):
            self.menu_index = (self.menu_index + 1) % len(entries)
        elif key == pygame.K_RETURN:
            label, kind = entries[self.menu_index % len(entries)]
            if label in self._disabled_options():
                return
            actor = self._actor()
            if kind == "defend":
                self._emit(self.engine.take_turn({"type": "defend"}))
                self.phase = "turn_start"
            elif kind == "item":
                self.pending_action = {"type": "item"}
                self.item_index = 0
                self.phase = "item"
            else:
                ability = actor.abilities_of_type(kind)[0]
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
        if not items or key == pygame.K_ESCAPE:
            self.phase = "menu"
            return
        if key in (pygame.K_UP, pygame.K_w):
            self.item_index = (self.item_index - 1) % len(items)
        elif key in (pygame.K_DOWN, pygame.K_s):
            self.item_index = (self.item_index + 1) % len(items)
        elif key == pygame.K_RETURN:
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
        surface.blit(sprites.battle_backdrop(config.WIDTH, config.HEIGHT), (0, 0))
        self._draw_turn_strip(surface)
        for i, hero in enumerate(self.engine.heroes):
            self._draw_hero(surface, hero, pygame.Rect(30, 100 + i * 56, 180, 48))
        for i, enemy in enumerate(self.engine.enemies):
            self._draw_enemy(surface, enemy, self._enemy_rect(i))

        if self.phase == "menu":
            pixelkit.text(surface, f"{self._actor().name}'s turn", 15, "gold",
                          topleft=(30, config.HEIGHT - 122), shadow="ink")
            widgets.menu(surface, pygame.Rect(30, config.HEIGHT - 108, 210, 96),
                         self._menu_options(), self.menu_index,
                         disabled=self._disabled_options(),
                         colors=self._menu_colors())
        elif self.phase == "target":
            targets = self._targets_for_pending()
            tgt = targets[self.target_index % len(targets)]
            pos = self._position_of(tgt.id)
            self._target_arrow(surface, (pos[0], pos[1] - 30))
            pixelkit.text(surface, "Arrows: pick target  Enter: confirm  Esc: back",
                          13, "cream", center=(config.WIDTH // 2, config.HEIGHT - 12),
                          shadow="ink")
        elif self.phase == "item":
            items = self._battle_items()
            labels = [f"{self.content['items'][iid]['name']} x{n}" for iid, n in items]
            widgets.menu(surface, pygame.Rect(30, config.HEIGHT - 108, 190,
                                              max(30, 24 * len(labels or [1]))),
                         labels or ["(no items)"], self.item_index)
        elif self.phase == "result":
            box = pygame.Rect(config.WIDTH // 2 - 120, config.HEIGHT // 2 - 46, 240, 92)
            pixelkit.panel(surface, box, fill="ink", border="gold")
            won = self.engine.outcome == "win"
            pixelkit.text(surface, "VICTORY!" if won else "DEFEATED", 34,
                          "gold" if won else "red", bold=True,
                          center=(box.centerx, box.y + 28), shadow="maroon")
            if won:
                r = self.engine.rewards()
                pixelkit.text(surface, f"+{r['xp']} XP   +{r['credits']} credits", 16,
                              "white", center=(box.centerx, box.y + 52))
            pixelkit.text(surface, "Enter: return to Tower", 13, "cream",
                          center=(box.centerx, box.bottom - 16))

        for p in self.popups:
            widgets.text(surface, p["text"], 18, p["color"],
                         center=(int(p["x"]), int(p["y"])), shadow="ink", bold=True)

    def _target_arrow(self, surface, pos):
        """Gold arrowhead pointing DOWN at the targeted enemy."""
        x, y = pos
        pygame.draw.line(surface, widgets.INK, (x - 4, y - 1), (x + 4, y - 1))
        for i in range(5):
            pygame.draw.line(surface, widgets.GOLD,
                             (x - (4 - i), y + i), (x + (4 - i), y + i))

    def _draw_turn_strip(self, surface):
        pixelkit.text(surface, f"Round {self.engine.round_number}", 14, "cream",
                      topleft=(30, 8), shadow="ink")
        x = 30
        current = self._actor()
        for c in self.engine.round_order:
            chip = pygame.Rect(x, 22, 26, 26)
            surface.blit(pygame.transform.scale(
                sprites.portrait(c.data["id"]), (26, 26)), chip.topleft)
            border = "gold" if c is current else ("grey_dark" if not c.alive else "ink")
            pygame.draw.rect(surface, pixelkit.color(border), chip, 2 if c is current else 1)
            if not c.alive:
                pixelkit.checker(surface, chip.inflate(-4, -4), "shadow", "ink", cell=2)
            x += 30

    def _draw_hero(self, surface, c, rect):
        pixelkit.panel(surface, rect, fill="navy",
                       border="gold" if c is self._actor() else "ink")
        surface.blit(pygame.transform.scale(
            sprites.portrait(c.data["id"]), (36, 36)),
            (rect.x + 5, rect.y + 6))
        name_c = "grey" if not c.alive else "white"
        pixelkit.text(surface, c.name, 13, name_c,
                      topleft=(rect.x + 46, rect.y + 4), shadow="ink")
        widgets.bar(surface, pygame.Rect(rect.x + 46, rect.y + 16, rect.width - 54, 10),
                    c.hp_fraction(), "green", label=f"{c.hp}/{c.max_hp}")
        widgets.bar(surface, pygame.Rect(rect.x + 46, rect.y + 28, rect.width - 54, 6),
                    c.energy / c.max_energy if c.max_energy else 0, "sky")
        widgets.bar(surface, pygame.Rect(rect.x + 46, rect.y + 36, rect.width - 54, 5),
                    c.ult_charge / config.ULT_CHARGE_MAX, "gold")
        self._status_tags(surface, c, rect)

    def _draw_enemy(self, surface, c, rect):
        pixelkit.panel(surface, rect, fill="shadow",
                       border="gold" if c is self._actor() else "ink")
        surface.blit(pygame.transform.scale(
            sprites.portrait(c.data["id"]), (40, 40)),
            (rect.x + 5, rect.y + 6))
        name_c = "grey" if not c.alive else "white"
        pixelkit.text(surface, c.name + ("  [DOWN]" if not c.alive else ""), 13,
                      name_c, topleft=(rect.x + 50, rect.y + 6), shadow="ink")
        widgets.bar(surface, pygame.Rect(rect.x + 50, rect.y + 20, rect.width - 58, 10),
                    c.hp_fraction(), "red", label=f"{c.hp}/{c.max_hp}")
        self._status_tags(surface, c, rect)

    def _status_tags(self, surface, c, rect):
        tags = [s.upper() for s in c.statuses]
        if c.defending:
            tags.insert(0, "DEF")
        if tags:
            pixelkit.text(surface, " ".join(tags), 11, "orange",
                          topright=(rect.right - 4, rect.y + 2), shadow="ink")
