#!/usr/bin/env python3
"""Check the world map decoding against the game (needs Mesen 2, about 2 minutes).

Plays as ジョアン up to the harbour office of Lisbon (tools/replay.py). ジョアン starts without a ship, so every round
first writes one ship into his fleet (fleet 1: $7E:41DD + 9; the first ship of NPC fleet 2) and then sets sail
(出航), and sails in one direction for a while. Checked:
- blocks: every map block the game decompresses ($C4:7DF6, block number at sp+4; 144 bytes at $7F:8000 when it
  returns) must equal rom.Rom.map_block;
- tilemap: the BG2 tilemap (VRAM word 0x5800, 32 x 32) must equal rom.Rom.map_tile for the 32 x 28 cells from the
  camera cell ($7E:23EE, $7E:23F0), up to the ring-buffer offset of the tilemap;
- tiles and palettes: VRAM words 0x2000-0x2FFF must equal rom.Rom.map_chars; CGRAM palette 2 must be one of the 4
  rows at MAP_PALETTE2 and palettes 3-5 one of the 8 rows of palette groups 0, 3, 4 (MAP_GROUPS_LISBON);
- ports (ROM only): every port's (x, y) must be the top-left cell of a port icon on the decoded map (cells BC-BF
  for the 100 trade ports, C0-C3 for the 30 supply ports).

Usage: .venv/bin/python daikoukai2/verify_maps.py [--rom ROM]
"""
import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "tools"))
sys.path.insert(0, HERE)
import replay
from rom import (
    DEFAULT_ROM,
    FLEET_SIZE,
    FLEETS,
    MAP_GROUPS_LISBON,
    MAP_PALETTE2,
    MAP_PALETTE_GROUPS,
    MAP_W,
    TRADE_PORTS,
    Rom,
    le16,
    wram,
)

# Lisbon: from the start position down to the quay and into the harbour office (the building with the anchor)
WALK = ("down:16 w10 down:16 w10 left:32 w10 left:32 w10 down:16 w10 down:16 w30 down:16 w60 "
        "left:8 w20 left:8 w20 down:8 w20 down:8 w20 down:8 w20 down:8 w20 right:8 w20 right:8 w20 "
        "down:8 w30 right:8 w30 right:8 w30 up:8 w60 up:8 w80")
# talk to the clerk -> 出航 -> confirm the warning about supplies -> at sea
SAIL = "w10 up:8 w20 up:8 w20 up:8 w20 a:10 w100 up+a:10 w200 a:10 w200 a:10 w300"
DIRECTIONS = ["left", "down", "up", "down+left", "up+left"]
CRUISE = 1500
PLAYER_SHIP = wram(FLEETS) + FLEET_SIZE + 9   # first ship of fleet 1, ジョアン's start fleet
CAMERA = 0x23EE
TILEMAP, CHARS = 0x5800 * 2, 0x2000 * 2

LUA = """
local pending=-1
emu.addMemoryCallback(function()
  local sp=emu.getState()["cpu.sp"]
  pending=emu.read(sp+4, emu.memType.snesMemory) | emu.read(sp+5, emu.memType.snesMemory) << 8
end, emu.callbackType.exec, 0xC47DF6)
emu.addMemoryCallback(function()
  if pending<0 then return end
  local out={}
  for i=0,143 do out[#out+1]=string.format("%02x", emu.read(0x7F8000+i, emu.memType.snesMemory)) end
  emu.log("BLOCK " .. pending .. " " .. table.concat(out))
  pending=-1
end, emu.callbackType.exec, 0xC47E3B)
"""


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證世界地圖解碼")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    ship = rom.fleets()[2]["raw"][9:18]
    rounds = [([(0x7E0000 | PLAYER_SHIP, ship)], f"{SAIL} {d}:{CRUISE} w60") for d in DIRECTIONS]
    errors = 0
    blocks: dict[int, bytes] = {}
    data = rom.data
    palette_variants = {2: [data[MAP_PALETTE2 + 32 * k:][:32] for k in range(4)]}
    for p, g in zip((3, 4, 5), MAP_GROUPS_LISBON):
        palette_variants[p] = [data[MAP_PALETTE_GROUPS + 0x100 * g + 32 * k:][:32] for k in range(8)]
    for d, mem in zip(DIRECTIONS, replay.run(args.rom, replay.BOOT_TOWN + " " + WALK, rounds, lua=LUA)):
        vram, w = mem["vram"], mem["wram"]
        cx, cy = le16(w, CAMERA), le16(w, CAMERA + 2)
        tm = [le16(vram, TILEMAP + 2 * i) for i in range(1024)]
        want = {(x, y): rom.map_tile(x, y) for x in range(cx, cx + 32) for y in range(cy, cy + 28)}
        best = max(sum(tm[(y + dy) % 32 * 32 + (x + dx) % 32] == t for (x, y), t in want.items())
                   for dx in range(32) for dy in range(32))
        chars_ok = vram[CHARS:CHARS + 0x2000] == rom.map_chars()
        pals_ok = all(mem["cgram"][32 * p:32 * p + 32] in variants for p, variants in palette_variants.items())
        ok = best == len(want) and chars_ok and pals_ok
        errors += not ok
        print(f"[sail {d}] camera cell ({cx}, {cy}): BG2 tilemap {best}/{len(want)} cells = map_tile, "
              f"tiles {'OK' if chars_ok else 'NG'}, palettes 2-5 {'OK' if pals_ok else 'NG'}")
        for b, raw in re.findall(r"^BLOCK (\d+) ([0-9a-f]+)$", mem["log"], re.MULTILINE):
            blocks[int(b)] = bytes.fromhex(raw)
    bad = [b for b, raw in blocks.items() if raw != rom.map_block(b)]
    land = [b for b in blocks if any(blocks[b])]
    print(f"[blocks] {len(blocks) - len(bad)}/{len(blocks)} blocks decompressed by the game = map_block "
          f"({len(land)} with land)" + (f" NG {bad[:20]}" if bad else ""))
    errors += len(bad) + (not blocks)
    cells = rom.map_cells()
    bad_ports = []
    for p in rom.ports():
        icon = 0xBC if p["id"] < TRADE_PORTS else 0xC0
        got = [cells[(p["y"] + dy) * MAP_W + p["x"] + dx] for dy in (0, 1) for dx in (0, 1)]
        if got != [icon, icon + 1, icon + 2, icon + 3]:
            bad_ports.append(p["id"])
    print(f"[ports] {len(rom.ports()) - len(bad_ports)}/{len(rom.ports())} port coordinates are the top-left cell "
          f"of a port icon" + (f" NG {bad_ports}" if bad_ports else ""))
    errors += len(bad_ports)
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
