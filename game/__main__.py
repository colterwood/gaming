"""Entry point: python -m game

Env vars for headless verification:
  GAME_SMOKE=1        scripted key sequence walks every state, then quits
  GAME_SMOKE_SHOT=dir save a screenshot per visited state into dir
"""

import os

import pygame

from game import config, data_loader
from game.core.state_machine import StateMachine

# Scripted walk through every state: boot->title->path->hub->battle->hub->
# pause->hub->sleep->hub, then quit.
SMOKE_KEYS = ["return", "return", "return", "b", "return", "p", "escape", "s", "return"]


class App:
    def __init__(self):
        self.machine = StateMachine()
        self.content = data_loader.load_all()
        self.running = True
        self.fps = 0.0


def main():
    from game.ui import screens  # after pygame import, keeps logic modules pygame-free

    smoke = os.environ.get("GAME_SMOKE") == "1"
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
            if smoke_step < len(SMOKE_KEYS):
                screens.handle_key(app, pygame.key.key_code(SMOKE_KEYS[smoke_step]))
                smoke_step += 1
            else:
                app.running = False

        screens.draw(screen, app)
        pygame.display.flip()
        clock.tick(config.FPS)
        app.fps = clock.get_fps()
        frame += 1

    pygame.quit()


if __name__ == "__main__":
    main()
