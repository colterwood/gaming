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


SCROLLABLE_TABS = ("Social", "Tasks")   # lists that grow with the roster


class ImpelCardScene:
    def __init__(self, content):
        self.content = content
        self.tab_index = 0
        self.hero_index = 0
        self.message = ""
        # M14: Social/Tasks lists scroll independently of hero switching.
        self.scroll = {"Social": 0, "Tasks": 0}

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
            tab = TABS[self.tab_index]
            if tab in SCROLLABLE_TABS:
                # Clamped against the real row count at draw time — here we
                # just track intent so repeated presses keep working.
                self.scroll[tab] = max(0, self.scroll[tab] + step)
            else:
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
        boosts = hero.get("boosts", {})
        for i, attribute in enumerate(config.ATTRIBUTES):
            row_y = paper.y + i * config.CARD_GRID_ROW_HEIGHT
            row = pygame.Rect(paper.x, row_y, paper.width, config.CARD_GRID_ROW_HEIGHT)
            # M15: pink = the trained rank (1..10), gold = what the innate
            # boost adds on top of it in combat.
            rank = attrs.rank(entry, attribute)
            effective = attrs.effective_rank(boosts, entry, attribute)
            bar = pygame.Rect(row.x + 1, row.y + 4,
                              int((rank + 1) * unit) - 2, row.height - 8)
            pygame.draw.rect(surface, pixelkit.color(PINK), bar)
            pygame.draw.line(surface, pixelkit.color("white"),
                             (bar.x, bar.y), (bar.right - 1, bar.y))
            # The grid only has RANK_MAX columns, but a boosted combat value
            # runs past it — clamp the gold band to the paper so it never
            # spills over the card edge.
            shown = min(config.RANK_MAX, effective)
            if shown > rank:
                left = row.x + int((rank + 1) * unit)
                right = min(paper.right - 1, row.x + int((shown + 1) * unit) - 1)
                if right > left:
                    pygame.draw.rect(surface, pixelkit.color(GOLD),
                                     pygame.Rect(left, row.y + 4,
                                                 right - left, row.height - 8))
            btext(surface, attribute.upper(), 12, INK,
                  midleft=(row.x + 5, row.centery))
            boost = boosts.get(attribute, 0)
            if boost:
                pixelkit.text(surface, f"+{boost}", 11, GOLD,
                              midleft=(row.right - 18, row.centery), shadow="ink")
            if mastered:
                self._foil_sparkle(surface, row, hero["id"], i)

        band = pygame.Rect(paper.x, paper.bottom + 3, paper.width, 16)
        pygame.draw.rect(surface, pixelkit.color(INK), band)
        label = ("POWER RATINGS  (gold = innate boost)"
                 + ("  * MASTERED *" if mastered else ""))
        btext(surface, label, 14, GOLD if mastered else "white", center=band.center)

    def _foil_sparkle(self, surface, row, hero_id, row_index):
        seed = sum(ord(c) for c in hero_id) + row_index * 31
        for k in range(5):
            x = row.x + ((seed * (k + 3) * 97) % max(1, row.width - 8)) + 4
            y = row.y + ((seed * (k + 7) * 53) % max(1, row.height - 8)) + 4
            pygame.draw.line(surface, pixelkit.color("white"), (x - 2, y), (x + 2, y))
            pygame.draw.line(surface, pixelkit.color("white"), (x, y - 2), (x, y + 2))

    def _scroll_window(self, tab, total, visible):
        """Clamp the tab's scroll offset against the real row count and
        return (first_index, showing_more_above, showing_more_below)."""
        max_scroll = max(0, total - visible)
        offset = max(0, min(self.scroll[tab], max_scroll))
        self.scroll[tab] = offset
        return offset, offset > 0, offset + visible < total

    @staticmethod
    def _fit(text, max_width, size=11, bold=False):
        """Truncate text with an ellipsis so it never overflows its column."""
        f = pixelkit.font(size, bold)
        if f.size(text)[0] <= max_width:
            return text
        while text and f.size(text + "...")[0] > max_width:
            text = text[:-1]
        return text + "..." if text else "..."

    def _scroll_arrows(self, surface, panel, more_above, more_below):
        if more_above:
            pixelkit.text(surface, "^", 11, GREY, topright=(panel.right - 6, panel.y + 1))
        if more_below:
            pixelkit.text(surface, "v", 11, GREY,
                          bottomright=(panel.right - 6, panel.bottom - 1))

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
            row_h = 15
            top = panel.y + 4
            names = sorted(c["id"] for c in self.content["characters"].values()
                           if bonds.bondable(c))
            visible = max(1, (panel.height - 4) // row_h)
            first, more_above, more_below = self._scroll_window(
                "Social", len(names), visible)
            y = top
            for char_id in names[first:first + visible]:
                char = self.content["characters"][char_id]
                bond = bonds.ensure_bond(state, char_id)
                level = bonds.bond_level(bond["points"])
                birthday = char["birthday"]
                bar = pygame.Rect(panel.right - pad - 110, y + 1, 110, 6)
                pixelkit.text(
                    surface,
                    f"{char['name']} - Bond {level} ({bond['points']}pts) "
                    f"bday I{birthday['issue']}D{birthday['day']}",
                    11, INK, topleft=(panel.x + pad, y))
                into = bond["points"] - level * config.BOND_POINTS_PER_LEVEL
                frac = 1.0 if level >= config.BOND_LEVEL_MAX else into / config.BOND_POINTS_PER_LEVEL
                pygame.draw.rect(surface, pixelkit.color(CREAM), bar)
                pygame.draw.rect(surface, pixelkit.color(PINK),
                                 pygame.Rect(bar.x, bar.y, max(1, int(bar.width * frac)),
                                             bar.height))
                pygame.draw.rect(surface, pixelkit.color(INK), bar, width=1)
                y += row_h
            if not names:
                pixelkit.text(surface, "(no relationships yet)", 12, GREY,
                              topleft=(panel.x + pad, top))
            self._scroll_arrows(surface, panel, more_above, more_below)
        elif tab == "Tasks":
            half = panel.width // 2
            board_w = half - pad - 4
            tier = dispatch.roster_tier(self.content, state)
            btext(surface, f"Board (today) - Tier {tier}", 12, INK,
                  topleft=(panel.x + pad, panel.y + 5))
            row_h = 11
            list_top = panel.y + 18
            today = activities.assignment_tasks_today(
                state, self.content["assignments"], tier)
            today_ids = {t["id"] for t in today}
            rows = []
            for task in today:
                job = dispatch.find(state, task["id"])
                mark = "[>]" if job else "[ ]"
                heroes, days = task["heroes"], task["days"]
                crew = (f"{heroes}H/{days}D" if job is None else
                        f"back {job['days_left']}d")
                rows.append((f"{mark} {task['name']} -{task['credits']}cr {crew}",
                            bool(job)))
            for job in dispatch.active(state):
                if job["task_id"] in today_ids:
                    continue         # already shown above
                names = ", ".join(self.content["characters"][h]["name"]
                                  for h in job["heroes"])
                rows.append((f"[>] {job['name']}: {names} -{job['days_left']}d",
                            True))
            visible = max(1, (panel.bottom - list_top) // row_h)
            first, more_above, more_below = self._scroll_window(
                "Tasks", len(rows), visible)
            y = list_top
            for line, done in rows[first:first + visible]:
                pixelkit.text(surface, self._fit(line, board_w),
                              10, GREY if done else INK,
                              topleft=(panel.x + pad, y))
                y += row_h
            if not rows:
                pixelkit.text(surface, "(nothing on the board)", 11, GREY,
                              topleft=(panel.x + pad, list_top))
            board_panel = pygame.Rect(panel.x, list_top, half, panel.bottom - list_top)
            self._scroll_arrows(surface, board_panel, more_above, more_below)

            qx = panel.x + half + pad
            btext(surface, "Quests", 12, INK, topleft=(qx, panel.y + 5))
            quest_w = (half - 2 * pad) // 2 - 4
            quests = sorted(state.get("quests", {}).items())
            if quests:
                col_w = (half - 2 * pad) // 2
                for i, (qid, q) in enumerate(quests[:8]):
                    col, row = divmod(i, 4)
                    done = q.get("status") == "done"
                    mark = "[x]" if done else "[>]"
                    pixelkit.text(
                        surface, self._fit(f"{mark} {q.get('name', qid)}", quest_w, 10),
                        10, GREY if done else INK,
                        topleft=(qx + col * col_w, panel.y + 18 + row * 12))
            else:
                pixelkit.text(surface, "(no active quests)", 11, GREY,
                              topleft=(qx, panel.y + 18))
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
