"""Boot 大航海時代II once in Mesen, take a savestate, then replay it once per round with WRAM pokes and button presses.

Used by the verify_*.py scripts: a round is (pokes, steps); after its steps the emulator stops and the caller gets
the WRAM / VRAM / CGRAM / OAM of that moment, then the next round starts again from the savestate. Savestates are only
created / loaded in an exec callback, here the NMI handler at its second instruction (native NMI vector + 1); the
first round is played twice and the first result dropped (a load right after the boot does not always take effect).
Pokes are written on the first frame of the round. A savestate cannot be loaded in the callback that created it, so
the first load waits for the next NMI. Steps use session.py syntax (button[:hold][*n], w<n>, up+a).

    for mem in replay.run(rom, BOOT, [([(0x7E2616, b"\x05\x00")], "x:10 w40 right+a:10 w200")]):
        mem["vram"], mem["cgram"], mem["wram"], mem["oam"]
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "tools"))
from mesen import SNES_CGRAM, SNES_OAM, SNES_VRAM, SNES_WRAM, Mesen
from session import NMI_VECTOR, schedule

# Power-on -> title -> new game -> ジョアン (no name change) -> intro talk -> free to walk in Lisbon (about 18000 frames)
BOOT_TOWN = "w1800 start:10 w300 a:10 w200 a:10 w200 right:10 w30 a:10 w200" + " a:10 w300" * 46
# Power-on -> hero selection screen (cursor on ジョアン)
BOOT_SELECT = "w1800 start:10 w300"
LOG_BYTES = 1 << 22

LUA = """
%(extra)s
local boot={%(boot)s}
local rounds={%(rounds)s}
local boot_end=%(boot_end)d
local f, r, phase, state, held = 0, 0, "boot", nil, {}
local want_save, want_load = false, false
emu.addEventCallback(function()
  local inp={}
  for k,v in pairs(held) do inp[k]=v end
  emu.setInput(inp,0)
end, emu.eventType.inputPolled)
emu.addMemoryCallback(function()
  if want_save then state=emu.createSavestate(); want_save=false; want_load=true; return end  -- load at the next NMI
  if want_load then
    want_load=false
    r=r+1
    if r>#rounds then emu.log("DONE"); emu.breakExecution(); return end
    emu.loadSavestate(state)
    f=0; held={}; phase="round"
  end
end, emu.callbackType.exec, %(nmi)d)
emu.addEventCallback(function()
  f=f+1
  local ev = (phase=="boot") and boot or ((phase=="round") and rounds[r].ev or {})
  for _,e in ipairs(ev) do
    if e[1]==f then
      if e[2]=="press" then held[e[3]]=true elseif e[2]=="release" then held[e[3]]=false end
    end
  end
  if phase=="boot" and f==boot_end then want_save=true; phase="wait" end
  if phase=="round" then
    if f==1 then
      for _,p in ipairs(rounds[r].pokes) do
        for k=1,#p[2] do emu.write(p[1]+k-1, p[2][k], emu.memType.snesWorkRam) end
      end
    end
    if f==rounds[r].len then
      if ON_ROUND_END then ON_ROUND_END(r) end
      emu.log("ROUND " .. r); phase="wait"; want_load=true; emu.breakExecution()
    end
  end
end, emu.eventType.endFrame)
"""


def _events(steps: str) -> tuple[str, int]:
    ev, end = schedule(steps)
    return ",".join(f'{{{f},"{k}","{v}"}}' for f, k, v in ev if k != "shot"), end


def run(rom: str, boot: str, rounds: list[tuple[list[tuple[int, bytes]], str]], timeout: float = 600, lua: str = ""):
    """Yield {"wram", "vram", "cgram", "oam", "log"} at the end of every round. Pokes are (WRAM offset, bytes);
    lua is extra Lua code run with the script (its emu.log lines up to that point are in "log")."""
    from rom import load_rom_bytes
    data = load_rom_bytes(rom)
    rounds = [rounds[0]] + list(rounds)
    boot_ev, boot_end = _events(boot)
    parts = []
    for pokes, steps in rounds:
        ev, end = _events(steps)
        pk = ",".join(f"{{{a & 0x1FFFF},{{{','.join(map(str, b))}}}}}" for a, b in pokes)
        parts.append(f"{{pokes={{{pk}}},ev={{{ev}}},len={end}}}")
    lua = LUA % {"boot": boot_ev, "boot_end": boot_end, "rounds": ",".join(parts),
                 "nmi": (data[NMI_VECTOR] | data[NMI_VECTOR + 1] << 8) + 1, "extra": lua}
    with Mesen(rom) as m:
        m.run(lua, timeout)
        first = True
        while True:
            log = m.log(LOG_BYTES)
            if log.rstrip().rsplit("\n", 1)[-1] == "DONE":
                return
            mem = {"wram": m.memory(SNES_WRAM), "vram": m.memory(SNES_VRAM), "cgram": m.memory(SNES_CGRAM),
                   "oam": m.memory(SNES_OAM), "log": log}
            if not first:
                yield mem
            first = False
            m.resume(timeout)
