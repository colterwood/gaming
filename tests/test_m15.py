"""M15 systems: the rank/boost model, signature spread attacks, ultimate
charge carrying between battles, the ambush size table, and hidden board
requirements with Coulson's refusals."""

import random

import pytest

from game import config, data_loader
from game.combat import formulas
from game.combat.engine import BattleEngine
from game.combat.entities import Combatant, make_enemy_group
from game.core import save
from game.hub import dispatch, field, requirements
from game.progression import attributes as attrs
from game.social import bonds


class NoLuck:
    def randint(self, a, b):
        return a

    def uniform(self, a, b):
        return 99.0

    def random(self):
        return 0.99


@pytest.fixture(scope="module")
def content():
    return data_loader.load_all()


def entry(**ranks):
    e = {"trained_ranks": {}, "attribute_xp": {}, "perks": [],
         "perk_choices": {}, "energy": 100}
    for attribute, rank in ranks.items():
        e["trained_ranks"][attribute] = rank - config.RANK_START
    return e


def state_with(roster_ids, party_ids, **kw):
    state = save.new_game_state()
    state["path"] = "avengers"
    for hid in roster_ids:
        state["roster"][hid] = entry()
    state["party"] = list(party_ids)
    state.update(kw)
    return state


def task_by_id(content, task_id):
    return next(t for t in content["assignments"] if t["id"] == task_id)


# --- rank + boost model ---

def test_everyone_starts_at_rank_one(content):
    for char in content["characters"].values():
        if char["recruit"]["method"] == "npc":
            continue
        e = entry()
        for attribute in config.ATTRIBUTES:
            assert attrs.rank(e, attribute) == 1
            assert 1 <= char["boosts"][attribute] <= config.BOOST_MAX


def test_boost_shows_at_rank_one_and_still_shows_at_rank_ten(content):
    im = content["characters"]["iron_man"]["boosts"]       # strength boost 6
    cap = content["characters"]["captain_america"]["boosts"]   # strength boost 2
    low, high = entry(), entry(strength=config.RANK_MAX)
    # talent is visible immediately...
    assert (attrs.effective_rank(im, low, "strength")
            > attrs.effective_rank(cap, low, "strength"))
    # ...and survives both heroes maxing the rank
    assert (attrs.effective_rank(im, high, "strength")
            > attrs.effective_rank(cap, high, "strength"))
    # and Cap keeps the edge where HIS boost is higher (agility 5 vs 3)
    assert (attrs.effective_rank(cap, high, "agility")
            > attrs.effective_rank(im, high, "agility"))


def test_effective_rank_formula():
    # (rank + boost*0.5) * (1 + boost*0.01)
    assert formulas.effective_rank(1, 0) == 1
    assert formulas.effective_rank(10, 0) == 10
    assert formulas.effective_rank(1, 6) == pytest.approx(4.24)
    assert formulas.effective_rank(10, 6) == pytest.approx(13.78)


def test_enemies_use_their_flat_grid(content):
    grunt = Combatant(content["enemies"]["hydra_grunt"])
    assert grunt.rank("strength") == 2          # no boosts, no rank ladder
    assert grunt.boosts == {}


def test_training_ceiling_is_rank_ten(content):
    boosts = content["characters"]["captain_america"]["boosts"]
    e = entry()
    for _ in range(50):
        if not attrs.can_train(boosts, e, "speed"):
            break
        attrs.add_training_xp(boosts, e, "speed", 5000)
    assert attrs.rank(e, "speed") == config.RANK_MAX
    assert e["trained_ranks"]["speed"] == config.TRAINED_MAX


# --- M16b: training with the grain is cheaper ---

def test_boost_weighted_rank_costs(content):
    im = content["characters"]["iron_man"]["boosts"]     # STR 6, AGI 3
    cap = content["characters"]["captain_america"]["boosts"]  # STR 2, AGI 5
    # Iron Man climbs Strength cheaper than Cap does...
    assert (attrs.xp_for_rank(5, im["strength"])
            < attrs.xp_for_rank(5, cap["strength"]))
    # ...and Cap climbs Agility cheaper than Iron Man does.
    assert (attrs.xp_for_rank(5, cap["agility"])
            < attrs.xp_for_rank(5, im["agility"]))
    # boost 5 is the neutral point, and the tax/discount is bounded
    assert attrs.xp_for_rank(5, 5) == config.XP_TO_NEXT_RANK[5]
    assert attrs.boost_weight(0) == pytest.approx(1.5)
    assert attrs.boost_weight(config.BOOST_MAX) == pytest.approx(0.8)


