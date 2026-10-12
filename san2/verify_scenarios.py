#!/usr/bin/env python3
"""Check the scenario decode (rom.Rom.placement / province) against the game's own set-up (needs Mesen 2).

For each of the 6 scenarios the game is started in Mesen (tools/mesen.py) up to the "how many players"
prompt, and the WRAM the scenario loader builds is compared with the static decode: the 41 province records ($7E:F422 + 25 i,
bytes 8-15 and 18-24; 16-17 are runtime) and every person's 21-byte record (知武魅, faction, loyalty,
id). Initial soldiers follow the flags (ruler 100, flag 0x10 50, others 10) except for a few strong
generals the loader raises; those are listed, not counted as errors.

Usage: .venv/bin/python san2/verify_scenarios.py [--rom ROM]
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
from mesen import SNES_WRAM, Mesen
from rom import ABILITY_TABLE, DEFAULT_ROM, PERSON_COUNT, PROVINCE_COUNT, PROVINCE_SIZE, PROVINCES, SCENARIO_COUNT, Rom

WRAM_PROVINCES, PERSON_SIZE = 0xF422, 21
COMPARED = [*range(8, 16), *range(18, PROVINCE_SIZE)]

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
end, emu.callbackType.exec, 0x00832B)
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
    """WRAM right after each scenario is loaded (title -> scenario list -> scenario -> "how many players?")."""
    boot, menu = presses(["w600", "start", "w120"], 10)
    runs, end = [], 0
    for sc in [0, *range(SCENARIO_COUNT)]:  # the first replay still runs from power-on: done twice, dropped
        lua, f = presses(["w10", *["down"] * sc, "a", "w400"], menu)
        runs.append("{" + lua + "}")
        end = max(end, f)
    out = []
    with Mesen(rom_path) as m:
        m.run(LUA % {"boot": boot, "runs": ",".join(runs), "menu": menu, "end": end}, 300)
        while not m.log().rstrip().endswith("DONE"):
            out.append(m.memory(SNES_WRAM))
            m.resume(300)
    return out[1:]


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證劇本武將與州資料")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    d, errors = rom.data, 0
    for sc, w in enumerate(scenario_wrams(args.rom)):
        prov_ok = 0
        for i in range(PROVINCE_COUNT):
            o, a = PROVINCES + PROVINCE_SIZE * (PROVINCE_COUNT * sc + i), WRAM_PROVINCES + PROVINCE_SIZE * i
            prov_ok += all(w[a + k] == d[o + k] for k in COMPARED)
        found = {}
        for j in range(len(w) - PERSON_SIZE):
            r = w[j:j + PERSON_SIZE]
            n = r[19] | r[20] << 8
            if n < PERSON_COUNT and r[4:7] == d[ABILITY_TABLE + 3 * n:ABILITY_TABLE + 3 * n + 3]:
                found.setdefault(n, r)
        bad, raised = [], []
        for n in range(PERSON_COUNT):
            p = rom.placement(n, sc)
            if not p or p["status"] == "未登場":
                if n in found:
                    bad.append(n)
                continue
            r = found.get(n)
            faction = rom.province(sc, p["province"] - 1)["faction"]
            want = (0xFF, 0xFF) if p["status"] == "在野" else (faction, 0xFF if p["loyalty"] is None else p["loyalty"])
            if r is None or (r[7], r[8]) != want:
                bad.append(n)
            elif r[12] | r[13] << 8 != p["soldiers"]:
                raised.append(f"{n}:{r[12] | r[13] << 8}")
        print(f"[scenario {sc + 1}] provinces {prov_ok}/{PROVINCE_COUNT}, persons {len(found) - len(bad)}"
              f"/{len(found)} match" + (f" (NG {bad[:10]})" if bad else "")
              + (f"; soldiers raised by the loader: {', '.join(raised)}" if raised else ""))
        errors += PROVINCE_COUNT - prov_ok + len(bad)
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
