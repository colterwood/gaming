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
       TITLE → HUB               (M28: loading a save skips the path)
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
flags, quest states, side-arc states (`unlocks`, M17) and the queue of story
beats waiting to play (`pending_scenes`, M17), tower repair progress
(`repairs`, M29), gear upgrade levels (`gear_levels`, M31) and whatever is
sitting on the Pym bench (`upgrades`, M32).
Write to `saves/slot_N.json`, keep one `.bak` of the previous save.
`SAVE_SLOTS` (3) independent games; the title menu picks which one is
being played and `App.SAVE_SLOT` follows it (M28).

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
| Search a side-arc site (M17) | 5 energy, +20 min per stand searched |
| Talk / gift | 0 energy, +20 min |
| Eat a ration (M10; M18) | 0 energy, +10 min; restores the item's `energy` EN to EVERY active party member, each capped at 100 |
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
- **Rank costs DOUBLE per level** (M33, `XP_TO_NEXT_RANK`), keyed by the
  level you are climbing FROM — the published progression chart:

  | from level | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
  |---|---|---|---|---|---|---|---|---|---|
  | XP | 100 | 200 | 400 | 800 | 1,600 | 3,200 | 6,400 | 12,800 | 25,600 |

  M16 tried 1.5× growth; in play that made the back half of the ladder
  cheap enough that ambush XP alone carried a team toward rank 5 before
  Chapter 3, before gear started adding ranks on top.

- **The cost is the same for everybody** (M33). M16b discounted it by the
  hero's innate boost, which paid them twice for the same talent — once in
  the combat math, again on the clock. A boost now buys exactly one thing:
  the combat value in that category (§6.3 `effective_rank`).

- **Enlightenment** (`ENLIGHTENMENT_XP` 51,200) is the rung above rank 10 —
  one more doubling. It **opens only when all six attributes are at
  RANK_MAX**, appears as a seventh row on the rack, and is trained in
  level-9 sessions. Once the six are full it is also where field XP goes,
  since M21's split has nowhere else to put it. Finishing it sets
  `enlightened`; `mastered` (all six at ten) keeps its name because the
  card and binder read it for the foil treatment.

  One attribute 1→10 is 51,100 XP, so a whole hero is ~307k plus the
  capstone. At the training ceiling (0.5 XP per minute × 1,200 waking
  minutes = 600 XP/day) that is a **long-campaign goal, not a checklist
  item** — ranks 1–5 are the chapter-scale work, 6–10 is the long haul.
- **A rack session yields and costs** by the level being trained (M16,
  `TRAINING_XP_BY_LEVEL` / `TRAINING_MINUTES_BY_LEVEL`; energy stays
  `15 + 5 × level`):

  | level | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
  |---|---|---|---|---|---|---|---|---|---|
  | XP | 25 | 35 | 50 | 80 | 135 | 225 | 400 | 700 | 1,200 |
  | lockout (min) | 50 | 70 | 100 | 160 | 270 | 450 | 800 | 1,400 | 2,400 |
  | sessions to rank up (boost 5) | 4 | 5 | 5 | 5 | 4 | 4 | 3 | 3 | 3 |

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
                Paid to each participating hero; KO'd participants get
                KO_XP_MULT (50%). No XP on a loss. M21: it lands on their
                six attributes immediately, split evenly — there is no
                bank and no training top-up.
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
- `defensive`: guards below `AI_DEFENSIVE_HP_THRESHOLD` (40%) HP — but
  never two turns running, and not at all once below
  `AI_DEFENSIVE_LAST_STAND_HP` (15%), where it swings with everything it
  has left (M23). When it isn't guarding it attacks with its best
  available ability, not a token basic. Before M23 it simply guarded every
  turn below the threshold, which turned any wounded defensive enemy into
  a damage sponge that never fought back — unbearable on a high-level
  enemy with a deep HP pool.
- `support`: heal/buff ally if one is below 50% HP, else basic attack

---

## 7. Hub & Day Loop (POC content)

Avengers Tower rooms and activities:

