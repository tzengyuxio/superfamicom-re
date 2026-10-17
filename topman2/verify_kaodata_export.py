#!/usr/bin/env python3
"""Check a topman2-sfc kaodata dataset against the ROM decoding.

1. Every portrait rendered with the reference renderer (tools/kaodata.py, spec §6) must equal rom.Rom.face_rgb
   of its frame (the decoding verify_faces.py checks against VRAM and CGRAM); the palette = FACEPAL.
2. Every portrait has the group of its face file (会長 / 社長 / 秘書 / 部長) and the name export_kaodata gives it.
3. No portrait has "label" or "code".
4. checksums.json must equal the checksums recomputed from the dataset.

Usage: .venv/bin/python topman2/verify_kaodata_export.py --dataset <dir> [--rom ROM]
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import kaodata
from export_kaodata import portrait_name
from rom import DEFAULT_ROM, Rom, bgr555_rgb


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證 kaodata 資料集 topman2-sfc")
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    meta, blobs = kaodata.load_dataset(args.dataset)
    colors = meta["palettes"][0]["colors"]
    faces = rom.faces()
    pal_ok = colors == [f"#{r:02x}{g:02x}{b:02x}" for r, g, b in (bgr555_rgb(c) for c in rom.face_palette())]
    print("[palette] FACEPAL: " + ("OK" if pal_ok else "NG"))
    bad = []
    for n, f in enumerate(faces):
        got = kaodata.to_rgba(kaodata.compose_display(meta, blobs, {"portrait": n}), colors)
        want = b"".join(bytes(c) + b"\xff" for row in rom.face_rgb(f["file"], f["frame"]) for c in row)
        if got != want:
            bad.append(n)
    n_pt = len(meta["portraits"])
    ok_count = n_pt == len(faces)
    print(f"[render] portraits {n_pt - len(bad)}/{n_pt} match the ROM" + (f" (NG {bad[:10]})" if bad else "")
          + ("" if ok_count else f"; ROM has {len(faces)}"))
    bad_name = [n for n, (p, f) in enumerate(zip(meta["portraits"], faces))
                if p.get("group") != f["group"] or p.get("name") != portrait_name(f)]
    groups = {g: sum(p["group"] == g for p in meta["portraits"]) for g in dict.fromkeys(f["group"] for f in faces)}
    print(f"[groups] portraits {n_pt - len(bad_name)}/{n_pt}: group and name = face file "
          + " ".join(f"{g} {n}" for g, n in groups.items()) + (f" (NG {bad_name[:10]})" if bad_name else ""))
    bad_keys = [n for n, p in enumerate(meta["portraits"]) if "label" in p or "code" in p]
    print(f"[keys] portraits without label / code: {n_pt - len(bad_keys)}/{n_pt}")
    with open(os.path.join(args.dataset, "checksums.json"), encoding="utf-8") as f:
        sums_ok = json.load(f) == kaodata.checksums(meta, blobs)
    print("[checksums] " + ("OK" if sums_ok else "NG"))
    errors = len(bad) + len(bad_name) + len(bad_keys) + (not sums_ok) + (not ok_count) + (not pal_ok)
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
