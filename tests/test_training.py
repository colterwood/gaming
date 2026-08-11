"""M4: attribute XP thresholds, trained ranks in combat, perks (§6.3)."""

import pytest

from game import config, data_loader
from game.combat.engine import BattleEngine
from game.combat.entities import Combatant, make_enemy_group
from game.core import save
from game.hub import activities
from game.progression import attributes as attrs
from game.progression import mastery


class NoLuckRng:
    """No dodges, no crits, minimal initiative rolls."""

    def randint(self, a, b):
        return a

    def uniform(self, a, b):
        return 99.0


@pytest.fixture(scope="module")
def content():
    return data_loader.load_all()


def entry():
    return {"trained_ranks": {}, "attribute_xp": {}, "perks": [],
            "perk_choices": {}, "energy": 100}


def game_state(content):
    state = save.new_game_state()
    for hid in ("iron_man", "captain_america"):
        state["roster"][hid] = entry()
    state["party"] = ["iron_man", "captain_america"]
    return state


# --- XP thresholds (§6.3): rank N costs 100 × N ---

def test_xp_for_rank_thresholds():
    # M16: the cost to climb grows 1.5x per level, and M16b scales it by the
    # hero's innate talent for that attribute.
    assert [attrs.xp_for_rank(n, 5) for n in range(1, 10)] == [
        100, 150, 225, 340, 510, 760, 1140, 1710, 2560]     # boost 5 = neutral
    assert attrs.boost_weight(5) == pytest.approx(1.0)
    assert attrs.boost_weight(7) < 1.0 < attrs.boost_weight(0)
    # talent is a real discount, no talent is a real tax
    assert attrs.xp_for_rank(9, 7) == round(2560 * 0.8)
    assert attrs.xp_for_rank(9, 0) == round(2560 * 1.5)


def test_rank_up_consumes_exact_xp(content):
    cap = content["characters"]["captain_america"]     # strength boost 2
    e = entry()
    # M16b: Cap has little Strength talent, so his first rank costs 1.3x
    cost = attrs.xp_for_rank(1, cap["boosts"]["strength"])
    assert cost == 130
    result = attrs.add_training_xp(cap["boosts"], e, "strength", cost - 1)
    assert result["ranks_gained"] == [] and result["xp_banked"] == cost - 1
    result = attrs.add_training_xp(cap["boosts"], e, "strength", 1)
    assert result["ranks_gained"] == [1]
    assert result["rank"] == 2                          # rank 1 -> 2
    # effective = (2 + boost 2 * 0.5) * 1.02
    assert result["effective_rank"] == pytest.approx(3.06)
    assert result["xp_banked"] == 0


def test_multi_rank_overflow(content):
    cap = content["characters"]["captain_america"]
    boosts = cap["boosts"]
    e = entry()
    two = (attrs.xp_for_rank(1, boosts["strength"])
           + attrs.xp_for_rank(2, boosts["strength"]))
    result = attrs.add_training_xp(boosts, e, "strength", two + 50)
    assert result["ranks_gained"] == [1, 2]
    assert result["xp_banked"] == 50


def test_rank_tops_out_at_ten_and_xp_then_banks(content):
    # M15: rank runs 1..10 (trained 0..9); the innate boost stacks ON TOP,
    # so the combat-effective value legitimately exceeds 10.
    cap = content["characters"]["captain_america"]     # strength boost 2
    e = entry()
    attrs.add_training_xp(cap["boosts"], e, "strength", sum(
        attrs.xp_for_rank(n) for n in range(1, config.TRAINED_MAX + 1)))
    assert e["trained_ranks"]["strength"] == config.TRAINED_MAX
    assert attrs.rank(e, "strength") == config.RANK_MAX
    assert attrs.effective_rank(cap["boosts"], e, "strength") == pytest.approx(11.22)
    assert not attrs.can_train(cap["boosts"], e, "strength")
    banked_before = e["attribute_xp"]["strength"]
    result = attrs.add_training_xp(cap["boosts"], e, "strength", 500)
    assert result["ranks_gained"] == []                # capped: XP just banks
    assert e["attribute_xp"]["strength"] == banked_before + 500


# --- Perk tiers at trained ranks 3 and 6 ---

def test_perk_pending_at_3_and_6(content):
    im = content["characters"]["iron_man"]              # agility boost 3
    e = entry()
    to = lambda a, b: sum(attrs.xp_for_rank(n) for n in range(a, b))
    attrs.add_training_xp(im["boosts"], e, "agility", to(1, 4))  # trained 1..3
    assert attrs.pending_perk_tier(e, "agility") == 3
    result = attrs.choose_perk(e, "agility", 3, "precision", content["perks"])
    assert result["ok"]
    assert attrs.pending_perk_tier(e, "agility") is None
    attrs.add_training_xp(im["boosts"], e, "agility", to(4, 7))  # trained 4..6
    assert e["trained_ranks"]["agility"] == 6
    assert attrs.pending_perk_tier(e, "agility") == 6            # tier 6 reachable
    attrs.choose_perk(e, "agility", 6, "killer_instinct", content["perks"])
    assert attrs.pending_perk_tier(e, "agility") is None


