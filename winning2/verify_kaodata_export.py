#!/usr/bin/env python3
"""Check a winning2-sfc kaodata dataset against the ROM decoding.

1. Every portrait rendered with the reference renderer (tools/kaodata.py) must equal rom.Rom.face_rgb of its code
   (the decoding verify_faces.py checks against the game), carry that code and the group of its kind;
2. every character's face must render as rom.Rom.face_rgb of the trainer / jockey / owner / secretary record's face
   code at the start of a game, and its name must be the record's name;
3. checksums.json must equal the checksums recomputed from the dataset.

Usage: .venv/bin/python winning2/verify_kaodata_export.py --dataset <dir> [--rom ROM]
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import kaodata
from rom import DEFAULT_ROM, FACE_KINDS, Rom, face_kind


def rgba(rom: Rom, code: int) -> bytes:
    return b"".join(bytes(c) + b"\xff" for row in rom.face_rgb(code) for c in row)


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證 kaodata 資料集 winning2-sfc")
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    meta, blobs = kaodata.load_dataset(args.dataset)
    colors = meta["palettes"][0]["colors"]
    errors = 0

    n_face = rom.face_count
    bad = [n for n in range(n_face)
           if kaodata.to_rgba(kaodata.compose_display(meta, blobs, {"portrait": n}), colors) != rgba(rom, n)
           or meta["portraits"][n].get("code") != f"{n:02X}"
           or meta["portraits"][n].get("group") != FACE_KINDS[face_kind(n)][3]]
    n_pt = len(meta["portraits"])
    print(f"[portraits] {n_face - len(bad)}/{n_face} = ROM, with their code and group"
          + (f" (NG {bad[:10]})" if bad else "") + ("" if n_pt == n_face else f"; dataset has {n_pt}"))
    errors += len(bad) + (n_pt != n_face)

    want = {}
    for t in rom.trainers():
        want[1000 + t["index"]] = (t["surname"] + t["given"], t["face"])
    for j in rom.jockeys()[:61]:
        want[2000 + j["index"]] = (j["surname"] + j["given"], j["face"])
    for o in rom.owners()[:28]:
        want[3000 + o["index"]] = (o["surname"] + o["given"], o["face"])
    for s in rom.secretaries():
        want[4000 + s["index"]] = (s["surname"] + s["given"], s["face"])
    bad = [c["id"] for c in meta["characters"]
           if c["id"] not in want or c["name"] != want[c["id"]][0]
           or kaodata.to_rgba(kaodata.compose_display(meta, blobs, c["face"]), colors) != rgba(rom, want[c["id"]][1])]
    n_ch = len(meta["characters"])
    print(f"[characters] {n_ch - len(bad)}/{n_ch} name and face = trainer / jockey / owner / secretary record"
          + (f" (NG {bad[:10]})" if bad else "") + ("" if n_ch == len(want) else f"; expected {len(want)}"))
    errors += len(bad) + (n_ch != len(want))

    with open(os.path.join(args.dataset, "checksums.json"), encoding="utf-8") as f:
        sums_ok = json.load(f) == kaodata.checksums(meta, blobs)
    print("[checksums] " + ("OK" if sums_ok else "NG"))
    errors += not sums_ok
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
