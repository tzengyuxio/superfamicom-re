#!/usr/bin/env python3
"""Check rom.Rom.face (portraits and composite faces) and FACE_PALETTE against the game (Mesen 2, ~2 min).

In the prologue the game shows レオン's face: the p-code at $7E:4EFA reads the face code from $7E:F295 and calls
$7E:83DE (portrait, code < 0x1000) or $7E:858D (composite face), which put the 960 bytes of tiles at VRAM
0x2B20 and the palette in CGRAM BG palette 5. A savestate is taken just before; for every code the state is
replayed and, when the interpreter reaches VM pc $7E:4FA7, the code is written to $F295 / $0865, so the game's
own routines build the face. Codes: the 53 portraits, every admiral's composite code, and codes that use
every page of every slot of the 4 heads. The unpatched run must show portrait 0 (レオン, person 0's code).

Usage: .venv/bin/python daikoukai/verify_faces.py [--rom ROM]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "tools"))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
from boot import FACE_SAVE, FACE_SHOT, FACE_STEPS, PROLOGUE
from replay import replay
from rom import COMPOSITE_SLOTS, DEFAULT_ROM, FACE_BYTES, FACE_PALETTE, PORTRAIT_COUNT, Rom

FACE_VRAM = 0x2B20
FACE_CGRAM = 32 * 5
CODE_SLOT = 0x1FFF0             # WRAM scratch the hook reads: code lo, code hi, 0x5A = armed
HOOK = """
local function rd(a) return emu.read(a, emu.memType.snesMemory) end
emu.addMemoryCallback(function()
  if (rd(6) | rd(7) << 8) ~= 0x4FA7 or rd(8) ~= 0x7E then return end
  if emu.read(0x1FFF2, emu.memType.snesWorkRam) ~= 0x5A then return end
  local lo = emu.read(0x1FFF0, emu.memType.snesWorkRam)
  local hi = emu.read(0x1FFF1, emu.memType.snesWorkRam)
  emu.write(0x7EF295, lo, emu.memType.snesMemory); emu.write(0x7EF296, hi, emu.memType.snesMemory)
  emu.write(0x7E0865, lo, emu.memType.snesMemory); emu.write(0x7E0866, hi, emu.memType.snesMemory)
end, emu.callbackType.exec, 0x00A141)
"""


def main() -> None:
    ap = argparse.ArgumentParser(description="以模擬器驗證頭像（專屬＋組合）")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    t0 = time.time()
    rom = Rom(args.rom)
    admirals = sorted({p["face"] for p in rom.persons() if p["face"] >= 0x1000})
    # one slot at page p, the others at page 0: every (head, slot, page) once
    cover = sorted({0x1000 | head << 10 | p << shift for head in range(4) for _, _, shift in COMPOSITE_SLOTS
                    for p in range(4)})
    codes = [None] + list(range(PORTRAIT_COUNT)) + admirals + [c for c in cover if c not in admirals]
    reads = [("vram", FACE_VRAM, FACE_BYTES), ("cgram", FACE_CGRAM, 32)]
    runs = [{"wram": [] if c is None else [(CODE_SLOT, bytes([c & 0xFF, c >> 8, 0x5A]))],
             "steps": FACE_STEPS, "shot": FACE_SHOT, "read": reads} for c in codes]
    res = replay(args.rom, PROLOGUE, FACE_SAVE, runs, extra_lua=HOOK)
    pal = rom.data[FACE_PALETTE:FACE_PALETTE + 32]
    bad = []
    for code, (tiles, cg) in zip(codes, res):
        want = rom.face(0 if code is None else code)
        if tiles != want or cg != pal:
            bad.append("unpatched" if code is None else f"{code:04X}")
    n_pt = PORTRAIT_COUNT
    n_comp = len(codes) - 1 - n_pt
    print(f"[faces] unpatched run = portrait 0 (レオン): {'OK' if 'unpatched' not in bad else 'NG'}")
    print(f"[faces] portraits {n_pt - sum(1 for b in bad if b != 'unpatched' and int(b, 16) < 0x1000)}/{n_pt}, "
          f"composite codes {n_comp - sum(1 for b in bad if b != 'unpatched' and int(b, 16) >= 0x1000)}/{n_comp} "
          f"({len(admirals)} admirals + {n_comp - len(admirals)} page-coverage codes): VRAM 0x{FACE_VRAM:04X} "
          f"{FACE_BYTES} B and CGRAM palette 5 equal the ROM decoding" + (f" (NG {bad[:10]})" if bad else ""))
    print(f"{len(codes)} runs, {time.time() - t0:.0f} s")
    print("ALL OK" if not bad else f"{len(bad)} problem(s)")
    raise SystemExit(1 if bad else 0)


if __name__ == "__main__":
    main()
