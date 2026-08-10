"""Tunable constants. Every number here is sourced from docs/GAME_SPEC.md §6/§8."""

# --- Display ---
WIDTH = 1280
HEIGHT = 720
FPS = 60
TITLE = "Marvel: Roads to Secret Wars — POC"

# --- Power grid (§6.3) ---
RANK_MAX = 7
ATTRIBUTES = ("strength", "speed", "agility", "stamina", "durability", "intelligence")

# --- Clock & Energy (§6.1) — times in in-game minutes since midnight ---
DAY_START_MINUTES = 6 * 60          # 6:00 AM
DAY_END_MINUTES = 26 * 60           # 2:00 AM next day
TICK_GAME_MINUTES = 10              # cosmetic tick: 10 in-game minutes...
TICK_REAL_SECONDS = 7               # ...per 7 real seconds
DAILY_ENERGY = 100
PASS_OUT_NEXT_DAY_ENERGY = 80

TRAINING_ENERGY = 25
TRAINING_MINUTES = 90
MISSION_ENERGY = 40
MISSION_MINUTES = 180
CRAFT_ENERGY = 15
CRAFT_MINUTES = 60
SMALL_TASK_ENERGY_MIN = 10
SMALL_TASK_ENERGY_MAX = 20
TALK_GIFT_MINUTES = 20              # talking/gifting costs time, no energy

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
GIFTS_PER_WEEK_MAX = 2
BOND_GATE_SCENE = 2                 # bond scene
BOND_GATE_RECRUIT = 4               # relationship recruit
BOND_GATE_SYNERGY = 6               # synergy passive
BOND_GATE_GEAR = 8                  # exclusive gear quest
BOND_GATE_SIGNATURE = 10            # signature scene + costume
BOND_PERSONAL_QUEST_MIN = 150       # personal quest reward range
BOND_PERSONAL_QUEST_MAX = 250

# --- Attributes & Training (§6.3) ---
ATTRIBUTE_XP_PER_RANK = 100         # XP to gain trained rank N = 100 * N
TRAINING_XP_BASIC = 40
TRAINING_XP_UPGRADED = 80
TRAINING_XP_EVENT = 120
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
AI_DEFENSIVE_HP_THRESHOLD = 0.40    # defensive: Defend below 40% HP
AI_SUPPORT_HP_THRESHOLD = 0.50     # support: heal/buff ally below 50% HP

# --- Save (§5.4) ---
SAVE_DIR = "saves"
SAVE_SLOTS = 3

# --- Impel card UI palette (§8) ---
# Placeholder era-inspired values. Replace by sampling real 1991 card-back
# scans dropped into assets/reference/ before/at M5.
PALETTE = {
    "cream": "#F2E6C9",
    "red": "#C8102E",
    "gold": "#FFC72C",
    "navy": "#1B1F3B",
    "ink": "#121212",
}
CARD_MARGIN = 24
CARD_HEADER_HEIGHT = 64
CARD_PORTRAIT_SIZE = (300, 340)
CARD_GRID_ROW_HEIGHT = 44
