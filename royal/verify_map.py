#!/usr/bin/env python3
"""Check the strategy map (rom.Rom.map_words / map_chr / map_rgb) and the province marker cells against the game
(needs Mesen 2, about 15 seconds).

On the scenario menu the game shows the map with each house's marker on the provinces it rules. For each of
the 4 scenarios (cursor moved down) the screen is read and compared with the ROM decoding:
- BG2 tilemap, 15x20 cells at tile (16, 3): equal to MAP_TILEMAP;
- the 8x8 tiles they use (VRAM): equal to the LZ stream MAP_CHR loaded at tile MAP_TILE0;
- CGRAM BG palettes 0-7: equal to STRATEGY_PALETTES; the map drawn from VRAM and CGRAM equals map_rgb;
- BG1 markers: tile 0x0A4 + house (palette 2) exactly at (16 + x, 3 + y) for the marker cell (x, y) of every
  province with an owner in that scenario, and nowhere else on the map.

Usage: .venv/bin/python royal/verify_map.py [--rom ROM]
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
from replay import end_frame, replay
from rom import (
    DEFAULT_ROM,
    MAP_H,
    MAP_ORIGIN,
    MAP_TILE0,
    MAP_W,
    SCENARIO_COUNT,
    STRATEGY_PALETTES,
    Rom,
    le16,
    render_tilemap,
)

BOOT = "w1500 start w200 start w200"            # title -> scenario menu
CHR, BG1_MAP, BG2_MAP = 0x4000, 0xD000, 0xE000   # VRAM bytes
MARKER = 0x08A4                                  # BG1 word of house 0's marker; house h = MARKER + h


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證戰略地圖與家標記")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    reads = [("vram", CHR, 0x8000), ("vram", BG1_MAP, 0x800), ("vram", BG2_MAP, 0x800), ("cgram", 0, 256)]
    runs = []
    for s in range(SCENARIO_COUNT):
        steps = "down:10 w60 " * s + "w120"
        runs.append({"steps": steps, "shot": end_frame(steps, 0), "read": reads})
    got = replay(args.rom, BOOT, end_frame(BOOT), runs)

    words, chr_ = rom.map_words(), rom.map_chr()
    want_rgb = rom.map_rgb()
    x0, y0 = MAP_ORIGIN
    errors = 0
    for s, (vchr, bg1, bg2, cg) in enumerate(got):
        shown = [le16(bg2, ((y0 + i // MAP_W) * 32 + x0 + i % MAP_W) * 2) for i in range(MAP_W * MAP_H)]
        cells = sum(a == b for a, b in zip(shown, words))
        used = sorted({w & 0x3FF for w in words})
        tiles_ok = sum(vchr[32 * t:32 * t + 32] == chr_[32 * (t - MAP_TILE0):32 * (t - MAP_TILE0) + 32] for t in used)
        pal_ok = cg == rom.data[STRATEGY_PALETTES:STRATEGY_PALETTES + 256]
        palettes = [[le16(cg, 32 * p + 2 * i) for i in range(16)] for p in range(8)]
        tiles = {t: vchr[32 * t:32 * t + 32] for t in used}
        rgb = render_tilemap(shown, MAP_W, tiles, palettes)
        px = sum(a == b for a, b in zip(rgb, want_rgb))
        want_marks = {(x0 + p["marker"][0], y0 + p["marker"][1]): MARKER + p["owner"]
                      for p in rom.provinces(s) if p["owner"] is not None}
        got_marks = {}
        for y in range(y0, y0 + MAP_H):
            for x in range(x0, x0 + MAP_W):
                e = le16(bg1, (y * 32 + x) * 2)
                if MARKER <= e < MARKER + 16:
                    got_marks[(x, y)] = e
        marks_ok = got_marks == want_marks
        errors += (len(words) - cells) + (len(used) - tiles_ok) + (not pal_ok) + (len(rgb) - px) + (not marks_ok)
        print(f"[scenario {s + 1}] tilemap {cells}/{len(words)}, tiles {tiles_ok}/{len(used)}, palettes "
              f"{'OK' if pal_ok else 'NG'}, pixels {px}/{len(rgb)}, markers {len(want_marks)} "
              + ("OK" if marks_ok else f"NG (got {sorted(got_marks.items())})"))
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
