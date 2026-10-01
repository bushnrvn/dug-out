#!/usr/bin/env python3
"""
Dug Out asset generator.

Everything visual in the game is authored here (as code + ASCII pixel art) and
quantized to the real GameTank palette, so the look is fully reproducible.

Outputs
  assets/bg/bg.bmp        128x128 : baked dirt field, depth gauges
  assets/spr/spr.bmp      128x128 : all sprites, tunnel autotiles, font, logo
  src/gen_art.h           C header with sprite coordinates + palette constants
  tools_py/preview_*.png  scaled previews for eyeballing
"""
import json, math, os, struct, zlib, random

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
PAL = [tuple(c) for c in json.load(open(os.path.join(ROOT, 'tools_py', 'palette.json')))]

# ---------------------------------------------------------------- palette --
_cache = {}
def pc(rgb, allow_zero=False):
    """nearest GameTank palette index for an RGB colour (0 reserved = transparent)"""
    key = (rgb, allow_zero)
    if key in _cache:
        return _cache[key]
    best, bi = 1e9, 1
    for i, p in enumerate(PAL):
        if i == 0 and not allow_zero:
            continue
        d = (0.30 * (p[0]-rgb[0])**2 + 0.59 * (p[1]-rgb[1])**2 + 0.11 * (p[2]-rgb[2])**2)
        if d < best:
            best, bi = d, i
    _cache[key] = bi
    return bi

# The "Strata" palette: warm earth bands that cool with depth, luminous cool voids.
C = dict(
    ink      = (26, 22, 64),      # outline / deep navy
    void     = (26, 30, 70),      # tunnel interior
    voidhi   = (49, 53, 100),     # tunnel interior lighter (gradient)
    rim      = (137, 198, 184),   # lit tunnel edge (mint glow)
    rimlo    = (49, 100, 96),     # secondary rim
    sky0     = (150, 189, 240),
    sky1     = (112, 168, 244),
    sky2     = (167, 188, 210),
    hill     = (65, 122, 198),
    sun      = (237, 178, 98),
    grass    = (88, 162, 57),
    grass_d  = (44, 117, 11),
    b1a=(191, 134, 53), b1b=(146, 89, 9), b1c=(224, 176, 96),     # clay
    b2a=(160, 64, 80),  b2b=(119, 58, 71),  b2c=(187, 125, 139),  # rust plum
    b3a=(110, 64, 130), b3b=(85, 33, 105),  b3c=(153, 101, 172),  # violet
    b4a=(60, 60, 130),  b4b=(27, 15, 143),  b4c=(94, 86, 172),    # indigo
    gem      = (135, 192, 255),
    hat      = (185, 197, 65),
    hat_d    = (140, 152, 20),
    lamp     = (185, 185, 185),
    skin     = (203, 183, 159),
    suit     = (214, 155, 75),
    suit_d   = (167, 110, 30),
    boot     = (99, 42, 0),
    grub     = (234, 140, 162),
    grub_d   = (188, 95, 116),
    grub_l   = (255, 190, 200),
    ember    = (237, 178, 98),
    ember_d  = (167, 110, 30),
    ember_r  = (200, 70, 40),
    bone     = (203, 183, 159),
    bone_d   = (134, 114, 89),
    bone_l   = (232, 220, 200),
    white    = (185, 185, 185),
    hose     = (161, 191, 182),
    hose_d   = (70, 100, 93),
    cream    = (220, 181, 127),
    gold     = (237, 178, 98),
    txt_sh   = (26, 22, 64),
    cap      = (60, 60, 130),
    cap_d    = (27, 15, 143),
    brim     = (200, 60, 40),
    jersey   = (185, 185, 185),
    pin      = (94, 86, 172),
    sock     = (200, 60, 40),
    seam     = (200, 50, 50),
    vskin    = (172, 150, 200),
    vskin_d  = (118, 96, 150),
    uni      = (132, 132, 152),
    vred     = (230, 40, 60),
    gskin    = (140, 178, 92),
    gskin_d  = (86, 124, 62),
    ball     = (185, 185, 185),
    ball_d   = (116, 116, 116),
    flame1   = (237, 205, 130),
    flame2   = (232, 130, 40),
    flame3   = (200, 60, 40),
)
P = {k: pc(v) for k, v in C.items()}

# ------------------------------------------------------------- canvas util --
class Sheet:
    def __init__(self, w=128, h=128):
        self.w, self.h = w, h
        self.px = [[0]*w for _ in range(h)]
        self.cx = self.cy = self.rowh = 0
        self.names = {}

    def put(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.px[y][x] = c

    def alloc(self, w, h, name=None):
        if self.cx + w > self.w:
            self.cx, self.cy, self.rowh = 0, self.cy + self.rowh, 0
        if self.cy + h > self.h:
            raise RuntimeError('sheet full placing %s' % name)
        x, y = self.cx, self.cy
        self.cx += w
        self.rowh = max(self.rowh, h)
        if name:
            self.names[name] = (x, y, w, h)
        return x, y

    def blit_grid(self, grid, legend, name=None, flip=False):
        h, w = len(grid), len(grid[0])
        x, y = self.alloc(w, h, name)
        for j, row in enumerate(grid):
            assert len(row) == w, (name, j, row)
            if flip:
                row = row[::-1]
            for i, ch in enumerate(row):
                if ch != '.':
                    self.put(x + i, y + j, legend[ch])
        return x, y

    def save_bmp(self, path):
        W, H = self.w, self.h
        pal = b''.join(bytes([c[2], c[1], c[0], 0]) for c in PAL)
        rows = b''.join(bytes(self.px[y]) for y in range(H-1, -1, -1))
        hdr = struct.pack('<2sIHHI', b'BM', 14+40+1024+len(rows), 0, 0, 14+40+1024)
        dib = struct.pack('<IiiHHIIiiII', 40, W, H, 1, 8, 0, len(rows), 2835, 2835, 256, 256)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, 'wb').write(hdr + dib + pal + rows)

def png(path, pixels, scale=4):
    h, w = len(pixels), len(pixels[0])
    raw = bytearray()
    for y in range(h):
        line = bytearray()
        for x in range(w):
            r, g, b = PAL[pixels[y][x]]
            line += bytes([r, g, b]) * scale
        for _ in range(scale):
            raw += b'\x00' + line
    def chunk(t, d):
        c = struct.pack('>I', len(d)) + t + d
        return c + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    data = (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w*scale, h*scale, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(bytes(raw), 9)) + chunk(b'IEND', b''))
    open(path, 'wb').write(data)

# ================================================================ SPRITES ===
spr = Sheet()
NAMES = {}

DOUG_L = dict(k=P['ink'], c=P['cap'], C=P['cap_d'], r=P['brim'], s=P['skin'], e=P['ink'],
              w=P['jersey'], p=P['pin'], b=P['sock'], x=P['ink'], h=P['cap'], H=P['cap_d'],
              o=P['jersey'], O=P['pin'])
