#!/usr/bin/env python3
"""Check the new-game tables in Mesen: the blocks a new game copies from ROM to WRAM ($C3:0F12) must be the bytes
rom.py reads.

The copies run once the owner registration is done (~frame 12000, press 21 of tools/w2.py's script). A Lua hook on
the instruction after the last copy ($C3:0FEE; Program '96 $C4:31AB) reads every block of rom.INIT_COPIES back
from WRAM, and the result is compared with the ROM bytes at rom.py's offsets; the decoded tables are then checked
against the WRAM copy (racehorse name parts / sire / dam, stallion and mare name parts, jockey and trainer and
owner name parts).

Usage: .venv/bin/python winning2/verify_init.py [--rom ROM]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "tools"))
import w2
from replay import end_frame, replay
from rom import (
    DEFAULT_ROM,
    INIT_COPIES,
    INIT_WRAM_96,
    JOCKEY_COUNT,
    JOCKEY_SIZE,
    MARE_SIZE,
    OWNER_SIZE,
    RACEHORSE_SIZE,
    STALLION_SIZE,
    TRAINER_SIZE,
    Rom,
)

HOOK = {"original": 0xC30FEE, "program96": 0xC431AB}


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證開新局時 ROM → WRAM 的初始資料")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    t0 = time.time()
    boot = w2.new_game(rom.version) + w2.A * 20
    copies = [(k, INIT_WRAM_96[k] if rom.version == "program96" else w, n) for k, w, n in INIT_COPIES]
    blocks = ",".join(f"{{{w},{n}}}" for _, w, n in copies)
    lua = w2.COLLECT_LUA + """
local done = false
RESET_HOOKS[#RESET_HOOKS + 1] = function() done = false end
emu.addMemoryCallback(function()
  if done then return end
  done = true
  for _, b in ipairs({@BLOCKS@}) do
    local s = {}
    for a = 0, b[2] - 1 do s[#s + 1] = string.format("%02x", emu.read(b[1] + a, emu.memType.snesWorkRam, false)) end
    REC_ADD(table.concat(s))
  end
end, emu.callbackType.exec, @HOOK@)
""".replace("@BLOCKS@", blocks).replace("@HOOK@", str(HOOK[rom.version]))
    [res] = replay(rom.path, boot, end_frame(boot), [{"steps": (w2.A * 2).strip(), "shot": 460, "read": []}],
                   extra_lua=lua)
    got = [bytes.fromhex(r[0]) for r in w2.records(res[-2])]
    errors = 0
    if len(got) != len(copies):
        print(f"[blocks] the copy hook did not run ({len(got)} blocks read)")
        raise SystemExit(1)
    bad = [k for (k, _, n), b in zip(copies, got) if b != rom.data[rom.o[k]:rom.o[k] + n]]
    print(f"[blocks] {len(copies) - len(bad)}/{len(copies)} WRAM blocks = ROM ({rom.version})"
          + (f" (NG {bad})" if bad else ""))
    print(f"         {sum(n for _, _, n in copies)} bytes: "
          + ", ".join(f"{k} {rom.o[k]:06X}->${w:04X}" for k, w, _ in copies))
    errors += len(bad)
    wram = {k: b for (k, _, _), b in zip(copies, got)}

    def w16(k: str, o: int) -> int:
        return wram[k][o] | wram[k][o + 1] << 8

    def check(label: str, rows: list[dict], key: str, size: int, fields) -> None:
        nonlocal errors
        ng = [h["index"] for h in rows if fields(h) != tuple(
            w16(key, size * h["index"] + o) if o < 4 else wram[key][size * h["index"] + o] for o in (0, 2, 4, 5)
            [:len(fields(h))])]
        print(f"[{label}] {len(rows) - len(ng)}/{len(rows)} = WRAM" + (f" (NG {ng[:10]})" if ng else ""))
        errors += len(ng)

    def parts(h: dict) -> tuple:
        return tuple(int(x) for x in h["name_parts"].split())

    check("racehorses: name parts / sire / dam", rom.racehorses(), "RACEHORSE", RACEHORSE_SIZE,
          lambda h: (*parts(h), h["sire"], h["dam"]))
    check("stallions: name parts", rom.stallions(), "STALLION", STALLION_SIZE, parts)
    check("mares: name parts / sire", rom.mares(), "MARE", MARE_SIZE, lambda h: (*parts(h), h["sire"]))
    check("jockeys 0-59: name parts", rom.jockeys()[:JOCKEY_COUNT], "JOCKEY", JOCKEY_SIZE, parts)
    check("trainers: name parts", rom.trainers(), "TRAINER", TRAINER_SIZE, parts)
    check("owners: name parts", rom.owners(), "OWNER", OWNER_SIZE, parts)
    print(f"time {time.time() - t0:.0f}s")
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
