#!/usr/bin/env python3
"""Check the 89 city names, their areas and area-map positions, and the 32 default airline names, in Mesen.

For each of the 7 areas a new game is started and the area is chosen in the area menu; on the home-city map
(savestate, tools/replay.py) the map cursor ($24CD / $24CF) is put 6 px right of and 4 px below each city's
area-map position (rom: $05:E2E5) and moved 1 px left with the d-pad. The game's hit test then prints the city
name under the cursor ('％ｓ', service 4F/43): it must be the ROM name of that city ($05:DEF1, half-width,
converted to full width by the game). Every city of the area is checked, so the area table ($05:E8A6) and the
positions are checked too.
For the home cities (0-31) the run goes on: the city is chosen and the game started; the setup screen prints
each player's company, MAN / COM and home city ('％ｓ' x 3): every company printed must be the default airline
of its home city ($05:E397, airline i = home city i), and the chosen city's airline must be among them.
One child process per area (Mesen can be opened once per process), 4 in parallel.

Usage: .venv/bin/python airmanage2/verify_cities.py [--rom ROM]
"""
import argparse
import ast
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "tools"))
import am2
from replay import presses, replay
from rom import AREA_COUNT, DEFAULT_ROM, Rom

HOVER = "right:3 w40 left:3 w60"    # the first press only closes the message window; the second moves by -1
START = " a:10 w201 a:10 w201 a:10 w201 a:10 w201 a:10 w301"   # choose, confirm, ... -> setup screen


def run_area(rom: Rom, area: int) -> int:
    steps = am2.TO_AREA_MENU + " " + am2.AREA_KEYS[area] + " w40 a:10 w400"
    save = presses(steps, 10)[-1][0] + 380          # home-city map with the "select your home city" message
    cities = [c for c in rom.cities() if c["area"] == area]
    runs = [{"wram": [(am2.CURSOR_X, am2.le16(c["area_x"] + 6)), (am2.CURSOR_Y, am2.le16(c["area_y"] + 4))],
             "steps": HOVER + (START if c["home"] else ""), "shot": 1500 if c["home"] else 90, "read": []}
            for c in cities]
    res = replay(rom.path, steps, save, runs, extra_lua=am2.COLLECT_LUA + am2.PRT_LUA)
    by_name = {c["name_full"]: c for c in rom.cities()}
    bad = 0
    for c, r in zip(cities, res):
        names = [p["s1"] for p in am2.prints(am2.parse(r[-1])) if p["fmt"] == "％ｓ"]
        ok = names[:1] == [c["name_full"]]
        bad += not ok
        print(f"CITY {c['index']} {'OK' if ok else 'NG'} {c['name_full']} game={names[:1]}")
        if c["home"]:
            pairs = [(names[i], names[i + 2]) for i in range(1, len(names) - 2) if names[i + 1] in ("ｍａｎ", "ｃｏｍ")]
            good = [a == by_name[h]["airline"] for a, h in pairs if h in by_name]
            ok = len(good) == len(pairs) == 4 and all(good) and (c["airline"], c["name_full"]) in pairs
            bad += not ok
            print(f"AIRLINE {c['index']} {'OK' if ok else 'NG'} {pairs}")
    return bad


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--area", type=int, help=argparse.SUPPRESS)
    args = ap.parse_args()
    rom = Rom(args.rom)
    if args.area is not None:
        sys.exit(1 if run_area(rom, args.area) else 0)
    t = time.time()

    def child(area: int) -> str:
        r = subprocess.run([sys.executable, __file__, "--rom", args.rom, "--area", str(area)],
                           check=False, capture_output=True, text=True)
        return r.stdout

    with ThreadPoolExecutor(4) as ex:
        outs = list(ex.map(child, range(AREA_COUNT)))
    lines = [ln for o in outs for ln in o.splitlines() if ln.startswith(("CITY", "AIRLINE"))]
    for area, o in enumerate(outs):
        n = sum(ln.startswith("CITY") for ln in o.splitlines())
        print(f"area {area} {rom.areas()[area]['name']}: {n} cities")
    for ln in lines:
        if " NG " in ln:
            print("  " + ln)
    n = len(rom.cities())
    n_home = sum(c["home"] for c in rom.cities())
    ok_city = sum(ln.startswith("CITY") and " OK " in ln for ln in lines)
    ok_air = sum(ln.startswith("AIRLINE") and " OK " in ln for ln in lines)
    seen = {x for ln in lines if ln.startswith("AIRLINE") for x in ast.literal_eval(ln.split(" ", 3)[3])}
    print(f"city name under the cursor at the ROM position: {ok_city}/{n} OK")
    print(f"setup screen company = default airline of its home city: {ok_air}/{n_home} runs OK "
          f"({len(seen)} distinct company / home-city pairs printed)")
    good = ok_city == n and ok_air == n_home
    print(f"{'OK' if good else 'NG'} ({time.time() - t:.0f} s)")
    sys.exit(0 if good else 1)


if __name__ == "__main__":
    main()
