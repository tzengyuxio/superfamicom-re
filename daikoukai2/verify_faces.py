#!/usr/bin/env python3
"""Check rom.Rom.face_tiles / face_palette against the game (needs Mesen 2, about 4 minutes).

Plays as ジョアン up to free walking in Lisbon (tools/replay.py), takes a savestate, then for every portrait 0-127,
every composed face code used by a person and one extra composed code per pack value 0-7 (pack 7 is drawn as 6)
writes the code into ジョアン's face field ($7E:2616 = person 0 +26) and opens 艦隊情報 > 人物情報. The face is drawn
as OBJ: the 960 bytes of tiles at VRAM 0x3800 and CGRAM palette 10 (OBJ palette 2) must equal the ROM decoding
(portraits: $C1:42BB; composed faces: $C1:3B22).

Usage: .venv/bin/python daikoukai2/verify_faces.py [--rom ROM] [--quick]
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "tools"))
sys.path.insert(0, HERE)
import replay
from rom import DEFAULT_ROM, FACE_BYTES, PERSONS, PORTRAIT_COUNT, Rom, wram

OPEN_INFO = "w5 x:10 w40 right+a:10 w80 a:10 w100"
FACE_VRAM, FACE_CGRAM = 0x3800, 2 * 160
FACE_FIELD = 0x7E0000 | wram(PERSONS) + 26


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證頭像解碼（專屬頭像與組合臉）")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--quick", action="store_true", help="only every 8th portrait and composed code")
    args = ap.parse_args()
    rom = Rom(args.rom)
    composed = sorted({p["face"] for p in rom.persons() if p["face"] & 0x8000})
    composed += [0x8000 | t << 12 | (t + 3) % 8 << 9 | (t + 5) % 8 << 6 | (7 - t) << 3 | t for t in range(8)]
    portraits = list(range(PORTRAIT_COUNT))
    if args.quick:
        portraits, composed = portraits[::8], composed[::8]
    codes = portraits + composed
    rounds = [([(FACE_FIELD, bytes([c & 0xFF, c >> 8]))], OPEN_INFO) for c in codes]
    shown = {c: (m["vram"][FACE_VRAM:FACE_VRAM + FACE_BYTES], m["cgram"][FACE_CGRAM:FACE_CGRAM + 32])
             for c, m in zip(codes, replay.run(args.rom, replay.BOOT_TOWN, rounds))}
    errors = 0
    for label, group in (("portraits", portraits), ("composed", composed)):
        bad = [hex(c) if c & 0x8000 else c for c in group if shown[c] != (rom.face_tiles(c), rom.face_palette(c))]
        errors += len(bad)
        print(f"[{label}] {len(group) - len(bad)}/{len(group)}: VRAM tiles and CGRAM palette 10 match the ROM"
              + (f" (NG {bad[:20]})" if bad else ""))
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
