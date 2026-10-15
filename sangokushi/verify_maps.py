#!/usr/bin/env python3
"""Check the strategic map and the 58 battle fields against what the game puts in VRAM / WRAM / CGRAM.

1. Strategic map (one Mesen process). A savestate is taken just before the last press of the new-game sequence
   (the map is set up after it). Each run sets the owner (+14) of all 58 countries, finishes the sequence, opens
   the whole map (B) and reads:
     VRAM 0x9800  BG1 tilemap: rows 1-22, columns 1-30 must be MAP_TILEMAP
     VRAM 0xA020  BG1 tiles 1..: the LZ stream at MAP_TILES
     VRAM 0x3800  BG2 tilemap: tile 1 + 30 y + x, palette 3 (the owner layer)
     VRAM 0x4020  BG2 tiles: the owner layer, which must be map_owner_pixels(owners) (mask region of country c
                  painted with owner + 1; this also checks the country of each region, MAP_REGION_SEEDS)
     CGRAM        palette 2 = one of the 10 MAP_PALETTE_FRAMES; palette 3 = MAP_OWNER_PALETTE
   Runs: the owners of scenarios 1-5, and two runs with owner = c mod 15 and c // 15 (every country different).
2. Battle fields (another process). Scenario 1, 曹操 attacks 5国; a savestate is taken before the last press. Each
   run points the attacked-country word (WRAM 0x2720) at country c, starts the battle and reads at the
   deployment screen:
     WRAM 7F:8000  the BG2 tilemap the game decompressed: LZ entry BATTLE_TILEMAP + c - 1
     WRAM 0x9499   the cell grid: battle_grid(c, castles) (castle places of CASTLES turned into terrain 4)
     VRAM 0x3800   the BG2 tilemap at (2, 2): battle_tilemap(c, castles) (castle tiles drawn)
     VRAM 0x4C00   the characters: LZ entry BATTLE_CHR
     CGRAM         palettes 5 and 6 = ROM, palette 7 = one of its 3 cycle frames
   castles = the country's 城 (record +18). The unpatched run (5国) shows the game's own choice of entries.

Usage: .venv/bin/python sangokushi/verify_maps.py [--rom ROM]
"""
import argparse
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
sys.path.insert(0, os.path.join(HERE, "tools"))
import replay
import sequences
from rom import (
    BATTLE_CHR,
    BATTLE_PALETTE7_FRAMES,
    BATTLE_PALETTES,
    BATTLE_TARGET_WRAM,
    BATTLE_TH,
    BATTLE_TILEMAP,
    BATTLE_TW,
    CASTLE_SLOTS,
    COUNTRY_COUNT,
    COUNTRY_SIZE,
    COUNTRY_WRAM,
    DEFAULT_ROM,
    MAP_H,
    MAP_MASK,
    MAP_OWNER_PALETTE,
    MAP_PALETTE_FRAMES,
    MAP_TILES,
    MAP_W,
    SCENARIO_COUNT,
    Rom,
    decode_tile,
    le16,
)

LAST = " a:10 w1200"                    # the last press of TO_MAIN; the map is set up after it
SHOT = 30                               # frames after the end of the steps


