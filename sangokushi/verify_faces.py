#!/usr/bin/env python3
"""Check the face decoding (rom.Rom.face_bytes: portraits, male and female composites) against the game.

Scenario 1 is played to the 武将 list of 曹操's country; a savestate is taken there. Each run opens 曹操's info
screen with the face code replaced: a Lua hook at the face loader $C1:143F(code) overwrites its stack argument with
the code under test (handed over in WRAM $7F:FFF0). The game then builds the face itself (portrait LZ entry, or
the composite parts at their places) and puts its 30 tiles in VRAM at 0xEC80 (sprite tiles 0x164-0x181). For
every code 0x00-0x132 the 960 VRAM bytes must equal face_bytes(code), OAM must hold 30 8x8 sprites with those tiles
in a 5 x 6 grid (row-major) with OBJ palette 1, and CGRAM OBJ palette 1 must be FACE_PALETTE.

Usage: .venv/bin/python sangokushi/verify_faces.py [--rom ROM]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
sys.path.insert(0, os.path.join(HERE, "tools"))
import replay
import sequences
from rom import (
    DEFAULT_ROM,
    FACE_BYTES,
    FACE_CGRAM,
    FACE_H,
    FACE_OAM_TILE,
    FACE_PALETTE,
    FACE_W,
    LAST_FACE,
    Rom,
    face_kind,
)

FACE_VRAM = 0xEC80
CODE_WRAM = 0x1FFF0                      # $7F:FFF0 code (LE16), $7F:FFF2 = 1: replace

LUA = r"""
emu.addMemoryCallback(function()
  if emu.read(0x1FFF2, emu.memType.snesWorkRam) ~= 1 then return end
  local sp = emu.getState()["cpu.sp"]
  emu.write(sp + 4, emu.read(0x1FFF0, emu.memType.snesWorkRam), emu.memType.snesMemory)
  emu.write(sp + 5, emu.read(0x1FFF1, emu.memType.snesWorkRam), emu.memType.snesMemory)
end, emu.callbackType.exec, 0xC1143F)
"""


def sprites_ok(oam: bytes) -> bool:
    """The face sprites: tile FACE_OAM_TILE + i at (x0 + 8 (i % 5), y0 + 8 (i // 5)), OBJ palette 1."""
    spr = {}
    for k in range(128):
        x, y, t, a = oam[4 * k:4 * k + 4]
        tile = t | (a & 1) << 8
        if FACE_OAM_TILE <= tile < FACE_OAM_TILE + FACE_W * FACE_H and y < 224:
            spr[tile - FACE_OAM_TILE] = (x, y, a >> 1 & 7)
    if len(spr) != FACE_W * FACE_H:
        return False
    x0, y0, _ = spr[0]
    return all(spr[i] == (x0 + 8 * (i % FACE_W), y0 + 8 * (i // FACE_W), 1) for i in range(FACE_W * FACE_H))


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證頭像（肖像、男性與女性組合臉）")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    t0 = time.time()
    rom = Rom(args.rom)
    boot = sequences.TO_MAIN + " " + sequences.INFO_PERSONS
    steps = "a:10 w200"
    codes = list(range(LAST_FACE + 1))
    runs = [{"wram": [(CODE_WRAM, bytes([c & 0xFF, c >> 8, 1]))], "steps": steps,
             "shot": sequences.end_frame(steps, 0) + 10,
             "read": [("vram", FACE_VRAM, FACE_BYTES), ("cgram", FACE_CGRAM, 32), ("oam", 0, 544)]} for c in codes]
    results = replay.replay(args.rom, sequences.expand(boot), sequences.end_frame(boot), runs, extra_lua=LUA)
    pal = b"".join(c.to_bytes(2, "little") for c in rom.palette(FACE_PALETTE))
    bad: dict[str, list[int]] = {}
    total: dict[str, int] = {}
    pal_bad = oam_bad = 0
    for c, (vram, cgram, oam) in zip(codes, results):
        oam_bad += not sprites_ok(oam)
        kind = face_kind(c)
        total[kind] = total.get(kind, 0) + 1
        if vram != rom.face_bytes(c):
            bad.setdefault(kind, []).append(c)
        pal_bad += cgram != pal
    for kind in ("portrait", "male", "female"):
        ng = bad.get(kind, [])
        print(f"[{kind}] {total[kind] - len(ng)}/{total[kind]} faces equal the game's VRAM"
              + (f" (NG {[hex(c) for c in ng[:10]]})" if ng else ""))
    print(f"[sprites] 30 sprites, tiles 0x{FACE_OAM_TILE:X}+, 5 x 6 grid, OBJ palette 1 in {len(codes) - oam_bad}/{len(codes)} runs")
    print(f"[palette] CGRAM OBJ palette 1 = ROM 0x{FACE_PALETTE:X} in {len(codes) - pal_bad}/{len(codes)} runs")
    print(f"{time.time() - t0:.0f} s")
    errors = sum(len(v) for v in bad.values()) + pal_bad + oam_bad
    print("ALL OK" if not errors else f"{errors} mismatch(es)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
