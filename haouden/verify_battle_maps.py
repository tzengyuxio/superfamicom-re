#!/usr/bin/env python3
"""Check the 143 battle maps (rom.Rom.battle_tilemaps) against the game (needs Mesen 2, about 6 minutes).

A new game is started with 0 player daimyo, 好戦的 and 他国合戦 = 見る, so the computer's battles are shown;
the first one starts about frame 20400 (map 134, a castle-less map; Rev 1: about frame 19900, map 131).
A savestate is taken before it; for every
map m the battle loader's three reads of the map number $7E:8733 ($CA:36D8, $CA:3BDE, $CA:3C1F) are patched
to LDA #m and the state replayed, so the game decompresses LZ entry 466 + m (and its edge record in entry 609)
and builds its two BG tilemap buffers $7F:0000 (ground) and $7F:20D0 (overlay), 84 x 50 entries each.
For every one of the 920 cells plus the 20 half cells of the top edge, the 2x2 entries must equal the ROM
decoding (metatile tables, flips). Overlay entries the game adds on top of cells that have no overlay in
the map (unit / camp markers) are counted apart. The unpatched run also checks the tiles at VRAM 0x8200
(LZ entry 441) and that CGRAM palettes 2-4 are one of the 3 palette sets (set 0 in the original, set 2 in Rev 1).

Usage: .venv/bin/python haouden/verify_battle_maps.py [--rom ROM] [--quick]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "tools"))
from replay import replay
from rom import BATTLE_CHARS, BATTLE_COUNT, BATTLE_H, BATTLE_W, DEFAULT_ROM, Rom

# title -> 新しく始める -> 1551, 好戦的, 初級, 0 daimyo, 他国合戦 見る -> 実行 -> confirm; then the computer plays
BOOT = ("w1500 start:10 w200 a:10 w300 a w60 a w60 right w60 a w60 a w60 left w60 a w60 left w60 a w60 a w100"
        " a:10 w100 a:20 w400")
SAVE_AT = {0: 20000, 1: 19600}                  # per revision: the computer plays differently
SHOT = 1200
MAP_READ = bytes.fromhex("af33877e")            # LDA $7E8733
LOADER = (0xA3000, 0xA4400)                     # the battle loader's bank range searched for MAP_READ
BUF_W, BUF_H = 84, 50
GROUND, OVERLAY = 0x10000, 0x120D0              # WRAM offsets of $7F:0000 / $7F:20D0


def cells(rom: Rom, m: int, buf: bytes, overlay: bool) -> tuple[int, int, int]:
    """(equal cells, cells where the game added an overlay, other differences)."""
    want = rom.battle_tilemaps(m)[overlay]
    w = 2 * BATTLE_W
    entry = rom.entry(466 + m)

    def got(x: int, y: int) -> int:
        a = 2 * ((y + 2) * BUF_W + x + 2)
        return buf[a] | buf[a + 1] << 8

    eq = added = other = 0
    spots = [(c, r) for c in range(BATTLE_W) for r in range(BATTLE_H)] + [(c, -1) for c in range(1, BATTLE_W, 2)]
    for c, r in spots:
        y = 2 * r + (c & 1)
        pos = [(2 * c, y), (2 * c + 1, y), (2 * c, y + 1), (2 * c + 1, y + 1)]
        pos = [(x, yy) for x, yy in pos if yy >= 0]
        if all(want[yy * w + x] == got(x, yy) for x, yy in pos):
            eq += 1
        elif overlay and r >= 0 and entry[2 * (c * BATTLE_H + r) + 1] == 0xFF:
            added += 1
        else:
            other += 1
    return eq, added, other


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證 143 張戰場地圖")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--quick", action="store_true", help="only every 8th map")
    args = ap.parse_args()
    t0 = time.time()
    rom = Rom(args.rom)
    sites = []
    p = rom.data.find(MAP_READ, LOADER[0], LOADER[1])
    while p >= 0:
        sites.append(p)
        p = rom.data.find(MAP_READ, p + 1, LOADER[1])
    assert len(sites) == 3, sites
    maps = list(range(0, BATTLE_COUNT, 8 if args.quick else 1))
    read = [("wram", GROUND, 2 * BUF_W * BUF_H), ("wram", OVERLAY, 2 * BUF_W * BUF_H), ("wram", 0x8733, 1)]
    first = [{"shot": SHOT, "read": read + [("vram", 0x8200, len(rom.entry(BATTLE_CHARS))), ("cgram", 0x40, 0x60)]}]
    runs = first + [{"patch": [(s, bytes([0xA9, m, 0x00, 0xEA])) for s in sites], "shot": SHOT, "read": read}
                    for m in maps]
    shots = replay(args.rom, BOOT, SAVE_AT[rom.rev], runs)
    errors = 0
    g, o, mid, chars, cg = shots[0]
    sets = [b"".join(c.to_bytes(2, "little") for k in range(2, 5) for c in rom.battle_palettes(n)[k]) for n in range(3)]
    pset = sets.index(cg) if cg in sets else None
    print(f"[unpatched] the computer's battle uses map {mid[0]}; ground {cells(rom, mid[0], g, False)[0]}/940 cells; "
          f"VRAM 0x8200 = entry {BATTLE_CHARS}: {chars == rom.entry(BATTLE_CHARS)}; "
          f"CGRAM palettes 2-4 = palette set {pset}")
    errors += chars != rom.entry(BATTLE_CHARS) or pset is None
    total = [0, 0, 0, 0]
    bad = []
    for m, (g, o, _) in zip(maps, shots[1:]):
        ge, _, gx = cells(rom, m, g, False)
        oe, oa, ox = cells(rom, m, o, True)
        total[0] += ge
        total[1] += oe
        total[2] += oa
        total[3] += gx + ox
        if gx or ox:
            bad.append((m, gx, ox))
    n = len(maps)
    print(f"[maps] {n - len(bad)}/{n} maps built by the game equal the ROM decoding: ground {total[0]}/{940 * n} "
          f"cells, overlay {total[1]}/{940 * n} cells, plus {total[2]} cells where the game drew a marker over "
          f"an empty overlay" + (f"; NG (map, ground diff, overlay diff) {bad[:10]}" if bad else ""))
    errors += len(bad)
    print(f"time {time.time() - t0:.0f} s")
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
