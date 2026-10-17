#!/usr/bin/env python3
"""Check the font addressing (rom.glyph_code / glyph_offset) against the game's glyph lookup in Mesen.

Full-width text is drawn one code at a time: $C2:0E5D takes the 2-byte code (local S+$8B), maps 0x91xx escapes
and blanks, and computes the glyph address; $C2:091E then copies the 32 font bytes from the pointer at S+4. From
the savestate after the secretary's question (tools/wp.TRAINER_LIST + one press), the next press draws the trainer
list; the code of every lookup is replaced by the next code under test; the pointer and the 32 bytes the game reads must be
rom.glyph_offset(code) and the ROM bytes there. All 2368 codes 0x8140-0x8A7F, every 0x91xx escape 0x9140-0x9148
and a few blank codes (0x8A80-0x913F) are checked, PER_RUN per run.

Usage: .venv/bin/python winning/verify_text.py [--rom ROM]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "tools"))
import wp
from replay import end_frame, replay
from rom import DEFAULT_ROM, GLYPH_COUNT, Rom, glyph_offset

BOOT = wp.TRAINER_LIST + wp.A200
PER_RUN = 20
LUA = """
local codes = {%s}
local n, cur = 0, nil
emu.addMemoryCallback(function()
  local sp = emu.getState()["cpu.sp"]
  local k = (PARAM(0) | PARAM(1) << 8) + n + 1
  if n >= PARAM(2) or k > #codes then cur = nil return end
  cur = codes[k]
  n = n + 1
  emu.write(sp + 0x8B, cur & 0xFF, emu.memType.snesMemory)
  emu.write(sp + 0x8C, cur >> 8, emu.memType.snesMemory)
end, emu.callbackType.exec, 0xC20E5D)
emu.addMemoryCallback(function()
  if cur == nil then return end
  local function rd(a) return emu.read(a, emu.memType.snesMemory, false) end
  local sp = emu.getState()["cpu.sp"]
  local p = rd(sp + 4) | rd(sp + 5) << 8 | rd(sp + 6) << 16
  local t = {}
  for i = 0, 31 do t[#t + 1] = string.format("%%02x", rd(p + i)) end
  REC_ADD(string.format("G %%04x %%06x %%s", cur, p, table.concat(t)))
  cur = nil
end, emu.callbackType.exec, 0xC2091E)
local reset0 = EXTRA_RESET
function EXTRA_RESET() reset0(); n = 0; cur = nil end
"""


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證字型定址")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    t0 = time.time()
    codes = [0x8140 + g for g in range(GLYPH_COUNT)] + list(range(0x9140, 0x9149)) + [0x8A80, 0x8F00, 0x913F]
    runs = []
    for start in range(0, len(codes), PER_RUN):
        n = min(PER_RUN, len(codes) - start)
        runs.append({"steps": "a:10 w200", "shot": 400, "read": [],
                     "wram": [(wp.WRAM_PARAM, bytes([start & 255, start >> 8, n]))]})
    res = replay(rom.path, BOOT, end_frame(BOOT), runs,
                 extra_lua=wp.COLLECT_LUA + LUA % ",".join(map(str, codes)))
    got = {}
    for r in res:
        for x in wp.parse(r[-1]):
            if x[0] == "G":
                got[int(x[1], 16)] = (int(x[2], 16) & 0x3FFFFF, bytes.fromhex(x[3]))
    bad = [f"{c:04X}" for c in codes if c in got
           and got[c] != (glyph_offset(c), rom.data[glyph_offset(c):glyph_offset(c) + 32])]
    missing = [f"{c:04X}" for c in codes if c not in got]
    print(f"[glyphs] {len(codes) - len(bad) - len(missing)}/{len(codes)} codes: address and 32 font bytes = "
          "rom.glyph_offset" + (f" (NG {bad[:8]})" if bad else "") + (f" (not drawn {missing[:8]})" if missing else ""))
    errors = len(bad) + len(missing)
    print(f"time {time.time() - t0:.0f}s")
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
