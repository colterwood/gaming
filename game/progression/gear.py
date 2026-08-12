"""Equipment (spec §9 M31). Pure Python — no pygame.

Every roster entry has carried an empty `gear: {}` since M0 and nothing
ever filled it. The Tech Lab does: buy a piece, fit it to a hero, and its
effects land in combat.

    state["roster"][hero]["gear"] = {"weapon": "combat_gauntlets", ...}

A piece is WORN or CARRIED, never both — equipping takes it out of the bag
(M18 capacity) and unequipping puts it back, so a full party can't quietly
carry sixteen spare chestplates in their slots.

An item's `effects` may name:
  * an attribute  -> flat RANK bonus, which is how gear pushes a hero past
    the trained ceiling of 10 (`entities.Combatant.rank`)
  * any PERK_EFFECT_KEY -> the same meaning it has on a perk, summed with
    whatever the perks already give

Upgrade levels (M32) live on the SCHEMATIC, not the object:
`state["gear_levels"][item_id]` is a level from 1, and every copy of that
item benefits — the lab improved the design. Effects scale by
GEAR_UPGRADE_STEP per level above the first.
"""

from game import config
from game.core import inventory

SLOTS = ("weapon", "armor", "accessory")
SLOT_LABELS = {"weapon": "Weapon", "armor": "Armor", "accessory": "Accessory"}


def is_gear(item):
    return item.get("kind") in ("weapon", "armor", "accessory")


def slot_of(item):
    return item.get("slot")


def level(state, item_id):
    """The schematic's upgrade level, 1 by default."""
    return max(1, state.get("gear_levels", {}).get(item_id, 1))


def scaled_effects(state, item):
    """An item's effects at its current upgrade level. Attribute bonuses
    stay whole numbers — half a rank of Strength isn't a thing."""
    step = 1 + config.GEAR_UPGRADE_STEP * (level(state, item["id"]) - 1)
    out = {}
    for key, value in item.get("effects", {}).items():
        out[key] = int(round(value * step)) if key in config.ATTRIBUTES \
            else round(value * step, 2)
    return out


def equipped(entry):
    return {slot: item_id for slot, item_id in (entry.get("gear") or {}).items()
            if slot in SLOTS and item_id}


def total_effects(state, entry, items):
    """Everything this hero's worn gear adds, summed."""
    total = {}
    for item_id in equipped(entry).values():
        item = items.get(item_id)
        if not item:
            continue
        for key, value in scaled_effects(state, item).items():
            total[key] = total.get(key, 0) + value
    return total


def split_effects(effects):
    """(attribute rank bonuses, perk-style combat effects)."""
    ranks = {k: v for k, v in effects.items() if k in config.ATTRIBUTES}
    combat = {k: v for k, v in effects.items() if k not in config.ATTRIBUTES}
    return ranks, combat


def effect_label(state, item):
    """"+2 Strength, +8 crit" — what a piece actually does, at its level."""
    parts = []
    for key, value in scaled_effects(state, item).items():
        if key in config.ATTRIBUTES:
            parts.append(f"+{value} {key.title()}")
        elif key.endswith("_pct"):
            parts.append(f"+{value:g}% {key[:-4].replace('_', ' ')}")
        else:
            parts.append(f"+{value:g} {key.replace('_', ' ')}")
    return ", ".join(parts) or "no effect"


def item_label(state, item):
    lvl = level(state, item["id"])
    star = f" +{lvl - 1}" if lvl > 1 else ""
    return f"{item['name']}{star}"


# ------------------------------------------------------------ fitting

def equip(state, hero_id, item_id, items):
    """Fit a carried piece. Whatever was in that slot goes back in the bag
    — forced, because a full bag must never eat a hero's own equipment."""
    item = items.get(item_id)
    if not item or not is_gear(item):
        return {"ok": False, "message": "That isn't equipment."}
    entry = state.get("roster", {}).get(hero_id)
    if entry is None:
        return {"ok": False, "message": "Nobody by that name."}
    if state.get("inventory", {}).get(item_id, 0) <= 0:
        return {"ok": False, "message": f"No {item['name']} in the bag."}
    slot = slot_of(item)
    gear = entry.setdefault("gear", {})
    previous = gear.get(slot)
    inventory.remove(state, item_id, 1)
    if previous:
        inventory.add(state, previous, 1, force=True)
    gear[slot] = item_id
    swapped = f" (stowed the {items[previous]['name']})" if previous else ""
    return {"ok": True, "message": f"{item['name']} fitted"
                                   f"{swapped}: {effect_label(state, item)}."}


def unequip(state, hero_id, slot, items):
    entry = state.get("roster", {}).get(hero_id)
    if entry is None:
        return {"ok": False, "message": "Nobody by that name."}
    item_id = (entry.get("gear") or {}).get(slot)
    if not item_id:
        return {"ok": False, "message": "Nothing fitted there."}
    del entry["gear"][slot]
    inventory.add(state, item_id, 1, force=True)
    return {"ok": True,
            "message": f"{items[item_id]['name']} stowed."}


def owned_for_slot(state, items, slot):
    """Carried gear that fits a slot, in a stable order."""
    return sorted((items[item_id] for item_id, count
                   in (state.get("inventory") or {}).items()
                   if count > 0 and item_id in items
                   and is_gear(items[item_id])
                   and slot_of(items[item_id]) == slot),
                  key=lambda i: i["id"])
