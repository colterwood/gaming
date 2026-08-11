"""Walkable world (spec §9 M8/M9), 16-bit style: the Avengers Tower floors
plus the city mission zones. Rendering + input only — rules live in
game.hub.* / game.social / game.core.

The player roams as the active TEAM: the leader walks, teammates follow in
a chain. Enter interacts with the nearest station or character.
"""

import random

import pygame

from game import config
from game.core import calendar as cal
from game.core import clock, energy, inventory
from game.core.state_machine import GameState
from game.hub import (activities, dispatch, field, party as party_mod, passive,
                      story, unlocks)
from game.social import bonds, dialogue, events
from game.ui import audio, pixelkit, sprites, widgets

TILE = 16
HUD_H = 20
MAP_W = config.MAP_TILES_W
MAP_H = config.MAP_TILES_H

WALKABLE = {".", ",", "m", "=", "_", "H"}
TILE_NAMES = {"#": "wall", "w": "window", "E": "elevator", ".": "floor",
              ",": "carpet", "m": "mat", "S": "counter", "b": "board",
              "O": "console", "Z": "bed", "c": "couch", "t": "table",
              "p": "plant", "r": "rack", "=": "road", "_": "sidewalk",
              "x": "crate", "H": "helipad"}
ZONE_TILE_OVERRIDES = {"p": "tree", ".": "sidewalk"}
STATION_KINDS = {"E": "elevator", "S": "shop", "b": "board", "O": "ops",
                 "Z": "bed", "r": "training", "H": "helipad"}
STATION_LABELS = {"elevator": "Elevator", "shop": "Tower Shop",
                  "board": "Assignment Board", "ops": "Ops Console",
                  "bed": "Sleep", "training": "Training Rack",
                  "helipad": "Quinjet"}
ZONE_STATION_KINDS = {"helipad", "shop"}    # what works in the field (M10)

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
        ],
        "spawn": (17, 2),
    },
}


def _normalize(rows):
    rows = [r.ljust(MAP_W, "#")[:MAP_W] for r in rows]
    while len(rows) < MAP_H:
        rows.append("#" * MAP_W)
    rows = rows[:MAP_H]
    rows[0] = "#" * MAP_W
    rows[-1] = "#" * MAP_W
    return [("#" + r[1:-1] + "#") for r in rows]


for _floor in FLOORS.values():
    _floor["map"] = _normalize(_floor["map"])

# Talk lines live in data/dialogue.json, tiered by relationship (M11).

# Benched heroes stand where their assignment happens. The train spot sits
# on the big mats, clear of the rack tiles, so a trainee never outranks the
# rack in the interaction-prompt distance check.
ASSIGNMENT_SPOTS = {
    "train": ("training", 24, 12),
    "support": ("ops", 10, 6),
    "socialize": ("common", 22, 12),
    None: ("common", 8, 15),        # idle: loafing by the bunks
}


