#!/usr/bin/env python3
"""Check rom.Rom.face_tiles / face_palette against the game (needs Mesen 2, about 10 minutes).

Starts scenario 1 in Mesen (tools/mesen.py) up to the ruler selection map. Choosing 劉繇 opens a confirmation
box with his face, drawn by the face routine $C3:59B7 (argument word at sp+4 = face code; bit 15 set ->
composed face $C3:5303, else portrait $C3:5823; then palette $C3:598B). A savestate is taken just before
that press; for every portrait 0-338 and every composed face code used by a person, the state is replayed
and the argument overwritten (the routine's "last code" cache $7E:5743 is cleared so it always decodes).
The 960 bytes of tiles at VRAM 0x440 and CGRAM palette 3 must equal the ROM decoding, and the unpatched
argument must be 劉繇's face code (74).

Usage: .venv/bin/python san4/verify_faces.py [--rom ROM] [--quick]
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
from mesen import Mesen
from rom import DEFAULT_ROM, FACE_BYTES, FACE_PALETTES, PORTRAIT_COUNT, Rom, le16

NMI = 0x008FA4
FACE_ROUTINE = 0xC359B7
FACE_CACHE = 0x7E5743
FACE_VRAM = 0x440
FACE_CGRAM = 32 * 3
HOLD = 10
# title -> new game -> scenario 1 -> ruler selection map (cursor on 劉繇); the last a opens the confirmation box
INPUTS = "w1300 start w600 a w600 a w800 a w600"
SHOT_AFTER = 150  # frames from the press to reading VRAM
LIU_YAO = 74      # person id; his face code is 74

LUA = """
local presses={%(presses)s}
local faces={%(faces)s}
local f, idx, state = 0, 0, nil
local want_save, want_load = false, false
emu.addEventCallback(function()
  local inp={}
  for _,p in ipairs(presses) do
    if f>=p[1] and f<p[1]+%(hold)d then inp[p[2]]=true end
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
  emu.write(%(cache)d, 0xFF, emu.memType.snesMemory)
  emu.write(%(cache)d + 1, 0xFF, emu.memType.snesMemory)
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
    """(frame, button) presses: a button is held HOLD frames, w<n> waits n frames."""
    out, f = [], 10
    for step in inputs.split():
        if step.startswith("w"):
            f += int(step[1:])
        else:
            out.append((f, step))
            f += HOLD
    return out


def capture_faces(rom_path: str, faces: list[int]) -> dict[int, tuple[int, bytes, bytes]]:
    """{face code: (unpatched argument, 960 bytes of VRAM tiles, 32 bytes of palette)}."""
    presses = schedule(INPUTS)
    save = presses[-1][0] + HOLD + 600
    presses.append((save + 10, "a"))
    faces = [faces[0]] + list(faces)  # the first replay still runs from power-on: done twice
    lua = LUA % {"presses": ",".join(f'{{{f},"{b}"}}' for f, b in presses), "faces": ",".join(map(str, faces)),
                 "save": save, "shot": save + 10 + SHOT_AFTER, "nmi": NMI, "routine": FACE_ROUTINE,
                 "cache": FACE_CACHE, "size": FACE_BYTES, "vram": FACE_VRAM, "pal": FACE_CGRAM, "hold": HOLD}
    out = {}
    with Mesen(rom_path) as m:
        m.run(lua, 900)
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
    ap = argparse.ArgumentParser(description="驗證頭像解碼（專屬頭像與組合臉）")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--quick", action="store_true", help="only every 8th portrait and composed code")
    args = ap.parse_args()
    rom = Rom(args.rom)
    persons = rom.persons()
    composed = sorted({p["face"] for p in persons if p["face"] & 0x8000})
    portraits = list(range(PORTRAIT_COUNT))
    if args.quick:
        portraits, composed = portraits[::8], composed[::8]
    shown = capture_faces(args.rom, portraits + composed)
    errors = 0
    for label, codes in (("portraits", portraits), ("composed", composed)):
        bad = []
        for code in codes:
            n = rom.face_palette_number(code)
            want = (rom.face_tiles(code), rom.data[FACE_PALETTES + 32 * n:FACE_PALETTES + 32 * n + 32])
            if shown.get(code, (0, b"", b""))[1:] != want:
                bad.append(hex(code) if code & 0x8000 else code)
        errors += len(bad)
        print(f"[{label}] {len(codes) - len(bad)}/{len(codes)}: VRAM tiles and CGRAM palette 3 match the ROM"
              + (f" (NG {bad[:20]}{' ...' if len(bad) > 20 else ''})" if bad else ""))
    naturals = {v[0] for v in shown.values()}
    want = le16(persons[LIU_YAO]["raw"], 20)
    print(f"[person] 劉繇's confirmation box asks for face {sorted(naturals)} (person {LIU_YAO} +20 = {want})")
    errors += naturals != {want}
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
