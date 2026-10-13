#!/usr/bin/env python3
"""First look at SFC ROMs: header, mapping, KOEI LZ tables and pointer table, Shift-JIS game words.

Usage: .venv/bin/python tools/triage.py [ROM ...]     # default: every Japanese ROM in roms/
       .venv/bin/python tools/triage.py --all         # every ROM in roms/
Prints a Markdown table.
"""
import argparse
import glob
import os
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from koei_lz import find_pointer_tables, find_tables

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Words most KOEI strategy games show; plenty of Shift-JIS hits means the game text is (at least partly) SJIS
WORDS = ["武将", "兵士", "君主", "大名", "シナリオ", "劇本", "金", "兵糧"]


def load_rom(path: str) -> bytes:
    """ROM bytes from a .zip (first .sfc/.smc inside) or a plain file, copier header dropped."""
    if path.lower().endswith(".zip"):
        with zipfile.ZipFile(path) as z:
            data = z.read(next(n for n in z.namelist() if n.lower().endswith((".sfc", ".smc"))))
    else:
        with open(path, "rb") as f:
            data = f.read()
    return data[len(data) % 0x8000:]


def header(rom: bytes) -> dict:
    """The internal header that passes the checksum-complement test (LoROM 0x7FC0, HiROM 0xFFC0)."""
    best = None
    for base, kind in ((0x7FC0, "LoROM"), (0xFFC0, "HiROM")):
        if base + 0x20 > len(rom):
            continue
        h = rom[base:base + 0x20]
        comp, csum = h[0x1C] | h[0x1D] << 8, h[0x1E] | h[0x1F] << 8
        score = (comp ^ csum == 0xFFFF) * 2 + ((h[0x15] & 0x0F) == (kind == "HiROM"))
        if best is None or score > best[0]:
            best = (score, base, kind, h)
    _, base, kind, h = best
    return {"kind": kind, "title": h[:21].decode("cp932", "replace").rstrip(), "map": h[0x15], "type": h[0x16],
            "sram_kb": (1 << h[0x18]) if h[0x18] else 0, "region": h[0x19]}


def triage(path: str) -> dict:
    rom = load_rom(path)
    h = header(rom)
    t = find_tables(rom)
    lz = ""
    if t >= 0:
        ptrs = find_pointer_tables(rom, t, h["kind"] == "HiROM")
        lz = f"tables {t:#x}" + "".join(f", ptr {at:#x} ×{count}" for at, count in ptrs)
    sjis = sum(rom.count(w.encode("cp932")) for w in WORDS)
    return {"file": os.path.basename(path).removesuffix(".zip"), "size": f"{len(rom) >> 10} KB", **h, "lz": lz,
            "sjis": sjis}


def main() -> None:
    ap = argparse.ArgumentParser(description="SFC ROM 初步分診")
    ap.add_argument("roms", nargs="*")
    ap.add_argument("--all", action="store_true", help="包含非日版")
    args = ap.parse_args()
    paths = args.roms or sorted(p for p in glob.glob(os.path.join(REPO, "roms", "*.zip"))
                                if args.all or "(Japan)" in p or "(Hong Kong)" in p)
    print("| ROM | size | map | title | type | SRAM | KOEI LZ | SJIS words |")
    print("|-----|------|-----|-------|------|------|---------|------------|")
    for p in paths:
        r = triage(p)
        print(f"| {r['file']} | {r['size']} | {r['kind']} {r['map']:02X} | {r['title']} | {r['type']:02X} "
              f"| {r['sram_kb']} KB | {r['lz'] or '—'} | {r['sjis']} |", flush=True)


if __name__ == "__main__":
    main()
