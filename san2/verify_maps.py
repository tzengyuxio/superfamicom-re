#!/usr/bin/env python3
"""Check the big map and the 41 battle fields against the game (needs Mesen 2, about 2 minutes).

1. Big map: on the way to the battle, with scenario 1 picked, the map screen's VRAM is read. BG1 must show tiles 0x1D0-
   row-major at (2, 3) with palette 7, and every tile must equal ROM MAP_TILES except where the game
   painted a faction colour over colour 7 (the only change allowed: 7 -> 8..15). The CGRAM palette
   must equal ROM MAP_PALETTE.
2. Battle fields (tools/battle_capture.py): every field is put in place of field 20 and the game lays
   it out; each hex's 4 tilemap entries must equal TERRAIN_CELLS of its terrain. The game marks the
   attacker's 5 entry hexes by putting tile 0x1F3 in their top-right cell; those are counted apart.
   The terrain tiles in VRAM and BG palettes 0-2 must equal the ROM (BATTLE_GFX, RIVER_GFX, BATTLE_PALETTE).

Usage: .venv/bin/python san2/verify_maps.py [--rom ROM]
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
from rom import (
    BATTLE,
    BATTLE_PALETTE,
    DEFAULT_ROM,
    MAP_H,
    MAP_PALETTE,
    MAP_TILES,
    MAP_W,
    PROVINCE_COUNT,
    Rom,
    decode_tile,
)
from tools.battle_capture import capture_fields

MAP_TILE0, MAP_PAL, MAP_X, MAP_Y = 0x1D0, 7, 2, 3
CHR = 0x4000                        # BG1 tile data (VRAM bytes)
ENTRY_MARK = 0x1F3


def check_map(rom: Rom, vram: bytes, cgram: bytes) -> int:
    d, errors, painted = rom.data, 0, 0
    if cgram[32 * MAP_PAL:32 * MAP_PAL + 32] != d[MAP_PALETTE:MAP_PALETTE + 32]:
        print("  NG palette")
        errors += 1
    for i in range(MAP_W * MAP_H):
        a = 2 * ((MAP_Y + i // MAP_W) * 32 + MAP_X + i % MAP_W)
        e = vram[a] | vram[a + 1] << 8
        if e != MAP_TILE0 + i | MAP_PAL << 10:
            print(f"  NG tilemap cell {i}: {e:04X}")
            errors += 1
            continue
        t = MAP_TILE0 + i
        shown = decode_tile(vram[CHR + 32 * t:CHR + 32 * t + 32])
        rom_px = decode_tile(d[MAP_TILES + 32 * i:MAP_TILES + 32 * i + 32])
        bad = [(a, b) for a, b in zip(rom_px, shown) if a != b and not (a == 7 and b >= 8)]
        painted += shown != rom_px
        if bad:
            print(f"  NG tile {i}: {bad[:4]}")
            errors += 1
    print(f"[map] {MAP_W * MAP_H - errors}/{MAP_W * MAP_H} tiles match the ROM ({painted} with faction colours)")
    return errors


def check_battle_gfx(rom: Rom, vram: bytes, cgram: bytes) -> int:
    """Terrain tiles and BG palettes 0-2 on the battle screen vs ROM (rom.Rom.battle_tile)."""
    entries = {e for cells in rom.terrain_cells() for e in cells}
    bad = [f"{e & 0x3FF:03X}" for e in sorted(entries)
           if decode_tile(vram[CHR + 32 * (e & 0x3FF):CHR + 32 * (e & 0x3FF) + 32]) != rom.battle_tile(e)]
    pal_ok = cgram[:96] == rom.data[BATTLE_PALETTE:BATTLE_PALETTE + 96]
    print(f"[battle] {len(entries) - len(bad)}/{len(entries)} terrain tiles match the ROM, palettes 0-2 "
          + ("OK" if pal_ok else "NG") + (f" (NG {' '.join(bad)})" if bad else ""))
    return len(bad) + (not pal_ok)


def check_fields(rom: Rom, shown: dict[int, list[list[int]]]) -> int:
    cells = rom.terrain_cells()
    bad, marks = [], set()
    for i in range(PROVINCE_COUNT):
        want = [cells[t] for row in rom.battle_terrain(i) for t in row]
        got = shown.get(i, [])
        for h, (w, g) in enumerate(zip(want, got)):
            if g != w and g == [w[0], ENTRY_MARK, w[2], w[3]]:
                marks.add(h)
            elif g != w:
                bad.append(i + 1)
                break
        if len(got) != len(want):
            bad.append(i + 1)
    print(f"[battle] {PROVINCE_COUNT - len(set(bad))}/{PROVINCE_COUNT} fields match the game's tilemap"
          f" (entry marks at hexes {sorted(marks)})" + (f" NG {sorted(set(bad))}" if bad else ""))
    return len(set(bad))


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證大地圖與戰場地圖")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    maps = {i: rom.data[BATTLE + 78 * i:BATTLE + 78 * i + 78] for i in range(PROVINCE_COUNT)}
    shown, big_map, field_mem = capture_fields(args.rom, maps, BATTLE)
    errors = check_map(rom, *big_map)
    errors += check_battle_gfx(rom, *field_mem)
    errors += check_fields(rom, shown)
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
