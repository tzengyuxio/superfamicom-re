#!/usr/bin/env python3
"""Check the Japan map decoding (rom.Rom.map_blocks_at_start, map_cells, map_tilemaps, map_chr, map_palettes)
against the game (needs Mesen 2, about 6 minutes).

A new game is played to the Japan map in 尾張 (tools/sequences.TO_MAP) and a savestate taken there.
1. The 0x8240 bytes of block cells at $7F:0000 must equal rom.Rom.map_blocks_at_start() (the LZ stream at ROM 0
   plus the castle icon bits the game sets at the start).
2. Every run walks right and down; crossing into the next block makes the game redraw its 3 x 3 block window
   ($C3:00EF: cells to $7E:64B5, BG1 / BG2 words to the 32 x 32 tilemaps). Run 0 is unpatched. In the other runs
   an exec callback on $C3:00EF moves the window's centre ($7E:200A / $7E:200B) to another block when it is
   entered, so the game's own code draws that part of Japan. At the end, BG1 (VRAM 0xF000) and BG2 (0xF800)
   must equal rom.Rom.map_tilemaps of the 24 x 24 cells around the final ($200A, $200B) taken from map_cells().
3. BG characters VRAM 0x8240-0xAEA0 (every tile the map uses) must equal rom.Rom.map_chr(), CGRAM palettes 2-7 the
   ROM palettes (palette 2 cycles with the time of day through the palettes at 0xD85C9-0xD8FC8).

Usage: .venv/bin/python taikou/verify_maps.py [--rom ROM] [--quick]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
sys.path.insert(0, os.path.join(HERE, "tools"))
from replay import replay
from rom import BLOCK, DEFAULT_ROM, MAP_PALETTES, MAP_ROWS, TABLE_W, Rom, le16
from sequences import TO_MAP, end_frame, expand

SAVE_AT = end_frame(TO_MAP) - 100
STEPS = "w100 right:200 down:200"
SHOT = 700
BLOCKS_SIZE = 0x8240
CHR_LO, CHR_HI = 0x8240, 0xAEA0
# palette 2 changes with the time of day: any palette of the run at TIMED_RANGE is accepted there
TIMED, TIMED_RANGE = {2}, (0xD85C9, 0xD8FC9)
PARAM = 0x1FFF0       # $7F:FFF0 (unused): the run's target block, handed over by a WRAM patch
REDRAW = 0xC300EF
EXTRA = f"""
emu.addMemoryCallback(function()
  local x = emu.read(0x7FFFF0, emu.memType.snesMemory, false)
  if x ~= 0 then
    emu.write(0x7E200A, x, emu.memType.snesMemory)
    emu.write(0x7E200B, emu.read(0x7FFFF1, emu.memType.snesMemory, false), emu.memType.snesMemory)
    emu.write(0x7FFFF0, 0, emu.memType.snesMemory)
  end
end, emu.callbackType.exec, {REDRAW}, {REDRAW})
"""


def window(cells: list[list[int]], x: int, y: int) -> list[list[int]]:
    return [row[(x - 1) * BLOCK:(x + 2) * BLOCK] for row in cells[(y - 1) * BLOCK:(y + 2) * BLOCK]]


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證大地圖（日本地圖）解碼")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--quick", action="store_true", help="fewer windows")
    args = ap.parse_args()
    t0 = time.time()
    rom = Rom(args.rom)
    table = rom.block_table()
    # blocks whose 3 x 3 window has a block of Japan in it (every 2nd column and row)
    targets = [(x, y) for y in range(1, MAP_ROWS - 1, 2) for x in range(1, TABLE_W - 1, 2)
               if any(table[y + dy][x + dx] for dy in (-1, 0, 1) for dx in (-1, 0, 1))]
    if args.quick:
        targets = targets[::6]
    read = [("wram", 0x200A, 4), ("vram", 0xF000, 2048), ("vram", 0xF800, 2048)]
    first = read + [("wram", 0x10000, BLOCKS_SIZE), ("vram", CHR_LO, CHR_HI - CHR_LO), ("cgram", 0, 256)]
    runs = [{"steps": STEPS, "shot": SHOT, "read": first}]
    runs += [{"wram": [(PARAM, bytes([x, y]))], "steps": STEPS, "shot": SHOT, "read": read} for x, y in targets]
    shots = replay(args.rom, expand(TO_MAP), SAVE_AT, runs, extra_lua=EXTRA)
    errors = 0

    blocks = rom.map_blocks_at_start()
    ok = shots[0][3] == blocks
    print(f"[blocks] $7F:0000 ({BLOCKS_SIZE:#x} bytes) {'equals' if ok else 'DIFFERS from'} the ROM blocks + castle bits")
    errors += not ok
    ok = shots[0][4] == rom.map_chr()[CHR_LO:CHR_HI]
    print(f"[chr] VRAM {CHR_LO:#x}-{CHR_HI:#x} {'equals' if ok else 'DIFFERS from'} rom.map_chr()")
    errors += not ok
    cg = shots[0][5]
    timed = {rom.data[o:o + 32] for o in range(*TIMED_RANGE, 32)}
    bad = [p for p, pal in rom.map_palettes().items() if [le16(cg, 32 * p + 2 * i) for i in range(16)] != pal
           and not (p in TIMED and cg[32 * p:32 * p + 32] in timed)]
    print(f"[palettes] CGRAM palettes {sorted(MAP_PALETTES)}: {len(MAP_PALETTES) - len(bad)}/{len(MAP_PALETTES)} match"
          + (f" (NG {bad})" if bad else ""))
    errors += len(bad)

    cells = rom.map_cells(blocks)
    ok_windows, bad_windows, skipped = [], [], []
    for shot in shots:
        pos, v1, v2 = shot[:3]
        x, y, mode = pos[0], pos[1], pos[3]
        if mode != 1 or not (1 <= x < TABLE_W - 1 and 1 <= y < MAP_ROWS - 1):
            skipped.append((x, y, mode))
            continue
        bg1, bg2 = rom.map_tilemaps(window(cells, x, y))
        c0, r0 = (x - 1) * BLOCK % 32, (y - 1) * BLOCK % 32
        bad = 0
        for j in range(3 * BLOCK):
            for k in range(3 * BLOCK):
                a = 2 * (32 * ((r0 + j) % 32) + (c0 + k) % 32)
                bad += (le16(v1, a) != bg1[j][k]) + (le16(v2, a) != bg2[j][k])
        (bad_windows if bad else ok_windows).append((x, y, bad))
    n = len(ok_windows) + len(bad_windows)
    print(f"[windows] {len(ok_windows)}/{n} windows drawn by the game (1152 BG1/BG2 entries each) match map_tilemaps"
          + (f" (NG (x, y, mismatches) {bad_windows[:10]})" if bad_windows else ""))
    if skipped:
        print(f"  {len(skipped)} runs ended off the Japan map (x, y, mode): {skipped[:10]}")
    print(f"  {len({(x, y) for x, y, _ in ok_windows})} distinct window centres from {len(runs)} runs")
    errors += len(bad_windows) + (len(ok_windows) < len(runs) // 2)
    print(f"time {time.time() - t0:.0f} s")
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
