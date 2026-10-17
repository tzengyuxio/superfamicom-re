#!/usr/bin/env python3
"""Check the opponents' card faces, name graphics and palettes on the 雀荘 screen, in Mesen.

The 雀荘 screen lists the 21 opponents as cards (face 0 above the name graphic). A savestate is taken on it
(tools/sequences.py TO_JANSO) and replayed with 0, 3 and 6 presses of down, which scroll the list. In each run every
5x5 block of consecutive tiles in the BG1 tilemap (except blank ones: empty slots) is a card face: its VRAM tiles must equal rom.face_tiles(i, 0)
of some opponent i, with BG palette 1 + $01:8925[i]; the 6x2 block below it must be rom.name_tiles(i) (top row
then bottom row), palette 3. All 21 opponents must be seen, and their cards must come in person order (the last card is the player's own,
with a montage face that is not decoded).
CGRAM rows 1-3 must be the face palettes ($01:9384, $01:93A4) and the name palette ($01:93C4).

Usage: .venv/bin/python mahjong/verify_janso.py [--rom ROM]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "tools"))
import sequences as sq
from replay import end_frame, replay
from rom import (
    DEFAULT_ROM,
    FACE_BYTES,
    FACE_PAL_SELECT,
    FACE_PALETTES,
    FACE_W,
    NAME_BYTES,
    NAME_PALETTE,
    NAME_W,
    PERSON_COUNT,
    Rom,
)

CHR = 0x8000          # BG1 tiles on this screen
SCROLLS = (0, 3, 6)


def cards(tilemap: bytes, vram: bytes, rom: Rom) -> list[tuple]:
    """[(row, col, person or None, face palette, name ok, name palette)] of the face blocks in the tilemap."""
    def word(r: int, c: int) -> int:
        return tilemap[2 * (r * 32 + c)] | tilemap[2 * (r * 32 + c) + 1] << 8

    def tiles(r: int, c: int, w: int, h: int) -> tuple[bytes, set[int]]:
        ws = [word(r + y, c + x) for y in range(h) for x in range(w)]
        return b"".join(vram[CHR + 32 * (v & 0x3FF):CHR + 32 * (v & 0x3FF) + 32] for v in ws), {v >> 10 & 7 for v in ws}

    faces = {rom.face_tiles(i, 0): i for i in range(PERSON_COUNT)}
    out = []
    for r in range(32 - 7):
        for c in range(1, 32 - FACE_W):
            t0 = word(r, c) & 0x3FF
            if t0 < 0x100 or any(word(r + y, c + x) & 0x3FF != t0 + 5 * y + x for y in range(5) for x in range(5)):
                continue
            data, pal = tiles(r, c, 5, 5)
            person = faces.get(data)
            if person is None and len(set(data)) <= 2:
                continue  # an empty card slot after the last opponent
            name, npal = tiles(r + 5, c - 1, NAME_W, 2)
            out.append((r, c, person, pal, person is not None and name == rom.name_tiles(person), npal))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證雀荘畫面的頭像、名字圖與調色盤（Mesen）")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    t0 = time.time()
    rom = Rom(args.rom)
    reads = [("vram", 0, 0x10000), ("cgram", 32, 96)]
    runs = [{"steps": " ".join(["down:10 w30"] * k), "shot": 40 * k + 60, "read": reads} for k in SCROLLS]
    res = replay(rom.path, sq.TO_JANSO, end_frame(sq.TO_JANSO), runs, timeout=600)
    seen, bad, pal_ok = {}, [], True
    want_pal = rom.data[FACE_PALETTES:FACE_PALETTES + 64] + rom.data[NAME_PALETTE:NAME_PALETTE + 32]
    for k, (vram, cgram) in zip(SCROLLS, res):
        pal_ok &= cgram == want_pal
        found = cards(vram[:0x800], vram, rom)
        order = [p for _, _, p, *_ in found]
        print(f"scroll {k}: cards {order}")
        if k == SCROLLS[-1] and order[-1:] == [None]:
            order = order[:-1]  # the player's own card (a montage face, not decoded) follows 大森大
        if None in order or order != sorted(order):
            bad.append(("order", k, order))
        for r, c, p, pal, name_ok, npal in found:
            if p is None:
                continue
            ok = pal == {1 + rom.data[FACE_PAL_SELECT + p]} and name_ok and npal == {3}
            seen[p] = seen.get(p, True) and ok
            if not ok:
                bad.append((p, r, c, pal, name_ok, npal))
    good = sum(seen.values())
    print(f"[cards] {good}/{PERSON_COUNT}: face 0 ({FACE_BYTES} bytes), name graphic ({NAME_BYTES} bytes) and palettes"
          + (f" NG {bad[:5]}" if bad else ""))
    print(f"[palettes] CGRAM rows 1-3 = $01:9384 / $01:93A4 / $01:93C4: {'OK' if pal_ok else 'NG'}")
    errors = (good != PERSON_COUNT) + len(bad) + (not pal_ok)
    print(("ALL OK" if not errors else f"{errors} problem(s)") + f" ({time.time() - t0:.0f} s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