DOUG_R0 = [
    "..kkkk..",
    ".kccccr.",
    ".kCCCCrr",
    "..kssek.",
    "..ksssk.",
    ".kwpwpwk",
    ".kwwwwk.",
    "..kb.bk.",
]
DOUG_R1 = [
    "..kkkk..",
    ".kccccr.",
    ".kCCCCrr",
    "..kssek.",
    "..ksssk.",
    ".kwpwpwk",
    ".kwwwwk.",
    "...kbbk.",
]
DOUG_D0 = [
    "..kkkk..",
    ".kccccck",
    ".krrrrrk",
    ".ksesesk",
    ".kssssk.",
    "kwpwwpwk",
    ".kwwwwk.",
    "..kb.bk.",
]
DOUG_D1 = [
    "..kkkk..",
    ".kccccck",
    ".krrrrrk",
    ".ksesesk",
    ".kssssk.",
    "kwpwwpwk",
    ".kwwwwk.",
    "...kbbk.",
]
DOUG_U0 = [
    "..kkkk..",
    ".kcccccC",
    ".kcccccC",
    ".kCCCCCk",
    ".kwpwwpk",
    "kwwppwwk",
    ".kwwwwk.",
    "..kb.bk.",
]
DOUG_U1 = [
    "..kkkk..",
    ".kcccccC",
    ".kcccccC",
    ".kCCCCCk",
    ".kwpwwpk",
    "kwwppwwk",
    ".kwwwwk.",
    "...kbbk.",
]
DOUG_X0 = [
    "........",
    "..kkkk..",
    ".kccccrk",
    ".kCCCCCk",
    "kssxssxk",
    "kwpwwpwk",
    ".kbkkbk.",
    "........",
]
DOUG_X1 = [
    "........",
    "........",
    "..kkkk..",
    ".kccccck",
    "kCCCCCCk",
    "kwpwwpwk",
    "kbbkkbbk",
    "........",
]
DOUG_L2 = dict(DOUG_L)

# index by dir: 0=R 1=L 2=U 3=D ; frame 0/1
doug_frames = {}
for d, (g0, g1, flip) in enumerate([(DOUG_R0, DOUG_R1, False), (DOUG_R0, DOUG_R1, True),
                                    (DOUG_U0, DOUG_U1, False), (DOUG_D0, DOUG_D1, False)]):
    for f, g in enumerate((g0, g1)):
        doug_frames[(d, f)] = spr.blit_grid(g, DOUG_L, 'doug_%d_%d' % (d, f), flip=flip)
doug_dead = [spr.blit_grid(DOUG_X0, DOUG_L2, 'doug_x0'), spr.blit_grid(DOUG_X1, DOUG_L2, 'doug_x1')]

GRUB_L = dict(k=P['ink'], K=P['uni'], v=P['vskin'], R=P['vred'], f=P['white'], r=P['vred'], w=P['white'])
GRUB_R0 = [
    "..kkkk..",
    ".kKKKKk.",
    ".kKKKKkk",
    "..kvvRk.",
    "..kvfvk.",
    ".krwwwrk",
    ".kKKKKk.",
    "..kk.kk.",
]
GRUB_R1 = [
    "..kkkk..",
    ".kKKKKk.",
    ".kKKKKkk",
    "..kvvRk.",
    "..kvfvk.",
    ".krwwwrk",
    ".kKKKKk.",
    ".kk..kk.",
]

EMB_L = dict(k=P['ink'], P=P['ember'], m=P['ember_d'], w=P['white'], p=P['ink'], r=P['ember_r'], l=P['flame1'], y=P['flame2'])
EMB_R0 = [
    "..l.l...",
    ".lylyl..",
    ".kPPPPk.",
    "kPPPkkPk",
    "kPrPwpPk",
    "kPPrPPPk",
    ".kPPPPk.",
    "..kk.kk.",
]
EMB_R1 = [
    "...l.l..",
    ".lylyl..",
    ".kPPPPk.",
    "kPPPkkPk",
    "kPrPwpPk",
    "kPPrPPPk",
    ".kPPPPk.",
    ".kk..kk.",
]
grub_frames = {}
emb_frames = {}
for d, flip in ((0, False), (1, True)):
    for f, (g, e) in enumerate(((GRUB_R0, EMB_R0), (GRUB_R1, EMB_R1))):
        grub_frames[(d, f)] = spr.blit_grid(g, GRUB_L, 'grub_%d_%d' % (d, f), flip=flip)
        emb_frames[(d, f)] = spr.blit_grid(e, EMB_L, 'emb_%d_%d' % (d, f), flip=flip)

GHOST = [
    "..kkkk..",
    ".kLLLLk.",
    "kLkLLkLk",
    "kLkLLkLk",
    "kLLLLLLk",
    "kLLLLLLk",
    "kLkLLkLk",
    ".k.kk.k.",
]
GHOST2 = [
    "..kkkk..",
    ".kLLLLk.",
    "kLkLLkLk",
    "kLkLLkLk",
    "kLLLLLLk",
    "kLLLLLLk",
    "kkLkkLkk",
    "..k..k..",
]
GL = dict(k=P['ink'], L=P['bone_l'], w=P['white'], p=P['ink'])
ghost_frames = [spr.blit_grid(GHOST, GL, 'ghost0'), spr.blit_grid(GHOST2, GL, 'ghost1')]

def blob(size, body, shade, hi, eye_dir, angry=False, frame=0, seam=None):
    """procedural inflated ball, size px square, outline ink, curved seams"""
    seam = seam if seam is not None else P['seam']
    s = Sheet(size, size)
    r = (size - 1) / 2.0
    for y in range(size):
        for x in range(size):
            dx, dy = x - r, y - r
            d = math.hypot(dx, dy)
            if d <= r + 0.25:
                if d > r - 1.0:
                    s.put(x, y, P['ink'])
                else:
                    c = body
                    if dx + dy > r * 0.55:
                        c = shade
                    if dx + dy < -r * 0.9 and d < r - 1.6:
                        c = hi
                    s.put(x, y, c)
    R = 1.2 * r
    for y in range(size):
        for x in range(size):
            dx, dy = x - r, y - r
            if math.hypot(dx, dy) > r - 1.6:
                continue
            for cx in (1.65 * r, 0.35 * r):
                if abs(math.hypot(x - cx, y - r) - R) < 0.55:
                    s.put(x, y, seam)
    ex = int(r + (1 if eye_dir == 0 else -2 if eye_dir == 1 else 0))
    ey = int(r - 1)
    for ox, oy, col in ((0, 0, P['white']), (1, 0, P['white']), (0, 1, P['white']), (1, 1, P['ink'])):
        s.put(ex + ox, ey + oy, col)
    my = int(r + r * 0.45)
    for i in range(-1, 3):
        s.put(int(r) + i, my, P['ink'])
    return s

def place_sheet(sh, name):
    x, y = spr.alloc(sh.w, sh.h, name)
    for j in range(sh.h):
        for i in range(sh.w):
            if sh.px[j][i]:
                spr.put(x + i, y + j, sh.px[j][i])
    return x, y

BLOB_SIZES = [10, 12, 14, 16]
grub_inf, emb_inf = [], []

ROCK = [
    "kkkkkkkk",
    "kWLLWWDk",
    "kWLWWWDk",
    "kWWWWWDk",
    ".kWWWDk.",
    "..kWDk..",
    "...kk...",
    "........",
]
RL = dict(k=P['ink'], W=P['jersey'], D=P['ball_d'], L=P['white'], B=P['jersey'])
rock_still = spr.blit_grid(ROCK, RL, 'rock')
ROCK_W = [
    ".kkkkkkk",
    ".kWLLWWD",
    ".kWLWWWD",
    ".kWWWWWD",
    "..kWWWDk",
    "...kWDk.",
    "....kk..",
    "........",
]
rock_wob = [spr.blit_grid(ROCK_W, RL, 'rockw0'), spr.blit_grid(ROCK_W, RL, 'rockw1', flip=True)]
ROCK_C = [
    [
        "........",
        "k.k.kk.k",
        "kWkWWkDk",
        "kWWkDkDk",
        "kDDkDDDk",
        ".kkkkkk.",
        "........",
        "........",
    ],
    [
        "........",
        "........",
        "........",
        "k.k..k.k",
        "kDkkDkDk",
        ".kkkkkk.",
        "........",
        "........",
    ],
]
rock_crumble = [spr.blit_grid(g, RL, 'rockc%d' % i) for i, g in enumerate(ROCK_C)]

