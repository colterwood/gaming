"""Pause screen styled as a 1991 Impel Marvel card back (spec §8, pixel
edition per §9 M7). Zone sizes are the §8 values halved to internal-res px.

Palette anchored to the reference scans in assets/reference/; trained ranks
overlay in gold (a game addition), foil sparkle when Mastered.
Rendering + input only.
"""

import pygame

from game import config
from game.core import calendar as cal
from game.core import save
from game.core.state_machine import GameState
from game.hub import activities, dispatch
from game.progression import attributes as attrs
from game.social import bonds
from game.ui import binder, pixelkit, sprites

TABS = ("Inventory", "Attributes", "Social", "Collections", "Tasks", "Map", "Options")

CREAM = "cream"
PAPER = "paper"
YELLOW = "yellow"
BLUE = "blue"
PINK = "pink"
RED = "red"
INK = "ink"
GOLD = "gold"
GREY = "grey_dark"


def btext(surface, *args, **kwargs):
    kwargs.setdefault("bold", True)
    return pixelkit.text(surface, *args, **kwargs)


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
        surface.fill(pixelkit.color("shadow"))
        m = config.CARD_MARGIN
        card = pygame.Rect(m, m + 16, config.WIDTH - 2 * m, config.HEIGHT - 2 * m - 16)

        self._draw_tab_strip(surface, pygame.Rect(m, 2, card.width, 16))

        pixelkit.panel(surface, card, fill=CREAM, border=INK, shadow=False)
        pygame.draw.rect(surface, pixelkit.color(RED), card.inflate(-6, -6), width=1)
        self._halftone(surface, card)

        hero_id = self._hero(state)
        header = pygame.Rect(card.x + 10, card.y + 8, card.width - 20,
                             config.CARD_HEADER_HEIGHT)
        pygame.draw.rect(surface, pixelkit.color(YELLOW), header)
        pygame.draw.rect(surface, pixelkit.color(INK), header, width=1)
        hero = self.content["characters"][hero_id] if hero_id else None
        title = hero["name"].upper() if hero else "ROADS TO SECRET WARS"
        btext(surface, title, 26, BLUE, midleft=(header.x + 10, header.centery))
        btext(surface, f"#{app.SAVE_SLOT:02d}", 20, INK,
              topright=(header.right - 8, header.y + 8))

        body = pygame.Rect(card.x + 10, header.bottom + 6, card.width - 20,
                           card.bottom - header.bottom - 34)
        tab = TABS[self.tab_index]
        if tab == "Collections":
            binder.draw_page(surface, body, self.content, state)
        else:
            self._draw_portrait(surface, body, hero)
            if hero:
                self._draw_power_grid(surface, body, state, hero)
            panel = pygame.Rect(body.x, body.y + 180, body.width, body.height - 180)
            self._draw_lower_panel(surface, panel, app, tab)

        footer = f"No. {app.SAVE_SLOT:03d}  -  Issue {state['issue']}, Day {state['day']}"
        btext(surface, footer, 13, INK, center=(card.centerx, card.bottom - 11))
        pixelkit.text(surface, "Arrows: tab/hero  Esc: resume", 11, GREY,
                      topright=(card.right - 10, card.bottom - 15))

    def _draw_tab_strip(self, surface, strip):
        tab_w = strip.width // len(TABS)
        for i, name in enumerate(TABS):
            rect = pygame.Rect(strip.x + i * tab_w, strip.y, tab_w - 3, strip.height)
            greyed = name == "Map"
            selected = i == self.tab_index
            bg = RED if selected else ("steel_dark" if greyed else INK)
            pygame.draw.rect(surface, pixelkit.color(bg), rect)
            if selected:
                pygame.draw.rect(surface, pixelkit.color(GOLD), rect, width=1)
            pixelkit.text(surface, name, 13, "grey" if greyed else "white",
                          center=rect.center)

    def _halftone(self, surface, card):
        overlay = pygame.Surface(card.size, pygame.SRCALPHA)
        dot = pygame.Color(0, 0, 0, 16)
        for y in range(4, card.height - 4, 7):
            offset = 3 if (y // 7) % 2 else 0
            for x in range(4 + offset, card.width - 4, 7):
                overlay.set_at((x, y), dot)
        surface.blit(overlay, card.topleft)

    def _draw_portrait(self, surface, body, hero):
        w, h = config.CARD_PORTRAIT_SIZE
        frame = pygame.Rect(body.x, body.y, w, h)
        pygame.draw.rect(surface, pixelkit.color(RED), frame)
        pygame.draw.rect(surface, pixelkit.color(INK), frame, width=1)
        inner = frame.inflate(-12, -12)
        inner.height -= 18
        pygame.draw.rect(surface, pixelkit.color("navy"), inner)
        pygame.draw.rect(surface, pixelkit.color(INK), inner, width=1)
        if hero:
            big = pygame.transform.scale(sprites.portrait(hero["id"], size=24),
                                         (120, 120))
            surface.blit(big, (inner.centerx - 60, inner.centery - 60))
            name_box = pygame.Rect(frame.x + 12, frame.bottom - 22, frame.width - 24, 14)
            pygame.draw.rect(surface, pixelkit.color(RED), name_box)
            pygame.draw.rect(surface, pixelkit.color(INK), name_box, width=1)
            btext(surface, hero["name"], 13, "white", center=name_box.center,
                  shadow="maroon")

    def _draw_power_grid(self, surface, body, state, hero):
        grid = pygame.Rect(body.x + config.CARD_PORTRAIT_SIZE[0] + 12, body.y,
                           body.width - config.CARD_PORTRAIT_SIZE[0] - 12,
                           config.CARD_GRID_ROW_HEIGHT * 6 + 20)
        paper = pygame.Rect(grid.x, grid.y + 10, grid.width,
                            config.CARD_GRID_ROW_HEIGHT * 6)
        pygame.draw.rect(surface, pixelkit.color(PAPER), paper)
        pygame.draw.rect(surface, pixelkit.color(INK), paper, width=1)

        entry = state["roster"].get(hero["id"], {})
        unit = paper.width / (config.RANK_MAX + 1)
        for n in range(config.RANK_MAX + 1):
            x = int(paper.x + n * unit)
            pixelkit.text(surface, str(n), 11, INK,
                          center=(x + int(unit) // 2, grid.y + 5))
            if n > 0:
                pygame.draw.line(surface, pixelkit.color("grey"),
                                 (x, paper.y), (x, paper.bottom - 1))

        mastered = entry.get("mastered", False)
        for i, attribute in enumerate(config.ATTRIBUTES):
            row_y = paper.y + i * config.CARD_GRID_ROW_HEIGHT
            row = pygame.Rect(paper.x, row_y, paper.width, config.CARD_GRID_ROW_HEIGHT)
            base = hero["power_grid"][attribute]
            trained = entry.get("trained_ranks", {}).get(attribute, 0)
            effective = min(config.RANK_MAX, base + trained)
            bar = pygame.Rect(row.x + 1, row.y + 4,
                              int((base + 1) * unit) - 2, row.height - 8)
            pygame.draw.rect(surface, pixelkit.color(PINK), bar)
            pygame.draw.line(surface, pixelkit.color("white"),
                             (bar.x, bar.y), (bar.right - 1, bar.y))
            if effective > base:
                overlay = pygame.Rect(row.x + int((base + 1) * unit), row.y + 4,
                                      int((effective - base) * unit) - 1, row.height - 8)
                pygame.draw.rect(surface, pixelkit.color(GOLD), overlay)
            btext(surface, attribute.upper(), 13, INK,
                  midleft=(row.x + 5, row.centery))
            if mastered:
                self._foil_sparkle(surface, row, hero["id"], i)

        band = pygame.Rect(paper.x, paper.bottom + 3, paper.width, 16)
        pygame.draw.rect(surface, pixelkit.color(INK), band)
        label = "POWER RATINGS" + ("  * MASTERED *" if mastered else "")
        btext(surface, label, 15, GOLD if mastered else "white", center=band.center)

    def _foil_sparkle(self, surface, row, hero_id, row_index):
        seed = sum(ord(c) for c in hero_id) + row_index * 31
        for k in range(5):
            x = row.x + ((seed * (k + 3) * 97) % max(1, row.width - 8)) + 4
            y = row.y + ((seed * (k + 7) * 53) % max(1, row.height - 8)) + 4
            pygame.draw.line(surface, pixelkit.color("white"), (x - 2, y), (x + 2, y))
            pygame.draw.line(surface, pixelkit.color("white"), (x, y - 2), (x, y + 2))

    # --- lower panel per tab ---

    def _draw_lower_panel(self, surface, panel, app, tab):
        state = app.game_state
        pygame.draw.rect(surface, pixelkit.color(PAPER), panel)
        pygame.draw.rect(surface, pixelkit.color(INK), panel, width=1)
        pad = 8
        surface.set_clip(panel.inflate(-2, -2))
        if tab == "Inventory":
            items = [(iid, n) for iid, n in sorted(state["inventory"].items()) if n > 0]
            extra = f"  (+{len(items) - 10} more)" if len(items) > 10 else ""
            btext(surface, f"Inventory - {state['credits']} credits{extra}", 13, INK,
                  topleft=(panel.x + pad, panel.y + 5))
            slot_w, slot_h = 116, 20
            for i, (iid, n) in enumerate(items[:10]):
                row, col = divmod(i, 5)
                slot = pygame.Rect(panel.x + pad + col * (slot_w + 4),
                                   panel.y + 21 + row * (slot_h + 3), slot_w, slot_h)
                pygame.draw.rect(surface, pixelkit.color(CREAM), slot)
                pygame.draw.rect(surface, pixelkit.color(INK), slot, width=1)
                surface.blit(sprites.icon(iid), (slot.x + 3, slot.y + 4))
                name = self.content["items"].get(iid, {}).get("name", iid)
                pixelkit.text(surface, f"{name[:14]} x{n}", 11, INK,
                              midleft=(slot.x + 18, slot.centery))
            if not items:
                pixelkit.text(surface, "(empty - visit the Tower Shop)", 13, GREY,
                              topleft=(panel.x + pad, panel.y + 24))
        elif tab == "Attributes":
            hero_id = self._hero(state)
            entry = state["roster"].get(hero_id, {})
            chosen = sorted(entry.get("perk_choices", {}).items())
            extra = f"  (+{len(chosen) - 6} more)" if len(chosen) > 6 else ""
            btext(surface, f"Chosen perks:{extra}", 13, INK,
                  topleft=(panel.x + pad, panel.y + 5))
            if chosen:
                by_id = {p["id"]: p for a in self.content["perks"].values()
                         for t in a.values() for p in t}
                col_w = (panel.width - 2 * pad) // 2
                shown = 0
                for slot_key, pid in chosen:
                    perk = by_id.get(pid)
                    if perk is None:
                        continue
                    if shown >= 6:
                        break
                    row, col = divmod(shown, 2)
                    attribute, tier = slot_key.split(":")
                    pixelkit.text(
                        surface,
                        f"{attribute.title()} {tier}: {perk['name']} ({perk['blurb']})",
                        11, INK, topleft=(panel.x + pad + col * col_w,
                                          panel.y + 20 + row * 12))
                    shown += 1
            else:
                pixelkit.text(surface, "(none yet - train to rank 3)", 12, GREY,
                              topleft=(panel.x + pad + 6, panel.y + 21))
            banked = entry.get("attribute_xp", {})
            summary = "  ".join(f"{a[:3].upper()} {banked.get(a, 0)}"
                                for a in config.ATTRIBUTES)
            pixelkit.text(surface, "Banked XP:  " + summary, 11, INK,
                          topleft=(panel.x + pad, panel.bottom - 14))
        elif tab == "Social":
            y = panel.y + 6
            names = sorted(c["id"] for c in self.content["characters"].values()
                           if bonds.bondable(c))
            shown = 0
            for char_id in names:
                if shown >= 4:
                    continue
                char = self.content["characters"][char_id]
                bond = bonds.ensure_bond(state, char_id)
                level = bonds.bond_level(bond["points"])
                birthday = char["birthday"]
                pixelkit.text(surface,
                              f"{char['name']} - Bond {level} ({bond['points']} pts)  "
                              f"bday I{birthday['issue']} D{birthday['day']}",
                              12, INK, topleft=(panel.x + pad, y))
                into = bond["points"] - level * config.BOND_POINTS_PER_LEVEL
                frac = 1.0 if level >= config.BOND_LEVEL_MAX else into / config.BOND_POINTS_PER_LEVEL
                bar = pygame.Rect(panel.right - pad - 140, y + 1, 140, 7)
                pygame.draw.rect(surface, pixelkit.color(CREAM), bar)
                pygame.draw.rect(surface, pixelkit.color(PINK),
                                 pygame.Rect(bar.x, bar.y, max(1, int(bar.width * frac)),
                                             bar.height))
                pygame.draw.rect(surface, pixelkit.color(INK), bar, width=1)
                y += 19
                shown += 1
        elif tab == "Tasks":
            half = panel.width // 2
            tier = dispatch.roster_tier(self.content, state)
            btext(surface, f"Board (today) - Tier {tier}", 13, INK,
                  topleft=(panel.x + pad, panel.y + 5))
            y = panel.y + 20
            today = activities.assignment_tasks_today(
                state, self.content["assignments"], tier)
            for task in today:
                job = dispatch.find(state, task["id"])
                mark = "[>]" if job else "[ ]"
                heroes, days = task["heroes"], task["days"]
                crew = (f"{heroes} Hero{'es' if heroes != 1 else ''} / "
                        f"{days} Day{'s' if days != 1 else ''}")
                line = f"{mark} {task['name']} - {task['credits']}cr"
                line += (f" (back in {job['days_left']}d)" if job
                         else f" ({crew})")
                pixelkit.text(surface, line, 11, GREY if job else INK,
                              topleft=(panel.x + pad, y))
                y += 13
            for job in dispatch.active(state):
                if any(t["id"] == job["task_id"] for t in today):
                    continue        # already shown above
                names = ", ".join(self.content["characters"][h]["name"]
                                  for h in job["heroes"])
                pixelkit.text(surface, f"[>] {job['name']}: {names} - "
                              f"{job['days_left']}d left", 11, GREY,
                              topleft=(panel.x + pad, y))
                y += 13
            qx = panel.x + half + pad
            btext(surface, "Quests", 13, INK, topleft=(qx, panel.y + 5))
            quests = sorted(state.get("quests", {}).items())
            if quests:
                col_w = (half - 2 * pad) // 2
                for i, (qid, q) in enumerate(quests[:8]):
                    col, row = divmod(i, 4)
                    done = q.get("status") == "done"
                    mark = "[x]" if done else "[>]"
                    pixelkit.text(surface, f"{mark} {q.get('name', qid)}", 11,
                                  GREY if done else INK,
                                  topleft=(qx + col * col_w, panel.y + 20 + row * 12))
            else:
                pixelkit.text(surface, "(no active quests)", 11, GREY,
                              topleft=(qx, panel.y + 20))
        elif tab == "Map":
            btext(surface, "WORLD MAP - coming in a later issue", 15, GREY,
                  center=panel.center)
        elif tab == "Options":
            btext(surface, "Enter: save game", 14, INK,
                  topleft=(panel.x + pad, panel.y + 7))
            for ev in cal.active_events(state, self.content["calendar"]):
                pixelkit.text(surface, f"Active event: {ev['name']}", 12, RED,
                              topleft=(panel.x + pad, panel.y + 25))
            if self.message:
                pixelkit.text(surface, self.message, 13, RED,
                              topleft=(panel.x + pad, panel.y + 42))
        surface.set_clip(None)
