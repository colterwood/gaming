"""9-pocket binder page for the Collections tab (spec §8). Rendering only.

Filled pockets show mini card fronts for recruited heroes; empty pockets are
grey slots with silhouettes.
"""

import pygame

from game import config
from game.ui import widgets


def _hero_color(hero_id):
    h = sum(ord(c) * (i + 7) for i, c in enumerate(hero_id)) + len(hero_id)
    palette = [(178, 34, 52), (30, 60, 160), (170, 40, 140), (20, 110, 80),
               (190, 120, 20), (90, 50, 130)]
    return palette[h % len(palette)]


def draw_page(surface, rect, content, state):
    """Draw the 3x3 pocket grid inside rect."""
    pygame.draw.rect(surface, pygame.Color(30, 30, 36), rect, border_radius=10)
    pygame.draw.rect(surface, widgets.INK, rect, width=3, border_radius=10)

    pool = sorted(c["id"] for c in content["characters"].values()
                  if c["path"] == state.get("path", "avengers"))
    roster = state.get("roster", {})

    gap = 14
    pocket_w = (rect.width - gap * 4) // 3
    pocket_h = (rect.height - gap * 4) // 3
    for i in range(9):
        row, col = divmod(i, 3)
        pocket = pygame.Rect(rect.x + gap + col * (pocket_w + gap),
                             rect.y + gap + row * (pocket_h + gap),
                             pocket_w, pocket_h)
        hero_id = pool[i] if i < len(pool) else None
        if hero_id and hero_id in roster:
            _draw_mini_front(surface, pocket, content["characters"][hero_id],
                             roster[hero_id])
        else:
            _draw_empty_pocket(surface, pocket)


def _draw_mini_front(surface, pocket, character, entry):
    color = _hero_color(character["id"])
    pygame.draw.rect(surface, pygame.Color(*color), pocket, border_radius=8)
    border = pygame.Color(config.CARD_PALETTE["gold"]) if entry.get("mastered") \
        else pygame.Color(config.CARD_PALETTE["yellow"])
    pygame.draw.rect(surface, border, pocket, width=3, border_radius=8)
    name_band = pygame.Rect(pocket.x + 6, pocket.y + 6, pocket.width - 12, 26)
    pygame.draw.rect(surface, pygame.Color(config.CARD_PALETTE["yellow"]),
                     name_band, border_radius=4)
    widgets.text(surface, character["name"], 22,
                 pygame.Color(config.CARD_PALETTE["blue"]), center=name_band.center)
    initials = "".join(w[0] for w in character["name"].split()[:2])
    widgets.text(surface, initials, 64, pygame.Color(config.CARD_PALETTE["cream"]),
                 center=(pocket.centerx, pocket.centery + 10))
    widgets.text(surface, character["rarity"].upper(), 18,
                 pygame.Color(config.CARD_PALETTE["cream"]),
                 center=(pocket.centerx, pocket.bottom - 16))
    if entry.get("mastered"):
        widgets.text(surface, "FOIL", 18, pygame.Color(config.CARD_PALETTE["gold"]),
                     topleft=(pocket.x + 8, pocket.bottom - 24))


def _draw_empty_pocket(surface, pocket):
    pygame.draw.rect(surface, pygame.Color(58, 58, 64), pocket, border_radius=8)
    pygame.draw.rect(surface, pygame.Color(90, 90, 100), pocket, width=2, border_radius=8)
    # silhouette: head + shoulders
    cx, cy = pocket.centerx, pocket.centery
    pygame.draw.circle(surface, pygame.Color(78, 78, 86), (cx, cy - 18), 20)
    pygame.draw.ellipse(surface, pygame.Color(78, 78, 86),
                        pygame.Rect(cx - 34, cy + 4, 68, 44))
    widgets.text(surface, "?", 30, pygame.Color(110, 110, 120),
                 center=(cx, pocket.bottom - 22))
