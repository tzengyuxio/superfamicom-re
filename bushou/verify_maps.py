#!/usr/bin/env python3
"""Check the big map and the 48 field-battle maps against the game (needs Mesen 2, about a minute).

1. Big map, on the daimyo selection screen of scenario 1 (frame 2483): BG2 (tilemap VRAM word 0x0C00, CHR
   0x4000) must hold rom.map_bg_entries at tile (1, 2) and their tiles must equal rom.map_bg_tile; BG1
   (tilemap 0x0000, CHR 0x2000) at tile (2, 5) must be the 28 x 17 land bitmap (MAP_TILES, palette 7), where the
   game only repaints colour-7 pixels (faction colours); CGRAM palettes 0-7 must equal BG_PALETTES.
2. Field battles (bushou/tools/battle_capture.py): each of the 48 field maps is patched in place of 美濃's and
   the battle screen drawn by the game; its BG2 tilemap (32 x 28) must equal rom.battle_tilemap (cells holding
   a unit, bit 6 set by the game in the WRAM terrain, are skipped), the WRAM terrain must equal the ROM map
   outside those cells, the BG2 CHR must equal rom.battle_bg_tile and CGRAM 0-95 BATTLE_PALETTES.

Usage: .venv/bin/python bushou/verify_maps.py [--rom ROM] [--quick]
"""
import argparse
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "tools"))
from battle_capture import capture_fields
from replay import replay
from rom import (
    BATTLE_PALETTES,
    BG_PALETTES,
    DEFAULT_ROM,
    FIELD_COUNT,
    FIELD_W,
    MAP_BG_ORIGIN,
    MAP_BG_W,
    MAP_H,
    MAP_ORIGIN,
    MAP_TILES,
    MAP_W,
    Rom,
    decode_tile,
)

MAP_STEPS = "w900 start:10 w300 a:10 w200 a:10 w200 a:10 w200 a:10 w200 up:10 w60 a:10"


def check_big_map(rom: Rom, path: str) -> int:
    vram, cg = replay(path, MAP_STEPS, 2300, [{"shot": 183, "read": [("vram", 0, 0x10000), ("cgram", 0, 512)]}])[0]

    def entry(tm: int, x: int, y: int) -> int:
        a = 2 * (tm + y * 32 + x)
        return vram[a] | vram[a + 1] << 8

    bad_bg2 = 0
    for i, e in enumerate(rom.map_bg_entries()):
        ty, tx = divmod(i, MAP_BG_W)
        got = entry(0x0C00, MAP_BG_ORIGIN[0] + tx, MAP_BG_ORIGIN[1] + ty)
        n = got & 0x3FF
        bad_bg2 += got != e or vram[0x8000 + 32 * n:0x8000 + 32 * n + 32] != rom.map_bg_tile(n)
    print(f"[big map BG2] {MAP_BG_W * 21 - bad_bg2}/{MAP_BG_W * 21} tilemap entries and tiles match")
    bad_bg1, painted = 0, 0
    for t in range(MAP_W * MAP_H):
        e = entry(0, MAP_ORIGIN[0] + t % MAP_W, MAP_ORIGIN[1] + t // MAP_W)
        n = e & 0x3FF
        want = decode_tile(rom.data[MAP_TILES + 32 * t:MAP_TILES + 32 * t + 32])
        got = decode_tile(vram[0x4000 + 32 * n:0x4000 + 32 * n + 32])
        bad = sum(1 for a, b in zip(want, got) if a != b and a != 7) + (e >> 10 & 7 != 7)
        painted += sum(1 for a, b in zip(want, got) if a != b)
        bad_bg1 += bad > 0
    print(f"[big map BG1] {MAP_W * MAP_H - bad_bg1}/{MAP_W * MAP_H} land tiles match "
          f"(palette 7; {painted} colour-7 pixels repainted with faction colours)")
    pal_ok = cg[:256] == rom.data[BG_PALETTES:BG_PALETTES + 256]
    print(f"[big map CGRAM] palettes 0-7: {'OK' if pal_ok else 'NG'}")
    return bad_bg2 + bad_bg1 + (not pal_ok)


def check_fields(rom: Rom, path: str, maps: list[int]) -> int:
    shown = capture_fields(path, [rom.battle_terrain(False, n) for n in maps])
    bad_maps, units = [], 0
    for n, s in zip(maps, shown):
        rom_map = rom.battle_terrain(False, n)
        skip = set()
        for i, t in enumerate(s["terrain"]):
            if t & 0x40 or t != rom_map[i]:
                units += 1
                r, c = divmod(i, FIELD_W)
                x, y = 2 + 2 * c, 5 + 2 * r + (c & 1)
                skip |= {(y + k // 2) * 32 + x + k % 2 for k in range(4)}
                if t & 0x3F not in (rom_map[i], 0x0A):
                    bad_maps.append((n, "terrain", i))
        want = rom.battle_tilemap(rom_map)
        bad = [i for i in range(32 * 28) if i not in skip and s["tilemap"][i] != want[i]]
        if bad:
            bad_maps.append((n, "tilemap", len(bad)))
    print(f"[field maps] {len(maps) - len({b[0] for b in bad_maps})}/{len(maps)}: BG2 tilemap (32 x 28) and WRAM "
          f"terrain match ({units} unit cells skipped)" + (f" NG {bad_maps[:10]}" if bad_maps else ""))
    first = shown[0]
    chr_bad = [n for n in range(0x400) if rom.battle_bg_tile(n) != bytes(32)
               and first["chr"][32 * n:32 * n + 32] != rom.battle_bg_tile(n)]
    used = len([n for n in range(0x400) if rom.battle_bg_tile(n) != bytes(32)])
    print(f"[field CHR] {used - len(chr_bad)}/{used} BG2 tiles from the battle CHR DMAs match")
    pal_ok = first["cgram"][:0xC0] == rom.data[BATTLE_PALETTES:BATTLE_PALETTES + 0xC0]
    print(f"[field CGRAM] BG palettes 0-5: {'OK' if pal_ok else 'NG'}")
    return len(bad_maps) + len(chr_bad) + (not pal_ok)


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證大地圖與野戰地圖")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--quick", action="store_true", help="only 6 field maps")
    ap.add_argument("--big-map-only", action="store_true", help=argparse.SUPPRESS)
    args = ap.parse_args()
    t0 = time.time()
    rom = Rom(args.rom)
    if args.big_map_only:
        raise SystemExit(1 if check_big_map(rom, args.rom) else 0)
    # Mesen can be opened only once per process: the big map runs in a child process
    child = subprocess.run([sys.executable, __file__, "--rom", args.rom, "--big-map-only"], check=False,
                           capture_output=True,
                           text=True)
    print("\n".join(line[line.index("[big map"):] for line in child.stdout.splitlines() if "[big map" in line))
    errors = child.returncode != 0
    errors += check_fields(rom, args.rom, list(range(0, FIELD_COUNT, 8) if args.quick else range(FIELD_COUNT)))
    print(f"{time.time() - t0:.0f} s")
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
