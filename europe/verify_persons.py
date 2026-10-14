#!/usr/bin/env python3
"""Check the general records, biographies, portraits and the text code -> glyph mapping against the game's own
ability review screen (needs Mesen 2, a few minutes).

Scenario 1, one player, 枢軸軍: 将軍の能力を検討せよ shows the 10 Axis generals (block slots 0-9) one by one with
name, 指揮 魅力 経験, 歩兵 砲兵 戦車, the portrait and 7 lines of biography. For each run the 10 slots of scenario
1's block are replaced in the ROM by other records, and the review routine's random roll ($C1:01F9: base +
rand(41) - 20, or capped at 99) is patched to return the base value, so the screen shows the record as stored.
Captured with exec callbacks while the game draws (tools/replay.py savestate replay):
  - $C1:195E (print string) with a pointer into the block copy ($7E:2220 + 22 k): the 9 name bytes
  - $C1:286A (vprintf) with format $CA:6472 / $CA:6486: 指揮 魅力 経験 / 歩兵 砲兵 戦車
  - $C1:195E with a pointer into the biography text: the 7 line pointers must be Rom.bio_pointer(id, line)
  - on the page's last print ($C6:8DB4, "a:change b:next"): VRAM 0xEC00 (the portrait's 30 tiles, 960 bytes)
    must be Rom.face_tiles(id) and CGRAM palette 11 the ROM copy FACE_PALETTE
  - $C1:1A06 / $C1:1A69 (glyph upload): text code -> source address must be rom.glyph_address(code)
Runs cover person ids 0-93 with their records (first scenario they appear in), then ids 94-99 (leaders, their
own records) and 100-119 (person 0's record with +20 patched) for the portraits only. The biography table has
only 94 x 7 pointers, so in those runs the pointers the game reads for ids 94-119 (past the table, over the start
of the biography text) are patched to an empty line; the glyph check uses the runs of ids 0-89 only.

Usage: .venv/bin/python europe/verify_persons.py [--rom ROM]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
from replay import replay
from rom import (
    BIO_LINES,
    BIOGRAPHIES,
    DEFAULT_ROM,
    FACE_BYTES,
    FACE_COUNT,
    FACE_PALETTE,
    GENERAL_SIZE,
    GENERALS_AT,
    PERSON_COUNT,
    SCENARIO_BLOCKS,
    Rom,
    glyph_address,
)
from scenes import EVENTS_LUA, ONE_PLAYER_AXIS, REVIEW_NEXT, TITLE, events, length, save_frame, scenario

PAGES = 10                               # scenario 1 has 10 Axis generals
ROLL = 0x101F9                           # $C1:01F9
ROLL_PATCH = bytes.fromhex("a304" "29ff00" "8500" "6b")   # LDA $04,s / AND #$FF / STA $00 / RTL
NAME_WRAM = 0x7E2220
FACE_VRAM = 0xEC00
EMPTY_LINE = 0xC6D152                    # an empty biography line (person 0, line 7)

LUA = EVENTS_LUA + """
local code = 0
local base_reset = EXTRA_RESET
EXTRA_RESET = function() base_reset(); SEEN_G = {} end
emu.addMemoryCallback(function()
  local p = arg_ptr(4)
  if p >= 0x7E2220 and p < 0x7E2220 + 40 * 22 then EVENTS[#EVENTS + 1] = "N" .. hex(p, 9)
  elseif p == 0xC68DB4 then
    EVENTS[#EVENTS + 1] = "F" .. mem_hex("snesVideoRam", 0xEC00, 960) .. "P" .. mem_hex("snesCgRam", 0x160, 32)
  elseif p >= 0xC6C000 and p < 0xC70000 then EVENTS[#EVENTS + 1] = string.format("T%06X", p) end
end, emu.callbackType.exec, 0xC1195E, 0xC1195E)
emu.addMemoryCallback(function()
  local f = arg_ptr(4)
  if f == 0xCA6472 or f == 0xCA6486 then
    EVENTS[#EVENTS + 1] = (f == 0xCA6472 and "A" or "B") .. hex(arg_ptr(8), 6)
  end
end, emu.callbackType.exec, 0xC1286A, 0xC1286A)
emu.addMemoryCallback(function() code = emu.getState()["cpu.a"] end, emu.callbackType.exec, 0xC11A06, 0xC11A06)
emu.addMemoryCallback(function()
  local sp = emu.getState()["cpu.sp"]
  local src = rd(sp + 3) + rd(sp + 4) * 256 + rd(sp + 5) * 65536
  local key = string.format("G%04X:%06X", code, src)
  if not SEEN_G then SEEN_G = {} end
  if not SEEN_G[key] then SEEN_G[key] = true; EVENTS[#EVENTS + 1] = key end
end, emu.callbackType.exec, 0xC11A69, 0xC11A69)
"""


def plan(rom: Rom) -> list[list[tuple[int, bytes]]]:
    """Per run: 10 (id, 22-byte record) for the block slots 0-9."""
    persons = {p["id"]: p["raw"] for p in rom.persons()}
    items = [(pid, persons[pid]) for pid in range(PERSON_COUNT + 6)]
    base = bytearray(persons[0])
    for pid in range(PERSON_COUNT + 6, FACE_COUNT):
        base[20] = pid
        items.append((pid, bytes(base)))
    return [items[k:k + PAGES] for k in range(0, len(items), PAGES)]


def check_run(rom: Rom, chunk: list[tuple[int, bytes]], ev: list[str], glyphs: dict) -> list[str]:
    bad = []
    pages, cur = [], None
    for e in ev:
        if e[0] == "N":
            cur = {"name": bytes.fromhex(e[1:]), "A": None, "B": None, "T": [], "F": None, "P": None}
            pages.append(cur)
        elif e[0] == "G":
            code, src = e[1:].split(":")
            glyphs[int(code, 16)] = int(src, 16)
        elif cur is None:
            continue
        elif e[0] in "AB":
            raw = bytes.fromhex(e[1:])
            cur[e[0]] = [raw[0], raw[2], raw[4]]
        elif e[0] == "T":
            cur["T"].append(int(e[1:], 16))
        elif e[0] == "F":
            f, p = e[1:].split("P")
            cur["F"], cur["P"] = bytes.fromhex(f), bytes.fromhex(p)
    if len(pages) != len(chunk):
        return [f"ids {chunk[0][0]}-{chunk[-1][0]}: {len(pages)} review pages, expected {len(chunk)}"]
    pal = rom.data[FACE_PALETTE:FACE_PALETTE + 32]
    for (pid, rec), pg in zip(chunk, pages):
        g = rom.general(rec)
        if pg["F"] != rom.face_tiles(pid) or pg["P"] != pal:
            bad.append(f"id {pid}: portrait / palette differ")
        if pid >= PERSON_COUNT:
            continue
        if pg["name"] != rec[:9]:
            bad.append(f"id {pid}: name {pg['name'].hex()} != {rec[:9].hex()}")
        if pg["A"] != [g["指揮"], g["魅力"], g["経験"]] or pg["B"] != [g["歩兵"], g["砲兵"], g["戦車"]]:
            bad.append(f"id {pid} {g['name']}: screen {pg['A']} {pg['B']}")
        want = [rom.bio_pointer(pid, k) | 0xC00000 for k in range(7)]
        if pg["T"][:7] != want:
            bad.append(f"id {pid}: biography pointers {[hex(x) for x in pg['T'][:7]]}")
    return bad


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證將領能力、經歷、頭像與字碼")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    t0 = time.time()
    rom = Rom(args.rom)
    chunks = plan(rom)
    steps = scenario(1) + " " + ONE_PLAYER_AXIS + " " + " ".join([REVIEW_NEXT] * (PAGES - 1)) + " w300"
    empty = EMPTY_LINE.to_bytes(3, "little")
    past_table = BIOGRAPHIES + 3 * BIO_LINES * PERSON_COUNT
    runs = []
    for chunk in chunks:
        recs = b"".join(r for _, r in chunk)
        recs += rom.block(0)[GENERALS_AT + len(recs):GENERALS_AT + PAGES * GENERAL_SIZE]
        patch = [(ROLL, ROLL_PATCH), (SCENARIO_BLOCKS[0] + GENERALS_AT, recs)]
        if chunk[-1][0] >= PERSON_COUNT:
            patch.append((past_table, empty * (BIO_LINES * (FACE_COUNT - PERSON_COUNT))))
        runs.append({"patch": patch, "steps": steps, "shot": length(steps), "read": [("wram", 0, 1)]})
    shots = replay(args.rom, TITLE, save_frame(TITLE), runs, extra_lua=LUA)
    bad, glyphs = [], {}
    for chunk, (_, raw) in zip(chunks, shots):
        bad += check_run(rom, chunk, events(raw), glyphs if chunk[-1][0] < PERSON_COUNT else {})
    n_faces = sum(len(c) for c in chunks)
    print(f"[review] ids 0-{PERSON_COUNT - 1}: name, 指揮 魅力 経験, 歩兵 砲兵 戦車, 7 biography line pointers; "
          f"portraits 0-{n_faces - 1} (VRAM 0x{FACE_VRAM:04X}, {FACE_BYTES} bytes) and CGRAM palette 11")
    gbad = [f"{c:04X}->{s:06X}" for c, s in glyphs.items() if s != glyph_address(c)]
    high = sum(c >= 0x89F0 for c in glyphs)
    print(f"[glyphs] {len(glyphs) - len(gbad)}/{len(glyphs)} text codes copied from rom.glyph_address(code) "
          f"({high} codes >= 0x89F0)" + (f" NG {gbad[:8]}" if gbad else ""))
    bad += gbad
    for b in bad[:20]:
        print("  NG", b)
    print(f"{'ALL OK' if not bad else f'{len(bad)} problem(s)'} ({time.time() - t0:.0f} s)")
    raise SystemExit(1 if bad else 0)


if __name__ == "__main__":
    main()
