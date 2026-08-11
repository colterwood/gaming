"""Bag capacity (spec §5.4, M18). Pure Python — no pygame.

The team carries what its members can carry: INVENTORY_SLOTS_PER_HERO (4)
slots each, so a full party of four has INVENTORY_SLOTS_MAX (16). A slot
holds one item id up to INVENTORY_STACK_MAX (99) — the 100th of anything
spills into a second slot.

The bag itself stays a flat {item_id: count} on the save state; capacity
is derived from the ACTIVE party, so benching someone shrinks it. Going
over capacity that way never destroys anything: you simply can't pick up
anything new until you're back under.
"""

from game import config


def party_size(state):
    return len([h for h in state.get("party", [])
                if h in state.get("roster", {})])


def capacity(state):
    """Slots the active party can carry between them."""
    return min(config.INVENTORY_SLOTS_MAX,
               config.INVENTORY_SLOTS_PER_HERO * party_size(state))


def slots_for(count):
    """Slots one stack of `count` occupies."""
    count = max(0, int(count))
    return -(-count // config.INVENTORY_STACK_MAX)      # ceil division


def slots_used(state):
    return sum(slots_for(n) for n in state.get("inventory", {}).values() if n > 0)


def slots_free(state):
    return max(0, capacity(state) - slots_used(state))


def room_for(state, item_id):
    """How many more of `item_id` will actually fit right now: whatever is
    left in its current top stack, plus a full stack per free slot."""
    have = state.get("inventory", {}).get(item_id, 0)
    top_stack_room = slots_for(have) * config.INVENTORY_STACK_MAX - have
    return top_stack_room + slots_free(state) * config.INVENTORY_STACK_MAX


def is_full(state):
    return slots_free(state) <= 0


def add(state, item_id, quantity=1, force=False):
    """Put items in the bag, capped by capacity. Returns
    {"ok", "added", "dropped", "message"} — `added` may be less than asked
    when the bag fills mid-stack.

    force=True bypasses capacity for story items that must never be
    droppable (a quest artifact you cannot pick up would dead-end the arc).
    """
    quantity = max(0, int(quantity))
    inventory = state.setdefault("inventory", {})
    fits = quantity if force else min(quantity, room_for(state, item_id))
    if fits <= 0:
        return {"ok": False, "added": 0, "dropped": quantity,
                "message": "The team's bags are full."}
    inventory[item_id] = inventory.get(item_id, 0) + fits
    dropped = quantity - fits
    return {"ok": True, "added": fits, "dropped": dropped,
            "message": "" if not dropped else
            f"Only {fits} fit - the bags are full."}


def remove(state, item_id, quantity=1):
    """Take items out; empty stacks free their slot. False if short."""
    inventory = state.setdefault("inventory", {})
    have = inventory.get(item_id, 0)
    if have < quantity:
        return False
    inventory[item_id] = have - quantity
    if inventory[item_id] <= 0:
        del inventory[item_id]
    return True


def label(state):
    """'Slots 5/12' for the shop, bag and pause card."""
    return f"Slots {slots_used(state)}/{capacity(state)}"
