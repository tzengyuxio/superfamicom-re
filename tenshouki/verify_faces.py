#!/usr/bin/env python3
"""Check rom.Rom.face_tiles / face_palette_number against the game (needs Mesen 2, about 10 minutes).

Every face code of the 700 persons and every portrait code 0-311 is patched in as 蠣崎季広's face and
his general's screen opened (tools/face_capture.py); the 960 bytes of face tiles in VRAM and CGRAM
palette 9 must equal the ROM decoding.

Usage: .venv/bin/python tenshouki/verify_faces.py [--rom ROM]
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "tools"))
from face_capture import capture_faces
from rom import DEFAULT_ROM, FACE_PALETTES, PORTRAIT_COUNT, Rom


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證頭像解碼")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    codes = sorted({p["face"] for p in rom.persons()} | set(range(PORTRAIT_COUNT)))
    shown = capture_faces(args.rom, codes)
    bad = []
    for code in codes:
        n = rom.face_palette_number(code)
        tiles, pal = shown.get(code, (b"", b""))
        if tiles != rom.face_tiles(code) or pal != rom.data[FACE_PALETTES + 32 * n:FACE_PALETTES + 32 * n + 32]:
            bad.append(f"{code:04X}")
    print(f"[faces] {len(codes) - len(bad)}/{len(codes)} codes: VRAM tiles and palette match the ROM"
          + (f" (NG {' '.join(bad)})" if bad else ""))
    print("ALL OK" if not bad else f"{len(bad)} problem(s)")
    raise SystemExit(1 if bad else 0)


if __name__ == "__main__":
    main()
