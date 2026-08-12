"""Tunable constants. Every number here is sourced from docs/GAME_SPEC.md §6/§8."""

import os

# --- Display (§9 M7: 16-bit pixel pipeline) ---
# All scenes lay out in INTERNAL coordinates; the frame is scaled up
# nearest-neighbor to the window for chunky uniform pixels.
WIDTH = 640                 # internal render width
HEIGHT = 360                # internal render height
WINDOW_SCALE = 2            # window = 1280x720
FPS = 60
TITLE = "Marvel: Roads to Secret Wars — POC"

# Master palette: every screen and sprite draws only these colors.
# Anchored to the sampled 1991 Impel card colors (yellow/blue/pink/cream/red).
PIXEL_PALETTE = {
    "ink": "#16121E",
    "shadow": "#2A2438",
    "navy": "#2E3350",
    "steel_dark": "#48506B",
    "steel": "#7C8BA6",
    "steel_light": "#AEBACF",
    "white": "#FFFDF5",
    "paper": "#F8EFDC",
    "cream": "#EFE3C8",
    "tan": "#D9B98C",
    "wood": "#C68A53",
    "wood_dark": "#8A5A32",
    "brown": "#5C3821",
    "red": "#E82C2C",
    "red_dark": "#9E1B1B",
    "maroon": "#6B1010",
    "pink": "#E07098",
    "orange": "#E87820",
    "yellow": "#F8D808",
    "gold": "#FFC72C",
    "gold_dark": "#B8860B",
    "green": "#3E9C4E",
    "green_dark": "#256B33",
    "mint": "#9CD9A8",
    "blue": "#2440D8",
    "blue_dark": "#101A80",
    "sky": "#4FA4E8",
    "purple": "#7B4FB8",
    "skin": "#F0C8A0",
    "skin_dark": "#C8906C",
    "grey": "#A0A098",
    "grey_dark": "#56565A",
}

# --- Power grid & innate boosts (§6.3, reworked M15) ---
# Everyone STARTS at rank 1 in all six and trains up to rank 10. What makes
# a character feel like themselves is their innate BOOST table (1..7, the
# old card-back grid): boosts add half a rank each plus a small percentage,
# so Iron Man out-hits Cap on Strength at rank 1 and still does at rank 10.
RANK_START = 1
RANK_MAX = 10
# Enemies aren't bound by the hero rank ladder — a boss may be written
# above it so it can soak a party of ultimates (M15 §6.4 balance pass).
ENEMY_RANK_MAX = 20
BOOST_MAX = 7
BOOST_RANK_VALUE = 0.5      # each boost level is worth this much flat rank
BOOST_PCT = 0.01            # ...plus this much percent, which grows with rank
TRAINED_MAX = RANK_MAX - RANK_START          # trained ranks 0..9
ATTRIBUTES = ("strength", "speed", "agility", "stamina", "durability", "intelligence")

# --- Clock & Energy (§6.1) — times in in-game minutes since midnight ---
DAY_START_MINUTES = 6 * 60          # 6:00 AM
DAY_END_MINUTES = 26 * 60           # 2:00 AM next day
TICK_GAME_MINUTES = 10              # cosmetic tick: 10 in-game minutes...
TICK_REAL_SECONDS = 7               # ...per 7 real seconds
DAILY_ENERGY = 100
PASS_OUT_NEXT_DAY_ENERGY = 80

# Training energy scales with the level being trained (M9). Minutes come
# from TRAINING_MINUTES_BY_LEVEL (M16) and are a LOCKOUT, not a clock jump
# — a high-level session legitimately spans more than one day.
TRAINING_ENERGY_BASE = 15
TRAINING_ENERGY_PER_RANK = 5
MISSION_ENERGY = 40
MISSION_MINUTES = 180
CRAFT_ENERGY = 15
CRAFT_MINUTES = 60
TALK_GIFT_MINUTES = 20              # talking/gifting costs time, no energy

# Walkable-map grid (tower floors and zones share it; §9 M8)
MAP_TILES_W = 40
MAP_TILES_H = 21

# --- Message log (M19) ---
# Three lines sit above the hint bar; PgUp/PgDn page back through the
# rest so a message that scrolls past on a busy night can still be read.
LOG_VISIBLE_LINES = 3
LOG_HISTORY_MAX = 12

# --- Calendar (§6.2 / §7) ---
DAYS_PER_ISSUE = 28
DAYS_PER_WEEK = 7                   # weeks are 7-day rows of the 28-day Issue

