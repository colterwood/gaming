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
                      repairs, requirements, story, unlocks)
from game.progression import gear
from game.social import bonds, dialogue, events
from game.ui import audio, pixelkit, sprites, widgets

TILE = 16
HUD_H = 20
# M36: the HUD packs itself from both edges instead of using fixed centres,
# so a long calendar-event banner can never be drawn through the floor name.
HUD_PAD = 6                 # margin at each end of the strip
HUD_GAP = 8                 # minimum gap between two elements
HUD_BAR_W = 62              # the team energy and team HP bars
HUD_TEXT_SIZE = 13
HUD_EVENT_SIZE = 12         # one size down so the banner never crowds the row
MAP_W = config.MAP_TILES_W
MAP_H = config.MAP_TILES_H

WALKABLE = {".", ",", "m", "=", "_", "H"}
TILE_NAMES = {"#": "wall", "w": "window", "E": "elevator", ".": "floor",
              ",": "carpet", "m": "mat", "S": "counter", "b": "board",
              "O": "console", "Z": "bed", "c": "couch", "t": "table",
              "p": "plant", "r": "rack", "=": "road", "_": "sidewalk",
              "x": "crate", "H": "helipad", "o": "ore",
              # M29 rooms
              "Q": "hangar", "+": "treatment", "T": "workbench",
              "P": "pym bench"}
ZONE_TILE_OVERRIDES = {"p": "tree", ".": "sidewalk"}
STATION_KINDS = {"E": "elevator", "S": "shop", "b": "board", "O": "ops",
                 "Z": "bed", "r": "training", "H": "helipad",
                 "Q": "quinjet", "+": "medbay", "T": "techlab",
                 "P": "pymlab"}
STATION_LABELS = {"elevator": "Elevator", "shop": "Tower Shop",
                  "board": "Assignment Board", "ops": "Ops Console",
                  "bed": "Sleep", "training": "Training Rack",
                  "helipad": "Quinjet", "quinjet": "Quinjet",
                  "medbay": "Treatment Station", "techlab": "Tech Bench",
                  "pymlab": "Pym Bench"}
ZONE_STATION_KINDS = {"helipad", "shop"}    # what works in the field (M10)
# M36: which floor's opening hours each station keeps. Anything absent here
# runs whenever the player does — the shop, the board, the ops console, the
# elevator and the bed have no shift.
STATION_FLOOR = {"training": "training", "medbay": "med_bay",
                 "techlab": "tech_lab", "pymlab": "pym_lab"}
# M35: furniture worth turning over while a repair is in hand. Nothing is
# marked — the hunt is walking the floor and searching things. Mats are
# searched as one field (you roll them back), everything else tile by tile.
SEARCHABLE_FURNITURE = {"c": "couch", "t": "table", "p": "plant",
                        "Z": "bunk", "m": "mats"}
