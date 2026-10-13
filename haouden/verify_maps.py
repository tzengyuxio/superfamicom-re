#!/usr/bin/env python3
"""Check the big map decoding (rom.Rom.map_tilemap / map_rgb inputs) against the game (needs Mesen 2, about 40 s).

Scenario 1 is started as 龍造寺隆信 in Mesen (tools/mesen.py, savestate replay haouden/tools/replay.py) up to the
first turn's main screen. The map is BG2 (16x16 tiles, tilemap VRAM 0xF000, characters 0x8000). Checked:
  - the game's map in WRAM $7F:E800 (its own decompression, 96 x 32 LE16) equals LZ entry 15, except castle
    icon cells, which the game redraws with the owner's palette or a flag tile;
  - every non-empty entry of the 32 x 32 BG2 tilemap in VRAM (the game fills the visible 16 x 14 cells) equals
    that map at one offset; castle icon cells may be drawn with the owner's palette / a flag tile instead;
  - VRAM 0x8400-0xCBFF = the map tiles (LZ entry 14);
  - CGRAM palettes 2 and 3 = the two map palettes in ROM (palette 3 colours 13 and 14 swap every few frames:
    water animation).

Usage: .venv/bin/python haouden/verify_maps.py [--rom ROM]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "tools"))
from replay import replay
from rom import DEFAULT_ROM, MAP_CHARS, MAP_H, MAP_TILEMAP, MAP_W, Rom

BOOT = ("w1500 start:10 w200 a:10 w200 a:10 w60 a:10 w60 a:10 w60 a:10 w60 a:10 w60 a:10 w400 a:10 w200 a:10 w900"
        " a:10 w300 right:10 w30 a:10 w1500 a:10 w1200")
SAVE_AT = 7000
SHOT = 300
MAP_WRAM = 0x1E800                      # $7F:E800
CASTLE_TILES = {0x10A, 0x10E, 0x120}   # castle icon cells of the map


def match_offset(tm: list[int], vram: bytes) -> tuple[int, int, int, int, int]:
    """(equal entries, castle cells drawn differently, non-empty entries, column, row) of the best map offset."""
    v = [vram[2 * i] | vram[2 * i + 1] << 8 for i in range(1024)]
    used = [i for i in range(1024) if v[i]]
    best = (0, 0, 0, 0)

    def at(i: int, base: int, sx: int, dy: int) -> int:
        # VRAM column x shows map column base + (x - sx) mod 32, VRAM row y map row (y + dy) mod 32
        return tm[((i // 32 + dy) % MAP_H) * MAP_W + base + (i % 32 - sx) % 32]

    for dy in range(MAP_H):
        for base in range(MAP_W - 31):
            for sx in range(32):
                if sum(v[i] == at(i, base, sx, dy) for i in used[:32]) < 20:
                    continue
                eq = sum(v[i] == at(i, base, sx, dy) for i in used)
                castle = sum(v[i] != at(i, base, sx, dy) and at(i, base, sx, dy) & 0x3FF in CASTLE_TILES
                             for i in used)
                if eq + castle > best[0] + best[1]:
                    best = (eq, castle, base, dy)
    return best[0], best[1], len(used), best[2], best[3]


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證大地圖")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    t0 = time.time()
    rom = Rom(args.rom)
    chars, raw = rom.entry(MAP_CHARS), rom.entry(MAP_TILEMAP)
    read = [("wram", MAP_WRAM, len(raw)), ("vram", 0xF000, 2048), ("vram", 0x8400, len(chars)), ("cgram", 0x40, 64)]
    (wmap, tmap, ch, cg), = replay(args.rom, BOOT, SAVE_AT, [{"shot": SHOT, "read": read}])
    pal = b"".join(c.to_bytes(2, "little") for p in (2, 3) for c in rom.map_palettes()[p])
    swapped = pal[:58] + pal[60:62] + pal[58:60] + pal[62:]    # palette 3 colours 13 and 14 exchanged
    eq, castle, used, dx, dy = match_offset(rom.map_tilemap(), tmap)
    tm = rom.map_tilemap()
    live = [wmap[2 * i] | wmap[2 * i + 1] << 8 for i in range(MAP_W * MAP_H)]
    w_eq = sum(a == b for a, b in zip(live, tm))
    w_castle = sum(a != b and b & 0x3FF in CASTLE_TILES for a, b in zip(live, tm))
    checks = [(w_eq + w_castle == len(tm), (f"WRAM $7F:E800 (the game's map): {w_eq}/{len(tm)} entries equal map entry 15"
                                            f" (+{w_castle} castle cells drawn with the owner)")),
              (eq + castle == used >= 16 * 14, (f"BG2 tilemap: {eq}/{used} non-empty entries equal the map at column "
                                                f"{dx}, row {dy} (+{castle} castle cells drawn with the owner)")),
              (ch == chars, f"VRAM 0x8400 = map tiles entry 14 ({len(chars)} bytes)"),
              (cg in (pal, swapped), "CGRAM palettes 2-3 = ROM map palettes"
                                     + (" (palette 3 colours 13-14 swapped: water animation frame)" if cg == swapped
                                        else ""))]
    for ok, text in checks:
        print(f"[{'OK' if ok else 'NG'}] {text}")
    errors = sum(not ok for ok, _ in checks)
    print(f"time {time.time() - t0:.0f} s")
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
