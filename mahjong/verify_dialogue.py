#!/usr/bin/env python3
"""Check the dialogue decoding (rom.Rom.dialogue_raw / text / glyph and data/charset.txt) against the game, in Mesen.

Same savestate as verify_faces.py (豊臣秀吉 about to speak), same hooks (tools/sequences.py).
1. Every opponent (21) made the speaker at $00:AB7C: the dialogue stream the game decompresses to $7F:F400
   (133 lines x 17 bytes) must equal rom.dialogue_raw, i.e. the table $01:89E1 / $01:8A0B and the line layout.
2. Every font code 00-D3 and FF, written as the shown line at $00:ABB4 (16 codes per run): the BG1 tilemap of the
   window (rows 15-18, columns 20-27) must hold tile 0x6E + 2c (top) / 0x6F + 2c (bottom), palette 3, for each
   code c (FF: the blank tile 0x001), and the BG1 tiles of every code (VRAM $8DC0 + 64c) must equal rom.glyph(c),
   i.e. the two font streams. That the glyphs read as data/charset.txt says is checked by eye on
   output/charset_sheet.png (tools/charset_sheet.py).

Usage: .venv/bin/python mahjong/verify_dialogue.py [--rom ROM]
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
from rom import DEFAULT_ROM, FONT_CODES, LINE_COUNT, LINE_SIZE, PERSON_COUNT, Rom

BLANK_TILE = 0x001
TEXT_PAL = 3
TEXT_SHOT = 290   # all 16 codes are typed out (at 240 the last five are not yet)


def params(speaker: int | None = None, codes: bytes | None = None) -> list:
    p = bytearray(32)
    if speaker is not None:
        p[0:2] = (1, speaker)
    if codes is not None:
        p[4] = 1
        p[16:32] = codes
    return [(sq.PARAM & 0xFFFF, bytes(p))]


def window_tiles(tilemap: bytes) -> list[tuple[int, int]]:
    """(top, bottom) tilemap words of the 16 code cells of the window."""
    def word(row: int, col: int) -> int:
        i = 2 * (row * 32 + col)
        return tilemap[i] | tilemap[i + 1] << 8
    return [(word(2 * (k // 8), sq.TEXT_COL + k % 8), word(2 * (k // 8) + 1, sq.TEXT_COL + k % 8)) for k in range(16)]


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證台詞與字型解碼（Mesen）")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    t0 = time.time()
    rom = Rom(args.rom)
    size = LINE_COUNT * LINE_SIZE
    runs, what = [], []
    for c in range(PERSON_COUNT):
        runs.append({"steps": sq.DIALOGUE_STEPS, "shot": sq.DIALOGUE_SHOT, "wram": params(c),
                     "read": [("wram", sq.DIALOGUE_WRAM, size)]})
        what.append(("stream", c))
    codes = list(range(FONT_CODES)) + [0xFF]
    groups = [codes[i:i + 16] for i in range(0, len(codes), 16)]
    groups[-1] = groups[-1][:-1] + [0xFF] * 4 + list(range(1, 13 - len(groups[-1])))  # a short line closes early
    font_at = sq.BG1_CHR + 0x6E * 32
    for n, g in enumerate(groups):
        reads = [("vram", 2 * sq.TEXT_ROWS * 32, 4 * 64)]
        if n == 0:
            reads.append(("vram", font_at, FONT_CODES * 64))
        runs.append({"steps": sq.DIALOGUE_STEPS, "shot": TEXT_SHOT, "wram": params(codes=bytes(g)),
                     "read": reads})
        what.append(("codes", g))
    res = replay(rom.path, sq.DIALOGUE, sq.DIALOGUE_SAVE, runs, extra_lua=sq.HOOK_LUA, timeout=900)

    bad_stream, bad_code, bad_glyph, checked = [], [], [], set()
    for (kind, arg), r in zip(what, res):
        if kind == "stream":
            if r[0] != rom.dialogue_raw(arg):
                bad_stream.append(arg)
            continue
        for c, (top, bottom) in zip(arg, window_tiles(r[0])):
            want = (BLANK_TILE, BLANK_TILE) if c == 0xFF else (0x6E + 2 * c, 0x6F + 2 * c)
            checked.add(c)
            if (top & 0x3FF, bottom & 0x3FF) != want or (top >> 10 & 7, bottom >> 10 & 7) != (TEXT_PAL, TEXT_PAL):
                bad_code.append((c, hex(top), hex(bottom)))
        if len(r) > 1:
            bad_glyph = [c for c in range(FONT_CODES) if r[1][64 * c:64 * c + 64] != rom.glyph(c)]
    print(f"[streams] {PERSON_COUNT - len(bad_stream)}/{PERSON_COUNT}: $7F:F400 = ROM dialogue stream "
          f"({LINE_COUNT} lines x {LINE_SIZE} bytes)" + (f" NG {bad_stream}" if bad_stream else ""))
    good = len(checked - {b[0] for b in bad_code})
    print(f"[codes] {good}/{len(codes)}: window tilemap = tile 0x6E + 2c / 0x6F + 2c, palette 3"
          " (FF = blank)" + (f" NG {bad_code[:8]}" if bad_code else ""))
    print(f"[glyphs] {FONT_CODES - len(bad_glyph)}/{FONT_CODES}: BG1 tiles = rom.glyph"
          + (f" NG {[hex(c) for c in bad_glyph[:10]]}" if bad_glyph else ""))
    errors = len(bad_stream) + len(bad_code) + len(bad_glyph) + (len(checked) != len(codes))
    print(("ALL OK" if not errors else f"{errors} problem(s)") + f" ({time.time() - t0:.0f} s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
