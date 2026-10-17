#!/usr/bin/env python3
"""Check the scenario decoding (rom.Rom.scenario_wram: persons + placement, countries, factions) against the game.

From the scenario list (savestate) every run picks one scenario and difficulty and the first ruler; when the
scenario loader $01:D4A9 reaches rom.Rom.loader_done ($01:D612 in Rev 0: after the difficulty-1 金 / 米 change,
before the difficulty-3 change) WRAM $0800-$1E15 is dumped. The person block (224 x 22 at $0800: faction /
country from the placement table,
level, the 14-byte ROM record), the country block (31 x 21 at $1B40) and the faction block (15 x 5 at $1DCB) must
equal scenario_wram(scenario, difficulty) byte for byte, for both scenarios and all three difficulties.

Usage: .venv/bin/python yokoyama/verify_scenarios.py [--rom ROM]
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
from rom import DEFAULT_ROM, PERSON_WRAM, SCENARIO_YEARS, Rom

NAMES = {PERSON_WRAM: "person", 0x1B40: "country", 0x1DCB: "faction"}


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證 2 個劇本 × 3 個難易度的 WRAM 初始資料")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    t0 = time.time()
    rom = Rom(args.rom)
    cases = [(k, d) for k in (0, 1) for d in (0, 1, 2)]
    runs = []
    for k, d in cases:
        steps = q.expand(q.scenario(k, d))
        runs.append({"steps": steps, "shot": q.end_frame(steps, 0) + 100, "read": []})
    results = replay.replay(args.rom, q.TO_SCENARIOS, q.end_frame(q.TO_SCENARIOS), runs,
                            extra_lua=q.loader_lua(rom.loader_done))
    errors = 0
    for (k, d), res in zip(cases, results):
        dump = res[-1]
        if len(dump) < 0x1E16 - 0x800:
            print(f"scenario {SCENARIO_YEARS[k]} difficulty {d + 1}: loader not reached")
            errors += 1
            continue
        parts = []
        for a, want in rom.scenario_wram(k, d).items():
            got = dump[a - 0x800:a - 0x800 + len(want)]
            bad = sum(x != y for x, y in zip(got, want))
            errors += bad
            parts.append(f"{NAMES[a]} {len(want) - bad}/{len(want)}")
        print(f"scenario {SCENARIO_YEARS[k]} difficulty {d + 1}: bytes equal " + ", ".join(parts))
    print(f"{time.time() - t0:.0f} s")
    print("ALL OK" if not errors else f"{errors} mismatch(es)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
