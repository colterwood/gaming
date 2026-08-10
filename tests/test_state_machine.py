import pytest

from game.core.state_machine import GameState, IllegalTransition, StateMachine


def test_full_legal_walk():
    sm = StateMachine()
    assert sm.state is GameState.BOOT
    sm.transition(GameState.TITLE)
    sm.transition(GameState.PATH_SELECT)
    sm.transition(GameState.HUB)
    sm.transition(GameState.BATTLE)
    sm.transition(GameState.HUB)
    sm.transition(GameState.PAUSE)
    sm.transition(GameState.HUB)
    sm.transition(GameState.SLEEP)
    assert sm.transition(GameState.HUB) is GameState.HUB


@pytest.mark.parametrize("start,to", [
    (GameState.BOOT, GameState.HUB),
    (GameState.TITLE, GameState.BATTLE),
    (GameState.BATTLE, GameState.PAUSE),
    (GameState.PAUSE, GameState.BATTLE),
    (GameState.SLEEP, GameState.BATTLE),
    (GameState.HUB, GameState.TITLE),
])
def test_illegal_transitions_raise(start, to):
    sm = StateMachine(initial=start)
    assert not sm.can_transition(to)
    with pytest.raises(IllegalTransition):
        sm.transition(to)
    assert sm.state is start
