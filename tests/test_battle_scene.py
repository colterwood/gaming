"""Regression: battle-scene turn tracking (M1 review finding).

A stunned combatant whose consumed turn ends the round, and who then wins
initiative in the rebuilt round, must still get begin_turn effects (burn
tick, defend reset) on their new turn. Identity comparison missed this;
the scene now compares engine.turn_counter.
"""

import pytest

from game import data_loader
from game.ui.battle_scene import BattleScene


class ScriptedRng:
    def __init__(self, randints=None, uniforms=None):
        self.randints = list(randints or [])
        self.uniforms = list(uniforms or [])

    def randint(self, a, b):
        return self.randints.pop(0) if self.randints else a

    def uniform(self, a, b):
        return self.uniforms.pop(0) if self.uniforms else 99.0


@pytest.fixture(scope="module")
def content():
    return data_loader.load_all()


def test_back_to_back_turns_still_run_begin_turn(content):
    # Cap (speed 2) vs a grunt (speed 2).
    # Round 1 rolls: Cap 1 (21), grunt 6 (26) -> grunt first, Cap last.
    # Round 2 rolls: Cap 6 (26), grunt 1 (21) -> Cap first again.
    rng = ScriptedRng(randints=[1, 6, 6, 1])
    scene = BattleScene(content, hero_ids=("captain_america",),
                        enemy_ids=("hydra_grunt",), rng=rng)
    cap = scene.engine.heroes[0]
    cap.statuses.update(burn=2, stun=1)
    hp_before = cap.hp

    for _ in range(20):
        if scene.phase == "menu":
            break
        scene.update(0.6)   # each step covers the enemy-turn delay

    # Round 1: CB acted, Cap's turn consumed by stun (burn 2 -> 1).
    # Round 2: Cap first — begin_turn must run again (burn 1 -> 0), then menu.
    assert scene.phase == "menu"
    assert "burn" not in cap.statuses, "second burn tick was skipped"
    assert "stun" not in cap.statuses
    burn_damage = 2 * 5
    assert cap.hp <= hp_before - burn_damage
