#!/usr/bin/env python3
"""Check the text codes and the font layout (rom.FONT16 / FONT8, rom.Rom.glyph16 / glyph8) against the game.

Scenario 189 is played to 情報 → 武将 "どの国の武将を" (savestate, tools/sequences.py). Each run patches the
message "どの武将の情報を\\nご覧になりますか？" ($1F:CE06, PRG ROM) with 16 codes under test (8 + newline + 8),
opens 冀州's officer list (which prints that message) and logs, for every code given to $00:8D60, the glyph offset
X the routine reads the font with ($00:8DC0 LDA $03:8000,X for 16x16 glyphs, $00:8DEF LDA $04:8800,X for 8x16).
Every code 0x100-0x5FF must be printed, in order, and read its glyph at FONT16 + 32 (code - 0x200) or
FONT8 + 16 (code - 0x100).

The glyph -> character table (data/charset.txt) is a human reading of the glyphs (tools/charset_sheet.py draws
them side by side); the game cannot check it. The 224 names and their readings are a cross-check.

Usage: .venv/bin/python yokoyama/verify_text.py [--rom ROM]
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
from rom import DEFAULT_ROM, FONT8, FONT16, TEXT_NEWLINE, Rom, off

MESSAGE = 0x1FCE06                  # "どの武将の情報を\nご覧になりますか？"
FIRST, LAST = 0x100, 0x600
PER_RUN = 16
LIST_STEPS = "a:10 w100 a:10 w100 a:10 w150"   # country -> panel -> list with the message
LIST_SHOT = 330

LUA = """
local log={}
local code=-1
for _,a in ipairs({0x008D60, 0x808D60}) do
  emu.addMemoryCallback(function() code=emu.getState()["cpu.a"] & 0xFFFF end, emu.callbackType.exec, a)
end
for _,p in ipairs({{0x008DC0, 1}, {0x808DC0, 1}, {0x008DEF, 2}, {0x808DEF, 2}}) do
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
    ap = argparse.ArgumentParser(description="驗證字碼與字型位址（$00:8D60 讀字型的位置）")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    t0 = time.time()
    rom = Rom(args.rom)
    old = rom.codes_at(MESSAGE)
    assert rom.text(old) == "どの武将の情報を\nご覧になりますか？", rom.text(old)
    _, x, y = q.HOME[0]
    chunks = [list(range(c, min(c + PER_RUN, LAST))) for c in range(FIRST, LAST, PER_RUN)]
    runs = []
    for ch in chunks:
        codes = ch[:8] + [TEXT_NEWLINE] + ch[8:]
        codes += [0x200] * (len(old) - len(codes))       # pad with spaces to the original length
        runs.append({"patch": [(off(MESSAGE), struct.pack(f"<{len(codes)}H", *codes))],
                     "wram": q.cursor_patch(x, y), "steps": LIST_STEPS, "shot": LIST_SHOT, "read": []})
    boot = q.TO_PICK_COUNTRY[0]
    results = replay.replay(rom.path, boot, q.end_frame(boot), runs, extra_lua=q.cursor_lua(0) + LUA)
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
