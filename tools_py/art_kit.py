#!/usr/bin/env python3
"""
Artist kit for Dug Out: redraw the sprites in any pixel editor and bring them back into the game.

  python3 tools_py/art_kit.py kit <folder>
      Writes a starter kit: the current sheets as transparent PNGs, slot-guide layers, a labelled
      slot map, the slot list, and the GameTank palette as .gpl (GIMP/Aseprite) and .pal (JASC).

  python3 tools_py/art_kit.py import <sheet.png> <spr|spr2> [out.bmp]
      Checks a 128x128 PNG, snaps every colour to the GameTank palette, and writes the indexed BMP the
      build needs (default: art_custom/<sheet>.bmp, which make_assets.py copies over the generated art).

Rules the game imposes: 128x128 pixels, GameTank palette, palette index 0 = transparent, and every sprite
stays in its slot (the code finds sprites by position). See slots.json.
"""
import json, os, runpy, struct, sys, zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..'))
PAL = [tuple(c) for c in json.load(open(os.path.join(HERE, 'palette.json')))]
SLOTS_FILE = os.path.join(HERE, 'slots.json')


# ------------------------------------------------------------------ PNG io --
def png_write(path, w, h, rgba):
    raw = bytearray()
    for y in range(h):
        raw += b'\x00' + b''.join(bytes(rgba[y][x]) for x in range(w))
    def chunk(t, d):
        c = struct.pack('>I', len(d)) + t + d
        return c + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    open(path, 'wb').write(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0))
                           + chunk(b'IDAT', zlib.compress(bytes(raw), 9)) + chunk(b'IEND', b''))


