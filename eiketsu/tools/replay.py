"""Replay one savestate of 三國志英傑伝 many times in Mesen (tools/mesen.py) and read memory after each round.

The game is played from power-on with a tools/drive.py button script (RAM all zeros, so it is deterministic).
At frame `save` a savestate is taken (inside the NMI handler: savestates only work in exec callbacks); then
for every parameter the state is loaded again, the rest of the script replays, and at frame `shot` the
requested memory regions are logged. Extra Lua sees the round's parameter as the global PARAM (nil while
the first, unpatched run is played) and may set the global NOTE (a string without spaces) that is returned
with the round. The first round after taking the state is not reliable, so it is run twice and the first
result dropped.
"""
import contextlib
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "tools"))
from drive import schedule
from mesen import Mesen

NMI = 0x008FC3                  # native NMI vector ($00:FFEA)
# power-on -> title -> new game -> the opening scenes (78 x a) -> free to walk in 劉備's camp (frame ~20000)
TO_CAMP = "w1200 start:10 w300 a:10 w300 " + "a:10 w200 " * 78 + "w200"
# camp: walk to 関羽, talk, confirm "出陣" (one save prompt) -> the press at frame 21676 starts battle 0 (汜水関),
# whose set-up script runs at frames ~21680-21760; the dialogue then shows 華雄's face after the press at 22396
TO_BATTLE = TO_CAMP + " down:3 w20 left:3 w20 " + "a:10 w100 " * 8 + "a:10 w150 " * 5
# camp: X opens the ring menu, left = 全体図 (the big map, drawn at frame ~20160)
TO_WORLD = TO_CAMP + " x:10 w60 left:10 w40 a:10 w200"

MEM = {"mem": "snesMemory", "vram": "snesVideoRam", "cgram": "snesCgRam", "wram": "snesWorkRam"}

LUA = """
local ev={%(events)s}
local params={%(params)s}
local regions={%(regions)s}
local f, idx, state = 0, 0, nil
local held={}
local want_save, want_load = false, false
PARAM=nil
NOTE="-"
FRAME=function() return f end
%(extra)s
emu.addEventCallback(function()
  local inp={}
  for k,v in pairs(held) do inp[k]=v end
  emu.setInput(inp,0)
end, emu.eventType.inputPolled)
emu.addMemoryCallback(function()
  if want_save then state=emu.createSavestate(); want_save=false; want_load=true; return end
  if want_load then
    want_load=false
    idx=idx+1
    if idx>#params then emu.log("DONE"); emu.breakExecution(); return end
    emu.loadSavestate(state)
    f=%(save)d
    held={}
    PARAM=params[idx]
    NOTE="-"
  end
end, emu.callbackType.exec, %(nmi)d)
emu.addEventCallback(function()
  f=f+1
  for _,e in ipairs(ev) do
    if e[1]==f then
      if e[2]=="press" then held[e[3]]=true elseif e[2]=="release" then held[e[3]]=false end
    end
  end
  if f==%(save)d and state==nil then want_save=true end
  if state~=nil and f==%(shot)d and PARAM~=nil then
    local s="ROUND " .. idx .. " " .. NOTE
    for _,r in ipairs(regions) do
      local out={}
      for a=0,r[3]-1 do out[#out+1]=string.format("%%02x", emu.read(r[2]+a, r[1], false)) end
      s=s .. " " .. table.concat(out)
    end
    emu.log(s)
    want_load=true
    emu.breakExecution()
  end
end, emu.eventType.endFrame)
"""


@contextlib.contextmanager
def quiet():
    """Silence MesenCore's own console output ("Uninitialized memory read" lines) on file descriptor 1."""
    sys.stdout.flush()
    saved = os.dup(1)
    with open(os.devnull, "w") as null:
        os.dup2(null.fileno(), 1)
    try:
        yield
    finally:
        sys.stdout.flush()
        os.dup2(saved, 1)
        os.close(saved)


def replay(rom_path: str, steps: str, save: int, shot: int, params: list[int],
           regions: list[tuple[str, int, int]], extra: str = "", timeout: float = 900) -> list[tuple[str, list[bytes]]]:
    """[(NOTE, [bytes of each region])] per parameter. regions: (mem|vram|cgram|wram, address, size)."""
    events, end = schedule(steps.split())
    assert save < shot <= end + 1000
    params = [params[0]] + list(params)
    lua = LUA % {
        "events": ",".join(f'{{{fr},"{k}","{v}"}}' for fr, k, v in events if k != "shot"),
        "params": ",".join(map(str, params)),
        "regions": ",".join(f"{{emu.memType.{MEM[t]},{a},{n}}}" for t, a, n in regions),
        "save": save, "shot": shot, "nmi": NMI, "extra": extra}
    out = []
    with quiet(), Mesen(rom_path) as m:
        m.run(lua, timeout)
        while True:
            line = m.log().rstrip().rsplit("\n", 1)[-1]
            if line == "DONE":
                break
            if not line.startswith("ROUND "):
                raise RuntimeError(f"unexpected log line: {line[:200]}")
            _, _, note, *raw = line.split(" ")
            out.append((note, [bytes.fromhex(r) for r in raw]))
            m.resume(120)
    return out[1:]
