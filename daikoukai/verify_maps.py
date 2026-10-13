#!/usr/bin/env python3
"""Check the world-map decoding (rom.Rom.chunk_tilemaps / map_band / map_chr / map_palette) against the game
(Mesen 2, ~1.5 min).

A new game is played to Lisbon's harbor master and a savestate taken there. For every run the fleet's location
(WRAM $7E:E564, chunk x/y + metatile x/y, the same 4 bytes as a port record) is overwritten with another port's
location, or with a spot near the poles, and the fleet leaves port: the game draws the sea screen around the
new place. The screen shows one chunk (28 x 28 tiles at tilemap column 2, row 1). Which one is not simply the
fleet record (at sea its 4 bytes change meaning, 未解), so the script takes the chunk around the patched place and
the fleet's chunk that matches best. Checked against the ROM decoding:
- BG1 (land) and BG2 (sea) tilemap entries of the 28 x 28 window; port marks (BG1 tiles >= 0xE8) are counted
  apart, the static map has none;
- the graphics set $7E:F164 = MAP_BAND[cy // 3];
- land CHR (VRAM tiles 0x77-0xBE) and BG palette 2 (one of the band's 4 animation frames).
The animated sea tiles (0xBF-0xDE) are only reported: rom.SEA_CHR holds one frame.

Usage: .venv/bin/python daikoukai/verify_maps.py [--rom ROM]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "tools"))
from boot import DEPART, HARBOR, HARBOR_SAVE, NEW_GAME, SEA_SHOT
from replay import replay
from rom import CHUNK_TILES, DEFAULT_ROM, MAP_CHR_COUNT, MAP_CHR_TILE, PORT_SIZE, PORTS, SEA_CHR, Rom, le16

FLEET = 0xE564
BAND = 0xF164
BG1, BG2, CHR = 0xD000, 0xE000, 0x2000
PORT_MARK = 0xE8
TEST_PORTS = [15, 20, 51, 10, 30, 47, 41, 26, 37]
POLAR = [(40, 1), (30, 34)]     # chunks of the two outer latitude bands (MAP_BAND 3), no port there


def polar_spot(rom: Rom, cx: int, cy: int) -> bytes:
    """A land metatile next to the sea in chunk (cx, cy), as a fleet location."""
    m = rom.chunk_metatiles(cx, cy)
    for i, v in enumerate(m):
        x, y = i % 14, i // 14
        if v not in (0, 17) and 0 < x < 13 and 0 < y < 13 and any(m[i + d] in (0, 17) for d in (-1, 1, -14, 14)):
            return bytes([cx, cy, x, y])
    raise ValueError((cx, cy))


def compare(rom: Rom, vram: bytes, cx: int, cy: int) -> tuple[int, int]:
    """(matching tiles, port-mark tiles) of the 28 x 28 window against chunk (cx, cy)."""
    bg1, bg2 = rom.chunk_tilemaps(cx, cy)
    ok = marks = 0
    for i in range(CHUNK_TILES ** 2):
        x, y = 2 + i % CHUNK_TILES, 1 + i // CHUNK_TILES
        g1, g2 = le16(vram, BG1 + 64 * y + 2 * x), le16(vram, BG2 + 64 * y + 2 * x)
        if (g1 & 0x3FF) >= PORT_MARK and g2 == bg2[i]:
            marks += 1
        elif (g1, g2) == (bg1[i], bg2[i]):
            ok += 1
    return ok, marks


def main() -> None:
    ap = argparse.ArgumentParser(description="以模擬器驗證世界地圖")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    t0 = time.time()
    rom = Rom(args.rom)
    places = [("リスボン（不改）", None)]
    places += [(rom.ports()[p]["name"], rom.data[PORTS + PORT_SIZE * p + 15:][:4]) for p in TEST_PORTS]
    places += [(f"chunk {cx},{cy}", polar_spot(rom, cx, cy)) for cx, cy in POLAR]
    reads = [("vram", 0, 0x10000), ("cgram", 0x40, 32), ("wram", FLEET, 4), ("wram", BAND, 1)]
    runs = [{"wram": [] if loc is None else [(FLEET, loc)], "steps": DEPART, "shot": SEA_SHOT, "read": reads}
            for _, loc in places]
    res = replay(args.rom, NEW_GAME + HARBOR, HARBOR_SAVE, runs)
    errors = 0
    for (name, loc), (vram, pal2, fleet, band) in zip(places, res):
        near = {(fleet[0], fleet[1]), *([] if loc is None else [(loc[0], loc[1])])}
        cands = {(x + dx, y + dy) for x, y in near for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
        (ok, marks), cx, cy = max((compare(rom, vram, x, y), x, y) for x, y in cands)
        want_band = rom.map_band(cy)
        chr_ = rom.map_chr(want_band)
        land = sum(vram[CHR + 32 * t:CHR + 32 * t + 32] == chr_[t]
                   for t in range(MAP_CHR_TILE, MAP_CHR_TILE + MAP_CHR_COUNT))
        sea = sum(vram[CHR + 32 * t:CHR + 32 * t + 32] == chr_[t] for t in SEA_CHR)
        frames = [f for f in range(4) if rom.data[rom.map_palette(want_band, f):][:32] == pal2]
        good = ok + marks == CHUNK_TILES ** 2 and band[0] == want_band and land == MAP_CHR_COUNT and frames
        errors += not good
        print(f"[{'OK' if good else 'NG'}] {name}: chunk ({cx},{cy}) band {band[0]} (MAP_BAND {want_band}), "
              f"tiles {ok}/{CHUNK_TILES ** 2 - marks} + {marks} port-mark tiles, land CHR {land}/{MAP_CHR_COUNT}, "
              f"palette 2 = frame {frames[0] if frames else '-'}; sea CHR {sea}/{len(SEA_CHR)} = SEA_CHR frame")
    bands = sorted({r[3][0] for r in res})
    print(f"bands seen: {bands}; {len(places)} runs, {time.time() - t0:.0f} s")
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
