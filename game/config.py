"""Tunable constants. Every number here is sourced from docs/GAME_SPEC.md §6/§8."""

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

# Training costs scale with the rank being trained (M9): rank 2 matches the
# original §6.1 flat costs (25 EN / 90 min).
TRAINING_ENERGY_BASE = 15
TRAINING_ENERGY_PER_RANK = 5
TRAINING_MINUTES_BASE = 60
TRAINING_MINUTES_PER_RANK = 15
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

ATROPHY_GRACE_DAYS = 2              # same-spot days before decay starts
ATROPHY_XP_PER_DAY = 20             # XP drained per unworked attribute

MISSION_FAIL_COOLDOWN_DAYS = 2
TRAVEL_MINUTES = 30                 # Quinjet hop tower <-> zone

# --- Field life (M10) ---
EAT_MINUTES = 10                    # eating a ration advances the clock
SEARCH_MINUTES = 15                 # rummaging a crate/dumpster
SEARCH_TRAP_CHANCE = 0.07           # per search, scaled by zone danger

# --- Board tiers & dispatch scaling (M11) ---
# Team power = sum of the top-4 roster heroes' effective grid totals
# (start: Iron Man 29 + Cap 18 = 47; max 42 per hero).
BOARD_TIER_POWER = {2: 70, 3: 110}  # team power to unlock board tier N
DISPATCH_POWER_BASELINE = 24        # avg sent-hero grid total paying 1.0x
DISPATCH_POWER_BONUS = 0.02         # pay multiplier step per point of avg power
DISPATCH_MULT_MIN = 0.8
DISPATCH_MULT_MAX = 1.5

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
