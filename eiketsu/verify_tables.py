#!/usr/bin/env python3
"""Check the class and item tables against the game (needs Mesen 2, about 1 minute).

Plays the opening in Mesen (tools/mesen.py) up to 劉備's camp, opens 情報 -> 武将 -> 関羽's status screen
(person 1: class 6 = 軽騎兵, holds item 12) and records every CPU read of the class tables ($C3:7BE6-$C3:7CE5)
and the item table while the screen is drawn. Expected:
- the class name pointer CLASS_NAMES + 4 * class and the bytes of that name string (軽騎兵);
- byte `class` of the three 19-byte class tables CLASS_PARAMS (策略 on the screen = first table, at level 1);
- only inside item 12's 20-byte record of ITEMS (the game reads its +19 byte).
The game reads 16-bit words, so a read of byte a also touches a + 1.
The status screen screenshot is saved next to the output (output/verify_tables_status.png).

Usage: .venv/bin/python eiketsu/verify_tables.py [--rom ROM]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "tools"))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
from mesen import Mesen
from replay import TO_CAMP, quiet, schedule
from rom import CLASS_NAMES, CLASS_PARAMS, DEFAULT_ROM, ITEM_COUNT, ITEM_SIZE, ITEMS, Rom, hirom

GUAN_YU = 1
# camp: X -> 情報 -> 武将 (list) -> down to 関羽 -> status screen
STEPS = TO_CAMP + " x:10 w60 up:10 w40 a:10 w100 left:10 w40 a:10 w200 down:4 w60 a:10 w150 @status"
LO, HI = 0xC37BE6, 0xC37CE5

LUA = """
local ev={%(events)s}
local f=0
local held={}
local seen={}
local function cb(addr, value)
  local s=emu.getState()
  local pc=s["cpu.k"]*65536+s["cpu.pc"]
  if addr>=pc and addr<pc+4 then return end
  if not seen[addr] then seen[addr]=true; emu.log(string.format("R %%06X %%02X", addr, value)) end
end
emu.addEventCallback(function()
  local inp={}
  for k,v in pairs(held) do inp[k]=v end
  emu.setInput(inp,0)
end, emu.eventType.inputPolled)
emu.addEventCallback(function()
  f=f+1
  for _,e in ipairs(ev) do
    if e[1]==f then
      if e[2]=="press" then held[e[3]]=true elseif e[2]=="release" then held[e[3]]=false else shot(e[3]) end
    end
  end
  if f==%(start)d then
    emu.addMemoryCallback(cb, emu.callbackType.read, %(lo)d, %(hi)d)
    emu.addMemoryCallback(cb, emu.callbackType.read, %(ilo)d, %(ihi)d)
  end
  if f==%(end)d then emu.log("DONE"); emu.breakExecution() end
end, emu.eventType.endFrame)
"""


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證兵種與道具表")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    t = time.time()
    events, end = schedule(STEPS.split())
    last_a = max(fr for fr, k, b in events if k == "press")
    ilo, ihi = 0xC00000 | ITEMS, 0xC00000 | (ITEMS + ITEM_COUNT * ITEM_SIZE - 1)
    lua = LUA % {"events": ",".join(f'{{{fr},"{k}","{v}"}}' for fr, k, v in events), "start": last_a, "end": end,
                 "lo": LO, "hi": HI, "ilo": ilo, "ihi": ihi}
    with quiet(), Mesen(args.rom) as m:
        m.run(lua, 900)
        reads = {hirom(int(a, 16)) for _, a, _ in (ln.split() for ln in m.log().splitlines() if ln.startswith("R "))}
        shots = m.screenshots()
    out = os.path.join(HERE, "output")
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "verify_tables_status.png"), "wb") as f:
        f.write(shots["status"])

    p = rom.persons()[GUAN_YU]
    cls, classes = p["class"], rom.classes()
    errors = 0
    ptr = CLASS_NAMES + 4 * cls
    name_at = rom.ptr(CLASS_NAMES, cls)
    name_len = len(classes[cls].encode("cp932"))
    class_reads = {a for a in reads if hirom(LO) <= a <= hirom(HI)}
    want = {ptr, ptr + 1, ptr + 2, ptr + 3} & class_reads
    ok = want >= {ptr, ptr + 2} and set(range(name_at, name_at + name_len)) <= class_reads
    print(f"[class] 関羽 class {cls}: pointer {ptr:#x} and name {classes[cls]} at {name_at:#x} read: {'OK' if ok else 'NG'}")
    errors += not ok
    params = {t + cls for t in CLASS_PARAMS}
    ok = params <= class_reads
    print(f"[class] class tables read at byte {cls}: {sorted(hex(a) for a in params & class_reads)} "
          f"{'OK' if ok else 'NG'}; 策略 table value {rom.data[CLASS_PARAMS[0] + cls]}")
    errors += not ok
    other = sorted(hex(a) for a in class_reads - {ptr, ptr + 1, ptr + 2, ptr + 3} - params - {a + 1 for a in params}
                   - set(range(name_at, name_at + name_len + 2)))
    print(f"[class] other reads in the class area: {other or 'none'}")
    errors += bool(other)
    item_reads = sorted(a for a in reads if ITEMS <= a < ITEMS + ITEM_COUNT * ITEM_SIZE)
    held = p["items"]
    words = {a for a in item_reads if a - 1 not in item_reads}  # 16-bit reads also touch the next byte
    ok = bool(item_reads) and {(a - ITEMS) // ITEM_SIZE for a in words} <= set(held)
    print(f"[item] 関羽 holds {[rom.items()[i]['name'] for i in held]}; the screen read item record bytes "
          f"{[(hex(a), (a - ITEMS) // ITEM_SIZE, (a - ITEMS) % ITEM_SIZE) for a in item_reads]}: {'OK' if ok else 'NG'}")
    errors += not ok
    print(f"({time.time() - t:.0f} s)")
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
