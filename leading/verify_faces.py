#!/usr/bin/env python3
"""Check the faces against the game's own face routine $01:A58F.

The 会長 greets the new president at ~frame 9335 by calling $01:A58F (stack +8 = kind, +10 = image). From a
savestate just before, every run patches a (kind, image) pair into the ending graphics ED_MAN4 (ROM 0xF8395 =
$1F:8395, not read in this scene; spare WRAM is not safe here, the game overwrote $7F:FFF0); a Lua exec hook at the
routine's entry replaces the arguments with it. About 50 frames later VRAM byte 0xBC00 (960 bytes, where $01:A58F copies the face) must equal
rom.Rom.face_bytes — or the face with one of its 3 strips laid over tile rows 1-3 (the talking animation) — and
CGRAM 0x1E0 (sprite palette 7, loaded by the routine) must equal the KAO file. All 7 kinds x all images (44 faces).

Usage: .venv/bin/python leading/verify_faces.py [--rom ROM]
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "tools"))
sys.path.insert(0, HERE)
import lc
from replay import end_frame, replay
from rom import DEFAULT_ROM, FACE_BYTES, FACE_KINDS, STRIP_BYTES, Rom

BOOT = lc.NEW_GAME + " a:10 w200" * 4 + " a:10"     # the next face call ($01:A58F) is at ~9335
PARAM = 0xF8395                                     # ROM offset of $1F:8395: marker 0xA5, kind, image
VRAM_FACE, CGRAM_FACE = 0xBC00, 0x1E0

HOOK_LUA = """
local function hook()
  local function rd(a) return emu.read(a, emu.memType.snesMemory, false) end
  if rd(0x1F8395) ~= 0xA5 then return end
  local s = emu.getState()["cpu.sp"]
  emu.write(s + 8, rd(0x1F8396), emu.memType.snesMemory); emu.write(s + 9, 0, emu.memType.snesMemory)
  emu.write(s + 10, rd(0x1F8397), emu.memType.snesMemory); emu.write(s + 11, 0, emu.memType.snesMemory)
end
emu.addMemoryCallback(hook, emu.callbackType.exec, 0x01A58F)
emu.addMemoryCallback(hook, emu.callbackType.exec, 0x81A58F)
"""


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證頭像（改頭像程式的引數）")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    faces = rom.faces()
    runs = [{"patch": [(PARAM, bytes((0xA5, f["kind"], f["image"])))], "shot": 130,
             "read": [("vram", VRAM_FACE, FACE_BYTES), ("cgram", CGRAM_FACE, 32)]} for f in faces]
    save = end_frame(BOOT)
    res = replay(args.rom, BOOT, save, runs, extra_lua=HOOK_LUA)
    pal = rom.raw("KAO")
    bad_img, bad_pal, strips = [], [], [0, 0, 0, 0]
    for f, (vram, cgram) in zip(faces, res):
        base = rom.face_bytes(f["kind"], f["image"])
        variants = [base] + [base[:160] + rom.strip_bytes(f["kind"], f["image"], k) + base[160 + STRIP_BYTES:]
                             for k in range(3)]
        hit = next((i for i, v in enumerate(variants) if v == vram), None)
        if hit is None:
            bad_img.append((FACE_KINDS[f["kind"]], f["image"]))
        else:
            strips[hit] += 1
        if cgram != pal:
            bad_pal.append((FACE_KINDS[f["kind"]], f["image"]))
    n = len(faces)
    print(f"[image] {n - len(bad_img)}/{n} faces in VRAM = ROM (plain {strips[0]}, strip 1/2/3 laid over "
          f"{strips[1]}/{strips[2]}/{strips[3]})" + (f" NG {bad_img[:8]}" if bad_img else ""))
    print(f"[palette] {n - len(bad_pal)}/{n} CGRAM 0x1E0 = KAO" + (f" NG {bad_pal[:8]}" if bad_pal else ""))
    errors = len(bad_img) + len(bad_pal)
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
