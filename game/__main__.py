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
        self.pause = None
        self.game_state = None

    def pause_scene(self):
        if self.pause is None:
            from game.ui.impel_card import ImpelCardScene
            self.pause = ImpelCardScene(self.content)
        return self.pause

    def new_game(self):
        from game.core import energy
        from game.hub import story
        from game.hub.tower import HubScene
        self.game_state = save.new_game_state()
        self.game_state["path"] = "avengers"
        for char in self.content["characters"].values():
            if char["recruit"]["method"] == "starter":
                self.game_state["roster"][char["id"]] = {
                    "trained_ranks": {}, "attribute_xp": {}, "perks": [],
                    "perk_choices": {}, "gear": {}, "ult_charge": 0,
                    "energy": config.DAILY_ENERGY, "unspent_xp": 0}
        self.game_state["party"] = sorted(self.game_state["roster"],
                                          reverse=True)[:config.PARTY_SIZE_MAX]
        energy.sync(self.game_state)
        story.init(self.game_state, self.content["story"])
        self.hub = HubScene(self.content)

    def load_game(self):
        from game.core import energy
        from game.hub import story
        from game.hub.tower import HubScene
        from game.progression import attributes as attrs
        if not save.slot_exists(self.SAVE_SLOT):
            return False
        self.game_state = save.load_game(self.SAVE_SLOT)
        story.init(self.game_state, self.content["story"])
        for entry in self.game_state["roster"].values():
            attrs.sanitize_perk_choices(entry, self.content["perks"])
            entry.setdefault("energy", self.game_state.get("energy", config.DAILY_ENERGY))
            entry.setdefault("unspent_xp", 0)
        if not self.game_state.get("party"):
            self.game_state["party"] = sorted(self.game_state["roster"],
                                              reverse=True)[:config.PARTY_SIZE_MAX]
        energy.sync(self.game_state)
        self.hub = HubScene(self.content)
        return True

    def autosave(self):
        save.save_game(self.game_state, self.SAVE_SLOT)

    def go_to_sleep(self, passed_out=False):
        from game.core import energy
        from game.hub import activities, dispatch, passive, story
        # unfinished rack sessions run into the night and complete (M12)
        messages = activities.finish_due_training(self.game_state, self.content,
                                                  force=True)
        messages += passive.process_day(self.content, self.game_state)
        messages += dispatch.process_day(self.content, self.game_state)
        result = activities.go_to_sleep(self.game_state, passed_out=passed_out)
        messages += story.check_deadlines(self.game_state, self.content["story"])
        energy.sync(self.game_state)
        self.autosave()
        if self.hub:
            self.hub.log(result["message"])
            for msg in messages:
                self.hub.log(msg)
            self.hub.return_to_tower()  # never wake up mid-menu or in the field
        self.machine.transition(GameState.SLEEP)

    def start_battle(self, enemy_ids=("hydra_grunt", "hydra_grunt", "hydra_grunt"),
                     quest=None, ambush=False):
        from game.core import energy
        from game.hub import party as party_mod
        from game.progression import attributes as attrs
        from game.social import bonds
        from game.ui.battle_scene import BattleScene
        self.battle_quest = quest
        self.battle_ambush = ambush
        trained = perk_fx = synergy_crit = energy_frac = None
        hero_ids = ("iron_man", "captain_america")
        if self.game_state:
            roster = self.game_state["roster"]
            hero_ids = tuple(party_mod.get_party(self.game_state)) or tuple(sorted(roster))
            trained = {hid: roster[hid].get("trained_ranks", {}) for hid in hero_ids}
            perk_fx = {hid: attrs.perk_effects(roster[hid], self.content["perks"])
                       for hid in hero_ids}
            energy_frac = {hid: energy.hero_energy(self.game_state, hid) / config.DAILY_ENERGY
                           for hid in hero_ids}
            synergy_crit = {}
            for hid in hero_ids:
                char = self.content["characters"][hid]
                total = 0
                for syn in char.get("synergies", []):
                    if syn["with"] in hero_ids and bonds.synergy_active(self.game_state, char, syn):
                        total += syn["effect"].get("crit_bonus", 0)
                synergy_crit[hid] = total
        self.battle = BattleScene(
            self.content, hero_ids=hero_ids, enemy_ids=enemy_ids, trained=trained,
            perk_fx=perk_fx, synergy_crit=synergy_crit, energy_frac=energy_frac,
            inventory=self.game_state["inventory"] if self.game_state else None)
        self.machine.transition(GameState.BATTLE)

    def finish_battle(self, engine):
        from game.core import clock, energy
        quest = getattr(self, "battle_quest", None)
        ambush = getattr(self, "battle_ambush", False)
        state = self.game_state
        if state and engine.outcome == "win":
            from game.hub import activities, story
            from game.progression import mastery
            from game.social import bonds
            if ambush:      # M12: an unplanned fight still takes time
                clock.advance(state, config.BATTLE_MINUTES)
            rewards = engine.rewards()
            credits = rewards["credits"] if ambush else \
                activities.mission_credits(state, rewards["credits"])
            state["credits"] += credits
            # M9: XP only to participants; KO'd participants earn half
            for hero in engine.heroes:
                entry = state["roster"].get(hero.id)
                if entry:
                    xp = rewards["xp"] if hero.alive else int(
                        rewards["xp"] * config.KO_XP_MULT)
                    entry["unspent_xp"] = entry.get("unspent_xp", 0) + xp
                    mastery.log_mastery_xp(entry, xp)
            bonds.mission_bond(state,
                               [h.id for h in engine.heroes
                                if bonds.bondable(self.content["characters"][h.data["id"]])])
            if self.hub:
                label = "Ambush repelled" if ambush else "Mission complete"
                self.hub.log(f"{label}: +{credits} cr, +{rewards['xp']} XP to the team")
            if quest:
                for msg in story.complete_battle_quest(state, quest, self.content):
                    if self.hub:
                        self.hub.log(msg)
                story.init(state, self.content["story"])
                if self.hub:
                    # No teleport home (M10): the team stays in the field —
                    # walk back to the helipad and take the Quinjet.
                    self.hub.log("Zone clear. The Quinjet is waiting at the helipad.")
        elif state:
            from game.hub import story
            if quest:
                message = story.fail_mission(state, quest)
                if self.hub:
                    self.hub.log(message)
            # M12: defeat costs 3 hours and CAPS the team at 10 EN back at
            # the tower — it no longer ends the day. A cap, never a raise:
            # losing on fumes must not beat winning on fumes.
            clock.advance(state, config.DEFEAT_RECOVERY_MINUTES)
            for hero_id in energy.party(state):
                energy.set_hero_energy(state, hero_id, min(
                    energy.hero_energy(state, hero_id), config.DEFEAT_ENERGY))
            energy.sync(state)
            if self.hub:
                self.hub.log("Beaten. The team limps back to the Tower to regroup.")
                self.hub.return_to_tower()
            self.battle_quest = None
            self.battle = None
            self.machine.transition(GameState.HUB)
            return
        self.battle_quest = None
        self.battle = None
        self.machine.transition(GameState.HUB)

    def update(self, dt):
        if self.machine.state is GameState.BATTLE and self.battle:
            self.battle.update(dt)
        elif self.machine.state is GameState.HUB and self.hub and self.game_state:
            self.hub.update(dt, self)


