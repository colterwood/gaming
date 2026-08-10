"""Bond-event triggering (spec §6.2 level gates). Pure Python — no pygame."""

from game.social import bonds


def pending_bond_events(state, scenes):
    """Scenes whose bond-level gate is reached and that haven't played yet."""
    seen = state.setdefault("bond_scenes_seen", [])
    pending = []
    for scene in scenes:
        if scene["id"] in seen:
            continue
        bond = bonds.ensure_bond(state, scene["character"])
        if bonds.bond_level(bond["points"]) >= scene["level"]:
            pending.append(scene)
    return pending


def mark_seen(state, scene_id):
    seen = state.setdefault("bond_scenes_seen", [])
    if scene_id not in seen:
        seen.append(scene_id)
