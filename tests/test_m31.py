"""M31: the Tech Lab fills the gear slots that have been empty since M0.
Buy a piece, fit it to a hero, and it shows up in the combat math — flat
rank bonuses that take a hero past the trained ceiling, plus perk-shaped
effects that stack with the perks themselves.
"""

import pygame
import pytest

from game import config, data_loader
from game.combat.entities import Combatant
from game.core import save
from game.core.state_machine import GameState
from game.progression import gear
from game.hub.tower import HubScene

from tests.test_tower_scene import FakeApp, choose, put_player_at


@pytest.fixture(scope="module")
def content():
    pygame.init()
    return data_loader.load_all()


@pytest.fixture
def lab(content):
    scene, app = HubScene(content), FakeApp(content)
    scene._switch_floor("tech_lab")
    app.game_state["credits"] = 2000
    # M36: the labs keep 9-6. The day starts at 6 AM, so a fixture that
    # wants a working bench has to be standing there during the shift.
    app.game_state["time_minutes"] = 10 * 60
    return scene, app


def hero(app, hero_id="iron_man"):
    return app.game_state["roster"][hero_id]


# --- the catalogue (1) ----------------------------------------------------

def test_the_tech_lab_stocks_something_for_every_slot(content):
    stock = [i for i in content["items"].values()
             if gear.is_gear(i) and "tech_lab" in i["sources"]]
    assert {i["slot"] for i in stock} == set(gear.SLOTS)


def test_gear_effects_are_attributes_or_perk_keys(content):
    for item in content["items"].values():
        if not gear.is_gear(item):
            continue
        for key in item["effects"]:
            assert (key in config.ATTRIBUTES
                    or key in data_loader.PERK_EFFECT_KEYS), key


# --- fitting it (2) -------------------------------------------------------

def test_equipping_takes_it_out_of_the_bag(lab):
    _, app = lab
    state = app.game_state
    state["inventory"]["combat_gauntlets"] = 1
    result = gear.equip(state, "iron_man", "combat_gauntlets",
                        app.content["items"])
    assert result["ok"]
    assert gear.equipped(hero(app))["weapon"] == "combat_gauntlets"
    assert "combat_gauntlets" not in state["inventory"]


def test_swapping_a_slot_puts_the_old_piece_back_in_the_bag(lab):
    _, app = lab
    state = app.game_state
    state["inventory"]["combat_gauntlets"] = 1
    state["inventory"]["targeting_optics"] = 1
    gear.equip(state, "iron_man", "combat_gauntlets", app.content["items"])
    gear.equip(state, "iron_man", "targeting_optics", app.content["items"])
    assert gear.equipped(hero(app))["weapon"] == "targeting_optics"
    assert state["inventory"]["combat_gauntlets"] == 1


def test_you_cannot_fit_what_you_do_not_carry(lab):
    _, app = lab
    result = gear.equip(app.game_state, "iron_man", "kevlar_weave",
                        app.content["items"])
    assert not result["ok"]
    assert gear.equipped(hero(app)) == {}


def test_taking_gear_off_never_dead_ends_on_a_full_bag(lab):
    _, app = lab
    state = app.game_state
    state["inventory"]["kevlar_weave"] = 1
    gear.equip(state, "iron_man", "kevlar_weave", app.content["items"])
    # Fill every slot the party can carry (M18 capacity).
    state["inventory"] = {f"filler_{i}": 1
                          for i in range(config.INVENTORY_SLOTS_MAX)}
    result = gear.unequip(state, "iron_man", "armor", app.content["items"])
    assert result["ok"]
    assert state["inventory"]["kevlar_weave"] == 1
    assert gear.equipped(hero(app)) == {}


# --- it lands in combat (3) ----------------------------------------------

def test_a_rank_bonus_raises_the_combat_rank(content):
    plain = Combatant(content["characters"]["captain_america"], is_hero=True)
    kitted = Combatant(content["characters"]["captain_america"], is_hero=True,
                       gear_ranks={"strength": 2})
    assert kitted.rank("strength") > plain.rank("strength")
    assert kitted.rank("agility") == plain.rank("agility")


def test_gear_takes_a_hero_past_the_trained_ceiling(content):
    maxed = {a: config.TRAINED_MAX for a in config.ATTRIBUTES}
    capped = Combatant(content["characters"]["iron_man"], trained_ranks=maxed,
                       is_hero=True)
    kitted = Combatant(content["characters"]["iron_man"], trained_ranks=maxed,
                       is_hero=True, gear_ranks={"strength": 2})
    # Training tops out at RANK_MAX; equipment is handed to you, not trained.
    assert kitted.rank("strength") > capped.rank("strength")