def test_perk_choice_validation(content):
    e = entry()
    e["trained_ranks"]["strength"] = 3
    bad = attrs.choose_perk(e, "strength", 3, "blur", content["perks"])
    assert not bad["ok"]
    good = attrs.choose_perk(e, "strength", 3, "haymaker", content["perks"])
    assert good["ok"]
    again = attrs.choose_perk(e, "strength", 3, "power_through", content["perks"])
    assert not again["ok"]                              # tier already chosen


def test_perk_effects_sum(content):
    e = entry()
    e["perk_choices"] = {"strength:3": "haymaker", "agility:3": "precision",
                         "speed:6": "momentum"}
    fx = attrs.perk_effects(e, content["perks"])
    assert fx == {"basic_damage_pct": 10, "crit_bonus": 8}   # 4 + 4 crit


# --- Session XP tiers: 40 basic / 80 upgraded / 120 event ---

def test_session_xp_tiers(content):
    # M16: the base yield comes from the level table, the facility multiplies it
    state = game_state(content)
    base = config.TRAINING_XP_BY_LEVEL[1]               # 25 at level 1
    assert attrs.session_xp(state, content["calendar"], 1) == base
    state["story_flags"]["training_upgraded"] = True
    assert attrs.session_xp(state, content["calendar"], 1) == base * 2
    state["day"] = 12                                   # S.H.I.E.L.D. Supply Drop
    assert attrs.session_xp(state, content["calendar"], 1) == base * 3
    # and it scales with the level being trained
    assert attrs.session_xp(state, content["calendar"], 5) == \
        config.TRAINING_XP_BY_LEVEL[5] * 3


def test_training_lockout_grants_xp_on_completion(content):
    # M12: training is a lockout — EN up front, XP when the clock runs out.
    state = game_state(content)
    result = activities.start_training(state, content, "captain_america", "strength")
    assert result["ok"] and result["minutes"] == 50             # M16: level 1 = 50 min
    cap = state["roster"]["captain_america"]
    assert cap["energy"] == 80                          # trainee pays 20 EN now
    assert state["roster"]["iron_man"]["energy"] == 100  # teammates untouched
    assert state["party"] == ["iron_man"]               # off the team
    assert cap["attribute_xp"] == {}                    # nothing granted yet
    # too early: nothing completes
    assert activities.finish_due_training(state, content) == []
    state["time_minutes"] += 50
    messages = activities.finish_due_training(state, content)
    assert len(messages) == 1 and "Strength" in messages[0]
    assert cap["attribute_xp"]["strength"] == config.TRAINING_XP_BY_LEVEL[1]
    assert "training" not in cap
    assert state["party"] == ["iron_man", "captain_america"]    # auto-rejoin


def test_training_costs_scale_with_rank(content):
    # M16: EN still linear, minutes from the table — level 8/9 sessions run
    # longer than a single 1200-minute day.
    assert activities.training_cost(1) == (20, 50)
    assert activities.training_cost(2) == (25, 70)
    assert activities.training_cost(7) == (50, 800)
    assert activities.training_cost(9) == (60, 2400)


def test_a_session_grants_its_own_yield_and_nothing_else(content):
    # M21: the battle-XP bank is gone, so a session is worth exactly the
    # facility-multiplied table value - no top-up, nothing reserved.
    state = game_state(content)
    cap = state["roster"]["captain_america"]
    session = config.TRAINING_XP_BY_LEVEL[1]            # 25 at level 1
    activities.start_training(state, content, "captain_america", "strength")
    assert cap.get("unspent_xp", 0) == 0        # nothing reserved from a bank
    assert cap["training"]["xp"] == session
    assert "banked" not in cap["training"]
    activities.finish_due_training(state, content, force=True)
    assert cap["attribute_xp"]["strength"] == session
    assert cap["trained_ranks"].get("strength", 0) == 0


def test_training_maxed_attribute_refused_without_cost(content):
    state = game_state(content)
    state["roster"]["iron_man"]["trained_ranks"]["intelligence"] = config.TRAINED_MAX
    result = activities.start_training(state, content, "iron_man", "intelligence")
    assert not result["ok"]
    assert state["roster"]["iron_man"]["energy"] == 100  # nothing spent
    assert state["party"] == ["iron_man", "captain_america"]


def test_training_last_party_member_refused(content):
    state = game_state(content)
    state["party"] = ["captain_america"]
    result = activities.start_training(state, content, "captain_america", "strength")
    assert not result["ok"] and "stay on the team" in result["message"]


def test_training_is_party_only(content):
    # M12 review fix: the perk-chooser fall-through must not let a benched
    # hero start a rack session.
    state = game_state(content)
    state["party"] = ["iron_man"]                       # cap benched
    result = activities.start_training(state, content, "captain_america", "strength")
    assert not result["ok"] and "isn't on the team" in result["message"]
    assert "training" not in state["roster"]["captain_america"]


