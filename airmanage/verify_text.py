#!/usr/bin/env python3
"""Check the full-width font lookup (rom.glyph_address) against the game in Mesen.

From the saved main screen (scenario 1) the VM is made to print a string of 100 full-width characters with
the game's printf ($1139, airmanage/tools/vm.py). On every call of the glyph lookup ($00:BCAA) the character
code in $4C is replaced by the next code under test, and at $00:BD79 the glyph address the game computed
($0CC0 bank, $0CC2 address) is logged. All 690 codes of the font (22 symbols, 10 digits, 52 letters,
83 hiragana, 86 katakana, 437 kanji) and a few codes outside it are checked, 100 per run.
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "tools"))
import vm
from replay import replay
from rom import DEFAULT_ROM, GLYPH_BASE, Rom, lorom

PRINT = 0x1139          # COMMON printf (fmt, ...) to the text window (the $1129 variant does not use $00:BCAA)
PER_RUN = 100
TEXT = vm.STUB + 0x10   # the string goes after the stub
LUA = """
local codes = {%s}
local first, n, cur, out = 0, 0, nil, {}
emu.addMemoryCallback(function()
  if not INJECTED then return end
  if n == 0 then first = emu.read(0x1FEC, emu.memType.snesWorkRam) * %d end
  local k = first + n + 1
  if k > #codes or n >= %d then cur = nil return end
  cur = codes[k]
  emu.write(0x4C, cur & 0xFF, emu.memType.snesWorkRam)
  emu.write(0x4D, cur >> 8, emu.memType.snesWorkRam)
  n = n + 1
end, emu.callbackType.exec, 0x00BCAA)
emu.addMemoryCallback(function()
  if cur == nil then return end
  local function w(a) return emu.read(a, emu.memType.snesWorkRam) | emu.read(a + 1, emu.memType.snesWorkRam) << 8 end
  out[#out + 1] = string.format("%%04x%%02x%%04x", cur, w(0x0CC0) & 0xFF, w(0x0CC2))
  cur = nil
end, emu.callbackType.exec, 0x00BD79)
local reset0 = EXTRA_RESET
function EXTRA_RESET() reset0(); n = 0; out = {} end
function EXTRA_SHOT() return table.concat(out) end
"""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    r = Rom(args.rom)
    t = time.time()
    # outside the font: 81A0, 889F, 9F40 fall back to ■; 837F (the katakana gap) uses the formula like the rest
    codes = r.font_codes() + [0x81A0, 0x837F, 0x889F, 0x9F40]
    text = ("あ" * PER_RUN).encode("cp932") + b"\0"
    stub = vm.stub([(PRINT, [TEXT])], vm.addresses(r.rev)["command_loop"])
    assert len(stub) <= TEXT - vm.STUB and TEXT + len(text) <= 0x1FEC
    runs = []
    for i in range((len(codes) + PER_RUN - 1) // PER_RUN):
        w = vm.command_inject(r.rev, [(PRINT, [TEXT])]) + [(TEXT, text), (0x1FEC, bytes([i]))]
        runs.append({"wram": w, "shot": 900, "read": []})
    lua = LUA % (",".join(map(str, codes)), PER_RUN, PER_RUN)
    res = replay(r.path, vm.boot(0), vm.MAIN_FRAME, runs, extra_lua=vm.boot_lua(r.rev) + vm.INJECT_LUA + vm.PRINTF_LUA + lua)
    got = {}
    for run in res:
        raw = run[-1] if run else b""
        for i in range(0, len(raw) - 4, 5):
            code = int.from_bytes(raw[i:i + 2], "big")
            got[code] = lorom(raw[i + 2], int.from_bytes(raw[i + 3:i + 5], "big"))
    ok = missing = 0
    for code in codes:
        a = r.glyph_address(code)
        want = a[0] if a else GLYPH_BASE["symbol"] + 64  # ■
        if code not in got:
            missing += 1
        elif got[code] == want:
            ok += 1
        else:
            print(f"  {code:04X}: game {got[code]:05X}, rom.py {want:05X}")
    print(f"glyph addresses: {ok}/{len(codes)} OK, {missing} not reached")
    bad = len(codes) - ok
    print(f"{'OK' if not bad else f'{bad} mismatches'} ({time.time() - t:.0f} s)")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