def words(raw: bytes) -> list[int]:
    return [le16(raw, 2 * i) for i in range(len(raw) // 2)]


def pal_bytes(rom: Rom, o: int) -> bytes:
    return rom.data[o:o + 32]


def map_part(rom: Rom) -> dict:
    assert sequences.TO_MAIN.endswith(LAST)
    boot = sequences.TO_MAIN[:-len(LAST)]
    steps = sequences.expand(LAST + " " + sequences.MAP)
    tiles, mask = rom.lz(MAP_TILES), rom.lz(MAP_MASK)
    owner_sets = [[k["owner"] for k in rom.countries(sc)] for sc in range(1, SCENARIO_COUNT + 1)]
    owner_sets += [[c % 15 for c in range(1, COUNTRY_COUNT + 1)], [c // 15 for c in range(1, COUNTRY_COUNT + 1)]]
    names = [f"scenario {sc}" for sc in range(1, SCENARIO_COUNT + 1)] + ["c mod 15", "c // 15"]
    reads = [("vram", 0x9800, 2048), ("vram", 0xA020, len(tiles)), ("vram", 0x3800, 2048),
             ("vram", 0x4020, len(mask)), ("cgram", 0, 256), ("wram", COUNTRY_WRAM, COUNTRY_SIZE * COUNTRY_COUNT)]
    runs = [{"wram": [(COUNTRY_WRAM + COUNTRY_SIZE * i + 14, bytes([o])) for i, o in enumerate(owners)],
             "steps": steps, "shot": sequences.end_frame(steps, 0) + SHOT, "read": reads} for owners in owner_sets]
    results = replay.replay(rom.path, boot, sequences.end_frame(boot), runs)
    rt = rom.map_tilemap()
    frames = [pal_bytes(rom, MAP_PALETTE_FRAMES + 32 * k) for k in range(10)]
    w = MAP_W * 8
    out = []
    for name, owners, (bg1, bg1chr, bg2, bg2chr, cg, wr) in zip(names, owner_sets, results):
        vm, v2 = words(bg1), words(bg2)
        tm_bad = sum(vm[32 * (y + 1) + x + 1] != rt[MAP_W * y + x] for y in range(MAP_H) for x in range(MAP_W))
        bg2_bad = sum(v2[32 * (y + 1) + x + 1] != (0x0C00 | 1 + MAP_W * y + x) for y in range(MAP_H) for x in range(MAP_W))
        got = [0] * len(mask) * 2
        for t in range(len(bg2chr) // 32):
            for i, v in enumerate(decode_tile(bg2chr[32 * t:32 * t + 32])):
                got[(t // MAP_W * 8 + i // 8) * w + t % MAP_W * 8 + i % 8] = v
        # the owners in WRAM when the map is shown (the game may change some after the patch: listed)
        live = [wr[COUNTRY_SIZE * i + 14] for i in range(COUNTRY_COUNT)]
        want = rom.map_owner_pixels(live)
        out.append({"name": name, "tilemap_bad": tm_bad, "tiles": bg1chr == tiles, "bg2_bad": bg2_bad,
                    "owner_px_bad": sum(a != b for a, b in zip(got, want)), "owner_px": len(want),
                    "pal2_frame": [k for k, f in enumerate(frames) if f == cg[0x40:0x60]],
                    "pal3": cg[0x60:0x80] == pal_bytes(rom, MAP_OWNER_PALETTE),
                    "changed": [[i + 1, a, b] for i, (a, b) in enumerate(zip(owners, live)) if a != b]})
    return {"map": out}


def battle_part(rom: Rom) -> dict:
    boot = sequences.TO_MAIN + " " + sequences.WAR_5
    steps = sequences.expand(sequences.WAR_START)
    chr_ = rom.entry(BATTLE_CHR)
    reads = [("wram", 0x18000, 2 * BATTLE_TW * BATTLE_TH), ("wram", 0x9499, 168), ("vram", 0x3800, 2048),
             ("vram", 0x4C00, len(chr_)), ("cgram", 0xA0, 96)]
    shot = sequences.end_frame(steps, 0) + 20
    runs = [{"steps": steps, "shot": shot, "read": reads}]  # the game's own 5国
    targets = list(range(1, COUNTRY_COUNT + 1))
    runs += [{"wram": [(BATTLE_TARGET_WRAM, (COUNTRY_WRAM + COUNTRY_SIZE * (c - 1)).to_bytes(2, "little"))],
              "steps": steps, "shot": shot, "read": reads} for c in targets]
    results = replay.replay(rom.path, boot, sequences.end_frame(boot), runs)
    countries = rom.countries(1)
    p7 = [pal_bytes(rom, BATTLE_PALETTES[7] + 32 * k) for k in range(BATTLE_PALETTE7_FRAMES)]
    p56 = pal_bytes(rom, BATTLE_PALETTES[5]) + pal_bytes(rom, BATTLE_PALETTES[6])
    out = []
    for c, (tm, grid, bg2, ch, cg) in zip([5] + targets, results):
        n = countries[c - 1]["castle"]
        want_grid = bytes(b for row in rom.battle_grid(c, n) for b in row)
        want_tm = rom.battle_tilemap(c, n)
        v2 = words(bg2)
        bg2_bad = sum(v2[32 * (y + 2) + x + 2] != want_tm[BATTLE_TW * y + x]
                      for y in range(BATTLE_TH) for x in range(BATTLE_TW))
        out.append({"c": c, "castles": n, "slots": len(rom.castle_cells(c)),
                    "tilemap": tm == rom.entry(BATTLE_TILEMAP + c - 1)[:len(tm)],
                    "grid_bad": sum(a != b for a, b in zip(grid, want_grid)), "bg2_bad": bg2_bad,
                    "chr": ch == chr_, "pal56": cg[:64] == p56, "pal7": [k for k, f in enumerate(p7) if f == cg[64:]]})
    return {"battle": out}


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證大地圖與 58 張戰場")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--part", choices=["map", "battle"], help="只跑一部分（JSON 輸出，內部用）")
    args = ap.parse_args()
    rom = Rom(args.rom)
    if args.part:
        print("RESULT " + json.dumps(map_part(rom) if args.part == "map" else battle_part(rom)))
        return
    t0 = time.time()
    res = {}
    for part in ("map", "battle"):
        out = subprocess.run([sys.executable, os.path.abspath(__file__), "--part", part, "--rom", args.rom],
                             capture_output=True, text=True, check=True).stdout
        res.update(json.loads(next(line for line in out.splitlines() if line.startswith("RESULT "))[7:]))
    errors = 0
    for r in res["map"]:
        ok = (not r["tilemap_bad"] and r["tiles"] and not r["bg2_bad"] and not r["owner_px_bad"] and r["pal2_frame"]
              and r["pal3"])
        errors += not ok
        print(f"[map {r['name']}] BG1 tilemap {MAP_W * MAP_H - r['tilemap_bad']}/{MAP_W * MAP_H}, BG1 tiles "
              f"{'=' if r['tiles'] else '!='} ROM, BG2 tilemap {MAP_W * MAP_H - r['bg2_bad']}/{MAP_W * MAP_H}, owner "
              f"layer {r['owner_px'] - r['owner_px_bad']}/{r['owner_px']} px, palette 2 = frame {r['pal2_frame']}, "
              f"palette 3 {'OK' if r['pal3'] else 'NG'}"
              + (f" (owner changed by the game before the map: {r['changed']} [country, set, now])" if r['changed'] else "")
              + ("" if ok else "  NG"))
    bt = res["battle"]
    cells, tiles = 14 * 12, BATTLE_TW * BATTLE_TH
    bad = [r for r in bt if not (r["tilemap"] and not r["grid_bad"] and not r["bg2_bad"] and r["chr"]
                                 and r["pal56"] and r["pal7"] and r["castles"] <= r["slots"])]
    errors += len(bad)
    own = bt[0]
    print(f"[battle 5国, the game's own choice] tilemap {'OK' if own['tilemap'] else 'NG'}, grid "
          f"{cells - own['grid_bad']}/{cells}, BG2 {tiles - own['bg2_bad']}/{tiles}, {own['castles']} castles")
    print(f"[battle] {sum(r not in bad for r in bt[1:])}/{len(bt) - 1} fields: WRAM "
          f"tilemap = LZ entry {BATTLE_TILEMAP}+c-1, grid = entry 245+c-1 with castles, BG2 (castle tiles drawn), "
          f"chr = entry {BATTLE_CHR}, palettes 5/6 = ROM; castles placed: {sum(r['castles'] for r in bt[1:])} "
          f"(≤ {CASTLE_SLOTS} places each); palette 7 frames seen {sorted({k for r in bt for k in r['pal7']})}")
    for r in bad[:5]:
        print("  NG", r)
    print(f"{time.time() - t0:.0f} s")
    print("ALL OK" if not errors else f"{errors} mismatch(es)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