def test_boost_weighting_applies_when_ranking_up(content):
    boosts = content["characters"]["hulk"]["boosts"]     # STR 7, SPD 2
    strong, slow = entry(), entry()
    cheap = attrs.xp_for_rank(1, boosts["strength"])
    attrs.add_training_xp(boosts, strong, "strength", cheap)
    assert strong["trained_ranks"]["strength"] == 1      # exactly enough
    attrs.add_training_xp(boosts, slow, "speed", cheap)
    assert slow["trained_ranks"].get("speed", 0) == 0    # not enough for Speed
    assert slow["attribute_xp"]["speed"] == cheap


def test_mastery_is_reachable_inside_a_campaign(content):
    # M16b sanity: the whole roster should master in the low hundreds of
    # days, not the ~490 the pure-doubling curve implied.
    for char in content["characters"].values():
        if char["recruit"]["method"] == "npc":
            continue
        total = sum(attrs.xp_for_rank(level, char["boosts"][attribute])
                    for attribute in config.ATTRIBUTES
                    for level in range(1, config.TRAINED_MAX + 1))
        # 0.5 XP per training minute x 1200 waking minutes = 600 XP/day ceiling
        assert 20_000 < total < 70_000, (char["id"], total)


# --- signature spread attacks ---

def _spread_hits(content, hero_id, ability_id, enemy_count, rng, target_index=2):
    """Ids the ability actually reached. A target that dodges still counts
    as reached — it emits a dodge event instead of a damage one."""
    heroes = [Combatant(content["characters"][hero_id], is_hero=True)]
    enemies = make_enemy_group([content["enemies"]["hydra_grunt"]] * enemy_count)
    engine = BattleEngine(heroes, enemies, rng=rng, items_data=content["items"])
    engine.round_order = [heroes[0]]
    engine._turn_index = 0
    engine.begin_turn()
    events = engine.take_turn({"type": "ability", "ability_id": ability_id,
                               "target_id": enemies[target_index].id})
    return [e["target"] for e in events if e["kind"] in ("damage", "dodge")]


def test_ant_man_special_hits_three_distinct_targets(content):
    hits = _spread_hits(content, "ant_man", "pym_barrage", 5, random.Random(3))
    assert len(hits) == 3
    assert len(set(hits)) == 3                 # all distinct
    assert "hydra_grunt_3" in hits             # the chosen target is included


def test_iron_man_special_hits_target_and_neighbours(content):
    hits = _spread_hits(content, "iron_man", "unibeam", 5, random.Random(3))
    # target is index 2 -> neighbours are index 1 and 3
    assert sorted(hits) == ["hydra_grunt_2", "hydra_grunt_3", "hydra_grunt_4"]


def test_cap_special_hits_three_or_four_distinct(content):
    seen = set()
    for seed in range(30):
        hits = _spread_hits(content, "captain_america", "shield_throw", 6,
                            random.Random(seed))
        assert len(set(hits)) == len(hits)     # never repeats a target
        assert "hydra_grunt_3" in hits
        seen.add(len(hits))
    assert seen <= {3, 4} and len(seen) == 2   # coin flip between 2 and 3 extras


def test_spread_never_exceeds_living_enemies(content):
    hits = _spread_hits(content, "ant_man", "pym_barrage", 2, random.Random(1),
                        target_index=0)
    assert len(hits) == 2                      # only two bodies to hit
    solo = _spread_hits(content, "ant_man", "pym_barrage", 1, random.Random(1),
                        target_index=0)
    assert len(solo) == 1


# --- review fixes: floats must never reach HP or the screen ---

def test_enemy_heal_keeps_hp_integral(content):
    # M15 review: ranks became floats, so a rank-scaled heal was turning a
    # combatant's HP into 55.0 and rendering "55.0/110" for the rest of the
    # fight. This is the Crossbones medic in normal play.
    heroes = [Combatant(content["characters"]["iron_man"], is_hero=True)]
    enemies = make_enemy_group([content["enemies"]["hydra_medic"],
                                content["enemies"]["hydra_grunt"]])
    engine = BattleEngine(heroes, enemies, rng=NoLuck(),
                          items_data=content["items"])
    medic, grunt = enemies
    grunt.hp = 40
    engine.round_order = [medic]
    engine._turn_index = 0
    engine.begin_turn()
    events = engine.take_turn({"type": "ability", "ability_id": "field_stim",
                               "target_id": grunt.id})
    heal = next(e for e in events if e["kind"] == "heal")
    assert isinstance(heal["amount"], int)
    assert isinstance(grunt.hp, int)
    grunt.take_damage(12)
    assert isinstance(grunt.hp, int)                # and stays integral


