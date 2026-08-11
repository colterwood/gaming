"""Top-level screen routing + the simple screens (boot/title/path/sleep),
pixel-styled (§9 M7). Rendering + input only."""

import pygame

from game import config
from game.core.state_machine import GameState
from game.ui import pixelkit

HINTS = {
    GameState.BOOT: "Enter: continue",
    GameState.TITLE: "Enter: new game",
    GameState.PATH_SELECT: "Enter: choose the Avengers path",
    GameState.HUB: "",
    GameState.BATTLE: "",
    GameState.PAUSE: "Esc: resume",
    GameState.SLEEP: "Enter: wake up",
}

PATHS = ["AVENGERS", "X-MEN", "GUARDIANS", "DEADPOOL", "ILLUMINATI"]


def handle_key(app, key):
    state = app.machine.state
    if state is GameState.BOOT and key == pygame.K_RETURN:
        app.machine.transition(GameState.TITLE)
    elif state is GameState.TITLE:
        if key == pygame.K_RETURN:
            app.machine.transition(GameState.PATH_SELECT)
        elif key == pygame.K_c and app.load_game():
            app.machine.transition(GameState.PATH_SELECT)
            app.machine.transition(GameState.HUB)
    elif state is GameState.PATH_SELECT and key == pygame.K_RETURN:
        app.new_game()
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
        from game.core import save as save_module
        if save_module.slot_exists(1):
            pixelkit.text(surface, "C: continue", 15, "gold",
                          center=(cx, 230), shadow="ink")
    elif state is GameState.PAUSE:
        pixelkit.text(surface, "PAUSED", 20, "white", center=(cx, 230))
    _hint_bar(surface, HINTS[state])
