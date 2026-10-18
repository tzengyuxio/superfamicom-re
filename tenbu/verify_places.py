#!/usr/bin/env python3
"""Check 所在 (person +29) and who is present against the 武将情報検索 list.

Each scenario is played to the map (ruler row 0, 普) and the 武将情報検索 window is opened (州 幽州 selected); a
savestate is taken there. The window lists, for the clicked 郡国, the persons whose +29 is that 郡国 and whose +14
is 0, in person order; each name is drawn by $00:CB6E with X = its WRAM record. Each run writes +29 = 6 (遼東) for
a block of 6 persons and 0 (三韓) for all others, clicks 遼東 and logs X at $00:CB6E: the listed persons must be
exactly the persons of the block that the game counts as present: per the ROM record, +14 (状態) = 1 (not 2) and
+30 = 0. All 600 x 4 persons.

Usage: .venv/bin/python tenbu/verify_places.py [--rom ROM] [--scenario 0-3]
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
from rom import DEFAULT_ROM, PERSON_COUNT, PERSON_SIZE, PERSON_WRAM, SCENARIO_YEARS, Rom

BLOCK = 6
TARGET = 6                      # 遼東: row 7 of 幽州, pointer (113, 209)
CLICK = "p:113:209 " + q.NUDGE + " b:10 w200"
SHOT = 200
NAMES_LUA = f"""
local names={{}}
emu.addMemoryCallback(function()
  local x=emu.getState()["cpu.x"]
  local p=(x-{PERSON_WRAM})//{PERSON_SIZE}
  if x>={PERSON_WRAM} and p<{PERSON_COUNT} and (x-{PERSON_WRAM})%{PERSON_SIZE}==0 then
    names[#names+1]=string.format("%04x", p)
  end
end, emu.callbackType.exec, 0x00CB6E)
function EXTRA_RESET() POINTER_RESET(); names={{}} end
function EXTRA_SHOT() local s=table.concat(names); names={{}}; if s=="" then s="00" end; return s end
"""


def run(rom: Rom, k: int) -> int:
    boot = (q.TO_SCENARIOS + " " + q.to_rulers(k) + " w200 " + q.card(0) + " " + q.START + " " + q.OPEN_PERSONS)
    blocks = [list(range(i, min(i + BLOCK, PERSON_COUNT))) for i in range(0, PERSON_COUNT, BLOCK)]
    boot_r, save, steps, plua = q.prepare(boot, [CLICK] * len(blocks))
    runs = []
    for i, (st, block) in enumerate(zip(steps, blocks)):
        wram = [q.mail(i)] + [(PERSON_WRAM + PERSON_SIZE * p + 29, bytes([TARGET if p in block else 0]))
                              for p in range(PERSON_COUNT)]
        runs.append({"steps": st, "shot": SHOT, "read": [], "wram": wram})
    results = replay.replay(rom.path, boot_r, save, runs, extra_lua=plua + NAMES_LUA, nmi=q.MAP_HOOK)
    bad = n = 0
    for block, (raw,) in zip(blocks, results):
        got = []
        for j in range(0, len(raw) - 1, 2):
            p = raw[j] << 8 | raw[j + 1]
            if p not in got:
                got.append(p)
        want = [p for p in block if rom.person(k, p)["状態"] == 1 and rom.person(k, p)["登場?"] == 0]
        n += len(block)
        if got != want:
            bad += 1
            print(f"  NG {SCENARIO_YEARS[k]} block {block[0]}: listed {got}, want {want}")
    print(f"scenario {SCENARIO_YEARS[k]}: list equal for {len(blocks) - bad}/{len(blocks)} blocks ({n} persons)")
    return bad


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證人物所在與是否在場（武将情報検索）")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--scenario", type=int, choices=(0, 1, 2, 3))
    args = ap.parse_args()
    t0 = time.time()
    if args.scenario is None:
        procs = [subprocess.Popen([sys.executable, __file__, "--rom", args.rom, "--scenario", str(k)])
                 for k in range(4)]
        errors = sum(p.wait() != 0 for p in procs)
        print(f"{time.time() - t0:.0f} s")
        print("ALL OK" if not errors else "mismatch(es)")
        raise SystemExit(1 if errors else 0)
    raise SystemExit(1 if run(Rom(args.rom), args.scenario) else 0)


if __name__ == "__main__":
    main()
