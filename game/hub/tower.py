"""Avengers Tower hub scene: three rooms, clock/energy HUD, activities,
talk/gift/shop interactions, bond-scene dialogue overlay. Rendering + input
only — rules live in game.hub.activities, game.social, game.core."""

import pygame

from game import config
from game.core import calendar as cal
from game.core import clock
from game.core.state_machine import GameState
from game.hub import activities
from game.social import bonds, events
from game.ui import widgets

ROOMS = ("Common Floor", "Training Floor", "Ops Floor")


class HubScene:
    def __init__(self, content):
        self.content = content
        self.room_index = 0
        self.activity_index = 0
        self.messages = []
        self.tick_accum = 0.0
        self.mode = "normal"        # normal | pick_gift | shop | scene | train_attr | perk_choice
        self.submenu_index = 0
        self.gift_hero_id = None
        self.scene = None
        self.scene_line = 0
        self.train_hero_id = None
        self.perk_ctx = None        # {"hero_id", "attribute", "tier", "options"}

    # --- activity lists per room ---

    def room_activities(self, state):
        room = ROOMS[self.room_index]
        if room == "Common Floor":
            acts = []
            for hero_id in sorted(state.get("roster", {})):
                hero = self.content["characters"][hero_id]
                bond = bonds.ensure_bond(state, hero_id)
                acts.append({"label": f"Talk to {hero['name']} (20m)",
                             "kind": "talk", "hero_id": hero_id,
                             "disabled": bond["talked_today"]})
            for hero_id in sorted(state.get("roster", {})):
                hero = self.content["characters"][hero_id]
                bond = bonds.ensure_bond(state, hero_id)
                capped = bond["gifts_this_week"] >= config.GIFTS_PER_WEEK_MAX
                acts.append({"label": f"Give Gift to {hero['name']} (20m)"
                             + ("  [week limit]" if capped else ""),
                             "kind": "gift", "hero_id": hero_id, "disabled": capped})
            acts.append({"label": "Tower Shop", "kind": "shop"})
            for task in activities.assignment_tasks_today(state, self.content["assignments"]):
                done = task["id"] in state.get("assignments_done", [])
                acts.append({"label": f"{task['name']} ({task['energy']} EN)"
                             + ("  [done]" if done else ""),
                             "kind": "assignment", "task": task, "disabled": done})
            acts.append({"label": f"Workshop Tinkering ({config.CRAFT_ENERGY} EN, 1h)",
                         "kind": "craft"})
            return acts
        if room == "Training Floor":
            from game.progression import attributes as attrs
            tier = attrs.session_xp(state, self.content["calendar"])
            acts = []
            for hero_id in sorted(state.get("roster", {})):
                hero = self.content["characters"][hero_id]
                acts.append({"label": f"Train {hero['name']} "
                             f"({config.TRAINING_ENERGY} EN, 90m, +{tier} XP)",
                             "kind": "train", "hero_id": hero_id})
            return acts
        from game.hub import story
        quest = story.current_quest(state, self.content["story"])
        acts = []
        if quest is None:
            acts.append({"label": "Chapters 1-2 complete! (more issues coming)",
                         "kind": "noop", "disabled": True})
        elif quest["kind"] == "battle":
            tag = "BOSS — " if quest.get("boss") else "Mission — "
            acts.append({"label": f"{tag}{quest['name']} ({config.MISSION_ENERGY} EN, 3h)",
                         "kind": "story_battle", "quest": quest})
        else:
            acts.append({"label": f"Task — {quest['name']} ({quest['energy']} EN)",
                         "kind": "story_task", "quest": quest})
        if quest:
            desc = quest["desc"]
            acts.append({"label": desc[:70] + ("..." if len(desc) > 70 else ""),
                         "kind": "noop", "disabled": True})
        done = sum(1 for v in state.get("quests", {}).values() if v["status"] == "done")
        acts.append({"label": f"Quest log: {done}/{len(self.content['story'])} complete",
                     "kind": "noop", "disabled": True})
        return acts

    def _gift_items(self, state):
        return [(iid, n) for iid, n in sorted(state["inventory"].items())
                if n > 0 and self.content["items"].get(iid, {}).get("kind") == "gift"]

    def _shop_items(self, state):
        discount = activities.shop_discount(state, self.content["calendar"])
        stock = [i for i in self.content["items"].values()
                 if i["kind"] in ("gift", "consumable")
                 and any(s in ("tower_shop", "tower_cafe") for s in i["sources"])]
        return sorted(stock, key=lambda i: i["id"]), discount

    def log(self, message):
        self.messages.append(message)
        self.messages = self.messages[-3:]

    # --- update / input ---

    def update(self, dt, app):
        if self.mode == "scene":
            return                                   # time stops for story
        state = app.game_state
        if self.mode == "normal":
            pending = events.pending_bond_events(state, self.content["bond_scenes"])
            if pending:
                self.scene = pending[0]
                self.scene_line = 0
                self.mode = "scene"
                return
        self.tick_accum += dt
        if self.tick_accum >= config.TICK_REAL_SECONDS:
            self.tick_accum -= config.TICK_REAL_SECONDS
            clock.advance(state, config.TICK_GAME_MINUTES)
        if activities.should_pass_out(state):
            self.log("You pass out...")
            app.go_to_sleep(passed_out=True)

    def handle_key(self, app, key):
        if self.mode == "scene":
            if key == pygame.K_RETURN:
                self.scene_line += 1
                if self.scene_line >= len(self.scene["lines"]):
                    events.mark_seen(app.game_state, self.scene["id"])
                    self.scene = None
                    self.mode = "normal"
            return
        if self.mode == "pick_gift":
            self._pick_gift_key(app, key)
            return
        if self.mode == "shop":
            self._shop_key(app, key)
            return
        if self.mode == "train_attr":
            self._train_attr_key(app, key)
            return
        if self.mode == "perk_choice":
            self._perk_choice_key(app, key)
            return
        self._normal_key(app, key)

    def _normal_key(self, app, key):
        state = app.game_state
        acts = self.room_activities(state)
        if key == pygame.K_LEFT:
            self.room_index = (self.room_index - 1) % len(ROOMS)
            self.activity_index = 0
        elif key == pygame.K_RIGHT:
            self.room_index = (self.room_index + 1) % len(ROOMS)
            self.activity_index = 0
        elif key == pygame.K_UP:
            self.activity_index = (self.activity_index - 1) % max(1, len(acts))
        elif key == pygame.K_DOWN:
            self.activity_index = (self.activity_index + 1) % max(1, len(acts))
        elif key == pygame.K_RETURN and acts:
            self._perform(app, acts[self.activity_index % len(acts)])
        elif key == pygame.K_s:
            app.go_to_sleep(passed_out=False)
        elif key in (pygame.K_p, pygame.K_ESCAPE):
            app.machine.transition(GameState.PAUSE)

    def _perform(self, app, act):
        state = app.game_state
        if act.get("disabled"):
            self.log("Not available right now.")
            return
        kind = act["kind"]
        if kind == "talk":
            hero = self.content["characters"][act["hero_id"]]
            result = bonds.talk(state, act["hero_id"])
            if result["ok"]:
                clock.advance(state, config.TALK_GIFT_MINUTES)
                self.log(f"You catch up with {hero['name']}: {result['message']}"
                         + (f" — Bond {result['level']}!" if result["level_up"] else ""))
            else:
                self.log(result["message"])
        elif kind == "gift":
            if not self._gift_items(state):
                self.log("No gifts in your bag — visit the Tower Shop.")
                return
            self.gift_hero_id = act["hero_id"]
            self.submenu_index = 0
            self.mode = "pick_gift"
        elif kind == "shop":
            self.submenu_index = 0
            self.mode = "shop"
        elif kind == "assignment":
            self.log(activities.do_assignment(state, act["task"])["message"])
        elif kind == "craft":
            self.log(activities.craft(state)["message"])
        elif kind == "train":
            self.train_hero_id = act["hero_id"]
            if self._open_pending_perk(state, act["hero_id"]):
                return
            self.submenu_index = 0
            self.mode = "train_attr"
        elif kind == "story_battle":
            result = activities.launch_mission(state)
            self.log(result["message"])
            if result.get("launch_battle"):
                app.start_battle(enemy_ids=act["quest"]["enemies"], quest=act["quest"])
                return
        elif kind == "story_task":
            from game.hub import story
            self.log(story.do_hub_task(state, act["quest"])["message"])
        elif kind == "noop":
            return
        if activities.should_pass_out(state):
            self.log("You pass out...")
            app.go_to_sleep(passed_out=True)

    def _pick_gift_key(self, app, key):
        state = app.game_state
        items = self._gift_items(state)
        if not items or key == pygame.K_ESCAPE:
            self.mode = "normal"
            return
        if key in (pygame.K_UP,):
            self.submenu_index = (self.submenu_index - 1) % len(items)
        elif key in (pygame.K_DOWN,):
            self.submenu_index = (self.submenu_index + 1) % len(items)
        elif key == pygame.K_RETURN:
            item_id, _ = items[self.submenu_index % len(items)]
            hero = self.content["characters"][self.gift_hero_id]
            result = bonds.give_gift(state, hero, item_id)
            if result["ok"]:
                clock.advance(state, config.TALK_GIFT_MINUTES)
                item_name = self.content["items"][item_id]["name"]
                self.log(f"{hero['name']} receives {item_name}: {result['message']}"
                         + (f" — Bond {result['level']}!" if result["level_up"] else ""))
            else:
                self.log(result["message"])
            self.mode = "normal"

    def _open_pending_perk(self, state, hero_id):
        """If the hero has an unchosen §6.3 perk tier, open the modal for it."""
        from game.progression import attributes as attrs
        entry = state["roster"][hero_id]
        for attribute in config.ATTRIBUTES:
            tier = attrs.pending_perk_tier(entry, attribute)
            if tier:
                self.perk_ctx = {
                    "hero_id": hero_id, "attribute": attribute, "tier": tier,
                    "options": attrs.perk_options(attribute, tier, self.content["perks"])}
                self.submenu_index = 0
                self.mode = "perk_choice"
                return True
        return False

    def _train_attr_labels(self, state):
        from game.progression import attributes as attrs
        hero = self.content["characters"][self.train_hero_id]
        entry = state["roster"][self.train_hero_id]
        labels = []
        for attribute in config.ATTRIBUTES:
            eff = attrs.effective_rank(hero["power_grid"], entry, attribute)
            trained = entry.get("trained_ranks", {}).get(attribute, 0)
            if not attrs.can_train(hero["power_grid"], entry, attribute):
                labels.append(f"{attribute.title()}  {eff}/{config.RANK_MAX}  [MAX]")
            else:
                banked = entry.get("attribute_xp", {}).get(attribute, 0)
                cost = attrs.xp_for_rank(trained + 1)
                labels.append(f"{attribute.title()}  {eff}/{config.RANK_MAX}"
                              f"  (+{trained} trained)  {banked}/{cost} XP")
        return labels

    def _train_attr_key(self, app, key):
        state = app.game_state
        if key == pygame.K_ESCAPE:
            self.mode = "normal"
            return
        if key == pygame.K_UP:
            self.submenu_index = (self.submenu_index - 1) % len(config.ATTRIBUTES)
        elif key == pygame.K_DOWN:
            self.submenu_index = (self.submenu_index + 1) % len(config.ATTRIBUTES)
        elif key == pygame.K_RETURN:
            attribute = config.ATTRIBUTES[self.submenu_index % len(config.ATTRIBUTES)]
            result = activities.training_session(state, self.content,
                                                 self.train_hero_id, attribute)
            self.log(result["message"])
            if result.get("perk_pending"):
                self._open_pending_perk(state, self.train_hero_id)
            elif activities.should_pass_out(state):
                self.log("You pass out...")
                self.mode = "normal"
                app.go_to_sleep(passed_out=True)

    def _perk_choice_key(self, app, key):
        from game.progression import attributes as attrs
        ctx = self.perk_ctx
        options = ctx["options"]
        if key == pygame.K_UP:
            self.submenu_index = (self.submenu_index - 1) % len(options)
        elif key == pygame.K_DOWN:
            self.submenu_index = (self.submenu_index + 1) % len(options)
        elif key == pygame.K_RETURN:
            perk = options[self.submenu_index % len(options)]
            entry = app.game_state["roster"][ctx["hero_id"]]
            result = attrs.choose_perk(entry, ctx["attribute"], ctx["tier"],
                                       perk["id"], self.content["perks"])
            self.log(f"{perk['name']}: {perk['blurb']}" if result["ok"]
                     else result["message"])
            self.perk_ctx = None
            # another tier may be pending (e.g. jumped 3 -> 6 in one session)
            if not self._open_pending_perk(app.game_state, ctx["hero_id"]):
                self.mode = "train_attr"
        # no Esc: the §6.3 choice is part of the rank-up

    def _shop_key(self, app, key):
        state = app.game_state
        stock, discount = self._shop_items(state)
        if key == pygame.K_ESCAPE:
            self.mode = "normal"
            return
        if key in (pygame.K_UP,):
            self.submenu_index = (self.submenu_index - 1) % len(stock)
        elif key in (pygame.K_DOWN,):
            self.submenu_index = (self.submenu_index + 1) % len(stock)
        elif key == pygame.K_RETURN and stock:
            item = stock[self.submenu_index % len(stock)]
            self.log(activities.buy_item(state, item, discount)["message"])

    # --- drawing ---

    def draw(self, surface, app):
        state = app.game_state
        surface.fill(widgets.NAVY)

        widgets.text(surface, f"Issue {state['issue']}, Day {state['day']}", 32,
                     widgets.CREAM, topleft=(40, 18))
        widgets.text(surface, clock.format_time(state["time_minutes"]), 32,
                     widgets.GOLD, center=(config.WIDTH // 2, 30))
        widgets.bar(surface, pygame.Rect(config.WIDTH - 340, 18, 240, 24),
                    state["energy"] / config.DAILY_ENERGY, widgets.GREEN,
                    label=f"{state['energy']} EN")
        widgets.text(surface, f"{state['credits']} cr", 28, widgets.GOLD,
                     topleft=(config.WIDTH - 90, 20))
        for ev in cal.active_events(state, self.content["calendar"]):
            widgets.text(surface, f"EVENT: {ev['name']}", 26, widgets.RED,
                         center=(config.WIDTH // 2, 64))
        for char_id in cal.birthdays_today(state, self.content["characters"]):
            name = self.content["characters"][char_id]["name"]
            widgets.text(surface, f"Today is {name}'s birthday!", 26, widgets.GOLD,
                         center=(config.WIDTH // 2, 88))

        tab_w = 280
        for i, room in enumerate(ROOMS):
            rect = pygame.Rect(40 + i * (tab_w + 16), 100, tab_w, 52)
            selected = i == self.room_index
            pygame.draw.rect(surface, widgets.RED if selected else widgets.INK,
                             rect, border_radius=8)
            pygame.draw.rect(surface, widgets.GOLD if selected else widgets.GREY,
                             rect, width=2, border_radius=8)
            widgets.text(surface, room, 28, widgets.CREAM, center=rect.center)

        acts = self.room_activities(state)
        panel = pygame.Rect(40, 180, 760, 330)
        pygame.draw.rect(surface, widgets.INK, panel, border_radius=8)
        pygame.draw.rect(surface, widgets.CREAM, panel, width=1, border_radius=8)
        row_h = min(44, (panel.height - 16) // max(1, len(acts)))
        for i, act in enumerate(acts):
            row = pygame.Rect(panel.x + 8, panel.y + 8 + i * row_h, panel.width - 16, row_h)
            if i == self.activity_index % max(1, len(acts)) and self.mode == "normal":
                pygame.draw.rect(surface, widgets.RED, row, border_radius=6)
            color = widgets.GREY if act.get("disabled") else widgets.CREAM
            size = 28 if row_h >= 40 else 24
            widgets.text(surface, act["label"], size, color, midleft=(row.x + 16, row.centery))

        self._draw_roster(surface, state)

        for i, msg in enumerate(self.messages):
            widgets.text(surface, msg, 26, widgets.CREAM, topleft=(40, 536 + i * 32))

        widgets.text(surface,
                     "Arrows: room/activity   Enter: do   S: sleep   Esc: pause",
                     26, widgets.CREAM, center=(config.WIDTH // 2, config.HEIGHT - 30))

        if self.mode == "pick_gift":
            self._draw_submenu(surface, f"Gift for {self.content['characters'][self.gift_hero_id]['name']}",
                               [f"{self.content['items'][iid]['name']} x{n}"
                                for iid, n in self._gift_items(state)])
        elif self.mode == "shop":
            stock, discount = self._shop_items(state)
            tag = "  (EVENT SALE!)" if discount < 1.0 else ""
            self._draw_submenu(surface, f"Tower Shop — {state['credits']} cr{tag}",
                               [f"{i['name']} — {int(i['price'] * discount)} cr" for i in stock])
        elif self.mode == "train_attr":
            hero = self.content["characters"][self.train_hero_id]
            self._draw_submenu(surface, f"Train {hero['name']} — pick an attribute",
                               self._train_attr_labels(state))
        elif self.mode == "perk_choice" and self.perk_ctx:
            ctx = self.perk_ctx
            hero = self.content["characters"][ctx["hero_id"]]
            self._draw_submenu(
                surface,
                f"{hero['name']} — {ctx['attribute'].title()} rank {ctx['tier']} perk!",
                [f"{p['name']} — {p['blurb']}" for p in ctx["options"]])
        elif self.mode == "scene" and self.scene:
            self._draw_scene(surface)

    def _draw_roster(self, surface, state):
        panel = pygame.Rect(840, 180, 400, 330)
        pygame.draw.rect(surface, widgets.INK, panel, border_radius=8)
        pygame.draw.rect(surface, widgets.CREAM, panel, width=1, border_radius=8)
        widgets.text(surface, "Roster", 28, widgets.GOLD, topleft=(panel.x + 16, panel.y + 12))
        y = panel.y + 52
        for hero_id in sorted(state.get("roster", {})):
            hero = self.content["characters"][hero_id]
            bond = bonds.ensure_bond(state, hero_id)
            level = bonds.bond_level(bond["points"])
            widgets.text(surface, f"{hero['name']} — Bond {level}", 26, widgets.CREAM,
                         topleft=(panel.x + 16, y))
            into_level = bond["points"] - level * config.BOND_POINTS_PER_LEVEL
            frac = 1.0 if level >= config.BOND_LEVEL_MAX else into_level / config.BOND_POINTS_PER_LEVEL
            widgets.bar(surface, pygame.Rect(panel.x + 16, y + 28, panel.width - 32, 10),
                        frac, widgets.GOLD)
            y += 56

    def _draw_submenu(self, surface, title, labels):
        overlay = pygame.Rect(320, 160, 640, 420)
        pygame.draw.rect(surface, widgets.INK, overlay, border_radius=10)
        pygame.draw.rect(surface, widgets.GOLD, overlay, width=3, border_radius=10)
        widgets.text(surface, title, 32, widgets.GOLD, topleft=(overlay.x + 20, overlay.y + 14))
        for i, label in enumerate(labels or ["(empty)"]):
            row = pygame.Rect(overlay.x + 12, overlay.y + 60 + i * 40, overlay.width - 24, 36)
            if labels and i == self.submenu_index % len(labels):
                pygame.draw.rect(surface, widgets.RED, row, border_radius=6)
            widgets.text(surface, label, 28, widgets.CREAM, midleft=(row.x + 12, row.centery))
        widgets.text(surface, "Enter: choose   Esc: back", 24, widgets.CREAM,
                     center=(overlay.centerx, overlay.bottom - 22))

    def _draw_scene(self, surface):
        shade = pygame.Surface((config.WIDTH, config.HEIGHT), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 180))
        surface.blit(shade, (0, 0))
        box = pygame.Rect(160, config.HEIGHT - 260, config.WIDTH - 320, 200)
        pygame.draw.rect(surface, widgets.INK, box, border_radius=10)
        pygame.draw.rect(surface, widgets.GOLD, box, width=3, border_radius=10)
        widgets.text(surface, self.scene["title"], 34, widgets.GOLD,
                     topleft=(box.x + 24, box.y - 48))
        line = self.scene["lines"][min(self.scene_line, len(self.scene["lines"]) - 1)]
        self._wrap_text(surface, line, box)
        widgets.text(surface, "Enter: continue", 24, widgets.GREY,
                     topright=(box.right - 16, box.bottom - 30))

    def _wrap_text(self, surface, line, box):
        words = line.split()
        rows, current = [], ""
        f = widgets.font(30)
        for word in words:
            trial = (current + " " + word).strip()
            if f.size(trial)[0] > box.width - 48:
                rows.append(current)
                current = word
            else:
                current = trial
        rows.append(current)
        for i, row in enumerate(rows[:4]):
            widgets.text(surface, row, 30, widgets.CREAM,
                         topleft=(box.x + 24, box.y + 24 + i * 38))
