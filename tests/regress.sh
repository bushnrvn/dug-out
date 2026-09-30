#!/bin/sh
# usage: tests/regress.sh <name>   builds a FIXED_SEED test ROM from the working tree and records it as /tmp/baseline/<name>
set -e
cd "$(dirname "$0")/.."
rm -f build/src/main.o build/src/main.si build/src/main.s bin/dugout.gtr
make CFLAGS='-t none -Osr --cpu 65c02 --codesize 500 --static-locals -I src/gt -g -DFIXED_SEED=4661' >/dev/null
mkdir -p /tmp/baseline_rom
cp bin/dugout.gtr /tmp/baseline_rom/$1.gtr
cp build/out.map /tmp/baseline_rom/$1.map
rm -f build/src/main.o build/src/main.si build/src/main.s bin/dugout.gtr
make >/dev/null
python3 tests/baseline.py record $1 /tmp/baseline_rom/$1.gtr /tmp/baseline_rom/$1.map
