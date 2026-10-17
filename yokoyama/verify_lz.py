#!/usr/bin/env python3
"""Check the decompressor (rom.lz) against the game's $01:F8FE (rom.Rom.lz_entry; Rev 1 $01:F903).

Both scenarios are played from power-on (savestate at frame 20) to the map of the first month (tools/sequences.py
TO_MAP). Every call of the decompressor logs its source (A = address, X = bank) and, when it returns
(rom.Rom.lz_return: the PLP before its RTL, Rev 0 $01:F99F), the size it wrote to $7E:8000 and a checksum of the
output (sum of (i + 1) * byte, mod 2^32). Every distinct stream must decompress with rom.lz to the same size and
checksum.

Usage: .venv/bin/python yokoyama/verify_lz.py [--rom ROM]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
sys.path.insert(0, os.path.join(HERE, "tools"))
import replay
import sequences as q
from rom import DEFAULT_ROM, Rom, le16, lz, off

LUA = """
local log={}
local src=-1
for _,a in ipairs({ENTRY, ENTRY | 0x800000}) do
  emu.addMemoryCallback(function()
    local s=emu.getState(); src=(s["cpu.x"] & 0xFF) * 65536 + (s["cpu.a"] & 0xFFFF)
  end, emu.callbackType.exec, a)
end
for _,a in ipairs({RETURN, RETURN | 0x800000}) do
  emu.addMemoryCallback(function()
    if src<0 then return end
    local rd=function(i) return emu.read(i, emu.memType.snesMemory, false) end
    local n=rd(src) | rd(src + 1) << 8
    local h=0
    for i=0,n-1 do h=(h + (i + 1) * emu.read(0x8000 + i, emu.memType.snesWorkRam, false)) & 0xFFFFFFFF end
    log[#log+1]=string.format("%06x%04x%08x", src, n, h)
    src=-1
  end, emu.callbackType.exec, a)
end
function EXTRA_RESET() log={} end
function EXTRA_SHOT() local s=table.concat(log); log={}; if s=="" then s="00" end; return s end
"""


def checksum(data: bytes) -> int:
    return sum((i + 1) * b for i, b in enumerate(data)) & 0xFFFFFFFF


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證 LZSS 解壓（$01:F8FE）")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    t0 = time.time()
    rom = Rom(args.rom)
    runs = []
    for k in (0, 1):  # from power-on (savestate at frame 20), so the title and menu streams are logged too
        steps = q.TO_MAP[k].replace("w1200", "w1190", 1)
        runs.append({"steps": steps, "shot": q.end_frame(steps, 0) + 20, "read": []})
    lua = f"ENTRY={rom.lz_entry}\nRETURN={rom.lz_return}\n" + LUA
    results = replay.replay(rom.path, "w10", 20, runs, extra_lua=lua)
    seen = {}
    for res in results:
        raw = res[-1].hex()
        for i in range(0, len(raw) - 17, 18):
            seen[int(raw[i:i + 6], 16)] = (int(raw[i + 6:i + 10], 16), int(raw[i + 10:i + 18], 16))
    bad = 0
    for src, (n, h) in sorted(seen.items()):
        data, _ = lz(rom.data, src)
        ok = len(data) == n == le16(rom.data, off(src)) and checksum(data) == h
        bad += not ok
        if not ok:
            print(f"  NG ${src:06X}: game {n} bytes {h:08x}, rom.lz {len(data)} bytes {checksum(data):08x}")
    print("sources: " + " ".join(f"${a:06X}({n})" for a, (n, _) in sorted(seen.items())))
    print(f"streams decompressed by the game: {len(seen)}, equal {len(seen) - bad}/{len(seen)}")
    print(f"{time.time() - t0:.0f} s")
    print("ALL OK" if not bad and seen else "no stream logged" if not seen else f"{bad} mismatch(es)")
    raise SystemExit(1 if bad or not seen else 0)


if __name__ == "__main__":
    main()
