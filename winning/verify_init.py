#!/usr/bin/env python3
"""Check the new-game tables in Mesen: the blocks a new game copies from ROM to WRAM ($CB:4850) must be there.

The game builds its state on the title screen (~frame 6505, before any choice). From a savestate at frame
6600 every block of rom.INIT_COPIES (racehorses, mares, stallions, jockeys, owners' and trainers' state, race
programme ...) is read back from WRAM and compared with the ROM bytes, and the decoded tables are checked against
the WRAM copy: racehorse / mare / stallion name words and parents, jockey face codes and person numbers.

Usage: .venv/bin/python winning/verify_init.py [--rom ROM]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "tools"))
import wp
from replay import replay
from rom import (
    DEFAULT_ROM,
    INIT_COPIES,
    WRAM_HORSE,
    WRAM_JOCKEY_A,
    WRAM_JOCKEY_B,
    WRAM_MARE,
    WRAM_STALLION,
    Rom,
)


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證開新局時 ROM → WRAM 的初始資料")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    t0 = time.time()
    reads = [("wram", dst, n) for _, dst, n in INIT_COPIES]
    [res] = replay(rom.path, "w6300 start:10", wp.INIT_DONE_FRAME, [{"shot": 5, "read": reads}])
    wram = {dst: b for (_, dst, _), b in zip(INIT_COPIES, res)}
    bad = [f"{src:06X}->{dst:04X}" for (src, dst, n), b in zip(INIT_COPIES, res) if b != rom.data[src:src + n]]
    print(f"[blocks] {len(INIT_COPIES) - len(bad)}/{len(INIT_COPIES)} WRAM blocks = ROM"
          + (f" (NG {bad})" if bad else ""))
    total = sum(n for _, _, n in INIT_COPIES)
    print(f"         {total} bytes")

    def w16(base: int, off: int) -> int:
        b = wram[base]
        return b[off] | b[off + 1] << 8

    errors = len(bad)
    checks = [("racehorses", rom.horses()[:400], WRAM_HORSE, 37), ("racehorses 400-423", rom.horses()[400:], 0x7F60, 37),
              ("mares", rom.mares(), WRAM_MARE, 20), ("stallions", rom.stallions(), WRAM_STALLION, 19)]
    for label, rows, base, size in checks:
        ng = [h["index"] for k, h in enumerate(rows)
              if (w16(base, size * k), w16(base, size * k + 2), w16(base, size * k + 4))
              != (h["name_word"], h["sire"], h["dam"])]
        print(f"[{label}] {len(rows) - len(ng)}/{len(rows)} name word / sire / dam = WRAM" + (f" (NG {ng[:10]})" if ng else ""))
        errors += len(ng)
    ng = []
    for j in rom.jockeys():
        base, k = (WRAM_JOCKEY_A, j["index"]) if j["index"] < 20 else (WRAM_JOCKEY_B, j["index"] - 20)
        b = wram[base][22 * k:22 * k + 22]
        if (b[0] | b[1] << 8, b[21]) != (j["face"], j["person"]):
            ng.append(j["index"])
    print(f"[jockeys] {70 - len(ng)}/70 face code / person = WRAM" + (f" (NG {ng})" if ng else ""))
    errors += len(ng)
    print(f"time {time.time() - t0:.0f}s")
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
