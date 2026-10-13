#!/usr/bin/env python3
"""Check the big map and the 58 battle maps against the game (needs Mesen 2, about 10 minutes).

Plays the opening in Mesen (tools/mesen.py, eiketsu/tools/replay.py) up to 劉備's camp:
- Big map: X -> 全体図. The BG tiles at VRAM word 0x400 and the 32 x 28 tilemap at VRAM word 0x3800 must equal
  rom.Rom.world_chars / world_tilemap, CGRAM palettes 4-6 WORLD_PALETTE; the marker layer at VRAM word 0x3C00
  must hold WORLD_MARKER exactly at the markers of place list rom.Rom.chapter_groups()[$7E:7618].
- Battle maps: talking to 関羽 and choosing 出陣 runs the prologue script, whose op 09 (word 0x3000 + battle at
  $CB:076B) starts battle 0. A savestate is taken before that press; for every battle n the script byte is
  patched to n and the state replayed, so the game sets up battle n itself. Then: the title at $7E:D97F must be
  rom.Rom.battle_titles()[n] (name + "の戦い", put before a trailing Ⅰ-Ⅲ); the tiles at VRAM tile 64 must be BATTLE_GFX stream [set] (set from BATTLE_SET1),
  CGRAM palettes 4-6 BATTLE_PALETTES[set]; the terrain cells at $7F:C910 must equal the map's terrain bytes;
  and the 64 x 32 BG tilemap at VRAM word 0x3800 must show the map (rom.Rom.battle_tilemap) - the camera
  position is not read, so the best offset is searched; some 32 x 28 screen window must match the map in every
  cell that lies inside the map (the camera may sit at a map edge), at least 30 x 26 cells.

Usage: .venv/bin/python eiketsu/verify_maps.py [--rom ROM] [--quick]
"""
import argparse
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "tools"))
from replay import TO_BATTLE, TO_WORLD, replay
from rom import (
    BATTLE_COUNT,
    BATTLE_PALETTES,
    DEFAULT_ROM,
    WORLD_H,
    WORLD_PALETTE,
    WORLD_W,
    Rom,
    le16,
    text,
)

BATTLE_ARG = 0xB076B            # low byte of the op 09 word 0x3000 in the prologue script ($CB:076A)
BATTLE_SAVE, BATTLE_SHOT = 21660, 22120
WORLD_SAVE, WORLD_SHOT = 20000, 20390
NAME_WRAM = 0x7ED97F
TERRAIN_WRAM = 0x7FC910
CHARS_MAX = 0x5740              # the larger of the two tile sets
SCREEN_W, SCREEN_H = 32, 28
MIN_SHOWN = 30 * 26           # cells of the map on screen when the camera is at a corner

PATCH_LUA = """
local patched=-1
emu.addEventCallback(function()
  if PARAM~=nil and patched~=PARAM then emu.write(%d, PARAM, emu.memType.snesPrgRom); patched=PARAM end
end, emu.eventType.endFrame)
"""


