#!/usr/bin/env python3
"""Check the local map, its chips and palette, and the 中国全土図 against the game.

1. Ruler list of scenario 190 (savestate there): the 868 tiles at VRAM 0x8020 must equal those of the 中国全土図
   stream (rom.REGION_STREAM), except that the game repaints some colour-1 pixels with colours 8-15 (the colouring
   rule is not decoded), and CGRAM palette 7 must be rom.REGION_PALETTE.
2. The map of scenario 190 (savestate on the first day; NMI is on again there): each run holds B on one or two of
   the scroll arrows (◀ ▶ ▲ ▼) of the map window for a while, so the window is redrawn at many places. Every byte
   the map reader $00:BCEE loads (at $00:BD20: x = $00, y = $02, A & FF) must be rom.MAP[270 y + x]; every BG tile
   with palette 7 in the window's tilemap (VRAM 0x7000, tiles at 0x8000) must be the chip (rom.MAP_CHIPS + 32 v) of
   its map cell (the cell offset found by vote, modulo the 32 x 32 tilemap), except the window's 2-pixel left
   border; BG palette 7 (CGRAM 0xE0-0xFF) must be rom.MAP_PALETTE.

Usage: .venv/bin/python tenbu/verify_maps.py [--rom ROM]
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
from rom import (
    DEFAULT_ROM,
    MAP,
    MAP_CHIPS,
    MAP_H,
    MAP_PALETTE,
    MAP_W,
    REGION_H,
    REGION_PALETTE,
    REGION_STREAM,
    REGION_W,
    Rom,
    decode_tile4,
    lz,
)

TILEMAP, CHR = 0x7000, 0x8000    # BG of the map window (VRAM bytes): 32 x 32 tilemap, its tiles
# pointer on the arrows of the scrollbar thumbs of the map window as it opens (scenario 190, ruler row 0); holding
# B scrolls by 2 cells per step until the thumb moves away from the pointer
ARROWS = {"right": (166, 214), "left": (149, 213), "down": (236, 104), "up": (239, 100)}
# (arrow, hold frames) pairs per run; every run starts from the first-day view
MOVES = [[]] + [[(a, h)] for a in ("right", "left", "down", "up") for h in (100, 300, 900)] + [
    [(h, 300), (v, 300)] for h in ("right", "left") for v in ("down", "up")] + [
    [(h, 900), (v, 900)] for h in ("right", "left") for v in ("down", "up")]

READ_LUA = """
local log={}
local function dp(o) local d=emu.getState()["cpu.d"]; return emu.read(d+o, emu.memType.snesWorkRam, false) end
emu.addMemoryCallback(function()
  local a=emu.getState()["cpu.a"] & 0xFF
  log[#log+1]=string.format("%02x%02x%02x%02x", dp(1), dp(0), dp(2), a)
end, emu.callbackType.exec, 0x00BD20)
function EXTRA_RESET() POINTER_RESET(); log={} end
function EXTRA_SHOT() local s=table.concat(log); log={}; if s=="" then s="00" end; return s end
"""


def cpu(o: int) -> int:
    return (o // 0x8000) << 16 | 0x8000 + o % 0x8000


def region(rom: Rom) -> int:
    boot = q.TO_SCENARIOS + " " + q.to_rulers(0) + " w200"
    boot_r, save, steps, plua = q.prepare(boot, ["w10"])
    tiles = lz(rom.data, REGION_STREAM)[0]
    res = replay.replay(rom.path, boot_r, save, [{"steps": steps[0], "shot": 10, "wram": [q.mail(0)],
                                                  "read": [("vram", 0x8020, len(tiles)), ("cgram", 0xE0, 32)]}],
                        extra_lua=plua + "function EXTRA_RESET() POINTER_RESET() end", nmi=q.FRAME_HOOK)
    vram, cgram = res[0]
    n = len(tiles) // 32
    same = recoloured = 0
    for t in range(n):
        a, b = decode_tile4(tiles[32 * t:32 * t + 32]), decode_tile4(vram[32 * t:32 * t + 32])
        if a == b:
            same += 1
        elif all(x == y or (x == 1 and 8 <= y <= 15) for x, y in zip(a, b)):
            recoloured += 1     # colour-1 pixels repainted with 8-15 at run time (rule not decoded)
    pal = cgram == rom.data[REGION_PALETTE:REGION_PALETTE + 32]
    print(f"中国全土図: {same}/{n} tiles equal ({REGION_W} x {REGION_H}), {recoloured} equal but for colour 1 -> 8-15, "
          f"{n - same - recoloured} differ; palette {'OK' if pal else 'NG'}")
    return (same + recoloured != n) + (not pal)


def local_map(rom: Rom) -> int:
    boot = (q.TO_SCENARIOS + " " + q.to_rulers(0) + " w200 " + q.card(0) + " " + q.START)
    steps = []
    for moves in MOVES:
        st = ""
        for arrow, hold in moves:
            x, y = ARROWS[arrow]
            st += f" p:{x}:{y} {q.NUDGE} b:{hold} w100"
        steps.append((st + " w60").strip())
    boot_r, save, rsteps, plua = q.prepare(boot, steps)
    read = [("vram", TILEMAP, 2048), ("vram", CHR, 0x8000), ("cgram", 0xE0, 32)]
    runs = [{"steps": st, "shot": q.end_frame(st, 0), "read": read, "wram": [q.mail(i)]} for i, st in enumerate(rsteps)]
    results = replay.replay(rom.path, boot_r, save, runs, extra_lua=plua + READ_LUA, nmi=q.MAP_HOOK)
    m = rom.data[MAP:MAP + MAP_W * MAP_H]
    chip = [rom.data[MAP_CHIPS + 32 * v:MAP_CHIPS + 32 * v + 32] for v in range(256)]
    cells, shown, bad, reads, tiles, edge = set(), set(), 0, 0, 0, 0
    for i, (tmap, chr_, cgram, log) in enumerate(results):
        if cgram != rom.data[MAP_PALETTE:MAP_PALETTE + 32]:
            bad += 1
            print(f"  NG run {i}: palette 7 differs")
        for j in range(0, len(log) - 3, 4):
            x, y, v = log[j] << 8 | log[j + 1], log[j + 2], log[j + 3]
            reads += 1
            if not (0 <= x < MAP_W and y < MAP_H) or v != m[MAP_W * y + x]:
                bad += 1
                print(f"  NG run {i}: read ({x}, {y}) -> {v:02X}")
            else:
                cells.add((x, y))
        # BG tiles with palette 7 hold the drawn chips: vote for the cell offset, then every such tile must equal
        # the chip of its cell (offset taken modulo the 32 x 32 tilemap)
        ent = {}
        for t in range(1024):
            e = tmap[2 * t] | tmap[2 * t + 1] << 8
            if e >> 10 & 7 == 7 and not e & 0xC000:
                ent[(t % 32, t // 32)] = chr_[32 * (e & 0x3FF):32 * (e & 0x3FF) + 32]
        votes = {}
        for (tx, ty), px in list(ent.items())[::7]:
            for y in range(MAP_H):
                for x in range(MAP_W):
                    if chip[m[MAP_W * y + x]] == px:
                        k = ((x - tx), (y - ty))
                        votes[k] = votes.get(k, 0) + 1
        ox, oy = max(votes, key=votes.get)
        miss = 0
        for (tx, ty), px in ent.items():
            near = [(tx + ox + 32 * a, ty + oy + 32 * b) for a in (-1, 0, 1) for b in (-1, 0, 1)]
            near = [(x, y) for x, y in near if 0 <= x < MAP_W and 0 <= y < MAP_H]
            ok = [(x, y) for x, y in near if chip[m[MAP_W * y + x]] == px]
            if ok:
                shown.add(ok[0])
                tiles += 1
                continue
            # the left edge of the map window: its 2-pixel border is drawn over the first BG column
            got = decode_tile4(px)
            if not any(all(a == b for j, (a, b) in enumerate(zip(got, decode_tile4(chip[m[MAP_W * y + x]])))
                           if j % 8 >= 2) for x, y in near):
                miss += 1
            else:
                edge += 1
        if miss:
            bad += 1
            print(f"  NG run {i}: {miss}/{len(ent)} BG tiles are not the chip of their cell (offset {ox}, {oy})")
    print(f"local map: {len(results)} views, {reads} map reads at {len(cells)} distinct cells, {tiles} BG tiles equal "
          f"to their chips ({len(shown)} distinct cells of {MAP_W} x {MAP_H}) + {edge} under the window's left border "
          f"(equal from pixel column 2 on), palette 7 x {len(results)}")
    return bad


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證地域拡大図（地圖、chip、調色盤）與中国全土図")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--part", choices=("region", "map"))
    args = ap.parse_args()
    t0 = time.time()
    rom = Rom(args.rom)
    if args.part:   # one Mesen per process
        raise SystemExit(1 if (region(rom) if args.part == "region" else local_map(rom)) else 0)
    import subprocess
    bad = sum(subprocess.run([sys.executable, __file__, "--rom", args.rom, "--part", p], check=False).returncode != 0
              for p in ("region", "map"))
    print(f"{time.time() - t0:.0f} s")
    print("ALL OK" if not bad else f"{bad} mismatch(es)")
    raise SystemExit(1 if bad else 0)


if __name__ == "__main__":
    main()
