#!/usr/bin/env python3
"""Check the big map (rom.Rom.map_tiles, MAP_PALETTE) against the game (needs Mesen 2, about 4 minutes).

The game is played to the first command screen (as verify_scenarios.py), which shows the 北部 region on BG2:
LZ entry 16 at VRAM tile 8, a sequential 28 x 24 block in the tilemap at VRAM 0xC800 (entry (row + 2) * 32 +
column + 2 = 0x0C00 | 8 + 28 row + column, palette 3), CGRAM palette 3 = MAP_PALETTE. The game then
- puts animated sea tiles 4-7 on some open-sea entries of the block (counted),
- cycles colours 9-11 of palette 3 (water; not compared),
- recolours the land of each location by owner: colour 15 (white) -> 3, 8 or 12, per region from masks that are
  not decoded.
A savestate is taken at frame 100; for region r the long pointer of LZ entry 16 is patched to the one of entry
16 + r and the game played again (still showing 北部, so the 北部 sea entries and owner masks are applied to the
other bitmap). Checked: the tilemap block apart from tiles 4-7, palette 3 colours 0-8 and 12-15, and every pixel
of the 672 tiles: 北部 equal to ROM or 15 -> 3/8/12; 中部 / 南部 equal to ROM or turned into 3/8/12 (the 北部 masks).

Usage: .venv/bin/python dokuritsu/verify_maps.py [--rom ROM]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
from replay import replay
from rom import DEFAULT_ROM, LZ_POINTERS, MAP_ENTRY, MAP_H, MAP_PALETTE, MAP_W, REGIONS, Rom, decode_tile, le16
from verify_scenarios import MAIN, presses

SAVE_AT = 100
MAP_TILE0 = 8
TILEMAP = 0xC800
OWNER_COLOURS = (3, 8, 12)
WATER_COLOURS = (9, 10, 11)


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證大地圖 3 區")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    t0 = time.time()
    rom = Rom(args.rom)
    steps = "w" + str(int(MAIN.split()[0][1:]) - (SAVE_AT - 10)) + " " + MAIN.split(" ", 1)[1]
    _, end = presses(steps, SAVE_AT)
    n = MAP_W * MAP_H
    read = [("vram", 32 * MAP_TILE0, 32 * n), ("vram", TILEMAP, 2048), ("cgram", 0x60, 32)]
    p0 = LZ_POINTERS + 3 * MAP_ENTRY
    runs = [{"patch": [(p0, rom.data[p0 + 3 * r:p0 + 3 * r + 3])], "steps": steps, "shot": end - SAVE_AT + 50,
             "read": read} for r in range(3)]
    shots = replay(args.rom, "", SAVE_AT, runs)
    errors = 0
    for r, (chars, tm, cg) in enumerate(shots):
        sea = tm_bad = 0
        for y in range(MAP_H):
            for x in range(MAP_W):
                e = le16(tm, 2 * ((y + 2) * 32 + x + 2))
                if e != 0x0C00 | MAP_TILE0 + MAP_W * y + x:
                    if e & 0xFC00 == 0x0C00 and 4 <= e & 0x3FF <= 7:
                        sea += 1
                    else:
                        tm_bad += 1
        pal_ok = all(le16(cg, 2 * i) == le16(rom.data, MAP_PALETTE + 2 * i) for i in range(16)
                     if i not in WATER_COLOURS)
        src = rom.map_tiles(r)
        same = recol = other = 0
        for t in range(n):
            for a, b in zip(decode_tile(src[32 * t:32 * t + 32]), decode_tile(chars[32 * t:32 * t + 32])):
                if a == b:
                    same += 1
                elif b in OWNER_COLOURS and (a == 15 or r):
                    recol += 1
                else:
                    other += 1
        print(f"[{REGIONS[r]}] LZ entry {MAP_ENTRY + r}: tilemap block {n - sea - tm_bad}/{n} entries equal, {sea} sea "
              f"tiles 4-7, {tm_bad} other; palette 3 = 0x{MAP_PALETTE:X} (without 9-11) {pal_ok}; pixels equal {same}, "
              f"owner colour {recol}, other {other}")
        errors += tm_bad + (not pal_ok) + other
    print(f"time {time.time() - t0:.0f} s")
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
