#!/usr/bin/env python3
"""Check a taikoh-sfc kaodata dataset against the ROM decoding.

1. Every character (name id, face = the name table's face code) and portrait (face code n = LZ entry 81 + n)
   rendered with the reference renderer (tools/kaodata.py, spec §6) must equal rom.Rom.face_pixels, which
   verify_faces.py checks against the game's VRAM. Portrait codes must be their face codes.
2. checksums.json must equal the checksums recomputed from the dataset.

Usage: .venv/bin/python taikou/verify_kaodata_export.py --dataset <dir> [--rom ROM]
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import kaodata
from rom import DEFAULT_ROM, Rom, bgr555_rgb


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證 kaodata 資料集 taikoh-sfc")
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    meta, blobs = kaodata.load_dataset(args.dataset)
    colors = meta["palettes"][0]["colors"]
    pal = [bgr555_rgb(c) for c in rom.face_palette()]
    faces = {n["id"]: n["face"] for n in rom.names()}

    def rgba(face: dict) -> bytes:
        return kaodata.to_rgba(kaodata.compose_display(meta, blobs, face), colors)

    def want(code: int) -> bytes:
        return b"".join(bytes(pal[v]) + b"\xff" for v in rom.face_pixels(code))

    bad_ch = [c["id"] for c in meta["characters"]
              if c["id"] not in faces or rgba(c["face"]) != want(faces[c["id"]])
              or c["face"].get("code", f"{faces[c['id']]:04X}") != f"{faces[c['id']]:04X}"]
    bad_pt = [n for n, p in enumerate(meta["portraits"]) if rgba({"portrait": n}) != want(n) or p["code"] != f"{n:04X}"]
    n_ch, n_pt = len(meta["characters"]), len(meta["portraits"])
    print(f"[render] characters {n_ch - len(bad_ch)}/{n_ch}, portraits {n_pt - len(bad_pt)}/{n_pt} match the ROM"
          + (f" (NG {bad_ch[:10]} {bad_pt[:10]})" if bad_ch or bad_pt else ""))
    with open(os.path.join(args.dataset, "checksums.json"), encoding="utf-8") as f:
        sums_ok = json.load(f) == kaodata.checksums(meta, blobs)
    print("[checksums] " + ("OK" if sums_ok else "NG"))
    errors = len(bad_ch) + len(bad_pt) + (not sums_ok)
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
