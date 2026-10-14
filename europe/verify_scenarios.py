#!/usr/bin/env python3
"""Check the scenario blocks (rom.SCENARIO_BLOCKS: header, generals, cities) and the menu against the game
(needs Mesen 2, under a minute).

For each of the 6 scenarios (savestate replay just before the scenario list is drawn, tools/replay.py): open the
list, select the scenario and answer Y. The game copies the block with its memcpy service, the MVN at $00:006C.
Exec callbacks record
  - every MVN to $7E:2000: its source and length must be Rom.block's file offset and BLOCK_SIZE, and right after
    it (exec $00:006F) WRAM $7E:2000 + BLOCK_SIZE must equal Rom.block(k) byte for byte (the game fills WRAM
    pointers into the copy afterwards, so a later read differs in about 310 bytes);
  - the strings printed with $C1:195E: the list must print the 6 menu lines at the pointers of SCENARIO_MENU.

Usage: .venv/bin/python europe/verify_scenarios.py [--rom ROM]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
from replay import replay
from rom import BLOCK_SIZE, DEFAULT_ROM, SCENARIO_BLOCKS, SCENARIO_COUNT, SCENARIO_MENU, Rom
from scenes import EVENTS_LUA, events, length, save_frame, scenario

BOOT = "w4600 start:10 w200"             # the scenario list is drawn by the next press

LUA = EVENTS_LUA + f"""
local pending = false
emu.addMemoryCallback(function()
  local s = emu.getState()
  if rd(0x6D) == 0x7E and s["cpu.y"] == 0x2000 then
    EVENTS[#EVENTS + 1] = string.format("M%02X%04X:%04X", rd(0x6E), s["cpu.x"], s["cpu.a"] + 1)
    pending = true
  end
end, emu.callbackType.exec, 0x00006C, 0x00006C)
emu.addMemoryCallback(function()
  if pending then pending = false; EVENTS[#EVENTS + 1] = "W" .. mem_hex("snesWorkRam", 0x2000, {BLOCK_SIZE}) end
end, emu.callbackType.exec, 0x00006F, 0x00006F)
emu.addMemoryCallback(function()
  EVENTS[#EVENTS + 1] = string.format("S%06X", arg_ptr(4))
end, emu.callbackType.exec, 0xC1195E, 0xC1195E)
"""


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證劇本區塊（標頭、將領、都市）與選單")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    t0 = time.time()
    rom = Rom(args.rom)
    runs = []
    for k in range(SCENARIO_COUNT):
        st = "a:10 w300 " + scenario(k + 1)
        runs.append({"steps": st, "shot": length(st), "read": [("wram", 0, 1)]})
    shots = replay(args.rom, BOOT, save_frame(BOOT), runs, extra_lua=LUA)
    bad = []
    menu = [rom.ptr(SCENARIO_MENU + 3 * k) | 0xC00000 for k in range(SCENARIO_COUNT)]
    for k, (_, raw) in enumerate(shots):
        ev = events(raw)
        mvn = [e for e in ev if e[0] == "M"]
        copies = [bytes.fromhex(e[1:]) for e in ev if e[0] == "W"]
        want = f"M{SCENARIO_BLOCKS[k] | 0xC00000:06X}:{BLOCK_SIZE:04X}"
        same = sum(a == b for a, b in zip(copies[0], rom.block(k))) if copies else 0
        printed = {int(e[1:], 16) for e in ev if e[0] == "S"}
        s = rom.scenarios()[k]
        menu_ok = all(m in printed for m in menu)
        ok = mvn == [want] and same == BLOCK_SIZE and menu_ok
        print(f"[scenario {k + 1}] {s['title']} {s['year']}/{s['month']}/{s['day']} map {s['map']}: "
              f"MVN {mvn[0] if mvn else None}, WRAM after the copy {same}/{BLOCK_SIZE} bytes = Rom.block, "
              f"6 menu lines printed: {menu_ok} ({len(rom.generals(k))} generals, {len(rom.cities(k))} cities)")
        if not ok:
            bad.append(k + 1)
    print(f"{'ALL OK' if not bad else f'NG scenarios {bad}'} ({time.time() - t0:.0f} s)")
    raise SystemExit(1 if bad else 0)


if __name__ == "__main__":
    main()
