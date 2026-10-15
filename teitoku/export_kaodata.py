#!/usr/bin/env python3
"""Export SFC 提督の決断 as a kaodata dataset (tk-sfc, format kaodata/1).

54 faces of 40x48 (LZ entries 0-53), each with its own 16-colour palette (Rom.face_palette: 23 + 18 different
palettes of the two pools at FACE_PALETTES). A byte pixel cannot index that many palettes, so the dataset palette
is the list of distinct colours of all faces (first use order) and each pixel is an index into it. The 40 admirals are the
characters (admiral i -> face Rom.admiral_face(i)); the other 14 faces are portraits with a group by uniform
(rom.OTHER_FACES). The game selects faces by (side, index) arguments of $0A:B2A9, not by one face code, so the
portraits carry no "code". Readings of the admirals' names are not in the ROM, so characters have none.

Usage: .venv/bin/python teitoku/export_kaodata.py --out <dir> [--rom ROM]
"""
import argparse
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "tools"))
import kaodata
from rom import ADMIRAL_COUNT, DEFAULT_ROM, FACE_COUNT, FACE_H, FACE_W, OTHER_FACES, Rom


def colours(rom: Rom) -> list[tuple[int, int, int]]:
    """Distinct colours of all faces, in order of first use."""
    out = []
    for n in range(FACE_COUNT):
        for c in rom.face_rgb(n):
            if c not in out:
                out.append(c)
    return out


def build(rom_path: str) -> tuple[dict, list[bytes]]:
    rom = Rom(rom_path)
    cols = colours(rom)
    assert len(cols) <= 255, len(cols)
    index = {c: i for i, c in enumerate(cols)}
    images, pixels, portraits = [], bytearray(), []
    for n in range(FACE_COUNT):
        images.append([len(pixels), FACE_W * 8, FACE_H * 8])
        pixels.extend(index[c] for c in rom.face_rgb(n))
        portraits.append({"img": n, **({"group": OTHER_FACES[n]} if n in OTHER_FACES else {})})
    characters = [{"id": a["id"], "name": a["name"].replace(" ", ""), "face": {"portrait": a["face"]}}
                  for a in rom.admirals()[:ADMIRAL_COUNT]]
    meta = {
        "format": kaodata.FORMAT,
        "id": "tk-sfc",
        "game": "TK",
        "platform": "SFC",
        "title": {"ja": "提督の決断", "zh": "提督之決斷"},
        "source": {"producer": "superfamicom-re", "revision": kaodata.revision(REPO),
                   "inputs": [{"path": os.path.basename(rom_path), "sha1": hashlib.sha1(rom.data).hexdigest()}]},
        "display": {"scale": 6},
        "palettes": [{"id": "face", "label": f"全部頭像用到的顏色（{len(cols)} 色，取自各頭像自己的調色盤）",
                      "colors": [f"#{r:02x}{g:02x}{b:02x}" for r, g, b in cols]}],
        "blobs": ["pixels.bin"],
        "images": images,
        "portraits": portraits,
        "characters": characters,
    }
    return meta, [bytes(pixels)]


def main() -> None:
    ap = argparse.ArgumentParser(description="匯出 kaodata 統一格式資料集 tk-sfc")
    ap.add_argument("--rom", default=DEFAULT_ROM, help="roms/Teitoku no Ketsudan (Japan).zip 或 .sfc")
    ap.add_argument("--out", required=True, help="輸出目錄")
    args = ap.parse_args()
    meta, blobs = build(args.rom)
    kaodata.write_dataset(args.out, meta, blobs)
    print(f"tk-sfc: {len(meta['characters'])} characters, {len(meta['portraits'])} portraits, "
          f"{len(meta['images'])} images, {len(meta['palettes'][0]['colors'])} colours")
    for name in [*meta["blobs"], "dataset.json", "checksums.json"]:
        print(f"  {name}: {os.path.getsize(os.path.join(args.out, name))} B")


if __name__ == "__main__":
    main()
