#!/usr/bin/env python3
"""Check rom.lz against the game's LZSS decoder.

For each scenario the game is played from power-on to the map (ruler row 0, 普). Every call of the decoder $00:A527
(A = bank, Y = address of the stream) is logged with the bytes written to WMDATA $2180 after it: the first `size`
bytes (the LE32 at stream + 4) must equal rom.lz of that stream. One Mesen per scenario (4 processes).

Usage: .venv/bin/python tenbu/verify_lz.py [--rom ROM] [--scenario 0-3]
"""
import argparse
import os
import struct
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
sys.path.insert(0, os.path.join(HERE, "tools"))
import sequences as q
from mesen import Mesen
from replay import end_frame, presses
from rom import DEFAULT_ROM, LZ_DECODER, REGION_STREAM, SCENARIO_YEARS, Rom, lz

LUA = """
local P={%(presses)s}
local W={%(writes)s}
local f=0
local cur=nil
emu.addEventCallback(function()
  local inp={}
  for _,p in ipairs(P) do if f>=p[1] and f<p[1]+p[3] then inp[p[2]]=true end end
  emu.setInput(inp,0)
end, emu.eventType.inputPolled)
local function flush() if cur then emu.log(table.concat(cur)); cur=nil end end
emu.addMemoryCallback(function()
  local s=emu.getState()
  flush()
  cur={string.format("S %%02x%%04x ", s["cpu.a"] & 0xFF, s["cpu.y"])}
end, emu.callbackType.exec, %(decoder)d)
emu.addMemoryCallback(function(a, v) if cur then cur[#cur+1]=string.format("%%02x", v) end end,
  emu.callbackType.write, 0x2180)
emu.addEventCallback(function()
  f=f+1
  for _,e in ipairs(W) do
    if e[1]==f then emu.write(0x200,e[2],emu.memType.snesWorkRam); emu.write(0x201,e[3],emu.memType.snesWorkRam) end
  end
  if f==%(end)d then flush(); emu.log("END"); emu.breakExecution() end
end, emu.eventType.endFrame)
"""


def run(rom: Rom, k: int) -> int:
    steps, writes = q.split(q.TO_SCENARIOS + " " + q.to_rulers(k) + " w200 " + q.card(0) + " " + q.START, 10)
    lua = LUA % {"presses": ",".join(f'{{{f},"{b}",{h}}}' for f, b, h in presses(steps, 10)),
                 "writes": ",".join(f"{{{f},{x},{y}}}" for f, x, y in writes),
                 "decoder": LZ_DECODER, "end": end_frame(steps, 10)}
    with Mesen(rom.path) as m:
        m.run(lua, 600)
        log = m.log(1 << 27)
    calls = [line.split(" ") for line in log.splitlines() if line.startswith("S ")]
    known = {REGION_STREAM: "中国全土図"}
    for j, o in enumerate(rom.scenario_streams(k)):
        known[o] = f"劇本 {j}"
    bad, sizes, seen = 0, 0, set()
    for call in calls:
        a = int(call[1], 16)
        o = (a >> 16) * 0x8000 + (a & 0xFFFF) - 0x8000
        got = bytes.fromhex(call[2]) if len(call) > 2 else b""
        size = struct.unpack_from("<I", rom.data, o + 4)[0]
        want = lz(rom.data, o)[0]
        seen.add(o)
        sizes += size
        if got[:size] != want:
            bad += 1
            print(f"  NG {SCENARIO_YEARS[k]} stream {o:06X}: {len(got)} bytes written, first difference at "
                  f"{next((i for i, (x, y) in enumerate(zip(got, want)) if x != y), min(len(got), size))}")
    names = sorted({known[o] for o in seen if o in known})
    print(f"scenario {SCENARIO_YEARS[k]}: {len(calls) - bad}/{len(calls)} decoder calls equal ({len(seen)} distinct "
          f"streams, {sizes} bytes; {', '.join(names)})")
    return bad + (not calls)


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證 LZSS 解壓（攔解壓程式的 WMDATA 輸出）")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--scenario", type=int, choices=(0, 1, 2, 3))
    args = ap.parse_args()
    t0 = time.time()
    if args.scenario is None:
        procs = [subprocess.Popen([sys.executable, __file__, "--rom", args.rom, "--scenario", str(k)])
                 for k in range(4)]
        errors = sum(p.wait() != 0 for p in procs)
        print(f"{time.time() - t0:.0f} s")
        print("ALL OK" if not errors else "mismatch(es)")
        raise SystemExit(1 if errors else 0)
    raise SystemExit(1 if run(Rom(args.rom), args.scenario) else 0)


if __name__ == "__main__":
    main()
