#!/usr/bin/env python3
"""Check the weapon table (rom.Rom.weapons: name, AP AT 防 速 射) against the game's weapons screen (needs Mesen 2,
a few minutes).

Scenario 1, one player, 枢軸軍, first command screen (savestate replay, tools/replay.py), then 情報 → 兵器 → 自軍.
The screen routine ($CA:24A0) draws 6 rows; for row r it reads a weapon index from its list in WRAM ($7E:805A,
pointer in DP $0C) at $CA:24D0, takes the record $C1:D2BC + 14 * index, prints the name with $C1:195E (long
pointer = record +0) and the numbers with vprintf "%2d %2d %2d %2d %2d" ($CA:6433). An exec callback at $CA:24D0
replaces the list byte by the weapon wanted for that row (handed over per run in WRAM $7F:FF00), so every run
shows 6 chosen weapons; all 158 are covered. The name pointer printed must be the record's, and the 5 numbers
+7 +6 +8 +9 +12 of the ROM record.

Usage: .venv/bin/python europe/verify_weapons.py [--rom ROM]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
from replay import replay
from rom import DEFAULT_ROM, WEAPON_COUNT, WEAPON_SIZE, WEAPONS, Rom
from scenes import EVENTS_LUA, TO_COMMAND, events, length, save_frame

TO_WEAPONS = "down:4 w30 a:10 w200 down:4 w30 a:10 w200 a:10 w300"   # 情報, 兵器, 自軍
ROWS = 6
WANT = 0x1FF00                           # WRAM offset ($7F:FF00) of the 6 weapon ids of the run
FORMAT = 0xCA6433

LUA = EVENTS_LUA + """
local row = 0
local base_reset = EXTRA_RESET
EXTRA_RESET = function() base_reset(); row = 0 end
emu.addMemoryCallback(function()
  local d = emu.getState()["cpu.d"]
  local p = rd(d + 0x0C) + rd(d + 0x0D) * 256 + rd(d + 0x0E) * 65536
  local id = emu.read(0x1FF00 + row % 6, emu.memType.snesWorkRam, false)
  emu.write(p, id, emu.memType.snesMemory)
  EVENTS[#EVENTS + 1] = string.format("R%02X", id)
  row = row + 1
end, emu.callbackType.exec, 0xCA24D0, 0xCA24D0)
emu.addMemoryCallback(function()
  EVENTS[#EVENTS + 1] = string.format("S%06X", arg_ptr(4))
end, emu.callbackType.exec, 0xC1195E, 0xC1195E)
emu.addMemoryCallback(function()
  if arg_ptr(4) == 0xCA6433 then EVENTS[#EVENTS + 1] = "V" .. hex(arg_ptr(8), 10) end
end, emu.callbackType.exec, 0xC1286A, 0xC1286A)
"""


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證兵器表（名稱、AP AT 防 速 射）")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    t0 = time.time()
    rom = Rom(args.rom)
    weapons = rom.weapons()
    ids = list(range(WEAPON_COUNT))
    chunks = [ids[k:k + ROWS] for k in range(0, len(ids), ROWS)]
    chunks[-1] += ids[:ROWS - len(chunks[-1])]
    runs = [{"wram": [(WANT, bytes(c))], "steps": TO_WEAPONS, "shot": length(TO_WEAPONS), "read": [("wram", 0, 1)]}
            for c in chunks]
    shots = replay(args.rom, TO_COMMAND, save_frame(TO_COMMAND), runs, extra_lua=LUA)
    ok_ids, bad = set(), []
    for chunk, (_, raw) in zip(chunks, shots):
        rows, cur = [], None
        for e in events(raw):
            if e[0] == "R":
                cur = {"id": int(e[1:], 16), "S": [], "V": None}
                rows.append(cur)
            elif cur is not None and e[0] == "S":
                cur["S"].append(int(e[1:], 16))
            elif cur is not None and e[0] == "V" and cur["V"] is None:
                v = bytes.fromhex(e[1:])
                cur["V"] = [v[2 * i] | v[2 * i + 1] << 8 for i in range(5)]
        for r in rows[:ROWS]:
            w = weapons[r["id"]]
            name_ptr = rom.ptr(WEAPONS + WEAPON_SIZE * r["id"]) | 0xC00000
            want = [w["AP"], w["AT"], w["防"], w["速"], w["射"]]
            if r["S"][:1] == [name_ptr] and r["V"] == want:
                ok_ids.add(r["id"])
            else:
                bad.append(f"{r['id']} {w['name']}: printed {[hex(s) for s in r['S'][:1]]} {r['V']}, ROM {want}")
        if [r["id"] for r in rows[:ROWS]] != chunk:
            bad.append(f"rows {[r['id'] for r in rows[:ROWS]]} != {chunk}")
    print(f"[weapons] {len(ok_ids)}/{WEAPON_COUNT} weapons: name pointer (record +0) and AP AT 防 速 射 "
          f"(+7 +6 +8 +9 +12) as the screen prints them")
    for b in bad[:20]:
        print("  NG", b)
    ok = not bad and len(ok_ids) == WEAPON_COUNT
    print(f"{'ALL OK' if ok else f'{len(bad)} problem(s)'} ({time.time() - t0:.0f} s)")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
