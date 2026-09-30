#!/usr/bin/env python3
"""
Regression harness for the code split.
  baseline.py record <name> <rom> <map>   run every scenario against a ROM, keep peeks + screenshots in /tmp/baseline/<name>
  baseline.py compare <a> <b>             report every scenario whose screenshots or peeked values differ
Build both ROMs with -DFIXED_SEED so the caves are identical (see tests/regress.sh).
"""
import glob, hashlib, os, re, shutil, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = '/tmp/baseline'
SKIP = {'s_soak', 's_layout'}          # soak is timing-dependent noise, layout depends on the seed on purpose

def scenarios():
    return sorted(os.path.basename(f)[:-4] for f in glob.glob(os.path.join(HERE, 's_*.txt')) if os.path.basename(f)[:-4] not in SKIP)

def record(name, rom, mp):
    base = os.path.join(OUT, name)
    shutil.rmtree(base, ignore_errors=True)
    for sc in scenarios():
        d = os.path.join(base, sc); os.makedirs(d)
        for f in glob.glob('/tmp/dd_*.bmp'): os.remove(f)
        if os.path.exists(rom[:-4] + '.xor'): os.remove(rom[:-4] + '.xor')     # the saved high score must not leak between runs
        env = dict(os.environ, GT_ROM=rom, GT_MAP=mp)
        r = subprocess.run([sys.executable, os.path.join(HERE, 'drive.py'), os.path.join(HERE, sc + '.txt')], env=env, capture_output=True, text=True)
        peeks = [re.sub(r'^(PEEK f\d+) [0-9A-F]{4}:', r'\1', l) for l in r.stdout.splitlines() if l.startswith('PEEK')]
        open(os.path.join(d, 'peeks.txt'), 'w').write('\n'.join(peeks) + '\n')
        for f in glob.glob('/tmp/dd_*.bmp'):
            shutil.copy(f, d)
        print('recorded', sc, len(peeks), 'peeks', len(glob.glob(d + '/*.bmp')), 'shots')

def compare(cand, *bases):
    """Every screenshot and peek line of the candidate must equal that of at least one baseline run
    (a few scenarios are not repeatable even with the same ROM, so two baseline runs are kept)."""
    bad = 0
    def shots(d):
        return {os.path.basename(f): hashlib.md5(open(f, 'rb').read()).hexdigest() for f in glob.glob(d + '/*.bmp')}
    for sc in scenarios():
        dc = os.path.join(OUT, cand, sc)
        pc, fc = open(dc + '/peeks.txt').read(), shots(dc)
        why = []
        for b in bases:
            db = os.path.join(OUT, b, sc)
            fb = shots(db)
        pk = [open(os.path.join(OUT, b, sc, 'peeks.txt')).read() for b in bases]
        if pc not in pk: why.append('peeks')
        for name in sorted(fc):
            if not any(shots(os.path.join(OUT, b, sc)).get(name) == fc[name] for b in bases):
                why.append(name)
        if why:
            bad += 1; print('DIFF', sc, ', '.join(why))
        else:
            print('same', sc, len(fc), 'shots')
    print('%d scenario(s) differ' % bad)
    sys.exit(1 if bad else 0)

if __name__ == '__main__':
    if sys.argv[1] == 'record': record(sys.argv[2], sys.argv[3], sys.argv[4])
    elif sys.argv[1] == 'compare': compare(sys.argv[2], *sys.argv[3:])
