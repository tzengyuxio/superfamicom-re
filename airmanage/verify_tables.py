#!/usr/bin/env python3
"""Check the aircraft table and the distance matrix against the game in Mesen.

From the saved main screen (scenario 1, home London) the game's own display code is run and its printf
arguments are compared with rom.py (airmanage/tools/vm.py):
  * aircraft: the VM is made to run TRADE ($1169("TRADE", $D000, $3000), as COMMAND's menu does) and A picks
    the first maker and A again in its welcome message; the trade screen then calls its spec panel TRADE $DF43(maker, aircraft), whose aircraft
    argument is replaced on entry (one run per aircraft): name, 座席数, 燃料費 rank, 航続距離, 価格;
  * distances: the VM is made to call COMMAND $A319(a, b), the main screen's distance box, which prints
    "%5u0km" with the matrix entry [b][a]; one run per row b, 21 calls each.
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "tools"))
import vm
from replay import replay
from rom import AIRCRAFT_COUNT, CITY_COUNT, DEFAULT_ROM, Rom

LOAD_MODULE = 0x1169      # COMMON: load and run a module (name, address, max size)
ARG = 0x1FEE              # WRAM byte: aircraft index for the hook on TRADE $DF43 (spec panel: maker, aircraft)
SPEC_LUA = """
emu.addMemoryCallback(function()
  if emu.read(0xD003, emu.memType.snesWorkRam) ~= 0x20 or emu.read(0xDF43, emu.memType.snesWorkRam) ~= 0x20 then
    return
  end
  local s = emu.getState()["cpu.sp"]
  emu.write(s + 10, emu.read(ARG, emu.memType.snesWorkRam), emu.memType.snesMemory)
  emu.write(s + 11, 0, emu.memType.snesMemory)
end, emu.callbackType.exec, 0x7EDF43)
""".replace("ARG", str(ARG))
# TRADE format strings (same in both releases); COMMAND "%5u0km" is added from vm.addresses()
FMT = {0xE9F0: "name", 0xE9F5: "seats", 0xEA11: "fuel_rank", 0xEA1B: "range", 0xEA27: "price"}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    r = Rom(args.rom)
    t = time.time()
    air = r.aircraft()
    dist = r.distances()
    ad = vm.addresses(r.rev)
    fmt = {**FMT, ad["km_fmt"]: "km"}
    trade = vm.command_inject(r.rev, [(LOAD_MODULE, [ad["trade_name"], 0xD000, 0x3000])])
    runs = [{"wram": trade + [(ARG, bytes([k]))], "steps": "w400 a:10 w400 a:10", "shot": 1300, "read": []}
            for k in range(AIRCRAFT_COUNT)]
    for b in range(CITY_COUNT):
        calls = [(ad["distance_box"], [a, b]) for a in range(CITY_COUNT) if a != b]
        runs.append({"wram": vm.command_inject(r.rev, calls), "shot": 300, "read": []})
    res = replay(r.path, vm.boot(0), vm.MAIN_FRAME, runs,
                 extra_lua=vm.boot_lua(r.rev) + vm.INJECT_LUA + vm.PRINTF_LUA + SPEC_LUA)
    recs = [[p for p in vm.printf_records(run[-1]) if p["fmt_ptr"] in fmt] if run else [] for run in res]
    bad = 0
    ok = 0
    for k, a in enumerate(air):
        val = {fmt[p["fmt_ptr"]]: p for p in recs[k]}
        try:
            screen = (val["name"]["s0"], val["seats"]["args"][0], val["fuel_rank"]["s0"],
                      val["range"]["args"][0] * 10, val["price"]["args"][0])
        except KeyError:
            screen = None
        want = (a["name"], a["seats"], a["fuel_rank"], a["range_km"], a["price"])
        if screen == want:
            ok += 1
            if k in (0, 19):
                print(f"  aircraft {k}: {screen}")
        else:
            print(f"  aircraft {k}: screen {screen}; ROM {want}")
    print(f"aircraft: {ok}/{AIRCRAFT_COUNT} OK")
    bad += AIRCRAFT_COUNT - ok
    ok = n = 0
    for b in range(CITY_COUNT):
        km = [p["args"][0] * 10 for p in recs[AIRCRAFT_COUNT + b] if fmt[p["fmt_ptr"]] == "km"]
        want = [dist[b][a] for a in range(CITY_COUNT) if a != b]
        n += len(want)
        if km == want:
            ok += len(want)
        else:
            print(f"  row {b}: screen {km}; ROM {want}")
    print(f"distances: {ok}/{n} OK (e.g. 東京-北京 {dist[0][1]} km, ロンドン-ニュ－ヨ－ク {dist[11][14]} km)")
    bad += n - ok
    print(f"{'OK' if not bad else f'{bad} mismatches'} ({time.time() - t:.0f} s)")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
