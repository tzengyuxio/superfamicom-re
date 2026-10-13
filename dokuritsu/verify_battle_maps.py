#!/usr/bin/env python3
"""Check the 53 HEX battle maps (rom.Rom.battle_map / cell_tiles / cell_pos) against the game (needs Mesen 2).

A new game is started with two computer sides and HEX戦 = 見る, so the computer's battles are shown; the first
one (map 10, Portsmouth, about frame 16600) is loaded by $C1:7A44 / $C1:7ABD, which copy the map of the
location $C8:0AA0($7E:2050) from LZ entries 1 and 2 to $7E:4363 / $7E:44B3; $C6:6CAB then builds the BG2
tilemap in $7F:8000 (32 x 28).
A savestate is taken before it; for every map m both reads of the location id (LDA $00 at $C1:7A52 and
$C1:7ACB) are patched to LDA #m and the state replayed. Checked per map: the two WRAM copies equal the ROM
streams, and for each of the 168 hexes the 4 tilemap entries equal the decoding (tile + 0x100, palette 5).
The unpatched run also checks the tiles at VRAM tile 0x2B9 (LZ entry 241) and CGRAM palette 5 (BATTLE_PALETTE).

Usage: .venv/bin/python dokuritsu/verify_battle_maps.py [--rom ROM] [--quick]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "tools"))
from replay import replay
from rom import (
    BATTLE_MAP_BYTES,
    BATTLE_PALETTE,
    BATTLE_TILE0,
    BATTLE_TM_H,
    BATTLE_TM_W,
    DEFAULT_ROM,
    LOCATION_COUNT,
    Rom,
    le16,
)

# title -> new game -> 2 computer sides, HEX戦 見る -> confirm; then the computer plays
BOOT = ("w9800 start:10 w200 a:10 w200 a:10 w200 down:10 w60 down:10 w60 a:10 w400 down:10 w100 down:10 w100"
        " down:10 w100 a:10 w100 down:10 w100 down:10 w100 down:10 w100 down:10 w100 a:10 w200 a:10 w300")
SAVE_AT = 16300
SHOT = 2400
SITES = [0x17A52, 0x17ACB]          # LDA $00 (A 8-bit) after JSL $C8:0AA0
A_WRAM, B_WRAM, TM_WRAM = 0x4363, 0x44B3, 0x18000


def check_map(rom: Rom, m: int, a: bytes, b: bytes, tm: bytes) -> tuple[bool, int]:
    """(WRAM copies equal ROM, hexes whose 4 tilemap entries equal the decoding)."""
    bm = rom.battle_map(m)
    ok = 0
    for cell in bm["cells"]:
        cx, cy = rom.cell_pos(cell["x"], cell["y"])
        want = [(t + 0x100) | 5 << 10 for t in rom.cell_tiles(cell)]
        got = [le16(tm, 2 * ((cy + k // 2) * BATTLE_TM_W + cx + k % 2)) for k in range(4)]
        ok += want == got
    return a == bm["a"] and b == bm["b"], ok


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證 53 張 HEX 戰場地圖")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--quick", action="store_true", help="only every 8th map")
    args = ap.parse_args()
    t0 = time.time()
    rom = Rom(args.rom)
    for s in SITES:
        assert rom.data[s - 2:s + 2] == bytes.fromhex("e220a500"), hex(s)
    maps = list(range(0, LOCATION_COUNT, 8 if args.quick else 1))
    read = [("wram", A_WRAM, BATTLE_MAP_BYTES), ("wram", B_WRAM, BATTLE_MAP_BYTES),
            ("wram", TM_WRAM, 2 * BATTLE_TM_W * BATTLE_TM_H)]
    chars = rom.battle_chars()
    first = [{"shot": SHOT, "read": read + [("vram", 32 * BATTLE_TILE0, len(chars)), ("cgram", 0xA0, 32)]}]
    runs = first + [{"patch": [(s, bytes([0xA9, m])) for s in SITES], "shot": SHOT, "read": read} for m in maps]
    shots = replay(args.rom, BOOT, SAVE_AT, runs)
    errors = 0
    a, b, tm, vram, cg = shots[0]
    m0 = next((m for m in range(LOCATION_COUNT) if rom.battle_map(m)["a"] == a), -1)
    same, ok = check_map(rom, m0, a, b, tm)
    pal_ok = cg == rom.data[BATTLE_PALETTE:BATTLE_PALETTE + 32]
    print(f"[unpatched] the computer's battle is at location {m0}: WRAM copies = ROM {same}, hexes {ok}/168; "
          f"VRAM tile 0x{BATTLE_TILE0:X} = LZ entry 241: {vram == chars}; CGRAM palette 5 = 0x{BATTLE_PALETTE:X}: "
          f"{pal_ok}")
    errors += (not same) + (ok != 168) + (vram != chars) + (not pal_ok)
    bad, total = [], 0
    for m, (a, b, tm) in zip(maps, shots[1:]):
        same, ok = check_map(rom, m, a, b, tm)
        total += ok
        if not same or ok != 168:
            bad.append((m, same, ok))
    n = len(maps)
    print(f"[maps] {n - len(bad)}/{n} maps: WRAM copies equal LZ entries 1/2 and the game's tilemap equals the "
          f"decoding, {total}/{168 * n} hexes" + (f"; NG (map, copies, hexes) {bad[:10]}" if bad else ""))
    errors += len(bad)
    print(f"time {time.time() - t0:.0f} s")
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
