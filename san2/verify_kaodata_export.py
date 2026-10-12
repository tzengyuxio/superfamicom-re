#!/usr/bin/env python3
"""Independent checks for the san2-sfc kaodata dataset.

1. Every character and portrait drawn by the spec renderer from the dataset equals the face
   composed directly from ROM tiles (rom.Rom.face_pixels + palette), pixel by pixel.
2. checksums.json matches a recomputation.
3. (needs Mesen 2, see tools/mesen.py) The game draws every face code used by a person (352) in
   the emulator; the screen equals the dataset's RGB, pixel by pixel (about 2 minutes).

Usage: .venv/bin/python san2/verify_kaodata_export.py --dataset <dir> [--rom ROM] [--no-emulator]
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import kaodata
from rom import DEFAULT_ROM, PORTRAIT_COUNT, Rom


def expected(rom: Rom, code: int) -> bytes:
    pal = rom.face_palette_number(code)
    return bytes(pal * 16 + v for v in rom.face_pixels(code))


def check_pixels(rom: Rom, meta: dict, blobs: list[bytes]) -> int:
    codes = {p["id"]: p["face"] for p in rom.persons()}
    faces = [(f"ch:{c['id']} {c['name']}", c["face"], codes[c["id"]]) for c in meta["characters"]]
    faces += [(f"pt:{n}", {"portrait": n}, n + 1) for n in range(PORTRAIT_COUNT)]
    errors = 0
    for label, face, code in faces:
        w, h, px = kaodata.compose_display(meta, blobs, face)
        if (w, h) != (40, 48) or px != expected(rom, code):
            print(f"  NG {label}")
            errors += 1
    print(f"[pixels] {len(faces) - errors}/{len(faces)} faces match the ROM tile composition")
    return errors


def check_checksums(meta: dict, blobs: list[bytes], path: str) -> int:
    with open(path, encoding="utf-8") as f:
        stored = json.load(f)
    ok = stored == kaodata.checksums(meta, blobs)
    print(f"[checksums] {'OK' if ok else 'MISMATCH'} ({len(stored['entries'])} entries)")
    return 0 if ok else 1


def check_emulated(rom_path: str, meta: dict, blobs: list[bytes]) -> int:
    from mesen import CORE
    if not os.path.exists(CORE):
        print(f"[emulator] skipped ({CORE} not found)")
        return 0
    from tools.face_capture import capture_faces
    colors = [tuple(bytes.fromhex(c[1:])) for c in meta["palettes"][0]["colors"]]
    faces = {}
    for c in meta["characters"]:
        code = int(c["face"]["code"], 16) if "variant" in c["face"] else c["face"]["portrait"] + 1
        faces.setdefault(code, c["face"])
    shown = capture_faces(rom_path, sorted(faces))
    bad = [f"{code:04X}" for code, face in faces.items()
           if [colors[v] for v in kaodata.compose_display(meta, blobs, face)[2]] != shown.get(code)]
    print(f"[emulator] game screen: {len(faces) - len(bad)}/{len(faces)} face codes match"
          + (f" (NG {' '.join(bad[:10])})" if bad else ""))
    return len(bad)


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證 san2-sfc kaodata 資料集")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--no-emulator", action="store_true", help="略過模擬器比對")
    args = ap.parse_args()
    rom = Rom(args.rom)
    meta, blobs = kaodata.load_dataset(args.dataset)
    errors = check_pixels(rom, meta, blobs)
    errors += check_checksums(meta, blobs, os.path.join(args.dataset, "checksums.json"))
    if not args.no_emulator:
        errors += check_emulated(args.rom, meta, blobs)
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
