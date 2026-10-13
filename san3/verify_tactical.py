#!/usr/bin/env python3
"""Check the battlefield data (rom.Rom.tactical_map) against the game (needs Mesen 2, ~20 s).

Starts scenario 1 as 劉備 in Mesen (tools/mesen.py). With this input timing the first turn opens with an AI
battle: 董卓 attacks 7.鄴 (province index 6). When the battlefield routine $C3:56BE first reads a cell, the 1342
bytes at WRAM $7E:C104 are logged; they must equal data entry TACTICAL_ENTRY + 6 (and no other battlefield
entry). A screenshot of the battle screen can be saved with --shot.

Usage: .venv/bin/python san3/verify_tactical.py [--rom ROM] [--shot PNG]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
from mesen import Mesen
from rom import DEFAULT_ROM, PROVINCE_COUNT, TACTICAL_ENTRY, Rom

# title -> new game -> scenario 1 -> one player -> 劉備 -> settings; turn 1 starts with the battle at 鄴
INPUTS = "w1200 start w200 start w300 a w200 a w500 up w30 a w300 right w30 right w30 a w300 a w300 a w300 a w300 a w300 a"
END = 6140
PROVINCE = 6       # 鄴
CELL_READER = 0xC356BE
WRAM_AT, SIZE = 0xC104, 1342

LUA = """
local presses={%(presses)s}
local f, done = 0, false
emu.addEventCallback(function()
  local inp={}
  for _,p in ipairs(presses) do if f>=p[1] and f<p[1]+4 then inp[p[2]]=true end end
  emu.setInput(inp,0)
end, emu.eventType.inputPolled)
emu.addMemoryCallback(function()
  if done then return end
  done=true
  local out={}
  for a=0,%(size)d-1 do out[#out+1]=string.format("%%02x", emu.read(0x7E0000+%(at)d+a, emu.memType.snesMemory)) end
  emu.log(string.format("FIELD %%d ", f) .. table.concat(out))
end, emu.callbackType.exec, %(reader)d)
emu.addEventCallback(function()
  f=f+1
  if f==%(end)d then shot("battle"); emu.breakExecution() end
end, emu.eventType.endFrame)
"""


def schedule(inputs: str) -> list[tuple[int, str]]:
    out, f = [], 10
    for step in inputs.split():
        if step.startswith("w"):
            f += int(step[1:])
        else:
            out.append((f, step))
            f += 24
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證戰場資料")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--shot", help="把戰場畫面截圖存到這個 PNG")
    args = ap.parse_args()
    t0 = time.time()
    rom = Rom(args.rom)
    lua = LUA % {"presses": ",".join(f'{{{f},"{b}"}}' for f, b in schedule(INPUTS)), "size": SIZE, "at": WRAM_AT,
                 "reader": CELL_READER, "end": END}
    with Mesen(args.rom) as m:
        m.run(lua, 300)
        lines = [ln for ln in m.log().splitlines() if ln.startswith("FIELD ")]
        if args.shot:
            with open(args.shot, "wb") as fh:
                fh.write(m.screenshots()["battle"])
    errors = 0
    if not lines:
        print("[field] the battlefield routine was not reached")
        errors += 1
    else:
        _, frame, raw = lines[0].split()
        got = bytes.fromhex(raw)
        hits = [k for k in range(PROVINCE_COUNT) if rom.entry(TACTICAL_ENTRY + k)[:SIZE] == got]
        want = rom.entry(TACTICAL_ENTRY + PROVINCE)[:SIZE]
        same = sum(a == b for a, b in zip(got, want))
        print(f"[field] frame {frame}: WRAM $7E:{WRAM_AT:04X} {same}/{SIZE} bytes = entry {TACTICAL_ENTRY + PROVINCE} "
              f"(province index {PROVINCE}); entries matching exactly: {[TACTICAL_ENTRY + k for k in hits]}")
        errors += (hits != [PROVINCE])
    print(f"time {time.time() - t0:.0f} s")
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
