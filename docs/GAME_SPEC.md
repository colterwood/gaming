# Marvel: Roads to Secret Wars — POC Build Spec (v0.2)

This is the working implementation spec. It lives in `/docs` of the repo and is the
document Claude Code reads and builds from. The .docx GDD is the human-readable
design reference; this file is the source of truth for code.

---

## 1. What We're Building (and Not Building)

**POC scope:** Chapters 1–2 of the Avengers path only.

- 2 starting heroes (Iron Man, Captain America), 1 recruitable hero (Ant-Man)
- 1 hub (Avengers Tower, 3 rooms), working day/energy loop
- Turn-based combat vs. HYDRA enemies, 2 boss fights
- Bond system (talk, gifts, 1 bond event)
- Attribute training for the six-stat power grid
- Pause screen styled as a 1991 Impel Marvel card back
- JSON save/load

**Explicit non-goals for the POC:** other paths, world map travel, crafting depth,
audio, animation polish, controller support, Battleworld. Do not build these.

**Legal:** Marvel IP — portfolio/personal project only. Not for sale or distribution.

---

## 2. Stack

- Python 3.11+
- `pygame-ce` (community edition — actively maintained, drop-in pygame replacement)
- `pytest` for logic tests
- All game content in JSON data files; code never hardcodes character/item data
- No other dependencies unless a milestone demands it

Design rule: **keep game logic pure and rendering thin.** Combat math, bond math,
XP math, and the day clock live in plain-Python modules with no pygame imports,
so they're unit-testable. Pygame code only draws state and collects input.

If this outgrows a POC, the migration path is Godot. The JSON data layer is
designed to survive that port; the Python code is not, and that's fine.

---

## 3. Repo Layout

```
secret-wars-poc/
├── CLAUDE.md                  # Claude Code project instructions (template in §10)
├── docs/
│   └── GAME_SPEC.md           # this file
├── game/
│   ├── __main__.py            # entry point: python -m game
│   ├── config.py              # tunable constants (all numbers from this spec)
│   ├── core/
│   │   ├── state_machine.py   # game states + transitions
│   │   ├── clock.py           # in-game time
│   │   ├── energy.py          # daily energy
│   │   ├── calendar.py        # issues/days/birthdays/events
│   │   └── save.py            # JSON save/load
│   ├── combat/
│   │   ├── engine.py          # turn loop, action resolution
│   │   ├── formulas.py        # pure math (damage, crit, dodge, initiative)
│   │   ├── entities.py        # Combatant built from character JSON + trained ranks
│   │   └── enemy_ai.py        # simple AI (see §7)
│   ├── social/
│   │   ├── bonds.py           # bond points, levels, gift limits (M12 rolling window)
│   │   └── events.py          # bond-event triggering
│   ├── progression/
│   │   ├── attributes.py      # training XP, ranks, perk choices
│   │   └── mastery.py         # stub for POC
│   ├── hub/
│   │   ├── tower.py           # hub scene + activity menu
│   │   └── activities.py      # activity definitions/costs/effects
│   ├── ui/
│   │   ├── impel_card.py      # pause screen card renderer
│   │   ├── binder.py          # 9-pocket collections page
│   │   └── widgets.py         # bars, menus, text boxes
│   └── data_loader.py         # JSON loading + schema validation
├── data/
│   ├── characters/            # one file per character
│   ├── enemies/
│   ├── items.json
│   ├── quests/
│   └── calendar.json
├── assets/
│   ├── reference/             # ← drop 2–3 Impel card-back scans here
│   └── sprites/               # colored-rectangle placeholders are fine
└── tests/
```

---

## 4. Game States

```
BOOT → TITLE → PATH_SELECT → HUB ⇄ BATTLE
                              HUB ⇄ PAUSE (Impel card UI)
                              HUB → SLEEP → (next day) → HUB
```

`PATH_SELECT` shows five "issue #1 covers"; only Avengers is selectable in the POC
(others greyed out). The state machine is the M0 deliverable — every later system
plugs into it.

---

## 5. Data Schemas

### 5.1 Character (`data/characters/iron_man.json`)

```json
{
  "id": "iron_man",
  "name": "Iron Man",
  "path": "avengers",
  "rarity": "legendary",
  "boosts": {
    "strength": 6, "speed": 6, "agility": 3,
    "stamina": 4, "durability": 5, "intelligence": 5
  },
  "abilities": [
    {"id": "repulsor_blast", "name": "Repulsor Blast", "type": "basic",
     "power": 12, "scales_with": "intelligence", "target": "single"},
    {"id": "unibeam", "name": "Unibeam", "type": "special",
     "power": 30, "cost": 12, "scales_with": "intelligence", "target": "single"},
    {"id": "house_party", "name": "House Party Protocol", "type": "ultimate",
     "power": 55, "charge_required": 100, "scales_with": "intelligence", "target": "all"}
  ],
  "gifts": {
    "loved": ["rare_alloy", "double_espresso"],
    "liked": ["tech_scrap", "vintage_vinyl"],
    "disliked": ["magnets"],
    "hated": ["paperwork"]
  },
  "birthday": {"issue": 2, "day": 14},
  "synergies": [
    {"with": "captain_america", "name": "Old Friends",
     "effect": {"crit_bonus": 8}, "requires_bond_level": 6}
  ],
  "recruit": {"chapter": 1, "method": "story"}
}
```

