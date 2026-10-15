"""Savestate replay in Mesen (tools/mesen.py): play a button script once, take a savestate, then for every run
patch PRG ROM / WRAM, press more buttons, and read memory back at a given frame.

Savestates only work inside exec callbacks, so they are taken and loaded in the NMI handler, at its second
instruction (native NMI vector + 1, read from the LoROM or HiROM header; pass nmi= to hook elsewhere). A state
cannot be loaded in the callback that created it, so the first load waits for the next NMI, and the first load
does not take effect (that run still continues from power-on), so run 0 is done twice.
extra_lua can add callbacks (e.g. a read trace) and hand their result back through EXTRA_SHOT().

    runs = [{"patch": [(rom_offset, bytes)], "wram": [(addr, bytes)], "steps": "a:10 w100",
             "shot": 150, "read": [("vram", 0xC800, 960), ("cgram", 0xA0, 32)]}]
    results = replay(rom_path, "w900 start:10 ...", save_at=3790, runs=runs)  # [[bytes per read], ...]

"steps" use tools/drive.py syntax (button[:hold][*n], w<n>; @tag is skipped) and count from the savestate frame;
"shot" is the frame (after the savestate) at which the reads are made. expand() spells out the *n repeats and
end_frame() gives the frame after the last step, e.g. replay(rom, boot, end_frame(boot), ...) saves right after
the boot presses. PRG patches of a run are undone before the next run.
Boot presses after save_at are dropped (each run plays its own "steps" from the savestate), so take the
savestate after the last boot press, or put the whole sequence into every run's steps.
"""
import os
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mesen import Mesen

LOG_SIZE = 1 << 26  # the log keeps every run's line; 4 MB (the Mesen.log default) is too small for big reads
MEM = {"vram": "snesVideoRam", "cgram": "snesCgRam", "wram": "snesWorkRam", "oam": "snesSpriteRam",
       "rom": "snesPrgRom"}

LUA = """
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


def expand(steps: str) -> str:
    """'a:10*3 w100' -> 'a:10 a:10 a:10 w100'."""
    out = []
    for st in steps.split():
        s, _, n = st.partition("*")
        out += [s] * int(n or 1)
    return " ".join(out)


def presses(steps: str, start: int) -> list[tuple[int, str, int]]:
    """[(frame, button, hold)]: a press holds `hold` frames (default 4) and is followed by 20."""
    out, f = [], start
    for st in expand(steps).split():
        if st.startswith("w"):
            f += int(st[1:])
        elif not st.startswith("@"):
            b, _, hold = st.partition(":")
            out.append((f, b, int(hold or 4)))
            f += int(hold or 4) + 20
    return out


def end_frame(steps: str, start: int = 10) -> int:
    """Frame after the last step; start is 10 for a boot script, 0 for a run's steps (counted from the savestate)."""
    f = start
    for st in expand(steps).split():
        if st.startswith("w"):
            f += int(st[1:])
        elif not st.startswith("@"):
            f += int(st.partition(":")[2] or 4) + 20
    return f


def load_rom_bytes(path: str) -> bytes:
    """The ROM image of a .sfc / .smc file or a zip holding one, without a 512-byte copier header."""
    if path.lower().endswith(".zip"):
        with zipfile.ZipFile(path) as z:
            data = z.read(next(n for n in z.namelist() if n.lower().endswith((".sfc", ".smc"))))
    else:
        with open(path, "rb") as f:
            data = f.read()
    return data[len(data) % 0x8000:]


def nmi_hook(data: bytes) -> int:
    """Second instruction of the native NMI handler: the vector of the LoROM or HiROM header whose checksum and
    complement add up to 0xFFFF, + 1 (every KOEI SFC handler starts with a one-byte SEI)."""
    for header in (0x7FC0, 0xFFC0):
        h = data[header:header + 0x40]
        if len(h) == 0x40 and (h[0x1C] | h[0x1D] << 8) + (h[0x1E] | h[0x1F] << 8) == 0xFFFF:
            return (h[0x2A] | h[0x2B] << 8) + 1
    raise ValueError("no valid LoROM / HiROM header")


def _lua_list(items) -> str:
    return "{" + ",".join(items) + "}"


def _bytes(b: bytes) -> str:
    return "{" + ",".join(map(str, b)) + "}"


def replay(rom_path: str, steps: str, save_at: int, runs: list[dict], timeout: float = 1800,
           extra_lua: str = "", nmi: int | None = None) -> list[list[bytes]]:
    """extra_lua may define EXTRA_RESET() (called after each savestate load) and EXTRA_SHOT() (returns a hex
    string appended to the reads of the run). EXTRA_RESET also runs for the dropped first load, so it is called
    once more than there are runs: hand per-run values over through "wram" patches, not by counting calls."""
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
                 "runs": ",\n".join(lua_runs), "save": save_at,
                 "nmi": nmi_hook(data) if nmi is None else nmi}
    lua = extra_lua + "\n" + lua  # not through %: extra Lua may contain % and braces
    out = {}
    with Mesen(rom_path) as m:
        m.run(lua, timeout)
        while True:
            line = m.log(LOG_SIZE).rstrip().rsplit("\n", 1)[-1]
            if line == "DONE":
                break
            parts = line.split(" ")
            if not parts[0] == "RUN":
                raise RuntimeError(m.log()[-3000:])
            out[int(parts[1])] = [bytes.fromhex(x) for x in parts[2:]]
            m.resume(timeout)
    return [out[i] for i in range(2, len(runs) + 1)]
