#!/usr/bin/env python3
"""Check a tk-sfc kaodata dataset against the ROM decoding.

1. Every portrait rendered with the reference renderer (tools/kaodata.py, spec §6) must equal rom.Rom.face_rgb
   of the same face (the decoding verify_faces.py checks against VRAM and CGRAM).
2. Every character is an admiral: same name (without the space) and face Rom.admiral_face(id); every face that
   is no admiral's has the group of rom.OTHER_FACES, the admirals' faces have none.
3. No portrait has "label" or "code".
4. checksums.json must equal the checksums recomputed from the dataset.

Usage: .venv/bin/python teitoku/verify_kaodata_export.py --dataset <dir> [--rom ROM]
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import kaodata
from rom import DEFAULT_ROM, FACE_COUNT, OTHER_FACES, Rom


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證 kaodata 資料集 tk-sfc")
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    meta, blobs = kaodata.load_dataset(args.dataset)
    colors = meta["palettes"][0]["colors"]
    n_pt = len(meta["portraits"])
    bad = []
    for n in range(FACE_COUNT):
        got = kaodata.to_rgba(kaodata.compose_display(meta, blobs, {"portrait": n}), colors) if n < n_pt else b""
        if got != b"".join(bytes(c) + b"\xff" for c in rom.face_rgb(n)):
            bad.append(n)
    print(f"[render] portraits {FACE_COUNT - len(bad)}/{FACE_COUNT} match the ROM" + (f" (NG {bad[:10]})" if bad else "")
          + ("" if n_pt == FACE_COUNT else f"; dataset has {n_pt}"))
    adm = rom.admirals()
    chars = meta["characters"]
    bad_ch = [a["id"] for a, c in zip(adm, chars)
              if (c["id"], c["name"], c["face"]) != (a["id"], a["name"].replace(" ", ""), {"portrait": a["face"]})]
    bad_ch += ["count"] * (len(chars) != len(adm))
    print(f"[characters] {len(chars) - len(bad_ch)}/{len(adm)} admirals with name and face"
          + (f" (NG {bad_ch[:10]})" if bad_ch else ""))
    bad_group = [n for n, p in enumerate(meta["portraits"]) if p.get("group") != OTHER_FACES.get(n)]
    print(f"[groups] portraits {n_pt - len(bad_group)}/{n_pt}: group only on the {len(OTHER_FACES)} non-admiral faces"
          + (f" (NG {bad_group[:10]})" if bad_group else ""))
    bad_keys = [n for n, p in enumerate(meta["portraits"]) if "label" in p or "code" in p]
    print(f"[keys] portraits without label / code: {n_pt - len(bad_keys)}/{n_pt}")
    with open(os.path.join(args.dataset, "checksums.json"), encoding="utf-8") as f:
        sums_ok = json.load(f) == kaodata.checksums(meta, blobs)
    print("[checksums] " + ("OK" if sums_ok else "NG"))
    errors = len(bad) + len(bad_ch) + len(bad_group) + len(bad_keys) + (not sums_ok) + (n_pt != FACE_COUNT)
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
