#!/usr/bin/env python3
"""Check rom.Rom.face_tiles / face_palette against the game (needs Mesen 2, about 5 minutes).

Scenario 1, 織田信長: after "start" the province screen of 尾張 shows Nobunaga's face, DMA'd at frame ~3876
straight from the ROM to VRAM word 0x6400 (bytes 0xC800, 960 bytes), with BG palette 5 (CGRAM 0xA0).
The face code comes from Nobunaga's name record (s1 name 119, face LE16 at ROM 0x10EDE). A savestate is taken
at frame 3700 and, for every dedicated face 0-179 and every composite code a general uses, the code is
patched in the ROM and the state replayed (tools/replay.py). The VRAM tiles and palette 5 must equal the ROM
decoding; an unpatched run must show face 25 (Nobunaga's own).

Usage: .venv/bin/python bushou/verify_faces.py [--rom ROM] [--quick]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "tools"))
from export_kaodata import distinct_characters
from replay import replay
from rom import DEFAULT_ROM, FACE_BYTES, FACE_PALETTE, PORTRAIT_COUNT, Rom, is_composite

STEPS = ("w900 start:10 w300 a:10 w200 a:10 w200 a:10 w200 a:10 w200 up:10 w60 a:10 w200 a:10 w200 a:10 w200 "
         "a:10 w300 a:10 w900")  # title -> scenario 1 -> 1 player -> 織田信長 -> start: province screen
SAVE_AT, SHOT_AFTER = 3700, 250
FACE_VRAM, FACE_CGRAM = 0xC800, 0xA0
NOBUNAGA_FACE_AT, NOBUNAGA_FACE = 0x10EDE, 25


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證頭像解碼（專屬頭像與組合臉）")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--quick", action="store_true", help="only every 8th face")
    args = ap.parse_args()
    t0 = time.time()
    rom = Rom(args.rom)
    assert rom.u16(NOBUNAGA_FACE_AT) == NOBUNAGA_FACE
    composite = sorted({c["face_code"] for c in distinct_characters(rom) if is_composite(c["face_code"])})
    portraits = list(range(PORTRAIT_COUNT))
    if args.quick:
        portraits, composite = portraits[::8], composite[::8]
    read = [("vram", FACE_VRAM, FACE_BYTES), ("cgram", FACE_CGRAM, 32)]
    runs = [{"shot": SHOT_AFTER, "read": read}]
    runs += [{"patch": [(NOBUNAGA_FACE_AT, c.to_bytes(2, "little"))], "shot": SHOT_AFTER, "read": read}
             for c in portraits + composite]
    res = replay(args.rom, STEPS, SAVE_AT, runs)
    pal = rom.data[FACE_PALETTE:FACE_PALETTE + 32]
    errors = 0
    natural = res[0] == [rom.face_tiles(NOBUNAGA_FACE), pal]
    print(f"[natural] 織田信長 shows face {NOBUNAGA_FACE}: {'OK' if natural else 'NG'}")
    errors += not natural
    shown = dict(zip(portraits + composite, res[1:]))
    for label, codes in (("portraits", portraits), ("composite", composite)):
        bad = [c for c in codes if shown[c] != [rom.face_tiles(c), pal]]
        errors += len(bad)
        print(f"[{label}] {len(codes) - len(bad)}/{len(codes)}: VRAM tiles and CGRAM palette 5 match the ROM"
              + (f" (NG {[hex(c) for c in bad[:20]]})" if bad else ""))
    print(f"{time.time() - t0:.0f} s")
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
