"""Generate docs/BIBLE.md — every number in the game, in one document.

    python tools/build_bible.py

WHY THIS IS GENERATED AND NOT WRITTEN. A hand-maintained reference for a game
this numeric goes stale the first time somebody retunes a constant, and then
it is worse than nothing, because it is confidently wrong. Everything below
is read out of game/config.py and data/*.json at build time, or DERIVED by
calling the same functions the game calls. If a number here is wrong, the
game is wrong.

Re-run it after any balance change and commit the diff — the diff is a
readable summary of what the change actually did.
"""

import math
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game import config, data_loader                        # noqa: E402
from game.combat import formulas                            # noqa: E402
from game.core import clock, energy                         # noqa: E402
from game.hub import field, repairs as repairs_mod          # noqa: E402
from game.progression import attributes as attrs            # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "docs", "BIBLE.md")

L = []


def w(line=""):
    L.append(line)


def h(level, text):
    w()
    w("#" * level + " " + text)
    w()


def table(headers, rows):
    w("| " + " | ".join(str(x) for x in headers) + " |")
    w("|" + "|".join("---" for _ in headers) + "|")
    for row in rows:
        w("| " + " | ".join("" if c is None else str(c) for c in row) + " |")
    w()


def pct(x):
    return f"{x * 100:.0f}%"


def mins(m):
    return "—" if not m else clock.format_duration(m)


def entry_at(**trained):
    return {"trained_ranks": dict(trained), "attribute_xp": {},
            "perk_choices": {}}


C = data_loader.load_all()
HEROES = {cid: c for cid, c in C["characters"].items()
          if c["recruit"]["method"] != "npc"}
NPCS = {cid: c for cid, c in C["characters"].items()
        if c["recruit"]["method"] == "npc"}
BASE_ENEMIES = {eid: e for eid, e in C["enemies"].items() if "@" not in eid}


# =========================================================================
w("# Roads to Secret Wars — The Bible")
w()
w("*Every number in the game, generated from the code.* Run "
  "`python tools/build_bible.py` to rebuild.")
w()
w("This file is **generated**. Do not hand-edit it — edit `game/config.py`, "
  "`data/*.json` or `tools/build_bible.py` and regenerate. The design "
  "*narrative* (why things are the way they are, milestone by milestone) "
  "lives in [GAME_SPEC.md](GAME_SPEC.md); this is the reference sheet.")
w()

counts = [
    ("Playable heroes", len(HEROES)), ("NPCs", len(NPCS)),
    ("Enemy types", len(BASE_ENEMIES)),
    ("Enemy level variants", len(C["enemies"]) - len(BASE_ENEMIES)),
    ("Items", len(C["items"])), ("Zones", len(C["zones"])),
    ("Tower floors", 6), ("Story quests", len(C["story"])),
    ("Side arcs", len(C["unlocks"])), ("Board jobs", len(C["assignments"])),
    ("Tower repairs", len(C["repairs"])),
    ("Bond scenes", len(C["bond_scenes"])),
]
w("**At a glance:** " + " · ".join(f"{n} {k.lower()}" for k, n in counts))

# ---------------------------------------------------------------- contents
h(2, "Contents")
for i, name in enumerate([
        "The day", "Energy & health", "Progression", "Combat",
        "Heroes", "NPCs", "Enemies", "Items", "Gear",
        "The tower", "Tower repairs", "Zones & the field",
        "Story", "Side arcs", "The assignment board", "Bonds",
        "Calendar", "The save file"], 1):
    w(f"{i}. [{name}](#{str(i) + '-' + name.lower().replace(' & ', '--').replace(' ', '-')})")


# =========================================================================
h(2, "1. The day")
w(f"The day runs **{clock.format_time(config.DAY_START_MINUTES)} to "
  f"{clock.format_time(config.DAY_END_MINUTES)}** — "
  f"{config.DAY_END_MINUTES - config.DAY_START_MINUTES} in-game minutes. "
  f"Past the end, the team passes out.")
w()
w(f"The world clock ticks **{config.TICK_GAME_MINUTES} in-game minutes per "
  f"{config.TICK_REAL_SECONDS} real seconds** while you are on your feet in "
  f"the hub, which makes a full day about "
  f"**{(config.DAY_END_MINUTES - config.DAY_START_MINUTES) / config.TICK_GAME_MINUTES * config.TICK_REAL_SECONDS / 60:.0f} "
  f"real minutes** of standing still. The clock is frozen inside menus and "
  f"cutscenes (M25) — reading is not an activity.")

h(3, "What costs what")
w("**Outside battle, almost nothing jumps the clock** (M37c). Energy is the "
  "gate; the day is spent by playing it, by flying, and by sitting in the "
  "Med Bay chair.")
w()
table(["Action", "Energy", "Clock", "Notes"], [
    ["Walk around", "—", "real time", "the cosmetic tick"],
    ["Search furniture / a crate / trees", "—", mins(config.FURNITURE_SEARCH_MINUTES) if config.FURNITURE_SEARCH_MINUTES else "—", "always available, usually empty"],
    ["Mine an ore seam", config.MINE_ENERGY, mins(config.MINE_MINUTES), "one swing per node per day"],
    ["Work a scout point", config.SCOUT_ENERGY or "—", mins(config.SCOUT_MINUTES), "free; the walk is the cost"],
    ["Search a side-arc stand", config.UNLOCK_SEARCH_ENERGY, mins(config.UNLOCK_SEARCH_MINUTES), ""],
    ["Salvage a repair part", f"{config.REPAIR_PART_ENERGY} if **heavy**", mins(config.REPAIR_PART_MINUTES), "light parts are free"],
    ["Fit a repair", "—", "—", "the hunt was the price"],
    ["Talk / give a gift", "—", mins(config.TALK_GIFT_MINUTES), ""],
    ["Eat a ration / use a med kit", "—", mins(config.EAT_MINUTES), "treats the whole active party"],
    ["Engage a mission", config.MISSION_ENERGY, mins(config.MISSION_MINUTES), "never refused for low EN or a late hour"],
    ["**Quinjet hop**", "—", f"**{mins(config.TRAVEL_MINUTES)}**", "the one journey that costs daylight"],
    ["**Med Bay chair**", "—", f"**{config.MEDBAY_TICK_MINUTES} min/tick**", "runs in real time; the hours ARE the price"],
    ["Training session", "15 + 5 × level", "a *lockout*, not a jump", "see Progression"],
    ["Win an ambush / trap fight", "—", mins(config.BATTLE_MINUTES), "battle keeps its costs"],
    ["Lose any fight", f"capped at {config.DEFEAT_ENERGY}", mins(config.DEFEAT_RECOVERY_MINUTES), f"HP floored at {pct(config.DEFEAT_HP_FRACTION)}"],
])

