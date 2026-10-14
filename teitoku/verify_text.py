#!/usr/bin/env python3
"""Check the two-byte text code -> font glyph rule (rom.Rom.text, glyph g = code - 0x8140) against the game (needs
Mesen 2, about 4 minutes).

Scenario 3 as 日本軍, 資料 -> 艦船 -> 予備艦船 lists 赤城 first; its row is printed by vprintf $06:BD03 with
"%-8s\\n%-12s" (type name, ship name). Each run patches 赤城's name string (14 bytes at the ship's name pointer)
with ESC K and five two-byte codes, opens the list, and records the glyphs the font copy $01:F06B reads (source
$23:8000 + 32 g; glyphs 1024-1035 are at $24:8000, the next LoROM bank) while that row is printed. They must be
the glyphs of 正規空母 followed by the five predicted glyphs. All 1036 glyphs are tested: 0x8140 + g, or the
escape 0x9140 + k for the codes 0x8200 + 0x100 k (low byte 0); and codes 0x854D-0x913F must draw glyph 0. The unpatched run must give 赤城.
(Which character each glyph is, data/charset.txt, comes from matching the glyph bitmaps; see its header.)

Usage: .venv/bin/python teitoku/verify_text.py [--rom ROM]
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
from sequences import DATA_MENU, TO_SCENARIOS, end_frame, new_game

SC, SHIP = 3, 2  # 赤城
TO_LIST = (f"{TO_SCENARIOS} {new_game(SC, 0)} {DATA_MENU} down:10 w30 down:10 w30 down:10 w30 a:10 w100 "
           "down:10 w30 down:10 w30")
SHIP_ROW = 0x06FDE1
PER_RUN = 5
EXTRA = """
local active, seq = false, {}
local TARGET = @TARGET@
function EXTRA_RESET() active = false; seq = {} end
local function rd(a) return emu.read(a, emu.memType.snesMemory, false) end
emu.addMemoryCallback(function()
  local sp = emu.getState()["cpu.sp"]
  local fmt = rd(sp + 4) | rd(sp + 5) << 8 | rd(sp + 6) << 16
  local va = rd(sp + 8) | rd(sp + 9) << 8
  active = fmt == @ROW@ and (rd(va + 4) | rd(va + 5) << 8 | rd(va + 6) << 16) == TARGET and #seq == 0
end, emu.callbackType.exec, 0x06BD03)
emu.addMemoryCallback(function()
  if not active or #seq >= 16 then return end
  local sp = emu.getState()["cpu.sp"]
  local src = rd(sp + 4) | rd(sp + 5) << 8 | rd(sp + 6) << 16
  seq[#seq + 1] = ((src >> 16) - 0x23) * 0x400 + ((src & 0xFFFF) - 0x8000) // 32  -- LoROM: 1024 glyphs per bank
end, emu.callbackType.exec, 0x01F06B)
function EXTRA_SHOT()
  local out = {}
  for i = 1, 16 do out[#out + 1] = string.format("%04x", seq[i] or 0xFFFF) end
  return table.concat(out)
end
"""


def code_of(g: int) -> int:
    c = 0x8140 + g
    return 0x9140 + ((c - 0x8200) >> 8) if c & 0xFF == 0 else c


def glyphs(raw: bytes) -> list[int]:
    """Glyphs of the two-byte codes of a string (single bytes and ESC sequences skipped)."""
    out, i = [], 0
    while i < len(raw) and raw[i]:
        c = raw[i]
        if 0x81 <= c <= 0x9F or c >= 0xE0:
            code = c << 8 | raw[i + 1]
            if code >= 0x9140:
                code = 0x8200 + ((code - 0x9140) << 8)
            out.append(code - 0x8140 if code <= 0x854C else 0)
            i += 2
        else:
            i += 2 if c == 0x1B else 1
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="文字碼與字型對應與遊戲比對")
    ap.add_argument("--rom", default=R.DEFAULT_ROM)
    args = ap.parse_args()
    t0 = time.time()
    rom = R.Rom(args.rom)
    img = rom.scenario_image(SC)
    ship = rom.ships(SC)[SHIP]
    name_ptr = int.from_bytes(img[R.SHIPS + R.SHIP_SIZE * SHIP:R.SHIPS + R.SHIP_SIZE * SHIP + 3], "little")
    at = R.lorom(name_ptr)
    size = rom.data.index(0, at) + 1 - at
    assert size == 2 + 2 * PER_RUN + 2, size
    type_ptr = rom.ptr(R.SHIP_TYPE_NAMES + 3 * ship["type"])
    prefix = glyphs(rom.data[R.lorom(type_ptr):])
    tests = [list(range(g, min(g + PER_RUN, R.GLYPH_COUNT))) for g in range(0, R.GLYPH_COUNT, PER_RUN)]
    blank_codes = [0x854D, 0x8641, 0x8A80, 0x8FFF, 0x913F]
    runs = [{"steps": "a:10 w300", "shot": 330, "read": []}]  # unpatched
    for t in tests:
        raw = b"\x1bK" + b"".join(code_of(g).to_bytes(2, "big") for g in t)
        runs.append({"patch": [(at, raw.ljust(size, b"\0"))], "steps": "a:10 w300", "shot": 330, "read": []})
    raw = b"\x1bK" + b"".join(c.to_bytes(2, "big") for c in blank_codes)
    runs.append({"patch": [(at, raw.ljust(size, b"\0"))], "steps": "a:10 w300", "shot": 330, "read": []})
    extra = EXTRA.replace("@TARGET@", str(name_ptr)).replace("@ROW@", str(rom.string_addr(SHIP_ROW)))
    res = replay(args.rom, TO_LIST, end_frame(TO_LIST), runs, extra_lua=extra)
    seqs = [[int(r[0][k:k + 2].hex(), 16) for k in range(0, 32, 2)] for r in res]
    seqs = [[g for g in s if g != 0xFFFF] for s in seqs]
    errors = 0
    ok = seqs[0] == prefix + glyphs(rom.data[at:])
    errors += not ok
    print(f"[unpatched] {rom.text(rom.data, at)}: glyphs {seqs[0]} " + ("OK" if ok else "NG"))
    bad = [t[0] for t, s in zip(tests, seqs[1:-1]) if s != prefix + t]
    errors += len(bad)
    print(f"[glyphs] {R.GLYPH_COUNT - sum(len(t) for t in tests if t[0] in bad)}/{R.GLYPH_COUNT} glyphs drawn as "
          f"predicted (code 0x8140 + g, escape 0x9140 + k for low byte 0)" + (f" (NG from {bad[:10]})" if bad else ""))
    for t, s in zip(tests, seqs[1:-1]):
        if t[0] in bad:
            print("   ", t, s[len(prefix):])
    ok = seqs[-1] == prefix + [0] * len(blank_codes)
    errors += not ok
    print(f"[blank] codes {', '.join(f'{c:04X}' for c in blank_codes)} draw glyph 0: " + ("OK" if ok else f"NG {seqs[-1]}"))
    print(f"({time.time() - t0:.0f} s)")
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
