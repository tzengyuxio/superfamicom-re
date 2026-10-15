#!/usr/bin/env python3
"""Check the strategy map (rom.Rom.map_bitmap) and the battle maps (rom.Rom.battle_tilemap, mode17_province)
against the game (needs Mesen 2, a few minutes).

Three scenes (savestate replay, tools/replay.py; one Mesen per process, so each scene runs in a subprocess):
  strategy  scenario list → scenario 1-4; 600 frames later the painted map bitmap at $7F:0000 and its copy in
            VRAM 0x4600 must equal Rom.map_bitmap(s), BG2 must show tiles 0x30.. row by row from tile (1, 1)
            with palette 2, and CGRAM palette 2 must be the ROM palette MAP_PALETTE (colours 2 and 3 are
            swapped back and forth by the game, so they are compared as a pair).
  cpu17     scenario 1 with 0 players and コンピュータどうしの戦いを見ます Y: the computers fight and the game
            shows the battles. A read callback on the battle table ($C3:AA88) notes which map the game takes;
            200 frames later BG2 (tilemap 0xF000), the battle tiles (VRAM 0x4400 = LZ stream 0; the 8 water tiles
            are animated and left out) and CGRAM are
            read. Run 0 leaves the ROM alone: the map must be MODE17_PROVINCE[p] for the 17-mode province p
            whose entry the game read just before. Runs 1-50 fill the 17 entries with map m (0-49): the game must
            take map m and draw Rom.battle_tilemap(m) at BG2 tile (8, 4).
  war50     scenario 2, 織田 attacks 美濃 (province 22): the game must take map 22 and draw it.

Usage: .venv/bin/python zenkoku/verify_maps.py [--rom ROM]
"""
import argparse
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
from replay import replay
from rom import (
    BATTLE_COUNT,
    BATTLE_H,
    BATTLE_MAPS,
    BATTLE_PALETTE,
    BATTLE_SCREEN_X,
    BATTLE_SCREEN_Y,
    BATTLE_STREAM,
    BATTLE_TILE0,
    BATTLE_W,
    BLOCK_ORDER,
    DEFAULT_ROM,
    MAP_H,
    MAP_PALETTE,
    MAP_SCREEN_X,
    MAP_SCREEN_Y,
    MAP_TILE0,
    MAP_W,
    MODE17_PROVINCE,
    SCENARIO_COUNT,
    Rom,
)
from scenes import CPU_GAME_17, MENU, TO_COMMAND, TO_WAR, length, save_frame, scenario

BG2_TILEMAP = 0xF000
BITMAP_WRAM, BITMAP_VRAM, BITMAP_BYTES = 0x10000, 0x4600, MAP_W * MAP_H * 32
TW, TH = 2 * BATTLE_W, 4 * BATTLE_H + 2      # battle map size in tiles
CHR_AT = 0x4000 + 32 * BATTLE_TILE0
DELAY = 200                                  # frames from the table read to the reads
CPU_SHOT = 3400                              # the first computer battle (美濃) is read about 2940 frames in
MAP_ROWS = BG2_TILEMAP + 2 * 32 * BATTLE_SCREEN_Y
# The water block (terrain 0x40, stream tiles 40-47) is animated: the game overwrites it with other frames.
WATER = (32 * 8 * BLOCK_ORDER.index(0x40), 32 * 8 * (BLOCK_ORDER.index(0x40) + 1))

