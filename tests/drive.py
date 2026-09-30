#!/usr/bin/env python3
"""
Scripted emulator runner for Dug Out.

usage: drive.py scenario.txt [--shots]

scenario lines:
    <vframe> <BUTTONS|0>          hold buttons (UP+A, START, ...) from that frame
    <vframe> shot <name>          screenshot -> /tmp/dd_<name>.png
    <vframe> peek <symbol> [len]  print game variable(s) (symbol from link map, no leading _)
    <vframe> poke <symbol> <value> [offset]   write a byte
    <vframe> quit
"""
import os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')
EMU = os.path.join(ROOT, '..', 'GameTankEmulator', 'bin', 'GameTankEmulator')

def symbols():
    txt = open(os.environ.get('GT_MAP') or os.path.join(ROOT, 'build', 'out.map')).read()
    sec = txt[txt.index('Exports list by name'):txt.index('Exports list by value')]
    return {m.group(1): int(m.group(2), 16) for m in re.finditer(r'\b_(\w+)\s+([0-9A-F]{6})\s+\w+', sec)}

def main():
    scen = sys.argv[1]
    syms = symbols()
    out = []
    shots = []
    for line in open(scen):
        line = line.split('#')[0].strip()
        if not line:
            continue
        p = line.split()
        if len(p) >= 3 and p[1] == 'peek':
            name = p[2]
            ln = p[3] if len(p) > 3 else '1'
            addr = syms[name]
            out.append('%s peek %04X %s' % (p[0], addr, ln))
        elif len(p) >= 4 and p[1] == 'poke':
            out.append('%s poke %04X %s' % (p[0], syms[p[2]] + (int(p[4]) if len(p) > 4 else 0), p[3]))
        elif len(p) >= 3 and p[1] == 'shot':
            out.append('%s shot /tmp/dd_%s.bmp' % (p[0], p[2]))
            shots.append(p[2])
        else:
            out.append(line)
    tmp = '/tmp/dd_scenario.script'
    open(tmp, 'w').write('\n'.join(out) + '\n')
    env = dict(os.environ, GT_FAST='1', GT_SCRIPT=tmp, GT_FPS=os.environ.get('GT_FPS', ''))
    if not env['GT_FPS']:
        del env['GT_FPS']
    r = subprocess.run([EMU, os.environ.get('GT_ROM') or os.path.join(ROOT, 'bin', 'dugout.gtr')], env=env, capture_output=True, text=True, timeout=300, cwd=ROOT)
    for l in r.stdout.splitlines():
        if l.startswith('PEEK') or l.startswith('vframe'):
            print(l)
    for s in shots:
        subprocess.run(['sips', '-s', 'format', 'png', '/tmp/dd_%s.bmp' % s, '--out', '/tmp/dd_%s.png' % s], capture_output=True)

if __name__ == '__main__':
    main()
