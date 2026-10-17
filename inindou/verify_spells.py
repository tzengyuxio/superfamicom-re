#!/usr/bin/env python3
"""Check the spell table (data file) against the game's 術 screen (needs Mesen 2, under a minute).

New game, field menu -> 情報 -> 人物選択 -> the hero -> 術. The hero's state record (WRAM $7E:F0B8) is replaced
by the initial record of a person of each school, with the four spell bytes (+18..+21) set to FF so every spell
of the school is listed: the hero (忍術, spells 0-13), 天海 (person 18, 仙術, 14-27) and 土御門晴友 (person 3,
妖術, 28-41). The screen lists a school's 14 spells in three columns of 5, 4 and 5 (rows 9, 12, ..., 21); each
row read back from VRAM must be the glyphs of its spells (rom.Rom.spells), and row 3 the school name.

Usage: .venv/bin/python inindou/verify_spells.py [--rom ROM]
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
from replay import end_frame, replay
from rom import DEFAULT_ROM, SDATA, SPELL_COUNT, SPELL_SIZE, SPELLS, STATE_SIZE, STATES, TEXT_BASE, Rom, text_codes
from scenes import BOOT, SAVE, STATE_WRAM, TILEMAP, TILEMAP_SIZE, WINDOW_CHR, WINDOW_CHR_SIZE, ScreenReader
from scenes import SPELLS as SPELL_STEPS

SCHOOLS = [(0, "忍術"), (18, "仙術"), (3, "妖術")]   # (person whose record is used, school name)
COLUMNS = [(0, 5), (5, 4), (9, 5)]                   # (first spell, count) of each column


def main() -> None:
    ap = argparse.ArgumentParser(description="以 Mesen 術畫面驗證術表")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    runs = []
    for person, _ in SCHOOLS:
        rec = bytearray(rom.data[SDATA + STATES + STATE_SIZE * person:SDATA + STATES + STATE_SIZE * (person + 1)])
        rec[18:22] = b"\xff" * 4
        runs.append({"wram": [(STATE_WRAM, bytes(rec))], "steps": SPELL_STEPS, "shot": end_frame(SPELL_STEPS, 0),
                     "read": [("vram", TILEMAP, TILEMAP_SIZE), ("vram", WINDOW_CHR, WINDOW_CHR_SIZE)]})
    results = replay(args.rom, BOOT, SAVE, runs)
    reader = ScreenReader(rom.data)
    gl = {ch: g for g, ch in enumerate(rom.charset) if g >= 15}

    def glyphs(n: int) -> list[int]:
        o = SPELLS + SPELL_SIZE * n
        return [c - TEXT_BASE for c in text_codes(rom.data[o:o + 6]) if c >= 0x80 and c - TEXT_BASE != 14]

    good, bad = set(), set()
    for s, ((_, school), (tm, chr_)) in enumerate(zip(SCHOOLS, results)):
        rows = reader.lines(tm, chr_)
        if [gl[c] for c in school] != rows.get(3, [])[-2:]:
            bad.add(f"school {school}")
        for i in range(5):
            ids = [14 * s + first + i for first, count in COLUMNS if i < count]
            (good if rows.get(9 + 3 * i, []) == [g for n in ids for g in glyphs(n)] else bad).update(ids)
    good -= bad
    print(f"[spells] {len(good)}/{SPELL_COUNT} spell names match the 術 screen" + (f" (NG {sorted(map(str, bad))})"
                                                                                   if bad else ""))
    print("ALL OK" if not bad and len(good) == SPELL_COUNT else "problem(s)")
    raise SystemExit(0 if not bad and len(good) == SPELL_COUNT else 1)


if __name__ == "__main__":
    main()