# --- Bonds (§6.2) ---
BOND_TALK_POINTS = 15               # once/day/character
BOND_MISSION_POINTS = 10            # same-party mission
GIFT_POINTS = {
    "loved": 80,
    "liked": 45,
    "neutral": 20,
    "disliked": -20,
    "hated": -40,
}
BIRTHDAY_GIFT_MULTIPLIER = 8
BOND_POINTS_PER_LEVEL = 250
BOND_LEVEL_MAX = 10
BOND_LIFETIME_MAX = 2500
# (weekly gift cap replaced by the M12 rolling window — see GIFT_WINDOW_DAYS)
BOND_GATE_SCENE = 2                 # bond scene
BOND_GATE_RECRUIT = 4               # relationship recruit
BOND_GATE_SYNERGY = 6               # synergy passive
BOND_GATE_GEAR = 8                  # exclusive gear quest
BOND_GATE_SIGNATURE = 10            # signature scene + costume
BOND_PERSONAL_QUEST_MIN = 150       # personal quest reward range
BOND_PERSONAL_QUEST_MAX = 250

# NPC bond-unlock effects (relationship redesign: NPCs + bond-recruits)
JARVIS_ENERGY_BONUS = 10            # jarvis_service flag: morning espresso
PEPPER_SHOP_DISCOUNT = 0.8          # pepper_requisitions flag: price multiplier
COULSON_CREDIT_MULT = 1.5           # coulson_intel flag: mission credits

# --- Field ops & team systems (M9) ---
# Initiative penalty when a hero's daily energy is low: none at >= 60%,
# then one tier per additional 10% below.
EN_PENALTY_THRESHOLD = 0.6
EN_PENALTY_STEP = 0.1
EN_PENALTY_INITIATIVE = 5           # initiative lost per tier
EN_PENALTY_MAX_TIERS = 6

KO_XP_MULT = 0.5                    # KO'd participants earn half XP

AMBUSH_MAX_SIZE = 8
AMBUSH_BASE_CHANCE = 0.010          # per walk-tick, scaled by zone danger
AMBUSH_PARTY_BONUS = 0.006          # added per missing party member below 4
AMBUSH_TICK_SECONDS = 0.6           # walking time between ambush rolls
# M15: an ambush always outnumbers the party, by this many (cumulative
# probability, extra attackers) — and never by more than double the party.
AMBUSH_SIZE_TABLE = ((0.50, 1), (0.85, 2), (0.95, 3), (1.00, 4))
# M20: hard ceiling on a squad by how many heroes are actually standing
# there. This binds for booby-trap squads too — those used to ignore party
# size completely, so a lone hero could open a crate onto eight HYDRA.
AMBUSH_MAX_BY_PARTY = {1: 4, 2: 6, 3: 8, 4: 8}

ATROPHY_GRACE_DAYS = 2              # same-spot days before decay starts
ATROPHY_XP_PER_DAY = 20             # XP drained per unworked attribute

MISSION_FAIL_COOLDOWN_DAYS = 2
TRAVEL_MINUTES = 30                 # Quinjet hop tower <-> zone

# --- Bag capacity (M18) ---
# The team carries what its members can carry: 4 slots each, so a full
# party of 4 has 16. One slot holds one item id up to STACK_MAX — the
# 100th of anything spills into a second slot.
INVENTORY_SLOTS_PER_HERO = 4
INVENTORY_SLOTS_MAX = 16            # = SLOTS_PER_HERO x PARTY_SIZE_MAX (4)
INVENTORY_STACK_MAX = 99

# --- Field life (M10) ---
EAT_MINUTES = 10                    # eating a ration advances the clock
SEARCH_MINUTES = 15                 # rummaging a crate/dumpster
SEARCH_TRAP_CHANCE = 0.07           # per search, scaled by zone danger

# --- Scout quests (M13): field work per scout point ---
SCOUT_ENERGY = 5
SCOUT_MINUTES = 20

# --- Story unlocks (M17): combing a search site in a side arc ---
UNLOCK_SEARCH_ENERGY = 5
UNLOCK_SEARCH_MINUTES = 20

# --- Tower repairs (M29) ---
# Salvaging a part is scout-point work that happens indoors; fitting it is
# a craft action. Repairs are the player's own energy and clock, which is
# why they sit outside the M25 board XP budget (that prices a hero's days).
REPAIR_PART_ENERGY = 5
REPAIR_PART_MINUTES = 20
REPAIR_ENERGY = 15
REPAIR_MINUTES = 60