FURNITURE_GROUPS = {"m"}                    # searched as a whole, not per tile

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
            "#............................QQQQ......#",
            "#............................QQQQ......#",
            "#......................................#",
            "#......................................#",
            "#......................................#",
            "#......................................#",
            "#......................................#",
            "########################################",
        ],
        "spawn": (17, 2),
    },
    "med_bay": {
        "name": "Med Bay",
        "map": [
            "########################################",
            "#ww##ww##ww##ww#EE#ww##ww##ww##ww##ww##",
            "#......................................#",
            "#....++++..........................++..#",
            "#......................................#",
            "#......................................#",
            "#......................................#",
            "#....cc....cc....cc....................#",
            "#......................................#",
            "#p....................................p#",
            "#......................................#",
            "#...........tt.........................#",
            "#...........tt.........................#",
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
    "tech_lab": {
        "name": "Tech Lab",
        "map": [
            "########################################",
            "#ww##ww##ww##ww#EE#ww##ww##ww##ww##ww##",
            "#......................................#",
            "#......................................#",
            "#....TTTT..........................TT..#",
            "#......................................#",
            "#......................................#",
            "#......................................#",
            "#.........tt.............tt............#",
            "#.........tt.............tt............#",
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
    "pym_lab": {
        "name": "Pym Lab",
        "map": [
            "########################################",
            "#ww##ww##ww##ww#EE#ww##ww##ww##ww##ww##",
            "#......................................#",
            "#......................................#",
            "#......................................#",
            "#......PPPP............................#",
            "#......................................#",
            "#......................................#",
            "#......................................#",
            "#..............tt......tt..............#",
            "#p.............tt......tt.............p#",
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

# The order the elevator lists them, and what each floor waits on (M29).
# The three original rooms come back with the elevator; the new ones are
# behind their own repair, and the Pym Lab behind Scott Lang's door code.
FLOOR_ORDER = ("common", "ops", "training", "med_bay", "tech_lab", "pym_lab")
BED_FLOOR = "common"        # M36: where you wake up, however the night went


def room_open(state, floor):
    """Whether a room's own station is working right now (M36).

    Rooms used to run 6 AM to 2 AM like the player does, which made the
    tower one undifferentiated surface with no reason to plan a day around
    it. Hours are half-open [open, close) in minutes since midnight of the
    day the day started, so the 6:00-26:00 span is 360..1560 and a closing
    time after midnight is written (24 + h) * 60."""
    hours = config.ROOM_HOURS.get(floor)
    if not hours:
        return True
    opens, closes = hours
    return opens <= state.get("time_minutes", opens) < closes


def room_hours_label(floor):
    """(opens, closes) as clock strings, for menus and refusals."""
    opens, closes = config.ROOM_HOURS[floor]
    return clock.format_time(opens), clock.format_time(closes)


def attrs_rank_for_training(content, state, hero_id):
    """The cheapest level this hero could train right now — what the rack
    row quotes as "from N cr", since the real price depends on which of the
    six they pick."""
    from game.progression import attributes as attrs
    entry = state["roster"][hero_id]
    boosts = content["characters"][hero_id].get("boosts", {})
    levels = [attrs.rank(entry, a) for a in config.ATTRIBUTES
              if attrs.can_train(boosts, entry, a)]
    return min(levels) if levels else config.RANK_MAX
FLOOR_REQUIRES = {
    "ops": ("elevator_repaired", "The elevator doesn't go up yet."),
    "training": ("elevator_repaired", "The elevator doesn't go up yet."),
    "med_bay": ("elevator_repaired", "The elevator doesn't go up yet."),
    "tech_lab": ("elevator_repaired", "The elevator doesn't go up yet."),
    "pym_lab": ("pym_lab_unlocked", "Sealed. The door wants a code you "
                                    "don't have."),
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
        # modes: normal | submenu | train_attr | perk_choice | scene |
        #        resting | keypad
        self.mode = "normal"
        self.submenu = None
        self.solo_ok = False        # M36: consent to empty the team (note 34)
        self.train_hero_id = None
        self.perk_ctx = None
        self.scene = None
        self.scene_line = 0
        self.submenu_index = 0
        self.rest_accum = 0.0       # med bay treatment in progress (M30)
        self.rest_from = 0
        self.keypad = ""            # the locked assignment board (M34)
        self.keypad_message = ""

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
        self.solo_ok = False        # M36: consent to empty the team, per session
        self.train_hero_id = None
        self.perk_ctx = None
        self.scene = None
        self.scene_line = 0
        self.rest_accum = 0.0
        self.keypad = ""

    def return_to_tower(self):
        self.reset_modes()
        if self.area != "tower":
            self.area = "tower"
            self.floor = "common"
        self._place_at_spawn()

    def wake_up(self):
        """Start the day standing beside your own bed (M36).

        Waking used to drop the player at the floor's elevator spawn, or
        wherever `return_to_tower` happened to put them — which after a
        collapse in the HYDRA District meant materialising at the lift with
        no sense of having gone to bed at all. However the night ended,
        morning is the same tile."""
        self.reset_modes()
        self.area = "tower"
        self.floor = BED_FLOOR
        tx, ty = self._bedside()
        self.px = tx * TILE + TILE // 2
        self.py = HUD_H + ty * TILE + TILE // 2
        self.trail = []

    def _bedside(self):
        """A walkable tile next to the bed, or the floor's spawn if the map
        is ever authored without one."""
        rows = FLOORS[BED_FLOOR]["map"]
        for ty, row in enumerate(rows):
            for tx, ch in enumerate(row):
                if STATION_KINDS.get(ch) != "bed":
                    continue
                for dx, dy in ((1, 0), (0, 1), (-1, 0), (0, -1)):
                    nx, ny = tx + dx, ty + dy
                    if (0 <= ny < len(rows) and 0 <= nx < len(rows[ny])
                            and rows[ny][nx] in WALKABLE):
                        return nx, ny
        return FLOORS[BED_FLOOR]["spawn"]

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
        # M36: the rebuilt rooms have somebody in them. A bench with a voice
        # is a place; a bench without one is a menu you walk to. Each shows
        # up only once their room actually works, so lighting a lab is also
        # meeting whoever runs it.
        elif self.floor == "tech_lab" and flags.get("tech_lab_repaired"):
            put("jarvis", 8, 5)         # the tower's own voice, at the bench
        elif self.floor == "pym_lab" and flags.get("pym_lab_repaired"):
            put("hank_pym", 11, 6)
        elif self.floor == "med_bay" and flags.get("med_bay_repaired"):
            put("medbay_unit", 4, 5)
            put("medbay_unit", 8, 5)   # two of them, identical by design
        if flags.get("hulk_arrived") and "hulk" not in roster \
                and self.floor == "training":
            put("hulk", 8, 12)
        bench_offsets = 0
        for hero_id in sorted(roster):
            if hero_id in active:
                continue
            if roster[hero_id].get("dispatch"):     # placed at the site above
                continue
            if roster[hero_id].get("training") or                     roster[hero_id].get("done_training"):
                kind = "train"      # on the mats (M12), or done and waiting
                                    # there to be collected (M36)
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

    def _here_key(self):
        """The area key parts and work-sites are tagged with: a tower floor
        name indoors, a zone id in the field."""
        return self.floor if self.area == "tower" else self.area

    def _repair_targets(self, state):
        """[(job, index, x, y)] for parts of the repair in hand lying where
        the team is standing — a tower floor or (M34) a city zone. Nothing
        shows until the job is taken, the same rule missions play by."""
        found = []
        for job in repairs.active(self.content, state):
            for index, tx, ty in repairs.parts_on(state, job,
                                                  self._here_key()):
                found.append((job, index, tx * TILE + TILE // 2,
                              HUD_H + ty * TILE + TILE // 2))
        return found

    def _station_repair_job(self, state, kind):
        """The repair this station is still waiting on, if it's broken. A
        thing is broken whether or not the board has got around to posting
        the job — the menu says which."""
        for job in self.content["repairs"]:
            if job["station"] == kind and not repairs.flag_set(state, job):
                return job
        return None

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

    def _furniture_here(self, state):
        """Searchable furniture and greenery on this screen.

        M35 made these live only while a repair hunt with hidden pieces was
        in hand, which taught the player that a couch is scenery 95% of the
        time and then quietly expected them to start turning couches over.
        M36: everything is searchable ALWAYS, indoors and out — the tower's
        furniture and the city's trees alike. Almost all of it is empty;
        that is what makes the occasional handful of credits worth the five
        minutes, and it means the habit already exists by the time a repair
        needs it."""
        # A stand of trees a live side arc still wants combed is that arc's
        # business, not an ordinary rummage — otherwise the two prompts sit
        # on the same tile and the generic one wins on a distance tie.
        spoken_for = self._arc_tiles(state)
        found = []
        for ty, row in enumerate(self._map()):
            for tx, ch in enumerate(row):
                if ch not in SEARCHABLE_FURNITURE or (tx, ty) in spoken_for:
                    continue
                if activities.spot_searched(state, self._here_key(), tx, ty):
                    continue
                found.append((tx, ty, self._furniture_name(ch),
                              tx * TILE + TILE // 2, HUD_H + ty * TILE + TILE // 2))
        return found

    def _arc_tiles(self, state):
        """Every tile claimed by a side arc that is still hunting here."""
        claimed = set()
        if self.area == "tower":
            return claimed
        for arc in unlocks.active_arcs(self.content, state, self.area):
            for index in unlocks.searchable(state, arc):
                claimed.update(tuple(t) for t in
                               arc["search_groves"][index]["tiles"])
        return claimed

    def _furniture_name(self, ch):
        """What the thing is called here — a planter indoors is a tree on
        the street, and the prompt should say which."""
        if self.area != "tower" and ch in ZONE_TILE_OVERRIDES:
            return ZONE_TILE_OVERRIDES[ch]
        return SEARCHABLE_FURNITURE[ch]

    def _search_group(self, tx, ty):
        """Every tile one search covers. A mat field is rolled back in one
        go; a couch is a couch."""
        rows = self._map()
        ch = rows[ty][tx]
        if ch not in FURNITURE_GROUPS:
            return [(tx, ty)]
        return [(x, y) for y, row in enumerate(rows)
                for x, c in enumerate(row) if c == ch]

    def _ore_here(self, state):
        """Unworked ore nodes in the current zone (M32). Same daily respawn
        as a crate — one swing per node per day."""
        if self.area == "tower" or not self._zone().get("mining"):
            return []
        found = []
        for ty, row in enumerate(self._map()):
            for tx, ch in enumerate(row):
                if ch == "o" and not activities.spot_searched(
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
        for tx, ty, x, y in self._ore_here(state):
            d = (x - self.px) ** 2 + (y - self.py) ** 2
            if d < best_d:
                best, best_d = ("ore", (tx, ty), "Mine"), d
        for tx, ty, name, x, y in self._furniture_here(state):
            d = (x - self.px) ** 2 + (y - self.py) ** 2
            if d < best_d:
                best, best_d = ("furniture", (tx, ty), f"Search the {name}"), d
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
        for job, i, x, y in self._repair_targets(state):
            d = (x - self.px) ** 2 + (y - self.py) ** 2
            if d < best_d:
                best, best_d = ("part", (job["id"], i), job["part_label"]), d
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
            # M25: the world clock only runs while the team is on its feet.
            # Reading a menu is not an activity — this used to tick behind
            # the board, the shop, the ops console and every other submenu.
            self.tick_accum += dt
            if self.tick_accum >= config.TICK_REAL_SECONDS:
                self.tick_accum -= config.TICK_REAL_SECONDS
                clock.advance(state, config.TICK_GAME_MINUTES)
        elif self.mode == "resting":
            # M30: the Med Bay is the one menu the clock DOES run behind,
            # because the passing hours are what you're paying.
            self._rest_update(dt, app)
        for msg in activities.finish_due_training(state, self.content):
            self.log(msg)           # sessions ending (M12). M36: never a
                                    # rejoin - they wait on the mats to be
                                    # collected, wherever the player is
        if activities.should_pass_out(state):
            self.log("The team passes out...")
            app.go_to_sleep(passed_out=True)

    def _move(self, dt, app):
        # M36 (round 2): movement is NEVER frozen. The first cut stopped the
        # player walking while the team was empty, which turned watching your
        # last hero train into a cage: the session ended, nobody was left to
        # walk over and collect them with, and 2 AM arrived. You can always
        # walk — off a floor that is closing, to the lift, to bed. There is
        # nothing to guard against here anyway: field.roll_ambush returns
        # None at party size 0 and _spring_squad refuses an empty squad.
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
        state = app.game_state
        # M36: a block only has so many patrols in it. Checked BEFORE the
        # accumulator so a quiet zone costs no RNG at all.
        if activities.zone_is_quiet(state, zone["id"]):
            return
        self.ambush_accum += dt
        if self.ambush_accum < config.AMBUSH_TICK_SECONDS:
            return
        self.ambush_accum = 0.0
        squad = field.roll_ambush(zone, len(self._party(state)), self.rng)
        if squad:
            self._spring_squad(app, zone, squad,
                               f"AMBUSH! A HYDRA squad of {len(squad)} "
                               f"jumps the team!")

    def _spring_squad(self, app, zone, squad, message):
        """Start a field fight and count it against the zone's day (M36).
        Ambushes and sprung trap squads are the same fight — no energy, full
        XP — so they share one budget, or capping only one just moves the
        farm onto the other."""
        if not squad or activities.zone_is_quiet(app.game_state, zone["id"]):
            return False            # nothing left in this block today
        self.log(message)
        left = config.AMBUSH_DAILY_CAP - activities.record_fight(
            app.game_state, zone["id"])
        if left <= 0:
            self.log(f"That was the last of them in {zone['name']} today.")
        app.start_battle(enemy_ids=squad, ambush=True)
        return True

    # ----------------------------------------------------------------- input

    def handle_key(self, app, key):
        if self.mode == "keypad":
            self._keypad_key(app, key)
            return
        if self.mode == "resting":
            if key in (pygame.K_RETURN, pygame.K_ESCAPE):
                self._stop_rest(app.game_state, "You get up.")
            return
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
        # M36: start on the first thing that can actually be chosen. Menus
        # here often open with a disabled label row — a job name, a question,
        # a status line — and the cursor landed on it, so the player's first
        # Enter did nothing at all and they had to work out that Down was
        # required. Arrow keys skip those rows too, below.
        self.submenu = {"title": title, "items": items,
                        "index": self._first_enabled(items)}
        self.mode = "submenu"

    @staticmethod
    def _first_enabled(items, start=0, step=1):
        """Index of the next selectable row from `start`, or `start` if the
        menu is nothing but labels."""
        for offset in range(len(items)):
            index = (start + offset * step) % len(items)
            if not items[index][1]:
                return index
        return start

    def _submenu_key(self, app, key):
        menu = self.submenu
        items = menu["items"]
        if key == pygame.K_ESCAPE:
            self.reset_modes()
            return
        if key == pygame.K_UP:
            menu["index"] = self._first_enabled(
                items, (menu["index"] - 1) % len(items), -1)
        elif key == pygame.K_DOWN:
            menu["index"] = self._first_enabled(
                items, (menu["index"] + 1) % len(items), 1)
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
        elif kind == "ore":
            self._mine_node(app, *ident)
        elif kind == "furniture":
            self._search_furniture(app, *ident)
        elif kind == "scout":
            self._do_scout_point(app, ident)
        elif kind == "grove":
            self._search_grove(app, *ident)
        elif kind == "part":
            self._salvage_part(app, *ident)
        elif ident in ("quinjet", "medbay", "techlab", "pymlab"):
            self._open_room_station(app, ident)
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

    def floor_locked(self, state, floor):
        """(locked, why) for a tower floor — M29 gates every floor above the
        common one behind the elevator repair, and the Pym Lab behind the
        code Scott Lang hands over. M36 adds the clock: the training floor
        locks its door at 11 PM."""
        flag, why = FLOOR_REQUIRES.get(floor, (None, ""))
        if flag and not state.get("story_flags", {}).get(flag):
            return True, why
        if floor in config.CLOSED_FLOORS_LOCK_OUT and not room_open(state, floor):
            return True, f"closed until {room_hours_label(floor)[0]}"
        return False, ""

    def _open_elevator(self, app):
        state = app.game_state
        if not state.get("story_flags", {}).get("elevator_repaired"):
            # The car is dead: the elevator IS the repair station until it
            # runs again, so interacting with it offers the work, not floors.
            job = self._station_repair_job(state, "elevator")
            if job:
                self._open_repair_menu(app, job)
                return
            self.log("The car is dead. The panel hangs open, wires and all.")
            self.reset_modes()
            return
        items = []
        for floor in FLOOR_ORDER:
            locked, why = self.floor_locked(state, floor)
            here = self.floor == floor and self.area == "tower"
            label = FLOORS[floor]["name"]
            if locked:
                label += f"  [{why}]"
            elif not self._floor_working(state, floor):
                label += "  [needs repair]"
            items.append((label, locked or here,
                          (lambda a, fl=floor: self._switch_floor(fl, a))))
        # M36: the elevator is an elevator. It used to list every zone in
        # the city as a destination, so the Quinjet sitting in its bay on
        # the Ops floor was scenery — you never had to go near it to fly.
        # Floors here; the jet is boarded where the jet is.
        if state.get("story_flags", {}).get("quinjet_repaired"):
            items.append(("(the Quinjet is in its bay on the Ops floor)",
                          True, None))
        else:
            items.append(("(the Quinjet is grounded)", True, None))
        self._open_submenu("Elevator", items)

    def _floor_working(self, state, floor):
        """Whether a floor's own station is repaired — a room can be
        reachable and still be a building site."""
        for job in self.content["repairs"]:
            if job["floor"] == floor and not repairs.flag_set(state, job):
                return False
        return True

    def _open_helipad(self, app):
        """M11: the Quinjet flies anywhere from a zone helipad, not just home.
        M29: the jet also sits in its bay on the Ops floor, where "fly home"
        is not a useful offer."""
        items = []
        if self.area != "tower":
            items.append(("Avengers Tower", False,
                          (lambda a: self._travel(a, "tower"))))
        for zone in sorted(self.content["zones"].values(), key=lambda z: z["danger"]):
            if zone["id"] == self.area:
                continue
            items.append((f"{zone['name']}  [{'!' * zone['danger']}]", False,
                          (lambda a, zid=zone["id"]: self._travel(a, zid))))
        items.append(("Stay here", False, None))
        self._open_submenu("Quinjet: fly to...", items)

    def _switch_floor(self, floor, app=None):
        self.area = "tower"
        self.floor = floor
        self._place_at_spawn()
        self.reset_modes()
        # M36: no "Common Floor." in the log — the HUD names the floor you
        # are standing on, top right, all the time. Saying it again in the
        # message window spends one of three visible lines on it and pushes
        # something the player actually needs to read off the bottom.
        if app is not None:
            self._greet_on_arrival(app)

    def _greet_on_arrival(self, app):
        """Somebody with a problem raises it the moment you walk in (M36).

        M34 put the tower's repairs in people's mouths, but you still had to
        go and ask: Pepper stood on the Ops floor with a grounded Quinjet and
        said nothing until spoken to. If the person on this floor is waiting
        to tell you something, they say it as you step off the lift."""
        state = app.game_state
        for char_id, _, _ in self._characters_here(state):
            if repairs.triggered_by(self.content, state, char_id) is None:
                continue
            self._repair_conversation(app, char_id)
            return

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
        # M36: a scout point used to be twenty silent minutes and five
        # energy. It is free now, and it SAYS something - authored copy for
        # this specific spot if the quest has any (the three ankle-monitor
        # relays each get their own), otherwise the leader's own line about
        # finding nothing worth finding.
        if result["ok"] and not result.get("hit_day_end"):
            line = self._scout_line(state, quest, index)
            leader = self._leader(state)
            if line and leader:
                self._show_line(leader, line)
        self._after_action(app)

    def _scout_line(self, state, quest, index):
        authored = quest.get("point_lines") or []
        if index < len(authored):
            return authored[index]
        return self._flavor_line(state, "scouting")

    # ------------------------------------------------- tower repairs (M29)

    def _salvage_part(self, app, job_id, index):
        state = app.game_state
        job = repairs.job_by_id(self.content, job_id)
        if job is None:
            return
        self._take_part(app, job, index)

    # M36: what an empty search says, by what you searched. A planter has
    # nothing in it but a planter; saying so in the couch's words ("dust and
    # somebody's old ID badge") is the kind of small wrongness that adds up.
    EMPTY_SEARCH = {
        "plant": "Soil, a few tired worms, and no sign of anything else.",
        "tree": "Bark, roots and startled pigeons. Nothing worth carrying.",
        "mats": "You roll the mats back. Underneath: floor.",
        None: "Nothing but dust and somebody's old ID badge.",
    }

    def _search_furniture(self, app, tx, ty):
        """Turn something over (M35). Costs minutes, never energy — the
        hunt is attention, not attrition. Most of it is empty."""
        state = app.game_state
        area = self._here_key()
        kind = self._furniture_name(self._map()[ty][tx])
        tiles = self._search_group(tx, ty)
        for x, y in tiles:
            activities.mark_spot_searched(state, area, x, y)
        clock.advance(state, config.FURNITURE_SEARCH_MINUTES)
        job = index = None
        for x, y in tiles:
            job, index = repairs.hidden_at(self.content, state, area, x, y)
            if job is not None:
                break
        if job is not None:
            self._claim_hidden(app, job, index)
            return
        self.log(self._furniture_loot(app, kind))
        self._after_action(app)

    def _furniture_loot(self, app, kind):
        """Roll what was down the back of it (M36) and return the line to
        log. Overwhelmingly nothing — the odds are set so that searching is
        a habit worth having rather than an income."""
        state = app.game_state
        if self.rng.random() < config.FURNITURE_SEARCH_CREDIT_CHANCE:
            lo, hi = config.FURNITURE_SEARCH_CREDITS
            found = self.rng.randint(lo, hi)
            state["credits"] = state.get("credits", 0) + found
            return f"Loose change down the back of it: +{found} cr."
        if self.rng.random() < config.FURNITURE_SEARCH_ITEM_CHANCE:
            pool = sorted(i["id"] for i in self.content["items"].values()
                          if i.get("kind") in ("gift", "consumable"))
            if pool:
                item_id = pool[self.rng.randrange(len(pool))]
                name = self.content["items"][item_id]["name"]
                if inventory.add(state, item_id, 1)["ok"]:
                    return f"Somebody left a {name} in there."
                return f"There's a {name} in there, and nowhere to put it."
        return self.EMPTY_SEARCH.get(kind, self.EMPTY_SEARCH[None])

    def _claim_hidden(self, app, job, index):
        """Wrestle a found piece out of wherever it was stashed."""
        self._take_part(app, job, index)

    def _take_part(self, app, job, index):
        """Pick a piece up, however it was found. M35: only a HEAVY part
        costs energy, and only a heavy part is worth the leader saying
        something about — the rest go in a pocket."""
        state = app.game_state
        result = repairs.work_part(state, job, index)
        self.log(result["message"])
        self.reset_modes()
        if result["ok"] and result.get("heavy") and not result.get("hit_day_end"):
            line = self._flavor_line(state, "part_lift")
            if line:
                self._show_line(self._leader(state), line)
        self._after_action(app)

    def _leader(self, state):
        party = self._party(state)
        return party[0] if party else None

    def _flavor_line(self, state, pool, **fields):
        """One of the leader's lines for a repeated field action (M34),
        rotated so the same hero isn't reading the same sentence all day."""
        leader = self._leader(state)
        if leader is None:
            return None
        pools = self.content["flavor"][pool]
        lines = pools.get(leader, pools["default"])
        index = (state["day"] + state["time_minutes"] // 10) % len(lines)
        return lines[index].format(**fields)

    def _open_room_station(self, app, kind):
        """A station in one of the rebuilt rooms. Until its repair lands the
        thing itself is the work site; afterwards it does its job."""
        state = app.game_state
        job = self._station_repair_job(state, kind)
        if job and not repairs.flag_set(state, job):
            self._open_repair_menu(app, job)
            return
        # M36: the room is open, the bench may not be. The Quinjet keeps no
        # hours — grounding the team overnight in a zone they flew to would
        # be a trap, not a schedule.
        if kind != "quinjet" and not self._station_open(app, kind):
            return
        if kind == "quinjet":
            self._open_helipad(app)
        elif kind == "medbay":
            self._start_rest(app)
        elif kind == "techlab":
            self._open_tech_lab(app)
        elif kind == "pymlab":
            self._open_pym_lab(app)
        else:
            self.log(f"{STATION_LABELS[kind]}: nothing installed here yet.")
            self.reset_modes()

    # M36: what each station says when you try it outside its hours. In
    # someone's voice where the room has someone in it.
    CLOSED_STATION = {
        "medbay": ("The ward lights are down to standby. The units are on "
                   "their charge cycle until {opens}."),
        "techlab": ("The fabricators are cold and the bench is locked out. "
                    "Back at {opens}."),
        "pymlab": ("The Pym bench is powered down for the night. It runs "
                   "{opens} to {closes}."),
        "training": "The mats are rolled up. The floor opens again at {opens}.",
    }

    def _station_open(self, app, kind):
        """True if this station is working now; otherwise log why and close
        the menu. The floor is still walkable — only the work stops."""
        floor = STATION_FLOOR.get(kind)
        if floor is None or room_open(app.game_state, floor):
            return True
        opens, closes = room_hours_label(floor)
        self.log(self.CLOSED_STATION.get(kind, "Closed until {opens}.")
                 .format(opens=opens, closes=closes))
        self.reset_modes()
        return False

    # ------------------------------------------------- locked board (M34)

    def _open_keypad(self, app):
        """Pepper's lock on the assignment board. There is no code — she
        opens it herself once the Quinjet flies — but the keypad is real
        enough to try, and trying is free."""
        self.reset_modes()
        self.mode = "keypad"
        self.keypad = ""
        self.keypad_message = "ENTER 4-DIGIT CODE"

    def _keypad_key(self, app, key):
        if key == pygame.K_ESCAPE:
            self.reset_modes()
            return
        if key in (pygame.K_BACKSPACE, pygame.K_DELETE):
            self.keypad = self.keypad[:-1]
            return
        if key == pygame.K_RETURN:
            if len(self.keypad) < 4:
                self.keypad_message = "ENTER 4-DIGIT CODE"
                return
            self.keypad = ""
            self.keypad_message = "ACCESS DENIED"
            return
        name = pygame.key.name(key)
        if len(self.keypad) < 4 and name.isdigit():
            self.keypad += name
            self.keypad_message = "ENTER 4-DIGIT CODE"

    def _draw_keypad(self, surface, state):
        box = pygame.Rect(config.WIDTH // 2 - 96, 92, 192, 128)
        pixelkit.panel(surface, box, fill="ink", border="steel")
        pixelkit.text(surface, "ASSIGNMENT BOARD", 13, "steel_light", bold=True,
                      center=(box.centerx, box.y + 16))
        pixelkit.text(surface, "LOCKED", 20, "red", bold=True,
                      center=(box.centerx, box.y + 38), shadow="maroon")
        slots = pygame.Rect(box.x + 40, box.y + 56, 112, 24)
        pygame.draw.rect(surface, pixelkit.color("shadow"), slots)
        pygame.draw.rect(surface, pixelkit.color("steel_dark"), slots, width=1)
        for i in range(4):
            char = "*" if i < len(self.keypad) else "-"
            pixelkit.text(surface, char, 20, "mint",
                          center=(slots.x + 16 + i * 27, slots.centery))
        colour = "red" if self.keypad_message == "ACCESS DENIED" else "steel"
        pixelkit.text(surface, self.keypad_message, 12, colour,
                      center=(box.centerx, box.y + 92))
        pixelkit.text(surface, "0-9: enter   Esc: give up", 11, "grey_dark",
                      center=(box.centerx, box.bottom - 12))

    # --------------------------------------------------- tech lab (M31)

    def _open_tech_lab(self, app):
        """Buy equipment, and fit it to whoever is standing here."""
        state = app.game_state
        items = []
        for hero_id in sorted(state.get("roster", {})):
            worn = gear.equipped(state["roster"][hero_id])
            summary = ", ".join(
                gear.item_label(state, self.content["items"][i])
                for i in worn.values()) or "nothing fitted"
            items.append((f"{self.content['characters'][hero_id]['name']} - "
                          f"{summary}", False,
                          (lambda a, h=hero_id: self._open_outfit(a, h))))
        items.append(("Order equipment...", False, self._open_gear_shop))
        items.append(("Close", False, None))
        self._open_submenu(f"Tech Bench - {state['credits']} cr", items)

    def _open_gear_shop(self, app):
        state = app.game_state
        stock = sorted((i for i in self.content["items"].values()
                        if gear.is_gear(i) and "tech_lab" in i["sources"]),
                       key=lambda i: (i["slot"], i["id"]))
        items = []
        for item in stock:
            items.append((f"{gear.item_label(state, item)} - {item['price']} cr",
                          item["price"] > state["credits"],
                          (lambda a, it=item: self._buy_gear(a, it))))
            items.append((f"   {gear.SLOT_LABELS[item['slot']]}: "
                          f"{gear.effect_label(state, item)}", True, None))
        items.append(("Back", False, self._open_tech_lab))
        self._open_submenu(f"Fabricator - {state['credits']} cr, "
                           f"{inventory.label(state)}", items)

    def _buy_gear(self, app, item):
        state = app.game_state
        index = self.submenu["index"] if self.submenu else 0
        self.log(activities.buy_item(state, item, 1.0)["message"])
        self._open_gear_shop(app)
        self.submenu["index"] = min(index, len(self.submenu["items"]) - 1)

    def _open_outfit(self, app, hero_id):
        state = app.game_state
        entry = state["roster"][hero_id]
        items = []
        for slot in gear.SLOTS:
            worn = gear.equipped(entry).get(slot)
            label = (gear.item_label(state, self.content["items"][worn])
                     if worn else "empty")
            items.append((f"{gear.SLOT_LABELS[slot]}: {label}", False,
                          (lambda a, s=slot: self._open_slot(a, hero_id, s))))
        items.append(("Back", False, self._open_tech_lab))
        name = self.content["characters"][hero_id]["name"]
        self._open_submenu(f"Outfit {name}", items)

    def _open_slot(self, app, hero_id, slot):
        state = app.game_state
        entry = state["roster"][hero_id]
        items = []
        if gear.equipped(entry).get(slot):
            items.append(("Take it off", False,
                          (lambda a: self._unequip(a, hero_id, slot))))
        for item in gear.owned_for_slot(state, self.content["items"], slot):
            items.append((f"{gear.item_label(state, item)} - "
                          f"{gear.effect_label(state, item)}", False,
                          (lambda a, it=item: self._equip(a, hero_id, it["id"]))))
        if len(items) == (1 if gear.equipped(entry).get(slot) else 0):
            items.append((f"No spare {gear.SLOT_LABELS[slot].lower()} in the "
                          f"bag.", True, None))
        items.append(("Back", False, (lambda a: self._open_outfit(a, hero_id))))
        self._open_submenu(f"{gear.SLOT_LABELS[slot]}", items)

    def _equip(self, app, hero_id, item_id):
        result = gear.equip(app.game_state, hero_id, item_id,
                            self.content["items"])
        self.log(result["message"])
        self._open_outfit(app, hero_id)

    def _unequip(self, app, hero_id, slot):
        result = gear.unequip(app.game_state, hero_id, slot,
                              self.content["items"])
        self.log(result["message"])
        self._open_outfit(app, hero_id)

    # ---------------------------------------------------- med bay (M30)

    def _start_rest(self, app):
        """Sit down and let the clock run. Nothing is skipped — the hours
        tick past in front of you and you get up when you've had enough."""
        ok, reason = activities.can_rest(app.game_state)
        if not ok:
            self.log(reason)
            self.reset_modes()
            return
        self.reset_modes()
        self.mode = "resting"
        self.rest_accum = 0.0
        self.rest_from = energy.team_energy(app.game_state)
        self.log("The chair reclines. Somebody finds you a blanket.")

    def _rest_update(self, dt, app):
        state = app.game_state
        self.rest_accum += dt
        while self.rest_accum >= config.MEDBAY_REST_SECONDS_PER_TICK:
            self.rest_accum -= config.MEDBAY_REST_SECONDS_PER_TICK
            result = activities.rest_tick(state)
            if result["full"] or result["hit_day_end"]:
                self._stop_rest(state,
                                "Patched up." if result["full"]
                                else "The night runs out on you.")
                return

    def _stop_rest(self, state, why):
        gained = energy.team_energy(state) - getattr(self, "rest_from", 0)
        self.mode = "normal"
        self.rest_accum = 0.0
        self.log(f"{why} +{max(0, gained)} EN "
                 f"({clock.format_time(state['time_minutes'])}).")

    def _open_repair_menu(self, app, job):
        """Stand at the broken thing: what's left to find, and the repair
        itself once every part is in hand."""
        state = app.game_state
        items = [(job["name"], True, None)]
        if not repairs.is_active(state, job):
            items.append(("  Not on your list - take it at the board."
                          if repairs.gate_open(state, job)
                          else "  Nobody's cleared this work yet.",
                          True, None))
        else:
            left = repairs.parts_left(state, job)
            total = len(job["parts"])
            items.append((f"  Parts: {total - left}/{total}", True, None))
            if repairs.can_repair(state, job):
                # M36: fitting is free of both clock and energy, so there
                # is no cost to quote here any more.
                items.append((job["repair_label"], False,
                              (lambda a, j=job: self._do_repair(a, j))))
            else:
                items.append(("  Still missing pieces - they're around the "
                              "tower.", True, None))
        items.append(("Close", False, None))
        self._open_submenu("Repair", items)

    def _do_repair(self, app, job):
        state = app.game_state
        result = repairs.repair(self.content, state, job)
        self.reset_modes()
        for message in result.get("messages", [result["message"]]):
            self.log(message)
        if result["ok"] and result.get("scene"):
            unlocks.queue_scene(state, result["scene"])
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
        # M35: a repair part stashed in this box comes out instead of loot.
        job, index = repairs.hidden_at(self.content, state, self.area, tx, ty)
        if job is not None:
            self._claim_hidden(app, job, index)
            return
        result = field.search_loot(zone, self.rng)
        if result["trap"]:
            squad = field.trap_squad(zone["danger"],
                                     len(self._party(state)), self.rng)
            if self._spring_squad(
                    app, zone, squad,
                    f"Booby-trapped! A HYDRA squad of {len(squad)} "
                    f"springs out!"):
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

    def _mine_node(self, app, tx, ty):
        """Work an ore seam (M32). Costs real energy — this is the one field
        job that pays in materials rather than credits."""
        state = app.game_state
        zone = self._zone()
        if not energy.can_afford(state, config.MINE_ENERGY):
            self.log("Too exhausted to swing at rock.")
            return
        energy.spend(state, config.MINE_ENERGY)
        activities.mark_spot_searched(state, self.area, tx, ty)
        clock.advance(state, config.MINE_MINUTES)
        # M35: a part buried in this seam comes out ahead of any ore.
        job, index = repairs.hidden_at(self.content, state, self.area, tx, ty)
        if job is not None:
            self._claim_hidden(app, job, index)
            return
        result = field.mine_node(zone, self.rng)
        if result["trap"]:
            squad = field.trap_squad(zone["danger"],
                                     len(self._party(state)), self.rng)
            if self._spring_squad(
                    app, zone, squad,
                    f"The seam was watched! {len(squad)} HYDRA close in!"):
                return
        # M36: a part that lives in "some ore seam somewhere" rolls here,
        # against whatever the player actually cracked open.
        for message in repairs.mine_drop(self.content, state, self.rng):
            self.log(message)
        if not result["item"]:
            self.log("The seam gives up nothing but dust.")
        else:
            item = self.content["items"][result["item"]]
            if inventory.add(state, item["id"], 1)["ok"]:
                # M34: who swung, and how — in the log, in their voice.
                self.log(self._flavor_line(state, "mining",
                                           material=item["name"])
                         or f"Prised out {item['name']}.")
            else:
                self.log(f"No room for the {item['name']} - "
                         f"{inventory.label(state)}.")
        self._after_action(app)

    # ---------------------------------------------------- pym lab (M32)

    def _open_pym_lab(self, app):
        """Clint's forge, in a lab coat: leave a piece with the materials
        and the money, come back in a few days for it."""
        state = app.game_state
        items = []
        for job in gear.queue(state):
            item = self.content["items"][job["item"]]
            if job["days_left"] > 0:
                items.append((f"{item['name']} +{job['level'] - 1} - "
                              f"{job['days_left']} day(s) to go", True, None))
            else:
                items.append((f"COLLECT: {item['name']} +{job['level'] - 1}",
                              False,
                              (lambda a, j=job: self._collect_upgrade(a, j))))
        owned = [i for i in sorted(self.content["items"].values(),
                                   key=lambda i: i["id"])
                 if gear.is_gear(i) and gear.owns(state, i["id"])
                 and not gear.job_for(state, i["id"])]
        for item in owned:
            ok, reason, target = gear.can_upgrade(state, item)
            if target is None:
                items.append((f"{gear.item_label(state, item)} - fully "
                              f"upgraded", True, None))
                continue
            credits, materials, days = gear.upgrade_recipe(target)
            cost = ", ".join(f"{n} {self.content['items'][m]['name']}"
                             for m, n in sorted(materials.items()))
            wearer = gear.wearer_of(state, item["id"])[0]
            # Say out loud whose back it comes off — it is gone for days.
            off = (f", off {self.content['characters'][wearer]['name']}"
                   if wearer and not state["inventory"].get(item["id"])
                   else "")
            label = (f"{gear.item_label(state, item)} -> +{target - 1}: "
                     f"{cost}, {credits} cr, {days}d{off}")
            items.append((label if ok else f"{label}  [{reason}]", not ok,
                          (lambda a, it=item: self._start_upgrade(a, it))))
        if not owned and not gear.queue(state):
            items.append(("Nothing to work on - buy gear at the Tech Lab.",
                          True, None))
        items.append(("Close", False, None))
        self._open_submenu(f"Pym Bench - {state['credits']} cr", items)

    def _start_upgrade(self, app, item):
        self.log(gear.start_upgrade(app.game_state, item,
                                    self.content["items"])["message"])
        self._open_pym_lab(app)

    def _collect_upgrade(self, app, job):
        self.log(gear.collect(app.game_state, job,
                              self.content["items"])["message"])
        self._open_pym_lab(app)

    # -------------------------------------------------------- rations (M10)

    def _rations(self, state):
        """What the bag holds that can be used on the spot — food for
        energy, and (M36) med kits for the HP the team is now carrying
        between fights."""
        return [(iid, n) for iid, n in sorted(state["inventory"].items())
                if n > 0 and (self.content["items"].get(iid, {}).get("energy")
                              or self.content["items"].get(iid, {}).get("heal"))]

    def _open_rations(self, app):
        state = app.game_state
        foods = self._rations(state)
        if not foods:
            self.log("No rations in the bag - the cafe and street carts sell food.")
            return
        from game.core import health
        # M18: a ration feeds the WHOLE team, so there's nobody to pick.
        fed = all(energy.hero_energy(state, h) >= config.DAILY_ENERGY
                  for h in self._party(state))
        hurt = health.party_needs_treatment(state)
        items = []
        for iid, n in foods:
            item = self.content["items"][iid]
            gains = []
            if item.get("energy"):
                gains.append(f"+{item['energy']} EN")
            if item.get("heal"):        # M36: med kits work out of combat now
                gains.append(f"+{item['heal']}% HP")
            useless = (fed or not item.get("energy")) and \
                      (not hurt or not item.get("heal"))
            items.append((f"{item['name']} x{n}  ({', '.join(gains)} team)"
                          + ("  [no use right now]" if useless else ""),
                          useless, (lambda a, i=iid: self._eat(a, i))))
        items.append(("Never mind", False, None))
        self._open_submenu(f"Supplies - team EN {energy.team_energy(state)}",
                           items)

    def _eat(self, app, item_id):
        from game.core import health
        state = app.game_state
        result = activities.eat_food(state, self.content, item_id)
        self.log(result["message"])
        self.reset_modes()
        # M18: one ration does the whole team, so only stay in the menu if
        # there is both something left to use and someone still short.
        needed = (any(energy.hero_energy(state, h) < config.DAILY_ENERGY
                      for h in self._party(state))
                  or health.party_needs_treatment(state))
        if result["ok"] and needed and self._rations(state):
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
            # M34: Talk is never greyed out. Once the day's points are
            # spent it simply repeats what they have to say.
            items.append(("Talk", False, lambda a: self._talk(a, char_id)))
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

    def _repair_conversation(self, app, char_id):
        """M34: the tower's problems are told to you by the people who have
        them. Jarvis raises the elevator, Pepper the Quinjet, and Coulson
        turns out to have been carrying a contactor relay all morning.

        Returns True if this conversation had something of its own to say,
        in which case the daily talk line stands aside for it."""
        state = app.game_state
        # A part in somebody's pocket comes out first — you asked about the
        # elevator, they remember they have the piece.
        for job in repairs.active(self.content, state):
            index, part = repairs.npc_part(state, job, char_id)
            if index is None:
                continue
            result = repairs.take_npc_part(state, job, index)
            if not result["ok"]:
                continue
            self.log(f"{job['part_label']}: {result['message']}")
            self.reset_modes()
            self._play_scene(part.get("scene") or {
                "character": char_id, "title": self.content["characters"][
                    char_id]["name"],
                "lines": ["\"Here - I think this is yours.\""]})
            return True
        job = repairs.triggered_by(self.content, state, char_id)
        if job is None:
            return False
        repairs.accept(self.content, state, job)
        self.log(f"{job['name']}: {len(job['parts'])} pieces to find.")
        self.reset_modes()
        if job.get("intro_scene"):
            self._play_scene(job["intro_scene"])
        return True

    def _flavor(self, app, char_id):
        if self._repair_conversation(app, char_id):
            return
        char = self.content["characters"][char_id]
        line = dialogue.line_for(app.game_state, char, self.content["dialogue"])
        self.reset_modes()
        if line:
            self._show_line(char_id, line)

    def _talk(self, app, char_id):
        state = app.game_state
        char = self.content["characters"][char_id]
        if self._repair_conversation(app, char_id):
            return
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
            # M34: talking again is never refused. Today's bond points are
            # spent, so this costs nothing and gives nothing — you just get
            # to hear them again, which is what a person is for.
            self.reset_modes()
            line = dialogue.line_for(state, char, self.content["dialogue"])
            if line:
                self._show_line(char_id, line)

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
        if not state.get("story_flags", {}).get("board_unlocked"):
            # M34: Pepper locked it while the tower was falling apart. The
            # keypad is real, the code is not — she unlocks it herself once
            # the Quinjet flies.
            self._open_keypad(app)
            return
        activities.check_board(state)       # M20: read in person, then the
        tier = dispatch.roster_tier(self.content, state)     # card knows it
        power = dispatch.team_power(self.content, state)
        items = []
        # M29: the tower's own repairs head the board. They are worked in
        # person rather than dispatched, so they never take a crew.
        repair_rows = repairs.posted(self.content, state)
        busy = repairs.active_job(self.content, state)
        for job in repair_rows:
            items.append((f"REPAIR - {job['name']}", False,
                          (lambda a, j=job: self._accept_repair(a, j))))
            items.append((f"   {job.get('board_line', job['desc'])}",
                          True, None))
            items.append((f"   {job['credits']} cr, {job['xp']} XP, "
                          f"{len(job['parts'])} parts to find", True, None))
        for job in repairs.active(self.content, state):
            left = repairs.parts_left(state, job)
            where = FLOORS[job["floor"]]["name"]
            progress = (f"parts {len(job['parts']) - left}/{len(job['parts'])}"
                        if left else "ready to fit")
            items.append((f"In hand: {job['name']} - {where}, {progress}",
                          True, None))
        posted = activities.assignment_tasks_today(
            state, self.content["assignments"], tier)
        # M34: a repair takes up a slot on the board. Finish it and an
        # ordinary job moves into the space.
        if repair_rows:
            posted = posted[len(repair_rows):]
        if not posted and not repair_rows:      # M26: one-shot jobs run out
            items.append(("Nothing posted today.", True, None))
        for task in posted:
            under_way = dispatch.find(state, task["id"]) is not None
            label = f"{task['name']} - {self._crew_label(task)}"
            if under_way:
                label += "  [under way]"
            items.append((label, under_way,
                          (lambda a, t=task: self._open_dispatch_picker(a, t))))
            # M23: every reward a job pays, spelled out — credits were the
            # only one on the board, so XP and bond were invisible.
            items.append((f"   {self._reward_label(task)}", True, None))
            requester = task.get("requested_by")
            if requester and not under_way:
                requester_name = self.content["characters"][requester]["name"]
                items.append((f"   requested by {requester_name}", True, None))
        for job in dispatch.active(state):
            names = ", ".join(self.content["characters"][h]["name"]
                              for h in job["heroes"])
            where = self._area_name(job.get("spot", [None])[0])
            items.append((f"Away: {names} - {where}, back in "
                          f"{job['days_left']} day(s)", True, None))
        items.append((self._tier_status(state, tier, power), True, None))
        items.append(("Close", False, None))
        self._open_submenu("Assignment Board", items)

    def _accept_repair(self, app, job):
        result = repairs.accept(self.content, app.game_state, job)
        if result.get("busy"):
            # M36: this line used to call requirements.coulson_says() with
            # `requirements` never imported at module scope — taking a second
            # repair while one was in hand raised NameError and dropped the
            # player out of the game. It is Coulson talking, so he says it.
            self._say_coulson(result["message"])
        else:
            self.log(result["message"])
        if result["ok"]:
            where = FLOORS[job["floor"]]["name"]
            self.log(f"{len(job['parts'])} parts to find. It gets fitted on "
                     f"the {where}.")
        self.reset_modes()

    @staticmethod
    def _tier_phrase(tiers):
        """'Tier 2' / 'Tier 1 and Tier 2' / 'Tier 1-3' for a run of tiers."""
        tiers = sorted(tiers)
        if len(tiers) == 1:
            return f"Tier {tiers[0]}"
        if len(tiers) == 2:
            return f"Tier {tiers[0]} and Tier {tiers[1]}"
        return f"Tier {tiers[0]}-{tiers[-1]}"

    def _tier_status(self, state, tier, power):
        """The footer (M25): what's open, what's finished, what opens next.
        M26 made every job one-shot, so a tier really can be cleared out."""
        from game.hub import requirements

        open_tiers, done_tiers = [], []
        for level in range(1, tier + 1):
            jobs = [t for t in self.content["assignments"]
                    if t.get("tier", 1) == level]
            if jobs and all(requirements.is_done(state, t) for t in jobs):
                done_tiers.append(level)
            else:
                open_tiers.append(level)
        parts = []
        if open_tiers:
            parts.append(f"{self._tier_phrase(open_tiers)} jobs available")
        if done_tiers:
            parts.append(f"{self._tier_phrase(done_tiers)} jobs complete")
        line = (", ".join(parts) + ".") if parts else "No jobs on the board."
        need = config.BOARD_TIER_POWER.get(tier + 1)
        if need:
            line += (f" Tier {tier + 1} jobs unlocked at team power "
                     f"{need} (currently {round(power)}).")
        return line

    @staticmethod
    def _crew_label(task):
        heroes, days = task["heroes"], task["days"]
        return (f"{heroes} Hero{'es' if heroes != 1 else ''} / "
                f"{days} Day{'s' if days != 1 else ''}")

    def _reward_label(self, task):
        """Everything a board job pays out (M23). M24: XP is per attribute
        and named. M25: quoted as the plain base figure — the M11 crew-power
        multiplier still scales what actually lands."""
        parts = [f"{task['credits']} cr"]
        if task.get("xp"):
            parts.append(f"{task['xp']} XP to "
                         f"{dispatch.trains_label(task.get('trains'))}")
        if task.get("bond") and task.get("requested_by"):
            name = self.content["characters"][task["requested_by"]]["name"]
            parts.append(f"+{task['bond']} bond with {name}")
        return ", ".join(parts)     # no job pays items yet — add them here

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
        energy.sync(app.game_state)
        if ok:
            self.log(message)
            self.reset_modes()
            return
        # M36: a refusal is Coulson turning you down to your face, not a
        # grey line in the corner of the screen. Skill requirements are
        # deliberately never advertised (M15), so the refusal IS the
        # feedback — it has to be somewhere the player is looking.
        self._say_coulson(message)

    COULSON_PREFIX = "COULSON: "

    def _say_coulson(self, line):
        """Coulson, in a dialogue box. Falls back to the log if he is not in
        the cast for some reason — a refusal must never be swallowed."""
        if "coulson" not in self.content["characters"]:
            self.log(requirements.coulson_says(line))
            return
        # dispatch.send tags its refusals for the message log; inside a box
        # with his name on the header the prefix is saying it twice.
        if line.startswith(self.COULSON_PREFIX):
            line = line[len(self.COULSON_PREFIX):]
        self._show_line("coulson", line)

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
        if not state.get("story_flags", {}).get("quinjet_repaired"):
            # M29: never offer a job the team physically cannot reach — an
            # accepted mission starts its deadline, so this would hand the
            # player a guaranteed failure.
            items.append(("The Quinjet is grounded.", True, None))
            items.append(("  Until it flies, nothing S.H.I.E.L.D. sends is",
                          True, None))
            items.append(("  a mission - it's a call you can't answer.",
                          True, None))
            items.extend(self._ops_unlock_rows(state))
            items.append(("Close", False, None))
            self._open_submenu("Ops Console", items)
            return
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
            # M23: same rule as a mission briefing — the console tells you
            # where, it doesn't drive you there.
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
        job = self._station_repair_job(state, "training")
        if job and not repairs.flag_set(state, job):
            self._open_repair_menu(app, job)     # torn mats, cracked frame
            return
        if not self._station_open(app, "training"):
            return
        if self._open_pending_perk(state, None):
            return
        party = self._party(state)
        items = []
        for hid in party:
            en = energy.hero_energy(state, hid)
            # M36: the rack bills at the door, so the price of THIS hero's
            # next session belongs on the row you are choosing from.
            price = activities.training_credits(
                attrs_rank_for_training(self.content, state, hid))
            label = (f"Train {self.content['characters'][hid]['name']} "
                     f"(EN {en}, from {price} cr)")
            items.append((label, False,
                          (lambda a, h=hid: self._pick_train_hero(a, h))))
        for hid in sorted(state.get("roster", {})):
            entry = state["roster"][hid]
            lock = entry.get("training")
            name = self.content["characters"][hid]["name"]
            if lock:
                left = activities.training_remaining(state, lock)
                items.append((f"{name} - {lock['attribute'].title()}, "
                              f"{clock.format_duration(left)} to go",
                              True, None))
            elif entry.get("done_training") and hid not in party:
                # M36: a finished session leaves the hero standing here
                # rather than teleporting them onto the team. Collect them.
                items.append((f"Put {name} back on the team", False,
                              (lambda a, h=hid: self._collect_trainee(a, h))))
        items.append(("Close", False, None))
        self._open_submenu("Training Rack (team only)", items)

    def _collect_trainee(self, app, hero_id):
        """Take a hero off the mats and back onto the team, in person."""
        state = app.game_state
        name = self.content["characters"][hero_id]["name"]
        if len(self._party(state)) >= config.PARTY_SIZE_MAX:
            self.log(f"No room on the team for {name} - bench someone first.")
            self.reset_modes()
            return
        ok, message = party_mod.add_to_party(self.content, state, hero_id)
        if ok:
            state["roster"][hero_id].pop("done_training", None)
        self.log(message)
        energy.sync(state)
        self.reset_modes()

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

    def _train_rows(self, state):
        """What the rack offers this hero: the six, plus Enlightenment once
        every one of them is at rank 10 (M33)."""
        from game.progression import mastery
        rows = list(config.ATTRIBUTES)
        if mastery.available(state["roster"][self.train_hero_id]):
            rows.append(mastery.ATTRIBUTE)
        return rows

    def _train_attr_labels(self, state):
        from game.progression import attributes as attrs
        from game.progression import mastery
        hero = self.content["characters"][self.train_hero_id]
        entry = state["roster"][self.train_hero_id]
        labels = []
        for attribute in self._train_rows(state):
            if attribute == mastery.ATTRIBUTE:
                done, needed = mastery.progress(entry)
                en_cost, minutes = activities.training_cost(config.RANK_MAX)
                gain = attrs.session_xp(state, self.content["calendar"],
                                        config.RANK_MAX)
                price = activities.training_credits(config.RANK_MAX)
                labels.append(f"ENLIGHTENMENT  {done}/{needed}xp  (+{gain}xp, "
                              f"{en_cost}EN, {price}cr, "
                              f"{clock.format_duration(minutes)})")
                continue
            # M15: rank is the trainable level (1..RANK_MAX); the innate
            # boost lifts the COMBAT value above it, so show both.
            rank = attrs.rank(entry, attribute)
            eff = attrs.effective_rank(hero["boosts"], entry, attribute)
            head = f"{attribute.title()}  {rank}/{config.RANK_MAX} ({eff:.1f})"
            if not attrs.can_train(hero["boosts"], entry, attribute):
                labels.append(f"{head}  [MAX]")
            else:
                banked = entry.get("attribute_xp", {}).get(attribute, 0)
                cost = attrs.xp_for_rank(rank)
                gain = attrs.session_xp(state, self.content["calendar"], rank)
                en_cost, minutes = activities.training_cost(rank)
                price = activities.training_credits(rank)
                labels.append(f"{head}  {banked}/{cost}xp  (+{gain}xp, "
                              f"{en_cost}EN, {price}cr, "
                              f"{clock.format_duration(minutes)})")
        return labels

    def _train_attr_key(self, app, key):
        state = app.game_state
        if key == pygame.K_ESCAPE:
            self.reset_modes()
            return
        rows = self._train_rows(state)
        if key == pygame.K_UP:
            self.submenu_index = (self.submenu_index - 1) % len(rows)
        elif key == pygame.K_DOWN:
            self.submenu_index = (self.submenu_index + 1) % len(rows)
        elif key == pygame.K_RETURN:
            self._start_session(app, rows[self.submenu_index % len(rows)])

    def _start_session(self, app, attribute):
        """Put the chosen hero on the mats — the ONE place a session starts.

        Every path lands here with the attribute already decided: straight
        off the rack list, or back from the "nobody left on the team"
        question. Confirming used to bounce the player onto the attribute
        list a second time to re-pick what they had already picked."""
        state = app.game_state
        hero_id = self.train_hero_id
        result = activities.start_training(state, self.content, hero_id,
                                           attribute, solo_ok=self.solo_ok)
        if result.get("needs_solo_confirm"):
            # Emptying the team is a decision, not an error. Ask once.
            self._open_solo_prompt(app, hero_id, attribute)
            return
        self.log(result["message"])
        if result["ok"]:
            if not self._party(state):
                name = self.content["characters"][hero_id]["name"]
                self.log(f"Watching {name} workout, hey? Creepy!")
            self.solo_ok = False
            self.reset_modes()          # they're off the team, on the mats

    # ------------------------------------------- training with nobody left

    def _open_solo_prompt(self, app, hero_id, attribute):
        """Nobody would be left standing. Ask once, plainly.

        The first cut asked twice and phrased the confirm as "No - I'll just
        watch", which reads as declining the thing it actually agrees to.
        One question, and the answers answer it."""
        state = app.game_state
        name = self.content["characters"][hero_id]["name"]
        items = [(f"{name} is the only one left on the team, do you want to "
                  f"continue?", True, None)]
        for other in self._benched_candidates(state):
            other_name = self.content["characters"][other]["name"]
            items.append((f"Put {other_name} on point instead", False,
                          (lambda a, o=other, at=attribute:
                           self._promote_and_train(a, o, at))))
        items.append(("Ya - I'll just watch", False,
                      (lambda a, at=attribute:
                       self._begin_solo_training(a, at))))
        items.append(("No!", False, None))
        self._open_submenu("Training", items)

    def _benched_candidates(self, state):
        """Roster heroes who could take the lead: off the team, not away,
        not themselves on the mats."""
        party = self._party(state)
        return [h for h in sorted(state.get("roster", {}))
                if h not in party
                and not state["roster"][h].get("dispatch")
                and not state["roster"][h].get("training")]

    def _promote_and_train(self, app, other_id, attribute):
        ok, message = party_mod.add_to_party(self.content, app.game_state,
                                             other_id)
        self.log(message)
        if not ok:
            self.reset_modes()
            return
        app.game_state["roster"][other_id].pop("done_training", None)
        energy.sync(app.game_state)
        # The team is no longer down to one, so this now goes straight
        # through — with the attribute the player already chose.
        self._start_session(app, attribute)

    def _begin_solo_training(self, app, attribute):
        self.solo_ok = True
        self._start_session(app, attribute)

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
        elif self.mode == "resting":
            self._draw_rest(surface, state)
        elif self.mode == "keypad":
            self._draw_keypad(surface, state)
        elif self.mode == "scene" and self.scene:
            self._draw_scene(surface)

    def _draw_rest(self, surface, state):
        """The treatment overlay (M30): the clock and the bar are the whole
        show — you watch the hours go in and the energy come back."""
        box = pygame.Rect(config.WIDTH // 2 - 110, 96, 220, 92)
        pixelkit.panel(surface, box, fill="ink", border="mint")
        pixelkit.text(surface, "TREATMENT STATION", 15, "mint", bold=True,
                      center=(box.centerx, box.y + 16), shadow="ink")
        pixelkit.text(surface, clock.format_time(state["time_minutes"]), 20,
                      "gold", center=(box.centerx, box.y + 40))
        team = energy.team_energy(state)
        widgets.bar(surface, pygame.Rect(box.x + 24, box.y + 54, 172, 12),
                    team / config.DAILY_ENERGY, "green",
                    label=f"{team} / {config.DAILY_ENERGY}")
        pixelkit.text(surface, "Enter: get up", 12, "steel_light",
                      center=(box.centerx, box.bottom - 12))

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
        # M34: the elevator LOOKS dead until it's fixed — buckled doors and
        # an open panel. Fixing it is visible, not just announced.
        broken_lift = (not in_zone
                       and not state.get("story_flags", {}).get(
                           "elevator_repaired"))
        for ty, row in enumerate(self._map()):
            for tx in range(MAP_W):
                name = self._tile_name(row[tx])
                if broken_lift and name == "elevator":
                    name = "elevator_broken"
                surface.blit(sprites.tile(name),
                             (tx * TILE, HUD_H + ty * TILE))
                if in_zone and ((row[tx] in ("x", "o")
                                 and activities.spot_searched(state, self.area,
                                                              tx, ty))
                                or (tx, ty) in spent):
                    surface.blit(self._search_shade, (tx * TILE, HUD_H + ty * TILE))

    def _worked_grove_tiles(self, state):
        """Stands already combed out.

        M36: returns nothing. Dimming the trees you had already searched
        drew the player a map of their own progress, so coming back the
        next day with the right hero meant walking to the one stand that
        was still lit. Trees look like trees; the notebook is the player's."""
        return set()

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
        for _, _, x, y in self._repair_targets(state):  # salvage (M29)
            points = [(x, y - 6), (x + 5, y), (x, y + 6), (x - 5, y)]
            pygame.draw.polygon(surface, pixelkit.color("orange"), points)
            pygame.draw.polygon(surface, pixelkit.color("ink"), points, width=1)
        # M36: no marker on the stand that turned out to hold something.
        # Finding Stormbreaker without anyone who can lift it used to pin a
        # blue diamond to the map and relabel the prompt "Take Stormbreaker",
        # which named the prize and did the remembering for you. The whole
        # arc is a hunt; the second trip is part of it.
        party = self._party(state)
        bob = int(self.walk_bob) % 2
        if not party:
            # M36: nobody on the team — the whole roster is on the mats or
            # away. You still walk (see _move), so there has to be something
            # on screen doing the walking.
            entities.append(("player", self.px, self.py, self.facing_left, bob))
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
        """The status strip.

        M36: laid out by MEASURING each element and packing left-to-right
        and right-to-left from the edges, instead of the old fixed pixel
        centres. Those were tuned against "Common Floor" with no event
        running; the moment the S.H.I.E.L.D. Supply Drop banner appeared it
        was drawn straight through the floor name. A measured layout cannot
        collide however long the strings get."""
        from game.core import health

        hud = pygame.Rect(0, 0, config.WIDTH, HUD_H)
        pygame.draw.rect(surface, pixelkit.color("ink"), hud)
        pygame.draw.line(surface, pixelkit.color("gold"), (0, HUD_H - 1),
                         (config.WIDTH, HUD_H - 1))

        # --- left to right: date, clock, then the two team bars
        x = HUD_PAD
        x = self._hud_text(surface, f"Issue {state['issue']} Day {state['day']}",
                           "white", x) + HUD_GAP
        x = self._hud_text(surface, clock.format_time(state["time_minutes"]),
                           "gold", x) + HUD_GAP
        # M36: with nobody on the team both bars floor at zero, which reads
        # as "you are about to collapse" — the exact opposite of the truth
        # while you stand watching your last hero train. Say so instead.
        if not energy.party(state):
            x = self._hud_text(surface, "no team", "grey", x) + HUD_GAP
            left_edge = x
        else:
            team_en = energy.team_energy(state)
            widgets.bar(surface, pygame.Rect(x, 5, HUD_BAR_W, 10),
                        team_en / config.DAILY_ENERGY, "green",
                        label=f"{team_en}")
            x += HUD_BAR_W + 4
            hp = health.team_hp_fraction(state)
            widgets.bar(surface, pygame.Rect(x, 5, HUD_BAR_W, 10), hp, "red",
                        label=f"{int(round(hp * 100))}%")
            left_edge = x + HUD_BAR_W + HUD_GAP

        # --- right to left: purse, where you are, what's on today
        right = config.WIDTH - HUD_PAD
        right = self._hud_text(surface, f"{state['credits']} cr", "gold",
                               right, rtl=True) - HUD_GAP
        zone = self._zone()
        where, colour = ((f"{zone['name']} [{'!' * zone['danger']}]", "red")
                         if zone else (FLOORS[self.floor]["name"], "steel_light"))
        right = self._hud_text(surface, where, colour, right, rtl=True) - HUD_GAP
        for ev in cal.active_events(state, self.content["calendar"]):
            if right - pixelkit.font(HUD_EVENT_SIZE).size(ev["name"])[0] < left_edge:
                break                   # no room today; the banner waits
            right = self._hud_text(surface, ev["name"], "red", right, rtl=True,
                                   size=HUD_EVENT_SIZE) - HUD_GAP

    @staticmethod
    def _hud_text(surface, text, colour, x, rtl=False, size=HUD_TEXT_SIZE):
        """Draw one HUD element and return the edge the next one starts
        from — the right edge going left-to-right, the left edge going
        right-to-left."""
        width = pixelkit.font(size).size(text)[0]
        if rtl:
            pixelkit.text(surface, text, size, colour, topright=(x, 5),
                          shadow="ink")
            return x - width
        pixelkit.text(surface, text, size, colour, topleft=(x, 5), shadow="ink")
        return x + width

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
        char_id, title = self._scene_speaker(self.scene_line)
        if char_id:
            big = pygame.transform.scale(sprites.portrait(char_id), (48, 48))
            surface.blit(big, (box.x + 8, box.y - 52))  # fully above the box
        pixelkit.text(surface, title, 16, "gold", bold=True,
                      topleft=(box.x + (62 if char_id else 12), box.y - 24),
                      shadow="maroon")
        line = self.scene["lines"][min(self.scene_line, len(self.scene["lines"]) - 1)]
        self._wrap_text(surface, line, box)
        pixelkit.text(surface, "Enter: continue", 11, "grey",
                      topright=(box.right - 8, box.bottom - 14))

    def _scene_speaker(self, index):
        """(character id or None, header text) for one line of a cutscene.

        M36: a scene may carry `speakers`, one entry per line, naming who is
        on screen — null for the narrator. Thor's arrival opens on four
        sentences of prose about a man standing on the common floor; with a
        single scene-level `character` his portrait sat over all of it, so
        the narrator appeared to be Thor describing himself in the third
        person. Without `speakers` the old behaviour is exactly preserved."""
        scene = self.scene or {}
        speakers = scene.get("speakers")
        if speakers:
            char_id = speakers[min(index, len(speakers) - 1)]
        else:
            char_id = scene.get("character")
        if not char_id:
            # Narration. `narration_title` lets a scene name the place while
            # keeping its authored speaker header for the talking lines.
            return None, scene.get("narration_title") or scene.get("title", "")
        if char_id == scene.get("character") and scene.get("title"):
            return char_id, scene["title"]      # the authored header wins
        character = self.content["characters"].get(char_id)
        return char_id, (character["name"] if character
                         else scene.get("title", ""))

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
