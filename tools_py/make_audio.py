#!/usr/bin/env python3
"""
Dug Out audio generator: .sfx frame data + MIDI songs (both consumed by the SDK's
FM audio coprocessor pipeline).

SFX format (see src/gt/audio/music.c tick_music):
    byte 0      : number of frames N (60 Hz)
    byte 1      : feedback register value (128 + 8*fb)
    N x 8 bytes : amp[0..3] (0..15) , note[0..3]   (per FM operator; op3 = carrier)
"""
import os, math, struct, json

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
OUT = os.path.join(ROOT, 'assets', 'audio')
os.makedirs(OUT, exist_ok=True)

def clamp(v, lo, hi):
    return max(lo, min(hi, int(round(v))))

def sfx(name, frames, fb=0):
    """frames: list of (carrier_amp, carrier_note, mod_amp, mod_note)"""
    data = bytearray([len(frames), 128 + 8 * fb])
    for ca, cn, ma, mn in frames:
        amps = [clamp(ma, 0, 15), 0, 0, clamp(ca, 0, 15)]
        notes = [clamp(mn, 12, 100), 40, 40, clamp(cn, 12, 100)]
        data += bytes(amps + notes)
    open(os.path.join(OUT, name + '.sfx'), 'wb').write(bytes(data))

def sweep(n, n0, n1, a0, a1, m0=0, m1=0, moff=12, vib=0):
    fr = []
    for i in range(n):
        t = i / max(1, n - 1)
        note = n0 + (n1 - n0) * t + (vib * math.sin(i * 1.3))
        fr.append((a0 + (a1 - a0) * t, note, m0 + (m1 - m0) * t, note + moff))
    return fr

sfx('dig',     sweep(4, 40, 34, 7, 1))
sfx('shoot',   sweep(8, 62, 86, 6, 2, 5, 1))
sfx('pump1',   sweep(7, 58, 62, 9, 1, 4, 0))
sfx('pump2',   sweep(7, 63, 68, 10, 1, 5, 0))
sfx('pump3',   sweep(7, 69, 75, 11, 1, 6, 0))
sfx('pop',     sweep(16, 78, 30, 13, 0, 14, 0, moff=7, vib=3), fb=6)
sfx('fall',    sweep(22, 88, 52, 5, 4, 2, 2))
sfx('thud',    sweep(11, 34, 22, 14, 0, 10, 0, moff=5), fb=7)
sfx('die',     sweep(44, 74, 38, 11, 2, 6, 0, moff=7, vib=4), fb=2)
sfx('flame',   sweep(26, 30, 26, 8, 3, 12, 6, moff=1, vib=6), fb=8)
sfx('squash',  sweep(12, 52, 28, 12, 0, 8, 0, moff=5), fb=5)
sfx('ready',   [(10, 72, 3, 84)] * 5 + [(10, 79, 3, 91)] * 5 + [(11, 84, 3, 96)] * 10 + sweep(8, 84, 84, 10, 0))
sfx('oneup',   [(9, n, 2, n + 12) for n in (72, 76, 79, 84) for _ in range(4)])
sfx('start',   [(9, n, 2, n + 12) for n in (60, 64, 67, 72, 67, 72, 76, 79) for _ in range(3)])

# ------------------------------------------------------------------ MIDI --
PPQ = 96
def vlq(n):
    out = [n & 0x7F]
    n >>= 7
    while n:
        out.append((n & 0x7F) | 0x80)
        n >>= 7
    return bytes(reversed(out))

def write_mid(name, bpm, events):
    """events: list of (tick, order, status, a, b)"""
    events = sorted(events, key=lambda e: (e[0], e[1]))
    trk = bytearray()
    trk += b'\x00\xff\x51\x03' + struct.pack('>I', int(60000000 / bpm))[1:]
    last = 0
    for tick, _, status, a, b in events:
        trk += vlq(tick - last) + bytes([status, a, b])
        last = tick
    trk += b'\x00\xff\x2f\x00'
    hdr = b'MThd' + struct.pack('>IHHH', 6, 0, 1, PPQ)
    open(os.path.join(OUT, name + '.mid'), 'wb').write(hdr + b'MTrk' + struct.pack('>I', len(trk)) + bytes(trk))