# tunnel autotiles: bit0 N solid, bit1 E, bit2 S, bit3 W
def tunnel_tile(mask):
    t = Sheet(8, 8)
    for y in range(8):
        for x in range(8):
            t.put(x, y, P['void'] if (x + y) % 2 == 0 or y < 4 else P['voidhi'])
    # subtle dither gradient toward the bottom
    for y in range(8):
        for x in range(8):
            base = P['void'] if y < 5 else (P['void'] if (x + y) % 2 else P['voidhi'])
            t.put(x, y, base)
    def line(pts, col):
        for (x, y) in pts:
            t.put(x, y, col)
    if mask & 1:
        line([(x, 0) for x in range(8)], P['rim']); line([(x, 1) for x in range(8)], P['rimlo'])
    if mask & 4:
        line([(x, 7) for x in range(8)], P['rim']); line([(x, 6) for x in range(8)], P['rimlo'])
    if mask & 2:
        line([(7, y) for y in range(8)], P['rim']); line([(6, y) for y in range(8)], P['rimlo'])
    if mask & 8:
        line([(0, y) for y in range(8)], P['rim']); line([(1, y) for y in range(8)], P['rimlo'])
    # re-assert bright rim on corners
    if mask & 1 and mask & 8: t.put(0, 0, P['rim'])
    return t

