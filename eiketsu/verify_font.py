#!/usr/bin/env python3
"""Check the font table against the game (needs Mesen 2, about 1 minute).

Plays the opening scenes in Mesen (tools/mesen.py) and watches every character the game draws:
- the binary search $C1:0878 (Shift-JIS code at sp+4, glyph number returned in $00 at $C1:089C) must give
  the index of the code in rom.FONT_CODES;
- the glyph renderer $C1:08B0 (source pointer at sp+4) must read every glyph at rom.FONT + 32 * glyph, and
  every searched glyph must be drawn from its address (a few glyphs are drawn by number, without a search).

Usage: .venv/bin/python eiketsu/verify_font.py [--rom ROM]
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
from rom import DEFAULT_ROM, FONT, GLYPH_COUNT, Rom, hirom

LUA = """
local ev={%(events)s}
local f=0
local held={}
local seen={}
local code=-1
local function rd(a) return emu.read(a, emu.memType.snesMemory) end
emu.addEventCallback(function()
  local inp={}
  for k,v in pairs(held) do inp[k]=v end
  emu.setInput(inp,0)
end, emu.eventType.inputPolled)
emu.addMemoryCallback(function()
  local sp=emu.getState()["cpu.sp"]
  code=rd(sp+4) | rd(sp+5)<<8
end, emu.callbackType.exec, 0xC10878)
emu.addMemoryCallback(function()
  local d=emu.getState()["cpu.d"]
  local k=string.format("G %%04X %%d", code, rd(d) | rd(d+1)<<8)
  if not seen[k] then seen[k]=true; emu.log(k) end
end, emu.callbackType.exec, 0xC1089C)
emu.addMemoryCallback(function()
  local sp=emu.getState()["cpu.sp"]
  local k=string.format("S %%06X", rd(sp+4) | rd(sp+5)<<8 | rd(sp+6)<<16)
  if not seen[k] then seen[k]=true; emu.log(k) end
end, emu.callbackType.exec, 0xC108B0)
emu.addEventCallback(function()
  f=f+1
  for _,e in ipairs(ev) do
    if e[1]==f then
      if e[2]=="press" then held[e[3]]=true elseif e[2]=="release" then held[e[3]]=false end
    end
  end
  if f==%(end)d then emu.log("DONE"); emu.breakExecution() end
end, emu.eventType.endFrame)
"""


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證字型表")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    t = time.time()
    events, end = schedule(TO_CAMP.split())
    lua = LUA % {"events": ",".join(f'{{{fr},"{k}","{v}"}}' for fr, k, v in events if k != "shot"), "end": end}
    with quiet(), Mesen(args.rom) as m:
        m.run(lua, 900)
        log = m.log()
    index = {c: g for g, c in enumerate(rom.glyph_codes())}
    pairs = [(int(c, 16), int(g)) for _, c, g in (ln.split() for ln in log.splitlines() if ln.startswith("G "))]
    srcs = {hirom(int(ln.split()[1], 16)) for ln in log.splitlines() if ln.startswith("S ")}
    bad = [(f"{c:04X}", g) for c, g in pairs if index.get(c) != g]
    print(f"[search] {len(pairs) - len(bad)}/{len(pairs)} distinct codes drawn: glyph = index in FONT_CODES"
          + (f" (NG {bad[:10]})" if bad else ""))
    glyphs = {g for _, g in pairs}
    odd = sorted(hex(s) for s in srcs if (s - FONT) % 32 or not 0 <= (s - FONT) // 32 < GLYPH_COUNT)
    drawn = {(s - FONT) // 32 for s in srcs}
    print(f"[glyph] renderer read {len(srcs)} glyph addresses: all FONT + 32 g, g < {GLYPH_COUNT}: "
          + ("OK" if not odd else f"NG {odd[:10]}")
          + f"; {len(glyphs & drawn)}/{len(glyphs)} searched glyphs drawn from there"
          + f" (+{len(drawn - glyphs)} glyph(s) drawn by number: {sorted(drawn - glyphs)})")
    errors = len(bad) + bool(odd) + (not pairs) + (glyphs - drawn != set())
    print(f"({time.time() - t:.0f} s)")
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
