#!/usr/bin/env python3
"""Check rom.Rom.face_tiles / face_palette against the game (needs Mesen 2, about 7 minutes).

At the battle of 桶狭間 the 情報 command opens 木下藤吉郎's info screen (tools/sequences.TO_INFO), whose face the
game builds with $CD:383F from the face code of name table entry 0 (+14). A savestate is taken just before; for
every portrait code 0-257 (LZ entry 81 + code) and every composed code a name uses, those two ROM bytes are
patched and the state replayed. The 640 bytes of OBJ tiles at VRAM 0x2400 and CGRAM 0x120 (OBJ palette 1) must
equal the ROM decoding; the unpatched run must show face 0.

Usage: .venv/bin/python taikou/verify_faces.py [--rom ROM] [--quick]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
sys.path.insert(0, os.path.join(HERE, "tools"))
from replay import replay
from rom import DEFAULT_ROM, FACE_BYTES, FACE_PALETTE, NAMES, PORTRAIT_COUNT, Rom, is_composite
from sequences import TO_INFO, expand
from verify_persons import SAVE_AT, SHOT, STEPS

FACE_VRAM, FACE_CGRAM = 0x2400, 0x120
CODE_AT = NAMES + 14   # face code of name entry 0 (木下藤吉郎)


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證頭像解碼（專屬頭像與組合臉）")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--quick", action="store_true", help="only every 8th portrait and composed code")
    args = ap.parse_args()
    t0 = time.time()
    rom = Rom(args.rom)
    portraits = list(range(PORTRAIT_COUNT))
    composed = sorted({n["face"] for n in rom.names() if is_composite(n["face"])})
    if args.quick:
        portraits, composed = portraits[::8], composed[::8]
    codes = portraits + composed
    read = [("vram", FACE_VRAM, FACE_BYTES), ("cgram", FACE_CGRAM, 32)]
    runs = [{"steps": STEPS, "shot": SHOT, "read": read}]
    runs += [{"patch": [(CODE_AT, c.to_bytes(2, "little"))], "steps": STEPS, "shot": SHOT, "read": read} for c in codes]
    shots = replay(args.rom, expand(TO_INFO), SAVE_AT, runs)
    pal = rom.data[FACE_PALETTE:FACE_PALETTE + 32]
    errors = 0
    tiles, cg = shots[0]
    ok = tiles == rom.face_tiles(0) and cg == pal
    print(f"[unpatched] 木下藤吉郎 (face 0): VRAM tiles and palette {'match' if ok else 'DO NOT match'} the ROM")
    errors += not ok
    got = dict(zip(codes, shots[1:]))
    for label, sel in (("portraits", portraits), ("composed", composed)):
        bad = [c for c in sel if got[c] != [rom.face_tiles(c), pal]]
        errors += len(bad)
        print(f"[{label}] {len(sel) - len(bad)}/{len(sel)} codes: VRAM 0x2400 tiles and CGRAM 0x120 match the ROM"
              + (f" (NG {[hex(c) for c in bad[:20]]})" if bad else ""))
    print(f"time {time.time() - t0:.0f} s")
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
