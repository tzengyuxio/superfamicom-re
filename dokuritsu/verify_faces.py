#!/usr/bin/env python3
"""Check every face code (rom.Rom.face_tiles) against the game (needs Mesen 2, about 5 minutes).

Same screen as verify_persons.py (side selection, ジョージ・ワシントン); the face code of his master record
(+31, LE16) is patched in ROM to each code and the state replayed; the game draws it with $C2:3FA8 to VRAM 0x9860
(30 tiles in a row), which must equal face_tiles(code), and CGRAM palette 2 must be the face palette.
Codes: the 174 portraits 0-173 (persons use 0-124), the 125 composed codes the persons use, and for each of the
4 types the 4 codes whose part digits are all v (v = 0-3), so every part variant is drawn at least once.

Usage: .venv/bin/python dokuritsu/verify_faces.py [--rom ROM] [--quick]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
from replay import replay
from rom import DEFAULT_ROM, FACE_BYTES, FACE_PALETTE, PERSON_SIZE, PERSONS, PORTRAIT_COUNT, TYPE_COUNT, Rom
from verify_persons import BOOT, FACE_VRAM, SAVE_AT, SHOT

WASHINGTON = 238


def codes(rom: Rom) -> tuple[list[int], list[int]]:
    used = sorted({p["face"] for p in rom.persons() if p["face"] & 0x8000})
    extra = [0x8000 | t << 10 | sum(v << 2 * k for k in range(5)) for t in range(TYPE_COUNT) for v in range(4)]
    return used, [c for c in extra if c not in used]


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證全部頭像碼")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--quick", action="store_true", help="only every 8th code")
    args = ap.parse_args()
    t0 = time.time()
    rom = Rom(args.rom)
    used, extra = codes(rom)
    groups = {"portrait": list(range(PORTRAIT_COUNT)), "composed (persons)": used, "composed (all digits v)": extra}
    if args.quick:
        groups = {k: v[::8] for k, v in groups.items()}
    allc = [c for v in groups.values() for c in v]
    site = PERSONS + PERSON_SIZE * WASHINGTON + 31
    read = [("vram", FACE_VRAM, FACE_BYTES), ("cgram", 0x40, 32)]
    runs = [{"patch": [(site, c.to_bytes(2, "little"))], "shot": SHOT, "read": read} for c in allc]
    shots = dict(zip(allc, replay(args.rom, BOOT, SAVE_AT, runs)))
    pal = rom.data[FACE_PALETTE:FACE_PALETTE + 32]
    errors = 0
    for name, cs in groups.items():
        bad = [f"{c:04X}" for c in cs if shots[c][0] != rom.face_tiles(c)]
        badp = [f"{c:04X}" for c in cs if shots[c][1] != pal]
        print(f"[{name}] {len(cs) - len(bad)}/{len(cs)} faces equal face_tiles, palette 2 = 0x{FACE_PALETTE:X} "
              f"{len(cs) - len(badp)}/{len(cs)}" + (f" NG {bad[:10]} {badp[:10]}" if bad or badp else ""))
        errors += len(bad) + len(badp)
    print(f"time {time.time() - t0:.0f} s")
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
