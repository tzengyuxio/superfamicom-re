#!/usr/bin/env python3
"""Check the location maps against what the game unpacks and draws (needs Mesen 2, a few minutes).

The savestate is taken on the naming screen's last YES, before the first map (伊賀の里, map 34) is loaded. Each
run patches the map table entry 34 (MAPS + 68) in PRG ROM to point at map m, so the game's own loader ($7E:72A3)
unpacks map m in its place:
  [cells]   WRAM $7F:B000 + 4 (W + 8) + 4, rows of W at stride W + 8, must be rom.Rom.map_wram(m) (all 48 maps)
For the unpatched run (map 34) the screen is checked as well:
  [tilemap] every BG2 tilemap word in use (VRAM byte 0x800, 32x32 16x16 tiles wrapping around) must be the
            town metatile word (rom.town_metatiles / town_tile_word) of the cell under it in the WRAM grid
            (the map plus the game's 4-cell border), all at one scroll offset
  [tileset] VRAM byte 0x4400-0x5FFF must be TOWN_TILESET, CGRAM palette 2 TOWN_PALETTE

Usage: .venv/bin/python inindou/verify_maps.py [--rom ROM]
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
from replay import end_frame, replay
from rom import (
    DEFAULT_ROM,
    MAP_COUNT,
    MAPS,
    START_VILLAGE,
    TOWN_PALETTE,
    TOWN_TILESET,
    TOWN_TILESET_SIZE,
    Rom,
    le16,
)
from scenes import BOOT

LOAD = "a w400"
BOOT0 = BOOT[:-len(" " + LOAD)]
WRAM_MAP, WRAM_MAP_SIZE = 0x1B000, 0x1000
BG2_TILEMAP, BG2_TILES = 0x800, 0x4400


def main() -> None:
    ap = argparse.ArgumentParser(description="以 Mesen 驗證地點地圖的解壓與町的圖塊")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    assert BOOT0 + " " + LOAD == BOOT
    rom = Rom(args.rom)
    reads = [("wram", WRAM_MAP, WRAM_MAP_SIZE), ("vram", BG2_TILEMAP, 0x800),
             ("vram", BG2_TILES, TOWN_TILESET_SIZE), ("cgram", 0x40, 32)]
    runs = []
    for m in range(MAP_COUNT):
        ptr = le16(rom.data, MAPS + 2 * m)
        runs.append({"patch": [] if m == START_VILLAGE else [(MAPS + 2 * START_VILLAGE, bytes([ptr & 255, ptr >> 8]))],
                     "steps": LOAD, "shot": end_frame(LOAD, 0), "read": reads})
    results = replay(args.rom, BOOT0, end_frame(BOOT0), runs)
    cells_ok = []
    for m, (wram, *_rest) in enumerate(results):
        at, want = rom.map_wram(m)
        got = wram[at - WRAM_MAP:at - WRAM_MAP + len(want)]
        hd = rom.map_header(m)
        stride = hd["w"] + 8
        if all(got[r * stride:r * stride + hd["w"]] == want[r * stride:r * stride + hd["w"]] for r in range(hd["h"])):
            cells_ok.append(m)
    print(f"[cells] {len(cells_ok)}/{MAP_COUNT} maps unpacked by the game equal rom.map_cells"
          + ("" if len(cells_ok) == MAP_COUNT else f" (NG {sorted(set(range(MAP_COUNT)) - set(cells_ok))})"))

    wram, tilemap, tiles, cgram = results[START_VILLAGE]
    hd = rom.map_header(START_VILLAGE)
    gw, gh = hd["w"] + 8, hd["h"] + 8            # the WRAM grid: the map and its 4-cell border (checked above)
    grid = wram[:gw * gh]
    meta = rom.town_metatiles()
    words = [le16(tilemap, 2 * i) for i in range(1024)]
    used = [(i % 32, i // 32, w) for i, w in enumerate(words) if w]
    best = (0, None)
    for ox in range(2 * gw):
        for oy in range(2 * gh):
            good = 0
            for x, y, w in used:
                # the 20x20 tiles in use wrap at 32 (columns and rows 30, 31, 0-17): 30 and 31 come first
                X = ox + (x if x < 24 else x - 32)
                Y = oy + (y if y < 24 else y - 32)
                if 0 <= X < 2 * gw and 0 <= Y < 2 * gh:
                    code = grid[(Y // 2) * gw + X // 2]
                    good += code < len(meta) and rom.town_tile_word(meta[code][(Y % 2) * 2 + X % 2]) == w
            if good > best[0]:
                best = (good, (ox, oy))
    print(f"[tilemap] {best[0]}/{len(used)} BG2 tilemap words equal the town metatiles of map {START_VILLAGE}"
          f" (scroll offset {best[1]})")
    ts_ok = tiles == rom.data[TOWN_TILESET:TOWN_TILESET + TOWN_TILESET_SIZE]
    pal_ok = cgram == rom.data[TOWN_PALETTE:TOWN_PALETTE + 32]
    print(f"[tileset] VRAM tiles {'OK' if ts_ok else 'NG'}, CGRAM palette 2 {'OK' if pal_ok else 'NG'}")
    errors = (MAP_COUNT - len(cells_ok)) + (best[0] != len(used)) + (not ts_ok) + (not pal_ok)
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
