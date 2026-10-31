"""portrait-sheet/1 manifest of the face parts (needs export.py's output first).

Usage: .venv/bin/python yokoyama/parts_manifest.py
then:  .venv/bin/python -I ~/.claude/skills/portrait-sheet/render.py \
           yokoyama/output/portrait-sheet/yokoyama-parts/sheet.json yokoyama/output/portrait-sheet/yokoyama-parts/out

Every face is put together from 11 parts (rom.FACE_SLOTS). One cell per part number the 224 persons use, by kind
then number: the part alone, drawn where it sits in the 48 x 64 face by the face layout (metasprite 0), in the
palette of its first user; `sub` = how many persons use it. The last kind (飾物) is drawn only by the extra sprites
of 4 persons (rom.FACE_EXTRA): those cells show the extra sprites of their one user, tagged 專屬.
yokoyama2/parts_manifest.py reuses build().
"""
import csv
import json
import os

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
KINDS = ["頭頂", "臉", "眼", "鬍鬚", "口", "冠側", "垂飾", "冠頂", "肩", "衣領", "飾物"]
COLORS = ["#8C6D46", "#D9A066", "#3F7FBF", "#6B4C9A", "#C8475A", "#2E9E8F", "#B8860B", "#D4A017", "#5E8C31",
          "#4A6FA5", "#A23B72"]
OPTIONAL = 0xFF


def image(rgb: list, w: int, h: int) -> Image.Image:
    im = Image.new("RGBA", (w, h))
    im.putdata([(0, 0, 0, 0) if c is None else c + (255,) for c in rgb])
    return im


def build(src: str, slug: str, slot_kind: list[int], parts, part_rgb, extra_rgb, size: tuple[int, int],
          head: dict) -> None:
    """parts(p) -> part numbers per slot; part_rgb(p, k, n) -> part n (default: person p's) in slot k drawn by the
    face layout in the palette of person p;
    extra_rgb(p, k) -> the extra sprites of person p (slot k = an accessory slot), or None when no sprite draws
    slot k."""
    with open(os.path.join(src, "persons.csv"), encoding="utf-8-sig") as f:
        names = [r["名前"] for r in csv.DictReader(f)]
    out = os.path.join(src, "portrait-sheet", slug)
    os.makedirs(os.path.join(out, "parts"), exist_ok=True)
    chars = []
    for ki, kind in enumerate(KINDS):
        users: dict[int, list[tuple[int, int]]] = {}
        for p in range(len(names)):
            for k, n in enumerate(parts(p)):
                if slot_kind[k] == ki:
                    users.setdefault(n, []).append((p, k))
        users.pop(OPTIONAL, None)
        tag = {"text": kind, "color": COLORS[ki]}
        if kind != "飾物":  # numbers below the highest used one that no one uses: in the table, never shown
            for n in set(range(max(users))) - set(users):
                users[n] = []
        for n in sorted(users):
            p, k = (users[n] or next(u for u in users.values() if u))[0]
            face = f"parts/{ki:02d}_{n:02d}.png"
            ch = {"face": face, "name": f"{kind} {n:02d}"}
            if kind == "飾物":
                rgb = extra_rgb(p, k)
                ch.update(sub=names[p], tags=[tag, "專屬"])
                if rgb is None:  # loaded with the face but drawn by no sprite
                    rgb = part_rgb(p, k)
                    ch["unseen"] = True
            else:
                rgb = part_rgb(p, k, n)
                ch.update(sub=f"{len(users[n])}人", tags=[tag])
                if not users[n]:
                    ch["unseen"] = True
            image(rgb, *size).save(os.path.join(out, face))
            chars.append(ch)
    manifest = {"format": "portrait-sheet/1", "slug": slug, **head, "title_font": "lanyang-semibold",
                "title": "頭像零件", "characters": chars}
    with open(os.path.join(out, "sheet.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    print(f"{slug}: {len(chars)} parts ({sum(bool(c.get('unseen')) for c in chars)} unseen) -> {out}")


def main() -> None:
    import rom as R

    r = R.Rom()
    R.FACE_OPTIONAL = set(range(len(R.FACE_SLOTS)))   # parts() below blanks the other slots with FF
    base = r.face_parts

    def only(p, ks, part):
        return bytes((part if part is not None else n) if k in ks else OPTIONAL for k, n in enumerate(base(p)))

    def draw(p, ks, sprites, part=None):
        r.face_parts, r.face_sprites = (lambda q: only(q, ks, part)), (lambda q: sprites)
        try:
            return r.face_rgb(p)
        finally:
            del r.face_parts, r.face_sprites

    def part_rgb(p, k, n=None):
        return draw(p, {k}, r.metasprite(R.FACE_META), n)

    def extra_rgb(p, k):
        return draw(p, {k}, r.metasprite(R.FACE_EXTRA[p])) if p in R.FACE_EXTRA else None

    build(os.path.join(HERE, "output"), "yokoyama-parts", list(range(11)), base, part_rgb, extra_rgb,
          (R.FACE_W, R.FACE_H), {"game": "橫山光輝三國志", "original": "横山光輝 三国志", "platform": "ANGEL　1992　SFC",
                                 "theme": {"base": "ink", "name_font": "sourcehan-serif"}})


if __name__ == "__main__":
    main()
