#!/usr/bin/env python3
"""Export SFC スーパー信長の野望・武将風雲録 as a kaodata dataset (bushou-sfc, format kaodata/1).

Pixels are colour numbers 0-15 of the one face palette (ROM 0x174DC, BG palette 5 of the province screen;
verify_faces.py checks it for every face). Composite faces: one variant per head (8). The game copies five
runs of 8x8 cells from the head's 4 pages in the order top, bottom, eyes, nose, mouth (later runs overwrite
earlier ones; runs per head from the table at 0x1793C), so every slot has 4 items: 40x48 canvases with 255
outside the slot's run. Portraits 0-179 are the dedicated faces. The ROM has no readings.

Usage: .venv/bin/python bushou/export_kaodata.py --out <dir> [--rom ROM]
"""
import argparse
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "tools"))
import kaodata
from rom import (
    COMPOSITE_HEADS,
    COMPOSITE_SLOTS,
    DEFAULT_ROM,
    FACE_H,
    FACE_W,
    PORTRAIT_COUNT,
    Rom,
    bgr555_rgb,
    decode_face_code,
    decode_tile,
    is_composite,
)

CANVAS = (FACE_W * 8, FACE_H * 8)
PAGES = 4


def cells_image(face: bytes, cells: list[int]) -> bytes:
    """40x48 image of the given cells of a 960-byte face, other cells transparent."""
    w, h = CANVAS
    out = bytearray([kaodata.TRANSPARENT]) * (w * h)
    for cell in cells:
        px = decode_tile(face[32 * cell:32 * cell + 32])
        cx, cy = cell % FACE_W * 8, cell // FACE_W * 8
        for i, v in enumerate(px):
            out[(cy + i // 8) * w + cx + i % 8] = v
    return bytes(out)


def distinct_characters(rom: Rom) -> list[dict]:
    """Every (name, face code) of both scenarios (start, renamed and later generals) once, in order of first
    appearance."""
    from export import all_generals
    seen, out = set(), []
    for g in all_generals(rom):
        key = (g["name"], g["face_code"])
        if key not in seen:
            seen.add(key)
            out.append({"id": len(out), **g})
    return out


def build(rom_path: str) -> tuple[dict, list[bytes]]:
    rom = Rom(rom_path)
    images, blobs = [], [bytearray(), bytearray()]

    def add(px: bytes, blob: int = 0) -> int:
        w, h = CANVAS
        assert len(px) == w * h
        images.append([len(blobs[blob]), w, h, blob] if blob else [len(blobs[blob]), w, h])
        blobs[blob].extend(px)
        return len(images) - 1

    variants = []
    for head in range(COMPOSITE_HEADS):
        runs = rom.composite_runs(head)
        parts = {sid: {"items": [add(cells_image(rom.composite_page(head, p), runs[sid])) for p in range(PAGES)]}
                 for sid, _, _ in COMPOSITE_SLOTS}
        variants.append({"id": str(head), "label": f"頭 {head}", "parts": parts})

    portraits = [{"img": add(bytes(rom.face_pixels(n)), blob=1), "label": f"F{n:03d}"} for n in range(PORTRAIT_COUNT)]

    characters = []
    for c in distinct_characters(rom):
        ch = {"id": c["id"], "name": c["name"]}
        code = c["face_code"]
        if is_composite(code):
            head, pages = decode_face_code(code)
            ch["face"] = {"variant": head, "parts": pages, "code": f"{code:04X}"}
        else:
            ch["face"] = {"portrait": code}
        characters.append(ch)

    colors = [f"#{r:02x}{g:02x}{b:02x}" for r, g, b in (bgr555_rgb(c) for c in rom.face_palette())]
    meta = {
        "format": kaodata.FORMAT,
        "id": "bushou-sfc",
        "game": "NOBU4",
        "platform": "SFC",
        "title": {"ja": "スーパー信長の野望・武将風雲録", "zh": "超級信長之野望・武將風雲錄"},
        "source": {"producer": "superfamicom-re", "revision": kaodata.revision(REPO),
                   "inputs": [{"path": os.path.basename(rom_path), "sha1": hashlib.sha1(rom.data).hexdigest()}]},
        "display": {"scale": 6},
        "palettes": [{"id": "face", "label": "頭像調色盤（BG 調色盤 5）", "colors": colors}],
        "blobs": ["pixels.bin", "portraits.bin"],
        "images": images,
        "composite": {
            "canvas": list(CANVAS),
            "slots": [{"id": sid, "label": label} for sid, label, _ in COMPOSITE_SLOTS],
            "variants": variants,
            "code": {"kind": "tuple"},
        },
        "portraits": portraits,
        "characters": characters,
    }
    return meta, [bytes(b) for b in blobs]


def main() -> None:
    ap = argparse.ArgumentParser(description="匯出 kaodata 統一格式資料集 bushou-sfc")
    ap.add_argument("--rom", default=DEFAULT_ROM, help="roms/Super Nobunaga no Yabou - Bushou Fuuunroku (Japan).zip 或 .sfc")
    ap.add_argument("--out", required=True, help="輸出目錄")
    args = ap.parse_args()
    meta, blobs = build(args.rom)
    kaodata.write_dataset(args.out, meta, blobs)
    chars = meta["characters"]
    mobs = [c for c in chars if "variant" in c["face"]]
    print(f"bushou-sfc: {len(chars)} characters ({len(chars) - len(mobs)} portrait, {len(mobs)} composite), "
          f"{len(meta['composite']['variants'])} variants, {len(meta['portraits'])} portraits, "
          f"{len(meta['images'])} images")
    for name in [*meta["blobs"], "dataset.json", "checksums.json"]:
        print(f"  {name}: {os.path.getsize(os.path.join(args.out, name))} B")


if __name__ == "__main__":
    main()
