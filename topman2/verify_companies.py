#!/usr/bin/env python3
"""Check the companies, the home / office pairs and the prefecture names against the game in Mesen.

Part A — the PRESENT MODE start places, made at power-on by $06:8AE1(company): it draws r1 = random 0..14 and
r2 = random 0..1 (stored at S+3 / S+5). A Lua exec hook at $06:8B61 replaces them for each company (values in
WRAM $E000, copied by
EXTRA_RESET into Lua since the boot clears that area), savestate before the routine runs; after it, checked for all 15 x 2 (r1, r2):
1. the company record's home prefecture ($2820 + 21c + 2) = rom.hq_pairs()[r1][r2];
2. the office mask ($3638 + 6c) has exactly the bits of both prefectures of the pair;
3. the company names ($2826 + 21c) = the defaults at $06:F2A2 / F2AF / F2BC.
Part B — prefecture names: savestate on the scenario page, before YES draws the company page; company 0's home ($2822) is set to
every prefecture p and its office mask to {p, p + 1}; the page must draw '本社~<name p>' and '支社~<name p + 1>'
($01:D3CF), and the 3 default company names.

Usage: .venv/bin/python topman2/verify_companies.py [--rom ROM]
"""
import argparse
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "tools"))
import tm2
from replay import end_frame, replay
from rom import COMPANY_COUNT, COMPANY_SIZE, DEFAULT_ROM, PREF_COUNT, WRAM_COMPANY, WRAM_PLACES, Rom

BOOT_A = "w580"                  # $06:8AE1 runs at frame ~648
RAND_LUA = """
local PAR = {}
local reset0 = EXTRA_RESET
function EXTRA_RESET()   -- after the run's WRAM patch; the boot clears $E000 before $06:8AE1 runs
  for i = 0, 5 do PAR[i] = emu.read(0xE000 + i, emu.memType.snesWorkRam) end
  if reset0 then reset0() end
end
local function rand_hook()
  local function rd(a) return PAR[a - 0xE000] end
  local s = emu.getState()["cpu.sp"]
  local c = emu.read(s + 0x0D, emu.memType.snesMemory, false)
  emu.write(s + 3, rd(0xE000 + 2 * c), emu.memType.snesMemory)
  emu.write(s + 4, 0, emu.memType.snesMemory)
  emu.write(s + 5, rd(0xE001 + 2 * c), emu.memType.snesMemory)
  emu.write(s + 6, 0, emu.memType.snesMemory)
end
emu.addMemoryCallback(rand_hook, emu.callbackType.exec, 0x068B61)
emu.addMemoryCallback(rand_hook, emu.callbackType.exec, 0x868B61)
"""
BOOT_B = tm2.TO_SCENARIO_MENU + " a:10 w300"   # scenario 1 page; each run presses YES: the company page follows


def part_a(rom: Rom) -> int:
    pairs = rom.hq_pairs()
    combos = [(r1, r2) for r1 in range(15) for r2 in range(2)]
    runs = []
    for k in range(0, len(combos), COMPANY_COUNT):
        group = (combos[k:k + COMPANY_COUNT] * COMPANY_COUNT)[:COMPANY_COUNT]
        runs.append({"wram": [(tm2.PARAM, bytes(v for c in group for v in c))], "shot": 120,
                     "read": [("wram", WRAM_COMPANY, COMPANY_COUNT * COMPANY_SIZE),
                              ("wram", WRAM_PLACES, 6 * COMPANY_COUNT)]})
    res = replay(rom.path, BOOT_A, end_frame(BOOT_A), runs, extra_lua=RAND_LUA)
    names = [c["name"] for c in rom.companies()]
    ok_home = ok_mask = ok_name = n = 0
    seen = set()
    for k, r in zip(range(0, len(combos), COMPANY_COUNT), res):
        group = (combos[k:k + COMPANY_COUNT] * COMPANY_COUNT)[:COMPANY_COUNT]
        for c, (r1, r2) in enumerate(group):
            rec = r[0][COMPANY_SIZE * c:COMPANY_SIZE * (c + 1)]
            mask = int.from_bytes(r[1][6 * c:6 * c + 6], "little")
            home = rec[2] | rec[3] << 8
            want_mask = (1 << pairs[r1][0] - 1) | (1 << pairs[r1][1] - 1)
            n += 1
            ok_home += home == pairs[r1][r2]
            ok_mask += mask == want_mask
            ok_name += rec[6:].split(b"\0")[0].decode("cp932") == names[c]
            if home != pairs[r1][r2] or mask != want_mask:
                print(f"  NG company {c} r1 {r1} r2 {r2}: home {home} mask {mask:x}, rom {pairs[r1][r2]} {want_mask:x}")
            seen.add((r1, r2))
    print(f"[start places] home = pair[r1][r2]: {ok_home}/{n}; offices = both of the pair: {ok_mask}/{n}; "
          f"(r1, r2) covered {len(seen)}/30")
    print(f"[names] default company names: {ok_name}/{n}")
    return (n - ok_home) + (n - ok_mask) + (n - ok_name) + (30 - len(seen))


def part_b(rom: Rom) -> int:
    prefs = rom.prefectures()
    names = [c["name"] for c in rom.companies()]
    runs = []
    for p in range(PREF_COUNT):
        q = (p + 1) % PREF_COUNT
        runs.append({"wram": [(WRAM_COMPANY + 2, tm2.le16(p + 1)),
                              (WRAM_PLACES, ((1 << p) | (1 << q)).to_bytes(6, "little"))],
                     "steps": "a:10", "shot": 250, "read": []})
    res = replay(rom.path, BOOT_B, end_frame(BOOT_B), runs, extra_lua=tm2.COLLECT_LUA + tm2.TEXT_LUA)
    ok = okn = 0
    for p, r in enumerate(res):
        shown = tm2.texts(tm2.parse(r[-1]))
        q = (p + 1) % PREF_COUNT
        good = f"本社~{prefs[p]['name']}" in shown and f"支社~{prefs[q]['name']}" in shown
        ok += good
        okn += all(n in shown for n in names)
        if not good:
            print(f"  NG prefecture {p} {prefs[p]['name']}: drawn {[s for s in shown if '社~' in s][:4]}")
    print(f"[prefectures] '本社~name' / '支社~name' = $01:D3CF: {ok}/{PREF_COUNT}; company names drawn {okn}/{PREF_COUNT}")
    return 2 * PREF_COUNT - ok - okn


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--part", choices=["a", "b"], help=argparse.SUPPRESS)
    args = ap.parse_args()
    if args.part:   # one Mesen per process
        bad = (part_a if args.part == "a" else part_b)(Rom(args.rom))
        print(f"PART_BAD {bad}", flush=True)
        return
    t = time.time()
    procs = [subprocess.Popen([sys.executable, __file__, "--rom", args.rom, "--part", p], stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, text=True) for p in "ab"]
    bad = 0
    for p in procs:
        out = p.communicate()[0]
        for line in out.splitlines():
            if line.startswith("PART_BAD"):
                bad += int(line.split()[1])
            else:
                print(line)
        bad += "PART_BAD" not in out
    print(f"{'OK' if not bad else f'{bad} problem(s)'} ({time.time() - t:.0f} s)")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
