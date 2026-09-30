#!/usr/bin/env python3
"""
Builds an artist-reference package from the game's own art data:
  <out>/DugOut-SpriteSheet.png   labelled sheet of every sprite (scaled up, transparent shown as checkerboard)
  <out>/palette.png + palette.txt  the colours the game uses
  <out>/screens/*.png            full-screen art pages (title art, ending, game over, dirt field)
  <out>/raw/*.png                the raw sprite pages at 1x and 8x (no labels)
Usage: python3 make_art_reference.py <output folder>
"""
import os, runpy, struct, sys, zlib

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, '..', 'art_reference'))
os.makedirs(os.path.join(OUT, 'screens'), exist_ok=True)
os.makedirs(os.path.join(OUT, 'raw'), exist_ok=True)

g = runpy.run_path(os.path.join(HERE, 'make_assets.py'))    # regenerates the assets, hands back the sheets
spr, spr2, PAL, P, C, G = g['spr'], g['spr2'], g['PAL'], g['P'], g['C'], g['G']

# ---------------------------------------------------------------- tiny RGB canvas + PNG writer ---
class Canvas:
    def __init__(self, w, h, bg=(24, 22, 48)):
        self.w, self.h = w, h
        self.px = [[bg] * w for _ in range(h)]
    def rect(self, x, y, w, h, c):
        for j in range(max(0, y), min(self.h, y + h)):
            row = self.px[j]
            for i in range(max(0, x), min(self.w, x + w)):
                row[i] = c
    def text(self, x, y, s, c=(232, 210, 160), scale=2):
        for ch in s.upper():
            if ch in G:
                bits = G[ch]
                for j in range(5):
                    for k in range(3):
                        if bits[j * 3 + k] == '1':
                            self.rect(x + k * scale, y + j * scale, scale, scale, c)
            x += 4 * scale
        return x
    def text_w(self, s, scale=2):
        return len(s) * 4 * scale
    def sprite(self, sheet, sx, sy, w, h, x, y, scale):
        # transparent (index 0) shows as a soft checkerboard so the artist can see the true silhouette
        for j in range(h):
            for i in range(w):
                idx = sheet.px[sy + j][sx + i]
                for b in range(scale):
                    for a in range(scale):
                        px_, py_ = x + i * scale + a, y + j * scale + b
                        if 0 <= px_ < self.w and 0 <= py_ < self.h:
                            if idx == 0:
                                chk = ((i + j) & 1) == 0
                                self.px[py_][px_] = (54, 52, 84) if chk else (44, 42, 72)
                            else:
                                self.px[py_][px_] = tuple(PAL[idx])
    def save(self, path):
        raw = bytearray()
        for row in self.px:
            raw += b'\x00' + b''.join(bytes(p) for p in row)
        def chunk(t, d):
            c = struct.pack('>I', len(d)) + t + d
            return c + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
        open(path, 'wb').write(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', self.w, self.h, 8, 2, 0, 0, 0))
                               + chunk(b'IDAT', zlib.compress(bytes(raw), 9)) + chunk(b'IEND', b''))

def save_indexed(pixels, path, scale=1):
    h, w = len(pixels), len(pixels[0])
    c = Canvas(w * scale, h * scale)
    for j in range(h):
        for i in range(w):
            col = tuple(PAL[pixels[j][i]])
            c.rect(i * scale, j * scale, scale, scale, col)
    c.save(path)

DIRS = {'0': 'RIGHT', '1': 'LEFT', '2': 'UP', '3': 'DOWN'}
def pretty(name):
    if name.startswith('doug_x'): return 'DEAD ' + str(int(name[-1]) + 1)
    if name.startswith('doug_'):
        _, d, f = name.split('_'); return 'FACING %s %s' % (DIRS[d], int(f) + 1)
    for pre in ('grub_', 'emb_', 'gk_', 'mascot_'):
        if name.startswith(pre):
            _, d, f = name.split('_'); return 'FACING %s %s' % (DIRS[d], int(f) + 1)
    if name.startswith('bat'): return 'WINGS %s' % ('UP' if name.endswith('0') else 'DOWN')
    if name == 'rock': return 'STILL'
    if name.startswith('rockw'): return 'WOBBLE %s' % (int(name[-1]) + 1)
    if name.startswith('rockc'): return 'CRUMBLE %s' % (int(name[-1]) + 1)
    if name.startswith('flame'): return 'FLAME %s' % (int(name[-1]) + 1)
    if name.startswith('burst'): return 'OUT BURST %s' % (int(name[-1]) + 1)
    if name.startswith('mark_'): return name[5:7] + (' RED' if 'X3' in name and name.endswith(str(P['vred'])) or name.endswith(('X5' + str(P['vred']), 'X6' + str(P['vred']))) else '')
    if name == 'tomb': return 'HEADSTONE'
    if name == 'life': return 'LIFE ICON'
    if name == 'tunnels': return '16 TUNNEL WALL TILES (BY NEIGHBOURS)'
    if name == 'logo': return 'TITLE LETTERING'
    if name == 'font': return 'FONT (2 COLOURS)'
    return name.upper()

