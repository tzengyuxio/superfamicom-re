#!/usr/bin/env python3
"""Check a winning-sfc kaodata dataset against the ROM decoding.

1. Every portrait rendered with the reference renderer (tools/kaodata.py, spec §6) must equal rom.Rom.face_rgb
   of its code (the decoding verify_faces.py checks against VRAM and CGRAM), and carry that code;
2. every composed face of the 8 types x 4^4 part combinations, rendered through the dataset's composite, must
   equal rom.Rom.face_rgb of the game code (type << 12 | parts at bits 1-0, 3-2, 5-4, 9-8 | 0x8000);
3. every character's face must render as rom.Rom.face_rgb of the trainer / jockey / owner record's face code,
   and its name must be the record's name;
4. checksums.json must equal the checksums recomputed from the dataset.

Usage: .venv/bin/python winning/verify_kaodata_export.py --dataset <dir> [--rom ROM]
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import kaodata
from export_kaodata import characters
from rom import DEFAULT_ROM, PORTRAIT_COUNT, Rom


def rgba(rom: Rom, code: int) -> bytes:
    return b"".join(bytes(c) + b"\xff" for row in rom.face_rgb(code) for c in row)


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證 kaodata 資料集 winning-sfc")
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    meta, blobs = kaodata.load_dataset(args.dataset)
    colors = meta["palettes"][0]["colors"]
    errors = 0

    bad = [n for n in range(PORTRAIT_COUNT)
           if kaodata.to_rgba(kaodata.compose_display(meta, blobs, {"portrait": n}), colors) != rgba(rom, n)
           or meta["portraits"][n].get("code") != f"{n:02X}"]
    n_pt = len(meta["portraits"])
    print(f"[portraits] {PORTRAIT_COUNT - len(bad)}/{PORTRAIT_COUNT} = ROM, with their code"
          + (f" (NG {bad[:10]})" if bad else "") + ("" if n_pt == PORTRAIT_COUNT else f"; dataset has {n_pt}"))
    errors += len(bad) + (n_pt != PORTRAIT_COUNT)

    combos = [(t, (a, b, c, d)) for t in range(8) for a in range(4) for b in range(4) for c in range(4)
              for d in range(4)]
    bad = []
    for t, p in combos:
        code = 0x8000 | t << 12 | p[0] | p[1] << 2 | p[2] << 4 | p[3] << 8
        face = {"variant": t, "parts": list(p)}
        if kaodata.to_rgba(kaodata.compose_display(meta, blobs, face), colors) != rgba(rom, code):
            bad.append(f"{code:04X}")
    print(f"[composite] {len(combos) - len(bad)}/{len(combos)} type x part combinations = ROM"
          + (f" (NG {bad[:10]})" if bad else ""))
    errors += len(bad)

    want = {c["id"]: c for c in characters(rom)}
    codes = {1000 + t["index"]: t["face"] for t in rom.trainers()}
    codes.update({(2000 + j["index"] - 20 if j["index"] >= 20 else 2100 + j["index"]): j["face"] for j in rom.jockeys()})
    codes.update({3000 + o["index"]: o["face"] for o in rom.owners()[:40]})
    bad = [c["id"] for c in meta["characters"]
           if c["id"] not in want or c["name"] != want[c["id"]]["name"]
           or kaodata.to_rgba(kaodata.compose_display(meta, blobs, c["face"]), colors) != rgba(rom, codes[c["id"]])]
    n_ch = len(meta["characters"])
    print(f"[characters] {n_ch - len(bad)}/{n_ch} name and face = trainer / jockey / owner record"
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
