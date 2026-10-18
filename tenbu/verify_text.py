#!/usr/bin/env python3
"""Check the text encoding and the font addresses against the game's glyph drawing.

Uses the ruler-card runs of verify_persons.py (scenario 190). Each run puts 3 test codes into the name of the
faction-0 ruler (and, for the half-width runs, 7 test bytes into the reading) and logs, after the click:

  - every tile code $00:A0CA gets: must be rom.Rom.text_codes / half_codes of the test text (SJIS code -> glyph
    0x6B + index in the kanji list $06:8180, values below 0x48 = glyph numbers)
  - the font address of each tile: $00:A47B (1bpp, tile >= 0x120) leaves it in $14-$16 at $00:A4AD, $00:A086
    (4bpp, tile < 0x120) at its RTS $00:A106. Must be FONT + 0x2400 + 8 (t - 0x120) / FONT + 32 t (rom.FONT)

Covered: the 1113 codes of the kanji list (371 runs), the 59 kana / ｰ / space of readings (9 runs) and the
digits 0-9 the card draws first (tiles 0x120-0x133, addresses only). Not covered: the glyph numbers 0x00-0x47 (the
4bpp button glyphs; in a name they do not go through $00:A0CA) and / (not converted in readings).

Usage: .venv/bin/python tenbu/verify_text.py [--rom ROM]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "tools"))
import sequences as q
from rom import DEFAULT_ROM, FONT, HALF_ORDER, KANJI_COUNT, Rom
from verify_persons import card_runs

ADDR_LUA = """
local addrs={}
local function dp(o) local d=emu.getState()["cpu.d"]; return emu.read(d+o, emu.memType.snesWorkRam, false) end
local cur=0
emu.addMemoryCallback(function() cur=emu.getState()["cpu.a"] & 0xFFFF end, emu.callbackType.exec, 0x00A47B)
emu.addMemoryCallback(function()
  addrs[#addrs+1]=string.format("%04x%02x%02x%02x", cur, dp(0x16), dp(0x15), dp(0x14))
end, emu.callbackType.exec, 0x00A4AD)
emu.addMemoryCallback(function()
  local c=dp(0)+256*dp(1)
  if (c & 0xC000)==0x8000 then
    addrs[#addrs+1]=string.format("%04x%02x%02x%02x", c, dp(0x16), dp(0x15), dp(0x14))
  end
end, emu.callbackType.exec, 0x00A106)
function EXTRA_START() addrs={} end
function ADDR_TAKE() local s=table.concat(addrs); addrs={}; if s=="" then s="00" end; return s end
"""


LEAD = list(range(0x8120, 0x8134))   # the card first draws the digits 0-9 (half-width 0-9, for the number sprites)


def cpu(o: int) -> int:
    return (o // 0x8000) << 16 | 0x8000 + o % 0x8000


def font_addr(code: int) -> int:
    t = code & 0x3FFF
    return cpu(FONT + 0x2400 + 8 * (t - 0x120)) if t >= 0x120 else cpu(FONT + 32 * t)


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證文字編碼與字型位址（君主卡）")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    t0 = time.time()
    rom = Rom(args.rom)
    base = rom.person_raw(0, rom.faction(0, 0)["君主"])
    kanji = rom.kanji_list()
    tests = [b"".join(kanji[i:i + 3]) for i in range(0, KANJI_COUNT, 3)]
    # readings: the kana, ｰ and space (digits and / are not converted in readings: they come out as ｰ)
    half = [c.encode("cp932") for c in HALF_ORDER[10:] if c != "/"]
    halves = [b" " + b"".join(half[i:i + 7]).ljust(7, b" ") for i in range(0, len(half), 7)]
    records = [t + base[6:] for t in tests] + [base[:6] + h + base[14:] for h in halves]
    results = card_runs(rom, 0, records, [], extra=ADDR_LUA, take='CODES_TAKE() .. " " .. ADDR_TAKE()')
    bad = n_codes = n_addr = 0
    for i, (raw, (codes, addrs)) in enumerate(zip(records, results)):
        got = q.codes(codes)
        if got[:20] == LEAD:
            got = got[20:]
        want = rom.text_codes(raw[:6]) + rom.half_codes(raw[6:14])
        ok = got[:len(want)] == want
        n_codes += len(want) if ok else 0
        pairs = [(addrs[j] << 8 | addrs[j + 1], addrs[j + 2] << 16 | addrs[j + 3] << 8 | addrs[j + 4])
                 for j in range(0, len(addrs) - 4, 5)]
        seen = {c: a for c, a in pairs}
        miss = [c for c in want + LEAD if seen.get(c) != font_addr(c)]
        n_addr += len(want) + len(LEAD) - len(miss)
        if not ok or miss:
            bad += 1
            print(f"  NG run {i} {raw[:14].hex()}: codes {'OK' if ok else [hex(c) for c in got[:len(want)]]}"
                  f" addresses {[(hex(c), hex(seen.get(c, 0))) for c in miss[:4]]}")
    total = sum(len(rom.text_codes(r[:6]) + rom.half_codes(r[6:14])) for r in records)
    print(f"tile codes equal {n_codes}/{total}, font addresses equal {n_addr}/{total + len(LEAD) * len(records)}"
          f" ({len(records)} runs)")
    print(f"{time.time() - t0:.0f} s")
    print("ALL OK" if not bad else f"{bad} mismatch(es)")
    raise SystemExit(1 if bad else 0)


if __name__ == "__main__":
    main()
