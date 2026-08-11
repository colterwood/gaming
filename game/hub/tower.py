"""Walkable Avengers Tower (spec §9 M8), 16-bit style. Rendering + input
only — activity/bond/story rules live in game.hub.activities, game.hub.story,
game.social, game.core.

Three tile-map floors; arrow keys move the player, Enter interacts with the
nearest station or character. Menus open as overlays on top of the scene.
"""

import pygame

from game import config
from game.core import calendar as cal
from game.core import clock
from game.core.state_machine import GameState
from game.hub import activities, story
from game.social import bonds, events
from game.ui import pixelkit, sprites, widgets

TILE = 16
HUD_H = 20
MAP_W = 40
MAP_H = 21

WALKABLE = {".", ",", "m"}
TILE_NAMES = {"#": "wall", "w": "window", "E": "elevator", ".": "floor",
              ",": "carpet", "m": "mat", "S": "counter", "b": "board",
              "O": "console", "Z": "bed", "c": "couch", "t": "table",
              "p": "plant", "r": "rack"}
STATION_KINDS = {"E": "elevator", "S": "shop", "b": "board", "O": "ops",
                 "Z": "bed", "r": "training"}
STATION_LABELS = {"elevator": "Elevator", "shop": "Tower Shop",
                  "board": "Assignment Board", "ops": "Ops Console",
                  "bed": "Sleep", "training": "Training Rack"}

FLOORS = {
    "common": {
        "name": "Common Floor",
        "map": [
            "########################################",
            "#ww##ww##ww##ww#EE#ww##ww##ww##ww##ww##",
            "#......................................#",
            "#......................................#",
            "#SS.................,,,,,,.............#",
            "#SS.................,c,,c,.............#",
            "#...................,tt,t,.............#",
            "#...................,,,,,,.............#",
            "#p.....................................#",
            "#......................................#",
            "#......................................#",
            "#......................................#",
            "#..................................b...#",
            "#..................................b...#",
            "#......................................#",
            "#ZZ....................................#",
            "#......................................#",
            "#p....................................p#",
            "#......................................#",
            "#......................................#",
            "########################################",
            "########################################",
        ],
        "spawn": (17, 2),
    },
    "training": {
        "name": "Training Floor",
        "map": [
            "########################################",
            "#ww##ww##ww##ww#EE#ww##ww##ww##ww##ww##",
            "#......................................#",
            "#......................................#",
            "#....mmmmmmmm..........mmmmmmmm........#",
            "#....mmmmmmmm..........mmmmmmmm........#",
            "#....mmmmmmmm..........mmmmmmmm.....rr.#",
            "#....mmmmmmmm..........mmmmmmmm.....rr.#",
            "#......................................#",
            "#......................................#",
            "#......................................#",
            "#....mmmmmmmmmmmmmmmmmmmmmmmmm.........#",
            "#....mmmmmmmmmmmmmmmmmmmmmmmmm.........#",
            "#....mmmmmmmmmmmmmmmmmmmmmmmmm.........#",
            "#......................................#",
            "#p....................................p#",
            "#......................................#",
            "#......................................#",
            "#......................................#",
            "########################################",
            "########################################",
        ],
        "spawn": (17, 2),
    },
    "ops": {
        "name": "Ops Floor",
        "map": [
            "########################################",
            "#ww##ww##ww##ww#EE#ww##ww##ww##ww##ww##",
            "#......................................#",
            "#......................................#",
            "#......OOOO............................#",
            "#......................................#",
            "#......................................#",
            "#...............tt.....................#",
            "#...............tt.....................#",
            "#......................................#",
            "#p....................................p#",
            "#......................................#",
            "#......................................#",
            "#......................................#",
            "#......................................#",
            "#......................................#",
            "#......................................#",
            "#......................................#",
            "#......................................#",
            "########################################",
            "########################################",
        ],
        "spawn": (17, 2),
    },
}