class HubScene:
    def __init__(self, content):
        self.content = content
        self.area = "tower"         # "tower" | zone id
        self.floor = "common"
        self._zone_maps = {}
        spawn = FLOORS["common"]["spawn"]
        self.px = spawn[0] * TILE + TILE // 2
        self.py = HUD_H + spawn[1] * TILE + TILE // 2
        self.trail = []             # leader position history for followers
        self.facing_left = False
        self.walk_bob = 0.0
        self._search_shade = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
        self._search_shade.fill((0, 0, 0, 110))     # dims rummaged crates
        self.messages = []
        self.log_scroll = 0         # pages back through the log (M19)
        self.tick_accum = 0.0
        self.ambush_accum = 0.0
        self.rng = random.Random()
        # modes: normal | submenu | train_attr | perk_choice | scene
        self.mode = "normal"
        self.submenu = None
        self.train_hero_id = None
        self.perk_ctx = None
        self.scene = None
        self.scene_line = 0
        self.submenu_index = 0

    # ------------------------------------------------------------------ util

    def log(self, message):
        self.messages.append(message)
        self.messages = self.messages[-config.LOG_HISTORY_MAX:]
        self.log_scroll = 0     # a new line always snaps back to the newest

    def scroll_log(self, pages):
        """Page the log window back through history (pages > 0) or forward
        again (M19). Clamped at both ends; a no-op with nothing to show."""
        window = config.LOG_VISIBLE_LINES
        furthest = max(0, len(self.messages) - window)
        self.log_scroll = max(0, min(furthest, self.log_scroll + pages * window))
        return self.log_scroll

    def visible_log(self):
        """(lines, older, newer) — the window on screen plus how many
        messages sit off it in each direction."""
        end = len(self.messages) - self.log_scroll
        start = max(0, end - config.LOG_VISIBLE_LINES)
        return self.messages[start:end], start, self.log_scroll

    def reset_modes(self):
        self.mode = "normal"
        self.submenu = None
        self.submenu_index = 0
        self.train_hero_id = None
        self.perk_ctx = None
        self.scene = None
        self.scene_line = 0

    def return_to_tower(self):
        self.reset_modes()
        if self.area != "tower":
            self.area = "tower"
            self.floor = "common"
        self._place_at_spawn()

    def _place_at_spawn(self):
        if self.area == "tower":
            spawn = FLOORS[self.floor]["spawn"]
        else:
            spawn = self.content["zones"][self.area]["spawn"]
        self.px = spawn[0] * TILE + TILE // 2
        self.py = HUD_H + spawn[1] * TILE + TILE // 2
        self.trail = []

    def _zone(self):
        return self.content["zones"].get(self.area) if self.area != "tower" else None

    def _map(self):
        if self.area == "tower":
            return FLOORS[self.floor]["map"]
        if self.area not in self._zone_maps:
            self._zone_maps[self.area] = _normalize(self.content["zones"][self.area]["map"])
        return self._zone_maps[self.area]

    def _tile_name(self, ch):
        if self.area != "tower" and ch in ZONE_TILE_OVERRIDES:
            return ZONE_TILE_OVERRIDES[ch]
        return TILE_NAMES.get(ch, "floor")

    def _solid(self, px, py):
        tx, ty = int(px // TILE), int((py - HUD_H) // TILE)
        if not (0 <= tx < MAP_W and 0 <= ty < MAP_H):
            return True
        ch = self._map()[ty][tx]
        return ch not in WALKABLE

    # -------------------------------------------------------------- entities

    def _party(self, state):
        return party_mod.get_party(state)

    def _here(self, spot_area):
        """Does an (area-or-floor) tag match the current screen?"""
        if self.area == "tower":
            return spot_area == self.floor
        return spot_area == self.area

    def _characters_here(self, state):
        """(char_id, px, py) for benched roster + NPCs on this screen.
        M13: dispatched heroes stand at their job's work site — find them
        there to recall them in person."""
        placed = []

        def put(cid, tx, ty):
            placed.append((cid, tx * TILE + TILE // 2, HUD_H + ty * TILE + TILE // 2))

        roster = state.get("roster", {})
        away_offsets = 0
        for hero_id in sorted(roster):
            if not roster[hero_id].get("dispatch"):
                continue
            job = dispatch.job_of(state, hero_id)
            spot = (job or {}).get("spot")
            if spot and self._here(spot[0]):
                put(hero_id, spot[1] + away_offsets, spot[2])
                away_offsets += 2
        if self.area != "tower":
            return placed
        active = set(self._party(state))
        flags = state.get("story_flags", {})
        if self.floor == "common":
            put("jarvis", 4, 6)
            put("coulson", 33, 10)
        elif self.floor == "ops":
            put("pepper_potts", 12, 5)
        if flags.get("hulk_arrived") and "hulk" not in roster \
                and self.floor == "training":
            put("hulk", 8, 12)
        bench_offsets = 0
        for hero_id in sorted(roster):
            if hero_id in active:
                continue
            if roster[hero_id].get("dispatch"):     # placed at the site above
                continue
            if roster[hero_id].get("training"):     # on the mats (M12)
                kind = "train"
            else:
                assignment = roster[hero_id].get("assignment")
                kind = assignment["kind"] if assignment else None
            floor, tx, ty = ASSIGNMENT_SPOTS.get(kind, ASSIGNMENT_SPOTS[None])
            if floor == self.floor:
                put(hero_id, tx + bench_offsets, ty)
                bench_offsets += 2
        return placed

    def _mission_target(self, state):
        """(quest, x, y) if the current mission's squad is in this zone.
        M13: nothing shows until the mission is accepted at Ops."""
        zone = self._zone()
        if not zone:
            return None
        quest = story.current_quest(state, self.content["story"])
        if (not quest or quest["kind"] != "battle"
                or quest.get("location") != zone["id"]
                or not story.is_accepted(state, quest)):
            return None
        tx, ty = zone["target_spot"]
        return (quest, tx * TILE + TILE // 2, HUD_H + ty * TILE + TILE // 2)

    def _scout_targets(self, state):
        """[(quest, index, x, y)] for the current scout quest's unworked
        points in this zone (only once accepted, M13)."""
        zone = self._zone()
        if not zone:
            return []
        quest = story.current_quest(state, self.content["story"])
        if (not quest or quest["kind"] != "scout"
                or quest.get("location") != zone["id"]
                or not story.is_accepted(state, quest)):
            return []
        done = story.scouted(state, quest)
        return [(quest, i, tx * TILE + TILE // 2, HUD_H + ty * TILE + TILE // 2)
                for i, (tx, ty) in enumerate(quest["scout_points"])
                if i not in done]

    def _grove_targets(self, state):
        """[(arc, index, label, [(x, y), ...])] for the tree stands a live
        side arc still wants worked in this zone (M17). Distance is measured
        to the nearest TILE of the stand, so standing beside any tree of a
        clump reaches it."""
        found = []
        if self.area == "tower":
            return found
        for arc in unlocks.active_arcs(self.content, state, self.area):
            for index in unlocks.searchable(state, arc):
                tiles = [(tx * TILE + TILE // 2, HUD_H + ty * TILE + TILE // 2)
                         for tx, ty in arc["search_groves"][index]["tiles"]]
                found.append((arc, index,
                              unlocks.action_label(state, arc, index), tiles))
        return found

    def _stations_here(self):
        found = []
        for ty, row in enumerate(self._map()):
            for tx, ch in enumerate(row):
                kind = STATION_KINDS.get(ch)
                if not kind:
                    continue
                if (kind in ZONE_STATION_KINDS) if self.area != "tower" \
                        else (kind != "helipad"):
                    found.append((kind, tx * TILE + TILE // 2,
                                  HUD_H + ty * TILE + TILE // 2))
        return found

    def _station_label(self, kind):
        if kind == "shop" and self.area != "tower":
            return "Street Cart"
        return STATION_LABELS[kind]

    def _crates_here(self, state):
        """Unsearched crate tiles in the current zone (M10 search spots)."""
        if self.area == "tower" or not self._zone().get("loot"):
            return []
        found = []
        for ty, row in enumerate(self._map()):
            for tx, ch in enumerate(row):
                if ch == "x" and not activities.spot_searched(
                        state, self.area, tx, ty):
                    found.append((tx, ty, tx * TILE + TILE // 2,
                                  HUD_H + ty * TILE + TILE // 2))
        return found

    def _nearest_interaction(self, state):
        best = None
        best_d = 26 ** 2
        for cid, x, y in self._characters_here(state):
            d = (x - self.px) ** 2 + (y - self.py) ** 2
            if d < best_d:
                best, best_d = ("char", cid,
                                self.content["characters"][cid]["name"]), d
        for kind, x, y in self._stations_here():
            d = (x - self.px) ** 2 + (y - self.py) ** 2
            if d < best_d:
                best, best_d = ("station", kind, self._station_label(kind)), d
        for tx, ty, x, y in self._crates_here(state):
            d = (x - self.px) ** 2 + (y - self.py) ** 2
            if d < best_d:
                best, best_d = ("crate", (tx, ty), "Search"), d
        for quest, i, x, y in self._scout_targets(state):
            d = (x - self.px) ** 2 + (y - self.py) ** 2
            if d < best_d:
                best, best_d = ("scout", i,
                                quest.get("action_label", "Scout")), d
        for arc, i, label, tiles in self._grove_targets(state):
            for x, y in tiles:
                d = (x - self.px) ** 2 + (y - self.py) ** 2
                if d < best_d:
                    best, best_d = ("grove", (arc["id"], i), label), d
        target = self._mission_target(state)
        if target:
            quest, x, y = target
            d = (x - self.px) ** 2 + (y - self.py) ** 2
            if d < 34 ** 2 and d < best_d:
                best = ("target", quest["id"], f"Engage: {quest['name']}")
        return best

    # ---------------------------------------------------------------- update

    def update(self, dt, app):
        if self.mode == "scene":
            return
        state = app.game_state
        if self.mode == "normal":
            queued = unlocks.pop_scene(state)    # story-arc beats first (M17)
            if queued:
                self._play_scene(queued)
                return
            pending = events.pending_bond_events(state, self.content["bond_scenes"])
            if pending:
                self.scene = pending[0]
                self.scene_line = 0
                self.mode = "scene"
                return
            self._move(dt, app)
            if app.machine.state is not GameState.HUB:
                return      # an ambush started a battle this frame — the
                            # pass-out check must not fire on top of it
                            # (BATTLE -> SLEEP is an illegal transition)
        self.tick_accum += dt
        if self.tick_accum >= config.TICK_REAL_SECONDS:
            self.tick_accum -= config.TICK_REAL_SECONDS
            clock.advance(state, config.TICK_GAME_MINUTES)
        for msg in activities.finish_due_training(
                state, self.content, rejoin=(self.area == "tower")):
            self.log(msg)                           # sessions ending (M12);
                                                    # no teleporting into zones
        if activities.should_pass_out(state):
            self.log("The team passes out...")
            app.go_to_sleep(passed_out=True)

    def _move(self, dt, app):
        keys = pygame.key.get_pressed()
        dx = (keys[pygame.K_RIGHT] - keys[pygame.K_LEFT]) * 90 * dt
        dy = (keys[pygame.K_DOWN] - keys[pygame.K_UP]) * 90 * dt
        if dx < 0:
            self.facing_left = True
        elif dx > 0:
            self.facing_left = False
        moved = False
        for axis_dx, axis_dy in ((dx, 0), (0, dy)):
            nx, ny = self.px + axis_dx, self.py + axis_dy
            feet = [(nx - 4, ny + 6), (nx + 4, ny + 6), (nx - 4, ny), (nx + 4, ny)]
            if (axis_dx or axis_dy) and not any(self._solid(fx, fy) for fx, fy in feet):
                self.px, self.py = nx, ny
                moved = True
        if moved:
            self.walk_bob += dt * 10
            self.trail.insert(0, (self.px, self.py, self.facing_left))
            del self.trail[64:]
            self._maybe_ambush(dt, app)

    def _maybe_ambush(self, dt, app):
        zone = self._zone()
        if not zone:
            return
        self.ambush_accum += dt
        if self.ambush_accum < config.AMBUSH_TICK_SECONDS:
            return
        self.ambush_accum = 0.0
        squad = field.roll_ambush(zone["danger"], len(self._party(app.game_state)),
                                  self.rng)
        if squad:
            self.log(f"AMBUSH! A HYDRA squad of {len(squad)} jumps the team!")
            app.start_battle(enemy_ids=squad, ambush=True)

    # ----------------------------------------------------------------- input

    def handle_key(self, app, key):
        if self.mode == "scene":
            if key == pygame.K_RETURN:
                self.scene_line += 1
                if self.scene_line >= len(self.scene["lines"]):
                    if self.scene.get("id"):    # transient talk lines have none
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
        if key == pygame.K_RETURN:
            hit = self._nearest_interaction(app.game_state)
            if hit:
                self._interact(app, hit)
        elif key == pygame.K_i:
            self._open_rations(app)
        elif key == pygame.K_PAGEUP:            # M19: read what scrolled by
            self.scroll_log(1)
        elif key == pygame.K_PAGEDOWN:
            self.scroll_log(-1)
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
        elif kind == "target":
            self._engage_target(app)
        elif kind == "crate":
            self._search_crate(app, *ident)
        elif kind == "scout":
            self._do_scout_point(app, ident)
        elif kind == "grove":
            self._search_grove(app, *ident)
        elif ident == "bed":
            app.go_to_sleep(passed_out=False)
        elif ident == "elevator":
            self._open_elevator(app)
        elif ident == "helipad":
            self._open_helipad(app)
        elif ident == "shop":
            self._open_shop(app)
        elif ident == "board":
            self._open_board(app)
        elif ident == "training":
            self._open_training(app)
        elif ident == "ops":
            self._open_ops(app)

    def _open_elevator(self, app):
        items = [(FLOORS[f]["name"], self.floor == f and self.area == "tower",
                  (lambda a, fl=f: self._switch_floor(fl)))
                 for f in ("common", "training", "ops")]
        for zone in sorted(self.content["zones"].values(), key=lambda z: z["danger"]):
            danger = "!" * zone["danger"]
            items.append((f"Quinjet: {zone['name']}  [{danger}]", False,
                          (lambda a, zid=zone["id"]: self._travel(a, zid))))
        self._open_submenu("Elevator", items)

    def _open_helipad(self, app):
        """M11: the Quinjet flies anywhere from a zone helipad, not just home."""
        items = [("Avengers Tower", False,
                  (lambda a: self._travel(a, "tower")))]
        for zone in sorted(self.content["zones"].values(), key=lambda z: z["danger"]):
            if zone["id"] == self.area:
                continue
            items.append((f"{zone['name']}  [{'!' * zone['danger']}]", False,
                          (lambda a, zid=zone["id"]: self._travel(a, zid))))
        items.append(("Stay here", False, None))
        self._open_submenu("Quinjet: fly to...", items)

    def _switch_floor(self, floor):
        self.area = "tower"
        self.floor = floor
        self._place_at_spawn()
        self.reset_modes()
        self.log(f"{FLOORS[floor]['name']}.")

    def _travel(self, app, destination):
        clock.advance(app.game_state, config.TRAVEL_MINUTES)
        self.reset_modes()
        if destination == "tower":
            self.area = "tower"
            self.floor = "common"
            self.log("Quinjet home. Tower sweet tower.")
        else:
            self.area = destination
            zone = self.content["zones"][destination]
            self.log(f"{zone['name']} - danger {'!' * zone['danger']}. "
                     f"Stay sharp.")
            for arc in unlocks.active_arcs(self.content, app.game_state,
                                           destination):
                if arc.get("zone_hint"):
                    self.log(arc["zone_hint"])
        self._place_at_spawn()
        self._after_action(app)

    def _engage_target(self, app):
        state = app.game_state
        quest = story.current_quest(state, self.content["story"])
        if not quest:
            return
        result = activities.launch_mission(state)
        self.log(result["message"])
        self.reset_modes()
        if result.get("launch_battle"):
            app.start_battle(enemy_ids=quest["enemies"], quest=quest)
            return
        self._after_action(app)

    def _do_scout_point(self, app, index):
        state = app.game_state
        quest = story.current_quest(state, self.content["story"])
        if not quest or quest["kind"] != "scout":
            return
        result = story.do_scout(state, quest, index, self.content["story"])
        self.log(result["message"])
        self.reset_modes()
        self._after_action(app)

    def _search_grove(self, app, arc_id, index):
        """Comb one stand of trees for a side arc's lost thing (M17). The
        stand that hides it rolls straight into the pickup attempt — which
        only works if the arc's named hero is on the team."""
        state = app.game_state
        arc = next((a for a in self.content["unlocks"] if a["id"] == arc_id),
                   None)
        if arc is None:
            return
        result = unlocks.search(self.content, state, arc, index)
        self.log(result["message"])
        self.reset_modes()
        self._after_action(app)

    # ------------------------------------------------- zone searching (M10)

    def _search_crate(self, app, tx, ty):
        state = app.game_state
        zone = self._zone()
        activities.mark_spot_searched(state, self.area, tx, ty)
        clock.advance(state, config.SEARCH_MINUTES)
        result = field.search_loot(zone, self.rng)
        if result["trap"]:
            squad = field.trap_squad(zone["danger"],
                                     len(self._party(state)), self.rng)
            self.log(f"Booby-trapped! A HYDRA squad of {len(squad)} springs out!")
            app.start_battle(enemy_ids=squad, ambush=True)
            return
        found = []
        left_behind = None
        if result["credits"]:
            state["credits"] += result["credits"]
            found.append(f"{result['credits']} cr")
        if result["item"]:
            item = self.content["items"][result["item"]]
            if inventory.add(state, item["id"], 1)["ok"]:
                found.append(item["name"])
            else:               # M18: a full bag leaves loot in the crate
                left_behind = item["name"]
        self.log(("Found " + " + ".join(found) + ".") if found
                 else "Nothing but rats and packing foam.")
        if left_behind:
            self.log(f"No room for the {left_behind} - {inventory.label(state)}.")
        self._after_action(app)

    # -------------------------------------------------------- rations (M10)

    def _rations(self, state):
        return [(iid, n) for iid, n in sorted(state["inventory"].items())
                if n > 0 and self.content["items"].get(iid, {}).get("energy")]

    def _open_rations(self, app):
        state = app.game_state
        foods = self._rations(state)
        if not foods:
            self.log("No rations in the bag - the cafe and street carts sell food.")
            return
        # M18: a ration feeds the WHOLE team, so there's nobody to pick.
        full = all(energy.hero_energy(state, h) >= config.DAILY_ENERGY
                   for h in self._party(state))
        items = []
        for iid, n in foods:
            item = self.content["items"][iid]
            items.append((f"{item['name']} x{n}  (+{item['energy']} EN team)"
                          + ("  [team full]" if full else ""), full,
                          (lambda a, i=iid: self._eat(a, i))))
        items.append(("Never mind", False, None))
        self._open_submenu(f"Rations - team EN {energy.team_energy(state)}",
                           items)

    def _eat(self, app, item_id):
        state = app.game_state
        result = activities.eat_food(state, self.content, item_id)
        self.log(result["message"])
        self.reset_modes()
        # M18: one ration does the whole team, so only stay in the menu if
        # there is both something left to eat and someone still short.
        hungry = any(energy.hero_energy(state, h) < config.DAILY_ENERGY
                     for h in self._party(state))
        if result["ok"] and hungry and self._rations(state):
            self._open_rations(app)
        self._after_action(app)

    def _interact_char(self, app, char_id):
        state = app.game_state
        char = self.content["characters"][char_id]
        entry = state["roster"].get(char_id)
        if entry is not None and entry.get("training"):
            lock = entry["training"]                # mid-workout: info only
            left = activities.training_remaining(state, lock)
            self._open_submenu(
                char["name"],
                [(f"Training {lock['attribute'].title()} - "
                  f"{clock.format_duration(left)} to go", True, None),
                 ("Never mind", False, None)])
            return
        if entry is not None and entry.get("dispatch"):
            # M13: you found them at the work site — recall them in person.
            job = dispatch.job_of(state, char_id)
            if job:
                self._open_submenu(
                    f"{char['name']} - on assignment",
                    [(f"{job['name']} - back in {job['days_left']} day(s)",
                      True, None),
                     ("Recall (abandon, no reward)", False,
                      (lambda a, tid=job["task_id"]:
                       self._recall_dispatch(a, tid))),
                     ("Never mind", False, None)])
            return
        items = []
        if bonds.bondable(char):
            bond = bonds.ensure_bond(state, char_id)
            can_gift, _ = bonds.gift_allowed(state, char_id)
            items.append(("Talk", bond["talked_today"],
                          lambda a: self._talk(a, char_id)))
            items.append(("Give Gift" + ("" if can_gift else "  [limit]"),
                          not can_gift, lambda a: self._open_gift_menu(a, char_id)))
        else:
            items.append(("Chat", False, lambda a: self._flavor(a, char_id)))
        if entry is not None and not party_mod.in_party(state, char_id):
            items.append(("Swap into team...", False,
                          lambda a: self._open_swap_menu(a, char_id)))
            items.append(("Assign task...", False,
                          lambda a: self._open_assign_menu(a, char_id)))
            if entry.get("assignment"):
                items.append(("Relieve from task", False,
                              lambda a: self._clear_assignment(a, char_id)))
        items.append(("Never mind", False, None))
        title = char["name"]
        if bonds.bondable(char):
            title += f" - Bond {bonds.bond_level(bonds.ensure_bond(state, char_id)['points'])}"
        if entry is not None:
            title += f"  EN {energy.hero_energy(state, char_id)}"
        self._open_submenu(title, items)

    def _play_scene(self, scene):
        """Put a queued story scene on screen, with its sound if it has one
        (M17: the Thor signal lands on a thunder crack)."""
        self.scene = scene
        self.scene_line = 0
        self.mode = "scene"
        audio.play(scene.get("sound"))

    def _show_line(self, char_id, line):
        """Pop a one-line dialogue box (transient scene — nothing marked
        seen). M11: talk lines live in data/dialogue.json by tier."""
        self.scene = {"character": char_id, "lines": [line],
                      "title": self.content["characters"][char_id]["name"]}
        self.scene_line = 0
        self.mode = "scene"

    def _flavor(self, app, char_id):
        char = self.content["characters"][char_id]
        line = dialogue.line_for(app.game_state, char, self.content["dialogue"])
        self.reset_modes()
        if line:
            self._show_line(char_id, line)

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
            self.reset_modes()
            if activities.should_pass_out(state):
                self._after_action(app)     # 2 AM mid-chat: no line tonight
                return
            line = dialogue.line_for(state, char, self.content["dialogue"])
            if line:
                self._show_line(char_id, line)
        else:
            self.log(result["message"])
            self.reset_modes()
            self._after_action(app)

    def _open_gift_menu(self, app, char_id):
        # M13: consumables are giftable too (Hulk loves an Energy Bar)
        state = app.game_state
        gifts = [(iid, n) for iid, n in sorted(state["inventory"].items())
                 if n > 0 and self.content["items"].get(iid, {}).get("kind")
                 in ("gift", "consumable")]
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

    def _open_swap_menu(self, app, incoming_id):
        state = app.game_state
        incoming = self.content["characters"][incoming_id]["name"]
        items = []
        if len(self._party(state)) < config.PARTY_SIZE_MAX:
            items.append((f"Add {incoming} (open slot)", False,
                          (lambda a: self._add_to_party(a, incoming_id))))
        for out_id in self._party(state):
            ok, reason = party_mod.can_swap_in(self.content, state,
                                               incoming_id, out_id)
            out_name = self.content["characters"][out_id]["name"]
            label = f"Swap out {out_name}"
            if not ok:
                label += f"  [{reason}]"
            items.append((label, not ok,
                          (lambda a, o=out_id: self._do_swap(a, incoming_id, o))))
        items.append(("Never mind", False, None))
        self._open_submenu(f"Team change: {incoming} in", items)

    def _add_to_party(self, app, hero_id):
        ok, message = party_mod.add_to_party(self.content, app.game_state, hero_id)
        self.log(message)
        energy.sync(app.game_state)
        self.reset_modes()

    def _do_swap(self, app, incoming_id, outgoing_id):
        ok, message = party_mod.swap(self.content, app.game_state,
                                     incoming_id, outgoing_id)
        self.log(message)
        energy.sync(app.game_state)
        self.reset_modes()

    def _open_assign_menu(self, app, hero_id):
        name = self.content["characters"][hero_id]["name"]
        items = []
        for attribute in config.ATTRIBUTES:
            items.append((f"Train {attribute.title()} (+40 xp/day)", False,
                          (lambda a, attr=attribute:
                           self._do_assign(a, hero_id, "train", attr))))
        for kind in ("support", "socialize"):
            spec = self.content["passive"][kind]
            requirement = spec.get("requires")
            suffix = ""
            if requirement:
                suffix = f"  [{requirement['attribute']} {requirement['min']}+]"
            items.append((f"{spec['label']}{suffix}", False,
                          (lambda a, k=kind: self._do_assign(a, hero_id, k))))
        items.append(("Never mind", False, None))
        self._open_submenu(f"Assign {name}", items)

    def _do_assign(self, app, hero_id, kind, attribute=None):
        ok, message = passive.assign(self.content, app.game_state, hero_id,
                                     kind, attribute)
        self.log(message)
        self.reset_modes()

    def _clear_assignment(self, app, hero_id):
        passive.clear(app.game_state, hero_id)
        self.log(f"{self.content['characters'][hero_id]['name']} stands down.")
        self.reset_modes()

    def _open_shop(self, app):
        state = app.game_state
        discount = activities.shop_discount(state, self.content["calendar"])
        sources = (("tower_shop", "tower_cafe") if self.area == "tower"
                   else ("street_cart",))
        stock = sorted((i for i in self.content["items"].values()
                        if i["kind"] in ("gift", "consumable")
                        and any(s in sources for s in i["sources"])),
                       key=lambda i: i["id"])
        items = [(f"{i['name']} - {int(i['price'] * discount)} cr", False,
                  (lambda a, it=i: self._buy(a, it)))
                 for i in stock]
        items.append(("Close", False, None))
        tag = "  (SALE!)" if discount < 1.0 else ""
        title = "Tower Shop" if self.area == "tower" else "Street Cart"
        self._open_submenu(f"{title} - {state['credits']} cr, "
                           f"{inventory.label(state)}{tag}", items)

    def _buy(self, app, item):
        state = app.game_state
        discount = activities.shop_discount(state, self.content["calendar"])
        self.log(activities.buy_item(state, item, discount)["message"])
        index = self.submenu["index"] if self.submenu else 0
        self._open_shop(app)
        self.submenu["index"] = min(index, len(self.submenu["items"]) - 1)

    def _open_board(self, app):
        """M10: board tasks are dispatches — pick heroes, send them away for
        days; they can't rejoin the party until they return or are recalled.
        M11: tiers unlock with team power; NPC requests pay bond."""
        state = app.game_state
        activities.check_board(state)       # M20: read in person, then the
        tier = dispatch.roster_tier(self.content, state)     # card knows it
        power = dispatch.team_power(self.content, state)
        items = []
        for task in activities.assignment_tasks_today(
                state, self.content["assignments"], tier):
            under_way = dispatch.find(state, task["id"]) is not None
            label = (f"{task['name']} - {self._crew_label(task)}, "
                     f"~{task['credits']} cr")
            if under_way:
                label += "  [under way]"
            items.append((label, under_way,
                          (lambda a, t=task: self._open_dispatch_picker(a, t))))
            requester = task.get("requested_by")
            if requester and not under_way:
                requester_name = self.content["characters"][requester]["name"]
                items.append((f"   requested by {requester_name}: "
                              f"+{task.get('bond', 0)} bond", True, None))
        next_tier = tier + 1
        if next_tier in config.BOARD_TIER_POWER:
            need = config.BOARD_TIER_POWER[next_tier]
            items.append((f"Tier {next_tier} jobs at team power {need} "
                          f"(now {round(power)})", True, None))
        for job in dispatch.active(state):
            names = ", ".join(self.content["characters"][h]["name"]
                              for h in job["heroes"])
            where = self._area_name(job.get("spot", [None])[0])
            items.append((f"Away: {names} - {where}, back in "
                          f"{job['days_left']} day(s)", True, None))
        items.append(("Close", False, None))
        self._open_submenu(f"Assignment Board - Tier {tier}", items)

    @staticmethod
    def _crew_label(task):
        heroes, days = task["heroes"], task["days"]
        return (f"{heroes} Hero{'es' if heroes != 1 else ''} / "
                f"{days} Day{'s' if days != 1 else ''}")

    def _area_name(self, area):
        if area in FLOORS:
            return FLOORS[area]["name"]
        zone = self.content["zones"].get(area)
        return zone["name"] if zone else "parts unknown"

    def _open_dispatch_picker(self, app, task, picked=()):
        state = app.game_state
        picked = list(picked)
        party = self._party(state)
        remaining_party = [p for p in party if p not in picked]
        items = []
        for hero_id in sorted(state["roster"]):
            if hero_id in picked or state["roster"][hero_id].get("dispatch"):
                continue
            name = self.content["characters"][hero_id]["name"]
            en = energy.hero_energy(state, hero_id)
            power = dispatch.hero_power(self.content, state, hero_id)
            label = f"Send {name}  (EN {en}, PWR {round(power)})"
            training = bool(state["roster"][hero_id].get("training"))
            would_empty = hero_id in party and len(remaining_party) <= 1
            if hero_id in party:
                label += "  [on team]"
            if would_empty:
                label += "  [team would be empty]"
            if training:
                label += "  [training]"
            items.append((label, would_empty or training,
                          (lambda a, h=hero_id:
                           self._pick_dispatch_hero(a, task, picked + [h]))))
        items.append(("Cancel", False, None))
        need = task["heroes"] - len(picked)
        self._open_submenu(f"{task['name']}: pick {need} hero(es)", items)

    def _pick_dispatch_hero(self, app, task, picked):
        if len(picked) < task["heroes"]:
            self._open_dispatch_picker(app, task, picked)
            return
        ok, message = dispatch.send(self.content, app.game_state, task, picked)
        self.log(message)
        energy.sync(app.game_state)
        self.reset_modes()

    def _recall_dispatch(self, app, task_id):
        ok, message = dispatch.recall(self.content, app.game_state, task_id)
        self.log(message)
        self.reset_modes()

    def _open_ops(self, app):
        """M13: missions are OFFERED here first — nothing shows in the field
        until you accept, and the deadline clock starts at accept."""
        state = app.game_state
        quest = story.current_quest(state, self.content["story"])
        done = sum(1 for v in state.get("quests", {}).values()
                   if v["status"] == "done")
        items = []
        if quest is None:
            items.append(("Chapters 1-2 complete!", True, None))
        else:
            zone = self.content["zones"].get(quest.get("location", ""), {})
            where = zone.get("name", "?")
            danger = "!" * zone.get("danger", 0)
            if story.is_locked(state, quest):
                entry = state["quests"][quest["id"]]
                wait = entry.get("retry_day", 0) - story.abs_day(state)
                items.append((f"FAILED - {quest['name']} (retry in {wait}d)",
                              True, None))
            elif not story.is_accepted(state, quest):
                tag = "BOSS - " if quest.get("boss") else "NEW - "
                items.append((f"{tag}{quest['name']}", True, None))
                items.append((f"  Where: {where}  [{danger}]", True, None))
                if quest.get("deadline_days"):
                    items.append((f"  Deadline: {quest['deadline_days']} day(s) "
                                  f"once accepted", True, None))
                items.append(("  ACCEPT MISSION", False,
                              (lambda a, q=quest: self._accept_quest(a, q))))
            else:
                tag = ("BOSS - " if quest.get("boss")
                       else "Scout - " if quest["kind"] == "scout"
                       else "Mission - ")
                items.append((f"{tag}{quest['name']}", True, None))
                items.append((f"  Where: {where}  [{danger}]", True, None))
                left = story.days_left(state, quest)
                if left is not None:
                    items.append((f"  Deadline: {left} day(s) left", True, None))
                if quest["kind"] == "scout":
                    worked = len(story.scouted(state, quest))
                    total = len(quest["scout_points"])
                    items.append((f"  Progress: {worked}/{total} spots worked",
                                  True, None))
                # M22: no taxi. Accepting a job tells you where it is; getting
                # there is the player's own trip to the Quinjet.
                items.append(("  Get to the Quinjet when you're ready.",
                              True, None))
            desc = quest["desc"]
            items.append((desc if len(desc) <= 44 else desc[:41] + "...",
                          True, None))
        items.extend(self._ops_unlock_rows(state))
        items.append((f"Quest log: {done}/{len(self.content['story'])} complete",
                      True, None))
        items.append(("Close", False, None))
        self._open_submenu("Ops Console", items)

    def _ops_unlock_rows(self, state):
        """Side arcs run alongside the mission chain (M17), so the console
        lists whatever signal is currently open and flies you to it."""
        rows = []
        for arc in unlocks.active_arcs(self.content, state):
            zone = self.content["zones"].get(arc["location"], {})
            where = zone.get("name", "?")
            rows.append((f"SIGNAL - {arc['name']}", True, None))
            rows.append((f"  Where: {where}  [{'!' * zone.get('danger', 0)}]",
                         True, None))
            if unlocks.status(state, arc) == "found":
                rows.append(("  Found it - someone has to lift it", True, None))
            else:
                total = len(arc["search_groves"])
                rows.append((f"  Searched: {len(unlocks.searched(state, arc))}"
                             f"/{total} stands of trees", True, None))
            rows.append((f"  Fly to {where} now", False,
                         (lambda a, z=arc["location"]: self._travel(a, z))))
        return rows

    def _accept_quest(self, app, quest):
        result = story.accept(app.game_state, quest)
        self.log(result["message"])
        if result["ok"]:
            self._open_ops(app)     # reopen on the briefing (M22: there is
            self.submenu["index"] = 0       # no flight to jump the cursor to)
        else:
            self.reset_modes()

    def _open_training(self, app):
        """M12: only ACTIVE party members can start a session, and starting
        one pulls the hero off the team until the clock runs out."""
        state = app.game_state
        if self._open_pending_perk(state, None):
            return
        party = self._party(state)
        items = []
        for hid in party:
            en = energy.hero_energy(state, hid)
            last = len(party) <= 1
            label = f"Train {self.content['characters'][hid]['name']} (EN {en})"
            if last:
                label += "  [team would be empty]"
            items.append((label, last,
                          (lambda a, h=hid: self._pick_train_hero(a, h))))
        for hid in sorted(state.get("roster", {})):
            lock = state["roster"][hid].get("training")
            if lock:
                left = activities.training_remaining(state, lock)
                items.append((f"{self.content['characters'][hid]['name']} - "
                              f"{lock['attribute'].title()}, "
                              f"{clock.format_duration(left)} to go",
                              True, None))
        items.append(("Close", False, None))
        self._open_submenu("Training Rack (team only)", items)

    def _pick_train_hero(self, app, hero_id):
        self.train_hero_id = hero_id
        if self._open_pending_perk(app.game_state, hero_id):
            return
        self.submenu = None
        self.submenu_index = 0
        self.mode = "train_attr"

    def _after_action(self, app):
        if activities.should_pass_out(app.game_state):
            self.log("The team passes out...")
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
            # M15: rank is the trainable level (1..RANK_MAX); the innate
            # boost lifts the COMBAT value above it, so show both.
            rank = attrs.rank(entry, attribute)
            eff = attrs.effective_rank(hero["boosts"], entry, attribute)
            head = f"{attribute.title()}  {rank}/{config.RANK_MAX} ({eff:.1f})"
            if not attrs.can_train(hero["boosts"], entry, attribute):
                labels.append(f"{head}  [MAX]")
            else:
                banked = entry.get("attribute_xp", {}).get(attribute, 0)
                cost = attrs.xp_for_rank(rank, hero["boosts"].get(attribute, 0))
                gain = attrs.session_xp(state, self.content["calendar"], rank)
                en_cost, minutes = activities.training_cost(rank)
                labels.append(f"{head}  {banked}/{cost}xp  (+{gain}xp, "
                              f"{en_cost}EN, {clock.format_duration(minutes)})")
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
            result = activities.start_training(state, self.content,
                                               self.train_hero_id, attribute)
            self.log(result["message"])
            if result["ok"]:
                self.reset_modes()      # they're off the team, on the mats

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
                if ctx["hero_id"] in self._party(app.game_state):
                    self.mode = "train_attr"
                    self.submenu_index = 0
                else:
                    self.reset_modes()  # benched/dispatched perk: no rack
                                        # session for off-team heroes (M12)

    # ------------------------------------------------------------------ draw

    def draw(self, surface, app):
        state = app.game_state
        surface.fill(pixelkit.color("ink"))
        self._draw_map(surface, state)
        self._draw_entities(surface, state)
        self._draw_hud(surface, state)
        self._draw_prompt(surface, state)
        self._draw_log(surface)
        if self.mode == "normal":
            pixelkit.text(surface, "I: rations   PgUp/PgDn: log", 11, "grey",
                          topright=(config.WIDTH - 6, config.HEIGHT - 14))

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
                surface,
                f"{hero['name']} - {ctx['attribute'].title()} rank {ctx['tier']} perk!",
                [f"{p['name']} - {p['blurb']}" for p in ctx["options"]],
                self.submenu_index)
        elif self.mode == "scene" and self.scene:
            self._draw_scene(surface)

    def _draw_log(self, surface):
        """The message window, with counts of what sits off it either way
        (M19). Sits clear of the hint bar so a long line can't run into it."""
        lines, older, newer = self.visible_log()
        top = config.HEIGHT - 30 - config.LOG_VISIBLE_LINES * 13
        for i, msg in enumerate(lines):
            pixelkit.text(surface, msg, 12, "white",
                          topleft=(6, top + i * 13), shadow="ink")
        if older:
            pixelkit.text(surface, f"^{older}", 11, "gold",
                          topright=(config.WIDTH - 6, top), shadow="ink")
        if newer:
            pixelkit.text(surface, f"v{newer}", 11, "gold",
                          topright=(config.WIDTH - 6, top + 13), shadow="ink")

    def _draw_map(self, surface, state):
        in_zone = self.area != "tower"
        spent = self._worked_grove_tiles(state) if in_zone else set()
        for ty, row in enumerate(self._map()):
            for tx in range(MAP_W):
                surface.blit(sprites.tile(self._tile_name(row[tx])),
                             (tx * TILE, HUD_H + ty * TILE))
                if in_zone and ((row[tx] == "x"
                                 and activities.spot_searched(state, self.area,
                                                              tx, ty))
                                or (tx, ty) in spent):
                    surface.blit(self._search_shade, (tx * TILE, HUD_H + ty * TILE))

    def _worked_grove_tiles(self, state):
        """Tiles of stands already combed out, dimmed like a rummaged crate.
        The one still holding the item stays lit even after it's found."""
        spent = set()
        for arc in unlocks.active_arcs(self.content, state, self.area):
            live = set(unlocks.searchable(state, arc))
            for index in unlocks.searched(state, arc):
                if index in live:
                    continue
                spent.update(tuple(t) for t in
                             arc["search_groves"][index]["tiles"])
        return spent

    def _draw_entities(self, surface, state):
        entities = [(cid, x, y, False, 0)
                    for cid, x, y in self._characters_here(state)]
        target = self._mission_target(state)
        if target:
            _, x, y = target
            entities.append(("hydra_squad", x, y, False, 0))
        for _, _, x, y in self._scout_targets(state):   # objective markers
            points = [(x, y - 6), (x + 5, y), (x, y + 6), (x - 5, y)]
            pygame.draw.polygon(surface, pixelkit.color("gold"), points)
            pygame.draw.polygon(surface, pixelkit.color("ink"), points, width=1)
        for arc, index, _, tiles in self._grove_targets(state):
            # Only the FOUND stand gets a marker — the hunt itself is on foot.
            if unlocks.status(state, arc) != "found":
                continue
            x = sum(t[0] for t in tiles) // len(tiles)
            y = sum(t[1] for t in tiles) // len(tiles)
            points = [(x, y - 7), (x + 6, y), (x, y + 7), (x - 6, y)]
            pygame.draw.polygon(surface, pixelkit.color("sky"), points)
            pygame.draw.polygon(surface, pixelkit.color("white"), points, width=1)
        party = self._party(state)
        bob = int(self.walk_bob) % 2
        for i, hero_id in enumerate(party):
            if i == 0:
                entities.append((hero_id, self.px, self.py, self.facing_left, bob))
            else:
                idx = min(len(self.trail) - 1, i * 9 - 1)
                if idx >= 0:
                    x, y, flip = self.trail[idx]
                    entities.append((hero_id, x, y, flip, bob if idx < 30 else 0))
        for cid, x, y, flip, oy in sorted(entities, key=lambda e: e[2]):
            spr = sprites.standing(cid, flip=flip)
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
                      "gold", center=(config.WIDTH // 2 - 70, 10))
        team_en = energy.team_energy(state)
        widgets.bar(surface, pygame.Rect(config.WIDTH // 2 - 10, 5, 100, 10),
                    team_en / config.DAILY_ENERGY, "green",
                    label=f"{team_en}")
        pixelkit.text(surface, f"{state['credits']} cr", 13, "gold",
                      topright=(config.WIDTH - 6, 5))
        zone = self._zone()
        if zone:
            pixelkit.text(surface, f"{zone['name']} [{'!' * zone['danger']}]", 13,
                          "red", topright=(config.WIDTH - 70, 5))
        else:
            pixelkit.text(surface, FLOORS[self.floor]["name"], 13, "steel_light",
                          topright=(config.WIDTH - 70, 5))
        for ev in cal.active_events(state, self.content["calendar"]):
            pixelkit.text(surface, ev["name"], 12, "red",
                          center=(config.WIDTH // 2 + 170, 10), shadow="ink")

    def _draw_prompt(self, surface, state):
        if self.mode != "normal":
            return
        hit = self._nearest_interaction(state)
        if not hit:
            return
        _, _, label = hit
        txt = f"[Enter] {label}"
        w = pixelkit.font(12).size(txt)[0] + 12
        box = pygame.Rect(int(self.px) - w // 2, int(self.py) - 30, w, 13)
        box.clamp_ip(surface.get_rect())
        pygame.draw.rect(surface, pixelkit.color("ink"), box)
        pygame.draw.rect(surface, pixelkit.color("gold"), box, width=1)
        pixelkit.text(surface, txt, 12, "white", center=box.center)

    def _draw_submenu(self, surface, title, labels, selected_index, disabled=()):
        overlay = pygame.Rect(150, 60, 340, 240)
        pixelkit.panel(surface, overlay, fill="navy", border="gold")
        pixelkit.text(surface, title, 15, "gold", bold=True,
                      topleft=(overlay.x + 10, overlay.y + 7), shadow="ink")
        labels = labels or ["(empty)"]
        visible = 9
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
        pixelkit.drop_queued_text()     # cutscene hides world text
        shade = pygame.Surface((config.WIDTH, config.HEIGHT), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 170))
        surface.blit(shade, (0, 0))
        box = pygame.Rect(80, config.HEIGHT - 120, config.WIDTH - 160, 90)
        pixelkit.panel(surface, box, fill="ink", border="gold")
        char_id = self.scene.get("character")
        if char_id:
            big = pygame.transform.scale(sprites.portrait(char_id), (48, 48))
            surface.blit(big, (box.x + 8, box.y - 52))  # fully above the box
        pixelkit.text(surface, self.scene["title"], 16, "gold", bold=True,
                      topleft=(box.x + 62, box.y - 24), shadow="maroon")
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
