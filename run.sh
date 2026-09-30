#!/bin/sh
# Build Dug Out and launch it in the (local) GameTank emulator.
set -e
cd "$(dirname "$0")"
make
exec ../GameTankEmulator/bin/GameTankEmulator bin/dugout.gtr
