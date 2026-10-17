#!/usr/bin/env python3
"""Check the face decoding (rom.Rom.face_tiles / palette / dialogue_faces) against the game, in Mesen.

A table game is played until リンカーン speaks (tools/sequences.py); a savestate is taken before the press that leads
to his line and replayed with tools/replay.py. Hooks (sequences.HOOK_LUA) change the speaker at $00:C318 (the game
then loads that person's face stream and dialogue) and the line at $00:C366: the face code, and a one-code line
("あ") so that the expression image is up by the shot (the game shows it once the line is typed out).
1. Every opponent (26) with every face code 0-6: the whole face stream the game decompresses to $7F:1000 must equal
   rom.face_stream (all 9 images); the image the code selects (copied to VRAM $DC60) must equal
   rom.face_tiles(person, rom.dialogue_faces()[code]) (images 0, 3-8); the talking face (VRAM $D940) must be one of
   images 0-2 (the mouth animation); CGRAM row 15 must be the person's palette ($01:CCB1, or $01:CCCB for the 56x56
   image of code 5) and the face sprites (OAM tiles 0xCA.. and 0xE3..) must use sprite palette 7 (= row 15).
2. The unmodified run: the speaker is リンカーン (2) and the line in WRAM is one of his ROM lines.

Usage: .venv/bin/python mahjong2/verify_faces.py [--rom ROM]
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
from rom import BIG_IMAGE, BLANK, DEFAULT_ROM, DIALOGUE_FACE_COUNT, PALETTES, PERSONS, Rom

EXPR_BYTES = 1568
TALK_BYTES = 800
FACE_TILES = (0xCA, 0xE3)   # first sprite tile of the talking face / of the expression image (VRAM $DC60)
SHORT_LINE = bytes([0x2E] + [BLANK] * 23)   # "あ": the expression image replaces the talking face once a line is typed


def params(speaker: int | None = None, face_code: int | None = None, codes: bytes | None = None) -> list:
    p = bytearray(48)
    if speaker is not None:
        p[0:2] = (1, speaker)
    if face_code is not None:
        p[2:4] = (1, face_code)
    if codes is not None:
        p[4] = 1
        p[16:40] = codes
    return [(sq.PARAM & 0xFFFF, bytes(p))]


def sprite_palettes(oam: bytes) -> set[int]:
    return {oam[4 * i + 3] >> 1 & 7 for i in range(128)
            if any(t <= (oam[4 * i + 2] | (oam[4 * i + 3] & 1) << 8) < t + 49 for t in FACE_TILES) and oam[4 * i + 1] < 224}


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證頭像解碼（Mesen）")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    t0 = time.time()
    rom = Rom(args.rom)
    reads = [("vram", sq.EXPR_VRAM, EXPR_BYTES), ("vram", sq.TALK_VRAM, TALK_BYTES), ("cgram", sq.FACE_CGRAM, 32),
             ("oam", 0, 512), ("wram", sq.LINE_BUF, 25), ("wram", sq.FACE_STREAM_WRAM, len(rom.face_stream(1)))]
    runs, what = [], []
    for p in PERSONS:
        for e in range(DIALOGUE_FACE_COUNT):
            runs.append({"steps": sq.DIALOGUE_STEPS, "shot": sq.DIALOGUE_SHOT, "read": reads, "wram": params(p, e, SHORT_LINE)})
            what.append((p, e))
    runs.append({"steps": sq.DIALOGUE_STEPS, "shot": sq.DIALOGUE_SHOT,
                 "read": reads + [("wram", sq.SEAT_SLOT, 10)]})
    what.append((None, None))
    res = replay(rom.path, sq.DIALOGUE, sq.DIALOGUE_SAVE, runs, extra_lua=sq.HOOK_LUA, timeout=1200)

    faces = rom.dialogue_faces()
    n = len(PERSONS) * DIALOGUE_FACE_COUNT
    bad_stream, bad_img, bad_talk, bad_pal, bad_sel = set(), [], [], [], []
    natural_ok = False
    for (p, e), r in zip(what, res):
        expr, talk, cgram, oam, line, stream = r[:6]
        if p is None:
            seats = r[6]
            speaker_ok = 2 in seats[6:10]
            shown = line[::-1][1:]
            natural_ok = speaker_ok and shown in {bytes(x["codes"]) for x in rom.dialogue(2)}
            print(f"[natural] slots {list(seats[6:10])}, line {rom.text(shown)!r}: {'OK' if natural_ok else 'NG'}")
            continue
        if stream != rom.face_stream(p):
            bad_stream.add(p)
        want = rom.face_tiles(p, faces[e])
        if expr[:len(want)] != want:
            bad_img.append((p, e))
        if talk not in [rom.face_tiles(p, k) for k in range(3)]:
            bad_talk.append((p, e))
        k = rom.image_palette(p, faces[e] if faces[e] == BIG_IMAGE else 0)
        if cgram != rom.data[PALETTES + 32 * k:PALETTES + 32 * k + 32]:
            bad_pal.append((p, e, k))
        if sprite_palettes(oam) != {sq.FACE_OAM_PAL}:
            bad_sel.append((p, e, sorted(sprite_palettes(oam))))
    print(f"[streams] {len(PERSONS) - len(bad_stream)}/{len(PERSONS)}: $7F:1000 = ROM face stream (9 images each)"
          + (f" NG {sorted(bad_stream)}" if bad_stream else ""))
    print(f"[expression] {n - len(bad_img)}/{n}: VRAM $DC60 = image {faces} of the code 0-6"
          + (f" NG {bad_img[:10]}" if bad_img else ""))
    print(f"[talking] {n - len(bad_talk)}/{n}: VRAM $D940 = one of images 0-2" + (f" NG {bad_talk[:10]}" if bad_talk else ""))
    print(f"[palettes] {n - len(bad_pal)}/{n}: CGRAM row 15 = $02:8000 + 32 x ($01:CCB1 or, for the 56x56 image, $01:CCCB)"
          + (f" NG {bad_pal[:10]}" if bad_pal else ""))
    print(f"[sprites] {n - len(bad_sel)}/{n}: face sprites use palette 7" + (f" NG {bad_sel[:5]}" if bad_sel else ""))
    errors = len(bad_stream) + len(bad_img) + len(bad_talk) + len(bad_pal) + len(bad_sel) + (not natural_ok)
    print(("ALL OK" if not errors else f"{errors} problem(s)") + f" ({time.time() - t0:.0f} s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
