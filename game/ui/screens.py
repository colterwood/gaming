"""Top-level screen routing + the simple screens (boot/title/path/sleep),
pixel-styled (§9 M7). Rendering + input only."""

import pygame

from game import config
from game.core import save as save_module
from game.core.state_machine import GameState
from game.ui import pixelkit

HINTS = {
    GameState.BOOT: "Enter: continue",
    GameState.TITLE: "Up/Down: choose    Enter: select    Esc: back",
    GameState.PATH_SELECT: "Enter: choose the Avengers path",
    GameState.HUB: "",
    GameState.BATTLE: "",
    GameState.PAUSE: "Esc: resume",
    GameState.SLEEP: "Enter: wake up",
}

PATHS = ["AVENGERS", "X-MEN", "GUARDIANS", "DEADPOOL", "ILLUMINATI"]


class TitleMenu:
    """The title screen's menu (M28): Continue / New Game / Load Game, plus
    the slot picker the last two drop into. Rendering + input only —
    save.py owns what a slot holds, App owns which one is being played.

    Rows follow the hub's convention, (label, disabled, action), where an
    action is a (verb, slot) pair rather than a callback so the menu can be
    tested without a window.
    """

    def __init__(self):
        self.mode = "root"      # root | new | load | confirm
        self.index = 0
        self.slot = None        # slot waiting on an overwrite confirmation
        self._rows = None

    # ---------------------------------------------------------- rows

    @staticmethod
    def _slot_label(slot, summary):
        if not summary:
            return f"Slot {slot}  -  empty"
        return (f"Slot {slot}  -  Issue {summary['issue']}, "
                f"Day {summary['day']}   ({summary['heroes']} heroes, "
                f"{summary['credits']} cr)")

    def rows(self):
        """Cached: draw() asks every frame, and each rebuild reads the slot
        files off disk. Nothing can write a slot while the title screen is
        up, so the cache only has to survive a mode change (_go clears it)."""
        if self._rows is None:
            self._rows = self._build_rows()
        return self._rows

    def _build_rows(self):
        slots = save_module.list_slots()
        if self.mode == "confirm":
            return [
                (f"Slot {self.slot} already holds a game. Overwrite it?",
                 True, None),
                ("No, go back", False, ("back", None)),
                ("Yes, start a new game here", False, ("start", self.slot)),
            ]
        if self.mode in ("new", "load"):
            rows = []
            for i, summary in enumerate(slots, start=1):
                # Load can only reach a slot with a game in it; New Game can
                # reach any, but an occupied one has to be confirmed first.
                disabled = self.mode == "load" and not summary
                rows.append((self._slot_label(i, summary), disabled,
                             ("pick", i)))
            rows.append(("Back", False, ("back", None)))
            return rows

        latest = save_module.latest_slot()
        rows = []
        if latest is not None:
            summary = slots[latest - 1]
            rows.append((f"Continue  -  Slot {latest}: Issue "
                         f"{summary['issue']}, Day {summary['day']}",
                         False, ("load_slot", latest)))
        rows.append(("New Game", False, ("new", None)))
        rows.append(("Load Game", latest is None, ("load", None)))
        return rows

    # --------------------------------------------------------- input

    def _go(self, mode):
        self.mode = mode
        self.index = 0
        self._rows = None
        self._move(0)   # a header row (the overwrite question) is disabled

    def _move(self, delta):
        """Step the cursor, skipping disabled rows. Standing still (delta 0)
        still moves off a disabled row onto the next selectable one."""
        rows = self.rows()
        n = len(rows)
        if all(row[1] for row in rows):
            return                          # nothing selectable at all
        if delta:
            self.index = (self.index + delta) % n
        while rows[self.index % n][1]:
            self.index = (self.index + (delta or 1)) % n

    def handle_key(self, app, key):
        rows = self.rows()
        if key == pygame.K_ESCAPE:
            if self.mode != "root":
                self._go("root")
            return
        if key == pygame.K_UP:
            self._move(-1)
        elif key == pygame.K_DOWN:
            self._move(1)
        elif key == pygame.K_RETURN:
            label, disabled, action = rows[self.index % len(rows)]
            if not disabled and action:
                self.activate(app, action)

    def activate(self, app, action):
        verb, slot = action
        if verb == "back":
            self._go("root")
        elif verb in ("new", "load"):
            self._go(verb)
        elif verb == "pick" and self.mode == "load":
            self._load(app, slot)
        elif verb == "pick":
            if save_module.slot_exists(slot):
                self.slot = slot        # never overwrite a game silently
                self._go("confirm")
            else:
                self._start(app, slot)
        elif verb == "start":
            self._start(app, slot)
        elif verb == "load_slot":
            self._load(app, slot)

    def _start(self, app, slot):
        """New Game: the slot is only remembered here — nothing is written
        until the first autosave, so backing out of PATH_SELECT costs the
        game that lives there nothing."""
        app.pending_slot = slot
        self._go("root")
        app.machine.transition(GameState.PATH_SELECT)

    def _load(self, app, slot):
        if not app.load_game(slot):
            return
        self._go("root")
        app.machine.transition(GameState.HUB)


