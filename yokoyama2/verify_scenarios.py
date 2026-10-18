#!/usr/bin/env python3
"""Check the scenario start state (rom.Rom.scenario_wram) against the game's loader.

The game is played to the scenario list and a savestate is taken there (tools/sequences.py). Each run picks a
scenario (189 / 200 / 215), the first ruler and a difficulty (上級 中級 初級), presses through the opening text and
dumps WRAM $0700-$1F8B when the loader $99:E436 returns ($80:8089): persons 229 x 24 ($0700), countries 35 x 20
($1C92, the last one cut to 18 bytes by the factions at $1F4C) and factions 16 x 4 ($1F4C) must equal
rom.Rom.scenario_wram(scenario, difficulty) byte for byte (金 / 米 from the 上級 / 初級 tables of $80:8103).

Usage: .venv/bin/python yokoyama2/verify_scenarios.py [--rom ROM]
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
from rom import DEFAULT_ROM, DIFFICULTIES, LOADER_DONE, PERSON_WRAM, SCENARIO_YEARS, Rom

LO, HI = PERSON_WRAM, 0x1F8C
SHOT = 1800


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證劇本開局狀態（載入程式結束時的 WRAM）")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    t0 = time.time()
    rom = Rom(args.rom)
    cases = [(k, d) for k in range(3) for d in range(3)]
    runs = [{"steps": q.scenario(k, 0, d), "shot": SHOT, "read": []} for k, d in cases]
    boot = q.TO_SCENARIOS
    results = replay.replay(rom.path, boot, q.end_frame(boot), runs, extra_lua=q.loader_lua(LOADER_DONE, LO, HI))
    bad = 0
    for (k, d), res in zip(cases, results):
        dump = res[-1]
        if len(dump) != HI - LO:
            bad += 1
            print(f"  NG {SCENARIO_YEARS[k]} {DIFFICULTIES[d]}: loader not reached")
            continue
        counts = []
        for addr, want in rom.scenario_wram(k, d).items():
            got = dump[addr - LO:addr - LO + len(want)]
            same = sum(a == b for a, b in zip(got, want))
            counts.append(f"{same}/{len(want)}")
            if same != len(want):
                bad += 1
                first = next(i for i in range(len(want)) if got[i] != want[i])
                print(f"  NG {SCENARIO_YEARS[k]} {DIFFICULTIES[d]} ${addr:04X}+{first}: {got[first]:02X} "
                      f"(want {want[first]:02X})")
        print(f"{SCENARIO_YEARS[k]} {DIFFICULTIES[d]}: persons {counts[0]}, countries {counts[1]}, "
              f"factions {counts[2]} bytes")
    print(f"{time.time() - t0:.0f} s")
    print("ALL OK" if not bad else f"{bad} mismatch(es)")
    raise SystemExit(1 if bad else 0)


if __name__ == "__main__":
    main()
