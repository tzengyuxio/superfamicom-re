#!/usr/bin/env python3
"""Check the scenario tables against the game: savestate at the scenario menu, pick scenario 1 or 2 + YES, and
after the game has built the scenario ($02:BF2B, ~frame 5550) compare WRAM with rom.Rom.scenario_wram (features
$5627, products $4E19, format records $4C59, maker records $4785 incl. the product pointer, $5401, $5541, $6E05, market cells $5785),
plus the scenario index $46DE.

Usage: .venv/bin/python leading/verify_scenarios.py [--rom ROM] [--dump FILE | --load FILE]
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "tools"))
sys.path.insert(0, HERE)
import lc
from replay import end_frame, replay
from rom import DEFAULT_ROM, SCENARIO_COUNT, WRAM_SCENARIO, Rom

LO, HI = 0x4600, 0x7700
STEPS = ["a:10 w300 a:10 w300 a:10 w300", "down:10 w60 a:10 w300 a:10 w300 a:10 w300"]


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證劇本資料（開局 WRAM）")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--dump", help="把讀到的 WRAM 存檔（之後可用 --load 不跑模擬器重做比對）")
    ap.add_argument("--load")
    args = ap.parse_args()
    rom = Rom(args.rom)
    if args.load:
        with open(args.load, "rb") as f:
            raw = f.read()
        res = [[raw[i * (HI - LO):(i + 1) * (HI - LO)]] for i in range(SCENARIO_COUNT)]
    else:
        runs = [{"steps": s, "shot": 1200, "read": [("wram", LO, HI - LO)]} for s in STEPS]
        res = replay(args.rom, lc.TO_SCENARIO_MENU, end_frame(lc.TO_SCENARIO_MENU), runs)
        if args.dump:
            with open(args.dump, "wb") as f:
                f.write(b"".join(r[0] for r in res))
    errors = 0
    for s in range(SCENARIO_COUNT):
        w = res[s][0]
        blocks = rom.scenario_wram(s)
        nbytes = sum(len(b) for b in blocks.values())
        bad = [hex(a) for a, b in blocks.items() if w[a - LO:a - LO + len(b)] != b]
        idx = w[WRAM_SCENARIO - LO] | w[WRAM_SCENARIO - LO + 1] << 8
        ok = not bad and idx == s
        errors += not ok
        print(f"scenario {s + 1}: index ${WRAM_SCENARIO:04X} = {idx}; {len(blocks) - len(bad)}/{len(blocks)} blocks "
              f"({nbytes} bytes) match" + (f" NG {bad[:8]}" if bad else ""))
    print("ALL OK" if not errors else f"{errors} scenario(s) differ")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
