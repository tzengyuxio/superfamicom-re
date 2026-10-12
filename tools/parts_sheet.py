#!/usr/bin/env python3
"""Draw every composite-face part of a kaodata dataset on one sheet (needs Pillow).

One row per variant, one column group per slot, items in dataset order.
Transparent pixels show as grey. Works for any kaodata/1 dataset with `composite`.
export_mob_parts() also writes every part as its own PNG; the game exporters call it.

Usage: .venv/bin/python tools/parts_sheet.py --dataset <dir> --out <dir> [--scale N]
"""
import argparse
import os

from kaodata import get_image, load_dataset, to_rgba
from PIL import Image, ImageDraw

GAP, LABEL_W, LABEL_H = 4, 40, 14
BG, CELL_BG, TEXT = (255, 255, 255), (160, 160, 160), (0, 0, 0)


def parts_sheet(meta: dict, blobs: list[bytes], scale: int) -> Image.Image:
    colors = meta["palettes"][0]["colors"]
    comp = meta["composite"]
    slots = [s["id"] for s in comp["slots"]]

    def image_of(item) -> int:
        return item if isinstance(item, int) else item["img"]

    # cell size per slot = largest item of that slot over all variants
    size = {s: [0, 0] for s in slots}
    count = {s: 0 for s in slots}
    for v in comp["variants"]:
        for s in slots:
            items = v["parts"][s]["items"]
            count[s] = max(count[s], len(items))
            for it in items:
                w, h, _ = get_image(meta, blobs, image_of(it))
                size[s] = [max(size[s][0], w), max(size[s][1], h)]
    row_h = max(h for _, h in size.values()) * scale + GAP
    group_w = {s: count[s] * (size[s][0] * scale + GAP) + GAP for s in slots}
    width = LABEL_W + sum(group_w.values())
    sheet = Image.new("RGB", (width, LABEL_H + row_h * len(comp["variants"]) + GAP), BG)
    draw = ImageDraw.Draw(sheet)

    x = LABEL_W
    for s in slots:
        draw.text((x + GAP, 1), s, fill=TEXT)
        x += group_w[s]
    for r, v in enumerate(comp["variants"]):
        y = LABEL_H + r * row_h + GAP
        draw.text((2, y), f"#{v['id']}", fill=TEXT)
        x = LABEL_W
        for s in slots:
            cw, ch = size[s][0] * scale, size[s][1] * scale
            for i, it in enumerate(v["parts"][s]["items"]):
                cx = x + GAP + i * (cw + GAP)
                draw.rectangle([cx, y, cx + cw - 1, y + ch - 1], fill=CELL_BG)
                src = get_image(meta, blobs, image_of(it))
                img = Image.frombytes("RGBA", src[:2], to_rgba(src, colors))
                img = img.resize((src[0] * scale, src[1] * scale), Image.NEAREST)
                sheet.paste(img, (cx, y), img)
            x += group_w[s]
    return sheet


def export_mob_parts(meta: dict, blobs: list[bytes], out_dir: str, scale: int = 4) -> None:
    """Write out_dir/mob_parts.png (sheet) and out_dir/mob_parts/<variant>_<slot>_<n>.png (each part, 1x)."""
    colors = meta["palettes"][0]["colors"]
    parts_dir = os.path.join(out_dir, "mob_parts")
    os.makedirs(parts_dir, exist_ok=True)
    count = 0
    for v in meta["composite"]["variants"]:
        for slot, sp in v["parts"].items():
            for n, it in enumerate(sp["items"]):
                src = get_image(meta, blobs, it if isinstance(it, int) else it["img"])
                Image.frombytes("RGBA", src[:2], to_rgba(src, colors)).save(
                    os.path.join(parts_dir, f"{v['id']}_{slot}_{n}.png"))
                count += 1
    parts_sheet(meta, blobs, scale).save(os.path.join(out_dir, "mob_parts.png"))
    print(f"已匯出大眾臉零件 {count} 張 → {parts_dir}，總覽 → {os.path.join(out_dir, 'mob_parts.png')}")


def main() -> None:
    ap = argparse.ArgumentParser(description="大眾臉零件總覽圖與各零件 PNG")
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--out", required=True, help="輸出目錄（寫入 mob_parts.png 與 mob_parts/）")
    ap.add_argument("--scale", type=int, default=4, help="總覽圖放大倍率")
    args = ap.parse_args()
    meta, blobs = load_dataset(args.dataset)
    export_mob_parts(meta, blobs, args.out, args.scale)


if __name__ == "__main__":
    main()
