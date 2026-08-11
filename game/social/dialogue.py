"""Relationship-tiered talk lines (M11). Pure Python — no pygame.

Pools live in data/dialogue.json keyed by minimum tier. For bondable
characters (NPCs, bond-recruits) the tier is their bond level, so lines
grow warmer as the relationship does. Starters and story recruits don't
bond (relationship redesign) — their tier tracks story progress instead,
so their lines grow with the campaign.
"""

from game.social import bonds

# Story stages standing in for bond level on non-bonding teammates:
# ch1 boss down -> tier 2 lines, ch2 done -> tier 4 lines.
_STORY_STAGE_FLAGS = (("ch2_complete", 4), ("training_upgraded", 2))


def tier_level(state, character):
    if bonds.bondable(character):
        return bonds.bond_level(bonds.ensure_bond(state, character["id"])["points"])
    flags = state.get("story_flags", {})
    for flag, level in _STORY_STAGE_FLAGS:
        if flags.get(flag):
            return level
    return 0


def line_for(state, character, dialogue_data):
    """The character's line for today: the richest pool their relationship
    tier unlocks, rotated daily. None if they have no dialogue."""
    pools = dialogue_data.get(character["id"])
    if not pools:
        return None
    level = tier_level(state, character)
    unlocked = [int(k) for k in pools if int(k) <= level]
    if not unlocked:
        return None
    lines = pools[str(max(unlocked))]
    return lines[(state["day"] + level + len(character["id"])) % len(lines)]
