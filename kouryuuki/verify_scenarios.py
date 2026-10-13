#!/usr/bin/env python3
"""Check the scenario image (rom.Rom.scenario_image, from SCENARIO_PIECES) against the game (needs Mesen 2).

For each of the 4 scenarios the game is started in Mesen (tools/mesen.py) up to 項羽's profile after the
lord is chosen, and WRAM $2000-$472C is compared with the image assembled from the ROM pieces; the
persons ($32F8), places ($3690) and armies ($3C0C) tables are counted record by record.

Usage: .venv/bin/python kouryuuki/verify_scenarios.py [--rom ROM]
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
from mesen import SNES_WRAM, Mesen
from rom import (
    ARMIES_AT,
    ARMY_COUNT,
    ARMY_SIZE,
    DEFAULT_ROM,
    PERSON_COUNT,
    PERSON_SIZE,
    PERSONS_AT,
    PLACE_COUNT,
    PLACE_SIZE,
    PLACES_AT,
    SCENARIO_COUNT,
    SCENARIO_SIZE,
    SCENARIO_WRAM,
    Rom,
)

NMI = 0x0084A2
TABLES = [("persons", PERSONS_AT, PERSON_SIZE, PERSON_COUNT), ("places", PLACES_AT, PLACE_SIZE, PLACE_COUNT),
          ("armies", ARMIES_AT, ARMY_SIZE, ARMY_COUNT)]

LUA = """
local boot={%(boot)s}
local runs={%(runs)s}
local f, sc, state, want_save, want_load = 0, 0, nil, false, false
local presses=boot
emu.addEventCallback(function()
  local inp={}
  for _,p in ipairs(presses) do if f>=p[1] and f<p[1]+4 then inp[p[2]]=true end end
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
            f += 24
    return ",".join(out), f


def scenario_wrams(rom_path: str) -> list[bytes]:
    """WRAM at 項羽's profile of each scenario (title -> new game -> scenario -> prologue -> settings -> lord)."""
    boot, menu = presses(["w900", "start", "w200", "start", "w200"], 10)
    runs, end = [], 0
    for sc in [0, *range(SCENARIO_COUNT)]:  # the first replay still runs from power-on: done twice, dropped
        steps = ["w10", "a", "w300", *["down", "w30"] * sc, "a", "w6500", "a", "w200", "a", "w200", "a", "w200",
                 "a", "w300"]
        lua, f = presses(steps, menu)
        runs.append("{" + lua + "}")
        end = max(end, f)
    out = []
    with Mesen(rom_path) as m:
        m.run(LUA % {"boot": boot, "runs": ",".join(runs), "menu": menu, "end": end, "nmi": NMI}, 600)
        while not m.log().rstrip().endswith("DONE"):
            out.append(m.memory(SNES_WRAM))
            m.resume(600)
    return out[1:]


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證劇本資料（人物、地點、軍隊）")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    errors = 0
    for sc, w in enumerate(scenario_wrams(args.rom)):
        img, got = rom.scenario_image(sc), w[SCENARIO_WRAM:SCENARIO_WRAM + SCENARIO_SIZE]
        diff = sum(a != b for a, b in zip(img, got))
        parts = [f"WRAM ${SCENARIO_WRAM:04X}-${SCENARIO_WRAM + SCENARIO_SIZE - 1:04X} {diff} byte(s) differ"]
        for name, at, size, count in TABLES:
            o = at - SCENARIO_WRAM
            ok = sum(img[o + size * k:o + size * (k + 1)] == got[o + size * k:o + size * (k + 1)] for k in range(count))
            parts.append(f"{name} {ok}/{count}")
        errors += diff
        print(f"[scenario {sc + 1}] " + ", ".join(parts))
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
