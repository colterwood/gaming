"""Procedural pixel art (spec §9 M7): character portraits, item icons,
battle backdrop, tower tiles. Rendering only.

Portraits are hand-authored 20x20 pixel grids (see pixelkit.build_sprite);
icons and tiles are drawn with primitives so they stay palette-locked.
"""

import pygame

from game.ui import pixelkit

# Shared grid keymap: char -> palette color
KEY = {
    "r": "red", "R": "red_dark", "m": "maroon",
    "g": "gold", "G": "gold_dark", "y": "yellow",
    "b": "sky", "B": "blue", "D": "blue_dark",
    "s": "skin", "S": "skin_dark",
    "w": "white", "k": "ink", "K": "shadow",
    "e": "steel_light", "E": "steel", "F": "steel_dark",
    "n": "green", "N": "green_dark",
    "o": "grey", "O": "grey_dark",
    "p": "paper", "t": "tan", "u": "purple",
}

PORTRAITS = {
    "iron_man": [
        "....kkkkkkkkkkkk....",
        "..kkRRRRRRRRRRRRkk..",
        ".kRRrrrrrrrrrrrrRRk.",
        ".kRrrrrrrrrrrrrrrRk.",
        "kRrrrrrrrrrrrrrrrrRk",
        "kRrrkggggggggggkrrRk",
        "kRrrkggggggggggkrrRk",
        "kRrkggggggggggggkrRk",
        "kRrkgkkwwgggwwkkgkrRk"[:20],
        "kRrkgkwwwggwwwkggkrRk"[:20],
        "kRrkggggggggggggkrRk",
        "kRrkggggggggggggkrRk",
        "kRrkgggkkkkkkgggkrRk",
        "kRrrkggggggggggkrrRk",
        "kRrrkggkkkkkkggkrrRk",
        ".kRrrkggggggggkrrRk.",
        ".kRRrrkkkkkkkkrrRRk.",
        "..kkRRRRRRRRRRRRkk..",
        "...kkkRRRRRRRRkkk...",
        "....kkkkkkkkkkkk....",
    ],
    "captain_america": [
        "....kkkkkkkkkkkk....",
        "..kkBBBBBBBBBBBBkk..",
        ".kBBBBBBwwBBBBBBBBk.",
        ".kBBBBBwwwwBBBBBBBk.",
        "kBBBBBwwwwwwBBBBBBBk"[:20],
        "kBBBBBBwwBBBBBBBBBBk"[:20],
        "kBwBBBBBBBBBBBBBwBBk"[:20],
        "kBwwBBBBBBBBBBBwwBBk"[:20],
        "kBBBkkwwBBBBwwkkBBBk",
        "kBBBkwwwBBBBwwwkBBBk",
        "kBBBBBBBBBBBBBBBBBBk",
        "kBBBBBBBBssBBBBBBBBk",
        "kkBBBBBBssssBBBBBBkk",
        ".kkkkkksssssskkkkkk.",
        "..kssssssssssssssk..",
        "..ksssSSssssSSsssk..",
        "..kssssssssssssssk..",
        "..kSssskssssksssSk..",
        "...kssskkkkkksssk...",
        "....kkkkkkkkkkkk....",
    ],
    "ant_man": [
        "....kkkkkkkkkkkk....",
        "..kkEEEEEEEEEEEEkk..",
        ".kEEeeeeeeeeeeeeEEk.",
        ".kEeeeeeeeeeeeeeeEk.",
        "kEeeekrrrrrrrrkeeeEk",
        "kEeekrrrrrrrrrrkeeEk",
        "kEekrrkkrrrrkkrrkeEk",
        "kEekrkrrkrrkrrkrkeEk"[:20],
        "kEekrrkkrrrrkkrrkeEk",
        "kEeekrrrrrrrrrrkeeEk",
        "kEeeekrrrrrrrrkeeeEk",
        "kEeeeekkkkkkkkeeeeEk",
        "kEeeeeeeeeeeeeeeeeEk",
        "kEekeeeeeeeeeeeekeEk",
        "kEekkeeeeeeeeeekkeEk",
        ".kEekkeeeeeeeekkeEk.",
        ".kEEekkkkkkkkkkeEEk.",
        "..kkEEEEEEEEEEEEkk..",
        "...kkkEEEEEEEEkkk...",
        "....kkkkkkkkkkkk....",
    ],
    "hydra_grunt": [
        "....kkkkkkkkkkkk....",
        "..kkNNNNNNNNNNNNkk..",
        ".kNNnnnnnnnnnnnnNNk.",
        ".kNnnnnnnnnnnnnnnNk.",
        "kNnnnnnnnnnnnnnnnnNk",
        "kNnnnnnnnnnnnnnnnnNk",
        "kNnnkyyykNNkyyyknnNk",
        "kNnnkyyykNNkyyyknnNk"[:20],
        "kNnnnkkknnnnkkknnnNk",
        "kNnnnnnnnnnnnnnnnnNk",
        "kNnnnnnnnnnnnnnnnnNk",
        "kNnnnkkkkkkkkkknnnNk",
        "kNnnnknnnnnnnnknnnNk",
        "kNnnnnkkkkkkkknnnnNk",
        "kNnnnnnnnnnnnnnnnnNk",
        ".kNnnnnnnnnnnnnnNk..",
        ".kNNnnnnnnnnnnnNNk..",
        "..kkNNNNNNNNNNNNkk..",
        "...kkkNNNNNNNNkkk...",
        "....kkkkkkkkkkkk....",
    ],
    "crossbones": [
        "....kkkkkkkkkkkk....",
        "..kkKKKKKKKKKKKKkk..",
        ".kKKkkkkkkkkkkkkKKk.",
        ".kKkkkkkkkkkkkkkkKk.",
        "kKkkkwwwwkkwwwwkkkKk"[:20],
        "kKkkwwwwwwwwwwwwkkKk"[:20],
        "kKkkwwkkwwwwkkwwkkKk"[:20],
        "kKkkwwkkwwwwkkwwkkKk"[:20],
        "kKkkwwwwwkkwwwwwkkKk"[:20],
        "kKkkkwwwwwwwwwwkkkKk"[:20],
        "kKkkkkwwkwwkwwkkkkKk"[:20],
        "kKkkkkwkkwwkkwkkkkKk"[:20],
        "kKkkkkkkkkkkkkkkkkKk",
        "kKkkkkkkkkkkkkkkkkKk",
        "kKkkkkkkkkkkkkkkkkKk",
        ".kKkkkkkkkkkkkkkKk..",
        ".kKKkkkkkkkkkkkKKk..",
        "..kkKKKKKKKKKKKKkk..",
        "...kkkKKKKKKKKkkk...",
        "....kkkkkkkkkkkk....",
    ],
}
PORTRAITS["hulk"] = [
    "....kkkkkkkkkkkk....",
    "..kkKKKKKKKKKKKKkk..",
    ".kKKKKKKKKKKKKKKKKk.",
    ".kKKnnnnnnnnnnnnKKk.",
    "kKnnnnnnnnnnnnnnnnKk",
    "kKnnnnnnnnnnnnnnnnKk",
    "kKnnkknnnnnnnnkknnKk",
    "kKnnnnnnnnnnnnnnnnKk",
    "kNnnkkwnnnnnnwkknnNk"[:20],
    "kNnnnkkNnnnnNkknnnNk"[:20],
    "kNnnnnnnnnnnnnnnnnNk",
    "kNnnnnnNnnnnNnnnnnNk",
    "kNnnnnnnNNNNnnnnnnNk",
    "kNnnnnkkkkkkkknnnnNk",
    "kNnnnnnkkkkkknnnnnNk",
    ".kNnnnnnnnnnnnnnNk..",
    ".kNNnnnnnnnnnnnNNk..",
    "..kkNNNNNNNNNNNNkk..",
    "...kkkNNNNNNNNkkk...",
    "....kkkkkkkkkkkk....",
]
PORTRAITS["thor"] = [       # winged helm, blond mane, red cape
    "....kkkkkkkkkkkk....",
    "..kkEEEEEEEEEEEEkk..",
    ".keEEEEEEEEEEEEEEek.",
    "keeEEEEkyyyykEEEEeek",
    "keekEEEyyyyyyEEEkeek",
    "kkeekEyyyyyyyyEkeekk",
    ".kyyyyssssssssyyyyk.",
    ".kyyysskssskkssyyyk.",
    ".kyyyssssssssssyyyk.",
    ".kyyyssssykssssyyyk.",
    ".kyyyssskkkksssyyyk.",
    ".kyyyysssssssyyyyyk.",
    "..kyyyyyyyyyyyyyyk..",
    "..krryyyyyyyyyyrrk..",
    ".krrrreeeeeeeerrrrk.",
    ".krrreeeggggeeerrrk.",
    ".krrreeeggggeeerrrk.",
    "..krrreeeeeeeerrrk..",
    "...kkrrrrrrrrrrkk...",
    "....kkkkkkkkkkkk....",
]
PORTRAITS["_human"] = [     # template: h=hair, x=jacket, v=shirt
    "....kkkkkkkkkkkk....",
    "..kkhhhhhhhhhhhhkk..",
    ".khhhhhhhhhhhhhhhhk.",
    ".khhhhhhhhhhhhhhhhk.",
    "khhhhhhhhhhhhhhhhhhk",
    "khhsssssssssssssshhk",
    "khssssssssssssssssshk"[:20],
    "kssskksssssssskksssk",
    "kssskksssssssskksssk",
    "kssssssssssssssssssk",
    "ksssssssSSSSsssssssk",
    "kssssssssssssssssssk",
    "kkssssSSssssSSsssskk",
    ".kksssssssssssssskk.",
    "..kkssssssssssskk...",
    "..kxxkkssssskkxxk...",
    ".kxxxxkkkkkkxxxxxk..",
    ".kxxxxxvvvvxxxxxxk..",
    ".kxxxxvvvvvvxxxxxk..",
    "kkkkkkkkkkkkkkkkkkkk",
]
# Variants that reuse a base grid with color substitutions
_VARIANTS = {
    "hydra_enforcer": ("hydra_grunt", {"n": "steel_dark", "N": "ink", "y": "orange"}),
    "hydra_medic": ("hydra_grunt", {"y": "white"}),
    "hydra_siege_captain": ("hydra_grunt", {"y": "red", "n": "green_dark"}),
    "jarvis": ("_human", {"h": "grey", "x": "shadow", "v": "white"}),
    "pepper_potts": ("_human", {"h": "orange", "x": "steel_light", "v": "white"}),
    "coulson": ("_human", {"h": "wood_dark", "x": "steel_dark", "v": "white"}),
    "player": ("_human", {"h": "brown", "x": "navy", "v": "gold"}),
}

