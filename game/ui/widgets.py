"""Shared drawing helpers: bars, text, menus. Rendering only."""

import pygame

from game import config

NAVY = pygame.Color(config.PALETTE["navy"])
CREAM = pygame.Color(config.PALETTE["cream"])
RED = pygame.Color(config.PALETTE["red"])
GOLD = pygame.Color(config.PALETTE["gold"])
INK = pygame.Color(config.PALETTE["ink"])
GREY = pygame.Color(90, 90, 100)
GREEN = pygame.Color(70, 160, 90)
BLUE = pygame.Color(70, 110, 200)

_fonts = {}


def font(size):
    if size not in _fonts:
        _fonts[size] = pygame.font.Font(None, size)
    return _fonts[size]


def text(surface, txt, size, color, center=None, topleft=None, midleft=None, topright=None):
    img = font(size).render(txt, True, color)
    rect = img.get_rect()
    if center:
        rect.center = center
    elif topleft:
        rect.topleft = topleft
    elif midleft:
        rect.midleft = midleft
    elif topright:
        rect.topright = topright
    surface.blit(img, rect)
    return rect


def bar(surface, rect, fraction, fg, label=None):
    fraction = max(0.0, min(1.0, fraction))
    pygame.draw.rect(surface, INK, rect, border_radius=4)
    if fraction > 0:
        fill = rect.copy()
        fill.width = max(2, int(rect.width * fraction))
        pygame.draw.rect(surface, fg, fill, border_radius=4)
    pygame.draw.rect(surface, CREAM, rect, width=1, border_radius=4)
    if label:
        text(surface, label, 22, CREAM, center=rect.center)


def menu(surface, rect, options, selected_index, disabled=()):
    """options: list of strings; returns per-row rects."""
    pygame.draw.rect(surface, INK, rect, border_radius=8)
    pygame.draw.rect(surface, GOLD, rect, width=2, border_radius=8)
    row_h = rect.height // max(1, len(options))
    for i, label in enumerate(options):
        row = pygame.Rect(rect.x, rect.y + i * row_h, rect.width, row_h)
        if i == selected_index:
            hl = row.inflate(-8, -6)
            pygame.draw.rect(surface, RED, hl, border_radius=6)
        color = GREY if label in disabled else CREAM
        text(surface, label, 30, color, midleft=(row.x + 24, row.centery))
