#!/usr/bin/env python3
"""Check a tk2-sfc kaodata dataset against the ROM decoding.

1. Every portrait rendered with the reference renderer (tools/kaodata.py, spec §6) must equal Rom.face_rgb of
   the same face (the decoding verify_faces.py checks against VRAM and CGRAM).
2. Every portrait's "code" is its face number (the argument of the face routine), as 4 hex digits.
3. The characters are the 60 admirals (face i) and 30 generals (face 60 + j): same name (without the space) and
   face; the faces of nobody have the group of rom.OTHER_FACES, the others none. No portrait has "label".
4. checksums.json must equal the checksums recomputed from the dataset.

Usage: .venv/bin/python teitoku2/verify_kaodata_export.py --dataset <dir> [--rom ROM]
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
    ap = argparse.ArgumentParser(description="驗證 kaodata 資料集 tk2-sfc")
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    meta, blobs = kaodata.load_dataset(args.dataset)
    colors = meta["palettes"][0]["colors"]
    pts = meta["portraits"]
    bad = [f for f in range(FACE_COUNT) if f >= len(pts) or kaodata.to_rgba(
        kaodata.compose_display(meta, blobs, {"portrait": f}), colors) != b"".join(bytes(c) + b"\xff"
                                                                                  for c in rom.face_rgb(f))]
    print(f"[render] portraits {FACE_COUNT - len(bad)}/{FACE_COUNT} match the ROM" + (f" (NG {bad[:10]})" if bad else "")
          + ("" if len(pts) == FACE_COUNT else f"; dataset has {len(pts)}"))
    bad_code = [f for f, p in enumerate(pts) if p.get("code") != f"{f:04X}"]
    print(f"[codes] {len(pts) - len(bad_code)}/{len(pts)} portraits carry their face number as code"
          + (f" (NG {bad_code[:10]})" if bad_code else ""))
    img = rom.wram_image(0)
    want = [(a["face"], a["name"].replace(" ", "")) for a in rom.admirals(img)]
    want += [(g["face"], g["name"].replace(" ", "")) for g in rom.generals(img)]
    chars = meta["characters"]
    got = [(c["id"], c["name"]) for c in chars]
    bad_ch = [w for w, g, c in zip(want, got, chars) if g != w or c["face"] != {"portrait": w[0]}]
    bad_ch += ["count"] * (len(chars) != len(want))
    print(f"[characters] {len(chars) - len(bad_ch)}/{len(want)} admirals and generals with name and face"
          + (f" (NG {bad_ch[:10]})" if bad_ch else ""))
    bad_group = [f for f, p in enumerate(pts) if p.get("group") != OTHER_FACES.get(f) or "label" in p]
    print(f"[groups] portraits {len(pts) - len(bad_group)}/{len(pts)}: group only on the {len(OTHER_FACES)} faces of "
          "nobody, no label" + (f" (NG {bad_group[:10]})" if bad_group else ""))
    with open(os.path.join(args.dataset, "checksums.json"), encoding="utf-8") as f:
        sums_ok = json.load(f) == kaodata.checksums(meta, blobs)
    print("[checksums] " + ("OK" if sums_ok else "NG"))
    errors = len(bad) + len(bad_code) + len(bad_ch) + len(bad_group) + (not sums_ok) + (len(pts) != FACE_COUNT)
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
