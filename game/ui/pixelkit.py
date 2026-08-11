"""16-bit pixel UI kit (spec §9 M7). Rendering only.

Everything draws in internal-resolution coordinates with colors from
config.PIXEL_PALETTE, no anti-aliasing. The window scale-up happens once
per frame in __main__.
"""

import pygame

from game import config

_colors = {}
_fonts = {}
_sprite_cache = {}


def color(name):
    if name not in _colors:
        _colors[name] = pygame.Color(config.PIXEL_PALETTE[name])
    return _colors[name]


def font(size, bold=False):
    key = (size, bold)
    if key not in _fonts:
        f = pygame.font.Font(None, size)
        f.set_bold(bold)
        _fonts[key] = f
    return _fonts[key]


def _resolve(c):
    return color(c) if isinstance(c, str) else c


def text(surface, txt, size, c, center=None, topleft=None, midleft=None,
         topright=None, bold=False, shadow=None):
    """Non-anti-aliased text; optional 1px drop shadow color name."""
    img = font(size, bold).render(txt, False, _resolve(c))
    rect = img.get_rect()
    if center:
        rect.center = center
    elif topleft:
        rect.topleft = topleft
    elif midleft:
        rect.midleft = midleft
    elif topright:
        rect.topright = topright
    if shadow:
        sh = font(size, bold).render(txt, False, _resolve(shadow))
        surface.blit(sh, (rect.x + 1, rect.y + 1))
    surface.blit(img, rect)
    return rect


def panel(surface, rect, fill="paper", border="ink", shadow=True):
    """Comic-panel frame: drop shadow, fill, 2px border, snipped corners."""
    if shadow:
        pygame.draw.rect(surface, color("shadow"), rect.move(2, 2))
    pygame.draw.rect(surface, _resolve(fill), rect)
    pygame.draw.rect(surface, _resolve(border), rect, width=2)
    for dx, dy in ((0, 0), (rect.width - 1, 0), (0, rect.height - 1),
                   (rect.width - 1, rect.height - 1)):
        surface.set_at((rect.x + dx, rect.y + dy), color("shadow") if shadow
                       else _resolve(border))


def bar(surface, rect, frac, fill, back="shadow", border="ink", label=None,
        label_color="white"):
    frac = max(0.0, min(1.0, frac))
    pygame.draw.rect(surface, _resolve(back), rect)
    if frac > 0:
        w = max(1, int((rect.width - 2) * frac))
        pygame.draw.rect(surface, _resolve(fill),
                         pygame.Rect(rect.x + 1, rect.y + 1, w, rect.height - 2))
        # 1px highlight line for that 16-bit sheen
        if rect.height >= 5:
            pygame.draw.line(surface, color("white"),
                             (rect.x + 1, rect.y + 1), (rect.x + w, rect.y + 1))
    pygame.draw.rect(surface, _resolve(border), rect, width=1)
    if label:
        text(surface, label, 12, label_color, center=rect.center, shadow="ink")


def cursor(surface, pos, c="gold"):
    """Small right-pointing pixel arrow at pos (tip midleft)."""
    x, y = pos
    col = _resolve(c)
    for i in range(4):
        pygame.draw.line(surface, col, (x + i, y - (3 - i)), (x + i, y + (3 - i)))
    pygame.draw.line(surface, color("ink"), (x, y - 3), (x + 3, y))
    pygame.draw.line(surface, color("ink"), (x, y + 3), (x + 3, y))


def checker(surface, rect, c1="navy", c2="shadow", cell=4):
    a, b = _resolve(c1), _resolve(c2)
    for gy in range(rect.y, rect.bottom, cell):
        for gx in range(rect.x, rect.right, cell):
            odd = ((gx - rect.x) // cell + (gy - rect.y) // cell) % 2
            pygame.draw.rect(surface, b if odd else a,
                             pygame.Rect(gx, gy, min(cell, rect.right - gx),
                                         min(cell, rect.bottom - gy)))


def build_sprite(rows, keymap, colorkey=None):
    """Build a Surface from pixel-grid strings.

    rows: list of equal-length strings; each char indexes keymap.
    keymap: char -> palette color name ('.' or ' ' = transparent).
    """
    cache_key = (tuple(rows), tuple(sorted(keymap.items())))
    if cache_key in _sprite_cache:
        return _sprite_cache[cache_key]
    h = len(rows)
    w = max(len(r) for r in rows)
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch in (".", " "):
                continue
            surf.set_at((x, y), color(keymap[ch]))
    _sprite_cache[cache_key] = surf
    return surf
