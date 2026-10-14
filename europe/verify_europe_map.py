#!/usr/bin/env python3
"""Check the Europe map of the menus (rom.EUROPE_*) against the game (needs Mesen 2, about 20 seconds).

Boot to the scenario list (tools/replay.py, one run) and read VRAM and CGRAM as the game left them:
  - BG2 tilemap (VRAM byte 0x2000, 32x32): rows 2-24, columns 1-30 must be Rom.europe_tilemap() and the rest 0;
  - BG2 tiles from tile EUROPE_TILE0 (VRAM byte 0x8000 + 32 * 0x20) must be LZ entry EUROPE_CHR;
  - CGRAM palette 2 must be one of the two ROM palettes EUROPE_PALETTES, and over 900 frames the 32-byte palettes
    the game DMAs to CGRAM ($420B write callback, bytes read at the DMA source) must include both (the game swaps
    them; colours 1-4, the sea);
  - the picture rendered from the dumped VRAM / CGRAM must equal Rom.europe_rgb() (drawn with the first palette)
    when palette 2 is the first one.

Usage: .venv/bin/python europe/verify_europe_map.py [--rom ROM]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
from replay import replay
from rom import (
    DEFAULT_ROM,
    EUROPE_CHR,
    EUROPE_H,
    EUROPE_PALETTES,
    EUROPE_TILE0,
    EUROPE_W,
    Rom,
    bgr555_rgb,
    draw_tile,
    le16,
)
from scenes import EVENTS_LUA, TITLE, events, save_frame

TILEMAP, CHR = 0x2000, 0x8000
X0, Y0 = 1, 2
LUA = EVENTS_LUA + """
emu.addMemoryCallback(function(addr, value)
  for ch = 0, 7 do
    if (value >> ch) & 1 == 1 then
      local b = 0x4300 + ch * 16
      if rd(b + 1) == 0x22 and rd(b + 5) + rd(b + 6) * 256 == 32 then
        local src = rd(b + 2) + rd(b + 3) * 256 + rd(b + 4) * 65536
        local p = "C" .. hex(src, 32)
        local seen = false
        for _, e in ipairs(EVENTS) do if e == p then seen = true end end
        if not seen then EVENTS[#EVENTS + 1] = p end
      end
    end
  end
end, emu.callbackType.write, 0x420B, 0x420B)
"""


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證選單的歐洲地圖")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    t0 = time.time()
    rom = Rom(args.rom)
    shots = replay(args.rom, TITLE, save_frame(TITLE),
                   [{"steps": "w900", "shot": 900, "read": [("vram", 0, 0x10000), ("cgram", 0, 512)]}],
                   extra_lua=LUA)
    want = [0] * 1024
    for i, w in enumerate(rom.europe_tilemap()):
        want[(Y0 + i // EUROPE_W) * 32 + X0 + i % EUROPE_W] = w
    tiles = rom.entry(EUROPE_CHR)
    roms = [rom.data[p:p + 32] for p in EUROPE_PALETTES]
    ok = True
    for vram, cgram, raw in shots:
        dmad = {bytes.fromhex(e[1:]) for e in events(raw)}
        words = [le16(vram, TILEMAP + 2 * i) for i in range(1024)]
        tm_same = sum(a == b for a, b in zip(words, want))
        chr_ok = vram[CHR + 32 * EUROPE_TILE0:CHR + 32 * EUROPE_TILE0 + len(tiles)] == tiles
        which = roms.index(cgram[0x40:0x60]) if cgram[0x40:0x60] in roms else None
        pal = {p: [bgr555_rgb(le16(cgram, 32 * p + 2 * i)) for i in range(16)] for p in range(8)}
        w, h = EUROPE_W * 8, EUROPE_H * 8
        shown = [(0, 0, 0)] * (w * h)
        for i in range(EUROPE_W * EUROPE_H):
            word = words[(Y0 + i // EUROPE_W) * 32 + X0 + i % EUROPE_W]
            draw_tile(shown, w, i % EUROPE_W * 8, i // EUROPE_W * 8, vram[CHR:], word, 8, pal)
        pic = shown == rom.europe_rgb()[2]
        print(f"[after 900 frames] tilemap {tm_same}/1024 words of the 32x32 BG2 screen = Rom.europe_tilemap at "
              f"({X0}, {Y0}); LZ entry {EUROPE_CHR} ({len(tiles)} bytes) at VRAM 0x{CHR + 32 * EUROPE_TILE0:04X}: "
              f"{chr_ok}; CGRAM palette 2 = "
              + (f"0x{EUROPE_PALETTES[which]:05X}" if which is not None else "NG")
              + f"; picture {w}x{h} from the dump = Rom.europe_rgb(): {pic}")
        both = all(r in dmad for r in roms)
        print(f"[palette DMAs] {len(dmad)} distinct 32-byte palettes DMA'd to CGRAM; both EUROPE_PALETTES among them: {both}")
        ok &= tm_same == 1024 and chr_ok and which is not None and (pic or which == 1) and both
    print(f"{'ALL OK' if ok else 'NG'} ({time.time() - t0:.0f} s)")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
