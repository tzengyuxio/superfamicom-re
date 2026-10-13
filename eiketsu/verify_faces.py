#!/usr/bin/env python3
"""Check rom.Rom.face_tiles / face_palette against the game (needs Mesen 2, about 5 minutes).

Plays the opening in Mesen (tools/mesen.py, eiketsu/tools/replay.py) into battle 0 (汜水関). In its opening
dialogue 華雄 (person 5) speaks; his face is built by the face routine $C7:04F7 (argument word at sp+4 = face
number; tiles decompressed and copied to $7E:8444, then sent to VRAM byte 0x5F40). A savestate is taken just
before that press; for every face 0-239 the state is replayed and the argument overwritten (the routine's
"last face" cache $7E:88C4 is cleared so it always decodes). The 1152 bytes at VRAM 0x5F40 and CGRAM palette 3
must equal the ROM decoding, and the unpatched argument must be 華雄's face number (name record +14).

Usage: .venv/bin/python eiketsu/verify_faces.py [--rom ROM] [--quick]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "tools"))
from replay import TO_BATTLE, replay
from rom import DEFAULT_ROM, FACE_BYTES, FACE_COUNT, FACE_PALETTE, Rom

FACE_ROUTINE = 0xC704F7
FACE_CACHE = 0x7E88C4
FACE_VRAM = 0x5F40
FACE_CGRAM = 32 * 3
HUA_XIONG = 5
STEPS = TO_BATTLE + " a:10 w150"   # 華雄 speaks and his face is built at frame ~22450
SAVE, SHOT = 22380, 22560

LUA = f"""
emu.addMemoryCallback(function()  -- face routine entry: argument word at sp+4
  if PARAM==nil then return end
  local sp=emu.getState()["cpu.sp"]
  if NOTE=="-" then
    NOTE=tostring(emu.read(sp+4,emu.memType.snesMemory) | emu.read(sp+5,emu.memType.snesMemory)<<8)
  end
  emu.write(sp+4, PARAM & 0xFF, emu.memType.snesMemory)
  emu.write(sp+5, PARAM >> 8, emu.memType.snesMemory)
  emu.write({FACE_CACHE}, 0xFF, emu.memType.snesMemory)
  emu.write({FACE_CACHE} + 1, 0xFF, emu.memType.snesMemory)
end, emu.callbackType.exec, {FACE_ROUTINE})
"""


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證頭像解碼")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--quick", action="store_true", help="only every 8th face")
    args = ap.parse_args()
    rom = Rom(args.rom)
    t = time.time()
    faces = list(range(FACE_COUNT))[::8 if args.quick else 1]
    shown = replay(args.rom, STEPS, SAVE, SHOT, faces, [("vram", FACE_VRAM, FACE_BYTES), ("cgram", FACE_CGRAM, 32)],
                   LUA)
    pal = rom.data[FACE_PALETTE:FACE_PALETTE + 32]
    bad = [n for n, (_, (tiles, cg)) in zip(faces, shown) if tiles != rom.face_tiles(n) or cg != pal]
    print(f"[faces] {len(faces) - len(bad)}/{len(faces)}: VRAM tiles at 0x5F40 and CGRAM palette 3 match the ROM"
          + (f" (NG {bad[:20]})" if bad else ""))
    naturals = {note for note, _ in shown}
    want = rom.persons()[HUA_XIONG]["face"]
    print(f"[person] 華雄's line asks for face {sorted(naturals)} (person {HUA_XIONG} +14 = {want})")
    errors = len(bad) + (naturals != {str(want)})
    print(f"({time.time() - t:.0f} s)")
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
