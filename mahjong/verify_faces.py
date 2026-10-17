#!/usr/bin/env python3
"""Check the face decoding (rom.Rom.face_tiles / face_palette / dialogue_faces) against the game, in Mesen.

A table game is played until 豊臣秀吉 speaks (tools/sequences.py); a savestate is taken before the press that
leads to his line and replayed with tools/replay.py. Hooks (sequences.HOOK_LUA) change the speaker at $00:AB7C
(the game then loads that person's face stream) and the line's face code at $00:ABB4.
1. Every opponent (21) with every face code 0-4 of a line: the whole face stream the game decompresses to
   $7F:1000 must equal rom.face_stream (all 7 images); the image the code selects (copied to VRAM $E400, sprite
   tiles 0x120..) must equal rom.face_tiles(person, rom.dialogue_faces()[code]) (faces 0, 3, 4, 5 and the 56x56
   image); the talking face next to the line (VRAM $EA20, sprite tiles 0x151..) must be one of faces 0-2 (the
   mouth animation); CGRAM rows 9-10 must be the two face palettes, and the face sprites (OAM tile 0x151, or 0x120
   when the expression image is up, as for シブサワ・コウ) must use palette 1 + the opponent's palette select ($01:8925).
2. The unmodified run: the speaker is 秀吉 (1) and his line in WRAM is one of his ROM lines.

Usage: .venv/bin/python mahjong/verify_faces.py [--rom ROM]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "tools"))
import sequences as sq
from replay import replay
from rom import (
    DEFAULT_ROM,
    DIALOGUE_FACE_COUNT,
    FACE_BYTES,
    FACE_PAL_SELECT,
    FACE_PALETTES,
    PERSON_COUNT,
    SPECIAL_BYTES,
    Rom,
)

FACE_TILES = (0x120, 0x151)   # first tile of the expression image / of the talking face


def params(speaker: int | None = None, face_code: int | None = None) -> list:
    p = bytearray(16)
    if speaker is not None:
        p[0:2] = (1, speaker)
    if face_code is not None:
        p[2:4] = (1, face_code)
    return [(sq.PARAM & 0xFFFF, bytes(p))]


def sprite_palettes(oam: bytes) -> set[int]:
    return {oam[4 * i + 3] >> 1 & 7 for i in range(128) if oam[4 * i + 2] | (oam[4 * i + 3] & 1) << 8 in FACE_TILES
            and oam[4 * i + 1] < 224}


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證頭像解碼（Mesen）")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    t0 = time.time()
    rom = Rom(args.rom)
    reads = [("vram", sq.EXPR_VRAM, SPECIAL_BYTES + FACE_BYTES), ("cgram", sq.FACE_CGRAM, 64), ("oam", 0, 512),
             ("wram", sq.LINE_BUF, 17), ("wram", sq.FACE_STREAM_WRAM, len(rom.face_stream(0)))]
    runs, what = [], []
    for c in range(PERSON_COUNT):
        for e in range(DIALOGUE_FACE_COUNT):
            runs.append({"steps": sq.DIALOGUE_STEPS, "shot": sq.DIALOGUE_SHOT, "read": reads, "wram": params(c, e)})
            what.append((c, e))
    runs.append({"steps": sq.DIALOGUE_STEPS, "shot": sq.DIALOGUE_SHOT, "read": reads + [("wram", sq.SEAT_PERSON, 4)]})
    what.append((None, None))
    res = replay(rom.path, sq.DIALOGUE, sq.DIALOGUE_SAVE, runs, extra_lua=sq.HOOK_LUA, nmi=sq.NMI_HOOK, timeout=900)

    palettes = rom.data[FACE_PALETTES:FACE_PALETTES + 64]
    faces = rom.dialogue_faces()
    bad_stream, bad_img, bad_talk, bad_pal, bad_sel = set(), [], [], [], []
    natural_ok = False
    for (c, e), r in zip(what, res):
        vram, cgram, oam, line, stream = r[:5]
        if c is None:
            lines = {bytes(x["codes"]) for x in rom.dialogue(1)}
            shown = line[::-1][1:]
            natural_ok = 1 in r[5][1:4] and shown in lines
            print(f"[natural] seats {list(r[5])}, line {rom.text(shown)!r}: {'OK' if natural_ok else 'NG'}")
            continue
        if stream != rom.face_stream(c):
            bad_stream.add(c)
        want = rom.face_tiles(c, faces[e])
        if vram[:len(want)] != want:
            bad_img.append((c, e))
        if vram[SPECIAL_BYTES:] not in [rom.face_tiles(c, k) for k in range(3)]:
            bad_talk.append((c, e))
        if cgram != palettes:
            bad_pal.append((c, e))
        if sprite_palettes(oam) != {1 + rom.data[FACE_PAL_SELECT + c]}:
            bad_sel.append((c, e, sorted(sprite_palettes(oam))))
    n = PERSON_COUNT * DIALOGUE_FACE_COUNT
    print(f"[streams] {PERSON_COUNT - len(bad_stream)}/{PERSON_COUNT}: $7F:1000 = ROM face stream (7 images each)"
          + (f" NG {sorted(bad_stream)}" if bad_stream else ""))
    print(f"[expression] {n - len(bad_img)}/{n}: VRAM $E400 = face {faces} of the code 0-4"
          + (f" NG {bad_img[:10]}" if bad_img else ""))
    print(f"[talking] {n - len(bad_talk)}/{n}: VRAM $EA20 = one of faces 0-2" + (f" NG {bad_talk[:10]}" if bad_talk else ""))
    print(f"[palettes] {n - len(bad_pal)}/{n}: CGRAM rows 9-10 = $01:9384 / $01:93A4" + (" NG" if bad_pal else ""))
    print(f"[palette select] {n - len(bad_sel)}/{n}: face sprites (tile 0x120 / 0x151) use palette 1 + $01:8925[person]"
          + (f" NG {bad_sel[:5]}" if bad_sel else ""))
    errors = len(bad_stream) + len(bad_img) + len(bad_talk) + len(bad_pal) + len(bad_sel) + (not natural_ok)
    print(("ALL OK" if not errors else f"{errors} problem(s)") + f" ({time.time() - t0:.0f} s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
