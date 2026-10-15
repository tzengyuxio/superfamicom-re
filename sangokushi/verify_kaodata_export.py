#!/usr/bin/env python3
"""Check a san1-sfc kaodata dataset against the ROM decoding.

1. Every character and portrait rendered with the reference renderer (tools/kaodata.py, spec §6) must equal
   rom.Rom.face_pixels of its face code (checked against the game's VRAM by verify_faces.py), coloured with
   the face palette (FACE_PALETTE, checked against CGRAM by verify_faces.py).
2. Every character's composite code / portrait code must be the face code of its name table entry.
3. checksums.json must equal the checksums recomputed from the dataset.

Usage: .venv/bin/python sangokushi/verify_kaodata_export.py --dataset <dir> [--rom ROM]
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
    ap = argparse.ArgumentParser(description="驗證 kaodata 資料集 san1-sfc")
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    meta, blobs = kaodata.load_dataset(args.dataset)
    colors = meta["palettes"][0]["colors"]
    pal = [bytes(bgr555_rgb(c)) + b"\xff" for c in rom.face_palette()]
    pal_ok = colors == [f"#{c[:3].hex()}" for c in pal]

    def rgba(face: dict) -> bytes:
        return kaodata.to_rgba(kaodata.compose_display(meta, blobs, face), colors)

    def want(code: int) -> bytes:
        return b"".join(pal[v] for v in rom.face_pixels(code))

    faces = {n["id"]: n["face"] for n in rom.names()}
    bad_ch = [c["id"] for c in meta["characters"] if rgba(c["face"]) != want(faces[c["id"]])]
    bad_code = [c["id"] for c in meta["characters"]
                if int(c["face"].get("code", f"{c['face'].get('portrait', -1):X}"), 16) != faces[c["id"]]]
    bad_pt = [n for n, p in enumerate(meta["portraits"]) if rgba({"portrait": n}) != want(int(p["code"], 16))]
    n_ch, n_pt = len(meta["characters"]), len(meta["portraits"])
    print(f"[render] characters {n_ch - len(bad_ch)}/{n_ch}, portraits {n_pt - len(bad_pt)}/{n_pt} match the ROM"
          + (f" (NG {bad_ch[:10]} {bad_pt[:10]})" if bad_ch or bad_pt else ""))
    print(f"[codes] {n_ch - len(bad_code)}/{n_ch} characters carry their name table face code; palette "
          + ("OK" if pal_ok else "NG"))
    with open(os.path.join(args.dataset, "checksums.json"), encoding="utf-8") as f:
        sums_ok = json.load(f) == kaodata.checksums(meta, blobs)
    print("[checksums] " + ("OK" if sums_ok else "NG"))
    errors = len(bad_ch) + len(bad_pt) + len(bad_code) + (not sums_ok) + (not pal_ok)
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
