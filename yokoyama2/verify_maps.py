#!/usr/bin/env python3
"""Check the strategic map (rom.Rom.map_vram, map_palette, marker) against the game.

The game is played to the scenario list and a savestate is taken there (tools/sequences.py). Each run starts one
scenario (189 / 200 / 215, 劉備, 中級) and plays to the player's first turn, then reads VRAM, CGRAM, OAM and the
countries in WRAM:
- VRAM 0x0000-0x7FFF (the mode-7 tilemap and pixels) must equal rom.Rom.map_vram() byte for byte;
- the map colours 0x20-0x5F must equal MAP_PALETTE (0x50-0x57: each group of 4 may be rotated, the colour cycle);
- OBJ 1-35 must be the country markers: position from MAP_POSITIONS, tile and palette from the country's faction
  in WRAM (rom.Rom.marker); OBJ palettes 6-7 must be MAP_MARKER_COLOURS. The WRAM factions are also compared with
  the scenario's start.
A fourth run plays 189 with the 砦 byte of every country patched in the ROM table (country c: bits (7 c + 1) & 0x3F)
and checks the fort pieces that $91:8031 draws (rom.Rom.map_vram(forts)). A fifth run plays 189, writes 8 marching
armies into the WRAM person heads on the map (ARMIES: faction, flag 0x10, column, row), opens and closes the country
information screen (X, B: the map is built again) and checks the army tiles that $91:81AF draws
(rom.Rom.map_vram(persons=the WRAM person block read at the shot)).

Usage: .venv/bin/python yokoyama2/verify_maps.py [--rom ROM]
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
    COUNTRIES,
    COUNTRY_COUNT,
    COUNTRY_SIZE,
    COUNTRY_WRAM,
    COUNTRY_WRAM_SIZE,
    DEFAULT_ROM,
    MAP_COLOURS,
    MAP_MARKER_COLOURS,
    MAP_PALETTE,
    PERSON_COUNT,
    PERSON_WRAM,
    PERSON_WRAM_SIZE,
    SCENARIO_YEARS,
    Rom,
    off,
)

FORTS = [(7 * c + 1) & 0x3F for c in range(COUNTRY_COUNT)]
ARMIES = [(p, 3 * i % 16 | 0x80 | (0x10 if i & 1 else 0), 8 + 6 * i, 10 + 5 * i) for i, p in enumerate(range(40, 48))]
ARMY_LUA = """
local cf=0
emu.addEventCallback(function()
  cf=cf+1
  if cf==ARMY_AT then
    for _,a in ipairs(ARMY) do for k=1,3 do emu.write(a[1]+k-1, a[k+1], emu.memType.snesWorkRam) end end
  end
end, emu.eventType.endFrame)
function EXTRA_RESET() cf=0 end
"""


def colours_ok(got: bytes, want: bytes) -> bool:
    """Colours 0x20-0x5F: equal, except 0x50-0x53 and 0x54-0x57 may each be rotated."""
    g, w = ([b[i:i + 2] for i in range(0, len(b), 2)] for b in (got, want))
    if g[:0x30] != w[:0x30] or g[0x38:] != w[0x38:]:
        return False
    for a in (0x30, 0x34):
        if not any(g[a:a + 4] == w[a + r:a + 4] + w[a:a + r] for r in range(4)):
            return False
    return True


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證大地圖（VRAM、調色盤、國的標記）")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    t0 = time.time()
    rom = Rom(args.rom)
    lo, hi = MAP_COLOURS
    steps = [q.scenario(k) + " a:10 w300" * n + " w400" for k, n in enumerate(q.TURN_PRESSES)]
    runs = [{"steps": s, "shot": q.end_frame(s, 0), "read": [
        ("vram", 0, 0x8000), ("cgram", 0, 0x200), ("oam", 0, 0x220),
        ("wram", COUNTRY_WRAM, COUNTRY_WRAM_SIZE * COUNTRY_COUNT),
        ("wram", PERSON_WRAM, PERSON_WRAM_SIZE * PERSON_COUNT)]} for s in steps]
    runs.append(dict(runs[0], patch=[(off(COUNTRIES[0]) + COUNTRY_SIZE * c + 17, bytes([FORTS[c]]))
                                     for c in range(COUNTRY_COUNT)]))
    army_steps = steps[0] + " w30 x:10 w300 b:10 w300"
    runs.append(dict(runs[0], steps=army_steps, shot=q.end_frame(army_steps, 0)))
    lua = (f"ARMY_AT={q.end_frame(steps[0], 0) + 10}\nARMY={{"
           + ",".join(f"{{{PERSON_WRAM + PERSON_WRAM_SIZE * p},{h},{x},{y}}}" for p, h, x, y in ARMIES) + "}\n"
           + ARMY_LUA)
    boot = q.TO_SCENARIOS
    results = replay.replay(rom.path, boot, q.end_frame(boot), runs, extra_lua=lua)
    bad = 0
    for i, (vram, cgram, oam, wram, persons) in enumerate(results):
        k = i if i < 3 else 0
        year = f"{SCENARIO_YEARS[k]}{['', '', '', ' 砦', ' 行軍'][i]}"
        want = rom.map_vram(FORTS if i == 3 else None, persons if i == 4 else None)
        if i == 4:
            placed = sum(persons[PERSON_WRAM_SIZE * p:PERSON_WRAM_SIZE * p + 3] == bytes([h, x, y])
                         for p, h, x, y in ARMIES)
            drawn = sum(a != b for a, b in zip(want, rom.map_vram()))
            print(f"  armies in WRAM at the shot {placed}/{len(ARMIES)}, {drawn} tilemap bytes differ from the plain map")
            bad += placed != len(ARMIES)
        same = sum(a == b for a, b in zip(vram, want))
        pal_ok = colours_ok(cgram[2 * lo:2 * hi], rom.raw(MAP_PALETTE, 2 * (hi - lo)))
        obj_ok = cgram[0x1C0:0x200] == rom.raw(MAP_MARKER_COLOURS, 64)
        marks = start = 0
        for c in range(COUNTRY_COUNT):
            f = wram[COUNTRY_WRAM_SIZE * c]
            start += f == rom.country(k, c)["勢力"]
            x, y = rom.position(c)
            tile, attr, _ = rom.marker(f)
            got = tuple(oam[4 * (c + 1):4 * (c + 1) + 4])
            if got == ((4 * x - 2) & 0xFF, (4 * y - 2) & 0xFF, tile, attr):
                marks += 1
            else:
                print(f"  NG {year} {rom.country_name(c)}: OBJ {got} (want {(4 * x - 2, 4 * y - 2, tile, attr)})")
        ok = same == len(want) and pal_ok and obj_ok and marks == COUNTRY_COUNT
        bad += not ok
        print(f"{year}: VRAM {same}/{len(want)} bytes, colours 0x{lo:02X}-0x{hi - 1:02X} {'OK' if pal_ok else 'NG'}, "
              f"marker colours {'OK' if obj_ok else 'NG'}, markers {marks}/{COUNTRY_COUNT} "
              f"(factions as at the start: {start}/{COUNTRY_COUNT}){'' if ok else '  NG'}")
    print(f"{time.time() - t0:.0f} s")
    print("ALL OK" if not bad else f"{bad} mismatch(es)")
    raise SystemExit(1 if bad else 0)


if __name__ == "__main__":
    main()