> `boosts` are the innate-talent table (M15), transcribed from the printed
> ratings on the real 1991 card backs — Iron Man's above are his actual
> Series II ratings. They run 0..`BOOST_MAX` (7); 0 means no natural talent.
> Boosts are NOT the hero's rank: every hero starts at rank 1 in all six and
> trains toward `RANK_MAX` (10). See §6.3 for how the two combine, both in
> combat and in what a rank costs to train.
>
> Note the card-derived roster has at least 1 in every attribute, so a board
> requirement of `min_boost: 1` would accept every current hero — M16 raised
> the shipped thresholds accordingly.

### 5.2 Enemy (`data/enemies/hydra_grunt.json`)

Same shape as character minus gifts/birthday/synergies, plus:
`"ai": "aggressive" | "defensive" | "support"`, `"level"` (1–10, the XP
tier — M16 replaced the old per-enemy `xp_reward`), and `"credit_reward"`.
Enemies keep a flat `power_grid` (no boosts) whose values ARE their effective
ranks, valid 1..`ENEMY_RANK_MAX` (20) so bosses can sit above the hero ladder.

### 5.3 Item (`data/items.json` entries)

```json
{"id": "double_espresso", "name": "Double Espresso", "kind": "gift",
 "price": 40, "sources": ["tower_cafe"]}
```

`kind`: `gift | consumable | weapon | armor | accessory | artifact | material`.
Equipment adds `"slot"` and `"effects"` (flat stat mods only in POC).

### 5.4 Save file

One JSON per slot: current day/issue/time, energy, roster (per hero: trained
ranks, attribute XP, chosen perks, equipped gear, ultimate charge), bond points +
gift history (gift_days/last_gift) per character, inventory, credits, story
flags, quest states.
Write to `saves/slot_N.json`, keep one `.bak` of the previous save.

---

## 6. Core Numbers (all live in `config.py`)

### 6.1 Clock & Energy

| Constant | Value |
|---|---|
| Day span | 6:00 → 26:00 (2 AM) |
| Tick | 10 in-game minutes per 7 real seconds (cosmetic in POC; activities also advance the clock in fixed jumps) |
| Daily energy | 100 |
| Training session | trainee EN 15+5/level; a LOCKOUT of TRAINING_MINUTES_BY_LEVEL (level 1 = 50 min, level 9 = 2,400) measured in WAKING minutes, so high-level sessions span days — see §6.3 |
| Battle (ambush/trap, won) | +1 h clock (M12 BATTLE_MINUTES) |
| Battle defeat | +3 h clock, party capped at 10 EN, dragged to the tower; the day does NOT end (M12) |
| Combat mission | 40 energy, +3 h clock; never refused for low EN (M11) — the team drains toward 0 and fights with the M9 initiative penalty |
| Craft action | 15 energy, +60 min |
| Scout point (M13, replaces hub small tasks) | 5 energy, +20 min per point |
| Talk / gift | 0 energy, +20 min |
| Eat a ration (M10) | 0 energy, +10 min; restores the item's `energy` EN to one party member, capped at 100 |
| Search a zone crate (M10) | 0 energy, +15 min; daily-respawning loot, trap risk scales with danger |
| Pass out (0 energy or 2 AM) | next day starts at 80 energy |

### 6.2 Bonds

| Action | Points |
|---|---|
| Daily talk | +15 (once/day/character) |
| Same-party mission | +10 per mission |
| Loved gift | +80 |
| Liked gift | +45 |
| Neutral gift | +20 |
| Disliked gift | −20 |
| Hated gift | −40 |
| Birthday multiplier | ×8 |
| Personal quest | +150 to +250 |

- 250 points per Bond Level; 10 levels; 2,500 lifetime max.
- Gift limits (M12, replaces the weekly cap): 1 gift per receiver per day,
  max 2 per receiver per rolling 5 days (GIFT_WINDOW_DAYS/GIFTS_PER_WINDOW);
  repeating yesterday's gift to the same receiver costs 5 points
  (GIFT_REPEAT_PENALTY, applied after the birthday multiplier).
- Level gates: 2 = bond scene, 4 = relationship recruit, 6 = synergy passive,
  8 = exclusive gear quest, 10 = signature scene + costume.
- POC content: Cap's Level-2 bond scene; Ant-Man recruit is quest-based (story),
  Shang-Chi's bond-recruit is post-POC.