h(3, "Sleep and collapse")
table(["", "Energy", "HP", "Credits"], [
    ["Sleep in a bed", "full (each hero's own ceiling)", pct(config.SLEEP_HP_FRACTION), "—"],
    ["Collapse **in the tower**", "full", pct(config.PASS_OUT_HP_FRACTION),
     f"−{pct(config.PASS_OUT_CREDIT_PCT)}, max {config.PASS_OUT_CREDIT_MAX:,}"],
    ["Collapse **in the field**", f"{pct(config.PASS_OUT_ENERGY_FRACTION)} of ceiling",
     pct(config.PASS_OUT_HP_FRACTION),
     f"−{pct(config.PASS_OUT_CREDIT_PCT)}, max {config.PASS_OUT_CREDIT_MAX:,}"],
])
w(f"You always wake beside your own bed on the Common Floor. "
  f"Jarvis's espresso (bond 4) adds **+{config.JARVIS_ENERGY_BONUS} EN** to a "
  f"proper night's sleep.")
w()
w("Cleared every night: crate/seam searches, the per-zone fight cap, daily "
  "talk flags. Autosave happens at lights-out and **nowhere else** — quit "
  "mid-day and you resume at 6:00 AM that morning.")


# =========================================================================
h(2, "2. Energy & health")
h(3, "Daily energy by Stamina")
w("Team energy is the **minimum** across the active party; team actions "
  "drain every member.")
w()
rows = []
for rank in range(config.RANK_START, config.RANK_MAX + 1):
    top = energy.max_for(entry_at(stamina=rank - config.RANK_START))
    rows.append([rank, top, f"+{config.ENERGY_BY_STAMINA_RANK[rank]}",
                 int(top * config.PASS_OUT_ENERGY_FRACTION)])
rows.append(["Enlightened", energy.max_for(
    dict(entry_at(stamina=config.TRAINED_MAX), enlightened=True)),
    f"+{config.ENLIGHTENMENT_ENERGY_BONUS} on top", "—"])
table(["Stamina rank", "Daily max EN", "vs rank 1", "after a field collapse"], rows)

h(3, "Low-energy initiative penalty")
w(f"Below **{pct(config.EN_PENALTY_THRESHOLD)}** of a hero's own ceiling, "
  f"initiative drops {config.EN_PENALTY_INITIATIVE} per tier, one tier per "
  f"further {pct(config.EN_PENALTY_STEP)} down, capped at "
  f"{config.EN_PENALTY_MAX_TIERS} tiers.")
w()
table(["Energy", "Tiers", "Initiative lost"],
      [[pct(f / 100), formulas.energy_penalty_tiers(f / 100),
        -formulas.energy_penalty_tiers(f / 100) * config.EN_PENALTY_INITIATIVE]
       for f in (100, 60, 50, 40, 30, 20, 10, 0)])

h(3, "Health")
w(f"`max_hp = {config.HP_BASE} + stamina × {config.HP_PER_STAMINA} + "
  f"durability × {config.HP_PER_DURABILITY}` (effective ranks).")
w()
w("**HP is carried between fights**, stored as a fraction of maximum so a "
  "rank-up or a piece of gear raises the pool with it. Restored by: sleeping "
  f"(full), a rank-up (full), the Med Bay chair "
  f"({pct(config.MEDBAY_HP_PCT_PER_TICK)} per {config.MEDBAY_TICK_MINUTES} "
  f"min), and med kits out of combat. A KO in a won fight revives at "
  f"{pct(config.KO_REVIVE_HP_FRACTION)}.")


# =========================================================================
h(2, "3. Progression")
w(f"Every hero starts at **rank {config.RANK_START}** in all six attributes "
  f"and trains to **{config.RANK_MAX}**. What differentiates them is the "
  f"innate **boost** table (0–{config.BOOST_MAX}), transcribed from the 1991 "
  f"Impel card backs.")
w()
w(f"`effective_rank = (rank + boost × {config.BOOST_RANK_VALUE}) × "
  f"(1 + boost × {config.BOOST_PCT})`")
w()
w("A boost buys the combat value **and nothing else** — it does not make "
  "the ladder cheaper (M33).")

h(3, "The ladder")
rows = []
cum_xp = cum_cr = 0
for lvl in range(1, config.TRAINED_MAX + 1):
    need = config.XP_TO_NEXT_RANK[lvl]
    per = config.TRAINING_XP_BY_LEVEL[lvl]
    sessions = math.ceil(need / per)
    cost = config.TRAINING_CREDITS_BY_LEVEL[lvl]
    cum_xp += need
    cum_cr += sessions * cost
    lock = config.TRAINING_MINUTES_BY_LEVEL[lvl] * config.TRAINING_LOCKOUT_MULT
    rows.append([f"{lvl} → {lvl + 1}", f"{need:,}", per, sessions,
                 15 + 5 * lvl, f"{cost:,}", mins(lock),
                 f"{sessions * cost:,}", f"{cum_cr:,}"])
