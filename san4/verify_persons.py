#!/usr/bin/env python3
"""Check the person table (rom.Rom.persons) against an external stats table.

The external table is "ROTK - Character Stats & Abilities.csv" of the kaodata-re project (columns
"S04 統率/武力/知力/政治/魅力" = 三國志IV). Persons are matched by name (the table's 日文 column, with
the ROM's user-area characters mapped by rom.EXT_CHARS); every matched person's 5 stats must agree
(with one of the rows of that name: two 馬忠).
This checks the decoding of names and stats against data compiled independently of this ROM.

Usage: .venv/bin/python san4/verify_persons.py [--ext CSV] [--rom ROM]
"""
import argparse
import csv
import os
import unicodedata

from rom import DEFAULT_ROM, STATS, Rom

EXT = os.path.expanduser("~/works/kaodata-re/MISC_TABLE/ROTK - Character Stats & Abilities.csv")


def norm(s: str) -> str:
    return unicodedata.normalize("NFKC", s).replace("髙", "高")


def main() -> None:
    ap = argparse.ArgumentParser(description="人物表與外部資料比對")
    ap.add_argument("--ext", default=EXT)
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    with open(args.ext, encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))
    head = [h.replace("\n", " ") for h in rows[0]]
    cols = [head.index(f"S04 {s}") for s in STATS]
    ext = {}
    for r in rows[1:]:
        if r[cols[0]]:
            for name in {r[0], r[2]}:
                ext.setdefault(norm(name), []).append([int(r[c]) for c in cols])
    persons = rom.persons()
    matched = [p for p in persons if norm(p["name"]) in ext]
    bad = [p["name"] for p in matched if [p[s] for s in STATS] not in ext[norm(p["name"])]]
    missing = [p["name"] for p in persons if norm(p["name"]) not in ext]
    print(f"[persons] {len(matched)}/{len(persons)} found by name in the external table, "
          f"{len(matched) - len(bad)}/{len(matched)} with identical 統率 武力 知力 政治 魅力"
          + (f" (NG {bad[:10]})" if bad else ""))
    print(f"[persons] not found ({len(missing)}): {'、'.join(missing[:30])}{' ...' if len(missing) > 30 else ''}")
    print("ALL OK" if not bad else f"{len(bad)} problem(s)")
    raise SystemExit(1 if bad else 0)


if __name__ == "__main__":
    main()
