#!/usr/bin/env python3
"""Infographic: 'Is Dug Out too big?'  Numbers are measured from the real build (see build/out.map)."""
import os, runpy, struct, sys, zlib
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.abspath(sys.argv[1])
G = runpy.run_path(os.path.join(HERE, 'make_assets.py'))['G']

W, H = 1400, 2120
NAVY, PANEL, GOLD, CREAM, MINT = (26, 22, 64), (38, 34, 88), (237, 178, 98), (232, 214, 170), (137, 198, 184)
RED, YEL, GRN, GREY, WHITE = (214, 70, 60), (240, 222, 70), (88, 172, 70), (150, 150, 200), (240, 240, 240)
px = [[NAVY] * W for _ in range(H)]

def rect(x, y, w, h, c):
    for j in range(max(0, y), min(H, y + h)):
        row = px[j]
        for i in range(max(0, x), min(W, x + w)):
            row[i] = c
def frame(x, y, w, h, c, t=3):
    rect(x, y, w, t, c); rect(x, y + h - t, w, t, c); rect(x, y, t, h, c); rect(x + w - t, y, t, h, c)
def text(x, y, s, c=CREAM, sc=3):
    for ch in s.upper():
        if ch in G:
            bits = G[ch]
            for j in range(5):
                for k in range(3):
                    if bits[j * 3 + k] == '1':
                        rect(x + k * sc, y + j * sc, sc, sc, c)
        x += 4 * sc
    return x