table(["Rank", "XP needed", "XP/session", "Sessions", "EN/session",
       "cr/session", "Lockout", "cr for the rank", "cr cumulative"], rows)
w(f"One attribute 1 → {config.RANK_MAX} is **{cum_xp:,} XP** and "
  f"**{cum_cr:,} cr**; all six is **{cum_xp * 6:,} XP**. "
  f"Enlightenment (all six at {config.RANK_MAX} first) is another "
  f"**{config.ENLIGHTENMENT_XP:,} XP**, trained in level-"
  f"{config.TRAINED_MAX} sessions.")
w()
w(f"Facility multiplier on session XP: ×{config.TRAINING_XP_MULT_BASIC} basic, "
  f"×{config.TRAINING_XP_MULT_UPGRADED} upgraded (after the Ch. 1 boss), "
  f"×{config.TRAINING_XP_MULT_EVENT} during a training event. The credit "
  f"price keys off the BASE table, so the upgraded rack is also half price "
  f"per XP.")
w()
w("**Sessions per day** are the lesser of what energy allows and what the "
  "day allows:")
w()
rows = []
for lvl in range(1, config.TRAINED_MAX + 1):
    cost = 15 + 5 * lvl
    left, n = config.DAILY_ENERGY, 0
    while left > cost:
        left -= cost
        n += 1
    day = config.DAY_END_MINUTES - config.DAY_START_MINUTES
    by_clock = day // (config.TRAINING_MINUTES_BY_LEVEL[lvl]
                       * config.TRAINING_LOCKOUT_MULT)
    rows.append([lvl, n, by_clock, min(n, by_clock)])
table(["Level", "by energy", "by clock", "actual"], rows)
w("<sub>0 by clock means the lockout is longer than a single day — the "
  "session still runs, it just spans nights. Energy binds through level 5, "
  "so `TRAINING_LOCKOUT_MULT` first bites at level 6.</sub>")
w()
w("A rank-up **restores the hero to full EN and HP** and chimes, wherever "
  "the XP came from.")

h(3, "Perks")
w(f"Two choices per attribute, at **card ranks "
  f"{' and '.join(str(r) for r in config.PERK_CHOICE_RANKS)}**. Effects are "
  f"flat and stack with gear.")
w()
rows = []
for attribute in config.ATTRIBUTES:
    for tier in sorted(C["perks"][attribute], key=int):
        for perk in C["perks"][attribute][tier]:
            rows.append([attribute.title(), tier, perk["name"],
                         perk["blurb"],
                         ", ".join(f"{k} {v:+}" for k, v in perk["effect"].items())])
table(["Attribute", "Rank", "Perk", "Blurb", "Effect"], rows)

h(3, "XP from the field")
w("Battle XP is paid **per enemy defeated**, to every participating hero "
  f"(KO'd participants get {pct(config.KO_XP_MULT)}), and lands on their six "
  "attributes immediately, split evenly. There is no bank.")
w()
table(["Enemy level"] + list(range(1, 11)),
      [["XP"] + [config.ENEMY_XP_BY_LEVEL[i] for i in range(1, 11)]])

h(3, "Passive assignments (benched heroes)")
table(["Assignment", "Pays", "Requires"],
      [[p["label"],
        ", ".join(f"{k.replace('_per_day', '')}/day: {v}"
                  for k, v in p.items() if k.endswith("_per_day")),
        (f"{p['requires']['attribute'].title()} {p['requires']['min']}+"
         if p.get("requires") else "—")]
       for p in C["passive"].values()])
w(f"After **{config.ATROPHY_GRACE_DAYS}** consecutive days in the same spot "
  f"(or idle), unworked attributes decay by **{config.ATROPHY_XP_PER_DAY} "
  f"XP/day** — banked XP first, then trained ranks.")


# =========================================================================
h(2, "4. Combat")
w("Party size max **" + str(config.PARTY_SIZE_MAX) + "**. Menu order: Basic, "
  "Special, Ultimate, Defend, Item.")
w()
table(["Quantity", "Formula"], [
    ["Max HP", f"{config.HP_BASE} + stamina×{config.HP_PER_STAMINA} + durability×{config.HP_PER_DURABILITY}"],
    ["Battle energy", f"{config.BATTLE_ENERGY_BASE} + intelligence×{config.BATTLE_ENERGY_PER_INT} (refills each battle)"],
    ["Initiative", f"speed×{config.INITIATIVE_SPEED_MULT} + rand{config.INITIATIVE_ROLL}, re-rolled each round"],
    ["Basic damage", f"power + rank×{config.BASIC_SCALING_MULT} − target durability×{config.DURABILITY_REDUCTION_MULT} (min {config.MIN_DAMAGE})"],
    ["Special/ultimate damage", f"power + rank×{config.SPECIAL_SCALING_MULT} − target durability×{config.DURABILITY_REDUCTION_MULT} (min {config.MIN_DAMAGE})"],
    ["Crit chance", f"agility×{config.CRIT_PCT_PER_AGILITY}% → ×{config.CRIT_MULTIPLIER} damage"],
    ["Dodge chance", f"agility×{config.DODGE_PCT_PER_AGILITY}% (rolled after the hit, before crit)"],
    ["Defend", f"×{config.DEFEND_DAMAGE_MULT} incoming until your next turn"],
    ["Ultimate charge", f"+{config.ULT_CHARGE_PER_TURN}/turn, +{config.ULT_CHARGE_PER_HIT}/hit taken, fires at {config.ULT_CHARGE_MAX}; **carries between battles**"],
])
w(f"Status effects: **Burn** {config.BURN_DAMAGE_PER_TURN} dmg/turn for "
  f"{config.BURN_TURNS} turns · **Stun** skip {config.STUN_TURNS} turn.")

