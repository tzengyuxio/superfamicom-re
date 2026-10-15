#!/usr/bin/env python3
"""Check the record decoders (rom.Decoders) against the game's own screens (needs Mesen 2, about 4 minutes).

Scenario 0 as 日本, from the main screen. Each run opens one screen of 情報, 一覧 or 作戦 -> 人事 and pages through
it with R; tools/printf_trace.py records every vsprintf call (format, arguments) and WRAM $7E:2000-$A2FF is dumped
when the run ends. The dump is decoded with rom.Decoders, and every row the screen printed must show the decoded
values of the same record (found by its name, code or number). Values the game changes after the start (e.g. the
reserve aircraft) are therefore compared with the game's memory, not with the scenario image (verify_scenarios.py
checks that image).

Usage: .venv/bin/python teitoku2/verify_tables.py [--rom ROM] [--dump DIR] [--load DIR]
  --dump writes the traces and WRAM of every run; --load checks such a directory without running the game.
"""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
sys.path.insert(0, os.path.join(HERE, "tools"))
import printf_trace
import rom as R
from replay import replay
from sequences import INFO, LIST, PERSONNEL, TO_SCENARIOS, end_frame, expand, new_game

SC = 0
TO_MAIN = f"{TO_SCENARIOS} {new_game(SC)}"
WRAM_LO, WRAM_HI = 0x2000, 0xA300
R_PAGE = " r:10 w200"
CHOICE = ["a:10 w300", "down:10 w60 a:10 w300", "down:10 w60 down:10 w60 a:10 w300"]  # 日本 / アメリカ / その他
RUNS = {
    "active": INFO + " a:10 w300" + R_PAGE * 8,
    "reserve": INFO + " down:10 w60 down:10 w60 down:10 w60 a:10 w300" + R_PAGE * 17,
    **{f"classes{k}": INFO + " right:10 w60 a:10 w200 " + CHOICE[k] + R_PAGE * 12 for k in range(3)},
    **{f"aircraft{k}": INFO + " right:10 w60 down:10 w60 a:10 w200 " + CHOICE[k] + R_PAGE * 8 for k in range(3)},
    "tanks": INFO + " right:10 w60 down:10 w60 down:10 w60 a:10 w300" + R_PAGE * 2,
    **{f"subclasses{k}": INFO + " right:10 w60 down:10 w60 down:10 w60 down:10 w60 a:10 w200 " + CHOICE[k] + R_PAGE * 3 for k in range(2)},
    "power": INFO + " right:10 w60 right:10 w60 a:10 w300",
    "navy": INFO + " right:10 w60 right:10 w60 down:10 w60 a:10 w300" + R_PAGE * 2,
    "army": INFO + " right:10 w60 right:10 w60 down:10 w60 down:10 w60 a:10 w300" + R_PAGE * 2,
    "diplomacy": INFO + " right:10 w60 right:10 w60 down:10 w60 down:10 w60 down:10 w60 a:10 w300",
    "fleets": LIST + " a:10 w300" + R_PAGE * 2,
    "marines": LIST + " down:10 w60 down:10 w60 a:10 w300" + R_PAGE * 4,
    "submarines": LIST + " down:10 w60 down:10 w60 down:10 w60 a:10 w300" + R_PAGE * 2,
    "bases": LIST + " down:10 w60 down:10 w60 down:10 w60 down:10 w60 a:10 w300" + R_PAGE * 14,
    "kyoten": LIST + " down:10 w60 down:10 w60 down:10 w60 down:10 w60 down:10 w60 a:10 w300" + R_PAGE * 11,
    "admirals": PERSONNEL + " a:10 w300" + R_PAGE * 5,
    "generals": PERSONNEL + " down:10 w60 a:10 w300" + R_PAGE * 3,
}

# formats (raw bytes; the same in both versions)
ACTIVE_ROW = (b"%s", b"%-8s    %2d\x1bC%c%2d\x1bC%c%2d\x1bC%c%2d\x1bC%c%2d\x1bC%c%2d\x1bC7%2d\x1bC6%2d\x1bC7")
RESERVE_ROW = (b"%-14s\x1bC%c%d", b"\x1bC%c%d", b"\x1bC%c%d\x1bC7", b"%-8s", b"\x1bC%c%d",
               b"\x1bC%c%2d\x1bC%c%2d\x1bC%c%2d\x1bC%c%2d\x1bC6%2d\x1bC7%2d")
