#!/usr/bin/env python3
"""Check the town map of the main screen against the game (scenario 1, JVD / VECTOR, first turn).

BG2: tilemap rows 0-17 (VRAM byte 0xF000), tiles (VRAM 0x6000) and CGRAM palette 2 must equal OFFCBACK
(rom.Rom.town_background). BG1: the 4 building lots must be laid out as rom.py says (palette 3 = EQUIP, 6 x 6
tiles from 0x3E + 36 n at columns 3 / 10 / 17 / 24) and each lot's 36 tiles must be one variant of the
BUSI / FACT / LABO _L1-5 files.

Usage: .venv/bin/python leading/verify_maps.py [--rom ROM]
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "tools"))
sys.path.insert(0, HERE)
import lc
from replay import end_frame, replay
from rom import (
    BG1_TILEMAP_VRAM,
    BUILDING_BYTES,
    BUILDING_KINDS,
    BUILDING_PALETTE,
    BUILDING_VARIANTS,
    DEFAULT_ROM,
    LOT_COLUMNS,
    LOT_ROW,
    LOT_TILE0,
    TOWN_PALETTE,
    TOWN_TILEMAP_VRAM,
    TOWN_TILES_VRAM,
    Rom,
    le16,
)


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證主畫面的街區地圖")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    town = rom.town_background()
    reads = [("vram", TOWN_TILEMAP_VRAM, len(town["tilemap"])), ("vram", TOWN_TILES_VRAM, len(town["tiles"])),
             ("cgram", 32 * TOWN_PALETTE, 32), ("cgram", 32 * BUILDING_PALETTE, 32),
             ("vram", BG1_TILEMAP_VRAM, 0x800), ("vram", LOT_TILE0 * 32, 4 * BUILDING_BYTES)]
    (tm, tiles, pal2, pal3, bg1, lots), = replay(args.rom, lc.MAIN, end_frame(lc.MAIN),
                                                 [{"shot": 60, "read": reads}])
    checks = {"BG2 tilemap 32x18": tm == town["tilemap"], "BG2 tiles": tiles == town["tiles"],
              "CGRAM palette 2 = OFFCBACK": pal2 == town["palette"],
              "CGRAM palette 3 = EQUIP": pal3 == rom.building_palette()}
    layout_ok = all(le16(bg1, 2 * ((LOT_ROW + r) * 32 + c0 + c))
                    == (BUILDING_PALETTE << 10 | (LOT_TILE0 + 36 * n + 6 * r + c))
                    for n, c0 in enumerate(LOT_COLUMNS) for r in range(6) for c in range(6))
    checks["BG1 lot layout"] = layout_ok
    for k, ok in checks.items():
        print(f"[{k}] " + ("OK" if ok else "NG"))
    found = []
    for n in range(4):
        chunk = lots[n * BUILDING_BYTES:(n + 1) * BUILDING_BYTES]
        hit = [f"{k}_L{lv}#{v}" for k in BUILDING_KINDS for lv in range(1, 6) for v in range(BUILDING_VARIANTS)
               if rom.building(k, lv, v) == chunk]
        found.append(hit[0] if hit else None)
    print(f"[lots] {sum(x is not None for x in found)}/4 lots = a building variant: {found}")
    errors = sum(not ok for ok in checks.values()) + found.count(None)
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
