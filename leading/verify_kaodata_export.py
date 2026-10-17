#!/usr/bin/env python3
"""Check a leading-sfc kaodata dataset against the ROM decoding.

1. Every portrait rendered with the reference renderer (tools/kaodata.py, spec §6) must equal rom.Rom.face_rgb
   (the decoding verify_faces.py checks against VRAM and CGRAM).
2. Portrait n is face n of rom.Rom.faces(); its group is the face kind's (会長, 社長, 秘書, 部長（…）).
3. No portrait has name / label / code; there are no characters.
4. checksums.json must equal the checksums recomputed from the dataset.

Usage: .venv/bin/python leading/verify_kaodata_export.py --dataset <dir> [--rom ROM]
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
    ap = argparse.ArgumentParser(description="驗證 kaodata 資料集 leading-sfc")
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    meta, blobs = kaodata.load_dataset(args.dataset)
    colors = meta["palettes"][0]["colors"]
    faces = rom.faces()
    n_pt = len(meta["portraits"])
    bad = []
    for n, f in enumerate(faces[:n_pt]):
        got = kaodata.to_rgba(kaodata.compose_display(meta, blobs, {"portrait": n}), colors)
        want = b"".join(bytes(c) + b"\xff" for row in rom.face_rgb(f["kind"], f["image"]) for c in row)
        if got != want:
            bad.append(n)
    ok_count = n_pt == len(faces)
    print(f"[render] portraits {n_pt - len(bad)}/{n_pt} match the ROM" + (f" (NG {bad[:10]})" if bad else "")
          + ("" if ok_count else f"; ROM has {len(faces)}"))
    bad_group = [n for n, (p, f) in enumerate(zip(meta["portraits"], faces)) if p.get("group") != f["group"]]
    print(f"[groups] portraits {n_pt - len(bad_group)}/{n_pt}: group = face kind"
          + (f" (NG {bad_group[:10]})" if bad_group else ""))
    bad_keys = [n for n, p in enumerate(meta["portraits"]) if {"name", "label", "code"} & p.keys()]
    print(f"[keys] portraits without name / label / code: {n_pt - len(bad_keys)}/{n_pt}; "
          f"characters {len(meta['characters'])}")
    with open(os.path.join(args.dataset, "checksums.json"), encoding="utf-8") as f:
        sums_ok = json.load(f) == kaodata.checksums(meta, blobs)
    print("[checksums] " + ("OK" if sums_ok else "NG"))
    errors = len(bad) + len(bad_group) + len(bad_keys) + bool(meta["characters"]) + (not sums_ok) + (not ok_count)
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
