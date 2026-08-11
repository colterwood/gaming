"""M6: story quest chain, Ant-Man recruitment, and the Ch.1-2 acceptance
playthrough — the whole arc driven through the pure logic layer."""

import pytest

from game import config, data_loader
from game.combat.engine import BattleEngine
from game.combat.entities import Combatant, make_enemy_group
from game.core import calendar as cal
from game.core import save
from game.hub import activities, story
from game.progression import attributes as attrs


class NoLuck:
    """No crits, no dodges, minimal initiative rolls — deterministic."""

    def randint(self, a, b):
        return a

    def uniform(self, a, b):
        return 99.0


@pytest.fixture(scope="module")
def content():
    return data_loader.load_all()


def fresh_run(content):
    state = save.new_game_state()
    state["path"] = "avengers"
    for c in content["characters"].values():
        if c["recruit"]["method"] == "starter":
            state["roster"][c["id"]] = {"trained_ranks": {}, "attribute_xp": {},
                                        "perks": [], "perk_choices": {},
                                        "gear": {}, "ult_charge": 0,
                                        "energy": 100, "unspent_xp": 0}
    state["party"] = sorted(state["roster"], reverse=True)
    story.init(state, content["story"])
    return state


# --- quest chain mechanics ---

def test_init_activates_first_quest(content):
    state = fresh_run(content)
    quest = story.current_quest(state, content["story"])
    assert quest["id"] == content["story"][0]["id"]
    assert state["quests"][quest["id"]]["status"] == "active"


def test_quests_unlock_in_order(content):
    state = fresh_run(content)
    first = content["story"][0]
    state["quests"][first["id"]] = {"name": first["name"], "status": "done"}
    story.init(state, content["story"])
    assert story.current_quest(state, content["story"])["id"] == content["story"][1]["id"]


def test_hub_task_costs_and_completes(content):
    state = fresh_run(content)
    task = next(q for q in content["story"] if q["kind"] == "hub_task")
    result = story.do_hub_task(state, task)
    assert result["ok"]
    assert state["energy"] == config.DAILY_ENERGY - task["energy"]
    assert state["quests"][task["id"]]["status"] == "done"


def test_hub_task_activates_next_quest_entry(content):
    # Review finding: the hub-task path must register the next quest in
    # state["quests"] so the pause-screen Tasks tab shows the active objective.
    state = fresh_run(content)
    for quest in content["story"]:
        if quest["kind"] != "hub_task":
            state["quests"][quest["id"]] = {"name": quest["name"], "status": "done"}
            continue
        story.do_hub_task(state, quest, content["story"])
        nxt = story.current_quest(state, content["story"])
        if nxt:
            assert nxt["id"] in state["quests"]
            assert state["quests"][nxt["id"]]["status"] == "active"


def test_hub_task_blocked_without_energy(content):
    state = fresh_run(content)
    for entry in state["roster"].values():
        entry["energy"] = 5
    task = next(q for q in content["story"] if q["kind"] == "hub_task")
    assert not story.do_hub_task(state, task)["ok"]
    assert state["roster"]["iron_man"]["energy"] == 5


def test_battle_quest_recruits_and_flags(content):
    state = fresh_run(content)
    breakout = next(q for q in content["story"] if q.get("recruit") == "ant_man")
    messages = story.complete_battle_quest(state, breakout, content)
    assert "ant_man" in state["roster"]
    assert any("joins the roster" in m for m in messages)

    boss = next(q for q in content["story"] if q.get("flags", {}).get("training_upgraded"))
    story.complete_battle_quest(state, boss, content)
    assert state["story_flags"]["training_upgraded"] is True
    # upgraded facility now grants 80 XP sessions (§6.3)
    assert attrs.session_xp(state, content["calendar"]) == config.TRAINING_XP_UPGRADED


def test_recruit_is_idempotent(content):
    state = fresh_run(content)
    breakout = next(q for q in content["story"] if q.get("recruit") == "ant_man")
    story.complete_battle_quest(state, breakout, content)
    state["roster"]["ant_man"]["trained_ranks"]["agility"] = 1
    story.complete_battle_quest(state, breakout, content)     # replay must not reset
    assert state["roster"]["ant_man"]["trained_ranks"]["agility"] == 1


# --- M9: mission deadlines and fail cooldowns ---

