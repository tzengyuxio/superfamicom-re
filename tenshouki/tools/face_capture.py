"""Let the game build any face code, in Mesen (tools/mesen.py), and read the face tiles and palette.

Boots with power-on RAM all zeros, starts 信長初陣 as 蠣崎季広 (person 1) and opens 情報 -> 家臣 -> his
general's screen at the first turn. A savestate is taken on the retainer list, just before the game
reads his face code; for every code the ROM bytes are patched and the state replayed, so the game's own
face routine ($C3:2DF5) builds the face. The face goes to VRAM tiles 0x522-0x53F (5 x 6, row-major)
with CGRAM palette 9.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "tools"))
from mesen import Mesen

FACE_CODE_AT = 0xD0F80 + 14 * 1     # 蠣崎季広's face code in the person table
FACE_VRAM = 0x522 * 32
FACE_PALETTE = 9
NMI = 0x008FC3                     # native NMI vector
# title -> new game -> 信長初陣 -> 蠣崎季広 -> first turn -> 情報 -> 家臣 (list), then a: his screen
INPUTS = ("w1100 start w300 start w300 a w300 a w300 a w300 a w300 start w300 down*8 w30 a w300 a w600 w8400"
          " right*4 w30 a w200 right*3 w30 a w200")
SHOT_AFTER = 120                    # frames from the last press to reading VRAM

LUA = """
local presses={%(presses)s}
local codes={%(codes)s}
local f, idx, state = 0, 0, nil
local want_save, want_load = false, false
emu.addEventCallback(function()
  local inp={}
  for _,p in ipairs(presses) do
    if f>=p[1] and f<p[1]+4 then inp[p[2]]=true end
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
end, emu.callbackType.exec, %(nmi)d)
emu.addEventCallback(function()
  f=f+1
  if f==%(save)d and state==nil then want_save=true end
  if state~=nil and f==%(shot)d then
    local out={}
    for a=0,959 do out[#out+1]=string.format("%%02x", emu.read(%(vram)d + a, emu.memType.snesVideoRam, false)) end
    for a=0,31 do out[#out+1]=string.format("%%02x", emu.read(%(pal)d + a, emu.memType.snesCgRam, false)) end
    emu.log(string.format("FACE %%04X ", codes[idx]) .. table.concat(out))
    want_load=true
    emu.breakExecution()
  end
end, emu.eventType.endFrame)
"""


def schedule(inputs: str) -> list[tuple[int, str]]:
    """(frame, button) presses: <button>[*n] holds 4 frames then waits 20, w<n> waits n frames."""
    out, f = [], 10
    for step in inputs.split():
        if step.startswith("w"):
            f += int(step[1:])
            continue
        button, _, n = step.partition("*")
        for _ in range(int(n or 1)):
            out.append((f, button))
            f += 24
    return out


def capture_faces(rom_path: str, codes: list[int]) -> dict[int, tuple[bytes, bytes]]:
    """{code: (960 bytes of face tiles, 32 bytes of palette) as the game puts them in VRAM / CGRAM}."""
    presses = schedule(INPUTS)
    save = presses[-1][0] + 24 + 190      # on the retainer list
    presses.append((save + 10, "a"))      # open the general's screen
    codes = [codes[0]] + list(codes)      # the first replay still shows the unpatched face
    lua = LUA % {"presses": ",".join(f'{{{f},"{b}"}}' for f, b in presses), "codes": ",".join(map(str, codes)),
                 "at": FACE_CODE_AT, "save": save, "shot": save + 10 + SHOT_AFTER, "nmi": NMI,
                 "vram": FACE_VRAM, "pal": 32 * FACE_PALETTE}
    out = {}
    with Mesen(rom_path) as m:
        m.run(lua, 600)
        while True:
            line = m.log().rstrip().rsplit("\n", 1)[-1]
            if line == "DONE":
                break
            _, code, raw = line.split()
            raw = bytes.fromhex(raw)
            out[int(code, 16)] = (raw[:960], raw[960:])
            m.resume(60)
    return out
