#!/usr/bin/env python3
"""Cartridge label template + placeholder mock-up (450x488 px = 1.5in x 1 5/8in @ 300 DPI)."""
import os, runpy, struct, subprocess, sys, zlib
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.abspath(sys.argv[1])
SHOT = sys.argv[2]
g = runpy.run_path(os.path.join(HERE, 'make_assets.py'))
G = g['G']
W, H, BAND = 450, 488, 150

def blank(c): return [[c] * W for _ in range(H)]
def rect(px, x, y, w, h, c):
    for j in range(max(0, y), min(H, y + h)):
        for i in range(max(0, x), min(W, x + w)):
            px[j][i] = c
def text(px, x, y, s, c, scale):
    for ch in s.upper():
        if ch in G:
            bits = G[ch]
            for j in range(5):
                for k in range(3):
                    if bits[j * 3 + k] == '1':
                        rect(px, x + k * scale, y + j * scale, scale, scale, c)
        x += 4 * scale
def tw(s, scale): return len(s) * 4 * scale - scale
def center(px, y, s, c, scale): text(px, (W - tw(s, scale)) // 2, y, s, c, scale)
def save(px, path):
    raw = bytearray()
    for row in px: raw += b'\x00' + b''.join(bytes(p) for p in row)
    def chunk(t, d):
        cc = struct.pack('>I', len(d)) + t + d
        return cc + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    ppm = 11811   # 300 DPI
    open(path, 'wb').write(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', W, H, 8, 2, 0, 0, 0))
                           + chunk(b'pHYs', struct.pack('>IIB', ppm, ppm, 1)) + chunk(b'IDAT', zlib.compress(bytes(raw), 9)) + chunk(b'IEND', b''))

# ---- 1. template with guides
t = blank((236, 236, 236))
rect(t, 0, 0, W, BAND, (0, 0, 0))
center(t, 30, 'TITLE TEXT', (255, 255, 255), 8)
center(t, 84, 'THIS BAND FOLDS OVER', (150, 150, 150), 3)
center(t, 106, 'THE TOP OF THE CART', (150, 150, 150), 3)
center(t, 126, '(EXACT FOLD LINE: ASK FOR THE TEMPLATE)', (110, 110, 110), 2)
for x in range(0, W, 10): rect(t, x, BAND, 5, 2, (220, 40, 40))       # scribe / fold line
rect(t, 0, BAND + 3, W, 1, (200, 200, 200))
center(t, BAND + 130, 'COVER ART', (90, 90, 90), 10)
center(t, BAND + 190, '450 X 338 PX', (110, 110, 110), 4)
center(t, BAND + 226, 'FRONT OF THE CARTRIDGE', (110, 110, 110), 3)
rect(t, 0, 0, W, 3, (255, 0, 0)); rect(t, 0, H - 3, W, 3, (255, 0, 0)); rect(t, 0, 0, 3, H, (255, 0, 0)); rect(t, W - 3, 0, 3, H, (255, 0, 0))
center(t, H - 44, '450 X 488 PX  300 DPI', (255, 0, 0), 3)
center(t, H - 24, '1.5 X 1.625 INCHES', (255, 0, 0), 3)
save(t, os.path.join(OUT, 'cartridge_label_TEMPLATE.png'))

# ---- 2. placeholder mock-up: in-game screenshot in the art area, pixel title in the band
bmp = '/tmp/label_shot.bmp'
subprocess.run(['sips', '-z', '387', '450', SHOT, '--out', '/tmp/label_shot_a.png'], capture_output=True)
subprocess.run(['sips', '-c', '338', '450', '--cropOffset', '20', '0', '/tmp/label_shot_a.png', '--out', '/tmp/label_shot_b.png'], capture_output=True)
subprocess.run(['sips', '-s', 'format', 'bmp', '/tmp/label_shot_b.png', '--out', bmp], capture_output=True)
d = open(bmp, 'rb').read()
off = struct.unpack('<I', d[10:14])[0]; w, h = struct.unpack('<ii', d[18:26]); bpp = struct.unpack('<H', d[28:30])[0] // 8
row = (w * bpp + 3) & ~3; td = h < 0; h = abs(h)
m = blank((0, 0, 0))
for y in range(min(h, H - BAND)):
    yy = y if td else h - 1 - y
    r = d[off + yy * row: off + yy * row + w * bpp]
    for x in range(min(w, W)):
        m[BAND + y][x] = (r[x * bpp + 2], r[x * bpp + 1], r[x * bpp])
center(m, 26, 'DUG OUT', (255, 236, 190), 12)
center(m, 104, 'PLACEHOLDER LAYOUT ONLY', (130, 130, 150), 3)
save(m, os.path.join(OUT, 'cartridge_label_PLACEHOLDER_mockup.png'))
print('label files written')
