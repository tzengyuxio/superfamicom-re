#!/usr/bin/env python3
"""Check the big map and the battle maps against the game (needs Mesen 2, about 2 minutes).

Plays scenario 1 as 劉繇 in Mesen (tools/mesen.py):
- Big map, at the first turn: the mode-7 plane in VRAM (low bytes rows 0-95 = tilemap, high bytes = the
  256 tiles) must equal rom.Rom.map_tilemap / map_chars, CGRAM rows 3-7 and 14-15 must equal the ROM
  palettes and rows 12-13 one of the 4 water frames. The city table CITY_VIEW is checked against the
  castle icons of the tilemap and the screen scroll (the turn starts centred on 寿春).
- Field battle: 劉繇 attacks 徐州 from 寿春 (a savestate is taken before the battle starts). The map number
  the game picks ($7E:3DAA at the loader $C7:5CA7) must be rom.Rom.field_map(徐州, 寿春); the BG2 tilemap
  (32 columns visible of 40) must equal layer 1 of that map, the tiles at VRAM 0x2000 the field tiles and
  CGRAM palettes 4-6 palette set 3 (month 12).
- Siege battle: the same attack replayed with $7E:3DAE (field flag) cleared on entry to $D1:9773, which
  makes the game load the siege map of 徐州 (45 + 17) with the siege tiles and palettes; same checks.

Usage: .venv/bin/python san4/verify_maps.py [--rom ROM]
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
from mesen import SNES_CGRAM, SNES_VRAM, Mesen
from rom import (
    BATTLE_COUNT,
    BATTLE_TILES_H,
    BATTLE_TILES_W,
    DEFAULT_ROM,
    FIELD_COUNT,
    MAP_H,
    MAP_PALETTE,
    MAP_PALETTE2,
    MAP_WATER,
    Rom,
    le16,
)

NMI = 0x008FA4
HOLD = 10
SHOUSHUN, XUZHOU = 31, 17
# title -> scenario 1 -> 劉繇 -> settings -> first turn (TURN) -> 軍事 -> 戦争 -> 徐州 -> 大将 劉繇 -> 30 soldiers
# -> 0 gold, 1 food -> 可 -> next turn messages -> battle
TURN = ("w1300 start w600 a w600 a w800 a w600 a w600 a w600 up w200 a w600 a w500 a w500 a w500 a w500 a w4000")
ATTACK = ("a w200 right w60 right w60 a w300 up:20 w60 up:20 w60 a w300 a w300 a w300 down w60 down w60 down w60 "
          "down w60 down w60 a w300 a w300 up:60 w60 a w300 down w60 down w60 down w60 down w60 down w60 a w300 "
          "a w300 a w300 a w300 a w300 a w600 a w600")
TURN_SHOT = 12290   # first turn screen, map centred on 寿春
SAVE_AT = 17000     # before the battle is set up
SCROLL = (8, 0)     # observed BG scroll minus CITY_VIEW of the city in focus

LUA = """
local presses={%(presses)s}
local f, idx, state = 0, 0, nil
local want_save, want_load = false, false
emu.addEventCallback(function()
  local inp={}
  for _,p in ipairs(presses) do
    if f>=p[1] and f<p[1]+p[3] then inp[p[2]]=true end
  end
  emu.setInput(inp,0)
end, emu.eventType.inputPolled)
emu.addMemoryCallback(function()  -- savestates only work inside exec callbacks: use the NMI handler
  if want_save then state=emu.createSavestate(); want_save=false end
  if want_load then
    want_load=false
    idx=idx+1
    if idx>2 then emu.log("DONE"); emu.breakExecution(); return end
    emu.loadSavestate(state)
    f=%(save)d
  end
end, emu.callbackType.exec, %(nmi)d)
emu.addMemoryCallback(function()  -- pass 1 and 2: force a siege battle
  if idx>=1 then emu.write(0x7E3DAE, 0, emu.memType.snesMemory) end
end, emu.callbackType.exec, 0xD19773)
local mapno = -1
emu.addMemoryCallback(function()
  mapno = emu.read(0x7E3DAA, emu.memType.snesMemory)
end, emu.callbackType.exec, 0xC75CA7)
emu.addEventCallback(function()
  f=f+1
  if idx==0 and f==%(turn)d then
    local s=emu.getState()
    emu.log(string.format("TURN %%d %%d", s["ppu.layers[0].hscroll"], s["ppu.layers[0].vscroll"]))
    emu.breakExecution()
  end
  if f==%(save)d and state==nil then want_save=true end
  if f==%(end)d then
    emu.log(string.format("BATTLE %%d %%d", idx, mapno))
    mapno=-1
    want_load=true
    emu.breakExecution()
  end
end, emu.eventType.endFrame)
"""


def schedule(inputs: str, f: int = 10) -> tuple[list[tuple[int, str, int]], int]:
    """(frame, button, hold) presses: button[:hold] (default HOLD frames), w<n> waits n frames."""
    out = []
    for step in inputs.split():
        if step.startswith("w"):
            f += int(step[1:])
        else:
            b, _, h = step.partition(":")
            h = int(h) if h else HOLD
            out.append((f, b, h))
            f += h
    return out, f


def capture(rom_path: str) -> dict:
    presses, end = schedule(TURN + " " + ATTACK)
    lua = LUA % {"presses": ",".join(f'{{{f},"{b}",{h}}}' for f, b, h in presses), "save": SAVE_AT, "end": end,
                 "turn": TURN_SHOT, "nmi": NMI}
    out = {}
    with Mesen(rom_path) as m:
        m.run(lua, 900)
        while True:
            line = m.log().rstrip().rsplit("\n", 1)[-1]
            if line == "DONE":
                break
            parts = line.split()
            if parts[0] == "TURN":
                out["turn"] = (int(parts[1]), int(parts[2]), m.memory(SNES_VRAM), m.memory(SNES_CGRAM))
            else:
                out[int(parts[1])] = (int(parts[2]), m.memory(SNES_VRAM), m.memory(SNES_CGRAM))
            m.resume(300)
    return out


def check_big_map(rom: Rom, hs: int, vs: int, vram: bytes, cgram: bytes) -> int:
    tm, ch = rom.map_tilemap(), rom.map_chars()
    rows = MAP_H * 128
    t_ok = sum(a == b for a, b in zip(vram[0:2 * rows:2], tm[:rows]))
    c_ok = vram[1::2][:len(ch)] == ch
    p_ok = cgram[0x60:0x100] == rom.data[MAP_PALETTE:MAP_PALETTE + 0xA0] and \
        cgram[0x1C0:0x200] == rom.data[MAP_PALETTE2:MAP_PALETTE2 + 0x40]
    water = [k for k, o in enumerate(MAP_WATER) if cgram[0x180:0x1C0] == rom.data[o:o + 0x40]]
    print(f"[big map] tilemap rows 0-{MAP_H - 1}: {t_ok}/{rows} cells match; 256 tiles "
          f"{'match' if c_ok else 'DIFFER'}; CGRAM rows 3-7, 14-15 {'match' if p_ok else 'DIFFER'}; "
          f"rows 12-13 = water frame {water or 'none'}")
    cities = rom.cities()
    icons = sum(tm[c["map_y"] * 128 + c["map_x"]] == 4 and tm[c["map_y"] * 128 + c["map_x"] + 1] == 5
                and tm[(c["map_y"] + 1) * 128 + c["map_x"]] == 6 for c in cities)
    c = cities[SHOUSHUN]
    scroll_ok = (hs - c["view_x"], vs - c["view_y"]) == SCROLL
    print(f"[cities] {icons}/{len(cities)} CITY_VIEW positions sit on a castle icon (tiles 04 05 / 06 07); "
          f"turn scroll ({hs}, {vs}) = 寿春 view ({c['view_x']}, {c['view_y']}) + {SCROLL}: {scroll_ok}")
    return (t_ok != rows) + (not c_ok) + (not p_ok) + (not water) + (icons != len(cities)) + (not scroll_ok)


def check_battle(rom: Rom, label: str, want: int, got: int, vram: bytes, cgram: bytes) -> int:
    siege = want >= FIELD_COUNT
    bg = rom.battle_stream(2 * BATTLE_COUNT + want)
    n = BATTLE_TILES_W * BATTLE_TILES_H
    layer = [le16(bg, 2 * (n + i)) for i in range(n)]
    tmap = [le16(vram, 0x7800 + 2 * i) for i in range(1024)]  # BG2 tilemap at VRAM word 0x3C00
    best = (0, 0, 0, 0, 0)
    for oy in range(10):  # the screen shows tilemap columns 1-30 = map columns sx+1 .. sx+30
        for sx in range(-1, BATTLE_TILES_W - 30):
            hit = tot = pal = 0
            for r in range(BATTLE_TILES_H):
                for c in range(1, 31):
                    mc = c + sx
                    if 0 <= mc < BATTLE_TILES_W and r + oy < 32:
                        a, b = tmap[(r + oy) * 32 + c], layer[r * BATTLE_TILES_W + mc]
                        tot += 1
                        hit += a & 0x3FF == b & 0x3FF
                        pal += a != b and a & 0x3FF == b & 0x3FF
            best = max(best, (hit, tot, pal, oy, sx))
    ch = rom.battle_chars(siege)
    tiles = len(ch) // 32
    bad = {t for t in range(tiles) if vram[0x2000 + 32 * t:0x2000 + 32 * t + 32] != ch[32 * t:32 * t + 32]}
    used = {(e & 0x3FF) - 0x100 for m in rom.battle_maps() if (m["id"] >= FIELD_COUNT) == siege
            for L in m["layers"] for e in L}
    pals = rom.battle_palettes(3, siege)
    p_ok = all(le16(cgram, 32 * p + 2 * i) == v[i] for p, v in pals.items() if p < 7 for i in range(16))
    game = got + FIELD_COUNT if siege else got  # siege: $7E:3DAA holds the city, the loader adds 45
    print(f"[{label}] game map {game}, ROM {want}; BG2 tilemap: {best[0]}/{best[1]} visible cells have the tile "
          f"of layer 1 ({best[2]} of them recoloured by the deployment highlight); tiles at VRAM 0x2000: "
          f"{tiles - len(bad)}/{tiles} match" + (f" (differing {sorted(hex(t + 0x100) for t in bad)} are used by "
                                                 f"no map: {not bad & used})" if bad else "")
          + f"; CGRAM palettes 4-6 = set 3: {p_ok}")
    return (game != want) + (best[0] != best[1] or best[1] < 600) + bool(bad & used) + (not p_ok)


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證大地圖與戰場地圖")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    got = capture(args.rom)
    errors = check_big_map(rom, *got["turn"])
    errors += check_battle(rom, "field battle 寿春 -> 徐州", rom.field_map(XUZHOU, SHOUSHUN), *got[0])
    errors += check_battle(rom, "siege battle 徐州 (forced)", FIELD_COUNT + XUZHOU, *got[2])
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