LUA = """
local fr, fr0, first, idx, tidx, tfr, cap = 0, 0, nil, -1, -1, -1, ""
local function hex(mem, a, n)
  local s = {}
  for i = 0, n - 1 do s[#s + 1] = string.format("%%02x", emu.read(a + i, mem, false)) end
  return table.concat(s)
end
function EXTRA_RESET() first = nil; idx = -1; tidx = -1; tfr = -1; cap = ""; fr0 = fr end
emu.addMemoryCallback(function(addr)
  if first == nil then first = fr; idx = (addr - %(maps)d) // 55 end
end, emu.callbackType.read, %(maps)d, %(maps_end)d)
emu.addMemoryCallback(function(addr)
  if first == nil and tfr ~= fr then tidx = addr - %(table)d; tfr = fr end
end, emu.callbackType.read, %(table)d, %(table)d + 16)
emu.addEventCallback(function()
  fr = fr + 1
  if first ~= nil and fr - first == %(delay)d then
    cap = hex(emu.memType.snesVideoRam, %(rows)d, %(rows_n)d) .. hex(emu.memType.snesVideoRam, %(chr)d, %(chr_n)d)
      .. hex(emu.memType.snesCgRam, 0, 128)
  end
end, emu.eventType.endFrame)
function EXTRA_SHOT()
  return string.format("%%02x%%02x%%08x", idx & 0xFF, tidx & 0xFF, ((first or fr0) - fr0) & 0xFFFFFFFF) .. cap
end
"""


def battle_lua(rom: Rom) -> str:
    return LUA % {"maps": 0xC00000 + BATTLE_MAPS, "maps_end": 0xC00000 + BATTLE_MAPS + 55 * BATTLE_COUNT - 1,
                  "table": 0xC00000 + MODE17_PROVINCE, "delay": DELAY, "rows": MAP_ROWS, "rows_n": 64 * TH,
                  "chr": CHR_AT, "chr_n": len(rom.entry(BATTLE_STREAM))}


def parse(rom: Rom, extra: bytes) -> dict:
    n_rows, n_chr = 64 * TH, len(rom.entry(BATTLE_STREAM))
    out = {"map": extra[0], "table": extra[1], "frame": int.from_bytes(extra[2:6], "big")}
    cap = extra[6:]
    if len(cap) == n_rows + n_chr + 128:
        rows, chars, cgram = cap[:n_rows], cap[n_rows:n_rows + n_chr], cap[n_rows + n_chr:]
        words = [rows[2 * i] | rows[2 * i + 1] << 8 for i in range(32 * TH)]
        out["tiles"] = [words[y * 32 + BATTLE_SCREEN_X + x] & 0x3FF for y in range(TH) for x in range(TW)]
        out["palettes"] = sorted({words[y * 32 + BATTLE_SCREEN_X + x] >> 10 & 7 for y in range(TH) for x in range(TW)})
        out["chr"], out["cgram"] = chars, cgram
    return out


def check_battle(rom: Rom, got: dict, m: int) -> list[str]:
    errs = []
    if got["map"] != m:
        errs.append(f"map read {got['map']}")
    if "tiles" not in got:
        return errs + ["no battle"]
    if got["tiles"] != rom.battle_tilemap(m):
        n = sum(a != b for a, b in zip(got["tiles"], rom.battle_tilemap(m)))
        errs.append(f"{n} tiles differ")
    chars = rom.entry(BATTLE_STREAM)
    if got["chr"][:WATER[0]] != chars[:WATER[0]] or got["chr"][WATER[1]:] != chars[WATER[1]:]:
        errs.append("CHR")
    if got["cgram"][64:96] != rom.data[BATTLE_PALETTE:BATTLE_PALETTE + 32]:
        errs.append("palette 2")
    return errs


def scene_strategy(rom: Rom, path: str) -> int:
    runs = []
    for s in range(SCENARIO_COUNT):
        st = scenario(s)
        runs.append({"steps": st, "shot": length(st),
                     "read": [("wram", BITMAP_WRAM, BITMAP_BYTES), ("vram", BITMAP_VRAM, BITMAP_BYTES),
                              ("vram", BG2_TILEMAP, 0x800), ("cgram", 64, 32)]})
    pal = rom.data[MAP_PALETTE:MAP_PALETTE + 32]
    errors = 0
    for s, (wram, vram, tmap, cg) in enumerate(replay(path, MENU, save_frame(MENU), runs)):
        want = rom.map_bitmap(s)
        tiles_ok = all(
            (tmap[2 * ((MAP_SCREEN_Y + y) * 32 + MAP_SCREEN_X + x)] | tmap[2 * ((MAP_SCREEN_Y + y) * 32 + MAP_SCREEN_X + x) + 1] << 8)
            == MAP_TILE0 + y * MAP_W + x | 2 << 10 for y in range(MAP_H) for x in range(MAP_W))
        pal_ok = cg[:4] == pal[:4] and cg[8:] == pal[8:] and {cg[4:6], cg[6:8]} == {pal[4:6], pal[6:8]}
        ng = [k for k, ok in (("WRAM bitmap", wram == want), ("VRAM bitmap", vram == want), ("BG2 tilemap", tiles_ok),
                              ("palette 2", pal_ok)) if not ok]
        errors += bool(ng)
        print(f"[strategy] scenario {s + 1} ({rom.province_count(s)} provinces): painted bitmap $7F:0000 and VRAM "
              f"0x4600 = map_bitmap, BG2 tilemap, palette 2: {'OK' if not ng else 'NG ' + ', '.join(ng)}", flush=True)
    return errors


