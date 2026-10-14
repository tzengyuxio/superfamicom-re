#!/usr/bin/env python3
"""Check the faces (rom.Rom.face_pixels / face_palette) against the game (needs Mesen 2, about 3 minutes).

Scenario 3 as 日本軍, 資料 -> 人材 shows the admiral list with the face of the admiral under the cursor, drawn by
$0A:B2A9(side, index). Each run patches the start of that routine ($0A:B2B0) to use a fixed (side, index), moves
the cursor (the game redraws the face), and reads the face tiles from VRAM $7A00 (960 bytes = 30 4bpp tiles)
and the face palette from CGRAM row 5. Face n < 27 is (0, n), face n >= 27 is (1, n - 7); both must equal the
LZ entry n and the 32 bytes of Rom.face_palette(n). The admirals' faces (admiral i = (i // 20, i)) are the same
calls, which gives Rom.admiral_face.

Usage: .venv/bin/python teitoku/verify_faces.py [--rom ROM]
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
from sequences import DATA_MENU, TO_SCENARIOS, end_frame, new_game

TO_PERSONS = f"{TO_SCENARIOS} {new_game(3, 0)} {DATA_MENU} down:10 w30 a:10 w300"
PATCH_AT = R.lorom(0x0AB2B0)
VRAM_FACE, CGRAM_FACE = 0x7A00, 0xA0


def patch(side: int, idx: int) -> bytes:
    # LDA #side; STA $0C,S; LDA #idx; STA $0E,S; BRA $B2EE (the side test)
    return bytes([0xA9, side, 0, 0x83, 0x0C, 0xA9, idx, 0, 0x83, 0x0E, 0x80, 0x32])


def main() -> None:
    ap = argparse.ArgumentParser(description="頭像與遊戲比對")
    ap.add_argument("--rom", default=R.DEFAULT_ROM)
    args = ap.parse_args()
    t0 = time.time()
    rom = R.Rom(args.rom)
    assert rom.data[PATCH_AT:PATCH_AT + 5] == bytes([0xA9, 0x64, 0, 0x85, 0x04])
    calls = [(0, n) if n < 27 else (1, n - 7) for n in range(R.FACE_COUNT)]
    runs = [{"patch": [(PATCH_AT, patch(s, i))], "steps": "down:10 w100" if k % 2 == 0 else "up:10 w100",
             "shot": 130, "read": [("vram", VRAM_FACE, 960), ("cgram", CGRAM_FACE, 32)]}
            for k, (s, i) in enumerate(calls)]
    res = replay(args.rom, TO_PERSONS, end_frame(TO_PERSONS), runs)
    bad = []
    for n, (tiles, cg) in enumerate(res):
        pal = b"".join(c.to_bytes(2, "little") for c in rom.face_palette(n))
        if tiles != rom.entry(n) or cg != pal:
            bad.append(n)
    print(f"[faces] {R.FACE_COUNT - len(bad)}/{R.FACE_COUNT} faces: VRAM tiles = LZ entry, CGRAM row 5 = palette"
          + (f" (NG {bad})" if bad else ""))
    print(f"({time.time() - t0:.0f} s)")
    print("ALL OK" if not bad else f"{len(bad)} problem(s)")
    raise SystemExit(1 if bad else 0)


if __name__ == "__main__":
    main()