def main():
    from game.ui import pixelkit, screens  # after pygame import; logic stays pygame-free

    smoke = os.environ.get("GAME_SMOKE") == "1"
    smoke_keys = SMOKE_KEYS
    if os.environ.get("GAME_SMOKE_KEYS"):
        smoke = True
        smoke_keys = os.environ["GAME_SMOKE_KEYS"].split(",")
    shot_dir = os.environ.get("GAME_SMOKE_SHOT")
    if shot_dir:
        os.makedirs(shot_dir, exist_ok=True)

    pygame.init()
    window = pygame.display.set_mode((config.WIDTH * config.WINDOW_SCALE,
                                      config.HEIGHT * config.WINDOW_SCALE))
    pygame.display.set_caption(config.TITLE)
    # All drawing happens at internal resolution; the frame is scaled up
    # nearest-neighbor for chunky uniform pixels (§9 M7).
    screen = pygame.Surface((config.WIDTH, config.HEIGHT))
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
                pygame.image.save(window, os.path.join(
                    shot_dir, f"smoke_{smoke_step:02d}_{app.machine.state.name.lower()}.png"))
            if smoke_step < len(smoke_keys):
                screens.handle_key(app, pygame.key.key_code(smoke_keys[smoke_step]))
                smoke_step += 1
            else:
                app.running = False

        dt = clock.tick(config.FPS) / 1000.0
        app.update(dt)
        screens.draw(screen, app)
        pygame.transform.scale(screen, window.get_size(), window)
        pixelkit.flush_text(window, config.WINDOW_SCALE)    # crisp text pass
        pygame.display.flip()
        app.fps = clock.get_fps()
        frame += 1

    pygame.quit()


if __name__ == "__main__":
    main()
