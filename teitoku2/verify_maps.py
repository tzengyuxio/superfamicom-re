#!/usr/bin/env python3
"""Check the world map bitmap (rom.Rom.map_bits, LZ entry 0, 1 = sea) against the game (needs Mesen 2, about 1
minute per ROM).

1. Scenario 0 as 日本: on the main screen WRAM $7F:8000-$7F:FE8F must hold LZ entry 0 as Rom.entry decompresses
   it (32400 bytes = 640 x 405 bits), which shows the game keeps the map bitmap and decompresses it like
   tools/koei_lz.py.
2. Coordinates (no emulator): in all 10 scenarios the 拠点 (Rom.kyoten) must lie on land or next to it (at most 1
   pixel from a land pixel), every submarine unit and every fleet that is not in port at sea (fleet +5 bit 4 set =
   in port, +1 = the base number; such fleets are left out). Bases (Rom.bases X / Y) are reported, not checked:
   small islands such as Midway are not in the bitmap.

Usage: .venv/bin/python teitoku2/verify_maps.py [--rom ROM]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
sys.path.insert(0, os.path.join(HERE, "tools"))
import rom as R
from replay import replay
from sequences import TO_SCENARIOS, end_frame, expand, new_game

MAP_WRAM = 0x18000  # $7F:8000 as an offset in the 128 KB WRAM
TO_MAIN = f"{TO_SCENARIOS} {new_game(0)}"


def land_distance(rom: R.Rom, x: int, y: int, limit: int = 40) -> int:
    for d in range(limit):
        for dx in range(-d, d + 1):
            for dy in range(-d, d + 1):
                if max(abs(dx), abs(dy)) == d and 0 <= x + dx < R.MAP_W and 0 <= y + dy < R.MAP_H \
                        and not rom.is_sea(x + dx, y + dy):
                    return d
    return limit


def main() -> None:
    ap = argparse.ArgumentParser(description="大地圖位圖與遊戲比對")
    ap.add_argument("--rom", default=R.DEFAULT_ROM)
    args = ap.parse_args()
    t0 = time.time()
    rom = R.Rom(args.rom)
    bits = rom.map_bits()
    boot = expand(TO_MAIN)
    (wram,), = replay(args.rom, boot, end_frame(boot), [{"steps": "w10", "shot": 30,
                                                         "read": [("wram", MAP_WRAM, len(bits))]}])
    errors = 0
    same = sum(a == b for a, b in zip(wram, bits))
    errors += same != len(bits)
    print(f"[bitmap] WRAM $7F:8000 = LZ entry 0: {same}/{len(bits)} bytes equal")

    ky_bad, sub_n, sub_bad, fl_n, fl_bad, base_far = set(), 0, [], 0, [], set()
    for sc in range(R.SCENARIO_COUNT):
        img = rom.wram_image(sc)
        for k in rom.kyoten(img):
            if land_distance(rom, k["x"], k["y"], 3) > 1:
                ky_bad.add(k["name"])
        for s in rom.submarines(img):
            if s["class"] != 0xFF:
                sub_n += 1
                if not rom.is_sea(s["x"], s["y"]):
                    sub_bad.append((sc, s["id"]))
        for f in rom.fleets(img):
            if f["admiral"] >= 0 and not f["mission"] & 0x10:
                fl_n += 1
                if not rom.is_sea(f["x"], f["y"]):
                    fl_bad.append((sc, f["id"]))
        base_far |= {b["code"] for b in rom.bases(img) if land_distance(rom, b["x"], b["y"], 6) > 5}
    errors += bool(ky_bad) + bool(sub_bad) + bool(fl_bad)
    print(f"[kyoten] {R.KYOTEN_COUNT - len(ky_bad)}/{R.KYOTEN_COUNT} 拠点 on land (or 1 px from it)"
          + (f" NG {sorted(ky_bad)}" if ky_bad else ""))
    print(f"[submarines] {sub_n - len(sub_bad)}/{sub_n} submarine units of the 10 scenarios at sea"
          + (f" NG {sub_bad[:8]}" if sub_bad else ""))
    print(f"[fleets] {fl_n - len(fl_bad)}/{fl_n} fleets out of port at sea" + (f" NG {fl_bad[:8]}" if fl_bad else ""))
    print(f"[bases] {R.BASE_COUNT - len(base_far)}/{R.BASE_COUNT} bases within 5 px of land (not checked; farther: "
          f"{' '.join(sorted(base_far))})")
    print(f"({time.time() - t0:.0f} s)")
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
