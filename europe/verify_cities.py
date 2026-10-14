#!/usr/bin/env python3
"""Check the city records (rom.Rom.cities: name, 耐久, the three supply values, garrison, side flag) against the
game's city screen (needs Mesen 2, a few minutes).

Scenario 1, one player, 連合軍, first command screen (savestate replay, tools/replay.py), then 情報 → 都市 → 自軍
and a on the first city. The screen ($CA:11F2 ...) lists the cities of the player's side ($7E:7FD1, built from
+57 bit 4 through $C3:0694), prints the name ($C1:195E, pointer = record), "%2d/%2d" 耐久 ($CA:635B) and
"%5d   %5d   %5d" ($CA:6363); the detail screen prints the first 3 garrison slots: weapon name ($C1:195E, the
weapon record's name pointer) and count ("%4d", $CA:6332 / $CA:6336). Slots after the third are not shown there
and are not checked.
For every city of the 6 scenarios one run overwrites the 11 city records of the WRAM block copy ($7E:3B28) with
that city's ROM record (+57 bit 4 set so that the Allies own it) and checks what the game prints. Two more runs
show a scenario 1 city with +57 bit 4 cleared (it must leave the list) and with the first and second triple of
supply values made different (shows which one the screen prints).

Usage: .venv/bin/python europe/verify_cities.py [--rom ROM]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
from replay import replay
from rom import CITIES_AT, CITY_SIZE, DEFAULT_ROM, SCENARIO_COUNT, WEAPON_SIZE, WEAPONS, Rom
from scenes import EVENTS_LUA, TO_COMMAND_ALLIES, events, length, save_frame

TO_CITIES = "down:4 w30 a:10 w200 down:4 w30 right:4 w30 a:10 w200 a:10 w300 a:10 w300"   # 情報, 都市, 自軍, a
TABLE = 0x2000 + CITIES_AT              # WRAM offset of the city table
SLOTS = 11                              # scenario 1 has 11 cities
DETAIL_LINES = 3                        # the detail screen shows the first 3 garrison slots

LUA = EVENTS_LUA + """
emu.addMemoryCallback(function()
  EVENTS[#EVENTS + 1] = string.format("S%06X", arg_ptr(4))
end, emu.callbackType.exec, 0xC1195E, 0xC1195E)
emu.addMemoryCallback(function()
  local f = arg_ptr(4)
  local kind = ({[0xCA635B] = "D", [0xCA6363] = "V", [0xCA6332] = "G", [0xCA6336] = "G"})[f]
  if kind then EVENTS[#EVENTS + 1] = kind .. hex(arg_ptr(8), 6) end
end, emu.callbackType.exec, 0xC1286A, 0xC1286A)
"""


def words(h: str) -> list[int]:
    b = bytes.fromhex(h)
    return [b[i] | b[i + 1] << 8 for i in range(0, len(b), 2)]


def screen(ev: list[str]) -> dict:
    """First list row (name pointer, 耐久, values) and the detail lines (weapon name pointer, count)."""
    out = {"name": None, "D": None, "V": None, "garrison": []}
    last_s = None
    for e in ev:
        if e[0] == "S":
            last_s = int(e[1:], 16)
            if out["name"] is None and 0x7E3B28 <= last_s < 0x7E3B28 + SLOTS * CITY_SIZE:
                out["name"] = last_s
        elif e[0] in "DV" and out[e[0]] is None:
            out[e[0]] = words(e[1:])
        elif e[0] == "G":
            out["garrison"].append((last_s, words(e[1:])[0]))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證都市（名稱、耐久、三項物資、駐軍、陣營旗標）")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    t0 = time.time()
    rom = Rom(args.rom)
    cities = [(sc, c) for sc in range(SCENARIO_COUNT) for c in rom.cities(sc)]

    def run(records: list[bytes]) -> dict:
        return {"wram": [(TABLE, b"".join(records))], "steps": TO_CITIES, "shot": length(TO_CITIES),
                "read": [("wram", 0, 1)]}

    runs = []
    for _, c in cities:
        r = bytearray(c["raw"])
        r[57] |= 0x10
        runs.append(run([bytes(r)] * SLOTS))
    base = rom.cities(0)
    enemy = bytearray(base[0]["raw"])
    enemy[57] &= ~0x10
    runs.append(run([bytes(enemy)] + [c["raw"] for c in base[1:SLOTS]]))
    split = bytearray(base[0]["raw"])
    split[13:19] = (11111).to_bytes(2, "little") + (22222).to_bytes(2, "little") + (3333).to_bytes(2, "little")
    split[19:25] = (1).to_bytes(2, "little") + (2).to_bytes(2, "little") + (3).to_bytes(2, "little")
    runs.append(run([bytes(split)] + [c["raw"] for c in base[1:SLOTS]]))
    shots = replay(args.rom, TO_COMMAND_ALLIES, save_frame(TO_COMMAND_ALLIES), runs, extra_lua=LUA)

    ok_n, bad = 0, []
    for (sc, c), (_, raw) in zip(cities, shots):
        got = screen(events(raw))
        garrison = [(rom.ptr(WEAPONS + WEAPON_SIZE * g["weapon"]) | 0xC00000, g["count"]) for g in c["garrison"]]
        want = {"name": 0x7E3B28, "D": [c["耐久"], c["耐久max"], got["D"][2] if got["D"] else None],
                "V": [c["弾薬"], c["燃料"], c["食料"]], "garrison": garrison}
        if (got["name"] == want["name"] and got["D"] and got["D"][:2] == want["D"][:2] and got["V"] == want["V"]
                and got["garrison"] == garrison[:DETAIL_LINES]):
            ok_n += 1
        else:
            bad.append(f"scenario {sc + 1} {c['name']}: screen {got}, ROM {want}")
    print(f"[cities] {ok_n}/{len(cities)} cities: name (record pointer), 耐久 cur/max, 弾薬 燃料 食料 and every "
          f"garrison slot the detail screen shows (weapon name pointer, count; first {DETAIL_LINES}) as the city "
          f"screen prints them; {sum(len(c['garrison']) > DETAIL_LINES for _, c in cities)} cities have more slots "
          f"({sum(max(0, len(c['garrison']) - DETAIL_LINES) for _, c in cities)} not shown, not checked)")
    e_ev, s_ev = (events(raw) for _, raw in shots[len(cities):])
    listed = {int(e[1:], 16) for e in e_ev if e[0] == "S"}
    enemy_out = 0x7E3B28 not in listed and 0x7E3B28 + CITY_SIZE in listed
    print(f"[side] scenario 1 city 0 with +57 bit 4 cleared is left out of the Allies' list: {enemy_out}")
    first = screen(s_ev)["V"]
    which = "first (+13 +15 +17)" if first == [11111, 22222, 3333] else \
        "second (+19 +21 +23)" if first == [1, 2, 3] else f"neither: {first}"
    print(f"[supplies] with the two triples made different the screen prints the {which}")
    bad += [] if enemy_out else ["side flag"]
    bad += [] if first == [11111, 22222, 3333] else ["supply triple"]
    for b in bad[:20]:
        print("  NG", b)
    print(f"{'ALL OK' if not bad else f'{len(bad)} problem(s)'} ({time.time() - t0:.0f} s)")
    raise SystemExit(1 if bad else 0)


if __name__ == "__main__":
    main()