# --- Med Bay (M30) ---
# Sit in the chair and the clock runs while you mend: 10% of the daily
# maximum per 10 in-game minutes, so a full team refill costs 100 of the
# day's 1,200 usable minutes. The price is hours, never credits or energy.
# REST_SECONDS_PER_TICK is how fast that plays out in real time — the sit
# is watched, not skipped, which is the whole point of the room.
MEDBAY_ENERGY_PER_TICK = 10
MEDBAY_TICK_MINUTES = 10
MEDBAY_REST_SECONDS_PER_TICK = 0.30

# --- Gear (M31) ---
# Upgrade levels belong to the SCHEMATIC, not the object: a level-3 Kevlar
# Weave means the lab builds them that way now. Each level above the first
# adds this much of the base effect (L1 1.0x, L2 1.5x, L3 2.0x).
GEAR_UPGRADE_STEP = 0.5
GEAR_LEVEL_MAX = 3

# --- Materials & the Pym Lab (M32) ---
# Ore nodes are the zones' second renewable: one swing per node per day,
# priced like a heavy crate search, with the same danger-scaled trap risk
# — the best metal is in the worst neighbourhood.
MINE_ENERGY = 8
MINE_MINUTES = 30
# Leaving gear at the Pym bench: what a level costs and how many nights it
# is gone for. Keyed by the level being upgraded TO.
GEAR_UPGRADE_CREDITS = {2: 250, 3: 600}
GEAR_UPGRADE_DAYS = {2: 2, 3: 3}
GEAR_UPGRADE_MATERIALS = {
    2: {"iso8": 3},
    3: {"vibranium": 2, "adamantium": 1},
}

# --- Battle time & defeat (M12) ---
# Engaging a mission costs MISSION_ENERGY/MISSION_MINUTES up front (§6.1).
# An ambush/trap fight you WIN eats BATTLE_MINUTES; a DEFEAT (any battle)
# costs DEFEAT_RECOVERY_MINUTES, sets every party member to DEFEAT_ENERGY,
# and drags the team back to the tower — the day does NOT end.
BATTLE_MINUTES = 60
DEFEAT_RECOVERY_MINUTES = 180
DEFEAT_ENERGY = 10

# --- Gifts (M12 rework; replaces the §6.2 weekly cap) ---
GIFT_WINDOW_DAYS = 5                # rolling window...
GIFTS_PER_WINDOW = 2                # ...allowing this many gifts per receiver
GIFT_REPEAT_PENALTY = 5             # same gift two days in a row: -5 points

# --- Board tiers & dispatch scaling (M11; rescaled for M15 ranks) ---
# Team power = sum of the top-4 roster heroes' effective totals. On the M15
# scale: two starters at rank 1 = 37, a full 4-hero roster at rank 1 = 75,
# everyone at rank 10 = 299.
BOARD_TIER_POWER = {2: 90, 3: 160}  # team power to unlock board tier N
# M25: what a board job pays in XP, as a multiple of the passive
# "Attribute training" assignment (passive.json, 40 XP/day). A dispatched
# hero is off the team exactly like one on the mats, so that's the fair
# baseline — and board work is meant to stay the lesser XP route, because
# it also pays credits and sometimes bond. This is the job's TOTAL per
# day, divided across whatever attributes it trains.
PASSIVE_TRAIN_XP_PER_DAY = 40
BOARD_TIER_XP_MULT = {1: 0.5, 2: 1.0, 3: 1.5}


def board_tier_xp_per_day(tier):
    return PASSIVE_TRAIN_XP_PER_DAY * BOARD_TIER_XP_MULT[tier]
DISPATCH_POWER_BASELINE = 22        # avg sent-hero total paying 1.0x
DISPATCH_POWER_BONUS = 0.01         # pay multiplier step per point of avg power
DISPATCH_MULT_MIN = 0.8
DISPATCH_MULT_MAX = 1.5

# --- Attributes & Training (§6.3; XP economy reworked M16) ---
# Rank costs grow 1.5x per level: each rank is a real investment, but a
# hero can be mastered inside a campaign rather than a dozen issues.
# Keyed by the level you are training FROM (1 -> 2 costs 100).
XP_TO_NEXT_RANK = {1: 100, 2: 150, 3: 225, 4: 340, 5: 510,
                   6: 760, 7: 1140, 8: 1710, 9: 2560}
# Training with the grain is cheaper than fighting your own nature: the
# rank cost is scaled by BASE - STEP x boost, so a boost-7 attribute costs
# 0.8x and a boost-0 one costs 1.5x (boost 5 is the neutral point).
BOOST_XP_WEIGHT_BASE = 1.5
BOOST_XP_WEIGHT_STEP = 0.1
# What one rack session yields and how long the trainee is locked out,
# also keyed by the level being trained.
TRAINING_XP_BY_LEVEL = {1: 25, 2: 35, 3: 50, 4: 80, 5: 135,
                        6: 225, 7: 400, 8: 700, 9: 1200}