| Room | Activities |
|---|---|
| Common Floor | Talk to present heroes, give gifts, assignment board (2 rotating tasks per day per unlocked board tier; dispatch jobs — see §9 M10/M11) |
| Training Floor | Attribute training (pick hero + attribute); upgrades to tier 2 via story flag after Ch. 1 boss |
| Ops Floor | Story missions are OFFERED here (M13): accept one to start its deadline and make its target/scout points appear in the field; view quest log. The Quinjet sits in its bay here (M29) |
| Med Bay | Treatment chair: hours for energy (M30). Opened by a repair |
| Tech Lab | Fabricate and fit equipment (M31). Opened by a repair |
| Pym Lab | Leave gear to be upgraded with materials (M32). Behind Lang's door code, then a repair |

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
**An empty pocket is anonymous** — a silhouette and a `?`, never a name.
The page says that someone is missing, never who: finding out who fills a
slot is the game, and once the Ch. 3–4 fork exists, naming the recruit you
turned down would spoil the road not taken.

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
  session length: TRAINING_MINUTES_BY_LEVEL (M16), 50 min at level 1.
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
  §6.3 and §6.4. Rank 10 is a campaign-scale goal (17–30 in-game days for
  one attribute depending on the hero's talent for it), not a week's work.
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

**M17 — Story unlocks: Thor & Stormbreaker** *(added post-POC)*.
- **Conditional side arcs** (`data/quests/unlocks.json`, resolved by
  `game/hub/unlocks.py`) run ALONGSIDE the sequential story.json chain
  instead of taking a slot in it, so an arc can sit dormant for issues
  without stalling the HYDRA missions queued behind it. An arc's
  `requires` block takes story `flags` plus `hero_min_rank`, which is a
  floor across ALL SIX attributes for the named hero — a rounded-out
  hero, not a one-stat specialist.
- **Night signal**: requirements are re-checked at the sleep boundary
  (after the calendar advances). When they come true the arc fires,
  logs its `signal_message`, and queues a cutscene onto
  `state["pending_scenes"]`, which the hub pops and plays the moment the
  player is back on their feet. A scene may carry a `sound`.
- **Procedural audio** (`game/ui/audio.py`), the first in the project and
  the same no-assets rule as the art: sounds are generated in code. The
  Thor signal lands on a synthesized thunder crash. Sound is entirely
  optional — a dead mixer (headless, no device, odd sample format) makes
  every call a silent no-op, and no rule depends on it.
- **Searching on foot**: the arc names a `location` zone and a list of
  `search_groves` (each a clump of tiles). Standing beside any tile of a
  clump offers the search; each costs UNLOCK_SEARCH_ENERGY (5) /
  UNLOCK_SEARCH_MINUTES (20), the same as a scout point. Combed-out
  stands dim like a rummaged crate; the one holding the prize is picked
  by a stable crc32 roll so reloading never moves it.
- **Not everyone can pick it up**: `lift_requires` names a hero who must
  be ON THE ACTIVE TEAM, not merely on the roster. Finding the thing
  without them ends the search but not the arc — the stand stays marked,
  the refusal closes the discovery cutscene, and retrying later with the
  right hero costs nothing.
- **The owner comes for it**: the morning after the item is carried home,
  the arc's `recruit` is standing in the tower. They join (the party if
  there's room, the roster otherwise), take their property back out of
  the inventory, and set the arc's `flags`.
- **Ch. 2 content**: "Something Strange in Midtown" — Crossbones down
  plus Captain America at rank 3 in all six opens it (raised from 2 in
  M23 — rank 2 arrives on its own by that point); Stormbreaker is in
  one of five stands of Midtown trees; only Cap can lift it; Thor joins
  and sets `thor_joined`, the hook the next HYDRA chapter gates on.
*AC: beat Crossbones, train Cap to a rounded 2, and get woken by thunder
and a message that says "Something strange happened in Midtown..."; comb
the Midtown trees and find the axe with Cap benched, get told none of
your heroes are mighty enough; fly back with Cap and pull it free; wake
the next morning to Thor on the common floor.*

**M18 — Bags, rations, collapse & saving** *(added post-POC)*.
- **Rations feed the TEAM** (`activities.eat_food`, §6.1): one item, every
  active party member gets its `energy`, each capped at the daily max.
  Team energy is the *minimum* across the party, so the old feed-one-hero
  version could move the HUD bar by nothing at all. There is no longer a
  "who eats?" step. Benched heroes don't eat — they wake up full anyway.
- **Bag capacity** (`game/core/inventory.py`): the team carries what its
  members can carry — `INVENTORY_SLOTS_PER_HERO` (4) per ACTIVE party
  member, so a full party of four has `INVENTORY_SLOTS_MAX` (16). One
  slot holds one item id up to `INVENTORY_STACK_MAX` (99); the 100th of
  anything spills into a second slot. The bag stays a flat
  `{item_id: count}` on the save; capacity is derived, so benching a hero
  shrinks it — which never destroys anything, it just blocks new pickups
  until you're back under. The shop refuses a full bag *before* taking
  the money; crate loot is left behind with a message; story artifacts
  pass `force=True` so a full bag can never dead-end an arc.
- **Collapsing on the job loses the job.** Previously the action that
  passed the team out still counted, so the last scout point of a quest
  could land — and COMPLETE it — on the way down. Now:
  - a scout point that drops the team (0 EN or past 2 AM) is not
    credited, and that quest's worked points are wiped: it has to be run
    again. The quest stays accepted; this is a reset, not a `fail_mission`
    (no HYDRA cooldown).
  - `launch_mission` keeps the M11 rule that a tired team is never
    refused, but a team the approach *drops* never makes contact: no
    battle launches and the mission is untouched.
- **Saving is a day boundary.** The autosave at lights-out is the only
  save; the pause screen's Options tab no longer writes one. Quitting
  mid-day rewinds to 6:00 AM that morning, so a day is played through or
  not at all. Tests are held to this by an autouse fixture in
  `conftest.py` that redirects `config.SAVE_DIR`; headless driver scripts
  must set `GAME_SAVE_DIR`.
*AC: feed the team a shawarma at 40 EN and watch every member gain 25;
fill 16 slots with a full party, bench someone and keep every item while
being refused the next pickup; carry 150 coffees in two slots; pass out on
the third marker of Case the Safehouse and find it back at 0/3 the next
morning; engage a mission at 40 EN and never reach the target; save, quit
mid-afternoon, reload at 6:00 AM the same day.*

**M19 — Message-log scrollback** *(added post-POC)*. The walkable world's
message log keeps `LOG_HISTORY_MAX` (12) lines instead of 3 and shows the
newest `LOG_VISIBLE_LINES` (3) above the hint bar. **PgUp/PgDn** page the
window back and forward through the history, clamped at both ends; gold
`^N`/`vN` counters show how many messages sit off-window each way. Any new
message snaps the window back to the newest, so nothing arrives unseen.
The page keys only bind in the walkable state — inside a menu or cutscene
their handlers consume input first. This is what makes a busy night
readable: a pass-out reason logged before the wake-up messages used to be
pushed off a 3-line log immediately.
*AC: collapse on a scout marker, sleep through a night with training and
dispatch returns landing, then PgUp and still find "the team drops where
they stand".*

**M20 — Squad caps, board discipline & card honesty** *(added post-POC)*.
- **Squad size is capped by who is actually standing there**
  (`field.squad_cap`, `AMBUSH_MAX_BY_PARTY`): 4 against a lone hero, 6
  against a pair, `AMBUSH_MAX_SIZE` (8) against three or four. This
  replaces the M15 "never more than double the party" rule and — the
  actual bug — now binds **booby-trap squads too**. `trap_squad` rolled
  2..8 regardless of party size, so a solo hero could open a crate onto
  eight HYDRA. It takes `party_size` now.
- **The power grid shows the trained rank and nothing else.** The gold
  band that extended each bar by the innate boost read as "this hero is
  at that level" — they are not; the boost is a bonus applied on top in
  combat. Bars are the rank; the boost stays as the `+N` marker at the
  end of the row. The band caption drops to "POWER RATINGS".
- **Attributes tab wording**: "Chosen perks" -> "Achievements"; "Banked
  XP: STR 40" -> "XP: STR 40/130", progress over what the next rank
  costs (or "MAX"), with battle XP still waiting to be spent shown as
  "Battle XP banked: N" so it isn't invisible between fights.
- **The board must be read in person.** `activities.check_board` stamps
  the day when the player opens the assignment board; the pause card's
  Tasks tab lists postings only for a day that's been read, and says
  "Check the board by Coulson!" otherwise. The tier is no longer
  advertised in the card's header.
- **Bond levels are ten Avengers logos**, lit blue as each level lands
  and dark grey beyond, replacing the progress bar (`sprites.avengers_pip`).
- **Old saves survive updates.** Every key added since M16 is read
  through `.get`/`.setdefault`, so a save from an earlier build loads and
  plays. `tests/test_m20.py` pins this with a literal M16-era save.
*AC: with one hero on the team, spring a crate trap and count at most 4
enemies; open Iron Man's card at rank 1 and see six short pink bars with
`+6`/`+5` markers, no gold; check the Tasks tab before visiting the board
and be sent to Coulson; reach Bond 4 with Jarvis and see four blue
logos of ten; load a save made two milestones ago and keep playing.*

**M21 — Field XP is applied, not banked** *(added post-POC)*.
- **The battle-XP bank is gone.** M9's `unspent_xp` held battle and
  dispatch XP until the hero next trained, and a session could only draw
  out as much as the session itself was worth — so a 270 XP Crossbones
  win needed **six** separate rack sessions to spend, landed on whatever
  attribute you happened to train, and showed no progress on the card in
  the meantime.
- **`attrs.award_battle_xp` applies it on the spot**, split evenly across
  the hero's six attributes (the remainder is spread, not rounded away).
  Battles and completed dispatch jobs both pay this way. Maxed
  attributes drop out of the split rather than swallowing a share.
- **The innate boost buys exactly what it buys on the rack.** The award
  runs through `add_training_xp`, so the XP number is boost-blind while
  the RANK COST is boost-weighted (`xp_for_rank`) — talent means fewer
  XP per rank, identical to training. No second mechanism.
- Total XP earned over a campaign is unchanged; only its timing and
  spread are. Progression is now: **fights round you out, the rack
  specialises you.**
- **Migration**: `load_game` spends any bank an older save still carries
  onto that hero's attributes, and drops the never-read top-level
  `state["unspent_xp"]`. Nothing earned is lost.
*AC: win an ambush and watch every attribute's XP move on the card
before you go anywhere near the training floor; give the same 300 XP to
Hulk's Strength (boost 7) and Cap's Strength (boost 2) and see the same
XP go in but Hulk rank up sooner; load a save with a bank and find it
already spent.*

**M22 — Sparring pays broad, Ops doesn't drive** *(added post-POC)*.
- **"Spar with S.H.I.E.L.D. Rookies"** pays `xp` 120 — which under M21's
  six-way split is **+20 to every stat**. It's a training job, so it
  trains everything; the M11 dispatch power multiplier still scales it
  with who you send.
- **The Ops Console briefs, it doesn't ferry.** Accepting a mission no
  longer offers "Fly to <zone> now", and the cursor no longer jumps to a
  travel row. The console tells you where the job is and stops; walking
  to the elevator (or a zone helipad) is the player's own trip.
*AC: send two qualifying heroes to spar and see all six attributes move
by ~20 each; accept a mission at Ops and find no way to leave the room
from that menu.*

**M23 — Defensive AI, reward transparency & a harder Stormbreaker gate**
*(added post-POC)*.
- **Defensive enemies stop turtling** — see §6.5. A `defended_last_turn`
  flag on the Combatant (set in `take_turn`) drives `should_defend`, so a
  wounded enemy alternates guard/attack and abandons guarding entirely
  once cornered.
- **Board jobs advertise every reward.** The board listed credits only, so
  XP and bond were invisible at the moment you choose. Each job now
  carries a "pays ~N cr, ~N XP (+N/stat), +N bond with <name>" line
  (`HubScene._reward_label`), and the card's Tasks tab shows the same in
  compact form. XP is quoted per stat because M21 splits it six ways; the
  `~` is the M11 crew-power multiplier, unknown until you pick who goes.
- **The Ops console never offers a ride** — the side-arc signal loses its
  "Fly to <zone> now" row too, matching M22's mission briefings.
- **Stormbreaker wants a rank-3 Captain America** in all six, up from 2,
  which arrives on its own by Chapter 2's end.
*AC: fight a HYDRA Enforcer down past 40% and watch it trade blows
instead of guarding every turn; open the board and read what each job
pays before sending anyone.*

**M24 — Assignments train specific skills** *(added post-POC)*.
- A board task's `xp` is now **per attribute**, not a total to divide, and
  an optional `trains` list names which attributes it feeds (absent = all
  six). Sweeping the hangar is +20 Stamina; a boot camp is +40 to all six.
  `attrs.award_attribute_xp` pays it; `dispatch.trains_label` renders it
  ("Stamina", "Strength, Stamina and Agility", "all skills"); the job
  snapshots `trains` at send time alongside the M11 crew multiplier.
- **Budget check** (a dispatched hero is off the team for the whole job,
  exactly like one on the rack or the passive train assignment, so XP/day
  is the fair yardstick). Passive "Attribute training" pays 40/day into
  one attribute; the rack pays 250/day at level 1 rising to 1,200/day at
  level 7+, all into one attribute. Against that baseline:

  | tier | shape | XP/day | vs passive-40 |
  |---|---|---|---|
  | 1 | +20-25 to one attribute | 10-25 | 0.2-0.6x |
  | 1 | Spar, +20 to all six, 1 day | 120 | 3x |
  | 2 | +40 to one attribute | 20 | 0.5x |
  | 2 | Expo/Boot Camp, 3-6 attributes | 120 | 3x |
  | 3 | Deep Recon, +60 to all six, 2 days | 180 | 4.5x |
  | 3 | U.N. Delegation, +60 to all six, **1 day** | **360** | **9x** |

  Single-attribute jobs sit *below* the passive assignment and trade that
  XP for credits — correct. The broad jobs at 3-4.5x are a real but
  supplementary parallel track. The U.N. Delegation is the outlier: 360
  XP/day across all six matches the rack's whole-campaign average rate
  (~333/day) while spreading over every attribute, so repeating it masters
  a hero in ~125 days for zero energy — as fast as the rack. Halving it,
  or making it a 2-day job like Deep Recon, brings it in line at 180/day.
*AC: send a hero to sweep the hangar and see Stamina move and nothing
else; read "+20 XP to Stamina" on the board before sending them.*

**M25 — The clock stops for menus; board XP gets a budget** *(added post-POC)*.
- **The world clock only runs while the team is on its feet.** The cosmetic
  tick sat outside the `mode == "normal"` branch, so it kept advancing
  behind the assignment board, the shop, the ops console and every other
  submenu. Reading a menu is not an activity. (The Impel pause screen was
  already frozen — `App.update` only ticks the hub in the HUB state, now
  pinned by a test.)
- **Board XP is budgeted per tier** against the passive "Attribute
  training" assignment (`PASSIVE_TRAIN_XP_PER_DAY` 40), because a
  dispatched hero is off the team exactly like one on the mats:
  `BOARD_TIER_XP_MULT` = 0.5x / 1.0x / 1.5x, i.e. **20 / 40 / 60 XP per
  day TOTAL**, divided across whatever the job trains. Board work is
  deliberately the lesser XP route — it also pays credits and often bond.
  A test asserts every shipped job sits inside its tier's budget.
- **Consequence**: a job that trains all six spreads its budget thinly, so
  a broad job is credit work and a narrow one is targeted training. The two
  jobs actually *named* for training were the casualties (3 and 13 XP a
  stat), so M27 narrowed them to what you'd really practise — Spar trains
  Strength/Agility/Durability at 7, Boot Camp the physical four at 20.
  Keep this in mind when authoring new jobs: `trains` width sets how much
  each stat sees.
- **Board presentation**: the title is just "Assignment Board"; payouts
  read "150 cr, 40 XP to Intelligence" with no "pays" and no "~" (the M11
  crew multiplier still scales what actually lands); and the last line
  before Close reports what's open and what's next — "Tier 1 and Tier 2
  jobs available. Tier 3 jobs unlocked at team power 160 (currently 121)."
  With every tier open it's simply "Tier 1-3 jobs available."
*AC: open the board and watch the HUD clock hold still; read a payout with
no tildes; see the footer name the next tier's threshold.*

**M26 — Every board job is one-shot** *(added post-POC)*.
- The M15 per-task `once` flag is gone; **being one-shot is now the rule**
  (`requirements.is_done`). Completing a job records it in
  `state["completed_tasks"]` and it never posts again. Recalling a job
  pays nothing and does NOT retire it — the work is still there to do.
- The board is therefore a **finite list of work, not an income tap**:
  16 jobs worth 3,160 credits base (890 / 1,010 / 1,260 by tier) before
  the M11 crew multiplier, plus one-shot bond from the four NPC requests.
  Missions, ambush drops and zone loot become the only repeatable income
  once it's cleared.
- **A tier can now be finished**, and the footer says so, e.g. "Tier 2
  jobs available, Tier 1 jobs complete. Tier 3 jobs unlocked at team
  power 160 (currently 121)." — degrading to "Tier 1-3 jobs complete."
  when the board is empty, with "Nothing posted today." where the
  listings would be.
- Consequence to design around: with no further content the board becomes
  a dead station once cleared. Adding tiers (and item rewards) is the
  intended answer.
*AC: send a hero to sweep the hangar, finish it, and never see it posted
again; recall a different job and find it still on the board; clear tier 1
and read "Tier 1 jobs complete" in the footer.*

**M28 — Save slots & the title menu** *(added post-POC)*.
- **Three independent games.** `SAVE_SLOTS` (3) has been in config since M0
  and nothing ever used it — `App.SAVE_SLOT` was a class constant of 1, so
  there was exactly one game and testing anything from a fresh start meant
  losing it. `new_game(slot=)` / `load_game(slot=)` set the slot and
  everything that writes (autosave, lights-out) follows it, including the
  Impel card footer.
- **The title screen is a menu**: **Continue** (the most recently written
  slot, named in the row), **New Game**, **Load Game** — the last two
  dropping into a picker that says what each slot holds, e.g.
  "Slot 1 - Issue 1, Day 10 (4 heroes, 3347 cr)".
- `save.slot_summary` / `list_slots` / `latest_slot` read those headline
  numbers off the files. A slot that won't parse reads as empty instead of
  taking the whole menu down with it.
- **No slot is overwritten without being asked.** New Game onto an occupied
  slot goes to a confirmation whose cursor starts on "No, go back", and
  nothing is written until that game's first lights-out (M18), so backing
  out at PATH_SELECT costs the game living there nothing.
- Loading transitions **TITLE → HUB** directly (§4): the path was chosen the
  day that game started, so PATH_SELECT has nothing left to ask.
*AC: start a game in slot 2, sleep, and find slot 1 untouched; pick New
Game on an occupied slot and get asked before anything is lost; corrupt a
slot and still reach the other two; read the slot number in the card
footer.*

**M29 — Tower rebuild** *(added post-POC)*.
- **The game opens with a broken tower.** Repairs are posted on the
  assignment board; accepting one is what makes the work appear. Order:
  **elevator** (opens the Ops Floor) → **Quinjet** (Pepper reports it
  inoperable at Ops; its parts are found around the tower) → **Training
  Floor** (mats and equipment) → the rest of Ch. 1–2. Later postings open
  the **Med Bay**, the **Tech Lab**, and the **Pym Lab** floor — the last
  reachable only after Scott Lang is rescued, because he has the access
  code.
- **Repairs are worked in person, not dispatched.** A board job today sends
  a hero away for 1–2 days (M10), which is the wrong shape for the opening
  — the player would accept "fix the elevator" and then have nothing to do
  while it happened. A repair is accepted at the board and then *worked*:
  search points around the tower for parts, then the repair action, on the
  scout-point / search-grove pattern (energy + minutes per point).
- Flags: `elevator_repaired`, `quinjet_repaired`, `training_repaired`,
  `med_bay_repaired`, `tech_lab_repaired`, `pym_lab_repaired`, plus
  `pym_lab_unlocked` for the floor itself. Job ids are `repair_*`.
  `training_repaired` is NOT `training_upgraded` — the latter is still the
  Ch. 1 boss's ×2 facility multiplier.
- **Repairs are on the critical path**, so they may never carry a `posting`
  chance or a bond gate (M16/M15): a dice roll that stalls the campaign is
  a softlock. They also sit outside the M25 per-day board XP budget, which
  prices a hero's *days* — a repair spends the player's own energy and
  clock instead. Credits plus a one-off XP chunk.
- **Old saves keep the rooms they already had.** Loading a pre-M29 save
  counts the elevator, Quinjet and Training Floor as repaired (the M20
  rule); only the new rooms post as fresh work.
*AC: start a new game and find the elevator dead, the board offering to
fix it, and three salvage markers on the common floor; fit the parts and
ride up into Pepper telling you the jet is down; walk to Ops with the jet
grounded and be offered no mission at all; load a save from M28 and find
the tower already standing.*

**M30 — The Med Bay** *(added post-POC)*.
- **Energy can be bought back with hours.** The daily 100 was a hard cap
  with exactly one answer — sleep. Sit in the treatment chair and the
  world clock RUNS in front of you: `MEDBAY_ENERGY_PER_TICK` (10) per
  `MEDBAY_TICK_MINUTES` (10), so a full refill costs 100 of the day's
  1,200 usable minutes. No credits, no energy — the hours are the price.
- The hub's `resting` mode is the one menu the clock deliberately keeps
  running behind (M25 froze every other). It stops itself when the team is
  full, the player can get up at any time and keeps what they bought, and
  passing 2 AM in the chair passes the team out where they sit.
- Treats every ACTIVE party member, like a ration (M18): team energy is
  the minimum across the party, so treating the leader alone moved nothing.
- **Consequence to watch in play**: with the chair available, energy stops
  being the binding constraint and the clock becomes it. Both numbers are
  one-line tunables; a per-day limit is the obvious brake if the trade
  turns out too cheap.
*AC: walk in at 40 EN, watch the clock and the bar climb together, and get
up at 70; sit down at full strength and be turned away.*

**M31 — Tech Lab: gear** *(added post-POC)*.
- **The gear slots finally hold something.** Every roster entry has
  carried an empty `gear: {}` since M0 while §5.3's equipment schema went
  unused and credits had nowhere to go once the board ran dry (M26).
- Six pieces across three slots (`weapon`/`armor`/`accessory`), fabricated
  at the Tech Bench for 350–520 cr and fitted per hero at the same bench.
- An effect is **either a flat attribute RANK bonus** — which is how gear
  takes a hero past the trained ceiling of 10, because the ceiling is on
  what a body can train to, not on what it can be handed — **or one of the
  perk effect keys**, summed with whatever the perks already give. One
  pipeline, no second mechanism (`entities.Combatant.gear_ranks`).
- **Worn or carried, never both**: equipping takes the piece out of the
  bag, swapping puts the old one back, and unequipping is forced past a
  full bag so equipment can never be stranded.
- The card's Attributes tab shows what a hero wears and what it's worth.
*AC: buy Combat Gauntlets, fit them to Iron Man, and watch his Strength
rank rise in a fight; fit Kevlar Weave to a rank-10 hero and go past 10.*

**M32 — Materials & the Pym bench** *(added post-POC)*.
- **Ore seams** (`o` tiles, `mining` table in zones.json) are the zones'
  second renewable next to crates: one swing per node per day for
  `MINE_ENERGY` (8) / `MINE_MINUTES` (30), rolled cumulatively against the
  zone's table, with the crate rule's danger-scaled trap risk. ISO-8 is
  common everywhere; vibranium and adamantium concentrate in the HYDRA
  District — **the best metal is in the worst neighbourhood**.
- **The Pym Lab is Clint's forge.** You don't upgrade over the counter,
  you LEAVE the piece: materials, credits **and the equipment itself** go
  at drop-off — off the hero's back if that's where it is — the job counts
  down at the sleep boundary, and **nothing is applied until the player
  collects it in person**. L2 costs 3 ISO-8 + 250 cr / 2 days; L3 costs
  2 vibranium + 1 adamantium + 600 cr / 3 days.
- **Going without it is the cost.** The team fights those 2–3 days
  unarmoured, which is what makes the timing a decision rather than a
  formality. A spare in the bag is handed over before the worn one; on
  collection the piece goes straight back onto the hero it came off,
  unless that slot has been filled meanwhile.
- **An upgrade belongs to the SCHEMATIC, not the object**
  (`state["gear_levels"][item_id]`): a level-3 Kevlar Weave means the lab
  builds them that way now, so a second copy comes off the line upgraded
  too. This is what lets gear live in a flat `{item_id: count}` bag with
  no per-instance identity — the alternative is instance ids threaded
  through the bag, the shop, the slots and the save, which is a much
  larger change for an edge case (owning two of one design) that the
  economy makes rare.
- Effects scale by `GEAR_UPGRADE_STEP` (0.5) per level: 1.0× / 1.5× / 2.0×,
  attribute bonuses rounded to whole ranks.
- The loader cross-checks that every material a recipe wants is actually
  mineable somewhere — a bench that asks for something the world doesn't
  contain is a dead end.
*AC: mine the HYDRA District until adamantium turns up (and spring a
squad doing it); hand in the armour Iron Man is wearing, watch it come
off his card, fight a fight without it, then collect it two mornings
later and find it back on him at +1.*

**M34 — The opening is people, not a noticeboard** *(added post-POC)*.
Play feedback on M29: Day 1 finished the elevator, the Quinjet, the
training floor, half the Med Bay, a story mission and a dispatch. Every
job was one menu away and none of it had to be worked out.

- **A repair may carry a `trigger`** (a character id). Those never appear
  on the board — the person with the problem tells you about it the first
  time you speak to them, and telling you is what starts the job.
  **Jarvis** raises the elevator; **Pepper**, who is on the Ops floor and
  therefore unreachable until it runs, raises the Quinjet.
- **A part may sit in somebody's pocket** (`{"from": "coulson"}`) instead
  of lying on the floor. Coulson gives his ordinary line until Jarvis has
  explained what the elevator needs; after that he remembers the contactor
  relay he was about to throw out. Such a part costs no energy and no time
  — it is handed over — and it cannot be picked up off the floor.
- **One repair at a time.** `repairs.accept` refuses while another is in
  hand ("One thing at a time - finish X first"), so the tower is a queue
  of problems rather than a checklist of them.
- **The board is locked until Pepper unlocks it.** She disabled it while
  the tower was falling apart; the station shows a 4-digit keypad that no
  code opens (`ACCESS DENIED`). Repairing the Quinjet sets `board_unlocked`
  through the job's `flags`, and her completion scene is where she says so.
  Training Floor and Med Bay then post together.
- **A posted repair occupies a board slot**, displacing an ordinary daily
  assignment until it is done.
- **Some parts are out in the city** — the Med Bay needs one from the
  docks, the Training Floor one from Midtown — so the Quinjet has to fly
  before the tower can finish being rebuilt.
- **The elevator LOOKS dead** until it is fixed (buckled doors, open
  panel), and **hauling a part** pops a dialogue box in the party leader's
  voice, because it costs energy and should feel like it. **Mining** logs
  the same way ("Cap cracks the rock open with the edge of the shield and
  collects ISO-8 Crystal"). Lines live in `data/flavor.json`, per hero,
  with a `default` pool so a new recruit is never silent.
- **Talk is never greyed out.** Once the day's bond points are spent it
  simply repeats what they have to say, for free.
*AC: start a new game, get told nothing by the board's keypad, hear it
from Jarvis, collect the relay from Coulson, and end Day 1 with the
elevator working and nothing else.*

**M35 — The parts are actually hidden** *(added post-POC)*. M34 moved the
repairs into conversation but left every piece marked on the map with a
diamond: walk to the marker, press Enter. The number of parts was
irrelevant because none of them had to be found.

A part is now one of four things (`repairs.part_kind`):

| kind | how you get it |
|---|---|
| `plain` | lying in the open — a marker shows it |
| `hidden` | inside the furniture / crate / ore seam at that tile. **No marker.** Searching the thing in the ordinary way turns it up |
| `npc` | in someone's pocket, handed over when you speak to them (`after_found` can hold it back until the rest are in) |
| `battle` | out of a won fight — a `chance` roll, or certain the first time a named hero is in the party |

- **Every spot is fixed.** No RNG decides where anything is, so learning
  the tower is worth something and a second playthrough is the same hunt.
- **Searching furniture costs `FURNITURE_SEARCH_MINUTES` (5) and no
  energy** — the hunt is attention, not attrition. Couches, tables,
  plants, bunks and mats become searchable *only* while a job with hidden
  pieces is in hand, and a searched spot dims for the day. **Mats are one
  field**: the training floor is ~140 mat tiles and searching them
  individually would be a punishment.
- **Only a `heavy` part costs energy** (`REPAIR_PART_ENERGY`), and only a
  heavy one gets the leader's line — a capacitor goes in a pocket, a
  nacelle strut does not. Elevator 0 heavy, Quinjet 3 of 4, Training
  Floor 1 of 3, the rest 0.
- Shipped hunts: elevator 3 (1 plain, 1 couch, Coulson), Quinjet 4 (2
  plain, 2 hidden, 3 heavy), Training Floor 3 (ops planter, under the
  mats, Midtown), Med Bay 4 (couch, ops, under a cot, a dock box), Tech
  Lab 6 (3 in the labs, 2 battle drops at 33%, Jarvis holds the sixth
  until five are in), Pym Lab 4 (an ore seam, Pepper, a Tech Lab table, a
  win with Ant-Man).
*AC: hear Jarvis name three parts, find one marker and turn over couches
until the second turns up; carry a nacelle strut and hear about it; win
fights until a Stark toolhead falls out of one.*

**Ch. 3–4** *(decided, not yet built)*.
- **Gate**: every Ch. 1–2 mission complete AND the tower repaired.
- Hulk and Thor are Ch. 1–2 recruits (they already are in code — Hulk at
  Bond 4, Thor off Stormbreaker), so Ch. 3–4's recruit weight is Shang-Chi
  plus exactly one of Widow/Hawkeye.
- **Dojo** unlocks at Shang-Chi **rank 3 across all six attributes** — the
  Stormbreaker gate's shape, not a bond level. It trains at **×1.2 XP for
  ÷1.2 energy; the lockout is unchanged.**
- **The Tony/Cap fork is commit-and-miss**: one recruit, and the other is
  only recoverable much later on the Illuminati path.
- **Black Widow** (Tony's path): she is already inside A.I.M. and doesn't
  want extracting. Dead drops across the zones, worked like scout points;
  she makes contact on her terms.
- **Hawkeye** (Cap's path): reach the target in a zone without triggering a
  single ambush — the ambush system as a skill check rather than a tax.

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
