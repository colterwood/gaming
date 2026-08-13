"""Pause screen styled as a 1991 Impel Marvel card back (spec §8, pixel
edition per §9 M7). Zone sizes are the §8 values halved to internal-res px.

Palette anchored to the reference scans in assets/reference/; trained ranks
overlay in gold (a game addition), foil sparkle when Mastered.
Rendering + input only.
"""

import pygame

from game import config
from game.core import calendar as cal
from game.core import inventory
from game.core.state_machine import GameState
from game.hub import activities, dispatch
from game.progression import attributes as attrs
from game.progression import gear
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
            # M18: no mid-day saving. The autosave at lights-out is the only
            # save, so quitting mid-day rewinds to that morning rather than
            # letting the player bank a good afternoon and retry a bad one.
            self.message = "The tower saves itself at lights-out."

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
            # M20: the bar is the TRAINED RANK and nothing else. It used to
            # be extended by a gold band for the innate boost, which read as
            # "this hero is at that level" — they aren't. The boost is a
            # bonus on top, shown as the +N marker at the end of the row.
            rank = attrs.rank(entry, attribute)
            bar = pygame.Rect(row.x + 1, row.y + 4,
                              int((rank + 1) * unit) - 2, row.height - 8)
            pygame.draw.rect(surface, pixelkit.color(PINK), bar)
            pygame.draw.line(surface, pixelkit.color("white"),
                             (bar.x, bar.y), (bar.right - 1, bar.y))
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
        label = "POWER RATINGS" + ("  * MASTERED *" if mastered else "")
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

    def _progress_rows(self, state):
        """Everything the player has going, with how far along it is (M36).

        The Tasks tab listed what was POSTED and what was accepted, but not
        how close any of it was to finishing — so "how many Pym parts do I
        still need" and "how long until Shang-Chi is off the mats" were
        questions you answered by walking to the thing and looking at it.
        Repairs, the story quest, the rack, the Pym bench: one line each.
        """
        from game.core import clock as clock_mod
        from game.hub import activities as act
        from game.hub import repairs as repairs_mod
        from game.hub import story as story_mod
        from game.progression import gear as gear_mod

        rows = []
        for job in repairs_mod.active(self.content, state):
            total = len(job["parts"])
            have = len(repairs_mod.found(state, job))
            tail = "ready to fit" if have >= total else f"{have}/{total} parts"
            rows.append((f"[~] {job['name']} - {tail}", False))

        quest = story_mod.current_quest(state, self.content["story"])
        if quest is not None and story_mod.is_accepted(state, quest):
            left = story_mod.days_left(state, quest)
            when = f", {left}d left" if left is not None else ""
            if quest.get("kind") == "scout":
                done = len(story_mod.scouted(state, quest))
                rows.append((f"[~] {quest['name']} - {done}/"
                             f"{len(quest['scout_points'])} spots{when}", False))
            else:
                rows.append((f"[~] {quest['name']} - "
                             f"{self._area_label(quest.get('location'))}{when}",
                             False))

        for hero_id in sorted(state.get("roster", {})):
            entry = state["roster"][hero_id]
            name = self.content["characters"][hero_id]["name"]
            lock = entry.get("training")
            if lock:
                left = act.training_remaining(state, lock)
                rows.append((f"[~] {name} training "
                             f"{lock['attribute'].title()} - "
                             f"{clock_mod.format_duration(left)} to go", False))
            elif entry.get("done_training"):
                rows.append((f"[!] {name} is done on the mats - collect them",
                             False))

        for job in gear_mod.queue(state):
            item = self.content["items"].get(job["item"], {})
            label = item.get("name", job["item"])
            tail = ("ready to collect" if job["days_left"] <= 0
                    else f"{job['days_left']}d left")
            rows.append((f"[~] Pym bench: {label} L{job['level']} - {tail}",
                         False))
        return rows

    def _area_label(self, area):
        zone = self.content["zones"].get(area) if area else None
        return zone["name"] if zone else "the tower"

    def _draw_quest_column(self, surface, panel, state, half, pad):
        """The Tasks tab's right-hand quest list — drawn whether or not
        today's board has been read (M20)."""
        qx = panel.x + half + pad
        btext(surface, "Quests", 12, INK, topleft=(qx, panel.y + 5))
        quest_w = (half - 2 * pad) // 2 - 4
        quests = sorted(state.get("quests", {}).items())
        if not quests:
            pixelkit.text(surface, "(no active quests)", 11, GREY,
                          topleft=(qx, panel.y + 18))
            return
        col_w = (half - 2 * pad) // 2
        for i, (qid, quest) in enumerate(quests[:8]):
            col, row = divmod(i, 4)
            done = quest.get("status") == "done"
            mark = "[x]" if done else "[>]"
            pixelkit.text(
                surface, self._fit(f"{mark} {quest.get('name', qid)}", quest_w, 10),
                10, GREY if done else INK,
                topleft=(qx + col * col_w, panel.y + 18 + row * 12))

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
            btext(surface, f"Inventory - {state['credits']} credits - "
                           f"{inventory.label(state)}{extra}", 13, INK,
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
            btext(surface, f"Achievements:{extra}", 13, INK,
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
            # M31: what they're wearing, and what it's worth.
            worn = gear.equipped(entry)
            if worn:
                kit = "  ".join(
                    f"{gear.item_label(state, self.content['items'][i])} "
                    f"({gear.effect_label(state, self.content['items'][i])})"
                    for i in worn.values())
            else:
                kit = "(nothing fitted - see the Tech Lab)"
            pixelkit.text(surface, f"Gear:  {kit}", 11, INK,
                          topleft=(panel.x + pad, panel.bottom - 27))
            # M20: XP toward the NEXT rank, as progress/needed rather than a
            # bare running total. "MAX" once an attribute is at RANK_MAX.
            banked = entry.get("attribute_xp", {})
            hero_boosts = self.content["characters"].get(hero_id, {}).get(
                "boosts", {})
            parts = []
            for attribute in config.ATTRIBUTES:
                got = banked.get(attribute, 0)
                if not attrs.can_train(hero_boosts, entry, attribute):
                    parts.append(f"{attribute[:3].upper()} MAX")
                    continue
                need = attrs.xp_for_rank(attrs.rank(entry, attribute))
                parts.append(f"{attribute[:3].upper()} {got}/{need}")
            line = "XP:  " + "  ".join(parts)
            pixelkit.text(surface, line, 11, INK,
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
                pixelkit.text(
                    surface,
                    f"{char['name']} - Bond {level} ({bond['points']}pts) "
                    f"bday I{birthday['issue']}D{birthday['day']}",
                    11, INK, topleft=(panel.x + pad, y))
                # M20: ten Avengers logos instead of a progress bar - one
                # lights up per bond level earned.
                pip = sprites.avengers_pip(True)
                step = pip.get_width() + 1
                left = panel.right - pad - config.BOND_LEVEL_MAX * step
                for slot in range(config.BOND_LEVEL_MAX):
                    surface.blit(sprites.avengers_pip(slot < level),
                                 (left + slot * step, y + 1))
                y += row_h
            if not names:
                pixelkit.text(surface, "(no relationships yet)", 12, GREY,
                              topleft=(panel.x + pad, top))
            self._scroll_arrows(surface, panel, more_above, more_below)
        elif tab == "Tasks":
            half = panel.width // 2
            board_w = half - pad - 4
            tier = dispatch.roster_tier(self.content, state)
            btext(surface, "Board (today)", 12, INK,
                  topleft=(panel.x + pad, panel.y + 5))
            row_h = 11
            list_top = panel.y + 18
            if not activities.board_checked_today(state):
                # M20: the card is a notebook, not a wire. Postings only get
                # written down once someone has actually read the board.
                pixelkit.text(surface, "Check the board by Coulson!", 12, RED,
                              topleft=(panel.x + pad, list_top))
                self._draw_quest_column(surface, panel, state, half, pad)
                surface.set_clip(None)
                return
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
                pay = f"{task['credits']}cr"        # M23: XP was invisible
                if task.get("xp"):
                    pay += f"/{task['xp']}xp"
                if task.get("bond") and task.get("requested_by"):
                    pay += f"/{task['bond']}bond"
                rows.append((f"{mark} {task['name']} -{pay} {crew}", bool(job)))
            for job in dispatch.active(state):
                if job["task_id"] in today_ids:
                    continue         # already shown above
                names = ", ".join(self.content["characters"][h]["name"]
                                  for h in job["heroes"])
                rows.append((f"[>] {job['name']}: {names} -{job['days_left']}d",
                            True))
            rows += self._progress_rows(state)
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

            self._draw_quest_column(surface, panel, state, half, pad)
        elif tab == "Map":
            btext(surface, "WORLD MAP - coming in a later issue", 15, GREY,
                  center=panel.center)
        # (progress rows for everything in flight are built by
        #  _progress_rows and appended to the Tasks list above)
        elif tab == "Options":
            btext(surface, f"The day autosaves when you sleep - "
                           f"slot {app.SAVE_SLOT}", 14, INK,
                  topleft=(panel.x + pad, panel.y + 7))
            pixelkit.text(surface, "Quit before bed and you wake up back at "
                                   "6:00 AM this morning.", 12, INK,
                          topleft=(panel.x + pad, panel.y + 25))
            for ev in cal.active_events(state, self.content["calendar"]):
                pixelkit.text(surface, f"Active event: {ev['name']}", 12, RED,
                              topleft=(panel.x + pad, panel.y + 40))
            if self.message:
                pixelkit.text(surface, self.message, 13, RED,
                              topleft=(panel.x + pad, panel.y + 55))
        surface.set_clip(None)
