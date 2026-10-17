#!/usr/bin/env python3
"""Check the system message table (rom.Rom.message_raw: messages at $01:DDFC split at 0, header sizes) in Mesen.

The card screen of 雀荘 shows message 23 ("たいせんあいてを えらんでください", LDA #$17 / JSR $918A at $00:AF9B). A
savestate on the 雀荘 selection is replayed once per message 1-71 with the immediate patched to that number (PRG patch
at file 0x2F9C). $00:918A walks the 0-ended strings from $01:DDFC and stores the message's address in DP $58; $00:938B
returns the header size, stored at $0D9E. Both must equal rom.message_raw (address of message n, header length).
The text itself is drawn into tiles allocated on the fly and is not compared (the profiles 49-71 are also shown in
output/messages.csv for reading).

Usage: .venv/bin/python mahjong2/verify_messages.py [--rom ROM]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "tools"))
import sequences as sq
from replay import end_frame, replay
from rom import DEFAULT_ROM, MESSAGE_COUNT, MESSAGES, Rom

MESSAGE_IMM = 0x2F9C      # file offset of the immediate of LDA #$17 before JSR $918A ($00:AF9B)
MESSAGE_PTR = 0x58        # DP: address of the current message (bank $01)
HEADER_SIZE = 0x0D9E


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證系統訊息表（Mesen）")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    t0 = time.time()
    rom = Rom(args.rom)
    reads = [("wram", MESSAGE_PTR, 2), ("wram", HEADER_SIZE, 1)]
    runs = [{"steps": "a:10", "shot": 120, "read": reads, "patch": [(MESSAGE_IMM, bytes([n]))]}
            for n in range(1, MESSAGE_COUNT + 1)]
    res = replay(rom.path, sq.TO_PARLORS, end_frame(sq.TO_PARLORS), runs, timeout=600)
    bad, addr = [], MESSAGES
    for n, (ptr, hsize) in zip(range(1, MESSAGE_COUNT + 1), res):
        head, codes = rom.message_raw(n)
        want = (0x8000 | addr & 0x7FFF, len(head))
        got = (ptr[0] | ptr[1] << 8, hsize[0])
        if got != want:
            bad.append((n, [hex(x) for x in got], [hex(x) for x in want]))
        addr += len(head) + len(codes) + 1
    print(f"[messages] {MESSAGE_COUNT - len(bad)}/{MESSAGE_COUNT}: DP $58 = address of message n, $0D9E = header size"
          + (f" NG {bad[:5]}" if bad else ""))
    print(("ALL OK" if not bad else f"{len(bad)} problem(s)") + f" ({time.time() - t0:.0f} s)")
    raise SystemExit(1 if bad else 0)


if __name__ == "__main__":
    main()
