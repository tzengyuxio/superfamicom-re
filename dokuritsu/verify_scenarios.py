#!/usr/bin/env python3
"""Check the 1775 scenario decode (rom.SCENARIO_BLOCKS, Rom.person_states, Rom.location_states) against the game
(needs Mesen 2, about a minute).

One run in Mesen (tools/mesen.py): new game, America played by a human, through the 大陸会議 to the first command
screen (1775/7; the location depends on the run), then 軍事 -> the person list of that location.
1. Frame 10172 (just after 新しく始める; $C8:17FC has copied the blocks): the six WRAM blocks equal ROM.
2. The game's own vprintf ($C1:430F) is hooked; for the screens below its arguments are compared with the
   decoding and with the WRAM person / location states at that moment (the states change during the 大陸会議,
   so the values shown later are compared with WRAM, the offsets with the decoding):
   - side selection, ジョージ・ワシントン: "%s %s" = the name pointers of master record 238, 統率力 戦術力 指導力 =
     master +26..+28, 名声 = person state +4;
   - command screen: "%d:%s" = location id + 1 and the name pointer, the %3d / %4d values = location state
     +5 (支持), +10, +6, +8;
   - person list: the names (initial.surname) are the persons of the location's WRAM list in order, and the three %3d per
     person = person state +3 (体力), +5 (忠誠), +4 (名声).

Usage: .venv/bin/python dokuritsu/verify_scenarios.py [--rom ROM]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
from mesen import SNES_WRAM, Mesen
from rom import (
    DEFAULT_ROM,
    LOCATION_SIZE,
    LOCATION_STATE_SIZE,
    LOCATION_STATE_WRAM,
    LOCATIONS,
    PERSON_SIZE,
    PERSON_STATE_SIZE,
    PERSON_STATE_WRAM,
    PERSONS,
    SCENARIO_BLOCKS,
    Rom,
    le16,
    text,
)

# title -> 新しく始める -> America (human) -> ... -> 大陸会議 -> first command screen (about frame 21900)
MAIN = ("w9800 start:10 w200 a:10 w200 a:10 w200 a:10 w200 a:10 w300 a:10 w400" + " down:10 w100" * 7
        + " a:10 w300 a:10 w1200 a:10 w100 a:10 w100 down:10 w100 down:10 w100 a:10 w100 a:10 w100 a:10 w100"
        " b:10 w100 b:10 w100 left:10 w60 a:10 w200 a:10 w200 a:10 w200 a:10 w200 w600" + " a:10 w200" * 7
        + " a:10 w300 a:10 w300 w1200" + " a:10 w300" * 6)
LIST = " a:10 w100 down:10 w100 a:10 w200 a:10 w200 down:10 w100 a:10 w200"   # 軍事 -> person list
BLOCK_FRAME = 10172
VPRINTF = 0xC1430F
WATCH = {  # format address -> screen
    0xC8AE11: "side", 0xC8AE1B: "side", 0xC8AE26: "side", 0xC8AE31: "side", 0xC8AE3C: "side",
    0xC7E493: "main", 0xC7E4E4: "main", 0xC7E4EA: "main", 0xC7E4EF: "main", 0xC7E4F4: "main",
    0xC2FAA0: "list", 0xC2FA3F: "list", 0xC2FA6D: "list", 0xC2FA59: "list",
}
STATES_LO, STATES_HI = LOCATION_STATE_WRAM, PERSON_STATE_WRAM + 250 * PERSON_STATE_SIZE

LUA = """
local presses = {%(presses)s}
local f = 0
local function rd(a) return emu.read(a, emu.memType.snesMemory, false) end
local watch = {%(watch)s}
emu.addEventCallback(function()
  local inp = {}
  for _, p in ipairs(presses) do if f >= p[1] and f < p[1] + p[3] then inp[p[2]] = true end end
  emu.setInput(inp, 0)
end, emu.eventType.inputPolled)
emu.addEventCallback(function()
  f = f + 1
  if f == %(block)d or f == %(last)d then emu.log("BREAK " .. f); emu.breakExecution() end
end, emu.eventType.endFrame)
emu.addMemoryCallback(function()
  local sp = emu.getState()["cpu.sp"]
  local fmt = rd(sp + 4) + rd(sp + 5) * 256 + rd(sp + 6) * 65536
  if not watch[fmt] then return end
  local va = rd(sp + 8) + rd(sp + 9) * 256 + rd(sp + 10) * 65536
  local a, s = {}, {}
  for i = 0, 23 do a[#a + 1] = string.format("%%02x", rd(va + i)) end
  local p, t = rd(va) + rd(va + 1) * 256 + rd(va + 2) * 65536, {}
  for i = 0, 15 do t[#t + 1] = string.format("%%02x", rd(p + i)) end
  for i = %(lo)d, %(hi)d - 1 do s[#s + 1] = string.format("%%02x", emu.read(i, emu.memType.snesWorkRam, false)) end
  emu.log(string.format("PF %%d %%06X %%s %%s %%s", f, fmt, table.concat(a), table.concat(t), table.concat(s)))
end, emu.callbackType.exec, %(vprintf)d, %(vprintf)d)
"""


def presses(steps: str, start: int = 10) -> tuple[list[tuple[int, str, int]], int]:
    """tools/drive.py timing: a press holds `hold` frames, then 20 frames released."""
    out, f = [], start
    for st in steps.split():
        if st.startswith("w"):
            f += int(st[1:])
        else:
            b, _, hold = st.partition(":")
            out.append((f, b, int(hold or 4)))
            f += int(hold or 4) + 20
    return out, f


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證 1775 年劇本資料")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    t0 = time.time()
    rom = Rom(args.rom)
    pr, end = presses(MAIN + LIST)
    lua = LUA % {"presses": ",".join(f'{{{f},"{b}",{h}}}' for f, b, h in pr), "block": BLOCK_FRAME,
                 "last": end + 100, "watch": ",".join(f"[{a}]=true" for a in WATCH), "lo": STATES_LO,
                 "hi": STATES_HI, "vprintf": VPRINTF}
    errors = 0
    with Mesen(args.rom) as m:
        m.run(lua, 600)
        wram = m.memory(SNES_WRAM)
        m.resume(600)
        log = m.log(1 << 24)
    # 1. blocks
    res = []
    for off, addr, n, _ in SCENARIO_BLOCKS:
        diff = sum(a != b for a, b in zip(wram[addr:addr + n], rom.data[off:off + n]))
        res.append(diff)
    print(f"[blocks] frame {BLOCK_FRAME}: {sum(d == 0 for d in res)}/6 WRAM blocks equal ROM "
          f"({sum(n for _, _, n, _ in SCENARIO_BLOCKS)} bytes, differing bytes per block {res})")
    errors += sum(d != 0 for d in res)
    # 2. vprintf
    events = []
    for line in log.splitlines():
        if line.startswith("PF "):
            _, f, fmt, a, t, s = line.split(" ")
            events.append((int(f), int(fmt, 16), bytes.fromhex(a), bytes.fromhex(s), bytes.fromhex(t)))
    persons = rom.persons()

    def pstate(snap: bytes, pid: int) -> bytes:
        o = PERSON_STATE_WRAM - STATES_LO + PERSON_STATE_SIZE * pid
        return snap[o:o + PERSON_STATE_SIZE]

    # side selection: name pointers, then four values in order
    side = [e for e in events if WATCH[e[1]] == "side"]
    w = 238
    want_ptr = [0xC10000 | (PERSONS + PERSON_SIZE * w + 2), 0xC10000 | (PERSONS + PERSON_SIZE * w + 14)]
    names = [e for e in side if e[1] == 0xC8AE11]
    vals = {e[1]: le16(e[2], 0) for e in side}
    got_ptr = [int.from_bytes(names[0][2][k:k + 3], "little") for k in (0, 4)] if names else None
    ok_side = (got_ptr == want_ptr
               and vals.get(0xC8AE1B) == persons[w]["統率力"] and vals.get(0xC8AE26) == persons[w]["戦術力"]
               and vals.get(0xC8AE31) == persons[w]["指導力"] and vals.get(0xC8AE3C) == pstate(side[-1][3], w)[4]
               == rom.person_states()[w]["名声"])
    print(f"[side] {persons[w]['name']}: name pointers {got_ptr == want_ptr}, "
          f"統率力 戦術力 指導力 名声 shown {[vals.get(a) for a in (0xC8AE1B, 0xC8AE26, 0xC8AE31, 0xC8AE3C)]} = "
          f"decoded {[persons[w][k] for k in ('統率力', '戦術力', '指導力')] + [rom.person_states()[w]['名声']]}: {ok_side}")
    errors += not ok_side
    # command screen
    main_ev = [e for e in events if WATCH[e[1]] == "main"]
    head = [e for e in main_ev if e[1] == 0xC7E493]
    ok_main = bool(head)
    if head:
        f0 = head[0][0]
        no, ptr = le16(head[0][2], 0), int.from_bytes(head[0][2][2:5], "little")
        loc = no - 1
        ok_main = ptr == 0xC10000 | (LOCATIONS + LOCATION_SIZE * loc + 2)
        shown = {e[1]: le16(e[2], 0) for e in main_ev if f0 <= e[0] < f0 + 60 and e[1] != 0xC7E493}
        snap = main_ev[-1][3]
        o = LOCATION_STATE_WRAM - STATES_LO + LOCATION_STATE_SIZE * loc
        st = snap[o:o + LOCATION_STATE_SIZE]
        want = {0xC7E4E4: st[5], 0xC7E4EA: le16(st, 10), 0xC7E4EF: le16(st, 6), 0xC7E4F4: le16(st, 8)}
        ok_main = ok_main and shown == want
        init = rom.location_states()[loc]
        print(f"[command] location {no} {rom.locations()[loc]['name']} (name pointer {ok_main}): shown "
              f"支持 {shown.get(0xC7E4E4)} +10 {shown.get(0xC7E4EA)} 食糧 {shown.get(0xC7E4EF)} +8 {shown.get(0xC7E4F4)}"
              f" = WRAM state +5 +10 +6 +8 {[want[k] for k in (0xC7E4E4, 0xC7E4EA, 0xC7E4EF, 0xC7E4F4)]}: "
              f"{shown == want}; ROM initial values {[init['支持'], init['弾薬'], init['食糧'], init['武器']]}")
    errors += not ok_main
    # person list: each row is "%s" (surname) then the three %3d; the first pass over the page is taken
    rows = []
    for e in events:
        if WATCH[e[1]] != "list":
            continue
        if e[1] == 0xC2FAA0:
            name = text(e[4])
            if any(r["name"] == name for r in rows):
                break
            rows.append({"name": name, "vals": {}, "snap": e[3]})
        elif rows:
            rows[-1]["vals"][e[1]] = le16(e[2], 0)
    ok_list = bool(rows) and head
    if ok_list:
        snap = rows[-1]["snap"]
        o = LOCATION_STATE_WRAM - STATES_LO + LOCATION_STATE_SIZE * loc
        p, members = le16(snap, o), []
        while p and len(members) < 250:
            pid = (p - PERSON_STATE_WRAM) // PERSON_STATE_SIZE
            members.append(pid)
            p = le16(pstate(snap, pid), 0)
        names_ok = [r["name"] for r in rows] == [f"{persons[k]['initial']}.{persons[k]['last']}" for k in members[:len(rows)]]
        offs = {0xC2FA3F: 3, 0xC2FA6D: 5, 0xC2FA59: 4}
        # the commander's row shows --- instead of 忠誠
        vals_ok = sum(len(r["vals"]) >= 2 and all(v == pstate(snap, k)[offs[f]] for f, v in r["vals"].items())
                      for r, k in zip(rows, members))
        ok_list = names_ok and vals_ok == len(rows)
        print(f"[list] location {loc + 1}: {len(rows)} rows, 'initial.surname' (master +0, +14) = the first {len(rows)} persons of the WRAM "
              f"list (location state +0, next = person state +0): {names_ok}; rows whose 体力 忠誠 名声 equal "
              f"person state +3 +5 +4: {vals_ok}/{len(rows)}; {[persons[k]['name'] for k in members[:len(rows)]]}")
    errors += not ok_list
    print(f"time {time.time() - t0:.0f} s")
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
