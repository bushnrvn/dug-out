THIRD-PARTY NOTICES
===================
This page runs "Dug Out" inside a WebAssembly build of the GameTank Emulator.

GameTank Emulator - MIT License, Copyright (c) 2020 Clyde Shaffer
  https://github.com/clydeshaffer/GameTankEmulator
  Compiled to WebAssembly with Emscripten (index.js contains the emulator and the game ROM).
  Full license text: GameTankEmulator-MIT.txt

Components of the emulator:
  6502 CPU core (Gianluca Ghettini, fork with 65C02 opcodes) ....... MIT   (mos6502-MIT.txt)
  Dear ImGui (Omar Cornut) ......................................... MIT   (DearImGui-MIT.txt)
  ImPlot (Evan Pezent) ............................................. MIT   (ImPlot-MIT.txt)
  toml++ (Mark Gillard) ............................................ MIT
  stb_image (Sean Barrett) ......................................... public domain
  whereami (Gregory Pakosz) ........................................ WTFPL / MIT dual
  SDL2 port bundled with Emscripten ................................ zlib
  Emscripten runtime ............................................... MIT / University of Illinois-NCSA

The game itself, "Dug Out", is built with the GameTank SDK and cc65.
