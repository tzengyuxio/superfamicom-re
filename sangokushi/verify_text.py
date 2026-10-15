#!/usr/bin/env python3
"""Check the text codes and the font (rom.encode_glyph / code_glyph, rom.FONT layout) against the game's drawing.

Scenario 1 is played to 曹操's command screen; a savestate is taken there. Each run patches the three kanji codes
of every name table entry (PRG ROM) with glyphs under test, opens 情報 → 武将 (the 7 generals of 7国: persons 1,
11, 12, 13, 14, 16, 30) and reads the whole VRAM. The game draws a glyph as four consecutive 2bpp tiles (TL TR
BL BR, both planes = the font byte), and the three glyphs of a name one after another, so for every listed
person the 3 x 64 bytes built from FONT + 32 g must stand in VRAM in a row. 7 names x 3 glyphs per run cover all
921 glyphs (codes 0x8140 + g, and the 0x9140 + k escape for the codes whose low byte would be 00).

The glyph → character table (data/charset.txt) is a human reading of the glyphs; the game cannot check it. It is
cross-checked by the 255 person names, which match the FC names except where the SFC changed a name (README).

Usage: .venv/bin/python sangokushi/verify_text.py [--rom ROM]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
sys.path.insert(0, os.path.join(HERE, "tools"))
import replay
import sequences
from rom import DEFAULT_ROM, FONT, GLYPH_COUNT, NAME_SIZE, NAMES, PERSON_COUNT, Rom, code_glyph, encode_glyph

SHOWN = [1, 11, 12, 13, 14, 16, 30]       # persons on the 武将 list of 7国 at the start of scenario 1


def glyph_tiles(rom: Rom, g: int) -> bytes:
    raw = rom.data[FONT + 32 * g:FONT + 32 * g + 32]
    return bytes(b for v in raw for b in (v, v))


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證字碼與字型")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    t0 = time.time()
    rom = Rom(args.rom)
    assert all(code_glyph(int.from_bytes(encode_glyph(g), "big")) == g for g in range(GLYPH_COUNT))
    per_run = 3 * len(SHOWN)
    steps = sequences.expand(sequences.INFO_PERSONS)
    runs, plans = [], []
    for start in range(0, GLYPH_COUNT, per_run):
        gs = [(start + i) % GLYPH_COUNT for i in range(per_run)]
        plan = {p: gs[3 * k:3 * k + 3] for k, p in enumerate(SHOWN)}
        patch = [(NAMES + NAME_SIZE * p + 8, b"".join(encode_glyph(g) for g in plan.get(p, plan[SHOWN[0]])))
                 for p in range(PERSON_COUNT)]
        runs.append({"patch": patch, "steps": steps, "shot": sequences.end_frame(steps, 0) + 20,
                     "read": [("vram", 0, 0x10000)]})
        plans.append(plan)
    results = replay.replay(args.rom, sequences.TO_MAIN, sequences.end_frame(sequences.TO_MAIN), runs)
    ok, bad = set(), []
    for plan, (vram,) in zip(plans, results):
        for p, gs in plan.items():
            name = b"".join(glyph_tiles(rom, g) for g in gs)
            if vram.find(name) >= 0:
                ok.update(gs)
            else:
                bad.append((p, gs))
    escaped = [g for g in range(GLYPH_COUNT) if encode_glyph(g)[0] == 0x91]
    print(f"[font] {len(ok)}/{GLYPH_COUNT} glyphs drawn by the game as rom.FONT + 32 g (TL TR BL BR) for code "
          f"encode_glyph(g); escape codes 0x9140 + k: glyphs {escaped} "
          f"{'OK' if set(escaped) <= ok else 'NG'}; {len(runs)} runs")
    for b in bad[:5]:
        print("  NG person", b)
    print(f"{time.time() - t0:.0f} s")
    errors = len(bad) + (len(ok) != GLYPH_COUNT)
    print("ALL OK" if not errors else f"{errors} mismatch(es)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
