"""M9 systems: ambushes, energy speed penalty, party swaps, passive
assignments + atrophy."""

import random

import pytest

from game import config, data_loader
from game.combat import formulas
from game.core import save
from game.hub import field, party, passive


@pytest.fixture(scope="module")
def content():
    return data_loader.load_all()


def entry():
    return {"trained_ranks": {}, "attribute_xp": {}, "perks": [],
            "perk_choices": {}, "energy": 100, "unspent_xp": 0}


def state_with(content, roster_ids, party_ids):
    state = save.new_game_state()
    state["path"] = "avengers"
    for hid in roster_ids:
        state["roster"][hid] = entry()
    state["party"] = list(party_ids)
    return state


# --- ambushes (3.1) ---

def test_ambush_chance_scales_with_danger_and_small_parties():
    assert field.ambush_chance(1, 4) < field.ambush_chance(3, 4)
    assert (field.ambush_chance(3, 1) > field.ambush_chance(3, 2)
            > field.ambush_chance(3, 3) > field.ambush_chance(3, 4))


def test_ambush_only_when_outnumbered():
    rng = random.Random(7)
    for party_size in (1, 2, 3, 4):
        for _ in range(300):
            squad = field.roll_ambush(3, party_size, rng)
            if squad is not None:
                assert len(squad) > party_size
                assert len(squad) <= config.AMBUSH_MAX_SIZE


def test_full_party_can_still_be_ambushed_by_bigger_squads():
    rng = random.Random(3)
    sizes = {len(s) for _ in range(3000)
             if (s := field.roll_ambush(3, 4, rng)) is not None}
    assert sizes and all(5 <= n <= 8 for n in sizes)


# --- energy speed penalty (3.2) ---

def test_energy_penalty_tiers():
    assert formulas.energy_penalty_tiers(1.0) == 0
    assert formulas.energy_penalty_tiers(0.60) == 0
    assert formulas.energy_penalty_tiers(0.59) == 1
    assert formulas.energy_penalty_tiers(0.50) == 1
    assert formulas.energy_penalty_tiers(0.49) == 2
    assert formulas.energy_penalty_tiers(0.31) == 3
    assert formulas.energy_penalty_tiers(0.05) == 6
    assert formulas.energy_penalty_tiers(0.0) == config.EN_PENALTY_MAX_TIERS


# --- party swaps (5) ---

def test_swap_transfers_task_and_checks_requirement(content):
    state = state_with(content, ["iron_man", "captain_america", "ant_man"],
                       ["captain_america", "ant_man"])
    ok, _ = passive.assign(content, state, "iron_man", "support")   # INT 3+
    assert ok
    # Cap (INT boost 3 -> effective 2.58) can't cover support -> blocked
    ok, reason = party.can_swap_in(content, state, "iron_man", "captain_america")
    assert not ok and "intelligence 3+" in reason
    # Ant-Man (INT boost 5) can -> allowed, and he inherits the task
    ok, message = party.swap(content, state, "iron_man", "ant_man")
    assert ok and "takes over their task" in message
    assert state["party"] == ["captain_america", "iron_man"]
    assert state["roster"]["ant_man"]["assignment"]["kind"] == "support"
    assert "assignment" not in state["roster"]["iron_man"]


def test_party_size_cap(content):
    state = state_with(content, ["iron_man", "captain_america", "ant_man", "hulk"],
                       ["iron_man", "captain_america", "ant_man", "hulk"])
    state["roster"]["hulk"] = entry()
    ok, message = party.add_to_party(content, state, "hulk")
    assert not ok                                      # full at PARTY_SIZE_MAX


# --- passive assignments + atrophy (2, 2.1) ---

def test_passive_train_gains_and_requirement(content):
    state = state_with(content, ["iron_man", "captain_america"],
                       ["captain_america"])
    ok, _ = passive.assign(content, state, "iron_man", "train", "agility")
    assert ok
    passive.process_day(content, state)
    assert state["roster"]["iron_man"]["attribute_xp"]["agility"] == 40
    # requirement rejection: Cap can't take support
    ok, reason = passive.assign(content, state, "captain_america", "support")
    assert not ok and "intelligence 3+" in reason


def test_passive_support_pays_and_socialize_bonds(content):
    state = state_with(content, ["iron_man", "captain_america", "ant_man"],
                       ["captain_america"])
    passive.assign(content, state, "iron_man", "support")
    passive.assign(content, state, "ant_man", "socialize")
    messages = passive.process_day(content, state)
    assert state["credits"] == 25
    assert any("spent the day with" in m for m in messages)
    assert any(b["points"] == 15 for b in state["bonds"].values())


def test_atrophy_after_grace_days(content):
    state = state_with(content, ["iron_man", "captain_america"],
                       ["captain_america"])
    im = state["roster"]["iron_man"]
    im["attribute_xp"]["strength"] = 30
    im["trained_ranks"]["speed"] = 1
    im["attribute_xp"]["speed"] = 0
    passive.assign(content, state, "iron_man", "train", "agility")
    for _ in range(2):                                 # grace period
        passive.process_day(content, state)
    assert im["attribute_xp"]["strength"] == 30        # untouched so far
    passive.process_day(content, state)                # day 3: decay starts
    assert im["attribute_xp"]["strength"] == 10        # -20
    # the worked attribute keeps growing: 3 days x 40 XP clears rank 1, whose
    # cost is boost-weighted for this hero (M16b)
    from game.progression import attributes as attrs
    boosts = content["characters"]["iron_man"]["boosts"]
    agility_rank_1 = attrs.xp_for_rank(1, boosts["agility"])
    assert im["trained_ranks"]["agility"] == 1
    assert im["attribute_xp"]["agility"] == 120 - agility_rank_1
    passive.process_day(content, state)                # day 4
    passive.process_day(content, state)                # day 5: strength bank dry
    assert im["attribute_xp"]["strength"] == 0
    # speed rank 1 eventually breaks down into a refunded, draining bank
    refund = attrs.xp_for_rank(1, boosts["speed"])
    for _ in range(refund // config.ATROPHY_XP_PER_DAY + 2):
        passive.process_day(content, state)
    assert im["trained_ranks"]["speed"] == 0


def test_idle_heroes_also_atrophy(content):
    state = state_with(content, ["iron_man", "captain_america"],
                       ["captain_america"])
    im = state["roster"]["iron_man"]
    im["attribute_xp"]["strength"] = 50
    for _ in range(3):
        passive.process_day(content, state)
    assert im["attribute_xp"]["strength"] == 30        # idle decay after grace
