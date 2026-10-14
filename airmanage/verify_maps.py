#!/usr/bin/env python3
"""Check the world map (ALMAPE) and the city map positions against the game in Mesen.

Main screen of scenario 1 (home London): the BG tilemap at VRAM $F000 (32 x 32), the BG CHR at VRAM $4000
(tiles 0-767: the rows the screen can show; tiles 768-1023 are the bottom quarter of the map, open sea, and
are not loaded), BG palette 1 (CGRAM $20) and the 22 city marker sprites (tile 23, the home city 20), which
the game puts at ((x - scroll) & 255, y) from the table at ALNMAIN $53A1 (scroll = WRAM $480C).
Colours 3 and 4 of palette 1 are the blinking cursor colours (ALMAPE has 0000 / 001F there).
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "tools"))
import vm
from replay import replay
from rom import CITY_COUNT, DEFAULT_ROM, Rom, le16

TILEMAP_VRAM, CHR_VRAM, CHR_TILES = 0xF000, 0x4000, 768


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    r = Rom(args.rom)
    t = time.time()
    pal, tm, chr_ = r.world_map()
    a = vm.addresses(r.rev)
    runs = [{"shot": 60, "read": [("vram", TILEMAP_VRAM, 0x800), ("vram", CHR_VRAM, 32 * CHR_TILES),
                                  ("cgram", 0x20, 32), ("oam", 0, 512), ("wram", a["scroll"], 2)]}]
    vtm, vchr, cg, oam, scroll = replay(r.path, vm.boot(0), vm.MAIN_FRAME, runs, extra_lua=vm.boot_lua(r.rev))[0]
    bad = 0
    n = sum(le16(vtm, 2 * i) == tm[i] for i in range(len(tm)))
    print(f"tilemap: {n}/{len(tm)} entries OK")
    bad += len(tm) - n
    n = sum(vchr[32 * i:32 * i + 32] == chr_[32 * i:32 * i + 32] for i in range(CHR_TILES))
    print(f"CHR: {n}/{CHR_TILES} tiles OK")
    bad += CHR_TILES - n
    cols = [le16(cg, 2 * i) for i in range(16)]
    n = sum(cols[i] == pal[i] for i in range(16) if i not in (3, 4))
    print(f"palette 1: {n}/14 colours OK (3, 4: game {cols[3]:04X} {cols[4]:04X}, ALMAPE {pal[3]:04X} {pal[4]:04X})")
    bad += 14 - n
    sc = le16(scroll, 0)
    sprites = {(oam[4 * i], oam[4 * i + 1]) for i in range(128) if oam[4 * i + 2] in (20, 23)}  # marker tiles
    n = 0
    for c, city in enumerate(r.cities()):
        want = ((city["map_x"] - sc) & 0xFF, city["map_y"])
        if want in sprites:
            n += 1
        else:
            print(f"  city {c}: no marker sprite at {want}")
    print(f"city markers: {n}/{CITY_COUNT} OK (scroll {sc - 0x10000 if sc & 0x8000 else sc})")
    bad += CITY_COUNT - n
    print(f"{'OK' if not bad else f'{bad} mismatches'} ({time.time() - t:.0f} s)")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
