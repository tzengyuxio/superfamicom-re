#!/usr/bin/env python3
"""Check the yaku names (rom.Rom.yaku, data/glyph16.txt) against the game's yaku screen, in Mesen.

A table game is played until ノストラダムス wins (tools/sequences.py: 三暗刻, 立直, 門前清摸和, ドラ); a savestate is
taken before the press that leads to the yaku screen. The unmodified run must show those 4 yaku ($41 = count, $175F
= ids). Then the hook at $00:E0DB (the name loop of the yaku screen) replaces the 4 ids with 4 of the 65 strings at
$01:F4BD per run. For each name, the BG tilemap row 4 + 2k from column 14 must hold, for each glyph byte b of the
string, the tiles 0x72 + 4b .. 0x75 + 4b (top-left, top-right / bottom-left, bottom-right); and the BG tiles of every
glyph (VRAM $8EC0 + 128g) must equal rom.glyph16(g), i.e. the stream 04:AD49. Columns 25 and up of a line are
skipped (the han count is drawn there over string 64, the only 6-glyph name). That the glyphs read as
data/glyph16.txt says is checked by eye on output/glyph16_sheet.png.

Usage: .venv/bin/python mahjong2/verify_yaku.py [--rom ROM]
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
from rom import DEFAULT_ROM, GLYPH16_COUNT, NAME_STRINGS, Rom

ROW, COL, LAST_COL = 4, 14, 25
PER_RUN = 4
NATURAL = [19, 5, 0, 32]


def params(ids: list[int]) -> list:
    p = bytearray(64)
    p[5] = len(ids)
    p[48:48 + len(ids)] = bytes(ids)
    return [(sq.PARAM & 0xFFFF, bytes(p))]


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證役名（Mesen）")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    t0 = time.time()
    rom = Rom(args.rom)
    codes = rom.name_codes()
    reads = [("vram", sq.TILEMAP, 0x800), ("wram", sq.YAKU_COUNT, 1), ("wram", sq.YAKU_IDS, PER_RUN)]
    runs = [{"steps": sq.YAKU_STEPS, "shot": sq.YAKU_SHOT,
             "read": reads + [("vram", sq.BG_CHR + 0x76 * 32, GLYPH16_COUNT * 128)]}]
    groups = [list(range(i, min(i + PER_RUN, NAME_STRINGS))) for i in range(0, NAME_STRINGS, PER_RUN)]
    for g in groups:
        runs.append({"steps": sq.YAKU_STEPS, "shot": sq.YAKU_SHOT, "read": reads, "wram": params(g)})
    res = replay(rom.path, sq.YAKU, sq.YAKU_SAVE, runs, extra_lua=sq.HOOK_LUA, timeout=900)

    def word(tm: bytes, r: int, c: int) -> int:
        return tm[2 * (r * 32 + c)] | tm[2 * (r * 32 + c) + 1] << 8

    def shown_ok(tm: bytes, k: int, s: bytes) -> bool:
        for j, b in enumerate(s):
            c = COL + 2 * j
            if c + 1 >= LAST_COL:
                break
            got = [word(tm, ROW + 2 * k + y, c + x) & 0x3FF for y in (0, 1) for x in (0, 1)]
            if got != [0x72 + 4 * b + q for q in range(4)]:
                return False
        return True

    tm, n, ids, chr_ = res[0]
    natural = n[0] == len(NATURAL) and list(ids) == NATURAL and all(shown_ok(tm, k, codes[y]) for k, y in enumerate(NATURAL))
    print(f"[natural] count {n[0]}, ids {list(ids)} ({' '.join(rom.yaku()[y]['name'] for y in ids)}): "
          + ("OK" if natural else "NG"))
    bad_glyph = [g for g in range(GLYPH16_COUNT) if chr_[128 * g:128 * (g + 1)] != rom.glyph16(g)]
    bad = []
    for g, (tm, n, ids) in zip(groups, res[1:]):
        for k, y in enumerate(g):
            if not shown_ok(tm, k, codes[y]):
                bad.append(y)
    print(f"[names] {NAME_STRINGS - len(bad)}/{NAME_STRINGS}: yaku screen tilemap = tiles 0x72 + 4b .. 0x75 + 4b"
          + (f" NG {bad}" if bad else ""))
    print(f"[glyphs] {GLYPH16_COUNT - len(bad_glyph)}/{GLYPH16_COUNT}: VRAM $8EC0 + 128g = rom.glyph16"
          + (f" NG {bad_glyph[:10]}" if bad_glyph else ""))
    errors = len(bad) + len(bad_glyph) + (not natural)
    print(("ALL OK" if not errors else f"{errors} problem(s)") + f" ({time.time() - t0:.0f} s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
