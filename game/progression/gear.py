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


# --------------------------------------------- the Pym bench (M32)
#
# You don't upgrade gear over the counter — you LEAVE it. Drop the piece
# with the materials and the money, and come back in a few days for it,
# the way Stardew hands a pickaxe to Clint. The queue lives on the save as
#
#     state["upgrades"] = [{"item": id, "level": 2, "days_left": 2}, ...]
#
# and a job with days_left 0 is sitting on the bench waiting to be
# collected. Nothing is applied until the player picks it up in person.

def upgrade_recipe(target_level):
    """(credits, {material: count}, days) for reaching a level, or None if
    there is no such level."""
    if target_level not in config.GEAR_UPGRADE_CREDITS:
        return None
    return (config.GEAR_UPGRADE_CREDITS[target_level],
            dict(config.GEAR_UPGRADE_MATERIALS[target_level]),
            config.GEAR_UPGRADE_DAYS[target_level])


def queue(state):
    return state.setdefault("upgrades", [])


def job_for(state, item_id):
    return next((j for j in queue(state) if j["item"] == item_id), None)


def missing_materials(state, materials):
    """What the bag is short of, as {id: how many more}."""
    bag = state.get("inventory", {})
    return {mid: need - bag.get(mid, 0)
            for mid, need in materials.items() if bag.get(mid, 0) < need}


def wearer_of(state, item_id):
    """(hero_id, slot) for whoever has this fitted, or (None, None)."""
    for hero_id, entry in sorted((state.get("roster") or {}).items()):
        for slot, worn in equipped(entry).items():
            if worn == item_id:
                return hero_id, slot
    return None, None


def owns(state, item_id):
    """A piece in the bag or on a hero's back — either can be handed over."""
    if state.get("inventory", {}).get(item_id, 0) > 0:
        return True
    return wearer_of(state, item_id)[0] is not None


def can_upgrade(state, item):
    """(ok, reason, target_level) for leaving this piece at the bench."""
    if job_for(state, item["id"]):
        return False, "That one's already on the bench.", None
    target = level(state, item["id"]) + 1
    recipe = upgrade_recipe(target)
    if recipe is None:
        return False, "That design is as good as it gets.", None
    if not owns(state, item["id"]):
        # The bench upgrades a PIECE, not a blueprint — you have to put
        # one on the counter.
        return False, "You'd have to own one first.", target
    credits, materials, _days = recipe
    if state.get("credits", 0) < credits:
        return False, f"Needs {credits} cr.", target
    short = missing_materials(state, materials)
    if short:
        return False, "Short " + ", ".join(f"{n} {mid}" for mid, n
                                           in sorted(short.items())), target
    return True, "", target


def start_upgrade(state, item, items):
    """Hand the piece over. The materials and the money go now — and so
    does the equipment: it comes off the hero's back if that's where it is,
    and the team fights without it until it's collected. That waiting is
    the cost of the upgrade, not an accounting detail."""
    ok, reason, target = can_upgrade(state, item)
    if not ok:
        return {"ok": False, "message": reason}
    credits, materials, days = upgrade_recipe(target)
    state["credits"] -= credits
    for material_id, count in materials.items():
        inventory.remove(state, material_id, count)

    stripped = None
    if state.get("inventory", {}).get(item["id"], 0) > 0:
        inventory.remove(state, item["id"], 1)      # a spare goes first
    else:
        hero_id, slot = wearer_of(state, item["id"])
        del state["roster"][hero_id]["gear"][slot]
        stripped = hero_id
    queue(state).append({"item": item["id"], "level": target,
                         "days_left": days, "worn_by": stripped})
    return {"ok": True, "days": days, "stripped": stripped,
            "message": (f"{item['name']} left at the bench - {days} days, "
                        f"{credits} cr. You're without it until then.")}


def process_day(state, items):
    """Run a night off every job on the bench. Returns log messages; a job
    that comes due WAITS to be collected rather than applying itself."""
    messages = []
    for job in queue(state):
        if job["days_left"] > 0:
            job["days_left"] -= 1
            if job["days_left"] == 0:
                name = items[job["item"]]["name"]
                messages.append(f"The Pym bench is done with your {name}.")
    return messages


def ready_jobs(state):
    return [j for j in queue(state) if j["days_left"] <= 0]


def collect(state, job, items):
    """Pick it up: the piece comes back and THIS is when the schematic's
    level moves. If it was taken off a hero, it goes straight back on them
    when that slot is still free — you handed it in, you get it back."""
    if job["days_left"] > 0:
        return {"ok": False,
                "message": f"Not for another {job['days_left']} day(s)."}
    queue(state).remove(job)
    state.setdefault("gear_levels", {})[job["item"]] = job["level"]
    item = items[job["item"]]
    # force: the piece was already theirs — a full bag must not eat it.
    inventory.add(state, item["id"], 1, force=True)
    refitted = None
    hero_id = job.get("worn_by")
    entry = (state.get("roster") or {}).get(hero_id) if hero_id else None
    if entry is not None and not equipped(entry).get(slot_of(item)):
        equip(state, hero_id, item["id"], items)
        refitted = hero_id
    tail = " Back on straight away." if refitted else ""
    return {"ok": True, "refitted": refitted,
            "message": (f"{item['name']} is now +{job['level'] - 1}: "
                        f"{effect_label(state, item)}.{tail}")}


def owned_for_slot(state, items, slot):
    """Carried gear that fits a slot, in a stable order."""
    return sorted((items[item_id] for item_id, count
                   in (state.get("inventory") or {}).items()
                   if count > 0 and item_id in items
                   and is_gear(items[item_id])
                   and slot_of(items[item_id]) == slot),
                  key=lambda i: i["id"])