def note_events(ch, seq, vel=100, gate=0.9):
    """seq: list of (midi_note or None, length_in_eighths); returns events"""
    ev, t = [], 0
    eighth = PPQ // 2
    for n, ln in seq:
        d = ln * eighth
        if n is not None:
            ev.append((t, 1, 0x90 | ch, n, vel))
            ev.append((t + max(1, int(d * gate)), 0, 0x80 | ch, n, 0))
        t += d
    return ev, t

def loop_to(ev_len, times):
    pass

def repeat(seq, k):
    return seq * k

# ---------------------------------------------------------------------------
# Music: transcriptions of PUBLIC-DOMAIN classical compositions (all composers
# died 100+ years ago). Notes were typed in from the scores, not from any
# recording or third-party MIDI file.
#   theme  - Grieg, "In the Hall of the Mountain King" (Peer Gynt, 1875), full piece,
#            transcribed from Grieg's piano-solo edition (Peters 9563, on IMSLP)
#   title  - "Take Me Out to the Ball Game" (1908): verse + full chorus, transcribed from the York Music Co. score
#   clear  - the traditional bugle call "Charge!"
#   over   - a descending 'sad trombone' figure
# ---------------------------------------------------------------------------
def mk(ev_list, bpm, name):
    ev = []
    for chn, seq, gate in ev_list:
        e, _ = note_events(chn, seq, 100, gate)
        ev += e
    write_mid(name, bpm, ev)

# --- Mountain King: transcribed from Grieg's own piano-solo edition (Peters 9563, IMSLP) ------
# Key B minor, 4/4, quarter = 138. Melodic cells (semitones above the section's base "B"):
#   a  B C# D E F# D F#(q)         b  E# C# E#(q) E C E(q)  (the echo, a half-step lower)
#   c  B C# D E F# D F# B(high)    d  A F# D F# A(half)
#   x1 F# G# A# B C# A# C#(q)      x2 D A# D(q) C# A# C#(q)   x3 D A# D(q) C#(half)
CELL = {
    'a':  [(0,1),(2,1),(3,1),(5,1),(7,1),(3,1),(7,2)],
    'b':  [(6,1),(2,1),(6,2),(5,1),(1,1),(5,2)],
    'c':  [(0,1),(2,1),(3,1),(5,1),(7,1),(3,1),(7,1),(12,1)],
    'd':  [(10,1),(7,1),(3,1),(7,1),(10,4)],
    'x1': [(0,1),(2,1),(4,1),(5,1),(7,1),(4,1),(7,2)],      # relative to F#
    'x2': [(8,1),(4,1),(8,2),(7,1),(4,1),(7,2)],
    'x3': [(8,1),(4,1),(8,2),(7,4)],
}
def cell(name, base):
    return [(base + n, d) for n, d in CELL[name]]