h(3, "Signature spreads")
table(["Spread", "Who", "Hits"], [
    ["`adjacent`", "Iron Man — Unibeam",
     "the target plus its immediate living neighbours **in the drawn line** "
     "(a downed body blocks the sweep)"],
    ["`random` + `extra_targets`", "Ant-Man — Pym Particle Barrage",
     "the target plus N others at random"],
    ["`random_range`", "Cap — Shield Throw",
     "the target plus extra_min..extra_max others, decided by coin flips"],
])

h(3, "Enemy AI")
table(["AI", "Behaviour"], [
    ["`aggressive`", "highest-damage action at the lowest-HP target"],
    ["`defensive`", f"guards below {pct(config.AI_DEFENSIVE_HP_THRESHOLD)} HP — "
     f"but never two turns running, and not at all below "
     f"{pct(config.AI_DEFENSIVE_LAST_STAND_HP)}, where it swings with everything"],
    ["`support`", f"heals/buffs an ally below {pct(config.AI_SUPPORT_HP_THRESHOLD)} HP, else attacks"],
])


# =========================================================================
h(2, "5. Heroes")
for cid, char in sorted(HEROES.items(), key=lambda kv: kv[1]["name"]):
    boosts = char["boosts"]
    e1, e10 = entry_at(), entry_at(**{a: config.TRAINED_MAX for a in config.ATTRIBUTES})
    h(3, f"{char['name']}")
    recruit = char["recruit"]
    how = {"starter": "starts with you", "story": "story recruit",
           "bond": f"bond recruit at Bond {recruit.get('bond_level')}"}.get(
        recruit["method"], recruit["method"])
    chapter = ("" if recruit["method"] == "starter"
               else f"Chapter {recruit['chapter']} · ")
    w(f"*{char['rarity'].title()}* · {chapter}{how}"
      + (f" · appears once `{char['appears_flag']}`" if char.get("appears_flag") else ""))
    w(f"Birthday: Issue {char['birthday']['issue']}, Day {char['birthday']['day']}")
    w()
    table(["Attribute", "Boost", "Effective @ rank 1", f"Effective @ rank {config.RANK_MAX}"],
          [[a.title(), boosts.get(a, 0),
            f"{attrs.effective_rank(boosts, e1, a):.2f}",
            f"{attrs.effective_rank(boosts, e10, a):.2f}"]
           for a in config.ATTRIBUTES])
    w(f"At rank 1: **{formulas.max_hp(attrs.effective_rank(boosts, e1, 'stamina'), attrs.effective_rank(boosts, e1, 'durability'))} HP**, "
      f"**{formulas.battle_energy(attrs.effective_rank(boosts, e1, 'intelligence'))} battle EN**, "
      f"crit {formulas.crit_chance(attrs.effective_rank(boosts, e1, 'agility')):.0f}%, "
      f"dodge {formulas.dodge_chance(attrs.effective_rank(boosts, e1, 'agility')):.0f}%. "
      f"At rank {config.RANK_MAX}: **{formulas.max_hp(attrs.effective_rank(boosts, e10, 'stamina'), attrs.effective_rank(boosts, e10, 'durability'))} HP**, "
      f"**{formulas.battle_energy(attrs.effective_rank(boosts, e10, 'intelligence'))} battle EN**, "
      f"crit {formulas.crit_chance(attrs.effective_rank(boosts, e10, 'agility')):.0f}%, "
      f"dodge {formulas.dodge_chance(attrs.effective_rank(boosts, e10, 'agility')):.0f}%.")
    w()
    rows = []
    for ab in char["abilities"]:
        rank1 = attrs.effective_rank(boosts, e1, ab["scales_with"])
        rank10 = attrs.effective_rank(boosts, e10, ab["scales_with"])
        spread = ab.get("spread")
        if spread == "random":
            spread = f"random +{ab['extra_targets']}"
        elif spread == "random_range":
            spread = f"random +{ab['extra_min']}–{ab['extra_max']}"
        rows.append([
            ab["name"], ab["type"], ab["power"], ab["scales_with"][:3].upper(),
            ab.get("cost") or ab.get("charge_required") or "—",
            ab["target"] + (f" ({spread})" if spread else ""),
            formulas.ability_damage(ab["power"], rank1, 0, ab["type"]),
            formulas.ability_damage(ab["power"], rank10, 0, ab["type"]),
            ab.get("applies_status") or ab.get("effect") or "—",
        ])
    table(["Ability", "Type", "Power", "Scales", "Cost", "Target",
           "Dmg @1*", "Dmg @10*", "Effect"], rows)
    w("<sub>* against durability 0 — subtract "
      f"{config.DURABILITY_REDUCTION_MULT}× the target's durability.</sub>")
    w()
    gifts = char["gifts"]
    w("**Gifts** — "
      + " · ".join(f"{cat}: {', '.join(C['items'][i]['name'] for i in gifts[cat]) or '—'}"
                   for cat in ("loved", "liked", "disliked", "hated")))
    for syn in char.get("synergies", []):
        w()
        w(f"**Synergy — {syn['name']}** with "
          f"{C['characters'][syn['with']]['name']}: "
          + ", ".join(f"{k} {v:+}" for k, v in syn["effect"].items())
          + f" (bond {syn['requires_bond_level']}+)")


# =========================================================================
h(2, "6. NPCs")
w("NPCs have no power grid and never fight. They are the talk/gift cast.")
w()
rows = []
for cid, char in sorted(NPCS.items(), key=lambda kv: kv[1]["name"]):
    unlocks = "; ".join(f"Bond {u['level']}: `{u['flag']}`"
                        for u in char.get("bond_unlocks", []))
    rows.append([char["name"], "no" if char.get("bondable") is False else "yes",
                 f"I{char['birthday']['issue']} D{char['birthday']['day']}",
                 unlocks or "—"])
