#!/usr/bin/env python3
"""Check the scenario decode (rom.Rom.scenario_*) against the game (needs Mesen 2, about a minute).

For each of the 6 scenarios the game is started in Mesen (tools/mesen.py) up to the ruler selection map,
and the WRAM the scenario loader fills is compared byte for byte with the decompressed ROM streams:
scenario persons ($7E:73B2, 17 bytes each), the 43 cities ($7E:B872, 87 bytes) and the 25 forces
($7E:C70F, 51 bytes). Bits the loader sets afterwards (rom.FORCE_RUNTIME, rom.PERSON_RUNTIME: force +10/+11,
the emperor flags of scenarios 5-6) are compared apart and only counted.
A savestate is taken at the scenario list and replayed for each scenario.

Usage: .venv/bin/python san4/verify_scenarios.py [--rom ROM]
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
from mesen import SNES_WRAM, Mesen
from rom import (
    CITIES_WRAM,
    CITY_COUNT,
    CITY_SIZE,
    DEFAULT_ROM,
    FORCE_COUNT,
    FORCE_RUNTIME,
    FORCE_SIZE,
    FORCES_WRAM,
    PERSON_RUNTIME,
    PERSONS_WRAM,
    SCENARIO_CITIES,
    SCENARIO_COUNT,
    SCENARIO_FORCES,
    SCENARIO_PERSONS,
    SP_SIZE,
    Rom,
)

NMI = 0x008FA4
HOLD = 10  # frames a button is held (shorter presses are often missed)

LUA = """
local boot={%(boot)s}
local runs={%(runs)s}
local f, sc, state, want_save, want_load = 0, 0, nil, false, false
local presses=boot
emu.addEventCallback(function()
  local inp={}
  for _,p in ipairs(presses) do if f>=p[1] and f<p[1]+%(hold)d then inp[p[2]]=true end end
  emu.setInput(inp,0)
end, emu.eventType.inputPolled)
emu.addMemoryCallback(function()  -- savestates only work inside exec callbacks: use the NMI handler
  if want_save then state=emu.createSavestate(); want_save=false; want_load=true end
  if want_load then
    want_load=false
    sc=sc+1
    if sc>#runs then emu.log("DONE"); emu.breakExecution(); return end
    emu.loadSavestate(state)
    f=%(menu)d
    presses=runs[sc]
  end
end, emu.callbackType.exec, %(nmi)d)
emu.addEventCallback(function()
  f=f+1
  if f==%(menu)d and state==nil then want_save=true end
  if sc>0 and f==%(end)d then want_load=true; emu.breakExecution() end
end, emu.eventType.endFrame)
"""


def presses(steps: list[str], f: int) -> tuple[str, int]:
    out = []
    for st in steps:
        if st.startswith("w"):
            f += int(st[1:])
        else:
            out.append(f'{{{f},"{st}"}}')
            f += HOLD
    return ",".join(out), f


def scenario_wrams(rom_path: str) -> list[bytes]:
    """WRAM at the ruler selection map of each scenario (title -> new game -> scenario list -> scenario)."""
    boot, menu = presses(["w1300", "start", "w600", "a", "w600", "a", "w800"], 10)
    runs, end = [], 0
    for sc in [0, *range(SCENARIO_COUNT)]:  # the first replay still runs from power-on: done twice, dropped
        lua, f = presses(["w10", *["down", "w30"] * sc, "a", "w900"], menu)
        runs.append("{" + lua + "}")
        end = max(end, f)
    out = []
    with Mesen(rom_path) as m:
        m.run(LUA % {"boot": boot, "runs": ",".join(runs), "menu": menu, "end": end, "nmi": NMI, "hold": HOLD}, 600)
        while not m.log().rstrip().endswith("DONE"):
            out.append(m.memory(SNES_WRAM))
            m.resume(600)
    return out[1:]


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證劇本資料（人物、都市、勢力）")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    errors = 0
    for sc, w in enumerate(scenario_wrams(args.rom)):
        parts = []
        for name, table, at, size, count, mask in (
                ("persons", SCENARIO_PERSONS, PERSONS_WRAM, SP_SIZE, None, PERSON_RUNTIME),
                ("cities", SCENARIO_CITIES, CITIES_WRAM, CITY_SIZE, CITY_COUNT, {}),
                ("forces", SCENARIO_FORCES, FORCES_WRAM, FORCE_SIZE, FORCE_COUNT, FORCE_RUNTIME)):
            img = rom.scenario_stream(table, sc)
            count = count or len(img) // size
            got = w[at:at + size * count]
            diff = runtime = ok = 0
            for k in range(count):
                same = True
                for j in range(size):
                    x = img[size * k + j] ^ got[size * k + j]
                    if x and not x & ~mask.get(j, 0):
                        runtime += 1
                    elif x:
                        diff += 1
                        same = False
                ok += same
            errors += diff
            parts.append(f"{name} {ok}/{count} records, {diff} byte(s) differ"
                         + (f" (+{runtime} loader-set)" if runtime else ""))
        print(f"[scenario {sc + 1}] " + ", ".join(parts))
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