tun = []
# keep all 16 tiles in one 64x16 strip so C can index by mask
tx0, ty0 = spr.alloc(64, 16, 'tunnels')
for m in range(16):
    t = tunnel_tile(m)
    ox, oy = tx0 + (m % 8) * 8, ty0 + (m // 8) * 8
    for j in range(8):
        for i in range(8):
            spr.put(ox + i, oy + j, t.px[j][i])

# --------------------------------------------------------------- font ----
G = {
'A':"010101111101101",'B':"110101110101110",'C':"011100100100011",'D':"110101101101110",
'E':"111100110100111",'F':"111100110100100",'G':"011100101101011",'H':"101101111101101",
'I':"111010010010111",'J':"001001001101010",'K':"101101110101101",'L':"100100100100111",
'M':"101111111101101",'N':"110101101101101",'O':"010101101101010",'P':"110101110100100",
'Q':"010101101111011",'R':"110101110101101",'S':"011100010001110",'T':"111010010010010",
'U':"101101101101111",'V':"101101101101010",'W':"101101111111101",'X':"101101010101101",
'Y':"101101010010010",'Z':"111001010100111",
'0':"111101101101111",'1':"010110010010111",'2':"110001010100111",'3':"110001010001110",
'4':"101101111001001",'5':"111100110001110",'6':"011100111101111",'7':"111001010010010",
'8':"111101111101111",'9':"111101111001110",
'-':"000000111000000",':':"000010000010000",'!':"010010010000010",'.':"000000000000010",
"'":"010010000000000",
}
FONT_ORDER = [chr(c) for c in range(ord('A'), ord('Z')+1)] + [chr(c) for c in range(ord('0'), ord('9')+1)] + ['-', ':', '!', '.', "'"]
assert len(FONT_ORDER) == 41
FONT_COLORS = [P['cream'], P['gold']]
fx0, fy0 = spr.alloc(128, 18, 'font')
for s, col in enumerate(FONT_COLORS):
    for i, ch in enumerate(FONT_ORDER):
        cell = s * 41 + i
        gx, gy = fx0 + (cell % 32) * 4, fy0 + (cell // 32) * 6
        bits = G[ch]
        for j in range(5):
            for k in range(3):
                if bits[j*3+k] == '1':
                    spr.put(gx + k + 1, gy + j + 1, P['txt_sh'])
        for j in range(5):
            for k in range(3):
                if bits[j*3+k] == '1':
                    spr.put(gx + k, gy + j, col)

# --------------------------------------------------------------- logo ----
def make_logo(text, scale=3, faces=None):
    gw, gh = 3 * scale, 5 * scale
    adv = gw + scale
    W = adv * len(text) + 3
    H = gh + 4
    L = Sheet(W, H)
    # stroke colours: top light, bottom darker -> chunky "cut stone" letters
    for n, ch in enumerate(text):
        if ch == ' ':
            continue
        bits = G[ch]
        ox = n * adv
        for j in range(5):
            for k in range(3):
                if bits[j*3+k] != '1':
                    continue
                for a in range(scale):
                    for b in range(scale):
                        x, y = ox + k*scale + a, j*scale + b
                        # shadow (drawn first, overwritten by face)
                        L.put(x + 2, y + 2, P['ink'])
    for n, ch in enumerate(text):
        if ch == ' ':
            continue
        bits = G[ch]
        ox = n * adv
        for j in range(5):
            for k in range(3):
                if bits[j*3+k] != '1':
                    continue
                for a in range(scale):
                    for b in range(scale):
                        x, y = ox + k*scale + a, j*scale + b
                        fc = faces or (P['jersey'], P['ball_d'], P['seam'])
                        face = fc[0] if j < 3 else (fc[1] if j < 4 else fc[2])
                        L.put(x, y, face)
                        if b == 0:
                            L.put(x, y, P['cream'])
    return L
logo = make_logo('DUG OUT', 3)
logo_xy = place_sheet(logo, 'logo')
LOGO_W, LOGO_H = logo.w, logo.h

# small DOUG portrait for title (2x scaled)
def scale_grid(grid, legend, s):
    L = Sheet(len(grid[0]) * s, len(grid) * s)
    for j, row in enumerate(grid):
        for i, ch in enumerate(row):
            if ch != '.':
                for a in range(s):
                    for b in range(s):
                        L.put(i*s + a, j*s + b, legend[ch])
    return L
portrait = scale_grid(DOUG_R0, DOUG_L, 3)
portrait_xy = place_sheet(portrait, 'portrait')

# heart / life icon
LIFE = [
    "..kkkk..",
    ".kWrWWk.",
    "kWrWWWrk",
    "kWrWWWrk",
    ".kWrWWk.",
    "..kkkk..",
]
LFL = dict(k=P['ink'], W=P['ball'], r=P['seam'])
life_xy = spr.blit_grid(LIFE, LFL, 'life')
FLAG = [
    "kkkkk",
    "kwwwk",
    "kwrwk",
    "kkkkk",
]
# flame breath tiles (drawn 8x8, stretched by repeated blits)
FLA = [
    "..3..3..",
    ".33.33..",
    ".3223.3.",
    "32211223",
    "32111123",
    ".321123.",
    "..3223..",
    "...33...",
]
FLB = [
    "..3..3..",
    "..33.33.",
    ".3.3223.",
    "32211223",
    "32111123",
    ".321123.",
    "..3223..",
    "..3333..",
]
FLM = dict(zip('123', (P['flame1'], P['flame2'], P['flame3'])))
flame_frames = [spr.blit_grid(FLA, FLM, 'flame0'),
                spr.blit_grid(FLB, FLM, 'flame1')]


# --- Bat Bat: a baseball with wings (12x8, two flap frames) -------------------------------
BATL = dict(k=P['ink'], B=P['ball'], r=P['seam'], W=P['b3c'], w=P['hose'], e=P['ink'])
BAT0 = [
    "W..........W",
    "WW..kkkk..WW",
    "WWWkBBBBkWWW",
    ".WWkBeeBkWW.",
    "..WkBrBBkW..",
    "...kBBrBk...",
    "....kkkk....",
    "............",
]
BAT1 = [
    "............",
    "....kkkk....",
    "...kBBBBk...",
    "WW.kBeeBk.WW",
    "WWWkBBrBkWWW",
    ".WWkBBBBkWW.",
    "..W.kkkk.W..",
    "............",
]
bat_frames = [spr.blit_grid(BAT0, BATL, 'bat0'), spr.blit_grid(BAT1, BATL, 'bat1')]
bat_inf = []

# --- Groundskeeper: a green ghoul in overalls and a cap, walks through dirt refilling tunnels -----
GKL = dict(k=P['ink'], c=P['grass_d'], C=P['grass'], z=P['gskin'], e=P['vred'], o=P['suit_d'], O=P['suit'], b=P['boot'])
GK_R0 = [
    "..kkkk..",
    ".kccccCk",
    ".kccccCk",
    "..kzzek.",
    "..kzzzk.",
    ".koOooOk",
    ".kooooOk",
    "..kb.bk.",
]
GK_R1 = [
    "..kkkk..",
    ".kccccCk",
    ".kccccCk",
    "..kzzek.",
    "..kzzzk.",
    ".koOooOk",
    ".kooooOk",
    "...kbbk.",
]
gk_frames = {}
for d, flip in ((0, False), (1, True)):
    for f, g in enumerate((GK_R0, GK_R1)):
        gk_frames[(d, f)] = spr.blit_grid(g, GKL, 'gk_%d_%d' % (d, f), flip=flip)
gk_inf = []

# --- strike marks: "X1" white, "X2" yellow, "X3" red (the out). Mascot uses X1..X6 with the same colours. ---
YEL = pc((240, 222, 70))
def mark(label, col):
    m = Sheet(8, 6)
    for pass_, c in ((0, P['ink']), (1, col)):
        ox = 1 if pass_ == 0 else 0
        for n, ch in enumerate(label):
            bits = G[ch]
            for j in range(5):
                for k in range(3):
                    if bits[j * 3 + k] == '1':
                        m.put(n * 4 + k + ox, j + ox, c)
    return place_sheet(m, 'mark_' + label + str(col))
mark_frames = [mark('X1', P['white']), mark('X2', P['white']), mark('X2', YEL), mark('X3', YEL),
               mark('X4', YEL), mark('X3', P['vred']), mark('X5', P['vred']), mark('X6', P['vred'])]
# --- a headstone marks where a Vumpire fell (other Vumpires can raise it again) -----------------
TOMB = [
    "..kkkk..",
    ".kGGGGk.",
    "kGGGGGGk",
    "kGrGGrGk",
    "kGGrrGGk",
    "kGrGGrGk",
    "kGGGGGGk",
    "kkkkkkkk",
]
tomb_xy = spr.blit_grid(TOMB, dict(k=P['ink'], G=P['ball_d'], r=P['seam']), 'tomb')

# --- firework burst frames (gold), 4 expanding sizes ------------------------------------
BURST_SIZES = [8, 12, 16, 20]
def burst(size):
    b = Sheet(size, size)
    r = (size - 1) / 2.0
    n = 12
    for k in range(n):
        ang = k * 2 * math.pi / n
        for step in range(int(r * 0.45), int(r) + 1):
            x = int(round(r + math.cos(ang) * step)); y = int(round(r + math.sin(ang) * step))
            b.put(x, y, P['flame1'] if step > r * 0.75 else P['sun'])
    b.put(int(r), int(r), P['white'])
    return b
burst_frames = [place_sheet(burst(sz), 'burst%d' % i) for i, sz in enumerate(BURST_SIZES)]

# --- a wrapped candy: a pink sweet with a twist of mint wrapper at each end (8x8)
CANDY = [
    "........",
    "h......h",
    "hh.pp.hh",
    ".hplpph.",
    ".hpplph.",
    "hh.pp.hh",
    "h......h",
    "........",
]
CANDYL = dict(h=P['hose'], p=P['grub'], l=P['grub_l'])
candy_xy = spr.blit_grid(CANDY, CANDYL, 'candy')

spr.save_bmp(os.path.join(ROOT, 'assets', 'spr', 'spr.bmp'))
png(os.path.join(ROOT, 'tools_py', 'preview_spr.png'), spr.px, 5)

# ==================================================================== BG ===
bg = Sheet()
fld = Sheet(112, 128)
rnd = random.Random(7)
FW, FH = 112, 104

BANDS = [  # (first pixel row, base, second, third)
    (8,  'b1a', 'b1b', 'b1c'),
    (32, 'b2a', 'b2b', 'b2c'),
    (56, 'b3a', 'b3b', 'b3c'),
    (80, 'b4a', 'b4b', 'b4c'),
]
def band_edge(x, i):
    """wavy contour boundary y for boundary index i"""
    y0 = BANDS[i][0]
    return int(round(y0 + 2.2 * math.sin(x * 0.19 + i * 1.7) + 1.3 * math.sin(x * 0.07 + i)))

def band_at(x, y):
    b = 0
    for i in range(1, 4):
        if y >= band_edge(x, i):
            b = i
    return b

# stadium surface (row 0..7): night sky, light towers, crowd, mown outfield grass
for y in range(8):
    for x in range(FW):
        c = P['cap_d'] if y < 3 else (P['cap'] if y < 5 else P['ink'])
        if y in (2, 4) and (x + y) % 2 == 0:
            c = P['cap'] if y == 2 else P['cap_d']
        fld.put(x, y, c)
rr = random.Random(11)
for x in range(FW):                      # crowd: tiny coloured heads on the stands
    for y in (3, 4, 5):
        if rr.random() < 0.55:
            fld.put(x, y, rr.choice([P['brim'], P['cream'], P['grub'], P['b3c'], P['hose'], P['sun']]))
for x in range(FW):                      # stand rail
    fld.put(x, 6, P['ball_d'])
for tx in (12, 98):                      # light towers
    for y in range(0, 6):
        fld.put(tx, y, P['ball_d'])
    for dx in (-2, -1, 0, 1, 2):
        fld.put(tx + dx, 0, P['white'])
        fld.put(tx + dx, 1, P['sun'] if dx in (-2, 2) else P['white'])
for x in range(FW):                      # outfield grass with mowing stripes
    fld.put(x, 7, P['grass'] if (x // 6) % 2 == 0 else P['grass_d'])

# --- stadium detail: outfield wall with ads, scoreboard, foul poles, dugout over Doug's shaft ---
for x in range(FW):                      # outfield wall (green) with ad panels
    fld.put(x, 6, P['grass_d'])
    if (x // 9) % 3 == 1:
        fld.put(x, 6, P['brim'])
    elif (x // 9) % 3 == 2:
        fld.put(x, 6, P['cream'])
for x in range(74, 98):                  # scoreboard
    for y in range(1, 5):
        fld.put(x, y, P['ink'])
for x in range(75, 97):
    fld.put(x, 1, P['ball_d'])
for i, x in enumerate(range(77, 95, 3)):
    fld.put(x, 3, P['sun'] if i % 2 == 0 else P['vred'])
    fld.put(x + 1, 3, P['sun'] if i % 2 == 0 else P['vred'])
for px_ in (4, 107):                     # yellow foul poles
    for y in range(0, 7):
        fld.put(px_, y, P['hat'])
for x in range(43, 62):                  # dugout: roof, dark opening, bench, steps
    fld.put(x, 3, P['ball_d']); fld.put(x, 2, P['ball'])
    for y in range(4, 7):
        fld.put(x, y, P['ink'])
for x in range(45, 60):
    fld.put(x, 5, P['brim'] if x % 2 == 0 else P['cap'])   # bench with striped rail
fld.put(47, 3, P['ball']); fld.put(58, 3, P['ball'])
for y in range(3, 7):                    # posts
    fld.put(43, y, P['ball_d']); fld.put(61, y, P['ball_d'])

# dirt
for y in range(8, FH):
    for x in range(FW):
        b = band_at(x, y)
        _, ca, cb, cc = BANDS[b]
        c = P[ca]
        n = rnd.random()
        if n < 0.10: c = P[cb]
        elif n < 0.14: c = P[cc]
        # strata boundaries drawn as dashed chalk lines
        for i in range(1, 4):
            e = band_edge(x, i)
            if y == e and (x % 4) != 3:
                c = P['jersey']
            elif y == e + 1 and (x % 4) == 1:
                c = P[BANDS[i][1]]
        # foul line: solid chalk at the top of the infield clay
        if y == 8:
            c = P['jersey']
        elif y == 9 and (x % 3) != 1:
            c = P[BANDS[0][1]]
        fld.put(x, y, c)
# pebbles & fossils
for _ in range(70):
    x, y = rnd.randrange(2, FW - 3), rnd.randrange(12, FH - 2)
    b = band_at(x, y)
    _, ca, cb, cc = BANDS[b]
    col = P[cc] if rnd.random() < .5 else P[cb]
    dark = P['ink'] if b >= 2 else P[cb]
    fld.put(x, y, col); fld.put(x + 1, y, col); fld.put(x, y + 1, dark if rnd.random() < .5 else col)
# buried baseballs deep down
for _ in range(9):
    x, y = rnd.randrange(3, FW - 5), rnd.randrange(84, FH - 4)
    for dx in range(3):
        for dy in range(3):
            if (dx, dy) in ((0, 0), (2, 0), (0, 2), (2, 2)):
                continue
            fld.put(x + dx, y + dy, P['ball'])
    fld.put(x, y + 1, P['seam']); fld.put(x + 2, y + 1, P['seam'])

# depth gauges: 7px wide strips with a tick per cell and a long tick per 3 cells
def gauge(x0, flip):
    for y in range(FH):
        for i in range(7):
            bg.put(x0 + i, y, P['ink'])
        row_y = y % 8
        cell = y // 8
        for i in range(7):
            col_i = (6 - i) if flip else i
            # ticks grow from the field-side edge
            tick_len = 4 if cell % 3 == 0 else 2
            if row_y == 0 and i < tick_len:
                bg.put(x0 + (6 - i if not flip else i), y, P['rim'] if cell % 3 == 0 else P['rimlo'])
        # ruler spine
        bg.put(x0 + (6 if not flip else 0), y, P['rimlo'])
FIELD_OX = 7
for y in range(FH):
    for x in range(FW):
        bg.put(FIELD_OX + x, y, fld.px[y][x])
gauge(0, False)           # left depth gauge  (screen x=1)
gauge(FIELD_OX + FW, True)  # right depth gauge (screen x=120)
bg.save_bmp(os.path.join(ROOT, 'assets', 'bg', 'bg.bmp'))
png(os.path.join(ROOT, 'tools_py', 'preview_bg.png'), bg.px, 5)


# ================================================================ ENDING ART ===
# A full-screen "high graphics" celebration page: dithered dusk sky, stadium lights and glow,
# a packed crowd, striped outfield, infield dirt with chalk lines and home plate, and a big
# Doug hoisting a trophy. Text, fireworks and confetti are layered on top by the game.
END = Sheet()
BAY = [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]
def bayer(x, y):
    return (BAY[y & 3][x & 3] + 0.5) / 16.0
def mix(ca, cb, t, x, y):
    """ordered-dither between two RGB colours"""
    return pc(cb if t > bayer(x, y) else ca, True) or 1
er = random.Random(5)
STOPS = [(0, (16, 14, 46)), (26, (36, 36, 96)), (48, (100, 56, 128)), (66, (196, 84, 104)), (82, (232, 150, 88))]
def sky_rgb(y):
    for i in range(len(STOPS) - 1):
        (y0, c0), (y1, c1) = STOPS[i], STOPS[i + 1]
        if y0 <= y <= y1:
            t = (y - y0) / float(y1 - y0)
            return c0, c1, t
    return STOPS[-1][1], STOPS[-1][1], 0
for y in range(128):
    for x in range(128):
        c0, c1, t = sky_rgb(y)
        END.px[y][x] = mix(c0, c1, t, x, y)
for _ in range(70):                       # stars
    x, y = er.randrange(1, 127), er.randrange(8, 48)
    END.px[y][x] = P['white'] if er.random() < .6 else pc((150, 150, 190))
# stadium lights with glow and beams
def glow(cx, cy, rad, col, strength, sh=None):
    sh = sh or END
    for y in range(max(0, cy - rad), min(128, cy + rad)):
        for x in range(max(0, cx - rad), min(128, cx + rad)):
            d = math.hypot(x - cx, y - cy)
            if d < rad:
                t = ((1 - d / rad) ** 2) * strength
                cur = PAL[sh.px[y][x]]
                sh.px[y][x] = mix(cur, col, t, x, y)
for lx in (14, 113):
    glow(lx, 34, 26, (255, 240, 200), 0.75)
    for k in range(0, 34):                          # beam toward centre
        for dx in range(-k // 3 - 1, k // 3 + 2):
            xx = lx + dx + (k // 2 if lx < 64 else -(k // 2))
            yy = 36 + k
            if 0 <= xx < 128 and yy < 128 and er.random() < 0.55:
                cur = PAL[END.px[yy][xx]]
                END.px[yy][xx] = mix(cur, (255, 240, 200), 0.18, xx, yy)
    for y in range(40, 90):                         # pole
        END.px[y][lx] = P['ball_d']; END.px[y][lx + 1] = P['ink']
    for dx in range(-7, 8):                         # lamp bank
        for dy in range(0, 5):
            END.px[30 + dy][lx + dx] = P['ink'] if dy in (0, 4) else P['ball']
        END.px[32][lx + dx] = P['white'] if dx % 2 == 0 else P['sun']
# crowd: stands with tiers of heads, bodies and raised arms
CROWD = [P['brim'], P['cream'], P['grub'], P['b3c'], P['hose'], P['sun'], P['cap'], P['jersey'], P['grass'], P['vred']]
SKIN = [P['skin'], P['vskin'], pc((150, 110, 80)), pc((220, 170, 130))]
for y in range(60, 92):
    for x in range(128):
        END.px[y][x] = P['ink']
for tier, y0 in enumerate((62, 69, 76, 83)):
    for x in range(0, 128, 4):
        xx = x + er.randrange(0, 2)
        head = er.choice(SKIN); body = er.choice(CROWD)
        arms = er.random() < 0.35
        hy = y0 + er.randrange(0, 2)
        for dx in range(3):
            for dy in range(3):
                END.px[hy + dy][xx + dx] = head
        for dx in range(4):
            for dy in range(3, 6):
                if 0 <= xx + dx - 1 < 128 and hy + dy < 92:
                    END.px[hy + dy][xx + dx - 1] = body
        if arms:
            for k in range(1, 4):
                if hy - k >= 60:
                    END.px[hy - k][xx - 1] = head; END.px[hy - k][xx + 3] = head
    for x in range(128):                                 # tier rail shadow
        END.px[y0 + 6][x] = P['ink']
for x in range(128):
    END.px[59][x] = P['ball_d']; END.px[60][x] = P['ink']
# pennants string across the top of the stands
for x in range(2, 126):
    y = 52 + int(4 * math.sin((x / 126.0) * math.pi))
    END.px[y][x] = P['ball_d']
    if x % 6 == 2:
        col = [P['brim'], P['cream'], P['cap'], P['hat']][(x // 6) % 4]
        for k in range(3):
            END.px[y + 1 + k][x] = col; END.px[y + 1 + k][x + 1] = col if k < 2 else 0 or col
# outfield: mown stripes with a dither shadow under the stands
for y in range(92, 128):
    for x in range(128):
        stripe = ((x // 8) % 2 == 0)
        base = (58, 150, 50) if stripe else (40, 118, 34)
        shade = max(0.0, 1 - (y - 92) / 10.0) * 0.6
        END.px[y][x] = mix(base, (16, 40, 20), shade, x, y)
# infield dirt: big arc of clay with pebbles, chalk lines fanning from home plate
for y in range(100, 128):
    for x in range(128):
        d = math.hypot((x - 64) / 70.0, (y - 130) / 30.0)
        if d < 1.0:
            t = 0.25 + 0.25 * math.sin(x * 0.7 + y * 0.4)
            END.px[y][x] = mix((196, 104, 60), (160, 84, 50), t, x, y)
            if er.random() < 0.06:
                END.px[y][x] = pc((224, 150, 96))
def line(sheet, x0, y0, x1, y1, col):
    dx, dy = abs(x1 - x0), abs(y1 - y0)
    sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
    err = dx - dy
    while True:
        if 0 <= x0 < 128 and 0 <= y0 < 128:
            sheet.px[y0][x0] = col
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 > -dy: err -= dy; x0 += sx
        if e2 < dx: err += dx; y0 += sy
line(END, 64, 118, 8, 96, P['jersey'])                 # foul lines
line(END, 64, 118, 120, 96, P['jersey'])
for (bx0, bx1) in ((50, 56), (72, 78)):                 # batter's boxes
    for x in range(bx0, bx1 + 1):
        END.px[112][x] = P['jersey']; END.px[121][x] = P['jersey']
    for y in range(112, 122):
        END.px[y][bx0] = P['jersey']; END.px[y][bx1] = P['jersey']
# home plate (pentagon, point down)
PLATE = ["kkkkkkkkkkkk", "kWWWWWWWWWWk", "kWWWWWWWWWWk", "kWWWWWWWWWWk", ".kWWWWWWWWk.",
         "..kWWWWWWk..", "...kWWWWk...", "....kkkk...."]
for j, row in enumerate(PLATE):
    for i, ch in enumerate(row):
        if ch != '.':
            END.px[113 + j][58 + i] = P['ink'] if ch == 'k' else P['jersey']
# ---- big Doug (3x) with arms up, holding a trophy ------------------------------------
layer = Sheet()
DOUG_BIG = [
    "..kkkk..",
    ".kccccr.",
    ".kCCCCrr",
    ".ksesesk",
    ".kssssk.",
    "kwpwwpwk",
    ".kwwwwk.",
    "..kb.bk.",
]
big = scale_grid(DOUG_BIG, dict(DOUG_L, k=0), 3)   # outline added later procedurally
dx0, dy0 = 52, 86
for j in range(big.h):
    for i in range(big.w):
        if big.px[j][i]:
            layer.px[dy0 + j][dx0 + i] = big.px[j][i]
def thick(sheet, x0, y0, x1, y1, col, w=3):
    n = max(abs(x1 - x0), abs(y1 - y0)) + 1
    for k in range(n + 1):
        x = int(round(x0 + (x1 - x0) * k / float(n))); y = int(round(y0 + (y1 - y0) * k / float(n)))
        for a in range(w):
            for b in range(w):
                if 0 <= x + a < 128 and 0 <= y + b < 128:
                    sheet.px[y + b][x + a] = col
thick(layer, 55, 100, 59, 80, P['jersey'], 3)          # arms raised in a V
thick(layer, 71, 100, 67, 80, P['jersey'], 3)
for hx in (58, 66):                                     # hands
    for a in range(4):
        for b in range(3):
            layer.px[76 + b][hx + a - 1] = P['skin']
# trophy: gold cup with handles, stem and base
for y, w in ((60, 12), (61, 12), (62, 11), (63, 10), (64, 9), (65, 8), (66, 6), (67, 4)):
    for x in range(64 - w // 2, 64 + w // 2):
        layer.px[y][x] = P['gold'] if x > 62 else P['sun']
for x in range(60, 68):
    layer.px[60][x] = P['white'] if 60 < x < 65 else layer.px[60][x]
for y in range(68, 73):
    layer.px[y][63] = P['gold']; layer.px[y][64] = P['sun']
for x in range(60, 68):
    layer.px[73][x] = P['gold']; layer.px[74][x] = P['suit_d']
for (hx, hy) in ((57, 61), (70, 61)):                   # handles
    for k in range(4):
        layer.px[hy + k][hx] = P['gold']
    layer.px[hy][hx + (1 if hx < 60 else -1)] = P['gold']
    layer.px[hy + 3][hx + (1 if hx < 60 else -1)] = P['gold']
# shadow under Doug
for y in range(109, 114):
    for x in range(48, 82):
        if ((x - 65) / 17.0) ** 2 + ((y - 111) / 3.0) ** 2 < 1:
            cur = PAL[END.px[y][x]]
            END.px[y][x] = mix(cur, (20, 20, 30), 0.6, x, y)
# composite with outline
for j in range(128):
    for i in range(128):
        if layer.px[j][i] == 0:
            near = any(0 <= j + b < 128 and 0 <= i + a < 128 and layer.px[j + b][i + a] for a, b in ((1,0),(-1,0),(0,1),(0,-1)))
            if near:
                END.px[j][i] = P['ink']
for j in range(128):
    for i in range(128):
        if layer.px[j][i]:
            END.px[j][i] = layer.px[j][i]
# baked "YOU WIN!" lettering (chunky, with a warm glow behind)
winlogo = make_logo('VICTORY!', 3)
lx0, ly0 = (128 - winlogo.w) // 2, 12
glow(64, ly0 + 9, 44, (255, 200, 120), 0.35)
for j in range(winlogo.h):
    for i in range(winlogo.w):
        if winlogo.px[j][i]:
            END.px[ly0 + j][lx0 + i] = winlogo.px[j][i]
END.save_bmp(os.path.join(ROOT, 'assets', 'end', 'end.bmp'))
png(os.path.join(ROOT, 'tools_py', 'preview_end.png'), END.px, 5)


# ============================================================== GAME OVER ART ===
OV = Sheet()
orr = random.Random(9)
OST = [(0, (8, 6, 26)), (30, (24, 20, 60)), (60, (70, 36, 90)), (84, (120, 52, 88))]
def ov_sky(y):
    for i in range(len(OST) - 1):
        (y0, c0), (y1, c1) = OST[i], OST[i + 1]
        if y0 <= y <= y1:
            return c0, c1, (y - y0) / float(y1 - y0)
    return OST[-1][1], OST[-1][1], 0
for y in range(128):
    for x in range(128):
        c0, c1, t = ov_sky(y)
        OV.px[y][x] = mix(c0, c1, t, x, y)
for _ in range(45):
    x, y = orr.randrange(1, 127), orr.randrange(8, 46)
    OV.px[y][x] = pc((150, 150, 190)) if orr.random() < .5 else P['white']
# big moon with halo, craters and bat silhouettes crossing it
glow(108, 50, 34, (190, 190, 160), 0.5, OV)
for y in range(38, 63):
    for x in range(96, 121):
        if (x - 108) ** 2 + (y - 50) ** 2 <= 100:
            OV.px[y][x] = pc((205, 205, 170))
for (cx_, cy_, r_) in ((105, 47, 2), (111, 53, 2), (107, 55, 1)):
    for y in range(cy_ - r_, cy_ + r_ + 1):
        for x in range(cx_ - r_, cx_ + r_ + 1):
            if (x - cx_) ** 2 + (y - cy_) ** 2 <= r_ * r_:
                OV.px[y][x] = pc((150, 150, 125))
for (bx_, by_) in ((100, 46), (112, 44)):
    for dx, dy in ((0,0),(1,-1),(2,0),(3,-1),(4,0),(2,1)):
        OV.px[by_ + dy][bx_ + dx] = P['ink']
# stadium lights: one flickering dim, one dead
glow(14, 34, 22, (200, 190, 150), 0.35, OV)
for lx, lit in ((14, True), (113, False)):
    for y in range(40, 90):
        OV.px[y][lx] = P['ball_d']; OV.px[y][lx + 1] = P['ink']
    for dx in range(-7, 8):
        for dy in range(0, 5):
            OV.px[30 + dy][lx + dx] = P['ink'] if dy in (0, 4) else P['ball_d']
        OV.px[32][lx + dx] = (P['sun'] if dx % 2 == 0 else P['ball']) if (lit and dx < 1) else P['b4b']
# empty stands: dark seat rows, a few lonely spectators
for y in range(62, 92):
    for x in range(128):
        OV.px[y][x] = P['ink']
for y0 in (63, 70, 77, 84):
    for x in range(0, 124, 5):
        for dx in range(4):
            for dy in range(5):
                OV.px[y0 + dy][x + dx] = P['b4b'] if (dx + dy) % 2 == 0 else P['cap_d']
        if orr.random() < 0.10:
            hx = x + 1
            for dx in range(2):
                for dy in range(2):
                    OV.px[y0 + dy][hx + dx] = P['vskin_d']
    for x in range(128):
        OV.px[y0 + 6][x] = P['ink']
for x in range(128):
    OV.px[61][x] = P['ball_d']
# scoreboard on the stands
for y in range(38, 60):
    for x in range(30, 98):
        OV.px[y][x] = P['ink']
for x in range(30, 98):
    OV.px[38][x] = P['rim']; OV.px[59][x] = P['rim']
for y in range(38, 60):
    OV.px[y][30] = P['rim']; OV.px[y][97] = P['rim']
def draw_glyphs(sheet, x, y, txt, col):
    for ch in txt:
        if ch in G:
            bits = G[ch]
            for j in range(5):
                for k in range(3):
                    if bits[j * 3 + k] == '1':
                        sheet.px[y + j][x + k] = col
        x += 4
draw_glyphs(OV, 48, 42, "STRIKE 3", P['white'])
for i, lx in enumerate((50, 64, 78)):                  # three OUT lamps, all lit
    glow(lx, 53, 9, (255, 60, 60), 0.7, OV)
    for dx in range(-2, 3):
        for dy in range(-2, 3):
            if abs(dx) + abs(dy) <= 3:
                OV.px[53 + dy][lx + dx] = P['vred']
    OV.px[52][lx - 1] = P['white']
# field at night: muted stripes, dark clay, dim chalk, home plate
for y in range(92, 128):
    for x in range(128):
        stripe = ((x // 8) % 2 == 0)
        base = (30, 64, 40) if stripe else (22, 50, 32)
        OV.px[y][x] = mix(base, (8, 14, 18), max(0.0, 1 - (y - 92) / 9.0) * 0.7, x, y)
for y in range(100, 128):
    for x in range(128):
        d = math.hypot((x - 64) / 70.0, (y - 130) / 30.0)
        if d < 1.0:
            OV.px[y][x] = mix((120, 70, 48), (94, 54, 40), 0.3 + 0.25 * math.sin(x * 0.7 + y * 0.4), x, y)
            if orr.random() < 0.05:
                OV.px[y][x] = pc((150, 96, 66))
line(OV, 64, 118, 8, 96, pc((130, 130, 130)))
line(OV, 64, 118, 120, 96, pc((130, 130, 130)))
for j, row in enumerate(PLATE):
    for i, ch in enumerate(row):
        if ch != '.':
            OV.px[113 + j][58 + i] = P['ink'] if ch == 'k' else pc((140, 140, 140))
# ---- giant Vumpire umpire making the "you're out" call --------------------------------
ol = Sheet()
umpire = scale_grid(GRUB_R0, dict(GRUB_L), 4)
ux0, uy0 = 24, 80
for j in range(umpire.h):
    for i in range(umpire.w):
        if umpire.px[j][i]:
            ol.px[uy0 + j][ux0 + i] = umpire.px[j][i]
# the classic "out" call: upper arm out to the side, elbow bent, forearm straight up, fist raised
thick(ol, 53, 98, 64, 98, P['uni'], 4)                 # upper arm (horizontal)
thick(ol, 62, 84, 62, 98, P['uni'], 4)                 # forearm (vertical)
for a in range(6):                                     # fist
    for b in range(6):
        ol.px[78 + b][61 + a] = P['vskin']
thick(ol, 26, 100, 22, 112, P['uni'], 4)               # other arm down at his side
for y in range(110, 115):                              # shadow
    for x in range(20, 62):
        if ((x - 41) / 21.0) ** 2 + ((y - 112) / 3.0) ** 2 < 1:
            cur = PAL[OV.px[y][x]]
            OV.px[y][x] = mix(cur, (6, 6, 10), 0.65, x, y)
glow(41, 96, 26, (255, 40, 60), 0.10, OV)             # faint red aura
for j in range(128):
    for i in range(128):
        if ol.px[j][i] == 0 and any(0 <= j + b < 128 and 0 <= i + a < 128 and ol.px[j + b][i + a] for a, b in ((1,0),(-1,0),(0,1),(0,-1))):
            OV.px[j][i] = P['ink']
for j in range(128):
    for i in range(128):
        if ol.px[j][i]:
            OV.px[j][i] = ol.px[j][i]
# baked "GAME OVER" lettering in blood red
ovlogo = make_logo('GAME OVER', 3, (P['vred'], P['seam'], P['b2b']))
ox0, oy0 = (128 - ovlogo.w) // 2, 12
glow(64, oy0 + 9, 46, (255, 60, 70), 0.25, OV)
for j in range(ovlogo.h):
    for i in range(ovlogo.w):
        if ovlogo.px[j][i]:
            OV.px[oy0 + j][ox0 + i] = ovlogo.px[j][i]
OV.save_bmp(os.path.join(ROOT, 'assets', 'over', 'over.bmp'))
png(os.path.join(ROOT, 'tools_py', 'preview_over.png'), OV.px, 5)


# ================================================================ MASCOT (boss) sheet ===
spr2 = Sheet()
MASCOT_SIZES = [18, 20, 22, 24]
def mascot_head(size, feet_frame, face_dir, inflated=False):
    """foam-headed team mascot: navy fur, cream muzzle, huge red nose, grin, striped cap"""
    m = Sheet(size, size)
    r = (size - 1) / 2.0
    fur, fur_d, fur_l = P['cap'], P['cap_d'], pc((110, 110, 190))
    for y in range(size):
        for x in range(size):
            dx, dy = x - r, y - r
            d = math.hypot(dx, dy)
            if d <= r + 0.3:
                if d > r - 1.0:
                    m.put(x, y, P['ink'])
                else:
                    c = fur
                    if dx + dy > r * 0.6: c = fur_d
                    if dx + dy < -r * 0.9 and d < r - 1.8: c = fur_l
                    m.put(x, y, c)
    # cream muzzle
    for y in range(size):
        for x in range(size):
            dx, dy = (x - (r + face_dir * 0.08 * size)) / (r * 0.62), (y - (r + r * 0.32)) / (r * 0.48)
            if dx * dx + dy * dy <= 1.0 and m.px[y][x] and m.px[y][x] != P['ink']:
                m.put(x, y, P['cream'])
    # cap: red crown with a white stripe, brim toward facing side
    for y in range(size):
        for x in range(size):
            dx, dy = x - r, y - r
            if dy < -r * 0.45 and math.hypot(dx, dy) < r - 0.6 and m.px[y][x] != P['ink']:
                m.put(x, y, P['brim'] if (x + y) % 9 else P['white'])
    for x in range(int(r - r * 0.9), int(r + r * 0.9) + 1):
        m.put(x + int(face_dir * 2), int(r - r * 0.45), P['ink'])
    # big red nose
    nx, ny = int(r + face_dir * 0.08 * size), int(r + r * 0.18)
    for dx in range(-2, 3):
        for dy in range(-2, 2):
            if dx * dx + dy * dy <= 5:
                m.put(nx + dx, ny + dy, P['vred'])
    m.put(nx - 1, ny - 1, P['white'])
    # eyes with heavy brows
    for sx in (-1, 1):
        ex = int(r + sx * r * 0.42 + face_dir * 0.06 * size); ey = int(r - r * 0.12)
        for dx in range(2):
            for dy in range(3):
                m.put(ex + dx, ey + dy, P['white'])
        m.put(ex + (1 if face_dir >= 0 else 0), ey + 1, P['ink'])
        for dx in range(-1, 3):
            m.put(ex + dx, ey - 1 - (1 if (sx * dx) < 0 else 0), P['ink'])
    # huge grin with teeth
    gy = int(r + r * 0.55)
    for x in range(int(r - r * 0.5), int(r + r * 0.5) + 1):
        m.put(x + int(face_dir * 1), gy, P['ink'])
        if (x % 2) == 0:
            m.put(x + int(face_dir * 1), gy - 1, P['white'])
    if not inflated:
        # stubby feet, alternating
        for fx in ((int(r - r * 0.55), int(r + r * 0.25))[feet_frame], (int(r + r * 0.25), int(r - r * 0.55))[feet_frame]):
            for dx in range(3):
                m.put(fx + dx, size - 1, P['ink'])
    return m
mascot_frames = {}
for d, dirv in ((0, 1), (1, -1)):
    for f in range(2):
        mascot_frames[(d, f)] = (lambda sh: (spr2.alloc(sh.w, sh.h, 'mascot_%d_%d' % (d, f)), sh))(mascot_head(16, f, dirv))
# paste them
def paste2(pos_sh):
    (x, y), sh = pos_sh
    for j in range(sh.h):
        for i in range(sh.w):
            if sh.px[j][i]:
                spr2.put(x + i, y + j, sh.px[j][i])
    return (x, y)
mascot_xy = {k: paste2(v) for k, v in mascot_frames.items()}
mascot_inf = []
for i, sz in enumerate(MASCOT_SIZES):
    sh = mascot_head(sz, 0, 0, inflated=True)
    x, y = spr2.alloc(sh.w, sh.h, 'mascotinf%d' % i)
    for j in range(sh.h):
        for i2 in range(sh.w):
            if sh.px[j][i2]:
                spr2.put(x + i2, y + j, sh.px[j][i2])
    mascot_inf.append((x, y))
spr2.save_bmp(os.path.join(ROOT, 'assets', 'spr2', 'spr2.bmp'))
png(os.path.join(ROOT, 'tools_py', 'preview_spr2.png'), spr2.px, 5)

# ================================================================ HEADER ===
def arr(name, pts):
    xs = ', '.join(str(p[0]) for p in pts)
    ys = ', '.join(str(p[1]) for p in pts)
    return 'static const unsigned char %s_x[] = {%s};\nstatic const unsigned char %s_y[] = {%s};\n' % (name, xs, name, ys)

h = ['// @generated by tools_py/make_assets.py - do not edit\n#ifndef GEN_ART_H\n#define GEN_ART_H\n']
for k in ('void', 'rim', 'ink', 'cream', 'gold', 'grub', 'grub_d', 'sky0', 'b1a', 'b2a', 'b3a', 'b4a', 'hose', 'hose_d',
          'flame1', 'flame2', 'flame3', 'white', 'hat', 'suit', 'brim'):
    h.append('#define COL_%s %d\n' % (k.upper(), P[k]))
h.append('#define BG_FIELD_W %d\n#define BG_FIELD_H %d\n' % (FW, FH))
h.append('#define BG_FIELD_OX %d\n#define BG_W %d\n' % (FIELD_OX, FIELD_OX*2 + FW))
# doug: index dir*2+frame
h.append(arr('doug', [doug_frames[(d, f)] for d in range(4) for f in range(2)]))
h.append(arr('doug_dead', doug_dead))
h.append(arr('grub', [grub_frames[(d, f)] for d in range(2) for f in range(2)]))
h.append(arr('emb', [emb_frames[(d, f)] for d in range(2) for f in range(2)]))
h.append(arr('ghost', ghost_frames))
h.append(arr('mark', mark_frames))
h.append('#define SP_TOMB_X %d\n#define SP_TOMB_Y %d\n' % tomb_xy)
h.append(arr('mascot', [mascot_xy[(d, f)] for d in range(2) for f in range(2)]))
h.append(arr('gk', [gk_frames[(d, f)] for d in range(2) for f in range(2)]))
h.append(arr('bat', bat_frames))
h.append(arr('burst', burst_frames))
h.append('static const unsigned char burst_size[] = {%s};\n' % ', '.join(str(z) for z in BURST_SIZES))
h.append('#define SP_ROCK_X %d\n#define SP_ROCK_Y %d\n' % rock_still)
h.append(arr('rockw', rock_wob))
h.append(arr('rockc', rock_crumble))
h.append(arr('flame', flame_frames))
h.append('#define SP_TUNNEL_X %d\n#define SP_TUNNEL_Y %d\n' % (tx0, ty0))
h.append('static const unsigned char tunnel_px[16][64] = {\n')
for m in range(16):
    t = tunnel_tile(m)
    h.append('  {' + ','.join(str(t.px[j][i]) for j in range(8) for i in range(8)) + '},\n')
h.append('};\n')
h.append('#define SP_FONT_X %d\n#define SP_FONT_Y %d\n' % (fx0, fy0))
h.append('#define SP_LOGO_X %d\n#define SP_LOGO_Y %d\n#define SP_LOGO_W %d\n#define SP_LOGO_H %d\n' % (logo_xy + (LOGO_W, LOGO_H)))
h.append('#define SP_PORTRAIT_X %d\n#define SP_PORTRAIT_Y %d\n#define SP_PORTRAIT_W %d\n#define SP_PORTRAIT_H %d\n' % (portrait_xy + (portrait.w, portrait.h)))
h.append('#define SP_LIFE_X %d\n#define SP_LIFE_Y %d\n' % life_xy)
h.append('#define SP_CANDY_X %d\n#define SP_CANDY_Y %d\n' % candy_xy)
h.append('#endif\n')
open(os.path.join(ROOT, 'src', 'gen_art.h'), 'w').write(''.join(h))
print('ok; sprite sheet used to y=%d' % (spr.cy + spr.rowh))

# Redrawn art (tools_py/art_kit.py import ...) wins over the generated sheets.
import shutil
for _name, _dir in (('spr', 'spr'), ('spr2', 'spr2')):
    _custom = os.path.join(ROOT, 'art_custom', _name + '.bmp')
    if os.path.exists(_custom):
        shutil.copyfile(_custom, os.path.join(ROOT, 'assets', _dir, _name + '.bmp'))
        print('using custom art for', _name)