def check_world(rom: Rom, rom_path: str) -> int:
    (_, (chars, tmap, marks, cg, chap)), = replay(
        rom_path, TO_WORLD, WORLD_SAVE, WORLD_SHOT, [0],
        [("vram", 0x800, len(rom.world_chars())), ("vram", 0x7000, 2 * WORLD_W * WORLD_H), ("vram", 0x7800, 2048),
         ("cgram", 0x80, 0x60), ("mem", 0x7E7618, 1)])
    errors = 0
    ok = chars == rom.world_chars()
    print(f"[world] tiles at VRAM word 0x400 ({len(chars)} bytes) {'match' if ok else 'NG'}")
    errors += not ok
    want = [e for row in rom.world_tilemap() for e in row]
    got = [le16(tmap, 2 * i) for i in range(WORLD_W * WORLD_H)]
    n = sum(a == b for a, b in zip(got, want))
    print(f"[world] tilemap at VRAM word 0x3800: {n}/{len(want)} entries match")
    errors += n != len(want)
    ok = cg == rom.data[WORLD_PALETTE:WORLD_PALETTE + 0x60]
    print(f"[world] CGRAM palettes 4-6 {'match' if ok else 'NG'} WORLD_PALETTE")
    errors += not ok
    group = rom.chapter_groups()[chap[0]]
    want_marks = {p["marker"] for p in rom.places(group) if p["marker"]}
    marker = rom.world_marker()
    got_marks = {(i % 32, i // 32) for i in range(1024) if le16(marks, 2 * i) == marker}
    others = {le16(marks, 2 * i) for i in range(1024)} - {0, marker}
    print(f"[world] chapter {chap[0]} -> place list {group}: {len(got_marks)} markers on screen, "
          f"{len(want_marks)} in the table, {'same cells' if got_marks == want_marks else 'NG'}"
          + (f"; other entries {sorted(others)}" if others else ""))
    errors += got_marks != want_marks
    return errors


def best_offset(got: list[int], want: list[list[int]]) -> tuple[int, int, int]:
    """(matches, ox, oy): VRAM cell (x, y) of the 64 x 32 tilemap compared with map tile (x + ox, y + oy)."""
    h, w = len(want), len(want[0])
    where: dict[int, list[tuple[int, int]]] = {}
    for wy, row in enumerate(want):
        for wx, e in enumerate(row):
            where.setdefault(e, []).append((wx, wy))
    cell = {(x, y): got[(x // 32) * 1024 + y * 32 + x % 32] for y in range(32) for x in range(64)}
    votes: dict[tuple[int, int], int] = {}
    for (x, y), e in cell.items():  # candidate offsets from entries that are rare in the map
        if len(where.get(e, ())) <= 40:
            for wx, wy in where.get(e, ()):
                votes[wx - x, wy - y] = votes.get((wx - x, wy - y), 0) + 1
    best = (0, 0, 0)
    for ox, oy in sorted(votes, key=votes.get, reverse=True)[:20]:
        n = sum(0 <= x + ox < w and 0 <= y + oy < h and want[y + oy][x + ox] == e for (x, y), e in cell.items())
        best = max(best, (n, ox, oy))
    return best


def screen_cells(got: list[int], want: list[list[int]]) -> int:
    """Map cells in the best 32 x 28 screen window of the 64 x 32 tilemap, if every window cell that lies inside
    the map (at the best offset) equals the map; else 0. The camera can stop at the map's edge, so part of the
    window may lie outside the map."""
    _, ox, oy = best_offset(got, want)
    h, w = len(want), len(want[0])
    best = 0
    for sy in range(32):
        for sx in range(64):
            n = 0
            for y in range(sy, sy + SCREEN_H):
                for x in range(sx, sx + SCREEN_W):
                    wx, wy = x + ox, y + oy
                    if 0 <= wx < w and 0 <= wy < h:
                        if want[wy][wx] != got[(x % 64 // 32) * 1024 + y % 32 * 32 + x % 32]:
                            n = -1
                            break
                        n += 1
                if n < 0:
                    break
            best = max(best, n)
    return best


def check_battles(rom: Rom, rom_path: str, battles: list[int]) -> int:
    titles = rom.battle_titles()
    shown = replay(rom_path, TO_BATTLE, BATTLE_SAVE, BATTLE_SHOT, battles,
                   [("mem", NAME_WRAM, 24), ("mem", TERRAIN_WRAM, 1024), ("vram", 0x800, CHARS_MAX),
                    ("vram", 0x7000, 0x1000), ("cgram", 0x80, 0x60)], PATCH_LUA % BATTLE_ARG)
    bad = {"name": [], "tiles": [], "palette": [], "terrain": [], "tilemap": []}
    worst = SCREEN_W * SCREEN_H
    for n, (_, (name, ter, chars, tmap, cg)) in zip(battles, shown):
        m = rom.battle_map(n)
        if text(name) != titles[n]:
            bad["name"].append(f"{n}:{text(name)}")
        want = rom.battle_chars(m["set"])
        if chars[:len(want)] != want:
            bad["tiles"].append(n)
        if cg != rom.data[BATTLE_PALETTES[m["set"]]:BATTLE_PALETTES[m["set"]] + 0x60]:
            bad["palette"].append(n)
        cells = bytes(c for row in m["terrain"] for c in row)
        if ter[:len(cells)] != cells:
            bad["terrain"].append(n)
        score = screen_cells([le16(tmap, 2 * i) for i in range(2048)], rom.battle_tilemap(n))
        worst = min(worst, score)
        if score < MIN_SHOWN:
            bad["tilemap"].append(n)
    k = len(battles)
    print(f"[battle] title at $7E:D97F = rom.Rom.battle_titles()[n]: {k - len(bad['name'])}/{k}")
    print(f"[battle] tiles at VRAM tile 64 = BATTLE_GFX[set]: {k - len(bad['tiles'])}/{k}")
    print(f"[battle] CGRAM palettes 4-6 = BATTLE_PALETTES[set]: {k - len(bad['palette'])}/{k}")
    print(f"[battle] terrain cells at $7F:C910 = map terrain bytes: {k - len(bad['terrain'])}/{k}")
    print(f"[battle] BG tilemap at VRAM word 0x3800: a 32 x 28 screen whose cells inside the map all match it "
          f"(>= {MIN_SHOWN} cells): "
          f"{k - len(bad['tilemap'])}/{k} (fewest matching cells {worst})")
    for key, v in bad.items():
        if v:
            print(f"  NG {key}: {v}")
    return sum(len(v) for v in bad.values())


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證大地圖與 58 張戰場地圖")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--quick", action="store_true", help="only every 8th battle")
    ap.add_argument("--part", choices=["world", "battles"], help=argparse.SUPPRESS)
    args = ap.parse_args()
    if args.part is None:  # Mesen can be opened once per process: run each part in its own process
        t = time.time()
        codes = [subprocess.run([sys.executable, __file__, "--rom", args.rom, "--part", part]
                                + (["--quick"] if args.quick else []), check=False).returncode for part in ("world", "battles")]
        print(f"({time.time() - t:.0f} s)")
        errors = sum(c != 0 for c in codes)
        print("ALL OK" if not errors else f"{errors} part(s) with problems")
        raise SystemExit(1 if errors else 0)
    rom = Rom(args.rom)
    if args.part == "world":
        errors = check_world(rom, args.rom)
    else:
        errors = check_battles(rom, args.rom, list(range(BATTLE_COUNT))[::8 if args.quick else 1])
    sys.stdout.flush()
    if errors:
        print(f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
