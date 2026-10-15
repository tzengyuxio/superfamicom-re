#!/usr/bin/env python3
"""Check the faces (rom.Rom.face_tiles / face_palette) against the game (needs Mesen 2, about 4 minutes).

Scenario 0 as 日本, 作戦 -> 人事 -> 海軍提督 shows the face of the admiral under the cursor, drawn by the face
routine (original $D4:6DBC(x, y, f), Rev 1 $C1:A08B). Each run moves the cursor, and a Lua hook at the routine's
entry replaces the face number f (the word at 8,S) with the run's test face, handed over in an unused 0xFF
padding byte of the ROM (a PRG patch). When the run ends, VRAM bytes 0x800-0xBBF (30 4bpp tiles) must equal LZ
entry 753 + f and CGRAM row 15 (bytes 0x1E0-0x1FF) Rom.face_palette(f), for all 104 faces. The unpatched runs
must show face 1 / 0 for admirals 1 / 0 and face 60 / 61 for generals 0 / 1 (陸軍将軍 list), which gives
admiral i -> face i and general j -> face 60 + j.

Usage: .venv/bin/python teitoku2/verify_faces.py [--rom ROM]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
sys.path.insert(0, os.path.join(HERE, "tools"))
import rom as R
from replay import replay
from sequences import PERSONNEL, TO_SCENARIOS, end_frame, expand, new_game

TO_LIST = f"{TO_SCENARIOS} {new_game(0)} {PERSONNEL} a:10 w300"
GENERALS = "b:10 w200 down:10 w100 a:10 w400"  # back to the 人事 menu, 陸軍将軍
VRAM_FACE, CGRAM_FACE = 0x800, 0x1E0
FACE_BYTES = R.FACE_W * R.FACE_H * 32
EXTRA = """
local function rd(a) return emu.read(a, emu.memType.snesMemory, false) end
emu.addMemoryCallback(function()
  local f = emu.read(@SLOT@, emu.memType.snesPrgRom, false)
  if f == 0xFF then return end
  local sp = emu.getState()["cpu.sp"]
  emu.write(sp + 8, f, emu.memType.snesMemory)
  emu.write(sp + 9, 0, emu.memType.snesMemory)
end, emu.callbackType.exec, @FACE@)
"""


def main() -> None:
    ap = argparse.ArgumentParser(description="頭像與遊戲比對")
    ap.add_argument("--rom", default=R.DEFAULT_ROM)
    args = ap.parse_args()
    t0 = time.time()
    rom = R.Rom(args.rom)
    slot = rom.data.find(b"\xff" * 64)
    reads = [("vram", VRAM_FACE, FACE_BYTES), ("cgram", CGRAM_FACE, 32)]
    checks = [(1, "admiral 1", "down:10 w120"), (0, "admiral 0", "down:10 w120 up:10 w120"),
              (R.GENERAL_FACE0, "general 0", GENERALS), (R.GENERAL_FACE0 + 1, "general 1", GENERALS + " down:10 w120")]
    runs = [{"steps": st, "shot": end_frame(st, 0) + 30, "read": reads} for _, _, st in checks]
    for f in range(R.FACE_COUNT):
        runs.append({"patch": [(slot, bytes([f]))], "steps": "down:10 w120" if f % 2 == 0 else "up:10 w120",
                     "shot": 150, "read": reads})
    boot = expand(TO_LIST)
    extra = EXTRA.replace("@SLOT@", str(slot)).replace("@FACE@", str(rom.off["code"]["face"]))
    res = replay(args.rom, boot, end_frame(boot), runs, extra_lua=extra)

    def same(f: int, tiles: bytes, cg: bytes) -> bool:
        pal = b"".join(c.to_bytes(2, "little") for c in rom.face_palette(f))
        return tiles == rom.face_tiles(f)[:FACE_BYTES] and cg == pal

    errors = 0
    for k, (want, who, _) in enumerate(checks):
        ok = same(want, *res[k])
        errors += not ok
        shown = next((f for f in range(R.FACE_COUNT) if same(f, *res[k])), None)
        print(f"[{who}] cursor on {who} shows face {want}: " + ("OK" if ok else f"NG (shows {shown})"))
    bad = [f for f, (tiles, cg) in enumerate(res[len(checks):]) if not same(f, tiles, cg)]
    errors += len(bad)
    print(f"[faces] {R.FACE_COUNT - len(bad)}/{R.FACE_COUNT} faces: VRAM tiles = LZ entry 753 + f, CGRAM row 15 = "
          f"palette (second one for {sum(R.face_alt_palette(f) for f in range(R.FACE_COUNT))} faces)"
          + (f" (NG {bad[:12]})" if bad else ""))
    print(f"({time.time() - t0:.0f} s)")
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
