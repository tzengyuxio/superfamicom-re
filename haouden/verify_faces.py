#!/usr/bin/env python3
"""Check rom.Rom.face_tiles / face_palette against the game (needs Mesen 2, about 5 minutes).

Scenario 1 is started as 龍造寺隆信 in Mesen (tools/mesen.py, savestate replay tools/replay.py). When the
first turn's main screen appears, the castle panel calls the face routine $C1:187F with the person id it reads
at $C1:8185 (LDY #$1F; LDA ($10),y = person +31). A savestate is taken just before; for every face id (0-928 except 920, 921) the
two instructions are patched to LDA #id and the state replayed, so the game's own routine builds the face
(portrait from an LZ entry or composed from parts). The 960 bytes of OBJ tiles at VRAM 0x2400 and CGRAM
palette 15 must equal the ROM decoding; the unpatched run must show 龍造寺隆信's face (id 48).

Usage: .venv/bin/python haouden/verify_faces.py [--rom ROM] [--quick]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
from replay import replay
from rom import DEFAULT_ROM, FACE_BYTES, Rom

BOOT = ("w1500 start:10 w200 a:10 w200 a:10 w60 a:10 w60 a:10 w60 a:10 w60 a:10 w60 a:10 w400 a:10 w200 a:10 w900"
        " a:10 w300 right:10 w30 a:10 w1500 a:10 w1200")
SAVE_AT = 6900      # the panel's face call comes about 100 frames later
SHOT = 250
CALL_SITE = bytes.fromhex("a01f00b11048f40000a307")  # LDY #$1F / LDA ($10),y / PHA / PEA $0000 / LDA $07,s
FACE_VRAM = 0x2400
FACE_CGRAM = 0x1E0
NATURAL = 48        # 龍造寺隆信


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證頭像解碼（專屬頭像與組合臉）")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--quick", action="store_true", help="only every 8th face id")
    args = ap.parse_args()
    t0 = time.time()
    rom = Rom(args.rom)
    site = rom.data.find(CALL_SITE)
    assert site > 0 and rom.data.find(CALL_SITE, site + 1) < 0
    ids = rom.face_ids()[::8 if args.quick else 1]
    read = [("vram", FACE_VRAM, FACE_BYTES), ("cgram", FACE_CGRAM, 32)]
    runs = [{"shot": SHOT, "read": read}]
    runs += [{"patch": [(site, bytes([0xA9, i & 0xFF, i >> 8, 0xEA, 0xEA]))], "shot": SHOT, "read": read} for i in ids]
    shots = replay(args.rom, BOOT, SAVE_AT, runs)
    pal = b"".join(c.to_bytes(2, "little") for c in rom.face_palette())
    errors = 0
    nat_tiles, nat_pal = shots[0]
    ok = nat_tiles == rom.face_tiles(NATURAL) and nat_pal == pal
    print(f"[unpatched] 龍造寺隆信 (id {NATURAL}): VRAM tiles and palette {'match' if ok else 'DO NOT match'} the ROM")
    errors += not ok
    for label, pick in (("portraits", "entry"), ("composed", "comp")):
        sel = [(i, s) for i, s in zip(ids, shots[1:]) if rom.face_source(i)[0] == pick]
        bad = [i for i, (tiles, p) in sel if tiles != rom.face_tiles(i) or p != pal]
        errors += len(bad)
        print(f"[{label}] {len(sel) - len(bad)}/{len(sel)} face ids: VRAM 0x2400 tiles and CGRAM palette 15 match"
              + (f" (NG {bad[:20]}{' ...' if len(bad) > 20 else ''})" if bad else ""))
    print(f"time {time.time() - t0:.0f} s")
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
