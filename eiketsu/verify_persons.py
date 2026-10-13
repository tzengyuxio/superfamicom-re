#!/usr/bin/env python3
"""Check the person tables against the game (needs Mesen 2, about 10 seconds).

Starts a new game in Mesen (tools/mesen.py). At frame ~1566 the game ($C8:0D39) builds its runtime person
table: 384 records of 43 bytes at $7E:200D, record k = person k. The fields it copies from the two ROM
streams (MASTER entries 6 and 7) must equal rom.Rom.persons:
  +5 name (6) = name +0, +12 reading (8) = name +6, +21 face = name +14,
  +23 = stats +0 (force), +24 武力 +25 統率 +26 知力 = stats +1..3, +29 = stats +6 + 2, +30 兵種 = stats +7,
  +31 = stats +8 (level), +32 = stats +9, +33..40 items = stats +10..17, +41 = stats +18.
Not copied: name +15, stats +4..5 (the record has 耐久 at +27 instead).

Usage: .venv/bin/python eiketsu/verify_persons.py [--rom ROM]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "tools"))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
from mesen import SNES_WRAM, Mesen
from replay import quiet
from rom import DEFAULT_ROM, PERSON_COUNT, Rom

TABLE, SIZE = 0x200D, 43
STEPS_LUA = """
local f=0
local presses={{1210,"start"},{1540,"a"}}
emu.addEventCallback(function()
  local inp={}
  for _,p in ipairs(presses) do if f>=p[1] and f<p[1]+10 then inp[p[2]]=true end end
  emu.setInput(inp,0)
end, emu.eventType.inputPolled)
emu.addEventCallback(function()
  f=f+1
  if f==2000 then emu.breakExecution() end
end, emu.eventType.endFrame)
"""
# (label, slice of the runtime record, slice of the name record or None, slice of the stats record or None, add)
FIELDS = [("姓名", (5, 11), (0, 6), None, 0), ("読み", (12, 20), (6, 14), None, 0), ("頭像", (21, 22), (14, 15), None, 0),
          ("勢力byte", (23, 24), None, (0, 1), 0), ("武力統率知力", (24, 27), None, (1, 4), 0),
          ("+6", (29, 30), None, (6, 7), 2), ("兵種", (30, 31), None, (7, 8), 0), ("等級", (31, 32), None, (8, 9), 0),
          ("+9", (32, 33), None, (9, 10), 0), ("持ち物", (33, 41), None, (10, 18), 0), ("+18", (41, 42), None, (18, 19), 0)]


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證人物資料")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    t = time.time()
    with quiet(), Mesen(args.rom) as m:
        m.run(STEPS_LUA, 300)
        wram = m.memory(SNES_WRAM)
    errors = 0
    persons = rom.persons()
    for label, (a, b), nm, st, add in FIELDS:
        bad = []
        for p in persons:
            rec = wram[TABLE + SIZE * p["id"]:TABLE + SIZE * (p["id"] + 1)]
            src = p["name_raw"][nm[0]:nm[1]] if nm else p["stats_raw"][st[0]:st[1]]
            if rec[a:b] != bytes((v + add) & 0xFF for v in src):
                bad.append(p["id"])
        errors += len(bad)
        print(f"[{label}] {PERSON_COUNT - len(bad)}/{PERSON_COUNT} runtime records match" + (f" (NG {bad[:10]})" if bad else ""))
    liu = wram[TABLE:TABLE + SIZE]
    print(f"[sample] 劉備 record: 武力 {liu[24]} 統率 {liu[25]} 知力 {liu[26]} 耐久 {liu[27] | liu[28] << 8} 等級 {liu[31]}")
    print(f"({time.time() - t:.0f} s)")
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