> **Relationship redesign (post-POC):** bonding gameplay moved off the
> starting heroes and onto NPCs + bond-recruits. Starters/story recruits
> (`recruit.method` "starter"/"story") give flavor talk only — no points —
> and the IM+Cap "Old Friends" synergy is innate. Characters with method
> "bond" (Hulk, card-authentic grid, appears after the Ch. 1 boss via
> `appears_flag`) join the roster at `recruit.bond_level`. Characters with
> method "npc" (Jarvis, Pepper Potts, Coulson — no power grid/abilities)
> are the talk/gift cast: Level-2 bond scenes and Level-4 `bond_unlocks`
> that set story flags with real effects (Jarvis +10 daily energy, Pepper
> 20% shop discount, Coulson +50% mission credits; constants in config).

### 6.3 Attributes & Training  *(reworked in M15)*

- Six attributes. Every hero **starts at rank 1 in all six** and trains up to
  `RANK_MAX = 10` (trained ranks 0–`TRAINED_MAX` 9).
- What makes a character feel like themselves is their **innate boost table**
  (`boosts` in the character JSON, 0–`BOOST_MAX` 7; 0 means no natural
  talent). This is the old
  card-back power grid, repurposed — Iron Man is Strength/Speed 6,
  Durability/Intelligence 5, Stamina 4, Agility 3.
- Combat uses:
  `effective_rank = (rank + boost × BOOST_RANK_VALUE) × (1 + boost × BOOST_PCT)`
  with `BOOST_RANK_VALUE = 0.5` and `BOOST_PCT = 0.01`. The flat half-rank
  makes talent visible at rank 1 (Iron Man Strength 4.24 vs Cap 2.04); the
  percentage widens the gap as ranks climb (13.78 vs 11.22 at rank 10), so a
  fully-trained Iron Man still out-hits a fully-trained Cap on Strength while
  Cap keeps his Agility edge. Both constants are single-line tunables.
- Enemies have no boosts — their `power_grid` IS the effective rank, and
  bosses may be written above the hero ladder up to `ENEMY_RANK_MAX` (20).
- **Rank costs grow 1.5× per level** (M16, `XP_TO_NEXT_RANK`), keyed by the
  level you are climbing FROM:

  | from level | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
  |---|---|---|---|---|---|---|---|---|---|
  | XP | 100 | 150 | 225 | 340 | 510 | 760 | 1,140 | 1,710 | 2,560 |

- **Costs are boost-weighted** (M16b): the table above is multiplied by
  `BOOST_XP_WEIGHT_BASE - BOOST_XP_WEIGHT_STEP × boost` (1.5 - 0.1 × boost),
  so training with the grain is cheap and fighting your own nature is a
  slog. Boost 5 is the neutral point; boost 7 pays 0.8× and boost 0 pays
  1.5×. Atrophy refunds the same weighted amount when a rank decays.

  | boost | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
  |---|---|---|---|---|---|---|---|---|
  | cost × | 1.50 | 1.40 | 1.30 | 1.20 | 1.10 | 1.00 | 0.90 | 0.80 |
  | days for that attribute 1→10 | 30 | 27 | 26 | 24 | 23 | 21 | 18 | 17 |

  Mastery (all six at rank 10) therefore costs ~46k–54k XP and lands at
  **125–146 in-game days per hero**, character-shaped: Hulk masters
  Strength in 17 days and Speed in 26, Iron Man the reverse. Because
  benched heroes train in parallel (party caps at 4, the rest can all be
  on the mats), a full roster masters in roughly the same calendar time as
  one hero.
- **A rack session yields and costs** by the level being trained (M16,
  `TRAINING_XP_BY_LEVEL` / `TRAINING_MINUTES_BY_LEVEL`; energy stays
  `15 + 5 × level`):

  | level | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
  |---|---|---|---|---|---|---|---|---|---|
  | XP | 25 | 35 | 50 | 80 | 135 | 225 | 400 | 700 | 1,200 |
  | lockout (min) | 50 | 70 | 100 | 160 | 270 | 450 | 800 | 1,400 | 2,400 |
  | sessions to rank up | 4 | 6 | 8 | 10 | 12 | 15 | 16 | 19 | 22 |

  The facility multiplies the yield: ×1 basic, ×2 upgraded (after the
  Ch. 1 boss), ×3 during a training event. Training costs energy and a
  lockout — it never costs XP (M12).
- **Lockouts are measured in WAKING minutes and may span days** (M16). A
  day holds 1,200 usable minutes (6:00–26:00), so a level-8 session runs
  1d 3h and a level-9 session exactly 2 days. `clock.absolute_minutes`
  counts elapsed waking time; sleeping banks the rest of that day rather
  than short-circuiting the session.
- Perk choice at trained ranks 3 and 6: two options per attribute, flat effects
  in POC. Define perk tables in `data/perks.json`.
- Mastery (all six at rank 10) is a stub in POC: detect it, show the foil
  treatment, log Mastery XP, no perk shop yet.

### 6.4 Combat Formulas (`combat/formulas.py` — pure functions, unit-tested)

