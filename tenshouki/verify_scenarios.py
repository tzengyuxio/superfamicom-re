#!/usr/bin/env python3
"""Check the scenario decode (data entries 7-14 through rom.decompress) against the game (needs Mesen 2).

For both scenarios the game is started in Mesen (tools/mesen.py) up to the daimyo selection, and the
WRAM the scenario loader builds is compared with the decoded records: persons ($7E:3F70, 35 bytes),
128 castles ($7E:882C, 23 bytes) and 128 軍団 ($7E:93AC, 31 bytes).

The ROM lists the persons in play first (333 / 406); the loader copies those and blanks the rest
(姫 and 未登場 are kept elsewhere). It rebuilds the person lists, so list links (person +2..+5,
castle +4..+5) are compared apart and only counted.

Usage: .venv/bin/python tenshouki/verify_scenarios.py [--rom ROM]
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
from mesen import SNES_WRAM, Mesen
from rom import (
    CASTLE_SIZE,
    CORPS_SIZE,
    DEFAULT_ROM,
    SCENARIO_CASTLES,
    SCENARIO_CORPS,
    SCENARIO_COUNT,
    SCENARIO_PERSON_SIZE,
    SCENARIO_PERSONS,
    Rom,
)

NMI = 0x008FC3
TABLES = [  # name, data entry, WRAM address, record size, bytes the loader relinks
    ("persons", SCENARIO_PERSONS, 0x3F70, SCENARIO_PERSON_SIZE, {2, 3, 4, 5}),
    ("castles", SCENARIO_CASTLES, 0x882C, CASTLE_SIZE, {4, 5}),
    ("corps", SCENARIO_CORPS, 0x93AC, CORPS_SIZE, set()),
]

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
    """WRAM at the daimyo selection of each scenario (title -> 新しくゲームを始める -> scenario)."""
    boot, menu = presses(["w1100", "start", "w300", "start", "w300"], 10)
    runs, end = [], 0
    for sc in [0, *range(SCENARIO_COUNT)]:  # the first replay still runs from power-on: done twice, dropped
        lua, f = presses(["w10", "a", "w300", *["down", "w30"] * sc, "a", "w300"], menu)
        runs.append("{" + lua + "}")
        end = max(end, f)
    out = []
    with Mesen(rom_path) as m:
        m.run(LUA % {"boot": boot, "runs": ",".join(runs), "menu": menu, "end": end, "nmi": NMI}, 300)
        while not m.log().rstrip().endswith("DONE"):
            out.append(m.memory(SNES_WRAM))
            m.resume(300)
    return out[1:]


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證劇本人物、城、軍団資料")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    errors = 0
    for sc, w in enumerate(scenario_wrams(args.rom)):
        parts = []
        in_play = sum(p["status"] not in (5, 6) and p["castle"] > 0 for p in rom.scenario_persons(sc))
        for name, entry, at, size, links in TABLES:
            e = rom.entry(entry + sc)
            count = in_play if name == "persons" else len(e) // size
            ok, relinked = 0, 0
            for k in range(count):
                want, got = e[size * k:size * (k + 1)], w[at + size * k:at + size * (k + 1)]
                diff = {i for i in range(size) if want[i] != got[i]}
                ok += not diff - links
                relinked += bool(diff & links)
            errors += count - ok
            parts.append(f"{name} {ok}/{count}" + (f" ({relinked} relinked)" if links else ""))
        print(f"[scenario {sc + 1}] " + ", ".join(parts))
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