table(["NPC", "Bondable", "Birthday", "Bond unlocks"], rows)
w()
table(["Flag", "Effect"], [
    ["`jarvis_service`", f"+{config.JARVIS_ENERGY_BONUS} energy every morning"],
    ["`pepper_requisitions`", f"shop prices ×{config.PEPPER_SHOP_DISCOUNT}"],
    ["`coulson_intel`", f"mission credits ×{config.COULSON_CREDIT_MULT}"],
])


# =========================================================================
h(2, "7. Enemies")
w("Enemies have no boosts — their `power_grid` **is** their effective rank, "
  f"valid up to {config.ENEMY_RANK_MAX} so bosses can sit above the hero "
  f"ladder. An encounter can ask for a variant at another level with "
  f"`id@level`.")
w()
rows = []
for eid, e in sorted(C["enemies"].items(),
                     key=lambda kv: (kv[1]["name"], kv[1]["level"])):
    g = e["power_grid"]
    rows.append([
        f"`{eid}`", e["name"], e["level"], e["ai"],
        formulas.max_hp(g["stamina"], g["durability"]),
        formulas.battle_energy(g["intelligence"]),
        "/".join(str(g[a]) for a in config.ATTRIBUTES),
        config.ENEMY_XP_BY_LEVEL[e["level"]], e["credit_reward"],
        "boss" if e.get("boss") else "",
    ])
table(["id", "Name", "Lvl", "AI", "HP", "EN", "STR/SPD/AGI/STA/DUR/INT",
       "XP", "cr", ""], rows)

for eid, e in sorted(BASE_ENEMIES.items()):
    if e.get("enrage"):
        w(f"**{e['name']}** enrages below "
          f"{pct(e['enrage']['hp_threshold'])} HP: "
          f"×{e['enrage']['damage_multiplier']} damage.")
w()
w("**Abilities**")
rows = []
for eid, e in sorted(BASE_ENEMIES.items(), key=lambda kv: kv[1]["name"]):
    for ab in e["abilities"]:
        rows.append([e["name"], ab["name"], ab["type"], ab["power"],
                     ab["scales_with"][:3].upper(), ab.get("cost", "—"),
                     ab["target"],
                     ab.get("applies_status") or ab.get("effect") or "—"])
table(["Enemy", "Ability", "Type", "Power", "Scales", "Cost", "Target",
       "Effect"], rows)


# =========================================================================
h(2, "8. Items")
for kind in ("consumable", "gift", "material", "weapon", "armor",
             "accessory", "artifact"):
    items = sorted((i for i in C["items"].values() if i["kind"] == kind),
                   key=lambda i: i["name"])
    if not items:
        continue
    w(f"**{kind.title()}s**")
    w()
    rows = []
    for i in items:
        extra = []
        if i.get("energy"):
            extra.append(f"+{i['energy']} EN (team)")
        if i.get("heal"):
            extra.append(f"+{i['heal']} HP in battle / +{i['heal']}% out")
        if i.get("battle_energy"):
            extra.append(f"+{i['battle_energy']} battle EN")
        if i.get("effects"):
            extra.append(", ".join(f"{k} {v:+}" for k, v in i["effects"].items()))
        rows.append([i["name"], f"`{i['id']}`", f"{i['price']:,}",
                     ", ".join(i["sources"]) or "—", "; ".join(extra) or "—"])
    table(["Item", "id", "Price", "Sources", "Effect"], rows)

w("**Who loves what** — gift reactions are worth "
  + ", ".join(f"{k} {v:+}" for k, v in config.GIFT_POINTS.items())
  + f", ×{config.BIRTHDAY_GIFT_MULTIPLIER} on a birthday.")
w()
liked_by = defaultdict(list)
for cid, char in C["characters"].items():
    for cat in ("loved", "liked", "disliked", "hated"):
        for item_id in char["gifts"][cat]:
            liked_by[item_id].append(f"{char['name']} ({cat})")
table(["Item", "Reactions"],
      [[C["items"][i]["name"], " · ".join(v)]
       for i, v in sorted(liked_by.items(),
                          key=lambda kv: C["items"][kv[0]]["name"])])


# =========================================================================
h(2, "9. Gear")
w("An effect is **either** a flat attribute rank bonus — which is how gear "
  "takes a hero past the trained ceiling of 10 — **or** one of the perk "
  "effect keys, summed with whatever the perks give. Worn or carried, never "
  "both.")
w()
w(f"Upgrade levels belong to the **schematic**, not the object: a level-3 "
  f"Kevlar Weave means the lab builds them that way now. Effects scale "
  f"×1 / ×{1 + config.GEAR_UPGRADE_STEP} / "
  f"×{1 + 2 * config.GEAR_UPGRADE_STEP}, attribute bonuses rounded to whole "
  f"ranks. Max level {config.GEAR_LEVEL_MAX}.")
w()
table(["To level", "Credits", "Materials", "Days at the bench"],
      [[lvl, f"{config.GEAR_UPGRADE_CREDITS[lvl]:,}",
        ", ".join(f"{n}× {C['items'][m]['name']}"
                  for m, n in config.GEAR_UPGRADE_MATERIALS[lvl].items()),
        config.GEAR_UPGRADE_DAYS[lvl]]
       for lvl in sorted(config.GEAR_UPGRADE_CREDITS)])
w("Nothing is applied until the piece is **collected in person**; the team "
  "fights without it in the meantime.")


# =========================================================================
h(2, "10. The tower")
from game.hub.tower import FLOORS, FLOOR_ORDER, FLOOR_REQUIRES, STATION_FLOOR  # noqa: E402
rows = []
for floor in FLOOR_ORDER:
    hours = config.ROOM_HOURS.get(floor)
    flag, why = FLOOR_REQUIRES.get(floor, (None, ""))
    stations = [k for k, f in STATION_FLOOR.items() if f == floor]
    rows.append([
        FLOORS[floor]["name"], f"`{floor}`",
        f"{clock.format_time(hours[0])}–{clock.format_time(hours[1])}" if hours else "always open",
        "**locks**" if floor in config.CLOSED_FLOORS_LOCK_OUT else ("station only" if hours else "—"),
        f"`{flag}`" if flag else "—",
    ])
