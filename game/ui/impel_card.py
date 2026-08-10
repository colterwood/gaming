"""Pause screen styled as a 1991 Impel Marvel card back (spec §8).

Layout and palette follow the reference scans in assets/reference/
(cap_54_back.jpg, iron_man_13_back.jpg, hulk_53_back.jpg): cream body,
yellow header banner with blue block lettering, pink 0-7 power-rating bars,
black POWER RATINGS band, red accent strip. Trained ranks overlay in gold
(a game addition), foil sparkle when Mastered. Rendering + input only.
"""

import pygame

from game import config
from game.core import calendar as cal
from game.core import save
from game.core.state_machine import GameState
from game.hub import activities
from game.progression import attributes as attrs
from game.social import bonds
from game.ui import binder, widgets

TABS = ("Inventory", "Attributes", "Social", "Collections", "Tasks", "Map", "Options")

CREAM = pygame.Color(config.CARD_PALETTE["cream"])
PAPER = pygame.Color(config.CARD_PALETTE["paper"])
YELLOW = pygame.Color(config.CARD_PALETTE["yellow"])
BLUE = pygame.Color(config.CARD_PALETTE["blue"])
BAR_PINK = pygame.Color(config.CARD_PALETTE["bar_pink"])
RED = pygame.Color(config.CARD_PALETTE["red"])
INK = pygame.Color(config.CARD_PALETTE["ink"])
GOLD = pygame.Color(config.CARD_PALETTE["gold"])
GREY = pygame.Color(120, 116, 108)

_bold_fonts = {}


def bold_font(size):
    if size not in _bold_fonts:
        f = pygame.font.Font(None, size)
        f.set_bold(True)
        _bold_fonts[size] = f
    return _bold_fonts[size]


def btext(surface, txt, size, color, center=None, topleft=None, midleft=None, topright=None):
    img = bold_font(size).render(txt, True, color)
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


