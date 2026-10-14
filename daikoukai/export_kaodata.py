#!/usr/bin/env python3
"""Export SFC スーパー大航海時代 as a kaodata dataset (koukai-sfc, format kaodata/1).

Pixels are colour numbers 0-15 of the one face palette (FACE_PALETTE, CGRAM BG palette 5).
Characters: the player, 20 mates, 20 admirals (ids 0-40) and 20 girls (ids 41-60; their portrait k + 13 is
推定, taken from the FC version). Portraits 0-52. Composite faces ($7E:858D): one variant per head (4). The
game copies 5 parts of whole 8x8 tiles into the 960-byte face, in the order bottom, top, eyes, nose, mouth, a
later part overwriting earlier tiles; the code picks one of 4 pages per slot. Every item is a 40 x 48 canvas
with the part's tiles opaque and 255 elsewhere, so layering the slots in that order gives the game's face.
The ROM has no readings, so characters carry no `reading`.

Usage: .venv/bin/python daikoukai/export_kaodata.py --out <dir> [--rom ROM]
"""
import argparse
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(REPO, "tools"))
import kaodata
from rom import (
    COMPOSITE_HEADS,
    COMPOSITE_SLOTS,
    DEFAULT_ROM,
    FACE_H,
    FACE_PALETTE,
    FACE_W,
    PORTRAIT_COUNT,
    Rom,
    decode_face_code,
    decode_tile,
    is_composite,
)

CANVAS = (FACE_W * 8, FACE_H * 8)
PAGES = 4


def part_image(first: int, raw: bytes) -> bytes:
    """40 x 48 canvas: the part's tiles (from tile `first`, row-major 5 wide) opaque, the rest transparent."""
    w, h = CANVAS
    out = bytearray([kaodata.TRANSPARENT]) * (w * h)
    for k in range(len(raw) // 32):
        cell = first + k
        cx, cy = cell % FACE_W * 8, cell // FACE_W * 8
        for i, v in enumerate(decode_tile(raw[32 * k:32 * k + 32])):
            out[(cy + i // 8) * w + cx + i % 8] = v
    return bytes(out)


def characters(rom: Rom) -> list[dict]:
    """Everyone with a face: 41 persons (id 0-40), then 20 girls (id 41-60)."""
    out = [{"id": p["id"], "name": p["name"], "role": p["role"], "face_code": p["face"]} for p in rom.persons()]
    out += [{"id": 41 + g["id"], "name": g["name"], "role": "女性", "face_code": g["face"]} for g in rom.girls()]
    return out


def build(rom_path: str) -> tuple[dict, list[bytes]]:
    rom = Rom(rom_path)
    images, blob = [], bytearray()

    def add(px: bytes) -> int:
        w, h = CANVAS
        assert len(px) == w * h
        images.append([len(blob), w, h])
        blob.extend(px)
        return len(images) - 1

    variants = []
    for head in range(COMPOSITE_HEADS):
        parts = {slot: {"items": [add(part_image(*rom.composite_part(head, slot, page))) for page in range(PAGES)]}
                 for slot, _, _ in COMPOSITE_SLOTS}
        variants.append({"id": str(head), "label": f"頭型 {head}", "parts": parts})

    portraits = [{"img": add(rom.face_pixels(n)), "code": f"{n:04X}"} for n in range(PORTRAIT_COUNT)]

    chars = []
    for c in characters(rom):
        code = c["face_code"]
        ch = {"id": c["id"], "name": c["name"]}
        if is_composite(code):
            head, pages = decode_face_code(code)
            ch["face"] = {"variant": head, "parts": pages, "code": f"{code:04X}"}
        else:
            ch["face"] = {"portrait": code}
        chars.append(ch)

    colors = [f"#{r:02x}{g:02x}{b:02x}" for r, g, b in rom.palette(FACE_PALETTE)]
    meta = {
        "format": kaodata.FORMAT,
        "id": "koukai-sfc",
        "game": "KOUKAI",
        "platform": "SFC",
        "title": {"ja": "スーパー大航海時代", "zh": "超級大航海時代"},
        "source": {"producer": "superfamicom-re", "revision": kaodata.revision(REPO),
                   "inputs": [{"path": os.path.basename(rom_path), "sha1": hashlib.sha1(rom.data).hexdigest()}]},
        "display": {"scale": 6},
        "palettes": [{"id": "face", "label": "頭像調色盤（CGRAM BG 5）", "colors": colors}],
        "blobs": ["pixels.bin"],
        "images": images,
        "composite": {
            "canvas": list(CANVAS),
            "slots": [{"id": sid, "label": label} for sid, label, _ in COMPOSITE_SLOTS],
            "variants": variants,
            "code": {"kind": "tuple"},
        },
        "portraits": portraits,
        "characters": chars,
    }
    return meta, [bytes(blob)]


def main() -> None:
    ap = argparse.ArgumentParser(description="匯出 kaodata 統一格式資料集 koukai-sfc")
    ap.add_argument("--rom", default=DEFAULT_ROM, help="roms/Super Daikoukai Jidai (Japan).zip 或 .sfc")
    ap.add_argument("--out", required=True, help="輸出目錄")
    args = ap.parse_args()
    meta, blobs = build(args.rom)
    kaodata.write_dataset(args.out, meta, blobs)
    chars = meta["characters"]
    mobs = [c for c in chars if "variant" in c["face"]]
    print(f"koukai-sfc: {len(chars)} characters ({len(chars) - len(mobs)} portrait, {len(mobs)} composite), "
          f"{len(meta['composite']['variants'])} variants, {len(meta['portraits'])} portraits, "
          f"{len(meta['images'])} images")
    for name in [*meta["blobs"], "dataset.json", "checksums.json"]:
        print(f"  {name}: {os.path.getsize(os.path.join(args.out, name))} B")


if __name__ == "__main__":
    main()
