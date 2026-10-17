#!/usr/bin/env python3
"""Check that the sdata file is the initial game state (needs Mesen 2, under a minute).

New game up to the first map; WRAM $7E:EFF0-$7E:FFCF (0xFE0 bytes) is read back and compared with sdata
(rom.SDATA). The game copies the block whole when the new game starts; by the time the map is shown only these
bytes may differ: the hero's name (sdata + 0xBC, 12 bytes: the name typed on the naming screen, here "ああ"),
and the bytes at ALLOWED (0-2, 0x1A, 0xBB4: counters the game has already updated, meaning not decoded).
Everything rom.py reads from sdata (person states, bag, vassal chains, daimyo table, province states) is in it.

Usage: .venv/bin/python inindou/verify_state.py [--rom ROM]
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
from replay import end_frame, replay
from rom import DEFAULT_ROM, HERO_NAME, SDATA_SIZE, SDATA_WRAM, TEXT_BASE, Rom
from scenes import BOOT, SAVE

ALLOWED = {0, 1, 2, 0x1A, 0xBB4}
TYPED = "ああ"


def main() -> None:
    ap = argparse.ArgumentParser(description="以 Mesen 驗證 sdata 是開新遊戲的初始狀態")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    (wram,), = replay(args.rom, BOOT, SAVE, [{"steps": "w10", "shot": end_frame("w10", 0),
                                              "read": [("wram", SDATA_WRAM, SDATA_SIZE)]}])
    sd = rom.sdata()
    name = b"".join((TEXT_BASE + rom.charset.index(c)).to_bytes(2, "big") for c in TYPED)
    want = bytearray(sd)
    want[HERO_NAME:HERO_NAME + 12] = name.ljust(12, b"\0")
    diff = [i for i in range(SDATA_SIZE) if wram[i] != want[i]]
    unexpected = [i for i in diff if i not in ALLOWED]
    print(f"[sdata] {SDATA_SIZE - len(diff)}/{SDATA_SIZE} bytes of WRAM $7E:EFF0 equal sdata (hero name = {TYPED});"
          f" differing at {[hex(i) for i in diff]}")
    print("ALL OK" if not unexpected else f"NG: unexpected differences at {[hex(i) for i in unexpected]}")
    raise SystemExit(1 if unexpected else 0)


if __name__ == "__main__":
    main()
