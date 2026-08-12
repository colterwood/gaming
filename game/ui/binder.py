"""9-pocket binder page for the Collections tab (spec §8, pixel edition).
Filled pockets show mini card fronts with pixel portraits; empty pockets are
grey slots with silhouettes. NPCs don't occupy pockets. Rendering only."""

import pygame

from game.ui import pixelkit, sprites


def _hero_color(hero_id):
    h = sum(ord(c) * (i + 7) for i, c in enumerate(hero_id)) + len(hero_id)
    palette = ["red_dark", "blue_dark", "purple", "green_dark", "gold_dark", "maroon"]
    return palette[h % len(palette)]


def draw_page(surface, rect, content, state):
    """Draw the 3x3 pocket grid inside rect."""
    pygame.draw.rect(surface, pixelkit.color("navy"), rect)
    pygame.draw.rect(surface, pixelkit.color("ink"), rect, width=2)

    pool = sorted(c["id"] for c in content["characters"].values()
                  if c["path"] == state.get("path", "avengers")
                  and c["recruit"]["method"] != "npc")
    roster = state.get("roster", {})

    gap = 8
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
            # An empty pocket stays ANONYMOUS on purpose: the page shows
            # that someone is missing, never who. Finding out who fills a
            # slot is the game — and once the Ch. 3-4 fork exists, naming
            # the recruit you didn't take would spoil the road not taken.
            _draw_empty_pocket(surface, pocket)


def _draw_mini_front(surface, pocket, character, entry):
    pygame.draw.rect(surface, pixelkit.color(_hero_color(character["id"])), pocket)
    border = "gold" if entry.get("mastered") else "yellow"
    pygame.draw.rect(surface, pixelkit.color(border), pocket, width=2)
    name_band = pygame.Rect(pocket.x + 3, pocket.y + 3, pocket.width - 6, 13)
    pygame.draw.rect(surface, pixelkit.color("yellow"), name_band)
    pixelkit.text(surface, character["name"], 12, "blue", bold=True,
                  center=name_band.center)
    size = min(48, pocket.height - 34)
    big = pygame.transform.scale(sprites.portrait(character["id"]), (size, size))
    surface.blit(big, (pocket.centerx - size // 2, pocket.y + 18))
    pixelkit.text(surface, character["rarity"].upper(), 10, "cream",
                  center=(pocket.centerx, pocket.bottom - 8))
    if entry.get("mastered"):
        pixelkit.text(surface, "FOIL", 10, "gold", bold=True,
                      topleft=(pocket.x + 5, pocket.bottom - 12))


def _draw_empty_pocket(surface, pocket):
    pygame.draw.rect(surface, pixelkit.color("steel_dark"), pocket)
    pygame.draw.rect(surface, pixelkit.color("grey_dark"), pocket, width=1)
    cx, cy = pocket.centerx, pocket.centery
    pygame.draw.circle(surface, pixelkit.color("shadow"), (cx, cy - 8), 9)
    pygame.draw.ellipse(surface, pixelkit.color("shadow"),
                        pygame.Rect(cx - 15, cy + 2, 30, 18))
    pixelkit.text(surface, "?", 14, "grey", bold=True,
                  center=(cx, pocket.bottom - 10))
