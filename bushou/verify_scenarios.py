#!/usr/bin/env python3
"""Check the scenario decode against the game (needs Mesen 2, about 15 seconds).

For both scenarios the game is started in Mesen (tools/mesen.py, savestate replay tools/replay.py) up to the
daimyo selection map, and WRAM $7E:DC04-$7E:F78B (where the game copies basedata block + 4 .. + 0x1B8C) is
compared byte for byte with the ROM block that rom.Rom reads provinces, tea, daimyo and generals from.
Bytes the loader rewrites are compared apart:
  province +19 (computed), +21 (= ROM value << 6), +31 (set to 4 for some provinces),
  daimyo +31 (renumbered in scenario 2), and the byte after the last general slot.

Usage: .venv/bin/python bushou/verify_scenarios.py [--rom ROM]
"""
import argparse
import os
import sys
import time
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "tools"))
from replay import replay
from rom import (
    BLOCK_COPY,
    DAIMYO_SIZE,
    DAIMYO_START,
    DEFAULT_ROM,
    GENERAL_SIZE,
    GENERAL_SLOTS,
    GENERAL_START,
    PROVINCE_SIZE,
    PROVINCE_START,
    SCENARIO_COUNT,
    TEA_START,
    WRAM,
    Rom,
)

STEPS = "w900 start:10 w300 a:10 w200"  # title -> new game: scenario list
SAVE_AT = 1460
# scenario k: cursor down k times, then level, 1 player, daimyo map
PICK = "w10 a:10 w200 a:10 w200 a:10 w200 up:10 w60 a:10 w200"


def region(k: int) -> str:
    if k < PROVINCE_START:
        return f"header+{k}"
    if k < TEA_START:
        return f"province+{(k - PROVINCE_START) % PROVINCE_SIZE}"
    if k < DAIMYO_START:
        return "tea"
    if k < GENERAL_START:
        return f"daimyo+{(k - DAIMYO_START) % DAIMYO_SIZE}"
    if k < GENERAL_START + GENERAL_SIZE * GENERAL_SLOTS:
        return f"general+{(k - GENERAL_START) % GENERAL_SIZE}"
    return "after generals"


RUNTIME = {"province+19", "province+21", "province+31", "daimyo+31", "after generals"}


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證劇本資料（國、茶器、大名、武將）與 WRAM 一致")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    t0 = time.time()
    rom = Rom(args.rom)
    lo, hi = BLOCK_COPY
    runs = [{"steps": "down:10 w30 " * s + PICK, "shot": 900, "read": [("wram", WRAM + lo, hi - lo)]}
            for s in range(SCENARIO_COUNT)]
    res = replay(args.rom, STEPS, SAVE_AT, runs)
    errors = 0
    for s in range(SCENARIO_COUNT):
        wram = res[s][0]
        b = rom.block(s)
        block = rom.data[b + lo:b + hi]
        diff = [k + lo for k in range(len(block)) if wram[k] != block[k]]
        kinds = Counter(region(k) for k in diff)
        bad = {k: v for k, v in kinds.items() if k not in RUNTIME}
        shifted = all(wram[k - lo] == (block[k - lo] << 6) & 0xFF for k in diff if region(k) == "province+21")
        info = rom.scenario_info(s)
        print(f"[scenario {s + 1} {info['name']} {info['year']}] {len(block) - len(diff)}/{len(block)} bytes equal;"
              f" loader-written: {dict(sorted((k, v) for k, v in kinds.items() if k in RUNTIME))}"
              f"; province+21 = ROM << 6: {'OK' if shifted else 'NG'}" + (f"; NG {bad}" if bad else ""))
        errors += sum(bad.values()) + (not shifted)
        # the decoded tables, read back from the WRAM copy
        g = rom.generals(s)
        ok = all(wram[GENERAL_START + GENERAL_SIZE * i + k - lo] == rom.general_record(s, i)[k]
                 for i in range(len(g)) for k in range(GENERAL_SIZE))
        print(f"  {len(g)} generals, {len(rom.daimyos(s))} daimyo, 48 provinces, 48 tea: general records "
              + ("OK" if ok else "NG"))
        errors += not ok
    print(f"{time.time() - t0:.0f} s")
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
