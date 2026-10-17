#!/usr/bin/env python3
"""Check the strategic map decoding (rom.Rom.map_vram / map_cgram) against the game.

From the scenario list (savestate) each run plays one scenario to the map of the first month (tools/sequences.py
TO_MAP; 1/4 scale view). VRAM 0x0000-0x7FFF (mode 7: tilemap + 8bpp tiles, with the city markers and castle
frames of every country) must equal rom.Rom.map_vram(scenario), and the CGRAM shadow ($0500) right after the map
palette routine $05:81B1 must equal rom.Rom.map_cgram(month $0127, zoom $DB != 0x400) byte for byte. On
screen the window palette ($02:CB1B in Rev 0) then replaces rows 5, 14 and 15 (rom.Rom.map_screen_palette):
colours 1-15 of those rows in CGRAM must equal it (colour 0 of rows 5 / 15 blinks; the other rows hold sprite
and window colours).

Usage: .venv/bin/python yokoyama/verify_maps.py [--rom ROM]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
sys.path.insert(0, os.path.join(HERE, "tools"))
import replay
import sequences as q
from rom import DEFAULT_ROM, SCENARIO_YEARS, WINDOW_ROWS, Rom


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證大地圖（mode 7 VRAM 與調色盤）")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    t0 = time.time()
    rom = Rom(args.rom)
    runs = []
    for k in (0, 1):
        steps = q.TO_MAP[k][len(q.TO_SCENARIOS):]
        runs.append({"steps": steps, "shot": q.end_frame(steps, 0) + 20,
                     "read": [("vram", 0, 0x8000), ("cgram", 0, 0x200)]})
    results = replay.replay(rom.path, q.TO_SCENARIOS, q.end_frame(q.TO_SCENARIOS), runs,
                            extra_lua=q.MAP_PALETTE_LUA)
    errors = 0
    window = rom.raw(rom.window_palette_at + 2, 30) * len(WINDOW_ROWS)
    for k, (vram, cgram, pal) in enumerate(results):
        zoom, month = pal[512] | pal[513] << 8, pal[514] | pal[515] << 8
        parts = []
        for name, got, want in (("VRAM", vram, rom.map_vram(k)),
                                ("palette", pal[:512], rom.map_cgram(month, zoom != 0x400)),
                                ("window rows", b"".join(cgram[32 * r + 2:32 * r + 32] for r in WINDOW_ROWS), window)):
            bad = sum(a != b for a, b in zip(got, want)) + abs(len(got) - len(want))
            errors += bad
            parts.append(f"{name} {len(want) - bad}/{len(want)}")
        print(f"scenario {SCENARIO_YEARS[k]} (month {month + 1}, matrix {zoom:#x}): bytes equal " + ", ".join(parts))
    print(f"{time.time() - t0:.0f} s")
    print("ALL OK" if not errors else f"{errors} mismatch(es)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