def test_training_labels_show_rank_over_ten_not_seven(content):
    import pygame
    from game.hub.tower import HubScene
    pygame.init()
    scene = HubScene(content)
    scene.train_hero_id = "iron_man"
    state = save.new_game_state()
    state["roster"]["iron_man"] = entry()
    labels = scene._train_attr_labels(state)
    joined = " | ".join(labels)
    assert "/7" not in joined                       # the old ceiling is gone
    assert f"/{config.RANK_MAX}" in joined
    assert "0000000" not in joined                  # no raw float noise
    # Iron Man: durability rank 1, boost 5 -> combat 3.7
    assert any(l.startswith("Durability  1/10 (3.7)") for l in labels), labels


def test_rank_up_message_is_readable(content):
    from game.hub import activities
    state = save.new_game_state()
    state["roster"]["iron_man"] = entry()
    state["roster"]["captain_america"] = entry()
    state["party"] = ["iron_man", "captain_america"]
    activities.start_training(state, content, "iron_man", "strength")
    state["roster"]["iron_man"]["attribute_xp"]["strength"] = 100
    messages = activities.finish_due_training(state, content, force=True)
    text = " ".join(messages)
    if "rank up" in text:
        assert "0000000" not in text                # no raw float noise
        assert f"/{config.RANK_MAX}" in text


# --- ultimate charge carries between battles ---

def test_ult_charge_carries_in(content):
    hero = Combatant(content["characters"]["iron_man"], is_hero=True,
                     ult_charge=80)
    assert hero.ult_charge == 80
    assert not hero.ult_ready()
    hero = Combatant(content["characters"]["iron_man"], is_hero=True,
                     ult_charge=100)
    assert hero.ult_ready()                    # walked in with a loaded ult
    over = Combatant(content["characters"]["iron_man"], is_hero=True,
                     ult_charge=500)
    assert over.ult_charge == config.ULT_CHARGE_MAX     # clamped


# --- ambush size table ---

def test_ambush_always_outnumbers_and_respects_the_cap():
    rng = random.Random(7)
    for party_size in (1, 2, 3, 4):
        for _ in range(400):
            size = field.ambush_size(party_size, rng)
            assert size > party_size
            assert size <= field.squad_cap(party_size)      # M20
            assert size <= config.AMBUSH_MAX_SIZE


def test_ambush_size_distribution_matches_the_table():
    rng = random.Random(11)
    counts = {}
    for _ in range(20000):
        extra = field.ambush_size(4, rng) - 4     # party 4: nothing clamps
        counts[extra] = counts.get(extra, 0) + 1
    assert counts[1] / 20000 == pytest.approx(0.50, abs=0.02)
    assert counts[2] / 20000 == pytest.approx(0.35, abs=0.02)
    assert counts[3] / 20000 == pytest.approx(0.10, abs=0.02)
    assert counts[4] / 20000 == pytest.approx(0.05, abs=0.02)


def test_small_party_ambush_is_capped_by_party_size():
    # M20 replaced the "never more than double" rule with an explicit
    # ceiling per party size: 4 on a lone hero, 6 on a pair.
    rng = random.Random(5)
    assert max(field.ambush_size(1, rng) for _ in range(400)) == 4
    assert max(field.ambush_size(2, rng) for _ in range(400)) == 6


# --- hidden board requirements + Coulson refusals ---

def test_open_tasks_take_anyone(content):
    state = state_with(["iron_man", "captain_america"],
                       ["iron_man", "captain_america"])
    for task_id in ("sweep_hangar", "inventory_armory", "escort_convoy"):
        task = task_by_id(content, task_id)
        ok, _ = requirements.check(content, state, task,
                                   ["captain_america"][:task["heroes"]] or ["iron_man"])
        assert ok, task_id


def test_intelligence_gate_accepts_boost_or_rank(content):
    # M16: the boost thresholds were raised so these gates actually bite.
    # Iron Man (INT boost 5) walks in; Cap (boost 3) has to train first.
    state = state_with(["iron_man", "captain_america"], ["iron_man"])
    calibrate = task_by_id(content, "calibrate_sensors")   # INT 2 OR boost 4+
    assert requirements.check(content, state, calibrate, ["iron_man"])[0]
    ok, reason = requirements.check(content, state, calibrate,
                                    ["captain_america"])
    assert not ok and "Intelligence" in reason
    debug = task_by_id(content, "debug_jarvis")            # INT 2 OR boost 5+
    assert requirements.check(content, state, debug, ["iron_man"])[0]
    assert not requirements.check(content, state, debug, ["captain_america"])[0]
    # one rank of training opens both for Cap
    state["roster"]["captain_america"] = entry(intelligence=2)
    assert requirements.check(content, state, calibrate, ["captain_america"])[0]
    assert requirements.check(content, state, debug, ["captain_america"])[0]


