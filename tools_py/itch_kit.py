#!/usr/bin/env python3
"""
Turns emulator screenshots into crisp itch.io page assets, using only the standard library.

  python3 tools_py/itch_kit.py native <emulator.bmp> <out.png>            128x128 native frame
  python3 tools_py/itch_kit.py scale  <emulator.bmp> <out.png> <factor>   native frame, integer nearest-neighbour zoom

Library use: read_shot() returns the 128x128 game frame as RGB rows; scale(), crop(), png_write() do the rest.
The emulator window is wider than the game, with the 128x128 frame drawn at exactly 4x in the middle, so the
crop position is found by checking which offset gives perfectly uniform 4x4 blocks.
"""
import struct, sys, zlib


def read_bmp(path):
    d = open(path, 'rb').read()
    off = struct.unpack('<I', d[10:14])[0]
    w, h = struct.unpack('<ii', d[18:26])
    bpp = struct.unpack('<H', d[28:30])[0]
    bytes_pp = bpp // 8
    stride = (w * bytes_pp + 3) & ~3
    rows = []
    for y in range(abs(h)):
        src = (abs(h) - 1 - y) if h > 0 else y
        line = d[off + src * stride: off + src * stride + w * bytes_pp]
        rows.append([(line[x * bytes_pp + 2], line[x * bytes_pp + 1], line[x * bytes_pp]) for x in range(w)])
    return w, abs(h), rows


def read_shot(path):
    """The game frame as 128 rows of 128 (r, g, b)."""
    w, h, rows = read_bmp(path)
    scores = []
    for x0 in range(0, w - 512 + 1):
        bad = 0
        for by in range(0, 128, 9):
            for bx in range(0, 128, 9):
                p = rows[by * 4][x0 + bx * 4]
                if any(rows[by * 4 + j][x0 + bx * 4 + i] != p for i in (0, 3) for j in (0, 3)):
                    bad += 1
        scores.append((bad, abs(x0 - (w - 512) / 2), x0))
    x0 = min(scores)[2]                  # most uniform 4x4 blocks, and of those the one nearest the window centre
    return [[rows[y * 4 + 2][x0 + x * 4 + 2] for x in range(128)] for y in range(128)]


def scale(rows, k):
    out = []
    for row in rows:
        big = [p for p in row for _ in range(k)]
        out.extend([big] * k)
    return out


def crop(rows, x, y, w, h):
    return [row[x:x + w] for row in rows[y:y + h]]


def png_write(path, rows):
    h, w = len(rows), len(rows[0])
    has_alpha = len(rows[0][0]) == 4
    raw = bytearray()
    for row in rows:
        raw += b'\x00' + b''.join(bytes(p) for p in row)
    def chunk(t, d):
        c = struct.pack('>I', len(d)) + t + d
        return c + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    ihdr = struct.pack('>IIBBBBB', w, h, 8, 6 if has_alpha else 2, 0, 0, 0)
    open(path, 'wb').write(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', ihdr) + chunk(b'IDAT', zlib.compress(bytes(raw), 9)) + chunk(b'IEND', b''))


if __name__ == '__main__':
    a = sys.argv[1:]
    if len(a) == 3 and a[0] == 'native':
        png_write(a[2], read_shot(a[1]))
    elif len(a) == 4 and a[0] == 'scale':
        png_write(a[2], scale(read_shot(a[1]), int(a[3])))
    else:
        print(__doc__)
