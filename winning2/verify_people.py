#!/usr/bin/env python3
"""Check the people's names in Mesen with the game's own name functions, printed by the horse card.

The horse card ($C3:360A) prints the sire as `父 :%-9s` with the name from $C4:64A7(stallion id). Each run patches
$C4:64A7 into a jump (JML) to one of the game's person-name functions, which take the id the same way and return
the name the same way, and sets racehorse 0's sire byte to the person id (the new-game blocks are written back
first, as in verify_horses.py):

  jockeys    $C4:A698 (ids 0-59 from WRAM $9D58, 60-109 from ROM $E9:0000, $C4:A3DB)
  trainers   $C4:AE9E
  owners     $C4:B4A7 (id 28 = the player, not checked)

(Program '96: card $C4:4077, $CA:10BC; jockeys $CC:43EC, trainers $CE:1584, owners $CC:4C0A.)

The printed name must be rom.py's surname part + given part (8 foreign jockeys have no given part, 0xFFFF: the
game then prints the surname followed by bytes from past the table; only the surname is compared).

Usage: .venv/bin/python winning2/verify_people.py [--rom ROM]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "tools"))
import w2  # noqa: I001 (puts tools/ on sys.path)
import printf_trace
from replay import end_frame, replay
from rom import DEFAULT_ROM, INIT_COPIES, INIT_WRAM_96, OWNER_COUNT, RACEHORSE_SIZE, Rom

ADDR = {
    "original": {"card": 0xC3360A, "stallion_name": 0xC464A7, "sire_fmt": 0xC3E6E0,
                 "jockey": 0xC4A698, "trainer": 0xC4AE9E, "owner": 0xC4B4A7},
    "program96": {"card": 0xC44077, "stallion_name": 0xCA10BC, "sire_fmt": 0xC4F5AE,
                  "jockey": 0xCC43EC, "trainer": 0xCE1584, "owner": 0xCC4C0A},
}
LUA = """
emu.addMemoryCallback(function()
  local sp = emu.getState()["cpu.sp"]
  emu.write(sp + 4, 0, emu.memType.snesMemory); emu.write(sp + 5, 0, emu.memType.snesMemory)
end, emu.callbackType.exec, @CARD@)
"""


def main() -> None:
    ap = argparse.ArgumentParser(description="用遊戲的人名函式驗證騎手、調教師、馬主姓名")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    if rom.version not in ADDR:
        raise SystemExit(f"{rom.version}: function addresses not known")
    a = ADDR[rom.version]
    t0 = time.time()
    init = [(INIT_WRAM_96[k] if rom.version == "program96" else w, rom.data[rom.o[k]:rom.o[k] + n])
            for k, w, n in INIT_COPIES]
    groups = {"jockey": rom.jockeys(), "trainer": rom.trainers(), "owner": rom.owners()[:OWNER_COUNT - 1]}
    runs, expect = [], []
    for kind, rows in groups.items():
        f = a[kind]
        jml = bytes([0x5C, f & 0xFF, f >> 8 & 0xFF, f >> 16])
        for p in rows:
            rec = bytearray(init[0][1][:RACEHORSE_SIZE])
            rec[4] = p["index"]
            runs.append({"patch": [(a["stallion_name"] & 0x3FFFFF, jml)], "wram": init + [(init[0][0], bytes(rec))],
                         "steps": "a:10 w200", "shot": 300, "read": []})
            # a given-name part of 0xFFFF (8 foreign jockeys known by one name) is read from past the table
            no_given = p["name_parts"].split()[1] == "65535"
            expect.append((kind, p["index"], p["surname"] + p["given"], no_given))
    lua = w2.COLLECT_LUA + w2.printf_lua(rom.version) + LUA.replace("@CARD@", str(a["card"]))
    card = w2.horse_card(rom.version)
    res = replay(rom.path, card, end_frame(card), runs, extra_lua=lua)
    ng = {k: [] for k in groups}
    for (kind, idx, want, no_given), out in zip(expect, res):
        calls = {c["fmt"]: c["args"] for c in printf_trace.parse(out[-1])}
        args = calls.get(a["sire_fmt"])
        got = rom.text_bytes(args[0]) if args else None
        if got != want and not (no_given and got is not None and got.startswith(want)):
            ng[kind].append((idx, want, got))
    errors = 0
    for kind, rows in groups.items():
        print(f"[{kind}s] {len(rows) - len(ng[kind])}/{len(rows)} names = game" + (f" NG {ng[kind][:5]}" if ng[kind] else ""))
        errors += len(ng[kind])
    print(f"time {time.time() - t0:.0f}s")
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
