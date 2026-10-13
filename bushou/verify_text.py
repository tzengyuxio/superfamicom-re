#!/usr/bin/env python3
"""Check the text decode (rom.Rom.codes, the font address of every glyph code) against the game (needs Mesen 2,
about 3.5 minutes).

On the daimyo selection map of scenario 1, A on 織田 opens "織田信長でよろしいですか". The game draws each kanji
from the 16x16 font at FONT + 32 * (code - 0x8000) (ROM banks $10-$11). Nobunaga's given name (name record
119, ROM 0x10ED3, 7 bytes) is patched with three glyph codes per run, so that all 868 codes 0x8140-0x84A3 are
drawn once; codes with low byte 00 (0x8200 / 0x8300 / 0x8400) cannot be stored and are written as their escape
0x85F0 / 0x85F1 / 0x85F2. A read trace records which font glyphs the game reads; after 織田 they must be
exactly rom.Rom.codes() of the patched bytes. The unpatched run must read 織田信長.
(Which character each glyph is, data/charset.txt, was matched by eye: see export.py's font.png.)

Usage: .venv/bin/python bushou/verify_text.py [--rom ROM] [--quick]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
from replay import replay
from rom import DEFAULT_ROM, FONT, GLYPH_COUNT, TEXT_BASE, ZERO_ESCAPE, Rom

STEPS = "w900 start:10 w300 a:10 w200 a:10 w200 a:10 w200 a:10 w200 up:10 w60 a:10 w200"  # daimyo map
SAVE_AT = 2470
GIVEN_AT = 0x10ED3  # name record 119 of scenario 1 (0x10580 + 20 * 119) + 7
EXTRA_LUA = """
local glyphs={}
EXTRA_RESET=function() glyphs={} end
EXTRA_SHOT=function() return table.concat(glyphs) end
emu.addMemoryCallback(function(addr, value)
  local off=(addr>>16 & 0x7F)*0x8000 + (addr & 0x7FFF) - %(font)d
  if off>=0 and off %% 32 == 0 then glyphs[#glyphs+1]=string.format("%%04x", 0x8000+off//32) end
end, emu.callbackType.read, 0x10D800, 0x11FFFF)
"""


def encode(code: int) -> bytes:
    if code & 0xFF == 0:
        code = ZERO_ESCAPE + (code >> 8) - 0x82
    return code.to_bytes(2, "big")


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證文字碼與字型位址")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--quick", action="store_true", help="only the first 30 groups and the escapes")
    args = ap.parse_args()
    t0 = time.time()
    rom = Rom(args.rom)
    codes = [TEXT_BASE + g for g in range(GLYPH_COUNT)]
    groups = [codes[k:k + 3] for k in range(0, len(codes), 3)]
    if args.quick:
        groups = groups[:30] + [[0x8200, 0x8300, 0x8400]]
    run = {"steps": "w10 a:10", "shot": 250, "read": []}
    raws = [b"".join(encode(c) for c in grp) + b"\0" for grp in groups]
    runs = [dict(run)] + [dict(run, patch=[(GIVEN_AT, raw)]) for raw in raws]
    res = replay(args.rom, STEPS, SAVE_AT, runs, extra_lua=EXTRA_LUA % {"font": FONT})
    read = [[int.from_bytes(r[-1][k:k + 2], "big") for k in range(0, len(r[-1]), 2)] for r in res]
    oda = rom.codes(rom.data[GIVEN_AT - 7:GIVEN_AT])
    nobunaga = rom.codes(rom.data[GIVEN_AT:GIVEN_AT + 7])
    errors = 0
    ok = read[0] == oda + nobunaga
    print(f"[natural] 織田信長 reads glyphs {' '.join(f'{c:04X}' for c in read[0])}: {'OK' if ok else 'NG'}"
          f" ({rom.text(rom.data[GIVEN_AT - 7:GIVEN_AT])}{rom.text(rom.data[GIVEN_AT:GIVEN_AT + 7])})")
    errors += not ok
    bad = [grp for grp, raw, got in zip(groups, raws, read[1:]) if got != oda + rom.codes(raw) or rom.codes(raw) != grp]
    n = sum(len(g) for g in groups)
    print(f"[glyphs] {n - sum(len(g) for g in bad)}/{n} codes: the game reads font glyph FONT + 32 * (code - 0x8000)"
          + (f" (NG {[[hex(c) for c in g] for g in bad[:10]]})" if bad else ""))
    esc = [grp for grp in groups if any(c & 0xFF == 0 for c in grp)]
    print(f"[escape] 85F0/85F1/85F2 -> 8200/8300/8400: {'OK' if not any(g in bad for g in esc) else 'NG'}")
    errors += len(bad)
    print(f"{time.time() - t0:.0f} s")
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
