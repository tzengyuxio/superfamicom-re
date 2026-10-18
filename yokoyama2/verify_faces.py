#!/usr/bin/env python3
"""Check the face decoding (rom.Rom.face_parts / face_buffer / metasprite / face_palette) against the game.

The officer detail screen shows the face as 32 16x16 sprites in the box at (104, 22) (OBJ tiles at VRAM 0xC000,
OBJ palette 0). With the runs of verify_persons.py (scenario 189: each person moved into 并州, detail screen
opened) OAM, VRAM 0xC000-0xCFFF and CGRAM 0x100-0x11F are read; the sprites are drawn from them (lower OAM index in
front) and the 48 x 64 box must equal rom.Rom.face_rgb(p, frame) pixel for pixel (transparent = no sprite pixel)
for one of the face metasprites 0-3 (the eyes and the mouth move; 5 persons have their own set, rom.FACE_META_BASE),
for all 229 persons.

Usage: .venv/bin/python yokoyama2/verify_faces.py [--rom ROM] [--persons 0-228]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
sys.path.insert(0, os.path.join(HERE, "tools"))
import sequences as q
from rom import DEFAULT_ROM, FACE_BUFFER, FACE_H, FACE_W, PERSON_COUNT, Rom, decode_tile4, palette
from verify_persons import detail_runs

FRAMES = range(4)


def draw(oam: bytes, vram: bytes, cgram: bytes) -> list:
    """The face box as the PPU would show the sprites (16x16, OBJ palette 0)."""
    pal = palette(cgram)
    box = [None] * (FACE_W * FACE_H)
    for i in reversed(range(128)):
        x, y, t, a = oam[4 * i:4 * i + 4]
        x |= (oam[512 + i // 4] >> (2 * (i % 4)) & 1) << 8
        if y >= 224:
            continue
        hflip, vflip = a >> 6 & 1, a >> 7 & 1
        for ty in range(2):
            for tx in range(2):
                n = (t & 0xF0) + 16 * ty + ((t + tx) & 15)
                px = decode_tile4(vram[32 * n:32 * n + 32])
                for yy in range(8):
                    for xx in range(8):
                        c = px[8 * yy + xx]
                        if not c:
                            continue
                        sx = (1 - tx) * 8 + 7 - xx if hflip else 8 * tx + xx
                        sy = (1 - ty) * 8 + 7 - yy if vflip else 8 * ty + yy
                        bx, by = x + sx - q.FACE_X, y + sy - q.FACE_Y
                        if 0 <= bx < FACE_W and 0 <= by < FACE_H:
                            box[by * FACE_W + bx] = pal[c]
    return box


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證頭像解碼（武将詳細畫面的 sprite）")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--persons", default=f"0-{PERSON_COUNT - 1}", help="人物編號範圍，如 0-228")
    args = ap.parse_args()
    t0 = time.time()
    rom = Rom(args.rom)
    lo, _, hi = args.persons.partition("-")
    persons = list(range(int(lo), int(hi or lo) + 1))
    read = [("oam", 0, 544), ("vram", q.FACE_OBJ_VRAM, FACE_BUFFER), ("cgram", 0x100, 32)]
    results = detail_runs(rom, 0, persons, read)
    bad = 0
    seen = {f: 0 for f in FRAMES}
    for p, res in zip(persons, results):
        got = draw(*res[:3])
        diffs = {f: sum(g != w for g, w in zip(got, rom.face_rgb(p, f))) for f in FRAMES}
        frame = min(diffs, key=diffs.get)
        if diffs[frame]:
            bad += 1
            print(f"  NG #{p} {rom.name(p)}: {diffs[frame]} pixels differ (closest metasprite {frame})")
        else:
            seen[frame] += 1
    print(f"faces equal {len(persons) - bad}/{len(persons)} (metasprite of the shot: "
          + ", ".join(f"{f}: {n}" for f, n in seen.items()) + ")")
    print(f"{time.time() - t0:.0f} s")
    print("ALL OK" if not bad else f"{bad} mismatch(es)")
    raise SystemExit(1 if bad else 0)


if __name__ == "__main__":
    main()