def png_read(path):
    """Minimal PNG decoder (no interlace). Returns (w, h, rows of (r, g, b, a))."""
    data = open(path, 'rb').read()
    if data[:8] != b'\x89PNG\r\n\x1a\n':
        raise SystemExit('%s is not a PNG file' % path)
    pos, idat, plte, trns = 8, b'', None, None
    while pos < len(data):
        n, t = struct.unpack('>I4s', data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + n]
        pos += 12 + n
        if t == b'IHDR':
            w, h, depth, ctype, _, _, interlace = struct.unpack('>IIBBBBB', body)
        elif t == b'PLTE': plte = body
        elif t == b'tRNS': trns = body
        elif t == b'IDAT': idat += body
    if interlace:
        raise SystemExit('interlaced PNGs are not supported: re-export without interlacing')
    chans = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ctype]
    bpp = max(1, chans * depth // 8)
    stride = (w * chans * depth + 7) // 8
    raw = zlib.decompress(idat)
    rows, prev = [], bytearray(stride)
    for y in range(h):
        f = raw[y * (stride + 1)]
        line = bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        for i in range(stride):
            a = line[i - bpp] if i >= bpp else 0
            b = prev[i]
            c = prev[i - bpp] if i >= bpp else 0
            if f == 1: line[i] = (line[i] + a) & 255
            elif f == 2: line[i] = (line[i] + b) & 255
            elif f == 3: line[i] = (line[i] + ((a + b) >> 1)) & 255
            elif f == 4:
                p = a + b - c
                pa, pb, pc_ = abs(p - a), abs(p - b), abs(p - c)
                pr = a if pa <= pb and pa <= pc_ else (b if pb <= pc_ else c)
                line[i] = (line[i] + pr) & 255
        prev = line
        vals = []
        if depth == 16:
            vals = [line[i] for i in range(0, stride, 2)]
        elif depth == 8:
            vals = list(line)
        else:
            per = 8 // depth
            for byte in line:
                for k in range(per):
                    vals.append((byte >> (8 - depth * (k + 1))) & ((1 << depth) - 1))
        row = []
        for x in range(w):
            if ctype == 6: px = tuple(vals[x * 4:x * 4 + 4])
            elif ctype == 2: px = tuple(vals[x * 3:x * 3 + 3]) + (255,)
            elif ctype == 0: px = (vals[x],) * 3 + (255,)
            elif ctype == 4: px = (vals[x * 2],) * 3 + (vals[x * 2 + 1],)
            else:
                i = vals[x]
                px = tuple(plte[i * 3:i * 3 + 3]) + ((trns[i] if trns and i < len(trns) else 255),)
            row.append(px)
        rows.append(row)
    return w, h, rows


def bmp_write(path, idx):
    H, W = len(idx), len(idx[0])
    pal = b''.join(bytes([c[2], c[1], c[0], 0]) for c in PAL)
    rows = b''.join(bytes(idx[y]) for y in range(H - 1, -1, -1))
    hdr = struct.pack('<2sIHHI', b'BM', 14 + 40 + 1024 + len(rows), 0, 0, 14 + 40 + 1024)
    dib = struct.pack('<IiiHHIIiiII', 40, W, H, 1, 8, 0, len(rows), 2835, 2835, 256, 256)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    open(path, 'wb').write(hdr + dib + pal + rows)


# --------------------------------------------------------------------- kit --
def cmd_kit(out):
    os.makedirs(out, exist_ok=True)
    g = runpy.run_path(os.path.join(HERE, 'make_assets.py'))
    G = g['G']
    sheets = {'spr': g['spr'], 'spr2': g['spr2']}
    slots = {k: {n: list(v) for n, v in sh.names.items()} for k, sh in sheets.items()}
    json.dump(slots, open(SLOTS_FILE, 'w'), indent=1)
    json.dump(slots, open(os.path.join(out, 'slots.json'), 'w'), indent=1)

    for key, sh in sheets.items():
        W = H = 128
        cur = [[(0, 0, 0, 0) if sh.px[y][x] == 0 else PAL[sh.px[y][x]] + (255,) for x in range(W)] for y in range(H)]
        png_write(os.path.join(out, 'current_%s_128.png' % key), W, H, cur)
        guide = [[(0, 0, 0, 0)] * W for _ in range(H)]
        for n, (x, y, w, h) in sh.names.items():
            for i in range(w):
                for j in (0, h - 1): guide[y + j][x + i] = (255, 0, 200, 160)
            for j in range(h):
                for i in (0, w - 1): guide[y + j][x + i] = (255, 0, 200, 160)
        png_write(os.path.join(out, 'guides_%s_128.png' % key), W, H, guide)
        # labelled 8x map: slots numbered, list in slots_<sheet>.txt
        S = 8
        big = [[(30, 28, 56, 255)] * (W * S) for _ in range(H * S)]
        for y in range(H):
            for x in range(W):
                px = cur[y][x]
                c = px if px[3] else ((44, 42, 72, 255) if (x + y) & 1 else (38, 36, 66, 255))
                for b in range(S):
                    for a in range(S):
                        big[y * S + b][x * S + a] = c
        lines = ['slot  x    y    w   h   name']
        for k, (n, (x, y, w, h)) in enumerate(sh.names.items(), 1):
            lines.append('%3d  %3d  %3d  %3d %3d  %s' % (k, x, y, w, h, n))
            col = (255, 0, 200, 255)
            for i in range(w * S):
                for j in (0, h * S - 1): big[y * S + j][x * S + i] = col
            for j in range(h * S):
                for i in (0, w * S - 1): big[y * S + j][x * S + i] = col
            tx, ty = x * S + 3, y * S + 3
            for ch in str(k):
                bits = G.get(ch)
                if bits:
                    for j in range(5):
                        for i in range(3):
                            if bits[j * 3 + i] == '1':
                                for b in range(2):
                                    for a in range(2):
                                        if ty + j * 2 + b < H * S and tx + i * 2 + a < W * S:
                                            big[ty + j * 2 + b][tx + i * 2 + a] = (255, 255, 255, 255)
                tx += 8
        png_write(os.path.join(out, 'map_%s_x8.png' % key), W * S, H * S, big)
        open(os.path.join(out, 'slots_%s.txt' % key), 'w').write('\n'.join(lines) + '\n')

    with open(os.path.join(out, 'gametank.gpl'), 'w') as f:
        f.write('GIMP Palette\nName: GameTank\nColumns: 16\n#\n')
        for i, (r, gg, b) in enumerate(PAL):
            f.write('%3d %3d %3d\tindex %d%s\n' % (r, gg, b, i, ' (transparent in sprites)' if i == 0 else ''))
    with open(os.path.join(out, 'gametank.pal'), 'w') as f:
        f.write('JASC-PAL\n0100\n256\n')
        for r, gg, b in PAL: f.write('%d %d %d\n' % (r, gg, b))
    open(os.path.join(out, 'README-ART-KIT.txt'), 'w').write(KIT_README)
    print('kit written to', out)


KIT_README = """DUG OUT ART KIT

Files
  current_spr_128.png / current_spr2_128.png   the current sheets, transparent where the game is transparent
  guides_*_128.png                             slot outlines (magenta): put this on a layer above your art
  map_*_x8.png + slots_*.txt                   numbered map of every slot with its position and size
  gametank.gpl / gametank.pal                  the GameTank 256-colour palette (GIMP/Aseprite, and JASC)
  slots.json                                   the same slot list for tools

Rules
  * 128x128 pixels per sheet. spr = main sprites, tunnel tiles, font, logo. spr2 = Mad Scott.
  * Only colours from the GameTank palette. Anything else is snapped to the nearest palette colour.
  * Fully transparent pixels become palette index 0 (transparent). Partly transparent pixels below 50%
    alpha are treated as transparent. Do not use anti-aliasing or soft edges.
  * Keep every sprite inside its slot, at the same size. The game finds sprites by position.
  * Left/right frames and the 4 directions each have their own slot. Redraw all of them.

Bring art back
  python3 tools_py/art_kit.py import my_spr.png spr
  python3 tools_py/art_kit.py import my_spr2.png spr2
  (then run the asset step and make, as in the README)
The importer prints any colour it had to change and any pixel outside a slot.
"""


# ------------------------------------------------------------------ import --
_snap = {}
def nearest(rgb):
    if rgb in _snap: return _snap[rgb]
    best, bi = 1e9, 1
    for i, p in enumerate(PAL):
        if i == 0: continue                      # index 0 is transparency, never a drawn colour
        d = 0.30 * (p[0] - rgb[0]) ** 2 + 0.59 * (p[1] - rgb[1]) ** 2 + 0.11 * (p[2] - rgb[2]) ** 2
        if d < best: best, bi = d, i
    _snap[rgb] = bi
    return bi


def cmd_import(png_path, key, out=None):
    slots = json.load(open(SLOTS_FILE))
    if key not in slots:
        raise SystemExit('sheet must be one of: ' + ', '.join(slots))
    w, h, rows = png_read(png_path)
    if (w, h) != (128, 128):
        raise SystemExit('%s is %dx%d: the sheet must be exactly 128x128' % (png_path, w, h))
    exact = {}
    for i, c in enumerate(PAL):                  # some greys appear twice in the palette: keep the lowest index
        if i: exact.setdefault(tuple(c), i)
    idx, snapped, transparent = [], {}, 0
    for y in range(h):
        line = []
        for x in range(w):
            r, g, b, a = rows[y][x]
            if a < 128:
                line.append(0); transparent += 1
            elif (r, g, b) in exact:
                line.append(exact[(r, g, b)])
            else:
                line.append(nearest((r, g, b))); snapped[(r, g, b)] = snapped.get((r, g, b), 0) + 1
        idx.append(line)
    inside = [[False] * w for _ in range(h)]
    empty = []
    for n, (sx, sy, sw, sh) in slots[key].items():
        used = False
        for j in range(sh):
            for i in range(sw):
                inside[sy + j][sx + i] = True
                if idx[sy + j][sx + i]: used = True
        if not used: empty.append(n)
    stray = sum(1 for y in range(h) for x in range(w) if idx[y][x] and not inside[y][x])
    out = out or os.path.join(ROOT, 'art_custom', key + '.bmp')
    bmp_write(out, idx)
    print('wrote', out)
    print('  %d transparent pixels, %d colours used' % (transparent, len({v for r in idx for v in r if v})))
    if snapped:
        print('  WARNING: %d pixels (%d colours) were not GameTank palette colours and were snapped:' % (sum(snapped.values()), len(snapped)))
        for rgb, n in sorted(snapped.items(), key=lambda kv: -kv[1])[:8]:
            print('     #%02X%02X%02X x%d -> palette %d' % (rgb + (n, nearest(rgb))))
    if stray:
        print('  WARNING: %d drawn pixels are outside every sprite slot and will never be shown (check guides)' % stray)
    if empty:
        print('  WARNING: %d slots are completely empty: %s' % (len(empty), ', '.join(empty[:12]) + (' ...' if len(empty) > 12 else '')))
    print('Next: python3 tools_py/make_assets.py  (copies art_custom/*.bmp over the generated art), then make import && make')


if __name__ == '__main__':
    a = sys.argv[1:]
    if len(a) == 2 and a[0] == 'kit': cmd_kit(os.path.abspath(a[1]))
    elif len(a) in (3, 4) and a[0] == 'import': cmd_import(a[1], a[2], a[3] if len(a) == 4 else None)
    else: print(__doc__)
