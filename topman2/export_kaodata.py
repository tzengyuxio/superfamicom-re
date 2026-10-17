#!/usr/bin/env python3
"""Export SFC トップマネジメントII as a kaodata dataset (topman2-sfc, format kaodata/1).

The game has no named characters: its 96 face frames are the chairmen (KAICHO, 3 persons x 4 expressions), the
3 presidents (SHACHO, one per company), the secretaries (HISHO) and the 8 department heads (3 persons x 3
expressions each); see rom.FACE_FILES. All frames use the one 16-colour palette FACEPAL, so pixels are colour
numbers 0-15. Every frame is its own portrait (in file order, as rom.Rom.faces lists them and verify_faces.py
checks them against VRAM) with the group 会長 / 社長 / 秘書 / 部長 and the name "<role> <person>", like the PC-98
dataset topman2-pc98 ("秘書 1", ...; the department heads keep their department where it is known, e.g.
"開発部長 1"). Frames are not face codes, so the portraits carry no "code".

Usage: .venv/bin/python topman2/export_kaodata.py --out <dir> [--rom ROM]
"""
import argparse
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "tools"))
import kaodata
from rom import DEFAULT_ROM, FACE_H, FACE_W, Rom, bgr555_rgb

CANVAS = (FACE_W * 8, FACE_H * 8)


def portrait_name(f: dict) -> str:
    return f["label"] if f["file"] == "SHACHO" else f"{f['label']} {f['person'] + 1}"


def build(rom_path: str) -> tuple[dict, list[bytes]]:
    rom = Rom(rom_path)
    images, blob, portraits = [], bytearray(), []
    for f in rom.faces():
        px = bytes(v for row in rom.face_pixels(f["file"], f["frame"]) for v in row)
        assert len(px) == CANVAS[0] * CANVAS[1]
        images.append([len(blob), *CANVAS])
        blob.extend(px)
        portraits.append({"img": len(images) - 1, "group": f["group"], "name": portrait_name(f)})
    colors = [f"#{r:02x}{g:02x}{b:02x}" for r, g, b in (bgr555_rgb(c) for c in rom.face_palette())]
    meta = {
        "format": kaodata.FORMAT,
        "id": "topman2-sfc",
        "game": "TOPMAN2",
        "platform": "SFC",
        "title": {"ja": "トップマネジメントII", "zh": "頂尖經營者II"},  # zh: 超任終極聖經
        "source": {"producer": "superfamicom-re", "revision": kaodata.revision(REPO),
                   "inputs": [{"path": os.path.basename(rom_path), "sha1": hashlib.sha1(rom.data).hexdigest()}]},
        "display": {"scale": 6},
        "palettes": [{"id": "face", "label": "FACEPAL", "colors": colors}],
        "blobs": ["pixels.bin"],
        "images": images,
        "portraits": portraits,
        "characters": [],
    }
    return meta, [bytes(blob)]


def main() -> None:
    ap = argparse.ArgumentParser(description="匯出 kaodata 統一格式資料集 topman2-sfc")
    ap.add_argument("--rom", default=DEFAULT_ROM, help="roms/Top Management II (Japan).zip 或 .sfc")
    ap.add_argument("--out", required=True, help="輸出目錄")
    args = ap.parse_args()
    meta, blobs = build(args.rom)
    kaodata.write_dataset(args.out, meta, blobs)
    print(f"topman2-sfc: {len(meta['portraits'])} portraits, {len(meta['images'])} images, "
          f"{len(meta['characters'])} characters")
    for name in [*meta["blobs"], "dataset.json", "checksums.json"]:
        print(f"  {name}: {os.path.getsize(os.path.join(args.out, name))} B")


if __name__ == "__main__":
    main()
