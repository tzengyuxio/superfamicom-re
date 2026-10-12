"""Let the game draw any face code, in Mesen (tools/mesen.py), and read the pixels off the screen.

Boots with power-on RAM all zeros, starts scenario 1 with 0 players (computer-only demo) and waits
for the first province screen: 王朗 (person 13) at frame ~2824, face drawn at (72, 39). A savestate
is taken just before the game reads his face code; for every code the ROM bytes are patched and the
state replayed, so the game's own face routine draws it.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "tools"))
from mesen import Mesen

FACE_CODE_AT = 0x12434 + 13 * 9 + 7   # 王朗's face code in the person table
SAVE_AT, SHOT_AT = 2815, 2900         # frames: before the face code is read / face on screen
FACE_X, FACE_Y = 72, 39
INPUTS = "w600 start w120 a w400 a w200 a w200 a w200"  # title -> scenario 1 -> 0 players -> confirm

LUA = """
local presses={%(presses)s}
local codes={%(codes)s}
local f, idx, state = 0, 0, nil
local want_save, want_load = false, false
emu.addEventCallback(function()
  local inp={}
  for i,p in ipairs(presses) do
    if f>=p and f<p+4 then if i==1 then inp.start=true else inp.a=true end end
  end
  emu.setInput(inp,0)
end, emu.eventType.inputPolled)
emu.addMemoryCallback(function()  -- savestates only work inside exec callbacks: use the NMI handler
  if want_save then state=emu.createSavestate(); want_save=false; want_load=true end
  if want_load then
    want_load=false
    idx=idx+1
    if idx>#codes then emu.log("DONE"); emu.breakExecution(); return end
    emu.loadSavestate(state)
    emu.write(%(at)d, codes[idx] & 0xFF, emu.memType.snesPrgRom)
    emu.write(%(at)d + 1, codes[idx] >> 8, emu.memType.snesPrgRom)
    f=%(save)d
  end
end, emu.callbackType.exec, 0x00832B)
emu.addEventCallback(function()
  f=f+1
  if f==%(save)d and state==nil then want_save=true end
  if state~=nil and f==%(shot)d then
    local px={}
    for y=0,47 do for x=0,39 do px[#px+1]=string.format("%%06x", emu.getPixel(%(x)d+x, %(y)d+y) & 0xFFFFFF) end end
    emu.log(string.format("FACE %%04X ", codes[idx]) .. table.concat(px))
    want_load=true
    emu.breakExecution()
  end
end, emu.eventType.endFrame)
"""


def capture_faces(rom_path: str, codes: list[int]) -> dict[int, list[tuple[int, int, int]]]:
    """{code: 40x48 RGB pixels as the game shows them}."""
    presses, f = [], 10
    for step in INPUTS.split():
        if step.startswith("w"):
            f += int(step[1:])
        else:
            presses.append(f)
            f += 24
    codes = [codes[0]] + list(codes)  # the first replay still shows the unpatched face
    lua = LUA % {"presses": ",".join(map(str, presses)), "codes": ",".join(map(str, codes)),
                 "at": FACE_CODE_AT, "save": SAVE_AT, "shot": SHOT_AT, "x": FACE_X, "y": FACE_Y}
    out = {}
    with Mesen(rom_path) as m:
        m.run(lua, 300)
        while True:
            line = m.log().rstrip().rsplit("\n", 1)[-1]
            if line == "DONE":
                break
            _, code, hexpx = line.split()
            out[int(code, 16)] = [tuple(bytes.fromhex(hexpx[i:i + 6])) for i in range(0, len(hexpx), 6)]
            m.resume(60)
    return out
