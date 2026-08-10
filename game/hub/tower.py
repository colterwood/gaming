"""Avengers Tower hub scene (M2): three rooms, clock/energy HUD, activity
menu, cosmetic clock tick. Rendering + input only — rules live in
game.hub.activities and game.core."""

import pygame

from game import config
from game.core import calendar as cal
from game.core import clock
from game.hub import activities
from game.ui import widgets

ROOMS = ("Common Floor", "Training Floor", "Ops Floor")


class HubScene:
    def __init__(self, content):
        self.content = content
        self.room_index = 0
        self.activity_index = 0
        self.messages = []
        self.tick_accum = 0.0

    # --- activity lists per room ---

    def room_activities(self, state):
        room = ROOMS[self.room_index]
        if room == "Common Floor":
            acts = []
            for task in activities.assignment_tasks_today(state, self.content["assignments"]):
                done = task["id"] in state.get("assignments_done", [])
                label = f"{task['name']} ({task['energy']} EN)" + ("  [done]" if done else "")
                acts.append({"label": label, "kind": "assignment", "task": task,
                             "disabled": done})
            acts.append({"label": f"Workshop Tinkering ({config.CRAFT_ENERGY} EN, 1h)",
                         "kind": "craft"})
            return acts
        if room == "Training Floor":
            return [{"label": f"Training Session ({config.TRAINING_ENERGY} EN, 90m)",
                     "kind": "training"}]
        return [{"label": f"Story Mission: HYDRA Patrol ({config.MISSION_ENERGY} EN, 3h)",
                 "kind": "mission"}]

    def log(self, message):
        self.messages.append(message)
        self.messages = self.messages[-3:]

    # --- update / input ---

    def update(self, dt, app):
        """Cosmetic tick: 10 in-game minutes per 7 real seconds (§6.1)."""
        self.tick_accum += dt
        if self.tick_accum >= config.TICK_REAL_SECONDS:
            self.tick_accum -= config.TICK_REAL_SECONDS
            clock.advance(app.game_state, config.TICK_GAME_MINUTES)
        if activities.should_pass_out(app.game_state):
            self.log("You pass out...")
            app.go_to_sleep(passed_out=True)

    def handle_key(self, app, key):
        state = app.game_state
        acts = self.room_activities(state)
        if key == pygame.K_LEFT:
            self.room_index = (self.room_index - 1) % len(ROOMS)
            self.activity_index = 0
        elif key == pygame.K_RIGHT:
            self.room_index = (self.room_index + 1) % len(ROOMS)
            self.activity_index = 0
        elif key == pygame.K_UP:
            self.activity_index = (self.activity_index - 1) % max(1, len(acts))
        elif key == pygame.K_DOWN:
            self.activity_index = (self.activity_index + 1) % max(1, len(acts))
        elif key == pygame.K_RETURN and acts:
            self._perform(app, acts[self.activity_index % len(acts)])
        elif key == pygame.K_s:
            app.go_to_sleep(passed_out=False)
        elif key in (pygame.K_p, pygame.K_ESCAPE):
            from game.core.state_machine import GameState
            app.machine.transition(GameState.PAUSE)

    def _perform(self, app, act):
        state = app.game_state
        if act.get("disabled"):
            self.log("Already done today.")
            return
        if act["kind"] == "assignment":
            result = activities.do_assignment(state, act["task"])
        elif act["kind"] == "craft":
            result = activities.craft(state)
        elif act["kind"] == "training":
            result = activities.training_session(state)
        elif act["kind"] == "mission":
            result = activities.launch_mission(state)
        else:
            return
        self.log(result["message"])
        if result.get("launch_battle"):
            app.start_battle()
            return
        if result["ok"] and activities.should_pass_out(state):
            self.log("You pass out...")
            app.go_to_sleep(passed_out=True)

    # --- drawing ---

    def draw(self, surface, app):
        state = app.game_state
        surface.fill(widgets.NAVY)

        # HUD: calendar, clock, energy, credits
        widgets.text(surface, f"Issue {state['issue']}, Day {state['day']}", 32,
                     widgets.CREAM, topleft=(40, 18))
        widgets.text(surface, clock.format_time(state["time_minutes"]), 32,
                     widgets.GOLD, center=(config.WIDTH // 2, 30))
        widgets.bar(surface, pygame.Rect(config.WIDTH - 340, 18, 240, 24),
                    state["energy"] / config.DAILY_ENERGY, widgets.GREEN,
                    label=f"{state['energy']} EN")
        widgets.text(surface, f"{state['credits']} cr", 28, widgets.GOLD,
                     topleft=(config.WIDTH - 90, 20))
        for ev in cal.active_events(state, self.content["calendar"]):
            widgets.text(surface, f"EVENT: {ev['name']}", 26, widgets.RED,
                         center=(config.WIDTH // 2, 64))

        # Rooms as tabs
        tab_w = 280
        for i, room in enumerate(ROOMS):
            rect = pygame.Rect(40 + i * (tab_w + 16), 100, tab_w, 52)
            selected = i == self.room_index
            pygame.draw.rect(surface, widgets.RED if selected else widgets.INK,
                             rect, border_radius=8)
            pygame.draw.rect(surface, widgets.GOLD if selected else widgets.GREY,
                             rect, width=2, border_radius=8)
            widgets.text(surface, room, 28, widgets.CREAM, center=rect.center)

        # Activity list
        acts = self.room_activities(state)
        panel = pygame.Rect(40, 180, 760, 320)
        pygame.draw.rect(surface, widgets.INK, panel, border_radius=8)
        pygame.draw.rect(surface, widgets.CREAM, panel, width=1, border_radius=8)
        for i, act in enumerate(acts):
            row = pygame.Rect(panel.x + 8, panel.y + 12 + i * 52, panel.width - 16, 44)
            if i == self.activity_index % max(1, len(acts)):
                pygame.draw.rect(surface, widgets.RED, row, border_radius=6)
            color = widgets.GREY if act.get("disabled") else widgets.CREAM
            widgets.text(surface, act["label"], 28, color, midleft=(row.x + 16, row.centery))

        # Roster panel
        roster_panel = pygame.Rect(840, 180, 400, 320)
        pygame.draw.rect(surface, widgets.INK, roster_panel, border_radius=8)
        pygame.draw.rect(surface, widgets.CREAM, roster_panel, width=1, border_radius=8)
        widgets.text(surface, "Roster", 28, widgets.GOLD,
                     topleft=(roster_panel.x + 16, roster_panel.y + 12))
        for i, hero_id in enumerate(sorted(state.get("roster", {}))):
            name = self.content["characters"][hero_id]["name"]
            widgets.text(surface, name, 26, widgets.CREAM,
                         topleft=(roster_panel.x + 16, roster_panel.y + 52 + i * 34))

        for i, msg in enumerate(self.messages):
            widgets.text(surface, msg, 26, widgets.CREAM, topleft=(40, 530 + i * 32))

        widgets.text(surface,
                     "Arrows: room/activity   Enter: do   S: sleep   Esc: pause",
                     26, widgets.CREAM, center=(config.WIDTH // 2, config.HEIGHT - 30))
