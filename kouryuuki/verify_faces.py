#!/usr/bin/env python3
"""Check rom.Rom.face_tiles / face_palette against the game (needs Mesen 2, a few minutes).

Starts scenario 1 as 項羽 in Mesen (tools/mesen.py). Choosing the lord opens his profile, which calls the
face routine $C9:4341 with the face number as its stack argument. A savestate is taken just before that
press; for every face 0-96 the state is replayed and the argument overwritten, so the game's own routine
loads the face. The 960 bytes of tiles at VRAM 0x400 and CGRAM palette 8 must equal the ROM decoding,
and the unpatched argument must be 項羽's person id (0).

Usage: .venv/bin/python kouryuuki/verify_faces.py [--rom ROM]
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
from mesen import Mesen
from rom import DEFAULT_ROM, FACE_BYTES, FACE_COUNT, FACE_PALETTE, Rom

NMI = 0x0084A2
FACE_ROUTINE = 0xC94341
FACE_VRAM = 0x400
FACE_CGRAM = 32 * 8
# title -> new game -> scenario 1 (its prologue runs ~6500 frames) -> settings -> 項羽; the last a opens his profile
INPUTS = "w900 start w200 start w200 a w300 a w6500 a w200 a w200 a w200"
SHOT_AFTER = 250  # frames from the last press to reading VRAM

LUA = """
local presses={%(presses)s}
local faces={%(faces)s}
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
    if idx>#faces then emu.log("DONE"); emu.breakExecution(); return end
    emu.loadSavestate(state)
    f=%(save)d
  end
end, emu.callbackType.exec, %(nmi)d)
local natural = -1
emu.addMemoryCallback(function()  -- face routine entry: argument word at sp+4
  if idx==0 then return end
  local sp=emu.getState()["cpu.sp"]
  natural=emu.read(sp+4,emu.memType.snesMemory) | emu.read(sp+5,emu.memType.snesMemory)<<8
  emu.write(sp+4, faces[idx] & 0xFF, emu.memType.snesMemory)
  emu.write(sp+5, faces[idx] >> 8, emu.memType.snesMemory)
end, emu.callbackType.exec, %(routine)d)
emu.addEventCallback(function()
  f=f+1
  if f==%(save)d and state==nil then want_save=true end
  if state~=nil and f==%(shot)d then
    local out={}
    for a=0,%(size)d-1 do out[#out+1]=string.format("%%02x", emu.read(%(vram)d + a, emu.memType.snesVideoRam, false)) end
    for a=0,31 do out[#out+1]=string.format("%%02x", emu.read(%(pal)d + a, emu.memType.snesCgRam, false)) end
    emu.log(string.format("FACE %%d %%d ", faces[idx], natural) .. table.concat(out))
    natural=-1
    want_load=true
    emu.breakExecution()
  end
end, emu.eventType.endFrame)
"""


def schedule(inputs: str) -> list[tuple[int, str]]:
    """(frame, button) presses: a button holds 4 frames then waits 20, w<n> waits n frames."""
    out, f = [], 10
    for step in inputs.split():
        if step.startswith("w"):
            f += int(step[1:])
        else:
            out.append((f, step))
            f += 24
    return out


def capture_faces(rom_path: str, faces: list[int]) -> dict[int, tuple[int, bytes, bytes]]:
    """{face: (unpatched argument, 960 bytes of VRAM tiles, 32 bytes of palette)}."""
    presses = schedule(INPUTS)
    save = presses[-1][0] + 24 + 180
    presses.append((save + 10, "a"))
    faces = [faces[0]] + list(faces)  # the first replay still runs from power-on: done twice
    lua = LUA % {"presses": ",".join(f'{{{f},"{b}"}}' for f, b in presses), "faces": ",".join(map(str, faces)),
                 "save": save, "shot": save + 10 + SHOT_AFTER, "nmi": NMI, "routine": FACE_ROUTINE,
                 "size": FACE_BYTES, "vram": FACE_VRAM, "pal": FACE_CGRAM}
    out = {}
    with Mesen(rom_path) as m:
        m.run(lua, 600)
        while True:
            line = m.log().rstrip().rsplit("\n", 1)[-1]
            if line == "DONE":
                break
            _, face, natural, raw = line.split()
            raw = bytes.fromhex(raw)
            out[int(face)] = (int(natural), raw[:FACE_BYTES], raw[FACE_BYTES:])
            m.resume(60)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證頭像解碼")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    shown = capture_faces(args.rom, list(range(FACE_COUNT)))
    palette = rom.data[FACE_PALETTE:FACE_PALETTE + 32]
    bad = [n for n in range(FACE_COUNT) if shown.get(n, (0, b"", b""))[1:] != (rom.face_tiles(n), palette)]
    naturals = {v[0] for v in shown.values()}
    print(f"[faces] {FACE_COUNT - len(bad)}/{FACE_COUNT}: VRAM tiles and palette match the ROM"
          + (f" (NG {bad})" if bad else ""))
    print(f"[person] 項羽's profile asks for face {sorted(naturals)} (person id 0)")
    errors = len(bad) + (naturals != {0})
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