_portrait_cache = {}


def portrait(char_id, size=24):
    """24x24 framed portrait Surface (20x20 grid + panel frame)."""
    key = (char_id, size)
    if key in _portrait_cache:
        return _portrait_cache[key]
    if char_id in _VARIANTS:
        base, subs = _VARIANTS[char_id]
        keymap = dict(KEY)
        keymap.setdefault("h", "grey")
        keymap.setdefault("x", "steel_dark")
        keymap.setdefault("v", "white")
        keymap["h"] = subs.get("h", keymap["h"])
        for ch, color_name in subs.items():
            keymap[ch] = color_name
        grid = PORTRAITS[base]
    else:
        keymap = dict(KEY)
        grid = PORTRAITS.get(char_id)
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.rect(surf, pixelkit.color("shadow"), pygame.Rect(0, 0, size, size))
    pygame.draw.rect(surf, pixelkit.color("ink"), pygame.Rect(0, 0, size, size), 1)
    if grid:
        sprite = pixelkit.build_sprite(grid, keymap)
        surf.blit(sprite, ((size - sprite.get_width()) // 2,
                           (size - sprite.get_height()) // 2))
    else:   # unknown character: silhouette
        pygame.draw.circle(surf, pixelkit.color("grey_dark"), (size // 2, size // 2 - 3), 5)
        pygame.draw.ellipse(surf, pixelkit.color("grey_dark"),
                            pygame.Rect(size // 2 - 8, size // 2 + 2, 16, 9))
    _portrait_cache[key] = surf
    return surf


# --- item icons: primitive-drawn 12x12, palette-locked ---

_icon_cache = {}


def _icon_surface():
    return pygame.Surface((12, 12), pygame.SRCALPHA)


def _draw_icon(surf, item_id):
    c = pixelkit.color
    r = pygame.Rect
    if item_id == "double_espresso":
        pygame.draw.rect(surf, c("white"), r(2, 4, 7, 6))
        pygame.draw.rect(surf, c("brown"), r(3, 5, 5, 3))
        pygame.draw.rect(surf, c("white"), r(9, 5, 2, 3), 1)
    elif item_id == "rare_alloy":
        pygame.draw.polygon(surf, c("steel_light"), [(2, 9), (5, 3), (10, 9)])
        pygame.draw.line(surf, c("white"), (5, 4), (4, 7))
    elif item_id == "tech_scrap":
        pygame.draw.circle(surf, c("steel"), (6, 6), 4, 2)
        pygame.draw.rect(surf, c("steel_light"), r(5, 5, 3, 3))
    elif item_id == "vintage_vinyl":
        pygame.draw.circle(surf, c("ink"), (6, 6), 5)
        pygame.draw.circle(surf, c("red"), (6, 6), 2)
        surf.set_at((6, 6), c("white"))
    elif item_id == "magnets":
        pygame.draw.rect(surf, c("red"), r(3, 2, 3, 7))
        pygame.draw.rect(surf, c("sky"), r(7, 2, 3, 7))
        pygame.draw.rect(surf, c("steel_light"), r(3, 8, 7, 2))
    elif item_id == "paperwork":
        pygame.draw.rect(surf, c("paper"), r(2, 2, 7, 9))
        for y in (4, 6, 8):
            pygame.draw.line(surf, c("grey"), (3, y), (7, y))
    elif item_id == "forties_memorabilia":
        pygame.draw.circle(surf, c("red"), (6, 6), 5)
        pygame.draw.circle(surf, c("white"), (6, 6), 3)
        pygame.draw.circle(surf, c("sky"), (6, 6), 1)
    elif item_id == "war_bonds_poster":
        pygame.draw.rect(surf, c("cream"), r(2, 1, 8, 10))
        pygame.draw.rect(surf, c("red"), r(3, 2, 6, 3))
        pygame.draw.rect(surf, c("sky"), r(3, 6, 6, 3))
    elif item_id == "sketchbook":
        pygame.draw.rect(surf, c("tan"), r(2, 2, 8, 9))
        pygame.draw.line(surf, c("brown"), (4, 2), (4, 10))
        pygame.draw.line(surf, c("grey_dark"), (6, 5, ), (8, 7))
    elif item_id == "modern_slang_guide":
        pygame.draw.rect(surf, c("purple"), r(2, 2, 8, 9))
        pygame.draw.rect(surf, c("white"), r(4, 4, 4, 2))
    elif item_id == "hydra_propaganda":
        pygame.draw.rect(surf, c("paper"), r(2, 2, 8, 9))
        pygame.draw.circle(surf, c("green"), (6, 6), 2)
    elif item_id == "ant_farm":
        pygame.draw.rect(surf, c("sky"), r(1, 3, 10, 7))
        pygame.draw.rect(surf, c("tan"), r(2, 6, 8, 3))
        for x in (3, 6, 8):
            surf.set_at((x, 7), c("ink"))
    elif item_id == "magic_trick_kit":
        pygame.draw.rect(surf, c("ink"), r(3, 4, 6, 6))
        pygame.draw.rect(surf, c("ink"), r(1, 9, 10, 2))
        pygame.draw.rect(surf, c("red"), r(3, 8, 6, 1))
    elif item_id == "bug_spray":
        pygame.draw.rect(surf, c("green"), r(4, 4, 4, 7))
        pygame.draw.rect(surf, c("grey"), r(4, 2, 3, 2))
        surf.set_at((9, 3), c("mint"))
    elif item_id == "med_kit":
        pygame.draw.rect(surf, c("white"), r(1, 3, 10, 8))
        pygame.draw.rect(surf, c("red"), r(5, 4, 2, 6))
        pygame.draw.rect(surf, c("red"), r(3, 6, 6, 2))
    elif item_id == "stormbreaker":
        pygame.draw.rect(surf, c("wood_dark"), r(5, 2, 2, 9))
        pygame.draw.polygon(surf, c("steel_light"),
                            [(1, 1), (6, 2), (6, 7), (1, 6)])
        pygame.draw.polygon(surf, c("steel"), [(6, 2), (9, 3), (9, 6), (6, 7)])
        pygame.draw.line(surf, c("sky"), (9, 1), (11, 4))
    elif item_id == "energy_bar":
        pygame.draw.rect(surf, c("gold"), r(1, 4, 10, 5))
        pygame.draw.line(surf, c("gold_dark"), (4, 4), (4, 8))
        pygame.draw.line(surf, c("gold_dark"), (7, 4), (7, 8))
    else:
        pygame.draw.rect(surf, c("grey"), r(2, 2, 8, 8), 1)
        pygame.draw.line(surf, c("grey"), (4, 6), (8, 6))


def icon(item_id):
    if item_id not in _icon_cache:
        surf = _icon_surface()
        _draw_icon(surf, item_id)
        _icon_cache[item_id] = surf
    return _icon_cache[item_id]


# --- Avengers pip: the bond-level marker on the card's Social tab (M20) ---

# Ringed "A" with the right stroke carried up through the ring as the
# arrow. 'o' = ring, 'a' = the letter — both drawn in the same colour, so
# a pip is either lit or dark.
AVENGERS_PIP = [
    "...ooooo...",
    ".oo.....oo.",
    ".o...a...o.",
    "o...a.a...o",
    "o..a...a..o",
    "o..aaaaa..o",
    "o.a.....a.o",
    ".oa.....ao.",
    ".oo.....oo.",
    "...ooooo...",
]

_pip_cache = {}


def avengers_pip(lit=True):
    """One bond level: lit blue when earned, dark grey when not."""
    if lit not in _pip_cache:
        keymap = {"o": "blue" if lit else "grey_dark",
                  "a": "sky" if lit else "grey_dark"}
        _pip_cache[lit] = pixelkit.build_sprite(AVENGERS_PIP, keymap)
    return _pip_cache[lit]


# --- standing sprites (12x16) for the walkable tower (§9 M8) ---

STANDING = {
    "player": [     # S.H.I.E.L.D. coordinator — the "you" avatar
        "...kkkkkk...",
        "..kssssssk..",
        "..kssksskk..",
        "..kssssssk..",
        "...kssssk...",
        "..kFFFFFFk..",
        ".kFFFFFFFFk.",
        ".kFsFFFFsFk.",
        ".kFFFgFFFFk.",
        ".kFFFFFFFFk.",
        "..kFFFFFFk..",
        "..kFFkkFFk..",
        "..kFFk.kFFk."[:12],
        "..kFFk.kFFk."[:12],
        "..kkk..kkk..",
        "............",
    ],
    "iron_man": [
        "...kkkkkk...",
        "..krrrrrrk..",
        "..krkggkrk..",
        "..krggggrk..",
        "...krrrrk...",
        "..krrrrrrk..",
        ".krrgggrrrk.",
        ".krrgwggrrk.",
        ".krrgggrrrk.",
        ".krrrrrrrrk.",
        "..krrrrrrk..",
        "..krrkkrrk..",
        "..krrk.krrk."[:12],
        "..kggk.kggk."[:12],
        "..kkk..kkk..",
        "............",
    ],
    "captain_america": [
        "...kkkkkk...",
        "..kBBBBBBk..",
        "..kBwkkwBk..",
        "..kBssssBk..",
        "...kssssk...",
        "..kBBBBBBk..",
        ".kBBwBBwBBk.",
        ".kBBBwwBBBk.",
        ".krwrwwrwrk.",
        ".krwrrrrwrk.",
        "..kBBBBBBk..",
        "..kBBkkBBk..",
        "..kBBk.kBBk."[:12],
        "..krrk.krrk."[:12],
        "..kkk..kkk..",
        "............",
    ],
    "ant_man": [
        "...kkkkkk...",
        "..keeeeeek..",
        "..kekrrkek..",
        "..kerrrrek..",
        "...keeeek...",
        "..krrrrrrk..",
        ".krreeeerrk.",
        ".krrekkerrk.",
        ".krreeeerrk.",
        ".krrrrrrrrk.",
        "..krrrrrrk..",
        "..krrkkrrk..",
        "..krrk.krrk."[:12],
        "..keek.keek."[:12],
        "..kkk..kkk..",
        "............",
    ],
}

STANDING["hulk"] = [
    "..kkkkkkkk..",
    ".kKnnnnnnKk.",
    ".knnkknnkkk."[:12],
    ".knnnnnnnnk.",
    "..knnnnnnk..",
    ".knnnnnnnnk.",
    "knnknnnnknnk",
    "knnknnnnknnk",
    "knnknnnnknnk",
    ".kkkuuuukkk.",
    "..kuuuuuuk..",
    "..kuukkuuk..",
    "..kuuk.kuuk."[:12],
    "..kuuk.kuuk."[:12],
    "..knnk.knnk."[:12],
    "..kkk..kkk..",
]
STANDING["thor"] = [        # winged helm, blond mane, blue tunic, red cape
    "...kkkkkk...",         # (the cape is what tells him apart from Ant-Man
    "..kekeekek..",         #  at a glance — never give him a red torso)
    "..keeeeeek..",
    "..kyssssyk..",
    "...kssssk...",
    "krrkBBBBkrrk",
    "krrkBeeBkrrk",
    "krrkBeeBkrrk",
    "krrkBBBBkrrk",
    ".krBBBBBBrk.",
    "..kBBBBBBk..",
    "..kBBkkBBk..",
    "..kBBk.kBBk."[:12],
    "..keek.keek."[:12],
    "..kkk..kkk..",
    "............",
]
STANDING["_human"] = [      # template: h=hair, x=jacket, v=shirt
    "...kkkkkk...",
    "..khhhhhhk..",
    "..ksskkssk"[:12] + "..",
    "..kssssssk..",
    "...kssssk...",
    "..kxxxxxxk..",
    ".kxxvvvvxxk.",
    ".kxsvvvvsxk.",
    ".kxxvvvvxxk.",
    ".kxxxxxxxxk.",
    "..kxxxxxxk..",
    "..kxxkkxxk..",
    "..kxxk.kxxk."[:12],
    "..kxxk.kxxk."[:12],
    "..kkk..kkk..",
    "............",
]
STANDING["hydra_squad"] = [
    "...kkkkkk...",
    "..knnnnnnk..",
    "..knkyyknk..",
    "..knnnnnnk..",
    "...knnnnk...",
    "..knnnnnnk..",
    ".knnkNNknnk.",
    ".knnkNNknnk.",
    ".knnnnnnnnk.",
    ".knnnnnnnnk.",
    "..knnnnnnk..",
    "..knnkknnk..",
    "..knnk.knnk."[:12],
    "..kNNk.kNNk."[:12],
    "..kkk..kkk..",
    "............",
]
_STAND_VARIANTS = {
    "jarvis": {"h": "grey", "x": "shadow", "v": "white"},
    "pepper_potts": {"h": "orange", "x": "steel_light", "v": "white"},
    "coulson": {"h": "wood_dark", "x": "steel_dark", "v": "white"},
}

_standing_cache = {}


def standing(char_id, flip=False):
    key = (char_id, flip)
    if key not in _standing_cache:
        if char_id in _STAND_VARIANTS:
            grid = STANDING["_human"]
            keymap = dict(KEY)
            keymap.update(_STAND_VARIANTS[char_id])
            for ch, color_name in _STAND_VARIANTS[char_id].items():
                keymap[ch] = color_name
        else:
            grid = STANDING.get(char_id, STANDING["player"])
            keymap = dict(KEY)
            keymap.setdefault("h", "brown")
            keymap.setdefault("x", "navy")
            keymap.setdefault("v", "gold")
        surf = pixelkit.build_sprite(grid, keymap)
        if flip:
            surf = pygame.transform.flip(surf, True, False)
        _standing_cache[key] = surf
    return _standing_cache[key]


# --- tower tileset: 16x16, primitive-drawn (§9 M8) ---

TILE = 16
_tile_cache = {}


def _make_tile(name):
    c = pixelkit.color
    r = pygame.Rect
    surf = pygame.Surface((TILE, TILE))
    if name == "floor":
        surf.fill(c("steel_dark"))
        pygame.draw.line(surf, c("navy"), (0, 15), (15, 15))
        pygame.draw.line(surf, c("navy"), (15, 0), (15, 15))
        surf.set_at((4, 4), c("steel"))
        surf.set_at((11, 11), c("steel"))
    elif name == "carpet":
        surf.fill(c("maroon"))
        pygame.draw.line(surf, c("red_dark"), (0, 15), (15, 15))
        pygame.draw.line(surf, c("red_dark"), (15, 0), (15, 15))
        for x, y in ((4, 4), (11, 11)):
            surf.set_at((x, y), c("gold_dark"))
    elif name == "mat":
        surf.fill(c("blue_dark"))
        pygame.draw.rect(surf, c("navy"), r(1, 1, 14, 14), 1)
    elif name == "wall":
        surf.fill(c("shadow"))
        pygame.draw.line(surf, c("steel_dark"), (0, 4), (15, 4))
        pygame.draw.line(surf, c("steel_dark"), (0, 12), (15, 12))
        pygame.draw.line(surf, c("ink"), (0, 15), (15, 15))
    elif name == "window":
        surf.fill(c("shadow"))
        pygame.draw.rect(surf, c("navy"), r(2, 2, 12, 11))
        for i, (x, y) in enumerate(((4, 4), (9, 3), (12, 6), (6, 8))):
            surf.set_at((x, y), c("white" if i % 2 else "steel_light"))
        pygame.draw.rect(surf, c("yellow"), r(3, 9, 2, 3))
        pygame.draw.rect(surf, c("yellow"), r(10, 10, 2, 2))
        pygame.draw.rect(surf, c("steel"), r(2, 2, 12, 11), 1)
    elif name == "elevator":
        surf.fill(c("shadow"))
        pygame.draw.rect(surf, c("steel"), r(2, 1, 12, 14))
        pygame.draw.line(surf, c("ink"), (8, 1), (8, 14))
        pygame.draw.rect(surf, c("gold"), r(3, 0, 10, 2))
    elif name == "counter":
        surf.fill(c("wood_dark"))
        pygame.draw.rect(surf, c("wood"), r(0, 0, 16, 6))
        pygame.draw.line(surf, c("brown"), (0, 6), (15, 6))
        pygame.draw.rect(surf, c("tan"), r(2, 8, 4, 3))
    elif name == "board":
        surf.fill(c("shadow"))
        pygame.draw.rect(surf, c("wood_dark"), r(1, 1, 14, 12))
        pygame.draw.rect(surf, c("tan"), r(2, 2, 12, 10))
        pygame.draw.rect(surf, c("paper"), r(3, 3, 4, 4))
        pygame.draw.rect(surf, c("yellow"), r(9, 4, 4, 3))
        pygame.draw.rect(surf, c("paper"), r(5, 8, 4, 3))
    elif name == "console":
        surf.fill(c("shadow"))
        pygame.draw.rect(surf, c("steel_dark"), r(1, 4, 14, 11))
        pygame.draw.rect(surf, c("sky"), r(2, 5, 12, 6))
        pygame.draw.line(surf, c("white"), (3, 7), (8, 7))
        pygame.draw.line(surf, c("mint"), (3, 9), (11, 9))
        for x in (3, 6, 9, 12):
            surf.set_at((x, 13), c("gold"))
    elif name == "bed":
        surf.fill(c("steel_dark"))
        pygame.draw.rect(surf, c("brown"), r(1, 1, 14, 14))
        pygame.draw.rect(surf, c("red"), r(2, 5, 12, 9))
        pygame.draw.rect(surf, c("white"), r(2, 2, 12, 4))
    elif name == "couch":
        surf.fill(c("steel_dark"))
        pygame.draw.rect(surf, c("red_dark"), r(1, 4, 14, 10))
        pygame.draw.rect(surf, c("red"), r(2, 7, 12, 6))
        pygame.draw.rect(surf, c("red_dark"), r(0, 2, 3, 12))
        pygame.draw.rect(surf, c("red_dark"), r(13, 2, 3, 12))
    elif name == "plant":
        surf.fill(c("steel_dark"))
        pygame.draw.rect(surf, c("steel"), r(1, 1, 14, 14), 1)
        pygame.draw.rect(surf, c("wood_dark"), r(5, 10, 6, 5))
        pygame.draw.circle(surf, c("green"), (8, 6), 4)
        pygame.draw.circle(surf, c("green_dark"), (5, 8), 2)
        pygame.draw.circle(surf, c("mint"), (10, 4), 2)
    elif name == "table":
        surf.fill(c("steel_dark"))
        pygame.draw.rect(surf, c("steel"), r(1, 1, 14, 14), 1)
        pygame.draw.rect(surf, c("wood"), r(2, 4, 12, 8))
        pygame.draw.rect(surf, c("wood_dark"), r(2, 10, 12, 2))
    elif name == "road":
        surf.fill(c("shadow"))
        pygame.draw.line(surf, c("grey_dark"), (0, 0), (15, 0))
        for x in range(1, 16, 5):
            pygame.draw.line(surf, c("gold_dark"), (x, 8), (x + 2, 8))
    elif name == "sidewalk":
        surf.fill(c("grey_dark"))
        pygame.draw.line(surf, c("shadow"), (0, 15), (15, 15))
        pygame.draw.line(surf, c("shadow"), (15, 0), (15, 15))
        surf.set_at((5, 6), c("grey"))
        surf.set_at((11, 12), c("grey"))
    elif name == "crate":
        surf.fill(c("grey_dark"))
        pygame.draw.rect(surf, c("wood"), r(1, 2, 14, 13))
        pygame.draw.rect(surf, c("wood_dark"), r(1, 2, 14, 13), 1)
        pygame.draw.line(surf, c("wood_dark"), (1, 8), (14, 8))
        pygame.draw.line(surf, c("wood_dark"), (8, 2), (8, 14))
    elif name == "helipad":
        surf.fill(c("shadow"))
        pygame.draw.circle(surf, c("gold"), (8, 8), 7, 1)
        pygame.draw.line(surf, c("gold"), (5, 4), (5, 12), 2)
        pygame.draw.line(surf, c("gold"), (10, 4), (10, 12), 2)
        pygame.draw.line(surf, c("gold"), (5, 8), (10, 8), 2)
    elif name == "tree":
        surf.fill(c("grey_dark"))
        pygame.draw.rect(surf, c("wood_dark"), r(7, 9, 3, 6))
        pygame.draw.circle(surf, c("green_dark"), (8, 6), 6)
        pygame.draw.circle(surf, c("green"), (6, 4), 3)
        pygame.draw.circle(surf, c("mint"), (10, 3), 2)
    elif name == "rack":
        surf.fill(c("steel_dark"))
        pygame.draw.rect(surf, c("steel"), r(1, 1, 14, 14), 1)
        pygame.draw.line(surf, c("grey"), (3, 4), (13, 4), 2)
        pygame.draw.line(surf, c("grey"), (3, 9), (13, 9), 2)
        for x in (3, 12):
            pygame.draw.rect(surf, c("ink"), r(x, 2, 2, 5))
            pygame.draw.rect(surf, c("ink"), r(x, 7, 2, 5))
    else:
        surf.fill(c("purple"))
    return surf


def tile(name):
    if name not in _tile_cache:
        _tile_cache[name] = _make_tile(name)
    return _tile_cache[name]


# --- battle backdrop: night city skyline ---

_backdrop = None


def battle_backdrop(width, height):
    global _backdrop
    if _backdrop and _backdrop.get_size() == (width, height):
        return _backdrop
    surf = pygame.Surface((width, height))
    surf.fill(pixelkit.color("navy"))
    for i in range(70):     # stars
        x = (i * 89 + 17) % width
        y = (i * 53 + 7) % (height // 2)
        surf.set_at((x, y), pixelkit.color("steel_light" if i % 5 else "white"))
    ground = height - 40
    # far skyline
    x = 0
    i = 0
    while x < width:
        w = 24 + (i * 37) % 30
        h = 60 + (i * 53) % 80
        pygame.draw.rect(surf, pixelkit.color("shadow"),
                         pygame.Rect(x, ground - h, w, h))
        x += w + 4
        i += 1
    # near skyline with lit windows
    x = -8
    i = 0
    while x < width:
        w = 34 + (i * 41) % 36
        h = 100 + (i * 71) % 110
        rect = pygame.Rect(x, ground - h, w, h)
        pygame.draw.rect(surf, pixelkit.color("steel_dark"), rect)
        pygame.draw.rect(surf, pixelkit.color("ink"), rect, 1)
        for wy in range(rect.y + 6, rect.bottom - 4, 8):
            for wx in range(rect.x + 4, rect.right - 4, 7):
                if (wx * 7 + wy * 13 + i) % 3:
                    pygame.draw.rect(surf, pixelkit.color("yellow"),
                                     pygame.Rect(wx, wy, 2, 3))
        x += w + 6
        i += 1
    pygame.draw.rect(surf, pixelkit.color("ink"),
                     pygame.Rect(0, ground, width, height - ground))
    pygame.draw.line(surf, pixelkit.color("steel_dark"), (0, ground), (width, ground))
    _backdrop = surf
    return surf
