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

def test_init_offers_first_quest(content):
    state = fresh_run(content)
    quest = story.current_quest(state, content["story"])
    assert quest["id"] == content["story"][0]["id"]
    # M13: quests start OFFERED — nothing in the field until accepted
    assert state["quests"][quest["id"]]["status"] == "offered"
    assert not story.is_accepted(state, quest)
    assert story.days_left(state, quest) is None        # clock not started
    result = story.accept(state, quest)
    assert result["ok"]
    assert story.is_accepted(state, quest)
    assert story.accept(state, quest)["ok"] is False    # only once


def test_quests_unlock_in_order(content):
    state = fresh_run(content)
    first = content["story"][0]
    state["quests"][first["id"]] = {"name": first["name"], "status": "done"}
    story.init(state, content["story"])
    assert story.current_quest(state, content["story"])["id"] == content["story"][1]["id"]


def test_scout_quest_costs_and_completes(content):
    state = fresh_run(content)
    quest = next(q for q in content["story"] if q["kind"] == "scout")
    assert not story.do_scout(state, quest, 0)["ok"]    # accept first (M13)
    story.accept(state, quest)
    points = quest["scout_points"]
    for i in range(len(points)):
        result = story.do_scout(state, quest, i, content["story"])
        assert result["ok"]
    assert result.get("complete")
    assert state["quests"][quest["id"]]["status"] == "done"
    assert state["energy"] == config.DAILY_ENERGY - config.SCOUT_ENERGY * len(points)
    assert state["time_minutes"] == \
        config.DAY_START_MINUTES + config.SCOUT_MINUTES * len(points)
    assert not story.do_scout(state, quest, 0)["ok"]    # nothing left


def test_scout_completion_activates_next_quest_entry(content):
    # The pause-screen Tasks tab needs the next quest registered.
    state = fresh_run(content)
    for quest in content["story"]:
        if quest["kind"] != "scout":
            state["quests"][quest["id"]] = {"name": quest["name"], "status": "done"}
            continue
        story.accept(state, quest)
        for i in range(len(quest["scout_points"])):
            story.do_scout(state, quest, i, content["story"])
        nxt = story.current_quest(state, content["story"])
        if nxt:
            assert nxt["id"] in state["quests"]
            assert state["quests"][nxt["id"]]["status"] == "offered"


def test_scout_blocked_without_energy(content):
    state = fresh_run(content)
    quest = next(q for q in content["story"] if q["kind"] == "scout")
    story.accept(state, quest)
    for entry in state["roster"].values():
        entry["energy"] = 2
    assert not story.do_scout(state, quest, 0)["ok"]
    assert state["roster"]["iron_man"]["energy"] == 2
    assert story.scouted(state, quest) == []            # nothing marked


def test_battle_quest_recruits_and_flags(content):
    state = fresh_run(content)
    breakout = next(q for q in content["story"] if q.get("recruit") == "ant_man")
    messages = story.complete_battle_quest(state, breakout, content)
    assert "ant_man" in state["roster"]
    assert any("joins the roster" in m for m in messages)

    boss = next(q for q in content["story"] if q.get("flags", {}).get("training_upgraded"))
    story.complete_battle_quest(state, boss, content)
    assert state["story_flags"]["training_upgraded"] is True
    # M16: the upgraded facility doubles the level's session yield
    assert (attrs.session_xp(state, content["calendar"], 1)
            == config.TRAINING_XP_BY_LEVEL[1] * config.TRAINING_XP_MULT_UPGRADED)


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
    state["day"] += 4                                  # offered jobs never expire
    assert story.check_deadlines(state, content["story"]) == []
    story.accept(state, quest)                         # M13: clock starts here
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
    assert story.days_left(state, quest) is None       # re-offered: re-accept
    story.accept(state, quest)
    assert story.days_left(state, quest) == 3          # fresh deadline


def test_reoffered_scout_restarts_clean(content):
    # A scout quest that fails its deadline must not keep partial progress
    # through the re-offer (review fix, M13).
    state = fresh_run(content)
    scout = dict(next(q for q in content["story"] if q["kind"] == "scout"),
                 deadline_days=2)
    chain = [scout]
    story.init(state, chain)
    story.accept(state, scout)
    story.do_scout(state, scout, 0, chain)
    assert story.scouted(state, scout) == [0]
    state["day"] += 3                                  # blow the deadline
    assert any("Mission failed" in m
               for m in story.check_deadlines(state, chain))
    state["day"] += 2                                  # cooldown over
    assert any("back on the board" in m
               for m in story.check_deadlines(state, chain))
    assert story.scouted(state, scout) == []           # progress wiped


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


def _train_everyone_to(state, content, rank):
    """Grant enough attribute XP that every roster hero sits at `rank`."""
    for hero_id, entry in state["roster"].items():
        boosts = content["characters"][hero_id]["boosts"]
        for attribute in config.ATTRIBUTES:
            while attrs.rank(entry, attribute) < rank:
                need = attrs.xp_for_rank(
                    entry.get("trained_ranks", {}).get(attribute, 0) + 1)
                attrs.add_training_xp(boosts, entry, attribute, need)


def test_full_ch1_ch2_playthrough(content):
    # M15: the two boss fights are real walls now — the Siege is a coin flip
    # at rank 1 and Crossbones is a struggle below rank 2, so the intended
    # line of play is "train between chapters", which this run models.
    state = fresh_run(content)
    battles = 0
    while not story.story_complete(state, content["story"]):
        quest_now = story.current_quest(state, content["story"])
        if quest_now["id"] == "ch1_siege":
            _train_everyone_to(state, content, 2)
        elif quest_now["id"] == "ch2_crossbones":
            _train_everyone_to(state, content, 3)
        assert state["day"] < 28, "run must finish well inside Issue 1"
        quest = story.current_quest(state, content["story"])
        if not story.is_accepted(state, quest):         # M13: take the job
            story.accept(state, quest)
        if quest["kind"] == "scout":
            done = story.scouted(state, quest)
            index = next(i for i in range(len(quest["scout_points"]))
                         if i not in done)
            if not story.do_scout(state, quest, index, content["story"])["ok"]:
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
    # 5 missions + 2 scout quests: a handful of in-game days -> well under
    # 45 real minutes of play (M6 AC)
    assert state["day"] <= 10
