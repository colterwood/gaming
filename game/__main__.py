"""Entry point: python -m game

Env vars for headless verification:
  GAME_SMOKE=1        scripted key sequence walks every state, then quits
  GAME_SMOKE_SHOT=dir save a screenshot per visited state into dir
"""

import os

import pygame

from game import config, data_loader
from game.core import save
from game.core.state_machine import GameState, StateMachine

# Scripted walk through every state: boot->title->path->hub->pause->hub->
# sleep->hub->battle, then quit. Override with GAME_SMOKE_KEYS=comma,list.
SMOKE_KEYS = ["return", "return", "return", "p", "escape", "s", "return", "b"]


class App:
    SAVE_SLOT = 1

    def __init__(self):
        self.machine = StateMachine()
        self.content = data_loader.load_all()
        self.running = True
        self.fps = 0.0
        self.battle = None
        self.hub = None
        self.game_state = None

    def new_game(self):
        from game.hub.tower import HubScene
        self.game_state = save.new_game_state()
        self.game_state["path"] = "avengers"
        for char in self.content["characters"].values():
            if char["recruit"]["method"] == "starter":
                self.game_state["roster"][char["id"]] = {
                    "trained_ranks": {}, "attribute_xp": {}, "perks": [],
                    "gear": {}, "ult_charge": 0}
        self.hub = HubScene(self.content)

    def load_game(self):
        from game.hub.tower import HubScene
        if not save.slot_exists(self.SAVE_SLOT):
            return False
        self.game_state = save.load_game(self.SAVE_SLOT)
        self.hub = HubScene(self.content)
        return True

    def autosave(self):
        save.save_game(self.game_state, self.SAVE_SLOT)

    def go_to_sleep(self, passed_out=False):
        from game.hub import activities
        result = activities.go_to_sleep(self.game_state, passed_out=passed_out)
        self.autosave()
        if self.hub:
            self.hub.log(result["message"])
        self.machine.transition(GameState.SLEEP)

    def start_battle(self, enemy_ids=("hydra_grunt", "hydra_grunt", "hydra_grunt")):
        from game.ui.battle_scene import BattleScene
        trained = {hid: h.get("trained_ranks", {})
                   for hid, h in self.game_state["roster"].items()} if self.game_state else None
        self.battle = BattleScene(
            self.content, enemy_ids=enemy_ids, trained=trained,
            inventory=self.game_state["inventory"] if self.game_state else None)
        self.machine.transition(GameState.BATTLE)

    def finish_battle(self, engine):
        if self.game_state and engine.outcome == "win":
            rewards = engine.rewards()
            self.game_state["credits"] += rewards["credits"]
            self.game_state["unspent_xp"] += rewards["xp"]
            if self.hub:
                self.hub.log(f"Mission complete: +{rewards['credits']} cr, +{rewards['xp']} XP")
        elif self.hub:
            self.hub.log("Mission failed. The team limps home.")
        self.battle = None
        self.machine.transition(GameState.HUB)

    def update(self, dt):
        if self.machine.state is GameState.BATTLE and self.battle:
            self.battle.update(dt)
        elif self.machine.state is GameState.HUB and self.hub and self.game_state:
            self.hub.update(dt, self)


def main():
    from game.ui import screens  # after pygame import, keeps logic modules pygame-free

    smoke = os.environ.get("GAME_SMOKE") == "1"
    smoke_keys = SMOKE_KEYS
    if os.environ.get("GAME_SMOKE_KEYS"):
        smoke = True
        smoke_keys = os.environ["GAME_SMOKE_KEYS"].split(",")
    shot_dir = os.environ.get("GAME_SMOKE_SHOT")
    if shot_dir:
        os.makedirs(shot_dir, exist_ok=True)

    pygame.init()
    screen = pygame.display.set_mode((config.WIDTH, config.HEIGHT))
    pygame.display.set_caption(config.TITLE)
    clock = pygame.time.Clock()
    app = App()

    frame = 0
    smoke_step = 0
    while app.running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                app.running = False
            elif event.type == pygame.KEYDOWN:
                screens.handle_key(app, event.key)

        if smoke and frame > 0 and frame % 10 == 0:
            if shot_dir:
                pygame.image.save(screen, os.path.join(
                    shot_dir, f"smoke_{smoke_step:02d}_{app.machine.state.name.lower()}.png"))
            if smoke_step < len(smoke_keys):
                screens.handle_key(app, pygame.key.key_code(smoke_keys[smoke_step]))
                smoke_step += 1
            else:
                app.running = False

        dt = clock.tick(config.FPS) / 1000.0
        app.update(dt)
        screens.draw(screen, app)
        pygame.display.flip()
        app.fps = clock.get_fps()
        frame += 1

    pygame.quit()


if __name__ == "__main__":
    main()
