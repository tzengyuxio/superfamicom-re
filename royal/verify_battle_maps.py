#!/usr/bin/env python3
"""Check the 30 battle maps (rom.Rom.battle_grid / battle_words / battle_rgb) against the game (needs Mesen 2,
about 30 seconds).

The demo play (title -> scenario 1 -> デモプレイ) runs into a battle at キャメロン (province 0) by itself. A
savestate is taken before it starts; for each province p the 80 bytes of province 0's grid in the ROM are
replaced with grid p, so the game builds battlefield p. 1000 frames later (during the battle) the game's
copy of the grid at WRAM $7E:FF00 (high nibbles), the BG2 tilemap (20x16 tiles at (6, 6)), the BG tiles and
CGRAM palettes 1-2 are compared with the ROM decoding, and the battlefield drawn from VRAM/CGRAM with
battle_rgb (water tiles at the animation frame the game shows). Units are sprites/BG1 and do not cover BG2.

Usage: .venv/bin/python royal/verify_battle_maps.py [--rom ROM]
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
from replay import replay
from rom import (
    BATTLE_GRIDS,
    BATTLE_H,
    BATTLE_ORIGIN,
    BATTLE_PALETTES,
    BATTLE_W,
    BATTLE_WRAM,
    DEFAULT_ROM,
    PROVINCE_COUNT,
    WATER_FRAMES,
    Rom,
    le16,
    render_tilemap,
)

BOOT = "w1500 start w200 start w200 a w200 a w200 right right a w300 a w300"   # demo play, ends at frame 3102
SAVE_AT, SHOT = 4000, 1000   # later in the battle cells can change (province 8: a 柵 appears at 1400)
CHR, BG2_MAP = 0x4000, 0xE000


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證 30 張戰場地圖")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    reads = [("wram", BATTLE_WRAM, 80), ("vram", BG2_MAP, 0x800), ("vram", CHR, 0x1000), ("cgram", 0, 96)]
    runs = [{"patch": [(BATTLE_GRIDS, rom.battle_grid(p))], "shot": SHOT, "read": reads} for p in range(PROVINCE_COUNT)]
    got = replay(args.rom, BOOT, SAVE_AT, runs)

    frames = [rom.battle_chr(f) for f in range(WATER_FRAMES)]
    pal_rom = rom.data[BATTLE_PALETTES + 32:BATTLE_PALETTES + 96]
    w, h = BATTLE_W * 2, BATTLE_H * 2
    x0, y0 = BATTLE_ORIGIN
    totals = [0] * 5
    errors = 0
    for p, (grid, bg2, vchr, cg) in enumerate(got):
        grid_ok = bytes(b & 0xF0 for b in grid) == rom.battle_grid(p)
        shown = [le16(bg2, ((y0 + i // w) * 32 + x0 + i % w) * 2) for i in range(w * h)]
        want = rom.battle_words(p)
        cells = sum(a == b for a, b in zip(shown, want))
        frame = next((f for f in range(WATER_FRAMES)
                      if all(vchr[32 * t:32 * t + 32] == raw for t, raw in frames[f].items())), None)
        tiles_ok = frame is not None
        pal_ok = cg[32:96] == pal_rom
        palettes = [[le16(cg, 32 * q + 2 * i) for i in range(16)] if q < 3 else [0] * 16 for q in range(8)]
        rgb = render_tilemap(shown, w, {t: vchr[32 * t:32 * t + 32] for t in range(128)}, palettes)
        want_rgb = render_tilemap(want, w, frames[frame or 0], rom.palettes(BATTLE_PALETTES))
        px = sum(a == b for a, b in zip(rgb, want_rgb))
        ok = grid_ok and cells == len(want) and tiles_ok and pal_ok and px == len(rgb)
        errors += not ok
        for k, v in enumerate((grid_ok, cells == len(want), tiles_ok, pal_ok, px == len(rgb))):
            totals[k] += v
        if not ok:
            print(f"[province {p}] NG: grid {grid_ok}, cells {cells}/{len(want)}, tiles {tiles_ok}, palettes {pal_ok}, "
                  f"pixels {px}/{len(rgb)}")
    n = PROVINCE_COUNT
    print(f"[battle maps] WRAM grid {totals[0]}/{n}, BG2 tilemap {totals[1]}/{n} (320 cells each), "
          f"BG tiles {totals[2]}/{n}, palettes {totals[3]}/{n}, pixels {totals[4]}/{n} (160x128 each)")
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
