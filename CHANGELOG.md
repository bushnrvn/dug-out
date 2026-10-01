# Changelog

Versions follow MAJOR.MINOR.PATCH. The current version is in `VERSION`. Each release is a git tag (`v1.0.0`) with the ROM in `releases/`.

## 1.3.1
* Fix: the on-screen touch controls in the web build now work on iOS Safari. Taps were read one row off, and sliding between buttons or interrupted touches could leave a direction stuck.
* The ROM is unchanged (`releases/dugout-1.3.0.gtr`); only the web build in `docs/` changed.

## 1.3.0
* Scoring: tunnelling pays 10, 20, 30 or 40 points per block, matching the four depth bands that enemy kills use. The score now keeps a tens digit.
* The Groundskeeper takes back exactly what a block paid when it rakes the block shut. Blocks Doug did not dig (the enemy pockets, or tunnels the boss smashed) cost nothing, and the score never drops below zero.
* Groundskeepers now count toward clearing the inning: strike them out (or crush them) like every other enemy.
* Code split: the scenes and the enemy code move into their own code banks (`PROG1`, `PROG2`), leaving room for new features.
* Fix: the vsync counter no longer loses ticks while the draw queue's RAM bank is mapped, so frame timing and music tempo are exact on busy screens.
* ROM: `releases/dugout-1.3.0.gtr`. The web build in `docs/` is rebuilt with it.

## 1.2.1
* Fix: cave layouts were only shuffled between ten fixed slots. Each pocket now gets its own random row, width and column, and some get a shaft.
* Cave layouts are still seeded per game, from `new_game()`, so starting from the title or the attract screen both give new caves.
* Removed a debug counter and redundant random-number churn to make room.
* ROM: `releases/dugout-1.2.1.gtr`. The web build in `docs/` is rebuilt with it.

## 1.2.0
* Cave layouts are random every game (seeded from when you press Start) instead of the same for each inning.
* Baseball bats get faster in later innings.
* Tooling: `tools_py/art_kit.py` builds an artist kit and imports redrawn sprite sheets (`art_custom/`), and `tests/` has Heater fireball checks.
* ROM: `releases/dugout-1.2.0.gtr`. The web build in `docs/` is rebuilt with it.

## 1.1.0
* Heaters: shorter wind-up before the fire, faster and more frequent fire blasts, and two fireballs that orbit each Heater and kill on touch.
* Enemy paths are less predictable: walking enemies aim a few cells off the player and turn at random more often.
* ROM: `releases/dugout-1.1.0.gtr`. The web build in `docs/` is rebuilt with it.

## 1.0.1
* Victory screen: "NINE INNINGS COMPLETE" and "NEW BEST SCORE!" now sit on a solid dark plate so they are readable on an LCD. Nothing else changed.
* ROM: `releases/dugout-1.0.1.gtr`. The web build in `docs/` is rebuilt with it.

## 1.0.0
* First release: nine innings, Vumpires, Heaters, Baseball Bats, Groundskeepers, and the Mad Scott boss.
* High score saved to cartridge flash.
* Web build in `docs/`, ROM in `releases/dugout-1.0.0.gtr`.