table(["Floor", "id", "Hours", "When shut", "Needs flag"], rows)
w()
table(["Room", "Operator", "What they run"], [
    ["Tech Lab", "Jarvis", "the fabricator — talk once, then he opens it"],
    ["Pym Lab", "Hank Pym", "the upgrade bench"],
    ["Med Bay", "two S.H.I.E.L.D. autodocs", "the treatment chair (not bondable)"],
    ["Common Floor", "Jarvis, Coulson", "talk, gifts, the board"],
    ["Ops Floor", "Pepper Potts", "the ops console, the Quinjet bay"],
])
w()
w(f"**Bag capacity** is derived from who is on the team: "
  f"{config.INVENTORY_SLOTS_PER_HERO} slots per active member, "
  f"{config.INVENTORY_SLOTS_MAX} at a full party of "
  f"{config.PARTY_SIZE_MAX}. One slot holds up to "
  f"{config.INVENTORY_STACK_MAX} of one item.")


# =========================================================================
h(2, "11. Tower repairs")
w("Accepted at the board (or raised in conversation), then **worked in "
  "person**. One at a time. Fitting costs nothing — the hunt is the price.")
w()
rows = []
for job in C["repairs"]:
    kinds = Counter(repairs_mod.part_kind(p) for p in job["parts"])
    heavy = sum(1 for p in job["parts"] if p.get("heavy"))
    req = job.get("requires", {})
    gate = ", ".join([f"`{f}`" for f in req.get("flags", [])]
                     + [f"quest *{q}*" for q in req.get("quests", [])])
    rows.append([
        job["name"], f"`{job['id']}`",
        FLOORS[job["floor"]]["name"], len(job["parts"]),
        " ".join(f"{n} {k}" for k, n in sorted(kinds.items())),
        heavy * config.REPAIR_PART_ENERGY, job["xp"],
        (job.get("trigger") or {}).get("character", "board"),
        gate or "—", f"`{job['flag']}`",
    ])
table(["Repair", "id", "Floor", "Parts", "Kinds", "EN cost", "XP",
       "Offered by", "Gated on", "Sets"], rows)
w("Part kinds: **plain** (a marker shows it) · **hidden** (inside furniture "
  "or a seam, no marker) · **npc** (handed over in conversation) · "
  "**battle** (drops from a won fight) · **mine** (rolls out of any ore "
  "seam).")
w()
w("Every part, in order:")
w()
rows = []
for job in C["repairs"]:
    for i, part in enumerate(job["parts"]):
        kind = repairs_mod.part_kind(part)
        if kind == "npc":
            where = f"from {part['from']}" + (
                f" (after {part['after_found']} found)"
                if part.get("after_found") else "")
        elif kind == "battle":
            spec = part["battle"]
            where = ("certain with " + spec["with"] if spec.get("with")
                     else f"{pct(spec['chance'])} per win")
        elif kind == "mine":
            where = f"{pct(part['mine']['chance'])} per swing, any seam"
        else:
            where = f"{part['area']} ({part['x']}, {part['y']})"
        rows.append([job["name"] if i == 0 else "", i, kind, where,
                     "heavy" if part.get("heavy") else ""])
table(["Repair", "#", "Kind", "Where", ""], rows)


# =========================================================================
h(2, "12. Zones & the field")
rows = []
for z in sorted(C["zones"].values(), key=lambda z: z["danger"]):
    crates = sum(r.count("x") for r in z["map"])
    seams = sum(r.count("o") for r in z["map"])
    trees = sum(r.count("p") for r in z["map"])
    rows.append([z["name"], f"`{z['id']}`", "!" * z["danger"],
                 field.ambush_rate(z), pct(z["danger"] * config.SEARCH_TRAP_CHANCE),
                 crates, seams, trees])
table(["Zone", "id", "Danger", "Ambush rate", "Trap chance", "Crates",
       "Ore seams", "Trees"], rows)
w("`danger` drives the badge, the trap risk and the enemy pool. "
  "`ambush_rate` drives how often you are jumped — a separate knob that "
  "currently agrees with danger.")

h(3, "Ambush probability")
w(f"One roll per **{config.AMBUSH_TICK_SECONDS} seconds of walking** "
  f"(standing still never rolls). "
  f"`chance = ambush_rate × ({config.AMBUSH_BASE_CHANCE} + "
  f"{config.AMBUSH_PARTY_BONUS} × missing party members)`.")
w()
zones = sorted(C["zones"].values(), key=lambda z: field.ambush_rate(z))
table(["Party"] + [z["name"] for z in zones],
      [[size] + [
          f"{field.ambush_chance(field.ambush_rate(z), size) * 100:.1f}% "
          f"(1 per {config.AMBUSH_TICK_SECONDS / field.ambush_chance(field.ambush_rate(z), size):.0f}s)"
          for z in zones]
       for size in (4, 3, 2, 1)])
w(f"Capped at **{config.AMBUSH_DAILY_CAP} field fights per zone per day** — "
  f"ambushes and sprung traps share the budget. Cleared at sleep.")
w()
w("**Squad size** — an ambush always outnumbers the party:")
w()
table(["Extra attackers", "Chance"],
      [[v, pct(c - (config.AMBUSH_SIZE_TABLE[i - 1][0] if i else 0))]
       for i, (c, v) in enumerate(config.AMBUSH_SIZE_TABLE)])
table(["Party size", "Hard cap on the squad"],
      [[k, v] for k, v in sorted(config.AMBUSH_MAX_BY_PARTY.items())])
w(f"Absolute maximum {config.AMBUSH_MAX_SIZE}. Trap squads roll "
  f"2..cap with no outnumber guarantee.")
