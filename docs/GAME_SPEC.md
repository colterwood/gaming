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
  "power_grid": {
    "strength": 6, "speed": 5, "agility": 3,
    "stamina": 5, "durability": 6, "intelligence": 7
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

> Power-grid values above are placeholders. For card-authentic grids, transcribe
> the printed ratings from the actual 1991 card backs and adjust. If the cards
> use a bar length other than 7, change `RANK_MAX` in `config.py` to match —
> everything else derives from it.

### 5.2 Enemy (`data/enemies/hydra_grunt.json`)

Same shape as character minus gifts/birthday/synergies, plus:
`"ai": "aggressive" | "defensive" | "support"` and `"xp_reward"`, `"credit_reward"`.

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
| Training session | trainee EN 15+5/rank; M12: a LOCKOUT of 30+30/rank min (rank 1 = 1 h) — the trainee leaves the party for that time; no clock jump |
| Battle (ambush/trap, won) | +1 h clock (M12 BATTLE_MINUTES) |
| Battle defeat | +3 h clock, party capped at 10 EN, dragged to the tower; the day does NOT end (M12) |
| Combat mission | 40 energy, +3 h clock; never refused for low EN (M11) — the team drains toward 0 and fights with the M9 initiative penalty |
| Craft action | 15 energy, +60 min |
| Small task | 10–20 energy |
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

### 6.3 Attributes & Training

- Six attributes, ranks 1–7 (`RANK_MAX = 7`).
- `effective_rank = base_grid_rank`, plus trained ranks stored separately and
  added for combat math, capped at 7 total for POC simplicity.
- Attribute XP to gain trained rank N: `100 × N` (100, 200, … 700).
- Training XP per session: 40 (basic facility) / 80 (upgraded) / 120 (event).
- Perk choice at trained ranks 3 and 6: two options per attribute, flat effects
  in POC (e.g., Strength 3: `+10% basic damage` vs. `+1 knockback`). Define perk
  tables in `data/perks.json`.
- Mastery (all six at 7) is a stub in POC: detect it, show the foil treatment,
  log Mastery XP, no perk shop yet.

### 6.4 Combat Formulas (`combat/formulas.py` — pure functions, unit-tested)

Let ranks be effective ranks 1–7.

```
max_hp        = 50 + stamina*20 + durability*10
battle_energy = 20 + intelligence*5          (spent by Specials, refills each battle)
initiative    = speed*10 + rand(1,6)          (recomputed each round)
basic_damage  = ability.power + scaling_rank*4 - target.durability*2   (min 1)
special_damage= ability.power + scaling_rank*5 - target.durability*2   (min 1)
crit_chance   = agility*4  (percent; crit = damage × 1.5)
dodge_chance  = agility*3  (percent; roll after hit roll, before crit)
ultimate      = +20 charge per turn taken, +10 per hit received; fires at 100
```

Party size 4 (POC uses 2–3). Actions: Basic, Special, Item, Defend (halve
incoming damage until next turn), Ultimate when charged. Status effects in POC:
Burn (5 dmg/turn, 3 turns) and Stun (skip 1 turn) only.

Boss 1 (Ch. 1): HYDRA Siege Captain + 2 grunts. Boss 2 (Ch. 2): Crossbones —
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
| Ops Floor | Launch story missions, view quest log |

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
tasks + 1 battle), Ant-Man joins roster and appears in binder/party select.
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
  (MISSION_FAIL_COOLDOWN_DAYS) before it reactivates.
- **Ambushes**: while walking a zone, ambush chance scales with zone
  danger and inversely with party size. Squad size rolls 2–8 and the
  ambush only triggers if it outnumbers the party (max 8).
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