TRAINING_MINUTES_BY_LEVEL = {1: 50, 2: 70, 3: 100, 4: 160, 5: 270,
                             6: 450, 7: 800, 8: 1400, 9: 2400}
# Facility multipliers on the session yield (was flat 40/80/120).
TRAINING_XP_MULT_BASIC = 1
TRAINING_XP_MULT_UPGRADED = 2       # after the Ch.1 boss
TRAINING_XP_MULT_EVENT = 3          # during a training event
# Battle XP per enemy defeated, keyed by the enemy's level.
ENEMY_XP_BY_LEVEL = {1: 12, 2: 24, 3: 36, 4: 54, 5: 72,
                     6: 90, 7: 114, 8: 138, 9: 162, 10: 192}
PERK_CHOICE_RANKS = (3, 6)

# --- Combat formulas (§6.4) ---
HP_BASE = 50
HP_PER_STAMINA = 20
HP_PER_DURABILITY = 10
BATTLE_ENERGY_BASE = 20
BATTLE_ENERGY_PER_INT = 5
INITIATIVE_SPEED_MULT = 10
INITIATIVE_ROLL = (1, 6)            # rand(1, 6), recomputed each round
BASIC_SCALING_MULT = 4
SPECIAL_SCALING_MULT = 5
DURABILITY_REDUCTION_MULT = 2
MIN_DAMAGE = 1
CRIT_PCT_PER_AGILITY = 4
CRIT_MULTIPLIER = 1.5
DODGE_PCT_PER_AGILITY = 3
ULT_CHARGE_PER_TURN = 20
ULT_CHARGE_PER_HIT = 10
ULT_CHARGE_MAX = 100
DEFEND_DAMAGE_MULT = 0.5            # halve incoming damage until next turn
PARTY_SIZE_MAX = 4

# --- Status effects (§6.4) ---
BURN_DAMAGE_PER_TURN = 5
BURN_TURNS = 3
STUN_TURNS = 1

# --- Enemy AI (§6.5) ---
AI_DEFENSIVE_HP_THRESHOLD = 0.40    # defensive: start guarding below 40% HP
# ...but never twice running, and not at all once cornered (M23). Without
# these a wounded defensive enemy guarded every single turn forever.
AI_DEFENSIVE_LAST_STAND_HP = 0.15   # below this it stops guarding entirely
AI_SUPPORT_HP_THRESHOLD = 0.50     # support: heal/buff ally below 50% HP

# --- Save (§5.4) ---
# GAME_SAVE_DIR redirects the slots somewhere scratch. Any headless driver
# that boots a real App MUST set it: App.autosave() and go_to_sleep() write
# the live slot, so a verification script left pointed here will silently
# eat the player's game.
SAVE_DIR = os.environ.get("GAME_SAVE_DIR", "saves")
SAVE_SLOTS = 3

# --- General UI palette (era-inspired; hub/battle screens) ---
PALETTE = {
    "cream": "#F2E6C9",
    "red": "#C8102E",
    "gold": "#FFC72C",
    "navy": "#1B1F3B",
    "ink": "#121212",
}

# --- Impel card UI palette (§8) ---
# Sampled from real 1991 Impel Marvel Universe Series II card-back scans in
# assets/reference/ (cap_54_back.jpg, iron_man_13_back.jpg, hulk_53_back.jpg).
# The printed power-rating scale runs 0-7 -> RANK_MAX 7 segments per row.
CARD_PALETTE = {
    "cream": "#F0E8D8",         # card body / text panel
    "paper": "#F8E8D8",         # power-grid paper behind unfilled bars
    "yellow": "#F8D808",        # header banner + Real Name box
    "blue": "#0A10C8",          # block-letter name blue
    "bar_pink": "#E07098",      # printed power-rating bar fill
    "red": "#E80000",           # Did You Know strip / accents
    "ink": "#000000",           # text, POWER RATINGS band
    "gold": "#FFC72C",          # trained-rank overlay (game addition, not on card)
}
# §8 zones in internal-res px (halved from the 1280x720 spec values; same
# on-screen proportions after the 2x window scale).
CARD_MARGIN = 12
CARD_HEADER_HEIGHT = 32
CARD_PORTRAIT_SIZE = (150, 170)
CARD_GRID_ROW_HEIGHT = 22
