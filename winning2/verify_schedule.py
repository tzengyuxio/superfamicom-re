#!/usr/bin/env python3
"""Check the race schedule in Mesen with the game's own schedule function, printed by the horse card.

The schedule function $C4:C225(month 0-11, week 0-3, day, race 0-9, slot 0-3) returns the race number of a meeting
slot (day 2 = 日曜; slot 3 returns the word at +60 of the day record). A shim written to WRAM $7F:FF40 pushes five
arguments from $7F:FF02-$7F:FF0B and calls it; the card's age call ($C3:364E JSL $C4:399C, printed as `%u歳`) is
patched to JSL the shim. Every card entry takes the next argument set from the list at $7F:FF70 (5 bytes each), and
the card is redrawn by pressing left / right, so one run checks BATCH entries. All 96 days x (3 slots x 10 races
+ the word at +60) = 2976 values, FFFF (no race) included.

Program '96: the same function at $C7:0200, card $C4:4077 (call site $C4:40BB).

Usage: .venv/bin/python winning2/verify_schedule.py [--rom ROM]
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
from rom import DEFAULT_ROM, RACES_PER_SLOT, SCHEDULE_DAYS, SCHEDULE_SIZE, SLOTS, Rom

ADDR = {
    "original": {"card": 0xC3360A, "site": 0xC3364E, "schedule": 0xC4C225, "fmt": 0xC3E6C1},
    "program96": {"card": 0xC44077, "site": 0xC440BB, "schedule": 0xC70200, "fmt": 0xC4F58F},
}
SHIM = 0x7FFF40
ARGS, LIST = 0x1FF02, 0x1FF70       # WRAM offsets ($7F:FF02, $7F:FF70; the shim is $7F:FF40-FF62)
BATCH = 24
LUA = """
local k = 0
RESET_HOOKS[#RESET_HOOKS + 1] = function() k = 0 end
emu.addMemoryCallback(function()
  for j = 0, 4 do
    emu.write(@ARGS@ + 2 * j, emu.read(@LIST@ + 5 * k + j, emu.memType.snesWorkRam), emu.memType.snesWorkRam)
    emu.write(@ARGS@ + 2 * j + 1, 0, emu.memType.snesWorkRam)
  end
  k = k + 1
end, emu.callbackType.exec, @CARD@)
"""


def shim(target: int) -> bytes:
    """LDA long a4 / PHA ... LDA long a0 / PHA; JSL target; PLA x 5; RTL (16-bit A, as the compiled code runs)."""
    code = b""
    for j in range(4, -1, -1):
        a = 0x7F0000 + (ARGS & 0xFFFF) + 2 * j
        code += bytes([0xAF, a & 0xFF, a >> 8 & 0xFF, a >> 16, 0x48])
    return code + bytes([0x22, target & 0xFF, target >> 8 & 0xFF, target >> 16]) + b"\x68" * 5 + b"\x6b"


def main() -> None:
    ap = argparse.ArgumentParser(description="用遊戲的日程函式驗證比賽日程")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    a = ADDR[rom.version]
    t0 = time.time()
    cases = []
    for day in range(SCHEDULE_DAYS):
        month, rest = divmod(day, 8)
        week, sunday = divmod(rest, 2)
        base = rom.o["SCHEDULE"] + SCHEDULE_SIZE * day
        for slot in range(SLOTS + 1):
            for k in range(RACES_PER_SLOT if slot < SLOTS else 1):
                want = rom.u16(base + 20 * slot + 2 * k) if slot < SLOTS else rom.u16(base + 60)
                cases.append(((month, week, 2 if sunday else 1, k, slot), want))
    patch = [((a["site"] + 1) & 0x3FFFFF, SHIM.to_bytes(3, "little"))]
    code = shim(a["schedule"])
    runs = []
    for i in range(0, len(cases), BATCH):
        part = cases[i:i + BATCH]
        lst = b"".join(bytes(c) for c, _ in part)
        steps = "a:10 w200" + " right:6 w80 left:6 w80" * (len(part) // 2)
        runs.append({"patch": patch, "wram": [(SHIM - 0x7E0000, code), (LIST, lst)], "steps": steps.strip(),
                     "shot": 260 + 112 * len(part), "read": []})
    lua = w2.COLLECT_LUA + w2.printf_lua(rom.version) + LUA.replace("@CARD@", str(a["card"])) \
        .replace("@ARGS@", str(ARGS)).replace("@LIST@", str(LIST))
    card = w2.horse_card(rom.version)
    res = replay(rom.path, card, end_frame(card), runs, extra_lua=lua)
    ng, missing = [], 0
    for i, out in enumerate(res):
        got = [c["args"][0] for c in printf_trace.parse(out[-1]) if c["fmt"] == a["fmt"]]
        for j, (c, want) in enumerate(cases[i * BATCH:(i + 1) * BATCH]):
            if j >= len(got):
                missing += 1
            elif got[j] != want:
                ng.append((c, want, got[j]))
    n = len(cases)
    print(f"[schedule] {n - len(ng) - missing}/{n} (month, week, day, race, slot) -> race number = game"
          + (f" NG {ng[:5]}" if ng else "") + (f"; {missing} not reached" if missing else ""))
    print(f"time {time.time() - t0:.0f}s")
    print("ALL OK" if not ng and not missing else f"{len(ng) + missing} problem(s)")
    raise SystemExit(1 if ng or missing else 0)


if __name__ == "__main__":
    main()