def tw(s, sc): return len(s) * 4 * sc - sc
def wrap(x, y, s, w, c=CREAM, sc=3, lead=None):
    lead = lead or 8 * sc
    maxc = max(1, w // (4 * sc))
    line = ''
    for word in s.split():
        if len((line + ' ' + word).strip()) > maxc:
            text(x, y, line, c, sc); y += lead; line = word
        else:
            line = (line + ' ' + word).strip()
    if line:
        text(x, y, line, c, sc); y += lead
    return y
def bar(x, y, w, h, frac, col, label, right):
    rect(x, y, w, h, (16, 14, 44)); frame(x, y, w, h, GREY, 2)
    rect(x + 3, y + 3, int((w - 6) * min(1.0, frac)), h - 6, col)
    text(x, y - 26, label, CREAM, 3)
    text(x + w + 16, y + h // 2 - 8, right, col, 4)

# ---- title
text(40, 36, 'IS DUG OUT TOO BIG?', GOLD, 8)
rect(40, 96, W - 80, 4, MINT)
wrap(40, 120, 'SHORT ANSWER: NO. YOUR CARTRIDGE IS ABOUT 9 PERCENT FULL. ONLY ONE THING IS TIGHT: THE SPACE FOR GAME CODE THAT THE CONSOLE CAN CALL DIRECTLY.', W - 80, WHITE, 4, 40)

# ---- panel 1: the cartridge
y0 = 270
rect(30, y0, W - 60, 470, PANEL); frame(30, y0, W - 60, 470, MINT)
text(56, y0 + 24, '1. THE CARTRIDGE HAS 128 SLOTS OF 16 KB EACH - 2 MB', GOLD, 4)
used = {0: 'code', 1: 'art', 2: 'art', 3: 'art', 4: 'art', 5: 'art', 6: 'art', 7: 'art', 8: 'music', 9: 'code', 10: 'save', 11: 'code'}
colr = {'code': GOLD, 'art': MINT, 'music': (200, 130, 200), 'save': GREY}
gx, gy, cs, gap = 60, y0 + 90, 30, 6
for i in range(128):
    cx = gx + (i % 16) * (cs + gap); cy = gy + (i // 16) * (cs + gap)
    if i in used:
        rect(cx, cy, cs, cs, colr[used[i]])
    else:
        rect(cx, cy, cs, cs, (16, 14, 44)); frame(cx, cy, cs, cs, (60, 56, 110), 2)
lx = gx + 16 * (cs + gap) + 50
text(lx, gy - 6, '12 SLOTS USED', WHITE, 4)
text(lx, gy + 30, '116 SLOTS EMPTY', GRN, 4)
yy = gy + 86
for name, c, note in (('CODE', GOLD, 'GAME LOGIC AND SDK'), ('ART', MINT, 'SPRITES AND SCREENS'),
                      ('MUSIC AND SOUND', (200, 130, 200), 'SONGS AND EFFECTS'), ('SAVE', GREY, 'HIGH SCORE')):
    rect(lx, yy, 22, 22, c); text(lx + 34, yy + 1, name + ':  ' + note, CREAM, 3); yy += 36
wrap(lx, yy + 14, 'THE REAL CONTENT IS ONLY ABOUT 52 KB OUT OF 2048 KB. THE CARTRIDGE ITSELF IS NOWHERE NEAR FULL.', 640, WHITE, 3)

# ---- panel 2: what the CPU sees
y1 = y0 + 500
rect(30, y1, W - 60, 470, PANEL); frame(30, y1, W - 60, 470, MINT)
text(56, y1 + 24, '2. THE CATCH: THE CPU ONLY SEES 64 KB AT ONCE', GOLD, 4)
bx, bw = 70, 460
blocks = [('0000-1FFF  WORK RAM  8 KB', (60, 90, 120), 52),
          ('2000-7FFF  VIDEO AND SOUND', (70, 70, 110), 52),
          ('8000-BFFF  BANKED WINDOW  16 KB', GOLD, 96),
          ('C000-FFFF  FIXED BANK  16 KB', RED, 96)]
by = y1 + 90
for label, c, h in blocks:
    rect(bx, by, bw, h, c); frame(bx, by, bw, h, NAVY, 3)
    text(bx + 14, by + h // 2 - 8, label, NAVY if c in (GOLD, RED) else WHITE, 3)
    by += h + 6
tx = bx + bw + 60
text(tx, y1 + 100, 'BANKED WINDOW', GOLD, 4)
wrap(tx, y1 + 140, 'A 16 KB WINDOW THAT SHOWS ONE SLOT OF THE CARTRIDGE AT A TIME. THE GAME CODE LIVES HERE.', 700, CREAM, 3)
text(tx, y1 + 250, 'FIXED BANK', RED, 4)
wrap(tx, y1 + 290, 'ALWAYS VISIBLE. HOLDS STARTUP AND INTERRUPTS AND THE SDK PLUS THE PIECES OF MY CODE THAT WOULD NOT FIT IN THE WINDOW.', 700, CREAM, 3)
wrap(tx, y1 + 378, 'CODE IN ONE SLOT CANNOT CALL CODE IN ANOTHER SLOT DIRECTLY. SWITCHING WOULD PULL THE CALLER OUT FROM UNDER ITSELF.', 700, WHITE, 3)

# ---- panel 3: how full is everything
y2 = y1 + 500
rect(30, y2, W - 60, 470, PANEL); frame(30, y2, W - 60, 470, MINT)
text(56, y2 + 24, '3. HOW FULL IS EACH PART?', GOLD, 4)
bw2 = 760
rows = [('GAME CODE BANK  15.96 OF 16 KB', 15959 / 16384, RED, '97 PCT'),
        ('FIXED BANK  ABOUT 0.3 KB FREE', 16065 / 16384, RED, '98 PCT'),
        ('WORK RAM  4.6 OF 7.5 KB INCL STACK', 4.6 / 7.5, YEL, '61 PCT'),
        ('WHOLE CARTRIDGE  12 OF 128 SLOTS', 12 / 128, GRN, '9 PCT')]
yy = y2 + 96
for label, f, c, r in rows:
    bar(60, yy, bw2, 40, f, c, label, r); yy += 78
text(60, yy + 4, 'FRAME TIME: HOLDING A STEADY 30 FPS', GRN, 3)

# ---- panel 4: the fix
y3 = y2 + 500
rect(30, y3, W - 60, 390, PANEL); frame(30, y3, W - 60, 390, MINT)
text(56, y3 + 24, '4. HOW WE GET MORE ROOM', GOLD, 4)
rect(60, y3 + 90, 600, 170, (16, 14, 44)); frame(60, y3 + 90, 600, 170, RED, 3)
text(80, y3 + 104, 'TODAY', RED, 4)
wrap(80, y3 + 146, 'ALL GAME CODE IN ONE 16 KB SLOT. NO ROOM TO GROW.', 560, CREAM, 3)
for i in range(0, 60, 4):                               # arrow
    rect(690 + i, y3 + 170 - (60 - i) // 2, 4, (60 - i), GOLD)
rect(690, y3 + 160, 40, 20, GOLD)
rect(800, y3 + 90, 540, 170, (16, 14, 44)); frame(800, y3 + 90, 540, 170, GRN, 3)
text(820, y3 + 104, 'FIX', GRN, 4)
wrap(820, y3 + 146, 'SPLIT THE CODE ACROSS SEVERAL SLOTS AND JOIN THEM WITH TINY HELPERS CALLED TRAMPOLINES THAT SWITCH SLOTS THEN RUN THEN SWITCH BACK.', 500, CREAM, 3)
wrap(60, y3 + 290, 'BOTTOM LINE: THE GAME IS NOT TOO BIG. 116 SLOTS ARE EMPTY. WHEN YOU WANT MORE FEATURES THE CODE JUST NEEDS TO SPREAD OUT.', W - 120, WHITE, 3)

H2 = y3 + 390 + 30
px = px[:H2]
raw = bytearray()
for row in px:
    raw += b'\x00' + b''.join(bytes(p) for p in row)
def chunk(t, d):
    c = struct.pack('>I', len(d)) + t + d
    return c + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
open(OUT, 'wb').write(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', W, H2, 8, 2, 0, 0, 0))
                      + chunk(b'IDAT', zlib.compress(bytes(raw), 9)) + chunk(b'IEND', b''))
print('wrote', OUT, W, H2)
