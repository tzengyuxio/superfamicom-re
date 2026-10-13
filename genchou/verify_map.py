#!/usr/bin/env python3
"""Check the main map (rom.Rom.map_tiles / map_palette) against the game (needs Mesen 2, about 20 seconds).

From the scenario menu (savestate replay, genchou/tools/replay.py; the 4th scenario through the menu patch of
verify_scenarios.py) every scenario is started up to a screen that shows the map. Then BG2 is read back:
the 552 tiles at VRAM byte 0x4E00 (character base 0x4000 + tile 0x70 * 32) must equal the LZ map entry in every
pixel whose ROM colour is not MAP_FILL (the game paints the regions' insides per house), the tilemap (VRAM
0xF000) must place them row-major at columns 7-29, rows 3-26 with palette 6, and CGRAM palette 6 must equal
MAP_PALETTE.

Usage: .venv/bin/python genchou/verify_map.py [--rom ROM]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "tools"))
from replay import replay
from rom import DEFAULT_ROM, MAP_ENTRY, MAP_FILL, MAP_H, MAP_PALETTE, MAP_W, SCENARIO_COUNT, Rom, decode_tile
from verify_scenarios import BOOT, MENU_ARG, SAVE_AT

TILE0 = 0x70
CHR = 0x4000
TILEMAP = 0xF000
COL0, ROW0 = 7, 3
PALETTE = 6
# from the scenario menu: scenario 1 up to its first turn; the others up to "他国の戦争を見ますか"
STEPS = ["a:10 w200 " * 6 + "a:10 w300 " * 4,
         "down:10 w30 a:10 w200 a:10 w200 a:10 w200",
         "down:10 w30 down:10 w30 a:10 w200 a:10 w200 a:10 w200",
         "a:10 w200 a:10 w200 a:10 w200"]


def length(steps: str) -> int:
    return sum(int(s[1:]) if s[0] == "w" else int(s.split(":")[1]) + 20 for s in steps.split())


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證大地圖")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    t0 = time.time()
    rom = Rom(args.rom)
    n = MAP_W * MAP_H
    runs = [{"patch": [(MENU_ARG, bytes.fromhex("a90300eaea"))] if sc == 3 else [], "steps": STEPS[sc],
             "shot": length(STEPS[sc]),
             "read": [("vram", CHR + 32 * TILE0, 32 * n), ("vram", TILEMAP, 0x800), ("cgram", 32 * PALETTE, 32)]}
            for sc in range(SCENARIO_COUNT)]
    errors = 0
    for sc, (tiles, tmap, cgram) in enumerate(replay(args.rom, BOOT, SAVE_AT, runs)):
        world = sc > 0
        want = rom.map_tiles(world)
        same = fill = 0
        for t in range(n):
            for a, b in zip(decode_tile(want[32 * t:32 * t + 32]), decode_tile(tiles[32 * t:32 * t + 32])):
                if a == MAP_FILL:
                    fill += 1
                else:
                    same += a == b
        cells = sum((tmap[2 * (32 * (ROW0 + r) + COL0 + c)] | tmap[2 * (32 * (ROW0 + r) + COL0 + c) + 1] << 8)
                    == (PALETTE << 10 | TILE0 + MAP_W * r + c) for r in range(MAP_H) for c in range(MAP_W))
        base = MAP_PALETTE["world" if world else "mongol"]
        pal = cgram == rom.data[base:base + 32]
        total = 64 * n - fill
        print(f"[scenario {sc + 1}] LZ entry {MAP_ENTRY['world' if world else 'mongol']}: {same}/{total} pixels "
              f"(outside the {fill} region-fill pixels), tilemap {cells}/{n}, palette 6 = ROM {base:#x} {pal}")
        errors += same != total or cells != n or not pal
    print(f"{'ALL OK' if not errors else f'{errors} problem(s)'} ({time.time() - t0:.0f} s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
