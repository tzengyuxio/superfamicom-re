#!/usr/bin/env python3
"""Check the scenario tables and the city data against the game in Mesen.

For both scenarios a new game is started (PLAYER1 = MAN, home city London, 3 COM players) and the main screen
is saved. Then:
  * WRAM after the game's own set-up (OPENING $A929): city records $5BF2 (+2 population / 100, +4 tourism,
    +6 economy, +10 = (2 * tourism + economy) / 3), slot records $6DD6 (+2 slots), each player's slots in the
    home city ($6DD6 + 20 * home + 4 + 2 * player = home slots) and the player record +18..+25 (OPENING $BB70,
    scenario 1 lowers it by 15 / 15 / 15 / 30);
  * the city screen (DIORMINF $D3BE) for each of the 22 cities: the game's printf arguments for the name,
    人口, 経済力 / 観光地 rank, スロット数 and the city type sentence. The screen is opened by making the VM
    call COMMAND $AA02(city, player) from the main screen's pad loop (airmanage/tools/vm.py).
"""
import argparse
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "tools"))
import vm
from replay import replay
from rom import CITY_COUNT, DEFAULT_ROM, Rom, le16


def check_scenario(r: Rom, s: int) -> int:
    cities = r.cities()
    sc = r.scenario_cities(s)
    hq = r.hq_table(s)
    a = vm.addresses(r.rev)
    runs = [{"wram": vm.command_inject(r.rev, [(a["city_show"], [c, 0])]), "shot": 300,
             "read": [("wram", a["city_rec"], 12 * CITY_COUNT), ("wram", a["slot_rec"], 20 * CITY_COUNT),
                      ("wram", a["player_rec"], 256),
                      ("wram", a["scenario"], 2)]} for c in range(CITY_COUNT)]
    res = replay(r.path, vm.boot(s), vm.MAIN_FRAME, runs, extra_lua=vm.boot_lua(r.rev) + vm.INJECT_LUA + vm.PRINTF_LUA)
    bad = 0
    city, slot, player, scen = res[0][:4]
    if le16(scen, 0) != s:
        print(f"  scenario variable $4686 = {le16(scen, 0)}")
        bad += 1
    # WRAM set-up
    wbad = 0
    for c, v in enumerate(sc):
        rec = city[12 * c:12 * c + 12]
        want = [v["pop_raw"], v["tourism"], v["economy"]]
        got = [le16(rec, 2), le16(rec, 4), le16(rec, 6)]
        if got != want or le16(rec, 10) != (2 * v["tourism"] + v["economy"]) // 3 or slot[20 * c + 2] != v["slots"]:
            print(f"  city {c}: WRAM {got} +10={le16(rec, 10)} slots={slot[20 * c + 2]}; ROM {want} {v['slots']}")
            wbad += 1
    pbad = 0
    for p in range(4):
        rec = player[64 * p:64 * p + 64]
        h = le16(rec, 2)
        want = hq[h]
        got = [le16(rec, 18 + 2 * k) for k in range(4)]
        home = slot[20 * h + 4 + 2 * p]
        ok = got == want and home == sc[h]["home_slots"]
        pbad += not ok
        print(f"  player {p}: home {h} {cities[h]['name']}, slots there {home} (ROM {sc[h]['home_slots']}), "
              f"+18..+25 {got} (ROM {want}) {'OK' if ok else 'NG'}")
    print(f"  WRAM city / slot records: {CITY_COUNT - wbad}/{CITY_COUNT} OK")
    # city screen
    sbad = 0
    for c, run in enumerate(res):
        pf = vm.printf_records(run[-1]) if len(run) > 4 else []
        by = {}
        for p in pf:
            by.setdefault(p["fmt_ptr"], []).append(p)
        v = sc[c]
        try:
            name = by[0xDBF6][0]["s0"]
            pop = by[0xDBFB][0]["args"][0]
            ranks = [p["s0"] for p in by[0xDC11] + by[0xDC23]]
            used, total = by[0xDC39][0]["args"][:2]
            kind = by[0xDC65][0]["s1"]
        except (KeyError, IndexError):
            print(f"  city {c}: screen not captured ({len(pf)} printf calls)")
            sbad += 1
            continue
        want = (cities[c]["name"], v["population"], [r.rank(v["economy"]), r.rank(v["tourism"])], v["slots"],
                cities[c]["type_name"])
        got = (name, pop, [x.translate(str.maketrans("ａｂｃｄｓ", "abcds")) for x in ranks], total, kind)
        if got != want:
            print(f"  city {c}: screen {got}; ROM {want}")
            sbad += 1
        elif c in (0, 11):
            print(f"  city {c}: {name} 人口{pop}万人 経済力{ranks[0]} 観光地{ranks[1]} スロット{used}/{total} {kind}")
    print(f"  city screen: {CITY_COUNT - sbad}/{CITY_COUNT} OK")
    return bad + wbad + pbad + sbad


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--scenario", type=int, choices=[1, 2])
    args = ap.parse_args()
    t = time.time()
    if args.scenario is None:  # Mesen can only be opened once per process: one subprocess per scenario
        bad = sum(subprocess.run([sys.executable, os.path.abspath(__file__), "--rom", args.rom, "--scenario", str(s)],
                                 stderr=subprocess.DEVNULL, check=False).returncode != 0 for s in (1, 2))
        print(f"{'OK' if not bad else f'{bad} scenario(s) with mismatches'} ({time.time() - t:.0f} s)")
        sys.exit(1 if bad else 0)
    print(f"scenario {args.scenario}:", flush=True)
    bad = check_scenario(Rom(args.rom), args.scenario - 1)
    print(f"  {'OK' if not bad else f'{bad} mismatches'} ({time.time() - t:.0f} s)", flush=True)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
