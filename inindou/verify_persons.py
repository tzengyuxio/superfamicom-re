#!/usr/bin/env python3
"""Check persons, person states, jobs, job icons and the text code -> glyph mapping against the game's own 能力
screen (needs Mesen 2, a few minutes).

New game, field menu -> 情報 -> 人物選択 -> the hero -> 能力. For each run the hero's state record (WRAM
$7E:F0B8, the copy of sdata + 0xC8) is replaced before opening the menu:
  - persons 0-62: their own initial state record (sdata + 0xC8 + 32 n)
  - persons 63-104 (no state record): the hero's record with +0 = n (name and job only)
The screen is read back from VRAM (window layer, matched against the ROM font, tools-free: scenes.ScreenReader):
  - row 4: name (persons table, glyph = code - 0x8132; person 0 shows the typed name instead) and job name
  - 性別 (state +31 bit 7), レベル, 最大体力, 体力, 経験値, 最大気力, 気力, 知力, 力, 素早さ, 運 (state fields)
  - the job icon: VRAM 0xB600 (BG1 tiles 0x1B0-0x1BB, 384 bytes) must be rom.icon_tiles(JOB_ICON[job]) and
    CGRAM palette 0 the ROM palette rom.icon_palette_offset(icon)

Usage: .venv/bin/python inindou/verify_persons.py [--rom ROM]
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
from replay import end_frame, replay
from rom import (
    DEFAULT_ROM,
    ICON_BYTES,
    JOB_CODES,
    JOB_ICON,
    PERSON_COUNT,
    PERSON_SIZE,
    PERSONS,
    SDATA,
    STATE_COUNT,
    STATE_SIZE,
    STATES,
    TEXT_BASE,
    Rom,
    text_codes,
)
from scenes import (
    ABILITY,
    BOOT,
    SAVE,
    STATE_WRAM,
    TILEMAP,
    TILEMAP_SIZE,
    WINDOW_CHR,
    WINDOW_CHR_SIZE,
    ScreenReader,
    numbers,
)

ICON_VRAM = 0xB600
MALE, FEMALE = "男", "女"
# screen row -> state fields shown as half-width numbers, in order
ROWS = {8: ["レベル"], 10: ["最大体力"], 12: ["体力", "経験値"], 14: ["最大気力"], 16: ["気力"], 18: ["知力"],
        20: ["力"], 22: ["素早さ"], 24: ["運"]}


def glyphs(rom: Rom, raw: bytes) -> list[int]:
    return [c - TEXT_BASE for c in text_codes(raw) if c - TEXT_BASE != 14]


def main() -> None:
    ap = argparse.ArgumentParser(description="以 Mesen 能力畫面驗證人物、狀態、職業、職業圖示")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    persons, states, jobs = rom.persons(), rom.states(), rom.jobs()
    job_index = {c: k for k, c in enumerate(JOB_CODES)}
    runs, expect = [], []
    for n in range(PERSON_COUNT):
        src = n if n < STATE_COUNT else 0
        rec = bytearray(rom.data[SDATA + STATES + STATE_SIZE * src:SDATA + STATES + STATE_SIZE * (src + 1)])
        rec[0] = n
        st = states[src]
        runs.append({"wram": [(STATE_WRAM, bytes(rec))], "steps": ABILITY, "shot": end_frame(ABILITY, 0),
                     "read": [("vram", TILEMAP, TILEMAP_SIZE), ("vram", WINDOW_CHR, WINDOW_CHR_SIZE),
                              ("vram", ICON_VRAM, ICON_BYTES), ("cgram", 0, 32)]})
        expect.append((n, st))
    results = replay(args.rom, BOOT, SAVE, runs)
    reader = ScreenReader(rom.data)
    gl = {ch: g for g, ch in enumerate(rom.charset) if g >= 15}
    ok = {"name+job": 0, "values": 0, "icon": 0, "palette": 0}
    bad = []
    for (n, st), (tm, chr_, icon, cgram) in zip(expect, results):
        p = persons[n]
        k = job_index[p["job"]]
        rows = reader.lines(tm, chr_)
        job_glyphs = [gl[c] for c in jobs[k]["name"]]
        name_glyphs = glyphs(rom, rom.data[PERSONS + PERSON_SIZE * n:PERSONS + PERSON_SIZE * n + 12])
        row4 = rows.get(4, [])
        name_ok = row4[-len(job_glyphs):] == job_glyphs and (n == 0 or row4[:-len(job_glyphs)] == name_glyphs)
        vals_ok = True
        for y, fields in ROWS.items():
            got = numbers(rows.get(y, []))[:len(fields)]
            if got != [st[f] for f in fields]:
                vals_ok = False
        sex = gl[FEMALE] if st["female"] else gl[MALE]
        vals_ok &= sex in rows.get(8, [])
        icon_ok = icon == rom.icon_tiles(JOB_ICON[k])
        pal_off = rom.icon_palette_offset(JOB_ICON[k])
        pal_ok = cgram == rom.data[pal_off:pal_off + 32]
        for key, good in (("name+job", name_ok), ("values", vals_ok), ("icon", icon_ok), ("palette", pal_ok)):
            ok[key] += good
            if not good:
                bad.append((n, key))
    total = len(expect)
    for key, v in ok.items():
        print(f"[{key}] {v}/{total}")
    if bad:
        print("NG", bad[:20])
    print("ALL OK" if not bad else f"{len(bad)} problem(s)")
    raise SystemExit(1 if bad else 0)


if __name__ == "__main__":
    main()
