#!/usr/bin/env python3
"""Check an air-sfc kaodata dataset against the ROM decoding.

1. Every portrait rendered with the reference renderer (tools/kaodata.py, spec §6) must equal
   rom.Rom.face_rgb, which verify_faces.py checks against the game's VRAM and CGRAM.
2. Every portrait has its kind as group; only the maker faces have a name.
3. checksums.json must equal the checksums recomputed from the dataset.

Usage: .venv/bin/python airmanage/verify_kaodata_export.py --dataset <dir> [--rom ROM]
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import kaodata
from rom import DEFAULT_ROM, Rom


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證 kaodata 資料集 air-sfc")
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    meta, blobs = kaodata.load_dataset(args.dataset)
    colors = meta["palettes"][0]["colors"]
    faces = rom.faces()
    bad = []
    for n, f in enumerate(faces):
        got = kaodata.to_rgba(kaodata.compose_display(meta, blobs, {"portrait": n}), colors)
        want = b"".join(bytes(c) + b"\xff" for row in rom.face_rgb(f["kind"], f["image"]) for c in row)
        if got != want:
            bad.append(n)
    n_pt = len(meta["portraits"])
    ok_count = n_pt == len(faces)
    print(f"[render] portraits {n_pt - len(bad)}/{n_pt} match the ROM" + (f" (NG {bad[:10]})" if bad else "")
          + ("" if ok_count else f"; ROM has {len(faces)}"))
    groups = {"MANAGER": "部下", "PERSON": "交涉對象", "MAKER": "廠商"}
    makers = {m["face_image"] for m in rom.makers()}
    bad_group = [n for n, (p, f) in enumerate(zip(meta["portraits"], faces))
                 if p.get("group") != groups[f["file"]]
                 or ("name" in p) != (f["file"] == "MAKER" and f["image"] in makers)]
    print(f"[groups] portraits {n_pt - len(bad_group)}/{n_pt}: group = kind, name only on maker faces"
          + (f" (NG {bad_group[:10]})" if bad_group else ""))
    with open(os.path.join(args.dataset, "checksums.json"), encoding="utf-8") as f:
        sums_ok = json.load(f) == kaodata.checksums(meta, blobs)
    print("[checksums] " + ("OK" if sums_ok else "NG"))
    errors = len(bad) + len(bad_group) + (not sums_ok) + (not ok_count)
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