class ImpelCardScene:
    def __init__(self, content):
        self.content = content
        self.tab_index = 0
        self.hero_index = 0
        self.message = ""

    # --- helpers ---

    def _hero_ids(self, state):
        return sorted(state.get("roster", {}))

    def _hero(self, state):
        ids = self._hero_ids(state)
        return ids[self.hero_index % len(ids)] if ids else None

    # --- input ---

    def handle_key(self, app, key):
        state = app.game_state
        if key == pygame.K_ESCAPE:
            self.message = ""
            app.machine.transition(GameState.HUB)
        elif key == pygame.K_LEFT:
            self.tab_index = (self.tab_index - 1) % len(TABS)
            self.message = ""
        elif key == pygame.K_RIGHT:
            self.tab_index = (self.tab_index + 1) % len(TABS)
            self.message = ""
        elif key in (pygame.K_UP, pygame.K_DOWN):
            step = -1 if key == pygame.K_UP else 1
            ids = self._hero_ids(state)
            if ids:
                self.hero_index = (self.hero_index + step) % len(ids)
        elif key == pygame.K_RETURN and TABS[self.tab_index] == "Options":
            save.save_game(state, app.SAVE_SLOT)
            self.message = f"Saved to slot {app.SAVE_SLOT}."

    # --- drawing ---

    def draw(self, surface, app):
        state = app.game_state
        surface.fill(pygame.Color(24, 24, 28))
        m = config.CARD_MARGIN
        card = pygame.Rect(m, m + 36, config.WIDTH - 2 * m, config.HEIGHT - 2 * m - 36)

        self._draw_tab_strip(surface, pygame.Rect(m, 4, card.width, 34))

        pygame.draw.rect(surface, CREAM, card, border_radius=14)
        pygame.draw.rect(surface, INK, card, width=3, border_radius=14)
        pygame.draw.rect(surface, RED, card.inflate(-10, -10), width=2, border_radius=10)
        self._halftone(surface, card)

        hero_id = self._hero(state)
        header = pygame.Rect(card.x + 18, card.y + 14, card.width - 36,
                             config.CARD_HEADER_HEIGHT)
        pygame.draw.rect(surface, YELLOW, header, border_radius=6)
        pygame.draw.rect(surface, INK, header, width=2, border_radius=6)
        hero = self.content["characters"][hero_id] if hero_id else None
        title = hero["name"].upper() if hero else "ROADS TO SECRET WARS"
        btext(surface, title, 52, BLUE, midleft=(header.x + 22, header.centery))
        btext(surface, f"#{app.SAVE_SLOT:02d}", 40, INK,
              topright=(header.right - 18, header.y + 16))

        body = pygame.Rect(card.x + 18, header.bottom + 12, card.width - 36,
                           card.bottom - header.bottom - 64)
        tab = TABS[self.tab_index]
        if tab == "Collections":
            binder.draw_page(surface, body, self.content, state)
        else:
            self._draw_portrait(surface, body, hero)
            if hero:
                self._draw_power_grid(surface, body, state, hero)
            panel = pygame.Rect(body.x, body.y + 356, body.width, body.height - 356)
            self._draw_lower_panel(surface, panel, app, tab)

        footer = f"No. {app.SAVE_SLOT:03d}  —  Issue {state['issue']}, Day {state['day']}"
        btext(surface, footer, 26, INK, center=(card.centerx, card.bottom - 24))
        btext(surface, "Arrows: tab/hero   Esc: resume", 22, GREY,
              topright=(card.right - 20, card.bottom - 34))

    def _draw_tab_strip(self, surface, strip):
        tab_w = strip.width // len(TABS)
        for i, name in enumerate(TABS):
            rect = pygame.Rect(strip.x + i * tab_w, strip.y, tab_w - 6, strip.height)
            greyed = name == "Map"
            selected = i == self.tab_index
            bg = RED if selected else (pygame.Color(70, 70, 76) if greyed else INK)
            pygame.draw.rect(surface, bg, rect, border_radius=6)
            color = CREAM if not greyed else GREY
            btext(surface, name, 24, color, center=rect.center)

    def _halftone(self, surface, card):
        dot = pygame.Color(0, 0, 0, 14)
        overlay = pygame.Surface(card.size, pygame.SRCALPHA)
        for y in range(8, card.height - 8, 14):
            offset = 7 if (y // 14) % 2 else 0
            for x in range(8 + offset, card.width - 8, 14):
                pygame.draw.circle(overlay, dot, (x, y), 2)
        surface.blit(overlay, card.topleft)

    def _draw_portrait(self, surface, body, hero):
        w, h = config.CARD_PORTRAIT_SIZE
        frame = pygame.Rect(body.x, body.y, w, h)
        pygame.draw.rect(surface, RED, frame, border_radius=6)
        inner = frame.inflate(-16, -16)
        color = binder._hero_color(hero["id"]) if hero else (90, 90, 100)
        pygame.draw.rect(surface, pygame.Color(*color), inner, border_radius=4)
        if hero:
            initials = "".join(word[0] for word in hero["name"].split()[:2])
            btext(surface, initials, 120, CREAM, center=inner.center)
            name_box = pygame.Rect(frame.x + 24, frame.bottom - 44, frame.width - 48, 32)
            pygame.draw.rect(surface, RED, name_box)
            pygame.draw.rect(surface, INK, name_box, width=2)
            btext(surface, hero["name"], 24, CREAM, center=name_box.center)

    def _draw_power_grid(self, surface, body, state, hero):
        grid = pygame.Rect(body.x + config.CARD_PORTRAIT_SIZE[0] + 24, body.y,
                           body.width - config.CARD_PORTRAIT_SIZE[0] - 24,
                           config.CARD_GRID_ROW_HEIGHT * 6 + 40)
        paper = pygame.Rect(grid.x, grid.y + 20, grid.width,
                            config.CARD_GRID_ROW_HEIGHT * 6)
        pygame.draw.rect(surface, PAPER, paper)
        pygame.draw.rect(surface, INK, paper, width=2)

        entry = state["roster"].get(hero["id"], {})
        unit = paper.width / (config.RANK_MAX + 1)
        # 0..7 tick numbers + vertical gridlines, like the printed card
        for n in range(config.RANK_MAX + 1):
            x = int(paper.x + n * unit)
            btext(surface, str(n), 20, INK, center=(x + int(unit) // 2, grid.y + 10))
            if n > 0:
                pygame.draw.line(surface, pygame.Color(150, 150, 150),
                                 (x, paper.y), (x, paper.bottom))

        mastered = entry.get("mastered", False)
        for i, attribute in enumerate(config.ATTRIBUTES):
            row_y = paper.y + i * config.CARD_GRID_ROW_HEIGHT
            row = pygame.Rect(paper.x, row_y, paper.width, config.CARD_GRID_ROW_HEIGHT)
            base = hero["power_grid"][attribute]
            trained = entry.get("trained_ranks", {}).get(attribute, 0)
            effective = min(config.RANK_MAX, base + trained)
            bar = pygame.Rect(row.x + 2, row.y + 8,
                              int((base + 1) * unit) - 4, row.height - 16)
            pygame.draw.rect(surface, BAR_PINK, bar)
            if effective > base:
                overlay = pygame.Rect(row.x + int((base + 1) * unit), row.y + 8,
                                      int((effective - base) * unit) - 2, row.height - 16)
                pygame.draw.rect(surface, GOLD, overlay)
            btext(surface, attribute.upper(), 26, INK,
                  midleft=(row.x + 10, row.centery))
            if mastered:
                self._foil_sparkle(surface, row, hero["id"], i)

        band = pygame.Rect(paper.x, paper.bottom + 6, paper.width, 34)
        pygame.draw.rect(surface, INK, band)
        label = "POWER RATINGS" + ("  * MASTERED *" if mastered else "")
        btext(surface, label, 30, GOLD if mastered else CREAM, center=band.center)

    def _foil_sparkle(self, surface, row, hero_id, row_index):
        """Static sparkle overlay (POC foil treatment)."""
        seed = sum(ord(c) for c in hero_id) + row_index * 31
        for k in range(6):
            x = row.x + ((seed * (k + 3) * 97) % max(1, row.width - 12)) + 6
            y = row.y + ((seed * (k + 7) * 53) % max(1, row.height - 12)) + 6
            pygame.draw.line(surface, pygame.Color(255, 255, 255), (x - 4, y), (x + 4, y), 1)
            pygame.draw.line(surface, pygame.Color(255, 255, 255), (x, y - 4), (x, y + 4), 1)

    # --- lower panel per tab ---

    def _draw_lower_panel(self, surface, panel, app, tab):
        state = app.game_state
        pygame.draw.rect(surface, PAPER, panel, border_radius=6)
        pygame.draw.rect(surface, INK, panel, width=2, border_radius=6)
        pad = 14
        if tab == "Inventory":
            items = [(iid, n) for iid, n in sorted(state["inventory"].items()) if n > 0]
            btext(surface, f"Inventory — {state['credits']} credits", 28, INK,
                  topleft=(panel.x + pad, panel.y + 10))
            slot_w, slot_h = 214, 44
            for i, (iid, n) in enumerate(items[:15]):
                row, col = divmod(i, 5)
                slot = pygame.Rect(panel.x + pad + col * (slot_w + 8),
                                   panel.y + 44 + row * (slot_h + 8), slot_w, slot_h)
                pygame.draw.rect(surface, CREAM, slot, border_radius=4)
                pygame.draw.rect(surface, INK, slot, width=1, border_radius=4)
                name = self.content["items"].get(iid, {}).get("name", iid)
                btext(surface, f"{name} x{n}", 22, INK,
                      midleft=(slot.x + 8, slot.centery))
            if not items:
                btext(surface, "(empty — visit the Tower Shop)", 26, GREY,
                      topleft=(panel.x + pad, panel.y + 48))
        elif tab == "Attributes":
            hero_id = self._hero(state)
            entry = state["roster"].get(hero_id, {})
            btext(surface, "Chosen perks:", 26, INK, topleft=(panel.x + pad, panel.y + 10))
            chosen = entry.get("perk_choices", {})
            if chosen:
                by_id = {p["id"]: p for a in self.content["perks"].values()
                         for t in a.values() for p in t}
                for i, (slot_key, pid) in enumerate(sorted(chosen.items())):
                    perk = by_id[pid]
                    attribute, tier = slot_key.split(":")
                    btext(surface, f"{attribute.title()} {tier}: {perk['name']} ({perk['blurb']})",
                          24, INK, topleft=(panel.x + pad + 12, panel.y + 42 + i * 28))
            else:
                btext(surface, "(none yet — train to rank 3)", 24, GREY,
                      topleft=(panel.x + pad + 12, panel.y + 42))
            banked = entry.get("attribute_xp", {})
            summary = "   ".join(f"{a[:3].upper()} {banked.get(a, 0)}xp"
                                 for a in config.ATTRIBUTES)
            btext(surface, "Banked XP:  " + summary, 22, INK,
                  topleft=(panel.x + pad, panel.bottom - 34))
        elif tab == "Social":
            btext(surface, "Bonds", 28, INK, topleft=(panel.x + pad, panel.y + 10))
            y = panel.y + 44
            for char_id in sorted(state.get("roster", {})):
                char = self.content["characters"][char_id]
                bond = bonds.ensure_bond(state, char_id)
                level = bonds.bond_level(bond["points"])
                birthday = char["birthday"]
                btext(surface, f"{char['name']} — Bond {level}  "
                      f"({bond['points']} pts)   birthday: Issue {birthday['issue']} "
                      f"Day {birthday['day']}", 24, INK, topleft=(panel.x + pad, y))
                into = bond["points"] - level * config.BOND_POINTS_PER_LEVEL
                frac = 1.0 if level >= config.BOND_LEVEL_MAX else into / config.BOND_POINTS_PER_LEVEL
                bar = pygame.Rect(panel.x + pad, y + 26, 300, 8)
                pygame.draw.rect(surface, CREAM, bar)
                pygame.draw.rect(surface, BAR_PINK,
                                 pygame.Rect(bar.x, bar.y, int(bar.width * frac), bar.height))
                pygame.draw.rect(surface, INK, bar, width=1)
                y += 46
        elif tab == "Tasks":
            btext(surface, "Assignment Board (today)", 28, INK,
                  topleft=(panel.x + pad, panel.y + 10))
            y = panel.y + 44
            for task in activities.assignment_tasks_today(state, self.content["assignments"]):
                done = task["id"] in state.get("assignments_done", [])
                mark = "[x]" if done else "[ ]"
                btext(surface, f"{mark} {task['name']} — {task['credits']} cr", 24,
                      GREY if done else INK, topleft=(panel.x + pad, y))
                y += 30
            quests = state.get("quests", {})
            btext(surface, "Quests", 28, INK, topleft=(panel.x + pad, y + 8))
            y += 42
            if quests:
                for qid, q in sorted(quests.items()):
                    btext(surface, f"- {q.get('name', qid)}: {q.get('status', '?')}", 24,
                          INK, topleft=(panel.x + pad, y))
                    y += 28
            else:
                btext(surface, "(no active quests)", 24, GREY,
                      topleft=(panel.x + pad, y))
        elif tab == "Map":
            btext(surface, "WORLD MAP — coming in a later issue", 32, GREY,
                  center=panel.center)
        elif tab == "Options":
            btext(surface, "Enter: save game", 28, INK,
                  topleft=(panel.x + pad, panel.y + 14))
            for ev in cal.active_events(state, self.content["calendar"]):
                btext(surface, f"Active event: {ev['name']}", 24, RED,
                      topleft=(panel.x + pad, panel.y + 50))
            if self.message:
                btext(surface, self.message, 26, RED, topleft=(panel.x + pad, panel.y + 84))