Let ranks be **effective** ranks (§6.3: trained rank lifted by the innate
boost, so a hero's effective value legitimately exceeds 10).

```
max_hp        = 50 + stamina*20 + durability*10
battle_energy = 20 + intelligence*5          (spent by Specials, refills each battle)
initiative    = speed*10 + rand(1,6)          (recomputed each round)
basic_damage  = ability.power + scaling_rank*4 - target.durability*2   (min 1)
special_damage= ability.power + scaling_rank*5 - target.durability*2   (min 1)
crit_chance   = agility*4  (percent; crit = damage × 1.5)
dodge_chance  = agility*3  (percent; roll after hit roll, before crit)
battle XP     = per enemy DEFEATED, from its level (M16 ENEMY_XP_BY_LEVEL):
                lvl 1-10 -> 12, 24, 36, 54, 72, 90, 114, 138, 162, 192.
                Banked per participating hero; KO'd participants get
                KO_XP_MULT (50%). No XP on a loss.
ultimate      = +20 charge per turn taken, +10 per hit received; fires at 100
                (M15: charge CARRIES OVER between battles — banked to the
                 roster entry on finish_battle, restored on the next one)
```

Party size 4 (POC uses 2–3). Menu order (M15): **Basic, Special, Ultimate,
Defend, Item** — rows show the character's own ability names, with the
Special row tinted like the energy bar (sky) and the Ultimate row like the
ultimate bar (gold); no "(N EN)" suffix. Status effects in POC: Burn
(5 dmg/turn, 3 turns) and Stun (skip 1 turn) only.

**Signature spread (M15).** A single-target ability may carry a `spread`:

| spread | who | effect |
|---|---|---|
| `adjacent` | Iron Man — Unibeam | the target plus its immediate neighbours in the enemy line |
| `random` + `extra_targets` | Ant-Man — Pym Particle Barrage | the target plus 2 other random enemies (3 distinct in total) |
| `random_range` + `extra_min`/`extra_max` | Cap — Shield Throw | the target plus 2 or 3 others, the count decided by a coin flip |

Targets are always distinct and a spread never exceeds the living enemies.

**Boss balance (M15).** Bosses previously fielded fewer bodies than an
ambush and fell in 2–3 rounds. They now field real escorts and enough bulk
to survive a party's ultimates. Measured win rates for the party the player
realistically brings (Iron Man + Cap + Ant-Man, competent play):

| fight | rank 1 | rank 2 | rank 3 |
|---|---|---|---|
| Siege of the Tower (Captain HP 260 + 3 grunts + 2 enforcers) | ~41% | ~100% | 100% |
| Crossbones (HP 380 + medic + 2 enforcers + grunt) | ~3% | ~77% | 100% |

Ordinary patrols and ambushes stay at ~100% — they are attrition, not walls.
Boss 1 (Ch. 1): HYDRA Siege Captain + escort. Boss 2 (Ch. 2): Crossbones —
enrages below 30% HP (+50% damage).

### 6.5 Enemy AI (POC)

- `aggressive`: highest-damage available action at lowest-HP target
- `defensive`: Defend below 40% HP, else basic attack
- `support`: heal/buff ally if one is below 50% HP, else basic attack

---

## 7. Hub & Day Loop (POC content)

Avengers Tower rooms and activities:

| Room | Activities |
|---|---|
| Common Floor | Talk to present heroes, give gifts, assignment board (2 rotating tasks per day per unlocked board tier; dispatch jobs — see §9 M10/M11) |
| Training Floor | Attribute training (pick hero + attribute); upgrades to tier 2 via story flag after Ch. 1 boss |
| Ops Floor | Story missions are OFFERED here (M13): accept one to start its deadline and make its target/scout points appear in the field; view quest log |

Sleep sequence: fade out → advance calendar → reset energy/talk flags →
autosave → fade in. (Gift limits are the M12 rolling window — nothing weekly
to reset.)

Calendar POC content: Issue 1 (28 days), Cap's birthday on Issue 1 Day 20, one
2-day mini-event ("S.H.I.E.L.D. Supply Drop": shop discount + bonus training XP).

---

## 8. Pause Screen — Impel Card UI (M5)

Full-screen card back at 1280×720 internal resolution (scale to window).

Layout zones (px, at 1280×720):

- Outer card frame: 24 px margin, rounded corners, border trim
- Tab strip (top, above the card): 7 tabs — Inventory, Attributes, Social,
  Collections, Tasks, Map (greyed in POC), Options
- Header banner inside card: 64 px tall, character name in block lettering
- Portrait panel: upper-left, 300×340
- Power grid: right column, six rows × 44 px; each row = label + 7 segment pips.
  Base ranks in the primary bar color, trained ranks overlaid in gold, foil
  shimmer effect when Mastered (static sparkle overlay is fine for POC)
- Lower text panel: full width below portrait/grid, content swaps per tab
- Footer: "No. {save_slot} — Issue {n}, Day {d}"

Collections tab renders the roster as a 9-pocket binder page: filled pockets show
mini card fronts; empty pockets show grey slots with silhouettes.

The Social and Tasks tabs' lists (M14, added post-POC) grow with the roster
and board tier, so their lower panel is scrollable: Up/Down scrolls the list
on those two tabs specifically (elsewhere Up/Down still switches which
hero's card is shown), with `^`/`v` glyphs indicating more rows off-screen.
Long lines truncate with an ellipsis rather than overflow their column.

**Palette:** placeholder era-inspired values until reference scans exist —
cream `#F2E6C9`, red `#C8102E`, gold `#FFC72C`, navy `#1B1F3B`, ink `#121212`,
plus a subtle halftone-dot texture. **Before building M5, drop 2–3 scans of real
1991 card backs into `assets/reference/` and sample the actual colors, bar
counts, and proportions from them.** Do not trust remembered colors — including
these.

---

## 9. Milestones

Work strictly in order. Each milestone ends with its acceptance criteria passing
and a commit.

**M0 — Scaffold.** Repo layout, `python -m game` opens a window, state machine
with keyboard-switchable placeholder screens for every state, JSON loader reads
`data/characters/*.json` with basic validation, empty save/load round-trips.
*AC: window runs at 60 fps; states switch; `pytest` green on loader tests.*

**M1 — Combat vertical slice.** Iron Man + Cap vs. 3 HYDRA grunts using §6.4
formulas. Menu-driven actions, HP/energy bars, turn-order strip, damage popups,
win/lose → back to HUB. All formulas unit-tested against hand-computed cases.
*AC: full battle playable start to finish; formula tests cover crit, dodge, min
damage, defend, ultimate charge.*

**M2 — Day loop.** Tower scene with three rooms, clock HUD, energy bar,
activities with §6.1 costs, sleep → next day, autosave. Missions launch M1
battles from the Ops Floor.
*AC: play three consecutive in-game days; energy and clock enforce limits;
save/reload restores mid-run state.*

**M3 — Bonds.** Talk/gift interactions with §6.2 math, gift limits (weekly
at M3; replaced by the M12 rolling window),
bond-level display, Cap's Level-2 bond scene (simple dialogue boxes), same-party
mission points.
*AC: reach Cap Bond 2 through play; gift-week limit enforced across a week
boundary; bond math unit-tested including birthday multiplier.*

**M4 — Training & perks.** Training Floor grants attribute XP, trained ranks
apply to combat math, perk choice modal at ranks 3 and 6, perks affect combat.
*AC: train Cap's Strength to rank 3, pick a perk, and see the damage change in
battle; XP thresholds unit-tested.*

**M5 — Impel card pause screen.** §8 in full, replacing the placeholder pause
state.
*AC: all tabs navigable; power grid reflects live base+trained ranks; binder
shows recruited vs. empty pockets.*

**M6 — Quest & recruitment.** Quest log, the Ant-Man rescue questline (2 hub
tasks + 1 battle; superseded by M13: the hub tasks are now field scout
quests), Ant-Man joins roster and appears in binder/party select.
Ch. 1–2 story missions and both bosses wired in sequence.
*AC: fresh save → complete Ch. 1–2 including recruiting Ant-Man, in under
~45 minutes of play.*

**M7 — 16-bit visual identity** *(added post-POC; supersedes the
"placeholder art" rule)*. The game renders to a 640×360 internal surface
scaled 2× nearest-neighbor to the 1280×720 window — chunky uniform pixels,
no anti-aliasing. One master palette (~32 colors, anchored to the sampled
Impel card colors) drives every screen. All art is procedural (pixel data
authored in code): pixel UI kit (comic-panel 9-slice frames, non-AA font,
bars, cursors), hero/enemy portraits and battle sprites, 16×16 item icons,
battle backdrop. The Impel card pause screen is redrawn in the same pixel
style. Layout zone sizes in §8 are halved (internal-res px) and keep their
on-screen proportions.
*AC: every existing screen renders through the pixel pipeline at 60 fps;
no anti-aliased text or off-grid pixels anywhere.*

**M8 — Walkable Avengers Tower** *(added post-POC)*. The hub menu screen is
replaced by a top-down walkable tower floor rendered from a procedural
tileset. Arrow keys move a player sprite with tile collision; Enter/E at an
interaction point (heroes standing in the room, shop counter, assignment
board, training equipment, ops console, bed) opens the existing menu
overlays. Elevator tiles switch floors. All §6/§7 rules are unchanged — the
walkable scene is rendering/input only; game logic modules stay pure.
*AC: walk between all three floors; every §7 activity reachable via an
interaction point; recruited heroes appear standing in the tower.*

**M9 — Field ops & team systems** *(added post-POC)*.
- **Party**: the player roams as the active team (max `PARTY_SIZE_MAX` 4) —
  leader walks, teammates follow in a chain. Battles field the party.
  Swapping happens in person: engage a benched character; if they hold a
  passive task with a requirement, the outgoing teammate must meet it
  (they take the task over) or the swap is blocked.
- **Per-character energy**: every roster member has daily energy 0–100.
  Team energy = the minimum across the party; team actions drain every
  member. Below 60% a hero's combat initiative takes a penalty that
  worsens each additional 10% down (config EN_PENALTY_*).
- **Passive assignments**: benched characters can Train (attribute XP/day),
  do Ops Support (credits/day; requires the attribute minimum in
  data/passive.json), or Socialize (bond/day with the lowest-bond NPC).
  After `ATROPHY_GRACE_DAYS` (2) consecutive days in the same spot — or
  idle — their unworked attributes decay: banked XP drains and trained
  ranks drop when the bank empties.
- **Mission zones & deadlines**: battle quests carry a `location` (zone in
  data/zones.json, danger 1–3) and `deadline_days`. Travel by Quinjet,
  find the target squad in the zone, engage (mission energy/time §6.1).
  Deadline expiry or battle loss fails the mission: 2-day cooldown
  (MISSION_FAIL_COOLDOWN_DAYS) before it reactivates. *(Superseded by
  M13: targets appear only after accepting at Ops — the deadline starts
  at accept — and a cooled-down mission returns as offered.)*
- **Ambushes**: while walking a zone, ambush chance scales with zone
  danger and inversely with party size. *(Squad sizing superseded by M15:
  an ambush always outnumbers the party by 1 (50%), 2 (35%), 3 (10%) or
  4 (5%), capped at twice the party and at `AMBUSH_MAX_SIZE` 8.)*
- **XP**: battle XP banks per participating hero only (KO'd participants
  earn KO_XP_MULT 50%); banked XP is consumed as bonus progress when that
  hero trains. Training EN/time scale with the rank being trained
  (TRAINING_ENERGY_BASE + PER_RANK × next rank; same for minutes).
- **Crisp text**: all text renders on the window at native resolution with
  anti-aliasing via pixelkit's deferred text pass; pixel art stays at
  internal res. No text is pixel-scaled.
*AC: complete a mission end-to-end (fly, search, engage, win) with the
party; fail one by deadline and see the cooldown; assign a benched hero
and observe passive gains and post-grace atrophy; all text crisp.*

**M10 — Field life & dispatch** *(added post-POC)*.
- **Rations**: consumable items may carry an `"energy"` field (EN restored
  to one hero). Press I anywhere (tower or zone) → pick a ration → pick a
  party member; +10 min clock (EAT_MINUTES), no energy cost, capped at
  daily 100. Sold at the Tower Café (`tower_cafe`) and zone street carts
  (`street_cart`): coffee +10, shawarma +25, power smoothie +40.
- **Zone activities**: crate tiles (`x`) in zones are daily-respawning
  search spots (tracked in `state["searched_today"]`, cleared at sleep).
  Searching takes 15 min (SEARCH_MINUTES) and rolls the zone's `loot`
  table in zones.json (credit range + item chance); trap chance =
  danger × SEARCH_TRAP_CHANCE (7%) springs a HYDRA squad (any size, no
  outnumber rule) and forfeits the loot. Midtown has a street cart (`S`
  tile) selling `street_cart` items mid-mission.
- **Dispatch board**: board tasks are no longer done on the spot. Each
  assignments.json task has `heroes` (1–2), `days` (1–2), `credits`, and
  `xp`. At the board you pick which roster heroes to send; they leave the
  party (at least one member must remain), stop appearing in the tower,
  and can't rejoin the party, take passive tasks, or be swapped in until
  the job ends. Jobs advance at sleep; on completion credits are paid and
  each sent hero banks `xp` into `unspent_xp` (spent as training bonus,
  like battle XP). Recalling a job frees the heroes with no reward. Away
  heroes neither idle-atrophy nor gain passively.
- **No teleport home**: winning a mission battle no longer returns the
  team to the tower — they stay in the zone and must walk back to the
  helipad to take the Quinjet. Losing drags the team home (superseded by
  M12: +3 h recovery, party capped at 10 EN, the day continues).
*AC: feed a hero mid-zone and see EN rise; search a crate, get loot, and
have it respawn next day; spring at least one trap; dispatch a hero, see
them refuse party re-entry until they return with rewards; win a mission
and walk back to the helipad yourself.*

**M11 — Progression, dialogue & free flight** *(added post-POC)*.
- **Never blocked from battle**: engaging a mission target always works.
  `launch_mission` drains MISSION_ENERGY from each party member flooring
  at 0 (energy.drain) instead of refusing; a tired team just fights with
  the M9 initiative penalty (and passes out after, if it hits 0).
  Training, crafting, and hub tasks still require the energy.
- **Quinjet free flight**: a zone helipad opens a destination menu —
  tower or any other zone (TRAVEL_MINUTES per hop) — instead of only
  flying home.
- **Board tiers**: team power = sum of the top-4 roster heroes' effective
  grid totals. Tier 2 unlocks at 70, tier 3 at 110 (BOARD_TIER_POWER).
  Each unlocked tier contributes 2 rotating tasks/day to the board; the
  board teases the next tier's threshold. assignments.json tasks carry
  `tier` 1–3.
- **Dispatch pay scales with who you send**: multiplier =
  1 + 0.02 × (avg sent-hero grid total − 24), clamped 0.8–1.5
  (DISPATCH_POWER_* / DISPATCH_MULT_*), applied to credits and XP and
  snapshotted on the job when it starts.
- **NPC requests**: tasks may carry `requested_by` (an NPC id) and
  `bond`; completion pays the bond points to that NPC (feeding the
  existing level-4 unlock flags: Jarvis energy, Pepper discount, Coulson
  credits) on top of credits/XP. The board labels these "for <name>".
- **Tiered dialogue** (`data/dialogue.json`): every character has talk-line
  pools keyed by minimum tier. Bondable characters (NPCs, bond-recruits)
  use their bond level; non-bonding teammates use story stage instead
  (0 → 2 after the Ch. 1 boss via `training_upgraded`, → 4 at
  `ch2_complete`). Talking/chatting shows the line in the dialogue box
  (a transient scene, nothing marked seen), picked from the richest
  unlocked pool and rotated daily. Lines grow more personal per tier.
- **Gift reactions**: gift results now include the category and a visible
  reaction ("loves it!", "hates it!") so per-character gift relevance
  (§6.2 loved/liked/disliked/hated tables in each character JSON) is
  legible in play.
*AC: engage a mission at 0 EN and fight (slowly); fly zone→zone direct;
watch board tiers unlock as the roster's top-4 power crosses 70/110; send
a strong hero and see a bigger payout than a weak one; complete an NPC
request and see the bond gain; talk to an NPC at bond 0 and 4+ and hear
different registers; get a "loves it!" and a "hates it!" reaction.*

**M12 — Time, defeat & discipline** *(added post-POC)*.
- **Target arrow** points down at the selected enemy; the dialogue-box
  portrait sits fully above the box frame.
- **Mostly-empty crates**: zone loot tables gain `find_chance` (docks 0.30,
  midtown 0.35, HYDRA district 0.40) rolled after the trap check — most
  searches find nothing.
- **Battle time standard**: engaging a mission costs MISSION_ENERGY /
  MISSION_MINUTES up front (unchanged). A won ambush/trap fight now costs
  BATTLE_MINUTES (60). A DEFEAT (any battle) costs DEFEAT_RECOVERY_MINUTES
  (180), caps every party member at DEFEAT_ENERGY (10 — never a raise, so
  losing on fumes can't beat winning on fumes), and drags the team
  back to the tower — the day continues (failed missions still cool down
  2 days). Passing 2 AM during recovery passes out as usual.
- **Training lockout**: only active party members can use the rack, and
  starting a session pulls the trainee off the team — they stand at the
  mats, can't be swapped/assigned/dispatched, and return automatically
  (rejoining the party if there's room) when the in-game clock passes the
  session length: TRAINING_MINUTES_BASE 30 + 30 × rank (rank 1 = 1 h).
  EN cost unchanged (15 + 5 × rank, paid at start); XP (facility + banked
  double-dip, snapshotted at start) lands on completion. Unfinished
  sessions complete at sleep. The last party member can't train. The
  benched passive "train" assignment (M9) is unchanged.
- **Gift limits**: see §6.2 — 1/day per receiver, 2 per rolling 5 days,
  −5 for repeating yesterday's gift.
*AC: arrow points at the enemy; most crate searches come up empty; lose a
fight at noon and be back in the tower at 3 PM with 10 EN; start a rank-1
session, watch the hero leave the party and return an hour later ranked
up; get gift-blocked on the second same-day gift and see −5 for a lazy
repeat.*

**M13 — Accept, scout & find them in the field** *(added post-POC)*.
- **Accept before engage**: story quests are "offered" at the Ops Console
  and show NOTHING in the field until accepted; accepting starts the
  deadline (days_left is None before accept). A failed mission comes off
  cooldown as offered again — re-accept it.
- **Scout quests** replace hub tasks (story.json kind "scout"): a
  location zone plus `scout_points` [[x,y],...] and an optional
  `action_label`. Once accepted, gold markers appear in the zone; each
  point costs SCOUT_ENERGY (5) / SCOUT_MINUTES (20) to work; the quest
  completes on the last point. Ch. 1: Case the Safehouse and Spoof the
  Ankle Monitor both play out on Lang's Midtown block.
- **Dispatched heroes are physically at their work site**: every
  assignments.json task carries `spot` [area, x, y] (a tower floor or a
  zone), snapshotted onto the job. The hero stands there while away;
  recall happens IN PERSON by finding them and choosing Recall (the
  board only shows where everyone is). Board rows read "2 Heroes /
  2 Days" and NPC requests show "requested by <name>: +N bond".
- **Named attacks**: the battle menu lists the actor's actual ability
  names (Repulsor Blast / Unibeam (12 EN) / House Party Protocol...)
  instead of Basic/Special/Ultimate; Item and Defend stay generic.
- **Consumables are giftable** alongside gift-kind items (Hulk's loved
  Energy Bar is finally reachable); unlisted items land as neutral.
*AC: fly to the docks before accepting quest 1 and find nothing; accept
and the squad appears; case the safehouse by working all three markers on
foot; walk to the ops floor and find Cap calibrating the sensors, recall
him face to face; see "Shield Throw (10 EN)" in Cap's battle menu; gift
Hulk an Energy Bar for +80.*

**M15 — Ranks, talent & real bosses** *(added post-POC)*.
- **Rank/boost rework** — see §6.3. Everyone starts at rank 1, trains to 10,
  and is differentiated by an innate boost table (the old card grid). All
  combat math flows through `formulas.effective_rank(rank, boost)`.
- **Ultimate charge persists** between battles (§6.4).
- **Signature spreads** for the three hero specials (§6.4 table).
- **Battle menu**: Basic / Special / Ultimate / Defend / Item, ability names
  in the resource colours, no EN suffix.
- **Ambush sizing** by the §M9 table as amended (50/35/10/5, cap 2× party).
- **Boss rebalance** — see §6.4. Escorts grew and the two bosses gained bulk
  so they are the hardest fights in the game rather than the easiest.
- **Hidden board requirements** (`requires` in assignments.json, resolved by
  `game/hub/requirements.py`): `hero_any_of` clauses (each clause needs ONE
  attribute to satisfy all of its `min_rank`/`min_boost` keys),
  `hero_all_attributes`, plus `flag` and `bond` gates. Skill requirements are
  never advertised — sending an unqualified hero gets a refusal in Coulson's
  voice. Flag/bond/`once` gates instead keep a job off the board entirely.
- **Hulk's one-shot job** ("Spot Hulk at the Heavy Bags", posted once
  `hulk_arrived` is set) pays +600 bond so recruiting him at Bond 4 is a
  handful of days rather than weeks.
*AC: Iron Man out-damages Cap on Strength at rank 1 AND at rank 10 while Cap
wins Agility at both; walk into a battle with a part-charged ultimate; watch
Unibeam splash the neighbours and Pym Barrage hit three; lose to Crossbones at
rank 1 and beat him at rank 2; get refused by Coulson for sending Cap to
decrypt a data cache.*

**M16 — XP economy & posting chances** *(added post-POC)*.
- **Geometric rank costs, level-keyed sessions, enemy XP tiers** — see
  §6.3 and §6.4. Rank 10 is now a long-campaign goal (roughly 82 in-game
  days for one attribute, energy- and time-bound), not a week's work.
- **Multi-day training lockouts** (§6.3): a session is a number of waking
  minutes, so high-level training genuinely takes the hero off the team
  for days. The rack and the character menu show "2d 0h to go".
- **Posting chances** (`posting` in assignments.json): a board job may
  appear only on a dice roll that warms as its requester's bond grows.
  Hulk's "Spot Hulk at the Heavy Bags" is posted on 5% of days at Bond 0,
  25% at Bond 1 and 80% at Bond 2+. The roll is a deterministic hash of
  (task, issue, day) so reopening the board never rerolls it, and such a
  job bypasses the 2-per-tier rotation — it already won a roll to be there.
- **Boost thresholds raised** so the M15 hidden gates actually discriminate
  against the card-derived roster (every hero has at least boost 1 in
  every attribute, which made `min_boost: 1` a tautology): Calibrate wants
  INT rank 2 or boost 4+, Debug JARVIS rank 2 or boost 5+, Spar rank 2 or
  boost 6+, and the tier-2 jobs step up from there.
*AC: watch a level-1 attribute take four sessions and a level-9 one take
22; start a level-9 session and find the hero still on the mats two days
later; see Hulk's job show up roughly four days in five once he likes you;
get refused sending Cap to calibrate the sensors at Intelligence rank 1.*

---

## 10. CLAUDE.md Starter (place at repo root)

```markdown
# Roads to Secret Wars — POC

Stardew-style Marvel RPG proof of concept. Python 3.11 + pygame-ce.
The build spec is docs/GAME_SPEC.md — read it before any task and follow its
numbers and schemas exactly.

## Commands
- Run: `python -m game`
- Test: `pytest`

## Rules
- Do not make changes beyond the specific task requested. No drive-by
  refactors, renames, or "improvements."
- Game logic stays pure-Python and unit-tested; pygame only in rendering/input.
- All content comes from JSON in /data — never hardcode character or item data.
- All tunable numbers come from game/config.py, sourced from the spec.
- Work one milestone (spec §9) at a time; run pytest before finishing a task.
- Placeholder art = colored rectangles + text. Do not spend effort on art.
```

## 11. Working With Claude Code

- Start each session by pointing it at a single milestone: "Read
  docs/GAME_SPEC.md and implement M1. Stop at M1's acceptance criteria."
- Keep tasks small — one system or one file cluster per request. Review diffs.
- When something's off, quote the spec section at it rather than re-explaining.
- Commit at every green-test point so you can roll back cheaply.
- Update this spec when a design decision changes. The spec drifting from the
  code is how projects rot.
