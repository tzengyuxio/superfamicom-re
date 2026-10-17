#!/usr/bin/env python3
"""Check the race programme, race names, classes, editions, meetings and tracks in Mesen.

月刊競馬ニュース (January 1997, tools/wp.RACE_PAGE) shows one page per graded race of the month: $C8:5258(x, y,
slot) prints the race name (puts $C2:06E9, name from $C5:AE9E), 第N回 ($C8:C41C: edition, race number), the class
($C5:A80D -> $CB:E0C1), "N回<track>N週" ($C8:C42C: kai and track of the current month $7E:DA63 and side slot % 2
from $C1:C0DF, week slot % 32 / 8 + 1) and "N00m <age> <sex>" ($C8:C437). For every run the slot argument
(S+8 at $C8:5258) is replaced and $DA63 is set to the slot's month:
1. every slot of the programme that has a named race (b0 != 0xFF): all fields must equal rom.Rom.calendar();
2. every race number 0-231: slot 6's race byte is patched in ROM ($CF:41C6 + 24); name and edition (0xFFFF for
   races 86-231, which have no edition) must equal rom.race_names() / RACE_NTH.

Usage: .venv/bin/python winning/verify_races.py [--rom ROM]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "tools"))
import wp
from replay import end_frame, replay
from rom import DEFAULT_ROM, GRADED_COUNT, RACE_COUNT, WRAM_MONTH, Rom

FMT_NTH, FMT_CLASS, FMT_MEET, FMT_DIST = 0x8C41C, 0x8C426, 0x8C42C, 0x8C437
NAME_SLOT = 6
STEPS, SHOT = "a:10 w200 a:10 w200", 420
OVERRIDE_LUA = """
emu.addMemoryCallback(function()
  if PARAM(2) == 0 then return end
  local sp = emu.getState()["cpu.sp"]
  emu.write(sp + 8, PARAM(0), emu.memType.snesMemory)
  emu.write(sp + 9, PARAM(1), emu.memType.snesMemory)
  REC_ADD("H")
end, emu.callbackType.exec, 0xC85258)
"""


def page(rom: Rom, raw: bytes) -> dict:
    """Fields of the first race page after the override marker."""
    recs = wp.parse(raw)
    if ["H"] not in recs:
        return {}
    recs = recs[recs.index(["H"]) + 1:]
    fmt = {k: rom.data[o:rom.data.index(b"\0", o)] for k, o in
           (("nth", FMT_NTH), ("class", FMT_CLASS), ("meet", FMT_MEET), ("dist", FMT_DIST))}
    out = {}
    for p in wp.prints(recs):
        if p["fmt"] is None:
            out.setdefault("name", rom.text_bytes(p["s"]))
        elif p["fmt"] == fmt["nth"] and "nth" not in out:
            out["nth"], out["race"] = p["args"][0], p["args"][1]
        elif p["fmt"] == fmt["class"] and "class" not in out:
            out["class"] = rom.text_bytes(p["s0"])
        elif p["fmt"] == fmt["meet"] and "kai" not in out:
            out["kai"], out["track"], out["week"] = p["args"][0], rom.text_bytes(p["s2"]).strip(), p["args"][3]
        elif p["fmt"] == fmt["dist"] and "dist" not in out:
            out["dist"], out["age"], out["sex"] = p["args"][0] * 100, rom.text_bytes(p["s2"]), rom.text_bytes(p["s6"])
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證比賽日程與比賽名")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    t0 = time.time()
    cal = rom.calendar()
    named = [e for e in cal if e["race"] is not None]
    runs = []
    for e in named:
        s = e["slot"]
        runs.append({"steps": STEPS, "shot": SHOT, "read": [],
                     "wram": [(wp.WRAM_PARAM, bytes([s & 255, s >> 8, 1])), (WRAM_MONTH, bytes([e["month"]]))]})
    for r in range(RACE_COUNT):
        runs.append({"steps": STEPS, "shot": SHOT, "read": [],
                     "patch": [(rom.o["CALENDAR"] + 4 * NAME_SLOT, bytes([r]))],
                     "wram": [(wp.WRAM_PARAM, bytes([NAME_SLOT, 0, 1]))]})
    res = replay(rom.path, wp.RACE_PAGE, end_frame(wp.RACE_PAGE), runs,
                 extra_lua=wp.COLLECT_LUA + wp.PRINT_LUA + OVERRIDE_LUA)
    errors = 0
    bad = []
    for e, r in zip(named, res):
        got = page(rom, r[-1])
        want = {"name": e["race_name"], "race": e["race"],
                "nth": e["nth_1997"] if e["nth_1997"] is not None else 0xFFFF, "class": e["class_short"],
                "kai": e["kai"], "track": e["track_name"], "week": e["week"], "dist": e["distance"],
                "age": e["age"], "sex": e["sex"]}
        diff = {k: (got.get(k), v) for k, v in want.items() if got.get(k) != v}
        if diff:
            bad.append((e["slot"], diff))
    print(f"[programme] {len(named) - len(bad)}/{len(named)} slots with a named race: name, edition, class, "
          "kai / track / week, distance, age, sex" + (f" (NG {bad[:3]})" if bad else ""))
    errors += len(bad)
    names = rom.race_names()
    nth = [rom.u16(rom.o["RACE_NTH"] + 2 * r) for r in range(GRADED_COUNT)]
    bad = []
    for r, x in zip(range(RACE_COUNT), res[len(named):]):
        got = page(rom, x[-1])
        want = {"name": names[r], "race": r, "nth": nth[r] if r < GRADED_COUNT else 0xFFFF}
        diff = {k: (got.get(k), v) for k, v in want.items() if got.get(k) != v}
        if diff:
            bad.append((r, diff))
    print(f"[races] {RACE_COUNT - len(bad)}/{RACE_COUNT} race names and editions" + (f" (NG {bad[:3]})" if bad else ""))
    errors += len(bad)
    print(f"time {time.time() - t0:.0f}s")
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