CLASS_ROW = (b"%-14s%d", b"%d", b"%d", b"%-8s", b"%d", b"\x1bC6%2d\x1bC7%2d\x1bC6%2d\x1bC7%2d\x1bC6%2d\x1bC7%2d")
AIRCRAFT_ROW = (b"%-12s        %-2d    %-2d", b"%-10s")
SUBCLASS_ROW = (b"%-12s\x82a     %-2d     %-2d", b"%-2d     %-2d")
TANK_ROW = (b"%-5s", b"%-2d    %-2d")
POWER_ROW = b"%6d %6d"
NAVY_HEAD = (b"%5d         %5d", b"%2d\x82\x89          %2d\x83\xcf")
ARMY_HEAD = (b"%5d         %5d", b"%2d\x82\x89          %2d\x84/", b"%2d\x82\x89")
RESERVE_AIR = b"%1s:%-12s%3d\x82\x0b\n"
DIPLOMACY_ROW = (b"%s", b"%8s %8s", b"%6d")
FLEET_ROW = (b"\x841%2d%s\x81\xf3\x84-\x1bC7", b"%-12s", b"%-10s", b"%3d-%3d", b"%4s", b"%2s")
MARINE_ROW = (b"\x841%2d%6s\x1bC7 %s", b"%-12s", b"%s%s", b"%3d")
SUB_ROW = (b"%2d\x1bC7%s", b"%-12s", b"%3d-%3d")  # number name, commander, position and target
BASE_ROW = (b"%2s %s\x1bC7", b"(%s%s)", b"%2d\x1bC7/%2d", b"%s  %s")
KYOTEN_ROW = (b"%2d", b" %-9s %2s %4s")
ADMIRAL_ROW = (b"%-12s", b"%-14s")
GENERAL_ROW = b"%-12s"
# 海軍兵力 shows the 14 reserve slots (type class k // 2, A / B) in this order over its two pages
NAVY_ORDER = [0, 1, 4, 5, 6, 7, 10, 11, 2, 3, 8, 9, 12, 13]
LIST_NAMES = ("日本", "アメリカ", "その他")


def collect(rom: R.Rom, names: list[str]) -> dict:
    """Run the screens: {run: (calls, WRAM bank $7E image)}; a call has "ftext", the raw format bytes."""
    lua = printf_trace.lua(rom.off["code"]["vsprintf"], fmt_at=8, va_at=12, dst_at=4, esc_c=True) + """
function EXTRA_RESET() PF_RESET() end
function EXTRA_SHOT() return PF_SHOT() end
"""
    runs = []
    for n in names:
        steps = expand(RUNS[n])
        runs.append({"steps": steps, "shot": end_frame(steps, 0) + 60, "read": [("wram", WRAM_LO, WRAM_HI - WRAM_LO)]})
    boot = expand(TO_MAIN)
    out = {}
    for n, (wram, pf) in zip(names, replay(rom.path, boot, end_frame(boot), runs, extra_lua=lua)):
        img = bytearray(0x10000)
        img[WRAM_LO:WRAM_HI] = wram
        out[n] = (with_ftext(rom, printf_trace.parse(pf)), bytes(img))
    return out


def with_ftext(rom: R.Rom, calls: list[dict]) -> list[dict]:
    for c in calls:
        o = R.hirom(c["fmt"]) if c["fmt"] >= 0xC00000 else None
        c["ftext"] = rom.data[o:rom.data.index(0, o)] if o is not None else b""
    return calls


def dump(res: dict, d: str) -> None:
    os.makedirs(d, exist_ok=True)
    for n, (calls, img) in res.items():
        with open(os.path.join(d, f"{n}.json"), "w", encoding="utf-8") as f:
            json.dump([{"fmt": c["fmt"], "out": c["out"].hex(),
                        "args": [{"s": a.hex()} if isinstance(a, bytes) else a for a in c["args"]]} for c in calls], f)
        with open(os.path.join(d, f"{n}.wram"), "wb") as f:
            f.write(img)


def load(rom: R.Rom, d: str, names: list[str]) -> dict:
    out = {}
    for n in names:
        with open(os.path.join(d, f"{n}.json"), encoding="utf-8") as f:
            calls = [{"fmt": c["fmt"], "out": bytes.fromhex(c["out"]),
                      "args": [bytes.fromhex(a["s"]) if isinstance(a, dict) else a for a in c["args"]]}
                     for c in json.load(f)]
        with open(os.path.join(d, f"{n}.wram"), "rb") as f:
            out[n] = (with_ftext(rom, calls), f.read())
    return out


