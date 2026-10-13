#!/usr/bin/env python3
"""Check a dokuritsu-sfc kaodata dataset against the ROM decoding.

1. Every character and portrait rendered with the reference renderer (tools/kaodata.py, spec §6)
   must equal rom.Rom.face_rgb, which verify_persons.py / verify_faces.py check against the game's VRAM.
2. Portrait "code" and composite "code" must be the face code (4 hex digits).
3. checksums.json must equal the checksums recomputed from the dataset.

Usage: .venv/bin/python dokuritsu/verify_kaodata_export.py --dataset <dir> [--rom ROM]
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
    ap = argparse.ArgumentParser(description="驗證 kaodata 資料集 dokuritsu-sfc")
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    meta, blobs = kaodata.load_dataset(args.dataset)
    colors = meta["palettes"][0]["colors"]

    def rgba(face: dict) -> bytes:
        return kaodata.to_rgba(kaodata.compose_display(meta, blobs, face), colors)

    def want(code: int) -> bytes:
        return b"".join(bytes(c) + b"\xff" for c in rom.face_rgb(code))

    faces = {p["id"]: p["face"] for p in rom.persons()}
    bad_ch = [c["id"] for c in meta["characters"] if rgba(c["face"]) != want(faces[c["id"]])]
    bad_pt = [n for n in range(len(meta["portraits"])) if rgba({"portrait": n}) != want(n)]
    n_ch, n_pt = len(meta["characters"]), len(meta["portraits"])
    print(f"[render] characters {n_ch - len(bad_ch)}/{n_ch}, portraits {n_pt - len(bad_pt)}/{n_pt} match the ROM"
          + (f" (NG {bad_ch[:10]} {bad_pt[:10]})" if bad_ch or bad_pt else ""))
    bad_code = [n for n, p in enumerate(meta["portraits"]) if p.get("code") != f"{n:04X}" or "label" in p]
    bad_code += [c["id"] for c in meta["characters"] if "variant" in c["face"]
                 and c["face"].get("code") != f"{faces[c['id']]:04X}"]
    print(f"[codes] portrait / composite codes: {'OK' if not bad_code else f'NG {bad_code[:10]}'}")
    with open(os.path.join(args.dataset, "checksums.json"), encoding="utf-8") as f:
        sums_ok = json.load(f) == kaodata.checksums(meta, blobs)
    print("[checksums] " + ("OK" if sums_ok else "NG"))
    errors = len(bad_ch) + len(bad_pt) + len(bad_code) + (not sums_ok)
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
