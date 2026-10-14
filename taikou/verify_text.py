#!/usr/bin/env python3
"""Check the text code -> font glyph rules (rom.Rom.code_glyph, kana1_glyph) against the game (needs Mesen 2,
about 6 minutes).

At the battle of 桶狭間 the 情報 command opens 木下藤吉郎's info screen (tools/sequences.TO_INFO); his name is
printed by vprintf $C6:2E8B with "%s%s" ($C6:FE87) from name table entry 0. Each run patches the given name
(7 bytes at ROM 0x1C324) with three text codes. A read trace on the font (ROM 0x170000, $D7:0000 or its mirror
$57:0000) records the glyphs read while that printf runs: they must be 木 下 followed by the glyphs rom.Rom
predicts for the patched codes. The unpatched run must read 木 下 藤 吉 郎.
- two-byte codes 0x8140 + g for every glyph g (a code with low byte 00 written as its escape 0x9140 + k):
  glyph g up to 0x748; codes 0x8889-0x893F draw glyph 0 (blank), so glyphs 0x749-0x7FF are reachable only
  through the escapes and the one-byte kana;
- one-byte kana 0xA6-0xDD (dialogue text): the hiragana of the second kana set (glyphs 0x748-0x797), and with a
  following DE / DF (dakuten / handakuten) the next glyph / the one after it.
(Which character each glyph is, data/charset.txt, comes from bitmap matching, see the file's header.)

Usage: .venv/bin/python taikou/verify_text.py [--rom ROM] [--quick]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
sys.path.insert(0, os.path.join(HERE, "tools"))
from replay import replay
from rom import DEFAULT_ROM, GLYPH_COUNT, NAMES, Rom, encode_glyph
from sequences import TO_INFO, expand
from verify_persons import SAVE_AT, SHOT, STEPS

GIVEN = NAMES + 7
EXTRA = """
local inname, seq, last = false, {}, -1
function EXTRA_RESET() inname = false; seq = {}; last = -1 end
function EXTRA_SHOT()
  local out = {}
  for i = 1, math.min(#seq, 12) do out[#out + 1] = string.format("%04x", seq[i]) end
  for i = #out + 1, 12 do out[#out + 1] = "ffff" end
  return table.concat(out)
end
local function rd(a) return emu.read(a, emu.memType.snesMemory, false) end
emu.addMemoryCallback(function()
  local sp = emu.getState()["cpu.sp"]
  inname = (rd(sp + 4) + rd(sp + 5) * 256 + rd(sp + 6) * 65536) == 0xC6FE87
end, emu.callbackType.exec, 0xC62E8B, 0xC62E8B)
local function font(addr)
  if not inname then return end
  local g = (addr & 0xFFFF) // 32
  if g ~= last then seq[#seq + 1] = g; last = g end
end
emu.addMemoryCallback(font, emu.callbackType.read, 0xD70000, 0xD7FFFF)
emu.addMemoryCallback(font, emu.callbackType.read, 0x570000, 0x57FFFF)
"""


def collapse(gs: list[int]) -> list[int]:
    """Consecutive reads of the same glyph count once (the trace sees one glyph per run of reads)."""
    return [g for i, g in enumerate(gs) if i == 0 or g != gs[i - 1]]


def cases(rom: Rom, quick: bool) -> list[tuple[str, bytes, list[int]]]:
    """(kind, given-name bytes, glyphs the game should read for them)."""
    out = []
    groups = [list(range(g, min(g + 3, GLYPH_COUNT))) for g in range(0, GLYPH_COUNT, 3)]
    for gs in groups[::10] if quick else groups:
        out.append(("two-byte", b"".join(encode_glyph(g) for g in gs), [rom.code_glyph(encode_glyph(g)) for g in gs]))
    letters = [c for c in range(0xA6, 0xDE) if c != 0xB0]
    for i in range(0, len(letters), 3):
        cs = letters[i:i + 3]
        out.append(("one-byte", bytes(cs), [rom.kana1_glyph(c) for c in cs]))
    marked = [(c, 0xDE) for c in range(0xB6, 0xC5)] + [(c, 0xDE) for c in range(0xCA, 0xCF)] \
        + [(c, 0xDF) for c in range(0xCA, 0xCF)]
    for i in range(0, len(marked), 3):
        ms = marked[i:i + 3]
        out.append(("one-byte + mark", b"".join(bytes(m) for m in ms), [rom.kana1_glyph(*m) for m in ms]))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證文字碼與字型 glyph 的對應")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--quick", action="store_true", help="only every 10th group of three two-byte codes")
    args = ap.parse_args()
    t0 = time.time()
    rom = Rom(args.rom)
    tests = cases(rom, args.quick)
    runs = [{"steps": STEPS, "shot": SHOT, "read": []}]
    runs += [{"patch": [(GIVEN, raw.ljust(7, b"\0"))], "steps": STEPS, "shot": SHOT, "read": []} for _, raw, _ in tests]
    shots = replay(args.rom, expand(TO_INFO), SAVE_AT, runs, extra_lua=EXTRA)
    seqs = [[int.from_bytes(s[0][2 * i:2 * i + 2], "big") for i in range(12)] for s in shots]
    seqs = [[g for g in s if g != 0xFFFF] for s in seqs]
    surname = rom.glyph_codes(rom.data[NAMES:NAMES + 7])
    full = surname + rom.glyph_codes(rom.data[GIVEN:GIVEN + 7])
    errors = 0
    ok = seqs[0] == full
    print(f"[unpatched] glyphs read for 木下藤吉郎: {seqs[0]} {'==' if ok else '!='} {full}")
    errors += not ok
    for kind in ("two-byte", "one-byte", "one-byte + mark"):
        sel = [(raw, want, got) for (k, raw, want), got in zip(tests, seqs[1:]) if k == kind]
        bad = [(raw.hex(), got[len(surname):]) for raw, want, got in sel if got != collapse(surname + want)]
        n = sum(len(want) for _, want, _ in sel)
        print(f"[{kind}] {len(sel) - len(bad)}/{len(sel)} runs ({n} codes) read the glyphs rom.Rom predicts"
              + (f" (NG {bad[:5]})" if bad else ""))
        errors += len(bad)
    print(f"time {time.time() - t0:.0f} s")
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
