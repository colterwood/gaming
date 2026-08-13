"""Entry point: python -m game

Env vars for headless verification:
  GAME_SMOKE=1        scripted key sequence walks every state, then quits
  GAME_SMOKE_SHOT=dir save a screenshot per visited state into dir

A smoke run drives the title menu, so it walks New Game -> empty slot 1.
Point GAME_SAVE_DIR at a scratch directory before running one (config
requires that of every headless driver anyway): against the real saves
directory slot 1 is occupied and the walk stops on the overwrite prompt.
"""

import os
import random

import pygame

from game import config, data_loader
from game.core import save
from game.core.state_machine import GameState, StateMachine

# Scripted walk through every state: boot->title->new game->slot->path->
# hub->pause->hub->sleep->hub->battle, then quit.
# Override with GAME_SMOKE_KEYS=comma,list.
SMOKE_KEYS = ["return", "return", "return", "return", "p", "escape", "s",
              "return", "b"]


class App:
    SAVE_SLOT = 1       # the slot being played; new_game/load_game set it

    def __init__(self):
        self.machine = StateMachine()
        self.content = data_loader.load_all()
        self.running = True
        self.fps = 0.0
        self.battle = None
        self.hub = None
        self.pause = None
        self.title = None
        self.game_state = None
        self.pending_slot = None    # slot New Game will start in (M28)

    def pause_scene(self):
        if self.pause is None:
            from game.ui.impel_card import ImpelCardScene
            self.pause = ImpelCardScene(self.content)
        return self.pause

    def title_menu(self):
        if self.title is None:
            from game.ui.screens import TitleMenu
            self.title = TitleMenu()
        return self.title

    def new_game(self, slot=None):
        from game.core import energy
        from game.hub import story
        from game.hub.tower import HubScene
        if slot is not None:
            self.SAVE_SLOT = slot
        self.game_state = save.new_game_state()
        self.game_state["path"] = "avengers"
        for char in self.content["characters"].values():
            if char["recruit"]["method"] == "starter":
                self.game_state["roster"][char["id"]] = {
                    "trained_ranks": {}, "attribute_xp": {}, "perks": [],
                    "perk_choices": {}, "gear": {}, "ult_charge": 0,
                    "energy": config.DAILY_ENERGY}
        self.game_state["party"] = sorted(self.game_state["roster"],
                                          reverse=True)[:config.PARTY_SIZE_MAX]
        energy.sync(self.game_state)
        story.init(self.game_state, self.content["story"])
        self.hub = HubScene(self.content)

    def load_game(self, slot=None):
        from game.core import energy
        from game.hub import story
        from game.hub.tower import HubScene
        from game.progression import attributes as attrs
        slot = self.SAVE_SLOT if slot is None else slot
        if not save.slot_exists(slot):
            return False
        self.SAVE_SLOT = slot
        self.game_state = save.load_game(slot)
        story.init(self.game_state, self.content["story"])
        from game.hub import activities, dispatch, repairs
        dispatch.backfill_spots(self.content, self.game_state)  # pre-M13 jobs
        activities.migrate_training_locks(self.game_state)      # pre-M16 locks
        repairs.migrate(self.content, self.game_state)          # pre-M29 tower
        story.backfill_flags(self.game_state, self.content["story"])
        for hero_id, entry in self.game_state["roster"].items():
            attrs.sanitize_perk_choices(entry, self.content["perks"])
            entry.setdefault("energy", self.game_state.get("energy", config.DAILY_ENERGY))
            # M21: the battle-XP bank is gone. Anything a save still has
            # sitting in it was EARNED — spend it onto the attributes now
            # rather than dropping it on the floor.
            owed = entry.pop("unspent_xp", 0)
            if owed:
                attrs.award_battle_xp(
                    self.content["characters"][hero_id].get("boosts", {}),
                    entry, owed)
        self.game_state.pop("unspent_xp", None)     # top-level copy: never read
        if not self.game_state.get("party"):
            # M36: an empty party is now a real state — training your last
            # hero (solo_ok) empties it deliberately. This fallback predates
            # that and would refill the team with heroes who are LOCKED on
            # the mats or away on a job, which skips the lockout the player
            # just paid for and drags them into battles. Only free heroes.
            free = [h for h, e in sorted(self.game_state["roster"].items())
                    if not e.get("training") and not e.get("dispatch")]
            self.game_state["party"] = sorted(
                free, reverse=True)[:config.PARTY_SIZE_MAX]
        energy.sync(self.game_state)
        self.hub = HubScene(self.content)
        return True

    def autosave(self):
        save.save_game(self.game_state, self.SAVE_SLOT)

    def go_to_sleep(self, passed_out=False):
        from game.core import energy
        from game.hub import activities, dispatch, passive, story, unlocks
        from game.progression import gear as gear_mod
        # M36: going down INDOORS is not the same as going down in the
        # HYDRA District. The hub knows which, and it is the only thing
        # that does.
        sheltered = bool(self.hub is None or self.hub.area == "tower")
        messages = passive.process_day(self.content, self.game_state)
        messages += dispatch.process_day(self.content, self.game_state)
        messages += gear_mod.process_day(self.game_state,
                                         self.content["items"])
        result = activities.go_to_sleep(self.game_state, passed_out=passed_out,
                                        sheltered=sheltered)
        # M16: rack sessions are measured in WAKING hours and may span days.
        # Settle them after the calendar advances, so the night banks the
        # rest of the day the hero spent on the mats.
        messages += activities.finish_due_training(self.game_state, self.content)
        messages += story.check_deadlines(self.game_state, self.content["story"])
        # M17: side arcs fire on the night boundary — a signal when its
        # requirements have come true, an arrival the morning after the
        # team carries its prize home.
        messages += unlocks.process_night(self.content, self.game_state)
        energy.sync(self.game_state)
        self.autosave()
        if self.hub:
            self.hub.log(result["message"])
            for msg in messages:
                self.hub.log(msg)
            self.hub.wake_up()          # M36: always beside your own bed
        self.machine.transition(GameState.SLEEP)

    def start_battle(self, enemy_ids=("hydra_grunt", "hydra_grunt", "hydra_grunt"),
                     quest=None, ambush=False):
        from game.core import energy, health
        from game.hub import party as party_mod
        from game.progression import attributes as attrs
        from game.progression import gear as gear_mod
        from game.social import bonds
        from game.ui.battle_scene import BattleScene
        self.battle_quest = quest
        self.battle_ambush = ambush
        trained = perk_fx = synergy_crit = energy_frac = ult_charge = None
        gear_ranks = hp_frac = None
        hero_ids = ("iron_man", "captain_america")
        if self.game_state:
            roster = self.game_state["roster"]
            hero_ids = tuple(party_mod.get_party(self.game_state)) or tuple(sorted(roster))
            trained = {hid: roster[hid].get("trained_ranks", {}) for hid in hero_ids}
            # M31: worn gear splits into flat rank bonuses and perk-shaped
            # combat effects, which stack onto whatever the perks give.
            gear_ranks, gear_fx = {}, {}
            for hid in hero_ids:
                ranks, combat = gear_mod.split_effects(gear_mod.total_effects(
                    self.game_state, roster[hid], self.content["items"]))
                gear_ranks[hid], gear_fx[hid] = ranks, combat
            perk_fx = {hid: attrs.perk_effects(roster[hid], self.content["perks"])
                       for hid in hero_ids}
            for hid in hero_ids:
                for key, value in gear_fx[hid].items():
                    perk_fx[hid][key] = perk_fx[hid].get(key, 0) + value
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
            # M15: ultimate charge carries over from the last fight.
            ult_charge = {hid: roster[hid].get("ult_charge", 0) for hid in hero_ids}
            # M36: so does HP.
            hp_frac = {hid: health.hero_hp_fraction(self.game_state, hid)
                       for hid in hero_ids}
        self.battle = BattleScene(
            self.content, hero_ids=hero_ids, enemy_ids=enemy_ids, trained=trained,
            perk_fx=perk_fx, synergy_crit=synergy_crit, energy_frac=energy_frac,
            ult_charge=ult_charge, gear_ranks=gear_ranks, hp_frac=hp_frac,
            on_resolve=self.battle_salvage,
            inventory=self.game_state["inventory"] if self.game_state else None)
        self.machine.transition(GameState.BATTLE)

    def battle_salvage(self, engine):
        """Roll what a won fight coughs up beyond XP and credits (M35), the
        moment the fight settles rather than when the panel is dismissed.

        M36: the return value is printed ON the victory panel. These drops
        are the only way some repair parts exist — a Stark toolhead at 33%
        a fight — and announcing them in the hub message log, after the
        player had already walked away, made them read as noise."""
        if self.game_state is None:
            return []
        from game.hub import repairs as repairs_mod
        messages = repairs_mod.battle_drop(
            self.content, self.game_state, [h.id for h in engine.heroes],
            random.Random())
        for message in messages:
            if self.hub:
                self.hub.log(message)
        return messages

    def finish_battle(self, engine):
        from game.core import clock, energy, health
        quest = getattr(self, "battle_quest", None)
        ambush = getattr(self, "battle_ambush", False)
        state = self.game_state
        if state:
            # M15: bank each hero's ultimate charge for the next fight.
            # M36: and the state of them — HP is carried, not reset, so a
            # bruising win is felt in the next fight.
            for hero in engine.heroes:
                entry = state["roster"].get(hero.id)
                if entry is not None:
                    entry["ult_charge"] = hero.ult_charge
                    fraction = hero.hp / hero.max_hp
                    if engine.outcome == "win" and not hero.alive:
                        # Won the fight, but this one went down doing it:
                        # they come round rather than staying at zero.
                        fraction = config.KO_REVIVE_HP_FRACTION
                    health.set_hero_hp_fraction(state, hero.id, fraction)
        if state and engine.outcome == "win":
            from game.hub import activities, story
            from game.progression import attributes as attrs
            from game.progression import mastery
            from game.social import bonds
            if ambush:      # M12: an unplanned fight still takes time
                clock.advance(state, config.BATTLE_MINUTES)
            rewards = engine.rewards()
            credits = rewards["credits"] if ambush else \
                activities.mission_credits(state, rewards["credits"])
            state["credits"] += credits
            # M9: XP only to participants; KO'd participants earn half.
            # M21: it lands on their attributes NOW, split across the six,
            # instead of banking for a future rack session.
            for hero in engine.heroes:
                entry = state["roster"].get(hero.id)
                if not entry:
                    continue
                xp = rewards["xp"] if hero.alive else int(
                    rewards["xp"] * config.KO_XP_MULT)
                boosts = self.content["characters"][hero.id].get("boosts", {})
                gain = attrs.award_battle_xp(boosts, entry, xp)
                mastery.log_mastery_xp(entry, xp)
                if self.hub and gain["ranks_gained"]:
                    name = self.content["characters"][hero.id]["name"]
                    ups = ", ".join(f"{a.title()} {r + config.RANK_START}"
                                    for a, r in gain["ranks_gained"])
                    self.hub.log(f"{name} ranks up from the field: {ups}!")
            bonds.mission_bond(state,
                               [h.id for h in engine.heroes
                                if bonds.bondable(self.content["characters"][h.data["id"]])])
            if self.hub:
                label = "Ambush repelled" if ambush else "Mission complete"
                share = rewards["xp"] // len(config.ATTRIBUTES)
                self.hub.log(f"{label}: +{credits} cr, +{rewards['xp']} XP each "
                             f"(+{share} to every skill)")
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
            # M36: patched up enough to stand, and no more. A FLOOR, like
            # DEFEAT_ENERGY is a cap — a team that wins on 5% must not be
            # better off for having lost instead.
            health.floor_party(state, config.DEFEAT_HP_FRACTION)
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
