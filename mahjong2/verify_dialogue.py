#!/usr/bin/env python3
"""Check the dialogue decoding (rom.Rom.dialogue_raw / text / glyph and data/charset.txt) against the game, in Mesen.

Same savestate as verify_faces.py (リンカーン about to speak), same hooks (tools/sequences.py).
1. Every opponent (26) made the speaker at $00:C318: the dialogue stream the game decompresses to $7F:6000
   (344 lines x 25 bytes) must equal rom.dialogue_raw, i.e. the table $01:D5BE / $01:D5F2 and the line layout.
2. Every font code 01-D4, written as the shown line at $00:C366 (24 codes per run): the BG tilemap of リンカーン's
   window (rows 13-18, columns 3-10) must hold tile 0x56 + 2c (top) / 0x57 + 2c (bottom), palette 3, for each code c (D4,
   the blank: tile 0x06E), and the BG tiles of every code (VRAM $8AC0 + 64c) must equal rom.glyph(c), i.e. the font stream 03:F630. That
   the glyphs read as data/charset.txt says is checked by eye on output/charset_sheet.png (tools/charset_sheet.py).

Usage: .venv/bin/python mahjong2/verify_dialogue.py [--rom ROM]
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
from rom import BLANK, DEFAULT_ROM, FONT_CODES, LINE_COUNT, LINE_SIZE, PERSONS, Rom

TEXT_PAL = 3
BLANK_TILE = 0x06E          # D4 (blank) is drawn with this tile, not with its own glyph
TEXT_ROW, TEXT_COL = 13, 3       # リンカーン's window: three lines of 8 codes, 8x16 each


def params(speaker: int | None = None, codes: bytes | None = None) -> list:
    p = bytearray(48)
    if speaker is not None:
        p[0:2] = (1, speaker)
    if codes is not None:
        p[4] = 1
        p[16:40] = codes
    return [(sq.PARAM & 0xFFFF, bytes(p))]


def window_tiles(tilemap: bytes) -> list[tuple[int, int]]:
    """(top, bottom) tilemap words of the 24 code cells of the window."""
    def word(row: int, col: int) -> int:
        i = 2 * (row * 32 + col)
        return tilemap[i] | tilemap[i + 1] << 8
    return [(word(TEXT_ROW + 2 * (k // 8), TEXT_COL + k % 8), word(TEXT_ROW + 2 * (k // 8) + 1, TEXT_COL + k % 8))
            for k in range(24)]


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證台詞與字型解碼（Mesen）")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    t0 = time.time()
    rom = Rom(args.rom)
    runs, what = [], []
    for p in PERSONS:
        runs.append({"steps": sq.DIALOGUE_STEPS, "shot": sq.DIALOGUE_SHOT, "wram": params(p),
                     "read": [("wram", sq.DIALOGUE_WRAM, LINE_COUNT * LINE_SIZE)]})
        what.append(("stream", p))
    codes = list(range(1, FONT_CODES + 1))
    groups = [codes[i:i + 24] for i in range(0, len(codes), 24)]
    groups[-1] += [BLANK] * (24 - len(groups[-1]))
    font_at = sq.BG_CHR + 0x58 * 32
    for n, g in enumerate(groups):
        reads = [("vram", sq.TILEMAP, 0x800)]
        if n == 0:
            reads.append(("vram", font_at, FONT_CODES * 64))
        runs.append({"steps": sq.DIALOGUE_STEPS, "shot": sq.TEXT_SHOT, "wram": params(codes=bytes(g)), "read": reads})
        what.append(("codes", g))
    res = replay(rom.path, sq.DIALOGUE, sq.DIALOGUE_SAVE, runs, extra_lua=sq.HOOK_LUA, timeout=900)

    bad_stream, bad_code, bad_glyph, checked = [], [], [], set()
    for (kind, arg), r in zip(what, res):
        if kind == "stream":
            if r[0] != rom.dialogue_raw(arg):
                bad_stream.append(arg)
            continue
        for c, (top, bottom) in zip(arg, window_tiles(r[0])):
            checked.add(c)
            want = (BLANK_TILE, BLANK_TILE) if c == BLANK else (0x56 + 2 * c, 0x57 + 2 * c)
            if (top & 0x3FF, bottom & 0x3FF) != want \
                    or (top >> 10 & 7, bottom >> 10 & 7) != (TEXT_PAL, TEXT_PAL):
                bad_code.append((hex(c), hex(top), hex(bottom)))
        if len(r) > 1:
            bad_glyph = [c for c in codes if r[1][64 * (c - 1):64 * c] != rom.glyph(c)]
    print(f"[streams] {len(PERSONS) - len(bad_stream)}/{len(PERSONS)}: $7F:6000 = ROM dialogue stream "
          f"({LINE_COUNT} lines x {LINE_SIZE} bytes)" + (f" NG {bad_stream}" if bad_stream else ""))
    good = len(checked - {int(b[0], 16) for b in bad_code})
    print(f"[codes] {good}/{len(codes)}: window tilemap = tile 0x56 + 2c / 0x57 + 2c, palette 3 (D4: 0x06E)"
          + (f" NG {bad_code[:8]}" if bad_code else ""))
    print(f"[glyphs] {len(codes) - len(bad_glyph)}/{len(codes)}: BG tiles = rom.glyph"
          + (f" NG {[hex(c) for c in bad_glyph[:10]]}" if bad_glyph else ""))
    errors = len(bad_stream) + len(bad_code) + len(bad_glyph) + (len(checked) != len(codes))
    print(("ALL OK" if not errors else f"{errors} problem(s)") + f" ({time.time() - t0:.0f} s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
