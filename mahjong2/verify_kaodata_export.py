#!/usr/bin/env python3
"""Check a mahjong2-sfc kaodata dataset against the ROM decoding.

1. Every portrait (26 x 9) rendered with the reference renderer (tools/kaodata.py, spec §6) must equal
   rom.Rom.face_rgb of its opponent and image (the decoding verify_faces.py checks against the game's VRAM and
   CGRAM), with that image's palette ($01:CCB1, or $01:CCCB for the 56x56 image).
2. Every character's face and expressions (with labels) must be its own nine images, in stream order, and its name
   must be the one in data/persons.tsv.
3. checksums.json must equal the checksums recomputed from the dataset (including `ch:<id>/<k>`).

Usage: .venv/bin/python mahjong2/verify_kaodata_export.py --dataset <dir> [--rom ROM]
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import kaodata
from export_kaodata import IMAGES, LABELS
from rom import DEFAULT_ROM, PERSON_COUNT, Rom


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證 kaodata 資料集 mahjong2-sfc")
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    meta, blobs = kaodata.load_dataset(args.dataset)
    colors = meta["palettes"][0]["colors"]

    bad_pt = []
    for n in range(len(meta["portraits"])):
        got = kaodata.to_rgba(kaodata.compose_display(meta, blobs, {"portrait": n}), colors)
        if got != b"".join(bytes(c) + b"\xff" for c in rom.face_rgb(n // IMAGES + 1, n % IMAGES)):
            bad_pt.append(n)
    n_pt, want_pt = len(meta["portraits"]), PERSON_COUNT * IMAGES
    print(f"[render] portraits {n_pt - len(bad_pt)}/{want_pt} match the ROM" + (f" (NG {bad_pt[:10]})" if bad_pt else ""))

    names = {p["id"]: p["name"] for p in rom.persons()}
    bad_ch = [c["id"] for c in meta["characters"]
              if [c["face"]] + c.get("expressions", []) != [{"portrait": IMAGES * (c["id"] - 1) + k, "label": LABELS[k]}
                                                             for k in range(IMAGES)]
              or c["name"] != names[c["id"]]]
    n_ch = len(meta["characters"])
    print(f"[characters] {n_ch - len(bad_ch)}/{PERSON_COUNT}: face + 8 expressions = own images, labels, names"
          + (f" (NG {bad_ch})" if bad_ch else ""))
    with open(os.path.join(args.dataset, "checksums.json"), encoding="utf-8") as f:
        sums = json.load(f)
    sums_ok = sums == kaodata.checksums(meta, blobs)
    print(f"[checksums] {len(sums['entries'])} entries: " + ("OK" if sums_ok else "NG"))
    errors = len(bad_pt) + len(bad_ch) + (not sums_ok) + (n_pt != want_pt) + (n_ch != PERSON_COUNT)
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