class Checker:
    def __init__(self, rom: R.Rom, res: dict):
        self.rom, self.res, self.errors = rom, res, 0

    def text(self, a):
        return self.rom.text(a, katakana=True) if isinstance(a, bytes) else a

    def calls(self, run: str) -> list[tuple[bytes, list]]:
        return [(c["ftext"], [self.text(a) for a in c["args"]]) for c in self.res[run][0]]

    def rows(self, run: str, fmts: tuple) -> list[list]:
        """For every call of fmts[0]: its args and those of the next call of each further format (None if a
        format does not come before the next fmts[0])."""
        calls = self.calls(run)
        out = []
        for k, (f, a) in enumerate(calls):
            if f != fmts[0]:
                continue
            row, j = [a], k + 1
            for g in fmts[1:]:
                while j < len(calls) and calls[j][0] not in (g, fmts[0]):
                    j += 1
                row.append(calls[j][1] if j < len(calls) and calls[j][0] == g else None)
            out.append(row)
        return out

    def img(self, run: str) -> bytes:
        return self.res[run][1]

    def report(self, label: str, n: int, bad: list, extra: str = "") -> None:
        self.errors += bool(bad) + (n == 0)
        print(f"[{label}] {n - len(bad)}/{n} rows OK{extra}" + (f"; NG {bad[:4]}" if bad else ""))


def check_ships(ck: Checker) -> None:
    rom = ck.rom
    types = rom.type_names()
    for run in ("active", "reserve"):
        img = ck.img(run)
        ships, cls = rom.ships(img), rom.ship_classes(img)
        by_name = {f"{s['name']} {s['reading']}": s for s in ships}
        rows = ck.rows(run, ACTIVE_ROW if run == "active" else RESERVE_ROW)
        rows = [r for r in rows if None not in r]  # "%s" also prints the screen title
        bad, seen, torpedo = [], set(), set()
        for r in rows:
            s = by_name.get(r[0][0])
            if s is None:
                bad.append(r[0][0])
                continue
            c = cls[s["class"]]
            if run == "active":
                a = r[1]
                got = [a[0], a[3], a[5], a[7], a[9], a[11], a[13]]
                want = [types[c["type"]], s["armor"][3], s["anti_ship"], s["anti_air"], c["torpedo"], s["speed"],
                        s["skill"]]
            else:
                a = r[5]
                got = [r[0][2], r[1][1], r[2][1], r[4][1], r[3][0], a[1], a[3], a[7], a[9]]
                want = s["armor"] + [types[c["type"]], s["anti_ship"], s["anti_air"], s["speed"], s["skill"]]
                torpedo.add(a[5])
            if got != want:
                bad.append(f"{s['name']}: {got} != {want}")
            seen.add(s["id"])
        fields = ("艦種 装甲(下) 対艦 対空 水雷(艦型) 速度 練度" if run == "active"
                  else f"装甲 上左右下 艦種 対艦 対空 速度 練度 (水雷 printed as {sorted(torpedo)})")
        ck.report(f"ships {run}", len(rows), bad, f" ({len(seen)} ships): {fields}")


def check_classes(ck: Checker) -> None:
    rom = ck.rom
    types = rom.type_names()
    for k in range(3):
        run = f"classes{k}"
        cls = rom.ship_classes(ck.img(run))
        rows = ck.rows(run, CLASS_ROW)
        bad, seen = [], set()
        for r in rows:
            got = [r[0][1], r[1][0], r[2][0], r[4][0], r[3][0], *r[5]]
            cands = [c for c in cls if c["name"] == r[0][0] and got == c["armor"] + [
                types[c["type"]], c["anti_ship"], c["anti_air"], c["torpedo"], c["speed"], c["aircraft"],
                c["supplies"]]]
            if cands:
                seen.add(cands[0]["id"])
            else:
                bad.append(f"{r[0][0]}: {got}")
        countries = sorted({cls[i]["country"] for i in seen})
        ck.report(f"ship classes {LIST_NAMES[k]}", len(rows), bad,
                  f" ({len(seen)} classes, country {countries}): 装甲 上左右下 艦種 対艦 対空 水雷 速度 搭載 物資")