def _normalize_maps():
    """Pad/trim every floor map to exactly MAP_W x MAP_H, walls at edges."""
    for floor in FLOORS.values():
        rows = [r.ljust(MAP_W, "#")[:MAP_W] for r in floor["map"]]
        while len(rows) < MAP_H:
            rows.append("#" * MAP_W)
        rows = rows[:MAP_H]
        rows[0] = "#" * MAP_W
        rows[-1] = "#" * MAP_W
        rows = [("#" + r[1:-1] + "#") for r in rows]
        floor["map"] = rows


_normalize_maps()

# Where characters stand: floor -> [(char_id or role, tile_x, tile_y)]
FLAVOR = {
    "iron_man": [
        "TONY: JARVIS ran the numbers. We're statistically overdue for a Tuesday.",
        "TONY: If anyone asks, the scorch mark on floor twelve was already there.",
        "TONY: Coffee's on Jarvis. Everything else in this tower is on me. Literally.",
    ],
    "captain_america": [
        "STEVE: Morning. Already did my ten miles. The city looks good from up here.",
        "STEVE: HYDRA doesn't rest, but you should. Take the couch sometime.",
        "STEVE: Keep the team close. That's the mission under the mission.",
    ],
    "ant_man": [
        "SCOTT: I've been small enough to hear ants argue. They're big on committee.",
        "SCOTT: House arrest to Avengers Tower. Massive upgrade. Huge. Well - variable.",
        "SCOTT: If you see a really big crumb in the kitchen, that was me. Sorry.",
    ],
    "hulk": [
        "HULK: ...",
        "HULK: Hulk smashed HYDRA good today.",
        "HULK: Metal man talks too much. You talk okay amount.",
    ],
}


