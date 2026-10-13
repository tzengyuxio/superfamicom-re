#!/usr/bin/env python3
"""Check the field-battle maps (rom.Rom.field_layers, field tiles and palettes) against the game (needs Mesen 2).

蠣崎季広 attacks 三戸城 in 信長初陣 (軍事 -> 戦争). That battle is fought on field maps 57-59, 87-89,
117-119 and 147-149; the BG1 / BG2 tilemaps (VRAM word 0x3400 / 0x3800, 32 x 32) then show maps 57 and 87
whole at column 1, rows 2 and 14. A savestate is taken on the 方針確認 screen, before the maps are loaded;
for every round two other maps are patched into slots 57 and 87 of FIELD_TABLE and the state replayed, so
the game's own loader puts them on screen. Every cell must show the ROM entry + 0x0D20 (overlay entries
0 and FFFF: 0); cells under the game's windows (tile below 0x120) are counted apart. The first round also
checks the field tiles (VRAM tiles 0x120-0x31F) and colours 1-15 of CGRAM palettes 3-6 (colour 0 is
transparent; the game leaves it 0).

Usage: .venv/bin/python tenshouki/verify_field_maps.py [--rom ROM]
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
from mesen import Mesen
from rom import (
    DEFAULT_ROM,
    FIELD_COUNT,
    FIELD_MAP_H,
    FIELD_MAP_W,
    FIELD_PALETTES,
    FIELD_SHOWN,
    FIELD_TABLE,
    FIELD_TILE0,
    FIELD_TILES_ENTRY,
    TILE_TABLE,
    Rom,
)

NMI = 0x008FC3
# title -> 信長初陣 -> 蠣崎季広 -> first turn -> 軍事 -> 戦争 -> 三戸城 -> 可 -> (B) -> 可: the 方針確認 screen
INPUTS = ("w1100 start w300 start w300 a w300 a w300 a w300 a w300 start w300 down*8 w30 a w300 a w600 w8400"
          " a w200 a w300 down w60 a w300 a w300 b w300 a w300 w300")
SLOTS = [(57, 0, 0), (87, 0, 1)]   # (slot, map column, map row) of the maps shown whole
ORIGIN = (1, 2)                    # BG cell of the battle's top-left tile
BG = (0x3400, 0x3800)
SHOT_AFTER = 340

LUA = """
local presses={%(presses)s}
local rounds={%(rounds)s}
local f, idx, state = 0, 0, nil
local want_save, want_load = false, false
emu.addEventCallback(function()
  local inp={}
  for _,p in ipairs(presses) do if f>=p[1] and f<p[1]+p[3] then inp[p[2]]=true end end
  emu.setInput(inp,0)
end, emu.eventType.inputPolled)
emu.addMemoryCallback(function()  -- savestates only work inside exec callbacks: use the NMI handler
  if want_save then state=emu.createSavestate(); want_save=false; want_load=true end
  if want_load then
    want_load=false
    idx=idx+1
    if idx>#rounds then emu.log("DONE"); emu.breakExecution(); return end
    emu.loadSavestate(state)
    for _,w in ipairs(rounds[idx]) do emu.write(w[1], w[2], emu.memType.snesPrgRom) end
    f=%(save)d
  end
end, emu.callbackType.exec, %(nmi)d)
local function hex(mem, a, n)
  local out={}
  for i=0,n-1 do out[#out+1]=string.format("%%02x", emu.read(a+i, mem, false)) end
  return table.concat(out)
end
emu.addEventCallback(function()
  f=f+1
  if f==%(save)d and state==nil then want_save=true end
  if state~=nil and f==%(shot)d then
    local s="ROUND " .. idx .. " " .. hex(emu.memType.snesVideoRam, %(bg)d, 4096)
    if idx<=2 then
      s=s .. " " .. hex(emu.memType.snesVideoRam, %(tiles)d, 16384) .. " " .. hex(emu.memType.snesCgRam, 96, 128)
    end
    emu.log(s)
    want_load=true
    emu.breakExecution()
  end
end, emu.eventType.endFrame)
"""


def schedule(inputs: str) -> list[tuple[int, str, int]]:
    """(frame, button, hold) presses: <button>[*n] holds 4 frames then waits 20, w<n> waits n frames."""
    out, f = [], 10
    for step in inputs.split():
        if step.startswith("w"):
            f += int(step[1:])
            continue
        button, _, n = step.partition("*")
        for _ in range(int(n or 1)):
            out.append((f, button, 4))
            f += 24
    return out


def capture(rom_path: str, data: bytes, rounds: list[list[int]]) -> list[str]:
    """Log lines ("ROUND i <BG1+BG2 hex> [<tiles hex> <CGRAM 3-6 hex>]"), one per round of slot maps."""
    presses = schedule(INPUTS)
    save = presses[-1][0] + 24 + 590
    presses.append((save + 10, "b", 15))  # end 方針確認: the battle loads
    patches = []
    for maps in [rounds[0], *rounds]:  # the first replay still runs unpatched: done twice
        writes = []
        for (slot, _, _), n in zip(SLOTS, maps):
            for k in range(3):
                writes.append(f"{{{FIELD_TABLE + 3 * slot + k},{data[FIELD_TABLE + 3 * n + k]}}}")
        patches.append("{" + ",".join(writes) + "}")
    lua = LUA % {"presses": ",".join(f'{{{f},"{b}",{h}}}' for f, b, h in presses), "rounds": ",".join(patches),
                 "save": save, "shot": save + 10 + SHOT_AFTER, "nmi": NMI, "bg": 2 * BG[0],
                 "tiles": 2 * 16 * FIELD_TILE0}
    out = []
    with Mesen(rom_path) as m:
        m.run(lua, 900)
        while True:
            line = m.log().rstrip().rsplit("\n", 1)[-1]
            if line == "DONE":
                break
            out.append(line)
            m.resume(120)
    return out[1:]


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證野戰地圖")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    rounds = [[57, 87]] + [[n, min(n + 1, FIELD_COUNT - 1)] for n in range(0, FIELD_COUNT, 2)]
    lines = capture(args.rom, rom.data, rounds)
    errors = 0
    tiles = rom.table_entry(TILE_TABLE, FIELD_TILES_ENTRY)
    shown_tiles, cgram = bytes.fromhex(lines[0].split()[3]), bytes.fromhex(lines[0].split()[4])
    ok = sum(shown_tiles[32 * t:32 * t + 32] == tiles[32 * t:32 * t + 32] for t in range(len(tiles) // 32))
    want = rom.data[FIELD_PALETTES:FIELD_PALETTES + 128]
    pal_ok = all(cgram[i:i + 2] == want[i:i + 2] for i in range(0, 128, 2) if i % 32)
    errors += len(tiles) // 32 - ok + (not pal_ok)
    print(f"[tiles] {ok}/{len(tiles) // 32} VRAM tiles 0x{FIELD_TILE0:X}+ match; CGRAM palettes 3-6 colours 1-15 "
          + ("OK" if pal_ok else "NG"))
    checked, bad_maps, cells, covered = set(), [], 0, 0
    for maps, line in zip(rounds, lines):
        vram = bytes.fromhex(line.split()[2])
        words = [vram[2 * i] | vram[2 * i + 1] << 8 for i in range(2048)]
        for (_, mc, mr), n in zip(SLOTS, maps):
            bad = 0
            for layer, entries in enumerate(rom.field_layers(n)):
                for i, t in enumerate(entries):
                    x = ORIGIN[0] + mc * FIELD_MAP_W + i % FIELD_MAP_W
                    y = ORIGIN[1] + mr * FIELD_MAP_H + i // FIELD_MAP_W
                    got = words[1024 * layer + y % 32 * 32 + x % 32]
                    want = 0 if layer and t in (0, 0xFFFF) else (t + FIELD_SHOWN) & 0xFFFF
                    if got != want and (got & 0x3FF) < FIELD_TILE0:
                        covered += 1
                    elif got != want:
                        bad += 1
                    else:
                        cells += 1
            checked.add(n)
            if bad:
                bad_maps.append((n, bad))
    errors += len(bad_maps) + (len(checked) != FIELD_COUNT)
    print(f"[maps] {len(checked) - len(bad_maps)}/{FIELD_COUNT} field maps match on BG1 + BG2 "
          f"({cells} cells; {covered} under windows)" + (f" NG {bad_maps[:10]}" if bad_maps else ""))
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