def scene_cpu17(rom: Rom, path: str) -> int:
    table = rom.mode17_province()
    runs = [{"steps": "w10", "shot": CPU_SHOT, "read": []}]
    runs += [{"patch": [(MODE17_PROVINCE, bytes([m] * 17))], "steps": "w10", "shot": CPU_SHOT, "read": []}
             for m in range(BATTLE_COUNT)]
    res = [parse(rom, r[-1]) for r in replay(path, CPU_GAME_17, save_frame(CPU_GAME_17), runs, extra_lua=battle_lua(rom))]
    errors = 0
    g = res[0]
    p = g["table"]
    ok = 0 <= p < 17 and g["map"] == table[p] and not check_battle(rom, g, table[p])
    errors += not ok
    names = rom.province_names(0)
    print(f"[mode17] unpatched: the battle in 17-mode province {p} ({names[p] if 0 <= p < 17 else '?'}) uses map "
          f"{g['map']} = MODE17_PROVINCE[{p}] = {table[p] if 0 <= p < 17 else '?'}: {'OK' if ok else 'NG'}", flush=True)
    bad = []
    for m, g in enumerate(res[1:]):
        errs = check_battle(rom, g, m)
        if errs:
            bad.append(f"{m}: {', '.join(errs)}")
    errors += len(bad)
    print(f"[battle] {BATTLE_COUNT - len(bad)}/{BATTLE_COUNT} maps (table patched): the game reads map m, BG2 at tile "
          f"({BATTLE_SCREEN_X}, {BATTLE_SCREEN_Y}) = battle_tilemap(m), VRAM 0x4400 = LZ stream 0 (but the animated water tiles), "
          f"palette 2 = ROM" + (f"  NG {bad}" if bad else ""), flush=True)
    print(f"[battle] BG2 palettes used on the map: {sorted({q for g in res if 'palettes' in g for q in g['palettes']})}",
          flush=True)
    return errors


def scene_war50(rom: Rom, path: str) -> int:
    tail = TO_WAR[len(TO_COMMAND) + 1:]
    runs = [{"steps": tail, "shot": length(tail) + DELAY + 100, "read": []}]
    g = parse(rom, replay(path, TO_COMMAND, save_frame(TO_COMMAND), runs, extra_lua=battle_lua(rom))[0][-1])
    errs = check_battle(rom, g, 22)
    print(f"[war50] scenario 2, 織田 attacks 美濃 (province 22): map {g['map']} read and drawn"
          f" = battle_tilemap(22): {'OK' if not errs else 'NG ' + ', '.join(errs)}", flush=True)
    return len(errs)


SCENES = {"strategy": scene_strategy, "cpu17": scene_cpu17, "war50": scene_war50}


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證大地圖上色與戰場地圖")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--scene", choices=list(SCENES), help=argparse.SUPPRESS)  # one Mesen per process
    args = ap.parse_args()
    t0 = time.time()
    if args.scene:
        raise SystemExit(1 if SCENES[args.scene](Rom(args.rom), args.rom) else 0)
    errors = 0
    for scene in SCENES:
        cmd = [sys.executable, __file__, "--rom", args.rom, "--scene", scene]
        errors += subprocess.run(cmd, check=False).returncode != 0
    print(f"{'ALL OK' if not errors else 'PROBLEMS'} ({time.time() - t0:.0f} s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
