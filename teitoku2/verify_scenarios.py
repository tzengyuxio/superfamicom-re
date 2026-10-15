#!/usr/bin/env python3
"""Check the scenario tables (rom.Rom.loader / block / wram_image, dates and titles) against the game (needs
Mesen 2, about 4 minutes per ROM).

One savestate at the scenario menu; one run per scenario (0-9) starts a new game as 日本 (tools/sequences.new_game)
and plays on to the main screen. Lua hooks record
1. WRAM bank $7E when the scenario loader has made its last copy (Rom.loader_end): every block the loader copies
   (19 ranges, 0x6A6D bytes) must equal Rom.wram_image(sc) byte for byte;
2. the arguments of the first vsprintf ($D3:19FA) with the confirmation format ("シナリオ%s ... ヨロシイデスカ?":
   the title pointer must be entry sc of the title table) and with the date format of the main screen
   ("%4d;%2d<%2d,": year, month, day must be Rom.dates()[sc]);
3. the date of the running game at $7E:21A7 (year - 1941, month, day) when the run ends.

Usage: .venv/bin/python teitoku2/verify_scenarios.py [--rom ROM] [--scenarios 0,1,...]
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
from sequences import TO_SCENARIOS, end_frame, expand, new_game

CONFIRM_FMT, DATE_FMT = "confirm", "date"
DATE_WRAM = 0x21A7  # year - 1941, month, day of the running game

EXTRA = """
local RANGES = {@RANGES@}
local FMTS = {@FMTS@}
local dump, recs = nil, {}
function EXTRA_RESET() dump = nil; recs = {} end
local function rd(a) return emu.read(a, emu.memType.snesMemory, false) end
emu.addMemoryCallback(function()
  if dump then return end
  local t = {}
  for _, r in ipairs(RANGES) do
    for a = r[1], r[1] + r[2] - 1 do t[#t + 1] = string.format("%02x", emu.read(a, emu.memType.snesWorkRam, false)) end
  end
  dump = table.concat(t)
end, emu.callbackType.exec, @END@)
emu.addMemoryCallback(function()
  local sp = emu.getState()["cpu.sp"]
  local fmt = rd(sp + 8) | rd(sp + 9) << 8 | rd(sp + 10) << 16
  local va = rd(sp + 12) | rd(sp + 13) << 8 | rd(sp + 14) << 16
  for k, f in ipairs(FMTS) do
    if f == fmt and recs[k] == nil then
      local u = {}
      for i = 0, 7 do u[#u + 1] = string.format("%02x", rd(va + i)) end
      recs[k] = table.concat(u)
    end
  end
end, emu.callbackType.exec, @VSPRINTF@)
function EXTRA_SHOT()
  local out = {dump or ""}
  for k = 1, #FMTS do out[#out + 1] = recs[k] or string.rep("ff", 8) end
  return table.concat(out)
end
"""


def main() -> None:
    ap = argparse.ArgumentParser(description="劇本資料表與遊戲比對")
    ap.add_argument("--rom", default=R.DEFAULT_ROM)
    ap.add_argument("--scenarios", default=",".join(map(str, range(R.SCENARIO_COUNT))))
    args = ap.parse_args()
    t0 = time.time()
    rom = R.Rom(args.rom)
    scs = list(map(int, args.scenarios.split(",")))
    ranges = sorted({(b["dst"], b["size"]) for b in rom.blocks})
    fmts = [rom.format_addr(CONFIRM_FMT), rom.format_addr(DATE_FMT)]
    lua = (EXTRA.replace("@RANGES@", ",".join(f"{{{d},{n}}}" for d, n in ranges))
           .replace("@FMTS@", ",".join(map(str, fmts))).replace("@END@", str(rom.loader_end))
           .replace("@VSPRINTF@", str(rom.off["code"]["vsprintf"])))
    boot = expand(TO_SCENARIOS)
    runs = []
    for sc in scs:
        steps = expand(new_game(sc))
        runs.append({"steps": steps, "shot": end_frame(steps, 0) + 60, "read": [("wram", DATE_WRAM, 3)]})
    res = replay(args.rom, boot, end_frame(boot), runs, extra_lua=lua)
    total = sum(n for _, n in ranges)
    titles, dates = rom.title_ptrs(), rom.dates()
    bad = 0
    printed = 0
    for sc, (cur, out) in zip(scs, res):
        errors = []
        dump, recs = out[:total], out[total:]
        img = rom.wram_image(sc)
        want = b"".join(bytes(img[d:d + n]) for d, n in ranges)
        diff = sum(x != y for x, y in zip(dump, want)) if len(dump) == total else total
        if diff:
            pos, where = 0, []
            for d, n in ranges:
                k = [i for i in range(n) if pos + i < len(dump) and dump[pos + i] != want[pos + i]]
                if k:
                    where.append(f"{d:04x}+{k[0]:x}({len(k)})")
                pos += n
            errors.append(f"WRAM {diff} bytes differ at " + " ".join(where))
        conf, date = recs[:8], recs[8:16]
        if conf == b"\xff" * 8 or int.from_bytes(conf[0:3], "little") != titles[sc]:
            errors.append(f"title pointer {conf[:3][::-1].hex()}")
        got = (1941 + cur[0], cur[1], cur[2])
        if got != tuple(dates[sc]):
            errors.append(f"WRAM date {got} != {dates[sc]}")
        if date != b"\xff" * 8:
            printed += 1
            got = (R.le16(date, 0), R.le16(date, 2), R.le16(date, 4))
            if got != tuple(dates[sc]):
                errors.append(f"printed date {got} != {dates[sc]}")
        bad += bool(errors)
        print(f"[scenario {sc} {rom.titles()[sc]['title']} {'-'.join(map(str, dates[sc]))}] WRAM {len(ranges)} blocks "
              f"{total - diff}/{total} bytes equal; title, date: " + ("OK" if not errors else "NG " + "; ".join(errors)))
    print(f"{len(scs) - bad}/{len(scs)} scenarios OK; main-screen date printed in {printed} of them "
          f"({time.time() - t0:.0f} s)")
    print("ALL OK" if not bad else f"{bad} problem(s)")
    raise SystemExit(1 if bad else 0)


if __name__ == "__main__":
    main()
