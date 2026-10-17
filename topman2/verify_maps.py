#!/usr/bin/env python3
"""Check the JAPANL map (the FREE MODE home / office selection) against the game in Mesen.

Savestate on the PRESENT / FREE menu; the run picks FREE MODE, the short scenario, keeps the start year and the
companies, answers yes to "本社、支社地区を変更しますか?", and on company 1 presses Y: the game shows the relief map of
Japan. Checked against rom.map_parts("JAPANL") (KOEI LZ, 7392 bytes):
1. the 188 tiles in VRAM from tile 0xA0 (byte 0x1400);
2. CGRAM row 3 = the file's palette (colour 0 excluded: backdrop);
3. the BG tilemap at $E800 from cell (2, 3): every row the windows leave uncovered equals the file's tilemap row.

Usage: .venv/bin/python topman2/verify_maps.py [--rom ROM]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "tools"))
import tm2
from replay import end_frame, replay
from rom import DEFAULT_ROM, FACE_TILEMAP, JAPANL_H, JAPANL_TILE0, JAPANL_W, Rom

BOOT = tm2.TITLE + " a:10 w200"                      # PRESENT / FREE menu
STEPS = "w20 down:3 w60 a:10 w300" + " a:10 w300" * 6 + " y:10 w300 right:10 w60 a:10 w300"
MIN_ROWS = 12                                        # rows of the map not covered by a window
MAP_X, MAP_Y = 2, 3                                   # the map's top-left cell in the 32-wide BG tilemap


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    t = time.time()
    pal, tilemap, tiles = rom.map_parts("JAPANL")
    reads = [("vram", JAPANL_TILE0 * 32, len(tiles)), ("cgram", 96, 32)]
    reads += [("vram", FACE_TILEMAP + 2 * (32 * (r + MAP_Y) + MAP_X), 2 * JAPANL_W) for r in range(JAPANL_H)]
    run = {"steps": STEPS, "shot": end_frame(STEPS, 0) + 30, "read": reads}
    r = replay(rom.path, BOOT, end_frame(BOOT), [run, run])[-1]     # the first run after a load is dropped
    ok_tiles = r[0] == tiles
    ok_pal = r[1][2:] == pal[2:]
    rows = [k for k in range(JAPANL_H)
            if [int.from_bytes(r[2 + k][2 * c:2 * c + 2], "little") for c in range(JAPANL_W)]
            == tilemap[JAPANL_W * k:JAPANL_W * (k + 1)]]
    print(f"[tiles] VRAM tiles 0x{JAPANL_TILE0:X}.. = JAPANL: {'OK' if ok_tiles else 'NG'} ({len(tiles) // 32} tiles)")
    print(f"[palette] CGRAM row 3 = JAPANL palette: {'OK' if ok_pal else 'NG'}")
    print(f"[tilemap] rows equal to JAPANL: {len(rows)}/{JAPANL_H} {rows}")
    bad = (not ok_tiles) + (not ok_pal) + (len(rows) < MIN_ROWS)
    print(f"{'OK' if not bad else f'{bad} problem(s)'} ({time.time() - t:.0f} s)")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
