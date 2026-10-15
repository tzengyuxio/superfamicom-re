#!/usr/bin/env python3
"""Check the scenario decoding (rom.Rom.scenario_image, scenario_titles) against the game (needs Mesen 2, about
20 seconds).

From the scenario list (savestate replay, tools/replay.py):
  * run 0 reads the list itself (BG3): every title line must be drawn from the ROM text at SCENARIO_MENU
    (full-width codes as their glyphs, digits as half-width digits, other single bytes one fixed half-width
    glyph each);
  * runs 1-4 choose scenario 1-4 and, 600 frames later, read WRAM $7E:2000-$3D2A, which must equal
    Rom.scenario_image(s) byte for byte (the two blocks, the 7 per-scenario tables, $2001 = year - 1).
The province, daimyo and name fields inside the image are checked on screen by verify_persons.py.

Usage: .venv/bin/python zenkoku/verify_scenarios.py [--rom ROM]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
from replay import replay
from rom import CODE_BASE, DEFAULT_ROM, HALF_DIGIT0, SCENARIO_COUNT, SCENARIO_MENU, WRAM_BASE, WRAM_END, Rom
from scenes import MENU, Screen, length, save_frame, scenario

TITLE_ROWS = [6, 9, 12, 15]     # BG3 tile rows of the 4 title lines
TITLE_X = 5


def title_codes(rom: Rom) -> list[list[int]]:
    out, o = [], SCENARIO_MENU
    for _ in range(SCENARIO_COUNT):
        end = rom.data.index(b"\0", o)
        out.append(rom.codes(rom.data[o:end]))
        o = end + 1
    return out


def check_line(sc: Screen, tx: int, ty: int, codes: list[int], half_map: dict) -> bool:
    for c in codes:
        if c >= CODE_BASE:
            if sc.glyphs(tx, ty, 1, stop_blank=False) != [c - CODE_BASE]:
                return False
            tx += 2
            continue
        k = sc.half.get(sc.tile(tx, ty) + sc.tile(tx, ty + 1))
        if c == 0x20:
            ok = not any(sc.tile(tx, ty) + sc.tile(tx, ty + 1))
        elif 0x30 <= c <= 0x39:
            ok = k == HALF_DIGIT0 + c - 0x30
        else:
            ok = k is not None and half_map.setdefault(c, k) == k
        if not ok:
            return False
        tx += 1
    return True


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證劇本載入（WRAM 映像）與劇本標題")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    t0 = time.time()
    rom = Rom(args.rom)
    runs = [{"steps": "w10", "shot": 10, "read": [("vram", 0, 0x4000), ("vram", 0xF800, 0x800)]}]
    for s in range(SCENARIO_COUNT):
        st = scenario(s)
        runs.append({"steps": st, "shot": length(st), "read": [("wram", WRAM_BASE, WRAM_END - WRAM_BASE)]})
    res = replay(args.rom, MENU, save_frame(MENU), runs)
    errors = 0

    chars, tmap = res[0]
    vram = bytearray(0x10000)
    vram[0:0x4000] = chars
    vram[0xF800:] = tmap
    sc = Screen(rom, vram)
    half_map: dict[int, int] = {}
    titles = rom.scenario_titles()
    ok = [check_line(sc, TITLE_X, ty, codes, half_map) for ty, codes in zip(TITLE_ROWS, title_codes(rom))]
    errors += ok.count(False)
    print(f"[titles] {ok.count(True)}/{SCENARIO_COUNT} scenario list lines drawn from the ROM text: "
          + " / ".join(t for t, k in zip(titles, ok) if k)
          + "".join(f"  NG {t}" for t, k in zip(titles, ok) if not k), flush=True)

    for s in range(SCENARIO_COUNT):
        got, want = res[1 + s][0], rom.scenario_image(s)
        diff = [WRAM_BASE + i for i in range(len(want)) if got[i] != want[i]]
        errors += bool(diff)
        print(f"[scenario {s + 1}] {titles[s]}: WRAM $7E:{WRAM_BASE:04X}-${WRAM_END - 1:04X} "
              f"({len(want)} bytes) = scenario_image: {'OK' if not diff else 'NG'}"
              + (f" {len(diff)} bytes differ, first ${diff[0]:04X}" if diff else ""), flush=True)
    print(f"{'ALL OK' if not errors else 'PROBLEMS'} ({time.time() - t0:.0f} s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
