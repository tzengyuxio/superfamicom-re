#!/usr/bin/env python3
"""Check the horse names (rom.Rom.horse_name, templates, fixed and foreign names, owners' crowns) in Mesen.

When the player names a horse, the game checks the name against every horse it knows (~1500 calls of the name
routine $C5:5D4E). The savestate is taken at frame 16430 and three presses are played (a savestate at
16660 followed by one press does not start the check in replay; not looked into); the routine's result (pointer
in DP $00-$02, logged at each of its RTLs) is read for every call.
1. run 0 leaves the game alone: every (name word, name) pair the game makes from its own tables must equal
   rom.horse_name, and every word of racehorses 0-399, mares and stallions must be among them (racehorses
   400-423 have fixed names, covered by 2.);
2. the next runs replace the word of each call (argument at S+4) by the words under test: every template with
   owner n % 40 (crown before / after, templates > 0x315 alone), all fixed names (0x29), all foreign names (0x2A),
   256 two-template names (0x2C) and the fallback kinds (0x2B, 0x2D-0x3F).

Usage: .venv/bin/python winning/verify_horses.py [--rom ROM]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "tools"))
import wp
from replay import end_frame, replay
from rom import DEFAULT_ROM, FIXED_COUNT, FOREIGN_COUNT, TEMPLATE_COUNT, Rom, kana

BOOT = wp.NEW_GAME + wp.A200 * 35
STEPS = wp.A200.strip() + wp.A200 * 2              # the name check runs ~1500 calls within these presses
PER_RUN = 1000
RTLS = [0xC55DCB, 0xC55EB2, 0xC55ED5, 0xC55EF8, 0xC55F1B, 0xC55F41, 0xC55FBA, 0xC55FC9]
LUA = """
local words = {%s}
local n, cur = 0, nil
emu.addMemoryCallback(function()
  local sp = emu.getState()["cpu.sp"]
  local function rd(a) return emu.read(a, emu.memType.snesMemory, false) end
  if PARAM(4) == 1 then
    local k = (PARAM(0) | PARAM(1) << 8) + n + 1
    if n < (PARAM(2) | PARAM(3) << 8) and k <= #words then
      emu.write(sp + 4, words[k] & 0xFF, emu.memType.snesMemory)
      emu.write(sp + 5, words[k] >> 8, emu.memType.snesMemory)
      n = n + 1
    end
  end
  cur = rd(sp + 4) | rd(sp + 5) << 8
end, emu.callbackType.exec, 0xC55D4E)
local function done()
  if cur == nil then return end
  local function rd(a) return emu.read(a, emu.memType.snesMemory, false) end
  local d = emu.getState()["cpu.d"]
  local p = rd(d) | rd(d + 1) << 8 | rd(d + 2) << 16
  REC_ADD(string.format("N %%04x %%s", cur, MEMSTR(p, 9)))
  cur = nil
end
for _, a in ipairs({%s}) do emu.addMemoryCallback(done, emu.callbackType.exec, a) end
local reset0 = EXTRA_RESET
function EXTRA_RESET() reset0(); n = 0; cur = nil end
"""


def test_words() -> list[int]:
    out = [(n % 40) << 10 | n for n in range(TEMPLATE_COUNT)]
    out += [0x29 << 10 | n for n in range(FIXED_COUNT)]
    out += [0x2A << 10 | n for n in range(FOREIGN_COUNT)]
    out += [0x2C << 10 | (n * 37) & 0x3FF for n in range(256)]
    out += [k << 10 | 5 for k in [0x2B] + list(range(0x2D, 0x40))]
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證馬名解碼")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    t0 = time.time()
    words = test_words()
    lua = wp.COLLECT_LUA + LUA % (",".join(map(str, words)), ",".join(map(str, RTLS)))
    runs = [{"steps": STEPS, "shot": 740, "read": []}]
    for start in range(0, len(words), PER_RUN):
        n = min(PER_RUN, len(words) - start)
        runs.append({"steps": STEPS, "shot": 740, "read": [],
                     "wram": [(wp.WRAM_PARAM, bytes([start & 255, start >> 8, n & 255, n >> 8, 1]))]})
    res = replay(rom.path, BOOT, end_frame(BOOT), runs, extra_lua=lua)
    errors = 0
    for i, r in enumerate(res):
        got = [(int(x[1], 16), kana(wp.unhex(x[2])).strip()) for x in wp.parse(r[-1]) if x[0] == "N"]
        if i == 0:
            seen = {w for w, _ in got}
            bad = [(f"{w:04X}", s, rom.horse_name(w)) for w, s in got if s != rom.horse_name(w)]
            print(f"[game] {len(got) - len(bad)}/{len(got)} name calls of the game = rom.horse_name, "
                  f"{len(seen)} distinct words" + (f" (NG {bad[:5]})" if bad else ""))
            # racehorses 400-423 (the special horses, fixed names) are not checked by the game; the forced
            # runs cover every fixed name
            tables = [h["name_word"] for h in rom.horses()[:400] + rom.mares() + rom.stallions() if h["used"]]
            missing = [f"{w:04X}" for w in tables if w not in seen]
            print(f"[game] {len(tables) - len(missing)}/{len(tables)} name words of racehorses 0-399, mares and "
                  "stallions were among them" + (f" (missing {missing[:8]})" if missing else ""))
            errors += len(bad) + len(missing)
        else:
            start = (i - 1) * PER_RUN
            want = words[start:start + PER_RUN]
            got = got[:len(want)]
            bad = [(f"{w:04X}", s, rom.horse_name(w)) for (w, s), x in zip(got, want)
                   if w != x or s != rom.horse_name(w)]
            short = len(want) - len(got)
            print(f"[forced {start}-{start + len(want) - 1}] {len(got) - len(bad)}/{len(want)} = rom.horse_name"
                  + (f" (NG {bad[:5]})" if bad else "") + (f"; {short} words not reached" if short else ""))
            errors += len(bad) + short
    print(f"time {time.time() - t0:.0f}s")
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
