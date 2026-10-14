#!/usr/bin/env python3
"""Check the meaning of ship, base and country fields (rom.Rom.ships / bases / countries) against the game's own
screens (needs Mesen 2, about 3 minutes).

Scenario 3 as 日本軍, from the main screen. Each run opens one screen and pages through it; a Lua hook on vprintf
($06:BD03) records every call with one of the screen's formats (format address + 16 bytes of arguments):
- 資料 -> 艦船 -> 建造中艦船 / 予備艦船 ("%-8s\\n%-12s": type name, ship name): the ships listed must be the
  Japanese ships under construction (ship +14 bit 1) / the Japanese ships in no fleet (+4 = 0) and not under
  construction, with their type (+3) and name (+0);
- 資料 -> 基地 ("%-2s %-9s%s", "%2d %2d %2d %2d"): every base with its code (+4), name (+1), owner (+38 bit 0:
  日 / 連) and 鉄鉱 原油 人口 工業 (+23 to +26);
- 資料 -> 他国 ("%-8s%s ", "%2d %2d"): every country with its name, alliance (+3: 日本 連合 中立) and attitude to
  日本 / 連合 (+4, +5);
- 命令 -> 基地 -> a base (detail panel, 7 formats): 友好 (+29), 兵員輸送船 / 燃料輸送船 (+27, +28), 鉄鉱 人口
  原油 工業, 耐久 / 武装 and their maxima (+8, +9, +7 nibbles x 10), the six aircraft counts (+A to +14, words),
  資材 (+1A), 兵員 (+1C), 燃料 (+16, long).

Usage: .venv/bin/python teitoku/verify_tables.py [--rom ROM]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
sys.path.insert(0, os.path.join(HERE, "tools"))
import rom as R
from replay import replay
from sequences import DATA_MENU, ORDER_MENU, TO_SCENARIOS, end_frame, new_game

SC = 3
TO_MAIN = f"{TO_SCENARIOS} {new_game(SC, 0)}"
SHIP_ROW = 0x06FDE1
BASE_ROW, BASE_NUMS = 0x0FF2E3, 0x0FF2F3
COUNTRY_ROW, COUNTRY_NUMS = 0x0FF58D, 0x0FF5A1
DETAIL = [0x0EEFA8, 0x0EEFC9, 0x0EEFE3, 0x0EF000, 0x0EF01D, 0x0EF032, 0x0EF047]
FMTS = [SHIP_ROW, BASE_ROW, BASE_NUMS, COUNTRY_ROW, COUNTRY_NUMS, *DETAIL]
PAGE = "a:10 w300 "
NEXT = "r:10 w300 "
SHIP_MENU = DATA_MENU + " down:10 w30 down:10 w30 down:10 w30 a:10 w100 "
DETAIL_ROWS = 7
RUNS = {
    "building": SHIP_MENU + "down:10 w30 a:10 w300 " + PAGE * 8,
    "reserve": SHIP_MENU + "down:10 w30 down:10 w30 a:10 w300 " + PAGE * 20,
    "bases": DATA_MENU + " down:10 w30 down:10 w30 down:10 w30 down:10 w30 a:10 w300 " + NEXT * 8,
    "countries": DATA_MENU + " down:10 w30 down:10 w30 a:10 w300 " + NEXT * 2,
    **{f"detail{r}": ORDER_MENU + " down:10 w30 a:10 w300 " + "down:10 w30 " * r + "a:10 w300" for r in range(DETAIL_ROWS)},
}
MAX_RECS = 160
EXTRA = """
local MAP = {@MAP@}
local recs = {}
function EXTRA_RESET() recs = {} end
local function rd(a) return emu.read(a, emu.memType.snesMemory, false) end
emu.addMemoryCallback(function()
  local sp = emu.getState()["cpu.sp"]
  local fmt = rd(sp + 4) | rd(sp + 5) << 8 | rd(sp + 6) << 16
  fmt = MAP[fmt]
  if fmt == nil or #recs >= @MAX@ then return end
  local va = rd(sp + 8) | rd(sp + 9) << 8
  local u = {string.format("%06x", fmt)}
  for i = 0, 15 do u[#u + 1] = string.format("%02x", rd(va + i)) end
  recs[#recs + 1] = table.concat(u)
end, emu.callbackType.exec, 0x06BD03)
function EXTRA_SHOT() return table.concat(recs) .. string.rep("00", 19 * (@MAX@ - #recs)) end
""".replace("@MAX@", str(MAX_RECS))


def records(raw: bytes) -> list[tuple[int, bytes]]:
    out = []
    for k in range(0, len(raw), 19):
        fmt = int.from_bytes(raw[k:k + 3], "big")
        if fmt:
            out.append((fmt, raw[k + 3:k + 19]))
    return out


def pairs(recs: list[tuple[int, bytes]], first: int, second: int) -> list[tuple[bytes, bytes]]:
    """(args of a `first` call, args of the `second` call right after it) for every such pair."""
    return [(a, recs[k + 1][1]) for k, (f, a) in enumerate(recs[:-1]) if f == first and recs[k + 1][0] == second]


def p24(raw: bytes, o: int) -> int:
    return int.from_bytes(raw[o:o + 3], "little")


def w(raw: bytes, k: int) -> int:
    return R.le16(raw, 2 * k)


def main() -> None:
    ap = argparse.ArgumentParser(description="艦船、基地、他國欄位與遊戲畫面比對")
    ap.add_argument("--rom", default=R.DEFAULT_ROM)
    args = ap.parse_args()
    t0 = time.time()
    rom = R.Rom(args.rom)
    img = rom.scenario_image(SC)
    ships, bases, countries = rom.ships(SC), rom.bases(SC), rom.countries(SC)
    runs = [{"steps": s, "shot": end_frame(s, 0) + 60, "read": []} for s in RUNS.values()]
    res = dict(zip(RUNS, (records(r[0]) for r in replay(args.rom, TO_MAIN, end_frame(TO_MAIN), runs,
                                                         extra_lua=EXTRA.replace("@MAP@", rom.lua_string_map(FMTS))))))
    errors = 0
    ship_at = {p24(img, R.SHIPS + R.SHIP_SIZE * s["id"]): s for s in ships}  # name string -> ship
    type_ptr = [rom.ptr(R.SHIP_TYPE_NAMES + 3 * t) for t in range(16)]

    # ship lists
    for kind, want in (("building", [s for s in ships if s["side"] == 0 and s["building"]]),
                       ("reserve", [s for s in ships if s["side"] == 0 and not s["fleet"] and not s["building"]
                                    and not s["sunk"]])):
        rows = [a for f, a in res[kind] if f == SHIP_ROW]
        seen, bad = [], 0
        for a in rows:
            s = ship_at.get(p24(a, 4))
            if s is None or p24(a, 0) != type_ptr[s["type"]]:
                bad += 1
            elif s["id"] not in seen:
                seen.append(s["id"])
        ok = not bad and sorted(seen) == sorted(s["id"] for s in want)
        errors += not ok
        print(f"[ships {kind}] {len(seen)} ships listed, decoded {len(want)}; type and name of every row "
              + ("OK" if ok else f"NG (bad rows {bad}, missing {[s['name'] for s in want if s['id'] not in seen][:8]}, "
                 f"extra {[ships[i]['name'] for i in seen if i not in [s['id'] for s in want]][:8]})"))

    # base list
    seen, bad = set(), []
    base_at = {0x7E0000 + R.BASES + R.BASE_SIZE * b["id"] + 4: b for b in bases}  # code string -> base
    for name_row, nums in pairs(res["bases"], BASE_ROW, BASE_NUMS):
        b = base_at.get(p24(name_row, 0))
        if b is None:
            bad.append("?")
            continue
        owner = rom.string(p24(name_row, 8))
        if (p24(name_row, 4) != p24(img, R.BASES + R.BASE_SIZE * b["id"] + 1) or owner != "日連"[b["owner"]]
                or [w(nums, k) for k in range(4)] != [b["iron"], b["oil"], b["population"], b["industry"]]):
            bad.append(b["code"])
        seen.add(b["id"])
    errors += bool(bad) + (len(seen) != R.BASE_COUNT)
    print(f"[bases list] {len(seen)}/{R.BASE_COUNT} bases listed; code, name, owner, 鉄鉱 原油 人口 工業 "
          + ("OK" if not bad else f"NG {bad[:10]}"))

    # countries
    by_ptr = {p24(img, R.COUNTRIES + R.COUNTRY_SIZE * c["id"]): c for c in countries}
    seen, bad = set(), []
    for k, (row, nums) in enumerate(pairs(res["countries"], COUNTRY_ROW, COUNTRY_NUMS)):
        c = by_ptr.get(p24(row, 0))
        if c is None or rom.string(p24(row, 4)) != R.ALLIANCE[c["alliance"]] or \
                (w(nums, 0), w(nums, 1)) != (c["to_japan"], c["to_allies"]):
            bad.append(k)
        else:
            seen.add(c["id"])
    errors += bool(bad) + (len(seen) != len(countries))
    print(f"[countries] {len(seen)}/{len(countries)} countries listed; name, alliance, 対日 対連 "
          + ("OK" if not bad else f"NG rows {bad}"))

    # base detail
    done, bad = [], []
    for r in range(DETAIL_ROWS):
        d = {f: a for f, a in res[f"detail{r}"] if f in DETAIL}
        if len(d) != len(DETAIL):
            bad.append(f"row {r}: no detail")
            continue
        b = base_at[p24(d[DETAIL[0]], 0)]
        got = [w(d[DETAIL[1]], k) for k in range(3)] + [w(d[DETAIL[2]], k) for k in range(4)] + \
            [w(d[DETAIL[3]], k) for k in range(4)] + [w(d[DETAIL[4]], k) for k in range(3)] + \
            [w(d[DETAIL[5]], k) for k in range(3)] + [w(d[DETAIL[6]], 0), w(d[DETAIL[6]], 1), R.le32(d[DETAIL[6]], 4)]
        want = [b[k] for k in ("friendship", "troop_ships", "fuel_ships", "iron", "population")] + \
            [b["durability"], min(b["durability_max"], 99)] + [b["oil"], b["industry"], b["armament"],
                                                                 min(b["armament_max"], 99)] + \
            [b[k] for k in ("fighters", "attackers", "scouts", "twin_engine", "rockets", "large_planes", "materials",
                            "troops", "fuel")]
        if got != want:
            bad.append(f"{b['code']}: {got} != {want}")
        done.append(b["code"])
    errors += bool(bad)
    print(f"[base detail] {len(done) - len(bad)}/{DETAIL_ROWS} bases ({' '.join(done)}): 20 fields "
          + ("OK" if not bad else f"NG {bad[:3]}"))
    print(f"({time.time() - t0:.0f} s)")
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
