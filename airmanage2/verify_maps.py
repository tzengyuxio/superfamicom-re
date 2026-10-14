#!/usr/bin/env python3
"""Check the world map and the 7 area maps against the game's VRAM, CGRAM and OAM in Mesen.

One savestate at the area menu of a new game (scenario 1, tools/replay.py):
- runs 1-7 choose each area: the home-city map must show BG tilemap $F000 = AR_MAP (rows 0-18; the command
  window covers the rest), CHR $4000 = the area's AREA1 stream tiles, CGRAM row 1 = its palette, and one sprite
  exactly at each of the area's cities ($05:E2E5);
- run 8 plays on (Berlin) to the world map shown after the COM players' turn: BG1 tilemap $E800 rows 3-17 =
  tiles 0-479 with palette 1, CHR $0000 = MAINMAP, CGRAM row 1 = M_COLOR; BG2 tilemap $F000 = the MAPBACK
  tilemap (22 rows), its tiles at VRAM $6C00 (tile $160) and CGRAM row 2 = its palette.

Usage: .venv/bin/python airmanage2/verify_maps.py [--rom ROM]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "tools"))
import am2
from replay import replay
from rom import AREA_COUNT, DEFAULT_ROM, WORLD_LAND_ROW, WORLD_SEA_ROWS, Rom

VISIBLE_ROWS = 19
REST_OF_BOOT = "w30 " + am2.BOOT[len(am2.TO_AREA_MENU) + 1:]   # from the area-menu savestate to the world map


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    t = time.time()
    tm = rom.raw("AR_MAP")[:64 * VISIBLE_ROWS]
    runs = [{"steps": am2.AREA_KEYS[a] + " w40 a:10 w400", "shot": 700,
             "read": [("vram", 0xF000, len(tm)), ("vram", 0x4000, 736 * 32), ("cgram", 0x20, 32), ("oam", 0, 512)]}
            for a in range(AREA_COUNT)]
    mb = rom.raw("MAPBACK")
    sea_tm = mb[0x20:0x20 + 64 * WORLD_SEA_ROWS]
    sea_chr = mb[0x20 + 64 * WORLD_SEA_ROWS:]
    runs.append({"steps": REST_OF_BOOT, "shot": 7880 - am2.AREA_MENU_FRAME,
                 "read": [("vram", 0xE800, 2048), ("vram", 0, 480 * 32), ("cgram", 0x20, 32),
                          ("vram", 0xF000, len(sea_tm)), ("vram", 0x6C00, len(sea_chr)), ("cgram", 0x40, 32)]})
    res = replay(rom.path, am2.TO_AREA_MENU, am2.AREA_MENU_FRAME, runs)
    bad = 0
    cities = rom.cities()
    for a, r in enumerate(res[:AREA_COUNT]):
        s = rom.area_stream(a)
        spr = {(r[3][4 * i], r[3][4 * i + 1]) for i in range(128)}
        mine = [c for c in cities if c["area"] == a]
        marks = sum((c["area_x"], c["area_y"]) in spr for c in mine)
        checks = [r[0] == tm, r[1] == s[32:], r[2][2:] == s[2:32], marks == len(mine)]
        bad += checks.count(False)
        print(f"area {a} {rom.areas()[a]['name']}: tilemap {checks[0]}, CHR {checks[1]}, palette {checks[2]}, "
              f"city sprites {marks}/{len(mine)}")
    w = res[AREA_COUNT]
    land = bytes(b for n in range(480) for b in ((n & 0xFF), 0x04 | n >> 8))
    rows = w[0][64 * WORLD_LAND_ROW:64 * (WORLD_LAND_ROW + 15)]
    mc = rom.raw("M_COLOR")
    checks = [("BG1 tilemap rows 3-17", rows == land), ("BG1 CHR = MAINMAP", w[1] == rom.lz("MAINMAP")),
              ("CGRAM row 1 = M_COLOR", w[2][2:] == mc[2:]), ("BG2 tilemap = MAPBACK", w[3] == sea_tm),
              ("BG2 CHR = MAPBACK", w[4] == sea_chr), ("CGRAM row 2 = MAPBACK palette", w[5][2:] == mb[2:32])]
    bad += sum(not ok for _, ok in checks)
    print("world map: " + ", ".join(f"{n} {ok}" for n, ok in checks))
    print(f"{'OK' if not bad else f'{bad} problem(s)'} ({time.time() - t:.0f} s)")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