def test_decrypt_cache_needs_real_intelligence(content):
    state = state_with(["captain_america"], ["captain_america"])
    task = task_by_id(content, "decrypt_cache")
    # Cap: INT rank 1, boost 3 -> fails rank 3 / (2 and boost 3) / (1 and boost 6)
    ok, reason = requirements.check(content, state, task, ["captain_america"])
    assert not ok and "Intelligence" in reason
    state["roster"]["captain_america"] = entry(intelligence=3)
    ok, _ = requirements.check(content, state, task, ["captain_america"])
    assert ok                                   # plain rank 3 clears it
    # Iron Man's INT boost 5 lets him in a whole rank earlier
    state["roster"]["iron_man"] = entry(intelligence=2)
    assert requirements.check(content, state, task, ["iron_man"])[0]


def test_deep_recon_needs_rank_two_everywhere(content):
    state = state_with(["iron_man"], ["iron_man"])
    task = task_by_id(content, "deep_recon")
    ok, reason = requirements.check(content, state, task, ["iron_man"])
    assert not ok and "across the board" in reason
    state["roster"]["iron_man"] = entry(**{a: 2 for a in config.ATTRIBUTES})
    ok, _ = requirements.check(content, state, task, ["iron_man"])
    assert ok


def test_bond_gated_tasks(content):
    state = state_with(["iron_man", "captain_america"], ["iron_man"])
    liaison = task_by_id(content, "shield_liaison")
    ok, reason = requirements.check(content, state, liaison, ["iron_man"])
    assert not ok and "know you better" in reason
    bonds.add_points(state, "coulson", config.BOND_POINTS_PER_LEVEL)
    ok, _ = requirements.check(content, state, liaison, ["iron_man"])
    assert ok


def test_refusal_comes_from_coulson(content):
    state = state_with(["captain_america", "iron_man"],
                       ["captain_america", "iron_man"])
    task = task_by_id(content, "decrypt_cache")
    ok, message = dispatch.send(content, state, task, ["captain_america"])
    assert not ok
    assert message.startswith("COULSON:")
    assert state["roster"]["captain_america"].get("dispatch") is None


def test_every_sent_hero_must_qualify(content):
    state = state_with(["iron_man", "captain_america", "ant_man"],
                       ["iron_man", "captain_america", "ant_man"])
    task = task_by_id(content, "train_recruits")     # needs rank/boost muscle
    # M16: at rank 1 neither Cap nor Ant-Man is muscular enough
    ok, reason = requirements.check(content, state, task,
                                    ["ant_man", "captain_america"])
    assert not ok and ("Ant-Man" in reason or "Captain America" in reason)
    # train ONE of them and the crew is still refused - every hero must clear
    state["roster"]["ant_man"] = entry(agility=3)
    ok, reason = requirements.check(content, state, task,
                                    ["ant_man", "captain_america"])
    assert not ok and "Captain America" in reason
    state["roster"]["captain_america"] = entry(agility=3)
    assert requirements.check(content, state, task,
                              ["ant_man", "captain_america"])[0]


# --- Hulk's one-shot bond job ---

def _days_posted(state, task, days=200):
    posted = 0
    for i in range(days):
        state["issue"], state["day"] = 1 + i // 28, 1 + i % 28
        posted += requirements.gate_open(state, task)
    state["issue"], state["day"] = 1, 1
    return 100.0 * posted / days


def test_hulk_task_posting_chance_warms_with_his_bond(content):
    # M16: 5% of days at Bond 0, 25% at Bond 1, 80% at Bond 2+
    state = state_with(["iron_man", "captain_america"],
                       ["iron_man", "captain_america"])
    task = task_by_id(content, "hulk_smash_therapy")
    assert task["bond"] == 600 and task["once"] is True
    assert _days_posted(state, task) == 0               # Hulk hasn't shown up
    state["story_flags"]["hulk_arrived"] = True
    assert _days_posted(state, task) == pytest.approx(5, abs=4)
    bonds.add_points(state, "hulk", config.BOND_POINTS_PER_LEVEL)
    assert _days_posted(state, task) == pytest.approx(25, abs=8)
    bonds.add_points(state, "hulk", config.BOND_POINTS_PER_LEVEL)
    assert _days_posted(state, task) == pytest.approx(80, abs=8)
    # the roll is stable within a day - reopening the board can't reroll it
    assert len({requirements.gate_open(state, task) for _ in range(20)}) == 1


def test_hulk_task_pays_600_bond_once(content):
    state = state_with(["iron_man", "captain_america"],
                       ["iron_man", "captain_america"])
    task = task_by_id(content, "hulk_smash_therapy")
    state["story_flags"]["hulk_arrived"] = True
    ok, message = dispatch.send(content, state, task, ["iron_man"])
    assert ok, message
    dispatch.process_day(content, state)
    assert state["bonds"]["hulk"]["points"] == 600     # most of the way to 4
    assert "hulk_smash_therapy" in state["completed_tasks"]
    assert _days_posted(state, task) == 0              # never posted again