def test_armor_that_adds_stamina_adds_hit_points(content):
    plain = Combatant(content["characters"]["captain_america"], is_hero=True)
    kitted = Combatant(content["characters"]["captain_america"], is_hero=True,
                       gear_ranks={"stamina": 2})
    assert kitted.max_hp > plain.max_hp


def test_perk_shaped_effects_stack_with_the_perks(content):
    both = Combatant(content["characters"]["iron_man"], is_hero=True,
                     perk_effects={"crit_bonus": 5 + 8})     # perk + optics
    assert both.crit_bonus == 13


def test_the_battle_the_app_launches_carries_the_gear(content, monkeypatch,
                                                      tmp_path):
    from game.__main__ import App

    monkeypatch.setattr(config, "SAVE_DIR", str(tmp_path))
    monkeypatch.setattr(data_loader, "load_all", lambda: content)
    app = App()
    app.new_game(slot=1)
    for to in (GameState.TITLE, GameState.PATH_SELECT, GameState.HUB):
        app.machine.transition(to)
    state = app.game_state
    state["inventory"]["combat_gauntlets"] = 1
    state["inventory"]["arc_cell"] = 1
    gear.equip(state, "iron_man", "combat_gauntlets", content["items"])
    gear.equip(state, "iron_man", "arc_cell", content["items"])

    bare = Combatant(content["characters"]["iron_man"], is_hero=True)
    app.start_battle(enemy_ids=("hydra_grunt",))
    fitted = next(h for h in app.battle.engine.heroes if h.id == "iron_man")

    assert fitted.rank("strength") > bare.rank("strength")   # gauntlets
    assert fitted.rank("intelligence") > bare.rank("intelligence")
    assert fitted.max_energy == bare.max_energy + 10 + \
        (config.BATTLE_ENERGY_PER_INT * (int(fitted.rank("intelligence"))
                                         - int(bare.rank("intelligence"))))


# --- upgrade levels are already understood (4) ---------------------------

def test_effects_scale_with_the_schematic_level(content):
    state = save.new_game_state()
    weave = content["items"]["kevlar_weave"]
    assert gear.scaled_effects(state, weave)["durability"] == 2
    state["gear_levels"]["kevlar_weave"] = 3
    assert gear.scaled_effects(state, weave)["durability"] == 4    # 2 x 2.0
    assert "+2" in gear.item_label(state, weave)                   # "Kevlar +2"


def test_an_upgrade_lifts_every_copy_because_it_is_the_design(content):
    state = save.new_game_state()
    state["gear_levels"]["combat_gauntlets"] = 2
    for hero_id in ("iron_man", "captain_america"):
        state["roster"][hero_id] = {"gear": {"weapon": "combat_gauntlets"}}
        effects = gear.total_effects(state, state["roster"][hero_id],
                                     content["items"])
        assert effects["strength"] == 3                            # 2 x 1.5


# --- through the bench (5) ------------------------------------------------

def test_buying_from_the_bench_spends_credits_and_fills_the_bag(lab):
    scene, app = lab
    state = app.game_state
    put_player_at(scene, 6, 4)                      # a workbench tile
    scene.handle_key(app, pygame.K_RETURN)
    choose(scene, app, "Order equipment")
    choose(scene, app, "Kevlar Weave")
    assert state["credits"] == 2000 - app.content["items"]["kevlar_weave"]["price"]
    assert state["inventory"]["kevlar_weave"] == 1


def test_the_bench_fits_it_to_the_hero_you_pick(lab):
    scene, app = lab
    state = app.game_state
    state["inventory"]["kevlar_weave"] = 1
    put_player_at(scene, 6, 4)
    scene.handle_key(app, pygame.K_RETURN)
    choose(scene, app, "Iron Man")
    choose(scene, app, "Armor:")
    choose(scene, app, "Kevlar Weave")
    assert gear.equipped(hero(app))["armor"] == "kevlar_weave"


def test_a_cold_tech_lab_offers_the_repair_instead(content):
    scene, app = HubScene(content), FakeApp(content)
    state = app.game_state
    state["repairs"].pop("repair_tech_lab")
    state["story_flags"]["tech_lab_repaired"] = False
    scene._switch_floor("tech_lab")
    put_player_at(scene, 6, 4)
    scene.handle_key(app, pygame.K_RETURN)
    assert scene.submenu["items"][0][0] == "Restart the Tech Lab"
