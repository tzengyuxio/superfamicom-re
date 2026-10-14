#!/usr/bin/env python3
"""Check the scenario tables against the game in Mesen.

From a savestate taken right after NEW GAME (tools/replay.py), each of the 4 scenarios is chosen and confirmed;
the game then builds its state ($82:B42C). Checked:
1. the scenario name and year range printed on the chosen scenario's page ($02:F568);
2. WRAM $24E9 = scenario number;
3. city records $2CBD (89 x 4) and $3E37 (89 x 2) = rom.Rom.scenario_cities (tables A / B, interpolated for
   scenarios 2 and 3, country changed by the world events before the start year);
4. the tables copied from bank $05: $2E21 (with the world events applied), $2955, $2AD5, $3DF7.

Usage: .venv/bin/python airmanage2/verify_scenarios.py [--rom ROM]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "tools"))
import am2
from replay import replay
from rom import CITY_COUNT, DEFAULT_ROM, SCENARIO_COUNT, WRAM_CITY, WRAM_CITY2, WRAM_SCENARIO, Rom

SAVE = 2945        # NEW GAME pressed at 2930; the scenario menu is drawn after this


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    t = time.time()
    init = rom.init_tables()
    reads = [("wram", WRAM_SCENARIO, 1), ("wram", WRAM_CITY, 4 * CITY_COUNT), ("wram", WRAM_CITY2, 2 * CITY_COUNT)]
    reads += [("wram", a, len(b)) for a, b in init.items()]
    # the menu takes input once its prompt is printed; a 10-frame hold moves 2 lines, so tap for 3 frames
    runs = [{"steps": "w215" + " down:3 w40" * s + " w30 a:10 w200 a:10 w200", "shot": 800, "read": reads}
            for s in range(SCENARIO_COUNT)]
    res = replay(rom.path, am2.TO_SCENARIO_MENU, SAVE, runs, extra_lua=am2.COLLECT_LUA + am2.PRT_LUA)
    bad = 0
    for sc, r in zip(rom.scenarios(), res):
        # the chosen scenario's page prints its name and year range as plain strings
        shown = [p["fmt"] for p in am2.prints(am2.parse(r[-1]))]
        ok = sc["name"] in shown and sc["years"] in shown
        bad += not ok
        print(f"scenario {sc['index'] + 1} page text {sc['name']} {sc['years']}: {'OK' if ok else 'NG'}")
    for s, r in enumerate(res):
        city, city2 = rom.scenario_cities(s)
        checks = [("$24E9", r[0][0] == s), ("$2CBD", r[1] == city), ("$3E37", r[2] == city2)]
        checks += [(f"${a:04X}", r[3 + k] == b) for k, (a, b) in enumerate(rom.init_tables(s).items())]
        diff = [i for i in range(CITY_COUNT) if r[1][4 * i:4 * i + 4] != city[4 * i:4 * i + 4]]
        bad += sum(not ok for _, ok in checks)
        print(f"scenario {s + 1}: " + ", ".join(f"{n} {'OK' if ok else 'NG'}" for n, ok in checks)
              + (f" (cities differing: {diff[:10]})" if diff else ""))
    print(f"{'OK' if not bad else f'{bad} problem(s)'} ({time.time() - t:.0f} s)")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
