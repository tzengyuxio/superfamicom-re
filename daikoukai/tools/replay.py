"""Savestate replay in Mesen (tools/mesen.py): play a button script once, take a savestate, then for every run
patch PRG ROM / WRAM, press more buttons, and read memory back at a given frame.

Savestates only work inside exec callbacks, so they are taken and loaded in the NMI handler ($00:8362), and
the first load does not take effect (that run still continues from power-on), so run 0 is done twice.
extra_lua can add callbacks (e.g. a read trace) and hand their result back through EXTRA_SHOT().

    runs = [{"patch": [(rom_offset, bytes)], "wram": [(addr, bytes)], "steps": "a:10 w100",
             "shot": 150, "read": [("vram", 0xC800, 960), ("cgram", 0xA0, 32)]}]
    results = replay(rom_path, "w900 start:10 ...", save_at=3790, runs=runs)  # [[bytes per read], ...]

"steps" use tools/drive.py syntax (button[:hold], w<n>) and count from the savestate frame; "shot" is the
frame (after the savestate) at which the reads are made. PRG patches of a run are undone before the next run.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "tools"))
from mesen import Mesen

NMI = 0x008362  # second instruction of the native NMI handler $00:8361
MEM = {"vram": "snesVideoRam", "cgram": "snesCgRam", "wram": "snesWorkRam", "oam": "snesSpriteRam",
       "rom": "snesPrgRom"}

LUA = """
%(extra)s
local boot=%(boot)s
local runs={%(runs)s}
local f, idx, state = 0, 0, nil
local want_save, want_load = false, false
local presses=boot
emu.addEventCallback(function()
  local inp={}
  for _,p in ipairs(presses) do if f>=p[1] and f<p[1]+p[3] then inp[p[2]]=true end end
  emu.setInput(inp,0)
end, emu.eventType.inputPolled)
emu.addMemoryCallback(function()
  if want_save then state=emu.createSavestate(); want_save=false; want_load=true end
  if want_load then
    want_load=false
    if idx>0 then for _,p in ipairs(runs[idx].undo) do
      for k=1,#p[2] do emu.write(p[1]+k-1, p[2][k], emu.memType.snesPrgRom) end
    end end
    idx=idx+1
    if idx>#runs then emu.log("DONE"); emu.breakExecution(); return end
    emu.loadSavestate(state)
    local r=runs[idx]
    for _,p in ipairs(r.patch) do for k=1,#p[2] do emu.write(p[1]+k-1, p[2][k], emu.memType.snesPrgRom) end end
    for _,p in ipairs(r.wram) do for k=1,#p[2] do emu.write(p[1]+k-1, p[2][k], emu.memType.snesWorkRam) end end
    presses=r.presses
    if EXTRA_RESET then EXTRA_RESET() end
    f=%(save)d
  end
end, emu.callbackType.exec, %(nmi)d)
emu.addEventCallback(function()
  f=f+1
  if f==%(save)d and state==nil then want_save=true end
  if state~=nil and idx>0 and f==runs[idx].shot then
    local out={}
    for _,rd in ipairs(runs[idx].read) do
      local s={}
      for a=0,rd[3]-1 do s[#s+1]=string.format("%%02x", emu.read(rd[2]+a, emu.memType[rd[1]], false)) end
      out[#out+1]=table.concat(s)
    end
    if EXTRA_SHOT then out[#out+1]=EXTRA_SHOT() end
    emu.log(string.format("RUN %%d ", idx) .. table.concat(out, " "))
    want_load=true
    emu.breakExecution()
  end
end, emu.eventType.endFrame)
"""


def presses(steps: str, start: int) -> list[tuple[int, str, int]]:
    out, f = [], start
    for st in steps.split():
        if st.startswith("w"):
            f += int(st[1:])
        else:
            b, _, hold = st.partition(":")
            out.append((f, b, int(hold or 4)))
            f += int(hold or 4) + 20
    return out


def _lua_list(items) -> str:
    return "{" + ",".join(items) + "}"


def _bytes(b: bytes) -> str:
    return "{" + ",".join(map(str, b)) + "}"


def replay(rom_path: str, steps: str, save_at: int, runs: list[dict], timeout: float = 1800,
           extra_lua: str = "") -> list[list[bytes]]:
    """extra_lua may define EXTRA_RESET() (called after each savestate load) and EXTRA_SHOT() (returns a hex
    string appended to the reads of the run)."""
    from rom import load_rom_bytes
    data = load_rom_bytes(rom_path)
    runs = [runs[0]] + list(runs)
    lua_runs = []
    for r in runs:
        patch = r.get("patch", [])
        lua_runs.append(
            "{patch=" + _lua_list(f"{{{o},{_bytes(b)}}}" for o, b in patch)
            + ",undo=" + _lua_list(f"{{{o},{_bytes(data[o:o + len(b)])}}}" for o, b in patch)
            + ",wram=" + _lua_list(f"{{{a},{_bytes(b)}}}" for a, b in r.get("wram", []))
            + ",presses=" + _lua_list(f'{{{f},"{b}",{h}}}' for f, b, h in presses(r.get("steps", ""), save_at))
            + f",shot={save_at + r['shot']}"
            + ",read=" + _lua_list(f'{{"{MEM[m]}",{a},{n}}}' for m, a, n in r["read"]) + "}")
    lua = LUA % {"boot": _lua_list(f'{{{f},"{b}",{h}}}' for f, b, h in presses(steps, 10)),
                 "runs": ",\n".join(lua_runs), "save": save_at, "nmi": NMI,
                 "extra": extra_lua}
    out = {}
    with Mesen(rom_path) as m:
        m.run(lua, timeout)
        while True:
            line = m.log().rstrip().rsplit("\n", 1)[-1]
            if line == "DONE":
                break
            parts = line.split(" ")
            if not parts[0] == "RUN":
                raise RuntimeError(m.log()[-3000:])
            out[int(parts[1])] = [bytes.fromhex(x) for x in parts[2:]]
            m.resume(timeout)
    return [out[i] for i in range(2, len(runs) + 1)]
