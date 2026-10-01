# Changelog

Versions follow MAJOR.MINOR.PATCH. The current version is in `VERSION`. Each release is a git tag (`v1.0.0`) with the ROM in `releases/`.

## 1.4.0
* Heaters: the flame now hurts only where it is drawn (before, it reached 6 pixels past its end and caught the edge of Doug's sprite), and one fireball circles each Heater instead of two, with its hit box matching.
* A stunned enemy now kills Doug if he touches it (Vumpires, Heaters, bats and Mad Scott; the Groundskeeper is still no threat to Doug's life). Before, Doug passed straight through a stunned one.
* Baseball bats leave their pocket sooner at the start of an inning (about 3.3 seconds instead of 5).
* An extra life now comes every 10,000 points instead of every 30,000.
* When only two enemies are left they run for the top along the open tunnels (bats fly straight up through the dirt, and Groundskeepers and Mad Scott never run). A sealed cave stays sealed. One that makes it out costs the points it would have paid at its depth and counts as gone.
* The Groundskeeper now digs as it moves: it tunnels through the dirt to the nearest sealed cave, then the next, opening them up. It still rakes shut the tunnels Doug dug (and takes back their points), but never a cave or a tunnel of its own.
* Walking enemies now find the way to Doug along the open tunnels (a breadth first search, around corners and dead ends) instead of only steering toward him, so once a path is open they come for him. With no open path they stay in their caves.
* Doug and the walking enemies (Vumpires, Groundskeepers, Mad Scott; not Heaters or bats) nod their heads, a pixel down, in time with the music while they move: on each snare hit and on the beat between. They stop when they stand still.
* New: a gold bar lies at a random spot in one of the enemy caves each inning. Enemies pass over it; Doug picks it up for 500 points.
* ROM: `releases/dugout-1.4.0.gtr`. The web build in `docs/` is rebuilt with it.

## 1.3.3
* A thrown ball now stops at dirt instead of flying on through it. It still gets one last chance to hit a Baseball Bat or Mad Scott sitting in the first dirt cell at a tunnel mouth, so bats can only be hit when they come out into the open.
* ROM: `releases/dugout-1.3.3.gtr`. The web build in `docs/` is rebuilt with it.

## 1.3.2
* A Heater's starting tunnel is now at least 4 cells wide, so there is always room to get to it and throw. Before, a Heater could start in a 2 or 3 cell pocket you could not reach safely.
* The caves change a little as a result (the same seed gives a different Heater pocket), but nothing else about the levels does.
* ROM: `releases/dugout-1.3.2.gtr`. The web build in `docs/` is rebuilt with it.

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
