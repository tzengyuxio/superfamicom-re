#!/usr/bin/env python3
"""Play a ROM in Mesen 2 (tools/mesen.py) from a button script; save screenshots and memory dumps.

Steps (space separated):
  <button>[:hold][*n]  press for `hold` frames (default 4), then release for 20; n times
                       buttons: a b x y l r start select up down left right
  w<n>                 wait n frames
  @<tag>               screenshot → OUT_<tag>.png
The script starts at frame 10. At the end OUT.wram / .vram / .cgram / .oam / .sram and OUT.log are written,
plus OUT_all.png (all screenshots side by side, half size).

--reads LO-HI traces CPU reads of that address range (hex, e.g. C00000-FFFFFF) during --window START-END
(frames) and logs one line per (PC, 256-byte page): count and address range, most frequent first. That
finds where data comes from (a table read by some routine) without hitting Mesen's log cap. --lua adds
your own Lua (FRAME() gives the current frame).

Usage: .venv/bin/python tools/drive.py ROM OUT "w900 start w200 a @menu" [--reads C00000-FFFFFF --window 900-1200]
"""
import argparse
import io
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mesen import SNES_CGRAM, SNES_OAM, SNES_SRAM, SNES_VRAM, SNES_WRAM, Mesen

READS_LUA = """
local st={}
local function cb(addr, value)
  local s=emu.getState()
  local pc=s["cpu.k"]*65536+s["cpu.pc"]
  if addr>=pc and addr<pc+4 then return end  -- instruction fetch
  local key=string.format("%%06X %%04X", pc, addr>>8)
  local r=st[key]
  if not r then r={n=0,lo=addr,hi=addr}; st[key]=r end
  r.n=r.n+1; if addr<r.lo then r.lo=addr end; if addr>r.hi then r.hi=addr end
end
emu.addEventCallback(function()
  local f=FRAME()
  if f==%(start)d then emu.addMemoryCallback(cb, emu.callbackType.read, %(lo)d, %(hi)d) end
  if f==%(end)d then
    emu.removeMemoryCallback(cb, emu.callbackType.read, %(lo)d, %(hi)d)
    local keys={}
    for k,_ in pairs(st) do keys[#keys+1]=k end
    table.sort(keys, function(a,b) return st[a].n>st[b].n end)
    for i=1,math.min(#keys,400) do
      local r=st[keys[i]]
      emu.log(string.format("READ pc=%%s n=%%d %%06X-%%06X", keys[i]:sub(1,6), r.n, r.lo, r.hi))
    end
  end
end, emu.eventType.endFrame)
"""


def schedule(steps: list[str]) -> tuple[list[tuple[int, str, str]], int]:
    """([(frame, press|release|shot, button or tag)], last frame)."""
    events, f = [], 10
    for st in steps:
        if st.startswith("w"):
            f += int(st[1:])
        elif st.startswith("@"):
            events.append((f, "shot", st[1:]))
            f += 1
        else:
            b, _, n = st.partition("*")
            b, _, hold = b.partition(":")
            for _ in range(int(n or 1)):
                events.append((f, "press", b))
                events.append((f + int(hold or 4), "release", b))
                f += int(hold or 4) + 20
    return events, f + 2


def main() -> None:
    ap = argparse.ArgumentParser(description="用按鍵序列操作遊戲，截圖並 dump 記憶體")
    ap.add_argument("rom")
    ap.add_argument("out", help="輸出檔名前綴")
    ap.add_argument("steps")
    ap.add_argument("--lua", help="額外的 Lua 檔")
    ap.add_argument("--reads", help="追蹤 CPU 讀取的位址範圍，如 C00000-FFFFFF")
    ap.add_argument("--window", help="追蹤的幀範圍，如 900-1200（預設整段）")
    ap.add_argument("--timeout", type=float, default=1800)
    args = ap.parse_args()

    events, end = schedule(args.steps.split())
    extra = ""
    if args.lua:
        with open(args.lua) as fh:
            extra = fh.read()
    if args.reads:
        lo, hi = (int(x, 16) for x in args.reads.split("-"))
        start, stop = (int(x) for x in args.window.split("-")) if args.window else (10, end - 1)
        extra += READS_LUA % {"lo": lo, "hi": hi, "start": start, "end": stop}
    lua_events = ",".join(f'{{{fr},"{k}","{v}"}}' for fr, k, v in events)
    lua = f"""
local ev={{{lua_events}}}
local f=0
local held={{}}
FRAME=function() return f end
{extra}
emu.addEventCallback(function()
  local inp={{}}
  for k,v in pairs(held) do inp[k]=v end
  emu.setInput(inp,0)
end, emu.eventType.inputPolled)
emu.addEventCallback(function()
  f=f+1
  for _,e in ipairs(ev) do
    if e[1]==f then
      if e[2]=="press" then held[e[3]]=true
      elseif e[2]=="release" then held[e[3]]=false
      else shot(e[3]) end
    end
  end
  if f=={end} then emu.breakExecution() end
end, emu.eventType.endFrame)
"""
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with Mesen(args.rom) as m:
        try:
            m.run(lua, args.timeout)
        finally:
            log = m.log()
            with open(f"{args.out}.log", "w") as fh:
                fh.write(log)
        shots = m.screenshots()
        for tag, png in shots.items():
            with open(f"{args.out}_{tag}.png", "wb") as fh:
                fh.write(png)
        for ext, t in (("wram", SNES_WRAM), ("vram", SNES_VRAM), ("cgram", SNES_CGRAM), ("oam", SNES_OAM),
                       ("sram", SNES_SRAM)):
            with open(f"{args.out}.{ext}", "wb") as fh:
                fh.write(m.memory(t))
    if shots:
        ims = [Image.open(io.BytesIO(png)) for png in shots.values()]
        ims = [im.resize((im.width // 2, im.height // 2)) for im in ims]
        sheet = Image.new("RGB", (sum(im.width for im in ims), max(im.height for im in ims)))
        x = 0
        for im in ims:
            sheet.paste(im, (x, 0))
            x += im.width
        sheet.save(f"{args.out}_all.png")
    reads = [line for line in log.splitlines() if line.startswith("READ")]
    print(f"frames {end}, shots {len(shots)}" + (f", {len(reads)} read groups" if args.reads else ""))
    for line in reads[:40]:
        print(line)


if __name__ == "__main__":
    main()
