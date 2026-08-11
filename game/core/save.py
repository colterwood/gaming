"""JSON save/load (spec §5.4). Pure Python — no pygame.

One JSON file per slot at saves/slot_N.json; the previous save is kept as
slot_N.json.bak.
"""

import json
import os
import shutil

from game import config


def new_game_state():
    """The starting save-state shape (§5.4). Systems fill it in as they land."""
    return {
        "day": 1,
        "issue": 1,
        "time_minutes": config.DAY_START_MINUTES,
        "energy": config.DAILY_ENERGY,
        "path": None,
        "roster": {},          # hero id -> trained ranks, xp, perks, gear, energy
        "party": [],           # active team, max PARTY_SIZE_MAX (M9)
        "bonds": {},           # char id -> {points, gifts_this_week, talked_today}
        "inventory": {"med_kit": 2, "energy_bar": 1, "shawarma": 1},
        "credits": 0,
        "story_flags": {},
        "quests": {},
        "unlocks": {},         # conditional side arcs in progress (M17)
        "pending_scenes": [],  # story beats waiting for the hub to play them
        "dispatches": [],      # board jobs under way (M10)
        "completed_tasks": [], # one-shot board jobs already done (M15)
        "searched_today": [],  # zone crates rummaged today (M10)
        "board_checked_day": 0,  # last day the board was read in person (M20)
    }


def _slot_path(slot, save_dir=None):
    return os.path.join(save_dir or config.SAVE_DIR, f"slot_{slot}.json")


def save_game(state, slot, save_dir=None):
    path = _slot_path(slot, save_dir)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        shutil.copy2(path, path + ".bak")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, path)
    return path


def load_game(slot, save_dir=None):
    path = _slot_path(slot, save_dir)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def slot_exists(slot, save_dir=None):
    return os.path.exists(_slot_path(slot, save_dir))