BASS_Q = {  # (root, fifth-ish) quarters, nominal slapbass pitches
    'a': [(59,2),(66,2),(59,2),(66,2)], 'b': [(59,2),(66,2),(59,2),(66,2)],
    'c': [(59,2),(66,2),(59,2),(66,2)], 'd': [(59,2),(66,2),(59,2),(66,2)],
    'x1': [(54,2),(61,2),(54,2),(61,2)], 'x2': [(59,2),(58,2),(54,2),(61,2)], 'x3': [(59,2),(58,2),(54,2),(61,2)],
}
BASS_E = {  # driving eighths for the loud sections
    'a': [(59,1),(57,1),(55,1),(54,1)] * 2, 'b': [(59,1),(57,1),(55,1),(54,1)] * 2,
    'c': [(59,1),(57,1),(55,1),(54,1)] * 2, 'd': [(59,1),(66,1),(64,1),(61,1)] * 2,
    'x1': [(54,1),(61,1),(60,1),(61,1)] * 2, 'x2': [(59,1),(58,1),(59,1),(61,1)] * 2, 'x3': [(59,1),(58,1),(59,1),(61,1)] * 2,
}
HARM = {  # offbeat chord tones for the counter voice (B minor)
    'a': (66, 71), 'b': (65, 70), 'c': (66, 71), 'd': (62, 69),
    'x1': (70, 73), 'x2': (70, 74), 'x3': (70, 74),
}
mel, bass, snr, hrm = [], [], [], []
def section(cells, base, bassmap, snare=False, harm=False, xbase=None):
    for c in cells:
        b0 = (xbase if (c.startswith('x') and xbase is not None) else base)
        mel.extend(cell(c, b0))
        bass.extend(bassmap[c])
        if snare:
            snr.extend([(None,2),(60,1),(None,1),(None,2),(60,1),(None,1)])
        else:
            snr.extend([(None,8)])
        if harm:
            h1, h2 = HARM[c]
            hrm.extend([(None,1),(h1,1),(None,1),(h2,1),(None,1),(h1,1),(None,1),(h2,1)])
        else:
            hrm.extend([(None,8)])
UNIT = ['a','b','c','d']
X = ['x1','x2','x1','x3']
# fermata pickup
mel.append((59, 8)); bass.append((None, 8)); snr.append((None, 8)); hrm.append((None, 8))
section(UNIT, 47, BASS_Q)                          # pp, low
section(UNIT, 59, BASS_Q)                          # an octave up
section(X, 47, BASS_Q, xbase=54)                   # the F#-major detour
section(X, 47, BASS_Q, xbase=54)
section(UNIT, 47, BASS_Q, snare=True)              # marcato again
section(UNIT, 59, BASS_Q, snare=True)
section(['c','d','a','b','c','d'], 59, BASS_Q, snare=True, harm=True)   # treble, broken-chord LH
section(X, 59, BASS_Q, snare=True, harm=True, xbase=66)                 # poco a poco cresc. e stretto
section(X, 59, BASS_Q, snare=True, harm=True, xbase=66)
section(UNIT + UNIT, 59, BASS_E, snare=True, harm=True)                 # mf, eighth-note bass
section(UNIT + UNIT, 71, BASS_E, snare=True, harm=True)                 # ff piu vivo, 8va
section(X + X, 71, BASS_E, snare=True, harm=True, xbase=78)             # sempre stretto al fine
section(UNIT, 71, BASS_E, snare=True, harm=True)
# coda: fz stabs, the run, and the closing figure
for _ in range(2):
    for _ in range(2):
        mel.append((None,2)); mel.append((83,2)); mel.append((None,4))
        bass.append((59,2)); bass.append((None,6)); snr.append((None,2)); snr.append((60,2)); snr.append((None,4))
        hrm.append((None,2)); hrm.append((74,2)); hrm.append((None,4))
    mel.extend(cell('a', 71)); bass.extend(BASS_E['a']); snr.append((None,8)); hrm.append((None,8))
    mel.extend([(82,1),(78,1),(82,1),(86,1),(None,4)]); bass.extend([(59,2),(66,2),(59,2),(66,2)]); snr.append((None,8)); hrm.append((None,8))
for _ in range(3):     # pp tremolo on D
    mel.extend([(74,1)] * 8); bass.append((59,8)); snr.append((None,8)); hrm.append((None,8))
mel.extend([(74,1)] * 8); bass.append((59,8)); snr.append((None,8)); hrm.append((None,8))
mel.append((None,8)); bass.extend([(59,1),(66,1)] * 4); snr.append((None,8)); hrm.append((None,8))
mel.extend([(83,2),(None,6)]); bass.extend([(47+12,2),(None,6)]); snr.extend([(60,2),(None,6)]); hrm.extend([(74,2),(None,6)])
mk([(0, mel, 0.55), (1, bass, 0.75), (2, snr, 0.9), (3, hrm, 0.6)], 138, 'theme')