def test_mission_deadline_expires_and_cools_down(content):
    state = fresh_run(content)
    quest = story.current_quest(state, content["story"])
    assert quest["kind"] == "battle" and quest["deadline_days"] == 3
    assert story.days_left(state, quest) == 3
    state["day"] += 4                                  # blow the deadline
    messages = story.check_deadlines(state, content["story"])
    assert any("Mission failed" in m for m in messages)
    assert story.is_locked(state, quest)
    state["day"] += 1                                  # cooldown day 1 of 2
    assert story.check_deadlines(state, content["story"]) == []
    assert story.is_locked(state, quest)
    state["day"] += 1                                  # cooldown over
    messages = story.check_deadlines(state, content["story"])
    assert any("back on the board" in m for m in messages)
    assert not story.is_locked(state, quest)
    assert story.days_left(state, quest) == 3          # fresh deadline


def test_battle_loss_fails_mission(content):
    state = fresh_run(content)
    quest = story.current_quest(state, content["story"])
    message = story.fail_mission(state, quest)
    assert "Mission failed" in message
    assert story.is_locked(state, quest)
    assert state["quests"][quest["id"]]["retry_day"] == story.abs_day(state) + 2


# --- M6 acceptance: fresh save -> Ch.1-2 complete incl. Ant-Man ---

def _smart_battle(content, state, enemy_ids):
    heroes = []
    for hid in sorted(state["roster"]):
        entry = state["roster"][hid]
        heroes.append(Combatant(content["characters"][hid],
                                trained_ranks=entry.get("trained_ranks", {}),
                                perk_effects=attrs.perk_effects(entry, content["perks"]),
                                is_hero=True))
    engine = BattleEngine(heroes,
                          make_enemy_group([content["enemies"][e] for e in enemy_ids]),
                          rng=NoLuck(), inventory=dict(state["inventory"]),
                          items_data=content["items"])
    for _ in range(500):
        if engine.outcome:
            break
        actor = engine.current()
        engine.begin_turn()
        if engine.current() is not actor:
            continue
        if actor.is_hero:
            target = min(engine.living(engine.enemies), key=lambda e: e.hp)
            ults = actor.abilities_of_type("ultimate")
            specials = actor.abilities_of_type("special")
            if actor.ult_ready():
                engine.take_turn({"type": "ability", "ability_id": ults[0]["id"],
                                  "target_id": None})
            elif specials and actor.can_afford(specials[0]):
                engine.take_turn({"type": "ability", "ability_id": specials[0]["id"],
                                  "target_id": target.id})
            elif actor.hp_fraction() < 0.25 and engine.inventory.get("med_kit", 0) > 0:
                engine.take_turn({"type": "item", "item_id": "med_kit",
                                  "target_id": actor.id})
            else:
                basic = actor.abilities_of_type("basic")[0]
                engine.take_turn({"type": "ability", "ability_id": basic["id"],
                                  "target_id": target.id})
        else:
            engine.take_turn(engine.enemy_action())
    return engine


def test_full_ch1_ch2_playthrough(content):
    state = fresh_run(content)
    battles = 0
    while not story.story_complete(state, content["story"]):
        assert state["day"] < 28, "run must finish well inside Issue 1"
        quest = story.current_quest(state, content["story"])
        if quest["kind"] == "hub_task":
            if not story.do_hub_task(state, quest)["ok"]:
                cal.sleep(state)
            continue
        if activities.should_pass_out(state):   # M11: engaging never refuses,
            cal.sleep(state)                    # so rest BEFORE a 0-EN fight
            continue
        activities.launch_mission(state)
        engine = _smart_battle(content, state, quest["enemies"])
        battles += 1
        assert engine.outcome == "win", f"lost {quest['id']} with smart play"
        rewards = engine.rewards()
        state["credits"] += rewards["credits"]
        story.complete_battle_quest(state, quest, content)
        story.init(state, content["story"])

    assert battles == 5
    assert "ant_man" in state["roster"]                        # recruited
    assert state["story_flags"]["training_upgraded"] is True
    assert state["story_flags"]["ch2_complete"] is True
    assert all(q["status"] == "done" for q in state["quests"].values())
    # 5 missions + 2 hub tasks: a handful of in-game days -> well under
    # 45 real minutes of play (M6 AC)
    assert state["day"] <= 7