def check_weapons(ck: Checker) -> None:
    rom = ck.rom
    air_types = rom.air_type_names()
    for k in range(3):
        run = f"aircraft{k}"
        ac = rom.aircraft(ck.img(run))
        rows = ck.rows(run, AIRCRAFT_ROW)
        bad, seen = [], set()
        for r in rows:
            got = [r[0][1], r[0][2], r[1][0] if r[1] else None]
            cands = [a for a in ac if a["name"] == r[0][0] and got == [a["combat"], a["range"], air_types[a["type"]]]]
            if cands:
                seen.add(cands[0]["id"])
            else:
                bad.append(f"{r[0][0]}: {got}")
        countries = sorted({ac[i]["country"] for i in seen})
        ck.report(f"aircraft {LIST_NAMES[k]}", len(rows), bad,
                  f" ({len(seen)} aircraft, country {countries}): 戦闘 航続 種別")
    for k in range(2):
        run = f"subclasses{k}"
        sc = rom.sub_classes(ck.img(run))
        rows = ck.rows(run, SUBCLASS_ROW)
        bad, seen = [], set()
        for r in rows:
            got = [r[0][1], r[0][2], *r[1]]
            cands = [c for c in sc if c["name"] == r[0][0] and got == [c["armor"], c["speed"], c["torpedo"],
                                                                        c["supplies"]]]
            if cands:
                seen.add(cands[0]["id"])
            else:
                bad.append(f"{r[0][0]}: {got}")
        countries = sorted({sc[i]["country"] for i in seen})
        ck.report(f"submarine classes {LIST_NAMES[k]}", len(rows), bad,
                  f" ({len(seen)} classes, country {countries}): 装甲 速度 水雷 物資")
    tanks = rom.tanks(ck.img("tanks"))
    rows = ck.rows("tanks", TANK_ROW)
    bad, seen = [], set()
    for r in rows:
        cands = [t for t in tanks if t["name"] == r[0][0] and r[1] == [t["caliber"], t["armor"]]]
        if cands:
            seen.add(cands[0]["id"])
        else:
            bad.append(f"{r[0][0]}: {r[1]}")
    ck.report("tanks", len(rows), bad, f" ({len(seen)}/{R.TANK_COUNT} tanks): 口径 装甲")


def check_nation(ck: Checker) -> None:
    rom = ck.rom
    sides = rom.sides(ck.img("power"))
    got = [a for f, a in ck.calls("power") if f == POWER_ROW]
    keys = ["gnp", "tech_intel", "tech_ships", "tech_aircraft", "tech_weapons", "tech_industry", "base_upkeep"]
    bad = [f"{k}: {a}" for k, a in zip(keys, got) if a != [sides[0][k], sides[1][k]]]
    ck.report("national power", min(len(got), len(keys)), bad,
              " (日本 連合国): 国民生産力 情報 艦船 航空 兵器 工業技術力 基地維持費")

    for run, order, head, labels in (
            ("navy", NAVY_ORDER, NAVY_HEAD, ("budget", "materials", "marines", "transports")),
            ("army", list(range(8)), ARMY_HEAD, ("budget", "materials", "infantry", "trucks", "armored"))):
        img = ck.img(run)
        res = getattr(rom, f"{run}_reserve")(img)[0]
        ac = rom.aircraft(img)
        calls = ck.calls(run)
        heads = [a for f, a in calls if f in head][:len(head)]
        want = [[res[labels[0]], res[labels[1]]], [res[labels[2]], res[labels[3]]]] + [[res[x]] for x in labels[4:]]
        bad = [f"head {heads} != {want}"] if heads != want else []
        rows = [a for f, a in calls if f == RESERVE_AIR]
        for i, r in zip(order, rows):
            aid, cnt = res["aircraft"][i]
            w = ["AB"[i % 2], ac[aid]["name"] if aid != 0xFF else "", cnt]
            if r != w:
                bad.append(f"slot {i}: {r} != {w}")
        if len(rows) < len(order):
            bad.append(f"only {len(rows)} aircraft rows")
        ck.report(f"{run} reserve", 1 + min(len(rows), len(order)), bad,
                  f" (日本): {' '.join(labels)}, {len(order)} aircraft slots (機種 機數)")

    countries = rom.countries(ck.img("diplomacy"))
    sides = rom.sides(ck.img("diplomacy"))
    abbr = rom.country_abbr()
    rows = ck.rows("diplomacy", DIPLOMACY_ROW)
    rows = [r for r in rows if None not in r]
    bad = []
    for r in rows:
        c = abbr.index(r[0][0])
        to_j = ("交戦状態" if c == 1 or c in sides[1]["relation1"] else "軍事協定" if c in sides[0]["alliance"]
                else "援助協定" if c in sides[0]["aid"] else "----")
        to_a = ("----" if c == 1 else "軍事同盟" if c in sides[1]["relation1"] + sides[1]["alliance"]
                else "援助協定" if c in sides[1]["aid"] else "----")
        if r[1] != [to_j, to_a] or r[2] != [countries[c]["japan_friendship"]]:
            bad.append(f"{r[0][0]}: {r[1]} {r[2]} != {[to_j, to_a]} {countries[c]['japan_friendship']}")
    ck.report("diplomacy", len(rows), bad, " (8 countries): 對日 對連關係（國力 mask +0x19 +0x1F +0x25）、對日友好度")