SECTIONS = [
    ('DOUG (PLAYER)  8X8', spr, [n for n in spr.names if n.startswith('doug_')], 8),
    ('VUMPIRE (VAMPIRIC UMPIRE)  8X8', spr, [n for n in spr.names if n.startswith('grub_')], 8),
    ('HEATER (FLAMING FASTBALL)  8X8', spr, [n for n in spr.names if n.startswith('emb_')], 8),
    ('BASEBALL BAT (WINGED BASEBALL)  12X8', spr, ['bat0', 'bat1'], 8),
    ('GROUNDSKEEPER (HARMLESS)  8X8', spr, [n for n in spr.names if n.startswith('gk_')], 8),
    ('MAD SCOTT (FINAL BOSS)  16X16', spr2, [n for n in spr2.names if n.startswith('mascot_') and not n.startswith('mascotinf')], 6),
    ('HOME PLATE (FALLING HAZARD)  8X8', spr, ['rock', 'rockw0', 'rockw1', 'rockc0', 'rockc1'], 8),
    ('EFFECTS AND MARKERS', spr, ['flame0', 'flame1', 'burst0', 'burst1', 'burst2', 'burst3', 'tomb', 'life'], 6),
    ('STRIKE MARKS  X1 WHITE / X2 YELLOW / X3 RED', spr, [n for n in spr.names if n.startswith('mark_')], 8),
    ('TUNNEL WALL TILES  8X8 EACH', spr, ['tunnels'], 6),
    ('TITLE LETTERING', spr, ['logo'], 5),
    ('FONT  3X5 GLYPHS, CREAM AND GOLD', spr, ['font'], 5),
]

def build_sheet():
    W = 1500
    c = Canvas(W, 6000)
    y = 24
    c.text(24, y, 'DUG OUT  SPRITE SHEET', (255, 224, 160), 4); y += 46
    c.text(24, y, 'GAMETANK  128X128 SCREEN  256 COLOUR PALETTE  ALL SPRITES SHOWN AT INTEGER ZOOM  CHECKERBOARD = TRANSPARENT', (150, 150, 190), 2); y += 34
    for title, sheet, names, scale in SECTIONS:
        y += 14
        c.rect(24, y, W - 48, 3, (137, 198, 184)); y += 12
        c.text(24, y, title, (255, 224, 160), 3); y += 34
        x, rowh = 24, 0
        for n in names:
            sx, sy, w, h = sheet.names[n]
            cw = max(w * scale, c.text_w(pretty(n), 2)) + 22
            if x + cw > W - 24:
                x, y, rowh = 24, y + rowh + 16, 0
            c.text(x, y, pretty(n), (170, 170, 210), 2)
            c.sprite(sheet, sx, sy, w, h, x, y + 18, scale)
            x += cw
            rowh = max(rowh, 18 + h * scale + 10)
        y += rowh + 14
    c.h = y + 20
    c.px = c.px[:c.h]
    c.save(os.path.join(OUT, 'DugOut-SpriteSheet.png'))

def build_palette():
    seen = {}
    for k, v in C.items():
        idx = P[k]
        seen.setdefault(idx, []).append(k)
    items = sorted(seen.items(), key=lambda kv: kv[0])
    cols = 6; cw, ch = 240, 84
    rows = (len(items) + cols - 1) // cols
    c = Canvas(cols * cw + 24, rows * ch + 90)
    c.text(24, 20, 'DUG OUT  COLOURS IN USE', (255, 224, 160), 3)
    lines = ['Dug Out colours (GameTank palette index, RGB as displayed, hex, names used in the art scripts)', '']
    for n, (idx, names) in enumerate(items):
        rgb = tuple(PAL[idx]); hexs = '#%02X%02X%02X' % rgb
        x = 24 + (n % cols) * cw; y = 70 + (n // cols) * ch
        c.rect(x, y, 56, 56, rgb)
        c.text(x + 66, y + 2, hexs, (232, 210, 160), 2)
        c.text(x + 66, y + 22, 'INDEX %d' % idx, (150, 150, 190), 2)
        c.text(x + 66, y + 42, names[0].upper()[:14], (170, 170, 210), 2)
        lines.append('%3d  %s  %s' % (idx, hexs, ', '.join(names)))
    c.save(os.path.join(OUT, 'palette.png'))
    open(os.path.join(OUT, 'palette.txt'), 'w').write('\n'.join(lines) + '\n')

build_sheet()
build_palette()

# full-screen art pages and the baked dirt field (exact 128x128 pixels, at 1x and 6x)
save_indexed(g['END'].px, os.path.join(OUT, 'screens', 'ending_victory_128.png'), 1)
save_indexed(g['END'].px, os.path.join(OUT, 'screens', 'ending_victory_x6.png'), 6)
save_indexed(g['OV'].px, os.path.join(OUT, 'screens', 'game_over_128.png'), 1)
save_indexed(g['OV'].px, os.path.join(OUT, 'screens', 'game_over_x6.png'), 6)
save_indexed(g['bg'].px, os.path.join(OUT, 'screens', 'dirt_field_and_depth_gauges_128.png'), 1)
save_indexed(g['bg'].px, os.path.join(OUT, 'screens', 'dirt_field_and_depth_gauges_x6.png'), 6)
# raw sprite pages
for nm, sh in (('sprites_main', spr), ('sprites_boss', spr2)):
    save_indexed(sh.px, os.path.join(OUT, 'raw', nm + '_128.png'), 1)
    save_indexed(sh.px, os.path.join(OUT, 'raw', nm + '_x8.png'), 8)
print('reference written to', OUT)
