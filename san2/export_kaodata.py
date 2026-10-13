#!/usr/bin/env python3
"""Export SFC スーパー三國志II as a kaodata dataset (san2-sfc, format kaodata/1).

Pixels are `palette * 16 + colour`: the dataset palette is the game's 4 face palettes (64 colours).
Portrait codes 1-208 use the palette the game looks up per code; composite faces carry the palette
in bits 13-14, so each composite variant is one head with one palette (8 heads x 4 = 32 variants).
Every slot has 4 items, the head's records 0-3, each a 40x48 canvas with 255 outside the slot's cells.

Usage: .venv/bin/python san2/export_kaodata.py --out <dir> [--rom ROM]
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
    COMPOSITE_TILES,
    DEFAULT_ROM,
    FACE_BYTES,
    HEAD_SIZE,
    PORTRAIT_COUNT,
    Rom,
    bgr555_rgb,
    decode_tile,
    is_composite,
    load_kanji,
)

CANVAS = (40, 48)
SURNAMES = os.path.join(HERE, "data", "surnames.tsv")
# The ROM writes some names with a stand-in kanji (or cut to 3 kanji); the dataset uses the historical spelling.
NAME_FIXES = {
    "張資": "張咨", "雷同": "雷銅", "夏侯懋": "夏侯楙", "桓楷": "桓階", "陳嬉": "陳紀", "辛毘": "辛毗",
    "李湛": "李堪", "寥化": "廖化", "歩鷙": "歩隲", "蔡仲": "蔡中", "尚拳": "向挙", "尚寵": "向寵",
    "鮑龍": "鮑隆", "朵思王": "朶思大王", "金環結": "金環三結", "沙摩可": "沙摩柯", "母丘倹": "毌丘倹",
}
READING_FIXES = {"李堪": "りかん", "朶思大王": "だしだいおう", "金環三結": "きんかんさんけつ"}
UNSPLIT = {"金環三結", "董荼奴"}  # 南蠻 names: no family / given split


def load_surnames() -> dict[str, str]:
    with open(SURNAMES, encoding="utf-8") as f:
        return dict(line.rstrip("\n").split("\t") for line in f if not line.startswith("#"))


def split_reading(name: str, kana: str, surnames: dict[str, str]) -> str:
    """'じゅん ゆう': a space after the family name's reading (compound family names first)."""
    if name in UNSPLIT:
        return kana
    for k in (2, 1):
        fam = surnames.get(name[:k])
        if fam and kana.startswith(fam) and len(kana) > len(fam):
            return f"{fam} {kana[len(fam):]}"
    return kana


def cells_image(rom: Rom, offsets: dict[int, int], palette: int) -> bytes:
    """40x48 image of the given cells {cell: tile offset}, other cells transparent."""
    w, h = CANVAS
    out = bytearray([kaodata.TRANSPARENT]) * (w * h)
    for cell, off in offsets.items():
        px = decode_tile(rom.data[off:off + 32])
        cx, cy = cell % 5 * 8, cell // 5 * 8
        for i, v in enumerate(px):
            out[(cy + i // 8) * w + cx + i % 8] = palette * 16 + v
    return bytes(out)


def build(rom_path: str) -> tuple[dict, list[bytes]]:
    rom = Rom(rom_path)
    kanji = load_kanji()
    surnames = load_surnames()
    images, blobs = [], [bytearray(), bytearray()]

    def add(px: bytes, blob: int = 0) -> int:
        w, h = CANVAS
        assert len(px) == w * h
        images.append([len(blobs[blob]), w, h, blob] if blob else [len(blobs[blob]), w, h])
        blobs[blob].extend(px)
        return len(images) - 1

    variants = []
    for pal in range(4):
        for head in range(COMPOSITE_HEADS):
            areas = rom.composite_areas(head)
            parts = {}
            for sid, _, _ in COMPOSITE_SLOTS:
                parts[sid] = {"items": [
                    add(cells_image(rom, {c: COMPOSITE_TILES + head * HEAD_SIZE + rec * FACE_BYTES + 32 * c
                                          for c in areas[sid]}, pal)) for rec in range(4)]}
            variants.append({"id": f"{head}-{pal}", "label": f"頭 {head}／色 {pal}", "parts": parts})

    portraits = []
    for code in range(1, PORTRAIT_COUNT + 1):
        px = rom.face_pixels(code)
        pal = rom.face_palette_number(code)
        portraits.append({"img": add(bytes(pal * 16 + v for v in px), blob=1), "label": f"{code:04X}"})

    characters = []
    for p in rom.persons():
        code = p["face"]
        name = "".join(kanji.get(c, "?") for c in p["kanji_codes"])
        name = NAME_FIXES.get(name, name)
        reading = READING_FIXES.get(name, kaodata.hiragana(p["reading"]))
        ch = {"id": p["id"], "name": name, "reading": split_reading(name, reading, surnames)}
        if is_composite(code):
            pal = code >> 13 & 3
            ch["face"] = {"variant": pal * COMPOSITE_HEADS + (code & 7),
                          "parts": [code >> shift & 3 for _, _, shift in COMPOSITE_SLOTS], "code": f"{code:04X}"}
        else:
            ch["face"] = {"portrait": code - 1}
        characters.append(ch)

    colors = [f"#{r:02x}{g:02x}{b:02x}" for pal in rom.face_palettes() for r, g, b in map(bgr555_rgb, pal)]
    meta = {
        "format": kaodata.FORMAT,
        "id": "san2-sfc",
        "game": "SAN2",
        "platform": "SFC",
        "title": {"ja": "スーパー三國志II", "zh": "超級三國志II"},
        "source": {"producer": "superfamicom-re", "revision": kaodata.revision(REPO),
                   "inputs": [{"path": os.path.basename(rom_path), "sha1": hashlib.sha1(rom.data).hexdigest()}]},
        "display": {"scale": 6},
        "palettes": [{"id": "face", "label": "頭像 4 組調色盤（色號＝組 × 16 ＋ 色）", "colors": colors}],
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
    ap = argparse.ArgumentParser(description="匯出 kaodata 統一格式資料集 san2-sfc")
    ap.add_argument("--rom", default=DEFAULT_ROM, help="roms/Super Sangokushi II (Japan).zip 或 .sfc")
    ap.add_argument("--out", required=True, help="輸出目錄")
    args = ap.parse_args()
    meta, blobs = build(args.rom)
    kaodata.write_dataset(args.out, meta, blobs)
    chars = meta["characters"]
    mobs = [c for c in chars if "variant" in c["face"]]
    print(f"san2-sfc: {len(chars)} characters ({len(chars) - len(mobs)} portrait, {len(mobs)} composite), "
          f"{len(meta['composite']['variants'])} variants, {len(meta['portraits'])} portraits, "
          f"{len(meta['images'])} images")
    unsplit = [c["name"] for c in chars if " " not in c["reading"]]
    print(f"  reading without family/given split: {' '.join(unsplit) or '-'}")
    for name in [*meta["blobs"], "dataset.json", "checksums.json"]:
        print(f"  {name}: {os.path.getsize(os.path.join(args.out, name))} B")


if __name__ == "__main__":
    main()
