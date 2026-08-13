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
    state["credits"] = 100000      # M36: the rack bills at the door
    return state


# --- XP thresholds (§6.3): rank N costs 100 × N ---

def test_xp_for_rank_thresholds():
    # M33: the cost to climb DOUBLES per level (M16's 1.5x let ambush XP
    # alone carry a team to rank 5 before Chapter 3), and it is the same
    # for every hero — talent is a combat bonus, not a training discount.
    assert [attrs.xp_for_rank(n) for n in range(1, 10)] == [
        100, 200, 400, 800, 1600, 3200, 6400, 12800, 25600]


def test_rank_up_consumes_exact_xp(content):
    cap = content["characters"]["captain_america"]     # strength boost 2
    e = entry()
    cost = attrs.xp_for_rank(1)
    assert cost == 100
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
    two = (attrs.xp_for_rank(1)
           + attrs.xp_for_rank(2))
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

def test_perk_pending_at_card_ranks_5_and_10(content):
    """M36: perk tiers are the rank PRINTED ON THE CARD, not the trained
    rank underneath — the old (3, 6) fired the "rank 3 perk!" modal at a
    hero the card called rank 4. Tiers are now 5 and RANK_MAX."""
    assert config.PERK_CHOICE_RANKS == (5, config.RANK_MAX)
    im = content["characters"]["iron_man"]              # agility boost 3
    e = entry()
    to = lambda a, b: sum(attrs.xp_for_rank(n) for n in range(a, b))

    attrs.add_training_xp(im["boosts"], e, "agility", to(1, 4))  # card rank 4
    assert attrs.rank(e, "agility") == 4
    assert attrs.pending_perk_tier(e, "agility") is None         # not yet

    attrs.add_training_xp(im["boosts"], e, "agility", to(4, 5))  # card rank 5
    assert attrs.pending_perk_tier(e, "agility") == 5
    assert attrs.choose_perk(e, "agility", 5, "precision",
                             content["perks"])["ok"]
    assert attrs.pending_perk_tier(e, "agility") is None

    attrs.add_training_xp(im["boosts"], e, "agility", to(5, 10))  # card rank 10
    assert attrs.rank(e, "agility") == config.RANK_MAX
    assert attrs.pending_perk_tier(e, "agility") == config.RANK_MAX
    attrs.choose_perk(e, "agility", config.RANK_MAX, "killer_instinct",
                      content["perks"])
    assert attrs.pending_perk_tier(e, "agility") is None


def test_perk_choice_validation(content):
    e = entry()
    e["trained_ranks"]["strength"] = 4                  # card rank 5
    bad = attrs.choose_perk(e, "strength", 5, "blur", content["perks"])
    assert not bad["ok"]
    good = attrs.choose_perk(e, "strength", 5, "haymaker", content["perks"])
    assert good["ok"]
    again = attrs.choose_perk(e, "strength", 5, "power_through", content["perks"])
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
    # M16 level 1 = 50 min, doubled by the M36 lockout multiplier.
    assert result["ok"] and result["minutes"] == 50 * config.TRAINING_LOCKOUT_MULT
    cap = state["roster"]["captain_america"]
    assert cap["energy"] == 80                          # trainee pays 20 EN now
    assert state["roster"]["iron_man"]["energy"] == 100  # teammates untouched
    assert state["party"] == ["iron_man"]               # off the team
    assert cap["attribute_xp"] == {}                    # nothing granted yet
    # too early: nothing completes
    assert activities.finish_due_training(state, content) == []
    state["time_minutes"] += 50 * config.TRAINING_LOCKOUT_MULT
    messages = activities.finish_due_training(state, content)
    assert len(messages) == 1 and "Strength" in messages[0]
    assert cap["attribute_xp"]["strength"] == config.TRAINING_XP_BY_LEVEL[1]
    assert "training" not in cap
    # M36: no auto-rejoin - they are standing on the mats waiting to be
    # collected in person.
    assert state["party"] == ["iron_man"]
    assert any("Waiting at the mats" in m for m in messages)


def test_training_costs_scale_with_rank(content):
    # M16: EN still linear, minutes from the table — level 8/9 sessions run
    # longer than a single 1200-minute day.
    mult = config.TRAINING_LOCKOUT_MULT
    assert activities.training_cost(1) == (20, 50 * mult)
    assert activities.training_cost(2) == (25, 70 * mult)
    assert activities.training_cost(7) == (50, 800 * mult)
    assert activities.training_cost(9) == (60, 2400 * mult)


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


def test_training_the_last_party_member_asks_before_it_allows(content):
    """M36: emptying the team is the player's call, not a refusal. The
    logic layer still says no by default so nothing does it by accident,
    but it flags that the caller should ask."""
    state = game_state(content)
    state["party"] = ["captain_america"]

    result = activities.start_training(state, content, "captain_america",
                                       "strength")
    assert not result["ok"] and result["needs_solo_confirm"]
    assert "training" not in state["roster"]["captain_america"]

    result = activities.start_training(state, content, "captain_america",
                                       "strength", solo_ok=True)
    assert result["ok"]
    assert state["party"] == []
    # ...and an empty team is not a collapsed one.
    assert not activities.should_pass_out(state)


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
    state["time_minutes"] += 50 * config.TRAINING_LOCKOUT_MULT
    messages = activities.finish_due_training(state, content, rejoin=False)
    assert any("Waiting at the mats" in m for m in messages)
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
    e["perk_choices"] = {"strength:5": "haymaker", "speed:5": "removed_perk"}
    fx = attrs.perk_effects(e, content["perks"])       # unknown id skipped
    assert fx == {"basic_damage_pct": 10}
    attrs.sanitize_perk_choices(e, content["perks"])
    assert e["perk_choices"] == {"strength:5": "haymaker"}


def test_a_pre_m36_perk_choice_moves_to_the_tier_that_now_owns_it(content):
    """The tiers moved from trained ranks (3, 6) to card ranks (5, 10). An
    untouched old key would match no live tier, so the hero would keep the
    perk AND be offered the same list again — and perk_effects sums by
    value, so taking it twice would count it twice."""
    e = entry()
    e["perk_choices"] = {"strength:3": "haymaker", "agility:6": "untouchable"}
    e["trained_ranks"] = {"strength": 9, "agility": 9}      # card rank 10

    attrs.sanitize_perk_choices(e, content["perks"])

    assert e["perk_choices"] == {"strength:5": "haymaker",
                                 "agility:10": "untouchable"}
    assert attrs.perk_effects(e, content["perks"]) == {
        "basic_damage_pct": 10, "dodge_bonus": 6}
    # Each hero keeps exactly the one tier they had already spent, and the
    # other is offered: strength's capstone, agility's first tier.
    assert attrs.pending_perk_tier(e, "strength") == config.RANK_MAX
    assert attrs.pending_perk_tier(e, "agility") == 5
