#!/usr/bin/env python3
"""Check the two-byte text code -> font glyph rule (rom.code_glyph: glyph g = code - 0x8140, escape 0x9140 + k for
the codes with low byte 0, 0x8981-0x913F draw glyph 0; 0x8140 itself is a space the game skips without reading
the font) against the game (needs Mesen 2, about 4 minutes).

Scenario 0 as 日本, 作戦 -> 人事 -> 海軍提督 lists admirals 0-6 on its first page. Each run patches the names of
admirals 0-5 in WRAM ($7E:2634 + 17 i, 14 bytes) with six two-byte codes each, opens the list, and records the
glyph every character draw reads from the font (at $D3:0E6B the word at $91,S is 32 g, the offset of the glyph in
bank $EB, file 0x2B0000). The glyphs of each patched name must appear in the log as one run, in list order.
All 1216 glyphs are tested, and a run of codes 0x8981-0x913F must draw glyph 0. The unpatched run must draw the
glyphs Rom.text decodes for the six admirals. (Which character each glyph is, data/charset.txt, comes from matching
the glyph bitmaps; see its header.)

Usage: .venv/bin/python teitoku2/verify_text.py [--rom ROM]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
sys.path.insert(0, os.path.join(HERE, "tools"))
import rom as R
from replay import replay
from sequences import PERSONNEL, TO_SCENARIOS, end_frame, expand, new_game

TO_MAIN = f"{TO_SCENARIOS} {new_game(0)}"
STEPS = expand(PERSONNEL + " a:10 w300")
NAMES, PER_NAME, NAME_SIZE = 6, 6, 14
GLYPH_SP = 0x91
MAX_LOG = 600
BLANK_CODES = [0x8981, 0x8A41, 0x8C40, 0x8FFF, 0x9041, 0x913F]
EXTRA = """
local log = {}
function EXTRA_RESET() log = {} end
local function rd(a) return emu.read(a, emu.memType.snesMemory, false) end
emu.addMemoryCallback(function()
  if #log >= @MAX@ then return end
  local sp = emu.getState()["cpu.sp"]
  log[#log + 1] = string.format("%04x", rd(sp + @SP@) | rd(sp + @SP@ + 1) << 8)
end, emu.callbackType.exec, @GLYPH@)
function EXTRA_SHOT() return table.concat(log) .. string.rep("ffff", @MAX@ - #log) end
"""


def code_of(g: int) -> int:
    c = 0x8140 + g
    return 0x9140 + ((c - 0x8200) >> 8) if c & 0xFF == 0 else c


def name_glyphs(raw: bytes) -> list[int]:
    out, i = [], 0
    while i < len(raw) and raw[i]:
        c = raw[i]
        if 0x81 <= c <= 0x9F or c >= 0xE0:
            out.append(R.code_glyph(c << 8 | raw[i + 1]))
            i += 2
        else:
            i += 1
    return out


def contains_in_order(log: list[int], parts: list[list[int]]) -> bool:
    i = 0
    for p in parts:
        while i + len(p) <= len(log) and log[i:i + len(p)] != p:
            i += 1
        if i + len(p) > len(log):
            return False
        i += len(p)
    return True


def main() -> None:
    ap = argparse.ArgumentParser(description="文字碼與字型對應與遊戲比對")
    ap.add_argument("--rom", default=R.DEFAULT_ROM)
    args = ap.parse_args()
    t0 = time.time()
    rom = R.Rom(args.rom)
    img = rom.wram_image(0)
    base = [bytes(img[R.ADMIRALS + R.ADMIRAL_SIZE * i:][:NAME_SIZE]) for i in range(NAMES)]
    glyphs = list(range(R.GLYPH_COUNT))
    chunk = NAMES * PER_NAME
    tests = [[glyphs[k + PER_NAME * j:k + PER_NAME * (j + 1)] for j in range(NAMES)] for k in range(0, len(glyphs), chunk)]
    tests = [[t for t in test if t] for test in tests]
    runs = [{"steps": STEPS, "shot": end_frame(STEPS, 0) + 60, "read": []}]
    for test in tests:
        wram = [(R.ADMIRALS + R.ADMIRAL_SIZE * j, b"".join(code_of(g).to_bytes(2, "big") for g in t).ljust(NAME_SIZE, b"\0"))
                for j, t in enumerate(test)]
        runs.append({"wram": wram, "steps": STEPS, "shot": end_frame(STEPS, 0) + 60, "read": []})
    blank = b"".join(c.to_bytes(2, "big") for c in BLANK_CODES).ljust(NAME_SIZE, b"\0")
    runs.append({"wram": [(R.ADMIRALS, blank)], "steps": STEPS, "shot": end_frame(STEPS, 0) + 60, "read": []})
    extra = (EXTRA.replace("@MAX@", str(MAX_LOG)).replace("@SP@", str(GLYPH_SP))
             .replace("@GLYPH@", str(rom.off["code"]["glyph"])))
    res = replay(args.rom, expand(TO_MAIN), end_frame(expand(TO_MAIN)), runs, extra_lua=extra)
    logs = []
    for (raw,) in res:
        v = [int(raw[k:k + 2].hex(), 16) for k in range(0, len(raw), 2)]
        logs.append([x // 32 for x in v if x != 0xFFFF])
    errors = 0
    want = [name_glyphs(b) for b in base]
    ok = contains_in_order(logs[0], want)
    errors += not ok
    print(f"[unpatched] admirals 0-{NAMES - 1} ({'、'.join(rom.text(b, katakana=True) for b in base)}) drawn with the "
          f"glyphs Rom.text decodes: " + ("OK" if ok else "NG"))
    # code 0x8140 (glyph 0, the full-width space) is skipped without reading the font
    drawn = [[[g for g in t if g] for t in test] for test in tests]
    bad = [test[0][0] for test, d, log in zip(tests, drawn, logs[1:-1]) if not contains_in_order(log, d)]
    errors += len(bad)
    n_bad = sum(sum(len(t) for t in test) for test in tests if test[0][0] in bad)
    print(f"[glyphs] {R.GLYPH_COUNT - n_bad}/{R.GLYPH_COUNT} glyphs drawn as predicted (code 0x8140 + g, escape "
          f"0x9140 + k for low byte 0, 0x8140 drawn as a space without a font read; {len(tests)} runs)"
          + (f" (NG runs from glyph {bad[:10]})" if bad else ""))
    for test, log in zip(tests, logs[1:-1]):
        if test[0][0] in bad:
            print(f"    want {test}\n    drew {log}")
    ok = contains_in_order(logs[-1], [[0] * len(BLANK_CODES)])
    errors += not ok
    print(f"[blank] codes {', '.join(f'{c:04X}' for c in BLANK_CODES)} draw glyph 0: " + ("OK" if ok else "NG"))
    print(f"({time.time() - t0:.0f} s)")
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