w()
w("**Who turns up**, by danger:")
w()
table(["Danger", "Pool"],
      [[k, ", ".join(f"{n}× {C['enemies'][e]['name']}"
                     for e, n in Counter(v).items())]
       for k, v in sorted(field._POOLS.items())])

h(3, "Loot & mining")
rows = []
for z in sorted(C["zones"].values(), key=lambda z: z["danger"]):
    loot = z["loot"]
    lo, hi = loot["credits"]
    rows.append([z["name"], pct(loot["find_chance"]), f"{lo}–{hi} cr",
                 pct(loot["item_chance"]),
                 ", ".join(C["items"][i]["name"] for i in loot["items"]),
                 f"~{sum(r.count('x') for r in z['map']) * loot['find_chance'] * (lo + hi) / 2:.0f} cr/day"])
table(["Zone", "Find chance", "Credits", "Item chance", "Possible items",
       "Expected/day"], rows)
w("<sub>Rolled after the trap check; a trap forfeits the loot.</sub>")
w()
rows = []
for z in sorted(C["zones"].values(), key=lambda z: z["danger"]):
    total = sum(z["mining"].values())
    rows.append([z["name"],
                 ", ".join(f"{C['items'][m]['name']} {pct(c)}"
                           for m, c in sorted(z["mining"].items())),
                 pct(1 - total)])
table(["Zone", "Yields", "Dust"], rows)
w(f"One swing per seam per day, {config.MINE_ENERGY} EN each.")


# =========================================================================
h(2, "13. Story")
w("Quests unlock strictly in order. A quest is **offered** at the Ops "
  "Console and shows nothing in the field until accepted; the deadline "
  "starts at accept.")
w()
rows = []
for i, q in enumerate(C["story"], 1):
    enemies = Counter(C["enemies"][e]["name"] for e in q.get("enemies", []))
    rows.append([
        i, q["name"], f"`{q['id']}`", f"Ch{q['chapter']}", q["kind"],
        C["zones"][q["location"]]["name"] if q.get("location") in C["zones"] else "—",
        q.get("deadline_days", "—"),
        ", ".join(f"{n}× {e}" for e, n in enemies.items())
        or (f"{len(q['scout_points'])} scout points" if q.get("scout_points") else "—"),
        q.get("recruit") or "—",
        ", ".join(f"`{f}`" for f in q.get("flags", {})) or "—",
    ])
table(["#", "Quest", "id", "Ch", "Kind", "Where", "Deadline", "Opposition",
       "Recruits", "Sets"], rows)
w(f"A failed mission cools down **{config.MISSION_FAIL_COOLDOWN_DAYS} days**. "
  f"A *fight* mission then re-arms itself in the field; anything else has to "
  f"be re-accepted at Ops.")
w()
w("**Chapter 3–4 gate:** every Ch. 1–2 mission complete **and** the tower "
  "fully repaired.")


# =========================================================================
h(2, "14. Side arcs")
w("Conditional arcs run *alongside* the story chain, so one can sit dormant "
  "without stalling the missions behind it. Requirements are re-checked at "
  "the sleep boundary.")
w()
for arc in C["unlocks"]:
    req = arc["requires"]
    w(f"### {arc['name']}")
    w(f"*{arc['desc']}*")
    w()
    ranks = ", ".join(f"{C['characters'][h]['name']} rank {r} in all six"
                      for h, r in req.get("hero_min_rank", {}).items())
    table(["", ""], [
        ["Opens when", ", ".join(f"`{f}`" for f in req.get("flags", []))
         + (f"; {ranks}" if ranks else "")],
        ["Where", C["zones"][arc["location"]]["name"]],
        ["Search sites", f"{len(arc['search_groves'])} stands "
         f"({config.UNLOCK_SEARCH_ENERGY} EN each)"],
        ["Prize", C["items"][arc["item"]]["name"]],
        ["Who can lift it", C["characters"][arc["lift_requires"]]["name"]
         + " — must be on the ACTIVE team"],
        ["Recruits", C["characters"][arc["recruit"]]["name"]],
        ["Sets", ", ".join(f"`{f}`" for f in arc.get("flags", {}))],
        ["Sound", arc.get("signal_scene", {}).get("sound", "—")],
    ])


# =========================================================================
h(2, "15. The assignment board")
w("Every job is **one-shot**. Two rotating jobs per unlocked tier per day. "
  "Repairs take a slot. Skill requirements are never advertised — sending "
  "the wrong hero gets a refusal in Coulson's voice.")
w()
w(f"Tier unlocks by team power (sum of the top-{config.PARTY_SIZE_MAX} "
  f"roster heroes' effective grid totals): "
  + ", ".join(f"tier {t} at {p}" for t, p in sorted(config.BOARD_TIER_POWER.items())))
w()
w("Dispatch pay multiplier = "
  f"1 + {config.DISPATCH_POWER_BONUS} × (avg sent-hero grid total − "
  f"{config.DISPATCH_POWER_BASELINE}), clamped "
  f"{config.DISPATCH_MULT_MIN}–{config.DISPATCH_MULT_MAX}, snapshotted when "
  f"the job starts.")
w()
w("XP budget per tier (vs the passive train assignment at "
  f"{config.PASSIVE_TRAIN_XP_PER_DAY} XP/day): "
  + ", ".join(f"tier {t} ×{m} = {config.board_tier_xp_per_day(t):.0f}/day"
              for t, m in sorted(config.BOARD_TIER_XP_MULT.items())))
