#!/usr/bin/env python3
"""Check the battle maps (rom.Rom.map_words / map_chr / map_terrain / map_palette) against the game (needs Mesen 2,
about a minute).

For each scenario (savestate replay at the scenario list, tools/replay.py): select it, 0 players, Y, until the
battle map is shown (computer vs computer). Then
  - BG2 tilemap (VRAM byte 0x2000, 64x64 words in four 32x32 screens, the map at (1, 1)) must equal
    Rom.map_words(m); the game changes some cells at run time (captured cities, built or blown bridges), so
    differing cells are only accepted on 都市 / 橋 / 川 terrain and are counted;
  - BG2 tiles (VRAM byte 0x8000) must equal Rom.map_chr(m) for every tile the map's metatiles fill;
  - the terrain bytes the game copies to WRAM $7E:40C2 (MVN at $00:006C, read at $00:006F right after it) must
    equal LZ entry MAP_TERRAIN + m, so their low nibbles are Rom.map_terrain(m);
  - CGRAM palette 2 must be Rom.map_palette(m) or the palette 32 bytes after it: on the map the game DMAs the
    WRAM buffers $7E:0D77 and $7E:0D97 to palette 2 by turns every 20 frames (the two differ only in colours 8
    and 13, a blink); the buffers must hold the two ROM palettes. The palettes DMA'd to CGRAM straight from the
    map palette area are listed.

Usage: .venv/bin/python europe/verify_maps.py [--rom ROM]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
from replay import replay
from rom import DEFAULT_ROM, MAP_SIZE, MAP_TERRAIN, SCENARIO_COUNT, TERRAIN_NAMES, Rom
from scenes import EVENTS_LUA, TITLE, ZERO_PLAYERS, events, length, save_frame, scenario

TILEMAP = 0x2000
CHR = 0x8000
TERRAIN_WRAM = 0x40C2
BLINK = 0x0D77                           # two 32-byte palette buffers, DMA to palette 2 by turns
ACCEPT = {TERRAIN_NAMES.index(t) for t in ("都市", "橋", "川")}

LUA = EVENTS_LUA + """
local pending = false
emu.addMemoryCallback(function()
  local s = emu.getState()
  if rd(0x6D) == 0x7E and s["cpu.y"] == 0x40C2 then pending = true end
end, emu.callbackType.exec, 0x00006C, 0x00006C)
emu.addMemoryCallback(function()
  if pending then pending = false; EVENTS[#EVENTS + 1] = "T" .. mem_hex("snesWorkRam", 0x40C2, 1600) end
end, emu.callbackType.exec, 0x00006F, 0x00006F)
emu.addMemoryCallback(function(addr, value)
  for ch = 0, 7 do
    if (value >> ch) & 1 == 1 then
      local b = 0x4300 + ch * 16
      local src = rd(b + 2) + rd(b + 3) * 256 + rd(b + 4) * 65536
      if rd(b + 1) == 0x22 and src >= 0xC14600 and src < 0xC14A00 then
        EVENTS[#EVENTS + 1] = string.format("P%06X", src)
      end
    end
  end
end, emu.callbackType.write, 0x420B, 0x420B)
"""


def screen_words(vram: bytes) -> list[int]:
    """The 40x40 map words of the 64x64 BG2 tilemap (four 32x32 screens), map at (1, 1)."""
    out = []
    for y in range(1, MAP_SIZE + 1):
        for x in range(1, MAP_SIZE + 1):
            a = TILEMAP + (y // 32 * 2 + x // 32) * 2048 + (y % 32 * 32 + x % 32) * 2
            out.append(vram[a] | vram[a + 1] << 8)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證戰場地圖（tilemap、tile、地形、調色盤）")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    t0 = time.time()
    rom = Rom(args.rom)
    runs = []
    for k in range(SCENARIO_COUNT):
        st = scenario(k + 1) + " " + ZERO_PLAYERS
        runs.append({"steps": st, "shot": length(st),
                     "read": [("vram", 0, 0x10000), ("cgram", 0x40, 32), ("wram", BLINK, 64)]})
    shots = replay(args.rom, TITLE, save_frame(TITLE), runs, extra_lua=LUA)
    bad = []
    for k, (vram, cg, blink, raw) in enumerate(shots):
        m = rom.block(k)[1]
        ev = events(raw)
        words, want, terrain = screen_words(vram), rom.map_words(m), rom.map_terrain(m)
        diff = [i for i in range(len(want)) if words[i] != want[i]]
        odd = [i for i in diff if terrain[i] not in ACCEPT]
        chr_ = rom.map_chr(m)
        tiles = [t for t in range(1024) if any(chr_[32 * t:32 * t + 32])]
        chr_bad = [t for t in tiles if vram[CHR + 32 * t:CHR + 32 * t + 32] != chr_[32 * t:32 * t + 32]]
        tcopy = [bytes.fromhex(e[1:]) for e in ev if e[0] == "T"]
        terr_ok = bool(tcopy) and tcopy[0] == rom.entry(MAP_TERRAIN + m)
        base = rom.map_palette_offset(m)
        pal = "base" if cg == rom.data[base:base + 32] else "+32" if cg == rom.data[base + 32:base + 64] else "NG"
        blink_ok = blink == rom.data[base:base + 64]
        dma = sorted({int(e[1:], 16) & 0x3FFFFF for e in ev if e[0] == "P"})
        print(f"[map {m}] scenario {k + 1}: tilemap {1600 - len(diff)}/1600 cells = Rom.map_words "
              f"({len(diff) - len(odd)} differ on 都市/橋/川, {len(odd)} elsewhere), tiles {len(tiles) - len(chr_bad)}"
              f"/{len(tiles)} = Rom.map_chr, terrain copy = LZ {MAP_TERRAIN + m}: {terr_ok}, CGRAM palette 2 = "
              f"{pal} (0x{base:05X}), blink buffers = ROM base / +32: {blink_ok}, palettes DMA'd from the area: {[hex(d) for d in dma]}")
        if odd or chr_bad or not terr_ok or pal == "NG" or not blink_ok:
            bad.append(m)
    print(f"{'ALL OK' if not bad else f'NG maps {bad}'} ({time.time() - t0:.0f} s)")
    raise SystemExit(1 if bad else 0)


if __name__ == "__main__":
    main()
