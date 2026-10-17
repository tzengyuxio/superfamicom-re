#!/usr/bin/env python3
"""Check the yaku names (rom.Rom.yaku, data/glyph16.txt) against the game's yaku screen, in Mesen.

A table game is played until 織田信長 wins (tools/sequences.py YAKU); a savestate is taken before the press that
leads to the yaku screen and replayed with tools/replay.py. A hook at $00:C37A, where the names are about to be
drawn, replaces the yaku list ($37 = count, $071E = ids) by 6 ids per run, so all 52 are drawn. For each name the
BG1 tilemap (column 14, rows 5, 7, ...; 2 x 2 tiles per glyph) must hold tiles 0x8C + 4b .. 0x8F + 4b for the
ROM bytes b of the name, and the BG1 tiles of all 99 glyphs (from tile 0x90) must equal rom.glyph16 (stream 07:BBAD).
The unmodified run must show 平和 and ドラ (ids 1 and 51). That the glyphs read as data/glyph16.txt says is
checked by eye (output/glyph16_sheet.png).

Usage: .venv/bin/python mahjong/verify_yaku.py [--rom ROM]
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
from rom import DEFAULT_ROM, GLYPH16_COUNT, YAKU_COUNT, Rom

PER_RUN = 6
NAME_COL, FIRST_ROW = 0x0E, 5
CHR = 0x8000


def params(ids: list[int]) -> list:
    p = bytearray(48)
    p[5] = len(ids)
    p[32:32 + len(ids)] = bytes(ids)
    return [(sq.PARAM & 0xFFFF, bytes(p))]


def drawn(tilemap: bytes, k: int, n: int) -> list[int]:
    """Tile numbers of the 4 cells of glyph n of the k-th name (TL, TR, BL, BR)."""
    r, c = FIRST_ROW + 2 * k, NAME_COL + 2 * n

    def tile(rr: int, cc: int) -> int:
        return (tilemap[2 * (rr * 32 + cc)] | tilemap[2 * (rr * 32 + cc) + 1] << 8) & 0x3FF
    return [tile(r, c), tile(r, c + 1), tile(r + 1, c), tile(r + 1, c + 1)]


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證役名（Mesen）")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    t0 = time.time()
    rom = Rom(args.rom)
    yaku = rom.yaku()
    groups = [list(range(i, min(i + PER_RUN, YAKU_COUNT))) for i in range(0, YAKU_COUNT, PER_RUN)]
    reads = [("vram", 0, 0x800), ("vram", CHR + 32 * 0x90, 128 * GLYPH16_COUNT), ("wram", sq.YAKU_IDS, 10),
             ("wram", sq.YAKU_COUNT, 1)]
    runs = [{"steps": sq.YAKU_STEPS, "shot": sq.YAKU_SHOT, "read": reads}]
    runs += [{"steps": sq.YAKU_STEPS, "shot": sq.YAKU_SHOT, "read": reads, "wram": params(g)} for g in groups]
    res = replay(rom.path, sq.YAKU, sq.YAKU_SAVE, runs, extra_lua=sq.HOOK_LUA, timeout=900)

    natural = list(res[0][2][:res[0][3][0]])
    nat_ok = natural == [1, 51] and all(
        drawn(res[0][0], k, n) == [0x8C + 4 * b + q for q in range(4)]
        for k, y in enumerate(natural) for n, b in enumerate(yaku[y]["codes"]))
    print(f"[natural] yaku {[yaku[y]['name'] for y in natural]}: {'OK' if nat_ok else 'NG'}")
    bad, bad_glyph = [], set()
    for g, r in zip(groups, res[1:]):
        for k, y in enumerate(g):
            want = [[0x8C + 4 * b + q for q in range(4)] for b in yaku[y]["codes"]]
            got = [drawn(r[0], k, n) for n in range(len(want))]
            if got != want:
                bad.append((y, yaku[y]["name"]))
        bad_glyph |= {n for n in range(GLYPH16_COUNT) if r[1][128 * n:128 * n + 128] != rom.glyph16(n)}
    print(f"[names] {YAKU_COUNT - len(bad)}/{YAKU_COUNT}: tilemap = tiles 0x8C + 4b of the ROM name"
          + (f" NG {bad[:8]}" if bad else ""))
    print(f"[glyphs] {GLYPH16_COUNT - len(bad_glyph)}/{GLYPH16_COUNT}: BG1 tiles 0x90.. = stream 07:BBAD"
          + (f" NG {sorted(bad_glyph)[:10]}" if bad_glyph else ""))
    errors = len(bad) + len(bad_glyph) + (not nat_ok)
    print(("ALL OK" if not errors else f"{errors} problem(s)") + f" ({time.time() - t0:.0f} s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
