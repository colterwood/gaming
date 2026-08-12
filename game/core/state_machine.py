"""Game states and legal transitions (spec §4). Pure Python — no pygame."""

from enum import Enum, auto


class GameState(Enum):
    BOOT = auto()
    TITLE = auto()
    PATH_SELECT = auto()
    HUB = auto()
    BATTLE = auto()
    PAUSE = auto()
    SLEEP = auto()


# BOOT → TITLE → PATH_SELECT → HUB ⇄ BATTLE, HUB ⇄ PAUSE, HUB → SLEEP → HUB
# M28: loading a save goes TITLE → HUB directly — the path was chosen the
# day that game was started, so PATH_SELECT has nothing left to ask.
TRANSITIONS = {
    GameState.BOOT: {GameState.TITLE},
    GameState.TITLE: {GameState.PATH_SELECT, GameState.HUB},
    GameState.PATH_SELECT: {GameState.HUB},
    GameState.HUB: {GameState.BATTLE, GameState.PAUSE, GameState.SLEEP},
    GameState.BATTLE: {GameState.HUB},
    GameState.PAUSE: {GameState.HUB},
    GameState.SLEEP: {GameState.HUB},
}


class IllegalTransition(Exception):
    pass


class StateMachine:
    def __init__(self, initial=GameState.BOOT):
        self.state = initial

    def can_transition(self, to):
        return to in TRANSITIONS.get(self.state, set())

    def transition(self, to):
        if not self.can_transition(to):
            raise IllegalTransition(f"{self.state.name} -> {to.name} is not allowed")
        self.state = to
        return self.state
