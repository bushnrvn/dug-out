#!/usr/bin/env python3
"""
Builds the itch.io page assets for Dug Out into a folder:

  screenshots/   real game frames (captured from the emulator), 1024x1024 pixel-exact
  cover_630x500.png, banner_1920x480.png, background_tile.png   composed from the game's own sprites and palette
  theme.txt, README-ITCH.txt

usage: python3 tools_py/itch_assets.py <shots folder> <output folder>
  <shots folder> holds emulator screenshots named like tests/itch/*.txt produce (see README-ITCH.txt).
"""
import os, random, runpy, sys, math, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import itch_kit as K

SHOTS = os.path.abspath(sys.argv[1])
OUT = os.path.abspath(sys.argv[2])
os.makedirs(os.path.join(OUT, 'screenshots'), exist_ok=True)

g = runpy.run_path(os.path.join(HERE, 'make_assets.py'))
PAL, P, G, spr, spr2 = g['PAL'], g['P'], g['G'], g['spr'], g['spr2']
rnd = random.Random(1908)


# -------------------------------------------------------------- canvas ----
class Canvas:
    def __init__(self, w, h, fill=0):
        self.w, self.h = w, h
        self.px = [[fill] * w for _ in range(h)]

    def put(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.px[y][x] = c

    def rect(self, x, y, w, h, c):
        for j in range(h):
            for i in range(w):
                self.put(x + i, y + j, c)

    def sprite(self, sheet, name, x, y, z=1, flip=False):
        sx, sy, w, h = sheet.names[name]
        for j in range(h):
            for i in range(w):
                c = sheet.px[sy + j][sx + (w - 1 - i if flip else i)]
                if c:
                    for b in range(z):
                        for a in range(z):
                            self.put(x + i * z + a, y + j * z + b, c)
        return w * z, h * z

    def text(self, x, y, s, c, z=1):
        for ch in s.upper():
            if ch in G:
                bits = G[ch]
                for j in range(5):
                    for i in range(3):
                        if bits[j * 3 + i] == '1':
                            self.rect(x + i * z, y + j * z, z, z, c)
            x += 4 * z
        return x

    def rgb(self, k):
        rows = [[tuple(PAL[v]) if v else (0, 0, 0) for v in row] for row in self.px]
        return K.scale(rows, k)


def tw(s, z=1):
    return len(s) * 4 * z - z


col = {k: P[k] for k in ('ink', 'void', 'voidhi', 'rim', 'rimlo', 'sky0', 'sky1', 'sky2', 'gold', 'cream', 'white', 'grass',
                         'grass_d', 'sun', 'lamp', 'hill', 'b1a', 'b1b', 'b1c', 'b2a', 'b2b', 'b2c', 'b3a', 'b3b', 'b3c',
                         'b4a', 'b4b', 'b4c', 'gem', 'flame1', 'flame2', 'flame3', 'vred', 'hat', 'skin')}


def strata(cv, top, seed=0):
    """warm clay at the top, cooling through rose and violet to indigo, split by dashed chalk lines."""
    bands = [(col['b1a'], col['b1b'], col['b1c']), (col['b2a'], col['b2b'], col['b2c']),
             (col['b3a'], col['b3b'], col['b3c']), (col['b4a'], col['b4b'], col['b4c'])]
    span = (cv.h - top) / 4.0
    for x in range(cv.w):
        for y in range(top, cv.h):
            wob = 3 * math.sin((x + seed) / 9.0) + 2 * math.sin((x + seed) / 4.3 + 1)
            t = (y - top + wob) / span
            k = max(0, min(3, int(t)))
            a, b, c = bands[k]
            r = rnd.random()
            cv.put(x, y, a if r < 0.78 else (b if r < 0.9 else c))
    for k in range(1, 4):                                   # chalk lines on the band edges
        for x in range(cv.w):
            wob = 3 * math.sin((x + seed) / 9.0) + 2 * math.sin((x + seed) / 4.3 + 1)
            y = int(top + k * span - wob)
            if (x // 3) % 2 == 0:
                cv.put(x, y, col['white'])


def tunnel(cv, x, y, w, h=10):
    cv.rect(x, y, w, h, col['rim'])
    cv.rect(x + 1, y + 1, w - 2, h - 2, col['void'])
    cv.rect(x + 1, y + 1, w - 2, 2, col['voidhi'])


def sky(cv, h):
    for y in range(h):
        for x in range(cv.w):
            cv.put(x, y, col['ink'] if rnd.random() > 0.004 * (h - y) / h * 6 else col['white'])
    for _ in range(cv.w // 6):
        cv.put(rnd.randrange(cv.w), rnd.randrange(h - 4), col['white'])


def grass(cv, y, h=5):
    for x in range(cv.w):
        for j in range(h):
            cv.put(x, y + j, col['grass'] if (x + j) % 4 else col['grass_d'])
    for x in range(0, cv.w, 6):                              # mown stripes
        cv.put(x, y, col['grass_d'])
    cv.rect(0, y + h - 1, cv.w, 1, col['cream'])


def cast(cv, x, y, gap=6, z=2, with_boss=True):
    """Doug chased by the whole cast, all standing on the tunnel floor at y."""
    w, h = cv.sprite(spr, 'doug_0_0', x, y - 8 * z, z); x += w + gap
    w, h = cv.sprite(spr, 'grub_0_0', x, y - 8 * z, z); x += w + gap
    hx = x
    w, h = cv.sprite(spr, 'emb_0_0', x, y - 8 * z, z)
    for ox, f in ((-6, 'flame0'), (6, 'flame1')):                # the game's two orbiting fireballs, drawn above the shoulders
        cv.sprite(spr, f, hx + ox * z * 2 // 3, y - 8 * z - 6 * z * 2 // 3, z)
    x += w + gap
    w, h = cv.sprite(spr, 'gk_0_0', x, y - 8 * z, z); x += w + gap
    w, h = cv.sprite(spr, 'bat0', x, y - 10 * z, z); x += w + gap
    if with_boss:
        cv.sprite(spr2, 'mascot_0_0', x, y - 16 * z, z)
        x += 16 * z
    return x


def plate(cv, x, y, w, h):
    cv.rect(x, y, w, h, col['ink'])
    cv.rect(x + 1, y, w - 2, 1, col['rim'])
    cv.rect(x + 1, y + h - 1, w - 2, 1, col['rim'])


# ------------------------------------------------------------ banner ----
CROWD = [P[k] for k in ('sun', 'white', 'b2c', 'gem', 'hat', 'vred', 'skin', 'b3c', 'flame2')]


def stadium(cv, top=28, towers=None, poles=None):
    """the ballpark above the dirt, as in the game: stands, light towers, scoreboards, foul poles, ad wall, striped grass."""
    W = cv.w
    # stands: rows of crowd, each row split by a dark gap
    for y in range(top + 12, top + 25):
        for x in range(W):
            if (y - top) % 3 == 0:
                cv.put(x, y, col['ink'])
            else:
                cv.put(x, y, rnd.choice(CROWD) if rnd.random() < 0.62 else col['b3a'])
    # light towers with lamp heads
    for tx in (towers or (100, W - 100)):
        cv.rect(tx, 6, 2, top + 18, col['lamp'])
        cv.rect(tx - 7, 3, 16, 7, col['lamp'])
        for i in range(4):
            for j in range(2):
                cv.rect(tx - 6 + i * 4, 4 + j * 3, 3, 2, col['white'])
        cv.rect(tx - 9, 11, 20, 1, col['sky1'])                # a soft glow under the lamps
    # two scoreboards behind the stands
    for bx, lights in ((W // 2 - 66, (col['rim'], col['rimlo'])), (W // 2 + 12, (col['sun'], col['flame2']))):
        cv.rect(bx, top + 3, 54, 13, col['lamp'])
        cv.rect(bx + 2, top + 5, 50, 9, col['ink'])
        for i in range(8):
            cv.rect(bx + 4 + i * 6, top + 7, 4, 2, lights[i % 2])
            cv.rect(bx + 4 + i * 6, top + 11, 4, 2, lights[(i + 1) % 2])
    # outfield wall with ad panels
    wy = top + 25
    cv.rect(0, wy, W, 7, col['b4a'])
    cv.rect(0, wy, W, 1, col['white'])
    ads = (col['sun'], col['rim'], col['b2c'], col['cream'], col['hat'])
    for i, x in enumerate(range(6, W - 12, 22)):
        cv.rect(x, wy + 2, 16, 4, ads[i % len(ads)])
        cv.rect(x + 2, wy + 3, 12, 1, col['b4a'])
    # foul poles
    for fx in (poles or (22, W - 24)):
        cv.rect(fx, 16, 2, wy - 14, col['gold'])
    # striped grass and a chalk line
    gy = wy + 7
    for y in range(gy, gy + 14):
        for x in range(W):
            cv.put(x, y, col['grass'] if (x // 12) % 2 == 0 else col['grass_d'])
    cv.rect(0, gy, W, 1, col['white'])
    return gy


def line(cv, x0, y0, x1, y1, c):
    dx, dy = abs(x1 - x0), -abs(y1 - y0)
    sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
    err = dx + dy
    while True:
        cv.put(x0, y0, c)
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 >= dy: err += dy; x0 += sx
        if e2 <= dx: err += dx; y0 += sy


def diamonds(cv, gy, centre, spacing=96, reach=400):
    """chalked ball diamonds with bases and a pitcher's mound, repeating along the field; one is centred on `centre`."""
    hw, top, bot, mid = 20, gy + 2, gy + 12, gy + 7
    for m in range(-(reach // spacing) - 1, reach // spacing + 2):
        cx = centre + m * spacing
        if cx + hw < 0 or cx - hw >= cv.w:
            continue
        for a, b in (((cx - hw, mid), (cx, top)), ((cx, top), (cx + hw, mid)),
                     ((cx + hw, mid), (cx, bot)), ((cx, bot), (cx - hw, mid))):
            line(cv, a[0], a[1], b[0], b[1], col['white'])
        for bx, by in ((cx - hw, mid), (cx + hw, mid), (cx, top), (cx, bot)):          # the bases
            cv.rect(bx - 1, by - 1, 3, 3, col['cream'])
        cv.rect(cx - 1, mid - 1, 3, 3, col['b1a'])                                      # the pitcher's mound


def clay(cv, y0):
    for y in range(y0, cv.h):
        for x in range(cv.w):
            r = rnd.random()
            cv.put(x, y, col['b1a'] if r < 0.78 else (col['b1b'] if r < 0.9 else col['b1c']))
    cv.rect(0, y0, cv.w, 1, col['cream'])


def banner():
    """1920x344, the wide strip itch.io shows: the ballpark above ground, everything centred."""
    cv = Canvas(480, 86)
    sky(cv, 42)
    gy = stadium(cv, 28)
    diamonds(cv, gy, 240)
    clay(cv, gy + 14)
    lw = spr.names['logo'][2]
    cv.sprite(spr, 'logo', (480 - lw) // 2, 3, 1)
    t = 'A DIGGING ARCADE GAME FOR THE GAMETANK'
    cv.text((480 - tw(t)) // 2, 24, t, col['gold'], 1)
    # the title-screen chase along the grass: Doug in front, the Vumpire and a Heater after him
    y = gy + 13
    cv.sprite(spr, 'doug_0_0', 290, y - 16, 2)
    cv.sprite(spr, 'grub_0_0', 254, y - 16, 2)
    cv.sprite(spr, 'emb_0_0', 218, y - 16, 2)
    cv.sprite(spr, 'flame0', 212, y - 22, 2)
    cv.sprite(spr, 'flame1', 232, y - 22, 2)
    K.png_write(os.path.join(OUT, 'banner_1920x344.png'), cv.rgb(4))


def background():
    """1920x2160 page background, drawn with the same 'native pixel' geometry as the banner but at 2px per pixel.
    itch.io stretches the page background about 1.35x while the banner shows at about 0.69x, so the two end up with
    the same on-screen pixel size (2.7px), the grass lines up with the banner's, and the diamonds carry on to the page edges."""
    cv = Canvas(960, 1080)
    gy = 58                                              # the banner's grass line, measured on the live page
    sky(cv, gy)
    for y in range(gy, gy + 14):
        for x in range(cv.w):
            cv.put(x, y, col['grass'] if (x // 12) % 2 == 0 else col['grass_d'])
    cv.rect(0, gy, cv.w, 1, col['white'])
    diamonds(cv, gy, 480, reach=520)
    strata(cv, gy + 14, 11)
    cv.rect(0, gy + 14, cv.w, 1, col['cream'])
    K.png_write(os.path.join(OUT, 'background_dirt_1920x2160.png'), cv.rgb(2))


# ------------------------------------------------------------- cover ----
def cover():
    """630x500: the ballpark above ground, the dirt layers below with a tunnel and the cast."""
    cv = Canvas(158, 125)
    sky(cv, 40)
    gy = stadium(cv, 28, towers=(9, 146), poles=(3, 153))
    gy_end = gy + 14                                     # first row below the grass
    strata(cv, gy_end, 2)
    cv.rect(0, gy_end, cv.w, 1, col['cream'])
    lw = spr.names['logo'][2]
    cv.sprite(spr, 'logo', (158 - lw) // 2, 3, 1)
    t = 'NINE INNINGS. ONE BOSS.'
    cv.text((158 - tw(t)) // 2, 24, t, col['gold'], 1)
    tunnel(cv, 0, 76, 158, 36)                           # tall enough for the boss at 2x
    cast(cv, 7, 109, gap=3, z=2, with_boss=False)
    cv.sprite(spr2, 'mascot_0_0', 122, 109 - 32, 2)
    plate(cv, 18, 114, 122, 9)
    t2 = 'PLAYS IN YOUR BROWSER'
    cv.text(79 - tw(t2) // 2, 116, t2, col['gold'], 1)
    rows = cv.rgb(4)
    K.png_write(os.path.join(OUT, 'cover_630x500.png'), [r[:630] for r in rows[:500]])


# ------------------------------------------------------ background tile --
def tile():
    cv = Canvas(64, 64, col['ink'])
    for _ in range(90):
        cv.put(rnd.randrange(64), rnd.randrange(64), col['void'] if rnd.random() < 0.8 else col['voidhi'])
    for _ in range(8):
        cv.put(rnd.randrange(64), rnd.randrange(64), col['rimlo'])
    K.png_write(os.path.join(OUT, 'background_tile.png'), cv.rgb(4))


# -------------------------------------------------------- screenshots ----
SHOT_LIST = [
    ('1-title', 'dd_title2.bmp'), ('2-digging', 'dd_dig.bmp'), ('3-heaters', 'dd_heater.bmp'),
    ('4-inning5', 'dd_inning5.bmp'), ('5-boss', 's_bossfight-dd_b08.bmp'), ('6-victory', 's_end-dd_e2.bmp'),
    ('7-game-over', 's_over-dd_o1.bmp'), ('8-intro', 'dd_intro.bmp'),
]

def shots():
    for name, f in SHOT_LIST:
        path = os.path.join(SHOTS, f)
        if os.path.exists(path):
            K.png_write(os.path.join(OUT, 'screenshots', name + '.png'), K.scale(K.read_shot(path), 8))
        else:
            print('missing', path)


def rgbhex(i):
    r, gg, b = PAL[i]
    return '#%02X%02X%02X' % (r, gg, b)


def docs():
    open(os.path.join(OUT, 'theme.txt'), 'w').write("""DUG OUT  ITCH.IO PAGE THEME

Every colour is taken from the game's own palette. In itch.io: Edit game > Edit theme.

Background colour     %s   (deep navy, the game's ink colour)
Background image      background_dirt_1920x2160.png   (no repeat, top centre: the dirt layers run down both sides of the page)
                      background_tile.png is a plain dark tiling alternative
Text colour           %s   (cream)
Link colour           %s   (mint, the tunnel rim glow)
Button colour         %s   (gold)
Button text colour    %s   (navy)
Panel / sidebar       %s   (slightly lighter navy)
Border colour         %s   (muted teal)

Font: pick a blocky or monospace option; the game's own type is a 3x5 pixel font.
Banner: banner_1920x344.png is the ballpark above ground (stands, light towers, scoreboards, ad wall, striped grass)
with the logo, tagline and the title-screen chase centred in it. It is the wide strip itch.io shows.
Cover image: cover_630x500.png (itch.io's recommended cover size).
""" % (rgbhex(col['ink']), rgbhex(col['cream']), rgbhex(col['rim']), rgbhex(col['gold']), rgbhex(col['ink']),
       rgbhex(col['voidhi']), rgbhex(col['rimlo'])))
    open(os.path.join(OUT, 'README-ITCH.txt'), 'w').write("""WHAT IS IN HERE

screenshots/   8 real frames captured from the game running in the GameTank emulator (version 1.3.0),
               each 1024x1024 (the 128x128 game frame at exact 8x, no smoothing).
               Suggested order on the page: 1-title, 2-digging, 3-heaters, 4-inning5, 5-boss, 6-victory.
cover_630x500.png        the cover image.
banner_1920x344.png      the page banner: the ballpark above ground.
background_dirt_1920x2160.png   page background: sky and grass at the top, then the dirt layers down the sides.
background_tile.png      tiling page background.
theme.txt                colours for the itch.io theme editor.

The cover, banner and background are composed from the game's own sprites, font, logo and palette. They are
artwork for the page, not game screenshots. The screenshots folder is the real game.

Suggested captions
  1-title      The title screen.
  2-digging    Tunnel through the strata. Every block pays 10 to 40 points.
  3-heaters    Heaters breathe fire, and fireballs circle them.
  4-inning5    By inning 5 the tunnels fill with Vumpires, Heaters, Baseball Bats and Groundskeepers.
  5-boss       Mad Scott, the inning 9 boss, smashes straight through the dirt at you.
  6-victory    Nine innings down.
  7-game-over  You're out.

Regenerate:  python3 tools_py/itch_assets.py <shots folder> <output folder>
""")


banner(); background(); cover(); tile(); shots(); docs()
print('itch kit written to', OUT)
