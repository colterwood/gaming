# Roads to Secret Wars — The Bible

*Every number in the game, generated from the code.* Run `python tools/build_bible.py` to rebuild.

This file is **generated**. Do not hand-edit it — edit `game/config.py`, `data/*.json` or `tools/build_bible.py` and regenerate. The design *narrative* (why things are the way they are, milestone by milestone) lives in [GAME_SPEC.md](GAME_SPEC.md); this is the reference sheet.

**At a glance:** 5 playable heroes · 5 npcs · 5 enemy types · 4 enemy level variants · 29 items · 3 zones · 6 tower floors · 7 story quests · 1 side arcs · 16 board jobs · 6 tower repairs · 4 bond scenes

## Contents

1. [The day](#1-the-day)
2. [Energy & health](#2-energy--health)
3. [Progression](#3-progression)
4. [Combat](#4-combat)
5. [Heroes](#5-heroes)
6. [NPCs](#6-npcs)
7. [Enemies](#7-enemies)
8. [Items](#8-items)
9. [Gear](#9-gear)
10. [The tower](#10-the-tower)
11. [Tower repairs](#11-tower-repairs)
12. [Zones & the field](#12-zones--the-field)
13. [Story](#13-story)
14. [Side arcs](#14-side-arcs)
15. [The assignment board](#15-the-assignment-board)
16. [Bonds](#16-bonds)
17. [Calendar](#17-calendar)
18. [The save file](#18-the-save-file)

## 1. The day

The day runs **6:00 AM to 2:00 AM** — 1200 in-game minutes. Past the end, the team passes out.

The world clock ticks **10 in-game minutes per 7 real seconds** while you are on your feet in the hub, which makes a full day about **14 real minutes** of standing still. The clock is frozen inside menus and cutscenes (M25) — reading is not an activity.

### What costs what

**Outside battle, almost nothing jumps the clock** (M37c). Energy is the gate; the day is spent by playing it, by flying, and by sitting in the Med Bay chair.

| Action | Energy | Clock | Notes |
|---|---|---|---|
| Walk around | — | real time | the cosmetic tick |
| Search furniture / a crate / trees | — | — | always available, usually empty |
| Mine an ore seam | 8 | — | one swing per node per day |
| Work a scout point | — | — | free; the walk is the cost |
| Search a side-arc stand | 5 | — |  |
| Salvage a repair part | 5 if **heavy** | — | light parts are free |
| Fit a repair | — | — | the hunt was the price |
| Talk / give a gift | — | — |  |
| Eat a ration / use a med kit | — | — | treats the whole active party |
| Engage a mission | 40 | — | never refused for low EN or a late hour |
| **Quinjet hop** | — | **30m** | the one journey that costs daylight |
| **Med Bay chair** | — | **10 min/tick** | runs in real time; the hours ARE the price |
| Training session | 15 + 5 × level | a *lockout*, not a jump | see Progression |
| Win an ambush / trap fight | — | 1h 00m | battle keeps its costs |
| Lose any fight | capped at 10 | 3h 00m | HP floored at 10% |


### Sleep and collapse

|  | Energy | HP | Credits |
|---|---|---|---|
| Sleep in a bed | full (each hero's own ceiling) | 100% | — |
| Collapse **in the tower** | full | 80% | −10%, max 5,000 |
| Collapse **in the field** | 80% of ceiling | 80% | −10%, max 5,000 |

You always wake beside your own bed on the Common Floor. Jarvis's espresso (bond 4) adds **+10 EN** to a proper night's sleep.

Cleared every night: crate/seam searches, the per-zone fight cap, daily talk flags. Autosave happens at lights-out and **nowhere else** — quit mid-day and you resume at 6:00 AM that morning.

## 2. Energy & health


### Daily energy by Stamina

Team energy is the **minimum** across the active party; team actions drain every member.

| Stamina rank | Daily max EN | vs rank 1 | after a field collapse |
|---|---|---|---|
| 1 | 100 | +0 | 80 |
| 2 | 105 | +5 | 84 |
| 3 | 110 | +10 | 88 |
| 4 | 115 | +15 | 92 |
| 5 | 120 | +20 | 96 |
| 6 | 130 | +30 | 104 |
| 7 | 140 | +40 | 112 |
| 8 | 160 | +60 | 128 |
| 9 | 190 | +90 | 152 |
| 10 | 230 | +130 | 184 |
| Enlightened | 730 | +500 on top | — |


### Low-energy initiative penalty

Below **60%** of a hero's own ceiling, initiative drops 5 per tier, one tier per further 10% down, capped at 6 tiers.

| Energy | Tiers | Initiative lost |
|---|---|---|
| 100% | 0 | 0 |
| 60% | 0 | 0 |
| 50% | 1 | -5 |
| 40% | 2 | -10 |
| 30% | 3 | -15 |
| 20% | 4 | -20 |
| 10% | 5 | -25 |
| 0% | 6 | -30 |


### Health

`max_hp = 50 + stamina × 20 + durability × 10` (effective ranks).

**HP is carried between fights**, stored as a fraction of maximum so a rank-up or a piece of gear raises the pool with it. Restored by: sleeping (full), a rank-up (full), the Med Bay chair (10% per 10 min), and med kits out of combat. A KO in a won fight revives at 10%.

## 3. Progression

Every hero starts at **rank 1** in all six attributes and trains to **10**. What differentiates them is the innate **boost** table (0–7), transcribed from the 1991 Impel card backs.

`effective_rank = (rank + boost × 0.5) × (1 + boost × 0.01)`

A boost buys the combat value **and nothing else** — it does not make the ladder cheaper (M33).

### The ladder

| Rank | XP needed | XP/session | Sessions | EN/session | cr/session | Lockout | cr for the rank | cr cumulative |
|---|---|---|---|---|---|---|---|---|
| 1 → 2 | 100 | 25 | 4 | 20 | 25 | 1h 40m | 100 | 100 |
| 2 → 3 | 200 | 35 | 6 | 25 | 35 | 2h 20m | 210 | 310 |
| 3 → 4 | 400 | 50 | 8 | 30 | 50 | 3h 20m | 400 | 710 |
| 4 → 5 | 800 | 80 | 10 | 35 | 80 | 5h 20m | 800 | 1,510 |
| 5 → 6 | 1,600 | 135 | 12 | 40 | 135 | 9h 00m | 1,620 | 3,130 |
| 6 → 7 | 3,200 | 225 | 15 | 45 | 225 | 15h 00m | 3,375 | 6,505 |
| 7 → 8 | 6,400 | 400 | 16 | 50 | 400 | 1d 6h | 6,400 | 12,905 |
| 8 → 9 | 12,800 | 700 | 19 | 55 | 700 | 2d 6h | 13,300 | 26,205 |
| 9 → 10 | 25,600 | 1200 | 22 | 60 | 1,200 | 4d 0h | 26,400 | 52,605 |

One attribute 1 → 10 is **51,100 XP** and **52,605 cr**; all six is **306,600 XP**. Enlightenment (all six at 10 first) is another **51,200 XP**, trained in level-9 sessions.

Facility multiplier on session XP: ×1 basic, ×2 upgraded (after the Ch. 1 boss), ×3 during a training event. The credit price keys off the BASE table, so the upgraded rack is also half price per XP.

**Sessions per day** are the lesser of what energy allows and what the day allows:

| Level | by energy | by clock | actual |
|---|---|---|---|
| 1 | 4 | 12 | 4 |
| 2 | 3 | 8 | 3 |
| 3 | 3 | 6 | 3 |
| 4 | 2 | 3 | 2 |
| 5 | 2 | 2 | 2 |
| 6 | 2 | 1 | 1 |
| 7 | 1 | 0 | 0 |
| 8 | 1 | 0 | 0 |
| 9 | 1 | 0 | 0 |

<sub>0 by clock means the lockout is longer than a single day — the session still runs, it just spans nights. Energy binds through level 5, so `TRAINING_LOCKOUT_MULT` first bites at level 6.</sub>

A rank-up **restores the hero to full EN and HP** and chimes, wherever the XP came from.

### Perks

Two choices per attribute, at **card ranks 5 and 10**. Effects are flat and stack with gear.

| Attribute | Rank | Perk | Blurb | Effect |
|---|---|---|---|---|
| Strength | 5 | Haymaker | +10% basic damage | basic_damage_pct +10 |
| Strength | 5 | Power Through | +5% max HP | max_hp_pct +5 |
| Strength | 10 | Wrecking Ball | +10% special damage | special_damage_pct +10 |
| Strength | 10 | Unstoppable | +15% basic damage | basic_damage_pct +15 |
| Speed | 5 | Quickdraw | +5 ult charge per turn | ult_turn_charge_bonus +5 |
| Speed | 5 | Fleet Footed | +3% dodge | dodge_bonus +3 |
| Speed | 10 | Blur | +5% dodge | dodge_bonus +5 |
| Speed | 10 | Momentum | +4% crit | crit_bonus +4 |
| Agility | 5 | Precision | +4% crit | crit_bonus +4 |
| Agility | 5 | Evasive | +3% dodge | dodge_bonus +3 |
| Agility | 10 | Killer Instinct | +6% crit | crit_bonus +6 |
| Agility | 10 | Untouchable | +6% dodge | dodge_bonus +6 |
| Stamina | 5 | Conditioning | +10% max HP | max_hp_pct +10 |
| Stamina | 5 | Second Wind | +5 battle energy | battle_energy_flat +5 |
| Stamina | 10 | Iron Lungs | +10 battle energy | battle_energy_flat +10 |
| Stamina | 10 | Juggernaut | +15% max HP | max_hp_pct +15 |
| Durability | 5 | Thick Skin | +8% max HP | max_hp_pct +8 |
| Durability | 5 | Shrug It Off | +2% dodge | dodge_bonus +2 |
| Durability | 10 | Fortress | +12% max HP | max_hp_pct +12 |
| Durability | 10 | Retaliation | +4% crit | crit_bonus +4 |
| Intelligence | 5 | Tactician | +8% special damage | special_damage_pct +8 |
| Intelligence | 5 | Efficient | +5 battle energy | battle_energy_flat +5 |
| Intelligence | 10 | Mastermind | +12% special damage | special_damage_pct +12 |
| Intelligence | 10 | Overcharge | +10 ult charge per turn | ult_turn_charge_bonus +10 |


### XP from the field

Battle XP is paid **per enemy defeated**, to every participating hero (KO'd participants get 50%), and lands on their six attributes immediately, split evenly. There is no bank.

| Enemy level | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|---|
| XP | 12 | 24 | 36 | 54 | 72 | 90 | 114 | 138 | 162 | 192 |


### Passive assignments (benched heroes)

| Assignment | Pays | Requires |
|---|---|---|
| Attribute training | xp/day: 40 | — |
| Ops support | credits/day: 25 | Intelligence 3+ |
| Tower socializing | bond/day: 15 | — |

After **2** consecutive days in the same spot (or idle), unworked attributes decay by **20 XP/day** — banked XP first, then trained ranks.

## 4. Combat

Party size max **4**. Menu order: Basic, Special, Ultimate, Defend, Item.

| Quantity | Formula |
|---|---|
| Max HP | 50 + stamina×20 + durability×10 |
| Battle energy | 20 + intelligence×5 (refills each battle) |
| Initiative | speed×10 + rand(1, 6), re-rolled each round |
| Basic damage | power + rank×4 − target durability×2 (min 1) |
| Special/ultimate damage | power + rank×5 − target durability×2 (min 1) |
| Crit chance | agility×4% → ×1.5 damage |
| Dodge chance | agility×3% (rolled after the hit, before crit) |
| Defend | ×0.5 incoming until your next turn |
| Ultimate charge | +20/turn, +10/hit taken, fires at 100; **carries between battles** |

Status effects: **Burn** 5 dmg/turn for 3 turns · **Stun** skip 1 turn.

### Signature spreads

| Spread | Who | Hits |
|---|---|---|
| `adjacent` | Iron Man — Unibeam | the target plus its immediate living neighbours **in the drawn line** (a downed body blocks the sweep) |
| `random` + `extra_targets` | Ant-Man — Pym Particle Barrage | the target plus N others at random |
| `random_range` | Cap — Shield Throw | the target plus extra_min..extra_max others, decided by coin flips |


### Enemy AI

| AI | Behaviour |
|---|---|
| `aggressive` | highest-damage action at the lowest-HP target |
| `defensive` | guards below 40% HP — but never two turns running, and not at all below 15%, where it swings with everything |
| `support` | heals/buffs an ally below 50% HP, else attacks |


## 5. Heroes


### Ant-Man

*Rare* · Chapter 1 · story recruit
Birthday: Issue 1, Day 6

| Attribute | Boost | Effective @ rank 1 | Effective @ rank 10 |
|---|---|---|---|
| Strength | 2 | 2.04 | 11.22 |
| Speed | 3 | 2.58 | 11.85 |
| Agility | 5 | 3.68 | 13.12 |
| Stamina | 3 | 2.58 | 11.85 |
| Durability | 2 | 2.04 | 11.22 |
| Intelligence | 5 | 3.68 | 13.12 |

At rank 1: **121 HP**, **38 battle EN**, crit 15%, dodge 11%. At rank 10: **399 HP**, **85 battle EN**, crit 52%, dodge 39%.

| Ability | Type | Power | Scales | Cost | Target | Dmg @1* | Dmg @10* | Effect |
|---|---|---|---|---|---|---|---|---|
| Shrink Strike | basic | 11 | AGI | — | single | 25 | 63 | — |
| Pym Particle Barrage | special | 26 | INT | 10 | single (random +2) | 44 | 91 | — |
| Giant-Man Stomp | ultimate | 48 | STR | 100 | all | 58 | 104 | — |

<sub>* against durability 0 — subtract 2× the target's durability.</sub>

**Gifts** — loved: Deluxe Ant Farm, Double Espresso · liked: Tech Scrap, Magic Trick Kit · disliked: Bug Spray · hated: Stack of Paperwork

### Captain America

*Legendary* · starts with you
Birthday: Issue 1, Day 20

| Attribute | Boost | Effective @ rank 1 | Effective @ rank 10 |
|---|---|---|---|
| Strength | 2 | 2.04 | 11.22 |
| Speed | 2 | 2.04 | 11.22 |
| Agility | 5 | 3.68 | 13.12 |
| Stamina | 4 | 3.12 | 12.48 |
| Durability | 2 | 2.04 | 11.22 |
| Intelligence | 3 | 2.58 | 11.85 |

At rank 1: **132 HP**, **32 battle EN**, crit 15%, dodge 11%. At rank 10: **411 HP**, **79 battle EN**, crit 52%, dodge 39%.

| Ability | Type | Power | Scales | Cost | Target | Dmg @1* | Dmg @10* | Effect |
|---|---|---|---|---|---|---|---|---|
| Shield Strike | basic | 12 | STR | — | single | 20 | 56 | — |
| Shield Throw | special | 28 | AGI | 10 | single (random +2–3) | 46 | 93 | — |
| Avengers Assemble | ultimate | 50 | STR | 100 | all | 60 | 106 | — |

<sub>* against durability 0 — subtract 2× the target's durability.</sub>

**Gifts** — loved: 1940s Memorabilia, War Bonds Poster · liked: Sketchbook, Vintage Vinyl · disliked: Modern Slang Guide · hated: HYDRA Propaganda Leaflet

**Synergy — Old Friends** with Iron Man: crit_bonus +8 (bond 6+)

### Hulk

*Legendary* · Chapter 2 · bond recruit at Bond 4 · appears once `hulk_arrived`
Birthday: Issue 1, Day 18

| Attribute | Boost | Effective @ rank 1 | Effective @ rank 10 |
|---|---|---|---|
| Strength | 7 | 4.82 | 14.45 |
| Speed | 2 | 2.04 | 11.22 |
| Agility | 2 | 2.04 | 11.22 |
| Stamina | 6 | 4.24 | 13.78 |
| Durability | 6 | 4.24 | 13.78 |
| Intelligence | 5 | 3.68 | 13.12 |

At rank 1: **177 HP**, **38 battle EN**, crit 8%, dodge 6%. At rank 10: **463 HP**, **85 battle EN**, crit 45%, dodge 34%.

| Ability | Type | Power | Scales | Cost | Target | Dmg @1* | Dmg @10* | Effect |
|---|---|---|---|---|---|---|---|---|
| Smash | basic | 14 | STR | — | single | 33 | 71 | — |
| Thunderclap | special | 24 | STR | 12 | all | 48 | 96 | — |
| Worldbreaker | ultimate | 60 | STR | 100 | all | 84 | 132 | — |

<sub>* against durability 0 — subtract 2× the target's durability.</sub>

**Gifts** — loved: Energy Bar, Double Espresso · liked: Vintage Vinyl, Sketchbook · disliked: Bag of Magnets, Bug Spray · hated: Stack of Paperwork, HYDRA Propaganda Leaflet

### Iron Man

*Legendary* · starts with you
Birthday: Issue 2, Day 14

| Attribute | Boost | Effective @ rank 1 | Effective @ rank 10 |
|---|---|---|---|
| Strength | 6 | 4.24 | 13.78 |
| Speed | 6 | 4.24 | 13.78 |
| Agility | 3 | 2.58 | 11.85 |
| Stamina | 4 | 3.12 | 12.48 |
| Durability | 5 | 3.68 | 13.12 |
| Intelligence | 5 | 3.68 | 13.12 |

At rank 1: **149 HP**, **38 battle EN**, crit 10%, dodge 8%. At rank 10: **430 HP**, **85 battle EN**, crit 47%, dodge 36%.

| Ability | Type | Power | Scales | Cost | Target | Dmg @1* | Dmg @10* | Effect |
|---|---|---|---|---|---|---|---|---|
| Repulsor Blast | basic | 12 | INT | — | single | 26 | 64 | — |
| Unibeam | special | 30 | INT | 12 | single (adjacent) | 48 | 95 | — |
| House Party Protocol | ultimate | 55 | INT | 100 | all | 73 | 120 | — |

<sub>* against durability 0 — subtract 2× the target's durability.</sub>

**Gifts** — loved: Rare Alloy, Double Espresso · liked: Tech Scrap, Vintage Vinyl · disliked: Bag of Magnets · hated: Stack of Paperwork

**Synergy — Old Friends** with Captain America: crit_bonus +8 (bond 6+)

### Thor

*Legendary* · Chapter 2 · story recruit
Birthday: Issue 2, Day 8

| Attribute | Boost | Effective @ rank 1 | Effective @ rank 10 |
|---|---|---|---|
| Strength | 7 | 4.82 | 14.45 |
| Speed | 6 | 4.24 | 13.78 |
| Agility | 4 | 3.12 | 12.48 |
| Stamina | 7 | 4.82 | 14.45 |
| Durability | 6 | 4.24 | 13.78 |
| Intelligence | 3 | 2.58 | 11.85 |

At rank 1: **188 HP**, **32 battle EN**, crit 12%, dodge 9%. At rank 10: **476 HP**, **79 battle EN**, crit 50%, dodge 37%.

| Ability | Type | Power | Scales | Cost | Target | Dmg @1* | Dmg @10* | Effect |
|---|---|---|---|---|---|---|---|---|
| Stormbreaker Swing | basic | 14 | STR | — | single | 33 | 71 | — |
| Chain Lightning | special | 26 | STR | 14 | single (random +3) | 50 | 98 | — |
| Bifrost Strike | ultimate | 58 | STR | 100 | all | 82 | 130 | — |

<sub>* against durability 0 — subtract 2× the target's durability.</sub>

**Gifts** — loved: Shawarma Wrap, Rare Alloy · liked: 1940s Memorabilia, Vintage Vinyl · disliked: Modern Slang Guide · hated: HYDRA Propaganda Leaflet

**Synergy — The Worthy** with Captain America: crit_bonus +6 (bond 6+)

## 6. NPCs

NPCs have no power grid and never fight. They are the talk/gift cast.

| NPC | Bondable | Birthday | Bond unlocks |
|---|---|---|---|
| Agent Coulson | yes | I1 D22 | Bond 4: `coulson_intel` |
| Edwin Jarvis | yes | I1 D9 | Bond 4: `jarvis_service` |
| Hank Pym | yes | I1 D24 | — |
| Pepper Potts | yes | I1 D15 | Bond 4: `pepper_requisitions` |
| S.H.I.E.L.D. Autodoc | no | I1 D1 | — |


| Flag | Effect |
|---|---|
| `jarvis_service` | +10 energy every morning |
| `pepper_requisitions` | shop prices ×0.8 |
| `coulson_intel` | mission credits ×1.5 |


## 7. Enemies

Enemies have no boosts — their `power_grid` **is** their effective rank, valid up to 20 so bosses can sit above the hero ladder. An encounter can ask for a variant at another level with `id@level`.

| id | Name | Lvl | AI | HP | EN | STR/SPD/AGI/STA/DUR/INT | XP | cr |  |
|---|---|---|---|---|---|---|---|---|---|
| `crossbones` | Crossbones | 8 | aggressive | 380 | 35 | 7/4/5/13/7/3 | 138 | 150 | boss |
| `hydra_enforcer@1` | HYDRA Enforcer | 1 | defensive | 80 | 25 | 1/1/1/1/1/1 | 12 | 7 |  |
| `hydra_enforcer@2` | HYDRA Enforcer | 2 | defensive | 110 | 25 | 2/1/1/2/2/1 | 24 | 13 |  |
| `hydra_enforcer` | HYDRA Enforcer | 3 | defensive | 140 | 30 | 3/2/2/3/3/2 | 36 | 20 |  |
| `hydra_medic@1` | HYDRA Field Medic | 1 | support | 80 | 25 | 1/1/1/1/1/1 | 12 | 7 |  |
| `hydra_medic` | HYDRA Field Medic | 3 | support | 100 | 40 | 1/3/2/2/1/4 | 36 | 20 |  |
| `hydra_grunt@1` | HYDRA Grunt | 1 | aggressive | 80 | 25 | 1/1/1/1/1/1 | 12 | 8 |  |
| `hydra_grunt` | HYDRA Grunt | 2 | aggressive | 110 | 30 | 2/2/2/2/2/2 | 24 | 15 |  |
| `hydra_siege_captain` | HYDRA Siege Captain | 6 | aggressive | 260 | 35 | 5/3/3/8/5/3 | 90 | 100 | boss |

**Crossbones** enrages below 30% HP: ×1.5 damage.

**Abilities**
| Enemy | Ability | Type | Power | Scales | Cost | Target | Effect |
|---|---|---|---|---|---|---|---|
| Crossbones | Gauntlet Smash | basic | 15 | STR | — | single | — |
| Crossbones | Concussive Charge | special | 26 | STR | 12 | single | stun |
| HYDRA Enforcer | Riot Baton | basic | 12 | STR | — | single | — |
| HYDRA Field Medic | Sidearm | basic | 8 | INT | — | single | — |
| HYDRA Field Medic | Field Stim | special | 25 | INT | 8 | single | heal |
| HYDRA Grunt | Rifle Burst | basic | 9 | STR | — | single | — |
| HYDRA Grunt | Frag Grenade | special | 13 | STR | 12 | all | — |
| HYDRA Siege Captain | Siege Hammer | basic | 14 | STR | — | single | — |
| HYDRA Siege Captain | Incendiary Rounds | special | 24 | STR | 10 | single | burn |


## 8. Items

**Consumables**

| Item | id | Price | Sources | Effect |
|---|---|---|---|---|
| Cup of Coffee | `coffee` | 20 | tower_cafe, street_cart | +10 EN (team) |
| Energy Bar | `energy_bar` | 30 | tower_cafe | +10 battle EN |
| Jarvis's Power Smoothie | `power_smoothie` | 110 | tower_cafe | +40 EN (team) |
| Med Kit | `med_kit` | 50 | tower_shop, street_cart | +40 HP in battle / +40% out |
| Shawarma Wrap | `shawarma` | 60 | tower_cafe, street_cart | +25 EN (team) |

**Gifts**

| Item | id | Price | Sources | Effect |
|---|---|---|---|---|
| 1940s Memorabilia | `forties_memorabilia` | 100 | tower_shop | — |
| Bag of Magnets | `magnets` | 15 | tower_shop | — |
| Bug Spray | `bug_spray` | 12 | tower_shop | — |
| Deluxe Ant Farm | `ant_farm` | 75 | tower_shop | — |
| Double Espresso | `double_espresso` | 40 | tower_cafe | — |
| HYDRA Propaganda Leaflet | `hydra_propaganda` | 10 | missions | — |
| Magic Trick Kit | `magic_trick_kit` | 30 | tower_shop | — |
| Modern Slang Guide | `modern_slang_guide` | 20 | tower_shop | — |
| Rare Alloy | `rare_alloy` | 120 | tower_shop | — |
| Sketchbook | `sketchbook` | 35 | tower_shop | — |
| Stack of Paperwork | `paperwork` | 5 | tower_shop | — |
| Tech Scrap | `tech_scrap` | 25 | tower_shop, missions | — |
| Vintage Vinyl | `vintage_vinyl` | 60 | tower_shop | — |
| War Bonds Poster | `war_bonds_poster` | 80 | tower_shop | — |

**Materials**

| Item | id | Price | Sources | Effect |
|---|---|---|---|---|
| Adamantium Ingot | `adamantium` | 340 | mining | — |
| ISO-8 Crystal | `iso8` | 90 | mining | — |
| Vibranium Shard | `vibranium` | 260 | mining | — |

**Weapons**

| Item | id | Price | Sources | Effect |
|---|---|---|---|---|
| Combat Gauntlets | `combat_gauntlets` | 400 | tech_lab | strength +2 |
| Targeting Optics | `targeting_optics` | 450 | tech_lab | crit_bonus +8 |

**Armors**

| Item | id | Price | Sources | Effect |
|---|---|---|---|---|
| Kevlar Weave | `kevlar_weave` | 380 | tech_lab | durability +2 |
| Stark Underlay | `stark_underlay` | 520 | tech_lab | max_hp_pct +10, stamina +1 |

**Accessorys**

| Item | id | Price | Sources | Effect |
|---|---|---|---|---|
| Arc Cell | `arc_cell` | 480 | tech_lab | battle_energy_flat +10, intelligence +1 |
| Field Stim Rig | `field_stim_rig` | 350 | tech_lab | speed +2 |

**Artifacts**

| Item | id | Price | Sources | Effect |
|---|---|---|---|---|
| Stormbreaker | `stormbreaker` | 0 | midtown | — |

**Who loves what** — gift reactions are worth loved +80, liked +45, neutral +20, disliked -20, hated -40, ×8 on a birthday.

| Item | Reactions |
|---|---|
| 1940s Memorabilia | Captain America (loved) · Agent Coulson (loved) · Edwin Jarvis (liked) · Thor (liked) |
| Bag of Magnets | Hulk (disliked) · Iron Man (disliked) · Pepper Potts (disliked) |
| Bug Spray | Ant-Man (disliked) · Agent Coulson (hated) · Hank Pym (disliked) · Hulk (disliked) · Edwin Jarvis (disliked) · Pepper Potts (hated) |
| Deluxe Ant Farm | Ant-Man (loved) |
| Double Espresso | Ant-Man (loved) · Hank Pym (liked) · Hulk (loved) · Iron Man (loved) · Edwin Jarvis (loved) · Pepper Potts (loved) |
| Energy Bar | Hulk (loved) |
| HYDRA Propaganda Leaflet | Captain America (hated) · Agent Coulson (disliked) · Hank Pym (hated) · Hulk (hated) · Edwin Jarvis (hated) · Thor (hated) |
| ISO-8 Crystal | Hank Pym (loved) |
| Magic Trick Kit | Ant-Man (liked) · Agent Coulson (liked) |
| Modern Slang Guide | Captain America (disliked) · Thor (disliked) |
| Rare Alloy | Iron Man (loved) · Thor (loved) |
| Shawarma Wrap | Thor (loved) |
| Sketchbook | Captain America (liked) · Hank Pym (loved) · Hulk (liked) · Edwin Jarvis (liked) · Pepper Potts (liked) |
| Stack of Paperwork | Ant-Man (hated) · Hulk (hated) · Iron Man (hated) · Pepper Potts (loved) |
| Tech Scrap | Ant-Man (liked) · Hank Pym (liked) · Iron Man (liked) |
| Vintage Vinyl | Captain America (liked) · Agent Coulson (liked) · Hulk (liked) · Iron Man (liked) · Edwin Jarvis (loved) · Thor (liked) |
| War Bonds Poster | Captain America (loved) · Agent Coulson (loved) · Pepper Potts (liked) |


## 9. Gear

An effect is **either** a flat attribute rank bonus — which is how gear takes a hero past the trained ceiling of 10 — **or** one of the perk effect keys, summed with whatever the perks give. Worn or carried, never both.

Upgrade levels belong to the **schematic**, not the object: a level-3 Kevlar Weave means the lab builds them that way now. Effects scale ×1 / ×1.5 / ×2.0, attribute bonuses rounded to whole ranks. Max level 3.

| To level | Credits | Materials | Days at the bench |
|---|---|---|---|
| 2 | 250 | 3× ISO-8 Crystal | 2 |
| 3 | 600 | 8× ISO-8 Crystal | 3 |

Nothing is applied until the piece is **collected in person**; the team fights without it in the meantime.

## 10. The tower

| Floor | id | Hours | When shut | Needs flag |
|---|---|---|---|---|
| Common Floor | `common` | always open | — | — |
| Ops Floor | `ops` | always open | — | `elevator_repaired` |
| Training Floor | `training` | 6:00 AM–11:00 PM | **locks** | `elevator_repaired` |
| Med Bay | `med_bay` | 6:00 AM–10:00 PM | station only | `elevator_repaired` |
| Tech Lab | `tech_lab` | 9:00 AM–6:00 PM | station only | `elevator_repaired` |
| Pym Lab | `pym_lab` | 9:00 AM–6:00 PM | station only | `pym_lab_unlocked` |


| Room | Operator | What they run |
|---|---|---|
| Tech Lab | Jarvis | the fabricator — talk once, then he opens it |
| Pym Lab | Hank Pym | the upgrade bench |
| Med Bay | two S.H.I.E.L.D. autodocs | the treatment chair (not bondable) |
| Common Floor | Jarvis, Coulson | talk, gifts, the board |
| Ops Floor | Pepper Potts | the ops console, the Quinjet bay |


**Bag capacity** is derived from who is on the team: 4 slots per active member, 16 at a full party of 4. One slot holds up to 99 of one item.

## 11. Tower repairs

Accepted at the board (or raised in conversation), then **worked in person**. One at a time. Fitting costs nothing — the hunt is the price.

| Repair | id | Floor | Parts | Kinds | EN cost | XP | Offered by | Gated on | Sets |
|---|---|---|---|---|---|---|---|---|---|
| Fix the Service Elevator | `repair_elevator` | Common Floor | 3 | 1 hidden 1 npc 1 plain | 0 | 30 | jarvis | — | `elevator_repaired` |
| Get the Quinjet Airworthy | `repair_quinjet` | Ops Floor | 4 | 2 hidden 2 plain | 15 | 36 | pepper_potts | `elevator_repaired` | `quinjet_repaired` |
| Restore the Training Floor | `repair_training` | Training Floor | 3 | 2 hidden 1 plain | 5 | 30 | board | `board_unlocked` | `training_repaired` |
| Open the Med Bay | `repair_med_bay` | Med Bay | 4 | 3 hidden 1 plain | 0 | 48 | board | `board_unlocked` | `med_bay_repaired` |
| Restart the Tech Lab | `repair_tech_lab` | Tech Lab | 6 | 2 battle 2 hidden 1 npc 1 plain | 0 | 48 | board | `board_unlocked`, quest *ch1_siege* | `tech_lab_repaired` |
| Get Into the Pym Lab | `repair_pym_lab` | Pym Lab | 4 | 1 battle 1 hidden 1 mine 1 npc | 0 | 60 | board | `board_unlocked`, `pym_lab_unlocked` | `pym_lab_repaired` |

Part kinds: **plain** (a marker shows it) · **hidden** (inside furniture or a seam, no marker) · **npc** (handed over in conversation) · **battle** (drops from a won fight) · **mine** (rolls out of any ore seam).

Every part, in order:

| Repair | # | Kind | Where |  |
|---|---|---|---|---|
| Fix the Service Elevator | 0 | npc | from coulson |  |
|  | 1 | plain | common (30, 6) |  |
|  | 2 | hidden | common (24, 5) |  |
| Get the Quinjet Airworthy | 0 | plain | ops (8, 14) | heavy |
|  | 1 | plain | training (33, 16) | heavy |
|  | 2 | hidden | common (38, 17) |  |
|  | 3 | hidden | ops (17, 8) | heavy |
| Restore the Training Floor | 0 | hidden | ops (1, 10) |  |
|  | 1 | hidden | training (14, 12) | heavy |
|  | 2 | plain | midtown (25, 5) |  |
| Open the Med Bay | 0 | hidden | common (21, 5) |  |
|  | 1 | plain | ops (20, 16) |  |
|  | 2 | hidden | med_bay (11, 7) |  |
|  | 3 | hidden | docks (3, 3) |  |
| Restart the Tech Lab | 0 | plain | tech_lab (31, 6) |  |
|  | 1 | hidden | tech_lab (10, 8) |  |
|  | 2 | hidden | common (1, 8) |  |
|  | 3 | battle | 33% per win |  |
|  | 4 | battle | 33% per win |  |
|  | 5 | npc | from jarvis (after 5 found) |  |
| Get Into the Pym Lab | 0 | mine | 33% per swing, any seam |  |
|  | 1 | npc | from pepper_potts |  |
|  | 2 | hidden | tech_lab (25, 8) |  |
|  | 3 | battle | certain with ant_man |  |


## 12. Zones & the field

| Zone | id | Danger | Ambush rate | Trap chance | Crates | Ore seams | Trees |
|---|---|---|---|---|---|---|---|
| Midtown | `midtown` | ! | 0.5 | 7% | 4 | 3 | 20 |
| Hudson Docks | `docks` | !! | 1.0 | 14% | 15 | 3 | 0 |
| HYDRA District | `hydra_district` | !!! | 2.0 | 21% | 17 | 3 | 0 |

`danger` drives the badge, the trap risk and the enemy pool. `ambush_rate` drives how often you are jumped — a separate knob that currently agrees with danger.

### Ambush probability

One roll per **0.6 seconds of walking** (standing still never rolls). `chance = ambush_rate × (0.01 + 0.006 × missing party members)`.

| Party | Midtown | Hudson Docks | HYDRA District |
|---|---|---|---|
| 4 | 0.5% (1 per 120s) | 1.0% (1 per 60s) | 2.0% (1 per 30s) |
| 3 | 0.8% (1 per 75s) | 1.6% (1 per 38s) | 3.2% (1 per 19s) |
| 2 | 1.1% (1 per 55s) | 2.2% (1 per 27s) | 4.4% (1 per 14s) |
| 1 | 1.4% (1 per 43s) | 2.8% (1 per 21s) | 5.6% (1 per 11s) |

Capped at **3 field fights per zone per day** — ambushes and sprung traps share the budget. Cleared at sleep.

**Squad size** — an ambush always outnumbers the party:

| Extra attackers | Chance |
|---|---|
| 1 | 50% |
| 2 | 35% |
| 3 | 10% |
| 4 | 5% |

| Party size | Hard cap on the squad |
|---|---|
| 1 | 4 |
| 2 | 6 |
| 3 | 8 |
| 4 | 8 |

Absolute maximum 8. Trap squads roll 2..cap with no outnumber guarantee.

**Who turns up**, by danger:

| Danger | Pool |
|---|---|
| 1 | 1× HYDRA Grunt |
| 2 | 2× HYDRA Grunt, 1× HYDRA Enforcer, 1× HYDRA Field Medic |
| 3 | 1× HYDRA Grunt, 2× HYDRA Enforcer, 1× HYDRA Field Medic |


### Loot & mining

| Zone | Find chance | Credits | Item chance | Possible items | Expected/day |
|---|---|---|---|---|---|
| Midtown | 35% | 15–35 cr | 35% | Vintage Vinyl, Sketchbook, Shawarma Wrap | ~35 cr/day |
| Hudson Docks | 30% | 8–20 cr | 35% | Tech Scrap, Cup of Coffee | ~63 cr/day |
| HYDRA District | 40% | 25–60 cr | 40% | HYDRA Propaganda Leaflet, Rare Alloy | ~289 cr/day |

<sub>Rolled after the trap check; a trap forfeits the loot.</sub>

| Zone | Yields | Dust |
|---|---|---|
| Midtown | ISO-8 Crystal 80% | 20% |
| Hudson Docks | ISO-8 Crystal 78% | 22% |
| HYDRA District | ISO-8 Crystal 84% | 16% |

One swing per seam per day, 8 EN each.

## 13. Story

Quests unlock strictly in order. A quest is **offered** at the Ops Console and shows nothing in the field until accepted; the deadline starts at accept.

| # | Quest | id | Ch | Kind | Where | Deadline | Opposition | Recruits | Sets |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Shattered Shield | `ch1_shattered_shield` | Ch1 | battle | Hudson Docks | 3 | 3× HYDRA Grunt | — | — |
| 2 | Case the Safehouse | `ch1_case_safehouse` | Ch1 | scout | Midtown | — | 3 scout points | — | — |
| 3 | Spoof the Ankle Monitor | `ch1_spoof_monitor` | Ch1 | scout | Midtown | — | 3 scout points | — | — |
| 4 | Break Out Scott Lang | `ch1_break_out_lang` | Ch1 | battle | Midtown | 3 | 2× HYDRA Grunt, 2× HYDRA Enforcer, 2× HYDRA Field Medic | ant_man | `pym_lab_unlocked` |
| 5 | Siege of the Tower | `ch1_siege` | Ch1 | battle | HYDRA District | 4 | 1× HYDRA Siege Captain, 3× HYDRA Grunt, 2× HYDRA Enforcer | — | `training_upgraded`, `hulk_arrived` |
| 6 | Cell Hunt | `ch2_cell_hunt` | Ch2 | battle | Hudson Docks | 3 | 2× HYDRA Enforcer, 1× HYDRA Field Medic, 2× HYDRA Grunt | — | — |
| 7 | Crossbones | `ch2_crossbones` | Ch2 | battle | HYDRA District | 4 | 1× Crossbones, 1× HYDRA Field Medic, 2× HYDRA Enforcer, 1× HYDRA Grunt | — | `ch2_complete` |

A failed mission cools down **2 days**. A *fight* mission then re-arms itself in the field; anything else has to be re-accepted at Ops.

**Chapter 3–4 gate:** every Ch. 1–2 mission complete **and** the tower fully repaired.

## 14. Side arcs

Conditional arcs run *alongside* the story chain, so one can sit dormant without stalling the missions behind it. Requirements are re-checked at the sleep boundary.

### Something Strange in Midtown
*Something came down in the Midtown trees.*

|  |  |
|---|---|
| Opens when | `ch2_complete`; Captain America rank 3 in all six |
| Where | Midtown |
| Search sites | 5 stands (5 EN each) |
| Prize | Stormbreaker |
| Who can lift it | Captain America — must be on the ACTIVE team |
| Recruits | Thor |
| Sets | `thor_joined` |
| Sound | thunder |


## 15. The assignment board

Every job is **one-shot**. Two rotating jobs per unlocked tier per day. Repairs take a slot. Skill requirements are never advertised — sending the wrong hero gets a refusal in Coulson's voice.

Tier unlocks by team power (sum of the top-4 roster heroes' effective grid totals): tier 2 at 90, tier 3 at 160

Dispatch pay multiplier = 1 + 0.01 × (avg sent-hero grid total − 22), clamped 0.8–1.5, snapshotted when the job starts.

XP budget per tier (vs the passive train assignment at 40 XP/day): tier 1 ×0.5 = 20/day, tier 2 ×1.0 = 40/day, tier 3 ×1.5 = 60/day

| Tier | Job | id | Crew | cr | XP | Bond | Requires | Posting odds |
|---|---|---|---|---|---|---|---|---|
| 1 | Calibrate Tower Sensors | `calibrate_sensors` | 1H/2D | 150 | 40 → INT | — | INT rank 2+; INT boost 4+ | always |
| 1 | Courier Pepper's Contracts | `pepper_contracts` | 1H/1D | 50 | 20 → SPE | +35 pepper_potts | — | always |
| 1 | Debug a JARVIS Subroutine | `debug_jarvis` | 1H/1D | 65 | 20 → INT | — | INT rank 2+; INT boost 5+ | always |
| 1 | Escort a Supply Convoy | `escort_convoy` | 2H/2D | 280 | 10 → STR, STA, AGI, DUR | — | — | always |
| 1 | Inventory the Armory | `inventory_armory` | 1H/1D | 70 | 20 → DUR | — | — | always |
| 1 | Parts Run for Jarvis | `jarvis_parts_run` | 1H/1D | 45 | 20 → SPE | +35 jarvis | — | always |
| 1 | Spar with S.H.I.E.L.D. Rookies | `spar_rookies` | 2H/1D | 130 | 7 → STR, AGI, DUR | — | STR/DUR/AGI/STA rank 2+; STR/DUR/AGI/STA boost 6+ | always |
| 1 | Spot Hulk at the Heavy Bags | `hulk_smash_therapy` | 1H/1D | 40 | 20 → STR | +600 hulk | flag `hulk_arrived` | 5%/25%/80% by hulk bond |
| 1 | Sweep the Quinjet Hangar | `sweep_hangar` | 1H/1D | 60 | 20 → STA | — | — | always |
| 2 | Decrypt a HYDRA Data Cache | `decrypt_cache` | 1H/2D | 230 | 80 → INT | — | INT rank 3+; INT rank 2+ or boost 5+; INT rank 1+ or boost 7+ | always |
| 2 | Guard the Stark Expo Floor | `guard_expo` | 2H/1D | 210 | 13 → STR, DUR, STA | — | — | always |
| 2 | Run a S.H.I.E.L.D. Boot Camp | `train_recruits` | 2H/2D | 380 | 20 → STR, STA, AGI, DUR | — | STR/DUR/AGI/STA rank 3+; STR/DUR/AGI/STA rank 2+ or boost 5+; STR/DUR/AGI/STA rank 1+ or boost 7+ | always |
| 2 | S.H.I.E.L.D. Liaison Detail | `shield_liaison` | 1H/2D | 190 | 80 → SPE | +45 coulson | coulson bond 1+ | always |
| 3 | Deep Recon: HYDRA Sub Base | `deep_recon` | 2H/2D | 520 | 20 → all six | — | all six rank 2+ | always |
| 3 | Escort the U.N. Delegation | `escort_delegation` | 2H/1D | 400 | 10 → all six | +60 coulson | coulson bond 2+ | always |
| 3 | Field-Test Stark Prototypes | `prototype_test` | 1H/2D | 340 | 120 → INT | +60 pepper_potts | pepper_potts bond 2+ | always |

Total one-shot board income: **890 (tier 1) + 1,010 (tier 2) + 1,260 (tier 3) = 3,160 cr**, before the crew multiplier. Once cleared, the board is done — missions, ambush drops and zone loot are the only repeatable income.

## 16. Bonds

**250 points per level**, 10 levels, 2,500 lifetime max.

| Action | Points |
|---|---|
| Daily talk (once per character) | +15 |
| Same-party mission | +10 |
| Loved gift | +80 |
| Liked gift | +45 |
| Neutral gift | +20 |
| Disliked gift | -20 |
| Hated gift | -40 |
| Birthday | ×8 |
| Repeating yesterday's gift | −5 (after the multiplier) |
| Personal quest | +150–250 |

Gift limits: **1 per receiver per day**, max **2 per rolling 5 days**.

| Level | Gate |
|---|---|
| 2 | bond scene |
| 4 | relationship recruit |
| 6 | synergy passive |
| 8 | exclusive gear quest |
| 10 | signature scene + costume |

**Authored bond scenes**

| id | Character | Level | Title |
|---|---|---|---|
| `coulson_bond_2` | Agent Coulson | 2 | Mint Condition |
| `jarvis_bond_2` | Edwin Jarvis | 2 | The Tower Keeps Its Own Hours |
| `hulk_bond_2` | Hulk | 2 | Quiet Floor |
| `hulk_bond_4` | Hulk | 4 | The Quiet Floor |

Starters and story recruits give flavour talk only — no points.

## 17. Calendar

An Issue is **28 days**, in 4 weeks of 7.

| Issue | Name | Days |
|---|---|---|
| 1 | Shattered Shield | 28 |

| Event | When | Effects |
|---|---|---|
| S.H.I.E.L.D. Supply Drop | Issue 1, days 12–13 | shop_discount: 0.5, training_xp_bonus: 40 |

**Birthdays** — S.H.I.E.L.D. Autodoc I1D1 · Ant-Man I1D6 · Edwin Jarvis I1D9 · Pepper Potts I1D15 · Hulk I1D18 · Captain America I1D20 · Agent Coulson I1D22 · Hank Pym I1D24 · Thor I2D8 · Iron Man I2D14

## 18. The save file

One JSON per slot at `saves/slot_N.json`, 3 independent games, one `.bak` kept. **The autosave at lights-out is the only save.**

| Key | Holds |
|---|---|
| `board_checked_day` | int = 0 |
| `bonds` | dict |
| `completed_tasks` | list |
| `credits` | int = 0 |
| `day` | int = 1 |
| `dispatches` | list |
| `energy` | int = 100 |
| `fights_today` | dict |
| `gear_levels` | dict |
| `inventory` | dict |
| `issue` | int = 1 |
| `party` | list |
| `path` | NoneType = None |
| `pending_scenes` | list |
| `quests` | dict |
| `repairs` | dict |
| `roster` | dict |
| `searched_today` | list |
| `story_flags` | dict |
| `time_minutes` | int = 360 |
| `unlocks` | dict |
| `upgrades` | list |


Per-hero roster entry: `trained_ranks`, `attribute_xp`, `perks`, `perk_choices`, `gear`, `ult_charge`, `energy`, `hp_fraction`, plus transient `training` / `dispatch` / `assignment` / `done_training` / `leveled_up` / `mastered` / `enlightened`.

Every key added after M16 is read through `.get`/`.setdefault`, so an older save loads and plays. Migrations run at load: pre-M13 dispatch spots, pre-M16 training locks, pre-M29 tower state, pre-M36 perk tiers, story-flag backfill, and the M21 battle-XP bank.

---

*Generated by `tools/build_bible.py` from 10 characters, 9 enemy entries, 29 items and 161 tuned constants.*
