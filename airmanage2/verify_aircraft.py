#!/usr/bin/env python3
"""Check the 53 aircraft (names and 11-byte records, $05:E8E6 / $05:EBFE) against the game in Mesen.

Scenario 1, main screen -> 航空機発注 -> first maker: the spec screen prints the aircraft in slot 11 of the
on-sale list (number at WRAM $3D42, record at $3DC0). From a savestate just before it prints (tools/replay.py),
each run writes one ROM record and its number there, and the game's own prints are compared:
name ('％ｓ'), range ('％５ｄ' km), seats ('％４ｄ'), fuel and maintenance ('％３ｄ'), first year ('％４ｄ年生産開始')
and price ('％＄６ｌｄ＠' 万$). The price the game shows depends on the player's relation with the maker
($04:B7D3): base × k / 100 with k = 90 / 100 / 110 (minus 10 more in some cases, so 80 also occurs), or 65535
when the maker does not sell to the player; the check accepts those and reports which k was used.

A second process opens the maker menu (savestate before it) and moves the cursor through it: every maker name
it prints ('％ｓ　　　　　') must be a ROM maker name ($05:EE45, converted to full width). In scenario 1 the menu
lists the makers that sell to the player (5 of the 12).

Usage: .venv/bin/python airmanage2/verify_aircraft.py [--rom ROM]
"""
import argparse
import os
import subprocess
import sys
import time
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "tools"))
import am2
from replay import replay
from rom import DEFAULT_ROM, Rom, half_to_full

MENU_SAVE = 10130      # SPEC's press at 10116 opens the maker menu


def maker_menu(rom: Rom) -> int:
    run = {"steps": "w500" + " right:3 w120" * 8, "shot": 1700, "read": []}
    res = replay(rom.path, am2.SPEC, MENU_SAVE, [run], extra_lua=am2.COLLECT_LUA + am2.PRT_LUA)
    shown = [p["s1"] for p in am2.prints(am2.parse(res[0][-1])) if p["fmt"] == "％ｓ　　　　　"]
    names = {half_to_full(m["name"]): m["index"] for m in rom.makers()}
    seen = sorted({names[s] for s in shown if s in names})
    unknown = sorted({s for s in shown if s not in names})
    print(f"maker menu: {len(shown)} names printed, makers {seen} = ROM names" +
          (f"; not in ROM: {unknown}" if unknown else ""))
    return len(unknown) + (not shown)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--menu", action="store_true", help=argparse.SUPPRESS)
    args = ap.parse_args()
    rom = Rom(args.rom)
    if args.menu:
        sys.exit(1 if maker_menu(rom) else 0)
    t = time.time()
    menu = subprocess.Popen([sys.executable, __file__, "--rom", args.rom, "--menu"], stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, text=True)
    planes = rom.aircraft()
    slot = am2.AIRCRAFT_LIST + 11 * am2.SPEC_SLOT
    runs = [{"wram": [(am2.AIRCRAFT_LIST_INDEX + am2.SPEC_SLOT, bytes([p["index"]])), (slot, p["raw"])],
             "shot": 80, "read": []} for p in planes]
    res = replay(rom.path, am2.SPEC, am2.SPEC_SAVE_FRAME, runs, extra_lua=am2.COLLECT_LUA + am2.PRT_LUA)
    bad, ks = 0, Counter()
    for p, r in zip(planes, res):
        pr = am2.prints(am2.parse(r[-1]))
        nums = [q["args"][0] for q in pr if q["svc"] == 0x55]          # sprintf: ％５ｄ ％４ｄ ％３ｄ ...
        name = [q["s1"] for q in pr if q["fmt"] == "％ｓ"]
        year = [q["args"][0] for q in pr if q["fmt"].endswith("年生産開始")]
        price = [q["args"][0] | q["args"][1] << 16 for q in pr if q["fmt"] == "％＄６ｌｄ＠"]
        k = "FFFF" if price == [0xFFFF] else next(
            (k for k in (80, 90, 100, 110) if price and price[0] == p["price"] * k // 100), None)
        ks[k] += 1
        got = (name[:1], nums[:4], year[:1])
        want = ([p["name"]], [p["range_km"], p["seats"], p["fuel"], p["maintenance"]], [p["first_year"]])
        ok = got == want and k is not None
        bad += not ok
        if not ok:
            print(f"  NG {p['index']} {p['name']}: game {got} price {price}, rom {want} base {p['price']}")
    print(f"aircraft shown on the spec screen = ROM: {len(planes) - bad}/{len(planes)}"
          f" (name, range, seats, fuel, maintenance, first year, price)")
    print("price factor k used: " + ", ".join(f"{k}{'' if k == 'FFFF' else '%'}: {n}"
                                             for k, n in sorted(ks.items(), key=str)))
    print(menu.communicate()[0].strip())
    bad += menu.returncode != 0
    print(f"{'OK' if not bad else f'{bad} problem(s)'} ({time.time() - t:.0f} s)")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
