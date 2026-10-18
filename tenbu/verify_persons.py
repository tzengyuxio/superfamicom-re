#!/usr/bin/env python3
"""Check the person records (name, reading, 官職, 政 外 策 采 武 徳, 年齢) against the game's ruler card.

Each scenario is played to the ruler list (諸侯を選択して下さい) and a savestate is taken there
(tools/sequences.py). Clicking a ruler reloads the scenario ($00:CA31) and draws the card from that load, so each
run hands person p's 35-byte record (rom.Rom.person_raw) through the WRAM mailbox and a hook on the loader's
return ($00:CA8D) copies it over the record of the faction-0 ruler; then the first row of the list is clicked.
The card must show:

  - $00:A0CA tile codes: name (3 characters x 4 codes), reading (8 half-width x 2), the first 4 characters of the
    官職 (person +33), after the 20 digit codes 0x8120-0x8133 the card starts with
  - OAM digit sprites (16 x 16, tile 0xE4 + 2 d for d = 0-5, 0x100 + 2 (d - 6) for 6-9, blank 0x140): 政 外 策
    at y 104, 采 武 徳 at y 128 (x 80 / 120 / 160 for tens, + 8 for ones), 年 at (80, 152)

All 600 records of all 4 scenarios are checked (the 4 scenarios run in parallel processes).

Usage: .venv/bin/python tenbu/verify_persons.py [--rom ROM] [--scenario 0-3] [--persons 0-599]
"""
import argparse
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
sys.path.insert(0, os.path.join(HERE, "tools"))
import replay
import sequences as q
from rom import DEFAULT_ROM, LOADER_DONE, OFFICES, PERSON_COUNT, PERSON_SIZE, PERSON_WRAM, SCENARIO_YEARS, Rom

SHOT = 300
DIGIT_POS = {"政": (80, 104), "外": (120, 104), "策": (160, 104), "采": (80, 128), "武": (120, 128),
             "徳": (160, 128), "年齢": (80, 152)}
LEAD = list(range(0x8120, 0x8134))

PATCH_LUA = f"""
emu.addMemoryCallback(function()
  local m={q.MAILBOX + 2}
  local slot=emu.read(m,emu.memType.snesWorkRam,false)+256*emu.read(m+1,emu.memType.snesWorkRam,false)
  if slot==0xFFFF then return end
  for i=0,{PERSON_SIZE - 1} do
    emu.write({PERSON_WRAM}+{PERSON_SIZE}*slot+i, emu.read(m+2+i,emu.memType.snesWorkRam,false), emu.memType.snesWorkRam)
  end
end, emu.callbackType.exec, {LOADER_DONE})
"""


def digit(tile: int) -> int | None:
    if tile == 0x140:
        return None
    if 0xE4 <= tile <= 0xEE and tile % 2 == 0:
        return (tile - 0xE4) // 2
    if 0x100 <= tile <= 0x106 and tile % 2 == 0:
        return 6 + (tile - 0x100) // 2
    return -1


def card_numbers(oam: bytes) -> dict:
    tiles = {}
    for i in range(128):
        x, y, t, a = oam[4 * i:4 * i + 4]
        if y < 224:
            tiles[(x | (oam[512 + i // 4] >> (i % 4 * 2) & 1) << 8, y)] = t | (a & 1) << 8
    out = {}
    for name, (x, y) in DIGIT_POS.items():
        tens, ones = digit(tiles.get((x, y), -1)), digit(tiles.get((x + 8, y), -1))
        out[name] = None if ones is None or ones < 0 or (tens is not None and tens < 0) else (tens or 0) * 10 + ones
    return out


def expected_codes(rom: Rom, raw: bytes) -> list[int]:
    office = rom.data[OFFICES + 26 * raw[33]:][:8]
    return rom.text_codes(raw[:6]) + rom.half_codes(raw[6:14]) + rom.text_codes(office)


def card_runs(rom: Rom, k: int, records: list[bytes], read: list, extra: str = "",
              take: str = "CODES_TAKE()") -> list[list[bytes]]:
    """Replay the ruler card of scenario k once per 35-byte record (copied over the faction-0 ruler). extra: more
    Lua (may define EXTRA_START()); take: the Lua expression handed back after the reads."""
    slot = rom.faction(k, 0)["君主"]
    boot = q.TO_SCENARIOS + " " + q.to_rulers(k) + " w200"
    boot_r, save, steps, plua = q.prepare(boot, [q.card(0)] * len(records))
    runs = [{"steps": st, "shot": SHOT, "read": read,
             "wram": [q.mail(i, slot.to_bytes(2, "little") + raw)]} for i, (st, raw) in enumerate(zip(steps, records))]
    lua = ("CODES_FROM=0\n" + q.CODES_LUA + plua + PATCH_LUA + extra
           + "function EXTRA_RESET() POINTER_RESET(); CODES_START(); if EXTRA_START then EXTRA_START() end end\n"
           + f"function EXTRA_SHOT() return {take} end\n")
    return replay.replay(rom.path, boot_r, save, runs, extra_lua=lua, nmi=q.FRAME_HOOK)


def run(rom: Rom, k: int, persons: list[int]) -> int:
    records = [rom.person_raw(k, p) for p in persons]
    results = card_runs(rom, k, records, [("oam", 0, 544)])
    bad = 0
    for p, raw, (oam, codes) in zip(persons, records, results):
        got = q.codes(codes)
        if got[:20] == LEAD:
            got = got[20:]
        want = expected_codes(rom, raw)
        v = rom.person(k, p)
        nums_want = {name: v[name] for name in DIGIT_POS}
        nums = card_numbers(oam)
        if got[:len(want)] != want or nums != nums_want:
            bad += 1
            print(f"  NG {SCENARIO_YEARS[k]} #{p} {v['名前']}: codes {'OK' if got[:len(want)] == want else 'NG'}"
                  f" {[hex(c) for c in got[:12]]}; numbers {nums} want {nums_want}")
    print(f"scenario {SCENARIO_YEARS[k]}: ruler card equal {len(persons) - bad}/{len(persons)}")
    return bad


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證人物姓名、讀音、官職、能力與年齡（君主卡）")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--scenario", type=int, choices=(0, 1, 2, 3), help="只跑一個劇本（預設四個劇本平行跑）")
    ap.add_argument("--persons", default=f"0-{PERSON_COUNT - 1}", help="人物編號範圍，如 0-599")
    args = ap.parse_args()
    t0 = time.time()
    if args.scenario is None:
        procs = [subprocess.Popen([sys.executable, __file__, "--rom", args.rom, "--scenario", str(k),
                                   "--persons", args.persons]) for k in range(4)]
        errors = sum(p.wait() != 0 for p in procs)
        print(f"{time.time() - t0:.0f} s")
        print("ALL OK" if not errors else "mismatch(es)")
        raise SystemExit(1 if errors else 0)
    lo, _, hi = args.persons.partition("-")
    persons = list(range(int(lo), int(hi or lo) + 1))
    errors = run(Rom(args.rom), args.scenario, persons)
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