def check_lists(ck: Checker) -> None:
    rom = ck.rom
    img = ck.img("fleets")
    fleets, adm, bases = rom.fleets(img), rom.admirals(img), rom.bases(img)
    calls = ck.calls("fleets")
    bad, n = [], 0
    for k, (f, a) in enumerate(calls):
        if f != FLEET_ROW[0]:
            continue
        n += 1
        fl = fleets[a[0] - 1]
        row = {}
        for g, b in calls[k + 1:]:
            if g == FLEET_ROW[0]:
                break
            row.setdefault(g, []).append(b)
        docked = FLEET_ROW[2] in row
        coords = row.get(FLEET_ROW[3], [])
        got = [row[FLEET_ROW[1]][0][0], row[FLEET_ROW[2]][0][0] if docked else coords[:1],
               row.get(FLEET_ROW[4], [["無し"]])[0][0], row.get(FLEET_ROW[5], [[None]])[0][0], coords[1:]]
        mission = R.FLEET_MISSIONS.get(fl["mission"], "?")
        want = [adm[fl["admiral"]]["name"], bases[fl["x"] & 0xFF]["name"] if docked else [[fl["x"], fl["y"]]],
                mission, bases[fl["target_x"]]["code"] if mission == "奇襲" else None,
                [[fl["target_x"], fl["target_y"]]] if mission == "哨戒" else []]
        if got != want:
            bad.append(f"fleet {a[0]}: {got} != {want}")
    ck.report("fleet list", n, bad, ": 提督 所在基地 / 座標 任務 目標基地 / 目標座標")

    img = ck.img("marines")
    gens, bases = rom.generals(img), rom.bases(img)
    bad, n = [], 0
    for r in ck.rows("marines", MARINE_ROW):
        n += 1
        b = img[R.MARINES + R.MARINE_SIZE * (r[0][0] - 1):][:R.MARINE_SIZE]
        got = [r[1][0] if r[1] else None, r[2][1] if r[2] else None, r[3][0] if r[3] else None]
        want = [gens[b[6]]["name"] if b[6] != 0xFF else "", bases[b[4]]["code"] if b[4] != 0xFF else None,
                b[1] if b[4] != 0xFF else None]
        if got != want:
            bad.append(f"{r[0][0]}: {got} != {want}")
    ck.report("marine list", n, bad, ": 指揮官（陸戦隊 +6）目標基地（+4，FF 無）兵力（+1）")

    subs = rom.submarines(ck.img("submarines"))
    bad, n = [], 0
    calls = ck.calls("submarines")
    for k, (f, a) in enumerate(calls):
        if f != SUB_ROW[0]:
            continue
        n += 1
        s = subs[a[0] - 1]
        xy = [b for g, b in calls[k + 1:k + 4] if g == SUB_ROW[2]]
        if [a[1], xy] != [s["name"], [[s["x"], s["y"]], [s["dest_x"], s["dest_y"]]]]:
            bad.append(f"{a}: {xy} != {s['name']} {s['x']},{s['y']} {s['dest_x']},{s['dest_y']}")
    ck.report("submarine list", n, bad, ": 名 位置 目標")

    bases = {b["code"]: b for b in rom.bases(ck.img("bases"))}
    lv = R.RESOURCE_LEVELS
    rows = ck.rows("bases", BASE_ROW)
    bad, seen = [], set()
    for r in rows:
        b = bases.get(r[0][0])
        if b is None:
            bad.append(r[0])
            continue
        got = [r[0][1], r[1][0], r[2], r[3]]
        want = [b["name"], R.COUNTRY_NAMES[b["owner"]], [b["production"], b["production_max"]],
                [lv[b["oil"]], lv[b["ore"]]]]
        if got != want:
            bad.append(f"{b['code']}: {got} != {want}")
        seen.add(b["code"])
    bad += [f"{len(seen)} bases listed"] if len(seen) != R.BASE_COUNT else []
    ck.report("base list", len(rows), bad, f" ({len(seen)}/{R.BASE_COUNT} bases): 代碼 名 擁有國 生産力/最大 油 鉱")

    ky = rom.kyoten(ck.img("kyoten"))
    abbr = rom.country_abbr()
    calls = ck.calls("kyoten")
    rows, num = [], 0  # number 100 is not printed with "%2d": it follows 99
    for k, (f, a) in enumerate(calls):
        if f == KYOTEN_ROW[1]:
            num = calls[k - 1][1][0] if calls[k - 1][0] == KYOTEN_ROW[0] else num + 1
            rows.append((num, a))
    bad, seen = [], set()
    for num, a in rows:
        k = ky[num - 1]
        want = [k["name"], abbr[k["owner"]], R.TERRAIN[k["terrain"]]]
        if a != want:
            bad.append(f"{num}: {a} != {want}")
        seen.add(k["id"])
    bad += [f"{len(seen)} 拠点 listed"] if len(seen) != R.KYOTEN_COUNT else []
    ck.report("kyoten list", len(rows), bad, f" ({len(seen)}/{R.KYOTEN_COUNT} 拠点): 名 擁有國 地形")


