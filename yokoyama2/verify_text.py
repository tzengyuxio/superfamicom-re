#!/usr/bin/env python3
"""Check the text codes and the font layout (rom.FONT16 / FONT8, rom.Rom.glyph16 / glyph8) against the game.

Scenario 189 is played to the player's first turn (savestate, tools/sequences.py TO_MAP). Each run writes 32 codes
under test to free ROM space (READING; $8C:F950-$8CFFFF is all FF) and points the reading of 遼東 there (PRG ROM
patches), puts the map cursor on 遼東 and presses X (the country information screen prints the reading), and logs,
for every code given to $80:8C2E, the glyph offset X the routine reads the font with ($80:8C8B LDA $9A:8000,X for
16x16 glyphs, $80:8CBE LDA $99:A000,X for 8x16). Every code 0x100-0x5FF must be printed and read its glyph at
FONT16 + 32 (code - 0x200) or FONT8 + 16 (code - 0x100).

The glyph -> character table (data/charset.txt) is a human reading of the glyphs (tools/charset_sheet.py draws
them side by side); the game cannot check it. The 239 names, 35 country names and their readings are a
cross-check (verify_persons.py, verify_countries.py).

Usage: .venv/bin/python yokoyama2/verify_text.py [--rom ROM]
"""
import argparse
import os
import struct
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
sys.path.insert(0, os.path.join(HERE, "tools"))
import replay
import sequences as q
from rom import COUNTRY_COUNT, COUNTRY_NAMES, DEFAULT_ROM, FONT8, FONT16, Rom, off

READING = 0x8CF960
COUNTRY = 0                         # 遼東
FIRST, LAST = 0x100, 0x600
PER_RUN = 32
CURSOR = 0x0160
PRE = "w30"
STEPS = PRE + " x:10 w300"

LUA = """
local log={}
local code=-1
for _,a in ipairs({0x008C2E, 0x808C2E}) do
  emu.addMemoryCallback(function() code=emu.getState()["cpu.a"] & 0xFFFF end, emu.callbackType.exec, a)
end
for _,p in ipairs({{0x008C8B, 1}, {0x808C8B, 1}, {0x008CBE, 2}, {0x808CBE, 2}}) do
  emu.addMemoryCallback(function()
    if code>=0 then
      log[#log+1]=string.format("%04x%02x%04x", code, p[2], emu.getState()["cpu.x"] & 0xFFFF)
      code=-1
    end
  end, emu.callbackType.exec, p[1])
end
function EXTRA_RESET() log={} end
function EXTRA_SHOT() local s=table.concat(log); log={}; if s=="" then s="00" end; return s end
"""


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證字碼與字型位址（$80:8C2E 讀字型的位置）")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    t0 = time.time()
    rom = Rom(args.rom)
    assert set(rom.raw(0x8CF950, 0x6B0)) == {0xFF}
    pointer = off(COUNTRY_NAMES + 4 * COUNTRY_COUNT + 2 * COUNTRY)
    x, y = rom.position(COUNTRY)
    cursor = [(CURSOR, struct.pack("<HH", 16 * x + 8, 16 * y + 8))]
    chunks = [list(range(c, min(c + PER_RUN, LAST))) for c in range(FIRST, LAST, PER_RUN)]
    runs = [{"patch": [(off(READING), struct.pack(f"<{len(ch) + 1}H", *ch, 0)),
                       (pointer, struct.pack("<H", READING & 0xFFFF))],
             "wram": cursor, "steps": STEPS, "shot": q.end_frame(STEPS, 0), "read": []} for ch in chunks]
    boot = q.TO_MAP[0]
    results = replay.replay(rom.path, boot, q.end_frame(boot), runs, extra_lua=LUA)
    ok = bad = 0
    for ch, res in zip(chunks, results):
        raw = res[-1].hex()
        log = [(int(raw[i:i + 4], 16), int(raw[i + 4:i + 6], 16), int(raw[i + 6:i + 10], 16))
               for i in range(0, len(raw) - 9, 10)]
        seen = {}
        for code, font, x_reg in log:
            seen.setdefault(code, (font, x_reg))
        for c in ch:
            want = (1, 32 * (c - 0x200)) if c >= 0x200 else (2, 16 * (c - 0x100))
            if seen.get(c) == want:
                ok += 1
            else:
                bad += 1
                print(f"  NG {c:#x}: {seen.get(c)} (want {want})")
    total = LAST - FIRST
    print(f"codes 0x{FIRST:X}-0x{LAST - 1:X}: glyph read at FONT16 ${FONT16:06X} / FONT8 ${FONT8:06X} as decoded "
          f"{ok}/{total}")
    print(f"{time.time() - t0:.0f} s")
    print("ALL OK" if not bad else f"{bad} mismatch(es)")
    raise SystemExit(1 if bad else 0)


if __name__ == "__main__":
    main()
