#!/usr/bin/env python3
"""Check a europe-sfc kaodata dataset against the ROM decoding.

1. Every character and portrait rendered with the reference renderer (tools/kaodata.py, spec §6) must equal
   rom.Rom.face_rgb (character id n -> portrait n), which verify_persons.py checks against the game's VRAM and CGRAM.
2. Portraits carry no "code" and no "label" (the game has no face code).
3. checksums.json must equal the checksums recomputed from the dataset.

Usage: .venv/bin/python europe/verify_kaodata_export.py --dataset <dir> [--rom ROM]
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import kaodata
from rom import DEFAULT_ROM, FACE_COUNT, Rom


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證 kaodata 資料集 europe-sfc")
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    meta, blobs = kaodata.load_dataset(args.dataset)
    colors = meta["palettes"][0]["colors"]

    def rgba(face: dict) -> bytes:
        return kaodata.to_rgba(kaodata.compose_display(meta, blobs, face), colors)

    def want(n: int) -> bytes:
        return b"".join(bytes(c) + b"\xff" for c in rom.face_rgb(n))

    persons = {p["id"]: p["name"] for p in rom.persons()}
    bad_ch = [c["id"] for c in meta["characters"]
              if rgba(c["face"]) != want(c["id"]) or persons.get(c["id"]) != c["name"]]
    bad_ch += sorted(set(persons) - {c["id"] for c in meta["characters"]})
    bad_pt = [n for n in range(len(meta["portraits"])) if rgba({"portrait": n}) != want(n)]
    if len(meta["portraits"]) != FACE_COUNT:
        bad_pt.append(f"count {len(meta['portraits'])}")
    n_ch, n_pt = len(meta["characters"]), len(meta["portraits"])
    print(f"[render] characters {n_ch - len(bad_ch)}/{n_ch}, portraits {n_pt - len(bad_pt)}/{n_pt} match the ROM"
          + (f" (NG {bad_ch[:10]} {bad_pt[:10]})" if bad_ch or bad_pt else ""))
    bad_code = [n for n, p in enumerate(meta["portraits"]) if "code" in p or "label" in p]
    print(f"[codes] portraits without code / label: {'OK' if not bad_code else f'NG {bad_code[:10]}'}")
    with open(os.path.join(args.dataset, "checksums.json"), encoding="utf-8") as f:
        sums_ok = json.load(f) == kaodata.checksums(meta, blobs)
    print("[checksums] " + ("OK" if sums_ok else "NG"))
    errors = len(bad_ch) + len(bad_pt) + len(bad_code) + (not sums_ok)
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
