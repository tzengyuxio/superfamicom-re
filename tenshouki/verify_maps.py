#!/usr/bin/env python3
"""Check the big map (rom.Rom.map_cells, map tiles and palettes) against the game (needs Mesen 2).

The game is played to 蠣崎季広's first turn in 信長初陣; then VRAM and CGRAM are read. The terrain BG
(tilemap at VRAM word 0x5400) and the road BG (0x5800) hold the 32 x 28 cells on screen: the window position in the
150 x 65 map is searched, and every visible cell must equal the ROM tilemap. The road BG also
carries the game's windows (tiles below 435) and castle markers (tiles 736 and up); those cells are
counted apart. The map tiles in VRAM (435-735) must equal data entry 19, and colours 1-15 of CGRAM
palettes 3-5 the ROM (colour 0 is transparent; colours 4, 5, 9 and 15 of palette 5 are animated).

Usage: .venv/bin/python tenshouki/verify_maps.py [--rom ROM]
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
sys.path.insert(0, os.path.join(HERE, "tools"))
from face_capture import schedule
from mesen import SNES_CGRAM, SNES_VRAM, Mesen
from rom import DEFAULT_ROM, MAP_H, MAP_PALETTES, MAP_TILE0, MAP_TILES_ENTRY, MAP_W, Rom

INPUTS = "w1100 start w300 start w300 a w300 a w300 a w300 a w300 start w300 down*8 w30 a w300 a w600 w8400"
TILEMAPS = {0: 0x5400, 1: 0x5800}   # VRAM word address of the terrain / road BG
VISIBLE_ROWS = 28
TERRAIN_AT = [0, 0]                 # the road BG scrolls with the terrain BG
ANIMATED = {(2, 4), (2, 5), (2, 9), (2, 15)}  # (palette - 3, colour) cycled by the game; the ROM has frame 0

LUA = """
local presses={%(presses)s}
local f=0
emu.addEventCallback(function()
  local inp={}
  for _,p in ipairs(presses) do if f>=p[1] and f<p[1]+4 then inp[p[2]]=true end end
  emu.setInput(inp,0)
end, emu.eventType.inputPolled)
emu.addEventCallback(function()
  f=f+1
  if f==%(end)d then emu.breakExecution() end
end, emu.eventType.endFrame)
"""


def capture(rom_path: str) -> tuple[bytes, bytes]:
    presses = schedule(INPUTS)
    end = 10 + 120 + sum(int(st[1:]) if st.startswith("w") else 24 * int(st.partition("*")[2] or 1)
                        for st in INPUTS.split())
    with Mesen(rom_path) as m:
        m.run(LUA % {"presses": ",".join(f'{{{f},"{b}"}}' for f, b in presses), "end": end}, 300)
        return m.memory(SNES_VRAM), m.memory(SNES_CGRAM)


def window(cells: list[int], tm: list[int]) -> tuple[int, int, int]:
    """(matches, x0, y0) of the best 32 x VISIBLE_ROWS window of the map in a 32 x 32 ring buffer."""
    best = (-1, 0, 0)
    for y0 in range(MAP_H - VISIBLE_ROWS + 1):
        for x0 in range(MAP_W - 32 + 1):
            n = sum(cells[(y0 + sy) * MAP_W + x0 + sx] == tm[sy * 32 + sx]
                    for sy in range(VISIBLE_ROWS) for sx in range(32))
            best = max(best, (n, x0, y0))
    return best


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證大地圖")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    vram, cgram = capture(args.rom)
    errors = 0
    for layer, name in ((0, "terrain"), (1, "roads")):
        cells = rom.map_cells(layer)
        tm = [vram[2 * (TILEMAPS[layer] + i)] | vram[2 * (TILEMAPS[layer] + i) + 1] << 8 for i in range(1024)]
        x0, y0 = TERRAIN_AT if layer else window(cells, tm)[1:]
        if not layer:
            TERRAIN_AT[:] = [x0, y0]
        ok = road = covered = marks = bad = 0
        for sy in range(VISIBLE_ROWS):
            for sx in range(32):
                want = cells[(y0 + sy) * MAP_W + x0 + sx]
                got = tm[sy * 32 + sx]
                if layer and (got & 0x3FF) < MAP_TILE0:
                    covered += 1
                elif layer and (got & 0x3FF) > MAP_TILE0 + 300:
                    marks += 1
                elif got == want:
                    ok += 1
                    road += want != cells[0]
                else:
                    bad += 1
        errors += bad
        extra = f" ({road} road cells; {covered} under windows, {marks} castle markers)" if layer else ""
        print(f"[{name}] window at ({x0}, {y0}): {ok} cells match the ROM, {bad} differ{extra}")
    e = rom.entry(MAP_TILES_ENTRY)
    n = len(e) // 32
    bad_tiles = [k for k in range(n) if vram[32 * (MAP_TILE0 + k):32 * (MAP_TILE0 + k + 1)] != e[32 * k:32 * (k + 1)]]
    pal_ok = all(cgram[32 * (3 + p) + 2 * c:32 * (3 + p) + 2 * c + 2] == rom.data[o:o + 2]
                 for p in range(3) for c in range(1, 16) if (p, c) not in ANIMATED
                 for o in [MAP_PALETTES + 32 * p + 2 * c])
    print(f"[tiles] {n - len(bad_tiles)}/{n} map tiles match data entry 19, palettes 3-5 "
          + ("OK" if pal_ok else "NG"))
    errors += len(bad_tiles) + (not pal_ok)
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
