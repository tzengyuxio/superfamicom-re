#!/usr/bin/env python3
"""Check the product record fields against the game's product sheet (scenario 1, JVD / VECTOR, first turn).

From the main screen the sheet of format 0 slot 0 (HITASHI's "hit 1bas", WRAM $4E19) is opened; every formatted
print of bank $04 (services 3C / 43 / 4F / 55 / 61, lc.PRT_LUA) is collected. Each run patches one field of that
record in WRAM at the savestate and checks what the sheet prints:

  +0x0E grade 0-7      -> the grade name (rom.Rom.grades, $0C:E03C)
  +0x10 maker 0-11     -> the maker name (rom.Rom.maker_names, $0C:DFAC)
  +0x11 contract 0-2   -> the contract label 'original' / 'license' / 'oem'
  +0x27 認知度, +0x21 新鮮度, +0x25 稼働率 (LE16) -> the printed number

Usage: .venv/bin/python leading/verify_products.py [--rom ROM]
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "tools"))
sys.path.insert(0, HERE)
import lc
from replay import end_frame, replay
from rom import DEFAULT_ROM, WRAM_PRODUCT, Rom

# the last 16 prints of the sheet, in order
SHEET = ["maker", "contract", "grade", "price", "認知度", "営業員", "製造員", "新鮮度", "研究員", "技術力", "稼働率",
         "材料費", "製造費", "合理化", "費用", "利益"]
CONTRACT = ["original", "license", "oem"]
NUMBERS = {0x27: ("認知度", 77), 0x21: ("新鮮度", 66), 0x25: ("稼働率", 55)}


def sheet(raw: bytes) -> dict:
    ps = lc.prints(lc.parse(raw))[-len(SHEET):]
    out = {}
    for k, p in zip(SHEET, ps):
        out[k] = p["s1"] if k in ("maker", "grade") else p["fmt"].strip().lower() if k == "contract" else p["args"][0]
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證產品記錄欄位（產品詳細畫面）")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    grades, makers = [g["name"] for g in rom.grades()], rom.maker_names()
    p0 = rom.products(0)[0]
    tests = [("base", None, None)]
    tests += [("grade", 0x0E, g) for g in range(len(grades))]
    tests += [("maker", 0x10, m) for m in range(len(makers))]
    tests += [("contract", 0x11, c) for c in range(3)]
    tests += [("number", off, v) for off, (_, v) in NUMBERS.items()]
    shot = end_frame(lc.SHEET_STEPS, 0) + 60
    runs = [{"steps": lc.SHEET_STEPS, "shot": shot, "read": [],
             "wram": [] if off is None else [(WRAM_PRODUCT + off, v.to_bytes(2 if kind == "number" else 1, "little"))]}
            for kind, off, v in tests]
    res = replay(args.rom, lc.MAIN, end_frame(lc.MAIN), runs,
                 extra_lua=lc.COLLECT_LUA + "function PRT_FILTER(f) return (f >> 16) == 4 end" + lc.PRT_LUA)
    ok = {"grade": 0, "maker": 0, "contract": 0, "number": 0}
    total = {k: 0 for k in ok}
    errors = 0
    base = sheet(res[0][-1])
    want_base = {"maker": makers[p0["maker"]], "contract": CONTRACT[p0["contract"]], "grade": grades[p0["grade"]],
                 "認知度": p0["awareness"]}
    base_ok = all(base[k] == v for k, v in want_base.items())
    print(f"[base] hit 1bas: {base}")
    print("[base] maker / contract / grade / 認知度 = ROM record: " + ("OK" if base_ok else "NG"))
    errors += not base_ok
    for (kind, off, v), r in zip(tests[1:], res[1:]):
        got = sheet(r[-1])
        if kind == "grade":
            good = got["grade"] == grades[v]
        elif kind == "maker":
            good = got["maker"] == makers[v]
        elif kind == "contract":
            good = got["contract"] == CONTRACT[v]
        else:
            good = got[NUMBERS[off][0]] == v
        total[kind] += 1
        ok[kind] += good
        if not good:
            print(f"  NG {kind} +{off:#04x}={v}: {got}")
    for k, n in total.items():
        print(f"[{k}] {ok[k]}/{n}")
        errors += n - ok[k]
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
