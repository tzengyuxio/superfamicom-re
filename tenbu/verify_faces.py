#!/usr/bin/env python3
"""Check the 250 portraits (rom.Rom.face_rgb) against the ruler card.

Same runs as verify_persons.py (scenario 190, the ruler list savestate): each run copies the faction-0 ruler's
record with +31 (face number) = n, clicks the ruler and reads OAM, VRAM 0x4000-0x7FFF (OBJ tiles: table 0 at byte
0x4000, table 1 at 0x6000) and CGRAM. The card's face is OBJ 56-61 (16 x 16) at (72, 24): a 32 x 48 box whose top 8
rows are blank and whose rows 8-47 must equal face n pixel for pixel (colours from the OBJ palette of each sprite,
colour 0 transparent).

Usage: .venv/bin/python tenbu/verify_faces.py [--rom ROM]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from rom import DEFAULT_ROM, FACE_COUNT, FACE_H, FACE_W, Rom, bgr555_rgb, decode_tile4, le16
from verify_persons import card_runs

OBJ_VRAM = 0x4000
BOX_X, BOX_Y, TOP = 72, 24, 8


def render(oam: bytes, vram: bytes, cgram: bytes) -> dict:
    """{(x, y): rgb} of OBJ 56-61 inside the face box (opaque pixels only)."""
    px = {}
    for i in range(56, 62):
        x, y, t, a = oam[4 * i:4 * i + 4]
        t |= (a & 1) << 8
        pal = 128 + 16 * (a >> 1 & 7)
        for k, (dx, dy) in enumerate(((0, 0), (8, 0), (0, 8), (8, 8))):
            tt = (t & 0x100) | ((t + (k & 1) + 16 * (k >> 1)) & 0xFF)
            base = OBJ_VRAM + 32 * (tt & 0xFF) + (0x2000 if tt & 0x100 else 0)
            tile = decode_tile4(vram[base - OBJ_VRAM:base - OBJ_VRAM + 32])
            for j, v in enumerate(tile):
                if v:
                    px[(x + dx + j % 8 - BOX_X, y + dy + j // 8 - BOX_Y)] = bgr555_rgb(le16(cgram, 2 * (pal + v)))
    return px


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證頭像（君主卡的 OAM／VRAM／CGRAM）")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    t0 = time.time()
    rom = Rom(args.rom)
    base = bytearray(rom.person_raw(0, rom.faction(0, 0)["君主"]))
    records = []
    for n in range(FACE_COUNT):
        base[31:33] = n.to_bytes(2, "little")
        records.append(bytes(base))
    results = card_runs(rom, 0, records, [("oam", 0, 544), ("vram", OBJ_VRAM, 0x4000), ("cgram", 0, 512)])
    bad = 0
    for n, (oam, vram, cgram, _) in enumerate(results):
        got = render(oam, vram, cgram)
        want = {}
        for i, c in enumerate(rom.face_rgb(n)):
            if c:
                want[(i % FACE_W, TOP + i // FACE_W)] = c
        if got != want:
            bad += 1
            diff = sum(got.get(k) != want.get(k) for k in set(got) | set(want))
            print(f"  NG face {n}: {diff} pixels differ")
    print(f"faces equal {FACE_COUNT - bad}/{FACE_COUNT} ({FACE_W} x {FACE_H} each)")
    print(f"{time.time() - t0:.0f} s")
    print("ALL OK" if not bad else f"{bad} mismatch(es)")
    raise SystemExit(1 if bad else 0)


if __name__ == "__main__":
    main()
