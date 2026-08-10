"""§6.4 formula tests against hand-computed cases (M1 AC)."""

from game.combat import formulas


# max_hp = 50 + stamina*20 + durability*10
def test_max_hp_iron_man():
    # Iron Man card grid: stamina 4, durability 5
    assert formulas.max_hp(4, 5) == 50 + 80 + 50 == 180


def test_max_hp_grunt():
    assert formulas.max_hp(2, 2) == 50 + 40 + 20 == 110


# battle_energy = 20 + intelligence*5
def test_battle_energy():
    assert formulas.battle_energy(7) == 55
    assert formulas.battle_energy(1) == 25


# initiative = speed*10 + rand(1,6)
def test_initiative():
    assert formulas.initiative(5, 3) == 53
    assert formulas.initiative(2, 6) == 26


# basic_damage = power + rank*4 - durability*2 (min 1)
def test_basic_damage_repulsor_vs_grunt():
    # Repulsor Blast 12, intelligence 7, grunt durability 2: 12 + 28 - 4 = 36
    assert formulas.ability_damage(12, 7, 2, "basic") == 36


# special_damage = power + rank*5 - durability*2 (min 1)
def test_special_damage_unibeam_vs_grunt():
    # Unibeam 30, intelligence 7, grunt durability 2: 30 + 35 - 4 = 61
    assert formulas.ability_damage(30, 7, 2, "special") == 61


def test_ultimate_scales_like_special():
    # House Party 55, intelligence 7, durability 2: 55 + 35 - 4 = 86
    assert formulas.ability_damage(55, 7, 2, "ultimate") == 86


def test_min_damage_floor():
    # power 1, rank 1 vs durability 7: 1 + 4 - 14 = -9 -> floor 1
    assert formulas.ability_damage(1, 1, 7, "basic") == 1


# crit_chance = agility*4 ; crit = damage * 1.5
def test_crit_chance_and_multiplier():
    assert formulas.crit_chance(3) == 12
    assert formulas.crit_chance(6) == 24
    assert formulas.apply_crit(36) == 54
    assert formulas.apply_crit(61) == 91  # int(91.5)


# dodge_chance = agility*3
def test_dodge_chance():
    assert formulas.dodge_chance(3) == 9
    assert formulas.dodge_chance(6) == 18


# defend halves incoming damage
def test_defend_halves():
    assert formulas.apply_defend(36) == 18
    assert formulas.apply_defend(61) == 30  # int(30.5)
    assert formulas.apply_defend(1) == 1    # never below min damage


# full resolution pipeline: dodge (before crit) -> crit -> defend
def test_resolve_dodged():
    dmg, dodged, crit = formulas.resolve_damage(
        base_damage=36, dodge_roll=8, defender_agility=3,  # 8 < 9 -> dodge
        crit_roll=0, attacker_agility=7, defending=False)
    assert (dmg, dodged, crit) == (0, True, False)


def test_resolve_hit_no_crit():
    dmg, dodged, crit = formulas.resolve_damage(
        base_damage=36, dodge_roll=50, defender_agility=3,
        crit_roll=99, attacker_agility=3, defending=False)
    assert (dmg, dodged, crit) == (36, False, False)


def test_resolve_crit_while_defending():
    # crit then defend: 36 -> 54 -> 27
    dmg, dodged, crit = formulas.resolve_damage(
        base_damage=36, dodge_roll=50, defender_agility=3,
        crit_roll=11, attacker_agility=3, defending=True)  # 11 < 12 -> crit
    assert (dmg, dodged, crit) == (27, False, True)


def test_resolve_synergy_crit_bonus():
    # agility 3 = 12% base; roll 15 misses base but hits with +8 bonus (20%)
    dmg, dodged, crit = formulas.resolve_damage(
        base_damage=30, dodge_roll=50, defender_agility=0,
        crit_roll=15, attacker_agility=3, defending=False, crit_bonus=8)
    assert crit and dmg == 45


# ultimate: +20/turn taken, +10/hit received, fires at 100
def test_ult_charge_caps_at_100():
    assert formulas.add_ult_charge(0, 20) == 20
    assert formulas.add_ult_charge(90, 20) == 100
    assert formulas.add_ult_charge(100, 10) == 100