def handle_key(app, key):
    state = app.machine.state
    if state is GameState.BOOT and key == pygame.K_RETURN:
        app.machine.transition(GameState.TITLE)
    elif state is GameState.TITLE:
        app.title_menu().handle_key(app, key)
    elif state is GameState.PATH_SELECT and key == pygame.K_RETURN:
        app.new_game(slot=app.pending_slot)
        app.machine.transition(GameState.HUB)
    elif state is GameState.HUB and app.hub:
        app.hub.handle_key(app, key)
    elif state is GameState.BATTLE and app.battle:
        app.battle.handle_key(app, key)
    elif state is GameState.PAUSE:
        if app.game_state:
            app.pause_scene().handle_key(app, key)
        elif key == pygame.K_ESCAPE:
            app.machine.transition(GameState.HUB)
    elif state is GameState.SLEEP and key == pygame.K_RETURN:
        app.machine.transition(GameState.HUB)


def _hint_bar(surface, txt):
    if not txt:
        return
    pixelkit.text(surface, txt, 13, "cream",
                  center=(config.WIDTH // 2, config.HEIGHT - 12), shadow="ink")


def _title_menu(surface, menu, cx):
    """The M28 title menu, drawn under the logo."""
    rows = menu.rows()
    row_h = 16
    box = pygame.Rect(cx - 160, 200, 320, 16 + row_h * len(rows))
    pixelkit.panel(surface, box, fill="ink", border="gold")
    for i, (label, disabled, _action) in enumerate(rows):
        y = box.y + 16 + i * row_h
        selected = i == menu.index
        c = "grey_dark" if disabled else ("gold" if selected else "cream")
        pixelkit.text(surface, label, 13, c, midleft=(box.x + 18, y))
        if selected and not disabled:
            pixelkit.cursor(surface, (box.x + 8, y))


def _starfield(surface):
    """Night-sky backdrop: navy with deterministic star pixels."""
    surface.fill(pixelkit.color("navy"))
    for i in range(90):
        x = (i * 97 + 31) % config.WIDTH
        y = (i * 57 + 11) % (config.HEIGHT - 40)
        c = "white" if i % 7 == 0 else ("steel_light" if i % 3 == 0 else "steel")
        surface.set_at((x, y), pixelkit.color(c))


def draw(surface, app):
    state = app.machine.state

    if state is GameState.BATTLE and app.battle:
        app.battle.draw(surface)
        return
    if state is GameState.HUB and app.hub and app.game_state:
        app.hub.draw(surface, app)
        return
    if state is GameState.PAUSE and app.game_state:
        app.pause_scene().draw(surface, app)
        return

    _starfield(surface)
    cx = config.WIDTH // 2

    if state is GameState.SLEEP and app.game_state:
        gs = app.game_state
        box = pygame.Rect(cx - 130, 100, 260, 120)
        pixelkit.panel(surface, box, fill="ink", border="gold", shadow=False)
        pixelkit.text(surface, "A NEW DAY", 34, "gold", bold=True,
                      center=(cx, 130), shadow="maroon")
        pixelkit.text(surface, f"Issue {gs['issue']}, Day {gs['day']}", 20, "white",
                      center=(cx, 165))
        pixelkit.text(surface, f"Energy: {gs['energy']}", 15, "mint",
                      center=(cx, 192))
        _hint_bar(surface, HINTS[state])
        return

    if state is GameState.PATH_SELECT:
        pixelkit.text(surface, "CHOOSE YOUR PATH", 28, "yellow", bold=True,
                      center=(cx, 40), shadow="maroon")
        cover_w, cover_h, gap = 100, 150, 18
        total = len(PATHS) * cover_w + (len(PATHS) - 1) * gap
        x = (config.WIDTH - total) // 2
        for i, name in enumerate(PATHS):
            rect = pygame.Rect(x + i * (cover_w + gap), 85, cover_w, cover_h)
            selectable = name == "AVENGERS"
            pixelkit.panel(surface, rect,
                           fill="red" if selectable else "steel_dark",
                           border="gold" if selectable else "ink")
            inner = rect.inflate(-14, -44)
            inner.y = rect.y + 30
            pygame.draw.rect(surface, pixelkit.color(
                "yellow" if selectable else "grey_dark"), inner)
            pygame.draw.rect(surface, pixelkit.color("ink"), inner, width=1)
            pixelkit.text(surface, "#1", 18, "red" if selectable else "grey",
                          bold=True, center=(inner.centerx, inner.centery))
            pixelkit.text(surface, name, 12,
                          "white" if selectable else "grey",
                          center=(rect.centerx, rect.bottom - 12), shadow="ink")
        _hint_bar(surface, HINTS[state])
        return

    # BOOT / TITLE / fallback PAUSE
    pixelkit.text(surface, "MARVEL", 24, "red", bold=True,
                  center=(cx, 90), shadow="ink")
    pixelkit.text(surface, "ROADS TO", 40, "yellow", bold=True,
                  center=(cx, 130), shadow="maroon")
    pixelkit.text(surface, "SECRET WARS", 40, "yellow", bold=True,
                  center=(cx, 168), shadow="maroon")
    if state is GameState.TITLE:
        _title_menu(surface, app.title_menu(), cx)
    elif state is GameState.PAUSE:
        pixelkit.text(surface, "PAUSED", 20, "white", center=(cx, 230))
    _hint_bar(surface, HINTS[state])