w()
rows = []
for task in sorted(C["assignments"], key=lambda t: (t.get("tier", 1), t["name"])):
    req = task.get("requires") or {}
    gates = []
    if req.get("flag"):
        gates.append(f"flag `{req['flag']}`")
    if req.get("bond"):
        gates.append(f"{req['bond']['character']} bond {req['bond']['level']}+")
    for clause in req.get("hero_any_of", []):
        bits = "/".join(a[:3].upper() for a in clause.get("attributes", []))
        want = " or ".join(
            f"{k.replace('min_', '')} {v}+" for k, v in clause.items()
            if k != "attributes")
        gates.append(f"{bits} {want}")
    if req.get("hero_all_attributes"):
        gates.append(f"all six rank {req['hero_all_attributes']['min_rank']}+")
    posting = task.get("posting")
    rows.append([
        task.get("tier", 1), task["name"], f"`{task['id']}`",
        f"{task['heroes']}H/{task['days']}D", f"{task['credits']:,}",
        f"{task['xp']} → " + (", ".join(a[:3].upper() for a in task["trains"])
                              if task.get("trains") else "all six"),
        (f"+{task['bond']} {task['requested_by']}"
         if task.get("bond") else "—"),
        "; ".join(gates) or "—",
        ("/".join(pct(c) for c in posting["chance_by_bond_level"])
         + f" by {posting['bond_character']} bond" if posting else "always"),
    ])
table(["Tier", "Job", "id", "Crew", "cr", "XP", "Bond", "Requires",
       "Posting odds"], rows)
by_tier = defaultdict(int)
for t in C["assignments"]:
    by_tier[t.get("tier", 1)] += t["credits"]
w("Total one-shot board income: **"
  + " + ".join(f"{v:,} (tier {k})" for k, v in sorted(by_tier.items()))
  + f" = {sum(by_tier.values()):,} cr**, before the crew multiplier. Once "
    "cleared, the board is done — missions, ambush drops and zone loot are "
    "the only repeatable income.")


# =========================================================================
h(2, "16. Bonds")
w(f"**{config.BOND_POINTS_PER_LEVEL} points per level**, "
  f"{config.BOND_LEVEL_MAX} levels, "
  f"{config.BOND_LIFETIME_MAX:,} lifetime max.")
w()
table(["Action", "Points"], [
    ["Daily talk (once per character)", f"+{config.BOND_TALK_POINTS}"],
    ["Same-party mission", f"+{config.BOND_MISSION_POINTS}"],
] + [[f"{k.title()} gift", f"{v:+}"] for k, v in config.GIFT_POINTS.items()] + [
    ["Birthday", f"×{config.BIRTHDAY_GIFT_MULTIPLIER}"],
    ["Repeating yesterday's gift", f"−{config.GIFT_REPEAT_PENALTY} (after the multiplier)"],
    ["Personal quest", f"+{config.BOND_PERSONAL_QUEST_MIN}–{config.BOND_PERSONAL_QUEST_MAX}"],
])
w(f"Gift limits: **1 per receiver per day**, max "
  f"**{config.GIFTS_PER_WINDOW} per rolling {config.GIFT_WINDOW_DAYS} days**.")
w()
table(["Level", "Gate"], [
    [config.BOND_GATE_SCENE, "bond scene"],
    [config.BOND_GATE_RECRUIT, "relationship recruit"],
    [config.BOND_GATE_SYNERGY, "synergy passive"],
    [config.BOND_GATE_GEAR, "exclusive gear quest"],
    [config.BOND_GATE_SIGNATURE, "signature scene + costume"],
])
w("**Authored bond scenes**")
w()
table(["id", "Character", "Level", "Title"],
      [[f"`{s['id']}`", C["characters"][s["character"]]["name"], s["level"],
        s["title"]] for s in C["bond_scenes"]])
w("Starters and story recruits give flavour talk only — no points.")


# =========================================================================
h(2, "17. Calendar")
w(f"An Issue is **{config.DAYS_PER_ISSUE} days**, in "
  f"{config.DAYS_PER_ISSUE // config.DAYS_PER_WEEK} weeks of "
  f"{config.DAYS_PER_WEEK}.")
w()
table(["Issue", "Name", "Days"],
      [[i["number"], i["name"], i["days"]] for i in C["calendar"]["issues"]])
table(["Event", "When", "Effects"],
      [[e["name"], f"Issue {e['issue']}, days {e['start_day']}–{e['end_day']}",
        ", ".join(f"{k}: {v}" for k, v in e["effects"].items())]
       for e in C["calendar"]["events"]])
w("**Birthdays** — "
  + " · ".join(f"{c['name']} I{c['birthday']['issue']}D{c['birthday']['day']}"
               for c in sorted(C["characters"].values(),
                               key=lambda c: (c["birthday"]["issue"],
                                              c["birthday"]["day"]))))


# =========================================================================
h(2, "18. The save file")
from game.core import save as save_mod                      # noqa: E402
w(f"One JSON per slot at `{config.SAVE_DIR}/slot_N.json`, "
  f"{config.SAVE_SLOTS} independent games, one `.bak` kept. "
  f"**The autosave at lights-out is the only save.**")
w()
table(["Key", "Holds"], [
    [f"`{k}`", type(v).__name__ + (f" = {v!r}" if not isinstance(v, (dict, list)) else "")]
    for k, v in sorted(save_mod.new_game_state().items())])
w()
w("Per-hero roster entry: `trained_ranks`, `attribute_xp`, `perks`, "
  "`perk_choices`, `gear`, `ult_charge`, `energy`, `hp_fraction`, plus "
  "transient `training` / `dispatch` / `assignment` / `done_training` / "
  "`leveled_up` / `mastered` / `enlightened`.")
w()
w("Every key added after M16 is read through `.get`/`.setdefault`, so an "
  "older save loads and plays. Migrations run at load: pre-M13 dispatch "
  "spots, pre-M16 training locks, pre-M29 tower state, pre-M36 perk tiers, "
  "story-flag backfill, and the M21 battle-XP bank.")

w()
w("---")
w()
w(f"*Generated by `tools/build_bible.py` from {len(C['characters'])} "
  f"characters, {len(C['enemies'])} enemy entries, {len(C['items'])} items "
  f"and {len([k for k in dir(config) if k.isupper()])} tuned constants.*")


os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(L) + "\n")
print(f"wrote {OUT}  ({len(L)} lines)")
