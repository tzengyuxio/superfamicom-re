#!/usr/bin/env python3
"""Check the scenario streams (rom.Rom.scenario_wram) against the game's loader.

The game is played to the scenario list and a savestate is taken there (tools/sequences.py). Each run clicks one
of the 4 scenarios and 了 of the opening text; when the loader $00:CA31 returns ($00:CA8D, the first time after the click) WRAM
$7E:8018-$E3A1 is dumped: persons 600 x 35 ($8018), factions 15 x 30 ($D220) and 郡国 126 x 32 ($D3E2) must equal
rom.Rom.scenario_wram(k) byte for byte.

Usage: .venv/bin/python tenbu/verify_scenarios.py [--rom ROM]
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
from rom import DEFAULT_ROM, LOADER_DONE, PERSON_WRAM, SCENARIO_YEARS, Rom

LO, HI = PERSON_WRAM, 0xE3A2
SHOT = 700


def loader_lua() -> str:
    return f"""
local dump="00"
emu.addMemoryCallback(function()
  if dump~="00" then return end
  local s={{}}
  for i={LO},{HI - 1} do s[#s+1]=string.format("%02x", emu.read(i, emu.memType.snesWorkRam, false)) end
  dump=table.concat(s)
end, emu.callbackType.exec, {LOADER_DONE})
function EXTRA_RESET() dump="00"; POINTER_RESET() end
function EXTRA_SHOT() local s=dump; dump="00"; return s end
"""


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證劇本串流（載入程式結束時的 WRAM）")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    t0 = time.time()
    rom = Rom(args.rom)
    boot, save, steps, plua = q.prepare(q.TO_SCENARIOS, [q.to_rulers(k) for k in range(4)])
    runs = [{"steps": st, "shot": SHOT, "read": [], "wram": [q.mail(k)]} for k, st in enumerate(steps)]
    results = replay.replay(rom.path, boot, save, runs, extra_lua=plua + loader_lua(), nmi=q.FRAME_HOOK)
    bad = 0
    for k, res in enumerate(results):
        dump = res[-1]
        if len(dump) != HI - LO:
            bad += 1
            print(f"  NG {SCENARIO_YEARS[k]}: loader not reached")
            continue
        counts = []
        for addr, want in rom.scenario_wram(k).items():
            got = dump[addr - LO:addr - LO + len(want)]
            same = sum(a == b for a, b in zip(got, want))
            counts.append(f"{same}/{len(want)}")
            if same != len(want):
                bad += 1
                first = next(i for i in range(len(want)) if got[i] != want[i])
                print(f"  NG {SCENARIO_YEARS[k]} ${addr:04X}+{first}: {got[first]:02X} (want {want[first]:02X})")
        print(f"{SCENARIO_YEARS[k]}: persons {counts[0]}, factions {counts[1]}, 郡国 {counts[2]} bytes")
    print(f"{time.time() - t0:.0f} s")
    print("ALL OK" if not bad else f"{bad} mismatch(es)")
    raise SystemExit(1 if bad else 0)


if __name__ == "__main__":
    main()
