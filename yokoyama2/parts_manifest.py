"""portrait-sheet/1 manifest of the face parts (needs export.py's output first).

Usage: .venv/bin/python yokoyama2/parts_manifest.py
then:  .venv/bin/python -I ~/.claude/skills/portrait-sheet/render.py \
           yokoyama2/output/portrait-sheet/yokoyama2-parts/sheet.json yokoyama2/output/portrait-sheet/yokoyama2-parts/out

Same sheet as yokoyama/parts_manifest.py (its build()). 12 slots: slots 10 and 11 take their parts from the same
table (飾物; the two slots use different part numbers), drawn only by the extra sprites of the 5 persons with their
own layouts (rom.FACE_META_BASE).
"""
import importlib.util
import os

import rom as R

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("parts1", os.path.join(HERE, "..", "yokoyama", "parts_manifest.py"))
parts1 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(parts1)
SLOT_KIND = list(range(11)) + [10]


def main() -> None:
    r = R.Rom()
    R.FACE_OPTIONAL = set(range(len(R.FACE_SLOTS)))   # the other slots are blanked with FF below
    base, layout = r.face_parts, r.metasprite(R.FACE_META)

    def draw(p, ks, sprites, part=None):
        r.face_parts = lambda q: bytes((part if part is not None else n) if k in ks else 0xFF
                                       for k, n in enumerate(base(q)))
        r.metasprite = lambda i: sprites
        try:
            return r.face_rgb(p)
        finally:
            del r.face_parts, r.metasprite

    def first(k):  # first 8x8 tile of slot k in the buffer
        return R.FACE_SLOTS[k][3][0] // 32

    def part_rgb(p, k, n=None):
        if k >= 10:  # no face layout draws the accessory slots: one 16x16 sprite in the middle of the box
            return draw(p, {k}, [(-8, -8, first(k), 0x30)])
        return draw(p, {k}, layout, n)

    def extra_rgb(p, k):
        if p not in R.FACE_META_BASE:
            return None
        extra = [s for s in r.metasprite(R.FACE_META_BASE[p]) if s not in layout]
        if not any(t == first(k) for _, _, t, _ in extra):
            return None
        return draw(p, {k}, extra)

    parts1.build(os.path.join(HERE, "output"), "yokoyama2-parts", SLOT_KIND, base, part_rgb, extra_rgb,
                 (R.FACE_W, R.FACE_H), {"game": "橫山光輝三國志2", "original": "横山光輝 三国志2",
                                        "platform": "ANGEL　1993　SFC",
                                        "theme": {"base": "paper", "name_font": "sourcehan-serif"}})


if __name__ == "__main__":
    main()
