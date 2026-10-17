#!/usr/bin/env python3
"""Check the faces (portraits 0x00-0xCF and composed faces) in Mesen.

From the savestate on the trainer list (tools/wp.TRAINER_LIST), the next press shows the secretary's message with
her face (code 0xCF, drawn by $CA:2DA7). For every run the face code on the stack (S+$44 at $CA:2DAD) is replaced
by the code under test; the 960 tile bytes the game puts at VRAM $85C0 and the 32 bytes of CGRAM palette 2 must
equal rom.face_bytes / the palette rom.face_palette_number picks:
1. all 208 portraits (LZ entries 287-494; palette by code range, $CA:2DA7);
2. composed faces ($CA:223A): every type 0-7 with all four parts = v for v = 0-3, every owner's face code of the
   ROM, and codes with the unused bits 6-7 / 10-11 set.
Run 0 leaves the game alone (the secretary, 0xCF).

Usage: .venv/bin/python winning/verify_faces.py [--rom ROM]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "tools"))
import wp
from replay import end_frame, replay
from rom import DEFAULT_ROM, FACE_BYTES, PORTRAIT_COUNT, SECRETARY_FACE, Rom

VRAM_FACE = 0x85C0              # byte address of the 30 tiles of face slot 0
CGRAM_FACE = 0x40               # palette 2
OVERRIDE_LUA = """
emu.addMemoryCallback(function()
  if PARAM(2) == 0 then return end
  local sp = emu.getState()["cpu.sp"]
  emu.write(sp + 0x44, PARAM(0), emu.memType.snesMemory)
  emu.write(sp + 0x45, PARAM(1), emu.memType.snesMemory)
end, emu.callbackType.exec, 0xCA2DAD)
"""


def composite_codes(rom: Rom) -> list[int]:
    out = [0x8000 | t << 12 | v | v << 2 | v << 4 | v << 8 for t in range(8) for v in range(4)]
    out += [0x8000 | t << 12 | 0xCC0 | (t * 0x47) & 0x33F for t in range(8)]     # unused bits 6-7, 10-11 set
    for o in rom.owners():
        if o["face"] >= PORTRAIT_COUNT and o["face"] not in out:
            out.append(o["face"])
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證頭像與組合臉")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    t0 = time.time()
    portraits = list(range(PORTRAIT_COUNT))
    composed = composite_codes(rom)
    reads = [("vram", VRAM_FACE, FACE_BYTES), ("cgram", CGRAM_FACE, 32)]
    runs = [{"steps": "a:10 w200", "shot": 150, "read": reads}]
    for c in portraits + composed:
        runs.append({"steps": "a:10 w200", "shot": 150, "read": reads,
                     "wram": [(wp.WRAM_PARAM, bytes([c & 255, c >> 8, 1]))]})
    res = replay(rom.path, wp.TRAINER_LIST, end_frame(wp.TRAINER_LIST), runs,
                 extra_lua=wp.COLLECT_LUA + OVERRIDE_LUA)

    def check(code: int, got: list[bytes]) -> tuple[bool, bool]:
        p = rom.palette_offset(rom.face_palette_number(code))
        return got[0] == rom.face_bytes(code), got[1] == rom.data[p:p + 32]

    errors = 0
    tiles, pal = check(SECRETARY_FACE, res[0])
    print(f"[game] secretary 0x{SECRETARY_FACE:02X}: tiles {'OK' if tiles else 'NG'}, palette {'OK' if pal else 'NG'}")
    errors += (not tiles) + (not pal)
    for label, codes, rs in (("portraits", portraits, res[1:1 + len(portraits)]),
                             ("composed", composed, res[1 + len(portraits):])):
        bad_t = [f"{c:04X}" for c, r in zip(codes, rs) if not check(c, r)[0]]
        bad_p = [f"{c:04X}" for c, r in zip(codes, rs) if not check(c, r)[1]]
        print(f"[{label}] tiles {len(codes) - len(bad_t)}/{len(codes)}, palette {len(codes) - len(bad_p)}/{len(codes)}"
              + (f" (NG tiles {bad_t[:8]})" if bad_t else "") + (f" (NG palette {bad_p[:8]})" if bad_p else ""))
        errors += len(bad_t) + len(bad_p)
    print(f"time {time.time() - t0:.0f}s")
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