def test_training_refused_when_it_would_zero_the_trainee(content):
    state = game_state(content)
    state["roster"]["captain_america"]["energy"] = 20   # rank-1 cost exactly
    result = activities.start_training(state, content, "captain_america", "strength")
    assert not result["ok"] and "exhausted" in result["message"]
    assert state["roster"]["captain_america"]["energy"] == 20


def test_training_completed_in_zone_waits_at_tower(content):
    # M12 review fix: a session ending while the team is out in a zone must
    # not teleport the hero into the field.
    state = game_state(content)
    activities.start_training(state, content, "captain_america", "strength")
    state["time_minutes"] += 50
    messages = activities.finish_due_training(state, content, rejoin=False)
    assert any("Waiting at the tower" in m for m in messages)
    assert state["party"] == ["iron_man"]               # benched, not fielded
    assert "training" not in state["roster"]["captain_america"]
    assert (state["roster"]["captain_america"]["attribute_xp"]["strength"]
            == config.TRAINING_XP_BY_LEVEL[1])


def test_training_locks_out_everything(content):
    from game.hub import dispatch, party, passive
    state = game_state(content)
    activities.start_training(state, content, "captain_america", "strength")
    assert not party.add_to_party(content, state, "captain_america")[0]
    assert not passive.assign(content, state, "captain_america", "socialize")[0]
    task = next(t for t in content["assignments"] if t["heroes"] == 1)
    assert not dispatch.send(content, state, task, ["captain_america"])[0]
    # atrophy never touches a hero mid-training
    passive.process_day(content, state)
    assert state["roster"]["captain_america"]["idle_days"] == 0


# --- M4 acceptance: Cap Strength to rank 3, pick Haymaker, damage changes ---

def test_trained_ranks_and_perk_change_battle_damage(content):
    grunt = content["enemies"]["hydra_grunt"]

    def cap_hit(trained_ranks, perk_effects):
        cap = Combatant(content["characters"]["captain_america"],
                        trained_ranks=trained_ranks, perk_effects=perk_effects,
                        is_hero=True)
        engine = BattleEngine([cap], make_enemy_group([grunt]), rng=NoLuckRng(),
                              items_data=content["items"])
        engine.round_order = [cap]
        engine._turn_index = 0
        engine.begin_turn()
        events = engine.take_turn({"type": "ability", "ability_id": "shield_strike",
                                   "target_id": "hydra_grunt_1"})
        return next(e["amount"] for e in events if e["kind"] == "damage")

    # Baseline: strength 2 -> 12 + 8 - 4 = 16
    assert cap_hit({}, {}) == 16
    # Trained +3 -> strength 5 -> 12 + 20 - 4 = 28
    assert cap_hit({"strength": 3}, {}) == 28
    # + Haymaker (+10% basic) -> int(28 * 1.1) = 30
    assert cap_hit({"strength": 3}, {"basic_damage_pct": 10}) == 30


def test_hp_energy_and_ult_perks(content):
    cap_data = content["characters"]["captain_america"]
    plain = Combatant(cap_data, is_hero=True)
    perked = Combatant(cap_data, is_hero=True,
                       perk_effects={"max_hp_pct": 10, "battle_energy_flat": 5,
                                     "ult_turn_charge_bonus": 5})
    assert perked.max_hp == int(plain.max_hp * 1.10)
    assert perked.max_energy == plain.max_energy + 5

    engine = BattleEngine([perked], make_enemy_group([content["enemies"]["hydra_grunt"]]),
                          rng=NoLuckRng(), items_data=content["items"])
    engine.round_order = [perked]
    engine._turn_index = 0
    engine.begin_turn()
    engine.take_turn({"type": "defend"})
    assert perked.ult_charge == 25                      # 20 + 5


def test_synergy_crit_bonus_applies(content):
    cap = Combatant(content["characters"]["captain_america"], is_hero=True,
                    synergy_crit=8)
    assert cap.crit_bonus == 8


# --- Mastery stub ---

def test_mastery_detection(content):
    # M15: Mastery = every attribute at RANK_MAX (trained TRAINED_MAX)
    im = content["characters"]["iron_man"]
    e = entry()
    assert not mastery.update_mastery(im["boosts"], e)
    for attr in config.ATTRIBUTES:
        e["trained_ranks"][attr] = config.TRAINED_MAX
    assert mastery.update_mastery(im["boosts"], e) is True
    assert e["mastered"]
    assert mastery.update_mastery(im["boosts"], e) is False       # only fires once
    mastery.log_mastery_xp(e, 60)
    assert e["mastery_xp"] == 60


def test_stale_perk_ids_are_sanitized_and_skipped(content):
    e = entry()
    e["perk_choices"] = {"strength:3": "haymaker", "speed:3": "removed_perk"}
    fx = attrs.perk_effects(e, content["perks"])       # unknown id skipped
    assert fx == {"basic_damage_pct": 10}
    attrs.sanitize_perk_choices(e, content["perks"])
    assert e["perk_choices"] == {"strength:3": "haymaker"}
