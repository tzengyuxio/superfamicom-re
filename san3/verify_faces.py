#!/usr/bin/env python3
"""Check rom.Rom.face_tiles / face_palette against the game (needs Mesen 2, a few minutes).

Starts scenario 1 as 劉備 in Mesen (tools/mesen.py) and opens 情報 > 自国 > 武将 > 一覧. Pressing A on the
list opens 劉備's profile, which calls the face routine $C1:65D7 with the face word as its first stack
argument (slot 1: tiles at VRAM 0x7C0). A savestate is taken just before that press; for every plain face
1-307 and every composite face word used by a person the state is replayed and the argument overwritten, so
the game's own routines (LZ entry for plain faces, the part compositor $C1:6477 for composite ones) build the
face. The 960 bytes of tiles at VRAM 0x7C0 and CGRAM palette 4 must equal the ROM decoding, and the
unpatched argument must be 劉備's face word.

Usage: .venv/bin/python san3/verify_faces.py [--rom ROM]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
from mesen import Mesen
from rom import DEFAULT_ROM, FACE_BYTES, FACE_COUNT, FACE_PALETTE, Rom

NMI = 0x008392  # second instruction of the NMI handler ($8391 itself refuses savestates)
FACE_ROUTINE = 0xC165D7
FACE_VRAM = 0x7C0
FACE_CGRAM = 32 * 4
# title -> new game -> scenario 1 -> one player -> 劉備 -> settings -> 情報 > 自国 > 武将 > 一覧 (cursor on 劉備).
# The game is timing-sensitive: with this exact timing (w1) turn 1 opens on the command menu, not an AI battle.
INPUTS = ("w1200 start w200 start w300 a w200 a w500 up w30 a w300 right w30 right w30 w1 a w300 a w300 a w300 "
          "a w300 a w300 a w1500 down w30 down w30 down w30 a w100 down w30 a w100 a w100")
SHOT_AFTER = 80  # frames from the press to reading VRAM

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
  if want_save then state=emu.createSavestate(); want_save=false; want_load=true; return end  -- load on a later NMI
  if want_load then
    want_load=false
    idx=idx+1
    if idx>#faces then emu.log("DONE"); emu.breakExecution(); return end
    emu.loadSavestate(state)
    f=%(save)d
  end
end, emu.callbackType.exec, %(nmi)d)
local natural = -1
emu.addMemoryCallback(function()  -- face routine entry: face word at sp+4
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
    """{face word: (unpatched argument, 960 bytes of VRAM tiles, 32 bytes of palette)}."""
    presses = schedule(INPUTS)
    save = presses[-1][0] + 24 + 120
    presses.append((save + 10, "a"))
    faces = [faces[0]] + list(faces)  # the first replay still runs from power-on: done twice
    lua = LUA % {"presses": ",".join(f'{{{f},"{b}"}}' for f, b in presses), "faces": ",".join(map(str, faces)),
                 "save": save, "shot": save + 10 + SHOT_AFTER, "nmi": NMI, "routine": FACE_ROUTINE,
                 "size": FACE_BYTES, "vram": FACE_VRAM, "pal": FACE_CGRAM}
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
    ap = argparse.ArgumentParser(description="驗證頭像解碼")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    t0 = time.time()
    rom = Rom(args.rom)
    persons = rom.persons()
    liu_bei = next(p["face"] for p in persons if p["name"] == "劉備")
    composite = sorted({p["face"] for p in persons if p["face"] & 0x8000})
    plain = list(range(1, FACE_COUNT + 1))
    shown = capture_faces(args.rom, plain + composite)
    palette = rom.data[FACE_PALETTE:FACE_PALETTE + 32]
    errors = 0
    for label, faces in (("plain", plain), ("composite", composite)):
        bad = [f for f in faces if shown.get(f, (0, b"", b""))[1:] != (rom.face_tiles(f), palette)]
        errors += len(bad)
        print(f"[faces] {label}: {len(faces) - len(bad)}/{len(faces)} VRAM tiles and palette match the ROM"
              + (f" (NG {[hex(f) for f in bad][:20]})" if bad else ""))
    naturals = {v[0] for v in shown.values()}
    print(f"[person] 劉備's profile asks for face {sorted(hex(n) for n in naturals)} (ROM: {liu_bei:#x})")
    errors += naturals != {liu_bei}
    print(f"time {time.time() - t0:.0f} s")
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
