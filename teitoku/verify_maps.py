#!/usr/bin/env python3
"""Check the world map and the sea map (rom.Rom.world_* / sea_block) against the game (needs Mesen 2, about
2 minutes).

1. World map: scenario 3, the map shown under the scenario description. VRAM $9800 (317 tiles) must equal the
   LZ stream at WORLD_TILES, VRAM $E200-$E5BF (tilemap rows 8-22) the 32 x 15 words at WORLD_TILEMAP, CGRAM row 7
   the palette at WORLD_PALETTE.
2. Sea map: on the main screen of scenario 3 (日本軍) 作戦 -> 移動 draws the 3 x 3 blocks around the first fleet
   ($0A:B6xx). Each run moves the fleet (WRAM fleet +0 / +2) to another position and records the LZ streams the
   game decompresses ($00:9896); they must be the entries 186 + Rom.sea_block(bx, by) of the blocks
   (x // 120 + dx, y // 120 + dy), dx, dy in -1..1, inside the 32 x 16 grid. CGRAM row 7 must again be
   WORLD_PALETTE.

Usage: .venv/bin/python teitoku/verify_maps.py [--rom ROM]
"""
import argparse
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
sys.path.insert(0, os.path.join(HERE, "tools"))
import rom as R
from replay import replay
from sequences import TO_SCENARIOS, end_frame, new_game

TO_DESCRIPTION = "down:10 w30 down:10 w30 a:10 w200 up:10 w100 a:10 w300 a:10 w300 a:10 w300 a:10 w300"
TO_MAIN = f"{TO_SCENARIOS} {new_game(3, 0)}"
POSITIONS = [(bx * R.SEA_BLOCK + 60, by * R.SEA_BLOCK + 60) for by in (0, 2, 5, 8, 11, 13, 15)
             for bx in (0, 3, 6, 10, 14, 20, 27, 31)]
EXTRA = """
local srcs = {}
function EXTRA_RESET() srcs = {} end
local function rd(a) return emu.read(a, emu.memType.snesMemory, false) end
emu.addMemoryCallback(function()
  if #srcs < 16 then srcs[#srcs + 1] = string.format("%06x", rd(0x56) | rd(0x57) << 8 | rd(0x58) << 16) end
end, emu.callbackType.exec, 0x009896)
function EXTRA_SHOT()
  local out = table.concat(srcs)
  return out .. string.rep("ffffff", 16 - #srcs)
end
"""


def world(rom_path: str) -> int:
    rom = R.Rom(rom_path)
    pal = b"".join(c.to_bytes(2, "little") for c in rom.palette(R.WORLD_PALETTE))
    tiles = rom.world_tiles()
    (vt, vm, cg), = replay(rom_path, TO_SCENARIOS, end_frame(TO_SCENARIOS), [
        {"steps": TO_DESCRIPTION, "shot": end_frame(TO_DESCRIPTION, 0) + 100,
         "read": [("vram", 0x9800, len(tiles)), ("vram", 0xE200, 2 * R.WORLD_W * R.WORLD_H), ("cgram", 0xE0, 32)]}])
    ok = [vt == tiles, vm == rom.world_tilemap(), cg == pal]
    print(f"[world] tiles {len(tiles) // 32} {'OK' if ok[0] else 'NG'}, tilemap {R.WORLD_W}x{R.WORLD_H} "
          f"{'OK' if ok[1] else 'NG'}, palette {'OK' if ok[2] else 'NG'}")
    return ok.count(False)


def sea(rom_path: str) -> int:
    rom = R.Rom(rom_path)
    pal = b"".join(c.to_bytes(2, "little") for c in rom.palette(R.WORLD_PALETTE))
    runs = [{"wram": [(R.FLEETS, x.to_bytes(2, "little") + y.to_bytes(2, "little"))], "steps": "a:10 w300",
             "shot": 330, "read": [("cgram", 0xE0, 32)]} for x, y in POSITIONS]
    res = replay(rom_path, TO_MAIN, end_frame(TO_MAIN), runs, extra_lua=EXTRA)
    entry_of = {rom.ptr(rom.off["entries"] + 3 * e): e for e in range(R.ENTRY_COUNT)}
    bad, land = [], 0
    for (x, y), (cg, srcs) in zip(POSITIONS, res):
        got = [entry_of.get(int.from_bytes(srcs[k:k + 3], "big")) for k in range(0, len(srcs), 3)]
        got = sorted(e for e in got if e is not None and e >= R.SEA_FIRST_ENTRY)
        bx, by = x // R.SEA_BLOCK, y // R.SEA_BLOCK
        want = sorted(R.SEA_FIRST_ENTRY + rom.sea_block(bx + dx, by + dy) for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                      if 0 <= bx + dx < R.SEA_W and 0 <= by + dy < R.SEA_H)
        land += sum(e > R.SEA_FIRST_ENTRY for e in want)
        if got != want or cg != pal:
            bad.append((bx, by, got, want))
    print(f"[sea] {len(POSITIONS) - len(bad)}/{len(POSITIONS)} positions: blocks loaded = Rom.sea_block "
          f"({land} land blocks among them), CGRAM row 7 = WORLD_PALETTE" + (f" (NG {bad[:3]})" if bad else ""))
    return len(bad)


def main() -> None:
    ap = argparse.ArgumentParser(description="地圖與遊戲比對")
    ap.add_argument("--rom", default=R.DEFAULT_ROM)
    ap.add_argument("--part", choices=["world", "sea"], help="只跑一部分（Mesen 一個 process 只能開一次）")
    args = ap.parse_args()
    if args.part:
        raise SystemExit(world(args.rom) if args.part == "world" else sea(args.rom))
    t0 = time.time()
    errors = 0
    for part in ("world", "sea"):
        p = subprocess.run([sys.executable, os.path.abspath(__file__), "--rom", args.rom, "--part", part],
                           check=False, capture_output=True, text=True)
        print("\n".join(ln for ln in p.stdout.splitlines() if ln.startswith(("[world]", "[sea]"))) or p.stderr[-2000:])
        errors += p.returncode != 0
    print(f"({time.time() - t0:.0f} s)")
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
