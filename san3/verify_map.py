#!/usr/bin/env python3
"""Check the big map decoding (rom.Rom.map_tilemap and the map tiles / palettes) against the game (needs Mesen 2).

Starts scenario 1 as 劉備 in Mesen (tools/mesen.py) and stops on the first command menu, where BG2 shows the
whole map: tilemap at VRAM word $1400 (32 wide, the map from column 1), tiles at byte 0x8000. Compared:
  tilemap   30 x 28 entries = MAP_TILEMAP with the scenario 1 province markers (MAP_CELLS, header colours)
  tiles     VRAM tiles 0x80- = data entry MAP_CHR, tiles 0x370- = entry MARKER_CHR
  palettes  CGRAM palette 2 = one of MAP_PALETTE_FRAMES (the water colours cycle), palette 3 = MARKER_PALETTE

Usage: .venv/bin/python san3/verify_map.py [--rom ROM]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
from mesen import SNES_CGRAM, SNES_VRAM, Mesen
from rom import (
    DEFAULT_ROM,
    MAP_CHR,
    MAP_CHR_TILE,
    MAP_H,
    MAP_PALETTE_FRAMES,
    MAP_W,
    MARKER_CHR,
    MARKER_PALETTE,
    MARKER_TILE,
    Rom,
    le16,
)

# title -> new game -> scenario 1 -> one player -> 劉備 -> settings -> first command menu (frame ~6140; the
# extra w1 keeps the timing on the path where turn 1 opens on the menu, not an AI battle)
INPUTS = ("w1200 start w200 start w300 a w200 a w500 up w30 a w300 right w30 right w30 w1 a w300 a w300 a w300 "
          "a w300 a w300 a w1500 w10")
TILEMAP_VRAM, CHR_VRAM = 0x2800, 0x8000

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
  if f==%(end)d then shot("menu"); emu.breakExecution() end
end, emu.eventType.endFrame)
"""


def schedule(inputs: str) -> tuple[list[tuple[int, str]], int]:
    out, f = [], 10
    for step in inputs.split():
        if step.startswith("w"):
            f += int(step[1:])
        else:
            out.append((f, step))
            f += 24
    return out, f


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證大地圖解碼")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--shot", help="把畫面截圖存到這個 PNG")
    args = ap.parse_args()
    t0 = time.time()
    rom = Rom(args.rom)
    presses, end = schedule(INPUTS)
    lua = LUA % {"presses": ",".join(f'{{{f},"{b}"}}' for f, b in presses), "end": end}
    with Mesen(args.rom) as m:
        m.run(lua, 300)
        vram, cgram = m.memory(SNES_VRAM), m.memory(SNES_CGRAM)
        if args.shot:
            with open(args.shot, "wb") as fh:
                fh.write(m.screenshots()["menu"])
    errors = 0
    want = rom.map_tilemap(0)
    got = [le16(vram, TILEMAP_VRAM + 2 * (y * 32 + 1 + x)) for y in range(MAP_H) for x in range(MAP_W)]
    ok = sum(a == b for a, b in zip(got, want))
    markers = sum(1 for (x, y) in rom.map_cells() if got[y * MAP_W + x] == want[y * MAP_W + x])
    errors += len(want) - ok
    print(f"[tilemap] {ok}/{len(want)} entries match (province markers {markers}/{len(rom.map_cells())})")
    for name, entry, tile in (("map tiles", MAP_CHR, MAP_CHR_TILE), ("marker tiles", MARKER_CHR, MARKER_TILE)):
        data = rom.entry(entry)
        n = len(data) // 32
        same = sum(vram[CHR_VRAM + 32 * (tile + i):CHR_VRAM + 32 * (tile + i + 1)] == data[32 * i:32 * (i + 1)]
                   for i in range(n))
        errors += n - same
        print(f"[{name}] entry {entry}: {same}/{n} tiles at VRAM tile {tile:#x} match")
    for p, frames in ((2, MAP_PALETTE_FRAMES), (3, (MARKER_PALETTE,))):
        hit = [at for at in frames if cgram[32 * p:32 * p + 32] == rom.data[at:at + 32]]
        errors += not hit
        print(f"[palette] CGRAM palette {p} " + (f"= ROM {hit[0]:#x}" if hit else
                                                  f"matches none of {', '.join(hex(a) for a in frames)}"))
    print(f"time {time.time() - t0:.0f} s")
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