class HubScene:
    def __init__(self, content):
        self.content = content
        self.floor = "common"
        spawn = FLOORS["common"]["spawn"]
        self.px = spawn[0] * TILE + TILE // 2
        self.py = HUD_H + spawn[1] * TILE + TILE // 2
        self.facing_left = False
        self.walk_bob = 0.0
        self.messages = []
        self.tick_accum = 0.0
        # modes: normal | submenu | train_attr | perk_choice | scene
        self.mode = "normal"
        self.submenu = None         # {"title", "items": [(label, disabled, cb)], "index"}
        self.train_hero_id = None
        self.perk_ctx = None
        self.scene = None
        self.scene_line = 0
        self.submenu_index = 0      # used by train_attr / perk_choice overlays

    # ------------------------------------------------------------------ util

    def log(self, message):
        self.messages.append(message)
        self.messages = self.messages[-2:]

    def reset_modes(self):
        """Back to walking (e.g. after a forced pass-out mid-menu). A pending
        perk choice re-prompts on the next Training Rack visit."""
        self.mode = "normal"
        self.submenu = None
        self.submenu_index = 0
        self.train_hero_id = None
        self.perk_ctx = None

    def _map(self):
        return FLOORS[self.floor]["map"]

    def _solid(self, px, py):
        tx, ty = int(px // TILE), int((py - HUD_H) // TILE)
        if not (0 <= tx < MAP_W and 0 <= ty < MAP_H):
            return True
        row = self._map()[ty]
        ch = row[tx] if tx < len(row) else "#"
        return ch not in WALKABLE

    def _characters_here(self, state):
        """(char_id, px, py) for everyone standing on the current floor."""
        placed = []

        def put(cid, tx, ty):
            placed.append((cid, tx * TILE + TILE // 2, HUD_H + ty * TILE + TILE // 2))

        roster = state.get("roster", {})
        flags = state.get("story_flags", {})
        if self.floor == "common":
            put("jarvis", 4, 6)
            put("coulson", 33, 10)
            put("iron_man", 10, 3)
            put("captain_america", 24, 8)
            if "ant_man" in roster:
                put("ant_man", 14, 3)
            if "hulk" in roster:
                put("hulk", 29, 3)
        elif self.floor == "training":
            if flags.get("hulk_arrived") and "hulk" not in roster:
                put("hulk", 8, 12)
        elif self.floor == "ops":
            put("pepper_potts", 12, 5)
        return placed

    def _stations_here(self):
        found = []
        for ty, row in enumerate(self._map()):
            for tx, ch in enumerate(row):
                kind = STATION_KINDS.get(ch)
                if kind:
                    found.append((kind, tx * TILE + TILE // 2,
                                  HUD_H + ty * TILE + TILE // 2))
        return found

    def _nearest_interaction(self, state):
        """('char', id, label) or ('station', kind, label) within reach."""
        best = None
        best_d = 26 ** 2
        for cid, x, y in self._characters_here(state):
            d = (x - self.px) ** 2 + (y - self.py) ** 2
            if d < best_d:
                name = self.content["characters"][cid]["name"]
                best, best_d = ("char", cid, name), d
        for kind, x, y in self._stations_here():
            d = (x - self.px) ** 2 + (y - self.py) ** 2
            if d < best_d:
                best, best_d = ("station", kind, STATION_LABELS[kind]), d
        return best

    # ---------------------------------------------------------------- update

    def update(self, dt, app):
        if self.mode == "scene":
            return
        state = app.game_state
        if self.mode == "normal":
            pending = events.pending_bond_events(state, self.content["bond_scenes"])
            if pending:
                self.scene = pending[0]
                self.scene_line = 0
                self.mode = "scene"
                return
            self._move(dt)
        self.tick_accum += dt
        if self.tick_accum >= config.TICK_REAL_SECONDS:
            self.tick_accum -= config.TICK_REAL_SECONDS
            clock.advance(state, config.TICK_GAME_MINUTES)
        if activities.should_pass_out(state):
            self.log("You pass out...")
            app.go_to_sleep(passed_out=True)

    def _move(self, dt):
        keys = pygame.key.get_pressed()
        dx = (keys[pygame.K_RIGHT] - keys[pygame.K_LEFT]) * 90 * dt
        dy = (keys[pygame.K_DOWN] - keys[pygame.K_UP]) * 90 * dt
        if dx < 0:
            self.facing_left = True
        elif dx > 0:
            self.facing_left = False
        if dx or dy:
            self.walk_bob += dt * 10
        for axis_dx, axis_dy in ((dx, 0), (0, dy)):
            nx, ny = self.px + axis_dx, self.py + axis_dy
            feet = [(nx - 4, ny + 6), (nx + 4, ny + 6), (nx - 4, ny), (nx + 4, ny)]
            if not any(self._solid(fx, fy) for fx, fy in feet):
                self.px, self.py = nx, ny

    # ----------------------------------------------------------------- input

    def handle_key(self, app, key):
        if self.mode == "scene":
            if key == pygame.K_RETURN:
                self.scene_line += 1
                if self.scene_line >= len(self.scene["lines"]):
                    events.mark_seen(app.game_state, self.scene["id"])
                    self.scene = None
                    self.mode = "normal"
            return
        if self.mode == "submenu":
            self._submenu_key(app, key)
            return
        if self.mode == "train_attr":
            self._train_attr_key(app, key)
            return
        if self.mode == "perk_choice":
            self._perk_choice_key(app, key)
            return
        # normal
        if key == pygame.K_RETURN:
            hit = self._nearest_interaction(app.game_state)
            if hit:
                self._interact(app, hit)
        elif key in (pygame.K_p, pygame.K_ESCAPE):
            app.machine.transition(GameState.PAUSE)

    # ----------------------------------------------------- generic submenus

    def _open_submenu(self, title, items):
        self.submenu = {"title": title, "items": items, "index": 0}
        self.mode = "submenu"

    def _submenu_key(self, app, key):
        menu = self.submenu
        items = menu["items"]
        if key == pygame.K_ESCAPE:
            self.reset_modes()
            return
        if key == pygame.K_UP:
            menu["index"] = (menu["index"] - 1) % len(items)
        elif key == pygame.K_DOWN:
            menu["index"] = (menu["index"] + 1) % len(items)
        elif key == pygame.K_RETURN:
            label, disabled, callback = items[menu["index"]]
            if disabled:
                return
            if callback is None:
                self.reset_modes()
            else:
                callback(app)

    # ------------------------------------------------------------- interact

    def _interact(self, app, hit):
        kind, ident, label = hit
        if kind == "char":
            self._interact_char(app, ident)
            return
        state = app.game_state
        if ident == "bed":
            app.go_to_sleep(passed_out=False)
        elif ident == "elevator":
            items = [(FLOORS[f]["name"], f == self.floor,
                      (lambda a, fl=f: self._switch_floor(fl)))
                     for f in ("common", "training", "ops")]
            self._open_submenu("Elevator", items)
        elif ident == "shop":
            self._open_shop(app)
        elif ident == "board":
            self._open_board(app)
        elif ident == "training":
            self._open_training(app)
        elif ident == "ops":
            self._open_ops(app)

    def _switch_floor(self, floor):
        self.floor = floor
        spawn = FLOORS[floor]["spawn"]
        self.px = spawn[0] * TILE + TILE // 2
        self.py = HUD_H + spawn[1] * TILE + TILE // 2
        self.reset_modes()
        self.log(f"{FLOORS[floor]['name']}.")

    def _interact_char(self, app, char_id):
        state = app.game_state
        char = self.content["characters"][char_id]
        if not bonds.bondable(char):
            lines = FLAVOR.get(char_id, ["..."])
            self.log(lines[(state["day"] + len(char_id)) % len(lines)])
            return
        bond = bonds.ensure_bond(state, char_id)
        capped = bond["gifts_this_week"] >= config.GIFTS_PER_WEEK_MAX
        items = [
            ("Talk", bond["talked_today"], lambda a: self._talk(a, char_id)),
            ("Give Gift" + ("  [week limit]" if capped else ""), capped,
             lambda a: self._open_gift_menu(a, char_id)),
            ("Never mind", False, None),
        ]
        level = bonds.bond_level(bond["points"])
        self._open_submenu(f"{char['name']} - Bond {level}", items)

    def _talk(self, app, char_id):
        state = app.game_state
        char = self.content["characters"][char_id]
        result = bonds.talk(state, char_id)
        if result["ok"]:
            clock.advance(state, config.TALK_GIFT_MINUTES)
            message = f"{char['name']}: {result['message']}"
            if result["level_up"]:
                message += f" - Bond {result['level']}!"
            self.log(message)
            for m in bonds.check_bond_progress(state, self.content):
                self.log(m)
        else:
            self.log(result["message"])
        self.reset_modes()
        self._after_action(app)

    def _open_gift_menu(self, app, char_id):
        state = app.game_state
        gifts = [(iid, n) for iid, n in sorted(state["inventory"].items())
                 if n > 0 and self.content["items"].get(iid, {}).get("kind") == "gift"]
        if not gifts:
            self.log("No gifts in your bag - visit the Tower Shop.")
            self.reset_modes()
            return
        char = self.content["characters"][char_id]
        items = [(f"{self.content['items'][iid]['name']} x{n}", False,
                  (lambda a, i=iid: self._give_gift(a, char_id, i)))
                 for iid, n in gifts]
        items.append(("Never mind", False, None))
        self._open_submenu(f"Gift for {char['name']}", items)

    def _give_gift(self, app, char_id, item_id):
        state = app.game_state
        char = self.content["characters"][char_id]
        result = bonds.give_gift(state, char, item_id)
        if result["ok"]:
            clock.advance(state, config.TALK_GIFT_MINUTES)
            item_name = self.content["items"][item_id]["name"]
            message = f"{char['name']} receives {item_name}: {result['message']}"
            if result["level_up"]:
                message += f" - Bond {result['level']}!"
            self.log(message)
            for m in bonds.check_bond_progress(state, self.content):
                self.log(m)
        else:
            self.log(result["message"])
        self.reset_modes()
        self._after_action(app)

    def _open_shop(self, app):
        state = app.game_state
        discount = activities.shop_discount(state, self.content["calendar"])
        stock = sorted((i for i in self.content["items"].values()
                        if i["kind"] in ("gift", "consumable")
                        and any(s in ("tower_shop", "tower_cafe") for s in i["sources"])),
                       key=lambda i: i["id"])
        items = [(f"{i['name']} - {int(i['price'] * discount)} cr", False,
                  (lambda a, it=i: self._buy(a, it)))
                 for i in stock]
        items.append(("Close", False, None))
        tag = "  (SALE!)" if discount < 1.0 else ""
        self._open_submenu(f"Tower Shop - {state['credits']} cr{tag}", items)

    def _buy(self, app, item):
        state = app.game_state
        discount = activities.shop_discount(state, self.content["calendar"])
        self.log(activities.buy_item(state, item, discount)["message"])
        index = self.submenu["index"] if self.submenu else 0
        self._open_shop(app)                    # refresh credits in title
        self.submenu["index"] = min(index, len(self.submenu["items"]) - 1)

    def _open_board(self, app):
        state = app.game_state
        items = []
        for task in activities.assignment_tasks_today(state, self.content["assignments"]):
            done = task["id"] in state.get("assignments_done", [])
            label = f"{task['name']} ({task['energy']} EN, +{task['credits']} cr)"
            if done:
                label += "  [done]"
            items.append((label, done, (lambda a, t=task: self._do_assignment(a, t))))
        items.append(("Close", False, None))
        self._open_submenu("Assignment Board", items)

    def _do_assignment(self, app, task):
        self.log(activities.do_assignment(app.game_state, task)["message"])
        self.reset_modes()
        self._after_action(app)

    def _open_ops(self, app):
        state = app.game_state
        quest = story.current_quest(state, self.content["story"])
        done = sum(1 for v in state.get("quests", {}).values() if v["status"] == "done")
        items = []
        if quest is None:
            items.append(("Chapters 1-2 complete!", True, None))
        elif quest["kind"] == "battle":
            tag = "BOSS - " if quest.get("boss") else "Mission - "
            items.append((f"{tag}{quest['name']} ({config.MISSION_ENERGY} EN)", False,
                          (lambda a, q=quest: self._launch_story_battle(a, q))))
            items.append((quest["desc"][:44], True, None))
        else:
            items.append((f"Task - {quest['name']} ({quest['energy']} EN)", False,
                          (lambda a, q=quest: self._do_story_task(a, q))))
            items.append((quest["desc"][:44], True, None))
        items.append((f"Quest log: {done}/{len(self.content['story'])} complete",
                      True, None))
        items.append(("Close", False, None))
        self._open_submenu("Ops Console", items)

    def _launch_story_battle(self, app, quest):
        result = activities.launch_mission(app.game_state)
        self.log(result["message"])
        self.reset_modes()
        if result.get("launch_battle"):
            app.start_battle(enemy_ids=quest["enemies"], quest=quest)
            return
        self._after_action(app)

    def _do_story_task(self, app, quest):
        self.log(story.do_hub_task(app.game_state, quest, self.content["story"])["message"])
        self.reset_modes()
        self._after_action(app)

    def _open_training(self, app):
        state = app.game_state
        if self._open_pending_perk(state, None):
            return
        from game.progression import attributes as attrs
        xp = attrs.session_xp(state, self.content["calendar"])
        items = [(f"Train {self.content['characters'][hid]['name']} "
                  f"({config.TRAINING_ENERGY} EN, +{xp} XP)", False,
                  (lambda a, h=hid: self._pick_train_hero(a, h)))
                 for hid in sorted(state.get("roster", {}))]
        items.append(("Close", False, None))
        self._open_submenu("Training Rack", items)

    def _pick_train_hero(self, app, hero_id):
        self.train_hero_id = hero_id
        if self._open_pending_perk(app.game_state, hero_id):
            return
        self.submenu = None
        self.submenu_index = 0
        self.mode = "train_attr"

    def _after_action(self, app):
        if activities.should_pass_out(app.game_state):
            self.log("You pass out...")
            app.go_to_sleep(passed_out=True)

    # ------------------------------------------- training + perks (overlays)

    def _open_pending_perk(self, state, hero_id):
        from game.progression import attributes as attrs
        hero_ids = [hero_id] if hero_id else sorted(state.get("roster", {}))
        for hid in hero_ids:
            entry = state["roster"][hid]
            for attribute in config.ATTRIBUTES:
                tier = attrs.pending_perk_tier(entry, attribute)
                if tier:
                    self.train_hero_id = hid
                    self.perk_ctx = {
                        "hero_id": hid, "attribute": attribute, "tier": tier,
                        "options": attrs.perk_options(attribute, tier,
                                                      self.content["perks"])}
                    self.submenu = None
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
                labels.append(f"{attribute.title()}  {eff}/7  [MAX]")
            else:
                banked = entry.get("attribute_xp", {}).get(attribute, 0)
                cost = attrs.xp_for_rank(trained + 1)
                labels.append(f"{attribute.title()}  {eff}/7  (+{trained})  {banked}/{cost}xp")
        return labels

    def _train_attr_key(self, app, key):
        state = app.game_state
        if key == pygame.K_ESCAPE:
            self.reset_modes()
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
                self.reset_modes()
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
            if not self._open_pending_perk(app.game_state, ctx["hero_id"]):
                self.mode = "train_attr"
                self.submenu_index = 0
        # no Esc: the perk choice is part of the rank-up

    # ------------------------------------------------------------------ draw

    def draw(self, surface, app):
        state = app.game_state
        surface.fill(pixelkit.color("ink"))
        self._draw_map(surface)
        self._draw_entities(surface, state)
        self._draw_hud(surface, state)
        self._draw_prompt(surface, state)
        for i, msg in enumerate(self.messages):
            pixelkit.text(surface, msg, 12, "white",
                          topleft=(6, config.HEIGHT - 30 + i * 13), shadow="ink")

        if self.mode == "submenu" and self.submenu:
            self._draw_submenu(surface, self.submenu["title"],
                               [i[0] for i in self.submenu["items"]],
                               self.submenu["index"],
                               disabled={i[0] for i in self.submenu["items"] if i[1]})
        elif self.mode == "train_attr":
            hero = self.content["characters"][self.train_hero_id]
            self._draw_submenu(surface, f"Train {hero['name']}",
                               self._train_attr_labels(state), self.submenu_index)
        elif self.mode == "perk_choice" and self.perk_ctx:
            ctx = self.perk_ctx
            hero = self.content["characters"][ctx["hero_id"]]
            self._draw_submenu(
                surface, f"{hero['name']} - {ctx['attribute'].title()} rank {ctx['tier']} perk!",
                [f"{p['name']} - {p['blurb']}" for p in ctx["options"]],
                self.submenu_index)
        elif self.mode == "scene" and self.scene:
            self._draw_scene(surface)

    def _draw_map(self, surface):
        for ty, row in enumerate(self._map()):
            for tx in range(MAP_W):
                ch = row[tx] if tx < len(row) else "#"
                name = TILE_NAMES.get(ch, "floor")
                surface.blit(sprites.tile(name), (tx * TILE, HUD_H + ty * TILE))

    def _draw_entities(self, surface, state):
        entities = [(cid, x, y, False) for cid, x, y in self._characters_here(state)]
        entities.append(("player", self.px, self.py, self.facing_left))
        bob = int(self.walk_bob) % 2
        for cid, x, y, flip in sorted(entities, key=lambda e: e[2]):
            spr = sprites.standing(cid, flip=flip)
            oy = bob if cid == "player" else 0
            surface.blit(spr, (int(x) - 6, int(y) - 12 - oy))
            pygame.draw.ellipse(surface, pixelkit.color("shadow"),
                                pygame.Rect(int(x) - 5, int(y) + 4, 10, 3))

    def _draw_hud(self, surface, state):
        hud = pygame.Rect(0, 0, config.WIDTH, HUD_H)
        pygame.draw.rect(surface, pixelkit.color("ink"), hud)
        pygame.draw.line(surface, pixelkit.color("gold"), (0, HUD_H - 1),
                         (config.WIDTH, HUD_H - 1))
        pixelkit.text(surface, f"Issue {state['issue']} Day {state['day']}", 13,
                      "white", topleft=(6, 5))
        pixelkit.text(surface, clock.format_time(state["time_minutes"]), 13,
                      "gold", center=(config.WIDTH // 2 - 60, 10))
        widgets.bar(surface, pygame.Rect(config.WIDTH // 2, 5, 110, 10),
                    state["energy"] / config.DAILY_ENERGY, "green",
                    label=f"{state['energy']}")
        pixelkit.text(surface, f"{state['credits']} cr", 13, "gold",
                      topright=(config.WIDTH - 6, 5))
        pixelkit.text(surface, FLOORS[self.floor]["name"], 13, "steel_light",
                      topright=(config.WIDTH - 90, 5))
        for ev in cal.active_events(state, self.content["calendar"]):
            pixelkit.text(surface, ev["name"], 12, "red",
                          center=(config.WIDTH // 2 + 160, 10), shadow="ink")

    def _draw_prompt(self, surface, state):
        if self.mode != "normal":
            return
        hit = self._nearest_interaction(state)
        if not hit:
            return
        _, _, label = hit
        txt = f"[Enter] {label}"
        w = pixelkit.font(12).size(txt)[0] + 10
        box = pygame.Rect(int(self.px) - w // 2, int(self.py) - 30, w, 13)
        box.clamp_ip(surface.get_rect())
        pygame.draw.rect(surface, pixelkit.color("ink"), box)
        pygame.draw.rect(surface, pixelkit.color("gold"), box, width=1)
        pixelkit.text(surface, txt, 12, "white", center=box.center)

    def _draw_submenu(self, surface, title, labels, selected_index, disabled=()):
        overlay = pygame.Rect(160, 70, 320, 220)
        pixelkit.panel(surface, overlay, fill="navy", border="gold")
        pixelkit.text(surface, title, 15, "gold", bold=True,
                      topleft=(overlay.x + 10, overlay.y + 7), shadow="ink")
        labels = labels or ["(empty)"]
        visible = 8
        selected = selected_index % len(labels)
        first = max(0, min(selected - visible + 1, len(labels) - visible)) \
            if len(labels) > visible else 0
        for i, label in enumerate(labels[first:first + visible]):
            row = pygame.Rect(overlay.x + 6, overlay.y + 26 + i * 21,
                              overlay.width - 12, 19)
            if first + i == selected:
                pygame.draw.rect(surface, pixelkit.color("red"), row)
                pygame.draw.rect(surface, pixelkit.color("ink"), row, width=1)
                pixelkit.cursor(surface, (row.x + 4, row.centery))
            color = "grey" if label in disabled else "white"
            pixelkit.text(surface, label, 13, color,
                          midleft=(row.x + 12, row.centery), shadow="ink")
        if first > 0:
            pixelkit.text(surface, "^", 12, "grey",
                          topright=(overlay.right - 8, overlay.y + 24))
        if first + visible < len(labels):
            pixelkit.text(surface, "v", 12, "grey",
                          topright=(overlay.right - 8, overlay.bottom - 30))
        pixelkit.text(surface, "Enter: choose  Esc: back", 11, "cream",
                      center=(overlay.centerx, overlay.bottom - 11))

    def _draw_scene(self, surface):
        shade = pygame.Surface((config.WIDTH, config.HEIGHT), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 170))
        surface.blit(shade, (0, 0))
        box = pygame.Rect(80, config.HEIGHT - 120, config.WIDTH - 160, 90)
        pixelkit.panel(surface, box, fill="ink", border="gold")
        char_id = self.scene.get("character")
        if char_id:
            big = pygame.transform.scale(sprites.portrait(char_id), (48, 48))
            surface.blit(big, (box.x + 8, box.y - 24))
        pixelkit.text(surface, self.scene["title"], 16, "gold", bold=True,
                      topleft=(box.x + 62, box.y - 20), shadow="maroon")
        line = self.scene["lines"][min(self.scene_line, len(self.scene["lines"]) - 1)]
        self._wrap_text(surface, line, box)
        pixelkit.text(surface, "Enter: continue", 11, "grey",
                      topright=(box.right - 8, box.bottom - 14))

    def _wrap_text(self, surface, line, box):
        words = line.split()
        rows, current = [], ""
        f = pixelkit.font(14)
        for word in words:
            trial = (current + " " + word).strip()
            if f.size(trial)[0] > box.width - 24:
                rows.append(current)
                current = word
            else:
                current = trial
        rows.append(current)
        for i, row in enumerate(rows[:4]):
            pixelkit.text(surface, row, 14, "white",
                          topleft=(box.x + 12, box.y + 10 + i * 16))