def check_personnel(ck: Checker) -> None:
    rom = ck.rom
    img = ck.img("admirals")
    adm, fleets = rom.admirals(img), rom.fleets(img)
    calls = ck.calls("admirals")
    names = [a[0] for f, a in calls if f == ADMIRAL_ROW[0]]
    cmd = [a[0].strip() for f, a in calls if f == ADMIRAL_ROW[1]]
    by_adm = {f["admiral"]: f["id"] for f in fleets if f["admiral"] >= 0}
    seen = list(dict(zip(names, cmd)).items())  # each name is followed by its command; pages repeat at the end
    want = [(a["name"], f"第{by_adm[a['id']] + 1:2d}艦隊" if a["id"] in by_adm else "") for a in adm[:30]]
    other = [g for g, w in zip(seen, want) if g[0] == w[0] and not w[1] and "艦隊" not in g[1] and g[1]]
    bad = [f"{k}: {g} != {w}" for k, (g, w) in enumerate(zip(seen, want)) if g != w and g not in other]
    bad += [f"{len(seen)} admirals listed"] if len(seen) != len(want) else []
    ck.report("admirals", len(want), bad, " (日本 0-29, id order): 姓名 指揮艦隊（艦隊 +0）"
              f"; other commands not checked: {other}")
    gens = rom.generals(ck.img("generals"))
    names = list(dict.fromkeys(a[0] for f, a in ck.calls("generals") if f == GENERAL_ROW))
    want = [g["name"] for g in gens[:15]]
    bad = [f"{k}: {g} != {w}" for k, (g, w) in enumerate(zip(names, want)) if g != w]
    bad += [f"{len(names)} generals listed"] if len(names) != len(want) else []
    ck.report("generals", len(want), bad, " (日本 0-14, id order): 姓名")


def main() -> None:
    ap = argparse.ArgumentParser(description="資料表欄位與遊戲畫面比對")
    ap.add_argument("--rom", default=R.DEFAULT_ROM)
    ap.add_argument("--dump", help="write each run's printf trace and WRAM here")
    ap.add_argument("--load", help="check a --dump directory instead of running the game")
    args = ap.parse_args()
    t0 = time.time()
    rom = R.Rom(args.rom)
    res = load(rom, args.load, list(RUNS)) if args.load else collect(rom, list(RUNS))
    if args.dump:
        dump(res, args.dump)
    ck = Checker(rom, res)
    for f in (check_ships, check_classes, check_weapons, check_nation, check_lists, check_personnel):
        f(ck)
    print(f"({time.time() - t0:.0f} s)")
    print("ALL OK" if not ck.errors else f"{ck.errors} problem(s)")
    raise SystemExit(1 if ck.errors else 0)


if __name__ == "__main__":
    main()
