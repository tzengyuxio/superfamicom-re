"""Let the game lay out any battle field, in Mesen (tools/mesen.py), and read the BG1 tilemap back.

Scenario 1, 1 player (袁術, level 2, watching other wars): 袁術 marches from 19 on 劉表's 20 with 200
food and leaves 袁胤 in charge; the field is on screen at frame ~7708. A savestate is taken before the
game reads field 20 (ROM 0x322D4 + 78 * 19, frame ~7515); for every field those 78 bytes are patched
and the state replayed, so the game's own code draws it.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "tools"))
from mesen import SNES_CGRAM, SNES_VRAM, Mesen

FIELD = 19                            # 0-based province whose field the game loads
SAVE_AT, SHOT_AT = 7450, 7708         # frames: before the field is read / field on screen
MAP_AT = 1170                         # frame: scenario 1 picked, big map on screen ("how many players?")
# title -> scenario 1 -> 1 player -> 袁術 (Y) -> level 2 -> watch wars (Y) -> all OK (Y) -> 軍事 -> 戦争 ->
# cursor to 20 -> 袁術 -> 終了 -> gold 0 -> food 200 -> attack (Y) -> 袁胤 stays as governor
INPUTS = ("w600 start w120 a w400 right w30 right w30 up w30 a w200 a w100 left w30 left w200 up w30 up w30 a w200 "
          "left w300 left w300 w2400 right w40 a w100 down w20 down w20 down w20 a w150 left:32 w20 a w150 a w150 "
          "right w30 down w20 down w20 a w150 a w150 up w20 up w20 a w300 left w300 a w200")
COLS, ROWS = 13, 12

LUA = """
local presses={%(presses)s}
local fields={%(fields)s}
local maps={%(maps)s}
local f, idx, state = 0, 0, nil
local want_save, want_load = false, false
emu.addEventCallback(function()
  local inp={}
  for _,p in ipairs(presses) do if f>=p[1] and f<p[1]+p[3] then inp[p[2]]=true end end
  emu.setInput(inp,0)
end, emu.eventType.inputPolled)
emu.addMemoryCallback(function()  -- savestates only work inside exec callbacks: use the NMI handler
  if want_save then state=emu.createSavestate(); want_save=false; want_load=true end
  if want_load then
    want_load=false
    idx=idx+1
    if idx>#fields then emu.log("DONE"); emu.breakExecution(); return end
    emu.loadSavestate(state)
    for k=0,77 do emu.write(%(at)d + k, maps[idx][k+1], emu.memType.snesPrgRom) end
    f=%(save)d
  end
end, emu.callbackType.exec, 0x00832B)
emu.addEventCallback(function()
  f=f+1
  if f==%(map)d and state==nil then emu.log("MAP"); emu.breakExecution() end
  if f==%(save)d and state==nil then want_save=true end
  if state~=nil and f==%(shot)d then
    local out={}
    for r=0,%(rows)d-1 do for c=0,%(cols)d-1 do
      local x, y = 3+2*c, 3+2*r+c%%2
      for k=0,3 do
        local a=2*((y+k//2)*32+x+k%%2)
        out[#out+1]=string.format("%%04x", emu.read16(a, emu.memType.snesVideoRam, false))
      end
    end end
    emu.log(string.format("FIELD %%d ", fields[idx]) .. table.concat(out))
    want_load=true
    emu.breakExecution()
  end
end, emu.eventType.endFrame)
"""


def capture_fields(rom_path: str, maps: dict[int, bytes], battle: int
                   ) -> tuple[dict[int, list[list[int]]], tuple[bytes, bytes], tuple[bytes, bytes]]:
    """{field: per hex (row-major), its 4 BG1 tilemap entries TL, TR, BL, BR} as the game shows them,
    (VRAM, CGRAM) of the big map screen passed on the way (frame MAP_AT) and of the first field shown.

    maps: {field: its 78 bytes}, put in place of field FIELD's."""
    presses, f = [], 10
    for step in INPUTS.split():
        if step.startswith("w"):
            f += int(step[1:])
        else:
            button, _, hold = step.partition(":")
            hold = int(hold or 4)
            presses.append(f'{{{f},"{button}",{hold}}}')
            f += hold + 20
    fields = list(maps)
    fields = [fields[0]] + fields  # the first replay still runs from power-on
    lua = LUA % {"presses": ",".join(presses), "fields": ",".join(map(str, fields)),
                 "maps": ",".join("{" + ",".join(map(str, maps[i])) + "}" for i in fields),
                 "at": battle + 78 * FIELD, "save": SAVE_AT, "shot": SHOT_AT, "rows": ROWS, "cols": COLS, "map": MAP_AT}
    out, big_map, field_mem = {}, None, None
    with Mesen(rom_path) as m:
        m.run(lua, 600)
        while True:
            line = m.log().rstrip().rsplit("\n", 1)[-1]
            if line == "DONE":
                break
            if line == "MAP":
                big_map = m.memory(SNES_VRAM), m.memory(SNES_CGRAM)
                m.resume(600)
                continue
            _, i, words = line.split()
            field_mem = field_mem or (m.memory(SNES_VRAM), m.memory(SNES_CGRAM))
            w = [int(words[k:k + 4], 16) for k in range(0, len(words), 4)]
            out[int(i)] = [w[k:k + 4] for k in range(0, len(w), 4)]
            m.resume(120)
    return out, big_map, field_mem
