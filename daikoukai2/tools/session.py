#!/usr/bin/env python3
"""Play 大航海時代II in Mesen from a savestate file (or power-on), press buttons, take screenshots / dumps,
and optionally write a new savestate file, so long operation sequences are only played once.

The game's intro and the walk to a screen take tens of thousands of frames (~1 min per run); a savestate
file made once lets every later probe start right there. Savestates can only be created / loaded inside an
exec callback, so both happen in the NMI handler at its second instruction (native NMI vector + 1). A load
is done twice (the first one right after power-on does not always take effect); frame 0 of the steps is the
frame after the second load.

    r = play(rom, "a:10 w60 @menu", state=open("town.mss", "rb").read(), save=True)
    r["shots"]["menu"], r["wram"], r["vram"], r["state"]

Steps use tools/drive.py syntax: button[:hold][*n], w<n>, @tag; up+a presses both. lua adds Lua code; FRAME() is the frame
number and LOG(...) logs a line returned in r["log"].

Usage: session.py ROM OUT "steps" [--state IN.mss] [--save] [--lua FILE]
       writes OUT_<tag>.png, OUT.wram/.vram/.cgram/.oam/.sram, OUT.log, and OUT.mss with --save.
"""
import argparse
import os
import pathlib
import re
import sys

GAME = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(GAME), "tools"))
sys.path.insert(0, GAME)
from mesen import SNES_CGRAM, SNES_OAM, SNES_SRAM, SNES_VRAM, SNES_WRAM, Mesen

NMI_VECTOR = 0xFFEA
LOG_SIZE = 1 << 27

LUA = """
local ev={%(events)s}
local state_hex=%(state)s
local f=-1
local held={}
local loads=0
local state_bin=nil
FRAME=function() return f end
LOG=function(s) emu.log("L " .. s) end
%(extra)s
emu.addEventCallback(function()
  local inp={}
  for k,v in pairs(held) do inp[k]=v end
  emu.setInput(inp,0)
end, emu.eventType.inputPolled)
local want_save=false
emu.addMemoryCallback(function()
  if state_hex and loads<2 then
    loads=loads+1
    if not state_bin then state_bin=(state_hex:gsub("%%x%%x", function(h) return string.char(tonumber(h,16)) end)) end
    emu.loadSavestate(state_bin)
    if loads==2 then f=0 end
    return
  end
  if want_save then
    want_save=false
    local s=emu.createSavestate()
    emu.log("STATE " .. s:gsub(".", function(c) return string.format("%%02x", c:byte()) end))
    emu.breakExecution()
  end
end, emu.callbackType.exec, %(nmi)d)
emu.addEventCallback(function()
  if f<0 then
    if not state_hex then f=0 end
    return
  end
  f=f+1
  for _,e in ipairs(ev) do
    if e[1]==f then
      if e[2]=="press" then held[e[3]]=true
      elseif e[2]=="release" then held[e[3]]=false
      else shot(e[3]) end
    end
  end
  if f==%(end)d then
    if %(save)s then want_save=true else emu.breakExecution() end
  end
end, emu.eventType.endFrame)
"""


def schedule(steps: str) -> tuple[list[tuple[int, str, str]], int]:
    events, f = [], 1
    for st in steps.split():
        if st.startswith("w"):
            f += int(st[1:])
        elif st.startswith("@"):
            events.append((f, "shot", st[1:]))
            f += 1
        else:
            b, _, n = st.partition("*")
            b, _, hold = b.partition(":")
            for _ in range(int(n or 1)):
                for k in b.split("+"):
                    events.append((f, "press", k))
                    events.append((f + int(hold or 4), "release", k))
                f += int(hold or 4) + 20
    return events, f + 1


def play(rom: str, steps: str, state: bytes | None = None, save: bool = False, lua: str = "",
         timeout: float = 1800) -> dict:
    from rom import load_rom_bytes
    data = load_rom_bytes(rom)
    events, end = schedule(steps)
    src = LUA % {"events": ",".join(f'{{{fr},"{k}","{v}"}}' for fr, k, v in events),
                 "state": f'"{state.hex()}"' if state else "nil", "extra": lua, "end": end,
                 "save": "true" if save else "false",
                 "nmi": (data[NMI_VECTOR] | data[NMI_VECTOR + 1] << 8) + 1}
    with Mesen(rom) as m:
        m.run(src, timeout)
        log = m.log(LOG_SIZE)
        out = {"log": [ln[2:] for ln in log.splitlines() if ln.startswith("L ")],
               "shots": {k: bytes.fromhex(v) for k, v in re.findall(r"^PNG (\S+) ([0-9a-f]+)$", log, re.MULTILINE)},
               "wram": m.memory(SNES_WRAM), "vram": m.memory(SNES_VRAM), "cgram": m.memory(SNES_CGRAM),
               "oam": m.memory(SNES_OAM), "sram": m.memory(SNES_SRAM), "frames": end}
        st = re.search(r"^STATE ([0-9a-f]+)$", log, re.MULTILINE)
        out["state"] = bytes.fromhex(st[1]) if st else None
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="從 savestate 檔開始操作遊戲，截圖、dump，可另存 savestate")
    ap.add_argument("rom")
    ap.add_argument("out")
    ap.add_argument("steps")
    ap.add_argument("--state")
    ap.add_argument("--save", action="store_true")
    ap.add_argument("--lua")
    args = ap.parse_args()
    state = pathlib.Path(args.state).read_bytes() if args.state else None
    lua = pathlib.Path(args.lua).read_text() if args.lua else ""
    r = play(args.rom, args.steps, state, args.save, lua)
    for tag, png in r["shots"].items():
        with open(f"{args.out}_{tag}.png", "wb") as fh:
            fh.write(png)
    for ext in ("wram", "vram", "cgram", "oam", "sram"):
        with open(f"{args.out}.{ext}", "wb") as fh:
            fh.write(r[ext])
    with open(f"{args.out}.log", "w") as fh:
        fh.write("\n".join(r["log"]))
    if r["state"]:
        with open(f"{args.out}.mss", "wb") as fh:
            fh.write(r["state"])
    print(f"frames {r['frames']}, shots {len(r['shots'])}, log {len(r['log'])} lines"
          + (f", state {len(r['state'])} bytes" if r["state"] else ""))
    for line in r["log"][:60]:
        print(line)


if __name__ == "__main__":
    main()
