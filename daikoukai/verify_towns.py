#!/usr/bin/env python3
"""Check the port records and the town pictures (rom.Rom.ports / town_tilemap / town_chr / TOWN_PALETTES) against
the game (Mesen 2, ~2 min).

A new game is played to just before the first town screen (Lisbon) and a savestate taken. For every run the
current port ($7E:EF69) is set to port p, and for a few runs the port's building flags ($7E:EE78 + p) too; the
game then builds that port's town screen. Checked:
- the game seeks the DATA file (handle $7E:1E1C, ROM DATA) to 0x12D4 + 19 p, i.e. reads the port record that
  rom.PORTS decodes (svc $1A calls logged);
- the BG2 tilemap (32 x 28 entries at VRAM 0xE000) equals rom.town_tilemap(p, flags): frame, picture and the
  pieces the flags select;
- the BG CHR equals rom.town_chr() (read for ports 0 and 55; the 32 water tiles 0x77-0x96 animate, so they are
  counted apart) and the 8 BG palettes equal TOWN_PALETTES.

Usage: .venv/bin/python daikoukai/verify_towns.py [--rom ROM]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "tools"))
from boot import NEW_GAME, TOWN_SAVE, TOWN_SHOT, TOWN_STEPS
from replay import replay
from rom import DATA, DEFAULT_ROM, PORT_COUNT, PORT_SIZE, PORTS, TOWN_FLAGS, TOWN_H, TOWN_PALETTES, TOWN_W, Rom, le16

PORT = 0xEF69
FLAGS = 0xDF02 + TOWN_FLAGS
DATA_HANDLE = 0x1E1C
WATER = range(0x77, 0x97)
CHR_FIRST, CHR_END = 0x77, 0x361     # town CHR tiles; read back for a trading and a supply port only
CHR_PORTS = (0, 55)
# extra runs with patched building flags: (port, flags)
FLAG_RUNS = [(3, 0x00), (3, 0x10), (3, 0x14), (10, 0x04), (10, 0x10), (10, 0x1F), (0, 0x00), (0, 0x04),
             (55, 0x14)]
HOOK = """
local function rd(a) return emu.read(a, emu.memType.snesMemory) end
local L = {}
EXTRA_RESET = function() L = {} end
EXTRA_SHOT = function() return "00" .. table.concat(L, "") end
emu.addMemoryCallback(function()
  if rd(0x52) ~= 0x1A or (rd(0x54) | rd(0x55) << 8) ~= 0x1E1C or rd(0x5A) ~= 0 then return end
  if #L < 64 then L[#L+1] = string.format("%02x%02x", rd(0x56), rd(0x57)) end
end, emu.callbackType.exec, 0x008DDD)
"""  # DATA_HANDLE


def main() -> None:
    ap = argparse.ArgumentParser(description="以模擬器驗證港口記錄與港町圖")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    t0 = time.time()
    rom = Rom(args.rom)
    cases = [(p, None) for p in range(PORT_COUNT)] + FLAG_RUNS
    reads = [("vram", 0xE000, 64 * TOWN_H), ("cgram", 0, 256), ("wram", 0x1E1C, 4)]
    chr_reads = [("vram", 0x2000 + 32 * CHR_FIRST, 32 * (CHR_END - CHR_FIRST))]
    runs = [{"wram": [(PORT, bytes([p]))] + ([] if f is None else [(FLAGS + p, bytes([f]))]),
             "steps": TOWN_STEPS, "shot": TOWN_SHOT, "read": reads + (chr_reads if p in CHR_PORTS and f is None else [])}
            for p, f in cases]
    res = replay(args.rom, NEW_GAME, TOWN_SAVE, runs, extra_lua=HOOK)
    chr_ = rom.town_chr()
    pals = b"".join(rom.data[o:o + 32] for o in TOWN_PALETTES)
    seek_ok = tm_ok = chr_ok = pal_ok = 0
    handle_ok = True
    water = set()
    bad = []
    n_chr = 0
    for (p, f), r in zip(cases, res):
        tm, cg, handle = r[:3]
        vchr, seeks = (r[3], r[4]) if len(r) == 5 else (None, r[3])
        # handle record: +0 bank, +2 address (LoROM) -> file offset
        bank, addr = le16(handle, 0), le16(handle, 2)
        handle_ok &= (bank & 0x7F) * 0x8000 + (addr & 0x7FFF) == DATA
        pos = {le16(seeks, 1 + 2 * i) for i in range((len(seeks) - 1) // 2)}
        s = PORTS - DATA + PORT_SIZE * p in pos
        got = [le16(tm, 64 * y + 2 * x) for y in range(TOWN_H) for x in range(TOWN_W)]
        t = got == rom.town_tilemap(p, f)
        c = True
        if vchr is not None:
            n_chr += 1
            c = all(vchr[32 * (k - CHR_FIRST):][:32] == b for k, b in chr_.items() if k not in WATER and k < CHR_END)
            water |= {k for k in WATER if vchr[32 * (k - CHR_FIRST):][:32] == chr_[k]}
        pl = cg == pals
        seek_ok += s
        tm_ok += t
        chr_ok += c and vchr is not None
        pal_ok += pl
        if not (s and t and c and pl):
            bad.append((p, f, s, t, c, pl))
    n = len(cases)
    print(f"[ports] DATA file handle $7E:1E1C -> file 0x{DATA:X}: {'OK' if handle_ok else 'NG'}; "
          f"seek to the port record DATA + 0x{PORTS - DATA:X} + 19p: {seek_ok}/{n}")
    print(f"[towns] BG2 tilemap 32x28 = rom.town_tilemap: {tm_ok}/{n} "
          f"({PORT_COUNT} ports with new-game flags + {len(FLAG_RUNS)} runs with patched flags)")
    print(f"[towns] BG CHR = rom.town_chr (without water tiles, ports {CHR_PORTS}): {chr_ok}/{n_chr}; water tiles equal to the first "
          f"frame in some run: {len(water)}/{len(WATER)}; 8 BG palettes = TOWN_PALETTES: {pal_ok}/{n}")
    if bad:
        print("NG (port, flags, seek, tilemap, chr, palettes):", bad[:10])
    print(f"{n} runs, {time.time() - t0:.0f} s")
    errors = len(bad) + (not handle_ok)
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
