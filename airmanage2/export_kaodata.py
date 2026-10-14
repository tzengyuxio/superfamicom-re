#!/usr/bin/env python3
"""Export SFC エアーマネージメントII 航空王をめざせ as a kaodata dataset (air2-sfc, format kaodata/1).

The game has no named characters: its faces are secretaries (SECRET, 7), staff (STAFF, 11), country
representatives (MAYOR, 5) and aircraft-maker representatives (MAKER, 6 images), so the dataset has portraits
only. FACEPAL has 30 palettes (480 colours), more than a byte pixel can index, so the dataset palette holds only
the 14 FACEPAL palettes the portraits use, in FACEPAL order (used_palettes()); pixels are `slot * 16 + colour`.
The game draws a face from a (kind, image, palette) descriptor: secretaries and staff get a random palette of
their home area's set of 4, country representatives one palette per area, makers a fixed descriptor
($05:EEC7). Each SECRET / STAFF
image is exported once with palette 26 (first of the European set), each MAYOR image with palette 0 (Europe),
and every one of the 12 maker descriptors as its own portrait named after the maker (rom.Rom.faces, checked by
verify_faces.py). Descriptors are not single face codes, so the portraits carry no "code". Each portrait has a
group (its kind, in Chinese) so the face browser lists it.

Usage: .venv/bin/python airmanage2/export_kaodata.py --out <dir> [--rom ROM]
"""
import argparse
import hashlib
import os
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "tools"))
import kaodata
from rom import DEFAULT_ROM, FACE_H, FACE_W, Rom, bgr555_rgb

CANVAS = (FACE_W * 8, FACE_H * 8)
GROUPS = {"SECRET": "秘書", "STAFF": "職員", "MAYOR": "國家代表", "MAKER": "廠商"}


def used_palettes(rom: Rom) -> list[int]:
    """FACEPAL palettes of the exported portraits, ascending."""
    return sorted({f["palette"] for f in rom.faces()})


def build(rom_path: str) -> tuple[dict, list[bytes]]:
    rom = Rom(rom_path)
    images, blob, portraits = [], bytearray(), []
    used = used_palettes(rom)
    for f in rom.faces():
        slot = used.index(f["palette"])
        px = bytes(slot * 16 + v for row in rom.face_pixels(f["kind"], f["image"]) for v in row)
        assert len(px) == CANVAS[0] * CANVAS[1]
        images.append([len(blob), *CANVAS])
        blob.extend(px)
        portrait = {"img": len(images) - 1, "group": GROUPS[f["file"]]}
        if f["file"] == "MAKER":
            # ﾀﾞｸﾞﾗｽ -> ダグラス; the font draws a-z with the A-Z glyphs, so bae is shown as BAE
            portrait["name"] = unicodedata.normalize("NFKC", f["maker_name"]).upper()
        portraits.append(portrait)
    colors = [f"#{r:02x}{g:02x}{b:02x}" for p in used for r, g, b in (bgr555_rgb(c) for c in rom.face_palette(p))]
    meta = {
        "format": kaodata.FORMAT,
        "id": "air2-sfc",
        "game": "AIR2",
        "platform": "SFC",
        "title": {"ja": "エアーマネージメントII 航空王をめざせ", "zh": "航空霸業II"},
        "source": {"producer": "superfamicom-re", "revision": kaodata.revision(REPO),
                   "inputs": [{"path": os.path.basename(rom_path), "sha1": hashlib.sha1(rom.data).hexdigest()}]},
        "display": {"scale": 6},
        "palettes": [{"id": "face", "label": "頭像用到的 FACEPAL 調色盤 " + ",".join(map(str, used))
                      + "（色號＝第幾組 × 16 ＋ 色）", "colors": colors}],
        "blobs": ["pixels.bin"],
        "images": images,
        "portraits": portraits,
        "characters": [],
    }
    return meta, [bytes(blob)]


def main() -> None:
    ap = argparse.ArgumentParser(description="匯出 kaodata 統一格式資料集 air2-sfc")
    ap.add_argument("--rom", default=DEFAULT_ROM, help="roms/Air Management II - Koukuu Ou o Mezase (Japan).zip 或 .sfc")
    ap.add_argument("--out", required=True, help="輸出目錄")
    args = ap.parse_args()
    meta, blobs = build(args.rom)
    kaodata.write_dataset(args.out, meta, blobs)
    print(f"air2-sfc: {len(meta['portraits'])} portraits, {len(meta['images'])} images, "
          f"{len(meta['characters'])} characters")
    for name in [*meta["blobs"], "dataset.json", "checksums.json"]:
        print(f"  {name}: {os.path.getsize(os.path.join(args.out, name))} B")


if __name__ == "__main__":
    main()