# --- Take Me Out to the Ball Game (title) - transcribed from the 1908 York Music Co. score ----
# D major, 3/4 "Tempo di Valse". Bars are 6 eighths. The title loop is just the famous chorus (32 bars). Pitches are MIDI (D4=62, A4=69, B4=71, D5=74).
VERSE = [
    [(69,4),(69,2)], [(69,2),(67,2),(66,2)], [(69,4),(69,2)], [(69,6)],
    [(71,4),(71,2)], [(71,2),(69,2),(67,2)], [(71,4),(71,2)], [(71,6)],
    [(73,4),(73,2)], [(73,2),(74,2),(76,2)], [(71,4),(71,2)], [(71,2),(73,2),(76,2)],
    [(71,6)], [(71,2),(73,2),(76,2)], [(69,6)], [(69,4),(None,2)],
]
VERSE_CH = ['D','D','D','D','G','G','G','G','A','A','G','G','G','A','D','D']
MOTIF = [[(62,4),(74,2)], [(71,2),(69,2),(66,2)]]          # "Take me out to the ball"
CHORUS = [
    MOTIF[0], MOTIF[1], [(69,6)], [(64,6)],                  # Take me out to the ball game,
    MOTIF[0], MOTIF[1], [(69,6)], [(69,4),(None,2)],         # Take me out with the crowd
    [(71,2),(70,2),(71,2)], [(66,2),(67,2),(69,2)], [(71,4),(67,2)], [(64,6)],   # Buy me some peanuts and cracker jack,
    [(71,4),(71,2)], [(71,2),(73,2),(74,2)],                 # I don't care if I
    [(76,2),(73,2),(71,2)], [(69,2),(66,2),(64,2)],          # never get back,
    MOTIF[0], MOTIF[1], [(69,6)], [(64,4),(64,2)],           # Let me root, root, root for the home team, if
    [(62,4),(64,2)], [(66,2),(67,2),(69,2)], [(71,6)],       # they don't win it's a shame,
    [(71,2),(71,2),(73,2)], [(74,6)], [(74,6)],              # for it's one, two,
    [(74,2),(73,2),(71,2)], [(69,2),(68,2),(69,2)],          # three strikes you're out, at the
    [(71,6)], [(73,6)], [(74,4),(None,2)],                   # old ball game
]
CHORUS_CH = ['D','D','D','A', 'D','D','D','D', 'G','D','G','A', 'G','G','A','D',
             'D','D','D','A', 'D','D','G','G', 'D','D','G','A', 'G','A','D']
ROOT = {'D': 62, 'G': 55, 'A': 57}
TONES = {'D': (66, 69), 'G': (71, 74), 'A': (73, 76)}
tm, tb, tc = [], [], []
for bars, chs in ((CHORUS, CHORUS_CH),):   # just the chorus: a clean seamless loop
    for bar, ch in zip(bars, chs):
        tm.extend(bar)
        tb.extend([(ROOT[ch], 2), (None, 4)])                           # oom
        t1, t2 = TONES[ch]
        tc.extend([(None, 2), (t1, 2), (t2, 2)])                        # pah pah
mk([(0, tm, 0.85), (1, tb, 0.7), (3, tc, 0.5)], 180, 'title')

# --- bugle "Charge!" (round clear; traditional, public domain) ---------------------
chg = [(67,1),(72,1),(76,1),(79,3),(76,1),(79,5)]
chg_bass = [(48,4),(55,4),(48,4)]
mk([(0, chg, 0.8), (1, chg_bass, 0.7)], 170, 'clear')

# --- sad trombone (game over): "wah wah wah waaah" ----------------------------------
wah = [(58,2),(57,2),(56,2),(55,10)]
wah_bass = [(46,8),(43,8)]
mk([(0, wah, 0.95), (1, wah_bass, 0.9)], 100, 'over')

# per-file config: piano melody, slapbass, snare, piano
json.dump({f: {"instruments": [1, 4, 5, 1]} for f in ('theme.mid', 'title.mid', 'clear.mid', 'over.mid')},
          open(os.path.join(OUT, 'asset.cfg'), 'w'), indent=1)
print('audio ok')
