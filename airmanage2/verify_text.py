#!/usr/bin/env python3
"""Check the font (rom.Rom.glyph: Shift-JIS code -> glyph) against the game's glyph lookup in Mesen.

From the savestate before the secretary's first message (scenario 1, tools/replay.py) the game prints the
message one character at a time. On every call of the glyph lookup $00:B8DE the code in $4C is replaced by the
next code under test; then
- for 16x16 glyphs (hiragana, kanji) the lookup ends at $00:B9DF with $98 = 0 and the 32 font bytes copied to
  WRAM $0CE9 (each byte twice, 2bpp): they must be the FONT bytes at rom.glyph's offset;
- for 8x16 glyphs (symbols, digits, letters, katakana) $98 = 2 and $9A = index, and the character is drawn by
  $00:BC02, which writes tilemap entry `tile` (logged at $00:BC5E): it must be NARROW_BASE + 2 * index of rom.glyph.
All 713 codes of the font and a few outside it (they fall back to ■) are checked, 20 per run.

Usage: .venv/bin/python airmanage2/verify_text.py [--rom ROM]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "tools"))
import am2
from replay import replay
from rom import DEFAULT_ROM, FONT_NARROW_TILE0, Rom

PER_RUN = 20
PARAM = 0xF0F0
LUA = """
local codes = {%s}
local n, cur, first = 0, nil, 0
local function wr(a) return emu.read(a, emu.memType.snesWorkRam) end
local function lookup()
  if n == 0 then first = wr(0xF0F0) | wr(0xF0F1) << 8 end
  local k = first + n + 1
  if n >= %d or k > #codes then cur = nil return end
  cur = codes[k]
  n = n + 1
  emu.write(0x4C, cur & 0xFF, emu.memType.snesWorkRam)
  emu.write(0x4D, cur >> 8, emu.memType.snesWorkRam)
end
local function done()
  if cur == nil then return end
  local kind, idx = wr(0x98), wr(0x9A) | wr(0x9B) << 8
  local t = {}
  if kind == 0 then for i = 0, 63, 2 do t[#t + 1] = string.format("%%02x", wr(0x0CE9 + i)) end end
  REC_ADD(string.format("G %%04x %%d %%d %%s", cur, kind, idx, #t > 0 and table.concat(t) or "-"))
  if kind == 0 then cur = nil end
end
local function tile()
  if cur == nil then return end
  REC_ADD(string.format("T %%04x %%d", cur, emu.getState()["cpu.a"] & 0x3FF))
  cur = nil
end
for _, a in ipairs({0x00B8DE, 0x80B8DE}) do emu.addMemoryCallback(lookup, emu.callbackType.exec, a) end
for _, a in ipairs({0x00B9DF, 0x80B9DF}) do emu.addMemoryCallback(done, emu.callbackType.exec, a) end
for _, a in ipairs({0x00BC5E, 0x80BC5E}) do emu.addMemoryCallback(tile, emu.callbackType.exec, a) end
local reset0 = EXTRA_RESET
function EXTRA_RESET() reset0(); n = 0; cur = nil end
"""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    t = time.time()
    chars = rom.font_chars()
    codes = [c for _, c in chars] + [0x81A0, 0x837F, 0x889F, 0x9F40]
    font = rom.raw("FONT")
    runs = [{"wram": [(PARAM, am2.le16(i))], "shot": 600, "read": []} for i in range(0, len(codes), PER_RUN)]
    lua = LUA % (",".join(map(str, codes)), PER_RUN)
    res = replay(rom.path, am2.BOOT_FACE, am2.FACE_SAVE_FRAME, runs, extra_lua=am2.COLLECT_LUA + lua)
    got = {}
    for r in res:
        for rec in am2.parse(r[-1]):
            code = int(rec[1], 16)
            if rec[0] == "G":
                got.setdefault(code, {}).update(kind=int(rec[2]), index=int(rec[3]), bytes=rec[4])
            else:
                got.setdefault(code, {})["tile"] = int(rec[2])
    ok = 0
    groups = {}
    for code in codes:
        kind, idx, off = rom.glyph(code)
        g = got.get(code, {})
        if kind == 0:
            good = g.get("kind") == 0 and g.get("bytes") == font[off:off + 32].hex()
        else:
            good = g.get("kind") == 2 and g.get("index") == idx and g.get("tile") == off // 16 + FONT_NARROW_TILE0
        ok += good
        grp = next((gname for gname, c in chars if c == code), "outside")
        groups.setdefault(grp, [0, 0])
        groups[grp][0] += good
        groups[grp][1] += 1
        if not good:
            print(f"  NG {code:04X}: game {g}, rom kind {kind} index {idx} offset {off:#x}")
    print("glyphs: " + ", ".join(f"{gname} {a}/{b}" for gname, (a, b) in groups.items()))
    print(f"{'OK' if ok == len(codes) else f'{len(codes) - ok} mismatches'} ({time.time() - t:.0f} s)")
    sys.exit(0 if ok == len(codes) else 1)


if __name__ == "__main__":
    main()
