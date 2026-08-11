"""Shared drawing helpers, pixel-style (spec §9 M7). Rendering only.

Thin wrappers over game.ui.pixelkit that keep the color-constant and
function API the scene code uses.
"""

import pygame

from game.ui import pixelkit

NAVY = pixelkit.color("navy")
CREAM = pixelkit.color("cream")
RED = pixelkit.color("red")
GOLD = pixelkit.color("gold")
INK = pixelkit.color("ink")
GREY = pixelkit.color("grey")
GREEN = pixelkit.color("green")
BLUE = pixelkit.color("sky")
WHITE = pixelkit.color("white")

font = pixelkit.font
text = pixelkit.text


def bar(surface, rect, fraction, fg, label=None):
    pixelkit.bar(surface, rect, fraction, fg,
                 label=label if rect.height >= 9 else None)
    if label and rect.height < 9:
        pixelkit.text(surface, label, 11, "white", center=rect.center, shadow="ink")


def menu(surface, rect, options, selected_index, disabled=()):
    """options: list of strings; pixel comic panel with cursor selection."""
    pixelkit.panel(surface, rect, fill="navy", border="ink")
    row_h = rect.height // max(1, len(options))
    for i, label in enumerate(options):
        row = pygame.Rect(rect.x, rect.y + i * row_h, rect.width, row_h)
        if i == selected_index:
            hl = row.inflate(-6, -4)
            pygame.draw.rect(surface, RED, hl)
            pygame.draw.rect(surface, INK, hl, width=1)
            pixelkit.cursor(surface, (row.x + 6, row.centery))
        color = "grey" if label in disabled else "white"
        pixelkit.text(surface, label, 15, color,
                      midleft=(row.x + 14, row.centery), shadow="ink")
