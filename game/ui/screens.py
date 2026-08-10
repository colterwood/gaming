"""Placeholder screens for every game state (M0). Rendering + input only —
all rules live in game.core.state_machine."""

import pygame

from game import config
from game.core.state_machine import GameState

NAVY = pygame.Color(config.PALETTE["navy"])
CREAM = pygame.Color(config.PALETTE["cream"])
RED = pygame.Color(config.PALETTE["red"])
GOLD = pygame.Color(config.PALETTE["gold"])
INK = pygame.Color(config.PALETTE["ink"])
GREY = pygame.Color(90, 90, 100)

HINTS = {
    GameState.BOOT: "Enter: continue",
    GameState.TITLE: "Enter: start",
    GameState.PATH_SELECT: "Enter: choose the Avengers path",
    GameState.HUB: "B: battle   P/Esc: pause   S: sleep",
    GameState.BATTLE: "Enter: finish battle (back to hub)",
    GameState.PAUSE: "Esc: resume",
    GameState.SLEEP: "Enter: wake up",
}

PATHS = ["AVENGERS", "X-MEN", "GUARDIANS", "DEADPOOL", "ILLUMINATI"]


def handle_key(app, key):
    state = app.machine.state
    if state is GameState.BOOT and key == pygame.K_RETURN:
        app.machine.transition(GameState.TITLE)
    elif state is GameState.TITLE and key == pygame.K_RETURN:
        app.machine.transition(GameState.PATH_SELECT)
    elif state is GameState.PATH_SELECT and key == pygame.K_RETURN:
        app.machine.transition(GameState.HUB)
    elif state is GameState.HUB:
        if key == pygame.K_b:
            app.start_battle()
        elif key in (pygame.K_p, pygame.K_ESCAPE):
            app.machine.transition(GameState.PAUSE)
        elif key == pygame.K_s:
            app.machine.transition(GameState.SLEEP)
    elif state is GameState.BATTLE and app.battle:
        app.battle.handle_key(app, key)
    elif state is GameState.PAUSE and key == pygame.K_ESCAPE:
        app.machine.transition(GameState.HUB)
    elif state is GameState.SLEEP and key == pygame.K_RETURN:
        app.machine.transition(GameState.HUB)


def _text(surface, txt, size, color, center=None, topleft=None):
    font = pygame.font.Font(None, size)
    img = font.render(txt, True, color)
    rect = img.get_rect()
    if center:
        rect.center = center
    if topleft:
        rect.topleft = topleft
    surface.blit(img, rect)


def draw(surface, app):
    state = app.machine.state

    if state is GameState.BATTLE and app.battle:
        app.battle.draw(surface)
        _text(surface, f"{app.fps:.0f} fps", 24, GOLD, topleft=(12, 10))
        return

    surface.fill(NAVY)
    cx = config.WIDTH // 2

    if state is GameState.PATH_SELECT:
        _text(surface, "CHOOSE YOUR PATH", 56, CREAM, center=(cx, 90))
        cover_w, gap = 200, 40
        total = len(PATHS) * cover_w + (len(PATHS) - 1) * gap
        x = (config.WIDTH - total) // 2
        for i, name in enumerate(PATHS):
            rect = pygame.Rect(x + i * (cover_w + gap), 180, cover_w, 300)
            selectable = name == "AVENGERS"
            pygame.draw.rect(surface, RED if selectable else GREY, rect, border_radius=8)
            pygame.draw.rect(surface, GOLD if selectable else INK, rect, width=4, border_radius=8)
            _text(surface, name, 28, CREAM if selectable else INK, center=(rect.centerx, rect.centery))
            _text(surface, "#1", 40, GOLD if selectable else INK, center=(rect.centerx, rect.top + 40))
    else:
        _text(surface, state.name, 72, CREAM, center=(cx, config.HEIGHT // 2 - 40))
        if state is GameState.HUB:
            roster = ", ".join(c["name"] for c in app.content["characters"].values()
                               if c["recruit"]["method"] == "starter")
            _text(surface, f"Avengers Tower — roster: {roster}", 30, GOLD,
                  center=(cx, config.HEIGHT // 2 + 30))

    _text(surface, HINTS[state], 30, CREAM, center=(cx, config.HEIGHT - 60))
    _text(surface, f"{app.fps:.0f} fps", 24, GOLD, topleft=(12, 10))
